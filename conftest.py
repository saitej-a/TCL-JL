"""Root test isolation: throttle state must not leak between tests.

Two pollution channels exist now that community writes actually throttle
(9.3 D4) and anonymous community reads are throttled (9.3 D1):

1. ``settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"][...] = "2/min"`` mutates
   a dict *in place* — pytest-django's ``settings`` fixture restores attribute
   assignments, not nested dict contents — so a rate shrunk for one test leaks
   into every later test in the process. The autouse fixture snapshots the
   mapping before the test and restores it after. **The restore must happen in
   place** (``clear()`` + ``update()``): DRF's ``api_settings`` caches
   ``DEFAULT_THROTTLE_RATES`` as a reference to the dict object on first
   access, so reassigning a fresh dict desyncs the cache and rate mutations
   silently stop taking effect.
2. DRF's throttle history lives in the cache keyed by ident, and all test
   traffic shares one ident (127.0.0.1 / testserver), so one test's
   half-consumed bucket 429s an unrelated later test. The autouse fixture
   clears the cache *before* each test; cache state within a single test
   behaves exactly as before.
"""

import pytest


@pytest.fixture(autouse=True)
def _isolated_throttle_state(settings):
    rates = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
    saved = dict(rates)

    from django.core.cache import cache

    cache.clear()
    yield
    rates.clear()  # in-place restore — see module docstring re: DRF's cache
    rates.update(saved)
