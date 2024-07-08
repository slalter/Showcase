
import dotenv
import json
dotenv.load_dotenv('.env')

from flask import Flask, request, jsonify, render_template
from cryptography.fernet import Fernet
from flask_cors import cross_origin
import os
from flask_socketio import SocketIO 
import io
import sys
from sqlalchemy import update
from flask_socketio import emit 
os.environ['debug'] = 'True'
from packages.debug import debug
if os.environ.get('debug', None):
    debug()


app = Flask(__name__)
sio = SocketIO(app)
from celery_app.celery import make_celery
celery = make_celery(app)

app.secret_key = os.getenv('SECRET_KEY')

from models import *

from packages.guru import cli, Flows, GLLM
from packages.ws.process_json import process_json
from packages.tasks import *

@app.route('/internal', methods=['POST'])
def internal():
    '''
    emit the message to the target session_id.
    expects:
    {
        'session_id': 'session_id',
        'payload': 'payload'
    }
    '''
    data = request.get_json()
    payload = data['payload']
    payload['request_type'] = data['emit_type']
    sio.emit('json', payload, to=data['session_id'])
    return jsonify({'status': 'success'})
    

@sio.on('connect')
def connect():
    print('connected')
    emit('response', {'content': 'Connected'})

@sio.on('disconnect')
def disconnect():
    print('disconnected')
    emit('response', {'content': 'Disconnected'})

@sio.on('json')
def handle_json(json):
    print('received json: ' + str(json))
    emit('response', {'content': 'Received JSON'})
    return process_json(json, request.sid) or {'content': 'Processed JSON'}

@cross_origin()
@app.route('/')
def home():
    return render_template('index.html')

@cross_origin()
@app.route('/start')
def start():
    return render_template('start.html')

@cross_origin
@app.route('/conversation')
def conversation():
    return render_template('conversation.html')

@cross_origin
@app.route('/pause/<conversation_id>')
def pause(conversation_id):
    '''
    a pause takes effect the next time the LLM gets to the top of the getResponse method.
    '''
    with Session() as session:
        #TODO:
        '''
        #check to see if the conversation is the logging_cid for any projects.
        logging_cid = session.query(Project).filter_by(logging_cid=conversation_id).first()
        if logging_cid:
            #make a list of all the object requests for this project and pause them, too.
        '''

        #atomically update the conversation
        stmt = (
            update(DBConversation)
            .where(DBConversation.id == conversation_id)
            .values(status='paused')
        )
        session.execute(stmt)
        session.commit()
        return 'Conversation paused.'

@cross_origin
@app.route('/resume/<conversation_id>')
def resume(conversation_id):
    from packages.tasks import resume_conversation_task
    #if the conversation is not paused, return an error
    with Session() as session:
        conversation = session.query(DBConversation).filter_by(id=conversation_id).first()
        if conversation.status != 'paused':
            return 'Conversation is not paused.'
    resume_conversation_task.delay(conversation_id)
    return 'Conversation resumed.'

@cross_origin
@app.route('/project/<project_id>')
def builder(project_id):
    with Session() as session:
        project = session.query(Project).filter_by(id=project_id).first()
        if not project:
            return 'Project not found.'
        return render_template('project.html', project=project, session=session)

@cross_origin()
@app.route('/report/<conversation_id>')
def report(conversation_id):
    return render_template('report.html', conversation_id=conversation_id)

@cross_origin()
@app.route('/test')
def test():
    from models import Project
    from packages.utils import recursive_dict
    from features.appBuilderUtils.dependencyAnalyzer import DependencyAnalyzer
    def getDisplay(object):
        d = recursive_dict(object)
        d['dependencies']= [d.name for d in object.dependencies]
        return d
    with Session() as session:
        da = DependencyAnalyzer('app.py', Session, '6609c9e2-e750-4881-9876-3eb6a54b3f7b')
        da.analyze()
        da.build_dependency_digraph(session)
        digraph:bytes = da.display_dependency_digraph()
        #return html snippet to display the png
        import base64
        return f'<img src="data:image/png;base64,{base64.b64encode(digraph).decode()}"/>'


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)