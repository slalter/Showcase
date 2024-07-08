
def getReport(request, sid):
    '''
    Returns a conversation report.
    '''
    from flask_socketio import emit 
    from models import DBConversation
    from models.database import Session

    print(request)
    with Session() as session:
        conversation = session.query(DBConversation).filter(DBConversation.id==request['conversation_id']).first()
        if conversation:
            report = conversation.getConversationReport(session)
            emit('json', {'content': report}, room=sid)
        else:
            emit('json', {'content': 'Conversation not found'}, room=sid)