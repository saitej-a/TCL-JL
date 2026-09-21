"""Test settings: fast, isolated, deterministic.

- Speeds up Argon2 to validation-only cost (never used outside tests).
- Console email backend; in-memory channels files.
- Celery stays eager=False but tests exercise tasks synchronously via .apply()
  where needed in later phases.
"""

from .base import *  # noqa: F401,F403

SECRET_KEY = "test-only-insecure-key"  # noqa: S105

DEBUG = False
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]

# MD5-first keeps the bulk suite fast; the real Argon2id hasher stays registered so
# hashing-policy tests can invoke it explicitly and verify argon2id hashes.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
    "apps.accounts.hashers.Argon2idHasher",
]
ARGON2_ARGS = {"time_cost": 1, "memory_cost": 8192, "parallelism": 1}

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "test-cache",
    }
}
