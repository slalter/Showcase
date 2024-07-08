import json
import asyncio
import importlib
import os
import yaml
from packages.guru.cli.utils import guru_settings


# Load settings and set tools_path
settings = guru_settings
os.environ['tools_path'] = settings['tools_path']


class Tool:
    def __init__(self, assignment, toolName, source_feature = None) -> None:
        self.toolName = toolName
        print(f"creating Tool: {toolName}")
        self.source_feature = source_feature
        self.assignment = assignment
        if source_feature:
            self.tool_json = source_feature.getToolJson(toolName)
        else:
            tool = [tool for tool in tools_json if tool['function']['name']==toolName]
            if len(tool)>1:
                raise Exception(f"More than one tool with name {toolName}")
            self.tool_json = tool[0]
        

    def execute(self, args, tool_call_id=None):
        if self.source_feature:
            return self.source_feature.executeTool(self.toolName, args, tool_call_id)
        module = importlib.import_module((os.path.join(os.environ["tools_path"],f"{self.toolName}")).replace('/','.').replace('\\','.'))

        result = module.execute(assignment = self.assignment, args = args,tool_call_id=tool_call_id)

        return result




def getTool(assignment, tool_name):
    for tool in assignment.tools:
          if tool.toolName == tool_name:
            return tool
    raise Exception(f"tool not found in getTool: {tool_name}")




HIDDEN_TOOLS = ['mark_complete','mark_complete_with_message']

with open(os.path.join(os.environ["tools_path"],'tools.json'), 'r') as f:
    tools = f.read()
tools_json=json.loads(tools)
if not isinstance(tools_json, list):
    tools_json = [tools_json]

available_tools = tools_json