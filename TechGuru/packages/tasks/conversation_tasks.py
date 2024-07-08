from app import celery
from models.database import Session
@celery.task(queue='high_priority')
def start_conversation_task(
    conversation_id,
    initial_messages=None,
    conversation_type=None,
    assignment_json=None,
    entry_assignment=None,
    assignment_json_path=None,
    sid=None,
    feature_args= None
):
    from packages.conversation_manager import conversation_manager
    session = Session()
    with session:
        conversation_manager.start_conversation(conversation_id, session, initial_messages, conversation_type, assignment_json, entry_assignment, assignment_json_path, sid, feature_args)

@celery.task(queue='high_priority')
def process_message_task(conversation_id, message, sid=None, system=False):
    from packages.conversation_manager import conversation_manager
    session = Session()
    with session:
        conversation_manager.process_message(conversation_id,session, message, sid, system)


@celery.task(queue='high_priority')
def start_object_request_task(object_request_id):
    from packages.conversation_manager import conversation_manager
    with Session() as session:
        conversation_manager.start_object_request_conversation(object_request_id,session)

@celery.task(queue='high_priority')
def deliver_external_tool_call_task(conversation_id, tool_id, tool_name, result):
    from packages.conversation_manager import conversation_manager
    with Session() as session:
        conversation_manager.deliver_external_tool_call(conversation_id, session, tool_id, tool_name, result)


@celery.task(queue='high_priority')
def resume_conversation_task(conversation_id, sid=None):
    from packages.conversation_manager import conversation_manager
    with Session() as session:
        conversation_manager.resume_conversation(conversation_id, session, sid)