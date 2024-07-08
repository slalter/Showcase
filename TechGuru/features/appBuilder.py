from packages.guru.Flows.features import Feature, wait_for
import os
from IPython import embed_kernel
from IPython.core.interactiveshell import InteractiveShell
from contextlib import redirect_stdout, redirect_stderr
import io
from models.conversation.llm_log import LLMLog
from models.conversation.db_conversation import addLog
import json
import traceback
import re
from features.appBuilderFunctions.handler import jsonHandler, executeHandler
from packages.guru.GLLM import LLM
from packages.guru.Flows.utils import CannotProceedException
from models.database import Session
#TODO: pyright settings.
#TODO: 'what task will you do next' -> context (setTask method)
#TODO: invisible tools
#TODO: better logging on assignment change
from features.appBuilderFunctions.handler import TOOL_LIST
from features.context_sets.context_sets import getContext
class AppBuilder(Feature):
    def __init__(self, 
                 assignment, 
                 project_id = None, 
                 object_request_id = None,
                 tools= None,
                 max_context_length = 10000,
                 semantic_threshold = 0.9,
                 context_sets = None,
                 submit_is_final=False,
                 mode = 'default',
                 file_path = None) -> None:
        if not file_path and not (project_id and object_request_id):
            raise Exception('Either file_path or project_id and object_request_id must be provided')
        super().__init__(assignment,self.__class__.__name__)
        self.max_context_length = max_context_length
        self.semantic_threshold = semantic_threshold
        self.context_sets = context_sets
        self.submit_is_final = submit_is_final
        self.mode = mode
        self.file_path = file_path

        #semantically similar objects
        self.visible_method_ids_s = []
        self.visible_model_ids_s = []
        self.design_decision_ids_s = []

        #objects that came from a request
        self.visible_method_ids = []
        self.visible_model_ids = []
        self.design_decision_ids = []

        self.context_dict = {}
        self.code = ''
        self.project_id = project_id
        self.main_object_request_id = object_request_id
        self.current_task = ''
        '''
        This will be embedded and compared to various things to curate context.
        '''

        self.object_request_ids = []
        if self.mode == 'test':
            self.create_test_object()
        if self.file_path:
            with open(self.file_path, 'r') as f:
                self.code = f.read()

        for tool in tools:
            if tool not in TOOL_LIST:
                raise Exception(f"Tool {tool} not in TOOL_LIST")
            self.addTool(tool)

        if self.prevFeature:
            if self.prevFeature.code:
                self.code = self.prevFeature.code
            if self.prevFeature.context_dict:
                self.context_dict = self.prevFeature.context_dict
            if self.prevFeature.object_request_ids:
                self.object_request_ids = self.prevFeature.object_request_ids
            if self.prevFeature.visible_method_ids:
                self.visible_method_ids = self.prevFeature.visible_method_ids
            if self.prevFeature.visible_model_ids:
                self.visible_model_ids = self.prevFeature.visible_model_ids
            if self.prevFeature.design_decision_ids:
                self.design_decision_ids = self.prevFeature.design_decision_ids
            if self.prevFeature.visible_method_ids_s:
                self.visible_method_ids_s = self.prevFeature.visible_method_ids_s
            if self.prevFeature.visible_model_ids_s:
                self.visible_model_ids_s = self.prevFeature.visible_model_ids_s
            if self.prevFeature.design_decision_ids_s:
                self.design_decision_ids_s = self.prevFeature.design_decision_ids_s
            if self.prevFeature.current_task:
                self.current_task = self.prevFeature.current_task
            if self.prevFeature.main_object_request_id:
                self.main_object_request_id = self.prevFeature.main_object_request_id
            if self.prevFeature.assigned_object_request_string:
                self.assigned_object_request_string = self.prevFeature.assigned_object_request_string
            if self.prevFeature.max_context_length:
                self.max_context_length = self.prevFeature.max_context_length
            if self.prevFeature.semantic_threshold:
                self.semantic_threshold = self.prevFeature.semantic_threshold


    def preAssignment(self):
        self.assignment.addInstructions("You do NOT need to include any of the actual code in messages to the user. The user will be able to see your tool calls, your current code, your object requests, and everything else via a nice ui.")
        self.assignment.addInstructions("the only way you can update your code is via tools. Simply having the code in your message will not update the code.")


        if self.file_path:
            return

        from models import ObjectRequest
        #get the main object request's description.
        with Session() as session:
            if self.main_object_request_id =='MAIN':
                self.current_task == 'Design the app routes and main application logic.'
                self.assigned_object_request_string = ''
            else:
                main_or = session.query(ObjectRequest).filter(ObjectRequest.id == self.main_object_request_id).first()
                self.current_task = main_or.description
                self.assigned_object_request_string = f'''
object_type: {main_or.object_type}
description: {main_or.description}
name: {main_or.name}
''' + f'''
input_class_definition: {main_or.io_pair.input_class.__str()}
output_class_definition: {main_or.io_pair.output_class.__str()}
example_io_pairs: {main_or.io_pair.example_pairs}
''' if main_or.io_pair else ''

                    
            self.updateDesignDecisionDict(session)

            if self.context_sets:
                for context_set in self.context_sets:
                    self.assignment.addInstructions(getContext(session, self, context_set))

            if self.main_object_request_id != 'MAIN':
                self.assignment.addInstructions("You should not be sending messages unless directly requested in the prompt. Interact only with your tools - some of which may send a message to the user or a coworker, as described.")


        #fill context with:
        #method requests + statuses
        #model requests + statuses
        #relevant standardizations
        #test cases from one level up (X visible, Y hidden)
        #semantically similar methods and classes that currently exist (only in some steps)
        #current state of the code for this task

        pass

    def preLLM(self):
        if self.file_path:
            lines = self.code.split('\n')
            numbered_code = '\n'.join([str(i+1) + ': ' + line for i, line in enumerate(lines)])
            self.assignment.addContext(f'''
------YOUR CODE SO FAR-------
{numbered_code}
------END CODE-------'''
            )
            return
        
        with Session() as session:
            self.refreshContextDict(session)
        self.assignment.addContext(json.dumps(self.context_dict))
        if self.assigned_object_request_string:
            self.assignment.addContext(f'''
    ------YOUR TASK-------
    {self.assigned_object_request_string}
    ------END TASK-------'''     )
            
        lines = self.code.split('\n')
        numbered_code = '\n'.join([str(i+1) + ': ' + line for i, line in enumerate(lines)])
        self.assignment.addContext(f'''
------YOUR CODE SO FAR-------
{numbered_code}
------END CODE-------'''
)                                   


    def postLLM(self):
        pass

    def postResponse(self):
        pass

    def postTool(self):
        #check for loops in the requested objects across all conversations.
        pass

    def checkComplete(self):
        return True
    
    def postAssignment(self):
        pass

    def updateDesignDecisionDict(self, session):
        '''
        Updates the existing design decisions that are visible to the llm based on semantic similarity to the task.
        '''
        from models import DesignDecision
        with Session() as session:
            design_decision = session.query(DesignDecision).first()
            if not design_decision:
                return
            nearest = design_decision.nearest(session, LLM.getEmbedding(self.current_task), limit=10, threshold=self.semantic_threshold)
            self.design_decision_ids_s = [d.id for d in nearest]

    def refreshContextDict(self, session):
        from models import ObjectRequest, Model, Method, DesignDecision
        object_requests:list[ObjectRequest] = session.query(ObjectRequest).filter(ObjectRequest.id.in_(self.object_request_ids)).all()
        models:list[Model] = session.query(Model).filter(Model.id.in_(self.visible_model_ids)).all()
        methods:list[Method] = session.query(Method).filter(Method.id.in_(self.visible_method_ids)).all()
        design_decisions:list[DesignDecision] = session.query(DesignDecision).filter(DesignDecision.id.in_(self.design_decision_ids)).all()
        design_decisions_s = session.query(DesignDecision).filter(DesignDecision.id.in_(self.design_decision_ids_s)).all()
        context_dict ={
            'object_requests':[
                object_request.getStatusString() for object_request in object_requests
            ],
            'models':[
                model.__str__() for model in models
            ],
            'methods':[
                method.__str__() for method in methods
            ],
            'standardizations':[
                design_decision.__str__() for design_decision in design_decisions
            ]

        }
        if len(json.dumps(context_dict)) > self.max_context_length:
            if self.main_object_request_id != 'MAIN':
                self.addLog(f'context too long: {len(json.dumps(context_dict))}', {'context_dict':context_dict}, session)
            else:
                self.addLog(f'context too long: {len(json.dumps(context_dict))}', {'context_dict':context_dict}, session)
        else:
            if design_decisions_s:
                dds_strings = [dd.__str__() for dd in design_decisions_s]
                for dds_string in dds_strings:
                    if len(json.dumps(context_dict)) + len(dds_string) < self.max_context_length:
                        context_dict['standardizations'] += dds_string
                    else:
                        addLog(f'did not add all dds_strings to context', {'last_used_dds':dds_string, 'dds_strings':dds_strings}, session)
                        break
        self.context_dict = context_dict      
        session.commit()

    def saveCode(self, session):
        '''
        saves the code to the appropriate model.
        '''
        from models import Project, ObjectRequest
        if self.main_object_request_id == 'MAIN':
            #save to main project
            project = session.query(Project).filter(Project.id == self.project_id).first()
            project.code = self.code
            session.commit()
        elif self.main_object_request_id:
            #save to the object request
            object_request = session.query(ObjectRequest).filter(ObjectRequest.id == self.main_object_request_id).first()
            object_request.code = self.code
            session.commit()
        else:
            return 



    def getToolJson(self, toolName):
        return jsonHandler(toolName)

    def executeTool(self, toolName, args, tool_call_id):
        session = Session()
        with session:
            try:
                return executeHandler(toolName, args, tool_call_id,session, self)
            except Exception as e:
                print(f"traceback: {traceback.format_exception(e)}")
                session.rollback()
                self.addLog('error in tool execution', {
                    'toolName': toolName,
                    'args': args,
                    'tool_call_id': tool_call_id,
                    'error': str(e),
                    'traceback': traceback.format_exception(e)
                },
                session)
                session.commit()
                if isinstance(e, CannotProceedException):
                    raise e
                return f'error:{str(e)}'

    def addTool(self, toolName):
        from packages.guru.Flows.tool import Tool
        self.assignment.tools.append(Tool(self.assignment, toolName, self))

    def getObjectRequests(self, session):
        from models import ObjectRequest
        return session.query(ObjectRequest).filter(ObjectRequest.id.in_(self.object_request_ids)).all()

    def addLog(self, message, data, session):
        from models import Project, ObjectRequest
        if self.main_object_request_id == 'MAIN':
            project = session.query(Project).filter(Project.id == self.project_id).first()
            if not project:
                raise Exception(f'Project {self.project_id} not found.')
            project.addLog(message, data, session)
        elif self.main_object_request_id:
            main_object_request = session.query(ObjectRequest).filter(ObjectRequest.id == self.main_object_request_id).first()
            main_object_request.addLog(message, data, session)
        else:
            addLog(self.assignment.conversation_id, message, data, session)
        session.commit()

    def createTestObject(self):
        with Session() as session:
            from models import ObjectRequest, Method
            test_or = ObjectRequest(
                object_type = 'method',
                name = 'get_sum_diff_prod_quot',
                description = 'a method to get the sum, difference, product, and quotient of two numbers.',
                io_pair = None,
                code = 'test',
                status = 'pending',
                project_id = self.project_id,
            )
            method_model = Method(
                name = 'get_sum_diff_prod_quot',
                description = 'a method to get the sum, difference, product, and quotient of two numbers.',
                code = '',
                project_id = self.project_id,
            )
            test_or.code_object = method_model
            session.add(method_model)
            session.add(test_or)
            session.commit()
            self.object_request_ids.append(test_or.id)
