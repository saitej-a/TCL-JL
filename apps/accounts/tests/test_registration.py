"""Registration endpoint tests (04 §12, 06 §2.4, D1 collision branch)."""

import pytest
from django.core import mail

from apps.accounts.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def eager_celery(settings):
    """Dispatches run synchronously so ``mail.outbox`` assertions hold."""
    settings.CELERY_TASK_ALWAYS_EAGER = True

REGISTER_URL = "/api/v1/auth/register/"
SUCCESS_MESSAGE = "Registration successful. Please check your email to activate your account."
VALID_PASSWORD = "Correct Horse Battery 9!"


@pytest.fixture
def post_register(client):
    def _post(payload):
        return client.post(
            REGISTER_URL,
            data=payload,
            content_type="application/json",
        )

    return _post


class TestRegistrationSuccess:
    def test_new_account_returns_generic_201(self, post_register):
        response = post_register(
            {"email": "new@example.com", "password": VALID_PASSWORD, "password_confirm": VALID_PASSWORD}
        )
        assert response.status_code == 201
        assert response.json() == {"message": SUCCESS_MESSAGE}
        user = User.objects.get(email="new@example.com")
        assert user.is_verified is False
        assert user.check_password(VALID_PASSWORD)
        # Verification email dispatched (Celery eager + on_commit).
        assert len(mail.outbox) == 1
        assert "Verify" in mail.outbox[0].subject

    def test_password_never_in_response(self, post_register):
        response = post_register(
            {"email": "no-leak@example.com", "password": VALID_PASSWORD, "password_confirm": VALID_PASSWORD}
        )
        assert VALID_PASSWORD not in response.content.decode()


class TestCollisionBranchD1:
    """Existing email → identical 201 + owner notified. No enumeration, ever."""

    def test_collision_returns_identical_body(self, post_register):
        User.objects.create_user("owner@example.com", VALID_PASSWORD)
        response = post_register(
            {"email": "owner@example.com", "password": VALID_PASSWORD, "password_confirm": VALID_PASSWORD}
        )
        assert response.status_code == 201
        assert response.json() == {"message": SUCCESS_MESSAGE}

    def test_collision_notifies_owner_and_creates_nothing(self, post_register):
        User.objects.create_user("owner@example.com", VALID_PASSWORD)
        mail.outbox.clear()
        post_register(
            {"email": "owner@example.com", "password": VALID_PASSWORD, "password_confirm": VALID_PASSWORD}
        )
        assert User.objects.filter(email="owner@example.com").count() == 1
        assert len(mail.outbox) == 1
        assert "registration attempt" in mail.outbox[0].subject.lower()

    def test_unknown_email_gets_same_body_but_no_email(self, post_register):
        mail.outbox.clear()
        response = post_register(
            {"email": "ghost@example.com", "password": VALID_PASSWORD, "password_confirm": VALID_PASSWORD}
        )
        assert response.status_code == 201
        assert response.json() == {"message": SUCCESS_MESSAGE}
        # Exactly one email (the verification), no collision notice.
        assert len(mail.outbox) == 1

    def test_collision_is_case_insensitive_via_citext(self, post_register):
        User.objects.create_user("CaseOwner@Example.com", VALID_PASSWORD)
        response = post_register(
            {"email": "caseowner@example.com", "password": VALID_PASSWORD, "password_confirm": VALID_PASSWORD}
        )
        assert response.status_code == 201
        assert response.json() == {"message": SUCCESS_MESSAGE}
        assert User.objects.filter(email="CaseOwner@Example.com").count() == 1


class TestRegistrationValidation:
    def test_password_mismatch_rejected(self, post_register):
        response = post_register(
            {"email": "mismatch@example.com", "password": VALID_PASSWORD, "password_confirm": "Different 123!"}
        )
        assert response.status_code == 400

    def test_weak_password_rejected_with_rule_code(self, post_register):
        response = post_register(
            {"email": "weak@example.com", "password": "alllowercase123!", "password_confirm": "alllowercase123!"}
        )
        assert response.status_code == 400
        assert "password_no_upper" in response.json()["password"]

    def test_common_password_rejected(self, post_register):
        response = post_register(
            {"email": "common@example.com", "password": "Password123!", "password_confirm": "Password123!"}
        )
        assert response.status_code == 400

    def test_invalid_email_rejected(self, post_register):
        response = post_register(
            {"email": "not-an-email", "password": VALID_PASSWORD, "password_confirm": VALID_PASSWORD}
        )
        assert response.status_code == 400

    def test_injected_is_staff_is_ignored(self, post_register):
        """06 §4.4 vertical escalation: staff flags can never be self-assigned."""
        response = post_register(
            {
                "email": "escalator@example.com",
                "password": VALID_PASSWORD,
                "password_confirm": VALID_PASSWORD,
                "is_staff": True,
                "is_superuser": True,
            }
        )
        assert response.status_code == 201
        user = User.objects.get(email="escalator@example.com")
        assert user.is_staff is False
        assert user.is_superuser is False
