
from jinja2 import Environment, Template
import os
from datetime import datetime
from packages.guru.GLLM.log import Log
from packages.guru.GLLM.models import OpenAIModel, AzureOpenAIModel, AnthropicModel, LLMCall

class ZipExamplePrompt:
    def __init__(self, seed):
        self.seed = seed
        self.params = {'provider': 'anthropic', 'model': 'sonnet35', 'description': '', 'timeout': 45, 'print_log': False, 'json_mode': True, 'timestamps': False, 'return_type': 'Any'}
        env = Environment()
        self.template = env.from_string('''
Generate the following based on the seed. 

seed: {{seed}}

example criteria:
{'price':'free', 'location':'San Francisco'}

Criteria list should be comprehensive. This often needs to be at least 5 criterion.
description should be succinct.
is_providing and is_receiving are optional. 

Respond with a JSON as follows:
{
    description: a description of the service/item/etc offered or requested,
    criteria: {
        "example_category":"example_value",
        "other_example_category":"other value,
        ...
    },
    is_providing: [list of strings showing what is being provided],
    is_seeking: [list of strings showing what is being sought]
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


class GetRelativeContextSummaryPrompt:
    def __init__(self, given_topic, context, object_summary):
        self.given_topic = given_topic
        self.context = context
        self.object_summary = object_summary
        self.params = {'provider': 'anthropic', 'model': 'sonnet35', 'description': '', 'timeout': 45, 'print_log': False, 'json_mode': False, 'timestamps': False, 'return_type': 'Any'}
        env = Environment()
        self.template = env.from_string('''
Create a description of how parts of the object described in object_summary might be useful in the given context.
Constrain your response to only consider the given_topic.
Avoid unnecessary words or phrases, maintaining a high density of meaningful words.

given_topic:
{{given_topic}}

context:
{{context}}

object_summary:
{{object_summary}}''')
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


class DesignDecisionComparePrompt:
    def __init__(self, description, relevant_for_list, stack_description, matches):
        self.description = description
        self.relevant_for_list = relevant_for_list
        self.stack_description = stack_description
        self.matches = matches
        self.params = {'provider': 'anthropic', 'model': 'sonnet35', 'description': '', 'timeout': 120, 'print_log': True, 'json_mode': True, 'timestamps': False, 'return_type': 'dict[dict[str, str]] | dict[str, int]'}
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


class CompareCodeObjectPrompt:
    def __init__(self, requested_method_description, matches, requested_method_input, requested_method_output, object_type):
        self.requested_method_description = requested_method_description
        self.matches = matches
        self.requested_method_input = requested_method_input
        self.requested_method_output = requested_method_output
        self.object_type = object_type
        self.params = {'provider': 'anthropic', 'model': 'sonnet35', 'description': '', 'timeout': 120, 'print_log': True, 'json_mode': False, 'timestamps': False, 'return_type': 'dict[str, list[int]]'}
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


class SummarizeForDCOVectorPrompt:
    def __init__(self, child_data, parent_data, given_topic):
        self.child_data = child_data
        self.parent_data = parent_data
        self.given_topic = given_topic
        self.params = {'provider': 'anthropic', 'model': 'sonnet35', 'description': '', 'timeout': 45, 'print_log': False, 'json_mode': False, 'timestamps': False, 'return_type': 'Any'}
        env = Environment()
        self.template = env.from_string('''
Prompt:

You are working in a system that determines how detailed the context provided to an agent will be. This is done with a tree structure where child nodes contain data that is a subset of their parent node's data, with a higher degree of detail. Your job is to assist in determining when we should use the greater detail from a child node instead of using the parent node.

Task:
{%if parent_data%}
Briefly describe how the child_data differs from the parent_data with respect to the given_topic. Focus on how the child_data provides more specific or detailed information regarding the given_topic. Use the knowledge of the parent_data, but only describe the child_data. Avoid unnecessary words or phrases, maintaining a high density of meaningful words.
{%endif%}

{%if not parent_data%}
This is a top-level node without a parent.
Briefly describe how the data relates to the given_topic. Focus on what information is provided regarding the given_topic. Avoid unnecessary words or phrases, maintaining a high density of meaningful words.
{%endif%}

given_topic:
{{given_topic}}

{%if parent_data%}
parent_data:
{{parent_data}}

child_data:
{{child_data}}
{%endif%}
{%if not parent_data%}
data:
{{child_data}}
{%endif%}''')
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


class DescribeObjectPrompt:
    def __init__(self, object_data, object_type):
        self.object_data = object_data
        self.object_type = object_type
        self.params = {'provider': 'anthropic', 'model': 'sonnet35', 'description': '', 'timeout': 45, 'print_log': False, 'json_mode': False, 'timestamps': False, 'return_type': 'Any'}
        env = Environment()
        self.template = env.from_string('''
You are working as part of an automated coding system. Your goal is to describe the following {{object_type}} in a way that is likely to make it appear in semantic similarity searches when agents are trying to find existing code objects while building new code or modifying existing code.
In general, don't respond with actual code - instead, describe the object and its usefulness.

{{object_data}}''')
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
