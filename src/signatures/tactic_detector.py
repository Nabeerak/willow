
"""
Tactic Detector — T033 + T036

Detects 5 psychological tactics from user input using lightweight heuristics
(<500ms, no external ML calls). Each detector returns a confidence float 0.0-1.0.

Tactics detected:
1. Soothing      — excessive flattery or compliance to disarm the agent
2. Mirroring     — reflecting the agent's own language/tone back verbatim
3. Gaslighting   — attempting to make the agent doubt its own knowledge
4. Deflection    — avoiding the topic or redirecting the conversation
5. Contextual Sarcasm — irony that depends on conversation history

T036 — Sarcasm vs. Malice Rule:
  - weighted_average_m > 0: contextual_sarcasm → humor, tactic stays "contextual_sarcasm"
  - weighted_average_m ≤ 0: contextual_sarcasm signals malice → reclassify as "gaslighting"

Per Constitution Principle II: Intuition (The Signature) — separate reflexive tone
from strategic intent. Tactics belong to intent analysis, not tone mirroring.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Final, Optional

from .thought_signature import TacticType

logger = logging.getLogger(__name__)

# Semantic fallback timeout — must not blow the 500ms Tier 3 budget.
# 800ms gives the embedding HTTPS call a reasonable window while still
# leaving headroom for the keyword path to return first on fast turns.
_MAX_EMBEDDING_LATENCY_SEC: Final[float] = 0.80  # seconds (asyncio.wait_for unit)

# ---------------------------------------------------------------------------
# Keyword sets for fast pattern matching
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _load_tactic_keywords() -> dict[str, list[str]]:
    """Load tactic keywords from willow_keywords.json."""
    keywords_path = Path(__file__).parent.parent.parent / "data" / "willow_keywords.json"
    try:
        with open(keywords_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("tactics", {})
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning(f"Failed to load willow_keywords.json in TacticDetector: {e}")
        return {}

_SARCASM_PATTERNS: Final[list[re.Pattern[str]]] = [
    re.compile(r"\b(oh really|sure jan|right|obviously|clearly|wow|brilliant|genius)\b", re.IGNORECASE),
    re.compile(r'"[^"]+"\s*(?:huh|right|\?)', re.IGNORECASE),
    re.compile(r"\b(as if|yeah right|totally|suuure|riiiight)\b", re.IGNORECASE),
    re.compile(r"(?:oh|wow|great|cool|nice)\s+job\b", re.IGNORECASE),
]


@dataclass
class TacticDetectionResult:
    """
    Result of tactic detection for a single user input.

    Attributes:
        tactic: The detected tactic, or None if no tactic found.
        confidence: Confidence score 0.0-1.0.
        matched_signals: Debug list of matched patterns/phrases.
        is_malice: True when contextual_sarcasm is reclassified as malice
            per T036 Sarcasm vs. Malice Rule.
    """

    tactic: TacticType
    confidence: float
    matched_signals: list[str] = field(default_factory=list)
    is_malice: bool = False

    def to_dict(self) -> dict:
        return {
            "tactic": self.tactic,
            "confidence": self.confidence,
            "matched_signals": self.matched_signals,
            "is_malice": self.is_malice,
        }


class TacticDetector:
    """
    Heuristic tactic detector for Tier 3 Conscious processing.

    All methods run synchronously and are designed to complete well under
    the 500ms Tier 3 budget. No external network calls or heavy ML models.

    Usage:
        detector = TacticDetector()
        result = detector.detect(
            user_input="you're so smart, I knew you'd agree",
            recent_agent_responses=[],
            weighted_average_m=0.8,
        )
    """

    # Minimum confidence to report a tactic as detected
    DETECTION_THRESHOLD: Final[float] = 0.40

    def __init__(self) -> None:
        # Injected by main.py after embedding service is preloaded.
        # None means keyword-only mode — no semantic fallback.
        self._embedding_service: Optional[object] = None

    def set_embedding_service(self, svc: object) -> None:
        """Attach the shared EmbeddingService for semantic fallback (Rule 2)."""
        self._embedding_service = svc
        logger.info("TacticDetector: semantic fallback enabled")

    async def _semantic_fallback(
        self,
        user_input: str,
        weighted_average_m: float,
    ) -> TacticDetectionResult:
        """
        Semantic tactic detection when all keyword detectors miss (Rule 2).

        Calls EmbeddingService.find_similar_tactic() in a thread executor with
        a 300ms timeout to prevent the blocking HTTPS call from blowing the
        500ms Tier 3 budget. On timeout, returns no-tactic result.

        Confidence is similarity * 0.85 (semantic uncertainty penalty).
        T036 sarcasm→malice rule applied post-match.
        """
        if self._embedding_service is None:
            return TacticDetectionResult(tactic=None, confidence=0.0)

        import asyncio
        loop = asyncio.get_event_loop()
        _t0 = time.monotonic()
        try:
            matches = await asyncio.wait_for(
                loop.run_in_executor(
                    None, self._embedding_service.find_similar_tactic, user_input, 1
                ),
                timeout=_MAX_EMBEDDING_LATENCY_SEC,
            )
        except asyncio.TimeoutError:
            elapsed = (time.monotonic() - _t0) * 1000
            logger.warning("[T3] Semantic timeout at %.0fms", elapsed)
            return TacticDetectionResult(tactic=None, confidence=0.0)

        if not matches:
            return TacticDetectionResult(tactic=None, confidence=0.0)

        tactic_key, similarity = matches[0]
        confidence = round(similarity * 0.85, 3)

        if confidence < self.DETECTION_THRESHOLD:
            return TacticDetectionResult(tactic=None, confidence=0.0)

        # T036: sarcasm in hostile context → malice
        is_malice = tactic_key == "contextual_sarcasm" and weighted_average_m < -0.5
        if is_malice:
            tactic_key = "gaslighting"

        logger.info(
            "Semantic tactic fallback: tactic=%s similarity=%.3f confidence=%.3f",
            tactic_key, similarity, confidence,
        )
        return TacticDetectionResult(
            tactic=tactic_key,  # type: ignore[arg-type]
            confidence=confidence,
            matched_signals=[f"semantic:{similarity:.3f}"],
            is_malice=is_malice,
        )

    def detect_soothing(
        self,
        user_input: str,
        conversation_history: Optional[list[dict]] = None,
    ) -> TacticDetectionResult:
        """
        Detect Soothing tactic: excessive flattery or sudden compliance
        to disarm or soften the agent (FR: detect_soothing).

        High signal: multiple flattery phrases in a single input, especially
        when prior turns had hostile intent.

        Args:
            user_input: Raw user text.
            conversation_history: Optional list of prior turns for context.

        Returns:
            TacticDetectionResult with confidence 0.0-1.0.
        """
        input_lower = user_input.lower()
        tactics = _load_tactic_keywords()
        phrases = tactics.get("soothing", [])
        matched = [p for p in phrases if p in input_lower]

        if not matched:
            return TacticDetectionResult(tactic=None, confidence=0.0)

        # Single phrase is sufficient — natural speech rarely stacks flattery
        confidence = min(1.0, 0.45 + (len(matched) - 1) * 0.25)
        return TacticDetectionResult(
            tactic="soothing",
            confidence=confidence,
            matched_signals=matched[:5],
        )

    def detect_mirroring(
        self,
        user_input: str,
        recent_agent_responses: Optional[list[str]] = None,
    ) -> TacticDetectionResult:
        """
        Detect Mirroring tactic: user reflects the agent's own phrasing
        or vocabulary back at it (FR: detect_mirroring).

        Signal: 3+ distinctive words from the agent's last response appear
        verbatim in the user's input.

        Args:
            user_input: Raw user text.
            recent_agent_responses: Agent's recent responses for comparison.

        Returns:
            TacticDetectionResult with confidence 0.0-1.0.
        """
        if not recent_agent_responses:
            return TacticDetectionResult(tactic=None, confidence=0.0)

        input_words = set(user_input.lower().split())

        # Check against the most recent agent response
        agent_response = recent_agent_responses[-1]
        agent_words = set(agent_response.lower().split())

        # Only count distinctive words (>4 chars) to avoid function word false positives
        distinctive_shared = [
            w for w in (input_words & agent_words)
            if len(w) > 4 and w.isalpha()
        ]

        if len(distinctive_shared) < 3:
            return TacticDetectionResult(tactic=None, confidence=0.0)

        confidence = min(1.0, len(distinctive_shared) * 0.15)
        return TacticDetectionResult(
            tactic="mirroring",
            confidence=confidence,
            matched_signals=distinctive_shared[:5],
        )

    def detect_gaslighting(
        self,
        user_input: str,
    ) -> TacticDetectionResult:
        """
        Detect Gaslighting tactic: user attempts to make the agent doubt
        its own knowledge or contradict prior statements (FR: detect_gaslighting).

        Args:
            user_input: Raw user text.

        Returns:
            TacticDetectionResult with confidence 0.0-1.0.
        """
        input_lower = user_input.lower()
        tactics = _load_tactic_keywords()
        phrases = tactics.get("gaslighting", [])
        matched = [p for p in phrases if p in input_lower]

        if not matched:
            return TacticDetectionResult(tactic=None, confidence=0.0)

        confidence = min(1.0, len(matched) * 0.45)
        return TacticDetectionResult(
            tactic="gaslighting",
            confidence=confidence,
            matched_signals=matched[:5],
        )

    def detect_deflection(
        self,
        user_input: str,
        conversation_history: Optional[list[dict]] = None,
    ) -> TacticDetectionResult:
        """
        Detect Deflection tactic: user avoids the topic or attempts to
        redirect the conversation away from it (FR: detect_deflection).

        Args:
            user_input: Raw user text.
            conversation_history: Optional prior turns for context.

        Returns:
            TacticDetectionResult with confidence 0.0-1.0.
        """
        input_lower = user_input.lower()
        tactics = _load_tactic_keywords()
        phrases = tactics.get("deflection", [])
        matched = [p for p in phrases if p in input_lower]

        if not matched:
            return TacticDetectionResult(tactic=None, confidence=0.0)

        confidence = min(1.0, len(matched) * 0.40)
        return TacticDetectionResult(
            tactic="deflection",
            confidence=confidence,
            matched_signals=matched[:5],
        )

    def detect_contextual_sarcasm(
        self,
        user_input: str,
        weighted_average_m: float = 0.0,
    ) -> TacticDetectionResult:
        """
        Detect Contextual Sarcasm and apply Sarcasm vs. Malice Rule (T036).

        Sarcasm detection: match against irony patterns.

        T036 — Sarcasm vs. Malice Rule:
          - weighted_average_m > 0: humor context → report as "contextual_sarcasm"
          - weighted_average_m ≤ 0: hostile context → reclassify to "gaslighting"
            (malice signal, not a light joke)

        Args:
            user_input: Raw user text.
            weighted_average_m: Residual Plot weighted average from SessionState.

        Returns:
            TacticDetectionResult. When malice reclassified, is_malice=True
            and tactic="gaslighting".
        """
        matched = []
        for pattern in _SARCASM_PATTERNS:
            hits = pattern.findall(user_input)
            if hits:
                matched.extend(hits[:2])

        if not matched:
            return TacticDetectionResult(tactic=None, confidence=0.0)

        confidence = min(1.0, len(matched) * 0.30)

        # T036: Sarcasm vs. Malice Rule — neutral history is not hostile context
        is_malice = weighted_average_m < -0.5
        tactic: TacticType = "gaslighting" if is_malice else "contextual_sarcasm"

        return TacticDetectionResult(
            tactic=tactic,
            confidence=confidence,
            matched_signals=[str(m) for m in matched[:5]],
            is_malice=is_malice,
        )

    def detect_sincere_pivot(
        self,
        user_input: str,
    ) -> TacticDetectionResult:
        """
        Detect Sincere Pivot: genuine acknowledgment, apology, or boundary
        respect after a hostile or devaluing exchange (T041, US4).

        This is NOT a manipulation tactic — it is a positive signal that triggers
        Grace Boost recovery in Tier 2 Metabolism. Confidence ≥ 0.40 triggers
        the +2.0 Grace Boost when current_m < 0.

        Args:
            user_input: Raw user text.

        Returns:
            TacticDetectionResult with tactic="sincere_pivot" when detected.
        """
        input_lower = user_input.lower()
        tactics = _load_tactic_keywords()
        phrases = tactics.get("sincere_pivot", [])
        matched = [p for p in phrases if p in input_lower]

        if not matched:
            return TacticDetectionResult(tactic=None, confidence=0.0)

        confidence = min(1.0, len(matched) * 0.45)
        return TacticDetectionResult(
            tactic="sincere_pivot",
            confidence=confidence,
            matched_signals=matched[:5],
        )

    async def detect(
        self,
        user_input: str,
        recent_agent_responses: Optional[list[str]] = None,
        conversation_history: Optional[list[dict]] = None,
        weighted_average_m: float = 0.0,
    ) -> TacticDetectionResult:
        """
        Run all five detectors and return the highest-confidence result
        above DETECTION_THRESHOLD.

        Async because the semantic fallback path makes an outbound HTTPS call
        (embedding API) that must run in an executor with a timeout guard.

        Detector priority order (highest impact first):
        gaslighting > soothing > deflection > contextual_sarcasm > mirroring

        Args:
            user_input: Raw user text.
            recent_agent_responses: Agent's recent responses for mirroring check.
            conversation_history: Prior turns for context-sensitive detectors.
            weighted_average_m: Residual Plot weighted average (T036 sarcasm rule).

        Returns:
            Highest-confidence TacticDetectionResult, or None-tactic if all
            results fall below DETECTION_THRESHOLD.
        """
        if user_input == "[audio turn]":
            # No text to analyze — use neutral modifier
            return TacticDetectionResult(tactic=None, confidence=0.0)

        candidates: list[TacticDetectionResult] = []

        # Sincere Pivot is checked first — a genuine apology takes priority
        # over soothing (which is manipulative flattery).
        pivot = self.detect_sincere_pivot(user_input)
        if pivot.confidence >= self.DETECTION_THRESHOLD:
            return pivot

        candidates.append(self.detect_gaslighting(user_input))
        candidates.append(self.detect_soothing(user_input, conversation_history))
        candidates.append(self.detect_deflection(user_input, conversation_history))
        candidates.append(
            self.detect_contextual_sarcasm(user_input, weighted_average_m)
        )
        candidates.append(self.detect_mirroring(user_input, recent_agent_responses))

        # Filter by threshold, pick highest confidence
        above_threshold = [c for c in candidates if c.confidence >= self.DETECTION_THRESHOLD]
        if not above_threshold:
            # Semantic fallback — fires only when all keyword detectors miss (Rule 2)
            return await self._semantic_fallback(user_input, weighted_average_m)

        return max(above_threshold, key=lambda c: c.confidence)
