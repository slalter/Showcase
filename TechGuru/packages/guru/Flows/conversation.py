import openai
from datetime import datetime
import json
import re
from .utils import remove_non_printable_chars
from .connector import Connector
from .assignment import Assignment
import os
from concurrent.futures import ThreadPoolExecutor
from . import features as features
from models.conversation.db_conversation import DBConversation

#TODO: create testing with variations, LLM-led?

class Conversation:
    def __init__(self, initJson = None, guiqueue=None, popup=None, run='', conversation_id='',entry_assignment = ''): 
        self.prevAssignment = None

        if not os.environ.get('tools_path',None):
            raise Exception("call initialize and specify your tools_path.")
        if not initJson:
            initJson = {}
        initJson = initJson.copy()
        print("loading conversation...")
        self.assignmentTemplates = initJson['assignments']
        self.personality = initJson['personality']
        self.id = conversation_id
        self.currentAssignment = Assignment(assignmentTemplate=self.getAssignmentByID('initAssignment' if not entry_assignment else entry_assignment), personality=self.personality, popup= popup, run=run,conversation_id=conversation_id, conversation=self)
        print(f"current assignment: {self.currentAssignment.id}")
        self.guiqueue = guiqueue
        self.popup = popup
        self.run = run

    def getAssignmentByID(self, id):
        if id == "end":
            return "end"
        for result in self.assignmentTemplates:
            print(result)
            if result['id'] == id:
                return result
        raise Exception(f"No assignment with ID: {id}")

    def getMessages(self):
        return self.currentAssignment.messages

    async def printStreamingResponse(self, message):
        return await self.currentAssignment.printStreamingResponse(message)
    
    #resumes the conversation automatically if all expected tool calls have been returned! Otherwise, returns false.
    def deliverExternalToolCalls(self, session, tool_calls, results):
        for tool_call, tool_result in zip(tool_calls, results):
            if tool_call['id'] in self.currentAssignment.expected_external_tool_results:
                self.currentAssignment.messages.append({
                                        "tool_call_id": tool_call['id'],
                                        "role": "tool",
                                        "name": tool_call['function']['name'],
                                        "content": str(tool_result),
                                    } 
                                ) 
                self.currentAssignment.expected_external_tool_results.remove(tool_call['id'])
            else:
                raise Exception(f"ERROR: did not recognize external tool result with id {tool_call['id']}!")
        if self.currentAssignment.expected_external_tool_results:
            print("warning: still expecting more tool results!")
            return {'external_tools':self.currentAssignment.expected_external_tool_results}
        else:
            print(f"recieved all tool calls. Current messages: {json.dumps(self.currentAssignment.messages, indent=4)}")
            response = self.currentAssignment.resumeAfterExternals(session)
            if response.get('external_tools', None):
                return response
            if response['status'] == 'current':
                return response['content']
            else:
                if response['nextAssignment']['id']=='end':
                    return 'end'
                assignmentTemplate = self.getAssignmentByID(response['nextAssignment']['id'])
                print(f"NEXT ASSIGNMENT: {response['nextAssignment']}")
                reprompt = response['nextAssignment'].get('reprompt', None)
                print(f"reprompt: {reprompt}")

                with ThreadPoolExecutor() as executor:
                    results = list(executor.map(lambda feature: features.run('postAssignment', feature), self.currentAssignment.features))
                    
                self.prevAssignment = self.currentAssignment
                self.currentAssignment = Assignment(assignmentTemplate, self.personality, prevAssignment=self.prevAssignment, popup=self.popup,run=self.run,conversation_id=self.id, conversation=self)
                db_conversation = session.get(DBConversation, self.id)
                db_conversation.current_assignment = response['nextAssignment']['id']
                session.commit()
                with ThreadPoolExecutor() as executor:
                    results = list(executor.map(lambda feature: features.run('preAssignment', feature), self.currentAssignment.features))
                self.currentAssignment.initialized=True
                if reprompt:
                    print("reprompting...")
                    response = self.getResponse(session, [{'role':'system', 'content':reprompt}])
                    return response
                
    def getResponse(self, session, messages=None):
        if self.currentAssignment.expected_external_tool_results:
            raise Exception(f"waiting for external tool results: {self.currentAssignment.expected_external_tool_results}")
        if messages:
            if isinstance(messages, list):
                self.currentAssignment.messages += messages
            else:
                self.currentAssignment.messages.append({'role':'user','content':messages})
        
        response = self.currentAssignment.getLLMResponse(session)
        if response.get('paused'):
            return response
        if response.get('external_tools', None):
            return response
        if response['status'] == 'current':
            return response['content']
        else:
            try:
                if response['nextAssignment']['id']=='end':
                    return 'end'
            except Exception as e:
                raise Exception(f"Error: {e}. Response: {response}")
            assignmentTemplate = self.getAssignmentByID(response['nextAssignment']['id'])
            print(f"NEXT ASSIGNMENT: {response['nextAssignment']}")
            reprompt = response['nextAssignment'].get('reprompt', None)
            print(f"reprompt: {reprompt}")
            self.currentAssignment.task = "Determining Next Task"
            with ThreadPoolExecutor() as executor:
                results = list(executor.map(lambda feature: features.run('postAssignment', feature), self.currentAssignment.features))
            self.prevAssignment = self.currentAssignment
            self.currentAssignment = Assignment(assignmentTemplate, self.personality, prevAssignment=self.prevAssignment, popup=self.popup,run=self.run,conversation_id=self.id, conversation=self)
            db_conversation = session.get(DBConversation, self.id)
            db_conversation.current_assignment = response['nextAssignment']['id']
            session.commit()
            with ThreadPoolExecutor() as executor:
                results = list(executor.map(lambda feature: features.run('preAssignment', feature), self.currentAssignment.features))
            self.currentAssignment.initialized=True
            
            if reprompt:
                print("reprompting...")
                response = self.getResponse(session,[{'role':'system', 'content':reprompt}])
                return response
            else:
                return self.getResponse(session)
            
    def close(self):
        self.complete = True
        #and what else?

 