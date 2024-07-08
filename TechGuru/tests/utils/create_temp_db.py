
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

def create_temp_db():
    try:
        temp_db_name = 'tempdb_test'
        db_user = 'user'
        db_password = 'password'
        db_host = 'db'
        db_port = '5432'
        
        # Connect to the default database to create a new one
        default_engine = create_engine(f'postgresql://{db_user}:{db_password}@{db_host}:{db_port}/postgres')
        with default_engine.connect() as default_conn:
            default_conn.execution_options(isolation_level="AUTOCOMMIT").execute(text(f"CREATE DATABASE {temp_db_name}"))

        # Create an engine for the temporary database
        temp_db_url = f'postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{temp_db_name}'
        engine = create_engine(temp_db_url, pool_size=20, max_overflow=20, pool_timeout=60)
        Session = sessionmaker(bind=engine)

        #initialize the db
        from models.utils.commands import initialize_db
        initialize_db(engine)

        return engine, Session, temp_db_name
    except Exception as e:
        # Drop the temporary database if an error occurs
        try:
            drop_temp_db(default_engine, temp_db_name)
        except:
            pass
        raise e

def drop_temp_db(engine, temp_db_name):
    db_user = 'user'
    db_password = 'password'
    db_host = 'db'
    db_port = '5432'

    # Dispose the engine to close all connections
    engine.dispose()

    # Connect to the default database to drop the temporary one
    default_engine = create_engine(f'postgresql://{db_user}:{db_password}@{db_host}:{db_port}/postgres')
    with default_engine.connect() as default_conn:
        default_conn.execution_options(isolation_level="AUTOCOMMIT").execute(text(f"DROP DATABASE {temp_db_name}"))