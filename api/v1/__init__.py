from flask import Blueprint

api_v1_bp = Blueprint('api_v1', __name__, url_prefix='/api/v1')

# Import routes to register them with the blueprint
from . import auth, blogs, comments, users, notifications, media
