from flask import jsonify, request, current_app
from . import api_v1_bp
from extensions import db, bcrypt, jwt
from models import User
from api.serializers import APISerializer
from flask_jwt_extended import (
    create_access_token, create_refresh_token, jwt_required,
    get_jwt_identity, get_jwt
)
import datetime
import redis

# Local memory blocklist fallback
LOCAL_BLOCKLIST = set()

@jwt.token_in_blocklist_loader
def check_if_token_in_blocklist(jwt_header, jwt_payload):
    jti = jwt_payload["jti"]
    redis_url = current_app.config.get('REDIS_URL')
    if redis_url:
        try:
            r = redis.from_url(redis_url)
            return r.get(jti) is not None
        except Exception as e:
            current_app.logger.error(f"Redis blocklist connection error: {e}")
    return jti in LOCAL_BLOCKLIST

def revoke_token(jti, expires_in_seconds=3600):
    """Revokes a token by adding its JTI to Redis or fallback local set."""
    redis_url = current_app.config.get('REDIS_URL')
    if redis_url:
        try:
            r = redis.from_url(redis_url)
            r.setex(jti, expires_in_seconds, "revoked")
            return True
        except Exception as e:
            current_app.logger.error(f"Redis revoke token failed: {e}")
    LOCAL_BLOCKLIST.add(jti)
    return True

@api_v1_bp.route('/auth/register', methods=['POST'])
def register():
    """
    User Registration API
    ---
    tags:
      - Authentication
    parameters:
      - in: body
        name: body
        required: True
        schema:
          type: object
          required:
            - username
            - email
            - password
          properties:
            username:
              type: string
              example: testuser
            email:
              type: string
              example: user@example.com
            password:
              type: string
              example: SecurePass123
    responses:
      201:
        description: User registered successfully
      400:
        description: Invalid fields or duplicate credentials
    """
    data = request.get_json()
    if not data or not data.get('username') or not data.get('email') or not data.get('password'):
        return jsonify({
            "success": False,
            "error": "BAD_REQUEST",
            "message": "Missing required fields: username, email, password."
        }), 400

    username = data['username'].strip()
    email = data['email'].strip().lower()
    password = data['password']

    if len(username) < 3 or len(password) < 6:
        return jsonify({
            "success": False,
            "error": "VALIDATION_ERROR",
            "message": "Username must be at least 3 chars and password at least 6 chars."
        }), 400

    if User.query.filter_by(email=email).first():
        return jsonify({
            "success": False,
            "error": "CONFLICT",
            "message": "Email is already registered."
        }), 400

    if User.query.filter_by(username=username).first():
        return jsonify({
            "success": False,
            "error": "CONFLICT",
            "message": "Username is already taken."
        }), 400

    hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
    user = User(username=username, email=email, password=hashed_pw, is_verified=False)
    db.session.add(user)
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "User registered successfully.",
        "data": APISerializer.user_basic(user)
    }), 201

@api_v1_bp.route('/auth/login', methods=['POST'])
def login():
    """
    User Login API
    ---
    tags:
      - Authentication
    parameters:
      - in: body
        name: body
        required: True
        schema:
          type: object
          required:
            - email
            - password
          properties:
            email:
              type: string
              example: user@example.com
            password:
              type: string
              example: SecurePass123
    responses:
      200:
        description: Successful login, returns tokens
      401:
        description: Invalid credentials
    """
    data = request.get_json()
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({
            "success": False,
            "error": "BAD_REQUEST",
            "message": "Missing email or password."
        }), 400

    email = data['email'].strip().lower()
    password = data['password']

    user = User.query.filter_by(email=email).first()
    if not user or not bcrypt.check_password_hash(user.password, password):
        return jsonify({
            "success": False,
            "error": "UNAUTHORIZED",
            "message": "Bad email or password."
        }), 401

    if user.is_banned:
        return jsonify({
            "success": False,
            "error": "FORBIDDEN",
            "message": "Your account has been banned."
        }), 403

    # Generate JWT tokens
    access_token = create_access_token(identity=user.id, expires_delta=datetime.timedelta(minutes=15))
    refresh_token = create_refresh_token(identity=user.id, expires_delta=datetime.timedelta(days=30))

    user.last_login = datetime.datetime.utcnow()
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Logged in successfully.",
        "data": {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": APISerializer.user_basic(user)
        }
    }), 200

@api_v1_bp.route('/auth/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """
    Refresh Token API
    ---
    tags:
      - Authentication
    security:
      - ApiKeyAuth: []
    responses:
      200:
        description: Returns a new access token
    """
    current_user_id = get_jwt_identity()
    new_access_token = create_access_token(identity=current_user_id, expires_delta=datetime.timedelta(minutes=15))
    return jsonify({
        "success": True,
        "message": "Token refreshed successfully.",
        "data": {
            "access_token": new_access_token
        }
    }), 200

@api_v1_bp.route('/auth/profile', methods=['GET'])
@jwt_required()
def profile():
    """
    Get Current User Profile
    ---
    tags:
      - Authentication
    security:
      - ApiKeyAuth: []
    responses:
      200:
        description: Returns current user profile details
      404:
        description: User not found
    """
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if not user:
        return jsonify({
            "success": False,
            "error": "NOT_FOUND",
            "message": "User session not found."
        }), 404

    return jsonify({
        "success": True,
        "message": "Profile retrieved successfully.",
        "data": APISerializer.user_profile(user, current_user=user)
    }), 200

@api_v1_bp.route('/auth/logout', methods=['POST'])
@jwt_required()
def logout():
    """
    Revoke current active token (Logout)
    ---
    tags:
      - Authentication
    security:
      - ApiKeyAuth: []
    responses:
      200:
        description: Logged out successfully
    """
    jti = get_jwt()["jti"]
    revoke_token(jti)
    return jsonify({
        "success": True,
        "message": "Successfully logged out and token revoked."
    }), 200
