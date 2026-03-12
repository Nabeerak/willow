"""
Vector embedding service for semantic contradiction detection (FR-012).

Uses Gemini's text-embedding-004 model to compute cosine similarity
between user input and sovereign truth assertions. Acts as a fallback
when keyword-based matching finds no candidates.
"""

import logging
import math
import os
from typing import Optional

from google import genai

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-004"
SIMILARITY_THRESHOLD = 0.45  # minimum cosine similarity to consider a match


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
        self._ready = False

    def preload(self, truths: list) -> int:
        """Embed all sovereign truth assertions in a batch.

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

        try:
            result = self._client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=texts,
            )
            for key, emb in zip(keys, result.embeddings):
                self._truth_embeddings[key] = emb.values
            self._ready = True
            logger.info("EmbeddingService: preloaded %d truth embeddings", len(keys))
            return len(keys)
        except Exception as e:
            logger.error("EmbeddingService: preload failed — %s", e)
            return 0

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

        try:
            result = self._client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=[user_input],
            )
            input_emb = result.embeddings[0].values
        except Exception as e:
            logger.debug("EmbeddingService: embed failed — %s", e)
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
