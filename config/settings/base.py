"""Shared Django settings (T1.3-T1.6).

Env parsing is done directly from os.environ (no python-dotenv dependency);
docker-compose injects env_file/.env.prod values into container environments.
"""

import os
from datetime import timedelta

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# --- Core -------------------------------------------------------------------
_IS_LOCAL = os.environ.get("DJANGO_SETTINGS_MODULE", "").endswith("local")

# Dev fallback only — production.py hard-requires the env var; local/test set their own.
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "insecure-dev-key-do-not-use-outside-local")

DEBUG = False  # only local.py flips this
ALLOWED_HOSTS = [h for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if h]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",  # refresh-token revocation (06 §3.4)
    "corsheaders",
    # Project apps (09 §3.1 app boundaries)
    "apps.accounts.apps.AccountsConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
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
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# --- Database (T1.4) ----------------------------------------------------------
DB_USER = os.environ.get("POSTGRES_USER", "tcs_tracker")
DB_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "")
DB_NAME = os.environ.get("POSTGRES_DB", "tcs_joining_tracker")
DB_HOST = os.environ.get("POSTGRES_HOST", "db")
DB_PORT = os.environ.get("POSTGRES_PORT", "5432")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": DB_NAME,
        "USER": DB_USER,
        "PASSWORD": DB_PASSWORD,
        "HOST": DB_HOST,
        "PORT": DB_PORT,
        "CONN_MAX_AGE": 600,  # 09 §8 persistent connections
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {"sslmode": os.environ.get("POSTGRES_SSLMODE", "prefer")},
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"

# --- Passwords (T2.3) -----------------------------------------------------------
# First hasher = what set_password()/create_user() emit (the registration path).
# Argon2idHasher pins T2.3's cost params: 64 MiB memory, 3 iterations, 2 threads.
PASSWORD_HASHERS = [
    "apps.accounts.hashers.Argon2idHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
]

# --- Password validation (T2.4 complexity rules) --------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "apps.accounts.validation.ComplexityPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

# --- Redis partitioning (T1.5, D-05): db0 cache/throttle, db1 broker, db2 results
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        "KEY_PREFIX": "tcsjl",
    }
}
SESSION_ENGINE = "django.contrib.sessions.backends.cache"

# --- Celery (T1.6) -------------------------------------------------------------
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/1")
CELERY_RESULT_BACKEND = os.environ.get(
    "CELERY_RESULT_BACKEND", "redis://redis:6379/2"
)  # D-05 partitioning: results live in redis db2
CELERY_TASK_ALWAYS_EAGER = False
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_QUEUES = {
    "default": {"exchange": "default", "routing_key": "default"},
    "notifications": {"exchange": "notifications", "routing_key": "notifications"},
    "maintenance": {"exchange": "maintenance", "routing_key": "maintenance"},
}
CELERY_TASK_ROUTES = {
    "notifications.tasks.send_push_notification": {"queue": "notifications"},
    "notifications.tasks.broadcast_announcement": {"queue": "notifications"},
    "accounts.tasks.send_verification_email": {"queue": "default"},
    "accounts.tasks.send_password_reset_email": {"queue": "default"},
    "notifications.tasks.prune_stale_devices": {"queue": "maintenance"},
}
CELERY_TIMEZONE = "UTC"

# --- i18n / tz -----------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# --- Static & media --------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# --- JWT (06 §3.1/§3.2; T2.7) -------------------------------------------------------
# Access carries UUID + is_verified only — never email/PII (06 §3.1.1).
# SIGNING_KEY: dedicated secret, falls back to SECRET_KEY when JWT_SECRET_KEY is unset.
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": os.environ.get("JWT_SECRET_KEY", SECRET_KEY),
    "AUDIENCE": "https://tracker.internal/api",
    "ISSUER": "tcs-joining-tracker-auth",
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# --- Password reset token lifetime (06 §3.5) -----------------------------------------
PASSWORD_RESET_TIMEOUT = 3600  # 60 minutes

# --- DRF (Phases 2-8 fill this out) ------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_RATES": {
        # Auth scopes (06 §7.1)
        "auth_login": "5/min",
        "auth_register": "3/hour",
        "auth_password_reset": "3/hour",
        "auth_verify_resend": "1/min",
    },  # community/device scopes land in Phases 5/6/8
}

# --- Email (console in dev; SMTP injected in real deployments) ----------------------
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "no-reply@tcsjoiningtracker.local"

# --- Security headers (baseline; production.py hardens further) ---------------------
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
