"""Announcement API tests (Phase 8.2 — 04 §71–§75)."""

import uuid
from datetime import timedelta
from unittest import mock

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.community.models import Announcement

pytestmark = pytest.mark.django_db

LIST_URL = "/api/v1/announcements/"
DETAIL_URL = "/api/v1/announcements/{id}/"
PUBLISH_URL = "/api/v1/announcements/{id}/publish/"
PASSWORD = "Str0ng!Passw0rd"


def _user(suffix: str, **overrides) -> User:
    defaults = dict(is_verified=True)
    defaults.update(overrides)
    return User.objects.create_user(
        f"annapi-{suffix}-{uuid.uuid4().hex[:8]}@example.com", PASSWORD, **defaults
    )


@pytest.fixture
def staff_client(db):
    client = APIClient()
    client.force_authenticate(user=_user("staff", is_staff=True))
    return client


@pytest.fixture
def candidate_client(db):
    client = APIClient()
    client.force_authenticate(user=_user("cand"))
    return client


@pytest.fixture
def published(staff_client):
    announcement = Announcement.objects.create(
        created_by=_user("author", is_staff=True),
        title="Live advisory",
        body="Community update.",
        is_published=True,
        published_at=timezone.now(),
    )
    return announcement


class TestPublicRead:
    def test_anonymous_sees_only_published_and_unexpired(self, published):
        Announcement.objects.create(title="Draft", body="...")  # unpublished
        Announcement.objects.create(
            title="Expired",
            body="...",
            is_published=True,
            published_at=timezone.now() - timedelta(days=3),
            expires_at=timezone.now() - timedelta(days=1),
        )
        anonymous = APIClient()
        response = anonymous.get(LIST_URL)
        assert response.status_code == 200
        body = response.json()
        titles = [row["title"] for row in body["results"]]
        assert titles == ["Live advisory"]

    def test_public_shape_has_no_staff_fields(self, published):
        response = APIClient().get(LIST_URL)
        row = response.json()["results"][0]
        assert set(row) == {"id", "title", "body", "is_pinned", "published_at", "expires_at"}
        assert "created_by" not in row
        assert "is_published" not in row

    def test_pinned_rows_sort_first(self, published):
        Announcement.objects.create(
            title="Pinned advisory",
            body="...",
            is_published=True,
            is_pinned=True,
            published_at=timezone.now() - timedelta(hours=1),
        )
        titles = [row["title"] for row in APIClient().get(LIST_URL).json()["results"]]
        assert titles == ["Pinned advisory", "Live advisory"]


class TestStaffWrites:
    def test_candidate_cannot_create(self, candidate_client):
        response = candidate_client.post(LIST_URL, {"title": "Nope", "body": "..."}, format="json")
        assert response.status_code == 403
        assert Announcement.objects.count() == 0

    def test_candidate_cannot_patch_or_delete(self, candidate_client, published):
        assert (
            candidate_client.patch(
                DETAIL_URL.format(id=published.id), {"title": "Hacked"}, format="json"
            ).status_code
            == 403
        )
        assert candidate_client.delete(DETAIL_URL.format(id=published.id)).status_code == 403

    def test_staff_creates_a_draft(self, staff_client):
        response = staff_client.post(
            LIST_URL,
            {"title": "New advisory", "body": "Draft body.", "is_pinned": True},
            format="json",
        )
        assert response.status_code == 201
        body = response.json()
        assert body["is_published"] is False
        assert body["published_at"] is None
        announcement = Announcement.objects.get(id=body["id"])
        assert announcement.is_pinned is True

    def test_draft_never_appears_publicly(self, staff_client):
        staff_client.post(LIST_URL, {"title": "Draft", "body": "..."}, format="json")
        assert APIClient().get(LIST_URL).json()["count"] == 0

    def test_unknown_id_is_json_404(self, staff_client):
        response = staff_client.patch(
            DETAIL_URL.format(id=uuid.uuid4()), {"title": "x"}, format="json"
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "announcement_not_found"

    def test_staff_deletes(self, staff_client, published):
        response = staff_client.delete(DETAIL_URL.format(id=published.id))
        assert response.status_code == 204
        assert not Announcement.objects.filter(pk=published.pk).exists()


class TestPublishLifecycle:
    def test_publish_endpoint_publishes_and_appears_publicly(self, staff_client):
        announcement = Announcement.objects.create(title="Soon live", body="...")
        with mock.patch("apps.community.tasks.broadcast_announcement_dispatch") as dispatch:
            response = staff_client.post(PUBLISH_URL.format(id=announcement.id), format="json")
        assert response.status_code == 202
        assert response.json()["detail"] == "broadcast scheduled"
        dispatch.assert_called_once_with(str(announcement.pk))

        announcement.refresh_from_db()
        assert announcement.is_published is True
        assert announcement.published_at is not None
        assert APIClient().get(LIST_URL).json()["count"] == 1

    def test_second_publish_does_not_rebroadcast(self, staff_client):
        announcement = Announcement.objects.create(title="Once", body="...")
        with mock.patch("apps.community.tasks.broadcast_announcement_dispatch"):
            staff_client.post(PUBLISH_URL.format(id=announcement.id), format="json")
        with mock.patch("apps.community.tasks.broadcast_announcement_dispatch") as dispatch:
            response = staff_client.post(PUBLISH_URL.format(id=announcement.id), format="json")
        assert response.status_code == 200
        assert response.json()["detail"] == "already published"
        dispatch.assert_not_called()

    def test_patch_publishes_when_flag_transitions(self, staff_client):
        announcement = Announcement.objects.create(title="Via patch", body="...")
        with mock.patch("apps.community.tasks.broadcast_announcement_dispatch") as dispatch:
            response = staff_client.patch(
                DETAIL_URL.format(id=announcement.id),
                {"is_published": True},
                format="json",
            )
        assert response.status_code == 200
        announcement.refresh_from_db()
        assert announcement.is_published is True
        dispatch.assert_called_once()

    def test_field_edit_on_published_row_does_not_rebroadcast(self, staff_client, published):
        with mock.patch("apps.community.tasks.broadcast_announcement_dispatch") as dispatch:
            response = staff_client.patch(
                DETAIL_URL.format(id=published.id), {"title": "Tweaked"}, format="json"
            )
        assert response.status_code == 200
        published.refresh_from_db()
        assert published.title == "Tweaked"
        dispatch.assert_not_called()
