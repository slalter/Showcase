
def execute(args, tool_call_id,session,feature_instance):
    '''
    modifies the code in the feature.
    '''
    from models import addLog
    code_lines = feature_instance.code.split('\n')
    old_lines = code_lines.copy()
    code_lines = [(i, line) for i, line in enumerate(code_lines)]
    insertions = args.get('insertions', [])
    deletions = args.get('deletions', [])

    #execute deletions
    for deletion in deletions:
        matched_line = next((line for line in code_lines if line[0]==deletion['line_no']-1), None)
        if not matched_line:
            raise Exception(f'Line {deletion["line_no"]} not found in code.')
        code_lines[code_lines.index(matched_line)] = (deletion['line_no']-1, 'REMOVED')
    
    #execute replacements
    replacements = args.get('replacements', [])
    for replacement in replacements:
        matched_line = next((line for line in code_lines if line[0]==replacement['line_no']-1), None)
        if not matched_line:
            raise Exception(f'Line {replacement["line_no"]} not found in code.')
        code_lines[code_lines.index(matched_line)] = (replacement['line_no']-1, replacement['string'])

    #execute insertions
    for insertion in insertions:
        #find the NEXT line number and insert the new line AN ADDITONAL INDEX BEFORE it with an index of -1.
        matched_line = next((line for line in code_lines if line[0]==insertion['line_no']), None)
        if not matched_line:
            raise Exception(f'Line {insertion["line_no"]} not found in code.')
        code_lines.insert(code_lines.index(matched_line)-1, (-1,insertion['string']))

    code_lines = [line[1] for line in code_lines if line[1] != 'REMOVED']
    feature_instance.code = '\n'.join(code_lines)
    feature_instance.saveCode(session)
    addLog(feature_instance.assignment.conversation_id, 'code modified', {
         'insertions': '<br>'.join([str(i) for i in insertions]), 
         'deletions': '<br>'.join([str(d) for d in deletions]), 
            'replacements': '<br>'.join([str(r) for r in replacements]),
         'old_code':'<code><pre style="text-align:left;">'+'\n'.join([str(i) + ': ' + o for i,o in enumerate(old_lines)]) + '</pre></code>',
            'new_code':'<code><pre style="text-align:left;">'+'\n'.join([str(i) + ': ' + o for i,o in enumerate(code_lines)]) + '</pre></code>'
         }, session)
    session.commit()
    return f'Code modified. Old code: {old_lines}. New code: {code_lines}'
    

def getJson():
        return {
    "type": "function",
    "function": {
        "name": "modify_code",
        "description": "Modify the code for your assigned task via a set of insertions, deletions, and replacements. Lines are flagged for deletion, insertions are made simultaneously, replacements are made, and then flagged lines are deleted (accounts for positional changes). This tool is for building out your assigned task, as seen in your context. Reference your requested_objects in the code, so you can maintain a complete outline of your task.",
        "parameters": {
            "type": "object",
            "properties": {
                "insertions": {
                    "type": "array",
                    "description": "A list of string:line_number pairs to insert into the code. Whitespace in your string will be preserved. This does NOT remove existing lines of code.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "line_no": {
                                "type": "integer",
                                "description": "The line number to insert your code before."
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
                        "type": "object",
                        "properties": {
                            "line_no": {
                                "type": "integer",
                                "description": "The line number to delete."
                            }
                        }
                    }
                },
                "replacements":{
                    "type": "array",
                    "description": "A list of string:line_number pairs to replace in the code. Whitespace in your string will be preserved.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "line_no": {
                                "type": "integer",
                                "description": "The line number to replace the code at."
                            },
                            "string": {
                                "type": "string",
                                "description": "The code to replace."
                            }
                        }
                    }
                }
            }
        }
    }
}
