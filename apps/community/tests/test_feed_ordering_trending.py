"""Feed ordering, trending window, and the row-multiplication trap (5.2 D1, R1,
R3; 04 §31).

The multiplication test is the load-bearing one: counting two reverse FKs
without `distinct=True` joins and multiplies rows — 3 votes × 2 comments would
report 6/6 — and it passes a naive "no N+1" check, so it's pinned exactly.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.community.views import POST_ORDERINGS

pytestmark = pytest.mark.django_db

LIST_URL = "/api/v1/community/posts/"


def test_counts_exact_under_multiplication(api, auth_api, make_post, make_comment, make_vote):
    """3 votes × 2 comments must report 3/2, not 6/6 (COMM-08's hidden trap)."""
    _client, author = auth_api()
    post = make_post(author=author)
    make_comment(post, author=author)
    make_comment(post, author=author)
    voters = [auth_api()[1] for _ in range(3)]
    for voter in voters:
        make_vote(voter, post)
    response = api.get(LIST_URL)
    card = response.json()["results"][0]
    assert card["vote_count"] == 3
    assert card["comment_count"] == 2


def test_trending_window_filters_stale_posts(api, auth_api, make_orm_post, make_comment):
    """R1: the window *filters* — a post with zero in-window activity is absent
    from the tab, not ranked zero; a hot old post is excluded entirely."""
    client, author = auth_api()
    hot_old = make_orm_post(author=author, title="hot old")
    hot_old.created_at = timezone.now() - timedelta(days=20)
    hot_old.save(update_fields=["created_at"])
    make_comment(hot_old, author=author)  # has activity — but outside the window

    fresh_hot = make_orm_post(author=author, title="fresh hot")
    make_comment(fresh_hot, author=author)

    response = client.get(LIST_URL, {"tab": "trending"})
    titles = [row["title"] for row in response.json()["results"]]
    assert titles == ["fresh hot"]


def test_trending_orders_by_activity_then_newest(
    api, auth_api, make_orm_post, make_comment, make_vote
):
    client, author = auth_api()
    make_orm_post(author=author, title="quiet")  # no activity
    mid = make_orm_post(author=author, title="mid")
    make_comment(mid, author=author)  # 1 activity
    top = make_orm_post(author=author, title="top")
    make_comment(top, author=author)
    make_comment(top, author=author)
    make_vote(author, top)  # 3 activity
    response = client.get(LIST_URL, {"tab": "trending"})
    titles = [row["title"] for row in response.json()["results"]]
    assert titles == ["top", "mid", "quiet"]


def test_pinned_precedes_every_ordering(api, auth_api, make_post, make_orm_post, make_vote):
    """Pinned threads keep precedence in every §31 ordering (03 §17's index)."""
    client, author = auth_api()
    pinned_old = make_orm_post(author=author, title="pinned")
    pinned_old.is_pinned = True
    pinned_old.save(update_fields=["is_pinned"])
    hot = make_post(author=author, title="hot")
    make_vote(author, hot)
    for ordering in ("created_at", "-created_at", "vote_count", "-vote_count"):
        response = client.get(LIST_URL, {"ordering": ordering})
        titles = [row["title"] for row in response.json()["results"]]
        assert titles[0] == "pinned", ordering


def test_ordering_whitelist_enforced(api, auth_api):
    """04 §31's whitelist: unknown ordering fields 400 invalid_ordering."""
    client, _user = auth_api()
    response = client.get(LIST_URL, {"ordering": "author__email"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_ordering"


def test_tab_orderings_match_plan_matrix(api):
    """The route's admitted orderings are exactly the plan's pinned set."""
    assert set(POST_ORDERINGS) == {"newest", "oldest", "votes", "trending"}


def test_votes_tab_orders_by_score(api, auth_api, make_post, make_vote):
    client, author = auth_api()
    make_post(author=author, title="low")
    high = make_post(author=author, title="high")
    make_vote(author, high)
    response = client.get(LIST_URL, {"tab": "votes"})
    titles = [row["title"] for row in response.json()["results"]]
    assert titles == ["high", "low"]
