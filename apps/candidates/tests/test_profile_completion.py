"""`compute_profile_completion` — the dashboard's completeness meter (T4.8, 4.2 R1).

The metric's most important property is a **privacy** one, not an arithmetic one:
`display_name` and `public_identity_mode` are deliberately excluded, so a
candidate who chooses ANONYMOUS (3.1 D1) is never told their profile is
incomplete for declining to identify themselves.
"""

from datetime import date

import pytest

from apps.candidates.models import CandidateProfile
from apps.candidates.services import (
    PROFILE_COMPLETION_FIELDS,
    PROFILE_COMPLETION_ITEMS,
    compute_profile_completion,
)

pytestmark = pytest.mark.django_db

S = CandidateProfile.Status


@pytest.fixture
def make_profile(db):
    def _make(**overrides) -> CandidateProfile:
        defaults = dict(
            user=None,
            batch="2025",
            hiring_type="DIGITAL",
            region="Telangana",
        )
        defaults.update(overrides)
        return CandidateProfile.objects.create(**defaults)

    return _make


def test_checklist_has_seven_items():
    assert PROFILE_COMPLETION_ITEMS == 7
    assert len(PROFILE_COMPLETION_FIELDS) == 5
    assert "display_name" not in PROFILE_COMPLETION_FIELDS
    assert "public_identity_mode" not in PROFILE_COMPLETION_FIELDS


def test_sparse_profile_is_zero(make_profile):
    assert compute_profile_completion(make_profile()) == 0


def test_each_enrichment_field_moves_the_meter(make_profile):
    for field in PROFILE_COMPLETION_FIELDS:
        value = date(2026, 5, 5) if field.endswith("_date") else "Somewhere"
        profile = make_profile(**{field: value})
        assert compute_profile_completion(profile) == round(100 / 7), field


def test_blank_strings_do_not_count(make_profile):
    profile = make_profile(interview_center="   ", joining_location="")

    assert compute_profile_completion(profile) == 0


def test_status_past_registered_counts(make_profile):
    assert compute_profile_completion(make_profile(current_status=S.INTERVIEWED)) == round(100 / 7)
    # WITHDRAWN is a decision the candidate made, not an absent profile field.
    assert compute_profile_completion(make_profile(current_status=S.WITHDRAWN)) == round(100 / 7)


def test_has_events_counts(make_profile):
    profile = make_profile()

    assert compute_profile_completion(profile, has_events=True) == round(100 / 7)
    assert compute_profile_completion(profile, has_events=False) == 0


def test_fully_satisfied_profile_is_one_hundred(make_profile):
    profile = make_profile(
        interview_center="Chennai",
        interview_date=date(2026, 3, 1),
        offer_letter_date=date(2026, 4, 1),
        joining_location="Bangalore",
        expected_joining_date=date(2026, 9, 1),
        current_status=S.JOINED,
    )

    assert compute_profile_completion(profile, has_events=True) == 100


def test_anonymous_candidate_can_still_reach_one_hundred(make_profile):
    """R1's privacy pin: anonymity must never look like incompleteness."""
    profile = make_profile(
        public_identity_mode=CandidateProfile.PublicIdentityMode.ANONYMOUS,
        display_name="",
        interview_center="Chennai",
        interview_date=date(2026, 3, 1),
        offer_letter_date=date(2026, 4, 1),
        joining_location="Bangalore",
        expected_joining_date=date(2026, 9, 1),
        current_status=S.JOINED,
    )

    assert compute_profile_completion(profile, has_events=True) == 100


def test_result_is_a_monotonic_integer(make_profile):
    """A pure function of the instance it is handed: filling a field can only
    move the meter up, and repeated calls are stable."""
    profile = make_profile(interview_center="Chennai")
    first = compute_profile_completion(profile)
    profile.joining_location = "Bangalore"

    values = [first, compute_profile_completion(profile), compute_profile_completion(profile)]

    assert all(isinstance(v, int) for v in values)
    assert values[0] < values[1] == values[2]
