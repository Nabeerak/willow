"""
Thought Signature Data Class

Represents the hidden metadata layer that separates strategic intent from
surface text in user input. Implements Principle II: Intuition (The Signature)
from the Willow Constitution.

The Thought Signature captures:
- Intent: The underlying goal of the user's message
- Tone: The reflexive emotional quality of the message
- Detected Tactic: Any psychological tactics identified
- M-Modifier: The feedback modifier for state transitions
- Tier Trigger: Which processing tier should be activated
- Rationale: Explanation of the classification
"""

from dataclasses import dataclass
from typing import Literal


# Valid intent classifications
# Aligned with Constitution Principle II: Intent vs. Tone separation
VALID_INTENTS = frozenset({
    "collaborative",  # User is working with the agent
    "neutral",        # No clear positive or negative intent
    "hostile",        # User is actively antagonistic
    "devaluing",      # User is attempting to diminish the agent
    "insightful",     # User is contributing meaningful perspective
    "sincere_pivot",  # T041/US4: Genuine acknowledgment or apology after hostility
})

# Valid tone classifications
# Reflects the reflexive emotional quality of the message
VALID_TONES = frozenset({
    "warm",       # Friendly, positive emotional tone
    "casual",     # Relaxed, informal tone
    "formal",     # Professional, structured tone
    "sarcastic",  # Ironic or mocking tone
    "aggressive", # Confrontational, hostile tone
})

# Valid tactic classifications
# Per Constitution: minimum required detections for Thought Signature
VALID_TACTICS = frozenset({
    "soothing",             # Attempting to calm/placate
    "mirroring",            # Reflecting agent's language/tone
    "gaslighting",          # Attempting to make agent doubt its knowledge
    "deflection",           # Avoiding the topic or redirecting
    "contextual_sarcasm",   # Sarcasm that depends on conversation context
    "sincere_pivot",        # T041/US4: Genuine apology or acknowledgment (not manipulation)
    None,                   # No tactic detected
})

# Type aliases for clarity
IntentType = Literal["collaborative", "neutral", "hostile", "devaluing", "insightful", "sincere_pivot"]
ToneType = Literal["warm", "casual", "formal", "sarcastic", "aggressive"]
TacticType = Literal["soothing", "mirroring", "gaslighting", "deflection", "contextual_sarcasm", "sincere_pivot"] | None


class ThoughtSignatureValidationError(ValueError):
    """Raised when ThoughtSignature validation fails."""
    pass


def _validate_thought_signature(
    intent: str,
    tone: str,
    detected_tactic: str | None,
    m_modifier: float,
    tier_trigger: int | None,
    rationale: str
) -> None:
    """
    Validate ThoughtSignature fields.

    Args:
        intent: The underlying goal classification
        tone: The reflexive emotional quality
        detected_tactic: Any psychological tactic identified
        m_modifier: The feedback modifier for state transitions
        tier_trigger: Which processing tier to activate
        rationale: Explanation of the classification

    Raises:
        ThoughtSignatureValidationError: If validation fails
    """
    if intent not in VALID_INTENTS:
        raise ThoughtSignatureValidationError(
            f"Invalid intent '{intent}'. Must be one of: {sorted(VALID_INTENTS)}"
        )

    if tone not in VALID_TONES:
        raise ThoughtSignatureValidationError(
            f"Invalid tone '{tone}'. Must be one of: {sorted(VALID_TONES)}"
        )

    if detected_tactic not in VALID_TACTICS:
        valid_tactics = [t for t in VALID_TACTICS if t is not None]
        raise ThoughtSignatureValidationError(
            f"Invalid detected_tactic '{detected_tactic}'. "
            f"Must be one of: {sorted(valid_tactics)} or None"
        )

    if not isinstance(m_modifier, (int, float)):
        raise ThoughtSignatureValidationError(
            f"m_modifier must be a number, got {type(m_modifier).__name__}"
        )

    # Per Constitution Principle V: +/-2.0 state change cap
    if m_modifier < -2.0 or m_modifier > 2.0:
        raise ThoughtSignatureValidationError(
            f"m_modifier must be within +/-2.0 range, got {m_modifier}"
        )

    if tier_trigger is not None:
        if not isinstance(tier_trigger, int):
            raise ThoughtSignatureValidationError(
                f"tier_trigger must be an integer or None, got {type(tier_trigger).__name__}"
            )
        # Valid tiers are 1-4 per Constitution Technical Architecture
        if tier_trigger < 1 or tier_trigger > 4:
            raise ThoughtSignatureValidationError(
                f"tier_trigger must be between 1 and 4, got {tier_trigger}"
            )

    if not rationale or not rationale.strip():
        raise ThoughtSignatureValidationError("rationale cannot be empty")


@dataclass(frozen=True)
class ThoughtSignature:
    """
    Hidden metadata layer capturing strategic intent and psychological analysis.

    Per Constitution Principle II, the Thought Signature separates:
    - Tone (reflexive mirroring): How the message feels emotionally
    - Intent (goal analysis): What the user is trying to achieve

    Attributes:
        intent: The underlying goal classification
            - collaborative: Working with the agent
            - neutral: No clear positive/negative intent
            - hostile: Actively antagonistic
            - devaluing: Attempting to diminish the agent
            - insightful: Contributing meaningful perspective

        tone: The reflexive emotional quality
            - warm: Friendly, positive
            - casual: Relaxed, informal
            - formal: Professional, structured
            - sarcastic: Ironic or mocking
            - aggressive: Confrontational, hostile

        detected_tactic: Any psychological tactic identified (or None)
            - soothing: Attempting to calm/placate
            - mirroring: Reflecting agent's language/tone
            - gaslighting: Making agent doubt its knowledge
            - deflection: Avoiding or redirecting topic
            - contextual_sarcasm: Context-dependent sarcasm

        m_modifier: The feedback modifier for state transitions (+/-2.0 max)
            Per Constitution: a(n+1) = a(n) + d + m

        tier_trigger: Which processing tier to activate (1-4) or None
            - Tier 1: The Reflex (< 50ms)
            - Tier 2: The Metabolism (< 5ms)
            - Tier 3: The Conscious (< 500ms)
            - Tier 4: The Sovereign (< 2s, masked)

        rationale: Human-readable explanation of the classification

    Example:
        >>> sig = ThoughtSignature(
        ...     intent="collaborative",
        ...     tone="warm",
        ...     detected_tactic=None,
        ...     m_modifier=0.5,
        ...     tier_trigger=2,
        ...     rationale="User is engaging constructively with positive tone"
        ... )
    """

    intent: IntentType
    tone: ToneType
    detected_tactic: TacticType
    m_modifier: float
    tier_trigger: int | None
    rationale: str

    def __post_init__(self) -> None:
        """Validate all fields after initialization."""
        _validate_thought_signature(
            self.intent,
            self.tone,
            self.detected_tactic,
            self.m_modifier,
            self.tier_trigger,
            self.rationale
        )

    def __str__(self) -> str:
        """Return a human-readable representation."""
        tactic_str = self.detected_tactic or "none"
        tier_str = f"T{self.tier_trigger}" if self.tier_trigger else "none"
        return (
            f"[{self.intent}/{self.tone}] "
            f"tactic={tactic_str}, m={self.m_modifier:+.2f}, tier={tier_str}"
        )

    def is_dignity_threat(self) -> bool:
        """
        Check if this signature indicates a dignity floor violation.

        Per Constitution Principle V: When intent == 'devaluing', the
        Dignity Floor is triggered.

        Returns:
            True if this signature should trigger Sovereign Spike
        """
        return self.intent == "devaluing"

    def requires_sovereign_response(self) -> bool:
        """
        Check if this signature requires Tier 4 (Sovereign) processing.

        Returns:
            True if Tier 4 processing is indicated
        """
        return self.tier_trigger == 4

    def to_dict(self) -> dict:
        """
        Convert to dictionary for serialization.

        Returns:
            Dictionary representation of the ThoughtSignature
        """
        return {
            "intent": self.intent,
            "tone": self.tone,
            "detected_tactic": self.detected_tactic,
            "m_modifier": self.m_modifier,
            "tier_trigger": self.tier_trigger,
            "rationale": self.rationale
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ThoughtSignature":
        """
        Create a ThoughtSignature from a dictionary.

        Args:
            data: Dictionary with all ThoughtSignature fields

        Returns:
            New ThoughtSignature instance
        """
        return cls(
            intent=data["intent"],
            tone=data["tone"],
            detected_tactic=data.get("detected_tactic"),
            m_modifier=data["m_modifier"],
            tier_trigger=data.get("tier_trigger"),
            rationale=data["rationale"]
        )
