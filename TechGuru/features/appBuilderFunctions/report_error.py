from packages.guru.Flows.utils import CannotProceedException

def execute(args, tool_call_id, session, feature_instance):
    '''
    reports an error.
    '''
    feature_instance.addLog('error in tool execution', {
        'toolName': 'report_error',
        'args': args,
        'tool_call_id': tool_call_id,
        'error': args['error']
    },
    session)
    session.commit()
    raise CannotProceedException('error reported')

def getJson():
    return {
                "type": "function",
                "function":{
                    "name": "report_error",
                    "description": "Report an error in your assigned task. This is a LAST RESORT for when you are unable to complete the task with the information you have.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "error": {
                                "type": "string",
                                "description": "A description of the error you encountered and why, as well as any snippets from your code or your research that may help illustrate your point."
                            }
                        }
                    }
                }
            }