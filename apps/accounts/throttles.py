"""Throttle classes for the auth surface (06 §7.2).

Login uses a combined IP+email bucket so distributed credential stuffing
against one account cannot ride under per-IP limits, while a single client
testing several passwords cannot lock out the whole IP for other accounts.
"""

from rest_framework.throttling import ScopedRateThrottle


class LoginRateThrottle(ScopedRateThrottle):
    """``auth_login`` scope keyed on (IP, email) — 5/min (06 §7.1/§7.2)."""

    scope = "auth_login"

    def get_cache_key(self, request, view):
        email = (request.data.get("email") or "").strip().lower()
        ident = self.get_ident(request)
        return self.cache_format % {
            "scope": self.scope,
            "ident": f"{ident}_{email}",
        }


class RegisterRateThrottle(ScopedRateThrottle):
    """``auth_register`` scope — 3/hour (06 §7.1)."""

    scope = "auth_register"


class PasswordResetRateThrottle(ScopedRateThrottle):
    """``auth_password_reset`` scope — 3/hour (06 §7.1)."""

    scope = "auth_password_reset"


class VerifyResendRateThrottle(ScopedRateThrottle):
    """``auth_verify_resend`` scope — 1/min (06 §2.5/§7.1)."""

    scope = "auth_verify_resend"
