from flask import jsonify, request, url_for
from . import api_v1_bp
from extensions import db
from models import User, Blog
from api.serializers import APISerializer
from flask_jwt_extended import jwt_required, get_jwt_identity

@api_v1_bp.route('/users', methods=['GET'])
def get_users():
    """
    List Users API
    ---
    tags:
      - Users
    parameters:
      - name: page
        in: query
        type: integer
        default: 1
      - name: per_page
        in: query
        type: integer
        default: 15
    responses:
      200:
        description: Returns a paginated list of users
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 15, type=int)

    query = User.query.order_by(User.username.asc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    serialized_users = [APISerializer.user_basic(u) for u in pagination.items]

    return jsonify({
        "success": True,
        "message": "Users retrieved successfully.",
        "data": {
            "users": serialized_users,
            "pagination": {
                "page": pagination.page,
                "per_page": pagination.per_page,
                "total_items": pagination.total,
                "total_pages": pagination.pages,
                "has_next": pagination.has_next,
                "has_prev": pagination.has_prev
            }
        }
    }), 200

@api_v1_bp.route('/users/<int:user_id>', methods=['GET'])
def get_user_detail(user_id):
    """
    Get Public Profile Details
    ---
    tags:
      - Users
    parameters:
      - name: user_id
        in: path
        type: integer
        required: True
    responses:
      200:
        description: Returns detailed public profile and follower statistics
      404:
        description: User not found
    """
    user = User.query.get_or_404(user_id)
    
    # Check if there is an active JWT to determine follow status
    current_user = None
    try:
        from flask_jwt_extended import verify_jwt_in_request
        verify_jwt_in_request(optional=True)
        current_user_id = get_jwt_identity()
        if current_user_id:
            current_user = User.query.get(current_user_id)
    except Exception:
        pass

    return jsonify({
        "success": True,
        "message": "User profile retrieved successfully.",
        "data": APISerializer.user_profile(user, current_user=current_user)
    }), 200

@api_v1_bp.route('/users/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    """
    Update Profile details
    ---
    tags:
      - Users
    security:
      - ApiKeyAuth: []
    parameters:
      - in: body
        name: body
        required: True
        schema:
          type: object
          properties:
            username:
              type: string
            email:
              type: string
            bio:
              type: string
    responses:
      200:
        description: Profile updated successfully
    """
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if not user:
        return jsonify({
            "success": False,
            "error": "UNAUTHORIZED",
            "message": "User session not active."
        }), 401

    data = request.get_json()
    if not data:
        return jsonify({
            "success": False,
            "error": "BAD_REQUEST",
            "message": "No fields to update provided."
        }), 400

    username = data.get('username', '').strip()
    email = data.get('email', '').strip().lower()
    bio = data.get('bio', '').strip()

    if username and username != user.username:
        if User.query.filter_by(username=username).first():
            return jsonify({
                "success": False,
                "error": "CONFLICT",
                "message": "Username already taken."
            }), 400
        user.username = username

    if email and email != user.email:
        if User.query.filter_by(email=email).first():
            return jsonify({
                "success": False,
                "error": "CONFLICT",
                "message": "Email already registered."
            }), 400
        user.email = email

    if 'bio' in data:
        user.bio = bio

    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Profile updated successfully.",
        "data": APISerializer.user_profile(user, current_user=user)
    }), 200

@api_v1_bp.route('/users/<int:user_id>/blogs', methods=['GET'])
def get_user_blogs(user_id):
    """
    Get Blogs Authored by User
    ---
    tags:
      - Users
    parameters:
      - name: user_id
        in: path
        type: integer
        required: True
      - name: page
        in: query
        type: integer
        default: 1
    responses:
      200:
        description: Returns a paginated list of blogs written by the user
    """
    user = User.query.get_or_404(user_id)
    page = request.args.get('page', 1, type=int)

    query = Blog.query.filter_by(user_id=user.id, is_blocked=False).order_by(Blog.date_posted.desc())
    pagination = query.paginate(page=page, per_page=10, error_out=False)

    serialized_blogs = [APISerializer.blog(b, include_content=False) for b in pagination.items]

    return jsonify({
        "success": True,
        "message": "User blogs retrieved successfully.",
        "data": {
            "blogs": serialized_blogs,
            "pagination": {
                "page": pagination.page,
                "per_page": pagination.per_page,
                "total_items": pagination.total,
                "total_pages": pagination.pages
            }
        }
    }), 200

@api_v1_bp.route('/users/<int:user_id>/follow', methods=['POST'])
@jwt_required()
def follow_user(user_id):
    """
    Follow a User
    ---
    tags:
      - Users
    security:
      - ApiKeyAuth: []
    parameters:
      - name: user_id
        in: path
        type: integer
        required: True
    responses:
      200:
        description: Followed user successfully
      400:
        description: Cannot follow yourself
    """
    current_user_id = get_jwt_identity()
    if current_user_id == user_id:
        return jsonify({
            "success": False,
            "error": "BAD_REQUEST",
            "message": "You cannot follow yourself."
        }), 400

    user_to_follow = User.query.get_or_404(user_id)
    current_user = User.query.get(current_user_id)

    if current_user.is_following(user_to_follow):
        return jsonify({
            "success": False,
            "error": "BAD_REQUEST",
            "message": "You are already following this user."
        }), 400

    current_user.follow(user_to_follow)
    db.session.commit()

    # Trigger Notification
    from services.socket_service import send_notification
    send_notification(
        receiver_id=user_to_follow.id,
        sender_id=current_user.id,
        notification_type='follow',
        message=f"{current_user.username} started following you!",
        link_url=url_for('user_profile', username=current_user.username)
    )

    return jsonify({
        "success": True,
        "message": f"Successfully following {user_to_follow.username}.",
        "data": {
            "is_following": True,
            "followers_count": user_to_follow.followers.count()
        }
    }), 200

@api_v1_bp.route('/users/<int:user_id>/follow', methods=['DELETE'])
@jwt_required()
def unfollow_user(user_id):
    """
    Unfollow a User
    ---
    tags:
      - Users
    security:
      - ApiKeyAuth: []
    parameters:
      - name: user_id
        in: path
        type: integer
        required: True
    responses:
      200:
        description: Unfollowed user successfully
    """
    current_user_id = get_jwt_identity()
    user_to_unfollow = User.query.get_or_404(user_id)
    current_user = User.query.get(current_user_id)

    if not current_user.is_following(user_to_unfollow):
        return jsonify({
            "success": False,
            "error": "BAD_REQUEST",
            "message": "You are not following this user."
        }), 400

    current_user.unfollow(user_to_unfollow)
    db.session.commit()

    return jsonify({
        "success": True,
        "message": f"Successfully unfollowed {user_to_unfollow.username}.",
        "data": {
            "is_following": False,
            "followers_count": user_to_unfollow.followers.count()
        }
    }), 200

@api_v1_bp.route('/users/<int:user_id>/followers', methods=['GET'])
def get_followers(user_id):
    """
    Get User Followers
    ---
    tags:
      - Users
    parameters:
      - name: user_id
        in: path
        type: integer
        required: True
    responses:
      200:
        description: Returns a list of follower users
      404:
        description: User not found
    """
    user = User.query.get_or_404(user_id)
    followers = user.followers.all()
    
    return jsonify({
        "success": True,
        "message": "Followers retrieved successfully.",
        "data": [APISerializer.user_basic(f) for f in followers]
    }), 200
