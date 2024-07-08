from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

#PSQL db
engine = create_engine('postgresql://user:password@localhost:5432/dbname')

Base = declarative_base()
Session = sessionmaker(bind=engine)