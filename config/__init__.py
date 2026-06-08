import os
from config.settings import DevelopmentConfig, ProductionConfig, TestingConfig

def get_config():
    """Returns the config class based on the FLASK_ENV environment variable."""
    env = os.environ.get('FLASK_ENV', 'development').lower()
    
    if env == 'production' or env == 'prod':
        return ProductionConfig
    elif env == 'testing' or env == 'test':
        return TestingConfig
    else:
        return DevelopmentConfig
