
import sys
import os
import yaml
import json


import pkg_resources
import os
import traceback 

from ..GLLM import prompt_loader

def new_prompt(args = None):
    prompt_name = input("enter the name of your new prompt (Prompt will be added automatically).")

    try:
        with open('guru_settings.yml', 'r') as f:
            settings = yaml.safe_load(f)
            prompt_path = settings.get('prompt_txt_folder_path')
        

        if not prompt_path:
            raise Exception("prompt_py not set in guru_settings.yml.")

        full_path = os.path.join(prompt_path, f"{prompt_name}.txt")
        create_new_prompt(full_path)
        print(f"New prompt template created at {full_path}")

    except Exception as e:
        print(f"Unable to create new prompt due to {e}")
        sys.exit(1)

def new_assignment(args = None):
    from .gui.new_assignment import create_or_edit_assignment, assignment_data_holder
    create_or_edit_assignment()
    result = assignment_data_holder['data']
    if result:
        try:
            with open(os.path.join(os.getcwd(),'guru_settings.yml'), 'r') as f:
                settings = yaml.safe_load(f)
            assignment_json_path = os.path.join(settings.get('assignments_path'), settings.get('assignments_file'))
            print(assignment_json_path)       
            with open(os.path.join(os.getcwd(),assignment_json_path), 'r') as f:
                txt = f.read()
            oldjson = json.loads(txt)
            oldjson['assignments'].append(result)
            with open(os.path.join(os.getcwd(),assignment_json_path), 'w') as f:
                f.write(json.dumps(oldjson))
            if not assignment_json_path:
                raise Exception("assignment_json not set in guru_settings.yml.")


        except Exception as e:
            print(e)
            sys.exit(1)


def create_new_prompt(file_path):
    default_content = """model: default_model
call_type: ex_oai_call
mode: OPEN_AI
logging_mode: save_to_csv
timeout: 45
timestamps: False
print_log: True
debug_content: Explain your reasoning.
return_type: Any
----
# Write your prompt content here. Use $variable_name to insert variables.
"""

    with open(file_path, 'w') as f:
        f.write(default_content)


import os
import yaml

def init(args = None):
    print("Initializing Guru project...")

    # Default settings
    default_settings = {
        'tools_path': 'tools',
        'tools_file': 'tools/tools.json',
        'features_path': 'features/',
        'prompt_py': 'prompt_classes.py',
        'prompt_txt_folder_path': 'prompts',
        'assignments_path':'assignments',
        'assignments_file':'assignments.json'
    }

    settings = {}
    if not args:
        settings = {}
        for key, default in default_settings.items():
            user_input = input(f"Enter the path to {key} [{default}]: ").strip()
            settings[key] = user_input if user_input else default
    elif not args.d:
        settings = {}
        for key, default in default_settings.items():
            user_input = input(f"Enter the path to {key} [{default}]: ").strip()
            settings[key] = user_input if user_input else default
    else:
        settings = default_settings

    # Ensure that directories/files exist
    for key, path in settings.items():
        if key.endswith('_path'):  # Assuming paths ending with '_path' are directories
            os.makedirs(path, exist_ok=True)
        else:  # Assuming other paths are files
            if not os.path.exists(path):
                with open(path, 'w') as f:
                    if '.json' in path:
                        if key=='assignments_file':
                            f.write('{}')
                        elif key == 'tools_file':
                            f.write('[]')
    #settings['project_dir'] = os.getcwd()
    with open('guru_settings.yml', 'w') as f:
        yaml.dump(settings, f)

    print("guru_settings.yml created in the current directory.")
    print("To create a new prompt, run 'guru new prompt'")
    custom_setup()


def internal_prompts(args=None):
    custom_setup()
    
def custom_setup():

    print("building internal prompt classes...")

    try:
        prompt_loader.run(pkg_resources.resource_filename('guru', 'internal_prompts.py'),pkg_resources.resource_filename('guru.Flows', 'prompts/'))

    except Exception as e:
        print(f"failed to properly install! please retry once you deal with this error: {traceback.format_exception(e)}")

