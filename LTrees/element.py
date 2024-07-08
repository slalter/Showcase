import json
from guru.GLLM import LLM
import uuid
from datetime import datetime
from packages.celery import getSession


class Element:
    def __init__(self, parent_tree=None, raw_text = None, description=None, metadata = None, id = None, timestamp = None, embedding = None):
        if id:
            self.id = str(id)
        else:
            self.id = str(uuid.uuid4())
        self.metadata = metadata
        self.raw_text = raw_text
        if description:
            self.description = description
        else:
            if len(raw_text)>20:
                self.description =  LLM.getShorthandSummary(raw_text)
            else:
                self.description=raw_text
        if parent_tree:
            self.parent_tree = parent_tree
            parent_tree.elements.append(self)
        else:
            self.parent_tree = None
        self.timestamp = timestamp if timestamp else datetime.utcnow().isoformat()
        self.embedding = embedding
    


    def __str__(self):
        out = {"id": self.id, "description":self.description}
        if hasattr(self,'timestamp'):
            out['timestamp']=self.timestamp
        return str(out)

    def getJson(self):
        parent_matches = [node for node in self.parent_tree.nodes if node.elementIds and self.id in node.elementIds]
        if parent_matches:
            parent = parent_matches[0]
        else:
            parent = None
        out = {
            "id": str(self.id), 
            "description":self.description,
            'raw_text':self.raw_text,
            'parent':str(parent.id) if parent else None,
            'parent_tree':str(self.parent_tree.id)}
        if hasattr(self,'timestamps'):
            out['timestamps']=self.timestamps
        return out



    
    @classmethod
    def loadElementFromModel(cls, model):
        from models import ElementNode
        assert isinstance(model, ElementNode)
        return cls(
            description=model.description, 
            metadata=model.getElementMetadata(), 
            id=model.id, 
            timestamp=model.content_timestamp.isoformat() if model.content_timestamp else None,
            embedding = model.embedding
            )