"""Password validation (T2.4 complexity rules shipped ahead of the 2.2 endpoints).

ComplexityPasswordValidator enforces the registration password policy from
10_MVP_TASKS.md T2.4: minimum 10 characters plus at least one uppercase letter,
one lowercase letter, one digit, and one special (non-alphanumeric) character.
Each failure raises with a distinct, stable error code so the API layer can
translate them to precise field messages.
"""

from django.core.exceptions import ValidationError
from django.utils.translation import ngettext


class ComplexityPasswordValidator:
    """Enforce character-class complexity in addition to length."""

    DEFAULT_MIN_LENGTH = 10

    def __init__(self, min_length: int = DEFAULT_MIN_LENGTH) -> None:
        self.min_length = min_length

    def validate(self, password: str, user=None) -> None:
        errors: list[ValidationError] = []

        if len(password) < self.min_length:
            errors.append(
                ValidationError(
                    ngettext(
                        "Password must be at least %(min_length)d character long.",
                        "Password must be at least %(min_length)d characters long.",
                        self.min_length,
                    ),
                    code="password_too_short",
                    params={"min_length": self.min_length},
                )
            )
        if not any(c.isupper() for c in password):
            errors.append(
                ValidationError(
                    "Password must contain at least one uppercase letter.",
                    code="password_no_upper",
                )
            )
        if not any(c.islower() for c in password):
            errors.append(
                ValidationError(
                    "Password must contain at least one lowercase letter.",
                    code="password_no_lower",
                )
            )
        if not any(c.isdigit() for c in password):
            errors.append(
                ValidationError(
                    "Password must contain at least one digit.",
                    code="password_no_digit",
                )
            )
        if all(c.isalnum() for c in password):
            errors.append(
                ValidationError(
                    "Password must contain at least one special character.",
                    code="password_no_special",
                )
            )

        if errors:
            # All violations surface at once — better UX than one-per-submit.
            raise ValidationError([e for e in errors])

    def get_help_text(self) -> str:
        return (
            f"Your password must contain at least {self.min_length} characters, "
            "including an uppercase letter, a lowercase letter, a digit, and a "
            "special character."
        )
