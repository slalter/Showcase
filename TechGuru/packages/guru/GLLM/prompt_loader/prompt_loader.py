import re
import os
from datetime import datetime
from jinja2 import Environment, Template

from .types import PromptParams
from ..models.llmmodel import LLMCall


def extract_args_and_debug_content(file_content):
    param_section, prompt_section = file_content.split('----', 1)
    prompt_section = prompt_section.replace('# Write your prompt content here. Use $variable_name to insert variables.', '')
    unique_variables = set()

    def replace_variable(match):
        start_brace, inner_content, end_brace = match.groups()
        modified_content, _ = re.subn(r'\$(\w+)', lambda m: unique_variables.add(m.group(1)) or m.group(1), inner_content)
        return f"{start_brace}{modified_content}{end_brace}"

    updated_template = re.sub(r'(\{\{|{%)\s*(.*?)\s*(\}\}|\%})', replace_variable, prompt_section)

    params = dict(re.findall(r'(\w+):\s*(.*)', param_section))
    prompt_params = PromptParams.from_dict(params)
    
    return list(unique_variables), updated_template, prompt_params

def create_class_definitions(file_name, args, prompt_section, prompt_params):
    types = extract_unique_types(prompt_params.return_type)
    return_type = f'tuple[Log, {prompt_params.return_type}]'
    class_name = file_name.split('.')[0][0].upper() + file_name.split('.')[0][1:] + 'Prompt'
    #if no provider or model is specified, default to environ variables
    if not prompt_params.provider:
        prompt_params.provider = os.environ.get('GLLM_DEFAULT_PROVIDER', 'anthropic')
    if not prompt_params.model:
        prompt_params.model = os.environ.get('GLLM_DEFAULT_MODEL', 'sonnet35')

    args_list = ', '.join(args)
    class_def = f"class {class_name}:\n"
    class_def += f"    def __init__(self, {args_list}):\n" if args else f"    def __init__(self):\n"
    for arg in args:
        class_def += f"        self.{arg} = {arg}\n"
    class_def += f"        self.params = {prompt_params.to_dict()}\n"
    class_def += f"        env = Environment()\n"
    class_def += f"        self.template = env.from_string('''{prompt_section}''')\n"
    class_def += f"    def get(self):\n"
    class_def += f"        content = self.template.render(**self.__dict__)\n"
    class_def += f"        if self.params['timestamps']:\n"
    class_def += f"             content = 'current utcnow isoformat: ' + datetime.utcnow().isoformat() + '\\n' + content\n"
    class_def += f"        return content\n"
    class_def += f"    def execute(self, print_log=None, tools=[], messages=[], model=None) -> LLMCall:\n"
    class_def += f"        if print_log:\n"
    class_def += f"             self.params['print_log'] = print_log\n"
    class_def += f"        content = self.get()\n"
    class_def += f"        if model:\n"
    class_def += f"             self.params['model'] = model\n"
    class_def += f"        if self.params['provider'] == 'openai':\n"
    class_def += f"             model_instance = OpenAIModel(self.params['model'], self.params['timeout'])\n"
    class_def += f"        elif self.params['provider'] == 'azureopenai':\n"
    class_def += f"             model_instance = AzureOpenAIModel(self.params['model'], self.params['timeout'])\n"
    class_def += f"        elif self.params['provider'] == 'anthropic':\n"
    class_def += f"             model_instance = AnthropicModel(self.params['model'], self.params['timeout'])\n"
    class_def += f"        result = model_instance.execute(messages=messages, prompt=content, temp=0.5, tools=tools, description=self.__class__.__name__, print_log=self.params['print_log'], json_mode=self.params['json_mode'])\n"
    class_def += f"        return result\n"
    
    return types, class_def

def run(output_file, prompt_directory, append=False):
    output_file = output_file
    prompt_directory = prompt_directory

    with open(output_file, 'w' if not append else 'a') as f_out:
        type_list = []
        class_definitions = []

        for file in os.listdir(prompt_directory):
            with open(os.path.join(prompt_directory, file), 'r') as f_in:
                content = f_in.read()
                args, prompt_section, prompt_params = extract_args_and_debug_content(content)
                types, class_def = create_class_definitions(file, args, prompt_section, prompt_params)
                class_definitions.append(class_def)
                type_list.extend(types)

        f_out.write("""
from jinja2 import Environment, Template
import os
from datetime import datetime
from packages.guru.GLLM.log import Log
from packages.guru.GLLM.models import OpenAIModel, AzureOpenAIModel, AnthropicModel, LLMCall\n\n""")
        f_out.write('\n\n'.join(class_definitions))
   
    print(f"prompts from {prompt_directory} loaded to {output_file}")

def runSet(prompt_directory_list):
    '''
    input:
    {
        'prompt_directory': 'output_file',
        'prompt_directory': 'output_file',...
    }
    '''
    print(f"loading prompts from {prompt_directory_list}...")

    for key, value in prompt_directory_list.items():
            run(value, key)
    print(f"prompts from {prompt_directory_list} loaded.")

def extract_unique_types(type_str):
    types = re.findall(r'\b[A-Z]\w*', type_str)
    unique_types = list(set(types))
    return unique_types
