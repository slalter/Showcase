from sqlalchemy import Column, Integer, ForeignKey, DateTime, event
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import declarative_base, mapper
from sqlalchemy.sql import func
from sqlalchemy.orm.session import Session
from sqlalchemy import Index

Base = declarative_base()

class VersionedMixin:
    @declared_attr
    def version_id(cls):
        return Column(Integer, default=0, nullable=False)

    @declared_attr
    def __history_mapper__(cls):
        # Define a history class dynamically for each subclass
        hist_cls = type(f'{cls.__name__}History', (Base,), {
            '__tablename__': f'{cls.__tablename__}_history',
            'id': Column(Integer, primary_key=True),
            'parent_id': Column(Integer, ForeignKey(f'{cls.__tablename__}.id', ondelete='CASCADE')),
            'version_id': Column(Integer, nullable=False),
            'timestamp': Column(DateTime, default=func.now(), nullable=False),
        })

        Index('ix_history_parent_version', hist_cls.parent_id, hist_cls.version_id)


        # Copy all other columns from the parent to the history table
        for column in cls.__table__.columns:
            if column.name not in ('id', 'version_id'):
                setattr(hist_cls, column.name, Column(column.type, nullable=column.nullable))

        return hist_cls

    @classmethod
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        event.listen(cls, 'before_insert', cls.create_history_entry)
        event.listen(cls, 'before_update', cls.create_history_entry)

    @staticmethod
    def create_history_entry(mapper, connection, target):
        """Create an entry in the history table on updates or inserts."""
        history_cls = target.__history_mapper__
        history_data = {
            'parent_id': target.id,
            'version_id': target.version_id + 1,
            **{attr: getattr(target, attr) for attr in target.__table__.c.keys() if attr not in ['id', 'version_id']}
        }
        connection.execute(history_cls.__table__.insert(), history_data)

    @classmethod
    def get_version(cls, id, version: int, session: Session):
        """
        Retrieve a specific version of this object.
        Returns a DETACHED instance, so if you want to make changes be careful and maybe make a new id?
        Alternatively, we can support branching versions. Would be good for ToT, but we have to consider how this affects dependencies, etc...
        """
        return session.query(cls.__history_mapper__).filter_by(parent_id=id, version_id=version).one()