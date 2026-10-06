# ============================================================
# config/settings.py — SokoMkononi (production-ready)
# ============================================================
import os
from datetime import timedelta
from pathlib import Path

from celery.schedules import crontab
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(key, default=False):
    v = os.environ.get(key)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def env_list(key, default=""):
    raw = os.environ.get(key, default) or ""
    return [i.strip() for i in raw.split(",") if i.strip()]


def env_int(key, default=0):
    v = os.environ.get(key)
    if v is None or v == "":
        return default
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


# ---------------- CORE ----------------
SECRET_KEY = os.environ.get("SECRET_KEY", "insecure-dev-key-change-me")
DEBUG = env_bool("DEBUG", False)

if not DEBUG:
    if SECRET_KEY == "insecure-dev-key-change-me":
        raise ImproperlyConfigured("SECRET_KEY must be set when DEBUG=False.")
    if len(SECRET_KEY) < 50:
        raise ImproperlyConfigured("SECRET_KEY must be at least 50 chars in production.")

ALLOWED_HOSTS = list(dict.fromkeys(
    env_list("ALLOWED_HOSTS", "127.0.0.1,localhost") + [
        "sokomkononi.co.tz",
        "www.sokomkononi.co.tz",
        "api.sokomkononi.co.tz",
        "127.0.0.1",
        "localhost",
    ]
))

INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "rest_framework", "rest_framework_simplejwt", "rest_framework_simplejwt.token_blacklist",
    "corsheaders", "django_filters", "drf_spectacular",
    "drf_spectacular_sidecar", "storages", "csp",
    "apps.core",
    "apps.payments", "apps.contact", "apps.accounts", "apps.categories", "apps.listings",
    "apps.boosting", "apps.deals", "apps.transactions", "apps.finance",
    "apps.notifications", "apps.waiting_list", "apps.saved", "apps.searches",
    "apps.leads", "apps.messaging", "apps.verifications", "apps.tickets",
    "apps.audit", "apps.announcements", "apps.content", "apps.rbac",
    "apps.system_settings", "apps.bundles", "apps.credits", "apps.banners",
    "apps.leading_fees", "apps.advertisement_fees", "apps.reservation_rates",
]

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
    "csp.middleware.CSPMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.debug",
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {"default": {
    "ENGINE": "django.db.backends.postgresql",
    "NAME": os.environ.get("DB_NAME", "sokomkononi"),
    "USER": os.environ.get("DB_USER", "postgres"),
    "PASSWORD": os.environ.get("DB_PASSWORD", ""),
    "HOST": os.environ.get("DB_HOST", "localhost"),
    "PORT": os.environ.get("DB_PORT", "5432"),
    "CONN_MAX_AGE": 60,
}}

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Dar_es_Salaam"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 2000

# ---------------- R2 STORAGE ----------------
R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME", "")
R2_ENDPOINT_URL = os.environ.get("R2_ENDPOINT_URL", "")
R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY", "")
R2_MEDIA_LOCATION = os.environ.get("R2_MEDIA_LOCATION", "media")

_raw_domain = (os.environ.get("R2_CUSTOM_DOMAIN", "") or "").strip().rstrip("/")
_raw_domain = _raw_domain.replace("https//", "https://").replace("http//", "http://")
for _p in ("https://", "http://"):
    if _raw_domain.startswith(_p):
        _raw_domain = _raw_domain[len(_p):]
R2_CUSTOM_DOMAIN = _raw_domain or None

R2_ENABLED = bool(R2_BUCKET_NAME and R2_ENDPOINT_URL and R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY)

_default_storage = (
    "config.storages.CloudflareR2MediaStorage" if R2_ENABLED
    else "django.core.files.storage.FileSystemStorage"
)

STORAGES = {
    "default": {"BACKEND": _default_storage},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

# ---------------- CSP ----------------
R2_PUBLIC_ORIGIN = f"https://{R2_CUSTOM_DOMAIN}" if R2_CUSTOM_DOMAIN else None

_CSP_IMG_SRC = ["'self'", "data:", "blob:"]
_CSP_MEDIA_SRC = ["'self'"]
if R2_PUBLIC_ORIGIN:
    _CSP_IMG_SRC.append(R2_PUBLIC_ORIGIN)
    _CSP_MEDIA_SRC.append(R2_PUBLIC_ORIGIN)

_connect_src = ["'self'"] + [
    o for o in ["https://api.sokomkononi.co.tz", R2_PUBLIC_ORIGIN] if o
]

_CSP_DIRECTIVES = {
    "default-src": ["'self'"],
    "img-src": _CSP_IMG_SRC,
    "media-src": _CSP_MEDIA_SRC,
    "script-src": ["'self'", "'unsafe-inline'", "https://unpkg.com", "https://cdn.jsdelivr.net"],
    "style-src": ["'self'", "'unsafe-inline'", "https://unpkg.com", "https://cdn.jsdelivr.net", "https://fonts.googleapis.com"],
    # FIX: duplicate "font-src" key removed; the Google Fonts version is kept.
    "font-src": ["'self'", "data:", "https://fonts.gstatic.com"],
    "connect-src": _connect_src,
    "frame-ancestors": ["'none'"],
    "base-uri": ["'self'"],
    "form-action": ["'self'"],
}

_EXCLUDE_URL_PREFIXES = ("/api/docs", "/api/schema", "/admin")

if env_bool("CSP_REPORT_ONLY", True):  # TEMP: unblock Swagger UI
    # django-csp 4.0 native report-only mode.
    CONTENT_SECURITY_POLICY_REPORT_ONLY = {
        "DIRECTIVES": _CSP_DIRECTIVES,
        "EXCLUDE_URL_PREFIXES": _EXCLUDE_URL_PREFIXES,
    }
    CONTENT_SECURITY_POLICY = {"DIRECTIVES": {}}
else:
    CONTENT_SECURITY_POLICY = {
        "DIRECTIVES": _CSP_DIRECTIVES,
        "EXCLUDE_URL_PREFIXES": _EXCLUDE_URL_PREFIXES,
    }



# ---------------- CORS ----------------
CORS_ALLOWED_ORIGINS = env_list(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:5173,https://sokomkononi.co.tz,https://www.sokomkononi.co.tz",
)
CORS_ALLOW_CREDENTIALS = env_bool("CORS_ALLOW_CREDENTIALS", True)
CORS_PREFLIGHT_MAX_AGE = env_int("CORS_PREFLIGHT_MAX_AGE", 86400)
CORS_ALLOW_HEADERS = [
    "accept", "accept-encoding", "authorization", "content-type", "dnt",
    "origin", "user-agent", "x-csrftoken", "x-requested-with", "x-access-token",
]
CORS_ALLOW_METHODS = ["DELETE", "GET", "OPTIONS", "PATCH", "POST", "PUT"]

CSRF_TRUSTED_ORIGINS = list(dict.fromkeys(
    env_list("CSRF_TRUSTED_ORIGINS", "") + [
        "https://sokomkononi.co.tz",
        "https://www.sokomkononi.co.tz",
        "https://api.sokomkononi.co.tz",
    ]
))

# ---------------- DRF ----------------
REST_FRAMEWORK = {
    # FIX: stop DRF from hijacking ?format=pdf|csv|doc (it returned 404).
    "URL_FORMAT_OVERRIDE": None,
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "apps.accounts.authentication.FlexibleJWTAuthentication",
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": ("rest_framework.throttling.ScopedRateThrottle",),
    "DEFAULT_THROTTLE_RATES": {
        "register": "10/hour",
        "login": "20/min",
        "otp_send": "5/hour",
        "otp_verify": "10/hour",
        "password_reset": "5/hour",
        "anon": "100/min",
        "user": "1000/hour",
        "support_ticket": "5/hour",
        "contact": "5/hour",
        "refresh": "60/min",
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

# ---------------- SPECTACULAR (SWAGGER) — FIXED ----------------
SPECTACULAR_SETTINGS = {
    "TITLE": "SokoMkononi API",
    "DESCRIPTION": "SokoMkononi marketplace API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SWAGGER_UI_DIST": "SIDECAR",
    "SWAGGER_UI_FAVICON_HREF": "SIDECAR",
    "REDOC_DIST": "SIDECAR",
    "COMPONENT_SPLIT_REQUEST": True,
    "SORT_OPERATIONS": False,
    # Disambiguate enum names that would otherwise collide across
    # multiple choice sets named "status", "type", "priority", etc.
    "ENUM_NAME_OVERRIDES": {
        # Transaction.status, Reservation.status, InspectionPeriod.status,
        # BannerAd.payment_status, ListingFee.payment_status,
        # BundlePurchase.status, ListingBoost.payment_status, etc.
        "TransactionStatusEnum":
            "apps.transactions.models.Transaction.Status.choices",
        "ReservationStatusEnum":
            "apps.transactions.models.Reservation.Status.choices",
        "InspectionStatusEnum":
            "apps.transactions.models.InspectionPeriod.Status.choices",
        "ListingStatusEnum":
            "apps.listings.models.Listing.Status.choices",
        "ListingFeeStatusEnum":
            "apps.listings.models.ListingFee.PaymentStatus.choices",
        "BoostStatusEnum":
            "apps.boosting.models.ListingBoost.BoostStatus.choices",
        "BoostPaymentStatusEnum":
            "apps.boosting.models.ListingBoost.PaymentStatus.choices",
        "DealRoomStatusEnum":
            "apps.deals.models.DealRoom.Status.choices",
        "BundleStatusEnum":
            "apps.bundles.models.BundlePurchase.Status.choices",
        "BundleTypeEnum":
            "apps.bundles.models.Bundle.Type.choices",
        "BannerPaymentStatusEnum": [
            ("PENDING", "Pending"),
            ("PAID", "Paid"),
            ("FAILED", "Failed"),
            ("REFUNDED", "Refunded"),
        ],
        "NotificationTypeEnum":
            "apps.notifications.models.Notification.NotificationType.choices",
        "NotificationPriorityEnum":
            "apps.notifications.models.Notification.Priority.choices",
        "NotificationAudienceEnum":
            "apps.notifications.models.Notification.Audience.choices",
        "TicketStatusEnum":
            "apps.tickets.models.Ticket.Status.choices",
        "TicketPriorityEnum":
            "apps.tickets.models.Ticket.Priority.choices",
        "TicketCategoryEnum":
            "apps.tickets.models.Ticket.Category.choices",
        "VerificationStatusEnum":
            "apps.verifications.models.VerificationRequest.Status.choices",
        "VerificationTypeEnum":
            "apps.verifications.models.VerificationRequest.Type.choices",
        "LeadingStatusEnum":
            "apps.leading_fees.models.ListingLeading.Status.choices",
        "LeadingPaymentStatusEnum":
            "apps.leading_fees.models.ListingLeading.PaymentStatus.choices",
        "PayoutStatusEnum":
            "apps.payments.models.Payout.Status.choices",
        "WaitingListStatusEnum":
            "apps.waiting_list.models.WaitingListEntry.Status.choices",
        "UserAccountTypeEnum":
            "apps.accounts.models.User.AccountType.choices",
    },
}

# Docs are PUBLIC by default. Flip RESTRICT_DOCS=True in .env to lock down.
if not DEBUG and env_bool("RESTRICT_DOCS", True):
    SPECTACULAR_SETTINGS["SERVE_PERMISSIONS"] = [
        "rest_framework.permissions.IsAdminUser",
    ]

# ---------------- EMAIL ----------------
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = env_int("EMAIL_PORT", 587)
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "SokoMkononi <info@sokomkononi.co.tz>")

if not DEBUG and not EMAIL_HOST:
    raise ImproperlyConfigured("EMAIL_HOST must be set when DEBUG=False.")

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "info@sokomkononi.co.tz")
ADMINS = [("SokoMkononi Admin", ADMIN_EMAIL)]
MANAGERS = ADMINS

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
APPLE_CLIENT_ID = os.environ.get("APPLE_CLIENT_ID", "")
PYNEXTSMS_TOKEN = os.environ.get("PYNEXTSMS_TOKEN", "")
PYNEXTSMS_SENDER_ID = os.environ.get("PYNEXTSMS_SENDER_ID", "")

# ---------------- FIMIPAY PAYMENTS ----------------
FIMIPAY_SECRET_KEY = os.environ.get("FIMIPAY_SECRET_KEY", "")
FIMIPAY_WEBHOOK_SECRET = os.environ.get("FIMIPAY_WEBHOOK_SECRET", "")
FIMIPAY_BASE_URL = "https://fimipay.com/api/v1"
FIMIPAY_CURRENCY = os.environ.get("FIMIPAY_CURRENCY", "TZS")

if not DEBUG and not FIMIPAY_SECRET_KEY:
    raise ImproperlyConfigured("FIMIPAY_SECRET_KEY must be set when DEBUG=False.")
if not DEBUG and not FIMIPAY_WEBHOOK_SECRET:
    raise ImproperlyConfigured("FIMIPAY_WEBHOOK_SECRET must be set when DEBUG=False.")


# ---------------- CELERY ----------------
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 10 * 60
CELERY_TASK_SOFT_TIME_LIMIT = 8 * 60
CELERY_RESULT_EXPIRES = 60 * 60 * 24
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

CELERY_BEAT_SCHEDULE = {
    "purge-soft-deleted": {"task": "core.purge_soft_deleted", "schedule": crontab(hour=3, minute=0)},
    "expire-stale-reservations": {"task": "transactions.expire_stale_reservations", "schedule": crontab(minute="*/15")},
    "expire-unpaid-reservations": {"task": "transactions.expire_unpaid_reservations", "schedule": crontab(minute="*/10")},
    "expire-stale-inspections": {"task": "transactions.expire_stale_inspections", "schedule": crontab(minute="*/15")},
    "warn-expiring-reservations": {"task": "transactions.warn_expiring_reservations", "schedule": crontab(minute=0)},
    "expire-stale-boosts": {"task": "boosting.expire_stale_boosts", "schedule": crontab(minute="*/15")},
    "expire-stale-banners": {"task": "banners.expire_stale_banners", "schedule": crontab(minute="*/15")},
    "expire-stale-credits": {"task": "credits.expire_stale_credits", "schedule": crontab(hour=2, minute=30)},
    "cleanup-stale-services": {"task": "credits.cleanup_stale_services", "schedule": crontab(hour=2, minute=45)},
    "refresh-pending-payouts": {
        "task": "payments.refresh_pending_payouts",
        "schedule": crontab(minute="*/10"),
    },
        "expire-stale-leading": {"task": "leading_fees.expire_stale_leading", "schedule": crontab(minute="*/15")},
    "cleanup-otp": {"task": "accounts.cleanup_old_otps", "schedule": crontab(hour=2, minute=15)},
    "cleanup-outstanding-tokens": {"task": "accounts.cleanup_expired_tokens", "schedule": crontab(hour=2, minute=25)},
}

# ---------------- SECURITY (prod) ----------------
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST = True
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 300
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = False
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
    SECURE_REFERRER_POLICY = "same-origin"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"verbose": {"format": "[{levelname}] {asctime} {name}:{lineno} — {message}", "style": "{"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "verbose"}},
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
        "django.security": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "csp": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "celery": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "apps": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}

# ---------------- SENTRY (optional) ----------------
SENTRY_DSN = os.environ.get("SENTRY_DSN", "")
if SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.django import DjangoIntegration
        from sentry_sdk.integrations.celery import CeleryIntegration
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=[DjangoIntegration(), CeleryIntegration()],
            traces_sample_rate=float(os.environ.get("SENTRY_TRACES_RATE", "0.1")),
            send_default_pii=False,
            environment=os.environ.get("SENTRY_ENV", "production" if not DEBUG else "local"),
        )
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Sentry init failed")


# ---------------- CSRF COOKIE ----------------
# The SPA must be able to read the CSRF cookie (js-cookie, axios xsrfCookieName).
# If you keep the access token in a cookie, the SPA also needs to send
# X-CSRFToken back on unsafe methods.
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = not DEBUG
