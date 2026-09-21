"""Hardened production settings (D-03/D-04). Phase 10.2 adds full TLS/CSP polish."""

import os

from .base import *  # noqa: F401,F403

DEBUG = False

# Hard gate: production must never boot on a fallback key.
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    raise RuntimeError("DJANGO_SECRET_KEY must be set in the deployment environment.")

# Behind nginx (compose) or the Vercel edge proxy; hosts come from deployment env.
# The ".vercel.app" wildcard keeps preview-deployment hostnames working.
ALLOWED_HOSTS = [
    h for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,.vercel.app").split(",") if h
]

# --- TLS-terminating proxy ------------------------------------------------
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# --- Production email via injected SMTP env vars -----------------------------
# Without EMAIL_HOST (e.g. a first deploy before SMTP creds exist), fall back to
# the console backend so eager task emails log instead of failing the request.
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
if EMAIL_HOST:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "true").lower() != "false"

# --- Origins (Phase 9 SPA + Vercel deployments) -------------------------------
CORS_ALLOWED_ORIGINS = [o for o in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",") if o]
CSRF_TRUSTED_ORIGINS = [
    o for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "https://*.vercel.app").split(",") if o
]
