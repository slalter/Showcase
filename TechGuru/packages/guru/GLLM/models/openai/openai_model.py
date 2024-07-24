from datetime import datetime
from ..llmmodel import LLMModel, LLMCall, LLMResponse, Log
from openai import OpenAI
import json
import os
from openai import APITimeoutError
import time


class OpenAIModel(LLMModel):
    def __init__(self, model, timeout, **kwargs):
        self.api_key = os.environ.get('OPENAI_KEY', '')
        if not self.api_key:
            raise Exception("OpenAI API key not found")
        self.model = model
        self.client = OpenAI(api_key=self.api_key, timeout=timeout, max_retries=0)
        self.name = "OpenAI " + model
        super().__init__(model, self.name, **kwargs)

    def get_cost(self):
        costs = {#K tokens
            10e3:{
                'gpt-3.5-turbo': (0.0015,0.0030),
                'gpt-4-turbo': (0.003,0.009),
                'gpt-4o': (0.004,.12)
            },
            10e6:{#M tokens
                'gpt-4o-mini': (.15,.6)
            }
        }

        
        #I promise I left it this way as a joke. I'm not a monster.
        price = [(x,y) for x,y in [[*price]*(prefix/1000) for prefix, model_name, price in [(prefix,*model.items()) for prefix,model in [(prefix, costs[prefix]) for prefix in costs.keys()]] if model_name == self.model]][0]
        return price

    def execute(self, messages=None, prompt=None, tools=None, temp: float = 0.5, description='', timeout=None, print_log=True, json_mode=False, max_tries=4):
        log = Log(mode=self.__class__.__name__+ " " +self.model, print_log=print_log)
        messages = messages or []
        if prompt:
            messages = [{"role": "system", "content": prompt}] + messages

        if not tools:
            tools = []
        tries = 0
        while tries < max_tries:
            try:
                start_time = datetime.now()
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temp,
                    response_format={'type':'json'} if json_mode else None,
                )
                elapsed_time = (datetime.now() - start_time).total_seconds()
                log.add_attempt(messages, response, elapsed_time, request_type=description, llm_method=self.name + ': json_mode' if json_mode else '', costs=self.get_cost())

                response_obj = LLMResponse(response.model_dump_json(), response.choices[0].message.content)
                if json_mode and not isinstance(response_obj.response, dict):
                    response_obj.response = json.loads(response_obj.response)
                return LLMCall(response_obj, log, status='success', tool_calls=response.choices[0].message.tool_calls)
            except Exception as e:
                time.sleep(1.8**tries)
                if isinstance(e, APITimeoutError):
                    self.client = OpenAI(
                        timeout=timeout,
                        max_retries=0,
                        api_key=self.api_key
                    )
                elapsed_time = (datetime.now() - start_time).total_seconds()
                log.add_attempt(messages, str(e), elapsed_time, request_type=description, llm_method=self.name + ': json_mode' if json_mode else '', costs=self.get_cost())
                print(f"json_response failed due to {e}")
                tries += 1

        return LLMCall(LLMResponse(None, None), log, status='failure')
