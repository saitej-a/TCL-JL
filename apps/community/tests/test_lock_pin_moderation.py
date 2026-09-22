"""Lock / pin — moderator control (04 §38; 5.2 P8; plan's unlock/unpin addition).

P8's split: the author owns their *words* (edit/delete), but lock/pin is
moderator power — an author cannot lock their own thread against other
candidates. `/unlock/` and `/unpin/` are this plan's documented additions
beyond 04 §37 (08's reversibility principle).
"""

import pytest

pytestmark = pytest.mark.django_db


def lock_url(post) -> str:
    return f"/api/v1/community/posts/{post.id}/lock/"


def pin_url(post) -> str:
    return f"/api/v1/community/posts/{post.id}/pin/"


def test_author_cannot_lock_own_thread(api, auth_api, make_post):
    """P8: lock is not an author power, even on your own post."""
    client, author = auth_api()
    post = make_post(author=author)
    response = client.post(lock_url(post))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "moderator_only"
    post.refresh_from_db()
    assert post.is_locked is False


def test_staff_can_lock_and_unlock(api, staff_api, make_post):
    client, _staff = staff_api()
    post = make_post()
    lock = client.post(lock_url(post))
    assert lock.status_code == 200
    assert lock.json()["is_locked"] is True
    post.refresh_from_db()
    assert post.is_locked is True
    unlock = client.delete(lock_url(post))
    assert unlock.status_code == 200
    assert unlock.json()["is_locked"] is False


def test_staff_can_pin_and_unpin(api, staff_api, make_post):
    client, _staff = staff_api()
    post = make_post()
    pin = client.post(pin_url(post))
    assert pin.status_code == 200
    assert pin.json()["is_pinned"] is True
    unpin = client.delete(pin_url(post))
    assert unpin.status_code == 200
    assert unpin.json()["is_pinned"] is False


def test_lock_blocks_new_comments(api, auth_api, make_post, staff_api, make_comment):
    """The lock's purpose, end to end: staff locks → comments refuse (04 §42)."""
    author_client, author = auth_api()
    post = make_post(author=author)
    make_comment(post, author=author)  # pre-lock comment survives
    mod_client, _mod = staff_api()
    mod_client.post(lock_url(post))
    response = author_client.post(
        f"/api/v1/community/posts/{post.id}/comments/", {"body": "late"}, format="json"
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "post_locked"


def test_pin_surfacing_in_feed_order(api, auth_api, make_orm_post, staff_api):
    """A pinned post leads the feed regardless of recency (03 §17's order)."""
    _author_client, author = auth_api()
    old = make_orm_post(author=author, title="old")
    make_orm_post(author=author, title="new")
    mod_client, _mod = staff_api()
    mod_client.post(pin_url(old))
    response = api.get("/api/v1/community/posts/")
    titles = [row["title"] for row in response.json()["results"]]
    assert titles == ["old", "new"]


def test_lock_on_deleted_post_404(api, staff_api, make_post):
    client, _staff = staff_api()
    post = make_post()
    post.is_deleted = True
    post.save(update_fields=["is_deleted"])
    response = client.post(lock_url(post))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "content_deleted"
