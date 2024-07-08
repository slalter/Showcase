import os
from sqlalchemy.pool import NullPool

SQLALCHEMY_DATABASE_URI = os.environ['DATABASE_URL']
SQLALCHEMY_TRACK_MODIFICATIONS = False
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    'http://localhost:5000',
    'https://localhost:5000',
    'https://localhost:3000',
    'http://127.0.0.1:5000',
    'http://34.42.45.101:5000',
    'https://34.42.45.101:5000',
    'http://34.42.45.101:443',
    'https://34.42.45.101:443',
    'http://34.42.45.101:80',
    'https://34.42.45.101:80'
]
