from string import Template
import os
from packages.guru.GLLM import LLM

class CheckCompletePrompt:
    def __init__(self, objectives, history):
        self.objectives = objectives
        self.history = history
        self.debug_content = '''Explain your reasoning.'''
        self.print_log = True
        self.content = Template(r'''current utcnow isoformat: 2024-02-26T23:23:33.246921

Based on the objectives and the chat history, determine whether or not ALL objectives have been completed. 
all_objectives_complete should be true IFF all objectives are complete.
The 'assistant' is trying to accomplish the objectives in their conversation with the 'user.'

objectives:
$objectives

history:
$history

Respond with JSON as follows.
{
    "all_objectives_complete": true or false,
    "explanation": explanation of your conclusion
}''')

    def get(self):
        content_template = self.content
        content = content_template.substitute({**self.__dict__})
        if os.environ.get('debug',None):
             content = content +'\n' + self.debug_content
        return content
    def execute(self,logging_mode="return",print_log=None, tools= [], messages = [], run = None, model = "gpt-4-turbo-preview"):
        if print_log:
             self.print_log=print_log 
        content_template = self.content
        content = content_template.substitute({**self.__dict__})
        if os.environ.get('debug',None):
             content = content +'\n' + self.debug_content
        if model:
             result = LLM.json_response_sync(prompt=LLM.cleanStringForLLM(content), messages = messages, run = None, model=model, request_type=self.__class__.__name__, mode="OPEN_AI", logging_mode=logging_mode, timeout=120, print_log=self.print_log, tools=tools)
        else:
             result = LLM.json_response_sync(prompt=LLM.cleanStringForLLM(content), messages = messages, run = None, request_type=self.__class__.__name__,mode="OPEN_AI",logging_mode=logging_mode,timeout=120,print_log=self.print_log, tools=tools)
        if os.environ.get('debug',None):
             if result[1].get('reasoning',None):
                 print(f'reasoning for {self.__class__.__name__}: {result[1].get("reasoning")}')
                 del(result[1]['reasoning'])
        return result

class AssignmentPrompt:
    def __init__(self, instructions, personality, guidelines, objectives, context):
        self.instructions = instructions
        self.personality = personality
        self.guidelines = guidelines
        self.objectives = objectives
        self.context = context
        self.debug_content = '''Explain your reasoning.'''
        self.print_log = True
        self.content = Template(r'''

Reread this prompt carefully every action. ALWAYS consider every tool. Never communicate your intent to do something and then return unless you are simultaneously calling a tool. If you send a message without a tool, you will NOT be able to work on anything until the user messages you again! Any time you need to 'get started and get back to the user soon' or similar, you must make a tool call.

$instructions

$personality

guidelines:
$guidelines

Your ultimate goal is to accomplish these objectives as quickly as possible.
objectives:
$objectives

context: 
$context''')

    def get(self):
        content_template = self.content
        content = content_template.substitute({**self.__dict__})
        if os.environ.get('debug',None):
             content = content +'\n' + self.debug_content
        return content
    def execute(self,logging_mode="return",print_log=None, tools= [], messages = [], run = None, model = None):
        if print_log:
             self.print_log=print_log 
        content_template = self.content
        content = content_template.substitute({**self.__dict__})
        if os.environ.get('debug',None):
             content = content +'\n' + self.debug_content
        if model:
             result = LLM.ex_oai_call_sync(prompt=LLM.cleanStringForLLM(content), messages = messages, run = None, model=model, request_type=self.__class__.__name__, mode="OPEN_AI", logging_mode=logging_mode, timeout=120, print_log=self.print_log, tools=tools)
        else:
             result =  LLM.ex_oai_call_sync(prompt=LLM.cleanStringForLLM(content), messages = messages, run = None, request_type=self.__class__.__name__,mode="OPEN_AI",logging_mode=logging_mode,timeout=120,print_log=self.print_log, tools=tools)
        if os.environ.get('debug',None):
             if result[1].get('reasoning',None):
                 print(f'reasoning for {self.__class__.__name__}: {result[1].get("reasoning")}')
                 del(result[1]['reasoning'])
        return result

class SummarizeMessagesPrompt:
    def __init__(self, history):
        self.history = history
        self.debug_content = '''Explain your reasoning.'''
        self.print_log = True
        self.content = Template(r'''current utcnow isoformat: 2024-02-26T23:23:33.247042
Take a deep breath and work slowly.

You are the agent in the conversation, and you are modifying your notes to reduce their length.
Given the conversation history below, replace sets of the indexed messages with short summaries. 
Your goal is to reduce the amount of text without discarding any information that is relevant to the current state of the conversation.
Always include any records of tool_calls.

conversation: 
$history

Respond with a json as follows:
{
    "indexes_to_replace": [list of indexes to replace],
    "summary": summary
}''')

    def get(self):
        content_template = self.content
        content = content_template.substitute({**self.__dict__})
        if os.environ.get('debug',None):
             content = content +'\n' + self.debug_content
        return content
    def execute(self,logging_mode="return",print_log=None, tools= [], messages = [], run = None, model = "gpt-4-turbo-preview"):
        if print_log:
             self.print_log=print_log 
        content_template = self.content
        content = content_template.substitute({**self.__dict__})
        if os.environ.get('debug',None):
             content = content +'\n' + self.debug_content
        if model:
             result = LLM.json_response_sync(prompt=LLM.cleanStringForLLM(content), messages = messages, run = None, model=model, request_type=self.__class__.__name__, mode="OPEN_AI", logging_mode=logging_mode, timeout=120, print_log=self.print_log, tools=tools)
        else:
             result = LLM.json_response_sync(prompt=LLM.cleanStringForLLM(content), messages = messages, run = None, request_type=self.__class__.__name__,mode="OPEN_AI",logging_mode=logging_mode,timeout=120,print_log=self.print_log, tools=tools)
        if os.environ.get('debug',None):
             if result[1].get('reasoning',None):
                 print(f'reasoning for {self.__class__.__name__}: {result[1].get("reasoning")}')
                 del(result[1]['reasoning'])
        return result

class ExtractInfoPrompt:
    def __init__(self, pairs, history):
        self.pairs = pairs
        self.history = history
        self.debug_content = '''Explain your reasoning.'''
        self.print_log = True
        self.content = Template(r'''current utcnow isoformat: 2024-02-26T23:23:33.247087
Based on the conversation provided, extract information according to the following name:description pairs. 
Pairs: $pairs
History: $history
Respond with a json with keys equal to the provided names and values equal to what you figure out from the history."""
''')

    def get(self):
        content_template = self.content
        content = content_template.substitute({**self.__dict__})
        if os.environ.get('debug',None):
             content = content +'\n' + self.debug_content
        return content
    def execute(self,logging_mode="return",print_log=None, tools= [], messages = [], run = None, model = "gpt-4-turbo-preview"):
        if print_log:
             self.print_log=print_log 
        content_template = self.content
        content = content_template.substitute({**self.__dict__})
        if os.environ.get('debug',None):
             content = content +'\n' + self.debug_content
        if model:
             result = LLM.json_response_sync(prompt=LLM.cleanStringForLLM(content), messages = messages, run = None, model=model, request_type=self.__class__.__name__, mode="OPEN_AI", logging_mode=logging_mode, timeout=120, print_log=self.print_log, tools=tools)
        else:
             result = LLM.json_response_sync(prompt=LLM.cleanStringForLLM(content), messages = messages, run = None, request_type=self.__class__.__name__,mode="OPEN_AI",logging_mode=logging_mode,timeout=120,print_log=self.print_log, tools=tools)
        if os.environ.get('debug',None):
             if result[1].get('reasoning',None):
                 print(f'reasoning for {self.__class__.__name__}: {result[1].get("reasoning")}')
                 del(result[1]['reasoning'])
        return result

class NextAssignmentPrompt:
    def __init__(self, conditions, conversation):
        self.conditions = conditions
        self.conversation = conversation
        self.debug_content = '''Explain your reasoning.'''
        self.print_log = True
        self.content = Template(r'''current utcnow isoformat: 2024-02-26T23:23:33.247148

Your job is to determine which of the conditions best describes the conversation.

conditions: $conditions

conversation: $conversation

Your response should match the following JSON format. Respond with an appropriately formatted JSON and nothing more. 
{
    "best_match": condition ID here
}''')

    def get(self):
        content_template = self.content
        content = content_template.substitute({**self.__dict__})
        if os.environ.get('debug',None):
             content = content +'\n' + self.debug_content
        return content
    def execute(self,logging_mode="return",print_log=None, tools= [], messages = [], run = None, model = "gpt-4-turbo-preview"):
        if print_log:
             self.print_log=print_log 
        content_template = self.content
        content = content_template.substitute({**self.__dict__})
        if os.environ.get('debug',None):
             content = content +'\n' + self.debug_content
        if model:
             result = LLM.json_response_sync(prompt=LLM.cleanStringForLLM(content), messages = messages, run = None, model=model, request_type=self.__class__.__name__, mode="OPEN_AI", logging_mode=logging_mode, timeout=120, print_log=self.print_log, tools=tools)
        else:
             result =  LLM.json_response_sync(prompt=LLM.cleanStringForLLM(content), messages = messages, run = None, request_type=self.__class__.__name__,mode="OPEN_AI",logging_mode=logging_mode,timeout=120,print_log=self.print_log, tools=tools)
        if os.environ.get('debug',None):
             if result[1].get('reasoning',None):
                 print(f'reasoning for {self.__class__.__name__}: {result[1].get("reasoning")}')
                 del(result[1]['reasoning'])
        return result

