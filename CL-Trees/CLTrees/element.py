import json
from guru.GLLM import LLM
import uuid
from datetime import datetime
from CLTrees.promptspy import CreateElementPrompt

elements = {}

class Element:
    def __init__(self, description, data='', detailed_description = 'None', timestamp=None, embedding = None, embedding_data = None, metadata = None, id = None, auto_summarize = False):
        if id:
            self.id = id
        else:
            self.id = str(uuid.uuid4())
        self.detailed_description=detailed_description
        if metadata:
            self.metadata = metadata
        if auto_summarize:
            description = LLM.shorthandSummary(description)
        self.description = description
        self.data = data #TODO: turn this into a dynamic data object that has an id and can exist in multiple trees, AND have dynamic key:values that are generated and can be called? Build vector comparison into data class?
        self.timestamp = timestamp if timestamp else datetime.now()
        if embedding:
            self.embedding = embedding
        else:
            if embedding_data:
                self.embedding = LLM.getEmbedding(embedding_data)
            else:
                self.embedding = LLM.getEmbedding(self.description)
        elements.update({self.id: self})
    
    def __str__(self):
        out = {"id": self.id, "description":self.description, 'timestamp':self.timestamp, 'detailed_description':self.detailed_description, 'data':self.data}

        return str(out)

    def getJson(self):
        out = {"id": self.id, "description":self.description, 'embedding':self.embedding,'raw_text':self.raw_text, 'timestamp':self.timestamp}

        return out
    def delete(self):
        elements.remove(self)

def getElementById(id):
    return elements[id]

async def createElement(data):
    '''
    creates an element from a chunk of data using an llm prompt.
    make sure to pass this something that is at least somewhat summarized already, or isn't that big to begin with.
    '''
    prompt = CreateElementPrompt(data).get()
    log, result = await LLM.json_response(prompt=prompt)
    element = Element(
        description=result['task_name'],
        data=result['relevant_data'],
        detailed_description=result['task_summary']
    )
    return element