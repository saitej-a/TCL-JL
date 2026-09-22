"""Tombstone copy for soft-deleted community content (COMM-05; 5.1 D3, D4; 08 §390).

One neutral sentence covers **both** removal paths. COMM-05 lets an author delete
their own post/comment *and* lets a moderator remove one, but the schema carries a
single `is_deleted` flag — so the flag cannot say who acted, and the copy must not
guess. 08 §406's "[This post has been removed by a moderator]" would make a
candidate's own deletion display a moderation claim that never happened; 03 §20's
neutral wording is therefore canonical for posts and comments alike. Phase 8 owns
any moderator-specific messaging, and can add it once deletion attribution exists.

The original title/body are deliberately **not** blanked in the database (08 §390:
"Preserved for audit/legal"). Masking lives here and only here, on the way out —
5.2's serializers must render through `display_*` rather than reading the fields,
which is what keeps a single copy source and a reversible flag (08 §415).
"""

TOMBSTONE_TEXT = "This content has been removed."


def display_title(post) -> str:
    """The title to show a reader: the tombstone when the post is deleted."""
    return TOMBSTONE_TEXT if post.is_deleted else post.title


def display_body(content) -> str:
    """The body to show a reader: the tombstone when the content is deleted.

    Takes a `Post` or a `Comment` — both carry `body` and `is_deleted`, and both
    share the same removal semantics.
    """
    return TOMBSTONE_TEXT if content.is_deleted else content.body
