from flask import jsonify, request
from . import api_bp
from extensions import db, bcrypt
from models import User
from flask_jwt_extended import (
    create_access_token, create_refresh_token, jwt_required,
    get_jwt_identity, get_jwt
)
import datetime

# Import unified local blocklist fallback from v1 auth to prevent registration conflicts
from api.v1.auth import LOCAL_BLOCKLIST as BLOCKLIST

@api_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data or not data.get('username') or not data.get('email') or not data.get('password'):
        return jsonify({"msg": "Missing required fields"}), 400
        
    if User.query.filter_by(email=data['email']).first():
        return jsonify({"msg": "Email already exists"}), 400
        
    if User.query.filter_by(username=data['username']).first():
        return jsonify({"msg": "Username already exists"}), 400
        
    hashed_password = bcrypt.generate_password_hash(data['password']).decode('utf-8')
    user = User(username=data['username'], email=data['email'], password=hashed_password, is_verified=False)
    db.session.add(user)
    db.session.commit()
    
    return jsonify({"msg": "User created successfully. Please verify email."}), 201

@api_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({"msg": "Missing email or password"}), 400
        
    user = User.query.filter_by(email=data['email']).first()
    if not user or not bcrypt.check_password_hash(user.password, data['password']):
        return jsonify({"msg": "Bad email or password"}), 401
        
    access_token = create_access_token(identity=user.id, expires_delta=datetime.timedelta(minutes=15))
    refresh_token = create_refresh_token(identity=user.id, expires_delta=datetime.timedelta(days=30))
    
    user.last_login = datetime.datetime.utcnow()
    db.session.commit()
    
    return jsonify({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email
        }
    }), 200

@api_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    current_user_id = get_jwt_identity()
    new_access_token = create_access_token(identity=current_user_id, expires_delta=datetime.timedelta(minutes=15))
    return jsonify({"access_token": new_access_token}), 200

@api_bp.route('/profile', methods=['GET'])
@jwt_required()
def profile():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if not user:
        return jsonify({"msg": "User not found"}), 404
        
    return jsonify({
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "bio": user.bio,
        "is_verified": user.is_verified,
        "date_joined": user.date_joined.isoformat() if user.date_joined else None
    }), 200

@api_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    jti = get_jwt()["jti"]
    BLOCKLIST.add(jti)
    return jsonify({"msg": "Successfully logged out"}), 200
