import re
import os
from string import Template
from datetime import datetime
from jinja2 import Environment, Template

'''
Uses jinja2 to render prompt content with variables, so you can do things like below. 
You must still mark variables with $variable_name if you want the prompt class to be able to access them (on at least one of their declarations).
for loop example with enumeration:
----
$variable_name = [{'value':a},{'value':b},{'value':c}]
{% for item in $variable_name %}
{{ loop.index}}}: {{ item.value }}
{% endfor %}
----
output:
1: a
2: b
3: c

if statement example:
----
$variable_name = 1
{% if $variable_name == 1 %}
$variable_name is 1
{% else %}
$variable_name is not 1
{% endif %}
----
etc.


'''
def extract_args_and_debug_content(file_content):
    param_section, prompt_section = file_content.split('----', 1)
    prompt_section = prompt_section.replace('# Write your prompt content here. Use $variable_name to insert variables.', '')
    unique_variables = set()  # Initialize the set to store unique variable names

    # Function to replace $variable_name with variable_name and update the variable set
    def replace_variable(match):
        start_brace, inner_content, end_brace = match.groups()  # Distinguish parts of the match
        # Perform replacement and simultaneously collect variable names
        modified_content, _ = re.subn(r'\$(\w+)', lambda m: unique_variables.add(m.group(1)) or m.group(1), inner_content)
        return f"{start_brace}{modified_content}{end_brace}"  # Return with original braces reattached

    # Apply the replacement function to all {{ }} and {% %} contents
    updated_template = re.sub(r'(\{\{|{%)\s*(.*?)\s*(\}\}|\%})', replace_variable, prompt_section)

    params = dict(re.findall(r'(\w+):\s*(.*)', param_section))
    debug_content = params.get('debug_content', '')
    call_type = params.get('call_type', 'default_method')
    model = params.get('model', None)
    mode = params.get('mode', None)
    logging_mode = params.get('logging_mode', None)
    timeout = params.get('timeout', None)
    timestamps = params.get('timestamps', 'None')
    print_log = params.get('print_log', None)
    return_type = params.get('return_type', 'Any')  # Default to 'None' if not specified

    if print_log in ['False', 'false']:
        print_log = ''
    return list(unique_variables), updated_template, debug_content, call_type, model, mode, logging_mode, timeout, print_log, timestamps, return_type

def create_class_definitions(file_name, args, prompt_section, debug_content, call_type, model, mode, logging_mode, timeout, print_log, timestamps, return_type):
    types = extract_unique_types(return_type)
    return_type = f'tuple[Log, {return_type}]'
    if mode:
        mode = f"\"{mode}\""
    else:
        mode = "None"
    if logging_mode:
        logging_mode = f"\"{logging_mode}\""
    else:
        logging_mode = "None"
    if model:
        model = f"\"{model}\""
    else:
        model = "None"
    class_name = file_name.split('.')[0][0].upper() + file_name.split('.')[0][1:] + 'Prompt'
    args_list = ', '.join(args)
    class_def = f"class {class_name}:\n"
    class_def += f"    def __init__(self, {args_list}):\n" if args else f"    def __init__(self):\n"
    for arg in args:
        class_def += f"        self.{arg} = {arg}\n"
    class_def += f"        self.debug_content = '''{debug_content}'''\n"
    class_def += f"        self.print_log = {print_log or 'False'}\n"
    class_def += f"        self.timestamps = {timestamps.capitalize()}\n"
    class_def += f"        env = Environment()\n"
    class_def += f"        self.template = env.from_string('''{prompt_section}''')\n"
    class_def += f"    def get(self):\n"
    class_def += f"        content = self.template.render(**self.__dict__)\n"
    class_def += f"        if self.timestamps:\n"
    class_def += f"             content = 'current utcnow isoformat: ' + datetime.utcnow().isoformat() + '\\n' + content\n"
    class_def += f"        if os.environ.get('debug', None):\n"
    class_def += f"             content = content + '\\n' + self.debug_content\n"
    class_def += f"        return content\n"
    if 'sync' in call_type and 'async' not in call_type:
        class_def += f"    def execute(self, logging_mode={logging_mode}, print_log=None, tools=[], messages=[], run=None, model={model}, mode=None) -> {return_type}:\n"
    else:
        class_def += f"    async def execute(self, logging_mode={logging_mode}, print_log=None, tools=[], messages=[], run=None, model={model}, mode=None) -> {return_type}:\n"
    class_def += f"        mode = mode if mode else {mode}\n"
    class_def += f"        if print_log:\n"
    class_def += f"             self.print_log = print_log\n"
    class_def += f"        content = self.get()\n"
    class_def += f"        if model:\n"
    if 'sync' in call_type and 'async' not in call_type:
        class_def += f"             result = LLM.{call_type}(prompt=LLM.cleanStringForLLM(content), messages=messages, run=None, model=model, request_type=self.__class__.__name__, mode=mode, logging_mode=logging_mode, timeout={timeout}, print_log=self.print_log, tools=tools)\n"
    else:
        class_def += f"             result = await LLM.{call_type}(prompt=LLM.cleanStringForLLM(content), messages=messages, run=None, model=model, request_type=self.__class__.__name__, mode=mode, logging_mode=logging_mode, timeout={timeout}, print_log=self.print_log, tools=tools)\n"
    class_def += f"        else:\n"
    if 'sync' in call_type and 'async' not in call_type:
        class_def += f"             result = LLM.{call_type}(prompt=LLM.cleanStringForLLM(content), messages=messages, run=None, request_type=self.__class__.__name__, mode=mode, logging_mode=logging_mode, timeout={timeout}, print_log=self.print_log, tools=tools)\n"
    else:
        class_def += f"             result = await LLM.{call_type}(prompt=LLM.cleanStringForLLM(content), messages=messages, run=None, request_type=self.__class__.__name__, mode=mode, logging_mode=logging_mode, timeout={timeout}, print_log=self.print_log, tools=tools)\n"
    class_def += f"        if os.environ.get('debug', None):\n"
    class_def += f"             if result[1].get('reasoning', None):\n"
    class_def += f"                 print(f'reasoning for {{self.__class__.__name__}}: {{result[1].get(\"reasoning\")}}')\n"
    class_def += f"                 del(result[1]['reasoning'])\n"
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
                args, prompt_section, debug_content, call_type, model, mode, logging_mode, timeout, print_log, timestamps, return_type = extract_args_and_debug_content(content)
                types, class_def = create_class_definitions(file, args, prompt_section, debug_content, call_type, model, mode, logging_mode, timeout, print_log, timestamps, return_type)
                class_definitions.append(class_def)
                type_list.extend(types)

        f_out.write("""from jinja2 import Environment, Template\nimport os\nfrom datetime import datetime\nfrom packages.guru.GLLM import LLM\nfrom packages.guru.GLLM.log import Log\nfrom typing import Any\n""")
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
    for pair in prompt_directory_list:
        i = 0
        for key, value in pair.items():
            if i == 0:
                run(value, key)
                i += 1
            else:
                run(value, key, append=True)
    print(f"prompts from {prompt_directory_list} loaded.")

def extract_unique_types(type_str):
    types = re.findall(r'\b[A-Z]\w*', type_str)
    unique_types = list(set(types))
    return unique_types