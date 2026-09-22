"""Report endpoint tests (Phase 8.1 — MOD-03, 04 §63–§66, T8.3).

Covers the 04 §64/§65 contract, dedup envelopes, tombstone-reportability, the
429 throttle proof (view-level scope), and the T-08.1-02 response-shape rules.
"""

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.moderation.models import Report

pytestmark = pytest.mark.django_db


@pytest.fixture
def api():
    return APIClient()


def _auth(api, user):
    api.force_authenticate(user=user)


class TestReportContract:
    def test_anonymous_refused(self, api, post):
        response = api.post(
            "/api/v1/reports/",
            {"post_id": str(post.id), "reason": "SPAM"},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_report_post_created(self, api, reporter, post):
        _auth(api, reporter)
        response = api.post(
            "/api/v1/reports/",
            {"post_id": str(post.id), "reason": "MISINFORMATION", "description": "rumor"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["status"] == "PENDING"
        assert response.data["message"] == "Report submitted successfully."
        # T-08.1-02: id/status/message only.
        assert set(response.data.keys()) == {"id", "status", "message"}

    def test_report_comment_created(self, api, reporter, comment):
        _auth(api, reporter)
        response = api.post(
            "/api/v1/reports/",
            {"comment_id": str(comment.id), "reason": "ABUSIVE_CONTENT"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_both_targets_rejected(self, api, reporter, post, comment):
        _auth(api, reporter)
        response = api.post(
            "/api/v1/reports/",
            {"post_id": str(post.id), "comment_id": str(comment.id), "reason": "SPAM"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_neither_target_rejected(self, api, reporter):
        _auth(api, reporter)
        response = api.post("/api/v1/reports/", {"reason": "SPAM"}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_unknown_reason_rejected(self, api, reporter, post):
        _auth(api, reporter)
        response = api.post(
            "/api/v1/reports/",
            {"post_id": str(post.id), "reason": "NOT_A_REASON"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_tombstoned_post_still_reportable(self, api, reporter, post):
        post.is_deleted = True
        post.save(update_fields=["is_deleted"])
        _auth(api, reporter)
        response = api.post(
            "/api/v1/reports/",
            {"post_id": str(post.id), "reason": "SCAM"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED


class TestDuplicateReports:
    def test_duplicate_pending_report_returns_400(self, api, reporter, post):
        _auth(api, reporter)
        first = api.post(
            "/api/v1/reports/", {"post_id": str(post.id), "reason": "SPAM"}, format="json"
        )
        assert first.status_code == status.HTTP_201_CREATED
        second = api.post(
            "/api/v1/reports/", {"post_id": str(post.id), "reason": "SCAM"}, format="json"
        )
        assert second.status_code == status.HTTP_400_BAD_REQUEST
        assert second.data["error"]["code"] == "duplicate_report"

    def test_after_dismissal_re_report_succeeds(self, api, reporter, post):
        _auth(api, reporter)
        api.post("/api/v1/reports/", {"post_id": str(post.id), "reason": "SPAM"}, format="json")
        report = Report.objects.get(reporter=reporter)
        report.status = Report.ReportStatus.DISMISSED
        report.save(update_fields=["status", "updated_at"])
        again = api.post(
            "/api/v1/reports/", {"post_id": str(post.id), "reason": "SPAM"}, format="json"
        )
        assert again.status_code == status.HTTP_201_CREATED

    def test_race_integrity_error_maps_to_duplicate_envelope(
        self, api, reporter, post, monkeypatch
    ):
        _auth(api, reporter)
        from apps.moderation import services, views

        def race(*args, **kwargs):
            raise services.DuplicateReportError(
                "You already have a pending report for this content."
            )

        monkeypatch.setattr(views.services, "create_report", race)
        response = api.post(
            "/api/v1/reports/", {"post_id": str(post.id), "reason": "SPAM"}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"]["code"] == "duplicate_report"


class TestThrottleEngagement:
    def test_report_throttled_after_ten_per_hour(self, api, reporter, post, settings):
        """The 7.2 R1 proof: if `throttle_scope` were missing from the view, every
        request would pass and this test would fail with a 201 on the 11th call."""
        settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["reports"] = "10/hour"
        _auth(api, reporter)
        codes = []
        for _ in range(11):
            response = api.post(
                "/api/v1/reports/", {"post_id": str(post.id), "reason": "SPAM"}, format="json"
            )
            codes.append(response.status_code)
        # 1st is a 201; 2..10 hit dedup (400 duplicate_report — still counted by
        # the throttle bucket); the 11th must be refused as 429, not processed.
        assert codes[0] == status.HTTP_201_CREATED
        assert codes[-1] == status.HTTP_429_TOO_MANY_REQUESTS
