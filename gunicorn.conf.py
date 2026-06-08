import os
import multiprocessing

# Bind address and port
bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"

# Concurrency Worker Setup
# Since we are using Flask-SocketIO, we MUST use the eventlet asynchronous worker class.
worker_class = 'eventlet'

# For eventlet/async workers, a lower worker count is recommended to avoid socket out-of-sync issues,
# as a single worker can handle thousands of concurrent greenlets.
workers = int(os.environ.get('GUNICORN_WORKERS', 2))

# Timeout and Connection Settings
# WebSocket connections need long-running connections, so keepalive is set higher.
timeout = 120
keepalive = 5

# Security Settings
# Limits maximum request line size to protect against buffer overflow exploits
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# Logging
# Log to standard output and error output so Docker captures logs properly
accesslog = '-'
errorlog = '-'
loglevel = os.environ.get('GUNICORN_LOG_LEVEL', 'info')
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Server Details
# Overrides server signature header to improve security (obscures tech stack details)
server = 'TechInsights WSGI Web Server'
