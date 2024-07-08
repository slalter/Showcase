from db import db
import uuid
from flask import session,redirect
from flask_admin.contrib.sqla import ModelView
from sqlalchemy.dialects.postgresql import UUID
from models import User
from sqlalchemy.orm import Query
import os
from flask import request

from flask_admin import AdminIndexView, expose


class Product(db.Model):
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    folders = db.Column(db.JSON(), nullable=False, default = [])



class AdminModelView(ModelView):

    @expose('/' if not os.environ.get('TESTING', 'false').lower() == 'true' else '/testing/')
    def index(self):
        if os.environ.get('TESTING', 'false').lower() == 'true':
            if not session.get('user',{}).get('is_admin',False):
                return redirect('/no-access')
            else:
                print("redirecting to testing.")
                #redirect to /testing/this_url
                return redirect('/testing'+request.path)
        else:
            return self.index_view()

    
    def is_accessible(self):
        print("Checking if user is admin...")
        if os.environ.get('ENVIRONMENT','').lower()=='local':
            return True
        if not session.get('user',None):

            print("User is not logged in. session data: ", safe_dump(session))
            return False
        user = User.find_by_email(session.get('user',{}).get('email',""),db)
        if user and user.is_admin:
            print("User is admin")
            return True
        print("User is not admin")
        return False

    def inaccessible_callback(self, name, **kwargs):
        from app import prefixed_url_for
        # Redirect to login page if user is not authorized
        if not session.get('user',None):
            return redirect(prefixed_url_for('login'))
        return redirect(prefixed_url_for('no-access'))


from flask_admin import AdminIndexView as _AdminIndexView
import json
class AdminIndexView(_AdminIndexView):

    @expose('/')
    def index(self):
        from app import prefixed_url_for
        if os.environ.get('ENVIRONMENT','').lower()=='local':
            return self.render('admin/index.html', user=User.find_by_email('', db))
        user = User.find_by_email(session.get('user',{}).get('email',''),db)
        if not user or not user.verify_token(session.get('id_token','')):
            return redirect(prefixed_url_for('login'))
        if not user.is_admin:
            return redirect(prefixed_url_for('no-access'))
        return self.render('admin/index.html', user=user)
    
    def __init__(self, *args, **kwargs):
        super(AdminIndexView, self).__init__(*args, **kwargs)

    def is_accessible(self):
        if os.environ.get('ENVIRONMENT','').lower()=='local':
            return True
        print("Checking if user is admin...")
        if not session.get('user',None):
            print("User is not logged in")
            return False
        user = User.find_by_email(session.get('user').get('email'),db)
        if user and user.is_admin:
            print("User is admin")
            return True
        print("User is not admin")
        return False
    
    def inaccessible_callback(self, name, **kwargs):
        from app import prefixed_url_for
        # Redirect to login page if user is not authorized
        if not session.get('email',None):
            return redirect(prefixed_url_for('login'))
        return redirect(prefixed_url_for('no-access'))

class UserModelView(AdminModelView):
    column_list = ('email', 'first_name','last_name','is_admin','send_admin_notifications')

class ButtonRequestModelView(AdminModelView):
    column_list = ('proposal_number', 'product_name', 'price', 'status', 'payment_methods', 'created_at', 'created_by', 'id', 'folder_name','folder_url','upload_only_url')
    column_sortable_list = ('proposal_number', 'product_name', 'price', 'status', 'created_at', 'created_by', 'id')
    column_formatters = {
        'payment_methods': lambda v, c, m, p: json.dumps(m.payment_methods)
    }

class ProductModelView(AdminModelView):
    column_list = ('name','folders')


def safe_dump(object):
    try:
        return json.dumps(object, indent=4, default=lambda o: o.__dict__)
    except:
        try:
            return json.dumps(object, indent=4, default=str)
        except:
            return str(object)
