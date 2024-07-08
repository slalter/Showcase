import requests
import os
from datetime import datetime, timedelta
import json
api_key = os.environ['RETREAVER_API_KEY']
company_id = 123848

def getCallByID(call_id):

    from .models import Call
    response = requests.get(f'https://api.retreaver.com/calls/{call_id}.json?api_key={api_key}&company_id={company_id}')
    if response.content:
        return Call.from_json(response.json()['call'])
    else: 
        return None

def getRecentCalls(created_after:datetime, created_before:datetime, limit=10000):

    from .models import Call
    created_after = created_after.isoformat()
    created_before = created_before.isoformat()
    content = "placeholder"
    results = []
    i=1
    while content:
        if 25*i>limit:
            break
        print(f"getting page {i}")
        response = requests.get(f'https://api.retreaver.com/calls.json?api_key={api_key}&company_id={company_id}', 
                                data={
                                    'created_at_start':created_after,
                                    'created_at_end':created_before,
                                    'order': 'asc',
                                    'sort_by':'created_at',
                                    'page':i
                                })
        content = response.json()
        results += content
        i+=1 

    if response.content:
        calls = [Call.from_json(item['call']) for item in results]
        return calls
    else:
        return []

def getCampaignById(campaign_id):
    response = requests.get(f'https://api.retreaver.com/campaigns/cid/{campaign_id}.json?api_key={api_key}&company_id={company_id}')
    if response.content:
        return json.loads(response.content)['campaign']
    else: 
        return None
    

def getAffiliateById(affiliate_id):
    response = requests.get(f'https://api.retreaver.com/affiliates/afid/{affiliate_id}.json?api_key={api_key}&company_id={company_id}')
    if response.content:
        return json.loads(response.content)['affiliate']
    else: 
        return None
    

def getCallBuyerByID(buyer_id):
    response = requests.get(f'https://api.retreaver.com/call_buyers/{buyer_id}.json?api_key={api_key}&company_id={company_id}')
    if response.content:
        return json.loads(response.content)
    else: 
        return None
    
def getAllNumbers():
    '''
    returns a list of numbers, usually one per afid/cid pair but not always.
    '''
    results = []
    response = None
    content = ''
    i=1
    while(not response or content):
        content = ''
        print(f"getting number page {i}...")
        response = requests.get(f'https://api.retreaver.com/numbers.json?api_key={api_key}&company_id={company_id}&page={i}')
        i+=1
        if response.content:
            content = json.loads(response.content)
            if isinstance(content, list):
                results += content
            elif isinstance(content, dict):
                results.append(content)
            else: 
                raise Exception(f"unable to parse response! {response.content}")
            
    return results
