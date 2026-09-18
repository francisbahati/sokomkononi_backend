#!/bin/sh
set -e

echo "============================================================"
echo "SokoMkononi — entrypoint"
echo "============================================================"

# ------------------------------------------------------------
# Wait for Postgres (pure Python — no netcat required)
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
# Migrations
# ------------------------------------------------------------
echo "Applying database migrations..."
python manage.py migrate --noinput

# ------------------------------------------------------------
# Static files
# ------------------------------------------------------------
echo "Collecting static files..."
python manage.py collectstatic --noinput --clear

# ------------------------------------------------------------
# Start
# ------------------------------------------------------------
echo "Starting application..."
exec "$@"
