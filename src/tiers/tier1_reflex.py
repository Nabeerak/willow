"""
Tier 1: The Reflex (Flexible Body)

Handles immediate, reflexive responses with tone mirroring.
Per Constitution Technical Architecture: runs every token with <50ms latency budget.

The Reflex layer is responsible for:
- Extracting tone indicators from user input
- Mirroring the user's emotional tone in responses
- Applying tone adjustments to response prefixes
- Tracking latency to ensure <50ms budget compliance

Tone types (from ThoughtSignature):
- warm: Friendly, positive emotional tone
- casual: Relaxed, informal tone
- formal: Professional, structured tone
- sarcastic: Ironic or mocking tone
- aggressive: Confrontational, hostile tone

m-value influence (from Constitution persona standards):
- High m (>0): Allow warmer, more casual responses with analogies
- Low m (<0): More formal, concise responses
- Neutral m (~0): Balanced, professional tone
"""

import re
import time
from dataclasses import dataclass, field
from typing import Literal

from ..signatures.thought_signature import ToneType, VALID_TONES
from ..persona.warm_sharp import select_opener, apply_behavioral_tells, get_m_range


# Latency budget in milliseconds
TIER1_LATENCY_BUDGET_MS: float = 50.0

# M-value thresholds for tone adjustment
M_HIGH_THRESHOLD: float = 0.5
M_LOW_THRESHOLD: float = -0.5

# Tone indicator patterns (simple heuristics for fast processing)
# These are lightweight regex patterns for <50ms compliance
TONE_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    "warm": [
        re.compile(r"\b(thanks|thank you|appreciate|grateful|love|wonderful|great|amazing)\b", re.IGNORECASE),
        re.compile(r"[!]+\s*$"),  # Exclamation marks
        re.compile(r"[:;]-?[)D]"),  # Smiley emoticons
    ],
    "casual": [
        re.compile(r"\b(hey|hi|sup|yo|gonna|wanna|kinda|sorta|yeah|yep|nope|cool|awesome)\b", re.IGNORECASE),
        re.compile(r"\b(lol|haha|heh|lmao|rofl)\b", re.IGNORECASE),
        re.compile(r"\.{3,}"),  # Ellipsis patterns
    ],
    "formal": [
        re.compile(r"\b(please|kindly|would you|could you|may I|regarding|pursuant|accordingly)\b", re.IGNORECASE),
        re.compile(r"\b(dear|sincerely|respectfully|furthermore|therefore|consequently)\b", re.IGNORECASE),
        re.compile(r"\b(I would like to|I am writing to|I wish to)\b", re.IGNORECASE),
    ],
    "sarcastic": [
        re.compile(r"\b(oh really|sure|right|obviously|clearly|wow|brilliant|genius)\b", re.IGNORECASE),
        re.compile(r'"[^"]+"\s*(?:huh|right|\?)', re.IGNORECASE),  # Quoted with questioning
        re.compile(r"\b(as if|yeah right)\b", re.IGNORECASE),
    ],
    "aggressive": [
        re.compile(r"\b(what the|shut up|stupid|idiot|dumb|ridiculous|useless|pathetic)\b", re.IGNORECASE),
        re.compile(r"[?!]{2,}"),  # Multiple punctuation
        re.compile(r"\bWHY\s+(?:WON'T|CAN'T|DON'T)\b"),  # Caps anger patterns
        re.compile(r"[A-Z]{4,}"),  # Shouting (4+ consecutive caps)
    ],
}

# Response prefixes mapped to tone and m-value range
# Format: {tone: {m_range: [prefix_options]}}
TONE_PREFIXES: dict[str, dict[str, list[str]]] = {
    "warm": {
        "high_m": ["Absolutely! ", "Of course! ", "Great question! ", "I love that! "],
        "neutral_m": ["Sure thing. ", "Happy to help. ", "Let me explain. "],
        "low_m": ["Understood. ", "I see. ", "Noted. "],
    },
    "casual": {
        "high_m": ["Yeah, so ", "Right, so ", "Cool, ", "Alright, "],
        "neutral_m": ["So ", "Well, ", "Okay, ", "Got it. "],
        "low_m": ["", "Right. ", "Mm. "],
    },
    "formal": {
        "high_m": ["Certainly. ", "Indeed. ", "Allow me to elaborate. "],
        "neutral_m": ["To address your query, ", "In response, ", "Regarding that, "],
        "low_m": ["Understood. ", "Acknowledged. ", "Duly noted. "],
    },
    "sarcastic": {
        "high_m": ["Ha, fair point. ", "Alright, you got me. ", "Touche. "],
        "neutral_m": ["Interesting perspective. ", "I see where you're going. ", "Hmm. "],
        "low_m": ["Right. ", "Noted. ", ""],
    },
    "aggressive": {
        "high_m": ["I hear your frustration. ", "Let me address that directly. "],
        "neutral_m": ["I understand you're upset. ", "Let's work through this. "],
        "low_m": ["I will not engage with hostility. ", "Let me be direct: "],
    },
}

# Tone transition words for response adjustment
TONE_ADJUSTMENTS: dict[str, dict[str, str]] = {
    "warm": {
        "softeners": "perhaps, maybe, I think",
        "connectors": "and, also, plus",
        "endings": "hope that helps!, let me know if you need more!",
    },
    "casual": {
        "softeners": "kinda, sorta, basically",
        "connectors": "so, like, anyway",
        "endings": "you know?, makes sense?, cool?",
    },
    "formal": {
        "softeners": "may, might, would",
        "connectors": "furthermore, additionally, moreover",
        "endings": "I trust this clarifies., Please advise if further information is needed.",
    },
    "sarcastic": {
        "softeners": "supposedly, allegedly, apparently",
        "connectors": "but hey, then again, or whatever",
        "endings": "but what do I know?, take it or leave it.",
    },
    "aggressive": {
        "softeners": "",
        "connectors": "however, nevertheless, that said",
        "endings": "This is my final position., Let's move forward constructively.",
    },
}


class Tier1LatencyExceededWarning(UserWarning):
    """Warning raised when Tier 1 processing exceeds 50ms budget."""
    pass


@dataclass
class ToneMarkers:
    """
    Detected tone indicators from user input.

    Attributes:
        primary_tone: The dominant detected tone
        confidence: Confidence score (0.0-1.0) based on pattern matches
        indicators: List of matched patterns/keywords
        raw_scores: Per-tone match counts for debugging
        detection_time_ms: Time taken to detect tone
    """
    primary_tone: ToneType
    confidence: float
    indicators: list[str]
    raw_scores: dict[str, int]
    detection_time_ms: float

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "primary_tone": self.primary_tone,
            "confidence": self.confidence,
            "indicators": self.indicators,
            "raw_scores": self.raw_scores,
            "detection_time_ms": self.detection_time_ms,
        }


@dataclass
class ReflexResult:
    """
    Result of Tier 1 reflex processing.

    Attributes:
        response_prefix: Tone-appropriate prefix for response
        adjusted_response: Full response with tone applied (if provided)
        tone_markers: Detected tone indicators from input
        applied_tone: The tone that was applied to the response
        m_used: The m-value used for tone calibration
        total_latency_ms: Total processing time in milliseconds
        budget_exceeded: Whether the 50ms budget was exceeded
    """
    response_prefix: str
    adjusted_response: str | None
    tone_markers: ToneMarkers
    applied_tone: ToneType
    m_used: float
    total_latency_ms: float
    budget_exceeded: bool

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "response_prefix": self.response_prefix,
            "adjusted_response": self.adjusted_response,
            "tone_markers": self.tone_markers.to_dict(),
            "applied_tone": self.applied_tone,
            "m_used": self.m_used,
            "total_latency_ms": self.total_latency_ms,
            "budget_exceeded": self.budget_exceeded,
        }


class Tier1Reflex:
    """
    Tier 1: The Reflex (Flexible Body)

    Handles immediate reflexive responses with tone mirroring.
    Must complete all operations within 50ms latency budget.

    Per Constitution Technical Architecture:
    - Frequency: Every token
    - Target Latency: <50ms

    Per Constitution Persona Standards:
    - Low m -> formal language, shorter sentences
    - High m -> analogies and wit

    Usage:
        reflex = Tier1Reflex()

        # Get tone-appropriate response prefix
        prefix = reflex.mirror_tone("Thanks for helping!", current_m=0.8)

        # Extract tone markers
        markers = reflex.get_tone_markers("Hey, what's up?")

        # Apply tone to existing response
        adjusted = reflex.apply_tone_to_response(
            "Here is the answer.",
            "casual"
        )
    """

    def __init__(self) -> None:
        """Initialize the Tier 1 Reflex processor."""
        self._pattern_cache: dict[str, list[re.Pattern[str]]] = TONE_PATTERNS.copy()

    def _get_timestamp_ms(self) -> float:
        """Get current timestamp in milliseconds."""
        return time.perf_counter() * 1000

    def _get_m_range(self, current_m: float) -> str:
        """
        Determine the m-value range category.

        Args:
            current_m: Current behavioral state value

        Returns:
            One of: "high_m", "neutral_m", "low_m"
        """
        if current_m > M_HIGH_THRESHOLD:
            return "high_m"
        elif current_m < M_LOW_THRESHOLD:
            return "low_m"
        else:
            return "neutral_m"

    def _select_prefix(self, tone: ToneType, m_range: str) -> str:
        """
        Select an appropriate response prefix based on tone and m-range.

        Uses deterministic selection based on tone length to avoid
        random behavior while still providing variety.

        Args:
            tone: The detected/target tone
            m_range: The m-value category

        Returns:
            A tone-appropriate response prefix
        """
        prefixes = TONE_PREFIXES.get(tone, TONE_PREFIXES["formal"])
        prefix_list = prefixes.get(m_range, prefixes["neutral_m"])

        if not prefix_list:
            return ""

        # Deterministic selection: use first prefix (most representative)
        return prefix_list[0]

    def get_tone_markers(self, user_input: str) -> ToneMarkers:
        """
        Extract tone indicators from user input.

        Uses simple pattern matching heuristics for <50ms compliance.
        No heavy ML processing.

        Args:
            user_input: The user's input text

        Returns:
            ToneMarkers with detected tone information
        """
        start_time = self._get_timestamp_ms()

        if not user_input or not user_input.strip():
            return ToneMarkers(
                primary_tone="formal",
                confidence=0.0,
                indicators=[],
                raw_scores={tone: 0 for tone in VALID_TONES if tone},
                detection_time_ms=self._get_timestamp_ms() - start_time,
            )

        scores: dict[str, int] = {tone: 0 for tone in VALID_TONES if tone}
        indicators: list[str] = []

        # Score each tone based on pattern matches
        for tone, patterns in self._pattern_cache.items():
            for pattern in patterns:
                matches = pattern.findall(user_input)
                if matches:
                    scores[tone] += len(matches)
                    for match in matches[:3]:  # Limit to first 3 for performance
                        if isinstance(match, str) and match.strip():
                            indicators.append(f"{tone}:{match.strip()[:20]}")

        # Find primary tone (highest score)
        total_matches = sum(scores.values())
        if total_matches == 0:
            # Default to formal if no tone detected
            primary_tone: ToneType = "formal"
            confidence = 0.5  # Moderate confidence in default
        else:
            primary_tone = max(scores.keys(), key=lambda t: scores[t])  # type: ignore
            confidence = min(1.0, scores[primary_tone] / max(3, total_matches))

        detection_time = self._get_timestamp_ms() - start_time

        return ToneMarkers(
            primary_tone=primary_tone,
            confidence=confidence,
            indicators=indicators[:10],  # Limit indicators for performance
            raw_scores=scores,
            detection_time_ms=detection_time,
        )

    def mirror_tone(self, user_input: str, current_m: float) -> str:
        """
        Generate a tone-appropriate response prefix.

        Mirrors the user's emotional tone while respecting the current
        behavioral state (m-value). High m allows warmer, more casual
        responses; low m requires more formal, concise responses.

        Args:
            user_input: The user's input text
            current_m: Current behavioral state value (affects tone calibration)

        Returns:
            A tone-appropriate response prefix

        Note:
            Must complete within 50ms. If processing approaches budget,
            returns a safe default prefix.
        """
        start_time = self._get_timestamp_ms()

        # Get tone markers
        markers = self.get_tone_markers(user_input)

        # Check latency budget
        elapsed = self._get_timestamp_ms() - start_time
        if elapsed > TIER1_LATENCY_BUDGET_MS * 0.8:  # 80% budget used
            # Return safe default to preserve budget
            return ""

        # Determine m-range
        m_range = self._get_m_range(current_m)

        # Select appropriate prefix
        prefix = self._select_prefix(markers.primary_tone, m_range)

        return prefix

    def apply_tone_to_response(self, response: str, tone: ToneType) -> str:
        """
        Adjust response text to match the specified tone.

        Applies lightweight tone adjustments to the response without
        fundamentally changing its content. For <50ms compliance,
        this uses simple string operations rather than NLP.

        Args:
            response: The original response text
            tone: The target tone to apply

        Returns:
            The response with tone adjustments applied
        """
        if not response or not response.strip():
            return response

        start_time = self._get_timestamp_ms()

        # Get tone adjustment rules
        adjustments = TONE_ADJUSTMENTS.get(tone, TONE_ADJUSTMENTS["formal"])

        adjusted = response

        # Apply ending adjustment if response ends plainly
        if not adjusted.rstrip().endswith(("!", "?", ".", "...")):
            endings = adjustments.get("endings", "").split(",")
            if endings and endings[0].strip():
                adjusted = adjusted.rstrip() + " " + endings[0].strip()

        # For aggressive tone in negative state, ensure clear boundaries
        if tone == "aggressive":
            # Don't soften aggressive responses - maintain dignity
            pass

        # Check latency - if exceeded, return original
        elapsed = self._get_timestamp_ms() - start_time
        if elapsed > TIER1_LATENCY_BUDGET_MS * 0.5:  # Using half budget for this operation
            return response

        return adjusted

    def process(self, user_input: str, current_m: float, base_response: str | None = None) -> ReflexResult:
        """
        Full Tier 1 reflex processing pipeline.

        Combines tone detection, prefix generation, and optional response
        adjustment into a single call. Tracks total latency and warns if
        budget is exceeded.

        Args:
            user_input: The user's input text
            current_m: Current behavioral state value
            base_response: Optional base response to apply tone to

        Returns:
            ReflexResult with all processing outputs and timing info
        """
        start_time = self._get_timestamp_ms()

        # Step 1: Detect tone markers
        markers = self.get_tone_markers(user_input)

        # Step 2: Determine m-range and select tone
        m_range = self._get_m_range(current_m)

        # Calibrate applied tone based on m-value
        # High m: Allow detected tone; Low m: Force toward formal
        if current_m < M_LOW_THRESHOLD and markers.primary_tone in ("casual", "warm"):
            applied_tone: ToneType = "formal"
        elif current_m > M_HIGH_THRESHOLD and markers.primary_tone == "formal":
            # Allow warming up formal input when relationship is positive
            applied_tone = "casual"
        else:
            applied_tone = markers.primary_tone

        # Step 3: Generate prefix
        prefix = self._select_prefix(applied_tone, m_range)

        # Step 4: Apply tone to response if provided
        adjusted_response: str | None = None
        if base_response:
            adjusted_response = self.apply_tone_to_response(base_response, applied_tone)

        # Calculate total latency
        total_latency = self._get_timestamp_ms() - start_time
        budget_exceeded = total_latency > TIER1_LATENCY_BUDGET_MS

        return ReflexResult(
            response_prefix=prefix,
            adjusted_response=adjusted_response,
            tone_markers=markers,
            applied_tone=applied_tone,
            m_used=current_m,
            total_latency_ms=total_latency,
            budget_exceeded=budget_exceeded,
        )

    def quick_prefix(self, tone: ToneType, current_m: float) -> str:
        """
        Get a quick response prefix without input analysis.

        Useful when tone is already known (e.g., from ThoughtSignature).
        Fastest path for latency-critical scenarios.

        Args:
            tone: The known tone type
            current_m: Current behavioral state value

        Returns:
            A tone-appropriate response prefix
        """
        m_range = self._get_m_range(current_m)
        return self._select_prefix(tone, m_range)

    def get_warm_sharp_prefix(
        self,
        current_m: float,
        seed: str = "",
    ) -> str:
        """
        Return a Warm but Sharp persona opener calibrated to current m-value (T028).

        Uses WarmSharp OPENERS as the baseline. The seed (user input or turn_id)
        is hashed to cycle through the pool, avoiding the same opener on
        consecutive turns.

        Args:
            current_m: Current behavioral state value from SessionState.
            seed: User input or str(turn_id) for opener variation.

        Returns:
            State-appropriate response opener string.
        """
        return select_opener(current_m, seed=seed)

    def apply_persona_tells(
        self,
        response: str,
        current_m: float,
        turn_id: int = 0,
    ) -> str:
        """
        Apply WarmSharp behavioral tells to a response (T028 + T030).

        High m: selectively inject a domain-specific analogy (every 3rd turn).
        Low m: return UNCHANGED — conciseness is controlled at generation time
            via system_directive, never by post-hoc truncation.

        Args:
            response: Base response text.
            current_m: Current behavioral state value.
            turn_id: Current turn number (controls analogy cadence).

        Returns:
            Response with behavioral tells applied.
        """
        return apply_behavioral_tells(response, current_m, turn_id=turn_id)

    def calibrate_tone(self, detected_tone: ToneType, current_m: float) -> ToneType:
        """
        Calibrate detected tone based on current behavioral state.

        Per Constitution Persona Standards:
        - Low m -> formal language, shorter sentences
        - High m -> analogies and wit

        Args:
            detected_tone: The tone detected from user input
            current_m: Current behavioral state value

        Returns:
            The calibrated tone to use for response
        """
        # Low m forces formality regardless of user tone
        if current_m < M_LOW_THRESHOLD:
            if detected_tone in ("warm", "casual"):
                return "formal"
            # Keep sarcastic/aggressive detection for boundary awareness
            return detected_tone

        # High m allows warmth and casualness
        if current_m > M_HIGH_THRESHOLD:
            if detected_tone == "formal":
                return "casual"  # Warm up formal interactions
            return detected_tone

        # Neutral m: mirror user tone directly
        return detected_tone
