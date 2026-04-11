"""
Cartridge Embedder
==================

Generates embeddings at paragraph and section levels for .lun cartridges.
Uses the same MiniLM model as the rest of Luna's embedding infrastructure.
"""

from __future__ import annotations

import logging
import sqlite3
import struct

logger = logging.getLogger(__name__)


def _vector_to_blob(vector: list[float]) -> bytes:
    """Convert a float vector to a raw blob for storage."""
    return struct.pack(f"{len(vector)}f", *vector)


class CartridgeEmbedder:
    """Generate and store embeddings for .lun cartridge nodes."""

    def __init__(self):
        self._generator = None

    def _get_generator(self):
        if self._generator is not None:
            return self._generator
        try:
            from luna.substrate.aibrarian_engine import _EmbeddingGenerator
            self._generator = _EmbeddingGenerator(model="local-minilm", dim=384)
            return self._generator
        except ImportError:
            logger.error(
                "[CARTRIDGE-EMBEDDER] Cannot import _EmbeddingGenerator. "
                "Ensure sentence-transformers is installed: pip install sentence-transformers"
            )
            return None

    async def embed(self, conn: sqlite3.Connection) -> int:
        """Generate embeddings for paragraph and section nodes. Returns count."""
        gen = self._get_generator()
        if gen is None:
            return 0

        total = 0

        # --- Paragraph-level embeddings ---
        paragraphs = conn.execute(
            """
            SELECT p.id, GROUP_CONCAT(s.content, ' ') as text
            FROM doc_nodes p
            JOIN doc_nodes s ON s.parent_id = p.id AND s.type = 'sentence'
            WHERE p.type = 'paragraph'
            GROUP BY p.id
            HAVING text IS NOT NULL AND text != ''
            """
        ).fetchall()

        if paragraphs:
            para_ids = [row[0] for row in paragraphs]
            para_texts = [row[1] for row in paragraphs]

            embeddings = await gen.generate_batch(para_texts)
            for node_id, emb in zip(para_ids, embeddings):
                if emb is None:
                    continue
                blob = _vector_to_blob(emb)
                conn.execute(
                    "INSERT OR REPLACE INTO embeddings (node_id, level, vector) VALUES (?, ?, ?)",
                    (node_id, "paragraph", blob),
                )
                total += 1

        # --- Section-level embeddings ---
        sections = conn.execute(
            "SELECT id FROM doc_nodes WHERE type = 'section'"
        ).fetchall()

        section_ids = []
        section_texts = []

        for (section_id,) in sections:
            # Gather all descendant text
            desc = conn.execute(
                """
                WITH RECURSIVE subtree AS (
                    SELECT id FROM doc_nodes WHERE id = ?
                    UNION ALL
                    SELECT d.id FROM doc_nodes d
                    JOIN subtree s ON d.parent_id = s.id
                )
                SELECT content FROM doc_nodes
                WHERE id IN (SELECT id FROM subtree)
                AND type IN ('sentence', 'list_item', 'cell')
                AND content IS NOT NULL AND content != ''
                ORDER BY id
                """,
                (section_id,),
            ).fetchall()

            text = " ".join(row[0] for row in desc)
            if text.strip():
                section_ids.append(section_id)
                section_texts.append(text)

        if section_texts:
            embeddings = await gen.generate_batch(section_texts)
            for node_id, emb in zip(section_ids, embeddings):
                if emb is None:
                    continue
                blob = _vector_to_blob(emb)
                conn.execute(
                    "INSERT OR REPLACE INTO embeddings (node_id, level, vector) VALUES (?, ?, ?)",
                    (node_id, "section", blob),
                )
                total += 1

        conn.commit()
        logger.info("[CARTRIDGE-EMBEDDER] Generated %d embeddings (%d paragraph, %d section)",
                    total, len(paragraphs) if paragraphs else 0, len(section_texts))
        return total
