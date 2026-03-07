"""
Conversational Turn Data Class

Represents a single turn in a conversation with Willow, capturing user input,
agent response, and the associated metadata including the Thought Signature
and timing information.

Part of Principle I: Memory (The Sequence) from the Willow Constitution.
The ConversationalTurn is the atomic unit that populates the Residual Plot.
"""

from dataclasses import dataclass
from datetime import datetime

from ..signatures.thought_signature import ThoughtSignature


class ConversationalTurnValidationError(ValueError):
    """Raised when ConversationalTurn validation fails."""
    pass


def _validate_conversational_turn(
    turn_id: int,
    user_input: str,
    agent_response: str,
    thought_signature: ThoughtSignature,
    m_modifier: float,
    timestamp: datetime,
    tier_latencies: dict[str, float]
) -> None:
    """
    Validate ConversationalTurn fields.

    Args:
        turn_id: Sequential turn identifier (0-indexed)
        user_input: The user's input text
        agent_response: The agent's response text
        thought_signature: The ThoughtSignature analysis of this turn
        m_modifier: The feedback modifier applied to state transition
        timestamp: When this turn occurred
        tier_latencies: Processing time per tier (tier name -> ms)

    Raises:
        ConversationalTurnValidationError: If validation fails
    """
    if not isinstance(turn_id, int):
        raise ConversationalTurnValidationError(
            f"turn_id must be an integer, got {type(turn_id).__name__}"
        )

    if turn_id < 0:
        raise ConversationalTurnValidationError(
            f"turn_id must be non-negative, got {turn_id}"
        )

    if not isinstance(user_input, str):
        raise ConversationalTurnValidationError(
            f"user_input must be a string, got {type(user_input).__name__}"
        )

    if not isinstance(agent_response, str):
        raise ConversationalTurnValidationError(
            f"agent_response must be a string, got {type(agent_response).__name__}"
        )

    if not isinstance(thought_signature, ThoughtSignature):
        raise ConversationalTurnValidationError(
            f"thought_signature must be a ThoughtSignature, got {type(thought_signature).__name__}"
        )

    if not isinstance(m_modifier, (int, float)):
        raise ConversationalTurnValidationError(
            f"m_modifier must be a number, got {type(m_modifier).__name__}"
        )

    # Per Constitution Principle V: +/-2.0 state change cap
    if m_modifier < -2.0 or m_modifier > 2.0:
        raise ConversationalTurnValidationError(
            f"m_modifier must be within +/-2.0 range, got {m_modifier}"
        )

    if not isinstance(timestamp, datetime):
        raise ConversationalTurnValidationError(
            f"timestamp must be a datetime, got {type(timestamp).__name__}"
        )

    if not isinstance(tier_latencies, dict):
        raise ConversationalTurnValidationError(
            f"tier_latencies must be a dict, got {type(tier_latencies).__name__}"
        )

    # Validate tier_latencies values are numbers
    for tier_name, latency in tier_latencies.items():
        if not isinstance(tier_name, str):
            raise ConversationalTurnValidationError(
                f"tier_latencies keys must be strings, got {type(tier_name).__name__}"
            )
        if not isinstance(latency, (int, float)):
            raise ConversationalTurnValidationError(
                f"tier_latencies values must be numbers, got {type(latency).__name__} for tier '{tier_name}'"
            )
        if latency < 0:
            raise ConversationalTurnValidationError(
                f"tier_latencies values must be non-negative, got {latency} for tier '{tier_name}'"
            )


@dataclass(frozen=True)
class ConversationalTurn:
    """
    A single turn in a conversation with Willow.

    Per Constitution Principle I: Memory maintains a rolling array of the last
    5 turns (the Residual Plot), weighted by recency. Each ConversationalTurn
    captures the full context needed for state calculations and audit trails.

    Attributes:
        turn_id: Sequential turn identifier (0-indexed)
            Used for ordering and Residual Plot position

        user_input: The user's input text
            Raw text of what the user said/typed

        agent_response: The agent's response text
            What Willow responded with

        thought_signature: The ThoughtSignature analysis of this turn
            Contains intent, tone, detected tactic, and classification rationale

        m_modifier: The feedback modifier applied to state transition
            Per Constitution: a(n+1) = a(n) + d + m
            Must be within +/-2.0 range

        timestamp: When this turn occurred
            Used for temporal decay calculations

        tier_latencies: Processing time per tier in milliseconds
            Maps tier name to processing duration (e.g., {"tier1": 45.2, "tier3": 320.0})
            Used for latency monitoring per Constitution Technical Architecture

    Residual Plot Weighting (per Constitution):
        - Turn 0 (most recent): 0.40
        - Turn 1: 0.25
        - Turn 2: 0.15
        - Turn 3: 0.12
        - Turn 4 (oldest): 0.08

    Example:
        >>> from datetime import datetime
        >>> from src.signatures.thought_signature import ThoughtSignature
        >>>
        >>> sig = ThoughtSignature(
        ...     intent="collaborative",
        ...     tone="warm",
        ...     detected_tactic=None,
        ...     m_modifier=0.5,
        ...     tier_trigger=2,
        ...     rationale="Positive engagement"
        ... )
        >>> turn = ConversationalTurn(
        ...     turn_id=0,
        ...     user_input="Hello, how are you?",
        ...     agent_response="I'm well, thanks for asking.",
        ...     thought_signature=sig,
        ...     m_modifier=0.5,
        ...     timestamp=datetime.now(),
        ...     tier_latencies={"tier1": 12.5, "tier2": 3.2}
        ... )
    """

    turn_id: int
    user_input: str
    agent_response: str
    thought_signature: ThoughtSignature
    m_modifier: float
    timestamp: datetime
    tier_latencies: dict[str, float]

    def __post_init__(self) -> None:
        """Validate all fields after initialization."""
        _validate_conversational_turn(
            self.turn_id,
            self.user_input,
            self.agent_response,
            self.thought_signature,
            self.m_modifier,
            self.timestamp,
            self.tier_latencies
        )

    def __str__(self) -> str:
        """Return a human-readable representation."""
        input_preview = self.user_input[:50] + "..." if len(self.user_input) > 50 else self.user_input
        return (
            f"Turn {self.turn_id} [{self.thought_signature.intent}]: "
            f"\"{input_preview}\" -> m={self.m_modifier:+.2f}"
        )

    def is_cold_start_turn(self) -> bool:
        """
        Check if this turn is within the Cold Start period.

        Per Constitution Principle I: Decay is disabled (d=0) for the first
        3 turns (Social Handshake) to prevent premature state collapse.

        Returns:
            True if turn_id < 3 (within Social Handshake period)
        """
        return self.turn_id < 3

    def get_residual_weight(self) -> float:
        """
        Get the Residual Plot weight for this turn based on position.

        Per Constitution: Rolling array weights are 0.40, 0.25, 0.15, 0.12, 0.08

        Returns:
            The weight for this turn's position (0.0 if outside Residual Plot)
        """
        weights = [0.40, 0.25, 0.15, 0.12, 0.08]
        if 0 <= self.turn_id < len(weights):
            return weights[self.turn_id]
        return 0.0

    def total_latency_ms(self) -> float:
        """
        Calculate total processing latency across all tiers.

        Returns:
            Sum of all tier latencies in milliseconds
        """
        return sum(self.tier_latencies.values())

    def to_dict(self) -> dict:
        """
        Convert to dictionary for serialization.

        Returns:
            Dictionary representation of the ConversationalTurn
        """
        return {
            "turn_id": self.turn_id,
            "user_input": self.user_input,
            "agent_response": self.agent_response,
            "thought_signature": self.thought_signature.to_dict(),
            "m_modifier": self.m_modifier,
            "timestamp": self.timestamp.isoformat(),
            "tier_latencies": self.tier_latencies
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ConversationalTurn":
        """
        Create a ConversationalTurn from a dictionary.

        Args:
            data: Dictionary with all ConversationalTurn fields

        Returns:
            New ConversationalTurn instance
        """
        return cls(
            turn_id=data["turn_id"],
            user_input=data["user_input"],
            agent_response=data["agent_response"],
            thought_signature=ThoughtSignature.from_dict(data["thought_signature"]),
            m_modifier=data["m_modifier"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            tier_latencies=data["tier_latencies"]
        )
