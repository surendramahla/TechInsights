# Multi-stage build to keep the production image clean and minimal
# Stage 1: Build dependencies
FROM python:3.11-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies required for building wheels (e.g. C compilers, postgres-dev)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install dependencies into a wheels directory to avoid polluting the host
RUN pip install --no-cache-dir --upgrade pip \
    && pip wheel --no-cache-dir --wheel-dir /app/wheels -r requirements.txt


# Stage 2: Final minimal runner image
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV FLASK_ENV=production
ENV EVENTLET_NO_GREENDNS=yes

# Install system runtime dependencies (libpq is needed for psycopg2 database client)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Copy built wheels from builder stage and install them
COPY --from=builder /app/wheels /wheels
COPY requirements.txt .
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt \
    && rm -rf /wheels

# Create a non-privileged system user for running the application securely
RUN useradd -u 1001 -r -s /bin/false webuser \
    && mkdir -p /app/static/uploads /app/instance \
    && chown -R webuser:webuser /app

# Copy application source code and set ownership
COPY --chown=webuser:webuser . .

# Grant execute rights to startup scripts
RUN chmod +x /app/scripts/entrypoint.sh \
    && chown webuser:webuser /app/scripts/entrypoint.sh

# Run as non-root user
USER 1001

EXPOSE 8000

# Run entrypoint script which handles DB migration and Gunicorn start
ENTRYPOINT ["/app/scripts/entrypoint.sh"]
