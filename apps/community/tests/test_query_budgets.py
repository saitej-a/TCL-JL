"""COMM-08 as a regression guard, not a hope (5.2 R5).

The budgets pin the *ceiling*, not the exact SQL: the feed is ≤3 queries
(count + page + the filtered has-voted prefetch — authors ride the page query
via select_related), trending stays inside the same ceiling, the comment
thread is ≤5 (post + top-level count + page + replies + the envelope's
`total_comments`, which is one more query than the plan's 4 because D4's
card-parity number counts replies and tombstones too). If anyone adds a
per-row query later, these fail with the number in hand.
"""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

pytestmark = pytest.mark.django_db

LIST_URL = "/api/v1/community/posts/"


def _count_queries(client, url) -> tuple[int, int]:
    with CaptureQueriesContext(connection) as ctx:
        response = client.get(url)
    return response.status_code, len(ctx.captured_queries)


def test_feed_budget_3_queries(api, auth_api, make_post, make_comment, make_vote):
    _client, author = auth_api()
    post = make_post(author=author)
    make_comment(post, author=author)
    make_vote(author, post)
    reader_client, _reader = auth_api()
    status_code, query_count = _count_queries(reader_client, LIST_URL)
    assert status_code == 200
    assert query_count <= 3, f"feed exceeded 3-query budget: {query_count}"


def test_trending_budget_3_queries(api, auth_api, make_post, make_comment):
    _client, author = auth_api()
    post = make_post(author=author)
    make_comment(post, author=author)
    reader_client, _reader = auth_api()
    status_code, query_count = _count_queries(reader_client, f"{LIST_URL}?tab=trending")
    assert status_code == 200
    assert query_count <= 3, f"trending exceeded 3-query budget: {query_count}"


def test_comment_thread_budget_4_queries(api, auth_api, make_post, make_comment):
    _client, author = auth_api()
    post = make_post(author=author)
    top = make_comment(post, author=author)
    make_comment(post, author=author, parent=top)
    make_comment(post, author=author)
    reader_client, _reader = auth_api()
    status_code, query_count = _count_queries(
        reader_client, f"/api/v1/community/posts/{post.id}/comments/"
    )
    assert status_code == 200
    assert query_count <= 5, f"comment thread exceeded 5-query budget: {query_count}"


def test_throttle_scope_registered(settings):
    """R7's scope exists and reads the settings rate (04 §41/§42)."""
    assert settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["community_writes"] == "30/min"
