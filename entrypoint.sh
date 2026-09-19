#!/bin/sh
set -e

echo "============================================================"
echo "SokoMkononi — entrypoint"
echo "============================================================"

# ------------------------------------------------------------
# Wait for Postgres
# ------------------------------------------------------------
if [ -n "$DB_HOST" ] && [ -n "$DB_PORT" ]; then
    echo "Waiting for PostgreSQL at $DB_HOST:$DB_PORT ..."
    python - <<'PY'
import os
import socket
import sys
import time

host = os.environ.get("DB_HOST")
port = int(os.environ.get("DB_PORT", "5432"))

for attempt in range(120):
    try:
        socket.create_connection((host, port), timeout=1).close()
        print(f"PostgreSQL is up at {host}:{port}")
        sys.exit(0)
    except OSError:
        time.sleep(0.5)

print(f"FATAL: PostgreSQL at {host}:{port} never became reachable", file=sys.stderr)
sys.exit(1)
PY
else
    echo "FATAL: DB_HOST or DB_PORT is not set" >&2
    exit 1
fi

# ------------------------------------------------------------
# Wait for Redis (only if CELERY_BROKER_URL points at Redis)
# ------------------------------------------------------------
BROKER_URL="${CELERY_BROKER_URL:-}"

if [ -n "$BROKER_URL" ]; then
    case "$BROKER_URL" in
        redis://*|rediss://*)
            echo "Detected Redis broker: $BROKER_URL"
            python - <<'PY'
import os
import socket
import sys
import time
from urllib.parse import urlparse

url = os.environ.get("CELERY_BROKER_URL", "")
parsed = urlparse(url)
host = parsed.hostname or "localhost"
port = parsed.port or 6379

print(f"Waiting for Redis at {host}:{port} ...")

for attempt in range(120):
    try:
        socket.create_connection((host, port), timeout=1).close()
        print(f"Redis is up at {host}:{port}")
        sys.exit(0)
    except OSError:
        time.sleep(0.5)

print(f"FATAL: Redis at {host}:{port} never became reachable", file=sys.stderr)
sys.exit(1)
PY
            ;;
        *)
            echo "Skipping Redis wait — CELERY_BROKER_URL is not a redis:// URL."
            ;;
    esac
else
    echo "Skipping Redis wait — CELERY_BROKER_URL is not set."
fi

# ------------------------------------------------------------
# Migrations
# ------------------------------------------------------------
echo "Applying database migrations..."
python manage.py migrate --noinput

# ------------------------------------------------------------
# Auto-create superuser (if env vars are present)
# ------------------------------------------------------------
if [ -n "$DJANGO_SUPERUSER_EMAIL" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
    echo "Ensuring superuser exists: $DJANGO_SUPERUSER_EMAIL"
    python manage.py shell -c "
import os
from apps.accounts.models import User

email = os.environ.get('DJANGO_SUPERUSER_EMAIL', '').strip()
name = os.environ.get('DJANGO_SUPERUSER_NAME', 'Admin').strip() or 'Admin'
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', '')

user = User.all_objects.filter(email=email).first()
if user:
    user.set_password(password)
    user.name = name
    user.is_staff = True
    user.is_superuser = True
    user.is_active = True
    user.is_verified = True
    user.is_deleted = False
    user.deleted_at = None
    user.deleted_by = None
    user.deletion_reason = ''
    user.save()
    print(f'Updated existing superuser: {email}')
else:
    User.objects.create_superuser(email=email, name=name, password=password)
    print(f'Created superuser: {email}')
" || echo "WARNING: superuser creation failed (continuing)."
else
    echo "Skipping superuser creation — DJANGO_SUPERUSER_EMAIL or DJANGO_SUPERUSER_PASSWORD not set."
fi

# ------------------------------------------------------------
# Static files
# ------------------------------------------------------------
echo "Collecting static files..."
python manage.py collectstatic --noinput

# ------------------------------------------------------------
# Start
# ------------------------------------------------------------
echo "Starting application..."
exec "$@"
