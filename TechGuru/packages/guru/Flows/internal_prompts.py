
from jinja2 import Environment, Template
import os
from datetime import datetime
from packages.guru.GLLM.log import Log
from packages.guru.GLLM.models import OpenAIModel, AzureOpenAIModel, AnthropicModel, LLMCall

class NextAssignmentPrompt:
    def __init__(self, conversation, conditions):
        self.conversation = conversation
        self.conditions = conditions
        self.params = {'provider': 'anthropic', 'model': 'sonnet35', 'description': '', 'timeout': 45, 'print_log': True, 'json_mode': True, 'timestamps': False, 'return_type': 'Any'}
        env = Environment()
        self.template = env.from_string('''

Your job is to determine which of the conditions best describes the conversation.

conditions: {{conditions}}

conversation: {{conversation}}

Your response should match the following JSON format. Respond with an appropriately formatted JSON and nothing more. 
{
    "best_match": condition ID here
}''')
    def get(self):
        content = self.template.render(**self.__dict__)
        if self.params['timestamps']:
             content = 'current utcnow isoformat: ' + datetime.utcnow().isoformat() + '\n' + content
        return content
    def execute(self, print_log=None, tools=[], messages=[], model=None) -> LLMCall:
        if print_log:
             self.params['print_log'] = print_log
        content = self.get()
        if model:
             self.params['model'] = model
        if self.params['provider'] == 'openai':
             model_instance = OpenAIModel(self.params['model'], self.params['timeout'])
        elif self.params['provider'] == 'azureopenai':
             model_instance = AzureOpenAIModel(self.params['model'], self.params['timeout'])
        elif self.params['provider'] == 'anthropic':
             model_instance = AnthropicModel(self.params['model'], self.params['timeout'])
        result = model_instance.execute(messages=messages, prompt=content, temp=0.5, tools=tools, description=self.__class__.__name__, print_log=self.params['print_log'], json_mode=self.params['json_mode'])
        return result


class ExtractInfoPrompt:
    def __init__(self, pairs, history):
        self.pairs = pairs
        self.history = history
        self.params = {'provider': 'anthropic', 'model': 'sonnet35', 'description': '', 'timeout': 45, 'print_log': True, 'json_mode': True, 'timestamps': False, 'return_type': 'Any'}
        env = Environment()
        self.template = env.from_string('''
Based on the conversation provided, extract information according to the following name:description pairs. 
Pairs: {{pairs}}
History: {{history}}
Respond with a json with keys equal to the provided names and values equal to what you figure out from the history.
If any of the data does not exist, simply leave it blank. Don't explain yourself.''')
    def get(self):
        content = self.template.render(**self.__dict__)
        if self.params['timestamps']:
             content = 'current utcnow isoformat: ' + datetime.utcnow().isoformat() + '\n' + content
        return content
    def execute(self, print_log=None, tools=[], messages=[], model=None) -> LLMCall:
        if print_log:
             self.params['print_log'] = print_log
        content = self.get()
        if model:
             self.params['model'] = model
        if self.params['provider'] == 'openai':
             model_instance = OpenAIModel(self.params['model'], self.params['timeout'])
        elif self.params['provider'] == 'azureopenai':
             model_instance = AzureOpenAIModel(self.params['model'], self.params['timeout'])
        elif self.params['provider'] == 'anthropic':
             model_instance = AnthropicModel(self.params['model'], self.params['timeout'])
        result = model_instance.execute(messages=messages, prompt=content, temp=0.5, tools=tools, description=self.__class__.__name__, print_log=self.params['print_log'], json_mode=self.params['json_mode'])
        return result


class SummarizeMessagesPrompt:
    def __init__(self, history):
        self.history = history
        self.params = {'provider': 'anthropic', 'model': 'sonnet35', 'description': '', 'timeout': 45, 'print_log': True, 'json_mode': True, 'timestamps': False, 'return_type': 'Any'}
        env = Environment()
        self.template = env.from_string('''
Take a deep breath and work slowly.

You are the agent in the conversation, and you are modifying your notes to reduce their length.
Given the conversation history below, replace sets of the indexed messages with short summaries. 
Your goal is to reduce the amount of text without discarding any information that is relevant to the current state of the conversation.
Always include any records of tool_calls.

conversation: 
{{history}}
Respond with a json as follows:
{
    "replacements": [
        {
        "indexes_to_replace": [list of indexes to replace],
        "summary": summary
        }, ...
    ]
}''')
    def get(self):
        content = self.template.render(**self.__dict__)
        if self.params['timestamps']:
             content = 'current utcnow isoformat: ' + datetime.utcnow().isoformat() + '\n' + content
        return content
    def execute(self, print_log=None, tools=[], messages=[], model=None) -> LLMCall:
        if print_log:
             self.params['print_log'] = print_log
        content = self.get()
        if model:
             self.params['model'] = model
        if self.params['provider'] == 'openai':
             model_instance = OpenAIModel(self.params['model'], self.params['timeout'])
        elif self.params['provider'] == 'azureopenai':
             model_instance = AzureOpenAIModel(self.params['model'], self.params['timeout'])
        elif self.params['provider'] == 'anthropic':
             model_instance = AnthropicModel(self.params['model'], self.params['timeout'])
        result = model_instance.execute(messages=messages, prompt=content, temp=0.5, tools=tools, description=self.__class__.__name__, print_log=self.params['print_log'], json_mode=self.params['json_mode'])
        return result


class CheckCompletePrompt:
    def __init__(self, objectives, history):
        self.objectives = objectives
        self.history = history
        self.params = {'provider': 'anthropic', 'model': 'sonnet35', 'description': '', 'timeout': 45, 'print_log': True, 'json_mode': True, 'timestamps': False, 'return_type': 'Any'}
        env = Environment()
        self.template = env.from_string('''

Based on the objectives and the chat history, determine whether or not ALL objectives have been completed. 
all_objectives_complete should be true IFF all objectives are complete.
The 'assistant' is trying to accomplish the objectives in their conversation with the 'user.'

objectives:
{{objectives}}

history:
{{history}}

Respond with JSON as follows.
{
    "all_objectives_complete": true or false,
    "explanation": explanation of your conclusion
}''')
    def get(self):
        content = self.template.render(**self.__dict__)
        if self.params['timestamps']:
             content = 'current utcnow isoformat: ' + datetime.utcnow().isoformat() + '\n' + content
        return content
    def execute(self, print_log=None, tools=[], messages=[], model=None) -> LLMCall:
        if print_log:
             self.params['print_log'] = print_log
        content = self.get()
        if model:
             self.params['model'] = model
        if self.params['provider'] == 'openai':
             model_instance = OpenAIModel(self.params['model'], self.params['timeout'])
        elif self.params['provider'] == 'azureopenai':
             model_instance = AzureOpenAIModel(self.params['model'], self.params['timeout'])
        elif self.params['provider'] == 'anthropic':
             model_instance = AnthropicModel(self.params['model'], self.params['timeout'])
        result = model_instance.execute(messages=messages, prompt=content, temp=0.5, tools=tools, description=self.__class__.__name__, print_log=self.params['print_log'], json_mode=self.params['json_mode'])
        return result


class AssignmentPrompt:
    def __init__(self, context, instructions, objectives, guidelines, personality, task_description):
        self.context = context
        self.instructions = instructions
        self.objectives = objectives
        self.guidelines = guidelines
        self.personality = personality
        self.task_description = task_description
        self.params = {'provider': 'anthropic', 'model': 'sonnet35', 'description': '', 'timeout': 120, 'print_log': True, 'json_mode': False, 'timestamps': False, 'return_type': 'Any'}
        env = Environment()
        self.template = env.from_string('''

Reread this prompt carefully every action. ALWAYS consider every tool. 

You may call tools/functions in parallel directly as a list, but do NOT use the 'multi_tool_use.parallel' function.

{%if task_description%}
---CURRENT TASK---
{{task_description}}
---END TASK---          
{%endif%}

---OBJECTIVES---
{{objectives}}
---END OBJECTIVES---

---INSTRUCTIONS---
{{instructions}}
---END INSTRUCTIONS---

---PERSONALITY---
{{personality}}
---END PERSONALITY---

---GUIDELINES---
{{guidelines}}
---END GUIDELINES---

---CURRENT CONTEXT---
{{context}}
---END CURRENT CONTEXT---''')
    def get(self):
        content = self.template.render(**self.__dict__)
        if self.params['timestamps']:
             content = 'current utcnow isoformat: ' + datetime.utcnow().isoformat() + '\n' + content
        return content
    def execute(self, print_log=None, tools=[], messages=[], model=None) -> LLMCall:
        if print_log:
             self.params['print_log'] = print_log
        content = self.get()
        if model:
             self.params['model'] = model
        if self.params['provider'] == 'openai':
             model_instance = OpenAIModel(self.params['model'], self.params['timeout'])
        elif self.params['provider'] == 'azureopenai':
             model_instance = AzureOpenAIModel(self.params['model'], self.params['timeout'])
        elif self.params['provider'] == 'anthropic':
             model_instance = AnthropicModel(self.params['model'], self.params['timeout'])
        result = model_instance.execute(messages=messages, prompt=content, temp=0.5, tools=tools, description=self.__class__.__name__, print_log=self.params['print_log'], json_mode=self.params['json_mode'])
        return result
