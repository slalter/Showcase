import uuid
from guru.GLLM import LLM
from .element import Element, getElementById
import json
import asyncio
import pkg_resources
from datetime import datetime
from CLTrees.promptspy import LlmSplitPrompt, CheckFitPrompt
from CLTrees.timeRange import TimeRange
import os



class Node:
    def __init__(self, description, parentTree, layer, time_range:TimeRange, id=None, embedding = None) -> None:

        if not id:
            self.id = str(uuid.uuid4())
        else:
            self.id = id
        self.time_range = time_range
        self.layer = layer
        self.created_at = datetime.now()
        self.description = description
        self.parentTree = parentTree
        if embedding:
            self.embedding =embedding
        else:
            self.embedding = LLM.getEmbedding(self.description)

    def getPath(self):
        path=""
        for i,layer in enumerate(self.parentTree.layers):
            node = layer.get_node_by_time_range(self.time_range)
            if node:
                path += node.description +"/"
            else:
                print(f"node not found while getting path for {self} in layer {i}")
        print(f"output path: {path}")
        return path

        
    async def split(self):
        #TODO: result must be distinct from existing nodes in that layer. or do they?
        if os.environ.get('debug', None):
            print(f"splitting {self}.")
        sub_steps = await self.llmSplit()
        i=0
        for step, child_descriptions in sub_steps.items():
            new_time_range = TimeRange()
            if self.layer == len(self.parentTree.layers)-1:
                print(f"\ndescription:{child_descriptions}\step:{step}")
                print(f"elements: \n{[element.description for element in self.getChildren()[i:i+len(child_descriptions)]]}")
                print(f"timestamps: \n{[str(element.timestamp) for element in self.getChildren()[i:i+len(child_descriptions)]]}")
                new_time_range.addStamps([element.timestamp for element in self.getChildren()[i:i+len(child_descriptions)]])
                print(f"resulting time_range: {new_time_range}\n")
            else:
                print(f"\ndescription:{child_descriptions}\step:{step}")
                print(f"nodes: \n{[node.description for node in self.getChildren()[i:i+len(child_descriptions)]]}")
                print(f"time_ranges: \n{[str(node.time_range) for node in self.getChildren()[i:i+len(child_descriptions)]]}")
                new_time_range.compose([node.time_range for node in self.getChildren()[i:i+len(child_descriptions)]])
                print(f"resulting time_range: {new_time_range}\n")
            self.parentTree.layers[self.layer].nodes.append(Node(step, self.parentTree, self.layer, new_time_range.copy()))
            i+=len(child_descriptions)
        self.delete()
    
    
    async def checkFit(self, description):
        prompt=CheckFitPrompt(
            input_description=description,
            step_description=self.description
            ).get()
        log, result = await LLM.json_response(prompt=prompt)
        if os.environ.get('debug',None):
            print(f"checkFit: {result}")
        return result['fits']

    async def checkSize(self):
        children = self.getChildren()
        size = len(children)
        print(f"\ncheckSize:\nSize of {self}: {size}\n")
        if size>self.parentTree.k:
            await self.split()

    async def llmSplit(self):
        prompt = LlmSplitPrompt(int(self.parentTree.k*self.parentTree.alpha),
                                self.getPath(),
                                [f"{child.description} at {child.time_range}" for child in self.getChildren()],
                                existing_categories=[node.description for node in self.parentTree.layers[self.layer].nodes]).get()
        log, response = await LLM.json_response(prompt=prompt)
        if os.environ.get('debug',None):
            try:
                print(f"llmsplit: {response}")
                del(response['reasoning'])
            except:
                pass
        return response

    def delete(self):
        self.parentTree.layers[self.layer].nodes.remove(self)

    
    def getJson(self):
        return {"id": self.id,
                "description": self.description,
                "childNodes": str([id for id, node in self.getChildNodes().items()]),
                "elements": str([element.getJson() for id, element in self.getElements().items()]),
                "prevNode": self.prevNodeId,
                "embedding":self.embedding
                }
    
    def getChildren(self):
        if self.layer == len(self.parentTree.layers)-1:
            return self.getElements()
        else:
            return [node for node in self.parentTree.layers[self.layer+1].nodes if node.time_range.subset_of(self.time_range)]


    def getElements(self):
        return [element for element in self.parentTree.elements if self.time_range.contains(element.timestamp)]

    def __str__(self):
        return json.dumps({"id": self.id,
                "description": self.description,
                "time_range":str(self.time_range),
                "layer":self.layer
                })
