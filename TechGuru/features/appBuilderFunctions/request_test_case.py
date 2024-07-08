
def execute(args, tool_call_id, session, feature_instance):
    '''
    adds to the IO pairs. The tests themselves are not generated until after the code passes pyright.

    '''
    from models import TestCase, IOPair, ObjectRequest
    object_request_id = args['object_request_id']
    input = args['input']
    output = args['output']
    object_request = session.query(ObjectRequest).filter(ObjectRequest.id == object_request_id).first()
    if object_request is None:
        return f"Object request with id {object_request_id} not found."
    assert(isinstance(object_request, ObjectRequest))
    if input or output:
        io_pair = object_request.io_pair
        if not io_pair:
            return f"Object request with id {object_request_id} does not have an io_pair."
        assert(isinstance(io_pair, IOPair))
        io_pair.example_pairs = io_pair.example_pairs + [{"input": input, "output": output}]
    session.commit()

def getJson():
    return {
        "name": "provide_sample_io",
        "parameters": {
            "object_request_id": {
                "type": "string",
                "description": "The id of the object request you want to create a test case for."
            },
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