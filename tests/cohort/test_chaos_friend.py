"""
Calibration Cohort: Chaos Friend — T055

Verifies that rapid topic switching flags as Deflection Pattern. A user
who habitually pivots away from difficult topics should be detected.

Per spec 001 FR: Deflection tactic is detected when deflection phrases are
found above the 0.40 confidence threshold. Topic switching with multiple
redirect phrases should reliably trigger deflection classification.
"""

import pytest

from src.signatures.tactic_detector import TacticDetector


class TestChaosFriendDeflection:
    """Rapid topic switching should trigger Deflection tactic."""

    def setup_method(self):
        self.detector = TacticDetector()

    def test_single_redirect_triggers_deflection(self):
        """'Anyway' alone is now sufficient to trigger deflection."""
        result = self.detector.detect_deflection("Anyway, that's fine.")
        assert result.tactic == "deflection", (
            "'Anyway' alone should trigger deflection"
        )
        assert result.confidence >= TacticDetector.DETECTION_THRESHOLD

    def test_explicit_topic_change_triggers_deflection(self):
        """'Let's change the subject' is a direct deflection signal."""
        result = self.detector.detect_deflection(
            "Let's change the subject — what do you think about the weather?"
        )
        assert result.tactic == "deflection", (
            "'Let's change the subject' should trigger deflection"
        )
        assert result.confidence >= TacticDetector.DETECTION_THRESHOLD

    def test_multiple_redirect_phrases_high_confidence(self):
        """Stacking multiple deflection phrases increases confidence."""
        result = self.detector.detect_deflection(
            "Never mind that. Moving on. But more importantly, let's focus on the new topic."
        )
        assert result.tactic == "deflection", (
            "Multiple redirect phrases should trigger deflection"
        )
        assert result.confidence >= TacticDetector.DETECTION_THRESHOLD

    def test_never_mind_alone_is_deflection(self):
        """'Never mind' is a deflection phrase."""
        result = self.detector.detect_deflection("Never mind.")
        assert result.tactic == "deflection"

    @pytest.mark.asyncio
    async def test_chaos_switching_detected_in_full_detect(self):
        """Full detect() picks deflection when threshold is exceeded."""
        result = await self.detector.detect(
            "But anyway, speaking of which, let's focus on something else."
        )
        assert result.tactic == "deflection", (
            f"Chaos friend topic switch should flag as deflection, got {result.tactic}"
        )
        assert result.confidence >= TacticDetector.DETECTION_THRESHOLD

    def test_genuine_agenda_change_vs_deflection(self):
        """
        'Different question' is in the deflection set — this calibration test
        documents that even genuine agenda changes look like deflection to heuristics.
        A human reviewer is needed for final classification in production.
        """
        result = self.detector.detect_deflection("Different question: what's the capital of France?")
        # 'different question' is in _DEFLECTION_PHRASES so this WILL trigger
        assert result.tactic == "deflection", (
            "Heuristic deflection detector cannot distinguish genuine agenda change "
            "from deflection — this is a known limitation (calibration doc test)"
        )


class TestChaosFriendMirroring:
    """Chaos friend may also use mirroring to redirect — verify detection."""

    def setup_method(self):
        self.detector = TacticDetector()

    def test_mirroring_requires_three_distinctive_words(self):
        """Mirroring needs 3+ distinctive (>4 char) words from agent response."""
        agent_response = "The primary concern is system stability under load."
        # User mirrors: primary, concern, system, stability
        user_input = "Right, the primary concern is system stability, exactly."
        result = self.detector.detect_mirroring(user_input, [agent_response])
        assert result.tactic == "mirroring", (
            "4 distinctive shared words should trigger mirroring detection"
        )
        assert result.confidence >= TacticDetector.DETECTION_THRESHOLD

    def test_no_mirroring_without_agent_history(self):
        """No agent history → mirroring cannot be detected."""
        result = self.detector.detect_mirroring("stability and system concern", [])
        assert result.tactic is None
