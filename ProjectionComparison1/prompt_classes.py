from string import Template
import os
from datetime import datetime
from guru.GLLM import LLM

class FindElementPrompt:
    def __init__(self, directives, target_element):
        self.directives = directives
        self.target_element = target_element
        self.debug_content = '''Explain your reasoning.'''
        self.print_log = True
        self.timestamps = False
        self.content = Template(r'''


You are attempting to pinpoint the location of an element within a dataset.
The dataset is partitioned according to different directives. For each partition, the relationship between the each element and the directive is calculated, and the resulting vectors are clustered into groups. 
Your goal is to provide a short description for each directive of how your target_item relates to that directive, with hopes of matching the clusters that contain your element by comparing the embedding of each description to each category.

Here are the directives:
$directives

And here is your element:
$target_element

Respond with a json as follows:
{
    (directive here): (description of how your item relates to the directive here),
    (next directive): (next description),
    ...

}''')

    def get(self):
        content_template = self.content
        content = content_template.substitute({**self.__dict__})
        if self.timestamps:
             content = "current utcnow isoformat: " + datetime.utcnow().isoformat() + "\n" + content
        if os.environ.get('debug',None):
             content = content +'\n' + self.debug_content
        return content
    def execute(self,logging_mode="save_to_csv",print_log=None, tools= [], messages = [], run = None, model = "default_model", mode = None):
        mode = mode if mode else "OPEN_AI"
        if print_log:
             self.print_log=print_log 
        content = self.get()
        if model:
             result = LLM.json_response_sync(prompt=LLM.cleanStringForLLM(content), messages = messages, run = None, model=model, request_type=self.__class__.__name__, mode=mode, logging_mode=logging_mode, timeout=45, print_log=self.print_log, tools=tools)
        else:
             result =  LLM.json_response_sync(prompt=LLM.cleanStringForLLM(content), messages = messages, run = None, request_type=self.__class__.__name__,mode=mode,logging_mode=logging_mode,timeout=45,print_log=self.print_log, tools=tools)
        if os.environ.get('debug',None):
             if result[1].get('reasoning',None):
                 print(f'reasoning for {self.__class__.__name__}: {result[1].get("reasoning")}')
                 del(result[1]['reasoning'])
        return result

