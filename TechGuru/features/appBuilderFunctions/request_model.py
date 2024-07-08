
def execute(args, tool_call_id, session,feature_instance):
    '''
    starts a request to make an object.
    '''
    from models import ObjectRequest, InputClass, OutputClass, IOPair
    name = args['name']
    description = args['description']

    object_request = ObjectRequest(
        description = description, 
        name = name, 
        object_type = 'model',
        project_id = feature_instance.project_id
        )
    session.add(object_request)
    session.commit()
    feature_instance.object_request_ids.append(object_request.id)
    object_request.fulfill()
    session.commit()
    return f"{object_request.id} requested."
    
def getJson():
    return {
                "type": "function",
                "function":{
                    "name": "request_model",
                    "description": "Request an object to be created for you, and for which your coworkers can provide any similar things they have already built.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "description": {
                                "type": "string",
                                "description": "A description of the object you want to request and its purpose, as well as any insights that may be useful for the developer."
                            },
                            "name": {
                                "type": "string",
                                "description": "The name of the object you want to request."
                            }
                            }
                        }
                    }
                }