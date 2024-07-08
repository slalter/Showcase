from sqlalchemy import Column, String, Text, JSON, Integer, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declared_attr
from .vector import ProjectVectorMixin, Vector
from .versioned_mixin import VersionedMixin
from .loggable import LoggableMixin
from prompt_classes import CompareCodeObjectPrompt
from packages.guru.GLLM import LLM
from packages.guru.GLLM.log import Log
from sqlalchemy.orm import relationship
from .smart_uuid import SmartUUID
from ..database import Base
import uuid
from sqlalchemy import Table

code_object_dependencies = Table(
    'code_object_dependencies', Base.metadata,
    Column('source_id', SmartUUID(), ForeignKey('code_object.id'), primary_key=True),
    Column('target_id', SmartUUID(), ForeignKey('code_object.id'), primary_key=True)
)

def add_dependency(session, source_id, target_id):
    # make sure the dependency doesn't already exist
    if session.query(code_object_dependencies).filter_by(source_id=convert_to_uuid(source_id), target_id=convert_to_uuid(target_id)).count() > 0:
        return
    dependency = code_object_dependencies.insert().values(
        source_id=convert_to_uuid(source_id),
        target_id=convert_to_uuid(target_id)
    )
    session.execute(dependency)
    session.commit()


class CodeMixin(Base, ProjectVectorMixin, LoggableMixin):
    '''
    Mixin for code objects. Handles:
    - Description
    - Input and output classes
    - Project state
    - Dependencies
    - Code
    - Test Cases
    - Documentation string
    - Embedding (pgvector)
    - Finding similar object in the same namespace (LLM-assisted)

    NOTE: objects should only be embedded once we know for sure that they are complete.
    '''
    __tablename__ = 'code_object' 
    id = Column(SmartUUID(), primary_key=True, default=uuid.uuid4)
    type = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    code = Column(Text, nullable=False)
    name = Column(String, nullable=False)
    docString = Column(String, default='')
    test_cases = relationship("TestCase", back_populates="code_object", cascade="all")
    io_pair = relationship("IOPair", back_populates="code_object", cascade="all")
    object_request = relationship("ObjectRequest", back_populates="code_object", cascade="all")
    pip_packages = Column(JSON, default=[])
    native_packages = Column(JSON, default=[])
    verified = Column(Boolean, default=False)

    # Dependency relationships
    dependencies = relationship(
        'CodeMixin', 
        secondary=code_object_dependencies,
        primaryjoin=id==code_object_dependencies.c.source_id,
        secondaryjoin=id==code_object_dependencies.c.target_id,
        backref='dependents'
    )

    def addPip(self, package):
        if self.pip_packages:
            self.pip_packages = self.pip_packages +[package]
        else:
            self.pip_packages = [package]

    def addNative(self, package):
        if self.native_packages:
            self.native_packages = self.native_packages + [package]
        else:
            self.native_packages = [package]

    def addDependency(self, dependency, session):
        add_dependency(session, self.id, dependency.id)

    @declared_attr
    def embedding(cls):
        # Column definition for vector embedding
        return Column(Vector(1536))

    __mapper_args__ = {
        'polymorphic_identity': 'code',
        'polymorphic_on': type
    }

    def build(self, file_path, session):
        '''
        builds the object in file_path/{self.name}.py
        All objects that this depends on will be built in file_path/{other_name}.py, unless they already exist, in which case their absolute path will be imported.
        '''
        if self.type == 'method':
            from models import Method
            Method.build(self, file_path, session)
        elif self.type == 'model':
            from models import Model
            Model.build(self, file_path, session)
        else:
            raise Exception(f'Unsupported object type:{self.type}')
        
    def get_code_with_line_numbers(self):
        """Return the code with line numbers."""
        return "\n".join(f"{i+1}: {line}" for i, line in enumerate(self.code.split('\n')))

    def replace_line(self, line_number, new_content):
        """Replace a specific line of code."""
        lines = self.code.split('\n')
        if 1 <= line_number <= len(lines):
            lines[line_number - 1] = new_content
            self.code = "\n".join(lines)

    def insert_line(self, line_number, new_content):
        """Insert a new line of code at a specific line number."""
        lines = self.code.split('\n')
        if 1 <= line_number <= len(lines) + 1:
            lines.insert(line_number - 1, new_content)
            self.code = "\n".join(lines)

    def delete_line(self, line_number):
        """Delete a specific line of code."""
        lines = self.code.split('\n')
        if 1 <= line_number <= len(lines):
            del lines[line_number - 1]
            self.code = "\n".join(lines)

    def get_code_without_line_numbers(self):
        """Return the code without line numbers."""
        return self.code

    def write_code_to_file(self, file_path):
        """Write the code to a designated file path."""
        with open(file_path, 'w') as file:
            file.write(f"#{self.version}\n\n{self.code}")

    def findSimilar(self, session, description, requested_output=None, requested_input=None, k=5):
        """
        Find the most similar objects in the namespace via cosine similarity.
        Use an LLM to determine if any of the top 5 are similar enough to be considered useful for the same purpose.
        """
        embedding = LLM.getEmbedding(description)
        similar_objects:self.__class__ = self.nearest(session, embedding, k)
        #verify that the object extends the CodeMixin class
        assert(all(isinstance(obj, CodeMixin) for obj in similar_objects))

        #use LLM to see if any are actually a match
        prompt = CompareCodeObjectPrompt(
            matches=[{
                'description': obj.description,
                'input': obj.input_class,
                'output': obj.output_class
            } for obj in similar_objects],
            requested_method_output=requested_output,
            requested_method_description=description,
            requested_method_input=requested_input,
            object_type=self.__class__.__name__
            )
        log, result = prompt.execute(
            model='gpt-3.5-turbo'
            )
        self.log(log)
        result: list[self.__class__] = [obj for i, obj in enumerate(similar_objects) if i in result['similar_method_numbers']]
        return result
    

    def run_tests(self, session):
        if self.test_cases:
            for test_case in self.test_cases:
                test_case.run(session)
            session.commit()
            return [test_case.test_results for test_case in self.test_cases]
        else:
            raise Exception("No test cases available to test object.")
        
    
    def __str__(self):
        return self.get_code_without_line_numbers()
    

def convert_to_uuid(value):
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(value)
