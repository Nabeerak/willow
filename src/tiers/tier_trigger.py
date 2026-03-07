"""TierTrigger data class for recording tier escalation events.

This module provides the TierTrigger frozen dataclass that captures
information about when and why an escalation to Tier 3 or Tier 4 occurred.

T052 / US5: All TierTrigger instances are logged at INFO level via
log_tier_trigger() so latency and filler audio usage are observable in
Cloud Logging and local logs.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

logger = logging.getLogger(__name__)

# Valid trigger types that can cause tier escalation
VALID_TRIGGER_TYPES: frozenset[str] = frozenset({
    "manipulation_pattern",
    "truth_conflict",
    "emotional_spike",
})

# Valid tiers that can be fired (only 3 and 4)
VALID_TIERS: frozenset[int] = frozenset({3, 4})


@dataclass(frozen=True)
class TierTrigger:
    """Immutable record of a tier escalation event.

    Captures the cause, tier level, optional filler audio, processing time,
    and timestamp of an escalation to Tier 3 or Tier 4.

    Attributes:
        trigger_type: The type of event that triggered escalation.
            Must be one of: manipulation_pattern, truth_conflict, emotional_spike.
        tier_fired: The tier level that was activated (must be 3 or 4).
        filler_audio_played: Optional path/identifier of filler audio played
            during processing, or None if no filler was used.
        processing_duration_ms: Time in milliseconds taken to process the
            escalation response.
        triggered_at: Timestamp when the escalation occurred.

    Raises:
        ValueError: If trigger_type is not valid or tier_fired is not 3 or 4.

    Example:
        >>> trigger = TierTrigger(
        ...     trigger_type="manipulation_pattern",
        ...     tier_fired=3,
        ...     filler_audio_played="fillers/thinking_01.wav",
        ...     processing_duration_ms=245.5,
        ...     triggered_at=datetime.now()
        ... )
    """

    trigger_type: str
    tier_fired: int
    filler_audio_played: str | None
    processing_duration_ms: float
    triggered_at: datetime

    def __post_init__(self) -> None:
        """Validate trigger_type and tier_fired after initialization."""
        if self.trigger_type not in VALID_TRIGGER_TYPES:
            valid_types = ", ".join(sorted(VALID_TRIGGER_TYPES))
            raise ValueError(
                f"Invalid trigger_type '{self.trigger_type}'. "
                f"Must be one of: {valid_types}"
            )

        if self.tier_fired not in VALID_TIERS:
            raise ValueError(
                f"Invalid tier_fired '{self.tier_fired}'. "
                f"Must be 3 or 4"
            )

        if self.processing_duration_ms < 0:
            raise ValueError(
                f"processing_duration_ms must be non-negative, "
                f"got {self.processing_duration_ms}"
            )


def log_tier_trigger(trigger: TierTrigger) -> None:
    """
    Log a TierTrigger event at INFO level (T052 / US5).

    Emits a structured log record consumable by Cloud Logging and local
    log handlers. Includes all fields needed for latency analysis and
    filler audio audit.

    Args:
        trigger: The TierTrigger event to log.
    """
    logger.info(
        "TierTrigger: tier=%d type=%s filler=%s duration_ms=%.1f triggered_at=%s",
        trigger.tier_fired,
        trigger.trigger_type,
        trigger.filler_audio_played or "none",
        trigger.processing_duration_ms,
        trigger.triggered_at.isoformat(),
    )
