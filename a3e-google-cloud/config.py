import os
from sqlalchemy.pool import NullPool

SQLALCHEMY_DATABASE_URI = os.environ['DATABASE_URL']
SQLALCHEMY_TRACK_MODIFICATIONS = False
CORS_ALLOWED_ORIGINS = [
    'REDACTED'
]
