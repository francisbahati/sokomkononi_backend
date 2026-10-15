"""
Local development settings — SQLite + LocMemCache + no R2.

Activate with:
    export DJANGO_SETTINGS_MODULE=config.settings_local
    python manage.py runserver
"""
import os

# These MUST be set before the star-import so config/settings.py
# does not raise ImproperlyConfigured on a machine with a prod .env.
os.environ["DEBUG"] = "True"
os.environ.setdefault(
    "SECRET_KEY",
    "local-dev-only-" + ("x" * 60),
)
os.environ.setdefault("FIMIPAY_SECRET_KEY", "sk_test_local")
os.environ.setdefault("FIMIPAY_WEBHOOK_SECRET", "local-webhook-secret")

# Force a file cache so redis:// URLs from .env don't leak in
os.environ.pop("REDIS_CACHE_URL", None)
os.environ.pop("CELERY_BROKER_URL", None)

from .settings import *  # noqa

# ── Local overrides ──────────────────────────────────
DEBUG = True

ALLOWED_HOSTS = ["127.0.0.1", "localhost", "0.0.0.0"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Use in-memory cache — django-ratelimit works with LocMemCache.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "soko-local",
    }
}

# Remove django_ratelimit from INSTALLED_APPS if it got added by settings.py
INSTALLED_APPS = [a for a in INSTALLED_APPS if a != "django_ratelimit"]
# Remove messaging app — it has been deleted from the project.
INSTALLED_APPS = [a for a in INSTALLED_APPS if a != "apps.messaging"]

# Keep CSRF/CORS permissive locally
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]

# Local dev: run Celery tasks inline (no Redis broker needed)
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Never touch production R2 in dev
R2_ENABLED = False
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

# Local email: print to console
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
