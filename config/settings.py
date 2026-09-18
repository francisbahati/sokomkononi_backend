# ============================================================
# config/settings.py
# SokoMkononi — Django settings
# ============================================================

import os
from datetime import timedelta
from pathlib import Path

from celery.schedules import crontab
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

# ------------------------------------------------------------
# ENV
# ------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env_bool(key, default=False):
    value = os.environ.get(key)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def env_list(key, default=""):
    raw = os.environ.get(key, default) or ""
    return [item.strip() for item in raw.split(",") if item.strip()]


def env_int(key, default=0):
    value = os.environ.get(key)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# ------------------------------------------------------------
# CORE
# ------------------------------------------------------------
SECRET_KEY = os.environ.get("SECRET_KEY", "insecure-dev-key-change-me")

DEBUG = env_bool("DEBUG", False)

# Fail loudly if production is running with the dev key.
if not DEBUG and SECRET_KEY == "insecure-dev-key-change-me":
    raise ImproperlyConfigured(
        "SECRET_KEY must be set to a secure value when DEBUG=False."
    )

ALLOWED_HOSTS = env_list(
    "ALLOWED_HOSTS",
    "127.0.0.1,localhost,sokomkononi.co.tz,www.sokomkononi.co.tz,api.sokomkononi.co.tz",
)

# ------------------------------------------------------------
# APPS
# ------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third-party
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    "storages",

    # Local apps
    "apps.core",
    "apps.accounts",
    "apps.categories",
    "apps.listings",
    "apps.boosting",
    "apps.deals",
    "apps.transactions",
    "apps.finance",
    "apps.notifications",
    "apps.waiting_list",
]

# ------------------------------------------------------------
# MIDDLEWARE  (CorsMiddleware MUST be before CommonMiddleware)
# ------------------------------------------------------------
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ------------------------------------------------------------
# DATABASE
# ------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "sokomkononi"),
        "USER": os.environ.get("DB_USER", "postgres"),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "5432"),
        "CONN_MAX_AGE": 60,
    }
}

# ------------------------------------------------------------
# AUTH
# ------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ------------------------------------------------------------
# I18N / TZ
# ------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Dar_es_Salaam"
USE_I18N = True
USE_TZ = True

# ------------------------------------------------------------
# STATIC / MEDIA
# ------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Hard caps on uploads.
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024       # 10 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024       # 10 MB
DATA_UPLOAD_MAX_NUMBER_FIELDS = 2000

# ------------------------------------------------------------
# STORAGE
# ------------------------------------------------------------
# R2 (S3-compatible) for media; WhiteNoise with compression+manifest
# for static files. Falls back to local FileSystemStorage when the
# R2 env vars are not configured (dev / CI).
# ------------------------------------------------------------
R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME", "")
R2_ENDPOINT_URL = os.environ.get("R2_ENDPOINT_URL", "")
R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY", "")
R2_MEDIA_LOCATION = os.environ.get("R2_MEDIA_LOCATION", "media")
R2_CUSTOM_DOMAIN = os.environ.get("R2_CUSTOM_DOMAIN", "") or None

R2_ENABLED = bool(
    R2_BUCKET_NAME
    and R2_ENDPOINT_URL
    and R2_ACCESS_KEY_ID
    and R2_SECRET_ACCESS_KEY
)

if R2_ENABLED:
    _default_storage = "config.storages.CloudflareR2MediaStorage"
else:
    _default_storage = "django.core.files.storage.FileSystemStorage"

STORAGES = {
    "default": {
        "BACKEND": _default_storage,
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# ------------------------------------------------------------
# CORS
# ------------------------------------------------------------
# CSRF_TRUSTED_ORIGINS is required because the Django admin (which
# uses session cookies + CSRF) is exposed under /admin/. The API
# itself uses JWT in the Authorization header, so CSRF middleware is
# a no-op for the API.
# ------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env_list(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:5173,https://sokomkononi.co.tz,https://www.sokomkononi.co.tz",
)

CORS_ALLOW_CREDENTIALS = env_bool("CORS_ALLOW_CREDENTIALS", False)

CORS_PREFLIGHT_MAX_AGE = env_int("CORS_PREFLIGHT_MAX_AGE", 86400)

CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
]

CORS_ALLOW_METHODS = [
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
]

CSRF_TRUSTED_ORIGINS = env_list(
    "CSRF_TRUSTED_ORIGINS",
    "https://sokomkononi.co.tz,https://www.sokomkononi.co.tz,https://api.sokomkononi.co.tz",
)

# ------------------------------------------------------------
# DRF
# ------------------------------------------------------------
# Global default is IsAuthenticated for safety. Public endpoints
# (categories, listing list/retrieve, auth) explicitly override with
# AllowAny at the view level. This keeps "secure by default" while
# still allowing public reads.
# ------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",

    # Scoped throttle class. Views opt-in by setting
    # `throttle_scope = "<key>"`.
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.ScopedRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "register": "10/hour",
        "login": "20/min",
        "otp_send": "5/hour",
        "otp_verify": "10/hour",
        "password_reset": "5/hour",
        "anon": "100/min",
        "user": "1000/hour",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": False,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
}

# ------------------------------------------------------------
# SPECTACULAR (Swagger / OpenAPI)
# ------------------------------------------------------------
# By default docs are admin-only in production. Set RESTRICT_DOCS=False
# in the environment to make /api/docs/ and /api/schema/ public — useful
# for testing or for exposing a public API reference.
# ------------------------------------------------------------
SPECTACULAR_SETTINGS = {
    "TITLE": "SokoMkononi API",
    "DESCRIPTION": "SokoMkononi marketplace API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

if not DEBUG and env_bool("RESTRICT_DOCS", True):
    SPECTACULAR_SETTINGS["SERVE_PERMISSIONS"] = [
        "rest_framework.permissions.IsAdminUser",
    ]

# ------------------------------------------------------------
# EMAIL
# ------------------------------------------------------------
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend",
)

EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = env_int("EMAIL_PORT", 587)
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")

DEFAULT_FROM_EMAIL = os.environ.get(
    "DEFAULT_FROM_EMAIL",
    "SokoMkononi <info@sokomkononi.co.tz>",
)

# Fail loudly if production has no working mailer.
if not DEBUG and not EMAIL_HOST:
    raise ImproperlyConfigured(
        "EMAIL_HOST must be set when DEBUG=False."
    )

# ADMINS / MANAGERS so mail_admins() works.
ADMINS = [
    ("SokoMkononi Admin", os.environ.get("ADMIN_EMAIL", DEFAULT_FROM_EMAIL)),
]
MANAGERS = ADMINS

# ------------------------------------------------------------
# SMS (NextSMS)
# ------------------------------------------------------------
PYNEXTSMS_TOKEN = os.environ.get("PYNEXTSMS_TOKEN", "")
PYNEXTSMS_SENDER_ID = os.environ.get("PYNEXTSMS_SENDER_ID", "")

# ------------------------------------------------------------
# CELERY
# ------------------------------------------------------------
# Default to localhost so bare-metal dev works without .env.
CELERY_BROKER_URL = os.environ.get(
    "CELERY_BROKER_URL",
    "redis://localhost:6379/0",
)
CELERY_RESULT_BACKEND = os.environ.get(
    "CELERY_RESULT_BACKEND",
    "redis://localhost:6379/0",
)

CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

# Production robustness for tasks.
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 10 * 60          # 10 min hard limit
CELERY_TASK_SOFT_TIME_LIMIT = 8 * 60      # 8 min soft limit
CELERY_RESULT_EXPIRES = 60 * 60 * 24      # 24 hours
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

# Beat schedule — drives the whole lifecycle.
CELERY_BEAT_SCHEDULE = {
    "purge-soft-deleted": {
        "task": "core.purge_soft_deleted",
        "schedule": crontab(hour=3, minute=0),
    },
    "expire-stale-reservations": {
        "task": "transactions.expire_stale_reservations",
        "schedule": crontab(minute="*/15"),
    },
    "expire-stale-inspections": {
        "task": "transactions.expire_stale_inspections",
        "schedule": crontab(minute="*/15"),
    },
    "warn-expiring-reservations": {
        "task": "transactions.warn_expiring_reservations",
        "schedule": crontab(minute=0),
    },
    "expire-stale-boosts": {
        "task": "boosting.expire_stale_boosts",
        "schedule": crontab(minute="*/15"),
    },
}

# ------------------------------------------------------------
# SECURITY (production)
# ------------------------------------------------------------
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST = True

    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30      # 30 days
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    X_FRAME_OPTIONS = "DENY"

    SECURE_REFERRER_POLICY = "same-origin"

# ------------------------------------------------------------
# LOGGING
# ------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": (
                "[{levelname}] {asctime} "
                "{name}:{lineno} — {message}"
            ),
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        # Security events (suspicious auth, CSRF failures,
        # disallowed hosts, etc.) at WARNING and above.
        "django.security": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "celery": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "apps": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}