"""accounts.User contract tests — Phase 2 builds auth endpoints on these guarantees."""

import pytest
from django.db import IntegrityError, transaction

from apps.accounts.models import User

pytestmark = pytest.mark.django_db


class TestUserManager:
    def test_create_user_normalizes_email_to_lowercase(self):
        user = User.objects.create_user("MixedCase@Example.COM", "S0me-Long-Passw0rd!")
        assert user.email == "mixedcase@example.com"
        assert user.is_active is True
        assert user.is_staff is False
        assert user.check_password("S0me-Long-Passw0rd!")

    def test_create_user_without_email_raises(self):
        with pytest.raises(ValueError):
            User.objects.create_user("", "whatever")

    def test_create_superuser_sets_flags(self):
        user = User.objects.create_superuser("admin@example.com", "S0me-Long-Passw0rd!")
        assert user.is_staff is True
        assert user.is_superuser is True

    def test_create_superuser_rejects_false_flags(self):
        with pytest.raises(ValueError):
            User.objects.create_superuser("admin@example.com", "x", is_staff=False)


class TestEmailUniqueness:
    def test_exact_duplicate_email_rejected(self):
        User.objects.create_user("dup@example.com", "S0me-Long-Passw0rd!")
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                User.objects.create_user("dup@example.com", "S0me-Long-Passw0rd!")

    def test_case_insensitive_duplicate_email_rejected(self):
        """The uq_user_email_lower constraint is the T2.2 guarantee."""
        User.objects.create_user("dup@example.com", "S0me-Long-Passw0rd!")
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                User.objects.create_user("DUP@EXAMPLE.COM", "S0me-Long-Passw0rd!")
