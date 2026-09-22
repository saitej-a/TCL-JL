"""Debounce tests (Phase 8.1 — T8.5 + CONTEXT D6)."""

from unittest.mock import patch

import pytest

from apps.moderation.debounce import check_duplicate_post, register_post_hashes

pytestmark = pytest.mark.django_db


class _SpyCache:
    """Records cache.set calls so TTL/namespace wiring is proven without
    depending on which cache backend the suite runs on (Redis in CI, LocMem
    locally) — the debounced behavior tests below use the real alias."""

    def __init__(self):
        self.calls = {}

    def set(self, key, value, timeout=None):
        self.calls[key] = timeout

    def get(self, key):
        return self.calls.get(key)


class TestDuplicateDetection:
    def test_identical_title_within_window_hits(self, author):
        register_post_hashes(author.id, "Hello World", "first body")
        assert check_duplicate_post(author.id, "Hello World", "different body") is True

    def test_identical_body_within_window_hits(self, author):
        register_post_hashes(author.id, "First Title", "Shared body text")
        assert check_duplicate_post(author.id, "Fresh Title", "shared body text") is True

    def test_different_content_misses(self, author):
        register_post_hashes(author.id, "Hello World", "some body")
        assert check_duplicate_post(author.id, "Goodbye World", "another body") is False

    def test_per_author_isolation(self, author, other_reporter):
        register_post_hashes(author.id, "Same Title", "Same body")
        assert check_duplicate_post(other_reporter.id, "Same Title", "Same body") is False

    def test_case_and_whitespace_variants_collide(self, author):
        register_post_hashes(author.id, "Hello  World", "Body   Text")
        assert check_duplicate_post(author.id, "hello world", "body text") is True

    def test_ttl_window_wiring(self, author, settings):
        """Both keys are written with DUPLICATE_POST_WINDOW as the TTL."""
        settings.DUPLICATE_POST_WINDOW = 1234
        spy = _SpyCache()
        with patch("apps.moderation.debounce.cache", spy):
            register_post_hashes(author.id, "Window Title", "window body")
        assert len(spy.calls) == 2
        assert set(spy.calls.values()) == {1234}


class TestCacheFrameworkOnly:
    def test_keys_use_moderation_namespace(self, author):
        spy = _SpyCache()
        with patch("apps.moderation.debounce.cache", spy):
            register_post_hashes(author.id, "Namespace Check", "ns body")
        assert spy.calls
        assert all(key.startswith("moderation:dup:post:") for key in spy.calls)
