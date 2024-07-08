from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import event
#PSQL db
engine = create_engine('postgresql://user:password@db:5432/techgurudb',pool_size=20, max_overflow=20, pool_timeout=60)

Base = declarative_base()
Session = sessionmaker(bind=engine)





@event.listens_for(Session, 'after_commit')
def receive_after_commit(session):
    needs_commit = False
    for instance in session.new:
        if is_loggable(instance):
            made_bool = instance.ensureConversation(session)
            if made_bool:
                needs_commit = True

    if needs_commit:
        session.commit()

def is_loggable(instance):
    from models.utils.loggable import LoggableMixin
    return any(issubclass(c, LoggableMixin) for c in instance.__class__.__mro__)
