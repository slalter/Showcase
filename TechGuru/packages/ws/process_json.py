from flask_socketio import emit 
from models import DBConversation
from models.database import Session


def process_json(json, sid):
    '''
    handles json from the ws.
    '''
    from .conversation_functions.report import getReport
    from .conversation_functions.manage_conversation import start_conversation, process_message
    from .project_functions import start_project
    
    func_dict = {
        'get_report': getReport,
        'new_conversation': start_conversation,
        'new_message': process_message,
        'start_project': start_project,
    }
    return func_dict[json['request_type']](json, sid)