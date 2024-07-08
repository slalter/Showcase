def execute(args, tool_call_id, session, feature_instance):
    '''
    submits code.
    '''
    pypi_packages = args['required_pypi_packages']
    code = feature_instance.code

    if feature_instance.file_path:
        with open(feature_instance.file_path, 'w') as f:
            f.write(code)
        return 'code submitted'

    from models import Model, Method, ObjectRequest
    #create the CodeObject.
    object_request = feature_instance.main_object_request
    object_requests:list[ObjectRequest] = feature_instance.getObjectRequests(session)
    used_object_requests = [object_request for object_request in object_requests if object_request.name in code]
    if any([object_request.status != 'fulfilled' for object_request in used_object_requests]):
        raise Exception('You cannot submit code until all dependencies have been completed. We are still waiting for the following object requests to be fulfilled: ' + ', '.join([object_request.name for object_request in used_object_requests if object_request.status != 'fulfilled']))
    used_object_model_ids = [object_request.code_object_id for object_request in used_object_requests]
    if object_request.object_type == 'Model':
        #verify no Models have the same name.
        original_name = object_request.name
        i=0
        while session.query(Model).filter_by(name = object_request.name).first():
            i+=1
            object_request.name = original_name + '_' + str(i)

        new_object = Model(
            code = args['code'],
            object_request_id = object_request.id,
            object_request = object_request,
            name = object_request.name,
            pip_packages = pypi_packages,
            docString = args['docString'],
            project_id = object_request.project_id,
            dependencies = used_object_model_ids
        )

    elif object_request.object_type == 'Method':
        #verify no Methods have the same name.
        original_name = object_request.name
        i=0
        while session.query(Method).filter_by(name = object_request.name).first():
            i+=1
            object_request.name = original_name + '_' + str(i)
        
        new_object = Method(
            code = args['code'],
            object_request_id = object_request.id,
            object_request = object_request,
            name = object_request.name,
            pip_packages = pypi_packages,
            io_pair = object_request.io_pair,
            docString = args['docString'],
            project_id = object_request.project_id,
            dependencies = used_object_model_ids
        )
    else:
        raise Exception('object_request object_type not recognized.')
    session.add(new_object)
    session.commit()

    feature_instance.addLog('code submitted', {
        'toolName': 'submit_code',
        'args': args,
        'tool_call_id': tool_call_id,
        'code': feature_instance.code
    },
    session)
    session.commit()

    if feature_instance.submit_is_final:
        from .final_submission import execute as final_submission_execute
        return final_submission_execute(args, tool_call_id, session, feature_instance)
    return 'code submitted'

def getJson():
    return {
        "type": "function",
        "function":{
            "name": "submit_code",
            "description": "Submit the code for your assigned task (automatically pulled from your context). This will allow you to begin testing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "required_pypi_packages": {
                        "type": "array",
                        "description": "A list of required pypi packages for your code.",
                        "items": {
                            "type": "string"
                        }
                    },
                    "docString": {
                        "type": "string",
                        "description": "A docstring for your code."
                    }

                }
            }
        }
    }