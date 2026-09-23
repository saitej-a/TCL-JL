"""Anonymous community reads (9.3 D1 — 05 §3.1's public-read matrix).

The SPA has routed /community and post detail to ALL roles since 9.1 (05 §3.1:
"All (Public Read)"), but the shipped views answered 401 — the route table and
the API disagreed. D1 opens GET on the four read surfaces (feed list, post
detail, comment list, comment detail) to anonymous callers and bounds the new
surface with a per-IP read bucket. Every write keeps the verified-candidate
wall: the opening is per-method (`get_permissions`), never a global permission
relaxation, because the shared class-level list also guards writes.

The throttle tests follow the 7.2 R1 discipline: prove the bucket *engages*
(429 past the rate), do not merely prove a rate exists in settings — a rate
nobody enforces is exactly the inert-throttle failure mode the project has
already hit twice.
"""

import pytest

from apps.community.throttles import CommunityAnonReadRateThrottle

pytestmark = pytest.mark.django_db

LIST_URL = "/api/v1/community/posts/"


def _detail_url(post) -> str:
    return f"{LIST_URL}{post.id}/"


def _comments_url(post) -> str:
    return f"{LIST_URL}{post.id}/comments/"


# --- Anonymous reads succeed -------------------------------------------------


def test_anonymous_can_list_feed(anon_api, make_post):
    make_post()
    response = anon_api.get(LIST_URL)
    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) == 1
    # An anonymous card carries no private state: has_voted is a plain False.
    assert results[0]["has_voted"] is False


def test_anonymous_can_read_post_detail(anon_api, make_post):
    post = make_post()
    response = anon_api.get(_detail_url(post))
    assert response.status_code == 200
    assert response.json()["id"] == str(post.id)


def test_anonymous_can_read_post_detail_tombstone(anon_api, auth_api, make_post):
    """P9's read half holds for visitors too: a tombstone stays readable."""
    _client, author = auth_api()
    post = make_post(author=author)
    post.is_deleted = True
    post.save(update_fields=["is_deleted", "updated_at"])
    response = anon_api.get(_detail_url(post))
    assert response.status_code == 200
    assert response.json()["is_deleted"] is True


def test_anonymous_can_list_comments(anon_api, auth_api, make_post, make_comment):
    _client, author = auth_api()
    post = make_post(author=author)
    make_comment(post, author=author, body="A visitor reads this.")
    response = anon_api.get(_comments_url(post))
    assert response.status_code == 200
    assert response.json()["results"][0]["body"] == "A visitor reads this."


# --- Writes stay sealed ------------------------------------------------------


def test_anonymous_cannot_create_post(anon_api, settings):
    settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["community_writes"] = "1000/min"
    response = anon_api.post(
        LIST_URL, {"title": "t", "body": "b", "category": "GENERAL"}, format="json"
    )
    assert response.status_code == 401


def test_anonymous_cannot_vote(anon_api, make_post, settings):
    post = make_post()
    settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["community_writes"] = "1000/min"
    response = anon_api.post(f"{_detail_url(post)}vote/")
    assert response.status_code == 401


def test_anonymous_cannot_comment(anon_api, make_post, settings):
    post = make_post()
    settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["community_writes"] = "1000/min"
    response = anon_api.post(_comments_url(post), {"body": "hi"}, format="json")
    assert response.status_code == 401


def test_anonymous_cannot_edit_or_delete_post(anon_api, make_post, settings):
    post = make_post()
    settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["community_writes"] = "1000/min"
    assert anon_api.patch(_detail_url(post), {"title": "x"}, format="json").status_code == 401
    assert anon_api.delete(_detail_url(post)).status_code == 401


# --- The anonymous read bucket engages (7.2 R1 discipline) -------------------


def test_anon_read_rate_registered(settings):
    assert (
        settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["community_anon_reads"] == "120/min"
    )


def test_anon_read_throttle_engages(anon_api, make_post, settings):
    """The bucket really 429s: shrink the rate, exceed it as a visitor.

    The rate mutation here is safe because the root conftest's autouse fixture
    restores DEFAULT_THROTTLE_RATES after every test (in-place dict edits are
    not reverted by pytest-django), and each test starts with an empty throttle
    cache — so this test measures its own traffic, not another test's residue."""
    settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["community_anon_reads"] = "2/min"
    make_post()
    codes = [anon_api.get(LIST_URL).status_code for _ in range(3)]
    assert codes[:2] == [200, 200]
    assert codes[2] == 429


def test_authenticated_reads_unthrottled(api, make_post, settings):
    """5.2's browsing contract survives D1: signed-in reads never hit the bucket."""
    settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["community_anon_reads"] = "1/min"
    make_post()
    codes = [api.get(LIST_URL).status_code for _ in range(4)]
    assert codes == [200, 200, 200, 200]


def test_throttle_scope_registered_in_settings(settings):
    """The rate registry must know every scope the views declare (the inverse of
    the 7.2 R1 inert-scope trap: a declared scope with no rate 500s a request)."""
    rates = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
    assert CommunityAnonReadRateThrottle.scope in rates


# --- The write bucket engages (D4, 7.2 R1 discipline) ------------------------


def test_write_throttle_engages(api, settings):
    """D4's proof: shrinking the write rate really 429s a verified author.

    Before 9.3 the six write views carried CommunityWriteRateThrottle with no
    view-level scope — inert (ScopedRateThrottle allows everything when the
    view declares no scope) — and PostListCreateView carried no throttle at
    all. Attachment is not enforcement; this pins engagement."""
    settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["community_writes"] = "3/min"
    codes = []
    for index in range(4):
        response = api.post(
            LIST_URL,
            {
                "title": f"write throttle probe {index}",
                "body": f"distinct body {index}",
                "category": "GENERAL",
            },
            format="json",
        )
        codes.append(response.status_code)
    assert codes[:3] == [201, 201, 201]
    assert codes[3] == 429
