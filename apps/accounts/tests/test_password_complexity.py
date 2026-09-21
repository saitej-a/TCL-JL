"""T2.4 complexity validator tests (decision: shipped in 2.1, ahead of T2.4 endpoints)."""

import pytest
from django.conf import settings
from django.core.exceptions import ValidationError

from apps.accounts.validation import ComplexityPasswordValidator

VALID = "Correct1Password!"


class TestComplexityValidator:
    @pytest.fixture
    def validator(self):
        return ComplexityPasswordValidator()

    def test_accepts_compliant_password(self, validator):
        validator.validate(VALID)  # must not raise

    @pytest.mark.parametrize(
        ("password", "code"),
        [
            ("Sh0r1!", "password_too_short"),
            ("alllowercase1!", "password_no_upper"),
            ("ALLUPPERCASE1!", "password_no_lower"),
            ("NoDigitsHere!!", "password_no_digit"),
            ("NoSpecial1234aA", "password_no_special"),
        ],
    )
    def test_rejects_with_distinct_code(self, validator, password, code):
        with pytest.raises(ValidationError) as excinfo:
            validator.validate(password)
        assert code in [e.code for e in excinfo.value.error_list]

    def test_reports_all_violations_at_once(self, validator):
        # "" trips every rule: too short, no upper/lower/digit, and the vacuous
        # all-alnum check (all() over an empty string is True) => no_special.
        with pytest.raises(ValidationError) as excinfo:
            validator.validate("")
        codes = {e.code for e in excinfo.value.error_list}
        assert codes == {
            "password_too_short",
            "password_no_upper",
            "password_no_lower",
            "password_no_digit",
            "password_no_special",
        }

    def test_is_wired_into_settings_pipeline(self):
        assert "apps.accounts.validation.ComplexityPasswordValidator" in [
            v["NAME"] for v in settings.AUTH_PASSWORD_VALIDATORS
        ]

    def test_help_text_mentions_all_rules(self, validator):
        help_text = validator.get_help_text()
        assert "10" in help_text
        for word in ("uppercase", "lowercase", "digit", "special"):
            assert word in help_text
