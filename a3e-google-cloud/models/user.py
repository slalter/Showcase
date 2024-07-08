from db import db
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy import cast
import uuid
import stripe
import time
from auth.login import verify_google_token
import os

class User(db.Model):
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)
    first_name = db.Column(db.String(255), nullable=False)
    last_name = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    email = db.Column(db.String(255), nullable=False, unique=True)
    known_alias_emails = db.Column(JSONB, nullable=False, default=[])
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    is_verified = db.Column(db.Boolean, nullable=False, default=False)
    created_from = db.Column(db.String(255), nullable=False, default='')
    transaction_history = db.Column(db.JSON(), nullable=False, default=[])
    send_admin_notifications = db.Column(db.Boolean, default=False)
    refresh_token = db.Column(db.String(255), nullable=True)
    refresh_token_expires_at = db.Column(db.Float, nullable=True)
    
    #relationship to button requests
    button_requests = db.relationship('ButtonRequest', backref='user', lazy=True)

    @classmethod
    def find_by_email(cls, email, db) -> 'User':
        result = db.session.query(cls).filter(cls.email == email.lower()).first()
        if result:
            return result
        alias_result = db.session.query(cls).filter(
            cls.known_alias_emails.contains([email])  # Correct usage of the contains method
        ).first()
        if alias_result:
            return alias_result
        return None
        
    @classmethod
    def find_by_id(cls, id):
        from app import app, db
        with app.app_context():
            return db.session.query(cls).filter(cls.id == id).first()
    
    @classmethod
    def create_or_update_from_google_user(cls, google_user, refresh_token, known_email = ''):
        google_user['email'] = google_user['email'].lower()
        known_email = known_email.lower()
        print(google_user, flush = True)
        from app import app, db
        with app.app_context():
            #check if we already have a user with this email
            if known_email:
                user = cls.find_by_email(known_email, db)
            else:
                user = cls.find_by_email(google_user['email'], db)
            if user:
                #update the user
                if user.email and user.email != google_user['email']:
                    user.known_alias_emails.append(google_user['email'])
                if not user.first_name:
                    user.first_name = google_user['given_name']
                if not user.last_name:
                    user.last_name = google_user['family_name']
                user.is_verified = True
                db.session.commit()
            else:
                user = cls(
                    first_name = google_user['given_name'],
                    last_name = google_user['family_name'], 
                    email = google_user['email'],
                    is_verified=True,
                    created_from = 'google'
                    )
                db.session.add(user)
                db.session.commit()
            user.refresh_token = refresh_token

            #set to expire in 7 days
            user.refresh_token_expires_at = time.time() + 604800
            db.session.commit()
            return user

    @classmethod
    def create_or_update_from_stripe_session(cls, stripe_session:stripe.checkout.Session, known_email = ''):
        from app import app, db
        with app.app_context():
            stripe_email = stripe_session.customer_details.email.lower() if stripe_session.customer_details.email else ''
            stripe_first_name = stripe_session.customer_details.name.split(' ')[0] if len(stripe_session.customer_details.name.split(' ')) > 0 else ''
            stripe_last_name = stripe_session.customer_details.name.split(' ')[-1] if len(stripe_session.customer_details.name.split(' ')) > 1 else ''
            if known_email:
                user = cls.find_by_email(known_email, db)
            else:
                user = cls.find_by_email(stripe_session.customer_details.email, db)
            if user:
                
                if not user.first_name:
                    user.first_name = stripe_first_name
                if not user.last_name:
                    user.last_name = stripe_last_name
                if user.email and user.email != stripe_email and stripe_email not in user.known_alias_emails:
                    user.known_alias_emails.append(stripe_email)
                if not user.email:
                    user.email = stripe_email
                
                db.session.commit()
                return user
            
            user = cls(
                first_name = stripe_first_name,
                last_name = stripe_last_name,
                email = stripe_email,
                is_verified = True,
                created_from = 'stripe'
            )
            db.session.add(user)
            db.session.commit()
            return user
        
    def verify_token(self, token):
        if os.environ.get('ENVIRONMENT','').lower()=='local':
            return True
        response=verify_google_token(token)
        if response and response.get('email',None) == self.email:
            return True
        else:
            if response and response.get('email',None) in self.known_alias_emails:
                return True
        print(f"Token verification failed for {self.email}. response was {response}", flush = True)
        return False


    