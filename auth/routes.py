from flask import render_template, url_for, flash, redirect, request, current_app
from flask_login import login_user, current_user, logout_user, login_required
from extensions import db, bcrypt, oauth, limiter
from models import User
from forms import RegistrationForm, LoginForm, UpdateProfileForm
from utils.email import generate_token, verify_token, send_email
from . import auth_bp
import os

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(username=form.username.data, email=form.email.data, password=hashed_password, is_verified=False)
        db.session.add(user)
        db.session.commit()
        
        # Send Verification Email
        token = generate_token(user.email, salt='email-verify')
        verify_url = url_for('auth.verify_email', token=token, _external=True)
        send_email(user.email, "Verify Your Account - TechInsights", "email/verify.html", verify_url=verify_url)
        
        flash('Account created! Please check your email to verify your account before logging in.', 'info')
        return redirect(url_for('auth.login'))
    return render_template('register.html', title='Register', form=form)

@auth_bp.route('/verify/<token>')
def verify_email(token):
    email = verify_token(token, salt='email-verify', expiration=86400) # 24 hours
    if not email:
        flash('The verification link is invalid or has expired.', 'danger')
        return redirect(url_for('auth.login'))
    
    user = User.query.filter_by(email=email).first()
    if user:
        if user.is_verified:
            flash('Account already verified. Please login.', 'info')
        else:
            user.is_verified = True
            db.session.commit()
            flash('Your account has been verified! You can now login.', 'success')
    return redirect(url_for('auth.login'))

@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            if not user.is_verified:
                flash('Please verify your email before logging in.', 'warning')
                return redirect(url_for('auth.login'))
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            import datetime
            user.last_login = datetime.datetime.utcnow()
            db.session.commit()
            return redirect(next_page) if next_page else redirect(url_for('home'))
        else:
            flash('Login Unsuccessful. Please check email and password', 'danger')
    return render_template('login.html', title='Login', form=form)

@auth_bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('home'))

@auth_bp.route('/login/google')
def google_login():
    redirect_uri = url_for('auth.google_authorized', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)

@auth_bp.route('/login/google/authorized')
def google_authorized():
    token = oauth.google.authorize_access_token()
    resp = oauth.google.get("https://www.googleapis.com/oauth2/v3/userinfo")
    user_info = resp.json()
    email = user_info.get('email')
    
    user = User.query.filter_by(email=email).first()
    if not user:
        # Create new user via Google
        import secrets
        random_pw = secrets.token_hex(16)
        hashed_pw = bcrypt.generate_password_hash(random_pw).decode('utf-8')
        user = User(
            username=user_info.get('name', '').replace(" ", "")[:20] + secrets.token_hex(2),
            email=email,
            password=hashed_pw,
            is_verified=True, # Trusted email
            google_id=user_info.get('id', user_info.get('sub'))
        )
        db.session.add(user)
        db.session.commit()
        
    import datetime
    user.last_login = datetime.datetime.utcnow()
    db.session.commit()
    login_user(user)
    return redirect(url_for('home'))

@auth_bp.route('/reset_password_request', methods=['GET', 'POST'])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    # Assume a form RequestResetForm is defined
    from forms import RequestResetForm
    form = RequestResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            token = generate_token(user.email, salt='password-reset')
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            send_email(user.email, "Reset Your Password - TechInsights", "email/reset_password.html", reset_url=reset_url)
        flash('If an account with that email exists, a reset link has been sent.', 'info')
        return redirect(url_for('auth.login'))
    return render_template('reset_request.html', title='Reset Password', form=form)

@auth_bp.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    email = verify_token(token, salt='password-reset', expiration=1800) # 30 mins
    if not email:
        flash('The reset link is invalid or has expired.', 'danger')
        return redirect(url_for('auth.reset_password_request'))
    
    from forms import ResetPasswordForm
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=email).first()
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user.password = hashed_password
        db.session.commit()
        flash('Your password has been updated! You are now able to log in', 'success')
        return redirect(url_for('auth.login'))
    return render_template('reset_password.html', title='Reset Password', form=form)
