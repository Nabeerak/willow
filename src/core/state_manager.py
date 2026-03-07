"""
Session State Management

Implements stateful behavioral tracking with async-safe operations.
Part of the core state management system from the Willow Constitution.

Key features:
- Atomic state updates with asyncio.Lock
- Lock-free snapshot reads for performance
- Cold Start logic (d=0 for turns 1-3)
- ±2.0 state change cap enforcement
- Sovereign Spike tracking for Troll Defense
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, List, Optional

from .residual_plot import ResidualPlot

logger = logging.getLogger(__name__)


# Constants from Constitution
COLD_START_TURNS: int = 3  # d=0 for first 3 turns (Social Handshake)
MAX_STATE_CHANGE: float = 2.0  # ±2.0 cap per turn
SOVEREIGN_SPIKE_THRESHOLD: int = 3  # Consecutive spikes to trigger Troll Defense
BASE_DECAY_RATE: float = -0.1  # Default decay rate when not in Cold Start


class SessionStateValidationError(ValueError):
    """Raised when SessionState validation fails."""
    pass


@dataclass
class DeferredContradiction:
    """
    A contradiction detected during Cold Start (turns 1-3) and queued for
    evaluation at turn 4 (T076, FR-020, FR-021).

    Attributes:
        truth_key: Key of the matched SovereignTruth.
        user_input: The raw user input that triggered the contradiction.
        turn_number: Turn at which the contradiction was detected.
        topic_keywords: Keywords from the matched truth for relevance check.
    """

    truth_key: str
    user_input: str
    turn_number: int
    topic_keywords: tuple[str, ...]


@dataclass
class SessionState:
    """
    Mutable session state for behavioral tracking.

    Implements the state formula: aₙ₊₁ = aₙ + d + m
    Where:
        - aₙ = current_m (current behavioral state)
        - d = base_decay (decay rate, 0 during Cold Start)
        - m = feedback modifier from user interaction

    Attributes:
        current_m: Current behavioral state value
        base_decay: Decay rate applied each turn (0 during Cold Start)
        turn_count: Number of turns in this session
        residual_plot: Rolling 5-turn history
        sovereign_spike_count: Consecutive Sovereign Spikes (for Troll Defense)
        cold_start_active: Whether Cold Start period is active
        troll_defense_active: Whether Troll Defense has been triggered
        audio_started: Set to True once audio streaming begins for the current
            turn. Blocks late Tier 4 fires for that turn (FR-022). Reset to
            False at the start of each new turn.
        preflight_active: Set to True during the 3-second pre-flight warmup
            window from spec 002 T028. Tier 4 is skipped entirely while True.
        last_updated: Timestamp of last state update
        session_id: Unique identifier for this session

    Example:
        >>> state = SessionState()
        >>> state.turn_count
        0
        >>> state.cold_start_active
        True
    """

    current_m: float = 0.0
    base_decay: float = 0.0  # Starts at 0 for Cold Start
    turn_count: int = 0
    residual_plot: ResidualPlot = field(default_factory=ResidualPlot)
    sovereign_spike_count: int = 0
    cold_start_active: bool = True
    troll_defense_active: bool = False
    audio_started: bool = False   # FR-022: blocks late Tier 4 fires per turn
    preflight_active: bool = False  # spec 002 T028 / T079: skip Tier 4 during warmup
    response_on_return: Optional[str] = None  # T035: vacuum mode — serve on next utility signal
    consecutive_sincere_turns: int = 0  # T043 / US4: cumulative forgiveness counter
    last_spike_tactic: Optional[str] = None  # Tactic type that triggered troll defense
    deferred_contradictions: List["DeferredContradiction"] = field(default_factory=list)  # T076: Cold Start queue
    last_agent_response: Optional[str] = None  # Most recent Willow response for mirroring detection
    last_updated: datetime = field(default_factory=datetime.now)
    session_id: Optional[str] = None

    # Debug overlay fields — populated by tier processors for live UI
    last_thought_signature: Optional[Any] = None  # ThoughtSignature from Tier 3
    last_sovereign_key: Optional[str] = None
    last_gate_results: dict = field(default_factory=dict)
    last_transcription_confidence: float = 0.0
    last_response_source: str = "gemini"  # "gemini" | "response_template" | "vacuum_mode"
    vacuum_mode_active: bool = False

    def __post_init__(self) -> None:
        """Validate fields after initialization."""
        if not isinstance(self.turn_count, int) or self.turn_count < 0:
            raise SessionStateValidationError(
                f"turn_count must be a non-negative integer, got {self.turn_count}"
            )

        if not isinstance(self.sovereign_spike_count, int) or self.sovereign_spike_count < 0:
            raise SessionStateValidationError(
                f"sovereign_spike_count must be a non-negative integer"
            )


class StateManager:
    """
    Thread-safe state manager with async Lock for atomic updates.

    Provides:
    - Atomic state mutations via asyncio.Lock
    - Lock-free snapshot reads for performance
    - State formula application with Cold Start logic
    - ±2.0 cap enforcement
    - Troll Defense tracking

    Usage:
        manager = StateManager()

        # Atomic update
        await manager.update(m_modifier=1.5)

        # Lock-free read
        snapshot = manager.get_snapshot()
        print(f"Current m: {snapshot.current_m}")
    """

    def __init__(self, session_id: Optional[str] = None):
        """
        Initialize the state manager.

        Args:
            session_id: Optional unique session identifier
        """
        self._lock = asyncio.Lock()
        self._state = SessionState(session_id=session_id)

    async def update(
        self,
        m_modifier: float,
        is_sovereign_spike: bool = False,
        spike_tactic: Optional[str] = None,
    ) -> SessionState:
        """
        Apply state update atomically.

        Implements: aₙ₊₁ = aₙ + d + m

        Args:
            m_modifier: Feedback modifier from user interaction
            is_sovereign_spike: Whether this is a Sovereign Spike (devaluing intent)

        Returns:
            Updated SessionState snapshot

        Raises:
            SessionStateValidationError: If update fails
        """
        async with self._lock:
            # Enforce ±2.0 cap on m_modifier
            capped_m = max(-MAX_STATE_CHANGE, min(MAX_STATE_CHANGE, m_modifier))

            # Update turn count
            self._state.turn_count += 1

            # Cold Start logic: d=0 for first 3 turns
            if self._state.turn_count <= COLD_START_TURNS:
                self._state.cold_start_active = True
                self._state.base_decay = 0.0
            else:
                self._state.cold_start_active = False
                self._state.base_decay = BASE_DECAY_RATE

            # Apply state formula: aₙ₊₁ = aₙ + d + m
            self._state.current_m = (
                self._state.current_m +
                self._state.base_decay +
                capped_m
            )

            # Track Sovereign Spikes for Troll Defense
            if is_sovereign_spike:
                self._state.sovereign_spike_count += 1
                if spike_tactic:
                    self._state.last_spike_tactic = spike_tactic
                if self._state.sovereign_spike_count >= SOVEREIGN_SPIKE_THRESHOLD:
                    self._state.troll_defense_active = True
                # Non-sincere turn — reset cumulative forgiveness counter
                self._state.consecutive_sincere_turns = 0
            else:
                # Reset spike count on non-spike turn
                self._state.sovereign_spike_count = 0

            # Update Residual Plot
            self._state.residual_plot.add_turn(capped_m)

            # Update timestamp
            self._state.last_updated = datetime.now()

            # T032: Log behavioral state change
            logger.debug(
                "State update: turn=%d m_modifier=%.2f capped_m=%.2f "
                "current_m=%.2f sovereign_spike=%s troll_defense=%s",
                self._state.turn_count,
                m_modifier,
                capped_m,
                self._state.current_m,
                is_sovereign_spike,
                self._state.troll_defense_active,
            )

            return self._state

    async def apply_grace_boost(self) -> SessionState:
        """
        Apply Grace Boost for sincere pivot (T042 / T043 / US4).

        Per Constitution Principle V: When user makes sincere pivot after
        negative state, apply Grace Boost. Boost starts at +2.0 and
        accelerates by +0.5 per consecutive sincere turn (T043).

        Boost only applies when current_m < 0. Consecutive sincere turns
        are tracked to accelerate recovery. Non-sincere turns reset the counter.

        Returns:
            Updated SessionState snapshot
        """
        async with self._lock:
            if self._state.current_m < 0:
                # T043: Accelerating boost — +2.0 base, +0.5 per consecutive sincere turn
                # Capped at MAX_STATE_CHANGE to prevent single-turn over-correction
                self._state.consecutive_sincere_turns += 1
                grace_m = min(
                    MAX_STATE_CHANGE,
                    2.0 + (self._state.consecutive_sincere_turns - 1) * 0.5
                )
                self._state.current_m += grace_m
                self._state.residual_plot.add_turn(grace_m)
                self._state.last_updated = datetime.now()
                logger.debug(
                    "Grace Boost applied: consecutive_sincere=%d grace_m=%.1f new_m=%.2f",
                    self._state.consecutive_sincere_turns,
                    grace_m,
                    self._state.current_m,
                )
            else:
                # Still in positive territory — increment counter but don't boost
                self._state.consecutive_sincere_turns += 1

            return self._state

    async def reset_troll_defense(self) -> SessionState:
        """
        Reset Troll Defense state (after tone change).

        Returns:
            Updated SessionState snapshot
        """
        async with self._lock:
            self._state.troll_defense_active = False
            self._state.sovereign_spike_count = 0
            self._state.last_spike_tactic = None
            self._state.last_updated = datetime.now()
            return self._state

    def get_snapshot(self) -> SessionState:
        """
        Get current state snapshot (lock-free read).

        Returns:
            Current SessionState (not a copy - treat as read-only)
        """
        return self._state

    def get_current_m(self) -> float:
        """Get current behavioral state value."""
        return self._state.current_m

    def get_turn_count(self) -> int:
        """Get current turn count."""
        return self._state.turn_count

    def is_cold_start(self) -> bool:
        """Check if Cold Start period is active."""
        return self._state.cold_start_active

    def is_troll_defense_active(self) -> bool:
        """Check if Troll Defense has been triggered."""
        return self._state.troll_defense_active

    def get_weighted_average_m(self) -> float:
        """Get weighted average from Residual Plot."""
        return self._state.residual_plot.weighted_average_m

    async def set_audio_started(self) -> None:
        """
        Mark that audio streaming has begun for the current turn (FR-022).

        Once set, SovereignTruthCache must not fire Tier 4 for this turn.
        Cleared automatically at the start of the next turn via reset_turn_flags().
        Called from src/main.py when the audio pipeline begins streaming.
        """
        async with self._lock:
            self._state.audio_started = True
            self._state.last_updated = datetime.now()

    async def reset_turn_flags(self) -> None:
        """Reset per-turn flags at the start of each new user input."""
        async with self._lock:
            self._state.audio_started = False
            self._state.last_updated = datetime.now()

    async def set_response_on_return(self, response: Optional[str]) -> None:
        """
        Store vacuum mode return response for delivery on next utility signal.

        Called from Tier4Sovereign when vacuum_mode=True. The stored value is
        served and cleared when the user sends their next substantive input.

        Args:
            response: Response text to deliver on return, or None to clear.
        """
        async with self._lock:
            self._state.response_on_return = response
            self._state.last_updated = datetime.now()

    async def consume_response_on_return(self) -> Optional[str]:
        """
        Retrieve and clear the vacuum mode return response.

        Returns:
            The stored response text, or None if none is pending.
        """
        async with self._lock:
            response = self._state.response_on_return
            if response is not None:
                self._state.response_on_return = None
                self._state.last_updated = datetime.now()
            return response

    async def queue_deferred_contradiction(
        self,
        truth_key: str,
        user_input: str,
        topic_keywords: tuple[str, ...],
    ) -> None:
        """
        Queue a contradiction detected during Cold Start for evaluation at turn 4
        (T076, FR-020).

        Args:
            truth_key: Key of the matched SovereignTruth.
            user_input: Raw user input that triggered the contradiction.
            topic_keywords: Keywords from the matched truth for relevance check.
        """
        async with self._lock:
            dc = DeferredContradiction(
                truth_key=truth_key,
                user_input=user_input,
                turn_number=self._state.turn_count,
                topic_keywords=topic_keywords,
            )
            self._state.deferred_contradictions.append(dc)
            self._state.last_updated = datetime.now()
            logger.debug(
                "Deferred contradiction queued: truth=%s turn=%d",
                truth_key,
                self._state.turn_count,
            )

    async def consume_deferred_contradictions(self) -> List[DeferredContradiction]:
        """
        Retrieve and clear all deferred contradictions (T076, FR-021).

        Called at turn 4 to evaluate relevance. Returns the queue and
        clears it atomically.

        Returns:
            List of DeferredContradiction entries (may be empty).
        """
        async with self._lock:
            items = list(self._state.deferred_contradictions)
            self._state.deferred_contradictions.clear()
            self._state.last_updated = datetime.now()
            return items

    async def set_preflight(self, active: bool) -> None:
        """
        Set preflight_active flag from spec 002 T028 audio capture layer.

        When True, Tier 4 Sovereign is skipped entirely (T079, FR-013).
        Called from src/main.py when the audio capture layer signals
        pre-flight warmup start/end.

        Args:
            active: True to enable preflight suppression, False to clear it.
        """
        async with self._lock:
            self._state.preflight_active = active
            self._state.last_updated = datetime.now()

    async def reset(self) -> SessionState:
        """
        Reset state to initial values.

        Returns:
            Fresh SessionState
        """
        async with self._lock:
            session_id = self._state.session_id
            self._state = SessionState(session_id=session_id)
            return self._state

    def to_dict(self) -> dict:
        """
        Convert current state to dictionary for logging/serialization.

        Returns:
            Dictionary representation of current state
        """
        state = self._state
        return {
            "current_m": state.current_m,
            "base_decay": state.base_decay,
            "turn_count": state.turn_count,
            "residual_plot": state.residual_plot.to_dict(),
            "sovereign_spike_count": state.sovereign_spike_count,
            "cold_start_active": state.cold_start_active,
            "troll_defense_active": state.troll_defense_active,
            "last_updated": state.last_updated.isoformat(),
            "session_id": state.session_id
        }
