"""
Integration Test: T056 — End-to-End Voice Flow

Verifies a full multi-turn conversation with:
- 5+ turns processing correctly
- Tier 1/2 executing each turn
- State progressing through Cold Start → normal decay
- Turn history accumulating
- Interruption handler state management
"""

import pytest

from src.main import WillowAgent, TurnResult
from src.core.state_manager import COLD_START_TURNS


@pytest.fixture
def agent():
    return WillowAgent()


class TestMultiTurnConversation:
    """End-to-end multi-turn voice conversation flow."""

    @pytest.mark.asyncio
    async def test_five_turn_conversation(self, agent):
        """Process 5 turns and verify state progression."""
        inputs = [
            "Hello, how are you?",
            "Tell me about your architecture.",
            "That's interesting, go on.",
            "Can you explain the tier system?",
            "Thanks, that was helpful!",
        ]

        results = []
        for inp in inputs:
            result = await agent.handle_user_input(inp)
            results.append(result)
            assert isinstance(result, TurnResult)
            assert result.response_text  # Non-empty response

        # Verify turn count
        state = agent.get_session_state()
        assert state.turn_count == 5

        # Verify turn history
        history = agent.get_turn_history()
        assert len(history) == 5

    @pytest.mark.asyncio
    async def test_cold_start_to_normal_transition(self, agent):
        """Cold Start ends after 3 turns, decay activates at turn 4."""
        for i in range(COLD_START_TURNS):
            await agent.handle_user_input(f"Turn {i + 1}")

        state = agent.get_session_state()
        assert state.cold_start_active is True

        # Turn 4 — Cold Start ends
        await agent.handle_user_input("Turn 4")
        state = agent.get_session_state()
        assert state.cold_start_active is False

    @pytest.mark.asyncio
    async def test_tier_latencies_recorded(self, agent):
        """Each turn records Tier 1 and Tier 2 latencies."""
        result = await agent.handle_user_input("Hello")
        assert "tier1" in result.tier_latencies
        assert "tier2" in result.tier_latencies
        assert result.tier_latencies["tier1"] >= 0
        assert result.tier_latencies["tier2"] >= 0


class TestInterruptionHandlerIntegration:
    """Interruption handler integrates with voice flow."""

    def test_interruption_handler_initial_state(self, agent):
        """Interruption handler starts in clean state."""
        handler = agent._interruption_handler
        assert handler.is_agent_speaking is False
        assert handler.is_user_speaking is False
        assert handler.frames_processed == 0

    def test_interruption_handler_reset(self, agent):
        """Interruption handler can be reset."""
        handler = agent._interruption_handler
        handler.start_agent_speaking()
        assert handler.is_agent_speaking is True
        handler.reset()
        assert handler.is_agent_speaking is False


class TestSessionSnapshot:
    """Session state snapshot is accurate."""

    @pytest.mark.asyncio
    async def test_snapshot_reflects_state(self, agent):
        """Session snapshot contains accurate state values."""
        await agent.handle_user_input("Hello")
        snapshot = agent.get_session_state()

        assert snapshot.session_id == agent.session_id
        assert snapshot.turn_count == 1
        assert snapshot.cold_start_active is True
        assert isinstance(snapshot.current_m, float)
        assert isinstance(snapshot.residual_plot_weighted_avg, float)
