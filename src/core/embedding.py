

"""
Vector embedding service for semantic contradiction detection (FR-012).

Uses Gemini's gemini-embedding-001 model to compute cosine similarity
between user input and sovereign truth assertions. Acts as a fallback
when keyword-based matching finds no candidates.
"""

import hashlib
import logging
import math
import os
import pickle
import concurrent.futures
from functools import lru_cache
from pathlib import Path
from typing import Optional

from google import genai

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "gemini-embedding-001"
SIMILARITY_THRESHOLD = 0.45       # minimum cosine similarity for sovereign truths
TACTIC_SIMILARITY_THRESHOLD = 0.55  # higher bar for tactics — fuzzier concept space
EMBEDDING_TIMEOUT_SEC = 0.80      # 800ms timeout for semantic fallback

# Disk cache path — persists embeddings across server restarts to avoid
# re-calling gemini-embedding-001 every time Uvicorn boots.
_EMBEDDING_CACHE_PATH = Path(".cache/truth_embeddings.pkl")


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class EmbeddingService:
    """Pre-computes and caches embeddings for sovereign truth assertions."""

    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self._client = genai.Client(api_key=api_key) if api_key else None
        self._truth_embeddings: dict[str, list[float]] = {}  # key -> embedding
        self._tactic_embeddings: dict[str, list[float]] = {}  # tactic_key -> embedding
        self._ready = False
        # Create a thread pool for blocking API calls to allow timeouts
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)

    def preload(self, truths: list) -> int:
        """Embed all sovereign truth assertions in a batch.

        Checks a local disk cache first (keyed by content hash) to avoid
        re-calling gemini-embedding-001 on every server restart.

        Args:
            truths: List of SovereignTruth objects with .key and .assertion

        Returns:
            Number of truths embedded, or 0 if service unavailable.
        """
        if not self._client:
            logger.warning("EmbeddingService: no API key — semantic matching disabled")
            return 0

        texts = [t.assertion for t in truths]
        keys = [t.key for t in truths]
        if not texts:
            return 0

        # Build a content hash to detect changes in sovereign_truths.json
        content_hash = hashlib.md5("".join(texts).encode()).hexdigest()

        # Try loading from disk cache
        if _EMBEDDING_CACHE_PATH.exists():
            try:
                with open(_EMBEDDING_CACHE_PATH, "rb") as f:
                    cached = pickle.load(f)
                if cached.get("hash") == content_hash:
                    self._truth_embeddings = cached["embeddings"]
                    self._ready = True
                    logger.info(
                        "EmbeddingService: loaded %d truth embeddings from disk cache",
                        len(self._truth_embeddings),
                    )
                    return len(self._truth_embeddings)
                logger.info("EmbeddingService: disk cache stale (truths changed) — re-embedding")
            except Exception as e:
                logger.warning("EmbeddingService: disk cache load failed — %s", e)

        try:
            result = self._client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=texts,
            )
            for key, emb in zip(keys, result.embeddings):
                self._truth_embeddings[key] = emb.values
            self._ready = True
            logger.info("EmbeddingService: preloaded %d truth embeddings via API", len(keys))

            # Persist to disk so next boot skips the API call
            try:
                _EMBEDDING_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
                with open(_EMBEDDING_CACHE_PATH, "wb") as f:
                    pickle.dump(
                        {"hash": content_hash, "embeddings": self._truth_embeddings}, f
                    )
                logger.info("EmbeddingService: saved embeddings to disk cache")
            except Exception as e:
                logger.warning("EmbeddingService: disk cache save failed — %s", e)

            return len(keys)
        except Exception as e:
            logger.error("EmbeddingService: preload failed — %s", e)
            return 0

    @lru_cache(maxsize=128)
    def _embed_user_input(self, user_input: str) -> list[float] | None:
        """Embed user_input and cache the result (Quick Win #3).

        Repeated identical phrases (e.g. user rephrases the same question)
        hit the cache instead of making a fresh API call to gemini-embedding-001.
        Cache holds the 128 most recent unique inputs.
        """
        try:
            future = self._executor.submit(
                self._client.models.embed_content,
                model=EMBEDDING_MODEL,
                contents=[user_input]
            )
            result = future.result(timeout=EMBEDDING_TIMEOUT_SEC)
            return result.embeddings[0].values
        except concurrent.futures.TimeoutError:
            logger.warning("EmbeddingService: embed timed out (>%.2fs)", EMBEDDING_TIMEOUT_SEC)
            return None
        except Exception as e:
            logger.debug("EmbeddingService: embed failed — %s", e)
            return None

    def find_similar(
        self, user_input: str, truths: list, top_k: int = 3
    ) -> list[tuple[str, float]]:
        """Find truths semantically similar to user input.

        Args:
            user_input: Raw user text.
            truths: List of SovereignTruth objects to search.
            top_k: Max results to return.

        Returns:
            List of (truth_key, similarity_score) tuples above threshold,
            sorted by similarity descending. Empty if service unavailable.
        """
        if not self._ready or not self._client:
            return []

        input_emb = self._embed_user_input(user_input)
        if input_emb is None:
            return []

        scores = []
        for truth in truths:
            truth_emb = self._truth_embeddings.get(truth.key)
            if truth_emb is None:
                continue
            sim = _cosine_similarity(input_emb, truth_emb)
            if sim >= SIMILARITY_THRESHOLD:
                scores.append((truth.key, sim))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def preload_tactics(self, descriptions: dict[str, str]) -> int:
        """Embed tactic descriptions for Tier 3 semantic fallback.

        Args:
            descriptions: Dict mapping tactic_key to its natural-language description
                (sourced from willow_rules.json description fields).

        Returns:
            Number of tactic embeddings computed, or 0 if service unavailable.
        """
        if not self._client or not descriptions:
            return 0

        keys = list(descriptions.keys())
        texts = [descriptions[k] for k in keys]

        try:
            result = self._client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=texts,
            )
            for key, emb in zip(keys, result.embeddings):
                self._tactic_embeddings[key] = emb.values
            logger.info("EmbeddingService: preloaded %d tactic embeddings", len(keys))
            return len(keys)
        except Exception as e:
            logger.error("EmbeddingService: tactic preload failed — %s", e)
            return 0

    def find_similar_tactic(
        self, user_input: str, top_k: int = 1
    ) -> list[tuple[str, float]]:
        """Find tactic descriptions semantically similar to user input.

        Args:
            user_input: Raw user text.
            top_k: Max results to return.

        Returns:
            List of (tactic_key, similarity_score) tuples above
            TACTIC_SIMILARITY_THRESHOLD, sorted by similarity descending.
            Empty if service unavailable or no tactics preloaded.
        """
        if not self._tactic_embeddings or not self._client:
            return []

        input_emb = self._embed_user_input(user_input)
        if input_emb is None:
            return []

        scores = []
        for tactic_key, tactic_emb in self._tactic_embeddings.items():
            sim = _cosine_similarity(input_emb, tactic_emb)
            if sim >= TACTIC_SIMILARITY_THRESHOLD:
                scores.append((tactic_key, sim))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]
