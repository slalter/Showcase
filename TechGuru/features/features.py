from packages.guru.Flows.features import Feature
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

class IPython(Feature):
    def __init__(self, assignment) -> None:
        '''
        NOTE: this does NOT address cross-assignment stuff. Weird with ACOT!
        '''
        super().__init__(assignment,self.__class__.__name__)
        self.shell = InteractiveShell()
        self.codeHistory = []
        from packages.guru.Flows.tool import Tool
        self.assignment.tools.append(Tool(toolName='execute_code',assignment=self.assignment, source_feature = self))

    def preAssignment(self):
        self.assignment.addInstructions("Code you want to execute MUST be included in a tool call.")
        pass

    def preLLM(self):
        pass

    def postLLM(self):
        messages = self.assignment.getMessages()
        if len(messages) > 0:
            content = messages[-1]['content']
            #if ```python \n (code)``` is in the content, execute the code.
            if '```python' in content:
                code = content.split('```python')[1].split('```')[0]
                self.execute_code(code)

    def postResponse(self):
        pass

    def postTool(self):pass

    def checkComplete(self):
        return True
    
    def postAssignment(self):
        pass

    def getCode(self):
        return self.codeHistory
    
    def execute_code(self, code, save_history=True):
        if save_history:
            self.codeHistory.append(code)
        # Execute the code in the IPython shell and capture the output
        stdout = io.StringIO()
        stderr = io.StringIO()

        # Execute the code and capture stdout and stderr
        try:
            with redirect_stdout(stdout), redirect_stderr(stderr):
                # This captures the result of the last expression, if any
                result = self.shell.run_cell(code, store_history=True).result
                result = str(result) if result is not None else ''
                output = stdout.getvalue() + result
                output = remove_ansi_codes(output)
                if len(output) > 7000:
                    output = "the printed output is too long to display! try something smaller."
                addLog(self.assignment.conversation_id, 'IPython Execution',{"code":code, "result": output, "error": stderr.getvalue()})

                
                return json.dumps({"result": output, "error": stderr.getvalue()})
        except Exception as e:
            return json.dumps({"result": None, "error": str(e)})
        
    def getVariableValues(self, variable_names, max_length = 10000):
        results = {v:None for v in variable_names}
        # Execute the code and capture stdout and stderr
        try:
                for variable_name in variable_names:
                    stdout = io.StringIO()
                    stderr = io.StringIO()
                    with redirect_stdout(stdout), redirect_stderr(stderr):
                        try:
                            code = f"""
                            try:
                                print(str({variable_name}))
                            except Exception as e:
                                print(str({{'error':str(e)}}))
                            """
                            # This captures the result of the last expression, if any
                            result = self.shell.run_cell(code, store_history=True).result
                            result = str(result) if result is not None else ''
                            output = stdout.getvalue() + result
                            if len(output) > max_length:
                                output = "too much data. try a more specific query."
                            try:
                                if json.loads(output).get('error'):
                                    output = 'An error occurred.'
                                    #quicklog(f"error while getting variable value: {variable_name}! {json.loads(output).get('error')} for data gathering with IPython")
                            except Exception as e:
                                if isinstance(e, json.JSONDecodeError):
                                    pass
                                else:
                                    #quicklog(f"error while trying to check for errors... it wasn't json decode error. {str(e)} for data gathering with IPython, {variable_name}. This result got saved. {output}")
                                    pass
                            results[variable_name] = output
                        except Exception as e:
                            addLog(self.assignment.conversation_id, 'IPython Data Extraction Error',{"code":code, "result": output, "exception":str(traceback.format_exception(e)),"error": stderr.getvalue()})
                addLog(self.assignment.conversation_id, 'IPython Data Extracted', {'result':results})
                return results
        except Exception as e:
            addLog(self.assignment.conversation_id, 'IPython Data Extraction Error',{"exception":traceback.format_exception(e)})
            return None
        

    def getToolJson(self, toolName):
        if toolName == 'execute_code':
            return {
    "type": "function",
    "function": {
        "name": "execute_code",
        "description": "Execute Code. Executes python code in an IPython shell. Repeated calls to this tool occur in the same environment, and maintain state. Do not call this function in parallel. You will only see the output from print statements and the last line of code in your results. Use descriptive variable names.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "The code to execute."
                }
            }
        }
    }
    }
    
    def executeTool(self, toolName, args, tool_call_id):
        if toolName == 'execute_code':
            return self.execute_code(args['code'])





def remove_ansi_codes(text):
    """
    Remove ANSI color/style codes from a string.

    Parameters:
    - text (str): The text string from which to remove ANSI codes.

    Returns:
    - str: The cleaned text string without ANSI codes.
    """
    # ANSI escape code pattern
    ansi_escape_pattern = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
    return ansi_escape_pattern.sub('', text)