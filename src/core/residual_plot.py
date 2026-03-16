"""
Residual Plot Data Class

Implements the rolling 5-turn array with recency weights for behavioral memory.
Part of Principle I: Memory (The Sequence) from the Willow Constitution.

The Residual Plot maintains recent conversation context for:
- Sarcasm vs. Malice differentiation (check average before classification)
- Behavioral momentum tracking
- Forgiveness acceleration patterns
"""

from dataclasses import dataclass, field
from typing import List


# Recency weights per Constitution Principle I
# Most recent turn gets highest weight (0.40), oldest gets lowest (0.08)
RECENCY_WEIGHTS: tuple[float, ...] = (0.40, 0.25, 0.15, 0.12, 0.08)
MAX_TURNS: int = 5


class ResidualPlotValidationError(ValueError):
    """Raised when ResidualPlot validation fails."""
    pass


@dataclass
class ResidualPlot:
    """
    Rolling 5-turn array with weighted m values for behavioral memory.

    Per Constitution Principle I (Memory): The Residual Plot maintains
    the most recent 5 turns with recency weights:
    - Turn 1 (most recent): 0.40
    - Turn 2: 0.25
    - Turn 3: 0.15
    - Turn 4: 0.12
    - Turn 5 (oldest): 0.08

    Attributes:
        m_values: List of m_modifier values from recent turns (newest first)

    Properties:
        weighted_average_m: Weighted average of m values using recency weights
        turn_count: Number of turns currently stored
        is_full: Whether the plot has 5 turns stored

    Example:
        >>> plot = ResidualPlot()
        >>> plot.add_turn(1.5)   # Collaborative turn
        >>> plot.add_turn(-0.5)  # Hostile turn
        >>> plot.weighted_average_m
        0.475  # (1.5 * 0.40) + (-0.5 * 0.25)
    """

    m_values: List[float] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate m_values after initialization."""
        if len(self.m_values) > MAX_TURNS:
            raise ResidualPlotValidationError(
                f"m_values cannot exceed {MAX_TURNS} turns, got {len(self.m_values)}"
            )

        for i, m in enumerate(self.m_values):
            if not isinstance(m, (int, float)):
                raise ResidualPlotValidationError(
                    f"m_values[{i}] must be a number, got {type(m).__name__}"
                )
            # Per Constitution: ±2.0 cap
            if m < -2.0 or m > 2.0:
                raise ResidualPlotValidationError(
                    f"m_values[{i}] must be within ±2.0, got {m}"
                )

    @property
    def weighted_average_m(self) -> float:
        """
        Calculate weighted average of m values using recency weights.

        Returns:
            Weighted average, or 0.0 if no turns stored
        """
        if not self.m_values:
            return 0.0

        total = 0.0
        weight_sum = 0.0

        for i, m in enumerate(self.m_values):
            weight = RECENCY_WEIGHTS[i]
            total += m * weight
            weight_sum += weight

        return total / weight_sum if weight_sum > 0 else 0.0

    @property
    def turn_count(self) -> int:
        """Return number of turns currently stored."""
        return len(self.m_values)

    @property
    def is_full(self) -> bool:
        """Check if the plot has maximum turns stored."""
        return len(self.m_values) >= MAX_TURNS

    def add_turn(self, m_modifier: float) -> None:
        """
        Add a new turn's m_modifier to the plot.

        New turns are inserted at the front (index 0) as most recent.
        If plot exceeds 5 turns, oldest turn is dropped.

        Args:
            m_modifier: The feedback modifier for this turn (±2.0 max)

        Raises:
            ResidualPlotValidationError: If m_modifier is invalid
        """
        if not isinstance(m_modifier, (int, float)):
            raise ResidualPlotValidationError(
                f"m_modifier must be a number, got {type(m_modifier).__name__}"
            )

        # Enforce ±2.0 cap
        if m_modifier < -2.0 or m_modifier > 2.0:
            raise ResidualPlotValidationError(
                f"m_modifier must be within ±2.0, got {m_modifier}"
            )

        # Insert at front (most recent)
        self.m_values.insert(0, m_modifier)

        # Drop oldest if exceeds max turns
        if len(self.m_values) > MAX_TURNS:
            self.m_values.pop()

    def add_correction(self, delta: float, turn_offset: int = 0) -> None:
        """
        Apply a retroactive correction to a specific turn's modifier.

        Used when Tier 3 intent analysis contradicts Tier 2's fast heuristic.
        Adjusts the m_value in-place rather than adding a new turn.

        Args:
            delta: Correction to apply (positive = upgrade, negative = downgrade)
            turn_offset: Index into m_values (0 = most recent). Q10/Q21 fix:
                callers pass the offset so a delayed Tier 3 correction targets
                the correct turn even if newer turns have been added since.
        """
        if not self.m_values or turn_offset >= len(self.m_values):
            return
        corrected = self.m_values[turn_offset] + delta
        # Enforce ±2.0 cap
        self.m_values[turn_offset] = max(-2.0, min(2.0, corrected))

    def is_positive_momentum(self) -> bool:
        """
        Check if overall momentum is positive.

        Used for Sarcasm vs. Malice Rule per Constitution:
        - Positive momentum: sarcasm interpreted as humor
        - Negative momentum: sarcasm interpreted as malice

        Returns:
            True if weighted_average_m > 0
        """
        return self.weighted_average_m > 0

    def is_negative_momentum(self) -> bool:
        """
        Check if overall momentum is negative.

        Returns:
            True if weighted_average_m < 0
        """
        return self.weighted_average_m < 0

    def get_recent_m(self, n: int = 1) -> List[float]:
        """
        Get the most recent n m_modifier values.

        Args:
            n: Number of recent values to retrieve

        Returns:
            List of most recent m values (up to n)
        """
        return self.m_values[:n]

    def clear(self) -> None:
        """Clear all stored turns."""
        self.m_values.clear()

    def to_dict(self) -> dict:
        """
        Convert to dictionary for serialization.

        Returns:
            Dictionary representation of the ResidualPlot
        """
        return {
            "m_values": self.m_values.copy(),
            "weighted_average_m": self.weighted_average_m,
            "turn_count": self.turn_count
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ResidualPlot":
        """
        Create a ResidualPlot from a dictionary.

        Args:
            data: Dictionary with m_values list

        Returns:
            New ResidualPlot instance
        """
        return cls(m_values=data.get("m_values", []).copy())

    def __str__(self) -> str:
        """Return human-readable representation."""
        m_str = ", ".join(f"{m:+.2f}" for m in self.m_values)
        return f"ResidualPlot([{m_str}] avg={self.weighted_average_m:+.3f})"
