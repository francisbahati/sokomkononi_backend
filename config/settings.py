from datetime import timedelta
from pathlib import Path
import os

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(
    BASE_DIR / ".env"
)


SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "django-insecure-change-this-in-development",
)


DEBUG = (
    os.getenv(
        "DEBUG",
        "False",
    ).lower()
    == "true"
)


ALLOWED_HOSTS = os.getenv(
    "ALLOWED_HOSTS",
    "127.0.0.1,localhost",
).split(",")


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "rest_framework",
    "drf_spectacular",
    "rest_framework_simplejwt.token_blacklist",

    "apps.accounts",
    "apps.categories",
    "apps.listings",
    "apps.deals",
    "apps.transactions",
    "apps.waiting_list",
    "apps.notifications",
    "apps.boosting",
    "apps.finance",
]


MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",

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
        "BACKEND": (
            "django.template.backends.django.DjangoTemplates"
        ),
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                (
                    "django.template.context_processors.request"
                ),
                (
                    "django.contrib.auth.context_processors.auth"
                ),
                (
                    "django.contrib.messages.context_processors.messages"
                ),
            ],
        },
    },
]


WSGI_APPLICATION = "config.wsgi.application"

ASGI_APPLICATION = "config.asgi.application"


DATABASES = {
    "default": {
        "ENGINE": (
            "django.db.backends.postgresql"
        ),
        "NAME": os.getenv("DB_NAME"),
        "USER": os.getenv("DB_USER"),
        "PASSWORD": os.getenv("DB_PASSWORD"),
        "HOST": os.getenv(
            "DB_HOST",
            "127.0.0.1",
        ),
        "PORT": os.getenv(
            "DB_PORT",
            "5432",
        ),
    }
}


AUTH_USER_MODEL = "accounts.User"


AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        )
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator"
        )
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        )
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        )
    },
]


LANGUAGE_CODE = "en-us"

TIME_ZONE = "Africa/Dar_es_Salaam"

USE_I18N = True

USE_TZ = True


STATIC_URL = "static/"

STATIC_ROOT = (
    BASE_DIR / "staticfiles"
)


MEDIA_URL = "/media/"

MEDIA_ROOT = (
    BASE_DIR / "media"
)


DEFAULT_AUTO_FIELD = (
    "django.db.models.BigAutoField"
)


REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": (
        "drf_spectacular.openapi.AutoSchema"
    ),

    "DEFAULT_AUTHENTICATION_CLASSES": [
        (
            "rest_framework_simplejwt.authentication."
            "JWTAuthentication"
        ),
    ],

    "DEFAULT_PERMISSION_CLASSES": [
        (
            "rest_framework.permissions."
            "IsAuthenticated"
        ),
    ],
}


SPECTACULAR_SETTINGS = {
    "TITLE": "SokoMkononi API",

    "DESCRIPTION": (
        "API ya SokoMkononi — jukwaa la "
        "kidijitali la kununua na kuuza "
        "mali na bidhaa."
    ),

    "VERSION": "1.0.0",

    "SERVE_INCLUDE_SCHEMA": False,

    "COMPONENT_SPLIT_REQUEST": True,

    "SWAGGER_UI_SETTINGS": {
        "persistAuthorization": True,
    },
}


SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=30
    ),

    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=7
    ),

    "ROTATE_REFRESH_TOKENS": True,

    "BLACKLIST_AFTER_ROTATION": True,
}


# ============================================================
# EMAIL — GOOGLE / GMAIL SMTP
# ============================================================

EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.smtp.EmailBackend",
)

EMAIL_HOST = os.getenv(
    "EMAIL_HOST",
    "smtp.gmail.com",
)

EMAIL_PORT = int(
    os.getenv("EMAIL_PORT", "587")
)

EMAIL_USE_TLS = os.getenv(
    "EMAIL_USE_TLS",
    "True",
).lower() == "true"

EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")

EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")

DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL",
    "SokoMkononi <sokomkononi80@gmail.com>",
)


# ============================================================
# NEXTSMS
# ============================================================

PYNEXTSMS_TOKEN = os.getenv(
    "PYNEXTSMS_TOKEN"
)

PYNEXTSMS_SENDER_ID = os.getenv(
    "PYNEXTSMS_SENDER_ID"
)