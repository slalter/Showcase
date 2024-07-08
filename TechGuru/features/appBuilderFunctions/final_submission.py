def execute(args, tool_call_id, session, feature_instance):
    '''
    submits the final code. marks the object request as complete.
    '''
    from models import ObjectRequest
    object_request_id = feature_instance.main_object_request_id
    object_request = session.query(ObjectRequest).filter(ObjectRequest.id == object_request_id).first()
    if object_request is None:
        raise Exception(f"Object request with id {object_request_id} not found.")
    assert(isinstance(object_request, ObjectRequest))
    object_request.setStatus(status = 'fulfilled',session=session)
    session.commit()
    return f"Object request {object_request_id} completed."

def getJson():
    return {
                "type": "function",
                "function":{
                    "name": "final_submission",
                    "description": "Submits the final code. Marks the object as complete.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }

            }