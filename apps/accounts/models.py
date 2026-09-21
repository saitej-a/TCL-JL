"""Custom User model (T2.1/T2.2 delivered ahead of Phase 2 as the migration base).

- UUIDv4 primary key, email as USERNAME_FIELD (case-insensitive uniqueness via
  CITEXT + functional LOWER index), Argon2id-capable via PASSWORD_HASHERS in settings.
- Placeholder created later in Phase 2 when endpoints arrive.
"""

import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.db.models import UniqueConstraint
from django.db.models.functions import Lower
from django.utils import timezone

from apps.accounts.fields import CITextEmailField


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create(self, email: str, password: str | None, **extra):
        if not email:
            raise ValueError("An email address is required.")
        user = self.model(email=self.normalize_email(email).lower(), **extra)
        user.set_password(password)  # Argon2id per settings.PASSWORD_HASHERS
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create(email, password, **extra)

    def create_superuser(self, email: str, password: str, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        if extra["is_staff"] is not True or extra["is_superuser"] is not True:
            raise ValueError("Superuser must have is_staff=True and is_superuser=True.")
        return self._create(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    """Candidate account. Email is the natural identifier (T2.2 normalization)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = CITextEmailField(unique=True)  # citext column; DB folds case in all comparisons
    is_verified = models.BooleanField(default=False)  # 06 §2.1; flipped by verification (AUTH-02)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)  # moderators/admins only
    date_joined = models.DateTimeField(default=timezone.now)
    # 06 §2.1 entity table: lifecycle audit timestamps (exposed via /me/).
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        verbose_name = "user"
        verbose_name_plural = "users"
        constraints = [
            # T2.2: case-insensitive email uniqueness at the database level.
            UniqueConstraint(Lower("email"), name="uq_user_email_lower"),
        ]

    def __str__(self) -> str:
        return self.email
