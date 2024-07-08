from packages.guru.GLLM.log import Log
from sqlalchemy import Column, JSON
from sqlalchemy.orm import declared_attr
from sqlalchemy.orm import class_mapper
from sqlalchemy.orm import RelationshipProperty
from models.utils.smart_uuid import SmartUUID
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship, object_session
from models.conversation.db_conversation import addLog
from models.conversation.llm_log import LLMLog
from sqlalchemy import event
from models.database import Session

class LoggableMixin:
    '''
    A mixin for objects that can be logged to a DBConversation object. 
    Automatically initializes.
    '''


    #relationship to db_conversation
    @declared_attr
    def logging_conversation(cls):
        return relationship("DBConversation", cascade="all")

    @declared_attr
    def logging_cid(cls):
        return Column(SmartUUID(), ForeignKey('db_conversation.id'))

    def addLog(self, title, content, session):
        '''
        makes a log object and adds it to the conversation.
        Does NOT commit.
        '''
        if self.ensureConversation(session):
            session.commit()
        addLog(self.logging_cid, title, content, session)


    def add_llm_log(self, log: Log, session):
        '''
        Builds a log from the guru log object returned from prompt.execute().
        Does NOT commit.
        '''
        if self.ensureConversation(session):
            session.commit()
        LLMLog.fromGuruLogObject(log, self.logging_cid, session)

    def ensureConversation(self, session):
        '''
        Ensures that the conversation is initialized. passes back True if a new conversation was made, otherwise false.
        '''
        if self.logging_conversation:
            return False
        from models.conversation.db_conversation import DBConversation
        conversation = DBConversation.newLoggingConversation(session)
        self.logging_conversation = conversation
        self.logging_cid = conversation.id
        session.add(conversation)
        return True

    def getHTMLReport(self):
        return self.logging_conversation.getConversationReport()
    
    def getLogs(self, session):
        if self.logging_conversation:
            logs = [{
                self.__class__.__name__: self.id,
                'logs': self.logging_conversation.generateReport()}
                ]
        else:
            logs = []
        for prop in class_mapper(self.__class__).iterate_properties:
            if isinstance(prop, RelationshipProperty):
                #check the other one to see if it is a LoggableMixin
                if prop.mapper.class_ == LoggableMixin:
                    logs += prop.getLogs()
        return logs
    
    def getCost(self, session):
        '''
        iterate through the logs and sum the costs from the LLMLog objects.
        '''
        cost = 0
        for log in self.getLogs(session):
            for log in log['LLMCalls']:
                cost += log['total_cost']
        return cost

