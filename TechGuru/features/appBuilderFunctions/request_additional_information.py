def execute(args, tool_call_id, session,feature_instance):
    '''
    requests additional information.
    TODO: build this.
    '''

    return 'Use your best judgement. If you are unable to proceed, use "report_error" instead.'




def getJson():
    return {
                "type": "function",
                "function":{
                    "name": "request_additional_information",
                    "description": "Ask your task's assigner for additional information about your task. This is a LAST RESORT for when you are unable to complete the task with the information you have.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "additional_information": {
                                "type": "string",
                                "description": "A description of the additional information you need and why, as well as any snippets from your code or your research that may help illustrate your point."
                            }
                        }
                    }
                }
            }