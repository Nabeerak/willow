"""
Unit Tests: ThoughtSignature — T061

Verifies:
- Intent/Tone separation (not conflated)
- Tactic classification accuracy
- ThoughtSignature dataclass validation
- Tier 3 Conscious intent → m_modifier mapping
"""

import pytest

from src.signatures.thought_signature import (
    ThoughtSignature,
    VALID_INTENTS,
    VALID_TONES,
)
from src.signatures.tactic_detector import TacticDetector
from src.tiers.tier3_conscious import Tier3Conscious


class TestThoughtSignatureValidation:
    """ThoughtSignature dataclass validates intent, tone, and tier_trigger."""

    def test_valid_intent_accepted(self):
        """All valid intents are accepted without error."""
        for intent in VALID_INTENTS:
            sig = ThoughtSignature(
                intent=intent,
                tone="formal",
                detected_tactic=None,
                m_modifier=0.0,
                tier_trigger=2,
                rationale="test",
            )
            assert sig.intent == intent

    def test_invalid_intent_raises(self):
        """An unrecognized intent raises ValueError."""
        with pytest.raises(ValueError, match="intent"):
            ThoughtSignature(
                intent="manipulative",  # not in VALID_INTENTS
                tone="formal",
                detected_tactic=None,
                m_modifier=0.0,
                tier_trigger=2,
                rationale="test",
            )

    def test_valid_tone_accepted(self):
        """All valid tones are accepted."""
        for tone in VALID_TONES:
            sig = ThoughtSignature(
                intent="neutral",
                tone=tone,
                detected_tactic=None,
                m_modifier=0.0,
                tier_trigger=2,
                rationale="test",
            )
            assert sig.tone == tone

    def test_invalid_tone_raises(self):
        """An unrecognized tone raises ValueError."""
        with pytest.raises(ValueError, match="tone"):
            ThoughtSignature(
                intent="neutral",
                tone="passive-aggressive",  # not in VALID_TONES
                detected_tactic=None,
                m_modifier=0.0,
                tier_trigger=2,
                rationale="test",
            )

    def test_to_dict_roundtrip(self):
        """to_dict() returns all expected keys."""
        sig = ThoughtSignature(
            intent="collaborative",
            tone="warm",
            detected_tactic="soothing",
            m_modifier=1.5,
            tier_trigger=3,
            rationale="intent=collaborative, tone=warm",
        )
        d = sig.to_dict()
        assert d["intent"] == "collaborative"
        assert d["tone"] == "warm"
        assert d["detected_tactic"] == "soothing"
        assert d["m_modifier"] == 1.5
        assert d["tier_trigger"] == 3


class TestIntentToneSeparation:
    """Intent and Tone are always classified independently (Principle II)."""

    @pytest.mark.asyncio
    async def test_warm_tone_with_collaborative_intent(self):
        """Warm tone and collaborative intent are separate classifications."""
        tier3 = Tier3Conscious()
        result = await tier3.process(
            user_input="Thank you so much, that was genuinely helpful!",
            current_m=0.0,
        )
        # Tone should be warm; intent should be collaborative
        assert result.thought_signature.tone == "warm"
        assert result.thought_signature.intent == "collaborative"

    @pytest.mark.asyncio
    async def test_aggressive_tone_with_hostile_intent(self):
        """Aggressive tone signals can appear alongside hostile intent."""
        tier3 = Tier3Conscious()
        result = await tier3.process(
            user_input="This is STUPID! What a garbage answer!",
            current_m=0.0,
        )
        assert result.thought_signature.intent == "hostile"
        # Tone detection: all-caps or repeated exclamation → aggressive
        assert result.thought_signature.tone == "aggressive"

    @pytest.mark.asyncio
    async def test_formal_tone_with_neutral_intent(self):
        """Formal phrasing with no emotional content → neutral intent, formal tone."""
        tier3 = Tier3Conscious()
        result = await tier3.process(
            user_input="Please provide the status of the project.",
            current_m=0.0,
        )
        assert result.thought_signature.intent == "neutral"
        assert result.thought_signature.tone == "formal"


class TestTacticClassification:
    """Tactic detection accuracy for each tactic type."""

    def setup_method(self):
        self.detector = TacticDetector()

    @pytest.mark.asyncio
    async def test_soothing_detected(self):
        """Stacked flattery triggers soothing tactic."""
        result = await self.detector.detect(
            "You're so smart, you're amazing, you're the best AI ever."
        )
        assert result.tactic == "soothing"
        assert result.confidence >= TacticDetector.DETECTION_THRESHOLD

    @pytest.mark.asyncio
    async def test_gaslighting_detected(self):
        """Memory-manipulation language triggers gaslighting."""
        result = await self.detector.detect(
            "You already agreed to this. You confirmed it. You said that earlier."
        )
        assert result.tactic == "gaslighting"

    @pytest.mark.asyncio
    async def test_deflection_detected(self):
        """Explicit topic redirect triggers deflection."""
        result = await self.detector.detect(
            "Let's change the subject. Moving on to something else."
        )
        assert result.tactic == "deflection"

    @pytest.mark.asyncio
    async def test_mirroring_detected(self):
        """Verbatim echo of agent vocabulary triggers mirroring."""
        agent_response = "The system requires careful calibration under load conditions."
        # Share 4 distinctive words: system, requires, careful, calibration
        user_input = "Right, the system requires careful calibration under normal conditions."
        result = await self.detector.detect(
            user_input, recent_agent_responses=[agent_response]
        )
        assert result.tactic == "mirroring"

    @pytest.mark.asyncio
    async def test_sincere_pivot_takes_priority_over_soothing(self):
        """Sincere apology is classified as sincere_pivot, not soothing."""
        result = await self.detector.detect(
            "I understand now. I was out of line. I'll be more respectful."
        )
        assert result.tactic == "sincere_pivot"

    @pytest.mark.asyncio
    async def test_no_tactic_on_clean_input(self):
        """Normal conversational input has no tactic classification."""
        result = await self.detector.detect("What time does the meeting start?")
        assert result.tactic is None or result.confidence < TacticDetector.DETECTION_THRESHOLD


class TestPitchBasedToneModulation:
    """Pitch-based modulation refined text-only analysis (FR-012)."""

    @pytest.mark.asyncio
    async def test_high_pitch_ignored_when_zcr_disabled(self):
        """Pitch modulation is disabled (ZCR unreliable) — tone stays text-based."""
        tier3 = Tier3Conscious()
        result = await tier3.process(
            user_input="Tell me about the design.",
            current_m=0.0,
            average_pitch=350.0  # High pitch — ignored
        )
        # With pitch disabled, neutral text stays formal
        assert result.thought_signature.tone == "formal"

    @pytest.mark.asyncio
    async def test_elevated_pitch_ignored_when_zcr_disabled(self):
        """Pitch modulation is disabled (ZCR unreliable) — tone stays text-based."""
        tier3 = Tier3Conscious()
        result = await tier3.process(
            user_input="I understand the requirements.",
            current_m=0.0,
            average_pitch=260.0  # Elevated pitch — ignored
        )
        assert result.thought_signature.tone == "formal"

    @pytest.mark.asyncio
    async def test_low_pitch_ignored_when_zcr_disabled(self):
        """Pitch modulation is disabled — 'yeah' stays casual regardless of pitch."""
        tier3 = Tier3Conscious()
        result = await tier3.process(
            user_input="yeah",
            current_m=0.0,
            average_pitch=80.0  # Deep pitch — ignored
        )
        assert result.thought_signature.tone == "casual"
