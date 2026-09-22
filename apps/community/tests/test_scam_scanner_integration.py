"""Scanner + debounce integration tests (Phase 8.1 — all four call sites).

Exercises the HTTP surface: post create/edit, comment create/edit — asserting
the 400 `scam_pattern_detected` envelope carries the category message and never
the pattern, that edit-path scanning sees merged state, and that the debounce
guards post creation only (comments never, edits never).
"""

import pytest
from rest_framework import status
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db

SCAM_BODY = "Join my telegram group @tcsoffers for paid letters"
BENIGN_TITLE = "Joining letter updates?"
BENIGN_BODY = "Anyone from the 2026 batch still waiting?"


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def poster(make_user):
    return make_user()


@pytest.fixture
def auth_api(api, poster):
    api.force_authenticate(user=poster)
    return api


class TestPostCreateScanning:
    def test_scam_post_blocked_with_category_message(self, auth_api):
        response = auth_api.post(
            "/api/v1/community/posts/",
            {"title": "Offer", "body": SCAM_BODY, "category": "GENERAL"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"]["code"] == "scam_pattern_detected"
        assert "fee solicitation" in response.data["error"]["message"].lower()
        assert "telegram" not in response.data["error"]["message"].lower()

    def test_benign_post_still_created(self, auth_api):
        response = auth_api.post(
            "/api/v1/community/posts/",
            {"title": BENIGN_TITLE, "body": BENIGN_BODY, "category": "GENERAL"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED


class TestPostEditScanning:
    def test_post_edit_blocked_when_body_becomes_scam(self, auth_api, make_post, poster):
        post = make_post(author=poster)
        response = auth_api.patch(
            f"/api/v1/community/posts/{post.id}/", {"body": SCAM_BODY}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"]["code"] == "scam_pattern_detected"
        post.refresh_from_db()
        assert post.body != SCAM_BODY

    def test_clean_edit_still_succeeds(self, auth_api, make_post, poster):
        post = make_post(author=poster)
        response = auth_api.patch(
            f"/api/v1/community/posts/{post.id}/",
            {"body": "Edited but perfectly clean content."},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK


class TestCommentScanning:
    def test_scam_comment_blocked(self, auth_api, make_post, poster):
        post = make_post(author=poster)
        response = auth_api.post(
            f"/api/v1/community/posts/{post.id}/comments/",
            {"body": SCAM_BODY},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"]["code"] == "scam_pattern_detected"

    def test_scam_comment_edit_blocked(self, auth_api, make_post, make_comment, poster):
        post = make_post(author=poster)
        comment = make_comment(post=post, author=poster)
        response = auth_api.patch(
            f"/api/v1/community/comments/{comment.id}/", {"body": SCAM_BODY}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        comment.refresh_from_db()
        assert comment.body != SCAM_BODY

    def test_comments_never_debounced(self, auth_api, make_post, poster):
        post = make_post(author=poster)
        body = "The same comment twice is fine."
        first = auth_api.post(
            f"/api/v1/community/posts/{post.id}/comments/", {"body": body}, format="json"
        )
        second = auth_api.post(
            f"/api/v1/community/posts/{post.id}/comments/", {"body": body}, format="json"
        )
        assert first.status_code == status.HTTP_201_CREATED
        assert second.status_code == status.HTTP_201_CREATED


class TestDuplicatePostDebounce:
    def test_identical_title_blocked_within_window(self, auth_api):
        payload = {"title": BENIGN_TITLE, "body": BENIGN_BODY, "category": "GENERAL"}
        first = auth_api.post("/api/v1/community/posts/", payload, format="json")
        second = auth_api.post("/api/v1/community/posts/", payload, format="json")
        assert first.status_code == status.HTTP_201_CREATED
        assert second.status_code == status.HTTP_400_BAD_REQUEST
        assert second.data["error"]["code"] == "duplicate_post"

    def test_identical_body_new_title_blocked(self, auth_api):
        body = BENIGN_BODY
        first = auth_api.post(
            "/api/v1/community/posts/",
            {"title": "First title", "body": body, "category": "GENERAL"},
            format="json",
        )
        second = auth_api.post(
            "/api/v1/community/posts/",
            {"title": "Second title", "body": body, "category": "GENERAL"},
            format="json",
        )
        assert first.status_code == status.HTTP_201_CREATED
        assert second.status_code == status.HTTP_400_BAD_REQUEST
        assert second.data["error"]["code"] == "duplicate_post"

    def test_different_content_not_blocked(self, auth_api):
        first = auth_api.post(
            "/api/v1/community/posts/",
            {"title": BENIGN_TITLE, "body": BENIGN_BODY, "category": "GENERAL"},
            format="json",
        )
        second = auth_api.post(
            "/api/v1/community/posts/",
            {"title": "A different question", "body": "Region 62 anyone?", "category": "GENERAL"},
            format="json",
        )
        assert first.status_code == status.HTTP_201_CREATED
        assert second.status_code == status.HTTP_201_CREATED

    def test_post_edits_never_debounced(self, auth_api, make_post, poster):
        post = make_post(author=poster, title="Editable", body="Original body")
        first = auth_api.patch(
            f"/api/v1/community/posts/{post.id}/", {"body": "First edit"}, format="json"
        )
        second = auth_api.patch(
            f"/api/v1/community/posts/{post.id}/", {"body": "First edit"}, format="json"
        )
        assert first.status_code == status.HTTP_200_OK
        assert second.status_code == status.HTTP_200_OK
