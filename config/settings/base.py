"""Shared Django settings (T1.3-T1.6).

Env parsing is done directly from os.environ (no python-dotenv dependency);
docker-compose injects env_file/.env.prod values into container environments.
"""

import os
import ssl
import urllib.parse
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# --- Core -------------------------------------------------------------------
_IS_LOCAL = os.environ.get("DJANGO_SETTINGS_MODULE", "").endswith("local")

# Dev fallback only — production.py hard-requires the env var; local/test set their own.
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "insecure-dev-key-do-not-use-outside-local")

DEBUG = False  # only local.py flips this
ALLOWED_HOSTS = [h for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if h]

# Origin used to build links inside outbound email (verify / password reset).
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost")

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
    "apps.candidates.apps.CandidatesConfig",
    "apps.timeline.apps.TimelineConfig",
    "apps.community.apps.CommunityConfig",
    "apps.notifications.apps.NotificationsConfig",
    "apps.analytics.apps.AnalyticsConfig",
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
        "OPTIONS": {
            "sslmode": os.environ.get("POSTGRES_SSLMODE", "prefer"),
            # psycopg3 skips server-side prepared statements; required behind
            # transaction poolers (Neon's -pooler host) and harmless elsewhere.
            "prepare_threshold": None,
        },
    }
}

# Managed Postgres providers (Vercel/Neon) inject a single DATABASE_URL; it takes
# precedence over the discrete POSTGRES_* variables when present.
_DATABASE_URL = os.environ.get("DATABASE_URL", "")
if _DATABASE_URL:
    _db_url = urllib.parse.urlparse(_DATABASE_URL)
    _db_query = dict(urllib.parse.parse_qsl(_db_url.query))
    DATABASES["default"].update(
        {
            "NAME": _db_url.path.lstrip("/") or DB_NAME,
            "USER": urllib.parse.unquote(_db_url.username or DB_USER),
            "PASSWORD": urllib.parse.unquote(_db_url.password or DB_PASSWORD),
            "HOST": _db_url.hostname or DB_HOST,
            "PORT": str(_db_url.port or DB_PORT),
        }
    )
    DATABASES["default"]["OPTIONS"]["sslmode"] = _db_query.get(
        "sslmode", os.environ.get("POSTGRES_SSLMODE", "prefer")
    )

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"

# Candidate cohort years (PROF-01 via 3.1 D3). Extend via settings, not migrations.
BATCH_YEARS = ["2024", "2025", "2026"]

# Reserved display-name tokens (T3.7 via 3.2 D3). Extend via settings, no deploy.
RESERVED_DISPLAY_NAME_TOKENS = ["TCS", "Tata", "HR", "Admin", "Official", "Moderator"]

# --- Timeline / dashboard (Phase 4.2) -------------------------------------------
# 04 §53 recommended initial privacy threshold. When fewer than this many
# candidate profiles exist, the dashboard's analytics block is suppressed rather
# than exposing a micro-cohort (a raw count of 1 is personal data). Read at call
# time so ops can tune it without a deploy.
ANALYTICS_MIN_COHORT_SIZE = 5

# D3 future-date horizon for timeline events: event_date may not exceed
# today + this many days (730 ≈ 24 months). JOINING_DATE is legitimately future;
# JOINING_LETTER is separately restricted to present-or-past in the serializer.
TIMELINE_FUTURE_HORIZON_DAYS = 730

# --- Community posting (Phase 5.1, 5.1 D1) --------------------------------------
# Post categories: the merged union of 01 §7 (product), 03 §9 and T5.1 (task spec),
# with 01's OFFER_LETTER spelling kept so the vocabulary matches TimelineEvent's
# event types (Phase 7 analytics filters both). Read at call time (like
# BATCH_YEARS) so adding a category needs no migration and no deploy — 01 §7:
# "Categories should be extensible". 5.2's GET /posts/categories/ serves these
# same keys + labels, so this list is the single source of truth.
POST_CATEGORIES = [
    ("GENERAL", "General"),
    ("JOINING_LETTER", "Joining Letter"),
    ("OFFER_LETTER", "Offer Letter"),
    ("JOINING_DATE", "Joining Date"),
    ("LOCATION", "Location"),
    ("INTERVIEW", "Interview"),
    ("DOCUMENTS", "Documents"),
    ("DISCUSSION", "Discussion"),
    ("TCS_PROCESS", "TCS Process"),
    ("HELP", "Help"),
    ("ANNOUNCEMENT", "Announcements"),
    ("OTHER", "Other"),
]

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
# Serverless targets (Vercel) have no long-lived worker process: tasks execute
# inline in the request instead of being queued. See CELERY_TASK_ALWAYS_EAGER env.
CELERY_TASK_ALWAYS_EAGER = os.environ.get("CELERY_TASK_ALWAYS_EAGER", "0") == "1"

CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/1")
CELERY_RESULT_BACKEND = os.environ.get(
    "CELERY_RESULT_BACKEND", "redis://redis:6379/2"
)  # D-05 partitioning: results live in redis db2
# Managed Redis (Upstash) hands out rediss:// URLs; Celery does not infer TLS
# parameters from the scheme, so pass them explicitly next to the URL.
if CELERY_BROKER_URL.startswith("rediss://"):
    CELERY_BROKER_USE_SSL = {"ssl_cert_reqs": ssl.CERT_REQUIRED}
if CELERY_RESULT_BACKEND.startswith("rediss://"):
    CELERY_REDIS_BACKEND_USE_SSL = {"ssl_cert_reqs": ssl.CERT_REQUIRED}
if CELERY_TASK_ALWAYS_EAGER:
    # Eager results are returned in-process and never read back, so keep them
    # in-process too — no network/TLS round-trip per task-bearing request.
    # Celery consults the CELERY_RESULT_BACKEND *environment variable* before
    # Django settings, so clear it here or the override would be ignored.
    CELERY_RESULT_BACKEND = "cache+memory://"
    os.environ.pop("CELERY_RESULT_BACKEND", None)
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
STATIC_URL = "/static/"
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
        # Community write scopes (04 §41/§42; plan 05-02 R7)
        "community_writes": "30/min",
        # Notifications & device scopes (Phase 6.2 — 07 §10)
        "device_registration": "10/hour",
        "notifications_reads": "60/min",
    },
}

# --- Community (Phase 5.2 / plan 05-02) --------------------------------------------
# D1/R1: trending = activity score (votes + comments) within a settings-held
# window. The window *filters* — a post with zero in-window activity never
# occupies the tab — so an empty tab means genuinely nothing happened.
TRENDING_WINDOW_DAYS = 14

# D2 avatar seed: HMAC(secret, candidate_id) % palette_size. Falls back to
# SECRET_KEY — a documented trade-off, since rotating SECRET_KEY would silently
# recolour every anonymous avatar (05 §60's "discussions remain followable").
# Ops can pin AVATAR_SEED_SECRET independently when that stability matters.
AVATAR_SEED_SECRET = os.environ.get("DJANGO_AVATAR_SEED_SECRET", "") or SECRET_KEY

# --- Email (console in dev; SMTP injected in real deployments) ----------------------
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "no-reply@tcsjoiningtracker.local"

# --- Security headers (baseline; production.py hardens further) ---------------------
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# --- Notifications & push (Phase 6.2) ------------------------------------------------
PUSH_BACKEND = os.environ.get("PUSH_BACKEND", "auto")  # firebase | recording | auto (R: D1)
FIREBASE_CREDENTIALS_PATH = os.environ.get("FIREBASE_CREDENTIALS_PATH", "")
VOTE_MILESTONE_THRESHOLDS = [10, 25, 50, 100, 250, 500]  # §10, read at call time (D4)
THREAD_PUSH_DEBOUNCE_SECONDS = 900  # §10.1, read at call time (D3)
PUSH_MAX_RETRIES = int(os.environ.get("PUSH_MAX_RETRIES", "3"))
