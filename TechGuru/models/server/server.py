from models import Base, Session
from sqlalchemy import Column, Integer, String, JSON, DateTime, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey
from datetime import datetime
from models import SmartUUID, EncryptedString
import uuid


#TODO
class Server(Base):
    '''
    Represents the VM on which the project is hosted.
    '''
    __tablename__ = 'server'
    id = Column(SmartUUID(), primary_key=True, default=uuid.uuid4)
    name = Column(String)
    project = relationship("Project", back_populates="server")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    ip = Column(String)
    ssh_key = Column(EncryptedString)