from flask import render_template
from utils.email import sendErrorEmail
import json
import os

def handleError(error, details):
    print(f"An error has occurred: {error} {details}", flush=True)
    if os.environ.get('TESTING','False').lower() == 'true' or os.environ.get('ENVIRONMENT','').lower() == 'local':
        return render_template('error.html', error = error + details + str(unpack_locals_as_dict(locals())) )
    sendErrorEmail(f"An error has occurred: {error}", f"Details:{details}\n {unpack_locals_as_dict(locals())}")
    return render_template('error.html', error = error)


def unpack_locals_as_dict(locals):

    def unpack(obj):
        if hasattr(obj, '__dict__'):
            return {k: unpack(v) for k, v in obj.__dict__.items() if not k.startswith('__')}
        return obj

    out = {}
    for k,v in locals.items():
        try:
            if not k.startswith('__'):
                out[k] = unpack(v)
        except Exception as e:
            out[k] = f'Error unpacking object:{e} + {v}'
    return json.dumps(out, indent=4)


#a wrapper to catch exceptions and call handleError
def errorWrapper(f):
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            return handleError(e, f"{args} {kwargs}")
    return wrapper

