def execute(args, tool_call_id, session, feature_instance):
    '''
    submits test_cases for the object request.
    '''
    from models import TestCase, ObjectRequest
    object_request_id = args['object_request_id']
    code = args['code']
    object_request = session.query(ObjectRequest).filter(ObjectRequest.id == object_request_id).first()
    if object_request is None:
        return f"Object request with id {object_request_id} not found."
    assert(isinstance(object_request, ObjectRequest))
    test_case = TestCase(
        object_request = object_request,
        code = code
    )
    session.add(test_case)
    session.commit()
    return f"Test case submitted for object request {object_request_id}."


def getJson():
    return {
        "name": "submit_test_case",
        "parameters": {
            "object_request_id": {
                "type": "string",
                "description": "The id of the object request you want to submit tests for."
            },
            "code":
            {
                "type": "string",
                "description": "The code for the test case."
            }
        }
    }