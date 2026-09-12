# ============================================================
# STAGE 1: Builder
# ============================================================
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies into a virtual environment
COPY requirements.txt .
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# ============================================================
# STAGE 2: Production
# ============================================================
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy the virtual environment from the builder
COPY --from=builder /opt/venv /opt/venv

# Copy project files
COPY . .

# Create directories for static and media files
RUN mkdir -p /app/staticfiles /app/media

# Create a non-root user for security
RUN addgroup --system django && \
    adduser --system --ingroup django django && \
    chown -R django:django /app

USER django

# Collect static files during build
RUN python manage.py collectstatic --no-input --settings=config.settings

EXPOSE 8000

# Entrypoint handles migrations + gunicorn startup
ENTRYPOINT ["/app/entrypoint.sh"]