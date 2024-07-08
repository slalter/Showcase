
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy import cast
import uuid
from sqlalchemy import Column, String, DateTime, Boolean, JSON, func
from models import Base
#TODO: update this.
class User(Base):
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)
    first_name = Column(String(255), nullable=False)
    last_name = Column(String(255), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    email = Column(String(255), nullable=False, unique=True)
    known_alias_emails = Column(JSONB, nullable=False, default=[])
    is_admin = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    is_verified = Column(Boolean, nullable=False, default=False)
    created_from = Column(String(255), nullable=False, default='')
    transaction_history = Column(JSON(), nullable=False, default=[])
    send_admin_notifications = Column(Boolean, default=False)


    @classmethod
    def find_by_email(cls, email, session) -> 'User'|None:
        result = session.query(cls).filter(cls.email == email.lower()).first()
        if result:
            return result
        alias_result = session.query(cls).filter(
            cls.known_alias_emails.contains([email])  # Correct usage of the contains method
        ).first()
        if alias_result:
            return alias_result
        return None
        
   