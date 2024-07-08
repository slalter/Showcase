def execute(args, tool_call_id, session, feature_instance):
    '''
    get model definitions
    '''
    from models import Model
    requests = args['table_names']
    model_definitions = {}
    for request in requests:
        model = session.query(Model).filter_by(name=request).first()
        if not model:
            raise Exception(f"Model {request} not found. Make sure to use the correct name.")
        model_definitions[request] = model.code
    return str(model_definitions)
        
def getJson():
    return {
        "name": "get_model_definitions",
        "description": "get model definitions",
        "parameters": {
            "type": "object",
            "properties": {
                "table_names": {
                    "type": "array",
                    "description": "A list of the model names you want to get the definitions for.",
                    "items": {
                        "type": "string"
                    }
                }
            }
        }
    }