from models import Base, Session
from sqlalchemy import Column, Integer, String, JSON, DateTime, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey
from datetime import datetime
from models import SmartUUID, CodeMixin
import uuid

class TestResult(Base):
    '''
    Represents a test result for a project.
    '''
    __tablename__ = 'test_result'
    id = Column(SmartUUID(), primary_key=True, default=uuid.uuid4)
    test_case_id = Column(SmartUUID(), ForeignKey('test_case.id'))
    test_case = relationship("TestCase", back_populates="test_results")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    passed = Column(Boolean)


class TestCase(Base):
    '''
    Represents a test case for a project.
    '''
    __tablename__ = 'test_case'
    id = Column(SmartUUID(), primary_key=True, default=uuid.uuid4)
    project = relationship("Project", back_populates="test_cases")
    project_id = Column(SmartUUID(), ForeignKey('project.id'))
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    name = Column(String)
    test_results = relationship("TestResult", back_populates="test_case", cascade="all")
    code_object_id = Column(SmartUUID(), ForeignKey('code_object.id'))
    code_object = relationship("CodeMixin", back_populates="test_cases")
    code = Column(String)

