"""
Luna Engine Vector Embeddings
=============================

Semantic search using sqlite-vec for memory retrieval.

sqlite-vec provides fast vector similarity search directly in SQLite,
enabling semantic memory retrieval without external dependencies.

Usage:
    embeddings = EmbeddingStore(db)
    await embeddings.initialize()

    # Store embedding
    await embeddings.store("node123", vector)

    # Semantic search
    similar = await embeddings.search(query_vector, limit=10)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional
import struct

if TYPE_CHECKING:
    from .database import MemoryDatabase

logger = logging.getLogger(__name__)

# Embedding dimensions for different models
EMBEDDING_DIMS = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "voyage-2": 1024,
    "local-minilm": 384,
}

DEFAULT_DIM = 384  # Local MiniLM (all-MiniLM-L6-v2)


def vector_to_blob(vector: list[float]) -> bytes:
    """Convert a float vector to sqlite-vec compatible blob format."""
    return struct.pack(f'{len(vector)}f', *vector)


def blob_to_vector(blob: bytes) -> list[float]:
    """Convert a sqlite-vec blob back to a float vector."""
    n_floats = len(blob) // 4  # 4 bytes per float
    return list(struct.unpack(f'{n_floats}f', blob))


class EmbeddingStore:
    """
    Vector embedding storage using sqlite-vec.

    Provides semantic search capabilities for Luna's memory system.
    Uses sqlite-vec virtual table for efficient similarity search.
    """

    def __init__(
        self,
        db: "MemoryDatabase",
        dim: int = DEFAULT_DIM,
        table_name: str = "memory_embeddings",
    ):
        """
        Initialize the embedding store.

        Args:
            db: The underlying MemoryDatabase instance
            dim: Embedding dimension (default 1536 for OpenAI)
            table_name: Name of the virtual table
        """
        self.db = db
        self.dim = dim
        self.table_name = table_name
        self._initialized = False
        self._vec_loaded = False

    async def initialize(self) -> bool:
        """
        Initialize sqlite-vec and create the embeddings table.

        Returns:
            True if sqlite-vec was loaded successfully, False otherwise
        """
        if self._initialized:
            return self._vec_loaded

        try:
            # Load sqlite-vec extension
            await self._load_extension()

            # Create virtual table for embeddings
            await self.db.execute(f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS {self.table_name} USING vec0(
                    node_id TEXT PRIMARY KEY,
                    embedding FLOAT[{self.dim}]
                )
            """)

            self._initialized = True
            self._vec_loaded = True
            logger.info(f"EmbeddingStore initialized with {self.dim}-dim vectors")
            return True

        except Exception as e:
            from luna.diagnostics.maturity import compiled_debug
            compiled_debug(logger, "sqlite-vec not available: %s", e)
            # Try pure-Python fallback for vector search
            try:
                from luna.substrate.vec_fallback import FallbackVecStore
                raw_conn = self.db._connection._conn if hasattr(self.db, '_connection') and hasattr(self.db._connection, '_conn') else None
                if raw_conn:
                    self._fallback = FallbackVecStore(raw_conn, f"{self.table_name}_fallback", self.dim)
                    self._fallback.ensure_table()
                    compiled_debug(logger, "Using pure-Python vector fallback for memory embeddings")
                else:
                    self._fallback = None
                    compiled_debug(logger, "Semantic search will not be available. Using keyword search fallback.")
            except Exception:
                self._fallback = None
                compiled_debug(logger, "Semantic search will not be available. Using keyword search fallback.")
            self._initialized = True
            self._vec_loaded = False
            return False

    async def _load_extension(self) -> None:
        """Load the sqlite-vec extension."""
        try:
            import sqlite_vec

            conn = self.db._connection
            if conn is None:
                raise RuntimeError("Database not connected")

            # Enable extension loading
            await conn.execute("SELECT 1")  # Ensure connection is active

            # Load sqlite-vec via the Python binding
            # sqlite-vec provides a loadable extension path
            await conn.enable_load_extension(True)

            # Get the extension path from the sqlite_vec module
            ext_path = sqlite_vec.loadable_path()
            await conn.execute(f"SELECT load_extension(?)", (ext_path,))

            await conn.enable_load_extension(False)

            logger.info("sqlite-vec extension loaded successfully")

        except ImportError:
            raise RuntimeError("sqlite-vec package not installed. Run: pip install sqlite-vec")
        except Exception as e:
            raise RuntimeError(f"Failed to load sqlite-vec extension: {e}")

    @property
    def is_available(self) -> bool:
        """Check if vector search is available (native or fallback)."""
        return self._vec_loaded or (hasattr(self, '_fallback') and self._fallback is not None and self._fallback.is_available)

    async def store(self, node_id: str, embedding: list[float]) -> bool:
        """
        Store an embedding for a memory node.

        Args:
            node_id: The ID of the memory node
            embedding: The embedding vector

        Returns:
            True if stored successfully
        """
        if not self._vec_loaded:
            # Try fallback store
            fb = getattr(self, '_fallback', None)
            if fb and fb.is_available:
                return fb.store(node_id, embedding)
            logger.debug("sqlite-vec not available, skipping embedding storage")
            return False

        if len(embedding) != self.dim:
            raise ValueError(f"Embedding dimension mismatch: got {len(embedding)}, expected {self.dim}")

        # Convert to blob format
        blob = vector_to_blob(embedding)

        # Upsert into vec0 table
        await self.db.execute(f"""
            INSERT OR REPLACE INTO {self.table_name} (node_id, embedding)
            VALUES (?, ?)
        """, (node_id, blob))

        logger.debug(f"Stored embedding for node {node_id}")
        return True

    async def delete(self, node_id: str) -> bool:
        """
        Delete an embedding for a memory node.

        Args:
            node_id: The ID of the memory node

        Returns:
            True if deleted successfully
        """
        if not self._vec_loaded:
            fb = getattr(self, '_fallback', None)
            if fb and fb.is_available:
                return fb.delete(node_id)
            return False

        result = await self.db.execute(f"""
            DELETE FROM {self.table_name} WHERE node_id = ?
        """, (node_id,))

        return result.rowcount > 0

    async def search(
        self,
        query_embedding: list[float],
        limit: int = 10,
        min_similarity: float = 0.0,
    ) -> list[tuple[str, float]]:
        """
        Search for similar embeddings using cosine similarity.

        Args:
            query_embedding: The query embedding vector
            limit: Maximum number of results
            min_similarity: Minimum similarity threshold (0-1)

        Returns:
            List of (node_id, similarity_score) tuples, sorted by similarity
        """
        if not self._vec_loaded:
            # Try fallback store
            fb = getattr(self, '_fallback', None)
            if fb and fb.is_available:
                return fb.search(query_embedding, limit, min_similarity)
            logger.debug("sqlite-vec not available, returning empty results")
            return []

        if len(query_embedding) != self.dim:
            raise ValueError(f"Query embedding dimension mismatch: got {len(query_embedding)}, expected {self.dim}")

        # Convert query to blob
        query_blob = vector_to_blob(query_embedding)

        # sqlite-vec uses vec_distance_cosine for similarity
        # Lower distance = more similar, so we convert to similarity
        rows = await self.db.fetchall(f"""
            SELECT
                node_id,
                1 - vec_distance_cosine(embedding, ?) AS similarity
            FROM {self.table_name}
            WHERE 1 - vec_distance_cosine(embedding, ?) >= ?
            ORDER BY vec_distance_cosine(embedding, ?) ASC
            LIMIT ?
        """, (query_blob, query_blob, min_similarity, query_blob, limit))

        return [(row[0], row[1]) for row in rows]

    async def get_embedding(self, node_id: str) -> Optional[list[float]]:
        """
        Retrieve the embedding for a memory node.

        Args:
            node_id: The ID of the memory node

        Returns:
            The embedding vector, or None if not found
        """
        if not self._vec_loaded:
            return None

        row = await self.db.fetchone(f"""
            SELECT embedding FROM {self.table_name} WHERE node_id = ?
        """, (node_id,))

        if row is None:
            return None

        return blob_to_vector(row[0])

    async def count(self) -> int:
        """Get the total number of stored embeddings."""
        if not self._vec_loaded:
            return 0

        row = await self.db.fetchone(f"SELECT COUNT(*) FROM {self.table_name}")
        return row[0] if row else 0

    async def clear(self) -> int:
        """
        Clear all embeddings.

        Returns:
            Number of embeddings deleted
        """
        if not self._vec_loaded:
            return 0

        count = await self.count()
        await self.db.execute(f"DELETE FROM {self.table_name}")
        logger.warning(f"Cleared {count} embeddings from {self.table_name}")
        return count


class EmbeddingGenerator:
    """
    Generate embeddings using various models.

    Supports:
    - local-minilm: Free local embeddings (384 dims, ~50ms) - DEFAULT
    - OpenAI text-embedding-3-small/large (1536/3072 dims, costs money)
    """

    def __init__(self, model: str = "local-minilm"):
        """
        Initialize the embedding generator.

        Args:
            model: The embedding model to use (default: local-minilm)
        """
        self.model = model
        self.dim = EMBEDDING_DIMS.get(model, DEFAULT_DIM)
        self._client = None
        self._local_embeddings = None

    @property
    def client(self):
        """Lazy init OpenAI client (only for OpenAI models)."""
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI()
            except ImportError:
                raise RuntimeError("openai package not installed. Run: pip install openai")
        return self._client

    @property
    def local_embeddings(self):
        """Lazy init local embeddings (for local-minilm model)."""
        if self._local_embeddings is None:
            from .local_embeddings import get_embeddings
            self._local_embeddings = get_embeddings()
        return self._local_embeddings

    async def generate(self, text: str) -> list[float]:
        """
        Generate an embedding for text.

        Args:
            text: The text to embed

        Returns:
            The embedding vector
        """
        if self.model == "local-minilm":
            # Local MiniLM embeddings (free, fast)
            return self.local_embeddings.encode(text)
        elif self.model.startswith("text-embedding"):
            # OpenAI embeddings
            response = self.client.embeddings.create(
                model=self.model,
                input=text,
            )
            return response.data[0].embedding
        else:
            raise ValueError(f"Unsupported model: {self.model}")

    async def generate_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        if self.model == "local-minilm":
            # Local MiniLM batch embeddings
            return self.local_embeddings.encode_batch(texts)
        elif self.model.startswith("text-embedding"):
            # OpenAI embeddings (batch)
            response = self.client.embeddings.create(
                model=self.model,
                input=texts,
            )
            return [item.embedding for item in response.data]
        else:
            raise ValueError(f"Unsupported model: {self.model}")
