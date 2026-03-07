"""Tier 2 Metabolism module for state transitions in the Willow Behavioral Framework.

This module implements the Tier 2 metabolism logic which handles:
- State formula: a_{n+1} = a_n + d + m
- Latency budget: <5ms
- Cold Start logic: d=0 for turns 1-3

The metabolism manages gradual state changes with decay rates and modifiers,
supporting both standard state transitions and sovereign spike calculations
for devaluing intent detection.
"""

import time
from dataclasses import dataclass, field
from typing import Final

# Constants for Tier 2 metabolism behavior
COLD_START_TURNS: Final[int] = 3
MAX_STATE_CHANGE: Final[float] = 2.0
BASE_DECAY_RATE: Final[float] = -0.1

# Latency budget in milliseconds
LATENCY_BUDGET_MS: Final[float] = 5.0

# T029: Intent → m_modifier mapping (FR values, capped at ±2.0 for ThoughtSignature).
# Devaluing triggers Sovereign Spike via calculate_sovereign_spike(); the -2.0 entry
# is what the ThoughtSignature field stores (clamped).
INTENT_MODIFIERS: Final[dict[str, float]] = {
    "collaborative": 1.5,
    "insightful": 1.5,
    "neutral": 0.0,
    "hostile": -0.5,
    "devaluing": -2.0,  # Sovereign Spike clamped value; actual spike = -(base_decay + 5.0)
    "sincere_pivot": 2.0,  # T042 / US4: Grace Boost — full +2.0 applied when current_m < 0
}


def map_intent_to_modifier(
    intent: str, base_decay: float = 0.0
) -> tuple[float, bool]:
    """
    Map a ThoughtSignature intent to (m_modifier, is_sovereign_spike) — T029 + T037.

    Returns the raw m_modifier for state update and a flag indicating whether
    the devaluing Sovereign Spike formula should be applied.

    For devaluing intent, m_modifier = -(base_decay + 5.0) per T037.
    For all other intents, m_modifier comes from INTENT_MODIFIERS.

    Args:
        intent: ThoughtSignature intent string.
        base_decay: Current session base decay rate (0.0 during Cold Start).

    Returns:
        Tuple of (m_modifier, is_sovereign_spike).
    """
    if intent == "devaluing":
        # T037: Sovereign Spike formula — -(base_decay + 5.0)
        spike_m = -(base_decay + 5.0)
        return (spike_m, True)
    if intent == "sincere_pivot":
        # T042 / US4: Grace Boost (+2.0) — caller must check current_m < 0
        # before applying. The +2.0 modifier is unconditional here; the guard
        # lives in StateManager.apply_grace_boost() / update().
        return (2.0, False)
    return (INTENT_MODIFIERS.get(intent, 0.0), False)


@dataclass
class MetabolismResult:
    """Result of a metabolism calculation with timing information.

    Attributes:
        value: The calculated result value.
        latency_ms: Time taken to compute the result in milliseconds.
        within_budget: Whether the calculation completed within the 5ms budget.
    """

    value: float
    latency_ms: float
    within_budget: bool


@dataclass
class Tier2Metabolism:
    """Handles Tier 2 state metabolism calculations.

    Implements the state transition formula: a_{n+1} = a_n + d + m
    where:
        - a_n is the current state (current_m)
        - d is the decay rate (base_decay, 0 during cold start)
        - m is the modifier (m_modifier, clamped to +/-2.0)

    The metabolism tracks latency to ensure all operations complete
    within the 5ms budget requirement.

    Attributes:
        last_latency_ms: The latency of the most recent calculation in milliseconds.

    Example:
        >>> metabolism = Tier2Metabolism()
        >>> result = metabolism.calculate_state_update(
        ...     current_m=1.0,
        ...     base_decay=-0.1,
        ...     m_modifier=0.5,
        ...     turn_count=5
        ... )
        >>> print(f"New state: {result.value}, Latency: {result.latency_ms}ms")
    """

    last_latency_ms: float = field(default=0.0, init=False)

    def apply_cold_start(self, turn_count: int) -> float:
        """Apply cold start logic to determine effective decay rate.

        During the cold start period (turns 1-3), decay is suppressed
        to allow the system to stabilize before applying state decay.

        Args:
            turn_count: The current turn number (1-indexed).

        Returns:
            0.0 if turn_count <= COLD_START_TURNS, otherwise BASE_DECAY_RATE.

        Example:
            >>> metabolism = Tier2Metabolism()
            >>> metabolism.apply_cold_start(1)  # Cold start period
            0.0
            >>> metabolism.apply_cold_start(4)  # After cold start
            -0.1
        """
        if turn_count <= COLD_START_TURNS:
            return 0.0
        return BASE_DECAY_RATE

    def clamp_modifier(self, m_modifier: float) -> float:
        """Clamp the modifier value to the allowed range.

        Enforces the +/-2.0 cap on state modifiers to prevent
        extreme state changes in a single turn.

        Args:
            m_modifier: The raw modifier value to clamp.

        Returns:
            The modifier clamped to the range [-MAX_STATE_CHANGE, MAX_STATE_CHANGE].

        Example:
            >>> metabolism = Tier2Metabolism()
            >>> metabolism.clamp_modifier(3.5)
            2.0
            >>> metabolism.clamp_modifier(-5.0)
            -2.0
            >>> metabolism.clamp_modifier(0.5)
            0.5
        """
        return max(-MAX_STATE_CHANGE, min(MAX_STATE_CHANGE, m_modifier))

    def calculate_sovereign_spike(self, base_decay: float) -> float:
        """Calculate the sovereign spike value for devaluing intent.

        When devaluing intent is detected, applies a strong negative
        modification to counteract manipulative behavior.

        Args:
            base_decay: The base decay rate to incorporate into the spike.

        Returns:
            The negative spike value: -(base_decay + 5.0).

        Example:
            >>> metabolism = Tier2Metabolism()
            >>> metabolism.calculate_sovereign_spike(-0.1)
            -4.9
            >>> metabolism.calculate_sovereign_spike(0.0)
            -5.0
        """
        return -(base_decay + 5.0)

    def calculate_state_update(
        self,
        current_m: float,
        base_decay: float,
        m_modifier: float,
        turn_count: int,
    ) -> MetabolismResult:
        """Calculate the next state using the metabolism formula.

        Applies the state transition formula: a_{n+1} = a_n + d + m
        where d is subject to cold start logic and m is clamped.

        This method tracks latency and ensures operation completes
        within the 5ms budget.

        Args:
            current_m: The current state value (a_n).
            base_decay: The base decay rate (used after cold start).
            m_modifier: The modifier to apply (will be clamped to +/-2.0).
            turn_count: The current turn number (1-indexed).

        Returns:
            MetabolismResult containing:
                - value: The new state value (a_{n+1})
                - latency_ms: Time taken for calculation
                - within_budget: Whether calculation was under 5ms

        Example:
            >>> metabolism = Tier2Metabolism()
            >>> # During cold start (turn 2), decay is 0
            >>> result = metabolism.calculate_state_update(1.0, -0.1, 0.5, 2)
            >>> result.value  # 1.0 + 0.0 + 0.5 = 1.5
            1.5
            >>> # After cold start (turn 5), decay applies
            >>> result = metabolism.calculate_state_update(1.0, -0.1, 0.5, 5)
            >>> result.value  # 1.0 + (-0.1) + 0.5 = 1.4
            1.4
        """
        start_time_ns = time.perf_counter_ns()

        # Apply cold start logic: d = 0 for turns 1-3
        effective_decay = 0.0 if turn_count <= COLD_START_TURNS else base_decay

        # Clamp modifier to +/-2.0
        clamped_modifier = self.clamp_modifier(m_modifier)

        # Apply state formula: a_{n+1} = a_n + d + m
        new_state = current_m + effective_decay + clamped_modifier

        end_time_ns = time.perf_counter_ns()
        latency_ms = (end_time_ns - start_time_ns) / 1_000_000

        self.last_latency_ms = latency_ms

        return MetabolismResult(
            value=new_state,
            latency_ms=latency_ms,
            within_budget=latency_ms < LATENCY_BUDGET_MS,
        )
