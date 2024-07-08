from dataclasses import dataclass, asdict, field, fields
from packages.cloudstorage import upload_blob_from_string, download_blob_to_string, list_blobs, delete_blobs_with_prefix
from typing import List
import json
import uuid 
from datetime import datetime
import asyncio
from packages.guru.prompt_classes import MapCampaignPrompt
from packages import retreaver
from packages.sheets import get_sheet_data

def makeCamps():
    delete_blobs_with_prefix('campaigns/')
    data = get_sheet_data('redacted','List')
    current_camp = Campaign(name=data[0][0])
    for row in data:
        if row[0].replace('/','and') != current_camp.name:
            current_camp.save()
            current_camp = Campaign(name=row[0].replace('/','and'))
        cats = [cat for cat in current_camp.categories if cat.name==row[1]]
        if not cats:
            cat = Category(name=row[1])
            current_camp.categories.append(cat)
        else:
            cat = cats[0]
        if len(row)>=3:
            cat.subcategories.append(row[2])
    current_camp.save()

def getCampaigns():
    camplist = list_blobs('campaigns/')
    camps = []
    for blob in camplist:
        camps.append(Campaign.from_json(json.loads(download_blob_to_string(blob))))
    if not camps:
        raise Exception('No campaigns!')
    return camps

def saveCampaigns(campaigns_in):
    campaigns = campaigns_in
    upload_blob_from_string(json.dumps(campaigns),'campaigns.json')
    
def mapCampaign(campaign_id):
    campaign = retreaver.getCampaignById(campaign_id)
    prompt = MapCampaignPrompt(
        campaign_categories = [camp.name for camp in getCampaigns()],
        campaign_info = [{str(key), str(value)} for key, value in campaign.items() if key in ['name']]
    )
    log, result = asyncio.run(prompt.execute())

    if not result.get('campaign_category'):
        print(f"error! unable to map to campaign! {json.dumps(log.to_dict(), indent=4)}")
        return False
    
    else:
        addToMap(campaign_id, result['campaign_category'])

def getCampaignFromID(campaign_id):
    map = getCampaignMap()
    campaign_name = map.get(campaign_id, '')
    if campaign_name:
        return getCampaignByName(campaign_name)
    else:
        mapCampaign(campaign_id)
    map = getCampaignMap()
    campaign_name = map.get(campaign_id, '')
    if campaign_name:
        return getCampaignByName(campaign_name)
    else:
        raise Exception("somehow failed to map a campaign...")


def getCampaignMap():
    cmap = download_blob_to_string('campaign_map.json')
    if cmap:
        return json.loads(cmap)
    else:
        return createCmap()

def addToMap(campaign_id, campaign_name):
    #TODO: consider whether we need to put a lock on this.
    oldmap = getCampaignMap()
    if oldmap.get(campaign_id,''):
        raise Exception("something has gone very wrong in addToMap! the campaign_id is already mapped!")
    oldmap[campaign_id] = campaign_name
    upload_blob_from_string(json.dumps(oldmap), 'campaign_map.json')

def getCampaignByName(name):
    camp = download_blob_to_string(f'campaigns/{name}.json')
    if camp:
        return Campaign.from_json(json.loads(camp))
    else:
        raise Exception('no such campaign!')

def createCmap():
    upload_blob_from_string(json.dumps({}), 'campaign_map.json')
    return {}


@dataclass
class Category:
    name: str = ''
    subcategories: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    @classmethod
    def from_json(cls, json_data: dict):
        # Handle nested Category objects
        categories_data = json_data.get('categories', [])
        categories = [Category(**cat) for cat in categories_data] if categories_data else []
        
        # Prepare other fields
        filtered_data = {k: v for k, v in json_data.items() if k in {'flags', 'questions', 'name'}}
        filtered_data['categories'] = categories  # Add categories to filtered_data
        
        return cls(**filtered_data)

@dataclass
class Campaign:
    flags: List[str] = field(default_factory=list)
    categories: List[Category] = field(default_factory=list)
    questions: List[str] = field(default_factory=list)
    name:str = ''
    uuid:str=''

    @classmethod
    def from_json(cls, json_data: dict):
        # Handle nested Category objects
        categories_data = json_data.get('categories', [])
        categories = [Category(**cat) for cat in categories_data] if categories_data else []
        
        # Prepare other fields
        filtered_data = {k: v for k, v in json_data.items() if k in {'flags', 'questions', 'name'}}
        filtered_data['categories'] = categories  # Add categories to filtered_data
        return cls(**filtered_data)
    
    def save(self):
        upload_blob_from_string(json.dumps(asdict(self)), f'campaigns/{self.name}.json')

    @classmethod
    def load(cls, camp_name):
        txt = download_blob_to_string(f'campaigns/{camp_name}.json')
        return Campaign.from_json(json.loads(txt))

