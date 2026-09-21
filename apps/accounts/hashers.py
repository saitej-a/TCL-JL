"""Password hashers (T2.3).

Django's stock Argon2PasswordHasher builds its parameters from *class
attributes* (verified against the installed Django 5.2 source: params() reads
self.time_cost / self.memory_cost / self.parallelism — it never consults a
settings value), so tuning requires a subclass. This one pins the spec'd cost
parameters at the class level:

- memory_cost 65536 KiB = 64 MiB
- time_cost 3 iterations
- parallelism 2 threads

Note: `algorithm` stays the inherited "argon2" — Django's encode() prepends it to
the raw argon2 string, which already carries the "argon2id" variety segment; using
"argon2id" would double the prefix and break decode(). The variety is ID either way
(stock params() hardcodes Type.ID).

Registered FIRST in settings.PASSWORD_HASHERS, so set_password()/create_user()
(the registration path) emit these parameters; older hashes upgrade
transparently on next login via Django's password-upgrade flow.
"""

from django.contrib.auth.hashers import Argon2PasswordHasher


class Argon2idHasher(Argon2PasswordHasher):
    # algorithm inherited ("argon2") — see module docstring.
    time_cost = 3
    memory_cost = 65536  # KiB (64 MiB)
    parallelism = 2
