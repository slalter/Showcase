import requests
import json
from openai import OpenAI
import os 
from models.conversation.db_conversation import addLog

def get_response(query, session, conversation_id=None, num_results = 6):
    try:
        search_url = "https://api.bing.microsoft.com/v7.0/search"
        headers = {"Ocp-Apim-Subscription-Key": os.environ.get('BING_SEARCH_KEY')}
        params = {"q": query, "count": num_results, "textDecorations": True, "textFormat": "Raw"}
        response = requests.get(search_url, headers=headers, params=params)
        response.raise_for_status()
        search_results = response.json()
        top_results = []
        for i, result in enumerate(search_results["webPages"]["value"]):
            top_results.append(
                {
                    "index": i + 1,
                    "url": result["url"],
                    "snippet": result["snippet"],
                }
            )
        if conversation_id:
            addLog(conversation_id, 'search', {'query':query,'search_results':top_results}, session)
    except Exception as e:
        if conversation_id:
            addLog(conversation_id, 'search error', {'query':query,'error':str(e)}, session)
        return {'error':str(e)}
    return {'results':top_results}