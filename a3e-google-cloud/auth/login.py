from functools import wraps
from flask import session, redirect
import os
import time
import requests
from google.auth.transport import requests
from google.oauth2 import id_token

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from models import User
        from app import db
        from app import prefixed_url_for
        if not session.get('user',None):
            if os.environ.get('ENVIRONMENT','').lower()=='local':
                session['user'] = {'email':''}
                return f(*args, **kwargs)
            else:
                # Redirect to login page if user is not in session
                return redirect(prefixed_url_for('login'))
        #check to see if the access token has expired
        if 'token_expires_at' in session:
            if session['token_expires_at'] < time.time():
                if not refresh_access_token() or os.environ.get('ENVIRONMENT','').lower()=='local':
                    return redirect(prefixed_url_for('login'))
        print("got here", flush=True)
        user = User.find_by_email(session['user']['email'],db)
        if not user or not user.verify_token(session.get('id_token','')):
            return redirect(prefixed_url_for('login'))
        
        if os.environ.get('TESTING', 'false').lower() == 'true':
            if not user.is_admin:
                return redirect(prefixed_url_for('no_access'))
        return f(*args, **kwargs)
    return decorated_function


def refresh_access_token():
    from app import db
    from models import User
    from app import db
    user_email = session.get('user', {}).get('email')
    if not user_email:
        return None

    user = User.find_by_email(user_email, db)
    if not user or not user.refresh_token or user.refresh_expires_at < time.time():
        return None

    refresh_response = requests.post(
        'https://oauth2.googleapis.com/token',
        data={
            'client_id': os.environ.get('GOOGLE_CLIENT_ID'),
            'client_secret': os.environ.get('GOOGLE_CLIENT_SECRET'),
            'refresh_token': user.refresh_token,
            'grant_type': 'refresh_token'
        }
    )

    new_token_data = refresh_response.json()

    if refresh_response.status_code != 200:
        print(f"Error refreshing token: {new_token_data}")
        return None

    session['access_token'] = new_token_data['access_token']
    session['token_expires_at'] = time.time() + new_token_data['expires_in']
    return new_token_data['access_token']


def verify_google_token(token):
    request = requests.Request()
    try:
        id_info = id_token.verify_oauth2_token(token, request, os.environ.get('GOOGLE_CLIENT_ID'))
    except ValueError as e:
        print(f"Error verifying token: {e}")
        return None
    return id_info