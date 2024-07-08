from sqlalchemy import text
def initialize_db(existing_engine = None):
    from models.database import Base, engine
    #execute 'CREATE EXTENSION VECTOR;' in the database
    existing_engine = existing_engine or engine
    with existing_engine.connect() as conn:
        conn.execution_options(isolation_level="AUTOCOMMIT").execute(text('CREATE EXTENSION IF NOT EXISTS VECTOR;'))
    Base.metadata.create_all(existing_engine)