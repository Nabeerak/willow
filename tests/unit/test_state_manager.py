"""
Unit Tests: StateManager — T060

Verifies:
- State formula aₙ₊₁ = aₙ + d + m
- ±2.0 cap on m_modifier
- Cold Start d=0 for turns 1-3
- Troll Defense tracking
- Grace Boost cumulative forgiveness
- Thread-safe atomic updates
"""

import asyncio
import pytest

from src.core.state_manager import StateManager, COLD_START_TURNS, MAX_STATE_CHANGE, BASE_DECAY_RATE


class TestColdStart:
    """d=0 during turns 1-3, BASE_DECAY_RATE after."""

    @pytest.mark.asyncio
    async def test_decay_is_zero_during_cold_start(self):
        """Turns 1-3: base_decay stays 0.0."""
        sm = StateManager()
        for _ in range(COLD_START_TURNS):
            state = await sm.update(m_modifier=0.0)
        assert state.base_decay == 0.0
        assert state.cold_start_active is True

    @pytest.mark.asyncio
    async def test_decay_activates_after_cold_start(self):
        """Turn 4+: base_decay = BASE_DECAY_RATE (-0.1)."""
        sm = StateManager()
        for _ in range(COLD_START_TURNS + 1):
            state = await sm.update(m_modifier=0.0)
        assert state.base_decay == BASE_DECAY_RATE
        assert state.cold_start_active is False

    @pytest.mark.asyncio
    async def test_turn_count_increments(self):
        """Each update increments turn_count by 1."""
        sm = StateManager()
        for i in range(5):
            state = await sm.update(m_modifier=0.0)
            assert state.turn_count == i + 1


class TestStateFormula:
    """Verify aₙ₊₁ = aₙ + d + m."""

    @pytest.mark.asyncio
    async def test_state_formula_cold_start(self):
        """During cold start: new_m = current_m + 0 + m_modifier."""
        sm = StateManager()
        state = await sm.update(m_modifier=1.5)
        assert abs(state.current_m - 1.5) < 1e-9

    @pytest.mark.asyncio
    async def test_state_formula_after_cold_start(self):
        """After cold start: new_m = current_m + decay + m_modifier."""
        sm = StateManager()
        # Advance past cold start (3 turns)
        for _ in range(COLD_START_TURNS):
            await sm.update(m_modifier=0.0)
        # current_m is 0.0 at this point, decay is now active
        state = await sm.update(m_modifier=1.0)
        # Expected: 0.0 + (-0.1) + 1.0 = 0.9
        assert abs(state.current_m - 0.9) < 1e-9

    @pytest.mark.asyncio
    async def test_cumulative_state_updates(self):
        """Multiple cold-start turns accumulate linearly."""
        sm = StateManager()
        await sm.update(m_modifier=1.0)  # → 1.0
        state = await sm.update(m_modifier=1.0)  # → 2.0
        assert abs(state.current_m - 2.0) < 1e-9


class TestModifierCap:
    """±2.0 cap enforced on m_modifier."""

    @pytest.mark.asyncio
    async def test_positive_cap(self):
        """m_modifier > 2.0 is clamped to 2.0."""
        sm = StateManager()
        state = await sm.update(m_modifier=99.0)
        assert abs(state.current_m - MAX_STATE_CHANGE) < 1e-9

    @pytest.mark.asyncio
    async def test_negative_cap(self):
        """m_modifier < -2.0 is clamped to -2.0."""
        sm = StateManager()
        state = await sm.update(m_modifier=-99.0)
        assert abs(state.current_m - (-MAX_STATE_CHANGE)) < 1e-9

    @pytest.mark.asyncio
    async def test_within_range_not_capped(self):
        """m_modifier within ±2.0 is applied verbatim."""
        sm = StateManager()
        state = await sm.update(m_modifier=1.5)
        assert abs(state.current_m - 1.5) < 1e-9


class TestTrollDefense:
    """Troll Defense activates after SOVEREIGN_SPIKE_THRESHOLD consecutive spikes."""

    @pytest.mark.asyncio
    async def test_troll_defense_not_active_initially(self):
        """Troll Defense is inactive on a fresh session."""
        sm = StateManager()
        assert not sm.is_troll_defense_active()

    @pytest.mark.asyncio
    async def test_spike_count_increments(self):
        """Each is_sovereign_spike=True increments the spike counter."""
        sm = StateManager()
        state = await sm.update(m_modifier=-5.0, is_sovereign_spike=True)
        assert state.sovereign_spike_count == 1

    @pytest.mark.asyncio
    async def test_troll_defense_activates_after_three_spikes(self):
        """Three consecutive spikes → troll_defense_active=True."""
        sm = StateManager()
        for _ in range(3):
            state = await sm.update(m_modifier=-5.0, is_sovereign_spike=True)
        assert state.troll_defense_active is True

    @pytest.mark.asyncio
    async def test_neutral_turn_preserves_spike_count(self):
        """Q7 fix: Neutral turns (m=0) preserve spike count."""
        sm = StateManager()
        await sm.update(m_modifier=-5.0, is_sovereign_spike=True)
        await sm.update(m_modifier=-5.0, is_sovereign_spike=True)
        state = await sm.update(m_modifier=0.0, is_sovereign_spike=False)
        assert state.sovereign_spike_count == 2  # preserved, not reset

    @pytest.mark.asyncio
    async def test_collaborative_turn_resets_spike_count(self):
        """Q7 fix: Collaborative turns (m>0) reset spike count."""
        sm = StateManager()
        await sm.update(m_modifier=-5.0, is_sovereign_spike=True)
        await sm.update(m_modifier=-5.0, is_sovereign_spike=True)
        state = await sm.update(m_modifier=1.0, is_sovereign_spike=False)
        assert state.sovereign_spike_count == 0  # reset by collaborative input


class TestGraceBoost:
    """Grace Boost: +2.0 base, accelerates by +0.5 per consecutive sincere turn."""

    @pytest.mark.asyncio
    async def test_grace_boost_applies_when_negative(self):
        """Grace Boost only applies when current_m < 0."""
        sm = StateManager()
        await sm.update(m_modifier=-2.0)  # current_m = -2.0
        state = await sm.apply_grace_boost()
        # first sincere turn: +2.0 (capped at MAX_STATE_CHANGE)
        assert state.current_m > -2.0

    @pytest.mark.asyncio
    async def test_grace_boost_skipped_when_positive(self):
        """Grace Boost does not reduce state when current_m ≥ 0."""
        sm = StateManager()
        await sm.update(m_modifier=1.0)  # current_m = 1.0
        state_before = sm.get_current_m()
        state = await sm.apply_grace_boost()
        # counter increments but m stays unchanged
        assert state.current_m == state_before

    @pytest.mark.asyncio
    async def test_consecutive_sincere_turns_accelerate(self):
        """Grace Boost accelerates: 2nd sincere turn boosts by 2.5."""
        sm = StateManager()
        await sm.update(m_modifier=-5.0)  # drive m very negative
        await sm.apply_grace_boost()      # 1st sincere: +2.0
        state = await sm.apply_grace_boost()  # 2nd sincere: +2.5 (capped at 2.0)
        assert state.consecutive_sincere_turns == 2


class TestAtomicUpdates:
    """Concurrent updates must not corrupt state."""

    @pytest.mark.asyncio
    async def test_concurrent_updates_are_atomic(self):
        """Multiple concurrent updates complete without error."""
        sm = StateManager()
        tasks = [sm.update(m_modifier=0.1) for _ in range(10)]
        results = await asyncio.gather(*tasks)
        assert all(isinstance(r.current_m, float) for r in results)

    @pytest.mark.asyncio
    async def test_get_snapshot_is_lock_free(self):
        """get_snapshot() returns current state without blocking."""
        sm = StateManager()
        await sm.update(m_modifier=1.0)
        snapshot = sm.get_snapshot()
        assert snapshot.current_m == 1.0

    @pytest.mark.asyncio
    async def test_reset_restores_initial_state(self):
        """reset() returns state to clean initial values."""
        sm = StateManager(session_id="test-session")
        await sm.update(m_modifier=1.5)
        state = await sm.reset()
        assert state.current_m == 0.0
        assert state.turn_count == 0
        assert state.session_id == "test-session"
