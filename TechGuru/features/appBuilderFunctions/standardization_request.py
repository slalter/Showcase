
def execute(args, tool_call_id, session,feature_instance):
    '''
    Request a standardization across the codebase. For example, you may want to standardize how sessions are managed, how logging is done, or how errors are handled.
    '''
    from models import DesignDecision
    description = args['description']
    relevant_for_list = args['relevant_for_list']
    result = DesignDecision.processRequest(
        session = session,
        description = description,
        relevant_for_list = relevant_for_list,
        project_id = feature_instance.project_id,
        conversation_id = feature_instance.assignment.conversation_id,
    )
    feature_instance.design_decision_ids.append(result.id)
    return 'Standardization added to context.'

def getJson():
    return {
                "type": "function",
                "function":{
                    "name": "standardization_request",
                    "description": "Request a standardization across the codebase. For example, you may want to standardize how sessions are managed, how logging is done, or how errors are handled. This should NOT be used in cases where production code needs to be generated - it is just for high-level decisions and docs.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "description": {
                                "type": "string",
                                "description": "A description of the standardization you want to request."
                            },
                            "relevant_for_list":{
                                "type": "array",
                                "description": "A list of the objects, code, or general tasks that this standardization is relevant for. Semantic similarity will be used to prodvide this to developers who need it.",
                                "items": {
                                    "type": "string"
                                }
                            }
                        }
                    }
                }
            }