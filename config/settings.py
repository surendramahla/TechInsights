import os
from dotenv import load_dotenv

# Load local environment variables from .env if present
load_dotenv()

IS_DOCKER = os.path.exists('/.dockerenv')

class Config:
    """Base Configuration with default settings."""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'techinsights_flask_ultra_secure_key_2026'
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'techinsights_jwt_ultra_secure_key_2026'
    
    # SQLAlchemy & Database Configurations
    # Handles Render/Heroku postgres:// vs postgresql:// compatibility
    db_url = os.environ.get('DATABASE_URL')
    if db_url and db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
        
    # If DATABASE_URL references the internal Docker 'db' host but we are running on the host machine,
    # fallback to local SQLite site.db to avoid connection failures.
    # In serverless environments like Vercel, fallback SQLite path is /tmp/site.db to avoid read-only system errors.
    is_vercel = os.environ.get('VERCEL') == '1'
    if db_url and '@db' in db_url and not IS_DOCKER:
        if is_vercel:
            SQLALCHEMY_DATABASE_URI = 'sqlite:////tmp/site.db'
        else:
            SQLALCHEMY_DATABASE_URI = 'sqlite:///site.db'
    else:
        if not db_url and is_vercel:
            SQLALCHEMY_DATABASE_URI = 'sqlite:////tmp/site.db'
        else:
            SQLALCHEMY_DATABASE_URI = db_url or 'sqlite:///site.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # File upload settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024   # 16 MB max upload
    UPLOAD_FOLDER = os.path.join('static', 'uploads')
    
    # Flask-Mail configuration
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
    MAIL_USERNAME = os.environ.get('EMAIL_USER')
    MAIL_PASSWORD = os.environ.get('EMAIL_PASS')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')
    
    # Cloudinary Integration credentials
    CLOUDINARY_CLOUD_NAME = os.environ.get('CLOUDINARY_CLOUD_NAME')
    CLOUDINARY_API_KEY = os.environ.get('CLOUDINARY_API_KEY')
    CLOUDINARY_API_SECRET = os.environ.get('CLOUDINARY_API_SECRET')

    # Google OAuth credentials
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')

    # Redis URL with smart fallback for host-side execution
    redis_url = os.environ.get('REDIS_URL') or 'redis://localhost:6379/0'
    if 'redis://redis' in redis_url and not IS_DOCKER:
        REDIS_URL = redis_url.replace('redis://redis', 'redis://localhost', 1)
    else:
        REDIS_URL = redis_url
    
    # Flask-Caching Configurations
    CACHE_TYPE = 'SimpleCache'  # Default fallback cache
    
    # Flask-Session Configurations
    SESSION_TYPE = 'null'  # Use standard secure cookies as default fallback
    
    # Security parameters
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'


class DevelopmentConfig(Config):
    """Development configuration overrides."""
    DEBUG = True
    CACHE_TYPE = 'SimpleCache'


class ProductionConfig(Config):
    """Production configuration overrides."""
    DEBUG = False
    TESTING = False
    
    # Force HTTPS cookie security settings in production
    # (If running on host over HTTP, modern browsers allow localhost cookies, 
    # but for local non-secure HTTP runs we dynamically lower to Lax/False if needed)
    SESSION_COOKIE_SECURE = IS_DOCKER
    REMEMBER_COOKIE_SECURE = IS_DOCKER
    
    # Database Connection Pooling optimization
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'max_overflow': 20,
        'pool_timeout': 30,
        'pool_recycle': 1800,
    }
    
    # Production Redis Configurations for Cache
    # Only enable Redis session store, caching, and limiting if we are inside Docker,
    # or if we are on the host but explicitly want to use a local Redis server,
    # or if we are running in serverless environments like Vercel.
    is_vercel = os.environ.get('VERCEL') == '1'
    if os.environ.get('REDIS_URL') and (IS_DOCKER or 'localhost' in os.environ.get('REDIS_URL', '') or is_vercel):
        CACHE_TYPE = 'RedisCache'
        CACHE_REDIS_URL = os.environ.get('REDIS_URL')
        
        # Redis Session setup
        SESSION_TYPE = 'redis'
        import redis
        SESSION_REDIS = redis.from_url(os.environ.get('REDIS_URL'))
        SESSION_USE_SIGNER = True  # Encrypt session cookies for production grade security
        
        # Flask-Limiter Storage URI (uses Redis in production if configured)
        RATELIMIT_STORAGE_URI = os.environ.get('REDIS_URL')
    else:
        # Fallback if outside Docker and local Redis is not running: use cookies and SimpleCache
        CACHE_TYPE = 'SimpleCache'
        SESSION_TYPE = 'null'
        RATELIMIT_STORAGE_URI = None


class TestingConfig(Config):
    """Testing configuration overrides."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'  # Fast in-memory DB for tests
    WTF_CSRF_ENABLED = False  # Disable CSRF in testing environment
    CACHE_TYPE = 'NullCache'
