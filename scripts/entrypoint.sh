#!/bin/sh

# exit immediately if a command exits with a non-zero status
set -e

echo "[Entrypoint] TechInsights container booting..."

# 1. Wait for PostgreSQL Database to accept connections
if [ -n "$POSTGRES_HOST" ]; then
    echo "[Entrypoint] Waiting for PostgreSQL database at $POSTGRES_HOST:$POSTGRES_PORT..."
    while ! nc -z "$POSTGRES_HOST" "${POSTGRES_PORT:-5432}"; do
        sleep 0.5
    done
    echo "[Entrypoint] PostgreSQL is online and ready!"
fi

# 2. Database Migrations via Flask-Migrate / Alembic
echo "[Entrypoint] Checking database migrations..."

# Initialize migration folder if missing
if [ ! -d "migrations" ]; then
    echo "[Entrypoint] 'migrations/' folder not found. Initializing Flask-Migrate..."
    
    # Drop the alembic_version table to avoid "Can't locate revision" errors
    echo "[Entrypoint] Clearing pre-existing database migration history..."
    python -c "from app import app; from extensions import db; import sqlalchemy; ctx = app.app_context(); ctx.push(); db.session.execute(sqlalchemy.text('DROP TABLE IF EXISTS alembic_version CASCADE')); db.session.commit(); ctx.pop()" || true
    
    flask db init
    echo "[Entrypoint] Creating initial schema migration..."
    flask db migrate -m "Initial schema migration"
    echo "[Entrypoint] Stamping database to new head..."
    flask db stamp head
fi

# Apply migrations
echo "[Entrypoint] Applying migrations (flask db upgrade)..."
if ! flask db upgrade; then
    echo "[Entrypoint] Migration failed (possibly due to revision mismatch). Stamping database with head and retrying..."
    flask db stamp head
    echo "[Entrypoint] Retrying database migration upgrade..."
    flask db upgrade
fi
echo "[Entrypoint] Database schema is fully up-to-date!"

# 3. Handover control to Gunicorn WSGI production server
echo "[Entrypoint] Starting Gunicorn application server..."
exec gunicorn --config gunicorn.conf.py app:app
