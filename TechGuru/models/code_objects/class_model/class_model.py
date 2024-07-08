from models import Base, Session
from sqlalchemy import Column, Integer, String, JSON, DateTime, Boolean, Text, Enum
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey
from datetime import datetime
from models import SmartUUID, CodeMixin
import uuid
import os
from packages.guru.GLLM import LLM

class Class(CodeMixin):
    '''
    Represents a class in a project.
    '''
    
    __tablename__ = 'class' 
    id = Column(SmartUUID(), ForeignKey('code_object.id'), primary_key=True, default=str(uuid.uuid4))
    bases = Column(JSON, default = [])

    project = relationship("Project", back_populates="classes")

    __mapper_args__ = {
        'polymorphic_identity': 'class',
        'inherit_condition': (id == CodeMixin.id)
    }

  
    def embed(self, session):
        if not self.verified:
            raise Exception('Cannot embed an unverified model.')
        self.namespace = f"{self.project_id}_{self.__class__.__name__}"
        self.embedding = LLM.getEmbedding(self.description)
        session.commit()
    
    __mapper_args__ = {
        'polymorphic_identity': 'class',
        'inherit_condition': (id == CodeMixin.id)
    }
