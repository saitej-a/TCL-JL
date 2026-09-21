"""CITEXT email column tests (CONTEXT.md gate: wrong-case lookup returns the user)."""

import pytest
from django.db import IntegrityError, transaction

from apps.accounts.models import User

pytestmark = pytest.mark.django_db


class TestCitextLookups:
    def test_wrong_case_lookup_returns_user(self):
        User.objects.create_user("Case@Test.COM", "Correct Horse Battery 9!")
        # citext proof: the WHERE clause uses different case than any stored value;
        # the DB folds the comparison and still matches.
        found = User.objects.get(email="case@test.com")
        # Stored value is normalized lowercase by the manager before citext sees it.
        assert found.email == "case@test.com"

    def test_iexact_and_exact_agree_on_citext(self):
        User.objects.create_user("Fold@Test.COM", "Correct Horse Battery 9!")
        exact = User.objects.get(email="FOLD@test.com")
        iexact = User.objects.get(email__iexact="fold@TEST.com")
        assert exact.pk == iexact.pk


class TestCitextUniqueness:
    def test_case_changed_email_still_unique(self):
        User.objects.create_user("dup@example.com", "Correct Horse Battery 9!")
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                User.objects.create_user("DUP@EXAMPLE.COM", "Correct Horse Battery 9!")

    def test_update_that_only_changes_case_collides(self):
        User.objects.create_user("keep@example.com", "Correct Horse Battery 9!")
        User.objects.create_user("move@example.com", "Correct Horse Battery 9!")
        user = User.objects.get(email="move@example.com")
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                user.email = "KEEP@EXAMPLE.COM"  # citext column: value-equal collision
                user.save(update_fields=["email"])
