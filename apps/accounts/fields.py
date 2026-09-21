"""Custom PostgreSQL field types.

Django 5.1 removed the built-in CI*/CIText fields (ticket #33872), but the
mechanism they used — declaring the column's DB type — remains fully supported.
A two-line db_type override restores CITEXT for the auth identity column so the
database folds case in *every* comparison (WHERE, JOIN, unique enforcement),
not just the ones our code remembers to normalize. Defense-in-depth on top of
the manager's write-time lowercasing and the uq_user_email_lower constraint.
"""

from django.db.models import EmailField


class CITextEmailField(EmailField):
    """EmailField stored as PostgreSQL ``citext`` (case-insensitive text)."""

    description = "Email (case-insensitive via PostgreSQL citext)"

    def db_type(self, connection) -> str:
        return "citext"
