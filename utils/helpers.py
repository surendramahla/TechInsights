from extensions import db
from models import ActivityLog
from flask_login import current_user

def log_activity(action, target_type=None, target_id=None, details=None):
    if current_user.is_authenticated:
        log = ActivityLog(
            user_id=current_user.id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details
        )
        db.session.add(log)
        db.session.commit()
