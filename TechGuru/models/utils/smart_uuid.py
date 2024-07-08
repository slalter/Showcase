import uuid
from sqlalchemy.dialects.postgresql import UUID

from sqlalchemy.types import TypeDecorator, String, CHAR

from functools import lru_cache

class SmartUUID(TypeDecorator):
    impl = String(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(UUID(as_uuid=True))
        else:
            return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        return self.convert_to_uuid(value, dialect)

    @lru_cache(maxsize=1024)
    def convert_to_uuid(self, value, dialect):
        if not isinstance(value, uuid.UUID):
            value = uuid.UUID(value)
        if dialect.name == 'postgresql':
            return value
        else:
            return str(value)

    @lru_cache(maxsize=1024)  # Caching to avoid redundant processing
    def process_result_value(self, value, dialect):
        if value is None:
            return value
        return str(value)
