from .settings import *  # noqa

# Local development overrides
DEBUG = True

ALLOWED_HOSTS = [
    "127.0.0.1",
    "localhost",
]

# Use SQLite instead of PostgreSQL
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Print emails to terminal instead of sending real emails
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"