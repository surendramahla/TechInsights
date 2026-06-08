from flask import Blueprint, jsonify, request, render_template
from flask_login import login_required, current_user
from models import db, Notification, Conversation, Message, User
from sqlalchemy import or_
from datetime import datetime

realtime_bp = Blueprint('realtime', __name__, url_prefix='/realtime')

@realtime_bp.route('/notifications', methods=['GET'])
@login_required
def get_notifications():
    notifications = Notification.query.filter_by(receiver_id=current_user.id).order_by(Notification.created_at.desc()).limit(20).all()
    unread_count = Notification.query.filter_by(receiver_id=current_user.id, is_read=False).count()
    return jsonify({
        'unread_count': unread_count,
        'notifications': [{
            'id': n.id,
            'message': n.message,
            'link_url': n.link_url,
            'type': n.notification_type,
            'is_read': n.is_read,
            'created_at': n.created_at.isoformat() + 'Z'
        } for n in notifications]
    })

@realtime_bp.route('/notifications/read_all', methods=['POST'])
@login_required
def mark_all_read():
    Notification.query.filter_by(receiver_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    return jsonify({'status': 'success'})

@realtime_bp.route('/notifications/read/<int:notif_id>', methods=['POST'])
@login_required
def mark_read(notif_id):
    notif = Notification.query.get_or_404(notif_id)
    if notif.receiver_id == current_user.id:
        notif.is_read = True
        db.session.commit()
    return jsonify({'status': 'success'})

@realtime_bp.route('/chat/conversations', methods=['GET'])
@login_required
def get_conversations():
    conversations = Conversation.query.filter(
        or_(Conversation.user1_id == current_user.id, Conversation.user2_id == current_user.id)
    ).order_by(Conversation.last_message_at.desc()).all()
    
    result = []
    for conv in conversations:
        other_user = conv.user2 if conv.user1_id == current_user.id else conv.user1
        last_msg = conv.messages.order_by(Message.timestamp.desc()).first()
        result.append({
            'id': conv.id,
            'other_user_id': other_user.id,
            'other_username': other_user.username,
            'other_avatar': other_user.image_file,
            'last_message': last_msg.message_content if last_msg else '',
            'last_message_time': last_msg.timestamp.strftime('%H:%M') if last_msg else ''
        })
    return jsonify({'conversations': result})

@realtime_bp.route('/chat/messages/<int:user_id>', methods=['GET'])
@login_required
def get_messages(user_id):
    conv = Conversation.query.filter(
        ((Conversation.user1_id == current_user.id) & (Conversation.user2_id == user_id)) |
        ((Conversation.user1_id == user_id) & (Conversation.user2_id == current_user.id))
    ).first()
    
    if not conv:
        return jsonify({'messages': []})
        
    messages = conv.messages.order_by(Message.timestamp.asc()).all()
    
    # Mark as read
    conv.messages.filter_by(receiver_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    
    return jsonify({'messages': [{
        'id': m.id,
        'sender_id': m.sender_id,
        'receiver_id': m.receiver_id,
        'content': m.message_content,
        'timestamp': m.timestamp.strftime('%H:%M')
    } for m in messages]})

@realtime_bp.route('/chat/send', methods=['POST'])
@login_required
def send_message_http():
    data = request.get_json() or {}
    receiver_id = data.get('receiver_id')
    content = data.get('message')
    if not receiver_id or not content:
        return jsonify({'error': 'Missing receiver_id or message'}), 400

    # Find or create conversation
    conv = Conversation.query.filter(
        ((Conversation.user1_id == current_user.id) & (Conversation.user2_id == receiver_id)) |
        ((Conversation.user1_id == receiver_id) & (Conversation.user2_id == current_user.id))
    ).first()

    if not conv:
        conv = Conversation(user1_id=current_user.id, user2_id=receiver_id)
        db.session.add(conv)
        db.session.commit()

    # Create message
    msg = Message(
        conversation_id=conv.id,
        sender_id=current_user.id,
        receiver_id=receiver_id,
        message_content=content
    )
    conv.last_message_at = datetime.utcnow()
    db.session.add(msg)
    db.session.commit()

    msg_data = {
        'id': msg.id,
        'sender_id': msg.sender_id,
        'receiver_id': msg.receiver_id,
        'content': msg.message_content,
        'timestamp': msg.timestamp.strftime('%H:%M'),
        'conversation_id': conv.id
    }

    # Try to emit socket event for real-time clients if socket is active
    try:
        from extensions import socketio
        socketio.emit('receive_message', msg_data, room=f"user_{receiver_id}")
        socketio.emit('receive_message', msg_data, room=f"user_{current_user.id}")
    except Exception:
        pass

    return jsonify({'status': 'success', 'message': msg_data})

