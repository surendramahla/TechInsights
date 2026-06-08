from itsdangerous import URLSafeTimedSerializer
from flask_mail import Message
from flask import current_app, render_template
from extensions import mail

def generate_token(email, salt):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps(email, salt=salt)

def verify_token(token, salt, expiration=3600):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email = serializer.loads(token, salt=salt, max_age=expiration)
        return email
    except:
        return False

def send_email(to, subject, template, **kwargs):
    msg = Message(subject, sender=current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@techinsights.com'), recipients=[to])
    msg.html = render_template(template, **kwargs)
    mail.send(msg)
