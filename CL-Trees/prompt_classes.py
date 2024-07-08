from string import Template
import os
from guru.GLLM import LLM

class TreeNavigatorPrompt:
    def __init__(self, information, categories):
        self.information = information
        self.categories = categories
        self.debug_content = '''Explain your reasoning.'''
        self.print_log = '''True'''
        self.content = Template(r'''current utcnow isoformat: 2024-02-26T23:07:24.179385
Use the given information to determine how likely each category is to have the information that the user is looking for.

information: $information

categories: $categories

respond with a stringified python list containing decimal weights on [0,1] that represent how likely the corresponding category is to contain the information you are looking for. Your weights are mapped to the categories based on their position in the list.
The weights should sum to 1.
Respond with just the stringified python list and nothing more.''')

    def get(self):
        content_template = self.content
        content = content_template.substitute({**self.__dict__})
        if os.environ.get('debug',None):
             content = content +'\n' + self.debug_content
        return content
    async def execute(self,logging_mode=return,print_log=None, tools= [], messages = [], run = None, model = gpt-4-turbo-preview):
        if print_log:
             self.print_log=print_log 
        content_template = self.content
        content = content_template.substitute({**self.__dict__})
        if os.environ.get('debug',None):
             content = content +'\n' + self.debug_content
        if model:
             result = await LLM.ex_oai_call(prompt=LLM.cleanStringForLLM(content), messages = messages, run = None, model=model, request_type=self.__class__.__name__, mode="OPEN_AI", logging_mode=logging_mode, timeout=45, print_log=self.print_log, tools=tools)
        else:
             result =  await LLM.ex_oai_call(prompt=LLM.cleanStringForLLM(content), messages = messages, run = None, request_type=self.__class__.__name__,mode="OPEN_AI",logging_mode=logging_mode,timeout=45,print_log=self.print_log, tools=tools)
        if os.environ.get('debug',None):
             if result[1].get('reasoning',None):
                 print(f'reasoning for {self.__class__.__name__}: {result[1].get("reasoning")}')
                 del(result[1]['reasoning'])
        return result

