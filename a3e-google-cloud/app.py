#get secrets from google secret manager
from google.cloud import secretmanager
import os
from datetime import timedelta
from flask_session import Session
import redis

#if the file exists
if os.path.exists('application_default_credentials.json'):
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'application_default_credentials.json' #dynamically inserted.

# Check if the TESTING environment variable is set to 'true'
is_testing = os.environ.get('TESTING', 'false').lower() == 'true'
prefix = '/testing' if is_testing else ''

from auth.secrets import load_secrets
load_secrets()

from flask import Flask, render_template, request, url_for, redirect, session, current_app, make_response
from flask_sqlalchemy import SQLAlchemy
import dotenv
import base64
from flask_cors import cross_origin
import requests
from authlib.integrations.flask_client import OAuth
from auth.login import login_required
import time
from utils.stripe import clean_payment_methods, getSessionFromClientReferenceID
import traceback
from utils.errors import handleError, errorWrapper
from datetime import datetime
import json

#TODO: proposal numbers must be PXXXX
#Provide google link to drive folder. They fill it out.
#when they pay, goes to project folder.
#invoice -> project number -> may not be a proposal number.
#TODO: when they do nopayment, email via no-reply@a3e.com ONLY for invoices.
#TODO: unique press confirm button for invoices, if you already did, timestamp
#tim@a3e.com should be admin

from redis import Redis 

app = Flask(__name__)
app.config.from_object('config')
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_PERMANENT'] = True
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_KEY_PREFIX'] = f'session:{"test" if is_testing else "prod"}'

redis_host = 'redis'
redis_port = 6379

app.config['SESSION_REDIS'] = Redis.from_url(f'redis://{redis_host}:{redis_port}')
app.config['SESSION_COOKIE_NAME'] = 'a3e_login_cookie'
app.config['SESSION_COOKIE_SECURE'] = True  
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)  
Session(app)
from db import db
db.init_app(app)

@app.before_request
def before_request():
    if prefix and request.path.startswith(prefix):
        request.environ['PATH_INFO'] = request.path[len(prefix):]

def prefixed_url_for(endpoint, **values):
    url = url_for(endpoint, **values)
    if is_testing:
        #replace starting after .com/ with /testing
        url_split = url.split('.com/')
        if len(url_split) > 1:
            url = url_split[0] + '.com' + prefix + '/' +url_split[1]
        else:
            url = prefix + url

    return url

@app.context_processor
def inject_url_for():
    def prefixed_url_for_jinja(endpoint, **values):
        url = url_for(endpoint, **values)
        if is_testing:
            return prefix + url
        return url
    return dict(
        url_for=prefixed_url_for_jinja,
        is_testing = is_testing,
        is_local=os.environ.get('ENVIRONMENT','').lower() == 'local')

@app.errorhandler(Exception)
def handle_error(e):
    #if its a 404, return standard 404 page
    if '404' in str(e):
        return render_template('404.html'), 404
    if '405' in str(e):
        return render_template('404.html'), 405
    #create a string with current url, session data
    error_string = f"Error: {e}\nrequest: {safe_dump(request)}\nSession: {safe_dump(session)}\n"
    return handleError('An error occurred.', f"{traceback.format_exception(e)}\n {error_string}")

def safe_dump(object):
    try:
        return json.dumps(object, indent=4, default=lambda o: o.__dict__)
    except:
        try:
            return json.dumps(object, indent=4, default=str)
        except:
            return str(object)
        
#set secret key
app.secret_key = os.getenv('SECRET_KEY')

oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.environ.get('GOOGLE_CLIENT_ID'),  
    client_secret=os.environ.get('GOOGLE_CLIENT_SECRET'),  
    access_token_url='https://accounts.google.com/o/oauth2/token',
    access_token_params=None,
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    authorize_params=None,
    api_base_url='https://www.googleapis.com/oauth2/v1/',
    client_kwargs={
        'scope': 'openid email profile',
        'token_endpoint_auth_method': 'client_secret_post',
        'issuer': 'https://accounts.google.com',
        'access_type':'offline'
    },
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration'

)
import models
# Secure the admin endpoint
from flask_admin import Admin
from models import AdminIndexView, UserModelView, ButtonRequestModelView, ProductModelView
import  utils.stripe
admin = Admin(app, 
              name='app', 
              template_mode='bootstrap3', 
              index_view=AdminIndexView(name='Database', 
                                        menu_icon_type='glyph', 
                                        menu_icon_value='glyphicon-home',
                                        endpoint='db',
                                        url='/db/')
                                        )
admin.add_view(UserModelView(models.User, db.session))
admin.add_view(ButtonRequestModelView(models.ButtonRequest, db.session))
admin.add_view(ProductModelView(models.Product, db.session))


def image_to_base64(image_path):
    with open(image_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
    return encoded_string


@app.route('/')
@login_required
@cross_origin()
def index():
    from models import User
    user = session.get('user', None)
    user_model = User.find_by_email(user['email'],db)

    return render_template('index.html', user=user_model)

@app.route('/make_button')
@cross_origin()
@login_required
def make_button():
    from models import User
    encoded_image = image_to_base64('static/button.png')   
    html_snippet = f'<img src="data:image/jpeg;base64,{encoded_image}" alt="Embedded Image" width="350">'
    products = db.session.query(models.Product).order_by(models.Product.name.asc()).all()
    user = session.get('user', None)
    user_model = User.find_by_email(user['email'],db)
    return render_template('make_button.html',
                           html_snippet = html_snippet, 
                           encoded_image = encoded_image,
                           user = user_model,
                           backend_url = prefixed_url_for('get_button_url'),
                           product_options = [p.name for p in products],
                           )


@app.route('/get_button_url', methods=['POST'])
@cross_origin()
def get_button_url():
    from models import User, ButtonRequest
    from utils.email import sendEmail
    from utils.foldermaker.foldermaker import make_proposal_folder
    try:
        data = request.get_json()
        print(data, flush=True)
        with app.app_context():
            #verify that ALL fields are non-null
            if not all([data.get('productName'), data.get('price'), data.get('paymentMethod'), data.get('proposalNumber')]):
                return {'error': 'All fields are required.'}, 400
            #make sure that the price is a number
            try:
                data['price'] = float(data['price'])
            except:
                return {'error': 'Price must be a number.'}, 400
            proposal_folder_url = None
            upload_folder_url = None
            if data.get('with_folders',False):
                address = data.get('address')
                if not address:
                    return {'error': 'Address is required if making folders.'}, 400
                
                proposal_folder_url, upload_folder_url = make_proposal_folder(data['proposalNumber'], address)
                

            #make sure that the proposal number is not a duplicate on any existing button request
            existing_br = db.session.query(ButtonRequest).filter_by(proposal_number = data['proposalNumber']).first()
            if existing_br:
                if data.get('force_create', False):
                    print('force create', flush=True)
                else:
                    return {'error': 'Duplicate Proposal Number'}, 400
            
            button_request = ButtonRequest(
                created_by = session.get('user', {}).get('email', 'unknown'),
                product_name = data['productName'],
                price = data['price'],
                payment_methods = clean_payment_methods(data['paymentMethod']),
                proposal_number = data['proposalNumber'],
                folder_url = proposal_folder_url,
                upload_only_url = upload_folder_url
            )
            db.session.add(button_request)
            db.session.commit()
            button_request_id = button_request.id

            button_request.build()
            db.session.commit()

        url = '/start_my_project/' + str(button_request_id)
        sendEmail(
            recipient_email=session.get('user', {}).get('email', {}) or '',
            subject=f"Proposal Number: {data['proposalNumber']}",
            body=f'''
            Proposal Number: {data['proposalNumber']}
            Price: ${data['price']/100:.2f}
            Payment Methods: {data['paymentMethod']}
            Checkout URL: http://start.a3e.com/{url}
            Proposal Folder URL: {proposal_folder_url or 'Not created'}
            Upload Folder URL: {upload_folder_url or 'Not created'}
            Created By: {session.get('user', {}).get('email', 'unknown')}
            Created At: {datetime.now()}
            '''
        )

    except Exception as e:
        print(traceback.format_exception(e), flush=True)
        return {'error': f'An error occurred. Please try again.\n{e}'}, 500
    return {
        'url':url,
        'proposal_folder_url':proposal_folder_url,
        'upload_folder_url':upload_folder_url
        }


@app.route('/start_my_project/<request_id>')
@cross_origin()
def start_my_project(request_id):
    from models import User, ButtonRequest
    user = session.get('user', None)
    user_model = None
    user_model_id = None
    if user:
        user_model = models.User.find_by_email(user['email'],db)
        if user_model:
            user_model_id = user_model.id
    with app.app_context():
        button_request = db.session.query(ButtonRequest).filter_by(id=request_id).first()
        
        if user_model:
            button_request.user_id = user_model_id
            db.session.commit()
        else:
            #NOTE: at some point, we should make them login here!
            pass
        page = button_request.getPage(db)
        return page



@app.route('/confirm/', methods=['POST'])
@cross_origin()
def confirm(noPayment=False, button_request_id = None):
    print('confirm recieved', flush=True)
    #TODO: mark that they clicked this in the DB!
    from utils.email import sendEmail, sendInternalNotificationEmail
    data = None
    if request.args['noPayment']:
        noPayment = True
    if request.args['button_request_id']:
        button_request_id = request.args['button_request_id']
    data = {}
    data['email'] = request.form['email']
    data['phone'] = request.form['phone']
    data['first_name'] = request.form['name']
    data['last_name'] = request.form['last_name']
    with app.app_context():
        user = session.get('user', None)
        user_model = models.User.find_by_email(user['email'],db)
        if user_model:
            br = user_model.button_requests[-1]
        else:
            if not button_request_id:
                return handleError('No button request found.')
            br = db.session.query(models.ButtonRequest).filter_by(id=button_request_id).first()
            if not br:
                return handleError('No button request found.')
        if noPayment:
            print('noPayment', flush=True)
            if br.email_sent_timestamp:
                print('email previously sent!', flush=True)
                return render_template('confirm.html', user = user_model, previously_sent = True)
            br.email_sent_timestamp = datetime.now()
            db.session.commit()
            try:
                #create user
                if not user_model:
                    if br.user_id:
                        #this means an error has occurred. email tim.
                        raise Exception("there already is a user_id on this invoice, but no user object!")
                    else:
                        user_model = models.User.find_by_email(data['email'],db)
                        if not user_model:
                            user_model = models.User(
                                first_name = data['first_name'],
                                last_name = data['last_name'],
                                email = data['email'],
                                is_verified = True,
                                transaction_history = [br.id]
                            )
                            db.session.add(user_model)
                            db.session.commit()
                        br.user_id = user_model.id
                        db.session.commit()
                    print(f"found user model: {user_model.email}", flush=True)
                    #if email is new, add to alias list.
                    if data['email'] != user_model.email:
                        user_model.known_alias_emails.append(data['email'])
                        db.session.commit()
                    #for other fields, update them if empty.
                    for k,v in data.items():
                        if not getattr(user_model,k):
                            setattr(user_model,k,v)
                    #add this transaction to the transaction list.
                    user_model.transaction_history = user_model.transaction_history.append(f"product: {br.product_name}, price: {br.price}, proposal_number: {br.proposal_number}, type: Invoice")
                    db.session.commit()

            except Exception as e:
                print(f"An error occurred in creating user from noPayment invoice: {e}", flush=True)
                handleError(
                          'Error in creating user from noPayment invoice',
                    f'Nothing bad can happen from this, but it is worth noting. Error: {traceback.format_exception(e)}')
            try:
                print('sending email', flush=True)
                sendInternalNotificationEmail(
                    f"New Project Started! {data['email']}: {br.product_name}: {br.proposal_number}", 
                    f"""
                    Email: {data['email']}
                    First Name: {data['first_name']}
                    Last Name: {data['last_name']}
                    Proposal Number: {br.proposal_number}
                    Price: ${br.price/100:.2f}
                    """,
                    db)
            except Exception as e:
                try:
                    handleError('New Invoice Project Started!, but an error occured in the notification email!',f"{traceback.format_exception(e)}")
                except:
                    print(f"Failed to send backup email: {e}", flush=True)
        return render_template('confirm.html', user = user_model)


@app.route('/stripe_callback/<session_id>')
@cross_origin()
def stripe_callback(session_id):
    from models import User, ButtonRequest
    with app.app_context():
        stripe_session = getSessionFromClientReferenceID(session_id)
        if not stripe_session:
            return handleError('No stripe session found.')
        print(stripe_session, flush = True)
        user = session.get('user', None)
        if user:
            dbuser = User.create_or_update_from_stripe_session(stripe_session, user['email'])
        else:
            dbuser = None
        button_request = db.session.query(ButtonRequest).filter_by(id=session_id).first()
        if not button_request:
            return handleError('No button request found.')
        button_request.handle_stripe_session(stripe_session, dbuser)
        db.session.commit()
    if stripe_session.status == 'complete':
        return redirect(prefixed_url_for('confirm', button_request_id = button_request.id))
    return redirect(prefixed_url_for('payment_failed'))


@app.route('/payment_failed')
@cross_origin()
def payment_failed():
    from models import User
    user = session.get('user', None)
    user_model = User.find_by_email(user['email'],db)
    return render_template('payment_failed.html', user = user_model)



@app.route('/logout', methods=['POST'])
@cross_origin()
@login_required
def logout():
    session.clear()
    return redirect(prefixed_url_for('login'))


@app.route('/login')
@cross_origin()
def login():
    if os.environ.get('ENVIRONMENT','').lower() == 'local':
        session['user'] = {'email': ""}
        session.modified=True
        current_app.session_interface.save_session(current_app, session, make_response())
        return redirect(prefixed_url_for('index'))
    #try to get the user from the session
    from auth.login import refresh_access_token
    if refresh_access_token():
        return redirect(prefixed_url_for('index'))

    redirect_uri = prefixed_url_for('authorize', _external=True).replace('http://', 'https://')
    return google.authorize_redirect(redirect_uri, prompt='consent')


@app.route('/login/callback')
def authorize():
    #check for an error
    if 'error' in request.args:
        return f"Error: {request.args.get('error')}"
    

    # Exchange code for token
    token_response = requests.post(
        'https://oauth2.googleapis.com/token',
        data={
            'code': request.args.get('code'),
            'client_id': os.environ.get('GOOGLE_CLIENT_ID'),
            'client_secret': os.environ.get('GOOGLE_CLIENT_SECRET'),
            'redirect_uri': prefixed_url_for('authorize', _external=True).replace('http://', 'https://'),
            'grant_type': 'authorization_code'
        }
    )

    token_data = token_response.json()
    # Handle errors in token response
    if token_response.status_code != 200:
        return f"Failed to fetch token: {token_data.get('error_description', token_data.get('error', 'Unknown error'))}", 400

    # Use the access token to fetch user information or other tasks
    access_token = token_data['access_token']
    id_token = token_data['id_token']
    refresh_token = token_data.get('refresh_token', '')
    userinfo_response = requests.get(
        'https://www.googleapis.com/oauth2/v2/userinfo',
        headers={'Authorization': f'Bearer {access_token}'}
    )
    user_info = userinfo_response.json()
    
    #if the email isn't like '@a3e.com' or exactly '''', reject them.
    if not user_info['email'].endswith('@a3e.com') and user_info['email'] != '':
        #remove them from the oauth in google via a post
        requests.post(
            'https://accounts.google.com/o/oauth2/revoke',
            params={'token': access_token},
            headers = {'content-type': 'application/x-www-form-urlencoded'}
        )
        return redirect(prefixed_url_for('no_access'))
    
    session['user'] = user_info
    session['access_token'] = access_token
    session['id_token'] = id_token
    session['token_expires_at'] = time.time() + token_data['expires_in']

    session.permanent = True
    from models import User
    #save the user to db
    User.create_or_update_from_google_user(user_info,refresh_token)
    #get secrets from google secret manager (to allow updates without restarting the server)
    load_secrets()
    return redirect(prefixed_url_for('index'))

@app.route('/admin')
@cross_origin()
@login_required
def admin_page():
    from models import User, Product
    #check if the user is an admin
    user = User.find_by_email(session['user']['email'],db)
    if not user.is_admin:
        return redirect(prefixed_url_for('no_access'))
    products = db.session.query(Product).order_by(Product.name.asc()).all()
    return render_template('admin.html', user = user, products = products)


@app.route('/no_access')
@cross_origin()
def no_access():
    return render_template('no_access.html')


@app.route('/folder/create', methods=['POST'])
def createFolder():
    from models import Product
    data = request.get_json()
    print(data, flush=True)
    with app.app_context():
        product = db.session.query(Product).filter_by(name=data['product_name']).first()
        print(f"found product? {product}", flush=True)
        if data['folder_name'] in product.folders:
            return {'error': 'Folder already exists'}
        product.folders = product.folders + [data['folder_name']]
        db.session.commit()
    return {'message': 'Success'}


@app.route('/folder/delete', methods=['POST'])
def deleteFolder():
    from models import Product
    data = request.get_json()
    with app.app_context():
        product = db.session.query(Product).filter_by(name=data['product_name']).first()
        product.folders = [f for f in product.folders if f != data['folder_name']]
        db.session.commit()
    return {'message': 'Success'}


@app.route('/product/add', methods=['POST'])
def addProduct():
    from models import Product
    data = request.get_json()
    print(data, flush=True)
    with app.app_context():
        product = Product(
            name = data['product_name']
        )
        db.session.add(product)
        db.session.commit()
    return {'message': 'Success'}


@app.route('/product/delete', methods=['POST'])
def deleteProduct():
    from models import Product
    data = request.get_json()
    with app.app_context():
        product = db.session.query(Product).filter_by(name=data['product_name']).first()
        db.session.delete(product)
        db.session.commit()
    return {'message': 'Success'}


@app.route('/make_folders', methods=['POST'])
def make_folders():
    data = request.get_json()
    from utils.foldermaker.foldermaker import make_project_folder, AlreadyExistsException
    from utils.email import sendEmail
    response = make_response()
    try:
        url = make_project_folder(data['project_num'], data['prod_type'], data['address'], db)
    except Exception as e:
        if isinstance(e, AlreadyExistsException):
            response.status_code = 500
            response.data = json.dumps({"error":f"Folder already exists.","url":e.url})
            return response
        response.status_code = 500
        response.data = json.dumps({"error":f"An error occurred: {e}"})
        handleError('An error occurred while making folders.', f"{traceback.format_exception(e)}")
        return response

    #send an email to the logged-in user
    email = session.get('user',{}).get('email',None) or ''
    if not email:
        handleError('No email found in session while making folders.', f'session details: {session}')
    else:
        sendEmail(
            recipient_email=email,
            subject=f"{data['project_num']} - {data['address'].replace(', USA','')}",
            body=f'''Project {data["project_num"]} has been created. This link is to the project folder: 
            {url}''',
        )
    response.data = json.dumps({"url":url})
    response.status_code = 200
    return response


@app.route('/terms')
@cross_origin()
def terms():
    return render_template('terms.html')


@app.route('/new_project')
@cross_origin()
@login_required
def new_project():
    from models import User
    user = User.find_by_email(session['user']['email'],db)
    with app.app_context():
        products = db.session.query(models.Product).order_by(models.Product.name.asc()).all()
        return render_template('create_project.html', products=products, user=user)


'''with app.app_context():
    from models.user import User
    from models.request import ButtonRequest
    print(db.metadata.tables.values())
    db.create_all()
'''

@app.route('/logo.jpg')
def logo():
    return app.send_static_file('logo.jpg')

# Run the app
if __name__ == '__main__':
    from utils import initialize
    '''
    initialize.reset_db(app, db)
    initialize.createDefaultObjects(app, db)'''
    if os.environ.get('ENVIRONMENT','').lower() == 'local':
        app.run(debug=True, host='0.0.0.0', port=5000 if os.getenv('PORT') is None else os.getenv('PORT'))
    if is_testing:
        app.run(debug=False, host='0.0.0.0', port=5000 if os.getenv('PORT') is None else os.getenv('PORT'))
    else:
        app.run(debug=False, host='0.0.0.0', port=5000 if os.getenv('PORT') is None else os.getenv('PORT'))

