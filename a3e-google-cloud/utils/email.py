import os
import sendgrid
from sendgrid.helpers.mail import Mail, Email, To, Content, TrackingSettings, ClickTracking
from models import User

sg = sendgrid.SendGridAPIClient(os.environ.get('SENDGRID_API_KEY',''))

def sendEmail(recipient_email, subject, body, track=False):
    from_email = Email("No-Reply@a3e.com")
    #send emails only to x when local
    if os.environ.get('ENVIRONMENT','').lower()=='local':
        recipient_email = "REDACTED"
        subject = "LOCAL TESTING: " + subject
    #send emails only to x and y when testing
    elif os.environ.get('TESTING', 'false').lower() == 'true':
        recipient_email = "REDACTED"
        to_email= To(recipient_email)
        subject = "TESTING: " + subject
        content = Content("text/plain", body)
        message = Mail(from_email, to_email ,subject, content)
        if not track:
            tracking_settings = TrackingSettings(
            click_tracking=ClickTracking(enable=False, enable_text=False)
            )
            message.tracking_settings = tracking_settings
        mail_json = message.get()
        response = sg.client.mail.send.post(request_body=mail_json)
        print(f"response from sendgrid: {response.status_code}\n {response.body}")
        recipient_email= "REDACTED"
    to_email= To(recipient_email)
    content = Content("text/plain", body)
    message = Mail(from_email, to_email ,subject, content)
    if not track:
        tracking_settings = TrackingSettings(
        click_tracking=ClickTracking(enable=False, enable_text=False)
        )
        message.tracking_settings = tracking_settings
    mail_json = message.get()
    response = sg.client.mail.send.post(request_body=mail_json)
    print(f"response from sendgrid: {response.status_code}\n {response.body}")


def sendErrorEmail(error, details):
    print("Sending error email.")
    sendEmail('READACTED', error, details)
    sendEmail('REDACTED', error, details)


def sendInternalNotificationEmail(subject, body, db):
    print("sending internal notification email.")
    if os.environ.get('ENVIRONMENT','').lower()=='local' or os.environ.get('TESTING', 'false').lower() == 'true':
        recipient_email = "REDACTED"
        sendEmail(recipient_email, "INTERNAL NOTIFICATION:" + subject, body)
        return
    Users = db.session.query(User).filter(User.send_admin_notifications == True).all()
    for user in Users:
        print(f"Sending email to {user.email}")
        sendEmail(user.email, subject, body)

if __name__ == "__main__":
    recipient_email = "REDACTED"
    subject = "Test Email"
    body = "This is a test email from Python."
    sendEmail(recipient_email, subject, body)
    