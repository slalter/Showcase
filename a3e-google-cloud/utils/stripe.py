import stripe
import uuid
import os
from flask import session
from utils.email import sendErrorEmail
if not os.environ.get('ENVIRONMENT','').lower()=='local' or os.environ.get('TESTING', 'false').lower() == 'true':
    stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
else:   
    stripe.api_key = os.environ.get('STRIPE_SECRET_KEY_TESTING')
if not stripe.api_key:
    raise Exception('Stripe API key not found in environment variables upon load')


def createSession(price, payment_methods, product_name, session_id):
    from app import prefixed_url_for
    print(f"Creating session for {product_name} at {price} with payment methods {payment_methods}", flush=True)
    session_id = str(session_id)
    session = stripe.checkout.Session.create(
        client_reference_id=session_id,
        payment_method_types=payment_methods,
        line_items=[{
            'price_data': {
                'currency': 'usd',
                'product_data': {
                    'name': f'{product_name}',
                    'images': ['']
                },
                'unit_amount_decimal': price,
            },
            'quantity': 1,
            
        }],
        mode='payment',
        success_url= prefixed_url_for('stripe_callback', _external=True,session_id=session_id),
        cancel_url=prefixed_url_for('payment_failed', _external=True, session_id=session_id),
        billing_address_collection='required',
        phone_number_collection=stripe.checkout.Session.CreateParamsPhoneNumberCollection(enabled=True),
        consent_collection=stripe.checkout.Session.CreateParamsConsentCollection(terms_of_service='required'),
        
    )
    return session

def verifySession(session_id):
    from models import ButtonRequest, User
    from app import db
    stripe_session = getSessionFromClientReferenceID(session_id)
    button_request = db.session.get(ButtonRequest,session_id)
    assert(isinstance(button_request, ButtonRequest))
    user = button_request.user
    if not user:
        user = User.find_by_email(session.get('user',{'email':'unknown'})['email'],db)
    if not stripe_session:
        button_request.remake_session()
        return
    if stripe_session.status == 'open':
        return 
    if stripe_session.status == 'complete':
        button_request.handle_stripe_session(stripe_session, user)
    if stripe_session.status == 'expired':
        if button_request.status == 'started':
            button_request.status = 'pending'
            return
        if button_request.status == 'pending':
            return
        raise Exception(f"An error has occurred! Please contact customer support.")
    
    return

def getSessionURL(price, payment_methods, product_name, session_id):
    session = createSession(price, payment_methods, product_name, session_id)

    return session.url


def getSessionFromClientReferenceID(client_reference_id):

    sessions = stripe.checkout.Session.list()
    sessions = [session for session in sessions if session.client_reference_id == client_reference_id]
    if len(sessions) == 0:
        return None
    return sessions[0]

def issueRefund(session, reason):
    refund = stripe.Refund.create(
        payment_intent=session.payment_intent,
        amount=session.amount_total,
        reason=reason
    )
    return refund

def clean_payment_methods(payment_methods):
    if payment_methods == 'noPayment':
        return ['noPayment']
    elif payment_methods == 'ACH':
        return ['us_bank_account']
    elif payment_methods == 'CC_ACH':
        return ['card', 'us_bank_account']