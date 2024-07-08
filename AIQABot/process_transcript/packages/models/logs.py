from dataclasses import dataclass, asdict, field, fields
from packages.cloudstorage import list_blobs, upload_blob_from_string, download_blob_to_string, upload_blob_from_bytes, delete_blobs_with_prefix
from typing import List, Optional, Tuple
import json
import uuid 
from datetime import datetime, timedelta
import traceback





@dataclass
class FailedAttempt:
    call_id:str = ''
    error:str = ''

    def get(self):
        from models.call import Call
        call= Call.loadCall(self.call_id)
        return [self.error] + call.error_log
    

@dataclass
class BatchReport:
    id:int = 0
    log:List[str] = field(default_factory=list)
    failed_calls: List[FailedAttempt] = field(default_factory=list)
    succeeded_calls: List[str] = field(default_factory=list)
    created_at: str = datetime.utcnow().isoformat()
    range_start: str = ''
    range_end: str = ''
    completed_at: str = ''
    
    

    @classmethod
    def load(cls, report_id):
        call = download_blob_to_string(f'batch_reports/{report_id}.json')
        if not call:
            return None
        result = json.loads(call)
        return cls(**result)
    
    @classmethod
    def from_json(cls, json_data: dict):
        valid_field_names = {f.name for f in fields(cls)}
        # Filter the input JSON data
        filtered_data = {k: v for k, v in json_data.items() if k in valid_field_names}
        result = cls(**filtered_data)
        return result

    @staticmethod
    def getMostRecent():
        txt = list_blobs(prefix = 'counters/batch_report')
        if not txt:
            return None
        else:
            num = int(txt[0])

        return BatchReport.load(num)
    
    def save(self):
        if self.id == -1:
            upload_blob_from_string(json.dumps(asdict(self)),f'batch_reports/{self.id}.json')
            return
        txt = list_blobs(prefix = 'counters/batch_report')
        if not txt:
            num = 0
        else:
            num = int(txt[0].split('/')[2])
            if num >=self.id and self.id!=0:
                upload_blob_from_string(json.dumps(asdict(self)),f'batch_reports/{self.id}ERROR.json')
                raise Exception("Duplicate BatchReport! this should never happen! saved as self.idERROR.json.")
        num += 1 
        delete_blobs_with_prefix('counters/batch_report')
        upload_blob_from_string('', f'counters/batch_report/{num}')
        self.id = num
        upload_blob_from_string(json.dumps(asdict(self)),f'batch_reports/{self.id}.json')
        for failed in self.failed_calls:
            markFailedTranscriptProcessing(failed.call_id, failed.error)

    def delete(self):
        delete_blobs_with_prefix(f'batch_reports/{self.uuid}')

    def to_dict(self):
        return asdict(self)
    
    @staticmethod
    def getAll():
        results = []
        for blob in list_blobs('batch_reports/'):
            br = BatchReport.from_json(json.loads(download_blob_to_string(blob)))
            results.append({
                'succeeded count': len(br.succeeded_calls),
                'failed count': len(br.failed_calls),
                'first call time': br.range_start,
                'last call time': br.range_end,
                'started at': br.created_at,
                'completed at': br.completed_at
            })

        # Sort the list of dictionaries by 'started at' in descending order
        sorted_results = sorted(results, key=lambda x: x['started at'], reverse=True)

        # (Optional) Convert the sorted list of dictionaries back to JSON strings if needed
        sorted_results_json = [json.dumps(result) for result in sorted_results]

        return sorted_results_json

def markFailedTranscriptProcessing(cid, error,try_num=0):
    upload_blob_from_string(str(error), f'failed_process_transcript/{datetime.utcnow().strftime("%m.%d.%Y")}/{cid}{f"/try={try_num}"}.txt')

def removeFailedCall(cid):
    bucket_path = f"failed_process_transcript/"


    # List all blobs/files in the specified directory
    for blob in list_blobs(bucket_path):
        if cid in blob:
            blob.delete()


def getFailedTranscriptProcessesByDate(m, d, y):
    '''
    returns {
    uuid:[{try: i, error: error}]
    }
    
    '''
    # Format the date as mm/dd/yyyy
    date_path = f"{m:02d}.{d:02d}.{y}"
    bucket_path = f"failed_process_transcript/{date_path}"

    # Initialize a list to hold the retrieved transcript processes
    failed_processes = {}

    # List all blobs/files in the specified directory
    for blob in list_blobs(bucket_path):
        try:
            content = download_blob_to_string(blob)
            split = blob.split('/try=')
            try_num = split[1].replace('.txt','')
            call_id = split[0]
            if failed_processes.get(call_id, ''):
                failed_processes[call_id].append({'try':try_num, 'error':content})
            else:
                failed_processes[call_id]=[{'try':try_num, 'error':content}]
        except Exception as e:
            print(f"unable to failed transcript!{blob}")

    return failed_processes


def retryFailed(max_retries = 1):
    from models.call import getCallByID
    from speech import queueTranscript
    from packages.speech import queueTranscript
    from packages.models.campaign import Category
    from packages.cloudstorage import upload_blob_from_string
    from packages.sheets import logCallInSheets
    from packages.categorization import checkProceduralReasons, checkBillable
    print("checking for failed transcriptions in the last 24 hours...")
    # Calculate yesterday's date
    yesterday = datetime.now() - timedelta(days=1)
    m, d, y = yesterday.month, yesterday.day, yesterday.year
    
    # Call the function with the calculated arguments
    failed = getFailedTranscriptProcessesByDate(m, d, y)
    for id, attempts in failed.items():
        if len(attempts)<=max_retries:
            try:
                call = getCallByID(id)
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
                        removeFailedCall(call.uuid)
                        logCallInSheets(call)
                    else:
                        upload_blob_from_string(json.dumps({'results':'No transcript Available.'}),f'calls/{call.uuid}/transcript/transcript.json')
                call.saveCall()
            except Exception as e:
                markFailedTranscriptProcessing(call.uuid, traceback.format_exception(e), try_num=len(attempts)+1)
            