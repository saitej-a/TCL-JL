"""Comment thread + creation (04 §39-§42; 5.2 D4, P9; 5.1 R1's service path).

`total_comments` includes tombstones (D4) so a card saying "7" never opens a
thread whose count says 3; `count` stays the honest top-level pagination count.
Locked posts refuse comments (`post_locked` 400); deleted posts refuse them
(`content_deleted` 404); the three model-level parent rules surface as 400s
from the 5.1 service.
"""

import pytest

pytestmark = pytest.mark.django_db


def comments_url(post) -> str:
    return f"/api/v1/community/posts/{post.id}/comments/"


def test_thread_shape_count_vs_total(api, auth_api, make_post, make_comment):
    """`count` = top-level rows on the page (tombstones included — P9 keeps
    them in the thread); `total_comments` = everything including replies (D4 —
    card parity)."""
    _client, author = auth_api()
    post = make_post(author=author)
    top1 = make_comment(post, author=author)
    top2 = make_comment(post, author=author)
    make_comment(post, author=author, parent=top1)  # a reply — not counted in `count`
    deleted = make_comment(post, author=author)
    deleted.is_deleted = True
    deleted.save(update_fields=["is_deleted", "updated_at"])

    client2, _reader = auth_api()
    response = client2.get(comments_url(post))
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 3  # top-level incl. the tombstone (P9)
    assert body["total_comments"] == 4  # + the reply
    top_ids = {row["id"] for row in body["results"]}
    assert top_ids == {str(top1.id), str(top2.id), str(deleted.id)}


def test_replies_nested_one_level(api, auth_api, make_post, make_comment):
    """04 §40: replies render under their parent; a reply never has children."""
    _client, author = auth_api()
    post = make_post(author=author)
    top = make_comment(post, author=author)
    reply = make_comment(post, author=author, parent=top)
    response = api.get(comments_url(post))
    assert response.status_code == 200
    (row,) = response.json()["results"]
    assert row["id"] == str(top.id)
    assert [r["id"] for r in row["replies"]] == [str(reply.id)]
    assert row["replies"][0]["replies"] == []


def test_tombstoned_comment_stays_in_thread_masked(api, auth_api, make_post, make_comment):
    """P9's thread half + D3: tombstones stay put, masked, author handle kept."""
    client, author = auth_api()
    post = make_post(author=author)
    comment = make_comment(post, author=author, body="to be removed")
    comment.is_deleted = True
    comment.save(update_fields=["is_deleted", "updated_at"])
    response = client.get(comments_url(post))
    (row,) = response.json()["results"]
    assert row["body"] == "This content has been removed."
    assert row["author"]["id"] == str(author.id)


def test_comment_on_locked_post_400(api, auth_api, make_post):
    """04 §42's request-context rule #1: locked posts accept no comments."""
    client, author = auth_api()
    post = make_post(author=author)
    post.is_locked = True
    post.save(update_fields=["is_locked"])
    response = client.post(comments_url(post), {"body": "let me in"}, format="json")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "post_locked"


def test_comment_on_deleted_post_404(api, auth_api, make_post):
    """P9: a tombstone accepts no comments — 404 content_deleted, not 400."""
    client, author = auth_api()
    post = make_post(author=author)
    client.delete(f"/api/v1/community/posts/{post.id}/")
    response = client.post(comments_url(post), {"body": "ghost"}, format="json")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "content_deleted"


def test_reply_to_reply_rejected_nested_reply(api, auth_api, make_post, make_comment):
    """04 §42's model rule #1 — nested replies are impossible."""
    client, author = auth_api()
    post = make_post(author=author)
    top = make_comment(post, author=author)
    reply = make_comment(post, author=author, parent=top)
    response = client.post(
        comments_url(post), {"body": "too deep", "parent_id": str(reply.id)}, format="json"
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "nested_reply"


def test_reply_across_posts_rejected(api, auth_api, make_post, make_comment):
    """04 §42's model rule #2 — the parent must belong to the same post."""
    client, author = auth_api()
    post_a = make_post(author=author, title="A")
    post_b = make_post(author=author, title="B")
    foreign_parent = make_comment(post_a, author=author)
    response = client.post(
        comments_url(post_b),
        {"body": "cross-post", "parent_id": str(foreign_parent.id)},
        format="json",
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "comment_not_found"


def test_reply_to_deleted_parent_rejected(api, auth_api, make_post, make_comment):
    """04 §42's model rule #3 — a tombstone parent accepts no replies."""
    client, author = auth_api()
    post = make_post(author=author)
    parent = make_comment(post, author=author)
    parent.is_deleted = True
    parent.save(update_fields=["is_deleted", "updated_at"])
    response = client.post(
        comments_url(post), {"body": "reply to ghost", "parent_id": str(parent.id)}, format="json"
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "parent_deleted"


def test_foreign_parent_uuid_404(api, auth_api, make_post):
    """Foreign or nonexistent parent: same verdict either way."""
    client, author = auth_api()
    post = make_post(author=author)
    import uuid

    response = client.post(
        comments_url(post),
        {"body": "orphan", "parent_id": str(uuid.uuid4())},
        format="json",
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "comment_not_found"


def test_edit_own_comment(api, auth_api, make_post, make_comment):
    client, author = auth_api()
    post = make_post(author=author)
    comment = make_comment(post, author=author, body="typo")
    response = client.patch(
        f"/api/v1/community/comments/{comment.id}/", {"body": "fixed"}, format="json"
    )
    assert response.status_code == 200
    comment.refresh_from_db()
    assert comment.body == "fixed"


def test_edit_foreign_comment_403(api, auth_api, make_post, make_comment):
    _client, author = auth_api()
    post = make_post(author=author)
    comment = make_comment(post, author=author)
    attacker_client, _attacker = auth_api()
    response = attacker_client.patch(
        f"/api/v1/community/comments/{comment.id}/", {"body": "hijack"}, format="json"
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "not_author"


def test_delete_own_comment_soft_and_reply_promotion(api, auth_api, make_post, make_comment):
    """COMM-05 + 5.1 P1: soft flag; the hard-delete promotion path is 5.1's."""
    client, author = auth_api()
    post = make_post(author=author)
    comment = make_comment(post, author=author, body="mine")
    response = client.delete(f"/api/v1/community/comments/{comment.id}/")
    assert response.status_code == 204
    comment.refresh_from_db()
    assert comment.is_deleted is True
    assert comment.body == "mine"


def test_anonymous_cannot_comment(anon_api, make_post):
    post = make_post()
    response = anon_api.post(comments_url(post), {"body": "anon"}, format="json")
    assert response.status_code == 401
