
from models import Base, Session
from sqlalchemy import Column, Integer, String, JSON, DateTime, Boolean, LargeBinary, Enum, Text, TIMESTAMP, update
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey
from datetime import datetime
from models.utils.smart_uuid import SmartUUID
import uuid
import json
import pickle

class DBConversation(Base):
    __tablename__ = 'db_conversation'
    id = Column(SmartUUID(), primary_key=True,default=uuid.uuid4)
    messages = relationship('Message', backref='db_conversation',lazy='joined', cascade='all, delete, delete-orphan')
    status = Column(Enum('processing','awaiting_message','error','complete','awaiting_external_tool_call','paused', name='status'))
    task = Column(Text, nullable=False, default = '')
    pickle = Column(LargeBinary)
    updated_at = Column(TIMESTAMP(timezone=False), default=datetime.utcnow, onupdate=datetime.utcnow)
    current_assignment = Column(Text, nullable = True, default = 'unknown')
    logs = relationship('ConversationLog', backref='db_conversation', lazy=True, cascade='all, delete, delete-orphan')
    summary = Column(Text, default = '', nullable = True)
    socket_id = Column(Text, nullable = True)
    conversation_type = Column(String, nullable = True)
    closed = Column(Boolean, default = False)
    paused = Column(Boolean, default = False)


    @staticmethod
    def setSID(conversation_id, sid, session):
        stmt = (
        update(DBConversation)
        .where(DBConversation.id == conversation_id)
        .values(socket_id=sid)
        )
        session.execute(stmt)
        session.commit()

    @staticmethod
    def getSID(conversation_id, session):
        sid = session.query(DBConversation.socket_id).filter(DBConversation.id == conversation_id).first()
        return sid[0] if sid else None

    def sendUpdate(self, request_type, payload):
        '''
        Sends an update to the socket associated with this conversation by sending a message to the web container.
        '''
        from packages.ws.utils.celery import emitFromCelery
        if not self.socket_id:
            raise Exception(f"Conversation {self.id} does not have a socket_id! Cannot emit.")
        emitFromCelery(self.socket_id, request_type, payload)

    def notify(self, message, session):
        '''
        sends a system message to a conversation to notify the LLM that something has happened.
        starts a celery task.
        '''
        from models import Message
        from packages.tasks import process_message_task
        db_message = Message(
            db_conversation_id = self.id,
            content = message,
            role = 'system'
        )
        session.add(db_message)
        session.commit()
        process_message_task.delay(self.id, message, system=True)
        

    @staticmethod
    def newLoggingConversation(session):
        '''
        Creates a new conversation for logging purposes.
        Does NOT commit.
        '''
        dbconversation = DBConversation(
            status='processing',
            conversation_type = 'internal',
            id = str(uuid.uuid4())
            )
        session.add(dbconversation)
        return dbconversation

    @staticmethod
    def setStatus(conversation_id, status, session):
        stmt = (
        update(DBConversation)
        .where(DBConversation.id == conversation_id)
        .values(status=status)
        )
        session.execute(stmt)
        addLog(conversation_id, status, {},session)
        session.commit()

    @staticmethod
    def setTask(conversation_id, task, session):
        stmt = (
        update(DBConversation)
        .where(DBConversation.id == conversation_id)
        .values(task=task)
        )
        session.execute(stmt)
        addLog(conversation_id, task, {},session)
        session.commit()


    def to_dict(self):
        sorted_messages = sorted(self.messages, key=lambda message: message.created_at)
        sorted_reports = sorted(self.reports, key=lambda report:report.created_at)
        return {
            "id": str(self.id),
            "tenant_id": str(self.tenant_id),
            "messages": [message.to_dict() for message in sorted_messages],
            "reports": [report.to_dict() for report in sorted_reports],
            "subscribed": self.subscribed,
            "status": self.status if self.status else None,
            "task": self.task,
            "conversation_type": self.conversation_type,
            "closed":self.closed,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "current_assignment":self.current_assignment,
            "summary":self.summary
        }
    
    @staticmethod
    def savePickle(conversation_id, conversation, session):
        pickled = pickle.dumps(conversation)
        stmt = (
        update(DBConversation)
        .where(DBConversation.id == conversation_id)
        .values(pickle=pickled)
        )
        session.execute(stmt)
        session.commit()

    @staticmethod
    def loadPickle(conversation_id, session):
        dbconversationpkl = session.query(DBConversation.pickle).filter(DBConversation.id==conversation_id).first()
        if not dbconversationpkl:
            raise Exception(f"Conversation {conversation_id} not found in database!")
        conversation = pickle.loads(dbconversationpkl[0])
        return conversation

        
    def generateReport(self,session):
        #TODO: the LLMLog get logs thing is pretty wonky. Should be a relationship or at least an index. Does it even cascade?
        from models import LLMLog
        report = {
            'messages': [message.to_dict() for message in self.messages],
            'logs': [log.to_dict() for log in self.logs],
            'LLMCalls': LLMLog.getLogsForObject(self.id,session)
        }
        return report
    
    def getConversationReport(self,session):
        from .conversation_log import formatReportToHTML
        report_data = self.generateReport(session)
        return formatReportToHTML(report_data)
    
    def __repr__(self):
        return f"<DBConversation {self.id} {self.status} {self.task} {self.current_assignment} {self.updated_at}>"
    

def addLog(conversation_id, type, content, session):
    '''
    returns true or false.
    Does NOT commit.
    '''
    from models.conversation.conversation_log import ConversationLog
    try:
        if not content:
            content = {}
        if not isinstance(content, dict):
            content = {'content':content}
        if not conversation_id:
            raise Exception(f"this content tried to get logged with no cid!. \n{type}\n{content}")

        try:
            json.dumps(content)
        except Exception as e:
            for key, value in content.items():
                try:
                    json.dumps({key:value})
                except Exception as e:
                    content[key] = str(value)
        log = ConversationLog(type=type, dbconversation_id = conversation_id, content=content)
        session.add(log)
        return True
    except Exception as e:
        print(f"Failed to add log to conversation {conversation_id}! {e}")
        return False
