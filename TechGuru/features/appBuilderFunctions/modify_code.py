
def execute(args, tool_call_id,session,feature_instance):
    '''
    modifies the code in the feature.
    '''
    code_lines = feature_instance.code.split('\n')
    insertions = args.get('insertions', [])
    deletions = args.get('deletions', [])

    #execute deletions
    for line_number in deletions:
        code_lines[line_number] = 'REMOVED'
    
    #execute insertions
    for insertion in insertions:
        code_lines.insert(insertion['line_number'], insertion['string'])

    code_lines = [line for line in code_lines if line != 'REMOVED']
    feature_instance.code = '\n'.join(code_lines)
    feature_instance.saveCode(session)

    return 'Code modified.'
    

def getJson():
        return {
            "type": "function",
            "function":{
                "name": "modify_code",
                "description": "Modify the code for your assigned task via a set of insertions and deletions. Lines are flagged for deletion, insertions are made, then flagged lines are deleted (accounts for positional changes). This tool is for building out your assigned task, as seen in your context. Reference your requested_objects in the code, so you can maintain a complete outline of your task.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "insertions": {
                            "type": "array",
                            "description": "A list of string:line_number pairs to insert into the code. Whitespace in your string will be preserved.",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "line_number": {
                                        "type": "integer",
                                        "description": "The line number to insert the code at."
                                    },
                                    "string": {
                                        "type": "string",
                                        "description": "The code to insert."
                                    }
                                }
                            }

                        },
                        "deletions": {
                            "type": "array",
                            "description": "A list of line numbers to delete from the code.",
                            "items": {
                                "type": "integer"
                            }
                        }
                    }
                
            }
        }
    }