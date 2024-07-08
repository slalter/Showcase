from packages.cloudstorage import upload_blob_from_string, download_blob_to_string, list_blobs, delete_blob
import json
from packages.models.campaign import Category, Campaign

#SCALING NOTE: making this with 'add x' instead of overwriting will be better if this scales out.

def getGlobalCategories():
    category_list = download_blob_to_string('global_categories.json')
    if not category_list:
        return createGlobalCats()
    return [Category.from_json(category) for category in json.loads(category_list)]

def saveGlobalCategories(categories: list[Category]):
    upload_blob_from_string(json.dumps([category.as_dict for category in categories]),'global_categories.json')

def createGlobalCats():
    upload_blob_from_string(json.dumps([]), 'global_categories.json')
    return []

def getGlobalFlags():
    flags = download_blob_to_string('global_flags.json')
    if not flags:
        return createGlobalFlags()
    return json.loads(download_blob_to_string('global_flags.json'))

def saveGlobalFlags(flags):
    upload_blob_from_string(json.dumps(flags), 'global_flags.json')

def createGlobalFlags():
    upload_blob_from_string(json.dumps([]), 'global_flags.json')
    return []

def getGlobalQuestions():
    questions = download_blob_to_string('global_questions.json')
    if not questions:
        return createGlobalQuestions()
    return json.loads(questions)

def saveGlobalQuestions(questions):
    upload_blob_from_string(json.dumps(questions),'global_questions.json')

def createGlobalQuestions():
    upload_blob_from_string(json.dumps([]), 'global_questions.json')
    return []

def getCriteria(campaign: Campaign):
    categories = getGlobalCategories() + campaign.categories
    flags = getGlobalFlags() + campaign.flags
    questions = getGlobalQuestions() + campaign.questions
    return categories, flags, questions

def addCallToNoneList(call, cat):
    nl = getNoneList()
    if cat == 'category':
        if call.uuid not in nl['category']:
            upload_blob_from_string(call.uuid,'nonelist/category')

    else:
        if cat == 'subcategory':
            if call.uuid not in nl['subcategory']:
                upload_blob_from_string(call.uuid,'nonelist/subcategory')

def getNoneList():
    nl = {}
    nl['category'] = list_blobs('nonelist/category/')
    nl['subcategory'] = list_blobs('nonelist/subcategory')
    return nl

def createNoneList():
    upload_blob_from_string('nonelist/','')
    upload_blob_from_string('subcategory/','nonelist/')
    upload_blob_from_string('category/','nonelist/')

def removeIdFromNoneList(id, cat):
    try:
        delete_blob(f'nonelist/{cat}/id')
    except:
        pass


def processNoneList():
    from packages.models.call import Call
    nl = getNoneList()
    
    #load calls
    calls = [Call.loadCall(id) for id in nl]

    #TODO


def checkProceduralReasons(call):
    from packages.models.call import Call
    from packages.retreaver import getCampaignById
    assert isinstance(call, Call)
    retreaver_camp = getCampaignById(call.cid)
    if retreaver_camp:
        targets = [target['target'] for target in retreaver_camp['targets'] if (target['target']['id']==call.system_target_id or not call.system_target_id)]
        tags = retreaver_camp.get('tag_values','')
        if not targets:
            pass
        else:
            foundgeo = False
            for target in targets:
                try:
                    if call.tags['geo'].split(',')[2] in str([tag['value'] for tag in target['tag_values'] if tag['key']=='geo']):
                        foundgeo=True
                except:
                    call.error_log.append("failed to check geotag!")
                    call.saveCall()
                    return None
            if not foundgeo:
                print("No matching geo.")
                return ['Not connected to buyer', 'No geo tags matched']
        if tags:
            caller_number_tags = [tag for tag in tags if tag['key']=='caller_number']
            if call.caller.replace('+','') in str([tag['value'] for tag in caller_number_tags]):
                return ['Not connected to buyer','Number was added on supression list']

    return None


def checkBillable(call):
    if call.converted:
        if call.conversion_seconds and isinstance(call.conversion_seconds,int):
            if call.conversion_seconds > 0:
                call.billable = True