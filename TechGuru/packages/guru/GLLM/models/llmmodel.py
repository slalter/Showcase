from abc import ABC, abstractmethod
from packages.guru.GLLM.log import Log
from typing import Literal
import json

class LLMResponse:
    def __init__(self, raw_response, response, **kwargs):
        self.response = response
        self.raw_response = raw_response
        for k, v in kwargs.items():
            setattr(self, k, v)

class LLMCall:
    def __init__(self, response: LLMResponse, log:Log, status:Literal['success','failure'] = 'success', tool_calls=[],**kwargs):
        self.response = response
        self.log = log
        self.status = status
        self.tool_calls = tool_calls
        for k, v in kwargs.items():
            setattr(self, k, v)

    def get(self):
        if hasattr(self, 'json_mode') and self.json_mode:
            if not isinstance(self.response.response, dict):
                return json.loads(self.response.response)
            else:
                return self.response.response
        return self.response.response
    
    def get_for_dspy(self):
        '''returns the response in a format that can be used by dspy. Only difference is that jsons are dumped.'''
        if isinstance(self.response.response, dict):
            return json.dumps(self.response.response)
        return self.response.response
    

from dspy import LM
class LLMModel(LM):
    def __init__(self, model, name, **kwargs):
        super().__init__(model)
        self.name = name
        self.max_tokens = kwargs.get('max_tokens', 1024)
        self.log_objects:list[Log] = []

    @abstractmethod
    def getCost(self) -> tuple[float, float]:
        '''input:output token cost'''
        pass

    @abstractmethod
    def execute(self,
                messages=None,
                prompt=None,
                tools=None,
                temp: float = 0.5,
                request_type='',
                run=None,
                mode=None,
                timeout=None,
                print_log=True,
                json_mode=False,
                max_tokens=None,
                magic_words=False,
                max_tries=4) -> LLMCall:
        pass

    def basic_request(self, prompt, **kwargs):
        """Implement the basic_request method from LM."""
        # Use the execute method to handle the request.
        #validate temperature
        if kwargs.get("temperature", self.kwargs["temperature"]) < 0 or kwargs.get("temperature", self.kwargs["temperature"]) > 1:
            kwargs["temperature"] = 0 if kwargs.get("temperature", self.kwargs["temperature"]) < 0 else 1
        #mock completion format to match
        split = prompt.split('---')
        if len(split) > 3:
            split[3] += ['---' + split[i] for i in range(4, len(split))]
        prompt, user, assistant = split[:3]
        if kwargs.get('json_mode'):
            print("json mode", flush=True)
            assistant = str(assistant) + "{"
        print(assistant)
        messages = [
            {"role": "user", "content": user},
            {"role": "assistant", "content": assistant}
            ]
        call = self.execute(
            messages=messages,
            temp=kwargs.get("temperature", self.kwargs["temperature"]),
            print_log=False,
            prompt=prompt,
        )
        response = call.get()

        history = {
            "prompt": prompt,
            "response": response,
            "kwargs": kwargs,
            "raw_kwargs": kwargs,
        }
        # Add the response to the history
        self.history.append(history)
        self.log_objects.append(call.log)
        return [call.get_for_dspy()]

    def __call__(self, prompt, only_completed=True, return_sorted=False, **kwargs):
        """Implement the call method from LM."""
        response = self.request(prompt, **kwargs)
        if only_completed:
            # Process to return only completed responses if applicable.
            pass
        if return_sorted:
            # Sort responses if applicable.
            pass
        return response

    def inspect_history(self, n: int = 1, skip: int = 0):
        """Prints the last n prompts and their completions."""
        provider: str = self.provider

        last_prompt = None
        printed = []
        n = n + skip

        for x in reversed(self.history[-100:]):
            prompt = x["prompt"]

            if prompt != last_prompt:
                printed.append((prompt, x["response"]))

            last_prompt = prompt

            if len(printed) >= n:
                break

        printing_value = ""
        for idx, (prompt, choices) in enumerate(reversed(printed)):
            # skip the first `skip` prompts
            if (n - idx - 1) < skip:
                continue
            printing_value += "\n\n\n"
            printing_value += prompt

            text = choices
            printing_value += self.print_green(text, end="")

            printing_value += "\n\n\n"

        print(printing_value)
        return printing_value
    
    def get_total_cost(self):
        return sum([log.get_cost() for log in self.log_objects])
