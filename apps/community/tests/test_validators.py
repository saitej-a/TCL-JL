"""Validators and the service error vocabulary (5.1 D1, R3, R4).

The category tests defend D1's *design*, not just its current list: the vocabulary
is read from settings at call time, so a new category must be accepted with no code
change and no migration — which is the only reason merging three disagreeing spec
lists into one list was workable.
"""

import pytest
from django.conf import settings
from django.core.exceptions import ValidationError
from django.test import override_settings

from apps.community.services import (
    InvalidCommentError,
    InvalidPostError,
    create_comment,
    create_post,
)
from apps.community.validators import (
    BLANK_CODE,
    CATEGORY_CODE,
    TITLE_LENGTH_CODE,
    TITLE_MAX_LENGTH,
    post_category_keys,
    validate_not_blank,
    validate_post_category,
    validate_title_length,
)

pytestmark = pytest.mark.django_db


def test_every_configured_category_is_accepted():
    for key in post_category_keys():
        validate_post_category(key)  # must not raise


def test_unknown_category_is_rejected():
    with pytest.raises(ValidationError) as exc:
        validate_post_category("NOT_A_CATEGORY")

    assert exc.value.code == CATEGORY_CODE


def test_category_matching_is_case_sensitive():
    """Keys are the API contract; 'joining_letter' is a different string and 5.2's
    filter must not have to guess."""
    with pytest.raises(ValidationError) as exc:
        validate_post_category("joining_letter")

    assert exc.value.code == CATEGORY_CODE


def test_missing_or_blank_category_is_rejected():
    for value in (None, "", "   "):
        with pytest.raises(ValidationError):
            validate_post_category(value)


def test_added_category_applies_without_a_migration():
    """01 §7's "categories should be extensible" — proven at call time, which is
    also why `Post.category` carries no `choices=` (see test_community_models)."""
    extended = [*settings.POST_CATEGORIES, ("CUSTOM", "Custom")]
    with override_settings(POST_CATEGORIES=extended):
        validate_post_category("CUSTOM")

    with pytest.raises(ValidationError):  # baseline restored
        validate_post_category("CUSTOM")


def test_blank_content_is_rejected():
    for value in (None, "", "   ", "\n\t"):
        with pytest.raises(ValidationError) as exc:
            validate_not_blank(value)
        assert exc.value.code == BLANK_CODE


def test_title_length_boundary():
    validate_title_length("x" * TITLE_MAX_LENGTH)  # exactly at the limit is fine

    with pytest.raises(ValidationError) as exc:
        validate_title_length("x" * (TITLE_MAX_LENGTH + 1))

    assert exc.value.code == TITLE_LENGTH_CODE


@pytest.mark.parametrize(
    ("overrides", "expected_code"),
    [
        ({"title": "   "}, "blank_title"),
        ({"body": ""}, "blank_body"),
        ({"category": "NOPE"}, "invalid_category"),
        ({"title": "x" * (TITLE_MAX_LENGTH + 1)}, "title_too_long"),
    ],
)
def test_create_post_surfaces_a_stable_code(make_user, overrides, expected_code):
    """R4: 5.2 renders these codes in the project envelope, so they are part of the
    contract — and each rejection must persist nothing."""
    from apps.community.models import Post

    kwargs = {
        "title": "Joining letter updates?",
        "body": "Anyone heard back?",
        "category": "JOINING_LETTER",
    }
    kwargs.update(overrides)

    with pytest.raises(InvalidPostError) as exc:
        create_post(make_user(), **kwargs)

    assert exc.value.code == expected_code
    assert Post.objects.count() == 0


def test_create_comment_surfaces_blank_body(make_post, make_user):
    post = make_post()

    with pytest.raises(InvalidCommentError) as exc:
        create_comment(post, make_user(), body="  \n ")

    assert exc.value.code == "blank_body"
    assert post.comments.count() == 0
