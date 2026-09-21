"""T2.3 hashing-pipeline tests (CONTEXT.md gate: hash carries m=65536,t=3,p=2)."""

import pytest
from django.conf import settings
from django.contrib.auth.hashers import check_password, get_hasher, identify_hasher, make_password
from django.test import override_settings

from apps.accounts.hashers import Argon2idHasher
from apps.accounts.models import User

pytestmark = pytest.mark.django_db

SPEC_PARAMS = "m=65536,t=3,p=2"
ARGON2ID_HASHER = "apps.accounts.hashers.Argon2idHasher"


class TestArgon2idHasher:
    def test_hasher_is_registered_with_spec_params(self):
        # Lookup key is the hasher's `algorithm` attribute ("argon2"), not the
        # hash-string variety segment ("argon2id").
        assert ARGON2ID_HASHER in settings.PASSWORD_HASHERS
        hasher = get_hasher("argon2")
        assert isinstance(hasher, Argon2idHasher)
        assert hasher.time_cost == 3
        assert hasher.memory_cost == 65536
        assert hasher.parallelism == 2

    @override_settings(PASSWORD_HASHERS=[ARGON2ID_HASHER])
    def test_make_password_uses_spec_params(self):
        """Pins the default hasher output independent of settings-module ordering
        (test settings deliberately put MD5 first for suite speed)."""
        encoded = make_password("Correct Horse Battery 9!")
        # Format: argon2$argon2id$v=19$m=65536,t=3,p=2$<salt>$<hash>
        assert encoded.startswith(f"argon2$argon2id$v=19${SPEC_PARAMS}$")
        assert identify_hasher(encoded).algorithm == "argon2"

    def test_round_trip_verify(self):
        encoded = make_password("Correct Horse Battery 9!")
        assert check_password("Correct Horse Battery 9!", encoded)
        assert not check_password("wrong password 1!", encoded)

    @override_settings(PASSWORD_HASHERS=[ARGON2ID_HASHER])
    def test_create_user_stores_argon2id(self):
        """The 'registration path' — manager create — emits the pinned hasher.

        override_settings makes this independent of which settings module the
        runner picked (test settings put MD5 first for suite speed).
        """
        user = User.objects.create_user("HashPath@Test.COM", "Correct Horse Battery 9!")
        assert user.password.startswith(f"argon2$argon2id$v=19${SPEC_PARAMS}$")
        assert user.check_password("Correct Horse Battery 9!")
