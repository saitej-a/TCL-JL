"""Avatar seed (5.2 D2 / 05 §60; plan R2).

Four properties pinned: determinism (discussions stay followable), palette
bounds, **uncomputability** (a client with the public profile UUID cannot
derive the colour without the server secret — the whole point of the HMAC),
and safe rendering for profile-less authors.
"""

import pytest

from apps.community.serializers import AVATAR_PALETTE_SIZE, avatar_seed

pytestmark = pytest.mark.django_db


def test_seed_stable_for_same_candidate(make_user):
    """Deterministic across calls — 05 §60's followability requirement."""
    first = avatar_seed("some-candidate-uuid")
    second = avatar_seed("some-candidate-uuid")
    assert first == second


def test_seed_within_palette_bounds():
    for index in range(50):
        seed = avatar_seed(f"candidate-{index}")
        assert 0 <= seed < AVATAR_PALETTE_SIZE


def test_seed_distinct_across_candidates():
    seeds = {avatar_seed(f"candidate-{index}") for index in range(30)}
    assert len(seeds) > 1  # not a constant in disguise


def test_seed_uncomputable_without_secret(settings):
    """The public UUID alone must not reveal the colour: changing the secret
    changes every seed, so a client-side reimplementation has nothing to work
    from (the 'internal random salt' reading of 05 §60)."""
    settings.AVATAR_SEED_SECRET = "secret-one"
    seeds_one = [avatar_seed(f"candidate-{index}") for index in range(20)]
    settings.AVATAR_SEED_SECRET = "secret-two"
    seeds_two = [avatar_seed(f"candidate-{index}") for index in range(20)]
    assert seeds_one != seeds_two


def test_seed_none_candidate_safe():
    """Profile-less authors render with a constant seed — no crash (3.2's
    None-safety rule carried into the community surface)."""
    assert isinstance(avatar_seed(None), int)


def test_author_payload_seed_matches_helper(api, auth_api, make_post):
    """The rendered seed is exactly `avatar_seed(profile_id)` — no parallel
    implementation in the serializer layer. (A profile-less author — the usual
    state here, since profiles are created in 3.2's flow, not these fixtures —
    renders the constant None-seed without crashing.)"""
    _client, author = auth_api()
    make_post(author=author)
    response = api.get("/api/v1/community/posts/")
    card = response.json()["results"][0]
    profile = getattr(author, "candidate_profile", None)
    expected = avatar_seed(profile.pk if profile is not None else None)
    assert card["author"]["avatar_seed"] == expected
