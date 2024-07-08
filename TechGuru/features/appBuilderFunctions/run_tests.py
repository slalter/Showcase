
def execute(args, tool_call_id,session, feature_instance):
    '''
    TODO: implement.
    '''
    return 'automated testing is not yet available. You can skip this step.'

def getJson():{
                "type": "function",
                "function":{
                    "name": "run_test",
                    "description": "Run a test case for your assigned task.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "test_case_ids": 
                            {
                                "type": "array",
                                "description": "A list of test case ids to run.",
                                "items": {
                                    "type": "string"
                                }
                            }
                        }
                    }
                }
            }