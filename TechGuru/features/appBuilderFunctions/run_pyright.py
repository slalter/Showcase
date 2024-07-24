import os
import subprocess

def execute(args, tool_call_id, session, feature_instance):
    '''
    ONLY CALLABLE WHEN ALL DEPENDENCIES HAVE BEEN COMPLETED.
    Run pyright starting in this feature's directory. 
    Builds the files.
    Catches output from pyright and returns it as a string. raises exceptions.
    '''
    from models import ObjectRequest, CodeMixin
    #get the code
    code = feature_instance.code
    object_requests = feature_instance.getObjectRequests(session)

    unfinished_ors = [or_ for or_ in object_requests if not or_.status=='fulfilled']
    if unfinished_ors:
        for or_ in unfinished_ors:
            if or_.name in code:
                raise Exception('You cannot run pyright until all dependencies have been completed. We are still waiting for the following object requests to be fulfilled: ' + ', '.join([or_.name for or_ in unfinished_ors if or_.name in code]))

    code_object:CodeMixin = feature_instance.main_object_request.code_object
    if not code_object:
        return 'No code object found. Please submit code first.'
    code_object.build(f'/tmp/{code_object.id}')

    os.chdir(f'/tmp/{code_object.id}')
    with open('pyrightconfig.json', 'w') as f:
        f.write('''{
  "venvPath": "./.venv",
  "venv": "your-virtual-env-name",
  "reportMissingImports": true,
  "reportMissingTypeStubs": true,
  "pythonVersion": "3.9",
  "pythonPlatform": "Linux",
  "typeCheckingMode": "strict",
  "exclude": [
    "**/node_modules",
    "**/__pycache__"
  ]
}
''')


    result = subprocess.run(['pyright'], stdout=subprocess.PIPE)
    if result.returncode:
        raise Exception('Pyright failed. Please fix the errors and try again. Here are the errors: \n' + result.stdout.decode('utf-8'))
    return result.stdout.decode('utf-8')

def getJson():
    return{
            "type": "function",
            "function":{
                "name": "run_pyright",
                "description": "Run Pyright on the code for your assigned task. This will check for type errors and provide suggestions for improving your code.",
                "parameters": {}
            }
        }