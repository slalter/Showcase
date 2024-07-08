from string import Template
import os
from guru.GLLM import LLM

class CategorizeTranscriptPrompt:
    def __init__(self, categories, flags, questions, conversation_text, metadata):
        self.categories = categories
        self.flags = flags
        self.questions = questions
        self.conversation_text = conversation_text
        self.metadata = metadata
        self.debug_content = '''Explain your reasoning in another field called 'reasoning'.'''
        self.print_log = '''True'''
        self.content = Template(r'''current utcnow isoformat: 2024-02-26T20:28:36.440473

You are working for a company that is the middle man for incoming calls between ad publishers and lead-buying companies. Calls are automatically handled by Retreaver. You will see data from Retreaver and any transcript, if one exists.
Your job is to look at a transcript of a call and categorize it according to the categories below for analysis. If none of the categories is a good fit, make a new one.
Additionally:
Flag any messages that meet one of the criteria in 'flags.'
Answer any questions in 'questions.'
Provide a brief summary of the call, including your reasoning for your conclusions and quotes from the transcript to support your position.

In these categories, 'Buyer' refers to the company that buys the call, and 'Caller' is the customer.
categories: $categories

These flags should be treated separately from categories unless there is explicit overlap.
flags: $flags

questions: $questions

conversation_text: $conversation_text

Here is other relevant metadata about the call from retreaver. Note that if ConnectedTo has a value, then the call was connected to a buyer unless a tag states otherwise:
$metadata

Always match category names verbatim.
respond with a json as follows:
{
    category: (matching category or a new one here),
    flags: (any flags, or omit this entry),
    answers: [list of answers to each of the questions, mapped by index.]
    summary: (a brief summary of the call here)
}''')

    def get(self):
        content_template = self.content
        content = content_template.substitute({**self.__dict__})
        if os.environ.get('debug',None):
             content = content +'\n' + self.debug_content
        return content
    async def execute(self,logging_mode=None,print_log=None, tools= [], messages = [], run = None):
        if logging_mode:
             self.logging_mode = logging_mode
        else:
             self.logging_mode = "return"
        if print_log:
             self.print_log=print_log 
        content_template = self.content
        content = content_template.substitute({**self.__dict__})
        if os.environ.get('debug',None):
             content = content +'\n' + self.debug_content
        result =  await LLM.json_response(prompt=content, messages = messages, run = None, request_type=self.__class__.__name__,mode="OPEN_AI",logging_mode=logging_mode,timeout=45,print_log=self.print_log, tools=tools)
        if os.environ.get('debug',None):
             if result[1].get('reasoning',None):
                 print(f'reasoning for {self.__class__.__name__}: {result[1].get("reasoning")}')
                 del(result[1]['reasoning'])
        return result

class CatAndSubcatTranscriptPrompt:
    def __init__(self, categories, flags, questions, conversation_text, metadata):
        self.categories = categories
        self.flags = flags
        self.questions = questions
        self.conversation_text = conversation_text
        self.metadata = metadata
        self.debug_content = '''Explain your reasoning in another field called 'reasoning'.'''
        self.print_log = '''True'''
        self.content = Template(r'''current utcnow isoformat: 2024-02-26T20:28:36.440531

You are working for a company that is the middle man for incoming calls between ad publishers and lead-buying companies. Calls are automatically handled by Retreaver. You will see data from Retreaver and any transcript, if one exists.
Your job is to look at a transcript of a call and provide the best-fitting category and a subcategory according to the categories below. For both category and subcategory, if there is not a good fit, you can provide a new one - but always consider the existing categories first. It is imperative that you only create a new category or subcategory when absolutely necessary.
The most important part of the call is how it was concluded.
Additionally:
Flag any messages that meet one of the criteria in 'flags.'
Answer any questions in 'questions.'
Provide a brief summary of the call, including your reasoning for your conclusions and quotes from the transcript to support your position.

In these categories, 'Buyer' refers to the company that buys the call, and 'Caller' is the customer.
Note: A call is connected to a buyer iff there is a value in 'ConnectedTo'.
categories: $categories

These flags should be treated separately from categories unless there is explicit overlap.
flags: $flags

questions: $questions

conversation_text: $conversation_text

Here is other relevant metadata about the call from retreaver. Note that if ConnectedTo has a value, then the call was connected to a buyer unless a tag states otherwise:
$metadata

Always match category and subcategory names verbatim.
respond with a json as follows:
{
    category: (matching category VERBATIM or a new one here),
    subcategory: (matching subcategory VERBATIM or a new one here),
    flags: (any flags, or omit this entry),
    answers: [list of answers to each of the questions, mapped by index.]
    summary: (a brief summary of the call here)
}''')

    def get(self):
        content_template = self.content
        content = content_template.substitute({**self.__dict__})
        if os.environ.get('debug',None):
             content = content +'\n' + self.debug_content
        return content
    async def execute(self,logging_mode=None,print_log=None, tools= [], messages = [], run = None):
        if logging_mode:
             self.logging_mode = logging_mode
        else:
             self.logging_mode = "return"
        if print_log:
             self.print_log=print_log 
        content_template = self.content
        content = content_template.substitute({**self.__dict__})
        if os.environ.get('debug',None):
             content = content +'\n' + self.debug_content
        result =  await LLM.json_response(prompt=content, messages = messages, run = None, request_type=self.__class__.__name__,mode="OPEN_AI",logging_mode=logging_mode,timeout=45,print_log=self.print_log, tools=tools)
        if os.environ.get('debug',None):
             if result[1].get('reasoning',None):
                 print(f'reasoning for {self.__class__.__name__}: {result[1].get("reasoning")}')
                 del(result[1]['reasoning'])
        return result

class SubcategorizeTranscriptPrompt:
    def __init__(self, category, categories, conversation_text, metadata):
        self.category = category
        self.categories = categories
        self.conversation_text = conversation_text
        self.metadata = metadata
        self.debug_content = '''Explain your reasoning in another field called 'reasoning'.'''
        self.print_log = '''True'''
        self.content = Template(r'''current utcnow isoformat: 2024-02-26T20:28:36.440563

Your job is to look at an input conversation and sub-categorize it according to the subcategories below. If none of the categories is a good fit, make a new one.
Additionally, flag any messages that meet one of the criteria in 'flags.'

The call already has been classified within this category:
category: $category

In these categories, 'Buyer' refers to the salesperson, and 'Caller' is the customer.
subcategories: $categories

conversation_text: $conversation_text

Here is other relevant metadata about the call from retreaver:
$metadata

Always match category names verbatim.
respond with a json as follows:
{
    subcategory: (matching subcategory or a new one here)
}''')

    def get(self):
        content_template = self.content
        content = content_template.substitute({**self.__dict__})
        if os.environ.get('debug',None):
             content = content +'\n' + self.debug_content
        return content
    async def execute(self,logging_mode=None,print_log=None, tools= [], messages = [], run = None):
        if logging_mode:
             self.logging_mode = logging_mode
        else:
             self.logging_mode = "return"
        if print_log:
             self.print_log=print_log 
        content_template = self.content
        content = content_template.substitute({**self.__dict__})
        if os.environ.get('debug',None):
             content = content +'\n' + self.debug_content
        result =  await LLM.json_response(prompt=content, messages = messages, run = None, request_type=self.__class__.__name__,mode="OPEN_AI",logging_mode=logging_mode,timeout=45,print_log=self.print_log, tools=tools)
        if os.environ.get('debug',None):
             if result[1].get('reasoning',None):
                 print(f'reasoning for {self.__class__.__name__}: {result[1].get("reasoning")}')
                 del(result[1]['reasoning'])
        return result

class MapCampaignPrompt:
    def __init__(self, campaign_categories, campaign_info):
        self.campaign_categories = campaign_categories
        self.campaign_info = campaign_info
        self.debug_content = '''Explain your reasoning.'''
        self.print_log = '''True'''
        self.content = Template(r'''current utcnow isoformat: 2024-02-26T20:28:36.440622

Given the information about the campaign, identify which of the campaign categories the campaign belongs to.

campaign categories: $campaign_categories

campaign information: $campaign_info

Respond with a json as follows:
{
    campaign_category: (your choice here, or null if no good fit exists.)
}''')

    def get(self):
        content_template = self.content
        content = content_template.substitute({**self.__dict__})
        if os.environ.get('debug',None):
             content = content +'\n' + self.debug_content
        return content
    async def execute(self,logging_mode=None,print_log=None, tools= [], messages = [], run = None):
        if logging_mode:
             self.logging_mode = logging_mode
        else:
             self.logging_mode = "return"
        if print_log:
             self.print_log=print_log 
        content_template = self.content
        content = content_template.substitute({**self.__dict__})
        if os.environ.get('debug',None):
             content = content +'\n' + self.debug_content
        result =  await LLM.json_response(prompt=content, messages = messages, run = None, request_type=self.__class__.__name__,mode="OPEN_AI",logging_mode=logging_mode,timeout=45,print_log=self.print_log, tools=tools)
        if os.environ.get('debug',None):
             if result[1].get('reasoning',None):
                 print(f'reasoning for {self.__class__.__name__}: {result[1].get("reasoning")}')
                 del(result[1]['reasoning'])
        return result

