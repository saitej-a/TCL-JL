"""Category vocabulary + feed card shape (04 §31-§32; 5.2 D1, D4, R3).

These prove the *surface* decisions: the settings-held 12-category union is
readable through the API with no migration, the card carries §31's shape, and
`comment_count` includes tombstones (D4) so the card matches the thread.
"""

import pytest

from apps.community.models import Post
from apps.community.validators import post_categories

pytestmark = pytest.mark.django_db

LIST_URL = "/api/v1/community/posts/"


def test_category_union_served_from_settings(api, settings):
    """The 12-item merged union (5.1 D1) is what the API validates against."""
    keys = {key for key, _label in post_categories()}
    assert len(keys) == 12
    assert {"LOCATION", "DOCUMENTS", "OFFER_LETTER", "TCS_PROCESS", "HELP"} <= keys
    response = api.get(LIST_URL, {"category": "OFFER_LETTER"})
    assert response.status_code == 200


def test_unknown_category_filter_404(api, auth_api):
    """04 §31's error contract: unknown category value → 404 invalid_category."""
    client, _user = auth_api()
    response = client.get(LIST_URL, {"category": "NOT_A_REAL_CATEGORY"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "invalid_category"


def test_feed_readable_without_authentication(anon_api, make_post):
    """9.3 D1 supersession: the feed is public (05 §3.1 routes /community to ALL
    roles; 04 §6 lists "Public posts" under Anonymous). This test previously
    asserted 401 — that encoded the pre-D1 contract, and the route table had
    already promised visitors a readable feed. Writes remain authenticated
    (test_read_access.py pins the 401 wall on every write surface)."""
    make_post()
    response = anon_api.get(LIST_URL)
    assert response.status_code == 200
    assert response.json()["results"][0]["has_voted"] is False


def test_unverified_user_reads_like_a_visitor_writes_are_blocked(api, make_user, make_post, settings):
    """P5 superseded for reads by 9.3 D1, preserved for writes.

    The original test asserted 403 on GET — the verified wall once covered the
    whole surface because anonymous reads were not offered at all. With reads
    public (05 §3.1's matrix), an authenticated-but-unverified account sees
    exactly what a visitor sees, so a GET 403 would now disclose nothing except
    that the surface once differed. P5's substance — unverified candidates do
    not PARTICIPATE — is the part that stays: the write wall is asserted below.
    """
    settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["community_writes"] = "1000/min"
    user = make_user(is_verified=False)
    api.force_authenticate(user=user)
    make_post()
    assert api.get(LIST_URL).status_code == 200  # reads: same as anonymous
    response = api.post(
        LIST_URL, {"title": "t", "body": "b", "category": "GENERAL"}, format="json"
    )
    assert response.status_code == 403  # participation: still verified-only


def test_feed_card_shape(api, auth_api, make_post):
    """04 §31's card: author via the redaction boundary + avatar seed, counts,
    no email, tombstone fields exposed for the UI."""
    _client, author = auth_api()
    make_post(author=author)
    response = api.get(LIST_URL)
    assert response.status_code == 200
    card = response.json()["results"][0]
    assert set(
        [
            "id",
            "author",
            "title",
            "body",
            "category",
            "is_pinned",
            "is_locked",
            "is_deleted",
            "vote_count",
            "comment_count",
            "has_voted",
            "created_at",
            "updated_at",
        ]
    ) == set(card)
    author_payload = card["author"]
    assert set(author_payload) == {
        "id",
        "display_name",
        "batch",
        "hiring_type",
        "region",
        "avatar_seed",
    }
    assert "email" not in author_payload
    assert 0 <= author_payload["avatar_seed"] <= 9


def test_comment_count_includes_tombstones(api, auth_api, make_post, make_comment):
    """D4: the card's number matches the thread the reader actually opens —
    a soft-deleted comment still counts on the card."""
    _client, author = auth_api()
    post = make_post(author=author)
    comment = make_comment(post, author=author)
    comment.is_deleted = True
    comment.save(update_fields=["is_deleted", "updated_at"])
    response = api.get(LIST_URL)
    assert response.json()["results"][0]["comment_count"] == 1


def test_search_narrows_case_insensitively(api, auth_api, make_post):
    _client, author = auth_api()
    make_post(author=author, title="Joining letter timeline")
    make_post(author=author, title="Completely different")
    response = api.get(LIST_URL, {"search": "joining"})
    assert response.status_code == 200
    assert response.json()["count"] == 1


def test_pagination_ignores_client_page_size(api, auth_api, make_post, settings):
    """04 §9's controlled maximum: no page_size_query_param means a client
    ?page_size= is ignored — same reasoning as 4.2's list route."""
    _client, author = auth_api()
    for index in range(25):
        make_post(author=author, title=f"post {index}")
    response = api.get(LIST_URL, {"page_size": "100"})
    assert response.status_code == 200
    assert len(response.json()["results"]) == 20
    assert response.json()["count"] == 25


def test_deleted_posts_absent_from_feed(api, auth_api, make_post, make_orm_post):
    """P9's feed half: soft-deleted posts leave the listing (03 §28).

    Asserted by **id**: the serializer masks a deleted card's title into the
    tombstone text, so the original title-based assertion passed even while
    feed_queryset happily returned tombstones — exactly the vacuous coverage
    9.3 D2 repaired. Reverting the `is_deleted` filter fails the first two
    assertions again."""
    client, author = auth_api()
    keep = make_post(author=author, title="kept")
    gone = make_post(author=author, title="gone")
    gone.is_deleted = True
    gone.save(update_fields=["is_deleted", "updated_at"])
    response = api.get(LIST_URL)
    ids = [row["id"] for row in response.json()["results"]]
    assert str(keep.id) in ids
    assert str(gone.id) not in ids
    # Search narrows within live posts only — same filter, same proof (the DB
    # row keeps its original title, so without the filter `search=gone` would
    # surface the masked tombstone card).
    searched = api.get(LIST_URL, {"search": "gone"})
    assert [row["id"] for row in searched.json()["results"]] == []
    assert Post.objects.filter(title="gone").exists()  # row retained (08 §390)
