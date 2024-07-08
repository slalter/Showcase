
def execute(args, tool_call_id, session,feature_instance):
    '''
    starts a request to make an object.
    '''
    from models import ObjectRequest, InputClass, OutputClass, IOPair
    name = args['method_name']
    description = args['description']
    object_type = 'method'
    input_class_parameters = args.get('input_class_parameters', [])
    output_class_parameters = args.get('output_class_parameters', [])


    input_class = None
    output_class = None
    if input_class_parameters:
        input_class = InputClass(
            attributes = input_class_parameters
            )
        session.add(input_class)
        session.commit()
    if output_class_parameters:
        output_class = OutputClass(
            attributes = output_class_parameters
            )
        session.add(output_class)
        session.commit()
    example_pairs = args.get('io_example_pairs', [])
    
    io_pair = IOPair(
        input_class = input_class, 
        output_class = output_class,
        example_pairs = example_pairs
        )
    object_request = ObjectRequest(
        description = description, 
        name = name, 
        object_type = object_type,
        io_pair = io_pair,
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
                    "name": "request_method",
                    "description": "Request a method to be created for you, or for which your coworkers can provide any similar things they have already built. Pyright will be used to verify the method, so provide detailed input and output classes with type hints.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "description": {
                                "type": "string",
                                "description": "A description of the method you want to request and its purpose, as well as any insights that may be useful for the developer."
                            },
                            "method_name": {
                                "type": "string",
                                "description": "A name for the method."
                            },
                            "input_class_parameters": {
                                "type": "object",
                                "description": "A dictionary of input class parameters.",
                                "properties": {
                                    "name": {
                                        "type": "string",
                                        "description": "The name of the parameter."
                                    },
                                    "type": {
                                        "type": "string",
                                        "description": "The type of the parameter."
                                    },
                                    "default": {
                                        "type": "string",
                                        "description": "The default value of the parameter, if applicable."
                                    }
                                }
                            },
                            "output_class_parameters": {
                                "type": "object",
                                "description": "A dictionary of output class parameters.",
                                "properties": {
                                    "name": {
                                        "type": "string",
                                        "description": "The name of the parameter."
                                    },
                                    "type": {
                                        "type": "string",
                                        "description": "The type of the parameter."
                                    },
                                    "default": {
                                        "type": "string",
                                        "description": "The default value of the parameter, if applicable."
                                    }
                                }
                            },
                            "io_example_pairs":{
                                "type": "array",
                                "description": "Example input-output pairs for the object you are requesting, if applicable.",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "input": {
                                            "type": "string",
                                            "description": "Example input."
                                        },
                                        "output": {
                                            "type": "string",
                                            "description": "Expected output."
                                        }
                                    }
                                }
                            }
                            }
                        }
                    }
                }