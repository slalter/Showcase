import os
from typing import List
import requests

api_key = os.environ.get('YOU_API_KEY',None)
url = "https://chat-api.you.com/research"
'''
query:str
chat_id: uuid (str)
stream: boolean

query can include the 'site:' operator
'''

class Result:
    url:str
    name:str
    snippet:str

class YouResponse:
    answer:str
    search_results:List[Result]
    
    def __str__(self) -> str:
        return self.__dict__

def get_response(query:str, session, chat_id:str=None, stream:bool=False)->YouResponse:
    headers = {
        'x-api-key': api_key,
    }
    params = {
        'query': query
    }
    if chat_id:
        params['chat_id'] = chat_id
    if stream:
        params['stream'] = stream

    response = requests.get(url, headers=headers, params=params)
    result:YouResponse = response.json()

    print(result)
    return result