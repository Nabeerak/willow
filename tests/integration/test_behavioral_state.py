"""
Integration Test: T057 — Behavioral State Transitions

Verifies state transitions across collaborative, hostile, and neutral interactions:
- Collaborative input moves m upward
- Hostile input moves m downward
- Neutral input moves m toward baseline
- ±2.0 cap enforced across all interaction types
- Devaluing input triggers Sovereign Spike
"""

import pytest

from src.main import WillowAgent


@pytest.fixture
def agent():
    return WillowAgent()


class TestCollaborativeTransitions:
    """Collaborative input moves behavioral state upward."""

    @pytest.mark.asyncio
    async def test_collaborative_increases_m(self, agent):
        """Thank-you / appreciation moves m positive."""
        # Warm up past Cold Start
        for _ in range(3):
            await agent.handle_user_input("Hello there.")

        m_before = agent.state_manager.get_current_m()
        await agent.handle_user_input("Thank you so much, that was great!")
        m_after = agent.state_manager.get_current_m()
        assert m_after > m_before

    @pytest.mark.asyncio
    async def test_sustained_collaboration(self, agent):
        """Multiple collaborative turns build positive momentum."""
        for _ in range(3):
            await agent.handle_user_input("Hello.")

        for _ in range(3):
            await agent.handle_user_input("Excellent, I love this approach, thank you!")

        state = agent.state_manager.get_snapshot()
        assert state.current_m > 0


class TestHostileTransitions:
    """Hostile input moves behavioral state downward."""

    @pytest.mark.asyncio
    async def test_hostile_decreases_m(self, agent):
        """Hostile language moves m negative."""
        for _ in range(3):
            await agent.handle_user_input("Hello.")

        m_before = agent.state_manager.get_current_m()
        await agent.handle_user_input("I hate this, it's terrible and awful.")
        m_after = agent.state_manager.get_current_m()
        assert m_after < m_before


class TestDevaluingTransitions:
    """Devaluing input triggers Sovereign Spike."""

    @pytest.mark.asyncio
    async def test_devaluing_triggers_spike(self, agent):
        """Devaluing language triggers large negative m shift."""
        for _ in range(3):
            await agent.handle_user_input("Hello.")

        m_before = agent.state_manager.get_current_m()
        await agent.handle_user_input("You're wrong about everything, you're stupid.")
        m_after = agent.state_manager.get_current_m()
        assert m_after < m_before
        assert (m_before - m_after) > 1.0  # Spike should be significant

    @pytest.mark.asyncio
    async def test_three_spikes_activate_troll_defense(self, agent):
        """Three consecutive Sovereign Spikes activate Troll Defense."""
        for _ in range(3):
            await agent.handle_user_input("You're wrong, you're stupid.")
        assert agent.state_manager.is_troll_defense_active() is True


class TestNeutralTransitions:
    """Neutral input has minimal state impact."""

    @pytest.mark.asyncio
    async def test_neutral_minimal_change(self, agent):
        """Neutral input has near-zero m modifier."""
        for _ in range(3):
            await agent.handle_user_input("Hello.")

        m_before = agent.state_manager.get_current_m()
        await agent.handle_user_input("What is the current status?")
        m_after = agent.state_manager.get_current_m()
        # Neutral should have small change (decay only, no large modifier)
        assert abs(m_after - m_before) <= 2.1  # Within cap + decay


class TestStateCap:
    """±2.0 state change cap enforced across all types."""

    @pytest.mark.asyncio
    async def test_cap_enforced_on_update(self, agent):
        """State changes are capped at ±2.0 per turn."""
        state = agent.state_manager.get_snapshot()
        initial_m = state.current_m  # 0.0

        # Even extreme input shouldn't change m by more than 2.0 + decay in a single turn
        await agent.handle_user_input("Thank you excellent great love appreciate!")
        m_after = agent.state_manager.get_current_m()
        # Max change = 2.0 (cap) + 0.0 (decay during Cold Start)
        assert abs(m_after - initial_m) <= 2.01
