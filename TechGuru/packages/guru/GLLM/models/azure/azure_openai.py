from datetime import datetime
from ..llmmodel import LLMModel, LLMCall, LLMResponse, Log
import json
import os
import requests
import time
import traceback

#azure version
MODEL_TO_DEPLOYMENT = {
    'gpt-4-32k': 'Cade-GPT4-32',
    'gpt-4': 'Cade-GPT-4',
    'gpt-4-turbo-preview':'gpt-4-turbo-2024-04-09',
    'gpt-4-1106-preview':'CadenzaaGPT4Preview',
    'gpt-3.5-turbo':'gpt-35-turbo',
    'gpt-4-turbo':'gpt-4-turbo-2024-04-09',
    'gpt-4o':'gpt-4o'
}


class AzureOpenAIModel(LLMModel):
    def __init__(self, model, timeout, **kwargs):
        self.api_key = os.environ.get('AZURE_API_KEY', '')
        if not self.api_key:
            raise Exception("Azure API key not found")
        self.resource_name = os.environ.get('AZURE_RESOURCE_NAME', '')
        if not self.resource_name:
            raise Exception("Azure resource name not found")
        self.model = model
        self.timeout = timeout
        self.name = "Azure " + model

        self. deployment_name = MODEL_TO_DEPLOYMENT.get(self.model)
        if not self.deployment_name:
            raise Exception(f"Deployment name not found for model {self.model}")
        super().__init__(model, self.name, **kwargs)

    def get_cost(self):
        return {
            'gpt-3.5-turbo': (0.0015, 0.002),
            'gpt-4-turbo': (0.003, 0.003),
            'gpt-4o': (0.004, 0.004)
        }.get(self.model)

    def execute(self, messages=None, prompt=None, tools=None, temp: float = 0.5, request_type='', print_log=True, json_mode=False, max_tries=4):
        log = Log(mode=self.__class__.__name__ + " " + self.model, print_log=print_log)
        messages = messages or []
        if prompt:
            messages = [{"role": "system", "content": prompt}] + messages

        if not tools:
            tools = []


        url = f"https://{self.resource_name}.openai.azure.com/openai/deployments/{self.deployment_name}/chat/completions?api-version=2023-12-01-preview"
        headers = {'Content-Type': 'application/json', 'api-key': self.api_key}
        payload = {'messages': messages, 'temperature': temp, 'response_format': 'json' if json_mode else None}
        if tools:
            payload['tools'] = tools

        tries = 0
        while tries < max_tries:
            try:
                start_time = datetime.now()
                response = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
                response_text = response.text
                elapsed_time = (datetime.now() - start_time).total_seconds()
                log.add_attempt(messages, response_text, elapsed_time, request_type=request_type, llm_method=self.name + ': json_mode' if json_mode else '', costs=self.get_cost())
                if response.status_code == 200:
                    response_obj = LLMResponse(response_text, response_text)
                    if json_mode and not isinstance(response_obj.response, dict):
                        response_obj.response = json.loads(response_obj.response)
                    return LLMCall(response_obj, log, status='success')
            except Exception as e:
                time.sleep(1.8**tries)
                elapsed_time = (datetime.now() - start_time).total_seconds()
                log.add_attempt(messages, str(e), elapsed_time, request_type=request_type, llm_method=self.name + ': json_mode' if json_mode else '', costs=self.get_cost())
                print(f"LLM Call failed due to {traceback.format_exc()}")
                tries += 1

        return LLMCall(LLMResponse(None, None), log, status='failure')
