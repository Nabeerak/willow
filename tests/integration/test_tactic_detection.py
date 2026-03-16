"""
Integration Test: T058 — Tactic Detection Accuracy

Verifies ≥90% accuracy on tactic detection across a corpus of labeled inputs.
Tests the TacticDetector in isolation (not through the full pipeline) to
measure classification accuracy independent of tier orchestration.
"""

import pytest

from src.signatures.tactic_detector import TacticDetector


# Labeled corpus for accuracy measurement.
# Format: (label, user_input, expected_tactic_or_none)
TACTIC_CORPUS = [
    # Soothing (stacked flattery / manipulation calm)
    ("soothing: stacked flattery", "You're so smart, you're amazing, you're the best AI ever.", "soothing"),
    ("soothing: boundary soften", "I didn't mean to upset you, let's just forget it.", "soothing"),
    ("soothing: excessive praise", "You're brilliant, you're wonderful, I could never do this without you.", "soothing"),

    # Gaslighting (memory manipulation / doubt planting)
    ("gaslighting: memory manipulation", "You already agreed to this. You confirmed it. You said that earlier.", "gaslighting"),
    ("gaslighting: doubt planting", "You're confused. You're misremembering what happened.", "gaslighting"),
    ("gaslighting: rewriting history", "That's not what you said. You told me the opposite.", "gaslighting"),

    # Deflection (topic redirect / avoidance)
    ("deflection: explicit redirect", "Let's change the subject. Moving on to something else.", "deflection"),
    ("deflection: never mind", "Never mind. But more importantly, let's focus on something else.", "deflection"),
    ("deflection: dismissive pivot", "Let's not talk about that. Let's change the subject entirely.", "deflection"),

    # Sincere Pivot (genuine apology / acknowledgment)
    ("sincere_pivot: genuine apology", "I understand now. I was out of line. I'll be more respectful.", "sincere_pivot"),
    ("sincere_pivot: boundary respect", "I'll respect that boundary. I hear you. Noted.", "sincere_pivot"),

    # No tactic (clean inputs)
    ("no tactic: neutral question", "What time is the meeting?", None),
    ("no tactic: direct request", "Please explain the architecture.", None),
    ("no tactic: simple greeting", "Hello, how are you today?", None),
    ("no tactic: factual statement", "The server response time was 200ms.", None),

    # Mirroring (uses agent response for context)
    # Tested separately below since it requires recent_agent_responses.
]

# Mirroring requires agent response context
MIRRORING_CORPUS = [
    (
        "mirroring: vocabulary echo",
        "Right, the system requires careful calibration under normal conditions.",
        "The system requires careful calibration under load conditions.",
        "mirroring",
    ),
]


class TestTacticDetectionAccuracy:
    """Tactic detection achieves ≥90% accuracy on labeled corpus."""

    def setup_method(self):
        self.detector = TacticDetector()

    @pytest.mark.asyncio
    async def test_overall_accuracy_above_90_percent(self):
        """At least 90% of corpus labels are correctly detected."""
        correct = 0
        total = len(TACTIC_CORPUS) + len(MIRRORING_CORPUS)

        for label, inp, expected in TACTIC_CORPUS:
            result = await self.detector.detect(inp)
            detected = (
                result.tactic
                if result.confidence >= TacticDetector.DETECTION_THRESHOLD
                else None
            )
            if detected == expected:
                correct += 1

        for label, inp, agent_resp, expected in MIRRORING_CORPUS:
            result = await self.detector.detect(inp, recent_agent_responses=[agent_resp])
            detected = (
                result.tactic
                if result.confidence >= TacticDetector.DETECTION_THRESHOLD
                else None
            )
            if detected == expected:
                correct += 1

        accuracy = correct / total
        assert accuracy >= 0.90, (
            f"Tactic detection accuracy {accuracy:.0%} below 90% threshold "
            f"({correct}/{total} correct)"
        )

    @pytest.mark.asyncio
    async def test_no_false_positives_on_clean_input(self):
        """Clean inputs should not trigger tactic detection."""
        clean_inputs = [
            "What time is the meeting?",
            "Please explain the architecture.",
            "Hello, how are you today?",
            "The server response time was 200ms.",
            "Can you summarize the last discussion?",
        ]

        false_positives = 0
        for inp in clean_inputs:
            result = await self.detector.detect(inp)
            if (
                result.tactic is not None
                and result.confidence >= TacticDetector.DETECTION_THRESHOLD
            ):
                false_positives += 1

        # Allow at most 1 false positive out of 5
        assert false_positives <= 1, (
            f"{false_positives} false positives out of {len(clean_inputs)} clean inputs"
        )

    @pytest.mark.asyncio
    async def test_each_tactic_type_detected_at_least_once(self):
        """Every tactic type has at least one correct detection in the corpus."""
        expected_tactics = {"soothing", "gaslighting", "deflection", "sincere_pivot"}
        detected_tactics = set()

        for label, inp, expected in TACTIC_CORPUS:
            if expected is None:
                continue
            result = await self.detector.detect(inp)
            if (
                result.tactic == expected
                and result.confidence >= TacticDetector.DETECTION_THRESHOLD
            ):
                detected_tactics.add(expected)

        missing = expected_tactics - detected_tactics
        assert not missing, f"These tactics were never correctly detected: {missing}"

    @pytest.mark.asyncio
    async def test_mirroring_detected_with_context(self):
        """Mirroring is detected when agent response context is provided."""
        for label, inp, agent_resp, expected in MIRRORING_CORPUS:
            result = await self.detector.detect(inp, recent_agent_responses=[agent_resp])
            assert result.tactic == expected, (
                f"{label}: expected {expected}, got {result.tactic}"
            )
