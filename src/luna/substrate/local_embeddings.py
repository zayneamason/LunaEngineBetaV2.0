"""
Local Embeddings using MiniLM
=============================

Free, local semantic embeddings using sentence-transformers.
No API costs, ~50ms per embedding on CPU.

Model: all-MiniLM-L6-v2 (384 dimensions)

Usage:
    embeddings = LocalEmbeddings()
    vector = embeddings.encode("search query")
    vectors = embeddings.encode_batch(["text1", "text2"])
"""

from __future__ import annotations

import logging
from typing import Optional
import threading

logger = logging.getLogger(__name__)

# Model configuration
MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

# Singleton instance and lock
_instance: Optional["LocalEmbeddings"] = None
_lock = threading.Lock()


def get_embeddings() -> "LocalEmbeddings":
    """
    Get the singleton LocalEmbeddings instance.

    Thread-safe lazy initialization.
    """
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = LocalEmbeddings()
    return _instance


class LocalEmbeddings:
    """
    Local embedding generator using sentence-transformers MiniLM.

    Features:
    - 384-dimensional embeddings
    - ~50ms per embedding on CPU
    - No API costs
    - Thread-safe singleton pattern

    The model is loaded lazily on first use to avoid startup overhead.
    """

    def __init__(self):
        """Initialize the embeddings wrapper (model loaded lazily)."""
        self._model = None
        self._load_lock = threading.Lock()
        self.dim = EMBEDDING_DIM
        self.model_name = MODEL_NAME
        logger.debug(f"LocalEmbeddings initialized (model will load on first use)")

    def _load_model(self) -> None:
        """Load the sentence-transformers model (lazy, thread-safe)."""
        if self._model is not None:
            return

        with self._load_lock:
            if self._model is not None:
                return

            try:
                from sentence_transformers import SentenceTransformer
                logger.info(f"Loading embedding model: {MODEL_NAME}")
                self._model = SentenceTransformer(MODEL_NAME)
                logger.info(f"Embedding model loaded successfully ({EMBEDDING_DIM} dimensions)")
            except ImportError:
                raise RuntimeError(
                    "sentence-transformers not installed. "
                    "Run: pip install sentence-transformers"
                )
            except Exception as e:
                raise RuntimeError(f"Failed to load embedding model: {e}")

    @property
    def model(self):
        """Get the model, loading it if necessary."""
        if self._model is None:
            self._load_model()
        return self._model

    def encode(self, text: str, normalize: bool = True) -> list[float]:
        """
        Generate embedding for a single text.

        Args:
            text: The text to embed
            normalize: Whether to L2-normalize the embedding (default True)

        Returns:
            384-dimensional embedding vector
        """
        if not text or not text.strip():
            # Return zero vector for empty text
            return [0.0] * self.dim

        embedding = self.model.encode(
            text,
            normalize_embeddings=normalize,
            show_progress_bar=False,
        )
        return embedding.tolist()

    def encode_batch(
        self,
        texts: list[str],
        normalize: bool = True,
        batch_size: int = 32,
        show_progress: bool = False,
    ) -> list[list[float]]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed
            normalize: Whether to L2-normalize embeddings (default True)
            batch_size: Batch size for encoding (default 32)
            show_progress: Whether to show progress bar (default False)

        Returns:
            List of 384-dimensional embedding vectors
        """
        if not texts:
            return []

        # Handle empty strings
        non_empty_indices = []
        non_empty_texts = []
        for i, text in enumerate(texts):
            if text and text.strip():
                non_empty_indices.append(i)
                non_empty_texts.append(text)

        # Initialize results with zero vectors
        results = [[0.0] * self.dim for _ in texts]

        if non_empty_texts:
            embeddings = self.model.encode(
                non_empty_texts,
                normalize_embeddings=normalize,
                batch_size=batch_size,
                show_progress_bar=show_progress,
            )

            # Place embeddings back in correct positions
            for idx, embedding in zip(non_empty_indices, embeddings):
                results[idx] = embedding.tolist()

        return results

    def similarity(self, text1: str, text2: str) -> float:
        """
        Compute cosine similarity between two texts.

        Args:
            text1: First text
            text2: Second text

        Returns:
            Cosine similarity score (0-1 for normalized vectors)
        """
        emb1 = self.encode(text1)
        emb2 = self.encode(text2)

        # Cosine similarity (vectors are already normalized)
        dot_product = sum(a * b for a, b in zip(emb1, emb2))
        return dot_product

    def is_loaded(self) -> bool:
        """Check if the model is currently loaded."""
        return self._model is not None

    def preload(self) -> None:
        """
        Explicitly load the model.

        Call this during startup to avoid first-query latency.
        """
        self._load_model()
