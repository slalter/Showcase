from string import Template
import os
from datetime import datetime
from guru.GLLM import LLM

class ProcessContextPrompt:
    def __init__(self, information, categories):
        self.information = information
        self.categories = categories
        self.debug_content = ''''''
        self.print_log = None
        self.timestamps = None
        self.content = Template(r'''
Use the given information to determine how likely each category is to have the best match.

information: $information

categories: $categories

Respond with a stringified python list containing decimal weights on [0,1] that represent how likely the corresponding category is to contain the information you are looking for. Your weights are mapped to the categories based on their position in the list.
The weights don't need to sum to 1. 
If it seems like it would be better to gather more information before proceeding, simply return an empty list instead. 
It is always better to gather more information than to proceed with any degree of uncertainty.
Respond with just the stringified python list and nothing more.''')

    def get(self):
        content_template = self.content
        content = content_template.substitute({**self.__dict__})
        if self.timestamps:
             content = "current utcnow isoformat: " + datetime.utcnow().isoformat() + "\n" + content
        if os.environ.get('debug',None):
             content = content +'\n' + self.debug_content
        return content
    def execute(self,logging_mode=None,print_log=None, tools= [], messages = [], run = None, model = None, mode = None):
        mode = mode if mode else None
        if print_log:
             self.print_log=print_log 
        content = self.get()
        if model:
             result = LLM.ex_oai_call_sync(prompt=LLM.cleanStringForLLM(content), messages = messages, run = None, model=model, request_type=self.__class__.__name__, mode=mode, logging_mode=logging_mode, timeout=None, print_log=self.print_log, tools=tools)
        else:
             result =  LLM.ex_oai_call_sync(prompt=LLM.cleanStringForLLM(content), messages = messages, run = None, request_type=self.__class__.__name__,mode=mode,logging_mode=logging_mode,timeout=None,print_log=self.print_log, tools=tools)
        if os.environ.get('debug',None):
             if result[1].get('reasoning',None):
                 print(f'reasoning for {self.__class__.__name__}: {result[1].get("reasoning")}')
                 del(result[1]['reasoning'])
        return result

class ReorganizeCondensePrompt:
    def __init__(self, categories, category_path, directive):
        self.category_path = category_path
        self.categories = categories
        self.directive = directive
        self.debug_content = ''''''
        self.print_log = None
        self.timestamps = None
        self.content = Template(r'''
Given the following categories, group together similar categories to reduce the total number of categories.
There should be 2-4 new categories.
Remember to make sure that every existing category is mapped to a new category.
NEVER categorize as "{x}" and "{opposite of x}". 
NEVER include a generic category like "other fields."
NEVER use subjective measures.

Both the existing categories and your new categories will be within this category_path:$category_path
existing categories (id:description): $categories
organizational purpose: $directive

Respond in the following stringified JSON format. Every existing category should be placed in exactly one of the new categories.
{
    newCategoryDescription: [old categoryIds that fit in the new category],
    otherNewCategoryDescription: [old categoryIds that fit in the new category]
}''')

    def get(self):
        content_template = self.content
        content = content_template.substitute({**self.__dict__})
        if self.timestamps:
             content = "current utcnow isoformat: " + datetime.utcnow().isoformat() + "\n" + content
        if os.environ.get('debug',None):
             content = content +'\n' + self.debug_content
        return content
    def execute(self,logging_mode=None,print_log=None, tools= [], messages = [], run = None, model = None, mode = None):
        mode = mode if mode else None
        if print_log:
             self.print_log=print_log 
        content = self.get()
        if model:
             result = LLM.json_response_sync(prompt=LLM.cleanStringForLLM(content), messages = messages, run = None, model=model, request_type=self.__class__.__name__, mode=mode, logging_mode=logging_mode, timeout=None, print_log=self.print_log, tools=tools)
        else:
             result =  LLM.json_response_sync(prompt=LLM.cleanStringForLLM(content), messages = messages, run = None, request_type=self.__class__.__name__,mode=mode,logging_mode=logging_mode,timeout=None,print_log=self.print_log, tools=tools)
        if os.environ.get('debug',None):
             if result[1].get('reasoning',None):
                 print(f'reasoning for {self.__class__.__name__}: {result[1].get("reasoning")}')
                 del(result[1]['reasoning'])
        return result

class NewNodePrompt:
    def __init__(self, directive, input, categories, category_path):
        self.input = input
        self.categories = categories
        self.category_path = category_path
        self.directive = directive
        self.debug_content = ''''''
        self.print_log = None
        self.timestamps = None
        self.content = Template(r'''
Your job is to look at the existing categories and create an additional category to fit the new input. 
The new category should be disjoint from the existing categories.
NEVER use subjective criteria in your categorization.

Your response should always be in JSON format as follows. Respond with nothing but the JSON.

{
    "newCategory": your new category description here
}

input: $input

existing categories: $categories

The existing categories, as well as your new category, are sub-categories of this category_path: $category_path

sorting purpose: $directive

Think carefully to make sure that your new category is COMPLETELY disjoint from the existing categories.''')

    def get(self):
        content_template = self.content
        content = content_template.substitute({**self.__dict__})
        if self.timestamps:
             content = "current utcnow isoformat: " + datetime.utcnow().isoformat() + "\n" + content
        if os.environ.get('debug',None):
             content = content +'\n' + self.debug_content
        return content
    def execute(self,logging_mode=None,print_log=None, tools= [], messages = [], run = None, model = None, mode = None):
        mode = mode if mode else None
        if print_log:
             self.print_log=print_log 
        content = self.get()
        if model:
             result = LLM.json_response_sync(prompt=LLM.cleanStringForLLM(content), messages = messages, run = None, model=model, request_type=self.__class__.__name__, mode=mode, logging_mode=logging_mode, timeout=None, print_log=self.print_log, tools=tools)
        else:
             result =  LLM.json_response_sync(prompt=LLM.cleanStringForLLM(content), messages = messages, run = None, request_type=self.__class__.__name__,mode=mode,logging_mode=logging_mode,timeout=None,print_log=self.print_log, tools=tools)
        if os.environ.get('debug',None):
             if result[1].get('reasoning',None):
                 print(f'reasoning for {self.__class__.__name__}: {result[1].get("reasoning")}')
                 del(result[1]['reasoning'])
        return result

class LlmSplitPrompt:
    def __init__(self, elements, category_path, directive):
        self.category_path = category_path
        self.directive = directive
        self.elements = elements
        self.debug_content = ''''''
        self.print_log = None
        self.timestamps = None
        self.content = Template(r'''
Break the given category into 3-6 distinct, disjoint sub-categories with no possibility for overlap.

Here is the category_path. Your new subcategories will each be sub-paths of this path: $category_path

Respond only with the new subcategories, not the entire path.

Here is the purpose of the categorization tree: $directive

These are the elements that are currently in the given category. For each of them, map them to exactly one of your new subcategories. All elements must be mapped to exactly one new subcategory, and none of your subcategories can be empty.
$elements


Respond with a json as follows:
{
    "subcategories":{
        'new_subcategory':[element_ids],
        'other_subcategory:[other element_ids],
        ...
    }
}''')

    def get(self):
        content_template = self.content
        content = content_template.substitute({**self.__dict__})
        if self.timestamps:
             content = "current utcnow isoformat: " + datetime.utcnow().isoformat() + "\n" + content
        if os.environ.get('debug',None):
             content = content +'\n' + self.debug_content
        return content
    def execute(self,logging_mode=None,print_log=None, tools= [], messages = [], run = None, model = None, mode = None):
        mode = mode if mode else None
        if print_log:
             self.print_log=print_log 
        content = self.get()
        if model:
             result = LLM.json_response_sync(prompt=LLM.cleanStringForLLM(content), messages = messages, run = None, model=model, request_type=self.__class__.__name__, mode=mode, logging_mode=logging_mode, timeout=180, print_log=self.print_log, tools=tools)
        else:
             result =  LLM.json_response_sync(prompt=LLM.cleanStringForLLM(content), messages = messages, run = None, request_type=self.__class__.__name__,mode=mode,logging_mode=logging_mode,timeout=180,print_log=self.print_log, tools=tools)
        if os.environ.get('debug',None):
             if result[1].get('reasoning',None):
                 print(f'reasoning for {self.__class__.__name__}: {result[1].get("reasoning")}')
                 del(result[1]['reasoning'])
        return result

class InsertRowCondensePrompt:
    def __init__(self, categories, category_path, max_new_cats, min_new_cats, directive):
        self.min_new_cats = min_new_cats
        self.max_new_cats = max_new_cats
        self.category_path = category_path
        self.categories = categories
        self.directive = directive
        self.debug_content = ''''''
        self.print_log = None
        self.timestamps = None
        self.content = Template(r'''
Given the existing_categories, come up with between $min_new_cats and $max_new_cats new non-empty super_categories that contain the existing_categories.
Each of the existing_categories must be mapped to exactly one of the super_categories, with no duplication. No existing_categories may be ommited.
NEVER categorize as "{x}" and "{opposite of x}". 
NEVER include a generic category like "other fields."
Whenever possible, avoid making categories that are simply 'X + Y' to summarize categories X and Y. 
Instead, come up with original super_categories that represent a commonality between some subset of the existing_categories.

Both the existing categories and your new categories will be within this category_path:$category_path
existing_categories (id:description): $categories
organizational purpose: You are sorting according to $directive

Respond in the following stringified JSON format. Every existing category should be placed in exactly one of the new categories.
{
    newCategoryDescription: [old categoryIds that fit in the new category],
    otherNewCategoryDescription: [old categoryIds that fit in the new category],
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
    def execute(self,logging_mode=None,print_log=None, tools= [], messages = [], run = None, model = None, mode = None):
        mode = mode if mode else None
        if print_log:
             self.print_log=print_log 
        content = self.get()
        if model:
             result = LLM.json_response_sync(prompt=LLM.cleanStringForLLM(content), messages = messages, run = None, model=model, request_type=self.__class__.__name__, mode=mode, logging_mode=logging_mode, timeout=None, print_log=self.print_log, tools=tools)
        else:
             result =  LLM.json_response_sync(prompt=LLM.cleanStringForLLM(content), messages = messages, run = None, request_type=self.__class__.__name__,mode=mode,logging_mode=logging_mode,timeout=None,print_log=self.print_log, tools=tools)
        if os.environ.get('debug',None):
             if result[1].get('reasoning',None):
                 print(f'reasoning for {self.__class__.__name__}: {result[1].get("reasoning")}')
                 del(result[1]['reasoning'])
        return result

class BestFitPrompt:
    def __init__(self, categories, input, category_path, directive):
        self.category_path = category_path
        self.categories = categories
        self.input = input
        self.directive = directive
        self.debug_content = ''''''
        self.print_log = None
        self.timestamps = None
        self.content = Template(r'''
Determine to which of the categories the input belongs. If no category is an accurate fit or a new category would better describe the input, return false for ideal_fit_exists.

Your response should always be in JSON format as follows. Respond with nothing but the JSON.

{
    "categoryId": categoryId here or omit this field if no ideal fit exists,
    "proposed_new_category": a proposed new category if there is no fit that exists. It should be similar in intention to the existing categories.
}

Here is the CATEGORY_PATH to our current location. The category you choose will be appended to this path: $category_path

Here are the categories (categoryId:description) pairs : $categories

Here is the input: $input

Categorizational purpose: $directive
Please be very specific in your categorization. If no category is an accurate fit for the input, return false for 'ideal_fit_exists.'
Remember to put the categoryId in your output, NOT the description.
Think carefully about whether a good fit exists.''')

    def get(self):
        content_template = self.content
        content = content_template.substitute({**self.__dict__})
        if self.timestamps:
             content = "current utcnow isoformat: " + datetime.utcnow().isoformat() + "\n" + content
        if os.environ.get('debug',None):
             content = content +'\n' + self.debug_content
        return content
    def execute(self,logging_mode=None,print_log=None, tools= [], messages = [], run = None, model = None, mode = None):
        mode = mode if mode else None
        if print_log:
             self.print_log=print_log 
        content = self.get()
        if model:
             result = LLM.json_response_sync(prompt=LLM.cleanStringForLLM(content), messages = messages, run = None, model=model, request_type=self.__class__.__name__, mode=mode, logging_mode=logging_mode, timeout=None, print_log=self.print_log, tools=tools)
        else:
             result =  LLM.json_response_sync(prompt=LLM.cleanStringForLLM(content), messages = messages, run = None, request_type=self.__class__.__name__,mode=mode,logging_mode=logging_mode,timeout=None,print_log=self.print_log, tools=tools)
        if os.environ.get('debug',None):
             if result[1].get('reasoning',None):
                 print(f'reasoning for {self.__class__.__name__}: {result[1].get("reasoning")}')
                 del(result[1]['reasoning'])
        return result