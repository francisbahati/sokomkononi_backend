# SokoMkononi — Backend

Django + DRF backend for the SokoMkononi marketplace.

## Local development

    python -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env
    python manage.py migrate
    python manage.py runserver

Use `DJANGO_SETTINGS_MODULE=config.settings_local` for SQLite dev.

## Production

    docker compose up -d --build

Services: `web` (gunicorn), `celery_worker`, `celery_beat`, `redis`.

Required `.env` variables — see `.env.example`:

- `SECRET_KEY` (≥ 50 chars)
- `DEBUG=False`
- `ALLOWED_HOSTS`
- `DB_*`
- `CELERY_BROKER_URL`
- `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`
- R2 storage: `R2_BUCKET_NAME`, `R2_ENDPOINT_URL`, `R2_ACCESS_KEY_ID`,
  `R2_SECRET_ACCESS_KEY` — **without these, uploaded media will NOT be
  served in production**
- `GOOGLE_CLIENT_ID`, `APPLE_CLIENT_ID` (social login)
- `PYNEXTSMS_TOKEN`, `PYNEXTSMS_SENDER_ID` (SMS OTP)

## API docs

    /api/docs/     Swagger UI
    /api/schema/   Raw OpenAPI schema

Restricted to admins in production unless `RESTRICT_DOCS=False`.

## Social login

    POST /api/auth/social/
    { "provider": "google" | "apple", "id_token": "..." }

Verifies the provider token, finds or creates the user by email, and
returns `{ user, access, refresh }`.

## Payments (SIMULATION)

All payment flows (`listing fee`, `boost`, `banner`, `bundle`,
`reservation`, `success-fee`) accept a `payment_reference` string and
mark the record paid. Replace with a real payment gateway / webhook
before going live.

## Known follow-ups

- Wire a real payment provider.
- Add `apps/searches/tasks.py` and `apps/saved/tasks.py` for alert
  matching and price-drop notifications (models already exist).
- Add a smoke-test suite.
