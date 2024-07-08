from models import DBConversation, Message, addLog, LLMLog, ObjectRequest
from models.database import Session
import json
import traceback
from packages.guru.Flows import Conversation, features
from concurrent.futures import ThreadPoolExecutor
import time
import uuid

def new_conversation(conversation_id, 
                     session,
                     initial_messages=None, 
                     conversation_type=None, 
                     assignment_json=None, 
                     entry_assignment=None, 
                     assignment_json_path=None,
                     feature_args = None):
    if not initial_messages:
        initial_messages = [{'role':'user', 'content':'begin by introducing yourself and stating your purpose.'}]

    if not assignment_json:
        if not assignment_json_path:
            raise Exception("no assignment json provided!")
        else:
            with open(assignment_json_path, 'r') as f:
                assignment_json = f.read()
            assignment_json = json.loads(assignment_json)
            
    else:
        if not isinstance(assignment_json, dict):
            assignment_json = json.loads(assignment_json)
    entry_assignment = entry_assignment if entry_assignment else (conversation_type if conversation_type else 'initAssignment')
    if feature_args:
        for assignment in assignment_json['assignments']:
            for feature in assignment['features']:
                for arg in feature_args:
                    if feature['featureName'] == arg['featureName']:
                        feature['args'].update(arg['args'])
    conversation = Conversation(assignment_json, conversation_id=conversation_id, entry_assignment=entry_assignment)
    
    with ThreadPoolExecutor() as executor:
        results = list(executor.map(lambda feature: features.run('preAssignment', feature), conversation.currentAssignment.features))
    response = conversation.getResponse(session, initial_messages)
    return handleResult(conversation, response, session)

def new_message_from_user(conversation_id, message, session):
    from models import DBConversation
    conversation:Conversation = DBConversation.loadPickle(conversation_id, session)
    conversation.id = conversation_id
    try:
        result = conversation.getResponse(session,message)
    except Exception as e:
        session.rollback()
        addLog(conversation_id,'Exception: new_message_from_user',{'error':f"Error in new_message_from_user: {traceback.format_exception(e)}"},session)
        session.commit()
        return

    return handleResult(conversation, result,session)

def new_message_from_system(conversation_id, message,session):
    from models import DBConversation
    conversation:Conversation = DBConversation.loadPickle(conversation_id,session)
    conversation.id = conversation_id
    try:
        result = conversation.getResponse(session,[{'role':'system', 'content':message}])
    except Exception as e:
        session.rollback()
        addLog(conversation_id,'Exception: new_message_from_system',{'error':f"Error in new_message_from_system: {traceback.format_exception(e)}"},session)
        session.commit()
       
        raise e
    return handleResult(conversation, result,session)
    

def deliver_external_tool_call(conversation_id, session, tool_id, tool_name, result):
    status, _ = session.query(DBConversation.status).filter(DBConversation.id==conversation_id).first()
    waits = 0
    while not status == 'awaiting_external_tool_call':
        time.sleep(0.5)
        waits += 1 
        status, _ = session.query(DBConversation.status).filter(DBConversation.id==conversation_id).first()
        #wait 20 seconds max
        if waits > 10:
            print(f"tool call delivery timed out!")
            raise Exception("tool call delivery timed out!")
    
    conversation = DBConversation.loadPickle(conversation_id,session)

    conversation_result = conversation.deliverExternalToolCalls(
        session,
        [{'id':tool_id, 'function':{'name':tool_name}}],
        [result]
        )
    
    return handleResult(conversation, conversation_result, session)

def handleResult(conversation:Conversation, result, session):
    try:
        conversation_id = conversation.id
        if result == 'paused':
            DBConversation.savePickle(conversation_id, conversation,session)
            DBConversation.setStatus(conversation_id, 'paused',session)
            session.commit()
            return result
        addLog(conversation_id,'Assistant Response',{'result':result},session=session)
        if result == 'end':
            DBConversation.setStatus(conversation_id, 'complete',session)
        
        elif isinstance(result, dict) and result.get('external_tools'):
            DBConversation.setStatus(conversation_id, 'awaiting_external_tool_call',session)
            addLog(conversation_id,'Awaiting External Tool Call',{'result':result})
        else:
            DBConversation.setStatus(conversation_id, 'awaiting_message',session)


        DBConversation.savePickle(conversation_id, conversation,session)
        session.commit()
        return result
    except Exception as e:
        session.rollback()
        if conversation.id:
            addLog(conversation.id,'Exception: handleResult',{'error':f"Error in handleResult: {traceback.format_exception(e)}"}, session)
            session.commit()
        DBConversation.setStatus(conversation_id, 'error', session)
        session.commit()
        raise e
    
def start_conversation(conversation_id, 
                       session,
                       initial_messages=None,
                       conversation_type=None, 
                       assignment_json=None, 
                       entry_assignment=None,
                       assignment_json_path = None,
                       sid = None,
                        feature_args = None
                       ):
    try:
        nc = session.get(DBConversation, conversation_id)
        if not nc:
            nc = DBConversation(id = conversation_id,
                                conversation_type=conversation_type, 
                                status = 'processing',
                                task = ['processing user input']
                                )
            session.add(nc)
            session.commit() #this is necessary because changing status and task trigger a secondary process. TODO: make that process handled via a celery worker so this doesn't matter.
        if sid:
            nc.socket_id = sid
            session.commit()
        if initial_messages:
            for msg in initial_messages:
                #create via session.execute to avoid triggering listeners
                session.execute(Message.__table__.insert().values(content=msg['content'], role=msg['role'], dbconversation_id=conversation_id))
                session.commit()
    
            with open(f'assignments/{conversation_type}.json', 'r') as f:
                txt = f.read()
                assignment_json = json.loads(txt)
                entry_assignment = 'initAssignment' if not entry_assignment else entry_assignment
            
        else:
            if assignment_json_path:
                with open(assignment_json_path, 'r') as f:
                    assignment_json = f.read()
                assignment_json = json.loads(assignment_json)
            else:
                if not assignment_json:
                    raise Exception("no assignment json provided!")


        response = new_conversation(conversation_id, 
                                    session,
                                    initial_messages=initial_messages,
                                    conversation_type=conversation_type, 
                                    assignment_json = assignment_json, 
                                    entry_assignment = entry_assignment, 
                                    assignment_json_path=assignment_json_path,
                                    feature_args = feature_args)
        return response

    except Exception as e:
        try:
            session.rollback()
            print(f"An error occurred while running {conversation_id}: {str(e)}.\nStack trace: {traceback.format_exception(e)}")
            db_conversation = session.get(DBConversation, conversation_id)
            if db_conversation:
                try:
                    addLog(conversation_id,'Exception in start conversation!',{'exception':str(e),'traceback':traceback.format_exception(e)})
                except:
                    pass
                db_conversation.status = 'error'
                session.commit()
            else:
                print(f"Conversation {conversation_id} not found")
        except Exception as inner_exception:
            print(f"An error occurred while handling the original exception: {inner_exception}")
            raise
    
def process_message(conversation_id, session, message, sid=None, system=False):
    if not system:
        return process_message_from_user(conversation_id, session, message, sid)
    else:
        return process_message_from_system(conversation_id, session, message)
    
def process_message_from_user(conversation_id, session, message, sid=None):
    DBConversation.setStatus(conversation_id, 'processing',session)
    DBConversation.setTask(conversation_id, 'processing user input.',session)
    if sid:
        DBConversation.setSID(conversation_id, sid,session)
    
    try:
        dbmsg = Message(content=message,role='user',dbconversation_id=conversation_id)
        session.add(dbmsg)
        session.commit()

        result = new_message_from_user(conversation_id, message,session)
        addLog(conversation_id,'Conversation Response',{'content':result},session)
        session.commit()

        return result
            
    except Exception as e:
        print(f"An error occurred while running {conversation_id}: {str(e)}.\nStack trace: {traceback.format_exception(e)}",session)
        #set status of conversation to error
        session.rollback()
        try:
            db_conversation = session.get(DBConversation, conversation_id)
            if db_conversation:
                try:
                    addLog(conversation_id,'Exception in process message!',{'exception':str(e),'traceback':traceback.format_exception(e)},session)
                except:
                    pass
                db_conversation.status = 'error'
                session.commit()
            else:
                print(f"Conversation {conversation_id} not found")
        except Exception as inner_exception:
            session.rollback()
            print(f"An error occurred while handling the original exception: {inner_exception}")
            raise

def process_message_from_system(conversation_id, session, message):
    DBConversation.setStatus(conversation_id, 'processing',session)
    DBConversation.setTask(conversation_id, 'processing system message.',session)
    try:
        dbmsg = Message(content=message,role='system',dbconversation_id=conversation_id)
        session.add(dbmsg)
        session.commit()

        result = new_message_from_system(conversation_id, message, session)
        addLog(conversation_id,'Conversation Response',{'content':result},session)
        session.commit()

        return result
            
    except Exception as e:
        print(f"An error occurred while running {conversation_id}: {str(e)}.\nStack trace: {traceback.format_exception(e)}",session)
        #set status of conversation to error
        session.rollback()
        try:
            db_conversation = session.get(DBConversation, conversation_id)
            if db_conversation:
                try:
                    addLog(conversation_id,'Exception in process message!',{'exception':str(e),'traceback':traceback.format_exception(e)},session)
                except:
                    pass
                db_conversation.status = 'error'
                session.commit()
            else:
                print(f"Conversation {conversation_id} not found")
        except Exception as inner_exception:
            print(f"An error occurred while handling the original exception: {inner_exception}")
            raise
        raise

def resume_conversation(conversation_id, session, sid=None):
    '''
    resumes a paused conversation by calling the getResponse method with no inputs.
    '''
    DBConversation.setStatus(conversation_id, 'processing',session)
    DBConversation.setTask(conversation_id, 'resuming conversation.',session)
    if sid:
        DBConversation.setSID(conversation_id, sid,session)
    try:
        result = new_message_from_user(conversation_id, '',session)
        addLog(conversation_id,'Conversation Response',{'content':result},session)
        session.commit()
        return result
    except Exception as e:
        print(f"An error occurred while resuming {conversation_id}: {str(e)}.\nStack trace: {traceback.format_exception(e)}",session)
        #set status of conversation to error
        session.rollback()
        try:
            db_conversation = session.get(DBConversation, conversation_id)
            if db_conversation:
                try:
                    addLog(conversation_id,'Exception in resume conversation!',{'exception':str(e),'traceback':traceback.format_exception(e)},session)
                except:
                    pass
                db_conversation.status = 'error'
                session.commit()
            else:
                print(f"Conversation {conversation_id} not found")
        except Exception as inner_exception:
            print(f"An error occurred while handling the original exception: {inner_exception}")
            raise
        raise

def start_object_request_conversation(object_request_id, session):
    try:
        object_request:ObjectRequest = session.get(ObjectRequest, object_request_id) 
        if not object_request:
            raise Exception(f"Object request {object_request_id} not found!")
        if object_request.status == 'fulfilled':
            raise Exception(f"Object request {object_request_id} already fulfilled!")
        if not object_request.logging_cid:
            raise Exception(f"Object request {object_request_id} has no logging_cid!")
        response = new_conversation(
            object_request.logging_cid, 
            session,
            initial_messages=[{'role':'user', 'content':'Begin working on the requested object.'}],
            conversation_type='object_request', 
            assignment_json_path='assignments/object_request.json',
            entry_assignment = 'initAssignment',
            feature_args = [
                {'featureName':'AppBuilder','args':{
                    'object_request_id':object_request_id,
                    'project_id':object_request.project_id
                    }}
            ]
            )
        return response
    except Exception as e:
        print(f"An error occurred while running {object_request_id}: {str(e)}.\nStack trace: {traceback.format_exception(e)}")
        #set status of conversation to error
        session.rollback()
        try:
            object_request = session.get(ObjectRequest, object_request_id)
            if object_request:
                try:
                    object_request.addLog('Exception in start object request conversation!', {'exception':str(e),'traceback':traceback.format_exception(e)}, session)
                except Exception as e:
                    print(f"Error adding log to object request: {e}")
            else:
                print(f"Object request {object_request_id} not found")
        except Exception as inner_exception:
            print(f"An error occurred while handling the original exception: {inner_exception}")
            raise
        raise
