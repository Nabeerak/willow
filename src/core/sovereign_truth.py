"""
Sovereign Truth Data Class and Cache

Represents a curated fact in Willow's Owned Plot - knowledge that takes
priority over user claims and base model training. Sovereign Truths NEVER
enter the LLM context window under any condition (FR-007).

Part of Principle III: Integrity (The Anchor) from the Willow Constitution.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from .embedding import EmbeddingService


class SovereignTruthValidationError(ValueError):
    """Raised when SovereignTruth validation fails."""
    pass


class SovereignTruthIntegrityError(RuntimeError):
    """Raised when sovereign_truths.json hash does not match Secret Manager."""
    pass


def _validate_sovereign_truth(
    key: str,
    assertion: str,
    contradiction_keywords: list[str],
    response_template: str,
    priority: int | bool,
) -> None:
    """
    Validate SovereignTruth fields.

    Args:
        key: Unique identifier for the truth
        assertion: The factual statement
        contradiction_keywords: Non-empty list of keywords for deterministic matching
        response_template: Pre-written persona-calibrated response text
        priority: Priority level (int 1-10 or boolean)

    Raises:
        SovereignTruthValidationError: If validation fails
    """
    if not key or not key.strip():
        raise SovereignTruthValidationError("key cannot be empty")

    if not assertion or not assertion.strip():
        raise SovereignTruthValidationError("assertion cannot be empty")

    if not contradiction_keywords:
        raise SovereignTruthValidationError(
            "contradiction_keywords must be a non-empty list"
        )
    for kw in contradiction_keywords:
        if not isinstance(kw, str) or not kw.strip():
            raise SovereignTruthValidationError(
                f"each contradiction keyword must be a non-empty string, got {kw!r}"
            )

    if not response_template or not response_template.strip():
        raise SovereignTruthValidationError("response_template cannot be empty")

    if not isinstance(priority, (int, bool)):
        raise SovereignTruthValidationError(
            f"priority must be an integer or boolean, got {type(priority).__name__}"
        )

    if type(priority) is int:
        if priority < 1 or priority > 10:
            raise SovereignTruthValidationError(
                f"priority must be between 1 and 10, got {priority}"
            )


@dataclass(frozen=True)
class SovereignTruth:
    """
    A curated fact in Willow's Owned Plot.

    Sovereign Truths are immutable facts that Willow will defend with confidence.
    When user context contradicts a Sovereign Truth, the Sovereign Truth wins.
    Truths NEVER enter the LLM context window (FR-007). The response_template
    stores persona-calibrated Tier 4 response text as data, not code (FR-008h).

    Attributes:
        key: Unique identifier for the truth (e.g., 'willow_definition')
        assertion: The factual statement Willow will assert
        contradiction_keywords: Keywords enabling deterministic pattern matching
        response_template: Pre-written Warm but Sharp persona response text, or
            "[VACUUM_MODE]" sentinel when vacuum_mode is True
        priority: Priority level 1-10 (1 = highest priority, core identity facts)
        vacuum_mode: When True, suppress all speech; play acoustic heartbeat only
            and serve response_on_return when the user next sends a utility signal.
            T035 MUST check this flag before constructing any audio response.
        response_on_return: Response to deliver when the user returns after vacuum
            mode. Only meaningful when vacuum_mode is True.
        created_at: Timestamp when the truth was created

    Priority Guidelines:
        - 1-3: Core identity facts (definition, persona, principles)
        - 4-6: Architecture facts (tiers, formulas, technical details)
        - 7-10: Operational details (latency budgets, filler audio, etc.)
    """

    key: str
    assertion: str
    contradiction_keywords: tuple[str, ...]
    response_template: str
    priority: int | bool
    vacuum_mode: bool = False
    response_on_return: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        """Validate fields after initialization."""
        # Convert list to tuple for frozen dataclass compatibility
        if isinstance(self.contradiction_keywords, list):
            object.__setattr__(
                self, "contradiction_keywords",
                tuple(self.contradiction_keywords),
            )
        _validate_sovereign_truth(
            self.key,
            self.assertion,
            list(self.contradiction_keywords),
            self.response_template,
            self.priority,
        )

    def __str__(self) -> str:
        """Return a human-readable representation."""
        return f"[P{self.priority}] {self.key}: {self.assertion}"

    def to_dict(self) -> dict:
        """
        Convert to dictionary for serialization.

        Returns:
            Dictionary representation of the SovereignTruth
        """
        d = {
            "key": self.key,
            "assertion": self.assertion,
            "contradiction_keywords": list(self.contradiction_keywords),
            "response_template": self.response_template,
            "priority": self.priority,
            "created_at": self.created_at.isoformat(),
        }
        if self.vacuum_mode:
            d["vacuum_mode"] = True
        if self.response_on_return is not None:
            d["response_on_return"] = self.response_on_return
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "SovereignTruth":
        """
        Create a SovereignTruth from a dictionary.

        Args:
            data: Dictionary with key, assertion, contradiction_keywords,
                  response_template, priority, and optional created_at

        Returns:
            New SovereignTruth instance
        """
        created_at = data.get("created_at")
        if created_at is not None:
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at)
        else:
            created_at = datetime.now()

        return cls(
            key=data["key"],
            assertion=data["assertion"],
            contradiction_keywords=tuple(data["contradiction_keywords"]),
            response_template=data["response_template"],
            priority=data["priority"],
            vacuum_mode=data.get("vacuum_mode", False),
            response_on_return=data.get("response_on_return"),
            created_at=created_at,
        )


# =============================================================================
# T077: Sovereign Truth Hash Validation (FR-008i, FR-008j, SC-014)
# =============================================================================

import hashlib
import json
import logging
import os
import re
import string
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_logger = logging.getLogger(__name__)


def validate_sovereign_truths_hash(
    filepath: str | Path,
    expected_hash: Optional[str] = None,
) -> str:
    """
    Compute SHA-256 of sovereign_truths.json and validate against expected hash.

    In production, expected_hash is read from Secret Manager secret
    ``sovereign-truths-hash``. Locally, the check is skipped when
    ``SKIP_HASH_VALIDATION=true`` is set in ``.env`` (FR-008i, FR-008j).

    Args:
        filepath: Path to data/sovereign_truths.json.
        expected_hash: SHA-256 hex digest to compare against.  When None the
            function attempts to read from Secret Manager (or skips if
            SKIP_HASH_VALIDATION is set).

    Returns:
        The computed SHA-256 hex digest.

    Raises:
        SovereignTruthIntegrityError: If hash does not match and validation
            is not bypassed.
        FileNotFoundError: If the file does not exist.
    """
    filepath = Path(filepath)
    actual_hash = hashlib.sha256(filepath.read_bytes()).hexdigest()

    # Local dev bypass
    skip = os.environ.get("SKIP_HASH_VALIDATION", "").lower() in ("true", "1", "yes")
    if skip:
        _logger.info(
            "Sovereign truths hash validation skipped (SKIP_HASH_VALIDATION=true). "
            "Hash: %s",
            actual_hash,
        )
        return actual_hash

    # Resolve expected hash
    if expected_hash is None:
        expected_hash = _read_hash_from_secret_manager()

    if expected_hash is None:
        _logger.warning(
            "No expected hash available (Secret Manager unreachable or not configured). "
            "Computed hash: %s",
            actual_hash,
        )
        return actual_hash

    if actual_hash != expected_hash:
        raise SovereignTruthIntegrityError(
            f"sovereign_truths.json integrity check failed. "
            f"Expected SHA-256: {expected_hash}, got: {actual_hash}. "
            f"The file may have been tampered with. Refusing to start."
        )

    _logger.info("Sovereign truths hash validated: %s", actual_hash)
    return actual_hash


def _read_hash_from_secret_manager() -> Optional[str]:
    """
    Attempt to read the expected hash from Google Secret Manager.

    Returns None if Secret Manager is unavailable (local dev without GCP).
    """
    try:
        from google.cloud import secretmanager  # type: ignore[import-untyped]

        client = secretmanager.SecretManagerServiceClient()
        project_id = os.environ.get("GCP_PROJECT_ID", os.environ.get("GOOGLE_CLOUD_PROJECT"))
        if not project_id:
            _logger.debug("No GCP project ID configured — skipping Secret Manager lookup")
            return None

        name = f"projects/{project_id}/secrets/sovereign-truths-hash/versions/latest"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("utf-8").strip()
    except Exception as e:
        _logger.debug("Secret Manager unavailable: %s", e)
        return None

# Minimum transcription confidence to allow Tier 4 to proceed (FR-008d).
# Below this value, skip the entire hard override and route to Tier 1-3.
MIN_TRANSCRIPTION_CONFIDENCE: float = 0.70

# Interrogative starters reduce confidence weight before gate one (FR-008f).
# A question form does not constitute a contradiction on its own.
_INTERROGATIVE_STARTERS = frozenset([
    "is", "are", "was", "were", "do", "does", "did", "have", "has", "had",
    "can", "could", "will", "would", "should", "may", "might", "must",
    "what", "why", "how", "when", "where", "who", "which", "whose", "whom",
])

_PUNCTUATION_STRIP = str.maketrans("", "", string.punctuation)

# Simple suffix rules for lightweight normalization (MVP — no NLTK dep)
_SUFFIX_RULES: List[Tuple[str, str]] = [
    ("n't", " not"),
    ("'re", " are"),
    ("'ve", " have"),
    ("'ll", " will"),
    ("'d",  " would"),
    ("'s",  ""),
]


class SovereignTruthCache:
    """
    LRU-cached Sovereign Truth storage with preload capability.

    Per Constitution Principle III (Integrity): The top 10 Sovereign Truths
    are cached locally for fast lookup. When user context contradicts
    a Sovereign Truth, the truth takes priority.

    Features:
    - LRU cache with maxsize=10 for fast repeated lookups
    - Preload from JSON file
    - Priority-based sorting
    - Contradiction detection support

    Usage:
        cache = SovereignTruthCache()
        cache.load_from_json("data/sovereign_truths.json")

        truth = cache.get("willow_definition")
        if truth:
            print(truth.assertion)
    """

    def __init__(self, maxsize: int = 10):
        """
        Initialize the cache.

        Args:
            maxsize: Maximum number of truths to cache (default 10)
        """
        self._truths: Dict[str, SovereignTruth] = {}
        self._maxsize = maxsize
        self._top_10_keys: List[str] = []
        self._embedding_service: Optional["EmbeddingService"] = None

    def load_from_json(self, filepath: str | Path) -> int:
        """
        Load Sovereign Truths from JSON file.

        Args:
            filepath: Path to sovereign_truths.json

        Returns:
            Number of truths loaded

        Raises:
            FileNotFoundError: If file doesn't exist
            json.JSONDecodeError: If file is invalid JSON
        """
        filepath = Path(filepath)

        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Accept both "sovereign_truths" (canonical) and "truths" (legacy alias)
        if isinstance(data, dict):
            truths = data.get("sovereign_truths") or data.get("truths") or data
        else:
            truths = data

        for truth_data in truths:
            truth = SovereignTruth.from_dict(truth_data)
            self._truths[truth.key] = truth

        # Sort by priority and cache top 10
        self._update_top_10()

        return len(self._truths)

    def init_embeddings(self) -> int:
        """Initialize vector embedding service for semantic fallback.

        Returns:
            Number of truths embedded, or 0 if unavailable.
        """
        from .embedding import EmbeddingService
        self._embedding_service = EmbeddingService()
        return self._embedding_service.preload(list(self._truths.values()))

    def _update_top_10(self) -> None:
        """Update the list of top 10 priority truth keys."""
        sorted_truths = sorted(
            self._truths.values(),
            key=lambda t: (0 if t.priority is True else t.priority)
        )
        self._top_10_keys = [t.key for t in sorted_truths[:self._maxsize]]

    def preload_top_10(self) -> List[SovereignTruth]:
        """
        Preload and return the top 10 highest priority truths.

        Returns:
            List of top 10 SovereignTruth objects sorted by priority
        """
        return [self._truths[key] for key in self._top_10_keys if key in self._truths]

    @lru_cache(maxsize=10)
    def get_cached(self, key: str) -> Optional[SovereignTruth]:
        """
        Get a truth by key with LRU caching.

        Args:
            key: The unique truth identifier

        Returns:
            SovereignTruth if found, None otherwise
        """
        return self._truths.get(key)

    def get(self, key: str) -> Optional[SovereignTruth]:
        """
        Get a truth by key (non-cached, for fresh lookups).

        Args:
            key: The unique truth identifier

        Returns:
            SovereignTruth if found, None otherwise
        """
        return self._truths.get(key)

    def add(self, truth: SovereignTruth) -> None:
        """
        Add a new Sovereign Truth to the cache.

        Args:
            truth: SovereignTruth to add
        """
        self._truths[truth.key] = truth
        self._update_top_10()
        # Clear LRU cache when truths change
        self.get_cached.cache_clear()

    def remove(self, key: str) -> bool:
        """
        Remove a truth by key.

        Args:
            key: The unique truth identifier

        Returns:
            True if removed, False if not found
        """
        if key in self._truths:
            del self._truths[key]
            self._update_top_10()
            self.get_cached.cache_clear()
            return True
        return False

    # ------------------------------------------------------------------
    # T013 — Steps 0-1: Input normalization + transcription confidence gate
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_input(text: str) -> str:
        """
        Step 0: Normalize user input for deterministic keyword matching.

        Operations (FR-008f):
        - Expand common contractions ("n't" → " not", etc.)
        - Lowercase
        - Strip punctuation
        - Collapse whitespace

        Not a full lemmatizer — MVP uses surface-form matching per FR-008a.
        """
        for suffix, expansion in _SUFFIX_RULES:
            text = text.replace(suffix, expansion)
        text = text.lower()
        text = text.translate(_PUNCTUATION_STRIP)
        text = " ".join(text.split())
        return text

    @staticmethod
    def _is_interrogative(normalized: str) -> bool:
        """
        Return True if input appears to be a question form (FR-008f).

        Interrogative inputs receive a reduced confidence weight, meaning
        a single-keyword question match will not confirm a contradiction.
        """
        first_word = normalized.split()[0] if normalized else ""
        return first_word in _INTERROGATIVE_STARTERS or normalized.endswith("?")

    def check_contradiction(
        self,
        user_input: str,
        transcription_confidence: float,
    ) -> Optional["SovereignTruth"]:
        """
        Entry point for the hard override layer — steps 0 and 1 only.

        Step 0 — Input normalization: lowercase, strip punctuation,
            expand contractions; detect interrogative form (FR-008f).
        Step 1 — Transcription confidence gate: if confidence below
            MIN_TRANSCRIPTION_CONFIDENCE, skip the override entirely
            and return None so routing falls through to Tier 1-3 (FR-008d).

        Gates 2 and 3 (keyword match + Tier 3 intent confirmation) are
        applied by the caller in T070. This method returns the best candidate
        truth for those gates to evaluate, or None to abort early.

        Args:
            user_input: Raw voice-transcribed user text.
            transcription_confidence: Float 0.0-1.0 from the ASR layer.

        Returns:
            Best-candidate SovereignTruth for downstream gate evaluation,
            or None if the confidence gate fails.
        """
        # Step 1 — Gate one: transcription confidence (FR-008d)
        if transcription_confidence < MIN_TRANSCRIPTION_CONFIDENCE:
            return None

        # Step 0 — Input normalization (FR-008f)
        normalized = self._normalize_input(user_input)
        is_question = self._is_interrogative(normalized)

        # Find candidate truths by keyword overlap.
        # is_question is consumed by T070 when it applies stricter gate-two
        # matching — interrogative inputs require 2+ keyword matches regardless.
        candidates = self._find_candidates(normalized)
        if not candidates:
            return None

        # Return highest-priority candidate for T070 to gate further
        return min(candidates, key=lambda t: t.priority)

    def _find_candidates(self, normalized: str) -> List[SovereignTruth]:
        """
        Return truths whose contradiction_keywords appear in normalized input.

        Single-keyword matches are included — T070 enforces the 2-keyword
        minimum and handles interrogative strictness.

        Falls back to vector embedding similarity when keyword matching
        finds no candidates and EmbeddingService is available.
        """
        results = []
        
        # Pass 1: Check only truths where "priority": True against user input.
        for truth in self._truths.values():
            if truth.priority is True:
                for kw in truth.contradiction_keywords:
                    kw_norm = self._normalize_input(kw)
                    if kw_norm in normalized:
                        results.append(truth)
                        break

        # Pass 2: Only if Pass 1 finds no match, check remaining truths.
        if not results:
            for truth in self._truths.values():
                if truth.priority is not True:
                    for kw in truth.contradiction_keywords:
                        kw_norm = self._normalize_input(kw)
                        if kw_norm in normalized:
                            results.append(truth)
                            break

        # Semantic fallback: if no keyword matches, try vector similarity
        if not results and self._embedding_service:
            similar = self._embedding_service.find_similar(
                normalized, list(self._truths.values()), top_k=2
            )
            for key, score in similar:
                truth = self._truths.get(key)
                if truth:
                    _logger.info(
                        "Semantic fallback matched truth '%s' (cosine=%.3f)",
                        key, score,
                    )
                    results.append(truth)

        return results

    # ------------------------------------------------------------------
    # T070 — Gate two (keyword count) + gate three (Tier 3 intent)
    # ------------------------------------------------------------------

    def run_gate_two(
        self,
        truth: "SovereignTruth",
        user_input: str,
        weighted_average_m: float,
    ) -> bool:
        """
        Gate two: minimum 2-keyword match requirement (FR-008c).

        Rules:
        - Interrogative input: always require 2+ keyword matches.
        - Non-interrogative: 2+ required UNLESS residual weighted_average_m
          is already negative (one match sufficient in established hostile
          context, but single-turn contradiction still cannot fire Tier 4
          alone without a confirming second turn — that is enforced upstream).

        Args:
            truth: Candidate SovereignTruth from check_contradiction.
            user_input: Raw user text (will be normalized internally).
            weighted_average_m: Residual Plot weighted average. Negative
                values allow single-match exception for non-interrogative input.

        Returns:
            True if the gate passes, False to abort Tier 4.
        """
        normalized = self._normalize_input(user_input)
        is_question = self._is_interrogative(normalized)

        match_count = sum(
            1
            for kw in truth.contradiction_keywords
            if self._normalize_input(kw) in normalized
        )

        min_matches = 2 if (is_question or weighted_average_m >= 0) else 1
        return match_count >= min_matches

    async def run_gate_three(
        self,
        tier3_intent_coro,
        cutoff_seconds: float = 1.5,
    ) -> bool:
        """
        Gate three: Tier 3 intent must return 'contradicting' @ ≥0.85 (FR-022).

        Runs Tier 3 intent classification as a parallel pre-check. If the
        result is not ready within cutoff_seconds, defaults to conservative
        path (hold Tier 4, return False).

        Args:
            tier3_intent_coro: Awaitable returning (intent: str, confidence: float).
            cutoff_seconds: Maximum wait before conservative default (default 1.5s).

        Returns:
            True if intent == 'contradicting' and confidence >= 0.85.
        """
        import asyncio

        REQUIRED_INTENT = "contradicting"
        REQUIRED_CONFIDENCE = 0.85

        try:
            intent, confidence = await asyncio.wait_for(
                tier3_intent_coro, timeout=cutoff_seconds
            )
            return intent == REQUIRED_INTENT and confidence >= REQUIRED_CONFIDENCE
        except asyncio.TimeoutError:
            # Conservative default: hold Tier 4 (FR-022)
            return False

    # ------------------------------------------------------------------
    # T071 — Hard exit (cancel active Gemini coroutine) (FR-008g)
    # ------------------------------------------------------------------

    @staticmethod
    async def hard_exit(active_task) -> None:
        """
        Step 4: Cancel active Gemini generation coroutine before constructing
        the programmatic Tier 4 response (FR-008g).

        A return guard MUST follow this call at the call site — do not
        continue into normal response flow after hard_exit.

        Args:
            active_task: asyncio.Task wrapping the active Gemini generation
                coroutine, or None if no task is running.
        """
        import asyncio

        if active_task is not None and not active_task.done():
            active_task.cancel()
            try:
                await active_task
            except asyncio.CancelledError:
                pass  # Expected — cancellation confirmed

    # ------------------------------------------------------------------
    # T072 — Response construction from response_template (FR-008h)
    # ------------------------------------------------------------------

    @staticmethod
    def build_response(truth: "SovereignTruth") -> str:
        """
        Step 5: Construct Tier 4 response from the SovereignTruth data.

        Templates are data, not code. Zero LLM involvement. The only
        interpolation allowed is inserting the verbatim assertion string
        where the placeholder {assertion} appears (FR-008h).

        Vacuum mode entries ([VACUUM_MODE] sentinel) must NOT reach this
        method — caller MUST check truth.vacuum_mode first (T035).

        Args:
            truth: The matching SovereignTruth.

        Returns:
            Rendered response string ready for audio pipeline injection.
        """
        return truth.response_template.format(assertion=truth.assertion)

    # ------------------------------------------------------------------
    # T073 — Synthetic turn injection (FR-008e)
    # T074 — audio_started flag (FR-022)
    # Both are consumed by the orchestration layer (src/main.py / T035).
    # Helpers here produce the data; main.py applies them to SessionState.
    # ------------------------------------------------------------------

    @staticmethod
    def build_synthetic_turn(truth: "SovereignTruth") -> dict:
        """
        Step 6: Build the synthetic assistant turn for conversation history.

        Uses an f-string with exact verbatim assertion values — not
        paraphrased (FR-008e). Returns a dict the orchestration layer
        appends to the conversation history before the next user turn.

        Args:
            truth: The SovereignTruth whose assertion was just delivered.

        Returns:
            Dict with role='assistant' and content set to the verbatim
            assertion (not the response_template).
        """
        return {
            "role": "assistant",
            "content": f"{truth.assertion}",
        }

    def find_by_keyword(self, keyword: str) -> List[SovereignTruth]:
        """
        Find truths whose contradiction_keywords contain the given keyword.

        Uses the dedicated contradiction_keywords field for deterministic
        pattern matching — not assertion text search (FR-008a).

        Args:
            keyword: Keyword to search for (case-insensitive)

        Returns:
            List of matching SovereignTruth objects
        """
        keyword_lower = keyword.lower()
        return [
            truth for truth in self._truths.values()
            if keyword_lower in (kw.lower() for kw in truth.contradiction_keywords)
        ]

    def get_all(self) -> List[SovereignTruth]:
        """
        Get all stored truths.

        Returns:
            List of all SovereignTruth objects
        """
        return list(self._truths.values())

    def get_by_priority(self, min_priority: int = 1, max_priority: int = 10) -> List[SovereignTruth]:
        """
        Get truths within a priority range.

        Args:
            min_priority: Minimum priority (inclusive, default 1)
            max_priority: Maximum priority (inclusive, default 10)

        Returns:
            List of SovereignTruth objects in priority range
        """
        return [
            truth for truth in self._truths.values()
            if min_priority <= truth.priority <= max_priority
        ]

    @property
    def count(self) -> int:
        """Return total number of truths stored."""
        return len(self._truths)

    def clear_cache(self) -> None:
        """Clear the LRU cache."""
        self.get_cached.cache_clear()

    def to_dict(self) -> dict:
        """
        Convert cache to dictionary for serialization.

        Returns:
            Dictionary with truths list
        """
        return {
            "truths": [t.to_dict() for t in self._truths.values()],
            "top_10_keys": self._top_10_keys
        }
