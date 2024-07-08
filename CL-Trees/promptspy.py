from string import Template
import os

os.environ['debug']=os.environ.get('debug','')
class CondensePrompt:
    def __init__(self, category_path, categories, directive):
        self.category_path = category_path
        self.categories = categories
        self.directive = directive
        self.debug = '$debug'
        self.debug_content = ''''''
        self.content = Template(r'''Take a deep breath and read carefully.
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
        content = content.replace('$debug',self.debug_content if os.environ['debug'] else '')
        return content

class CreateElementPrompt:
    def __init__(self, data):
        self.data = data
        self.debug = '$debug'
        self.debug_content = '''
Additionally, include a field called 'notes' that explains your reasoning, describes anything that was especially difficult to do, and provides recommendations for clearer instructions, if applicable.
'''
        self.content = Template(r'''Your job is to take the input_data and provide the following fields:
task_name: a description of what occurred in the task in fewer than 5 words. This should be as specific as possible.
task_summary: a more detailed description of what occurred in the task, fewer than 2 paragraphs. Do not explain relevance, simply describe the process as succinctly as possible.
relevant_data: any relevant data from the task that may need to be accessed in the future. Include a description of how to interpret the data, if necessary.

here is the data:
$data

You do not need to concern yourself with the rules, regulations, or instructions themselves as provided in the data.
Instead, focus on what tasks have been accomplished and the details of those tasks.

Respond with a JSON containing the fields described above.

$debug''')

    def get(self):
        content_template = self.content
        content = content_template.substitute({**self.__dict__})
        content = content.replace('$debug',self.debug_content if os.environ['debug'] else '')
        return content

class CheckFitPrompt:
    def __init__(self, input_description, step_description):
        self.input_description = input_description
        self.step_description = step_description
        self.debug = '$debug'
        self.debug_content = '''
In addition to the fields shown in the json below, also include 'reasoning,' where you describe why you made the choices that you made, challenges that this task included, and recommendations for clearer instructions.
'''
        self.content = Template(r'''Determine whether the input_description belongs in the given step_description. 

input_description:
$input_description

step_description:
$step_description

$debug

Respond with a JSON as follows:
{
    fits:true or false
}
''')

    def get(self):
        content_template = self.content
        content = content_template.substitute({**self.__dict__})
        content = content.replace('$debug',self.debug_content if os.environ['debug'] else '')
        return content

class NewNodePrompt:
    def __init__(self, existing_generalized_steps, specific_task, overall_goal):
        self.existing_generalized_steps = existing_generalized_steps
        self.specific_task = specific_task
        self.overall_goal = overall_goal
        self.debug = '$debug'
        self.debug_content = ''''''
        self.content = Template(r'''Given a set of existing_generalized_steps and a specific_task, create a new generalized_step to fit the specific_task.

Your new generalized_step should be approximately the same level of generalization as the existing_generalized_steps.
Your new generalized_step should be similar in length, specificity, and other attributes to the existing_generalized_steps.
The specific_task is the most recent task that was completed towards the overall_goal.

existing_generalized_steps: $existing_generalized_steps

specific_task: $specific_task

overall_goal: $overall_goal

respond with a json as follows:
{
    "new_generalized_step": (your generalized description.)
}''')

    def get(self):
        content_template = self.content
        content = content_template.substitute({**self.__dict__})
        content = content.replace('$debug',self.debug_content if os.environ['debug'] else '')
        return content

class BestFitPrompt:
    def __init__(self, step_path, steps, input):
        self.step_path = step_path
        self.steps = steps
        self.input = input
        self.debug = '$debug'
        self.debug_content = ''''''
        self.content = Template(r'''Take a deep breath and read carefully.
Determine to which of the steps the input belongs. If no step is an accurate fit, return false for ideal_fit_exists.

Your response should always be in JSON format as follows. Respond with nothing but the JSON.

{
    "ideal_fit_exists": true or false
    "stepId": stepId here
}

Here is the step_path to our current location. The category you choose will be appended to this path: $step_path

Here are the steps (step:description) pairs : $steps

Here is the input: $input

Remember to put the stepId in your output, NOT the description.
Think carefully about whether a good fit exists.
''')

    def get(self):
        content_template = self.content
        content = content_template.substitute({**self.__dict__})
        content = content.replace('$debug',self.debug_content if os.environ['debug'] else '')
        return content

class ProcessContextPrompt:
    def __init__(self, information, categories):
        self.information = information
        self.categories = categories
        self.debug = '$debug'
        self.debug_content = ''''''
        self.content = Template(r'''Use the given information to determine how likely each category is to have the best match.

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
        content = content.replace('$debug',self.debug_content if os.environ['debug'] else '')
        return content

class GetContextPrompt:
    def __init__(self, current_time, visible_nodes, current_task_or_query):
        self.current_time = current_time
        self.visible_nodes = visible_nodes
        self.current_task_or_query = current_task_or_query
        self.debug = '$debug'
        self.debug_content = '''
Also include 'notes,' where you explain your reasoning, points of confusion, recommendations for these instructions, or questions you have.
Justify each choice, including specifically the choice to expand or maintain.
'''
        self.content = Template(r'''datetime.now(): $current_time

Your job is to navigate through a timeline of events and curate a set of information relevant to the current_task_or_query.
The timeline is a tree that starts with general steps that can be 'expanded' to more and more specific sub-steps until you reach the actual 'EVENT' objects that have occurred. 'EVENT' nodes cannot be expanded.
The timeline tree contains only historical events.
For some tasks, a simple timeline as it exists might be ideal. For other tasks, specific details might be needed from some of the steps, while others might not matter to the task at all.
It is your job to explore and determine what information to pass to the agent who is performing the task.

Your job is to categorize each visible_node as one of these two options:
1. 'expand'. assign this category to nodes for which seeing greater granularity might assist with the current_task_or_query. The result will be the division of that node into smaller, more descriptive substeps.
2. 'maintain'. maintain nodes for those nodes for which the level of detail is sufficient for the current_task_or_query, but we don't need further details.
3. 'remove'. remove nodes only if you are completely certain that expanding them could not lead to finding information that would make it easier to execute the current_task_or_query.

Think carefully about how the historical data in visible_nodes can be used to help inform the current_task_or_query.

Your ultimate goal is to get the visible_nodes to an optimal state where it contains all the information you may need to execute the current_task_or_query.

Here are the currently visible_nodes on the timeline tree. Each node represents a step in the timeline.
visible_nodes:
$visible_nodes

current_task_or_query:
$current_task_or_query

Respond with a list of categories, where each category applies to the visible_node at the same index in visible_nodes.
The length of your list_of_categories MUST be identical to the length of visible_nodes.

$debug

Respond with a json as follows:
{
    list_of_categories:[a category for each visible_node here],
    notes:your explanation of why you made your choices.
}''')

    def get(self):
        content_template = self.content
        content = content_template.substitute({**self.__dict__})
        content = content.replace('$debug',self.debug_content if os.environ['debug'] else '')
        return content

class LlmSplitPrompt:
    def __init__(self, max_num_subtasks, task_description, individual_steps, existing_categories):
        self.max_num_subtasks = max_num_subtasks
        self.task_description = task_description
        self.individual_steps = individual_steps
        self.existing_categories = existing_categories
        self.debug = '$debug'
        self.debug_content = '''
In addition to the fields shown in the json below, also include 'reasoning,' where you describe why you made the choices that you made, challenges that this task included, and recommendations for clearer instructions.
'''
        self.content = Template(r'''The task description below describes the current task on a general level.

Your job is to come up with sub-tasks of the current task which encompass the individual_steps below, subject to the following constraints:
1. The number of sub-tasks you provide must be at least 2 and at most $max_num_subtasks.
2. All individual_steps must be assigned to a sub-task.
3. All sub_tasks must have at least one individual_step.
4. The chronology of the individual_steps must be preserved in your sub_tasks.
5. Your sub_tasks must be chronological.
6. You may not use any of the categories already defined in existing_categories.
7. The union of your substeps, in the order you provide them, MUST be equivalent to the original individual_steps list. You may NOT rearrange the objects.
8. Do not include the TimeRanges or timestamps in your response.
Before submitting your answer, think carefully about whether each of the constraints has been satisfied.

task_description: $task_description

individual_steps: $individual_steps

existing_categories: $existing_categories

$debug


respond with a json as follows:
{
    (your_substep_name_here):[list of individual_steps assigned to this substep],
    (your_next_substep_name_here):[list of individual steps assigned to this substep],
    ... and so on.
}''')

    def get(self):
        content_template = self.content
        content = content_template.substitute({**self.__dict__})
        content = content.replace('$debug',self.debug_content if os.environ['debug'] else '')
        return content

class MakeContextSummaryPrompt:
    def __init__(self, given_data, current_task_or_query):
        self.given_data = given_data
        self.current_task_or_query = current_task_or_query
        self.debug = '$debug'
        self.debug_content = ''''''
        self.content = Template(r'''Your job is to take the given_data use it to make a report containing all relevant_context for the current_task_or_query.
Only include information from the given_data. You may summarize the given_data and cherrypick it, but you may not modify or add to it.
Information in given_data is completed steps pulled out of a timeline, and the order of the given_data is the chronological order in which the steps described in the given_data occurred.


given_data:
$given_data

current_task_or_query:
$current_task_or_query

respond with a json as follows:
{
    "relevant_data": (all relevant context from given_data),
    "notes": (any notes you have about the data and the query.)
}''')

    def get(self):
        content_template = self.content
        content = content_template.substitute({**self.__dict__})
        content = content.replace('$debug',self.debug_content if os.environ['debug'] else '')
        return content

class NewTopLayerPrompt:
    def __init__(self, max_steps, task_description, substeps):
        self.max_steps = max_steps
        self.task_description = task_description
        self.substeps = substeps
        self.debug = '$debug'
        self.debug_content = '''
In addition to the fields shown in the json below, also include 'reasoning,' where you describe why you made the choices that you made, challenges that this task included, and recommendations for clearer instructions.
'''
        self.content = Template(r'''You are summarizing the current progress in task described in task_description. 
Your job is to take the existing_substeps and express the same process in fewer general_steps.


You must meet the following constraints:
1. The number of general_steps you provide must be at least 2 and at most $max_steps.
2. All existing_substeps must be mapped to a general_step.
3. All general_steps must have at least one individual_step.
4. The chronology of the existing_substeps must be preserved in your general_steps.
5. Your general_steps must be chronological with respect to the provided timestamps.
6. The union of your general_steps, in the order you provide them, MUST be equivalent to the original list. You may NOT rearrange the objects.
7. Do not include TimeRanges or timestamps in your response.

task_description: $task_description

existing_substeps: $substeps

$debug

Respond with a JSON as follows:
{
    (general_step_description):[list of existing_substeps mapped to this general_step],
    (next_general_step_description):[list of existing_substeps mapped to this general_step]
    ... and so on.
}''')

    def get(self):
        content_template = self.content
        content = content_template.substitute({**self.__dict__})
        content = content.replace('$debug',self.debug_content if os.environ['debug'] else '')
        return content

class MakeCandidatePromptPrompt:
    def __init__(self):
        self.debug = '$debug'
        self.debug_content = ''''''
        self.content = Template(r'''Give an example of a job candidate. They should be clearly predisposed to an existing field of some kind. Fill out the JSON below with information about the candidate.

Your response should always be in JSON format as follows. Respond with nothing but the JSON.

{
    "name": candidate name,
    "skills": skills here,
    "experience": experience here,
    "otherInfo": any other interesting info about the job candidate
}''')

    def get(self):
        content_template = self.content
        content = content_template.substitute({**self.__dict__})
        content = content.replace('$debug',self.debug_content if os.environ['debug'] else '')
        return content

