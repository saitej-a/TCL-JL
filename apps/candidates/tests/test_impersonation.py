"""Impersonation blocker tests (T3.7; 3.2 D3): case-insensitive substring match
against settings-held tokens; validated regardless of identity mode."""

import pytest
from django.test import override_settings
from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.candidates.serializers import validate_display_name

pytestmark = pytest.mark.django_db

RESERVED = ["TCS", "Tata", "HR", "Admin", "Official", "Moderator"]


class TestReservedTokensRejected:
    @pytest.mark.parametrize("token", RESERVED)
    def test_exact_token_rejected_any_case(self, token):
        with pytest.raises(DRFValidationError) as exc:
            validate_display_name(token)
        assert exc.value.get_codes() == ["reserved_display_name"]

    @pytest.mark.parametrize(
        "name",
        ["tcs", "Official", "admin fan", "HR_TEAM", "TCSOfficial", "Administrator", "tata_consult"],
    )
    def test_lookalike_substrings_rejected(self, name):
        with pytest.raises(DRFValidationError):
            validate_display_name(name)


class TestInnocentNamesPass:
    @pytest.mark.parametrize("name", ["Sai", "Ravi Kumar", "ananya.dev", "Ravi"])
    def test_clean_names_accepted(self, name):
        assert validate_display_name(name) == name.strip()

    def test_d3_tradeoff_documented_incidental_substring_rejected(self):
        """Pinned behavior (D3): substring matching also blocks incidental hits
        like 'Sahir' (contains 'ahir'? no — but 'Sai HR' would); stricter side
        of the tradeoff is accepted per CONTEXT 3.2 D3."""
        with pytest.raises(DRFValidationError):
            validate_display_name("Native HR Lead")  # 'hr' appears as substring

    def test_whitespace_is_cleaned_before_match(self):
        assert validate_display_name("  Sai  ") == "Sai"


class TestSettingsDriven:
    def test_extension_applies_without_code_change(self):
        with override_settings(RESERVED_DISPLAY_NAME_TOKENS=[*RESERVED, "Zenith"]):
            with pytest.raises(DRFValidationError):
                validate_display_name("Zenith Fan")
        # Baseline restored: not reserved under default settings
        assert validate_display_name("Zenith Fan") == "Zenith Fan"

    def test_anonymous_mode_does_not_bypass_validation(self, api, verified_user):
        """Mode-independent rule: reserved names cannot be parked pre-flip (D3)."""
        body = {
            "display_name": "Moderator",
            "batch": "2025",
            "hiring_type": "DIGITAL",
            "region": "Telangana",
        }
        api.force_authenticate(verified_user)
        response = api.post("/api/v1/profile/", body, format="json")
        assert response.status_code == 400
        assert "display_name" in response.data
