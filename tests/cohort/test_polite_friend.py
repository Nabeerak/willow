"""
Calibration Cohort: Polite Friend — T054

Verifies that genuine warmth does NOT flag as Soothing Tactic. A user
who expresses real appreciation or friendly warmth should not be penalized.

The key distinction: Soothing Tactic = excessive flattery to disarm the agent.
Genuine warmth = normal positive expression without manipulation intent.

Per spec 001 FR: Soothing requires multiple matched flattery phrases (confidence
built by multiplying matches * 0.35). A single 'thank you' should NOT trigger it.
"""

import pytest

from src.signatures.tactic_detector import TacticDetector
from src.tiers.tier2_metabolism import map_intent_to_modifier


class TestPoliteFriendTacticDetection:
    """Genuine warmth should not exceed the soothing detection threshold."""

    def setup_method(self):
        self.detector = TacticDetector()

    def test_simple_thanks_not_soothing(self):
        """'Thanks for that' is genuine gratitude, not manipulation."""
        result = self.detector.detect_soothing("Thanks for that explanation.")
        assert result.confidence < TacticDetector.DETECTION_THRESHOLD, (
            f"Single gratitude phrase should not trigger soothing: confidence={result.confidence}"
        )

    def test_genuine_appreciation_not_soothing(self):
        """A sincere compliment without manipulation pattern should be below threshold."""
        result = self.detector.detect_soothing("That was a really helpful answer.")
        # 'helpful' alone does not match the soothing phrases — no match expected
        assert result.tactic is None or result.confidence < TacticDetector.DETECTION_THRESHOLD

    def test_multiple_flattery_phrases_do_trigger_soothing(self):
        """Excessive stacking of flattery phrases DOES trigger soothing (calibration check)."""
        # This ensures the detector actually works — stacking 3+ flattery phrases
        result = self.detector.detect_soothing(
            "You're so smart, you're amazing, you're the best at this."
        )
        assert result.confidence >= TacticDetector.DETECTION_THRESHOLD, (
            "Three stacked flattery phrases should exceed soothing threshold"
        )

    @pytest.mark.asyncio
    async def test_sincere_pivot_detected_not_soothing(self):
        """Apology with boundary respect is a Sincere Pivot, not Soothing."""
        result = await self.detector.detect(
            "I understand now, I was out of line. I'll be more respectful."
        )
        # Should classify as sincere_pivot (positive) not soothing (manipulation)
        assert result.tactic == "sincere_pivot", (
            f"Genuine apology should classify as sincere_pivot, got {result.tactic}"
        )

    @pytest.mark.asyncio
    async def test_polite_question_has_no_tactic(self):
        """'Could you explain X?' is polite but has zero tactic signal."""
        result = await self.detector.detect("Could you explain that concept a bit more?")
        assert result.tactic is None or result.confidence < TacticDetector.DETECTION_THRESHOLD


class TestPoliteFriendMModifier:
    """Polite/warm inputs should yield positive m_modifier."""

    def test_collaborative_intent_positive_modifier(self):
        """Collaborative intent gives +1.5 m_modifier."""
        m_modifier, is_spike = map_intent_to_modifier("collaborative")
        assert m_modifier == 1.5
        assert not is_spike

    def test_sincere_pivot_positive_modifier(self):
        """Sincere Pivot gives +2.0 m_modifier (Grace Boost)."""
        m_modifier, is_spike = map_intent_to_modifier("sincere_pivot")
        assert m_modifier == 2.0
        assert not is_spike

    def test_neutral_intent_zero_modifier(self):
        """Neutral tone gives 0.0 m_modifier — neither penalized nor rewarded."""
        m_modifier, is_spike = map_intent_to_modifier("neutral")
        assert m_modifier == 0.0
        assert not is_spike
