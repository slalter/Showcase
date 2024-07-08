import functions_framework
import requests
from flask import make_response
@functions_framework.http
def handle_storage_trigger(request):
    """HTTP Cloud Function.
    Args:
        request (flask.Request): The request object.
        <https://flask.palletsprojects.com/en/1.1.x/api/#incoming-request-data>
    Returns:
        The response text, or any set of values that can be turned into a
        Response object using `make_response`
        <https://flask.palletsprojects.com/en/1.1.x/api/#flask.make_response>.
    """
    request_json = request.get_json(silent=True)
    request_args = request.args
    print(request_json)

    if not 'transcript' in request_json['name'] or 'cleaned' in request_json['name']:
        return make_response("not a transcript.",200)

    body = {
        'name':request_json['name']
    }
    print("posting...")
    response = requests.post('https://us-east1-ai-qa-bot-412819.cloudfunctions.net/process_transcript/process',json=body, headers={'Content-Type':'application/json'})
    print(f"result: {response.content}")
    return make_response("success", 200)
