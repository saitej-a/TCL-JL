"""Vote endpoint (04 §43; 5.2 — 409 already_voted; 5.1's DB constraint).

The unique constraint is the *real* guarantee (5.1 criterion 3); this suite
pins that the API translates it: duplicate → 409 `already_voted`, never a 500,
whether the duplicate is a clean second POST or hits the constraint directly.
"""

import pytest
from django.db import IntegrityError

from apps.community.models import PostVote

pytestmark = pytest.mark.django_db


def vote_url(post) -> str:
    return f"/api/v1/community/posts/{post.id}/vote/"


def test_vote_201_shape(api, auth_api, make_post):
    client, author = auth_api()
    post = make_post(author=author)
    response = client.post(vote_url(post))
    assert response.status_code == 201
    body = response.json()
    assert body["vote_count"] == 1
    assert PostVote.objects.filter(user=author, post=post).exists()


def test_duplicate_vote_409(api, auth_api, make_post):
    client, author = auth_api()
    post = make_post(author=author)
    first = client.post(vote_url(post))
    assert first.status_code == 201
    second = client.post(vote_url(post))
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "already_voted"
    assert PostVote.objects.filter(post=post).count() == 1


def test_duplicate_vote_via_orm_hits_constraint(make_user, make_post):
    """The DB constraint, not the API, is the law (5.1 criterion 3)."""
    user = make_user()
    post = make_post(author=user)
    PostVote.objects.create(user=user, post=post)
    with pytest.raises(IntegrityError):
        PostVote.objects.create(user=user, post=post)


def test_unvote_204(api, auth_api, make_post):
    client, author = auth_api()
    post = make_post(author=author)
    client.post(vote_url(post))
    response = client.delete(vote_url(post))
    assert response.status_code == 204
    assert PostVote.objects.filter(post=post).count() == 0


def test_unvote_without_vote_404(api, auth_api, make_post):
    client, author = auth_api()
    post = make_post(author=author)
    response = client.delete(vote_url(post))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "vote_not_found"


def test_vote_on_deleted_post_404(api, auth_api, make_post):
    """P9: tombstones accept no votes."""
    client, author = auth_api()
    post = make_post(author=author)
    client.delete(f"/api/v1/community/posts/{post.id}/")
    response = client.post(vote_url(post))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "content_deleted"


def test_vote_on_foreign_post_allowed(api, auth_api, make_post):
    """Voting on someone else's post is the point of the community (P5)."""
    _author_client, author = auth_api()
    post = make_post(author=author)
    voter_client, _voter = auth_api()
    response = voter_client.post(vote_url(post))
    assert response.status_code == 201


def test_has_voted_flag_true_for_own_vote(api, auth_api, make_post):
    client, author = auth_api()
    post = make_post(author=author)
    client.post(vote_url(post))
    feed = client.get("/api/v1/community/posts/")
    card = feed.json()["results"][0]
    assert card["has_voted"] is True
    other_client, _other = auth_api()
    card_other = other_client.get("/api/v1/community/posts/").json()["results"][0]
    assert card_other["has_voted"] is False


def test_vote_toggles_card_count_for_everyone(api, auth_api, make_post):
    _client, author = auth_api()
    post = make_post(author=author)
    voter_client, _voter = auth_api()
    voter_client.post(vote_url(post))
    response = api.get("/api/v1/community/posts/")
    assert response.json()["results"][0]["vote_count"] == 1
