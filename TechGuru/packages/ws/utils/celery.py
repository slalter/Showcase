from datetime import datetime
import uuid
import requests
import os

def emitFromCelery(session_id, emit_type, payload):
    from app import sio
    if not isinstance(payload, dict):
        payload = {'content': payload}
    request_id = str(uuid.uuid4())
    url = 'http://web:5000/internal'
    if os.environ.get('CONTAINER_ROLE','')=='web':
        sio.emit('json', payload, to=session_id)

    try:
        response = requests.post(url=url, json={
            'session_id': str(session_id),
            'emit_type': emit_type,
            'payload': payload,
            'request_id': request_id
        })
    except Exception as e:
        print(f"Error sending update to web: {e}")

