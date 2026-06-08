from flask import request
from flask_socketio import emit, join_room, leave_room
from extensions import socketio
from flask_login import current_user
from models import db, Message, Conversation
from datetime import datetime

# Store online users {user_id: sid}
online_users = {}

@socketio.on('connect')
def handle_connect():
    if current_user.is_authenticated:
        join_room(f"user_{current_user.id}")
        online_users[current_user.id] = request.sid
        emit('user_status', {'user_id': current_user.id, 'status': 'online'}, broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    if current_user.is_authenticated:
        leave_room(f"user_{current_user.id}")
        if current_user.id in online_users:
            del online_users[current_user.id]
        emit('user_status', {'user_id': current_user.id, 'status': 'offline'}, broadcast=True)

@socketio.on('typing')
def handle_typing(data):
    if current_user.is_authenticated:
        receiver_id = data.get('receiver_id')
        if receiver_id:
            emit('typing', {'sender_id': current_user.id}, room=f"user_{receiver_id}")
            
@socketio.on('stop_typing')
def handle_stop_typing(data):
    if current_user.is_authenticated:
        receiver_id = data.get('receiver_id')
        if receiver_id:
            emit('stop_typing', {'sender_id': current_user.id}, room=f"user_{receiver_id}")

@socketio.on('send_message')
def handle_send_message(data):
    if not current_user.is_authenticated:
        return

    receiver_id = data.get('receiver_id')
    content = data.get('message')
    if not receiver_id or not content:
        return

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

    # Send to receiver
    emit('receive_message', msg_data, room=f"user_{receiver_id}")
    # Send back to sender
    emit('receive_message', msg_data, room=f"user_{current_user.id}")
