from models import Base, Session
from sqlalchemy import Column, Integer, String, JSON, DateTime, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey
from datetime import datetime
from models.utils.smart_uuid import SmartUUID
import uuid

class Message(Base):
    __tablename__ = 'message'
    id = Column(SmartUUID(), primary_key=True,default=uuid.uuid4)
    dbconversation_id = Column(SmartUUID(), ForeignKey('db_conversation.id'), nullable=False, index=True)
    content = Column(String, nullable=False)
    role = Column(String, nullable=False)
    assignment = Column(String, nullable = True, default = 'unknown')
    created_at = Column(DateTime, default=datetime.now)


    def to_dict(self):
        return {
            "id": str(self.id),
            "dbconversation_id": str(self.dbconversation_id),
            "content": self.content,
            "role": self.role,
            "assignment":self.assignment,
            "created_at":str(self.created_at) if self.created_at else "none"
        }
    
    def __repr__(self):
        return f"<Message {self.role} {self.content} {self.assignment} {self.created_at}>"