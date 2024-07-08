from dataclasses import dataclass, asdict, field, fields
from packages.cloudstorage import upload_blob_from_string, download_blob_to_string, upload_blob_from_bytes, delete_blobs_with_prefix
from typing import List, Optional, Tuple
import json
import uuid 
from datetime import datetime
import requests
from packages.models.campaign import getCampaignFromID
from packages.models.campaign import Category
from packages.retreaver import getCallByID
#note: this doesn't handle situations where multiple processes at once are trying to modify a call.
#the program is designed as such.


@dataclass
class Call:
    transcript:str = ''
    category:Category = None
    subcategory:str = ''
    summary:str = ''
    flags: List[str] = field(default_factory=list)
    language:str = 'english'
    questions:List[Tuple[str, ...]] = field(default_factory=list)
    db_created_at: str = datetime.utcnow().isoformat()
    error_log: List[str]= field(default_factory=list)
    billable:bool = False
    ai_status:str = 'awaiting_transcription'
    connected_to: str = ''

    #retreaver fields
    uuid: str = ''
    system_target_id: int = 0
    system_campaign_id: str = ''
    caller: str = ''
    start_time: str = ''
    forwarded_time: str = ''
    end_time: str = ''
    cid: str = ''
    afid: str = ''
    sid: Optional[str] = None
    dialed_number: str = ''
    updated_at: str = ''
    recording_url: str = ''
    caller_number_sent:str = ''
    ivr_duration:str = ''
    hold_duration:str = ''
    revenue: str = ''
    payout: str = ''
    created_at: str = ''
    postback_value: str = ''
    network_sale_timer_fired: bool = False
    affiliate_sale_timer_fired: bool = False
    target_sale_timer_fired: bool = False
    hung_up_by: str = ''
    duplicate: bool = False
    payable_duplicate: bool = False
    receivable_duplicate: bool = False
    callpixels_target_id: str = ''
    system_target_id: str = ''
    system_campaign_id: str = ''
    system_affiliate_id: str = ''
    fired_pixels_count: int = 0
    charge_total: str = 0
    keys_pressed: str = ''
    repeat: bool = False
    affiliate_repeat: bool = False
    target_repeat: bool = False
    number_repeat: bool = False
    visitor_url: str = ''
    company_id: str = ''
    conversions_determined_at: str = ''
    billable_minutes: int = 0
    upstream_call_uuid: str = ''
    downstream_call_uuids: List[str] = field(default_factory=list)
    target_group: str = ''
    number: str = ''
    converted: bool = False
    payable: bool = False
    receivable: bool = False
    conversion_seconds: int = 0
    tid: str = ''
    tags: List[str] = field(default_factory=list)
    fired_pixels: List[str] = field(default_factory=list)
    via: str = ''
    
    def getMetadata(self):
        result = [{key:value} for key, value, in self.to_dict().items() if key in ['start_time','end_time','receivable','affiliate_repeat','number_repeat','target_repeat','repeat','hung_up_by', 'connected_to']]
        for key, value in self.tags.items():
            if key == 'caller_number':
                self.addLog(f"removed a tag with key: {key}")
                continue
            if len(str(value))<1000:
                result.append({str(key):str(value)})
            else: 
                self.addLog(f"removed a tag with key: {key}")

        for pix in self.fired_pixels:
            for key, value in pix.items():
                if len(str(value))<1000:
                    result.append({str(key), str(value)})
                else: 
                    self.addLog(f"removed a pix with url: {value['url']}")
        return result
    
    @classmethod
    def loadCall(cls, call_id):
        call = download_blob_to_string(f'calls/{call_id}/call.json')
        if not call:
            rcall = getCallByID(call_id)
            return rcall
        else:
            result = json.loads(call)
            return cls(**result)
    
    def saveCall(self):
        upload_blob_from_string(json.dumps(asdict(self)),f'calls/{self.uuid}/call.json')

    def deleteCall(self):
        delete_blobs_with_prefix(f'calls/{self.uuid}')

    def to_dict(self):
        return asdict(self)
    
    def getAudio(self):
        if self.recording_url:
            try:
                response = requests.get(self.recording_url)
                response.raise_for_status()
                upload_blob_from_bytes(response.content, f'calls/{self.uuid}/audio.mp3')
                return True
            except Exception as e:
                print(f"error getting audio: {e}")
                self.addLog(f"error getting audio: {e}")
                return False
        else:
            return False

    def addLog(self, log):
        self.error_log.append(str(log))

    def getCampaign(self):
        return getCampaignFromID(self.cid)
    
    def getConnectedTo(self):
        from packages.retreaver import getCampaignById
        campaign = getCampaignById(self.cid)
        buyers = [t['target'] for t in campaign['targets'] if t['target']['id']==self.system_target_id]
        if buyers:
            self.connected_to = buyers[0]['number']

    @classmethod
    def from_json(cls, json_data: dict):
        # Get field names of the Call class
        valid_field_names = {f.name for f in fields(cls)}
        # Filter the input JSON data
        filtered_data = {k: v for k, v in json_data.items() if k in valid_field_names}
        result = cls(**filtered_data)
        result.getConnectedTo()
        return result
    
    def queueTranscript(self):
        from packages import speech
        speech.queueTranscript(self)
    
    

def setPulledTimestamp(timestamp:datetime):
    return upload_blob_from_string(timestamp.isoformat(),f'processed_timestamp.txt')

def getPulledTimestamp():
    return datetime.fromisoformat(download_blob_to_string(f'processed_timestamp.txt'))


def cleanTranscript(text):
    content = json.loads(text)
    out = []
    for result in content['results']:
        if not isinstance(result, dict):
            continue
        for alternative in result.get('alternatives', []):
            out.append(str(alternative['transcript']))

    return '\n'.join(out)