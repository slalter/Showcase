from .tree import Tree
from .element import Element, getElementById
import pkg_resources
from guru.GLLM import LLM
import json
from CLTrees.promptspy import GetContextPrompt, MakeContextSummaryPrompt
from CLTrees.timeRange import TimeRange
from CLTrees.timeChain import TimeChain
from datetime import datetime

class TreeNavigator:
    def __init__(self, tree:Tree, min_threshold = 0.1) -> None:
        '''
        branch_threshold: the fraction of the fraction of 1 which triggers further investigation.
        '''
        self.tree = tree
        self.path = []
        self.nextNodes = []
        self.min_threshold = min_threshold
        self.context = None
        self.result = []

    async def getContext(self, query):
        print(f"getting context for {query}")
        if not self.tree.elements:
            return 'No context - no records exist.'
        if self.tree.layers:
            timeChain = TimeChain(self.tree.layers[0], self.tree)
            while True:
                prompt = GetContextPrompt(
                    visible_nodes=timeChain.get(),
                    current_task_or_query=query,
                    current_time= datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ).get()
                print(prompt)
                log, result = await LLM.json_response(prompt=prompt)
                print(f"result for getcontextprompt: {result}")
                if timeChain.processLabels(result['list_of_categories']):
                    break
        else:
            timeChain = TimeChain(self.tree.elements, self.tree)
        
        
        print(f"resulting chain: {timeChain.get()}")
        prompt = MakeContextSummaryPrompt(
            #given_data = [f"{element.description}: \n{element.data}\n{element.detailed_description}" for element in elements],
            given_data = [timeChain.get()],
            current_task_or_query=query
        ).get()
        print(prompt)
        log, result = await LLM.json_response(prompt=prompt)
        print(f"result for MakeContextSummaryPrompt: {result}")
        return result
        
    def reset(self):
        self.currentNodes = [node for node in self.tree.layers[0].nodes]
        