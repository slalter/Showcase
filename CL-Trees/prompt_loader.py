import re
import os
from string import Template

def extract_args_and_debug_content(file_content):
    # Extracting arguments and debug content
    args = re.findall(r'\$(?!DEBUGGING_MODE)(\w+)', file_content)
    debug_pattern = r'\$DEBUGGING_MODE(.*?)\/\$DEBUGGING_MODE'
    debug_content = re.search(debug_pattern, file_content, re.DOTALL)
    debug_content = debug_content.group(1) if debug_content else ''
    no_debug_content = re.sub(debug_pattern, '$debug', file_content, flags=re.DOTALL)
    return args, debug_content, no_debug_content

def create_class_definitions(file_name, args, debug_content, no_debug_content):
    class_name = file_name.split('.')[0][0].upper() + file_name.split('.')[0][1:] + 'Prompt'
    args_list = ', '.join(args)
    class_def = f"class {class_name}:\n"
    class_def += f"    def __init__(self, {args_list}):\n" if args else f"    def __init__(self):\n"
    for arg in args:
        class_def += f"        self.{arg} = {arg}\n"
    class_def += f"        self.debug = '$debug'\n"
    class_def += f"        self.debug_content = '''{debug_content}'''\n"
    class_def += f"        self.content = Template(r'''{no_debug_content}''')\n\n"
    class_def += f"    def get(self):\n"
    class_def += f"        content_template = self.content\n"
    class_def += f"        content = content_template.substitute({{**self.__dict__}})\n"
    class_def += f"        content = content.replace('$debug',self.debug_content if os.environ['debug'] else '')\n"
    class_def += f"        return content\n"
    return class_def

def main():
    output_files = ['CLTrees/promptspy.py','promptspy.py']
    prompt_directory = 'CLTrees/prompts'  # Update this path to your prompt files directory

    for output_file in output_files:
        with open(output_file, 'w') as f_out:
            f_out.write("from string import Template\nimport os\n\nos.environ['debug']=os.environ.get('debug','')\n")

            for file in os.listdir(prompt_directory):
                with open(os.path.join(prompt_directory, file), 'r') as f_in:
                    content = f_in.read()
                    args, debug_content, no_debug_content = extract_args_and_debug_content(content)
                    class_def = create_class_definitions(file, args, debug_content, no_debug_content)
                    f_out.write(class_def + '\n')

        print(f"Classes have been written to {output_file}")


main()
