
from app import celery
from models.database import Session

@celery.task(queue='high_priority')
def start_zip_conversation(zip1_id, zip2_id, interaction_id):
    pass