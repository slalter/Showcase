from anthropic import AnthropicVertex
import json
from ..llmmodel import LLMModel, LLMCall, LLMResponse, Log
from datetime import datetime
import os
import time
import traceback

MODEL_DICT = {
    'sonnet35':'claude-3-5-sonnet@20240620'
}

class AnthropicModel(LLMModel):
    def __init__(self, model, timeout, **kwargs):
        '''
        authed thru gcloud
        '''
        LOCATION="us-east5"
        self.model=model
        self.client = AnthropicVertex(region=LOCATION, project_id="gurucloudai",timeout=timeout if timeout else 120)
        self.name = "GoogleAnthropic" + self.model
        self.max_tokens = kwargs.get('max_tokens', 1024)
        super().__init__(model, self.name, **kwargs)

    def getCost(self):
        return 0.003, 0.003


    def execute(self, messages=None, prompt=None, tools=None, temp: float = 0.5, description='', print_log=True, json_mode=False, max_tokens=1024, max_tries=4, **kwargs):
        '''does not support timeout parameter'''
        log = Log(mode=self.__class__.__name__, print_log=print_log)
        messages = messages or []
        if prompt and not messages:
            messages = [{"role":"user","content":prompt}]
            prompt = ""
        if json_mode:
            messages = messages + [{"role":"assistant","content":"Here is the requested JSON:{"}]
        if not tools:
            tools = []
        tries = 0
        while tries < max_tries:
            try:
                startTime = datetime.now()
                args = {
                    "max_tokens":max_tokens,
                    "messages":messages,
                    "model":MODEL_DICT[self.model],
                    "temperature":temp,
                }
                if tools:
                    tools= [self.format_tool(tool) for tool in tools.copy()]
                    args['tools'] = tools
                if prompt:
                    args['system'] = prompt

                result = self.client.messages.create(
                    **args
                )
                elapsedTime = (datetime.now() - startTime).total_seconds()
                log.add_attempt(messages, 
                                result.model_dump(), 
                                elapsedTime, request_type=description, llm_method = self.name + ': json_mode' if json_mode else '',costs=self.getCost())
                
                resp = '{' if json_mode else ''
                text = next((content.text for content in result.content if content.type == 'text'),None)
                tool_calls = [{
                    'id':content.id,
                    'function':{
                        'name':content.name,
                        'arguments':content.input
                    }
                } for content in result.content if content.type == 'tool_use']
                response = LLMResponse(result.model_dump(),resp + text)
                if json_mode:
                    if not isinstance(response.response, dict):
                        response.response = json.loads(response.response)
                call = LLMCall(response, log, tool_calls= tool_calls)
                call.status = 'success'
                return call
            except Exception as e:
                elapsedTime = (datetime.now() - startTime).total_seconds()
                log.add_attempt(messages, str(e), 
                                elapsedTime, request_type=description, llm_method = self.name + ': json_mode' if json_mode else '',costs=self.getCost())

                print(f"LLM Call failed due to {traceback.format_exc()}")
                time.sleep(1.8**tries)                
                tries += 1

        return LLMCall(LLMResponse(None, None), log, status='failure')
    
    @staticmethod
    def format_tool(tool):
        '''reformats an openai tool definition into an anthropic tool definition.'''
        # Extract the relevant details from the input tool definition
        function_name = tool["function"]["name"]
        function_description = tool["function"]["description"]
        parameters = tool["function"]["parameters"]["properties"]
        
        # Create the translated tool structure
        translated_tool = {
            "name": function_name,
            "description": function_description,
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
        
        # Populate the properties and required fields
        for param, details in parameters.items():
            translated_tool["input_schema"]["properties"][param] = {
                "type": details["type"],
                "description": details["description"]
            }
            
            # Handle special cases for nested objects (like insertions)
            if details["type"] == "array":
                translated_tool["input_schema"]["properties"][param]["items"] = details["items"]
            
            # Add required parameters
            if "required" in details and details["required"]:
                translated_tool["input_schema"]["required"].append(param)
        
        return translated_tool

def main():
    s35 = AnthropicModel(timeout=120, model='sonnet35')
    resp1 = s35.execute(prompt="Once upon a time")
    resp2 = s35.execute(
        prompt="Provide a list of key:value pairs demonstrating examples of cookies. Respond in JSON format.",
        json_mode=True,
        )
    print(resp1.get())
    print(resp1.log.to_dict())
    print(resp2.get())
    print(resp2.log.to_dict())

if __name__=='main':
    main()