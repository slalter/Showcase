import packages.conversation_manager as cm
from models.database import Session
import uuid
from flask_socketio import emit

def start_conversation(json, sid):
    '''
    Starts a conversation.
    '''
    from packages.tasks import start_conversation_task
    json['session'] = Session()
    json['sid'] = sid
    json.pop('request_type')
    json.pop('request_id')
    json['conversation_id'] = str(uuid.uuid4())
    start_conversation_task.delay(**json)
    emit('json',{'request_type':'new_conversation','conversation_id':json['conversation_id']})


def process_message(json, sid):
    '''
    Processes a message.
    '''
    print('processing message')
    from packages.tasks import process_message_task
    json['sid'] = sid
    json.pop('request_type')
    json.pop('request_id')
    process_message_task.delay(**json)