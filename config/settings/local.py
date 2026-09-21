"""Local development settings."""

from .base import *  # noqa: F401,F403

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "nginx", "web"]

# Dev convenience only — relaxed for placeholder/no-TLS local stack.
SECRET_KEY = "dev-only-insecure-key"  # noqa: S105
CELERY_TASK_ALWAYS_EAGER = False  # real broker exercised end-to-end in dev
