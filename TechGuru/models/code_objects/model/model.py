from models import Base, Session
from sqlalchemy import Column, Integer, String, JSON, DateTime, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey
from datetime import datetime
from models import SmartUUID, CodeMixin
import uuid
import os
from packages.guru.GLLM import LLM
from models.code_objects.class_model import Class

'''
the purpose of this subdivision is to make sure that Model has a separate vector space from Class in general.
'''

class Model(Class):
    '''
    Represents a model in a project.
    '''
    
    __tablename__ = 'model' 
    id = Column(SmartUUID(), ForeignKey('class.id'), primary_key=True, default=uuid.uuid4)

    __mapper_args__ = {
        'polymorphic_identity': 'model',
        'inherit_condition': (id == Class.id)
    }

    @staticmethod
    def build(model_instance, file_path, session):
        '''
        builds the method in file_path/methods/{model_instance.name.lower()}.py
        All methods that this depends on will be built in file_path/methods/{other_name}.py, unless they already exist, in which case their absolute path will be imported.
        TODO: dynamic importing at build time. Currently, this is done at runtime.
        '''
        from models import Method
        if model_instance.dependencies:
            dependencies = session.query(Method).filter(Method.id.in_(model_instance.dependencies)).all()
            for dependency in dependencies:
                dependency.build(file_path, session)
            model_dependencies = session.query(Model).filter(Model.id.in_(model_instance.dependencies)).all()
            for model in model_dependencies:
                model.build(file_path, session)
        if model_instance.pip_packages:
            for package in model_instance.pip_packages:
                model_instance.project.pip_add_package(package)
        model_instance.write_code_to_file(os.path.join(file_path, 'models', model_instance.name + '.py'))
        model_instance.addLog('Model built.',{
            'file_path': os.path.join(file_path, 'models', model_instance.name + '.py')
        }, session)
        session.commit()

    def embed(self, session):
        if not self.verified:
            raise Exception('Cannot embed an unverified model.')
        self.namespace = f"{self.project_id}_{self.__class__.__name__}"
        self.embedding = LLM.getEmbedding(self.description)
        session.commit()
