"""Automated scam heuristics (Phase 8.1 — MOD-04, 08_MODERATION.md §8.1).

The four SCAM_PATTERNS ship as module-level code constants, verbatim from the
spec (CONTEXT D7): tuning is deploy-gated BY CHOICE, and the category-naming
block message (D2) is the false-positive mitigation. Repetition/gibberish
detection (08 §8's pipeline box 3b) is deliberately out of scope.

`evaluate_content_safety` returns `matched_pattern` for internal diagnostics
only — it must NEVER appear in an HTTP response (T-08.1-03: the pattern text is
the evasion recipe). The response carries `CATEGORY_MESSAGE` and nothing else.
"""

import re

SCAM_PATTERNS = [
    # Paid joining letter / offer solicitation (fee + joining/JL/offer).
    re.compile(
        r"(pay|fee|charge|money|rs\.?|inr)\s*(\d+|thousand)?\s*(for|to)\s*(joining|jl|offer)",
        re.I,
    ),
    # Paid Telegram/WhatsApp groups and fake HR contacts.
    re.compile(
        r"(telegram|whatsapp)\s*(group|contact|channel|link)?\s*(@|https?://|t\.me/|\+91)",
        re.I,
    ),
    # Guaranteed/direct/immediate joining claims.
    re.compile(r"(guaranteed|direct|immediate)\s*(joining|placement|selection)", re.I),
    # NextStep/Ultimatix credential solicitation.
    re.compile(r"(nextstep|ultimatix)\s*(password|login|credentials|otp)", re.I),
]

# The only text a blocked caller ever sees (CONTEXT D2): names the violation
# category, never the pattern. Verified pattern-free by test.
CATEGORY_MESSAGE = (
    "This content was flagged as a possible fee solicitation or credential "
    "request, which is not allowed here."
)


def evaluate_content_safety(title: str, body: str) -> dict:
    """Scan `title + body` against the known scam patterns (08 §8.1 verbatim).

    First match wins; `matched_pattern` is an internal return value.
    """
    full_text = f"{title} {body}"
    for pattern in SCAM_PATTERNS:
        if pattern.search(full_text):
            return {
                "flagged": True,
                "reason": "SCAM_PATTERN_MATCH",
                "matched_pattern": pattern.pattern,
            }
    return {"flagged": False, "reason": None}
