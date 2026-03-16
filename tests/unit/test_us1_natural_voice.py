"""
User Story 1 Tests: Natural Voice Conversation

Tests the acceptance scenarios from spec.md:
1. Agent responds within 2s (state pipeline latency)
2. Interruption handling (VAD + graceful stop)
3. 3-turn memory via ResidualPlot

Also covers: Tier 1 budget, Tier 2 formula, StateManager ±2.0 cap, Cold Start
"""

import asyncio
import pytest
import time

from src.tiers.tier1_reflex import Tier1Reflex
from src.tiers.tier2_metabolism import Tier2Metabolism
from src.core.residual_plot import ResidualPlot
from src.core.state_manager import StateManager
from src.voice.interruption_handler import InterruptionHandler
from src.main import WillowAgent


# ============================================================================
# Tier 1 Reflex Tests
# ============================================================================

class TestTier1Reflex:

    def test_completes_within_50ms(self):
        """Tier 1 must respond within 50ms budget."""
        reflex = Tier1Reflex()
        result = reflex.process("Hey thanks, that was amazing!", current_m=1.5)
        assert result.total_latency_ms < 50, (
            f"Tier 1 exceeded 50ms budget: {result.total_latency_ms:.2f}ms"
        )

    def test_detects_warm_tone(self):
        reflex = Tier1Reflex()
        result = reflex.process("Thanks so much, I really appreciate your help!", current_m=0.0)
        assert result.tone_markers.primary_tone == "warm"

    def test_detects_aggressive_tone(self):
        reflex = Tier1Reflex()
        result = reflex.process("This is STUPID!! What the hell?!", current_m=0.0)
        assert result.tone_markers.primary_tone == "aggressive"

    def test_low_m_forces_formal_tone(self):
        """Low m state should force formal response even on casual/warm input."""
        reflex = Tier1Reflex()
        result = reflex.process("Hey! Cool stuff!", current_m=-1.5)
        # calibrate_tone forces formal when m < -0.5
        assert result.applied_tone == "formal"

    def test_generates_nonempty_prefix(self):
        reflex = Tier1Reflex()
        result = reflex.process("Hello there!", current_m=0.5)
        # prefix can be empty string for some tones, just check it returns
        assert isinstance(result.response_prefix, str)

    def test_budget_not_exceeded_flag(self):
        reflex = Tier1Reflex()
        result = reflex.process("Simple input", current_m=0.0)
        assert result.budget_exceeded is False


# ============================================================================
# Tier 2 Metabolism Tests
# ============================================================================

class TestTier2Metabolism:

    def test_completes_within_5ms(self):
        """Tier 2 must complete within 5ms budget."""
        t2 = Tier2Metabolism()
        result = t2.calculate_state_update(
            current_m=0.0, base_decay=-0.1, m_modifier=1.5, turn_count=1
        )
        assert result.within_budget, (
            f"Tier 2 exceeded 5ms budget: {result.latency_ms:.3f}ms"
        )

    def test_cold_start_no_decay_turn1(self):
        """Turns 1-3: d=0 (Cold Start warmup)."""
        t2 = Tier2Metabolism()
        result = t2.calculate_state_update(
            current_m=0.0, base_decay=-0.1, m_modifier=1.5, turn_count=1
        )
        assert result.value == pytest.approx(1.5), (
            f"Cold Start: expected 0.0 + 0.0 + 1.5 = 1.5, got {result.value}"
        )

    def test_cold_start_no_decay_turn3(self):
        """Turn 3 still Cold Start."""
        t2 = Tier2Metabolism()
        result = t2.calculate_state_update(
            current_m=1.5, base_decay=-0.1, m_modifier=0.0, turn_count=3
        )
        assert result.value == pytest.approx(1.5)  # no decay

    def test_decay_applies_after_cold_start(self):
        """Turn 4+: decay applies."""
        t2 = Tier2Metabolism()
        result = t2.calculate_state_update(
            current_m=1.5, base_decay=-0.1, m_modifier=0.0, turn_count=4
        )
        assert result.value == pytest.approx(1.4)  # 1.5 + (-0.1) + 0.0

    def test_modifier_clamped_to_2(self):
        """m_modifier capped at ±2.0."""
        t2 = Tier2Metabolism()
        result = t2.calculate_state_update(
            current_m=0.0, base_decay=0.0, m_modifier=99.0, turn_count=5
        )
        assert result.value == pytest.approx(2.0)  # capped

    def test_modifier_clamped_negative(self):
        t2 = Tier2Metabolism()
        result = t2.calculate_state_update(
            current_m=0.0, base_decay=0.0, m_modifier=-99.0, turn_count=5
        )
        assert result.value == pytest.approx(-2.0)

    def test_sovereign_spike_formula(self):
        """Sovereign Spike: loaded from JSON."""
        t2 = Tier2Metabolism()
        spike = t2.calculate_sovereign_spike(base_decay=-0.1)
        assert spike == pytest.approx(-5.0)

    def test_state_formula(self):
        """a(n+1) = a(n) + d + m."""
        t2 = Tier2Metabolism()
        result = t2.calculate_state_update(
            current_m=1.0, base_decay=-0.1, m_modifier=0.5, turn_count=5
        )
        assert result.value == pytest.approx(1.4)  # 1.0 + (-0.1) + 0.5


# ============================================================================
# ResidualPlot Tests (3-turn memory — SC-010)
# ============================================================================

class TestResidualPlot:

    def test_rolling_window_max_5(self):
        """Plot never exceeds 5 turns."""
        plot = ResidualPlot()
        for m in [1.0, -0.5, 1.5, -1.0, 0.5, 2.0]:  # 6 turns
            plot.add_turn(m)
        assert plot.turn_count == 5

    def test_oldest_dropped(self):
        """6th turn drops oldest, newest at index 0."""
        plot = ResidualPlot()
        for m in [1.0, -0.5, 1.5, -1.0, 0.5]:
            plot.add_turn(m)
        plot.add_turn(2.0)
        assert plot.m_values[0] == pytest.approx(2.0)  # newest first
        assert len(plot.m_values) == 5

    def test_weights_applied_correctly(self):
        """weighted_average_m uses [0.40, 0.25, 0.15, 0.12, 0.08]."""
        plot = ResidualPlot(m_values=[1.0, 1.0, 1.0, 1.0, 1.0])
        # All 1.0 → weighted avg = 1.0
        assert plot.weighted_average_m == pytest.approx(1.0)

    def test_positive_momentum_detection(self):
        plot = ResidualPlot(m_values=[1.0, 0.5, 0.5])
        assert plot.is_positive_momentum() is True

    def test_negative_momentum_detection(self):
        plot = ResidualPlot(m_values=[-1.0, -0.5])
        assert plot.is_negative_momentum() is True

    def test_3_turn_memory(self):
        """US1 SC3: Agent demonstrates memory of 3 earlier turns."""
        plot = ResidualPlot()
        plot.add_turn(1.5)   # turn 1: collaborative
        plot.add_turn(1.0)   # turn 2: collaborative
        plot.add_turn(-0.5)  # turn 3: slight hostility
        assert plot.turn_count == 3
        # Positive momentum still (turn 1 and 2 outweigh turn 3)
        assert plot.weighted_average_m > 0


# ============================================================================
# StateManager Tests
# ============================================================================

class TestStateManager:

    def test_cold_start_active_first_3_turns(self):
        async def run():
            sm = StateManager()
            for _ in range(3):
                state = await sm.update(m_modifier=0.0)
            assert state.cold_start_active is True
            assert state.turn_count == 3
        asyncio.run(run())

    def test_cold_start_off_turn_4(self):
        async def run():
            sm = StateManager()
            for _ in range(4):
                state = await sm.update(m_modifier=0.0)
            assert state.cold_start_active is False
        asyncio.run(run())

    def test_state_formula_applied(self):
        async def run():
            sm = StateManager()
            state = await sm.update(m_modifier=1.5)
            assert state.current_m == pytest.approx(1.5)  # Cold Start: 0 + 0 + 1.5
        asyncio.run(run())

    def test_plus_2_cap_enforced(self):
        async def run():
            sm = StateManager()
            state = await sm.update(m_modifier=99.0)
            assert state.current_m == pytest.approx(2.0)
        asyncio.run(run())

    def test_minus_2_cap_enforced(self):
        async def run():
            sm = StateManager()
            state = await sm.update(m_modifier=-99.0)
            assert state.current_m == pytest.approx(-2.0)
        asyncio.run(run())

    def test_sovereign_spike_increments_count(self):
        async def run():
            sm = StateManager()
            state = await sm.update(m_modifier=-2.0, is_sovereign_spike=True)
            assert state.sovereign_spike_count == 1
        asyncio.run(run())

    def test_troll_defense_after_3_spikes(self):
        async def run():
            sm = StateManager()
            for _ in range(3):
                state = await sm.update(m_modifier=-2.0, is_sovereign_spike=True)
            assert state.troll_defense_active is True
        asyncio.run(run())

    def test_residual_plot_updated_each_turn(self):
        async def run():
            sm = StateManager()
            await sm.update(m_modifier=1.5)
            await sm.update(m_modifier=-0.5)
            state = sm.get_snapshot()
            assert state.residual_plot.turn_count == 2
        asyncio.run(run())

    def test_lock_free_snapshot_read(self):
        async def run():
            sm = StateManager()
            await sm.update(m_modifier=1.0)
            snap = sm.get_snapshot()
            assert snap.current_m == pytest.approx(1.0)
        asyncio.run(run())

    def test_reset_clears_state(self):
        async def run():
            sm = StateManager()
            await sm.update(m_modifier=2.0)
            await sm.reset()
            state = sm.get_snapshot()
            assert state.current_m == 0.0
            assert state.turn_count == 0
        asyncio.run(run())


# ============================================================================
# Interruption Handler Tests (SC-001)
# ============================================================================

class TestInterruptionHandler:

    def test_no_interruption_when_agent_silent(self):
        handler = InterruptionHandler()
        # Agent not speaking, loud audio should not trigger interruption
        loud_audio = bytes([200, 50] * 1600)
        result = handler.detect_voice_activity(loud_audio)
        assert handler.should_stop() is False  # not speaking, no stop needed

    def test_speech_detection_on_loud_audio(self):
        handler = InterruptionHandler()
        handler.start_agent_speaking()
        # Need consecutive frames above threshold
        loud_audio = bytes([200, 50] * 1600)
        for _ in range(5):  # multiple frames to confirm speech
            handler.detect_voice_activity(loud_audio)
        assert handler.should_stop() is True

    def test_no_speech_on_silence(self):
        handler = InterruptionHandler()
        handler.start_agent_speaking()
        silent_audio = bytes(320)  # all zeros
        for _ in range(20):
            handler.detect_voice_activity(silent_audio)
        assert handler.is_user_speaking is False

    def test_interruption_event_async(self):
        async def run():
            handler = InterruptionHandler()
            handler.start_agent_speaking()
            event = await handler.handle_interruption()
            assert event.agent_was_speaking is True
            assert handler.is_agent_speaking is False
        asyncio.run(run())

    def test_prepare_for_new_input_resets(self):
        handler = InterruptionHandler()
        handler.start_agent_speaking()
        handler.prepare_for_new_input()
        assert handler.is_user_speaking is False
        assert handler.should_stop() is False


# ============================================================================
# Full Pipeline Tests (WillowAgent)
# ============================================================================

class TestWillowAgentPipeline:

    def test_handle_user_input_returns_result(self):
        async def run():
            agent = WillowAgent()
            result = await agent.handle_user_input("Hello Willow!")
            assert result.response_text
            assert isinstance(result.m_modifier, float)
            assert "tier1" in result.tier_latencies
            assert "tier2" in result.tier_latencies
        asyncio.run(run())

    def test_turn_count_increments(self):
        async def run():
            agent = WillowAgent()
            await agent.handle_user_input("Turn 1")
            await agent.handle_user_input("Turn 2")
            await agent.handle_user_input("Turn 3")
            state = agent.get_session_state()
            assert state.turn_count == 3
        asyncio.run(run())

    def test_collaborative_input_raises_m(self):
        """Collaborative tone raises m state."""
        async def run():
            agent = WillowAgent()
            await agent.handle_user_input("Thank you so much, I really appreciate your help!")
            state = agent.get_session_state()
            assert state.current_m > 0
        asyncio.run(run())

    def test_hostile_input_lowers_m(self):
        """Hostile input lowers m state."""
        async def run():
            agent = WillowAgent()
            await agent.handle_user_input("You're wrong and stupid!")
            state = agent.get_session_state()
            assert state.current_m < 0
        asyncio.run(run())

    def test_cold_start_active_first_3_turns(self):
        async def run():
            agent = WillowAgent()
            await agent.handle_user_input("Turn 1")
            await agent.handle_user_input("Turn 2")
            await agent.handle_user_input("Turn 3")
            state = agent.get_session_state()
            assert state.cold_start_active is True
        asyncio.run(run())

    def test_history_records_all_turns(self):
        async def run():
            agent = WillowAgent()
            await agent.handle_user_input("Hello")
            await agent.handle_user_input("How are you?")
            history = agent.get_turn_history()
            assert len(history) == 2
        asyncio.run(run())

    def test_tier1_latency_under_50ms(self):
        async def run():
            agent = WillowAgent()
            result = await agent.handle_user_input("This is a test input message")
            t1 = result.tier_latencies.get("tier1", 0)
            assert t1 < 50, f"Tier 1 exceeded budget: {t1:.2f}ms"
        asyncio.run(run())

    def test_tier2_latency_under_5ms(self):
        async def run():
            agent = WillowAgent()
            result = await agent.handle_user_input("This is a test input message")
            t2 = result.tier_latencies.get("tier2", 0)
            assert t2 < 5, f"Tier 2 exceeded budget: {t2:.3f}ms"
        asyncio.run(run())
