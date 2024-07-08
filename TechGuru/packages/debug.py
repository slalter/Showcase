from sqlalchemy import MetaData
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql import select, text

import os
def debug():
    if os.environ.get('CONTAINER_ROLE',None) and os.environ.get('CONTAINER_ROLE') != 'web':
        print("debug is active! but not in web container, skipping..")
        return
    print("debug is active! changing print...")
    changePrint()
    print("remaking db")
    from models.database import Base, engine
    drop_all_with_cascade(engine)
    Base.metadata.create_all(engine)

import builtins
def changePrint():
    print("changing print function...")
    # Store the original print function
    original_print = builtins.print

    def custom_print(*args, **kwargs):
        kwargs['flush'] = True
        # Use the original print function stored earlier
        original_print(*args, **kwargs)

    # Override the built-in print
    builtins.print = custom_print


# Function to drop all tables with cascade
def drop_all_with_cascade(engine):
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            # Reflect the database schema to get the metadata of all tables
            meta = MetaData()
            meta.reflect(bind=engine)
            
            # Drop all tables with cascade
            for table in reversed(meta.sorted_tables):
                print(f'Dropping table {table.name}')
                conn.execute(text(f'DROP TABLE IF EXISTS {table.name} CASCADE'))
            
            trans.commit()
        except SQLAlchemyError as e:
            trans.rollback()
            print(f"An error occurred: {e}")
            raise