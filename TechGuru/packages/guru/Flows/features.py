import importlib.util
import inspect
from abc import ABC, abstractmethod, ABCMeta
import uuid
import os
from ..GLLM import LLM
from datetime import datetime
import re
import json
import sys
from .internal_prompts import ExtractInfoPrompt, SummarizeMessagesPrompt
from packages.guru.cli.utils import guru_settings
from pathlib import Path
from functools import wraps
from concurrent.futures import ThreadPoolExecutor
from threading import Thread, Condition
import time
from models.database import Session
from models.conversation.llm_log import LLMLog

class FeatureMeta(ABCMeta):
    def __new__(cls, name, bases, namespace):
        new_namespace = {}
        for attr_name, attr_value in namespace.items():
            if getattr(attr_value, "__isabstractmethod__", False):
                attr_value = cls.decorate(attr_value)
            new_namespace[attr_name] = attr_value
        return super().__new__(cls, name, bases, new_namespace)
    
    @staticmethod
    def decorate(func):
        time_guru =  os.environ.get('time_guru')
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                if time_guru:
                    start_time = time.time()
                    print(f"running {func.__name__}...", flush=True)
                result = func(self, *args, **kwargs)
            finally:
                if time_guru:
                    print(f"finished {func.__name__} in {time.time() - start_time} seconds.", flush=True)
                self.status.notify_all()
            return result
        return wrapper


class Feature(ABC, metaclass=FeatureMeta):
    def __init__(self, assignment,featureType) -> None:
        from packages.guru.Flows.assignment import Assignment
        assert(isinstance(assignment, Assignment))
        self.assignment:Assignment = assignment
        self.id = str(uuid.uuid4())
        self.run = assignment.run
        self.featureType = featureType
        self.prevFeature=None
        self.status = None
        if hasattr(self, 'hidden'):
            if self.hidden:
                from packages.guru.Flows.tool import HIDDEN_TOOLS
                if self.__class__.__name__ not in HIDDEN_TOOLS:
                    HIDDEN_TOOLS.append(self.__class__.__name__)
        if assignment.prevAssignment:
            prevFeatures = [feature for feature in assignment.prevAssignment.features if feature.featureType == self.__class__.__name__]
            if len(prevFeatures)>1:
                raise Exception(f"Multiple instances of {self.__class__.__name__} found on prevAssignment!")
            if prevFeatures:
                self.prevFeature = prevFeatures[0]
                assert(isinstance(self.prevFeature, self.__class__))
        super().__init__()



    @abstractmethod
    def preAssignment(self):pass

    @abstractmethod
    def preLLM(self):pass

    @abstractmethod
    def postLLM(self):pass

    @abstractmethod
    def postResponse(self):pass
    
    @abstractmethod
    def postTool(self):pass

    @abstractmethod
    def postAssignment(self):pass

    @abstractmethod
    def checkComplete(self):
        return True

    def __str__(self):
        return f"id:{self.id}: assignment:{self.assignment}"


feature_classes = []


def load_feature_classes_from_folder(folder_path):
    """
    Dynamically load Python files from a given folder path and return a list of subclasses of Feature
    """
    global feature_classes
    global default_feature_classes

    project_dir = Path(guru_settings['project_dir'])
    def load_features_from_file(file_path):
        # Convert file_path to an absolute path to avoid relative path issues
        file_path = Path(file_path).resolve()

        # Now both paths are absolute, we attempt to compute the relative path
        try:
            relative_path = file_path.relative_to(project_dir)
            module_name = relative_path.with_suffix('').as_posix().replace('/', '.')
        except ValueError as e:
            print(f"Error processing {file_path}: {e}")
            return []
        # Calculate module name based on file path to keep the structure
        module_name = Path(file_path).relative_to(project_dir).with_suffix('').as_posix().replace('/', '.')
        
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        print(f"loaded module as modules[{module_name}]")
        sys.modules[module_name] = module
        
        return [cls for name, cls in inspect.getmembers(module) if inspect.isclass(cls) and issubclass(cls, Feature) and cls is not Feature]

    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.endswith('.py') and not file.startswith('__'):
                file_path = os.path.join(root, file)
                feature_classes.extend(load_features_from_file(file_path))

    for feature in default_feature_classes:
        if feature.__name__ not in [feature.__name__ for feature in feature_classes]:
            feature_classes.append(feature)

    return feature_classes

def load_feature_classes(file_path):
    """
    Dynamically load Python file and return a list of subclasses of Feature.
    """
    global feature_classes
    global default_feature_classes
    spec = importlib.util.spec_from_file_location("features", file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules['features']=module
    spec.loader.exec_module(module)
    feature_classes= [cls for name, cls in inspect.getmembers(module) if inspect.isclass(cls) and issubclass(cls, Feature) and cls is not Feature]
    for feature in default_feature_classes:
        if feature.__name__ not in [feature.__name__ for feature in feature_classes]:
            feature_classes.append(feature)

def wait_for(feature):
    if os.environ.get('time_guru'):
        print(f"waiting for {feature.__class__.__name__}")
        start_time = time.time()
    if not feature.status:
        if os.environ.get('time_guru'):
            print(f"no status found for {feature.__class__.__name__}. waiting...")
        time.sleep(1)
    if not feature.status or not isinstance(feature.status, Condition):
        raise Exception(f"feature has no status or status is not a Condition.")
    with feature.status:
        feature.status.wait()
    if os.environ.get('time_guru'):
        print(f"finished waiting for {feature.__class__.__name__} in {time.time() - start_time} seconds.")
    
def new(assignment, featureTemplate):
    feature_name = featureTemplate["featureName"]

    for feature_class in feature_classes:
        if feature_class.__name__ == feature_name:
            return feature_class(assignment, **featureTemplate.get('args', {}))

    raise Exception(f"No feature called {feature_name}. features: {[feat.__name__ for feat in feature_classes]}")



#TODO: if it has a message, the message and toolcall are not back-to-back and it causes an error. fix that. current fix: use acot.
class SelfMarkComplete(Feature):
    def __init__(self, assignment, 
                 with_message=None, 
                 addti_data=None,
                 select_next_assignment=True) -> None:
        super().__init__(assignment, self.__class__.__name__)
        from packages.guru.Flows.tool import Tool
        self.addti_to_gather = addti_data
        self.addti_data = {}
        self.with_message = with_message
        self.assignment.addObjective("When the other objectives are all completed, immediately call the 'mark_complete' tool.")
        self.assignment.addInstructions("NEVER narrate your intention to mark a task complete, or mention the mark_complete tool to the user.")
        self.assignment.check_complete_after_tools=True
        self.select_next_assignment = select_next_assignment
        self.assignment.tools.append(Tool(toolName='mark_complete',assignment=self.assignment, source_feature = self))
        self.assignment.message_after_complete = False

    def preAssignment(self):
        pass

    def preLLM(self):
        pass

    def postLLM(self):
        pass

    def postResponse(self):
        pass
    
    def postAssignment(self):pass

    def postTool(self):
        pass

    def checkComplete(self):
        return True
    
    def getToolJson(self, toolName):
        tool_json = {
            "type": "function",
            "function": {
                "name": "mark_complete",
                "description": "Mark the current assignment as complete.",
                "parameters": {
                    "type": "object",
                    "properties": {
                    },
                    "required": []
                }
            }
        }
        if self.with_message:
            self.assignment.addInstructions(f"When you mark_complete, you MUST simultaneously send a message to the user. The message should be based on this criteria: {self.with_message}")
        if self.addti_to_gather:
            for key, description in self.addti_to_gather.items():
                tool_json['function']['parameters']['properties'][key] = {
                    "type":"string",
                    "description": description
                }
                tool_json['function']['parameters']['required'].append(key)
        if self.select_next_assignment:
            if len(self.assignment.connectors)>1:
                tool_json['function']['parameters']['properties']['next_task'] = {
                    "type":"string",
                    "description": f"the name of the next task to be assigned, selected from this list: {[{c.targetAssignment:c.conditions} for c in self.assignment.connectors]}"
                }
                tool_json['function']['parameters']['required'].append('next_task')

        return tool_json
    
    def executeTool(self, toolName, args, tool_call_id):
        session = Session()
        with session:
            if toolName == 'mark_complete':
                #remove the tool call
                self.assignment.messages.pop()
                
                if self.addti_to_gather:
                    for key, value in args.items():
                        if key in list(self.addti_to_gather.keys()):
                            self.addti_data[key] = value
                if self.select_next_assignment:
                    if len(self.assignment.connectors)==1:
                        self.assignment.nextAssignment = self.assignment.connectors[0].targetAssignment
                    elif len(self.assignment.connectors)==0:
                        self.assignment.nextAssignment = 'end'
                    elif args.get('next_task',None):
                        next_task = args['next_task']
                        self.assignment.nextAssignment = next_task
                    else:
                        raise Exception(f"no next_task provided. options: {[{c.targetAssignment:c.conditions} for c in self.assignment.connectors]}")
                    print(f"next assignment: {self.assignment.nextAssignment}")
                self.assignment.complete = True
                return "success"
            raise Exception(f"no tool with name {toolName}")



class PreventRunawayCalls(Feature):
    '''
    '''
    def __init__(self, assignment, max_cycles = None, mode = 'raise_exception', message = None) -> None:
        super().__init__(assignment, self.__class__.__name__)
        self.mode=mode
        self.message=message
        self.max_cycles = int(max_cycles) if max_cycles else None
        self.triggered = False
        if not max_cycles:
            self.max_cycles= 10
        self.counter = 0

    def preAssignment(self):
        pass

    def preLLM(self):
        self.counter+=1
        if self.counter%self.max_cycles==0:
            if self.mode == 'raise_exception':
                raise Exception(f"This failed because the total number of cycles exceeded {self.max_cycles}.")
            elif self.mode == 'wrap_up':
                if self.triggered:
                    raise Exception(f"This failed because the total number of cycles exceeded {self.max_cycles}, and the LLM did not wrap up!")
                if not self.message:
                    self.assignment.messages.append({'role':'system','content':'WARNING: this task will be automatically ended in one more message. Please use that message to wrap up as best you can, providing a response to the user to the best of your capabilities.'})
                else:
                    self.assignment.messages.append({'role':'system','content':self.message})

            self.triggered = True
            
    def postLLM(self):
        pass

    def postResponse(self):
        pass
    
    def postAssignment(self):pass

    def postTool(self):pass

    def checkComplete(self):
        return True 

class AddDynamicDataToInstructions(Feature):
    '''
    LLM looks at previous conversation and adds details to instructions per your request.
    '''
    def __init__(self, assignment, data_to_gather, model=None) -> None:
        super().__init__(assignment, self.__class__.__name__)
        if not self.assignment.prevAssignment:
            raise Exception("no previous assignment, so it makes no sense to use ADDTI.")
        
        self.data_to_gather = data_to_gather
        self.gathered_data = []
        self.model = model
        prev_smc = self.assignment.prevAssignment.getFeatureByType('SelfMarkComplete')
        if prev_smc:
            if prev_smc.addti_data:
                data_from_prev = prev_smc.addti_data
                for key, value in data_from_prev.items():
                    matches = [new_data for new_data in self.data_to_gather if key==new_data['name']]
                    if matches:
                        self.gathered_data.append({'name':key,'value':value})
                        self.data_to_gather = [x for x in self.data_to_gather if x['name']!=key]
        if self.prevFeature:
            print("prevInstance of ADDTI found. checking...")
            for data in self.prevFeature.gathered_data:
                if data.get('persist',None):
                    matches = [new_data for new_data in self.data_to_gather if data['name']==new_data['name']]
                    if matches:
                        print(f"found matches: {[m['name'] for m in matches]}")
                        if matches[0]['overwrite']:
                            pass
                        else:
                            self.gathered_data.append(data)
                            self.data_to_gather = [x for x in self.data_to_gather if x['name']!=data['name']]
                    else:
                        self.gathered_data.append(data)

        


    def preAssignment(self):
        print(f"getting data...")
        if self.data_to_gather:
            prompt = ExtractInfoPrompt(
                pairs = [x['name'] + ':' + x['description'] for x in self.data_to_gather],
                history = self.assignment.prevAssignment.getMessages(),
            )  
            response = prompt.execute()
            log = response.log
            response = response.get()
            with Session() as session:
                LLMLog.fromGuruLogObject(log, self.assignment.conversation.id, session)
                session.commit()
            
            for data in self.data_to_gather:
                data.update({'value':response[data['name']]})
                self.gathered_data.append(data)
        print(f"\nadding instructions:" +  f"\n{x['name']}: {x['value']}" for x in self.gathered_data if not x.get('invisible', False))
        self.assignment.addInstructions('\n'.join([f"{x['name']}: {x['value']}" for x in self.gathered_data if not x.get('invisible',False)]))

    def preLLM(self):
        pass


    def postLLM(self):
        pass

    def postResponse(self):
        pass
        
    def postAssignment(self):pass

    def postTool(self):pass

    def checkComplete(self):
        return True

    def getVariable(self, name):
        for data in self.gathered_data:
            if data['name']==name:
                return data['value']
        return None

class Timestamps(Feature):
    def __init__(self, assignment) -> None:
        super().__init__(assignment, self.__class__.__name__)

    
    def preAssignment(self):pass

    def preLLM(self):
        self.assignment.addContext(f"This is the current datetime.now(): {datetime.now()}")


    def postLLM(self):
        pass

    def postResponse(self):
        pass


    def postTool(self):pass

    def postAssignment(self):pass

    def checkComplete(self):
        return True
    
class AdvancedCOT(Feature):
    def __init__(self, assignment, model='gpt-3.5-turbo', num_messages_summarization_threshold = 6, length_summarization_threshold = 15000,tool_window=8, logging='none',circle_back_after=5) -> None:
        super().__init__(assignment, self.__class__.__name__)
        self.model = model
        self.num_messages_summarization_threshold = num_messages_summarization_threshold
        self.length_summarization_threshold = length_summarization_threshold
        self.tool_window = tool_window
        self.logging = logging
        self.circle_back_after = circle_back_after
        self.check_in = False
        system_message = {'role':'system','content':f'Begin assignment: {assignment.id}'}

        if self.prevFeature:
            if not assignment.persist_tool_calls:
                self.promptMessages = [message for message in self.prevFeature.promptMessages if 'tool_call_id' not in str(message)]
                self.tool_calls = []
            else:
                self.promptMessages = self.prevFeature.promptMessages
                self.tool_calls = self.prevFeature.tool_calls
        else:
            self.promptMessages = []
            self.tool_calls = []
        self.promptMessages.append(system_message)
        if not self.assignment.keep_messages:
            self.promptMessages = []
            self.tool_calls = []
        self.assignment.addInstructions(f"""
Your message chain and tool calls are automatically moved to the context of this message. Older messages are summarized, and only the {self.tool_window} most recent tool_calls are displayed.
Messages with role 'tool_tracker' show when tool calls were made in the conversation. 'tool_tracker' messages are automatically generated and should not be added manually, and maintain the chronological order of tool calls.
NOTE: if the most recent message is a 'tool_tracker', it means that all tool calls in that 'tool_tracker' have been completed since the last time you sent a message to the user.
""")
    
    def preAssignment(self):pass

    def preLLM(self):
        print(f"moving messages into context...")
        if len(self.assignment.messages)>1:
            newMessages = [self.assignment.messages[0]] 
            for i,message in enumerate(self.assignment.messages[1:]):
                print(f"{message} added to context.")
                self.promptMessages.append(message)
            self.assignment.messages = newMessages
        if self.promptMessages:
            if self.logging=='local':
                if self.run:
                    self.log(f'logs/{self.run}/acot/{datetime.now().strftime("%Y-%m-%d %H")}.txt',self.promptMessages)
                else:
                    self.log(f'logs/acot/{datetime.now().strftime("%Y-%m-%d %H")}.txt',self.promptMessages)
                    
        if self.tool_calls:
            print(self.tool_calls)
            self.assignment.addContext(f"""
------BEGIN TOOL CALLS------
{[tool_call for tool_call in (self.tool_calls[-self.tool_window:] if len(self.tool_calls)>self.tool_window else self.tool_calls)]}
------END TOOL CALLS------
""")

        self.assignment.addContext(f"""
This conversation history should be the guide for your next action.
YOU ARE CONTINUING FROM THE END OF THESE MESSAGES.
------BEGIN CONVERSATION HISTORY------
{[{'message_no':i, 'content':json.dumps(message)} for i,message in enumerate(self.promptMessages)]}
------END CONVERSATION HISTORY------
""")
      
        if self.check_in:
            if self.promptMessages[-1]['role'] == 'tool_tracker':
                self.assignment.addContext("#####You have done a lot without talking to the user!!! Please wrap up the current task, then reach out and update them. Remember, all of the tool calls in the most recent tool_tracker message have been completed since the last time you checked in with the user!#####")
            else:
                self.check_in = False

    def postLLM(self):
        pass

    def postResponse(self):
        with Session() as session:
            print(f"summarizing messages for ACOT...")
            if len(self.promptMessages) < self.num_messages_summarization_threshold and len(str(self.promptMessages)) < self.length_summarization_threshold:
                print(f"skipping.")
                return
            
            keep_num = 3
            if len(self.promptMessages) < 3:
                keep_num = len(self.promptMessages)-2
                if keep_num < 1:
                    keep_num = 1


            prompt = SummarizeMessagesPrompt(
                history = self.promptMessages[:-keep_num]
            )
            call = prompt.execute()
            log = call.log
            response = call.get()
            LLMLog.fromGuruLogObject(log, self.assignment.conversation.id,session)
            if response.get('replacements', None):
                self.replace_messages(replacements=response['replacements'])
            self.displayState()
            session.commit()

    def postTool(self):
        '''
        The tool call itself goes into the promptMessages. If the last message in promptMessages is a tool_tracker message, the new tools are added to it. Otherwise, a new tool_tracker message is created.
        '''
        all_messages = self.assignment.messages[1:]

        #extract and separate calls and responses.
        responses = []
        calls = []
        for message in all_messages:
            if message['role']=='tool':
                responses.append(message)
            elif message.get('tool_calls',None):
                for tool_call in message['tool_calls']:
                    calls.append(tool_call)
            else:
                self.promptMessages.append(message)
            
        self.assignment.messages = [self.assignment.messages[0]]   
        
        pairs = []
        for call in calls:
            call_id = call['id']
            for response in responses:
                if response['tool_call_id']==call_id:
                    pairs.append((call, response))
                    responses.remove(response)
                    break
        if responses:
            for response in responses:
                pairs.append(('request_lost.', responses[i]))
        if len(pairs) != len(calls):
            raise Exception("Not all calls resulted in a pair...")
        
        index = len(self.tool_calls)
        j=0
        new_calls = []
        for i in range(index, index+len(pairs)):
            print(f"adding tool_call_id: {i}. pair: {pairs[j]}")
            if self.promptMessages[-1]['role']== 'tool_tracker':
                self.promptMessages[-1]['tool_calls'].append(i)
                if len(self.promptMessages[-1]['tool_calls'])>self.circle_back_after:
                    self.check_in = True
            else:
                self.promptMessages.append({'role':'tool_tracker','tool_calls':[i]})
            new_calls.append(f"tool_call_id:{i}\nrequest: {json.dumps(pairs[j][0]['function'])}\nresponse:{json.dumps(pairs[j][1]['content'])}")
            j += 1
        if len(new_calls)>1:
            self.tool_calls.append({'parallel_set':new_calls})
        else:
            if new_calls:
                self.tool_calls.append(new_calls[0])
        
        #if the length of the promptmessages is greater than summarization_thresholds, call postResponse to summarize.
        if len(self.promptMessages) > self.num_messages_summarization_threshold or len(str(self.promptMessages)) > self.length_summarization_threshold:
            self.postResponse()

    def postAssignment(self):
        self.displayState()

    def checkComplete(self):
        return True

    def delete_messages(self, indexes):
        parsed= re.findall(r'\d+', str(indexes))
        try:
            indexes = [int(x) for x in parsed]
        except Exception as e:
            print(f"unable to parse indexes due to {e}")

        self.promptMessages = [message for i, message in enumerate(self.promptMessages) if i not in indexes]

    def replace_messages(self, replacements):
        '''
        replacements: {
            indexes_to_replace: [list of indexes to replace],
            summary: "summary of the messages that are being replaced"
        }
        '''
        # map current messages to indexes
        message_map = [
            {'index': i, 'message': message} for i, message in enumerate(self.promptMessages)
        ]

        # Create a dictionary of replacements for easier lookup
        replacements_dict = {replacement['indexes_to_replace'][0]: replacement for replacement in replacements}

        # Make a set of indexes to remove
        indexes_to_remove = set(index for replacement in replacements for index in replacement['indexes_to_replace'])

        # Create a new list to hold the updated messages
        new_messages = []

        # Iterate through the message_map and replace messages as needed
        for entry in message_map:
            index = entry['index']
            message = entry['message']

            # Check if the current index is the start of a replacement
            if index in replacements_dict:
                replacement = replacements_dict[index]
                # Add the replacement message
                new_messages.append({'role':'auto_summary', 'content':f"{replacement['summary']}"})
                # We don't need to add the replaced messages, so we just continue
                continue
            elif index not in indexes_to_remove:
                # Add the original message if it's not in the indexes to remove
                new_messages.append(message)

        self.promptMessages = new_messages

        
    def processToolCall(pair):
        return '''
    Based on the tool call and the 
    '''

    def log(self, path, message):
        # Ensure the directory exists
        directory = os.path.dirname(path)
        if not os.path.exists(directory):
            os.makedirs(directory)

        # Append the message to the file
        with open(path, 'a+') as f:
            f.write('\n\n' + str(message))

    def displayState(self):
        print(f"\n\nACOT state: {self.promptMessages}\nAssignment messages: {self.assignment.messages[1:]}\n\n")

    def getState(self):
        return f"{self.promptMessages}\n{self.assignment.messages[1:]}"

def run(method_name, feature):
    if method_name not in ['preAssignment', 'preLLM', 'postLLM', 'postResponse', 'postTool', 'postAssignment', 'checkComplete']:
        raise Exception(f"no method called {method_name} in {feature.__class__.__name__}")
    method = getattr(feature, method_name)
    return method()






default_feature_classes = [SelfMarkComplete, PreventRunawayCalls, AddDynamicDataToInstructions, Timestamps, AdvancedCOT]

