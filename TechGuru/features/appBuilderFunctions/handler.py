
TOOL_LIST = [
    'request_method',
    'request_model',
    'wait_for_objects',
    'request_test_case',
    'standardization_request',
    'modify_code',
    'run_pyright',
    'submit_tests',
    'run_tests',
    'submit_code',
    'request_additional_information',
    'report_error',
    'final_submission',
    'get_model_definitions'
]
#dynamically import everything in the list
for tool in TOOL_LIST:
    exec(f"from features.appBuilderFunctions import {tool}")


def executeHandler(toolName, args, tool_call_id,session, feature_instance):
    #dynamically make the function dict from the TOOL_LIST
    func_dict = {}
    for tool in TOOL_LIST:
        func_dict[tool] = eval(tool + ".execute")
    return func_dict[toolName](args, tool_call_id, session, feature_instance)

def jsonHandler(toolName):
    #dynamically make the json dict from the TOOL_LIST
    json_dict = {}
    for tool in TOOL_LIST:
        json_dict[tool] = eval(tool + ".getJson")
    return json_dict[toolName]()
