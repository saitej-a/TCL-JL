"""Report model tests (Phase 8.1 — MOD-01/MOD-02, 08 §3.2/§3.3).

XOR and pending-dedup are DATABASE law: every constraint here is proven with a
raw `queryset.create` / `force_insert` that bypasses `save()`/`clean()`, so the
tests fail if the constraint exists only in Python.
"""

import pytest
from django.db import IntegrityError, transaction

from apps.moderation.models import Report

pytestmark = pytest.mark.django_db


def _raw_create(**kwargs):
    """Insert bypassing Model.save()/clean() — proves DB-level enforcement.

    `bulk_create` skips save() (and therefore clean()), so any refusal here
    comes from the database constraints themselves.
    """
    with transaction.atomic():
        Report.objects.bulk_create([Report(**kwargs)])


class TestXorExactlyOneTarget:
    def test_clean_rejects_both_targets(self, reporter, post, comment):
        report = Report(reporter=reporter, post=post, comment=comment, reason="SPAM")
        with pytest.raises(Exception, match="either a post or a comment"):
            report.clean()

    def test_clean_rejects_neither_target(self, reporter):
        report = Report(reporter=reporter, reason="SPAM")
        with pytest.raises(Exception, match="either a post or a comment"):
            report.clean()

    def test_db_refuses_both_targets(self, reporter, post, comment):
        with pytest.raises(IntegrityError):
            _raw_create(reporter=reporter, post=post, comment=comment, reason="SPAM")

    def test_db_refuses_neither_target(self, reporter):
        with pytest.raises(IntegrityError):
            _raw_create(reporter=reporter, reason="SPAM")

    def test_post_only_and_comment_only_are_legal(self, reporter, post, comment):
        Report.objects.create(reporter=reporter, post=post, reason="SPAM")
        Report.objects.create(reporter=reporter, comment=comment, reason="SCAM")
        assert Report.objects.count() == 2


class TestPendingDedupConstraints:
    def test_second_pending_report_on_same_post_refused_at_db(self, reporter, post):
        Report.objects.create(reporter=reporter, post=post, reason="SPAM")
        with pytest.raises(IntegrityError):
            _raw_create(reporter=reporter, post=post, reason="HARASSMENT")

    def test_second_pending_report_on_same_comment_refused_at_db(self, reporter, comment):
        Report.objects.create(reporter=reporter, comment=comment, reason="SPAM")
        with pytest.raises(IntegrityError):
            _raw_create(reporter=reporter, comment=comment, reason="OTHER")

    def test_non_pending_re_report_is_allowed(self, reporter, post):
        first = Report.objects.create(reporter=reporter, post=post, reason="SPAM")
        first.status = Report.ReportStatus.DISMISSED
        first.save(update_fields=["status", "updated_at"])
        second = Report.objects.create(reporter=reporter, post=post, reason="SCAM")
        assert second.status == Report.ReportStatus.PENDING

    def test_different_reporters_can_report_same_target(self, reporter, other_reporter, post):
        Report.objects.create(reporter=reporter, post=post, reason="SPAM")
        Report.objects.create(reporter=other_reporter, post=post, reason="SPAM")
        assert Report.objects.count() == 2


class TestCascadeTargets:
    def test_hard_deleting_post_deletes_its_reports(self, reporter, post):
        Report.objects.create(reporter=reporter, post=post, reason="SCAM")
        post.delete()
        assert Report.objects.count() == 0

    def test_hard_deleting_comment_deletes_its_reports(self, reporter, comment):
        Report.objects.create(reporter=reporter, comment=comment, reason="ABUSIVE_CONTENT")
        comment.delete()
        assert Report.objects.count() == 0


class TestSpecVocabulary:
    def test_reasons_match_08_section_3_1(self):
        assert set(Report.ReportReason.values) == {
            "SPAM",
            "HARASSMENT",
            "MISINFORMATION",
            "ABUSIVE_CONTENT",
            "PERSONAL_INFORMATION",
            "SCAM",
            "OTHER",
        }

    def test_statuses_match_08_section_3_2(self):
        assert set(Report.ReportStatus.values) == {"PENDING", "REVIEWED", "RESOLVED", "DISMISSED"}

    def test_migration_carries_all_three_constraints(self):
        from pathlib import Path

        import apps.moderation.migrations as mig_pkg

        migration_text = "\n".join(
            Path(mig_pkg.__file__)
            .parent.glob("0001_initial.py")
            .__iter__()
            .__next__()
            .read_text()
            .splitlines()
        )
        assert "report_exactly_one_target" in migration_text
        assert "unique_pending_report_per_post" in migration_text
        assert "unique_pending_report_per_comment" in migration_text
