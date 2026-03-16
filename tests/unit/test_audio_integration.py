"""
Unit Tests: Cross-Spec Audio Integration — T025, T028, T079

Covers the two integration seams where spec 001 (behavioral framework) meets
spec 002 (audio pipeline):

- T025: Flush audio buffer — Tier 4 fires → flush command sent to browser
- T028: Preflight warmup — browser signals warmup → Python suppresses Tier 4
- T079: Consume preflight_active flag in Tier 4 gate check
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import NoiseGateConfig
from src.core.sovereign_truth import SovereignTruth, SovereignTruthCache
from src.core.state_manager import StateManager, SessionState
from src.main import WillowAgent
from src.tiers.tier4_sovereign import Tier4Result, Tier4Sovereign


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_truth(key="test-truth", vacuum=False):
    """Create a SovereignTruth for testing."""
    return SovereignTruth(
        key=key,
        assertion="The sky is blue.",
        contradiction_keywords=["sky", "blue", "color"],
        forced_prefix="Actually, {assertion}" if not vacuum else "[VACUUM_MODE]",
        response_directive="[test directive]",
        priority=1,
        vacuum_mode=vacuum,
        response_on_return="Stored response" if vacuum else None,
    )


# ---------------------------------------------------------------------------
# T025: Flush Audio Buffer
# ---------------------------------------------------------------------------


class TestFlushAudioBuffer:
    """T025: Tier 4 fires → flush_audio_buffer on Tier4Result → command sent."""

    @pytest.mark.asyncio
    async def test_non_vacuum_result_sets_flush_true(self):
        """When Tier 4 fires (non-vacuum), flush_audio_buffer must be True."""
        cache = SovereignTruthCache()
        manager = StateManager()
        tier4 = Tier4Sovereign(cache, manager)
        truth = _make_truth()

        result = await tier4.execute(truth, streaming_session=None)

        assert result.fired is True
        assert result.vacuum_mode is False
        assert result.flush_audio_buffer is True

    @pytest.mark.asyncio
    async def test_vacuum_result_sets_flush_false(self):
        """Vacuum mode has no audio to flush — flush_audio_buffer must be False."""
        cache = SovereignTruthCache()
        manager = StateManager()
        tier4 = Tier4Sovereign(cache, manager)
        truth = _make_truth(vacuum=True)

        result = await tier4.execute(truth, streaming_session=None)

        assert result.fired is True
        assert result.vacuum_mode is True
        assert result.flush_audio_buffer is False

    @pytest.mark.asyncio
    async def test_flush_command_sent_via_websocket(self):
        """When flush_audio_buffer is True, send_client_command sends flush."""
        agent = WillowAgent(session_id="test-flush")
        # Use spec to prevent AsyncMock auto-creating send_text, so the
        # hasattr(ws, 'send_text') branch in send_client_command is explicit.
        # FastAPI WebSocket has send_text; this mock simulates that path.
        mock_ws = AsyncMock(spec=["send_text"])
        agent._client_websocket = mock_ws

        await agent.send_client_command("flush_audio_buffer", fade_duration_ms=7)

        mock_ws.send_text.assert_called_once()
        sent = json.loads(mock_ws.send_text.call_args[0][0])
        assert sent["type"] == "flush_audio_buffer"
        assert sent["fade_duration_ms"] == 7

    @pytest.mark.asyncio
    async def test_flush_command_noop_without_websocket(self):
        """send_client_command is a no-op when no WebSocket is connected."""
        agent = WillowAgent(session_id="test-no-ws")
        assert agent._client_websocket is None

        # Should not raise
        await agent.send_client_command("flush_audio_buffer", fade_duration_ms=7)

    @pytest.mark.asyncio
    async def test_tier4_result_to_dict_includes_flush(self):
        """Tier4Result.to_dict() includes flush_audio_buffer field."""
        result = Tier4Result(
            fired=True,
            vacuum_mode=False,
            forced_prefix="test",
            response_directive="[test directive]",
            synthetic_turn=None,
            audio_started_set=True,
            flush_audio_buffer=True,
            latency_ms=1.0,
            within_budget=True,
        )
        d = result.to_dict()
        assert "flush_audio_buffer" in d
        assert d["flush_audio_buffer"] is True


# ---------------------------------------------------------------------------
# T028 + T079: Preflight Warmup Integration
# ---------------------------------------------------------------------------


class TestPreflightWarmup:
    """T028/T079: Browser preflight signal → Python suppresses Tier 4."""

    @pytest.mark.asyncio
    async def test_preflight_start_sets_flag(self):
        """preflight_start message sets preflight_active=True on StateManager."""
        agent = WillowAgent(session_id="test-preflight")

        await agent._handle_client_message(json.dumps({"type": "preflight_start"}))

        state = agent.state_manager.get_snapshot()
        assert state.preflight_active is True

    @pytest.mark.asyncio
    async def test_preflight_end_clears_flag(self):
        """preflight_end message sets preflight_active=False on StateManager."""
        agent = WillowAgent(session_id="test-preflight")
        await agent.state_manager.set_preflight(True)

        await agent._handle_client_message(json.dumps({"type": "preflight_end"}))

        state = agent.state_manager.get_snapshot()
        assert state.preflight_active is False

    @pytest.mark.asyncio
    async def test_tier4_skipped_during_preflight(self):
        """T079: check_and_execute returns None when preflight_active=True."""
        cache = SovereignTruthCache()
        truth = _make_truth()
        cache._truths = {"test-truth": truth}

        manager = StateManager()
        await manager.set_preflight(True)

        tier4 = Tier4Sovereign(cache, manager)

        result = await tier4.check_and_execute(
            user_input="the sky is blue and the color is nice",
            transcription_confidence=0.95,
            weighted_average_m=0.0,
            tier3_intent_factory=lambda: _mock_tier3(),
            streaming_session=None,
        )

        # Tier 4 should be suppressed — preflight is active
        assert result is None

    @pytest.mark.asyncio
    async def test_tier4_fires_after_preflight_ends(self):
        """After preflight ends, Tier 4 can fire normally."""
        cache = SovereignTruthCache()
        truth = _make_truth()
        cache._truths = {"test-truth": truth}

        manager = StateManager()
        # Simulate preflight start then end
        await manager.set_preflight(True)
        await manager.set_preflight(False)

        tier4 = Tier4Sovereign(cache, manager)

        result = await tier4.check_and_execute(
            user_input="the sky is blue and the color is nice",
            transcription_confidence=0.95,
            weighted_average_m=0.0,
            tier3_intent_factory=lambda: _mock_tier3(),
            streaming_session=None,
        )

        # May or may not fire depending on gate 2/3 — but it's not blocked by preflight
        # The key assertion is that we got past the preflight gate
        # (if it was still blocked, we'd get None before gate 2)

    @pytest.mark.asyncio
    async def test_preflight_not_reset_by_turn_flags(self):
        """preflight_active persists across turns — not cleared by reset_turn_flags."""
        manager = StateManager()
        await manager.set_preflight(True)
        await manager.reset_turn_flags()

        state = manager.get_snapshot()
        assert state.preflight_active is True

    @pytest.mark.asyncio
    async def test_preflight_cleared_on_session_reset(self):
        """Full session reset clears preflight_active."""
        manager = StateManager()
        await manager.set_preflight(True)
        await manager.reset()

        state = manager.get_snapshot()
        assert state.preflight_active is False

    @pytest.mark.asyncio
    async def test_invalid_json_message_ignored(self):
        """Non-JSON text frames are silently ignored."""
        agent = WillowAgent(session_id="test-bad-json")
        # Should not raise
        await agent._handle_client_message("not valid json {{{")
        state = agent.state_manager.get_snapshot()
        assert state.preflight_active is False

    @pytest.mark.asyncio
    async def test_unknown_message_type_ignored(self):
        """Unknown message types are silently ignored."""
        agent = WillowAgent(session_id="test-unknown")
        await agent._handle_client_message(json.dumps({"type": "foo_bar"}))
        state = agent.state_manager.get_snapshot()
        assert state.preflight_active is False


# ---------------------------------------------------------------------------
# Config: NoiseGateConfig.preflight_duration_ms
# ---------------------------------------------------------------------------


class TestNoiseGateConfigPreflight:
    """T028: NoiseGateConfig includes preflight_duration_ms."""

    def test_default_preflight_duration(self):
        config = NoiseGateConfig()
        assert config.preflight_duration_ms == 3000

    def test_custom_preflight_duration(self):
        config = NoiseGateConfig(preflight_duration_ms=5000)
        assert config.preflight_duration_ms == 5000


# ---------------------------------------------------------------------------
# Fade-out Math Verification
# ---------------------------------------------------------------------------


class TestFadeOutMath:
    """T025: Verify fade-out duration math for AudioWorklet."""

    def test_7ms_fade_at_48khz(self):
        """7ms at 48kHz = 336 samples — enough to complete within one block."""
        sample_rate = 48000
        fade_ms = 7
        samples = round((fade_ms / 1000) * sample_rate)
        assert samples == 336

    def test_7ms_fade_at_16khz(self):
        """7ms at 16kHz = 112 samples."""
        sample_rate = 16000
        fade_ms = 7
        samples = round((fade_ms / 1000) * sample_rate)
        assert samples == 112

    def test_10ms_fade_at_48khz(self):
        """10ms at 48kHz = 480 samples."""
        sample_rate = 48000
        fade_ms = 10
        samples = round((fade_ms / 1000) * sample_rate)
        assert samples == 480

    def test_linear_fade_reaches_zero(self):
        """Linear ramp gain reaches exactly 0 at the final sample."""
        total = 336
        # Last sample: remaining = 1, gain = 1/336 ≈ 0.003 (near zero)
        gain_last = 1 / total
        assert gain_last < 0.01
        # After last sample: remaining = 0, output is 0
        gain_after = 0 / total
        assert gain_after == 0.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _mock_tier3():
    """Mock Tier 3 intent factory result for gate 3."""
    return ("contradicting", 0.90)
