from models import Base, Session
from sqlalchemy import Column, Integer, String, JSON, DateTime, Boolean, Float
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey
from datetime import datetime
from models.utils.smart_uuid import SmartUUID
import uuid
import json
from datetime import datetime, timedelta



class LLMLog(Base):
    __tablename__ = 'llm_log'
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    mode = Column(String(50), nullable=True, default = 'OpenAI')  # OpenAI, Azure, etc.
    attempts = relationship('LLMAttempt', backref='llm_log', lazy='joined', cascade='all, delete, delete-orphan')
    parent_id = Column(SmartUUID(), nullable = True)
    tenant_id = Column(SmartUUID(), nullable = True)
    request_type = Column(String(500), default = '')
    created_at = Column(DateTime, default=datetime.now)

    @staticmethod
    def getLogsForObject(object_id, session):
        with Session() as session:
            matches = session.query(LLMLog)\
                .filter(LLMLog.parent_id == object_id).all()
            return [match.to_dict() for match in matches]

    @staticmethod
    def getLogsForTenant(tenant_id, session):
        matches = session.query(LLMLog)\
            .filter(LLMLog.tenant_id == tenant_id).all()
        return [match.to_dict() for match in matches]
    
    @staticmethod
    def removeLogsFromObject(object_id, session):
        matches = session.query(LLMLog)\
            .filter(LLMLog.parent_id == object_id).all()
        for match in matches:
            session.delete(match) 

    @staticmethod
    def moveLogs(from_object_id, to_object_id, session):
        matches = session.query(LLMLog)\
            .filter(LLMLog.parent_id == from_object_id).all()
        for match in matches:
            match.parent_id = to_object_id
            


    @staticmethod
    def moveLogsAsGroup(from_object_id, to_object_id, session, description = 'no description provided'):
        #make a new log that contains the summation of all the logs.
        new_log = LLMLog(parent_id=to_object_id, tenant_id=from_object_id, id = uuid.uuid4())

        matches = session.query(LLMLog)\
            .filter(LLMLog.parent_id == from_object_id).all()
        for mat in reversed(matches):
            for attempt in mat.attempts:
                new_attempt = LLMAttempt(
                    llm_log_id = new_log.id,
                    elapsed_time = attempt.elapsed_time,
                    request_tokens = attempt.request_tokens,
                    response_tokens = attempt.response_tokens,
                    model = attempt.model,
                    cost = attempt.cost,
                    request_content = attempt.request_content,
                    response_content = attempt.response_content

                )
                session.add(new_attempt)
            new_log.mode = mat.mode
            new_log.tenant_id = mat.tenant_id


        new_log.request_type = description + f" total cost: {sum([a.cost for a in new_log.attempts])}"
        session.add(new_log)
        
            


    @staticmethod
    def fromGuruLogObject(log, parent_id, session):
        llmlog = log_to_llmlog(log, session)
        llmlog.parent_id = str(parent_id)
        llmlog.mode = log.mode
        session.add(llmlog)
      

    @staticmethod
    def getAverageUsage(session, start_time=None, end_time= None, metadata_filter=None):
        '''
        return the average tokens per minute for all logs in the database within the given time range.
        Returns a triple of total tokens, input tokens, and output tokens.
        Written as efficiently as possible.
        No start/end time defaults to the last 10 minutes.     
        The metadata filter is a series of key-value pairs that must be present on the LLMLog model.   
        '''
        if not start_time:
            start_time = datetime.now() - timedelta(minutes=10)
        if not end_time:
            end_time = datetime.now()
        total_tokens = 0
        input_tokens = 0
        output_tokens = 0
        #if there is a metadata filter, return only LLMLogs that match the metadata filter.
        if metadata_filter:
            logs = session.query(LLMLog).filter(LLMLog.created_at>=start_time, LLMLog.created_at<=end_time).all()
            for log in logs:
                for key, value in metadata_filter.items():
                    if not hasattr(log, key) or getattr(log, key) != value:
                        continue
                for attempt in log.attempts:
                    total_tokens += attempt.request_tokens + attempt.response_tokens
                    input_tokens += attempt.request_tokens
                    output_tokens += attempt.response_tokens

        logs = session.query(LLMLog).filter(LLMLog.created_at>=start_time, LLMLog.created_at<=end_time).all()
        for log in logs:
            for attempt in log.attempts:
                total_tokens += attempt.request_tokens + attempt.response_tokens
                input_tokens += attempt.request_tokens
                output_tokens += attempt.response_tokens
        #divide by the number of minutes in the range.
        minutes = (end_time-start_time).total_seconds()/60
        total_tokens = total_tokens/minutes
        input_tokens = input_tokens/minutes
        output_tokens = output_tokens/minutes
        return total_tokens, input_tokens, output_tokens

    def to_dict(self):
        return {
            'mode':self.mode,
            'num_attempts': len(self.attempts),
            'total_cost':sum([a.cost for a in self.attempts]),
            'llm_method':self.attempts[0].llm_method if self.attempts else None,
            'created_at': self.created_at,
            'request_type':self.request_type,
            'completed_at':max([a.created_at for a in self.attempts]) if self.attempts else datetime.now(),
            'results':[a.to_dict()['response_content'] for a in self.attempts],
            'attempts':[a.to_dict() for a in self.attempts]
        }

class LLMAttempt(Base):
    __tablename__ = 'llm_attempt'
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    llm_log_id = Column(String(36), ForeignKey('llm_log.id'), nullable=False)
    elapsed_time = Column(Float)
    request_tokens = Column(Integer)
    response_tokens = Column(Integer)
    model = Column(String(50))
    cost = Column(Float)
    request_content = Column(String)
    response_content = Column(String)
    llm_method = Column(String, nullable = True)

    created_at = Column(DateTime, default=datetime.now)
    def to_dict(self):
        return {
            'id': str(self.id),
            'elapsed_time': self.elapsed_time,
            'request_tokens': self.request_tokens,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'response_tokens': self.response_tokens,
            'model': self.model,
            'cost': self.cost,
            'llm_method': self.llm_method,
            'request_content': self.request_content,
            'response_content': self.response_content
        }
    

def log_to_llmlog(log, session):
    """
    Converts a Log object to an LLMLog object.
    
    Parameters:
    - log: An instance of the Log class.
    
    Returns:
    - An instance of the LLMLog class populated with data from the Log object.
    """
    # Initialize a new LLMLog instance
    new_id = str(uuid.uuid4())
    llm_log = LLMLog()
    llm_log.id = new_id
    llm_log.mode = log.mode
    llm_log.request_type = log.attempts[0].request_type
    llm_log.created_at = datetime.fromisoformat(log.created_at) if isinstance(log.created_at, str) else log.created_at
    
    # Iterate through the attempts in the Log object
    for attempt in log.attempts:
        # Create a new LLMAttempt instance for each attempt
        llm_attempt = LLMAttempt()
        llm_attempt.elapsed_time = attempt.elapsed_time
        llm_attempt.request_tokens = attempt.request_tokens
        llm_attempt.response_tokens = attempt.response_tokens
        llm_attempt.model = attempt.model
        llm_attempt.cost = attempt.cost
        llm_attempt.request_content = json.dumps(attempt.request_content)
        llm_attempt.response_content = json.dumps(attempt.response_content)
        llm_attempt.created_at = datetime.strptime(attempt.time, '%Y-%m-%d %H:%M:%S')
        llm_attempt.llm_log_id = new_id
        llm_attempt.llm_method = attempt.llm_method
        
        session.add(llm_attempt)
    
    return llm_log