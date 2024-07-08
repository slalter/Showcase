from jinja2 import Environment, Template
import os
from datetime import datetime
from packages.guru.GLLM import LLM
from packages.guru.GLLM.log import Log
from typing import Any
class DesignDecisionComparePrompt:
    def __init__(self, description, relevant_for_list, matches, stack_description):
        self.description = description
        self.relevant_for_list = relevant_for_list
        self.matches = matches
        self.stack_description = stack_description
        self.debug_content = '''Explain your reasoning.'''
        self.print_log = True
        self.timestamps = False
        env = Environment()
        self.template = env.from_string('''
A developer has asked for you to make a standardization decision to standardize the codebase.

This is the stack the codebase is running with:
{{stack_description}}

Here is the request:
standardization_request: {{description}}
relevant_for: {{relevant_for_list}}

Here are the standardization decisions we have already made which are the closest:
{%for i in matches%}
#{{loop.index}}:
    description: {{i.description}}
    relevant_for: {%for j in i.relevant_fors%}{{j}}, {%endfor%}
    decision: {{i.decision}}
{%endfor%}

If similar decisions have been made, but this case is somewhat unique, use the existing decisions to inform the choice you make.

In all cases, use your best judgement to make a definitive decision that the development team can reference when they are building the project.

Respond with a json as follows. Include one of, but not both, new_standardization or standardization_already_exists.
{
    'new_standardization':{
        'description': describe the standardization,
        'relevant_for_list': list of tasks, packages, and/or parts of the codebase that this decision applies to,
        'decision': the standardization decision that you make.
    },
    'standardization_already_exists': (integer) the # of the existing standardization that applies to the situation. 
}''')
    def get(self):
        content = self.template.render(**self.__dict__)
        if self.timestamps:
             content = 'current utcnow isoformat: ' + datetime.utcnow().isoformat() + '\n' + content
        if os.environ.get('debug', None):
             content = content + '\n' + self.debug_content
        return content
    def execute(self, logging_mode="save_to_csv", print_log=None, tools=[], messages=[], run=None, model=None, mode=None) -> tuple[Log, dict[dict[str, str]] | dict[str, int]]:
        mode = mode if mode else "OPEN_AI"
        if print_log:
             self.print_log = print_log
        content = self.get()
        if model:
             result = LLM.json_response_sync(prompt=LLM.cleanStringForLLM(content), messages=messages, run=None, model=model, request_type=self.__class__.__name__, mode=mode, logging_mode=logging_mode, timeout=120, print_log=self.print_log, tools=tools)
        else:
             result = LLM.json_response_sync(prompt=LLM.cleanStringForLLM(content), messages=messages, run=None, request_type=self.__class__.__name__, mode=mode, logging_mode=logging_mode, timeout=120, print_log=self.print_log, tools=tools)
        if os.environ.get('debug', None):
             if result[1].get('reasoning', None):
                 print(f'reasoning for {self.__class__.__name__}: {result[1].get("reasoning")}')
                 del(result[1]['reasoning'])
        return result


class CompareCodeObjectPrompt:
    def __init__(self, object_type, requested_method_output, requested_method_input, matches, requested_method_description):
        self.object_type = object_type
        self.requested_method_output = requested_method_output
        self.requested_method_input = requested_method_input
        self.matches = matches
        self.requested_method_description = requested_method_description
        self.debug_content = '''Explain your reasoning.'''
        self.print_log = True
        self.timestamps = False
        env = Environment()
        self.template = env.from_string('''
A new {{object_type}} has been requested, but first we need to make sure we aren't rebuilding something we already have.

Here is the method that was requested:
requested_method: {{requested_method_description}}
{%if requested_method_output%}
requested_method_output: {{requested_method_output}}
{%endif%}
{%if requested_method_input%}
requested_method_input: {{requested_method_input}}
{%endif%}

Here are the closest things we already have:
{%for i in matches%}
#{{loop.index}}:
    description: {{i['description']}}
    input: {{i['input']}}
    output: {{i['output']}}
{%endfor%}


Respond with a json as follows:
{
    'similar_method_numbers':[method_numbers] ### A list of method_numbers for existing methods that are similar enough that they might already encompass a significant part of the required functionality.
}''')
    def get(self):
        content = self.template.render(**self.__dict__)
        if self.timestamps:
             content = 'current utcnow isoformat: ' + datetime.utcnow().isoformat() + '\n' + content
        if os.environ.get('debug', None):
             content = content + '\n' + self.debug_content
        return content
    def execute(self, logging_mode="save_to_csv", print_log=None, tools=[], messages=[], run=None, model=None, mode=None) -> tuple[Log, dict[str, list[int]]]:
        mode = mode if mode else "OPEN_AI"
        if print_log:
             self.print_log = print_log
        content = self.get()
        if model:
             result = LLM.json_response_sync(prompt=LLM.cleanStringForLLM(content), messages=messages, run=None, model=model, request_type=self.__class__.__name__, mode=mode, logging_mode=logging_mode, timeout=120, print_log=self.print_log, tools=tools)
        else:
             result = LLM.json_response_sync(prompt=LLM.cleanStringForLLM(content), messages=messages, run=None, request_type=self.__class__.__name__, mode=mode, logging_mode=logging_mode, timeout=120, print_log=self.print_log, tools=tools)
        if os.environ.get('debug', None):
             if result[1].get('reasoning', None):
                 print(f'reasoning for {self.__class__.__name__}: {result[1].get("reasoning")}')
                 del(result[1]['reasoning'])
        return result


class DescribeObjectPrompt:
    def __init__(self, object_data, object_type):
        self.object_data = object_data
        self.object_type = object_type
        self.debug_content = ''''''
        self.print_log = False
        self.timestamps = False
        env = Environment()
        self.template = env.from_string('''
You are working as part of an automated coding system. Your goal is to describe the following {{object_type}} in a way that is likely to make it appear in semantic similarity searches when agents are trying to find existing code objects while building new code or modifying existing code.
In general, don't respond with actual code - instead, describe the object and its usefulness.

{{object_data}}''')
    def get(self):
        content = self.template.render(**self.__dict__)
        if self.timestamps:
             content = 'current utcnow isoformat: ' + datetime.utcnow().isoformat() + '\n' + content
        if os.environ.get('debug', None):
             content = content + '\n' + self.debug_content
        return content
    def execute(self, logging_mode=None, print_log=None, tools=[], messages=[], run=None, model=None, mode=None) -> tuple[Log, Any]:
        mode = mode if mode else "AZURE"
        if print_log:
             self.print_log = print_log
        content = self.get()
        if model:
             result = LLM.ex_oai_call_sync(prompt=LLM.cleanStringForLLM(content), messages=messages, run=None, model=model, request_type=self.__class__.__name__, mode=mode, logging_mode=logging_mode, timeout=45, print_log=self.print_log, tools=tools)
        else:
             result = LLM.ex_oai_call_sync(prompt=LLM.cleanStringForLLM(content), messages=messages, run=None, request_type=self.__class__.__name__, mode=mode, logging_mode=logging_mode, timeout=45, print_log=self.print_log, tools=tools)
        if os.environ.get('debug', None):
             if result[1].get('reasoning', None):
                 print(f'reasoning for {self.__class__.__name__}: {result[1].get("reasoning")}')
                 del(result[1]['reasoning'])
        return result
