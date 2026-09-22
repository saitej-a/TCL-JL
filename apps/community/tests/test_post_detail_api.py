"""Post detail / create / edit / delete (04 §32, §35-§37; 5.2 P6, P9, D3, D4).

The contract split this phase deliberately makes against 4.2:

* foreign writes → **403 `not_author`** (the post exists publicly; enumeration
  secrecy doesn't apply to community content);
* writes into a tombstone → **404 `content_deleted`** (removed content is
  inert, not invisible);
* GET on a tombstone → **200 masked** through `display_*` (P9/D3).
"""

import pytest

from apps.community.models import Post

pytestmark = pytest.mark.django_db

LIST_URL = "/api/v1/community/posts/"


def detail_url(post) -> str:
    return f"/api/v1/community/posts/{post.id}/"


def test_create_returns_card_201(api, auth_api):
    client, author = auth_api()
    response = client.post(
        LIST_URL,
        {"title": "Badge collection day", "body": "When is it?", "category": "TCS_PROCESS"},
        format="json",
    )
    assert response.status_code == 201
    card = response.json()
    assert card["title"] == "Badge collection day"
    assert card["vote_count"] == 0
    assert card["comment_count"] == 0
    assert Post.objects.filter(title="Badge collection day").exists()


def test_create_rejects_invalid_category(api, auth_api):
    client, _author = auth_api()
    response = client.post(
        LIST_URL,
        {"title": "x", "body": "y", "category": "NOT_REAL"},
        format="json",
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_category"


def test_create_rejects_blank_body(api, auth_api):
    client, _author = auth_api()
    response = client.post(
        LIST_URL,
        {"title": "x", "body": "   ", "category": "HELP"},
        format="json",
    )
    assert response.status_code == 400


def test_anonymous_cannot_create(anon_api):
    response = anon_api.post(
        LIST_URL, {"title": "x", "body": "y", "category": "HELP"}, format="json"
    )
    assert response.status_code == 401


def test_detail_public_to_all_authenticated(api, auth_api, make_post):
    """P5: community posts are readable by every verified candidate."""
    _author_client, author = auth_api()
    post = make_post(author=author)
    reader_client, _reader = auth_api()
    response = reader_client.get(detail_url(post))
    assert response.status_code == 200
    assert response.json()["id"] == str(post.id)


def test_edit_foreign_post_403_not_404(api, auth_api, make_post):
    """P6's inversion of 4.2: foreign content exists publicly → 403."""
    _author_client, author = auth_api()
    post = make_post(author=author)
    attacker_client, _attacker = auth_api()
    response = attacker_client.patch(detail_url(post), {"title": "hijacked"}, format="json")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "not_author"
    post.refresh_from_db()
    assert post.title != "hijacked"


def test_edit_own_post_200(api, auth_api, make_post):
    client, author = auth_api()
    post = make_post(author=author)
    response = client.patch(detail_url(post), {"title": "edited"}, format="json")
    assert response.status_code == 200
    post.refresh_from_db()
    assert post.title == "edited"


def test_delete_foreign_post_403(api, auth_api, make_post):
    _author_client, author = auth_api()
    post = make_post(author=author)
    attacker_client, _attacker = auth_api()
    response = attacker_client.delete(detail_url(post))
    assert response.status_code == 403
    assert not Post.objects.get(id=post.id).is_deleted


def test_delete_own_post_soft(api, auth_api, make_post):
    """COMM-05: flag only — the row and its originals are retained (08 §390)."""
    client, author = auth_api()
    post = make_post(author=author, title="my words")
    response = client.delete(detail_url(post))
    assert response.status_code == 204
    post.refresh_from_db()
    assert post.is_deleted is True
    assert post.title == "my words"  # original retained for audit
    assert Post.objects.filter(id=post.id).exists()  # never a hard delete


def test_tombstone_detail_masked_but_readable(api, auth_api, make_post):
    """P9 + D3 + D4: detail 200s with the neutral tombstone copy and the author
    handle kept (the recorded 08 §406 deviation)."""
    client, author = auth_api()
    post = make_post(author=author, title="original title", body="original body")
    client.delete(detail_url(post))
    response = client.get(detail_url(post))
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "This content has been removed."
    assert body["body"] == "This content has been removed."
    assert body["author"]["id"] == str(author.id)  # handle kept (D3 deviation)
    assert body["is_deleted"] is True


def test_edit_tombstoned_own_post_404(api, auth_api, make_post):
    """A removed post stops accepting writes even from its author (P9)."""
    client, author = auth_api()
    post = make_post(author=author)
    client.delete(detail_url(post))
    response = client.patch(detail_url(post), {"title": "undead"}, format="json")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "content_deleted"


def test_malformed_uuid_404_in_envelope(api, auth_api):
    """F3 discipline: malformed identifiers land in the project envelope."""
    client, _author = auth_api()
    response = client.get("/api/v1/community/posts/not-a-uuid/")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "post_not_found"
