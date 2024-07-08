from models import Base, Session
from sqlalchemy import Column, Integer, String, JSON, DateTime, Boolean, LargeBinary
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey
from datetime import datetime
from models import SmartUUID
import uuid
import shutil
import os
import json
import subprocess
from models.utils.loggable import LoggableMixin


class Project(Base, LoggableMixin):
    '''
    Top-level class for a project.
    '''
    __tablename__ = 'project'
    id = Column(SmartUUID(), primary_key=True, default=uuid.uuid4)
    name = Column(String)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    test_cases = relationship("TestCase", back_populates="project", cascade="all")
    methods = relationship("Method", back_populates="project", cascade="all")
    classes = relationship("Class", back_populates="project", cascade="all")
    files = relationship("File", back_populates="project", cascade="all")
    git_repo = Column(String, nullable=True)
    server_id = Column(SmartUUID(), ForeignKey('server.id'))
    server = relationship("Server", back_populates="project")
    design_decisions = relationship("DesignDecision", back_populates="project", cascade="all")
    object_requests = relationship("ObjectRequest", back_populates="project", cascade="all")
    temp_folder_path = Column(String, nullable=True)
    pipfile = Column(String, nullable=True)
    verified = Column(Boolean, default=False)
    dependencies_analyzer = Column(LargeBinary, nullable=True)
    code = Column(String, nullable=True) #this is the main app code being held by the LLM that is managing the project.

    #TODO. This is currently just locally run in the /project folder.
    #server_id = Column(SmartUUID(), ForeignKey('server.id'))
    #server = relationship("Server", back_populates="project")

    def runPyright(self):
        '''
        Runs pyright on the project.
        '''
        pass

    def build(self, session, root_file_name,folder_path=None,):
        '''
        Builds the project in the folder path.
        '''
        from models import File
        if not folder_path:
            folder_path = '/tmp/' + str(self.id)
        self.temp_folder_path = folder_path
        session.commit()
        
        #initialize the standard project structure, 

        #copy the files from /project_skeleton to the folder path
        shutil.copytree('/project_skeleton', folder_path)

        #build starts at the root file given.
        root_file = session.query(File).filter(File.path == root_file_name).first()
        root_file.build(folder_path, session)



        

    def test(self, session):
        '''
        Tests the project.
        '''
        self.test_results = []
        #TODO: multithread. Maybe even celery?
        for test_case in self.project.test_cases:
            test_case.run(self)
        session.commit()

    def findSimilarObject(self, code_object_class, description, session, k=5):
        '''
        Finds a similar object in the project. Returns the object if found, None otherwise.
        code_object_class in Model, Method
        k is the number of semantically similar objects to search within.
        semantic search -> LLM verification
        '''
        #begin by getting the first representation of the class so we can use it for the query
        code_object = session.query(code_object_class).filter(code_object_class.project_state==self.id).first()
        result:list[code_object_class] = code_object.findSimilar(description, session)
        return result


    def pip_add_package(self, package_name, session):
        '''
        Adds a package to the pipfile, if not there already.
        '''
        if not self.pipfile:
            self.pipfile = ''
        if package_name not in self.pipfile:
            self.pipfile += package_name + '\n'
            session.commit()

    def getState(self, session):
        '''
        Returns all the logs for this project from its constituents.
        '''
        logs = {
            'object_requests':{
                'pending':[o for o in self.object_requests if o.status == 'pending'],
                'fulfilled':[o for o in self.object_requests if o.status == 'fulfilled'],
                'error':[o for o in self.object_requests if o.status == 'error']
            },
            'methods':[method for method in self.methods],
            'models':[model for model in self.models],
            'main':[self.main],
            'test_cases':self.test_cases,
            'design_decisions':self.design_decisions,
            'project':self
        }
        return logs


