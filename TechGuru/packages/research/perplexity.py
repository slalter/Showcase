import requests
import json
import os
from models.conversation.db_conversation import addLog

url = 'https://api.perplexity.ai/chat/completions'
key = os.environ.get('PERPLEXITY_API_KEY')


def get_response(query:str, session, conversation_id = None):
    payload = {
        "temperature":0,
        "return_citations":True,
        "model": "llama-3-sonar-large-32k-online",
        "messages": [
            {
                "role": "system",
                "content": "Provide relevant and/or useful quotes and return the url of each source. Do not provide a summary. Respond with a json of url:quote pairs. Respond with exactly the json and nothing more."
            },
            {
                "role": "user",
                "content": f"Provide relevant quotes and return the url of each source. You are trying to find information to assist with non-profits in their impact reporting and grant writing, so try to find hard data like studies, papers, government forms, or other reputable sources. Respond with url:quote pairs. {query}"
            }
        ]
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "Authorization": f"Bearer {key}"
    }

    response = requests.post(url, json=payload, headers=headers)
    try:
        result = response.json()['choices'][0]['message']['content']
        if isinstance(result, str):
            try:
                result = json.loads(result)
                return {'result':result}
            except:
                return {'result':result}
        return {'result':result}
    except:
        if conversation_id:
            addLog(conversation_id, 'search decode error. returning raw response', {'content':response.text},session)
        return {'result':response.text}