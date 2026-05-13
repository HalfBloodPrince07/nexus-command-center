"""Local cross-encoder reranker using BAAI/bge-reranker-v2-m3.

Usage:
    reranker = CrossEncoderReranker(
        model_id=settings.HF_RERANKER_MODEL_ID,
        cache_dir=str(settings.HF_RERANKER_CACHE_DIR),
    )
    # Returns indices of top_k documents sorted by relevance descending
    top_indices = reranker.rerank(query, documents, top_k=5)
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class CrossEncoderReranker:
    """Local cross-encoder reranker — no LM Studio or network calls required.

    Uses ``BAAI/bge-reranker-v2-m3`` (AutoModelForSequenceClassification).
    The model is downloaded once on first call and cached locally.

    Pairs (query, passage) are concatenated by the tokenizer using the
    standard two-sequence input format; the model outputs a single logit
    per pair which is passed through sigmoid to get a relevance probability.

    Args:
        model_id:   HuggingFace repo id (default: ``BAAI/bge-reranker-v2-m3``).
        cache_dir:  Local directory to cache downloaded model weights.
        batch_size: Pairs per forward pass (default 32).
        max_length: Token truncation limit (default 512).
    """

    def __init__(
        self,
        model_id: str,
        cache_dir: str | None = None,
        batch_size: int = 32,
        max_length: int = 512,
    ) -> None:
        self._model_id = model_id
        self._cache_dir = cache_dir
        self._batch_size = batch_size
        self._max_length = max_length
        self._tokenizer: Any = None
        self._model: Any = None
        self._device: str | None = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Lazy-load the tokenizer and model on first call."""
        if self._model is not None:
            return

        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError(
                "torch and transformers are required for cross-encoder reranking. "
                "Run: conda run -n Command pip install torch transformers"
            ) from exc

        logger.info("Loading cross-encoder reranker: %s", self._model_id)

        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info("Reranker device: %s", self._device)

        self._tokenizer = AutoTokenizer.from_pretrained(
            self._model_id,
            cache_dir=self._cache_dir,
        )
        self._model = AutoModelForSequenceClassification.from_pretrained(
            self._model_id,
            cache_dir=self._cache_dir,
        ).to(self._device)
        self._model.eval()

        logger.info(
            "Cross-encoder reranker ready — device=%s  model=%s",
            self._device,
            self._model_id,
        )

    def _score_pairs(self, pairs: list[tuple[str, str]]) -> list[float]:
        """Score a list of (query, passage) pairs.

        Returns a list of relevance probabilities in [0, 1].
        """
        import torch

        self._load()
        all_scores: list[float] = []

        for batch_start in range(0, len(pairs), self._batch_size):
            batch = pairs[batch_start : batch_start + self._batch_size]

            # Tokenize as two-sequence pairs: [query, passage]
            encoded = self._tokenizer(
                [list(pair) for pair in batch],
                padding=True,
                truncation=True,
                max_length=self._max_length,
                return_tensors="pt",
            ).to(self._device)

            with torch.no_grad():
                logits = self._model(**encoded).logits.squeeze(-1)

            probs = torch.sigmoid(logits).cpu().tolist()
            # squeeze may return a scalar if batch_size == 1
            if isinstance(probs, float):
                probs = [probs]
            all_scores.extend(probs)

        return all_scores

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int = 5,
    ) -> list[int]:
        """Return the indices of the top_k most relevant documents.

        The returned list is sorted by relevance descending (index 0 = best).
        If the model fails to load or score, falls back to returning
        ``list(range(min(top_k, len(documents))))``.

        Args:
            query:     The search query string.
            documents: Candidate passages to score.
            top_k:     Number of top results to return.

        Returns:
            List of original indices (into ``documents``) sorted best-first.
        """
        if not documents:
            return []

        top_k = min(top_k, len(documents))

        try:
            pairs = [(query, doc[:2000]) for doc in documents]
            scores = self._score_pairs(pairs)
            ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
            return ranked[:top_k]
        except Exception as exc:
            logger.warning("CrossEncoderReranker.rerank failed (%s). Returning original order.", exc)
            return list(range(top_k))

    def rerank_with_scores(
        self,
        query: str,
        documents: list[str],
    ) -> list[tuple[int, float]]:
        """Return (original_index, score) pairs sorted by score descending.

        Useful when the caller needs to know the actual relevance probabilities.

        Args:
            query:     The search query string.
            documents: Candidate passages to score.

        Returns:
            List of (index, probability) tuples sorted best-first.
        """
        if not documents:
            return []

        try:
            pairs = [(query, doc[:2000]) for doc in documents]
            scores = self._score_pairs(pairs)
            ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
            return ranked
        except Exception as exc:
            logger.warning("CrossEncoderReranker.rerank_with_scores failed (%s).", exc)
            return list(enumerate([0.0] * len(documents)))


# Module-level singleton — lazy-loaded on first use
from backend.config import settings as _settings

reranker = CrossEncoderReranker(
    model_id=_settings.HF_RERANKER_MODEL_ID,
    cache_dir=str(_settings.HF_RERANKER_CACHE_DIR),
    batch_size=32,
    max_length=512,
)
