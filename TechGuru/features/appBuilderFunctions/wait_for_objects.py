def execute(args, tool_call_id, session, feature_instance):
    '''
    waits until all object_requests are filled.
    '''
    from models.code_objects.trackers.object_request import ObjectRequest
    for object_request_id in feature_instance.object_request_ids:
        feature_instance.main_object_request.wait_for(object_request_id, ObjectRequest, session)
    feature_instance.addLog('Waiting for objects', {'object_requests':[object_request.name for object_request in feature_instance.getObjectRequests(session)]})
    return "!EXTERNAL_TOOL"

def getJson():
    return {
        "type": "function",
        "function":{
            "name": "wait_for_objects",
            "description": "waits until all object_requests are filled.",
            "parameters": {
                "type": "object",
                "properties": {
                    
                }
            }
        }

    }