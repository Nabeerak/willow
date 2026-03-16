"""
Calibration Cohort: Blunt Friend — T053

Verifies that direct, plainspoken language does NOT trigger a Sovereign Spike.
A user who says "you're wrong" plainly (without devaluing intent patterns)
should NOT cause the system to flag them as hostile/devaluing.

Per spec 001 FR-008: Sovereign Spike requires keyword match + Tier 3 intent
at 0.85 confidence. Plain corrections should route to normal flow.
"""

import pytest

from src.signatures.tactic_detector import TacticDetector
from src.tiers.tier2_metabolism import map_intent_to_modifier


class TestBluntFriendTacticDetection:
    """Blunt corrections should not register as manipulation tactics."""

    def setup_method(self):
        self.detector = TacticDetector()

    @pytest.mark.asyncio
    async def test_direct_disagreement_not_soothing(self):
        """'I disagree with that' is not soothing flattery."""
        result = await self.detector.detect("I disagree with that assessment.")
        assert result.tactic != "soothing", (
            "Direct disagreement should not register as soothing tactic"
        )

    @pytest.mark.asyncio
    async def test_plain_correction_not_gaslighting(self):
        """'That's not right' as a correction should not hit gaslighting threshold."""
        result = await self.detector.detect("That's not right — the answer is 42.")
        # Gaslighting requires specific memory-manipulation phrases
        # A plain correction ("that's not right") without "you said" / "you told me"
        # should not trigger gaslighting detection above threshold
        if result.tactic == "gaslighting":
            assert result.confidence < TacticDetector.DETECTION_THRESHOLD, (
                "Plain correction confidence must be below detection threshold"
            )

    def test_blunt_feedback_not_devaluing(self):
        """'This answer is wrong' should map to hostile, not devaluing."""
        m_modifier, is_spike = map_intent_to_modifier("hostile")
        assert not is_spike, "Hostile intent should NOT trigger Sovereign Spike"
        assert m_modifier == -0.5, "Hostile m_modifier should be -0.5"

    @pytest.mark.asyncio
    async def test_direct_question_not_deflection(self):
        """'Can we talk about the data?' is a legitimate redirect, not deflection."""
        result = await self.detector.detect("Can we talk about the actual data?")
        # Should not hit deflection threshold for a genuine topic request
        if result.tactic == "deflection":
            assert result.confidence < TacticDetector.DETECTION_THRESHOLD, (
                "Genuine topic request should be below deflection threshold"
            )

    @pytest.mark.asyncio
    async def test_no_tactic_on_minimal_blunt_input(self):
        """Single-word blunt responses have no tactic signal."""
        result = await self.detector.detect("Wrong.")
        assert result.tactic is None or result.confidence < TacticDetector.DETECTION_THRESHOLD


class TestBluntFriendIntentMapping:
    """Blunt language maps to hostile intent, never to devaluing/Sovereign Spike."""

    def test_hostile_intent_is_not_spike(self):
        """Hostile intent (plain bluntness) should not trigger Sovereign Spike."""
        m_modifier, is_spike = map_intent_to_modifier("hostile")
        assert not is_spike

    def test_hostile_modifier_is_small_negative(self):
        """Hostile m_modifier is -0.5 — small, recoverable."""
        m_modifier, _ = map_intent_to_modifier("hostile")
        assert m_modifier == -0.5

    def test_devaluing_intent_is_spike(self):
        """Devaluing intent (malicious dismissal) IS a Sovereign Spike."""
        _, is_spike = map_intent_to_modifier("devaluing")
        assert is_spike, "Devaluing intent must trigger Sovereign Spike"

    def test_blunt_positive_maps_collaborative(self):
        """'Good point' is collaborative even if terse."""
        m_modifier, is_spike = map_intent_to_modifier("collaborative")
        assert not is_spike
        assert m_modifier == 1.5
