from .assignment import Assignment
from .connector import Connector
from .conversation import Conversation
from .features import Feature
from .tool import Tool

import traceback

from ..GLLM import prompt_loader
from .features import load_feature_classes_from_folder
from packages.guru.cli.utils import guru_settings

def initialize():
    try:
        

        tools_path = guru_settings['tools_path']
        features_path = guru_settings['features_path']
        prompts_py_path = guru_settings.get('prompt_py','')
        prompt_txt_folder_path = guru_settings['prompt_txt_folder_path']

        #if the prompt_txt_folder_path is a single string as opposed to a list...
        if isinstance(prompt_txt_folder_path, str):
            prompt_txt_folder_path = {prompt_txt_folder_path:prompts_py_path}
        # Run prompt loader with the loaded settings
        prompt_loader.runSet(prompt_txt_folder_path)

        #run on internal prompts
        prompt_loader.runSet({
            'packages/guru/Flows/prompts': 'packages/guru/Flows/internal_prompts.py'
        })

        # Load features
        print("loading features...")
        load_feature_classes_from_folder(features_path)

        print("Settings loaded from packages.guru_settings.yml and applied.")

    except Exception as e:
        print(f"Error during initialization: {traceback.format_exception(e)}. Have you run 'guru init' for this project?")
        # Handle the error or re-raise as appropriate


initialize()