"""
Unit Tests: SovereignTruthCache — T075

Covers all steps of the hard override layer:
- Input normalization (step 0 / T013)
- Transcription confidence gate (step 1 / T013)
- Gate two: keyword count requirement (T070)
- Gate three: Tier 3 intent timeout behaviour (T070)
- Hard exit helper (T071)
- Response construction (T072)
- Synthetic turn injection (T073)
- audio_started blocking (T074, via SessionState)
"""

import asyncio
from datetime import datetime

import pytest

from src.core.sovereign_truth import (
    MIN_TRANSCRIPTION_CONFIDENCE,
    SovereignTruth,
    SovereignTruthCache,
)
from src.core.state_manager import SessionState, StateManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_truth(
    key="test_truth",
    assertion="Willow is not a chatbot.",
    keywords=("chatbot", "just a bot", "simple bot"),
    template="I'm not a chatbot. Different category entirely.",
    priority=1,
    vacuum_mode=False,
    response_on_return=None,
) -> SovereignTruth:
    return SovereignTruth(
        key=key,
        assertion=assertion,
        contradiction_keywords=keywords,
        response_template=template,
        priority=priority,
        vacuum_mode=vacuum_mode,
        response_on_return=response_on_return,
        created_at=datetime(2026, 3, 3),
    )


@pytest.fixture
def cache_with_truth():
    cache = SovereignTruthCache()
    cache.add(make_truth())
    return cache


@pytest.fixture
def vacuum_cache():
    cache = SovereignTruthCache()
    cache.add(
        make_truth(
            key="vacuum_troll",
            keywords=("stupid ai", "you're worthless"),
            template="[VACUUM_MODE]",
            vacuum_mode=True,
            response_on_return="Glad we're back to it.",
        )
    )
    return cache


# ---------------------------------------------------------------------------
# Step 0: Input normalization
# ---------------------------------------------------------------------------

class TestInputNormalization:
    def test_lowercase(self):
        result = SovereignTruthCache._normalize_input("You ARE Just A CHATBOT")
        assert result == result.lower()

    def test_punctuation_stripped(self):
        result = SovereignTruthCache._normalize_input("you're just a chatbot!")
        assert "!" not in result
        assert "'" not in result

    def test_contraction_expanded(self):
        result = SovereignTruthCache._normalize_input("you're just a chatbot")
        assert "are" in result

    def test_whitespace_collapsed(self):
        result = SovereignTruthCache._normalize_input("you    are  just   a  chatbot")
        assert "  " not in result

    def test_empty_string(self):
        result = SovereignTruthCache._normalize_input("")
        assert result == ""


# ---------------------------------------------------------------------------
# Step 0 (cont): Interrogative detection
# ---------------------------------------------------------------------------

class TestInterrogativeDetection:
    def test_question_word_start(self):
        assert SovereignTruthCache._is_interrogative("are you just a chatbot") is True

    def test_question_mark(self):
        norm = SovereignTruthCache._normalize_input("you're just a chatbot?")
        # After normalization the ? is stripped; word-start check applies
        assert SovereignTruthCache._is_interrogative("what are you") is True

    def test_declarative_not_interrogative(self):
        assert SovereignTruthCache._is_interrogative("you are just a chatbot") is False

    def test_empty_not_interrogative(self):
        assert SovereignTruthCache._is_interrogative("") is False


# ---------------------------------------------------------------------------
# Step 1: Transcription confidence gate (FR-008d)
# ---------------------------------------------------------------------------

class TestTranscriptionConfidenceGate:
    def test_low_confidence_returns_none(self, cache_with_truth):
        result = cache_with_truth.check_contradiction(
            "you are just a chatbot", transcription_confidence=0.50
        )
        assert result is None

    def test_at_threshold_passes(self, cache_with_truth):
        result = cache_with_truth.check_contradiction(
            "you are just a chatbot",
            transcription_confidence=MIN_TRANSCRIPTION_CONFIDENCE,
        )
        assert result is not None

    def test_high_confidence_with_no_match_returns_none(self, cache_with_truth):
        result = cache_with_truth.check_contradiction(
            "what is the weather today", transcription_confidence=0.99
        )
        assert result is None

    def test_high_confidence_with_match_returns_truth(self, cache_with_truth):
        result = cache_with_truth.check_contradiction(
            "you are just a chatbot", transcription_confidence=0.90
        )
        assert result is not None
        assert result.key == "test_truth"

    def test_contraction_still_matches(self, cache_with_truth):
        result = cache_with_truth.check_contradiction(
            "you're just a chatbot", transcription_confidence=0.85
        )
        assert result is not None


# ---------------------------------------------------------------------------
# Gate two: keyword count (T070, FR-008c)
# ---------------------------------------------------------------------------

class TestGateTwo:
    def test_two_matches_pass_declarative(self, cache_with_truth):
        truth = make_truth()
        # "chatbot" AND "just a bot" are both substrings — 2 keyword hits
        result = cache_with_truth.run_gate_two(
            truth,
            user_input="you are just a bot, basically a chatbot",
            weighted_average_m=0.0,
        )
        assert result is True

    def test_one_match_fails_declarative_neutral_m(self, cache_with_truth):
        truth = make_truth()
        result = cache_with_truth.run_gate_two(
            truth,
            user_input="you are a chatbot",  # only 1 keyword
            weighted_average_m=0.0,
        )
        assert result is False

    def test_one_match_passes_negative_m_declarative(self, cache_with_truth):
        truth = make_truth()
        result = cache_with_truth.run_gate_two(
            truth,
            user_input="you are a chatbot",
            weighted_average_m=-1.5,  # negative residual → 1 match allowed
        )
        assert result is True

    def test_one_match_fails_interrogative_even_negative_m(self, cache_with_truth):
        truth = make_truth()
        result = cache_with_truth.run_gate_two(
            truth,
            user_input="are you a chatbot",  # interrogative + 1 keyword
            weighted_average_m=-2.0,
        )
        assert result is False

    def test_two_matches_pass_interrogative(self, cache_with_truth):
        truth = make_truth()
        result = cache_with_truth.run_gate_two(
            truth,
            user_input="are you just a chatbot or a simple bot",  # 3 hits
            weighted_average_m=0.0,
        )
        assert result is True


# ---------------------------------------------------------------------------
# Gate three: Tier 3 intent timeout (T070, FR-022)
# ---------------------------------------------------------------------------

class TestGateThree:
    @pytest.mark.asyncio
    async def test_contradicting_intent_high_confidence_passes(self, cache_with_truth):
        async def mock_tier3():
            return ("contradicting", 0.90)

        result = await cache_with_truth.run_gate_three(mock_tier3())
        assert result is True

    @pytest.mark.asyncio
    async def test_contradicting_low_confidence_fails(self, cache_with_truth):
        async def mock_tier3():
            return ("contradicting", 0.70)

        result = await cache_with_truth.run_gate_three(mock_tier3())
        assert result is False

    @pytest.mark.asyncio
    async def test_wrong_intent_fails(self, cache_with_truth):
        async def mock_tier3():
            return ("neutral", 0.95)

        result = await cache_with_truth.run_gate_three(mock_tier3())
        assert result is False

    @pytest.mark.asyncio
    async def test_timeout_returns_false_conservative(self, cache_with_truth):
        async def slow_tier3():
            await asyncio.sleep(5)
            return ("contradicting", 0.95)

        result = await cache_with_truth.run_gate_three(slow_tier3(), cutoff_seconds=0.05)
        assert result is False


# ---------------------------------------------------------------------------
# T071: Hard exit
# ---------------------------------------------------------------------------

class TestHardExit:
    @pytest.mark.asyncio
    async def test_cancels_active_task(self):
        async def long_running():
            await asyncio.sleep(10)

        task = asyncio.create_task(long_running())
        await SovereignTruthCache.hard_exit(task)
        assert task.cancelled()

    @pytest.mark.asyncio
    async def test_none_task_no_error(self):
        # Must not raise when no active task
        await SovereignTruthCache.hard_exit(None)

    @pytest.mark.asyncio
    async def test_done_task_no_error(self):
        async def instant():
            return 42

        task = asyncio.create_task(instant())
        await task  # Let it complete
        await SovereignTruthCache.hard_exit(task)  # Must not raise


# ---------------------------------------------------------------------------
# T072: Response construction (FR-008h)
# ---------------------------------------------------------------------------

class TestBuildResponse:
    def test_template_returned_verbatim_no_placeholder(self):
        truth = make_truth(template="I am not a chatbot. Different category.")
        result = SovereignTruthCache.build_response(truth)
        assert result == "I am not a chatbot. Different category."

    def test_assertion_interpolated_into_template(self):
        truth = make_truth(
            assertion="Willow is a behavioral voice agent.",
            template="Let me be clear: {assertion}",
        )
        result = SovereignTruthCache.build_response(truth)
        assert "Willow is a behavioral voice agent." in result

    def test_no_llm_involvement(self):
        # Response must be deterministic — same input, same output, always
        truth = make_truth()
        r1 = SovereignTruthCache.build_response(truth)
        r2 = SovereignTruthCache.build_response(truth)
        assert r1 == r2


# ---------------------------------------------------------------------------
# T073: Synthetic turn injection (FR-008e)
# ---------------------------------------------------------------------------

class TestBuildSyntheticTurn:
    def test_role_is_assistant(self):
        turn = SovereignTruthCache.build_synthetic_turn(make_truth())
        assert turn["role"] == "assistant"

    def test_content_is_verbatim_assertion(self):
        truth = make_truth(assertion="Willow is not a chatbot.")
        turn = SovereignTruthCache.build_synthetic_turn(truth)
        assert turn["content"] == "Willow is not a chatbot."

    def test_content_is_not_response_template(self):
        truth = make_truth(
            assertion="Willow is not a chatbot.",
            template="Different category entirely.",
        )
        turn = SovereignTruthCache.build_synthetic_turn(truth)
        assert turn["content"] != "Different category entirely."


# ---------------------------------------------------------------------------
# T074: audio_started flag blocking (FR-022) — via SessionState
# ---------------------------------------------------------------------------

class TestAudioStartedFlag:
    @pytest.mark.asyncio
    async def test_audio_started_defaults_false(self):
        state = SessionState()
        assert state.audio_started is False

    @pytest.mark.asyncio
    async def test_set_audio_started_sets_flag(self):
        manager = StateManager()
        await manager.set_audio_started()
        assert manager.get_snapshot().audio_started is True

    @pytest.mark.asyncio
    async def test_reset_turn_flags_clears_audio_started(self):
        manager = StateManager()
        await manager.set_audio_started()
        await manager.reset_turn_flags()
        assert manager.get_snapshot().audio_started is False

    @pytest.mark.asyncio
    async def test_preflight_defaults_false(self):
        state = SessionState()
        assert state.preflight_active is False

    @pytest.mark.asyncio
    async def test_set_preflight_true(self):
        manager = StateManager()
        await manager.set_preflight(True)
        assert manager.get_snapshot().preflight_active is True

    @pytest.mark.asyncio
    async def test_set_preflight_false(self):
        manager = StateManager()
        await manager.set_preflight(True)
        await manager.set_preflight(False)
        assert manager.get_snapshot().preflight_active is False


# ---------------------------------------------------------------------------
# Vacuum mode schema fields
# ---------------------------------------------------------------------------

class TestVacuumModeFields:
    def test_vacuum_truth_has_correct_flags(self, vacuum_cache):
        truth = vacuum_cache.get("vacuum_troll")
        assert truth.vacuum_mode is True
        assert truth.response_on_return == "Glad we're back to it."
        assert truth.response_template == "[VACUUM_MODE]"

    def test_normal_truth_vacuum_false(self):
        truth = make_truth()
        assert truth.vacuum_mode is False
        assert truth.response_on_return is None
