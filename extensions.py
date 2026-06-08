from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_mail import Mail
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from authlib.integrations.flask_client import OAuth
from flask_socketio import SocketIO
from flask_migrate import Migrate
from flask_caching import Cache
from flask_session import Session
from flask_cors import CORS
from flasgger import Swagger

db = SQLAlchemy()
bcrypt = Bcrypt()
login_manager = LoginManager()
csrf = CSRFProtect()
mail = Mail()
jwt = JWTManager()
limiter = Limiter(key_func=get_remote_address)
oauth = OAuth()
socketio = SocketIO()
migrate = Migrate()
cache = Cache()
sess = Session()
cors = CORS()
swagger = Swagger()
