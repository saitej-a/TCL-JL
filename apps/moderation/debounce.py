"""Duplicate-post debounce (Phase 8.1 — T8.5 + CONTEXT D6).

08 §8.2's 60-minute duplicate defense, extended per CONTEXT D6: two hashes per
post — the spec's `(author_id, title)` MD5 plus a `(author_id, body)` MD5 — so
identical text under a fresh title is still caught. Comments are never
debounced; the edit path is never debounced (editing your own post twice in an
hour is legitimate).

Keys go through Django's cache framework — never a raw Redis client (6.2 D3) —
so test runs on LocMemCache behave identically. `author_id` is inside every
hash input (T-08.1-04: no cross-author gagging), and values hold only the
author id for diagnostics.
"""

import hashlib

from django.conf import settings
from django.core.cache import cache

_KEY_NAMESPACE = "moderation:dup:post:"


def _normalized_body(body: str) -> str:
    """Whitespace-collapsed, lowercased body (D6's normalization)."""
    return " ".join(body.split()).lower()


def _hash(author_id, text: str) -> str:
    # MD5 is 08 §8.2's own dedup choice and keys a non-security namespace;
    # `usedforsecurity=False` records that (S324).
    digest = hashlib.md5(f"{author_id}:{text}".encode(), usedforsecurity=False)
    return f"{_KEY_NAMESPACE}{digest.hexdigest()}"


def check_duplicate_post(author_id, title: str, body: str) -> bool:
    """True when this author posted the same title OR body within the window."""
    title_key = _hash(author_id, title.strip().lower())
    body_key = _hash(author_id, _normalized_body(body))
    return cache.get(title_key) is not None or cache.get(body_key) is not None


def register_post_hashes(author_id, title: str, body: str) -> None:
    """Record both hashes after a successful post create (TTL = 08 §8.2's 3600s)."""
    ttl = settings.DUPLICATE_POST_WINDOW
    title_key = _hash(author_id, title.strip().lower())
    body_key = _hash(author_id, _normalized_body(body))
    cache.set(title_key, author_id, timeout=ttl)
    cache.set(body_key, author_id, timeout=ttl)
