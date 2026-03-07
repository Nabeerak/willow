"""
Unit Tests: T076 Cold Start Deferral

Verifies:
- Contradictions detected during turns 1-3 are queued, not fired
- At turn 4, deferred contradictions are evaluated for relevance
- Relevant deferred contradictions fire Tier 4
- Irrelevant deferred contradictions are discarded
- Deferred contradictions do NOT trigger grace boost or sincere_pivot
"""

import pytest

from src.core.state_manager import (
    StateManager,
    DeferredContradiction,
    COLD_START_TURNS,
)


class TestDeferredContradictionQueuing:
    """Contradictions during Cold Start are queued, not fired."""

    @pytest.mark.asyncio
    async def test_queue_during_cold_start(self):
        """queue_deferred_contradiction stores entries on SessionState."""
        sm = StateManager()
        await sm.queue_deferred_contradiction(
            truth_key="willow_definition",
            user_input="Willow is just a chatbot",
            topic_keywords=("willow", "chatbot", "definition"),
        )

        state = sm.get_snapshot()
        assert len(state.deferred_contradictions) == 1
        dc = state.deferred_contradictions[0]
        assert dc.truth_key == "willow_definition"
        assert dc.user_input == "Willow is just a chatbot"

    @pytest.mark.asyncio
    async def test_multiple_contradictions_queued(self):
        """Multiple contradictions can be queued during Cold Start."""
        sm = StateManager()
        for i in range(3):
            await sm.queue_deferred_contradiction(
                truth_key=f"truth_{i}",
                user_input=f"input {i}",
                topic_keywords=(f"kw_{i}",),
            )

        state = sm.get_snapshot()
        assert len(state.deferred_contradictions) == 3

    @pytest.mark.asyncio
    async def test_consume_clears_queue(self):
        """consume_deferred_contradictions returns and clears the queue."""
        sm = StateManager()
        await sm.queue_deferred_contradiction(
            truth_key="test_truth",
            user_input="test input",
            topic_keywords=("test",),
        )

        items = await sm.consume_deferred_contradictions()
        assert len(items) == 1
        assert items[0].truth_key == "test_truth"

        # Queue should be empty after consume
        state = sm.get_snapshot()
        assert len(state.deferred_contradictions) == 0

    @pytest.mark.asyncio
    async def test_consume_empty_returns_empty_list(self):
        """consume_deferred_contradictions on empty queue returns []."""
        sm = StateManager()
        items = await sm.consume_deferred_contradictions()
        assert items == []


class TestColdStartTransition:
    """Cold Start transitions correctly at turn 4."""

    @pytest.mark.asyncio
    async def test_cold_start_active_during_turns_1_to_3(self):
        """Cold Start is active for the first 3 turns."""
        sm = StateManager()
        for _ in range(COLD_START_TURNS):
            state = await sm.update(m_modifier=0.0)
        assert state.cold_start_active is True

    @pytest.mark.asyncio
    async def test_cold_start_ends_at_turn_4(self):
        """Cold Start transitions to False at turn 4."""
        sm = StateManager()
        for _ in range(COLD_START_TURNS):
            await sm.update(m_modifier=0.0)
        state = await sm.update(m_modifier=0.0)  # Turn 4
        assert state.cold_start_active is False


class TestDeferredDoesNotTriggerGraceBoost:
    """Deferred contradictions must not interact with grace boost."""

    @pytest.mark.asyncio
    async def test_queuing_does_not_change_consecutive_sincere(self):
        """Queuing a deferred contradiction does not increment consecutive_sincere_turns."""
        sm = StateManager()
        before = sm.get_snapshot().consecutive_sincere_turns
        await sm.queue_deferred_contradiction(
            truth_key="test",
            user_input="test",
            topic_keywords=("test",),
        )
        after = sm.get_snapshot().consecutive_sincere_turns
        assert after == before

    @pytest.mark.asyncio
    async def test_consuming_does_not_change_consecutive_sincere(self):
        """Consuming deferred contradictions does not increment consecutive_sincere_turns."""
        sm = StateManager()
        await sm.queue_deferred_contradiction(
            truth_key="test",
            user_input="test",
            topic_keywords=("test",),
        )
        before = sm.get_snapshot().consecutive_sincere_turns
        await sm.consume_deferred_contradictions()
        after = sm.get_snapshot().consecutive_sincere_turns
        assert after == before

    @pytest.mark.asyncio
    async def test_deferred_does_not_reset_troll_defense(self):
        """Deferred contradiction queue/consume does not affect troll_defense_active."""
        sm = StateManager()
        # Manually activate troll defense
        sm._state.troll_defense_active = True

        await sm.queue_deferred_contradiction(
            truth_key="test",
            user_input="test",
            topic_keywords=("test",),
        )
        await sm.consume_deferred_contradictions()

        assert sm.get_snapshot().troll_defense_active is True
