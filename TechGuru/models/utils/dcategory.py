from models.database import Base
from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship

class CategoryMaster(Base):
    __tablename__ = 'category_master'
    id = Column(Integer, primary_key=True)
    category_name = Column(String, unique=True, nullable=False)
    category_type = Column(String, nullable=False)  # To identify different DCategory columns
    queue = relationship("CategoryQueue", back_populates="master")

class CategoryQueue(Base):
    __tablename__ = 'category_queue'
    id = Column(Integer, primary_key=True)
    category_id = Column(Integer, ForeignKey('category_master.id'))
    original_value = Column(String, nullable=False)
    row_reference = Column(Text, nullable=False)  # Store reference to the originating row
    master = relationship("CategoryMaster", back_populates="queue")



from sqlalchemy.types import TypeDecorator

class DCategory(TypeDecorator):
    impl = String

    def process_bind_param(self, value, dialect):
        if value is not None:
            return value.lower()
        return value

    def process_result_value(self, value, dialect):
        return value
    

from sqlalchemy import event
from sqlalchemy.orm import Session

def after_insert_or_update(mapper, connection, target):
    session = Session.object_session(target)
    if not isinstance(session, Session):
        return
    for column in target.__table__.columns:
        if isinstance(column.type, DCategory):
            category_name = getattr(target, column.name)
            if category_name:
                category = session.query(CategoryMaster).filter_by(category_name=category_name, category_type=column.name).first()
                if not category:
                    category = CategoryMaster(category_name=category_name, category_type=column.name)
                    session.add(category)
                    session.commit()
                queue_entry = CategoryQueue(category_id=category.id, original_value=category_name, row_reference=str(target.__table__.name) + ":" + str(target.id))
                session.add(queue_entry)
                session.commit()

event.listen(Base, 'after_insert', after_insert_or_update)
event.listen(Base, 'after_update', after_insert_or_update)
