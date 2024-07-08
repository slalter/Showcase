from models import Base, Session
from sqlalchemy import Column, Integer, String, JSON, DateTime, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey
from datetime import datetime
from ...utils import SmartUUID
import uuid
from ...utils.loggable import LoggableMixin
from ...conversation.db_conversation import DBConversation
from ...utils.waitable_mixin import WaitableMixin

class ObjectRequest(Base, LoggableMixin, WaitableMixin):
    '''
    A class to track a request for a new object.
    NOTE: We are currently using the logging_cid as the id for the conversation that occurs!
    Confusing, but convenient. 
    '''
    __tablename__ = 'object_request'
    id = Column(SmartUUID(), primary_key=True, default=uuid.uuid4)
    object_type = Column(String, default='model') #model, method, main, test_case
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    code_object_id = Column(SmartUUID(), ForeignKey('code_object.id'))
    code_object = relationship("CodeMixin", back_populates="object_request")
    project = relationship("Project", back_populates="object_requests")
    project_id = Column(SmartUUID(), ForeignKey('project.id'))
    io_pair = relationship("IOPair", back_populates="object_request")
    io_pair_id = Column(SmartUUID(), ForeignKey('io_pair.id'))
    description = Column(String)
    name = Column(String)
    error_message = Column(String, nullable=True)
    code = Column(String, nullable=True)

    #this is the tool_call_id that is used when this is waiting on an external tool.
    external_tool_call_id = Column(String, nullable=True)

    def on_wait_fulfilled(self, session):
        '''
        Called when ALL the objects that this object is waiting on are fulfilled.
        '''
        from packages.tasks import deliver_external_tool_call_task
        deliver_external_tool_call_task.delay(
            conversation_id = self.logging_cid,
            tool_call_id = self.external_tool_call_id,
            tool_name = 'request_object',
            result = 'all objects created.'
        )

        
    def fulfill(self):
        '''
        Fulfill the object request. Starts a celery task.
        '''
        from packages.tasks import start_object_request_task
        start_object_request_task.delay(self.id)


    def getStatusString(self):
        '''
        Returns the status string.
        returns status, input and output classes, name, and description in an LLM-friendly string.
        '''
        if self.status == 'pending':
            #return data from self
            return f'''
id: {self.id}
name: {self.name}
status: {self.status}
input_class: {self.io_pair.input_class.__str__() if self.io_pair else 'None'}
output_class: {self.io_pair.output_class.__str__() if self.io_pair else 'None'}
description: {self.description}
type: {self.object_type}'''
        
        elif self.status == 'fulfilled':
            #return data from code object
            return f'''
id: {self.id}
name: {self.code_object.name}
status: {self.status}
input_class: {self.code_object.io_pair.input_class.__str__() if self.code_object.io_pair else 'None'}
output_class: {self.code_object.io_pair.output_class.__str__() if self.code_object.io_pair else 'None'}
description: {self.code_object.description}
type: {self.object_type}'''
            
        elif self.status == 'error':
            return f'''
id: {self.id}
name: {self.name}
status: {self.status}
error_message: {self.error_message}
Consider a different implementation that avoids this error.
'''

        else:
            return f'''
id: {self.id}
name: {self.name}
Something went wrong... report this.
'''