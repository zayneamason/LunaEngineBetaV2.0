"""
Real Embedding Integration for Resolver

Provides production embedding functions for:
- Node deduplication (semantic similarity matching)
- Cross-conversation edge discovery (find related concepts)

Uses sentence-transformers all-MiniLM-L6-v2 (384 dimensions) for local inference.
"""

import asyncio
from typing import List, Optional
from sentence_transformers import SentenceTransformer


class SentenceTransformerEmbeddings:
    """Sentence-transformers embedding provider for semantic similarity."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize sentence-transformers embeddings.

        Args:
            model_name: Model to use (default: all-MiniLM-L6-v2, 384 dims)
        """
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)
        self.dimension = self.model.get_sentence_embedding_dimension()

        # Track usage for monitoring
        self.total_texts = 0
        self.total_requests = 0

    async def __call__(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a batch of texts.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors (each is a list of floats)
        """
        if not texts:
            return []

        # Run encoding in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None,
            self._encode_batch,
            texts
        )

        # Track usage
        self.total_texts += len(texts)
        self.total_requests += 1

        return embeddings

    def _encode_batch(self, texts: List[str]) -> List[List[float]]:
        """Synchronous encoding (runs in thread pool)."""
        # Convert to numpy, then to list of lists
        embeddings_np = self.model.encode(
            texts,
            convert_to_numpy=True,
            show_progress_bar=False
        )
        return embeddings_np.tolist()

    def get_stats(self) -> dict:
        """Get usage statistics."""
        return {
            "total_texts": self.total_texts,
            "total_requests": self.total_requests,
            "estimated_cost_usd": 0.0,  # Local inference is free
        }
