from models import Base, Session
from sqlalchemy import Column, Integer, String, JSON, DateTime, Boolean
from models.utils.code_mixin import CodeMixin
from models.utils.smart_uuid import SmartUUID
import uuid
import os
from packages.guru.GLLM import LLM
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship


class Method(CodeMixin):    
    __tablename__ = 'method'  # Ensuring there's a table name specified
    id = Column(SmartUUID(), ForeignKey('code_object.id'), primary_key=True, default=uuid.uuid4)
    decorators = Column(JSON, default = [])
    project = relationship("Project", back_populates="methods")

    __mapper_args__ = {
        'polymorphic_identity': 'method',
        'inherit_condition': (id == CodeMixin.id)
    }

    @staticmethod
    def build(method_instance, file_path, session):
        '''
        builds the method in file_path/methods/{method_instance.name}.py
        All methods that this depends on will be built in file_path/methods/{other_name}.py, unless they already exist, in which case their absolute path will be imported.
        TODO: dynamic importing at build time. Currently, this is done at runtime.
        '''
        from models import Model
        if method_instance.dependencies:
            dependencies = session.query(Method).filter(Method.id.in_(method_instance.dependencies)).all()
            for dependency in dependencies:
                dependency.build(file_path, session)
            model_dependencies = session.query(Model).filter(Model.id.in_(method_instance.dependencies)).all()
            for model in model_dependencies:
                model.build(file_path, session)
        if method_instance.pip_packages:
            for package in method_instance.pip_packages:
                method_instance.project.pip_add_package(package)
        method_instance.write_code_to_file(os.path.join(file_path, 'methods', method_instance.name + '.py'))
        method_instance.addLog('Model built.',{
            'file_path': os.path.join(file_path, 'methods', method_instance.name + '.py')
        }, session)
        session.commit()

    def embed(self, session):
        if not self.verified:
            raise Exception('Cannot embed an unverified method.')
        self.namespace = f"{self.project_id}_{self.__class__.__name__}"
        self.embedding = LLM.getEmbedding(self.description)
        session.commit()

