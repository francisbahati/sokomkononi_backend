#!/bin/sh
set -e

# Wait for PostgreSQL to be ready
if [ "$DATABASE" = "postgres" ]; then
    echo "Waiting for PostgreSQL..."
    while ! nc -z "$DB_HOST" "$DB_PORT"; do
        sleep 0.1
    done
    echo "PostgreSQL started"
fi

# Apply database migrations
echo "Applying migrations..."
python manage.py migrate --no-input

# Start Gunicorn
echo "Starting Gunicorn..."
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -