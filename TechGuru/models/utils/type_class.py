from models import Base, Session
from sqlalchemy import Column, Integer, String, JSON, DateTime, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey
from datetime import datetime
from .smart_uuid import SmartUUID
from .code_mixin import CodeMixin
import uuid
from sqlalchemy.ext.declarative import declared_attr

class TypeClassMixin:
    """
    Mixin to add serialization and file writing capabilities to type classes.
    Also adds example_values attribute to the class.
    """
    
    @declared_attr
    def attributes(cls):
        '''
        {
            attributes:
            [
                {
                    name: str,
                    type: str, #using python typestrings (lowercase)
                    default: any
                }
            ] 
        }
        '''
        return Column(JSON, nullable=False, default={})
    
    @declared_attr
    def example_values(cls):
        '''
        name:value pairs for example values of the attributes.
        '''
        return Column(JSON, nullable=False, default={})

    def __str__(self):
        string = f'class {self.__class__.__name__}:\n'
        # Assumes 'attributes' is a dictionary containing an "attributes" key that is a list of dictionaries.
        for attribute in self.attributes["attributes"]:
            string += f'    {attribute["name"]}:{attribute["type"]}' + ('' if attribute["default"] == None else f' = {attribute["default"]}') + '\n'
        return string

    def writeToFilePath(self, file_path):
        """
        Writes the string representation of the instance to a file specified by `file_path`.
        """
        with open(file_path, 'w') as file:
            file.write(self.__str__())



class InputClass(TypeClassMixin,Base):
    '''
    contains class definitions for input classes w/ typestrings.
    '''
    __tablename__ = 'input_class'
    id = Column(SmartUUID(), primary_key=True, default=uuid.uuid4)
    
    def writeToPythonFile(self, file):
        file.write(f'class {self.code_objects.__class__.__name__}Input:\n')
        for attribute in self.attributes["attributes"]:
            file.write(f'    {attribute["name"]}:{attribute["type"]}' + ('' if attribute["default"] == None else f' = {attribute["default"]}') + '\n')
        file.write('\n')



class OutputClass(TypeClassMixin,Base):
    '''
    contains class definitions for output classes
    '''
    __tablename__ = 'output_class'
    id = Column(SmartUUID(), primary_key=True, default=uuid.uuid4)

    
    def writeToPythonFile(self, file):
        file.write(f'class {self.code_objects.__class__.__name__}Output:\n')
        for attribute in self.attributes["attributes"]:
            file.write(f'    {attribute["name"]}:{attribute["type"]}' + ('' if attribute["default"] == None else f' = {attribute["default"]}') + '\n')
        file.write('\n')


class IOPair(Base):
    '''
    A class to store input-output pairs for code objects.
    '''
    __tablename__ = 'io_pair'
    id = Column(SmartUUID(), primary_key=True, default=uuid.uuid4)
    input_class_id = Column(SmartUUID(), ForeignKey('input_class.id'))
    input_class = relationship("InputClass", foreign_keys=[input_class_id])
    output_class_id = Column(SmartUUID(), ForeignKey('output_class.id'))
    output_class = relationship("OutputClass", foreign_keys=[output_class_id])
    code_object_id = Column(SmartUUID(), ForeignKey('code_object.id'))
    code_object = relationship("CodeMixin", foreign_keys=[code_object_id])
    object_request = relationship("ObjectRequest", back_populates="io_pair")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    example_pairs = Column(JSON, nullable=False, default=[])

    def __str__(self):
        return f'Input: {self.input_class.__str__()}\nOutput: {self.output_class.__str__()}'
