from db import db
from sqlalchemy.dialects.postgresql import UUID
import uuid
from utils import stripe
from flask import render_template, session

class ButtonRequest(db.Model):
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    created_by = db.Column(db.String(255), nullable=False, default = 'unknown')
    product_name = db.Column(db.String(255), nullable=False, default = 'unknown')
    price = db.Column(db.Float, nullable=False, default = 0.0)
    payment_methods = db.Column(db.JSON(), nullable=False, default = [])
    stripe_session_url = db.Column(db.String(510), nullable=False, default = '')
    target_template = db.Column(db.String(255), nullable=False, default = '')
    proposal_number = db.Column(db.String(255), nullable=False, default = '')
    status = db.Column(db.String(255), nullable=True, default = 'pending')
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('user.id'), nullable=True)
    email_sent_timestamp = db.Column(db.DateTime, nullable=True)
    folder_name = db.Column(db.String(255), nullable=True)
    folder_url = db.Column(db.String(255), nullable=True)
    upload_only_url = db.Column(db.String(255), nullable=True)

    def build(self):
        if 'noPayment' in self.payment_methods:
            self.target_template = 'no_payment.html'
            return
        self.target_template = 'stripe_redirect.html'

    def getPage(self,db):
        from models import User
        if self.target_template == 'no_payment.html':
            if self.user_id:
                user_model = db.session.get(User,self.user_id)
            else:
                user_model = None
            return render_template(self.target_template, user = user_model, button_request = self)
        from utils import stripe
        if self.stripe_session_url:
            stripe.verifySession(self.id)
            db.session.commit()
            if self.status == 'started':
                return render_template(self.target_template, 
                                        stripe_session_url = self.stripe_session_url, 
                                        user = session.get('user', None))
        if self.status == 'pending':
            self.stripe_session_url = stripe.getSessionURL(self.price, self.payment_methods, self.product_name, self.id)
            self.status = 'started'
            db.session.commit()
            return render_template(self.target_template, 
                                    stripe_session_url = self.stripe_session_url, 
                                    user = session.get('user', None))
        
        if self.status == 'complete':
            return render_template('session_complete.html', user = session.get('user', None))
        
        raise Exception("An error has occurred! Try the button again. If that doesn't work, contact customer support.")
        
    def handle_stripe_session(self, stripe_session, user):
        if not self.user and user:
            self.user = user
            db.session.commit()
        if stripe_session.status == 'complete':
            self.status = 'complete'
            db.session.commit()
        else:
            self.status = 'pending'
        if self.user:
            history = self.user.transaction_history
            if isinstance(history, dict):
                self.user.transaction_history = [self.user.transaction_history]
            self.user.transaction_history.append(stripe_session.client_reference_id)
            db.session.commit()
        return
    
    def remake_session(self):
        self.stripe_session_url = stripe.getSessionURL(self.price, self.payment_methods, self.product_name, self.id)
        self.status = 'started'
        db.session.commit()
        return
