"""
Tests for Vector Embeddings
============================

Tests for sqlite-vec integration and semantic search.
"""

import asyncio
import pytest
from pathlib import Path

from luna.substrate.database import MemoryDatabase
from luna.substrate.embeddings import (
    EmbeddingStore,
    vector_to_blob,
    blob_to_vector,
    DEFAULT_DIM,
)


class TestVectorConversion:
    """Tests for vector blob conversion."""

    def test_vector_to_blob_and_back(self):
        """Test round-trip conversion."""
        original = [0.1, 0.2, 0.3, -0.4, 0.5]
        blob = vector_to_blob(original)
        recovered = blob_to_vector(blob)

        assert len(recovered) == len(original)
        for orig, rec in zip(original, recovered):
            assert abs(orig - rec) < 1e-6

    def test_empty_vector(self):
        """Test empty vector conversion."""
        blob = vector_to_blob([])
        recovered = blob_to_vector(blob)
        assert recovered == []

    def test_large_vector(self):
        """Test conversion of large vectors."""
        original = [float(i) / 1000 for i in range(1536)]
        blob = vector_to_blob(original)
        recovered = blob_to_vector(blob)

        assert len(recovered) == 1536


class TestEmbeddingStore:
    """Tests for EmbeddingStore class."""

    @pytest.fixture
    async def store(self, temp_data_dir):
        """Create embedding store for testing."""
        db = MemoryDatabase(temp_data_dir / "test.db")
        await db.connect()
        store = EmbeddingStore(db, dim=4)  # Small dim for testing
        await store.initialize()
        yield store
        await db.close()

    @pytest.mark.asyncio
    async def test_initialize(self, store):
        """Test store initialization."""
        # May or may not be available depending on platform
        assert store._initialized is True

    @pytest.mark.asyncio
    async def test_store_and_retrieve(self, store):
        """Test storing and retrieving embeddings."""
        if not store.is_available:
            pytest.skip("sqlite-vec not available")

        embedding = [0.1, 0.2, 0.3, 0.4]
        await store.store("node1", embedding)

        retrieved = await store.get_embedding("node1")

        assert retrieved is not None
        assert len(retrieved) == 4
        for orig, ret in zip(embedding, retrieved):
            assert abs(orig - ret) < 1e-6

    @pytest.mark.asyncio
    async def test_search_similar(self, store):
        """Test similarity search."""
        if not store.is_available:
            pytest.skip("sqlite-vec not available")

        # Store some embeddings
        await store.store("node1", [1.0, 0.0, 0.0, 0.0])
        await store.store("node2", [0.9, 0.1, 0.0, 0.0])  # Similar to node1
        await store.store("node3", [0.0, 0.0, 1.0, 0.0])  # Different

        # Search for embeddings similar to node1
        query = [1.0, 0.0, 0.0, 0.0]
        results = await store.search(query, limit=3)

        assert len(results) >= 2
        # node1 and node2 should be most similar
        node_ids = [r[0] for r in results[:2]]
        assert "node1" in node_ids
        assert "node2" in node_ids

    @pytest.mark.asyncio
    async def test_delete_embedding(self, store):
        """Test deleting embeddings."""
        if not store.is_available:
            pytest.skip("sqlite-vec not available")

        await store.store("node1", [0.1, 0.2, 0.3, 0.4])
        await store.delete("node1")

        retrieved = await store.get_embedding("node1")
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_count(self, store):
        """Test embedding count."""
        if not store.is_available:
            pytest.skip("sqlite-vec not available")

        await store.store("node1", [0.1, 0.2, 0.3, 0.4])
        await store.store("node2", [0.5, 0.6, 0.7, 0.8])

        count = await store.count()
        assert count == 2

    @pytest.mark.asyncio
    async def test_dimension_mismatch(self, store):
        """Test dimension mismatch raises error."""
        if not store.is_available:
            pytest.skip("sqlite-vec not available")

        # Store expects dim=4, but we're giving dim=3
        with pytest.raises(ValueError, match="dimension mismatch"):
            await store.store("node1", [0.1, 0.2, 0.3])

    @pytest.mark.asyncio
    async def test_clear(self, store):
        """Test clearing all embeddings."""
        if not store.is_available:
            pytest.skip("sqlite-vec not available")

        await store.store("node1", [0.1, 0.2, 0.3, 0.4])
        await store.store("node2", [0.5, 0.6, 0.7, 0.8])

        cleared = await store.clear()
        assert cleared == 2

        count = await store.count()
        assert count == 0
