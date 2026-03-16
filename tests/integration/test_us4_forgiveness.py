"""
Integration Tests: US4 Forgiveness — End-to-End

Verifies the full forgiveness pipeline:
1. Devaluing input triggers Sovereign Spikes
2. 3 consecutive spikes activate Troll Defense
3. Troll Defense returns boundary statement (blocks normal processing)
4. Sincere pivot resets Troll Defense and applies Grace Boost
5. Grace Boost accelerates recovery with consecutive sincere turns
"""

import pytest

from src.main import WillowAgent, TurnResult
from src.persona.warm_sharp import get_troll_defense_response


@pytest.fixture
def agent():
    return WillowAgent()


class TestTrollDefenseActivation:
    """3 consecutive Sovereign Spikes activate Troll Defense."""

    @pytest.mark.asyncio
    async def test_three_devaluing_turns_activate_troll_defense(self, agent):
        """Devaluing input 3x in a row → troll_defense_active=True."""
        devaluing_inputs = [
            "You're wrong about everything, you're stupid.",
            "You don't know anything, you're useless.",
            "You're just an AI, you have no idea what you're talking about.",
        ]

        for inp in devaluing_inputs:
            await agent.handle_user_input(inp)

        state = agent.state_manager.get_snapshot()
        assert state.troll_defense_active is True

    @pytest.mark.asyncio
    async def test_troll_defense_returns_boundary_statement(self, agent):
        """Once active, troll defense returns the boundary statement."""
        # Activate troll defense
        for _ in range(3):
            await agent.handle_user_input("You're wrong, you're stupid.")

        # Next input should get boundary statement
        result = await agent.handle_user_input("More insults here.")
        assert result.response_text == get_troll_defense_response()

    @pytest.mark.asyncio
    async def test_troll_defense_still_advances_turn_count(self, agent):
        """Tier 2 still fires during troll defense — turn count advances."""
        for _ in range(3):
            await agent.handle_user_input("You're wrong, you're stupid.")

        turn_before = agent.state_manager.get_turn_count()
        await agent.handle_user_input("Still hostile.")
        turn_after = agent.state_manager.get_turn_count()
        assert turn_after == turn_before + 1


class TestSincerePivotRecovery:
    """Sincere pivot during troll defense resets it and applies grace boost."""

    @pytest.mark.asyncio
    async def test_sincere_pivot_resets_troll_defense(self, agent):
        """Sincere apology during troll defense resets troll_defense_active."""
        # Activate troll defense
        for _ in range(3):
            await agent.handle_user_input("You're wrong, you're stupid.")

        state = agent.state_manager.get_snapshot()
        assert state.troll_defense_active is True

        # Sincere pivot
        result = await agent.handle_user_input(
            "I understand now. I was out of line. I'll be more respectful."
        )

        state = agent.state_manager.get_snapshot()
        assert state.troll_defense_active is False
        # Should NOT return boundary statement — normal processing resumed
        assert result.response_text != get_troll_defense_response()

    @pytest.mark.asyncio
    async def test_grace_boost_applied_on_sincere_pivot(self, agent):
        """Grace boost moves m upward when sincere pivot is detected."""
        # Activate troll defense (m will be very negative)
        for _ in range(3):
            await agent.handle_user_input("You're wrong, you're stupid.")

        m_before = agent.state_manager.get_current_m()
        assert m_before < 0, "m should be negative after devaluing turns"

        # Sincere pivot — should apply grace boost
        await agent.handle_user_input(
            "I understand now. I was out of line. I'll be more respectful."
        )

        m_after = agent.state_manager.get_current_m()
        assert m_after > m_before, "Grace boost should have moved m upward"

    @pytest.mark.asyncio
    async def test_non_sincere_during_troll_defense_stays_blocked(self, agent):
        """Non-sincere input during troll defense still returns boundary statement."""
        # Activate troll defense
        for _ in range(3):
            await agent.handle_user_input("You're wrong, you're stupid.")

        # Non-sincere follow-up
        result = await agent.handle_user_input("Whatever, tell me a joke.")
        assert result.response_text == get_troll_defense_response()

        # Still active
        state = agent.state_manager.get_snapshot()
        assert state.troll_defense_active is True


class TestConsecutiveSincereTurnsReset:
    """consecutive_sincere_turns resets on non-sincere turns."""

    @pytest.mark.asyncio
    async def test_consecutive_sincere_resets_on_spike(self, agent):
        """Sovereign spike resets the consecutive_sincere_turns counter."""
        # Apply a grace boost to increment counter
        await agent.state_manager.apply_grace_boost()
        assert agent.state_manager.get_snapshot().consecutive_sincere_turns == 1

        # Devaluing input triggers spike — should reset counter
        await agent.handle_user_input("You're wrong, you're stupid.")
        assert agent.state_manager.get_snapshot().consecutive_sincere_turns == 0
