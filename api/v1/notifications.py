from flask import jsonify, request
from . import api_v1_bp
from extensions import db
from models import Notification, User
from api.serializers import APISerializer
from flask_jwt_extended import jwt_required, get_jwt_identity

@api_v1_bp.route('/notifications', methods=['GET'])
@jwt_required()
def get_notifications():
    """
    Get Current User Notifications
    ---
    tags:
      - Notifications
    security:
      - ApiKeyAuth: []
    parameters:
      - name: page
        in: query
        type: integer
        default: 1
      - name: unread_only
        in: query
        type: boolean
        description: Set to true to filter unread notifications only
    responses:
      200:
        description: Returns a list of user notifications and unread counter
    """
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if not user:
        return jsonify({
            "success": False,
            "error": "UNAUTHORIZED",
            "message": "User session not active."
        }), 401

    page = request.args.get('page', 1, type=int)
    unread_only = request.args.get('unread_only', '').lower() == 'true'

    query = Notification.query.filter_by(receiver_id=user.id)
    
    if unread_only:
        query = query.filter_by(is_read=False)
        
    query = query.order_by(Notification.created_at.desc())
    
    # Standard 15 items paging
    pagination = query.paginate(page=page, per_page=15, error_out=False)
    
    # Calculate global unread count
    unread_count = Notification.query.filter_by(receiver_id=user.id, is_read=False).count()

    serialized_notifications = [APISerializer.notification(n) for n in pagination.items]

    return jsonify({
        "success": True,
        "message": "Notifications retrieved successfully.",
        "data": {
            "notifications": serialized_notifications,
            "unread_count": unread_count,
            "pagination": {
                "page": pagination.page,
                "per_page": pagination.per_page,
                "total_items": pagination.total,
                "total_pages": pagination.pages
            }
        }
    }), 200

@api_v1_bp.route('/notifications/<int:notification_id>/read', methods=['PUT'])
@jwt_required()
def mark_notification_read(notification_id):
    """
    Mark Notification as Read
    ---
    tags:
      - Notifications
    security:
      - ApiKeyAuth: []
    parameters:
      - name: notification_id
        in: path
        type: integer
        required: True
    responses:
      200:
        description: Notification marked as read successfully
      403:
        description: Unauthorized to mark another user's notification
    """
    current_user_id = get_jwt_identity()
    notification = Notification.query.get_or_404(notification_id)

    if notification.receiver_id != current_user_id:
        return jsonify({
            "success": False,
            "error": "FORBIDDEN",
            "message": "You do not have permission to modify this resource."
        }), 403

    notification.is_read = True
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Notification marked as read successfully.",
        "data": APISerializer.notification(notification)
    }), 200

@api_v1_bp.route('/notifications/<int:notification_id>', methods=['DELETE'])
@jwt_required()
def delete_notification(notification_id):
    """
    Delete a Notification
    ---
    tags:
      - Notifications
    security:
      - ApiKeyAuth: []
    parameters:
      - name: notification_id
        in: path
        type: integer
        required: True
    responses:
      200:
        description: Notification deleted successfully
    """
    current_user_id = get_jwt_identity()
    notification = Notification.query.get_or_404(notification_id)

    if notification.receiver_id != current_user_id:
        return jsonify({
            "success": False,
            "error": "FORBIDDEN",
            "message": "You do not have permission to delete this resource."
        }), 403

    db.session.delete(notification)
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Notification deleted successfully."
    }), 200
