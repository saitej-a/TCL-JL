"""Scam heuristics tests (Phase 8.1 — MOD-04, 08 §8.1, CONTEXT D1/D2/D7)."""

from apps.moderation.heuristics import CATEGORY_MESSAGE, SCAM_PATTERNS, evaluate_content_safety


class TestSpecPatterns:
    def test_fee_solicitation_flagged(self):
        result = evaluate_content_safety("", "Pay 5000 for joining letter, contact me")
        assert result["flagged"] is True
        assert result["reason"] == "SCAM_PATTERN_MATCH"

    def test_telegram_group_scam_flagged(self):
        result = evaluate_content_safety("", "Join my telegram group @tcsoffers")
        assert result["flagged"] is True

    def test_whatsapp_contact_scam_flagged(self):
        result = evaluate_content_safety("", "whatsapp https://chat.whatsapp.com/abc")
        assert result["flagged"] is True

    def test_guaranteed_joining_flagged(self):
        result = evaluate_content_safety("", "Get guaranteed joining in TCS now!")
        assert result["flagged"] is True

    def test_nextstep_password_request_flagged(self):
        result = evaluate_content_safety("", "Share your NextStep password for verification")
        assert result["flagged"] is True

    def test_ultimatix_credentials_flagged(self):
        result = evaluate_content_safety("", "ultimatix credentials needed, DM me")
        assert result["flagged"] is True


class TestBenignContent:
    def test_ordinary_waiting_post_not_flagged(self):
        result = evaluate_content_safety(
            "Joining letter updates?", "Anyone from the 2026 batch still waiting?"
        )
        assert result["flagged"] is False
        assert result["reason"] is None

    def test_joining_word_alone_is_safe(self):
        result = evaluate_content_safety("", "When is my joining date expected?")
        assert result["flagged"] is False

    def test_nextstep_mention_without_solicitation_is_safe(self):
        result = evaluate_content_safety("", "NextStep portal shows my status as onboarding.")
        assert result["flagged"] is False

    def test_title_and_body_scanned_jointly(self):
        result = evaluate_content_safety("guaranteed selection", "in the next batch, friends")
        assert result["flagged"] is True


class TestResponseHygiene:
    def test_matched_pattern_is_internal_only(self):
        """T-08.1-03: matched_pattern exists for diagnostics but the HTTP layer
        only ever surfaces CATEGORY_MESSAGE."""
        result = evaluate_content_safety("", "guaranteed joining now")
        assert "matched_pattern" in result  # internal return value
        assert CATEGORY_MESSAGE  # the message constant is non-empty

    def test_category_message_contains_no_pattern_text(self):
        """The response never echoes the matched REGEX (T-08.1-03): none of the
        spec patterns' source strings may appear in the category message."""
        for pattern in SCAM_PATTERNS:
            assert pattern.pattern not in CATEGORY_MESSAGE

    def test_category_message_names_the_category(self):
        message = CATEGORY_MESSAGE.lower()
        assert "fee solicitation" in message or "credential" in message
