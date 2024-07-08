import uuid
from .connector import Connector
from ..GLLM import LLM
from . import features
import json
import asyncio
from .tool import Tool, getTool, HIDDEN_TOOLS
from .internal_prompts import AssignmentPrompt, NextAssignmentPrompt, CheckCompletePrompt
from typing import List
from concurrent.futures import ThreadPoolExecutor, as_completed
from packages.ws.utils.celery import emitFromCelery
from models.conversation.db_conversation import DBConversation
from models.conversation.llm_log import LLMLog
from models.database import Session
from models.conversation.db_conversation import addLog

class Assignment:

    def __init__(self, assignmentTemplate, personality, conversation, context = "", instructions = None, prevAssignment = None, popup=None, run = '', conversation_id='', tasks=''):
        from .features import Feature
        self.run = run
        self.conversation_id = conversation_id
        self.prevAssignment:Assignment = prevAssignment
        self.id = assignmentTemplate['id']
        self.message_after_complete = assignmentTemplate.get('message_after_complete',True)
        self.check_complete_after_tools = assignmentTemplate.get('check_complete_after_tools',False)
        self.keep_messages = assignmentTemplate.get('keep_messages',True)
        self.persist_tool_calls = assignmentTemplate.get('persist_tool_calls',True)
        self.guidelines = assignmentTemplate['guidelines']
        self.objectives = assignmentTemplate['objectives']
        self.connectors = [Connector(con['targetAssignment'],con['criteria'], con.get('reprompt',None)) for con in assignmentTemplate['connectors']]
        self.personality = personality
        self.features:List[Feature] = []
        self.instructions = instructions if instructions else []
        self.context = context
        self.tools = []
        self.popup = popup
        self.complete = False
        self.conversation = conversation
        self.expected_external_tool_results = [] #external_tools, etc
        self.nextAssignment = None
        self.prev_response = None
        self.tasks = tasks if tasks else ['loading']

        for tool in assignmentTemplate['tools']:
            self.tools.append(Tool(toolName=tool, assignment=self))
        for featureTemplate in assignmentTemplate["features"]:
            print(f"adding feature... {featureTemplate}")
            self.addFeature(featureTemplate)
        
        self.messages = [{"role":'system', 'content':self.getPrompt().get()}]
        if prevAssignment and len(prevAssignment.messages)>1:
            self.messages+=prevAssignment.messages[1:]

        #if no id, make one.
        if id:
            self.id = id
        else:
            self.id = uuid.uuid4()

    def addConnector(self, connector):
        self.connectors.append(connector)

    def __str__(self):
        #returns a string.
        dicOut = {
            "objectives":self.objectives,
            "guidelines":self.guidelines,
            "messages":[msg.get() for msg in self.messages],
            "connectors":[con.getDic() for con in self.connectors],
            "id":self.id
        }
        return json.dumps(dicOut)
    
    def getFeatureByType(self, type_string):
        for feature in self.features:
            if feature.featureType == type_string:
                return feature
        return None
    
    def addMessage(self,msg):
        self.messages.append(msg)
    
    def addTool(self, toolName):
        self.tools.append(Tool(self, toolName=toolName))

    def runTool(self, toolName, toolArgs, tool_call_id=None):
        with Session() as session:
            addLog(self.conversation_id, f'tool_call: {toolName}', {"tool":toolName, "args":toolArgs},session)
            session.commit()
            if toolName == 'multi_tool_use.parallel':
                tool_calls = toolArgs['tool_uses']
                with ThreadPoolExecutor() as executor:
                    futures = []
                    for tool in tool_calls:
                        tool_obj = getTool(self, tool['recipient_name'].split('.')[1])
                        futures.append(executor.submit(tool_obj.execute, tool['parameters'], tool_call_id))

                    results = [future.result() for future in as_completed(futures)]
                return results
            
            print(f"running {toolName} with: {toolArgs}")
            tool = [tool for tool in self.tools if tool.toolName == toolName][0]
            result = tool.execute(args=toolArgs, tool_call_id=tool_call_id)
            if not result:
                result = ''
            print(f"result for {toolName}: {result}")
            addLog(self.conversation_id, f'tool_result: {toolName}', {"tool":toolName, "result":result}, session)
            session.commit()
            return result

    #TODO: antiquated
    async def printStreamingResponse(self, msg):
        #add new message from customer
        self.addMessage({"role":"user", "content": msg})

        #reset context. Note: context should only be modified on a per-message basis.
        self.resetContext()

        for feat in self.featureIds:
            await features.getFeatureById(feat).preLLM()
        
        response = LLM.streamResponse(self.messages, prompt=self.getPrompt())
        txt = ""
        for chunk in response:
            if chunk:
                txt += chunk
                print(chunk,end="", flush=True)
        self.addMessage({'role':'assistant','content':txt})

        for feat in self.featureIds:
            await features.getFeatureById(feat).postResponse()
        #implement. move this to post-response.
        if len(self.messages)>1:
            complete = await self.checkComplete()
        if complete:
            nextassignment = await self.getNextassignment()
            return {'status':"complete", 'nextAssignment':nextassignment}
        
        return {'status':'current', 'content':response}


    def getLLMResponse(self,session, msg:str=None):
        #get db object.
        closed, paused = session.query(DBConversation.closed, DBConversation.paused).filter(DBConversation.id == self.conversation_id).first()
        if closed:
            raise Exception("Conversation is closed!")

        #add new message from user. If paused, we still want to add this.
        if msg:
            self.addMessage({"role":"user", "content": msg})

        if paused:
            return 'paused'

        #reset context. Note: context should only be modified on a per-message basis.
        self.resetContext()
        self.tasks = ['Waiting for OpenAI']
        with ThreadPoolExecutor() as executor:
            print(f"running prellm. Features:{[f.featureType for f in self.features]}")
            results = list(executor.map(lambda feature: features.run('preLLM', feature), self.features))

        print("waiting for openai...")
        log, response = self.getPrompt().execute(messages=self.messages[1:] if len(self.messages)>1 else [], tools=[tool.tool_json for tool in self.tools],run=self.run)
        LLMLog.fromGuruLogObject(log,self.conversation_id,session)
        session.commit()
        
        if not response['choices'][0]['message'].get('content', None):
            response['choices'][0]['message']['content'] = ''
        self.messages.append(response['choices'][0]['message'])
        self.prev_response = response
        
        #if tool calls, set tasks accordingly.
        if 'tool_calls' in response['choices'][0]['message']:
            tool_calls = response['choices'][0]['message']['tool_calls']
            self.tasks = [tool['function']['name'] for tool in tool_calls]
        print("running postllm.")
        with ThreadPoolExecutor() as executor:
            results = list(executor.map(lambda feature: features.run('postLLM', feature), self.features))
        

        if 'tool_calls' in response['choices'][0]['message']:
            tool_calls = response['choices'][0]['message']['tool_calls']
            fake_tool_calls = [tool for tool in tool_calls if tool['function']['name'] not in [tool.toolName for tool in self.tools]]
            if fake_tool_calls:
                #remove tool calls, kick back to LLM
                self.messages.pop()
                self.messages.append({"role":"system","content":f"make sure to only call tools that are defined in your instructions! {[call['function']['name'] for call in fake_tool_calls]} are not valid tool calls!"})
                return self.getLLMResponse(session)
            else:
                tool_calls = [tool for tool in tool_calls if tool['function']['name'] in [tool.toolName for tool in self.tools]]
                if tool_calls:
                    messages_to_add = []
                    if response['choices'][0]['message'].get('content', None):
                        self.displayResponse(session,response['choices'][0]['message']['content'])
                    print(f"{len(tool_calls)} tools detected.")
                    
                    with ThreadPoolExecutor() as executor:
                        tool_results = list(executor.map(lambda tool_call: self.runTool(tool_call['function']['name'], json.loads(tool_call['function']['arguments']), tool_call_id = tool_call['id']), tool_calls))

                    for tool_call, tool_result in zip(tool_calls, tool_results):
                        if tool_result == '!EXTERNAL_TOOL':
                            self.expected_external_tool_results.append(tool_call['id'])
                            continue
                        if tool_call['function']['name'] not in HIDDEN_TOOLS:
                            messages_to_add.append(
                                {
                                    "tool_call_id": tool_call['id'],
                                    "role": "tool",
                                    "name": tool_call['function']['name'],
                                    "content": str(tool_result),
                                } 
                            ) 
                        else:
                            #remove the tool call from the messages.
                            #if there are multiple tool calls, only remove this one! if there is only one, check if there is content as well. If not, remove the entire message.
                            if len(tool_calls) == 1:
                                #check for content.
                                if not response['choices'][0]['message'].get('content', None):
                                    self.messages.pop()
                            else:
                                #modify the message itself, removing just the tool call.
                                self.messages[-1]['tool_calls'] = [call for call in self.messages[-1]['tool_calls'] if call['id'] != tool_call['id']]
                    self.messages += messages_to_add
                    if self.expected_external_tool_results:
                        return {'external_tools':self.expected_external_tool_results}
                    if len(tool_calls)==1 and tool_calls[0]['function']['name'] == 'mark_complete':
                        return self.postToolProcess(False,session)
                    return self.postToolProcess(True,session)
                else:
                    return self.postToolProcess(False,session)
        else:
            return self.postToolProcess(False,session)

        
    def postToolProcess(self, tools, session):
        complete = self.complete
        complete_checked = False
        if tools:
            if self.check_complete_after_tools:
                complete = self.checkComplete()   
                complete_checked = True
            with ThreadPoolExecutor() as executor:
                results = list(executor.map(lambda feature: features.run('postTool', feature), self.features))
            if not complete:
                return self.getLLMResponse(session)
        response = self.prev_response['choices'][0]['message']['content']
        
        
        print("displaying response.")
        if (not complete) or self.message_after_complete:
            self.displayResponse(session,response)
        

    
        if not complete and not complete_checked:
            complete = self.checkComplete()
            complete_checked=True

        if complete and not self.nextAssignment:
            self.task = 'Determining Next Task'
            with ThreadPoolExecutor() as executor:
                futures = []
                for feature in self.features:
                    futures.append(executor.submit(features.run, 'postResponse', feature))
                
                futures.append(executor.submit(self.getNextassignment))
                results = [future.result() for future in as_completed(futures)]


            return {'status':"complete", 'nextAssignment':results[-1]}
        elif not complete:
            with ThreadPoolExecutor() as executor:
                results = list(executor.map(lambda feature: features.run('postResponse', feature), self.features))
            return {'status':'current', 'content':response}
        else:
            self.task = 'Determining Next Task'
            with ThreadPoolExecutor() as executor:
                results = list(executor.map(lambda feature: features.run('postResponse', feature), self.features))
            if complete:
                if self.nextAssignment:
                    matched_connector = [con for con in self.connectors if con.targetAssignment == self.nextAssignment]
                    if matched_connector:
                        return {'status':"complete", 'nextAssignment':{'id':self.nextAssignment, 'reprompt':matched_connector[0].reprompt}}
                    else:
                        raise Exception(f"could not find connector for next assignment {self.nextAssignment}")
                else:
                    raise Exception(f"complete but no next assignment found. response: {response}.")
            else:
                return {'status':'current', 'content':response}
    
    def resumeAfterExternals(self,session):
        return self.postToolProcess(True,session)

    def displayResponse(self, session, responseText):
        print(f"creating new message object...")
        from models import Message
        
        db_message = Message(role='assistant',content=responseText,dbconversation_id=self.conversation_id)
        
        session.add(db_message)
        session.commit()
        emitFromCelery(DBConversation.getSID(self.conversation_id,session), 'message', {'role':'assistant','content':responseText})

    def getNextassignment(self):
        session = Session()
        print("getting next assignment.")
        if not self.connectors:
            return {'id':'end'}
        if len(self.connectors) == 1:
            return {"id":self.connectors[0].targetAssignment,"reprompt":self.connectors[0].reprompt}
        conditions = [{"id":con.targetAssignment,"conditions":con.conditions} for con in self.connectors]
        prompt = NextAssignmentPrompt(
            conditions= str(conditions),
            conversation=self.getMessages())
        log, response = prompt.execute()
        with session:
            LLMLog.fromGuruLogObject(log,self.conversation_id,session)
            session.commit()

        print(response)
        print([con.targetAssignment for con in self.connectors])
        reprompt = [con.reprompt for con in self.connectors if con.targetAssignment == response['best_match']][0]
        return {"id":response['best_match'],"reprompt":reprompt}

    def checkComplete(self):
        if self.complete:
            return self.complete
        if not self.connectors:
            return False
        if self.getFeatureByType('SelfMarkComplete'):
            return self.complete
        
        with ThreadPoolExecutor() as executor:
            results = list(executor.map(lambda feature: features.run('checkComplete', feature), self.features))

        for result in results:
            if not result:
                return False
        
        prompt = CheckCompletePrompt(
            objectives=str(self.objectives),
            history=f"{self.getPrompt().get()} {self.messages[1:] if len(self.messages)>1 else ''}"
        )
        log, result = prompt.execute()
        with Session() as session:
            LLMLog.fromGuruLogObject(log,self.conversation_id,session)
            session.commit()

        print(f"check complete result: {result}")
        return result['all_objectives_complete']
        
    def addObjective(self,objective):
        self.objectives.append(objective)

    def addFeature(self, featureTemplate):
        self.features.append(features.new(self, featureTemplate))
    
    def addContext(self, context):
        self.context += '\n' + context

    def addInstructions(self, instructions):
        self.instructions.append(instructions)
    
    def resetContext(self):
        self.context = ""

    def getPrompt(self):
        return AssignmentPrompt(
            instructions=self.instructions,
            personality=self.personality,
            guidelines=self.guidelines,
            objectives=self.objectives,
            context=self.context
        )
    #this is so that features which modify how messages are stored can more easily be used to make current message state.
    def getMessages(self):
        ACOT = self.getFeatureByType('AdvancedCOT')
        if ACOT:
            return ACOT.getState()
        else:
            return self.messages[1:]


    def __str__(self) -> str:
        return str(self.id)
