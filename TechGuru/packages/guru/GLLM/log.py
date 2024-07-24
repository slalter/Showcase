import os
import json
import csv
from datetime import datetime
import requests
from openai.types.chat import ChatCompletion
import traceback
import ast

def getCosts(model):
    '''
    returns (prompt, completion) in dollars per thousand tokens.
    '''
    if model in ["gpt-4-1106-preview", 'gpt-4-turbo-preview']:
        return (0.01, 0.03)
    if model in ["gpt-4", "gpt-4-0613"]:
        return (0.03, 0.06)
    if model == "gpt-4-32k":
        return (0.06, 0.12)
    if model in ["gpt-3.5-turbo", "gpt-3.5-turbo-1106", "gpt-3.5-turbo-0125"]:
        return (0.0005, 0.0015)
    #print(f"unknown model: {model}. Returning gpt-4-turbo-preview for cost.")
    return (0.01, 0.03)

class Log:
    class Attempt:
        def __init__(self, messages, response, elapsed_time, request_type=None, llm_method=None, costs:tuple[float,float]|None=None):
            self.time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.request_type = request_type
            self.elapsed_time = elapsed_time
            self.request_content = messages
            self.response_content = self._parse_response(response)
            self.request_tokens, self.response_tokens, self.total_tokens, self.model = self._extract_response_details(self.response_content)
            self.costs = costs
            self.cost = self._calculate_cost()
            self.llm_method = llm_method

        def _parse_response(self, response):
            if isinstance(response, str):
                try:
                    return json.loads(response)
                except Exception as e:
                    try:
                        return json.loads(ast.literal_eval(response).decode('utf-8'))
                    except Exception as e2:
                        print(f"Unable to parse response of type str due to: {e}, {e2}. response: {response}")
            elif isinstance(response, requests.Response):
                try:
                    return response.json()
                except Exception as e:
                    print(f"Unable to parse requests.Response object due to: {e}. response: {response}")
            elif isinstance(response, ChatCompletion):
                try:
                    return response.model_dump(exclude_unset=True)
                except Exception as e:
                    print(f"Unable to parse ChatCompletions object due to: {e}. response: {response}")
            #if its bytes, try to decode it
            elif isinstance(response, bytes):
                try:
                    return json.loads(response.decode('utf-8'))
                except Exception as e:
                    print(f"Unable to parse response of type bytes due to: {e}. response: {response}")
            return response

        def _extract_response_details(self, response):
            if not isinstance(response, dict):
                try:
                    response = json.loads(response)
                except Exception as e:
                    self.response_content += f"Unable to parse response! \n response:\n{response}\n\nexception: \n{traceback.format_exception(e)}.\n type: {type(response)}"
                    return 0,0,0,0 
            request_tokens = response['usage'].get('prompt_tokens') or response['usage'].get('input_tokens')
            response_tokens = response['usage'].get('completion_tokens') or response['usage'].get('output_tokens')
            total_tokens = response['usage'].get('total_tokens') or request_tokens + response_tokens
            model = response['model']
            return request_tokens, response_tokens, total_tokens, model

        def _calculate_cost(self):
            prompt_cost, completion_cost = self.costs or getCosts(self.model)
            return (self.request_tokens * prompt_cost + self.response_tokens * completion_cost) / 1000

        def to_dict(self):
            return {
                'Time': self.time,
                'Request Tokens Used': self.request_tokens,
                'Response Tokens Used': self.response_tokens,
                'Total Tokens Used': self.total_tokens,
                'Request Content': self.request_content,
                'Response Content': self.response_content['choices'][0] if 'choices' in self.response_content else self.response_content,
                'Cost': self.cost,
                'Elapsed Time': self.elapsed_time,
                'Model': self.model,
                'Request Type': self.request_type,
                'LLM Method': self.llm_method
            }
        def __str__(self):
            return json.dumps(self.to_dict(), indent = 4)
    
    def __init__(self, print_log=True, mode='OPEN_AI'):
        self.attempts = []
        self.path = os.environ.get('GLLM_LOGGING_PATH', '')
        self.print_log = print_log
        self.mode = mode
        self.created_at = datetime.utcnow().isoformat()

    def add_attempt(self, messages, response, elapsed_time, request_type=None, llm_method=None, costs=None):
        try:
            attempt = self.Attempt(messages, response, elapsed_time, request_type, llm_method,costs)
            self.attempts.append(attempt)
            if self.print_log:
                print(f"{self.mode}\n"+str(attempt))
        except Exception as e:
            print(f"Error adding attempt to log: {e}")
            print(f"messages: {messages}")
            print(f"response: {response}")
            print(f"elapsed_time: {elapsed_time}")
            print(f"request_type: {request_type}")
            print(f"llm_method: {llm_method}")

    def save_to_csv(self, file_path='default'):
        if file_path == 'default':
            file_path = self.path if self.path else 'logs'
        fieldnames = ['Time', 'Request Tokens Used', 'Response Tokens Used', 'Total Tokens Used', 'Request Content', 'Response Content', 'Cost', 'Elapsed Time', 'Model', 'Request Type']
        with open(file_path, mode='a', newline='', encoding='utf-8') as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            for i, attempt in enumerate(self.attempts):
                writer.writerow({
                    'AttemptNo': i,
                    'Time': attempt.time,
                    'Request Tokens Used': attempt.request_tokens,
                    'Response Tokens Used': attempt.response_tokens,
                    'Total Tokens Used': attempt.total_tokens,
                    'Request Content': attempt.request_content,
                    'Response Content': attempt.response_content,
                    'Cost': attempt.cost,
                    'Elapsed Time': attempt.elapsed_time,
                    'Model': attempt.model,
                    'Request Type': attempt.request_type,
                    'LLM Method': attempt.llm_method
                })

    def to_dict(self):
        return {
            'print_log': self.print_log,
            'mode': self.mode,
            'attempts': [attempt.to_dict() for attempt in self.attempts],
            'total_cost': sum(attempt.cost for attempt in self.attempts)
        }

    def __str__(self):
        return json.dumps(self.to_dict(), indent=4, sort_keys=True)
    
    def get_cost(self):
        return sum(attempt.cost for attempt in self.attempts)
