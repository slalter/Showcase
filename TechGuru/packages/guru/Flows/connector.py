from ..GLLM import LLM
import uuid
import json
#connects one assignment to the next.

class Connector:
    def __init__(self, targetAssignment, conditions, reprompt='', id=None):
        #conditions should be a string describing the conditions. LLM-powered.
        self.conditions = conditions
        self.targetAssignment = targetAssignment
        self.reprompt=reprompt
        if id:
            self.id = id
        else: 
            self.id = uuid.uuid4()

    def __str__(self):
        return json.dumps({
            "connection": self.targetAssignment,
            "conditions": self.conditions
        })


