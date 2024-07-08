from flask import Flask, make_response, request
from functions_wrapper import entrypoint
import os
from collections import OrderedDict
from flask_cors import CORS
from google.cloud import secretmanager
import asyncio
import json
import uuid
import time
from datetime import datetime, timedelta
import traceback

#TODO: queue for retry
#TODO: if the camp is really old, do something
#TODO: retroactive questions
#TODO: questions on a per-category basis
#TODO: talk about hallucinations
#os.environ['debug'] = "True"
def access_secret_version(secret_id):
    """
    Accesses a secret version's payload.
    """

    project_id = 148921504269
    #project_id = os.environ.get('GCP_PROJECT')  # Automatically set by Cloud Function
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")

from dotenv import load_dotenv
load_dotenv('env')
os.environ['DEFAULT_MODEL'] = 'gpt-4-turbo-preview'
os.environ['GLLM_MODE'] = 'OPEN_AI'
os.environ['GLLM_LOGGING_PATH'] = ''

import guru
from guru.GLLM import prompt_loader

if not os.environ.get('PRODUCTION'):
    prompt_loader.run('packages/guru/prompt_classes.py','packages/guru/prompts')

from packages.guru.prompt_classes import CategorizeTranscriptPrompt, SubcategorizeTranscriptPrompt, CatAndSubcatTranscriptPrompt

from packages.categorization import getCriteria, addCallToNoneList, checkProceduralReasons, checkBillable
from packages.models.call import Call, getPulledTimestamp, setPulledTimestamp
from packages.models.campaign import Campaign, Category
from packages.retreaver import getRecentCalls
from packages.UI.admin import baseHTML
from packages.sheets import logCallInSheets
from packages.cloudstorage import getTranscriptFromBucket, delete_blobs_with_prefix, delete_old_blobs
from packages.models.logs import markFailedTranscriptProcessing, retryFailed, removeFailedCall

app = Flask(__name__)
CORS(app,methods=['GET','POST'])

@app.route("/admin", methods = ['GET'])
def base_ui():
    if request.method == 'GET':
        return baseHTML()

@app.route("/admin/<campaign_name>", methods = ['GET', 'POST'])
def campaign_ui(campaign_name):
    if request.method == 'GET':
        return baseHTML(campaign_name=campaign_name)

    if request.method == 'POST':
        print(request.json)
        data = request.json
        camp = Campaign.load(data['campaignName'])

        categories = []
        for category in data['categories']:
            if category:
                categories.append(Category(name=category['name']))
                for subcategory in category['subcategories']:
                    if subcategory:
                        categories[-1].subcategories.append(subcategory)
        camp.categories = categories

        camp.flags = data['flags']
        camp.questions = data['questions']
        camp.save()
        return make_response("successfully saved.",200)

@app.route("/reset", methods = ['GET'])
def reset():
    from packages.retreaver import getRecentCalls
    from datetime import datetime
    from packages.speech import queueTranscript
    from packages.models.campaign import makeCamps
    from packages.models.campaign import Category
    from packages.cloudstorage import upload_blob_from_string
    from packages.sheets import extract_date, ensureSheetExistence
    from packages.categorization import saveGlobalFlags
    makeCamps()
    saveGlobalFlags(['Excessive Rudeness','Potential Prank Call', 'Potential Litigator', 'Requested Do Not Call', 'Claimed to be on Do Not Call list'])
    calls = getRecentCalls(datetime(2024, 2, 5, 0, 0, 0),datetime(2024, 2, 5, 15, 0, 0) )
    start_date = extract_date(calls[0].created_at)
    end_date = extract_date(calls[1].created_at)
    ensureSheetExistence(start_date)
    if start_date != end_date:
        ensureSheetExistence(end_date)

    
    for i, call in enumerate(calls):
        print(f"processing call {i} of {len(calls)}...")
        if call.getAudio():
            print("queuing transcript...")
            queueTranscript(call)
        else:
            checkBillable(call)
            pr = checkProceduralReasons(call)
            if pr:
                call.category = Category(name=pr[0])
                call.subcategory= pr[1]
                call.ai_status = 'complete'
                logCallInSheets(call)
            else:
                upload_blob_from_string(json.dumps({'results':'No transcript Available.'}),f'calls/{call.uuid}/transcript/transcript.json')
        call.saveCall()
    
@app.route("/cron", methods = ['POST'])
def run_cron():
    from packages.retreaver import getRecentCalls
    from datetime import datetime
    from packages.speech import queueTranscript
    from packages.models.campaign import Category
    from packages.models.logs import BatchReport, FailedAttempt
    from packages.cloudstorage import upload_blob_from_string
    from packages.sheets import extract_date, ensureSheetExistence
    delete_old_blobs('calls/',5)
    delete_old_blobs('batch_reports/',5)
    delete_old_blobs('failed_process_transcript/',3)
    prevTime = getPulledTimestamp()
    calls = getRecentCalls(prevTime, datetime.utcnow()-timedelta(minutes=20), limit=80)
    if not calls:
        return make_response("no calls to process!",200)
    stamp = datetime.strptime(calls[-1].created_at, '%Y-%m-%dT%H:%M:%S.%fZ')
    if datetime.utcnow().date() != (datetime.utcnow()-timedelta(minutes=20)).date():
        retryFailed()
    setPulledTimestamp(stamp)
    br = BatchReport()
    br.range_start = datetime.strptime(calls[0].created_at, '%Y-%m-%dT%H:%M:%S.%fZ').isoformat()
    start_date = extract_date(calls[0].created_at)
    end_date = extract_date(calls[-1].created_at)
    ensureSheetExistence(start_date)
    if start_date != end_date:
        ensureSheetExistence(end_date)
    max_timestamp = None
    try:
        for i, call in enumerate(calls):
            try:
                print(f"processing call {i} of {len(calls)}...")
                if call.getAudio():
                    print("queuing transcript...")
                    queueTranscript(call)
                else:
                    checkBillable(call)
                    pr = checkProceduralReasons(call)
                    if pr:
                        call.category = Category(name=pr[0])
                        call.subcategory= pr[1]
                        call.ai_status = 'complete'
                        logCallInSheets(call)
                    else:
                        upload_blob_from_string(json.dumps({'results':'No transcript Available.'}),f'calls/{call.uuid}/transcript/transcript.json')
                call.saveCall()
                br.succeeded_calls.append(call.uuid)
            except Exception as e:
                br.failed_calls.append(FailedAttempt(call_id=call.uuid, error = traceback.format_exception(e)))
            finally:
                print(f"setting timestamp: {calls[i].created_at}")
                stamp = datetime.strptime(calls[i].created_at, '%Y-%m-%dT%H:%M:%S.%fZ')
                if not max_timestamp:
                    max_timestamp = stamp
                if max_timestamp<= stamp:
                    max_timestamp = stamp
                    br.range_end = max_timestamp.isoformat()
                    
    except Exception as e:
        print("failed to finish! creating log...")
        br.failed_calls.append(FailedAttempt(call_id='outside error!', error=traceback.format_exception(e)))
        setPulledTimestamp(stamp)
    finally:
        br.range_end = max_timestamp.isoformat()
        br.completed_at = datetime.utcnow().isoformat()
        br.save()
        return make_response("complete", 200)
          



@app.route("/process",methods= ['GET','POST'])
def process_transcript():
    try:
        from packages.models.campaign import Category
        from packages.models.call import cleanTranscript
        print(f"request: {request.json}",flush=True)
        jsonIn = request.json
        key = jsonIn['name']
        call_id = key.split('/')[1]
        text = getTranscriptFromBucket(key)
        transcript = cleanTranscript(text)
        call_logs = []

        call = Call.loadCall(call_id)
        call.transcript = transcript
    
        #quick locking mechanism...
        if call.ai_status != 'awaiting_transcription':
            print(f"incorrect state: {call.ai_status}")
            return(f"incorrect state: {call.ai_status}", 204)
        task_id = str(uuid.uuid4())
        call.ai_status = task_id
        call.saveCall()
        time.sleep(0.5)
        
        call = Call.loadCall(call_id)
        if call.ai_status != task_id:
            print(f"being processed by another task: {call.ai_status}")
            return(f"being processed by another task: {call.ai_status}", 204)

        
        #remove audio to save space
        delete_blobs_with_prefix(f'calls/{call.uuid}/audio')

        campaign = call.getCampaign()
        categories, flags, questions = getCriteria(campaign)

        checkBillable(call)
        pr = checkProceduralReasons(call)
        if pr:
            call.category = [cat for cat in categories if cat.name == pr[0]][0]
            call.subcategory = pr[1]
            call.ai_status = 'complete'
            logCallInSheets(call)
            call.saveCall()
            return make_response("logged due to procedural reasons", 200)

        prompt = CatAndSubcatTranscriptPrompt(
            categories = [{category.name:category.subcategories} for category in categories],
            flags = flags,
            questions = questions,
            conversation_text=text,
            metadata = call.getMetadata()
            )
        try:
            log, result = asyncio.run(prompt.execute())
        except Exception as e:
            try:
                log, result = asyncio.run(prompt.execute(model='gpt-4-turbo-preview'))
            except Exception as e:
                call_logs.append(f"failed to categorize due to {e}")
        call_logs.append(log)
        if result.get('flags',''):
            call.flags += [flag for flag in result.get('flags')]
            processFlaggedCall(call)

        call.summary = result['summary']
        call.questions = [(question, answer) for question, answer in zip(questions, result['answers'])] if result.get('answers','') else []

        if result.get('category', ''):
            category = [category for category in categories if category.name == result.get('category')]
            if not category:
                addCallToNoneList(call, 'category')
                call.category = Category(name = "other: " + result.get('category'))
                call.subcategory = "other: " + result.get('subcategory')
            else:
                call.category = category[0]
                if result.get('subcategory', ''):
                        call.subcategory = result.get('subcategory')
                        if call.subcategory not in call.category.subcategories:
                            call.subcategory = f'other: {call.subcategory}'
                            addCallToNoneList(call, 'subcategory')
                else: 
                        call.ai_status = 'error'
                        call.error_log.append("LLM did not provide a subcategory.")
                        call.subcategory = ''
        else:
            call.ai_status = 'error'
            call.error_log.append("LLM did not provide a category.")
            call.category = Category(name='NOT PROVIDED.')
                

        '''prompt = CategorizeTranscriptPrompt(
            categories = [category.name for category in categories],
            flags = flags,
            questions = questions,
            conversation_text=text,
            metadata = call.getMetadata()
        )
        try:
            log, result = asyncio.run(prompt.execute())
        except Exception as e:
            try:
                log, result = asyncio.run(prompt.execute(model='gpt-4-turbo-preview'))
            except Exception as e:
                call_logs.append(f"failed to categorize due to {e}")

        call_logs.append(log)
        if result.get('flags',''):
            call.flags += [flag for flag in result.get('flags')]
            processFlaggedCall(call)

        call.summary = result['summary']
        call.questions = [(question, answer) for question, answer in zip(questions, result['answers'])] if result.get('answers','') else []
        #categorize call. Note: if the main category results in 'Other,' then the subcategory is the initial category.
        #if the call is marked as NoneList, but also has a category and a subcategory, then that means that the call DID fit in a main cat, just not a subcat.
        if result.get('category', ''):
            category = [category for category in categories if category.name == result.get('category')]
            if not category:
                addCallToNoneList(call)
                call.subcategory = result.get('category')
                other_category = [category for category in categories if category.name=='Other']
                if not other_category:
                    call.category = Category(name='Other')
                else:
                    call.category = other_category[0]
            else:
                call.category = [category for category in categories if category.name==result.get('category')][0]
                print(f"\ncall categorized.\n {json.dumps(call.to_dict(), indent=4)}")
                if call.category.subcategories:
                    prompt = SubcategorizeTranscriptPrompt(
                        category = call.category.name,
                        categories = call.category.subcategories,
                        metadata = call.getMetadata(),
                        conversation_text=text
                    )

                    try:
                        log, result = asyncio.run(prompt.execute())
                    except Exception as e:
                        try:
                            log, result = asyncio.run(prompt.execute(model='gpt-4-turbo-preview'))
                        except Exception as e:
                            call_logs.append(f"failed to categorize due to {e}")
                    call_logs.append(log)
                    if result.get('subcategory', ''):
                        call.subcategory = result.get('subcategory')
                        if call.subcategory not in call.category.subcategories:
                            call.subcategory = f'other: {call.subcategory}'
                            addCallToNoneList(call)
                    else: 
                        call.ai_status = 'error'
                        call.error_log.append("LLM did not provide a subcategory.")
                        raise Exception("LLM DID NOT PROVIDE A SUBCATEGORY.")
        else:
            call.ai_status = 'error'
            call.error_log.append("LLM did not provide a category.")
            raise Exception("LLM DID NOT PROVIDE A CATEGORY.")'''
        
        if 'successful sale' in (str(call.category.name).lower() + call.subcategory.lower()):
            call.billable = True
        
        call.ai_status = 'complete'
        call.saveCall()
        logCallInSheets(call, call_logs)
    except Exception as e:
        try:
            call.ai_status = 'error'
            call.error_log.append(f"Error in processing: {traceback.format_exception(e)}")
            call.saveCall()
            logCallInSheets(call)
            removeFailedCall(call.uuid)
        except Exception as e:
            print(f"unable to log errored call!{e}")
            markFailedTranscriptProcessing(call.uuid, str(e))
            call.ai_status = 'error'
            raise e

    return make_response('success', 200)




def processFlaggedCall(call):
    #update google sheets, whatever else... #TODO
    pass





app_wrap = lambda request: entrypoint(app, request)


if not os.environ.get('PRODUCTION'):
    #test code here
    from packages.retreaver import getRecentCalls, getCallByID, getCampaignById, getAffiliateById, getCallBuyerByID
    from datetime import datetime, timedelta
    from packages.speech import queueTranscript
    from packages.models.campaign import makeCamps, getCampaigns
    from packages.models.campaign import Category
    from packages.cloudstorage import upload_blob_from_string, delete_old_blobs
    from packages.sheets import extract_date, ensureSheetExistence
    from packages.categorization import saveGlobalFlags

    print(getCallByID('0a97b61c-dc24-494b-9f55-05fca8f4ecc1'))
    #campaign = getCampaignById('ab4c697a')
    #print(campaign)
    #makeCamps()
    '''print(getAffiliateById('9d57ba9b'))
    campaign = getCampaignById('ab4c697a')
    call = getCallByID('df10ccd3-8201-4122-8937-07708755ea61')
    buyers = [t['target']['id'] for t in campaign['targets']]
    print(len(buyers))
    print(buyers)
    buyers = [t['target'] for t in campaign['targets'] if t['target']['id']==call.system_target_id]
    number = getNumberByIds(call.afid, call.cid)
    print(number['number']['name'])
    makeCamps()'''

    '''delete_old_blobs('calls',0)
    delete_old_blobs('batch_reports',0)
    setPulledTimestamp(datetime(2024, 2, 19, 0, 0, 0))'''
    '''calls = getRecentCalls(datetime(2024, 2, 19, 12, 0, 0),datetime(2024, 2, 19, 16, 0, 0) )
    start_date = extract_date(calls[0].created_at)
    end_date = extract_date(calls[-1].created_at)
    ensureSheetExistence(start_date)
    if start_date != end_date:
        ensureSheetExistence(end_date)

    
    for i, call in enumerate(calls):
        print(f"processing call {i} of {len(calls)}...")
        if call.getAudio():
            print("queuing transcript...")
            queueTranscript(call)
        else:
            checkBillable(call)
            pr = checkProceduralReasons(call)
            if pr:
                call.category = Category(name=pr[0])
                call.subcategory= pr[1]
                call.ai_status = 'complete'
                logCallInSheets(call)
            else:
                upload_blob_from_string(json.dumps({'results':'No transcript Available.'}),f'calls/{call.uuid}/transcript/transcript.json')
        call.saveCall()'''
    

    #print(getCallByID('e4847421-5cdd-4f9a-b8cb-362e654fe7a9'))
    #print(getCampaignById('43fe08c2'))
    '''getting numbername
    target = 83559
    camp = getCampaignById('43fe08c2')
    matches = [camp['target'] for camp in camp['targets'] if camp['target']['id']==target]
    print(matches)
    print(len(matches))
    did = ""
    #print(getCampaignById('43fe08c2'))
    #print(getAffiliateById('90096174'))
    numbers = getNumbersByIds('98d42a6e','b5ac97e2')
    print(numbers)
    print('\n')
    print(did)
    print('\n')
    print('\n'.join([number['number']['number'] for number in numbers]))
    print([number for number in numbers if number['number']['number']==did])'''

    #print(getNumberByNumber('5082971'))
    '''
    call = Call.loadCall('59ecd963-4c6a-407c-a39b-d2503562bf29')
    print(call.fired_pixels)
 
    queueTranscript(call)
    call.saveCall()
    print(call.getCampaign())
    print(call.cid)
    print(call.system_campaign_id)'''


    '''
'''
