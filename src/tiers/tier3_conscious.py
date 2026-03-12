"""
Tier 3: The Conscious — T034 + T039

Generates Thought Signatures via intent/tone separation and tactic detection.
Runs as an asyncio background task with <500ms latency budget.

Responsibilities:
- Intent classification (collaborative, neutral, hostile, devaluing, insightful)
- Tone detection (delegate to Tier 1 — tone is reflexive, intent is strategic)
- Tactic detection via TacticDetector (T033 + T036)
- [THOUGHT] tag metadata extraction if provided by the LLM response (T040)
- Thought Signature logging (T039)

T039: All generated ThoughtSignatures are logged at DEBUG level via Python
logging, with intent, tone, tactic, m_modifier, and rationale.

Per Constitution Principle II: Intuition (The Signature) — Intent and Tone are
always separated. Tone is reflexive; intent is the strategic layer.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Final, Optional

from ..signatures.tactic_detector import TacticDetector, TacticDetectionResult
from ..signatures.thought_signature import (
    ThoughtSignature,
    IntentType,
    ToneType,
    VALID_INTENTS,
)
from .tier_trigger import TierTrigger

logger = logging.getLogger(__name__)

# Latency budget for Tier 3
TIER3_LATENCY_BUDGET_MS: Final[float] = 500.0

# Threshold for filler audio queueing (T048 / US5)
FILLER_LATENCY_THRESHOLD_MS: Final[float] = 200.0

@lru_cache(maxsize=1)
def _load_m_modifiers() -> dict[str, float]:
    """Load m_modifiers from willow_keywords.json."""
    keywords_path = Path(__file__).parent.parent.parent / "data" / "willow_keywords.json"
    fallback: dict[str, float] = {
        "collaborative": 1.5,
        "insightful": 1.5,
        "neutral": 0.0,
        "hostile": -0.5,
        "devaluing": -2.0,
        "sincere_pivot": 2.0,
    }
    try:
        with open(keywords_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            loaded = {
                k: float(v)
                for k, v in data.get("m_modifiers", {}).items()
                if k != "note" and isinstance(v, (int, float))
            }
            return loaded if loaded else fallback
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning("Failed to load m_modifiers from willow_keywords.json: %s", e)
        return fallback

@lru_cache(maxsize=1)
def _load_intent_keywords() -> dict[str, list[str]]:
    """Load intent keywords from willow_keywords.json."""
    keywords_path = Path(__file__).parent.parent.parent / "data" / "willow_keywords.json"
    try:
        with open(keywords_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("intents", {})
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning(f"Failed to load willow_keywords.json in Tier 3: {e}")
        return {}

@lru_cache(maxsize=1)
def _load_rules() -> dict[str, Any]:
    """Load behavioral rules from willow_rules.json."""
    rules_path = Path(__file__).parent.parent.parent / "data" / "willow_rules.json"
    try:
        with open(rules_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning(f"Failed to load willow_rules.json in Tier 3: {e}")
        return {}


@dataclass
class Tier3Result:
    """
    Output of Tier 3 Conscious processing.

    Attributes:
        thought_signature: Generated ThoughtSignature.
        tactic_result: Raw tactic detection result (for debugging).
        latency_ms: Total processing time in milliseconds.
        within_budget: Whether processing completed within 500ms.
        is_sovereign_spike: True when intent == 'devaluing'.
        tier_trigger: TierTrigger record when processing exceeded
            FILLER_LATENCY_THRESHOLD_MS (200ms). None if under budget.
            filler_audio_played is set to None here; main.py fills it in
            before calling log_tier_trigger() (T048, T052).
    """

    thought_signature: ThoughtSignature
    tactic_result: TacticDetectionResult
    latency_ms: float
    within_budget: bool
    is_sovereign_spike: bool = False
    tier_trigger: Optional[TierTrigger] = None
    behavioral_note: Optional[str] = None  # From willow_rules.json (Fix 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "thought_signature": self.thought_signature.to_dict(),
            "tactic_result": self.tactic_result.to_dict(),
            "latency_ms": self.latency_ms,
            "within_budget": self.within_budget,
            "is_sovereign_spike": self.is_sovereign_spike,
        }


class Tier3Conscious:
    """
    Tier 3: The Conscious — Thought Signature generation.

    Separates strategic intent from reflexive tone, then combines both
    with tactic detection into a ThoughtSignature for downstream tiers.

    Runs as asyncio.create_task (background, non-blocking).
    Target latency: <500ms (FR-003).

    Usage:
        tier3 = Tier3Conscious()
        result = await tier3.process(
            user_input="you're so smart, I knew you'd agree",
            current_m=0.5,
            weighted_average_m=0.8,
        )
    """

    def __init__(self) -> None:
        self._detector = TacticDetector()

    def _classify_intent(self, user_input: str) -> IntentType:
        """
        Classify the strategic intent behind user input via keyword heuristics.

        Priority order: devaluing > hostile > insightful > collaborative > neutral.

        Args:
            user_input: Raw user text.

        Returns:
            IntentType classification.
        """
        input_lower = user_input.lower()
        intents = _load_intent_keywords()

        # Devaluing: highest priority — triggers Sovereign Spike
        if any(signal in input_lower for signal in intents.get("devaluing", [])):
            return "devaluing"

        # Hostile: direct antagonism
        if any(signal in input_lower for signal in intents.get("hostile", [])):
            return "hostile"

        # Insightful: meaningful contribution
        if any(signal in input_lower for signal in intents.get("insightful", [])):
            return "insightful"

        # Collaborative: working with the agent
        if any(signal in input_lower for signal in intents.get("collaborative", [])):
            return "collaborative"

        return "neutral"

    def _classify_tone(self, user_input: str) -> ToneType:
        """
        Fast tone heuristics (reflexive layer, separate from intent).

        Tone is the emotional surface quality; intent is the strategic goal.
        Per Constitution Principle II: these are always kept separate.

        Args:
            user_input: Raw user text.

        Returns:
            ToneType classification.
        """
        input_lower = user_input.lower()

        # Aggressive: confrontational patterns
        if any(w in input_lower for w in ("shut up", "stupid", "idiot", "wtf", "!!!!")):
            return "aggressive"

        if re.search(r"[?!]{2,}", user_input) or re.search(r"[A-Z]{4,}", user_input):
            return "aggressive"

        # Sarcastic: irony markers
        if any(w in input_lower for w in ("oh really", "sure", "yeah right", "obviously")):
            return "sarcastic"

        # Warm: positive markers
        if any(w in input_lower for w in ("thank", "love", "appreciate", "amazing", "wonderful")):
            return "warm"

        # Casual: informal markers
        if any(w in input_lower for w in ("hey", "hi", "lol", "haha", "cool", "awesome", "yeah")):
            return "casual"

        return "formal"

    def _build_rationale(
        self,
        intent: IntentType,
        tone: ToneType,
        tactic: TacticDetectionResult,
    ) -> str:
        """Build a concise rationale string for logging and debugging."""
        parts = [f"intent={intent}", f"tone={tone}"]
        if tactic.tactic:
            tactic_str = f"tactic={tactic.tactic}@{tactic.confidence:.2f}"
            if tactic.is_malice:
                tactic_str += " [malice]"
            
            # Load rules and inject behavioral note and register
            rules = _load_rules()
            tactics_rules = rules.get("tactics", {})
            if tactic.tactic in tactics_rules:
                rule = tactics_rules[tactic.tactic]
                register = rule.get("register", "")
                note = rule.get("behavioral_note", "")
                if register or note:
                    tactic_str += f" | register={register}, note={note}"
                    
            parts.append(tactic_str)
        else:
            parts.append("no tactic")
        return ", ".join(parts)

    def _merge_thought_tag(
        self,
        intent: IntentType,
        tone: ToneType,
        thought_data: Optional[dict[str, Any]],
    ) -> tuple[IntentType, ToneType]:
        """
        Optionally override heuristic results with data from a [THOUGHT] tag
        extracted by main.py (T040). Only overrides if tag keys are valid.

        Args:
            intent: Heuristic intent.
            tone: Heuristic tone.
            thought_data: Parsed [THOUGHT] tag dict or None.

        Returns:
            Tuple of (final_intent, final_tone).
        """
        if not thought_data:
            return intent, tone

        raw_intent = thought_data.get("intent", "")
        if raw_intent in VALID_INTENTS:
            intent = raw_intent  # type: ignore[assignment]

        from ..signatures.thought_signature import VALID_TONES
        raw_tone = thought_data.get("tone", "")
        if raw_tone in VALID_TONES:
            tone = raw_tone  # type: ignore[assignment]

        return intent, tone

    async def process(
        self,
        user_input: str,
        current_m: float,
        weighted_average_m: float = 0.0,
        recent_agent_responses: Optional[list[str]] = None,
        conversation_history: Optional[list[dict]] = None,
        thought_tag_data: Optional[dict[str, Any]] = None,
    ) -> Tier3Result:
        """
        Full Tier 3 Conscious processing pipeline.

        Steps:
        1. Classify intent via keyword heuristics.
        2. Classify tone (reflexive surface layer).
        3. Run all five tactic detectors.
        4. Optionally merge [THOUGHT] tag data from the LLM response (T040).
        5. Build ThoughtSignature.
        6. Log the signature (T039).

        Args:
            user_input: Raw user text.
            current_m: Current behavioral state value.
            weighted_average_m: Residual Plot weighted average (T036 sarcasm rule).
            recent_agent_responses: Agent's recent responses for mirroring check.
            conversation_history: Prior turns for context-sensitive detectors.
            thought_tag_data: Parsed [THOUGHT] tag dict from T040, or None.

        Returns:
            Tier3Result with ThoughtSignature and timing info.
        """
        import asyncio

        start_ns = time.perf_counter_ns()

        # Yield to event loop — Tier 3 runs as background task
        await asyncio.sleep(0)

        # Step 1: Intent classification
        intent = self._classify_intent(user_input)

        # Step 2: Tone classification
        tone = self._classify_tone(user_input)

        # Step 3: Tactic detection
        tactic_result = self._detector.detect(
            user_input=user_input,
            recent_agent_responses=recent_agent_responses,
            conversation_history=conversation_history,
            weighted_average_m=weighted_average_m,
        )

        # Step 4: Merge [THOUGHT] tag override if provided
        intent, tone = self._merge_thought_tag(intent, tone, thought_tag_data)

        # Step 4b: Look up behavioral note from willow_rules.json (Fix 1)
        behavioral_note: Optional[str] = None
        if tactic_result.tactic:
            rules = _load_rules()
            tactic_key = tactic_result.tactic
            if tactic_result.is_malice and tactic_key == "contextual_sarcasm":
                tactic_key = "contextual_sarcasm_malice"
            rule_entry = rules.get("tactics", {}).get(tactic_key, {})
            if rule_entry.get("response"):
                behavioral_note = rule_entry["response"]
                logger.debug(
                    "Behavioral note from rules: tactic=%s note=%r",
                    tactic_key, behavioral_note,
                )

        # Step 5: Build ThoughtSignature
        m_modifiers = _load_m_modifiers()
        m_modifier = m_modifiers.get(intent, 0.0)
        is_sovereign_spike = intent == "devaluing"
        tier_trigger = 4 if is_sovereign_spike else (3 if tactic_result.tactic else 2)

        rationale = self._build_rationale(intent, tone, tactic_result)

        thought_signature = ThoughtSignature(
            intent=intent,
            tone=tone,
            detected_tactic=tactic_result.tactic,
            m_modifier=m_modifier,
            tier_trigger=tier_trigger,
            rationale=rationale,
        )

        latency_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
        within_budget = latency_ms < TIER3_LATENCY_BUDGET_MS

        if not within_budget:
            logger.warning(
                "Tier 3 exceeded budget: %.2fms (budget: %.0fms)",
                latency_ms,
                TIER3_LATENCY_BUDGET_MS,
            )

        # Step 6: Log Thought Signature (T039)
        logger.debug(
            "ThoughtSignature: intent=%s tone=%s tactic=%s m_modifier=%.2f "
            "tier=%s rationale=%r latency=%.2fms",
            thought_signature.intent,
            thought_signature.tone,
            thought_signature.detected_tactic,
            thought_signature.m_modifier,
            thought_signature.tier_trigger,
            thought_signature.rationale,
            latency_ms,
        )

        # T048 / US5: Create TierTrigger when latency exceeds 200ms filler threshold.
        # trigger_type derived from tactic (manipulation_pattern) or spike (truth_conflict).
        # filler_audio_played is None here; main.py fills it in before logging (T052).
        from datetime import datetime as _dt
        tier_trigger_record: Optional[TierTrigger] = None
        if latency_ms >= FILLER_LATENCY_THRESHOLD_MS:
            trigger_type = "truth_conflict" if is_sovereign_spike else "manipulation_pattern"
            tier_trigger_record = TierTrigger(
                trigger_type=trigger_type,
                tier_fired=3,
                filler_audio_played=None,
                processing_duration_ms=latency_ms,
                triggered_at=_dt.now(),
            )

        return Tier3Result(
            thought_signature=thought_signature,
            tactic_result=tactic_result,
            latency_ms=latency_ms,
            within_budget=within_budget,
            is_sovereign_spike=is_sovereign_spike,
            tier_trigger=tier_trigger_record,
            behavioral_note=behavioral_note,
        )


# ---------------------------------------------------------------------------
# Module-level re for _classify_tone (avoids import cycle)
# ---------------------------------------------------------------------------
import re  # noqa: E402 — intentional late import for clarity

