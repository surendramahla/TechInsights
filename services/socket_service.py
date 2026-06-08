from extensions import socketio, db
from models import Notification

def send_notification(receiver_id, notification_type, message, link_url=None, sender_id=None):
    """
    Creates a notification in DB and emits a socket event.
    """
    notif = Notification(
        receiver_id=receiver_id,
        sender_id=sender_id,
        notification_type=notification_type,
        message=message,
        link_url=link_url
    )
    db.session.add(notif)
    db.session.commit()
    
    # Broadcast to the specific user's room
    socketio.emit('new_notification', {
        'id': notif.id,
        'message': message,
        'link_url': link_url,
        'type': notification_type,
        'created_at': notif.created_at.strftime("%b %d, %Y %H:%M")
    }, room=f"user_{receiver_id}")
    
    return notif
