from functools import wraps
from flask import session, redirect, url_for
import os

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            # Redirect to login page if user is not in session
            # Redirect to login page if no token
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function
