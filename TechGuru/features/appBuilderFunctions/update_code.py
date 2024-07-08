#this is an alternative to modify_code. The LLM seems to be doing a crappy job with insertion/deletion/replacements, so we will just replace the entire code.
#this should only be an option when the code itself is sufficiently short.
def execute(args, tool_call_id,session,feature_instance):
    '''
    modifies the code in the feature.
    '''
    from models import addLog
    code = args['code']
    #clean up the code
    code = code.replace('\t', '    ')
    code = code.replace('\r', '')

    feature_instance.code = args['code']
    feature_instance.saveCode(session)
    addLog(feature_instance.assignment.conversation_id, 'code modified', {
         'new_code':feature_instance.code
         }, session)
    session.commit()
    return 'Code modified.'
    

def getJson():
        return {
    "type": "function",
    "function": {
        "name": "update_code",
        "description": "Replace the code in your context with new code. Make sure you are careful to not omit any important information, as this will replace the entire code. This tool is for building out your assigned task, as seen in your context. Reference your requested_objects in the code, if applicable, so you can maintain a complete outline of your task.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "The new code to replace the existing code with. Use \t for tabs and \n for new lines."
                }
            }
        }
    }
}
