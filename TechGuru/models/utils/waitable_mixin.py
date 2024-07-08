from models import Base, Session
from sqlalchemy import Column, Integer, String, JSON, DateTime, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey
from datetime import datetime
from .smart_uuid import SmartUUID
import uuid
from sqlalchemy.ext.declarative import declared_attr

class Wait(Base):
    '''
    an object tracking when one waitablemixin is waiting on another.
    '''
    __tablename__ = 'wait'
    id = Column(SmartUUID(), primary_key=True, default=uuid.uuid4)
    waiter_id = Column(SmartUUID())
    waiter_table_name = Column(String)
    waitee_id = Column(SmartUUID())
    waitee_table_name = Column(String)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now)



class WaitableMixin:
    '''
    Models that extend this mixin can wait on other models to complete, or vice versa.
    Useful for dormant conversations that are relying on something.
    Keeps Wait objects in the database.
    '''


    @declared_attr
    def status(cls):
        return Column(String, default='pending')#pending, fulfilled, error

    def is_waiter(self, session):
        '''
        Returns True if the object is waiting on another object.
        '''
        if session.query(Wait).filter(Wait.waiter_id==self.id).first():
            return True
        return False
    
    def is_waitee(self, session):
        '''
        Returns True if the object is being waited on by another object.
        ''' 
        if session.query(Wait).filter(Wait.waitee_id==self.id).first():
            return True
        return False
        
    def on_wait_fulfilled(self, session):
        '''
        Called when the object is waiting on another object and that object is fulfilled.
        Should be implemented in the waitee object.
        '''
        raise NotImplementedError

    def setStatus(self, status, session):
        '''
        Set the status of the object request. Done manually so that we can trigger other tasks consistently.
        '''
        self.status = status
        self.updated_at = datetime.now()

        if status == 'fulfilled':
            self.notify(session)

    def wait_for(self, object_id, object_class, session):
        '''
        Waits for an object to complete.
        '''
        wait = Wait(
            waiter = self.id, 
            waiter_table_name = self.__tablename__,
            waitee = object_id,
            waitee_table_name = object_class.__tablename__
        )
        session.add(wait)
        session.commit()

    def notify(self, session):
        '''
        Deletes the waits for which this object is the waitee.
        If the waiter is no longer waiting on anything, calls on_wait_fulfilled on the waiter.
        '''
        waits = session.query(Wait).filter(Wait.waitee_id==self.id).all()
        waiter_ids_tablenames = [(wait.waiter_id, wait.waiter_table_name) for wait in waits]
        for wait in waits:
            session.delete(wait)
        session.commit()
        for waiter_id, table_name in waiter_ids_tablenames:
            if not session.query(Wait).filter(Wait.waiter_id==waiter_id).first():
                waiter = session.query(table_name).filter(table_name.id==waiter_id).first()
                waiter.on_wait_fulfilled(session)

