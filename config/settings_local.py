import os

# These MUST be set before the star-import so that config/settings.py
# does not raise ImproperlyConfigured on a machine that has a prod .env.
os.environ["DEBUG"] = "True"
os.environ.setdefault(
    "SECRET_KEY",
    "local-dev-only-" + ("x" * 60),
)
os.environ.setdefault("FIMIPAY_SECRET_KEY", "sk_test_local")
os.environ.setdefault("FIMIPAY_WEBHOOK_SECRET", "local-webhook-secret")

from .settings import *  # noqa

# Local dev: run Celery tasks inline (no Redis broker needed)
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
  # noqa

# ----------------------------------------------------------------------
# Local overrides
# ----------------------------------------------------------------------
DEBUG = True

ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Keep CSRF/CORS permissive locally
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]
