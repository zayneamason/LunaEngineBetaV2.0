"""
AiBrarian Engine — Universal Document Database Layer
=====================================================

Manages multiple document databases through a single interface.
Any Luna surface (MCP, Guardian, companion UI, Sheets, Eclissi)
calls the same methods.

Usage:
    engine = AiBrarianEngine("config/aibrarian_registry.yaml")
    await engine.initialize()

    results = await engine.search("dataroom", "budget solar")
    similar = await engine.similar("dataroom", doc_id, limit=5)
    hits = await engine.co_occurrence("dataroom", ["Kinoni", "grant"])
    available = engine.list_collections()
    doc_id = await engine.ingest("dataroom", file_path, metadata={})
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import struct
import subprocess
import time
import uuid
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

from .aibrarian_schema import EMBEDDING_TABLE_SQL, INVESTIGATION_SCHEMA, STANDARD_SCHEMA

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Document Chunking (word-based)
# ---------------------------------------------------------------------------

SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


@dataclass
class DocumentChunk:
    """A chunk of a document for indexing and embedding."""

    text: str
    index: int
    start_char: int
    end_char: int
    source_id: str = ""
    word_count: int = 0


def chunk_document(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50,
    source_id: str = "",
    preserve_sentences: bool = True,
) -> list[DocumentChunk]:
    """
    Split document text into overlapping word-based chunks.

    Preserves sentence boundaries when possible to keep chunks semantically
    coherent.  This is different from the SemanticChunker in extraction/
    which operates on conversation turns with token estimation.

    Args:
        text: Full document text.
        chunk_size: Target words per chunk.
        overlap: Words of overlap between adjacent chunks.
        source_id: Document ID to tag chunks with.
        preserve_sentences: Try to break at sentence boundaries.

    Returns:
        List of DocumentChunk objects.
    """
    words = text.split()
    if not words:
        return []

    chunks: list[DocumentChunk] = []
    start_word = 0
    chunk_index = 0

    while start_word < len(words):
        end_word = min(start_word + chunk_size, len(words))

        # Snap to sentence boundary if possible
        if preserve_sentences and end_word < len(words):
            chunk_text = " ".join(words[start_word:end_word])
            boundaries = list(SENTENCE_BOUNDARY.finditer(chunk_text))
            if boundaries:
                last_boundary = boundaries[-1]
                boundary_pos = last_boundary.start()
                words_to_boundary = len(chunk_text[:boundary_pos].split())
                if words_to_boundary > chunk_size * 0.6:
                    end_word = start_word + words_to_boundary

        chunk_words = words[start_word:end_word]
        chunk_text = " ".join(chunk_words)
        start_char = len(" ".join(words[:start_word])) + (1 if start_word > 0 else 0)
        end_char = start_char + len(chunk_text)

        chunks.append(
            DocumentChunk(
                text=chunk_text,
                index=chunk_index,
                start_char=start_char,
                end_char=end_char,
                source_id=source_id,
                word_count=len(chunk_words),
            )
        )

        chunk_index += 1
        if end_word >= len(words):
            break
        start_word = end_word - overlap

    # Edge case: empty text that passed the word split
    if not chunks:
        chunks.append(
            DocumentChunk(
                text=text,
                index=0,
                start_char=0,
                end_char=len(text),
                source_id=source_id,
                word_count=len(words),
            )
        )

    return chunks


# ---------------------------------------------------------------------------
# File Content Reading
# ---------------------------------------------------------------------------


def read_file_content(file_path: Path) -> str:
    """
    Read text content from a file, dispatching by extension.

    Supports: .md, .txt, .csv, .json, .yaml/.yml, .pdf (via pdftotext),
    .docx (via pandoc).
    """
    suffix = file_path.suffix.lower()

    if suffix in (".md", ".txt", ".csv", ".json", ".yaml", ".yml"):
        try:
            return file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return file_path.read_text(encoding="latin-1")

    if suffix == ".pdf":
        try:
            result = subprocess.run(
                ["pdftotext", str(file_path), "-"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            return result.stdout if result.returncode == 0 else ""
        except FileNotFoundError:
            logger.warning("pdftotext not installed — skipping PDF: %s", file_path.name)
            return ""

    if suffix == ".docx":
        try:
            result = subprocess.run(
                ["pandoc", str(file_path), "-t", "plain"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            return result.stdout if result.returncode == 0 else ""
        except FileNotFoundError:
            logger.warning("pandoc not installed — skipping DOCX: %s", file_path.name)
            return ""

    logger.warning("Unsupported file type: %s", suffix)
    return ""


# ---------------------------------------------------------------------------
# sqlite-vec helpers (match existing embeddings.py patterns)
# ---------------------------------------------------------------------------


def _vector_to_blob(vector: list[float]) -> bytes:
    return struct.pack(f"{len(vector)}f", *vector)


def _blob_to_vector(blob: bytes) -> list[float]:
    n = len(blob) // 4
    return list(struct.unpack(f"{n}f", blob))


# ---------------------------------------------------------------------------
# Configuration Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class AiBrarianConfig:
    """Configuration for a single AiBrarian collection."""

    key: str
    name: str
    description: str = ""
    db_path: str = ""
    enabled: bool = True
    read_only: bool = False
    create_if_missing: bool = False
    schema_type: str = "standard"
    source_dir: str = ""
    extract_on_ingest: bool = True
    extraction_model: str = "claude-haiku"
    chunk_size: int = 500
    chunk_overlap: int = 50
    embedding_model: str = "local-minilm"
    embedding_dim: int = 384
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    project_key: str = ""
    ingestion_pattern: str = "utilitarian"


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class AiBrarianRegistry:
    """Loads and manages AiBrarian collection configurations from YAML."""

    def __init__(self, config_path: str | Path):
        self.config_path = Path(config_path)
        self.collections: dict[str, AiBrarianConfig] = {}
        self.defaults: dict = {}

    def load(self) -> None:
        if not self.config_path.exists():
            logger.warning("AiBrarian registry not found: %s", self.config_path)
            return

        with open(self.config_path) as f:
            data = yaml.safe_load(f) or {}

        self.defaults = data.get("defaults", {})

        for key, conf in data.get("collections", {}).items():
            merged = {**self.defaults, **conf}
            # Remove keys that are not AiBrarianConfig fields
            valid_keys = {f.name for f in AiBrarianConfig.__dataclass_fields__.values()}
            filtered = {k: v for k, v in merged.items() if k in valid_keys}
            if "name" not in filtered:
                filtered["name"] = key
            self.collections[key] = AiBrarianConfig(key=key, **filtered)

    def get(self, key: str) -> Optional[AiBrarianConfig]:
        return self.collections.get(key)

    def list_enabled(self) -> list[AiBrarianConfig]:
        return [c for c in self.collections.values() if c.enabled]

    def resolve_db_path(self, config: AiBrarianConfig, project_root: Path) -> Path:
        p = Path(config.db_path)
        return p if p.is_absolute() else project_root / p


# ---------------------------------------------------------------------------
# Per-Collection Connection
# ---------------------------------------------------------------------------


class AiBrarianConnection:
    """Manages a single AiBrarian collection SQLite database connection."""

    def __init__(self, config: AiBrarianConfig, db_path: Path):
        self.config = config
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._vec_loaded = False

    async def connect(self) -> None:
        if not self.db_path.exists():
            if self.config.create_if_missing:
                self._create_database()
            else:
                raise FileNotFoundError(f"AiBrarian DB not found: {self.db_path}")

        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")

        # Try loading sqlite-vec
        try:
            import sqlite_vec

            self._conn.enable_load_extension(True)
            self._conn.load_extension(sqlite_vec.loadable_path())
            self._conn.enable_load_extension(False)

            # Create embedding virtual table
            self._conn.execute(
                EMBEDDING_TABLE_SQL.format(dim=self.config.embedding_dim)
            )
            self._conn.commit()
            self._vec_loaded = True
        except Exception as e:
            logger.warning("sqlite-vec not available for %s: %s", self.config.key, e)

    def _create_database(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.executescript(STANDARD_SCHEMA)
        if self.config.schema_type == "investigation":
            conn.executescript(INVESTIGATION_SCHEMA)
        conn.close()
        logger.info("Created AiBrarian database: %s", self.db_path)

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("AiBrarian collection not connected")
        return self._conn

    async def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None


# ---------------------------------------------------------------------------
# Embedding Generator (thin wrapper — reuses existing patterns)
# ---------------------------------------------------------------------------


class _EmbeddingGenerator:
    """Minimal embedding generator for document chunks."""

    def __init__(self, model: str = "local-minilm", dim: int = 384):
        self.model = model
        self.dim = dim
        self._model_instance = None

    def _load_model(self):
        if self._model_instance is not None:
            return
        if self.model == "local-minilm":
            try:
                from sentence_transformers import SentenceTransformer

                self._model_instance = SentenceTransformer("all-MiniLM-L6-v2")
            except ImportError:
                logger.warning("sentence-transformers not installed; embeddings disabled")
                self._model_instance = None
        else:
            logger.warning("Unsupported embedding model: %s", self.model)

    async def generate(self, text: str) -> Optional[list[float]]:
        self._load_model()
        if self._model_instance is None:
            return None
        vec = self._model_instance.encode(text).tolist()
        return vec

    async def generate_batch(self, texts: list[str]) -> list[Optional[list[float]]]:
        self._load_model()
        if self._model_instance is None:
            return [None] * len(texts)
        vecs = self._model_instance.encode(texts)
        return [v.tolist() for v in vecs]


# ---------------------------------------------------------------------------
# AiBrarian Engine
# ---------------------------------------------------------------------------


class AiBrarianEngine:
    """
    Universal document database interface.

    SUBSTRATE component — sits alongside MemoryMatrix.
    All surfaces (MCP, Guardian, UI, Sheets, Eclissi) call these methods.
    """

    def __init__(
        self,
        registry_path: str | Path,
        project_root: str | Path | None = None,
    ):
        self.registry = AiBrarianRegistry(registry_path)
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.connections: dict[str, AiBrarianConnection] = {}
        self._generators: dict[str, _EmbeddingGenerator] = {}
        self._lock_in_engine = None  # CollectionLockInEngine — set externally

    # =====================================================================
    # Lifecycle
    # =====================================================================

    async def initialize(self) -> None:
        """Load registry and connect to all enabled collections."""
        self.registry.load()
        for config in self.registry.list_enabled():
            db_path = self.registry.resolve_db_path(config, self.project_root)
            try:
                conn = AiBrarianConnection(config, db_path)
                await conn.connect()
                self.connections[config.key] = conn
                logger.info("AiBrarian connected: %s (%s)", config.key, config.name)
            except Exception as e:
                logger.warning("Failed to connect AiBrarian collection %s: %s", config.key, e)

        # Discover plugin collections from collections/ directory
        await self._discover_plugin_collections()

    async def _discover_plugin_collections(self) -> None:
        """Scan collections/ directory for plugin collection manifests."""
        collections_dir = self.project_root / "collections"
        if not collections_dir.exists():
            return

        for entry in sorted(collections_dir.iterdir()):
            if not entry.is_dir() or entry.name.startswith(("_", ".")):
                continue

            manifest_path = entry / "manifest.yaml"
            if not manifest_path.exists():
                continue

            try:
                with open(manifest_path) as f:
                    manifest = yaml.safe_load(f) or {}

                coll_cfg = manifest.get("collection", {})
                key = coll_cfg.get("key", entry.name)

                # Registry-defined collections take precedence
                if key in self.connections:
                    logger.debug("[NEXUS] Plugin '%s' overridden by registry", key)
                    continue

                # Resolve db_path relative to plugin directory
                db_file = coll_cfg.get("db_file", f"{key}.db")
                db_path = entry / db_file

                if not db_path.exists():
                    logger.warning("[NEXUS] Plugin '%s': db not found at %s", key, db_path)
                    continue

                # Build AiBrarianConfig from manifest
                config = AiBrarianConfig(
                    key=key,
                    name=manifest.get("name", key),
                    description=manifest.get("description", ""),
                    db_path=str(db_path),
                    enabled=True,
                    read_only=coll_cfg.get("read_only", False),
                    create_if_missing=False,
                    schema_type=coll_cfg.get("schema_type", "standard"),
                    chunk_size=coll_cfg.get("chunk_size", self.registry.defaults.get("chunk_size", 500)),
                    chunk_overlap=coll_cfg.get("chunk_overlap", self.registry.defaults.get("chunk_overlap", 50)),
                    embedding_model=coll_cfg.get("embedding_model", self.registry.defaults.get("embedding_model", "local-minilm")),
                    embedding_dim=coll_cfg.get("embedding_dim", self.registry.defaults.get("embedding_dim", 384)),
                    tags=coll_cfg.get("tags", []),
                    metadata={"plugin": True, "plugin_dir": str(entry)},
                )

                conn = AiBrarianConnection(config, db_path)
                await conn.connect()
                self.connections[key] = conn
                # Also register in the registry for list_enabled() consistency
                self.registry.collections[key] = config
                logger.info("[NEXUS] Plugin collection loaded: %s (%s)", key, db_path)
            except Exception as e:
                logger.warning("[NEXUS] Failed to load plugin %s: %s", entry.name, e)

    async def reload_registry(self) -> None:
        """Hot-reload registry — connect new, disconnect removed."""
        self.registry.load()
        enabled_keys = {c.key for c in self.registry.list_enabled()}

        # Disconnect removed
        for key in list(self.connections):
            if key not in enabled_keys:
                await self.connections[key].close()
                del self.connections[key]
                logger.info("Disconnected AiBrarian collection: %s", key)

        # Connect new
        for config in self.registry.list_enabled():
            if config.key not in self.connections:
                db_path = self.registry.resolve_db_path(config, self.project_root)
                try:
                    conn = AiBrarianConnection(config, db_path)
                    await conn.connect()
                    self.connections[config.key] = conn
                    logger.info("Connected AiBrarian collection: %s", config.key)
                except Exception as e:
                    logger.warning("Failed to connect AiBrarian collection %s: %s", config.key, e)

    async def shutdown(self) -> None:
        for conn in self.connections.values():
            await conn.close()
        self.connections.clear()

    def set_lock_in_engine(self, engine) -> None:
        """Attach a CollectionLockInEngine for access tracking."""
        self._lock_in_engine = engine

    async def _bump_collection_access(self, collection_key: str) -> None:
        """Increment access count in collection lock-in table."""
        if self._lock_in_engine is None:
            return
        try:
            pattern = "utilitarian"
            if collection_key in self.collections:
                pattern = self.collections[collection_key].ingestion_pattern
            await self._lock_in_engine.bump_access(collection_key, pattern=pattern)
        except Exception as e:
            logger.debug("Lock-in bump failed for %s: %s", collection_key, e)

    async def get_entity_overlap(
        self, collection_key: str, matrix_entities: list[str]
    ) -> int:
        """
        Count entities in this collection that also appear in Memory Matrix.

        Args:
            collection_key: Which collection to check
            matrix_entities: List of entity names from Memory Matrix

        Returns:
            Number of overlapping entities
        """
        if collection_key not in self.connections:
            return 0

        conn = self.connections[collection_key]
        if not matrix_entities:
            return 0

        # Search for each entity in the collection's extractions
        overlap = 0
        for entity in matrix_entities:
            try:
                row = conn.conn.execute(
                    """SELECT COUNT(*) FROM extractions
                       WHERE entity_text LIKE ? LIMIT 1""",
                    (f"%{entity}%",),
                ).fetchone()
                if row and row[0] > 0:
                    overlap += 1
            except Exception:
                pass

        return overlap

    # =====================================================================
    # List / Stats
    # =====================================================================

    def list_collections(self) -> list[dict]:
        result = []
        for config in self.registry.collections.values():
            db_path = self.registry.resolve_db_path(config, self.project_root)
            result.append(
                {
                    "key": config.key,
                    "name": config.name,
                    "description": config.description,
                    "enabled": config.enabled,
                    "connected": config.key in self.connections,
                    "read_only": config.read_only,
                    "db_exists": db_path.exists(),
                    "schema_type": config.schema_type,
                    "tags": config.tags,
                    "project_key": config.project_key,
                    "ingestion_pattern": config.ingestion_pattern,
                }
            )
        return result

    async def stats(self, collection: str) -> dict:
        conn = self._get_conn(collection)
        docs = conn.conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        chunks = conn.conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        words = conn.conn.execute(
            "SELECT COALESCE(SUM(word_count), 0) FROM documents"
        ).fetchone()[0]
        extractions = conn.conn.execute("SELECT COUNT(*) FROM extractions").fetchone()[0]
        return {
            "collection": collection,
            "name": conn.config.name,
            "documents": docs,
            "chunks": chunks,
            "total_words": words,
            "extractions": extractions,
        }

    # =====================================================================
    # Search
    # =====================================================================

    async def search(
        self,
        collection: str,
        query: str,
        search_type: str = "hybrid",
        limit: int = 20,
    ) -> list[dict]:
        """
        Search a collection.

        Args:
            collection: Registry key (e.g., "dataroom").
            query: Search query.
            search_type: "keyword", "semantic", or "hybrid" (RRF).
            limit: Max results.
        """
        conn = self._get_conn(collection)

        if search_type == "keyword":
            results = self._fts_search(conn, query, limit)
        elif search_type == "semantic":
            results = await self._vec_search(conn, query, limit)
        else:
            kw = self._fts_search(conn, query, limit)
            sem = await self._vec_search(conn, query, limit)
            if not sem:
                results = kw  # graceful fallback
            else:
                results = self._rrf_fuse(kw, sem, limit)

        # Lock-in hook: bump access on every search
        await self._bump_collection_access(collection)

        return results

    @staticmethod
    def _sanitize_fts_query(query: str) -> str:
        """Escape special FTS5 characters to prevent syntax errors."""
        import re
        # Remove FTS5 special chars: ? * " ( ) : ^ { } ~
        sanitized = re.sub(r'[?*"():^{}~]', ' ', query)
        # Collapse whitespace
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()
        return sanitized or query

    def _fts_search(
        self, conn: AiBrarianConnection, query: str, limit: int
    ) -> list[dict]:
        try:
            fts_query = self._sanitize_fts_query(query)
            cursor = conn.conn.execute(
                """
                SELECT
                    d.id, d.title, d.filename, d.category,
                    snippet(chunks_fts, 0, '>>>', '<<<', '...', 32) AS snippet,
                    bm25(chunks_fts) AS score
                FROM chunks_fts
                JOIN chunks c ON chunks_fts.rowid = c.rowid
                JOIN documents d ON c.doc_id = d.id
                WHERE chunks_fts MATCH ?
                ORDER BY score
                LIMIT ?
                """,
                (fts_query, limit),
            )
            return [
                {
                    "doc_id": row["id"],
                    "title": row["title"],
                    "filename": row["filename"],
                    "category": row["category"],
                    "snippet": row["snippet"],
                    "score": -row["score"],
                    "search_type": "keyword",
                }
                for row in cursor.fetchall()
            ]
        except sqlite3.OperationalError as e:
            logger.warning("FTS search failed for '%s': %s", query, e)
            return []

    async def _vec_search(
        self, conn: AiBrarianConnection, query: str, limit: int
    ) -> list[dict]:
        if not conn._vec_loaded:
            return []

        gen = self._get_generator(conn.config)
        query_vec = await gen.generate(query)
        if query_vec is None:
            return []

        blob = _vector_to_blob(query_vec)
        try:
            cursor = conn.conn.execute(
                """
                SELECT chunk_id, distance
                FROM chunk_embeddings
                WHERE embedding MATCH ?
                ORDER BY distance
                LIMIT ?
                """,
                (blob, limit),
            )
            results = []
            seen_docs: set[str] = set()
            for row in cursor.fetchall():
                chunk_id = row[0]
                distance = row[1]

                if ":chunk:" in chunk_id:
                    # Chunk-level embedding — join via chunks table
                    doc_row = conn.conn.execute(
                        """
                        SELECT d.id, d.title, d.filename, d.category, c.chunk_text
                        FROM chunks c
                        JOIN documents d ON c.doc_id = d.id
                        WHERE c.id = ?
                        """,
                        (chunk_id,),
                    ).fetchone()
                else:
                    # Doc-level average embedding — chunk_id IS the doc id
                    doc_row = conn.conn.execute(
                        """
                        SELECT d.id, d.title, d.filename, d.category,
                               substr(d.full_text, 1, 200) AS chunk_text
                        FROM documents d
                        WHERE d.id = ?
                        """,
                        (chunk_id,),
                    ).fetchone()

                if doc_row and doc_row["id"] not in seen_docs:
                    seen_docs.add(doc_row["id"])
                    results.append(
                        {
                            "doc_id": doc_row["id"],
                            "title": doc_row["title"],
                            "filename": doc_row["filename"],
                            "category": doc_row["category"],
                            "snippet": doc_row["chunk_text"][:200],
                            "score": max(0.0, 1.0 - distance),
                            "search_type": "semantic",
                        }
                    )
            return results
        except Exception as e:
            logger.warning("Vector search failed: %s", e)
            return []

    @staticmethod
    def _rrf_fuse(
        kw_results: list[dict],
        sem_results: list[dict],
        limit: int,
        k: int = 60,
    ) -> list[dict]:
        scores: dict[str, dict] = {}
        for rank, r in enumerate(kw_results):
            key = r["doc_id"]
            scores[key] = {"data": r, "score": 1 / (k + rank + 1)}
        for rank, r in enumerate(sem_results):
            key = r["doc_id"]
            if key not in scores:
                scores[key] = {"data": r, "score": 0}
            scores[key]["score"] += 1 / (k + rank + 1)

        sorted_results = sorted(scores.values(), key=lambda x: x["score"], reverse=True)
        return [
            {**item["data"], "score": item["score"], "search_type": "hybrid"}
            for item in sorted_results[:limit]
        ]

    # =====================================================================
    # Similarity
    # =====================================================================

    async def similar(
        self, collection: str, doc_id: str, limit: int = 10
    ) -> list[dict]:
        """Find documents similar to a given document."""
        conn = self._get_conn(collection)
        if not conn._vec_loaded:
            return []

        # Get average embedding for the document
        row = conn.conn.execute(
            "SELECT embedding FROM chunk_embeddings WHERE chunk_id = ?",
            (doc_id,),
        ).fetchone()
        if not row:
            chunk_rows = conn.conn.execute(
                """
                SELECT ce.embedding
                FROM chunk_embeddings ce
                JOIN chunks c ON ce.chunk_id = c.id
                WHERE c.doc_id = ?
                """,
                (doc_id,),
            ).fetchall()
            if not chunk_rows:
                return []
            import numpy as np

            vecs = [_blob_to_vector(r[0]) for r in chunk_rows]
            avg_vec = np.mean(vecs, axis=0).tolist()
        else:
            avg_vec = _blob_to_vector(row[0])

        blob = _vector_to_blob(avg_vec)
        cursor = conn.conn.execute(
            """
            SELECT chunk_id, distance
            FROM chunk_embeddings
            WHERE embedding MATCH ?
            ORDER BY distance
            LIMIT ?
            """,
            (blob, limit * 3),
        )

        seen_docs: set[str] = set()
        results = []
        for r in cursor.fetchall():
            chunk_id = r[0]
            distance = r[1]
            doc_row = conn.conn.execute(
                """
                SELECT d.id, d.title, d.filename, d.category
                FROM chunks c JOIN documents d ON c.doc_id = d.id
                WHERE c.id = ?
                """,
                (chunk_id,),
            ).fetchone()
            if doc_row and doc_row["id"] != doc_id and doc_row["id"] not in seen_docs:
                seen_docs.add(doc_row["id"])
                results.append(
                    {
                        "doc_id": doc_row["id"],
                        "title": doc_row["title"],
                        "filename": doc_row["filename"],
                        "category": doc_row["category"],
                        "similarity": 1.0 - distance,
                    }
                )
                if len(results) >= limit:
                    break
        return results

    # =====================================================================
    # Co-occurrence
    # =====================================================================

    async def co_occurrence(
        self, collection: str, terms: list[str], limit: int = 20
    ) -> list[dict]:
        """Find documents containing ALL specified terms."""
        conn = self._get_conn(collection)
        fts_query = " AND ".join(f'"{t}"' for t in terms)
        try:
            cursor = conn.conn.execute(
                """
                SELECT DISTINCT d.id, d.title, d.filename, d.category, d.word_count
                FROM chunks_fts
                JOIN chunks c ON chunks_fts.rowid = c.rowid
                JOIN documents d ON c.doc_id = d.id
                WHERE chunks_fts MATCH ?
                LIMIT ?
                """,
                (fts_query, limit),
            )
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.OperationalError as e:
            logger.warning("Co-occurrence search failed: %s", e)
            return []

    # =====================================================================
    # Ingestion
    # =====================================================================

    async def ingest(
        self,
        collection: str,
        file_path: Path,
        metadata: Optional[dict] = None,
    ) -> Optional[str]:
        """
        Ingest a document: read -> chunk -> embed -> extract.

        Returns the doc_id on success, None if skipped.
        """
        conn = self._get_conn(collection)
        if conn.config.read_only:
            raise PermissionError(f"Collection '{collection}' is read-only")

        metadata = metadata or {}
        file_path = Path(file_path)

        # 1. Read
        content = read_file_content(file_path)
        if not content or len(content.strip()) < 50:
            logger.info("Skipping %s (too short or unreadable)", file_path.name)
            return None

        # 2. Document record
        doc_id = str(uuid.uuid4())
        word_count = len(content.split())
        conn.conn.execute(
            """
            INSERT OR REPLACE INTO documents
                (id, filename, title, full_text, word_count, source_path,
                 doc_type, category, metadata, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                doc_id,
                file_path.name,
                metadata.get("title", file_path.stem),
                content,
                word_count,
                str(file_path),
                file_path.suffix.lower().lstrip("."),
                metadata.get("category"),
                json.dumps(metadata),
            ),
        )

        # 3. Delete old chunks + extractions (latest-wins)
        conn.conn.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))
        conn.conn.execute("DELETE FROM extractions WHERE doc_id = ?", (doc_id,))

        # 4. Chunk
        chunks = chunk_document(
            content,
            chunk_size=conn.config.chunk_size,
            overlap=conn.config.chunk_overlap,
            source_id=doc_id,
        )

        for chunk in chunks:
            chunk_id = f"{doc_id}:chunk:{chunk.index}"
            conn.conn.execute(
                """
                INSERT INTO chunks (id, doc_id, chunk_index, chunk_text, word_count, start_char, end_char)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk_id,
                    doc_id,
                    chunk.index,
                    chunk.text,
                    chunk.word_count,
                    chunk.start_char,
                    chunk.end_char,
                ),
            )

        # 5. Embed chunks
        await self._embed_chunks(conn, doc_id, chunks)

        conn.conn.commit()

        # 6. Run extraction if enabled for this collection
        if conn.config.extract_on_ingest:
            await self.extract(collection, doc_id)

        logger.info(
            "Ingested %s → %s (%d words, %d chunks)",
            file_path.name,
            doc_id,
            word_count,
            len(chunks),
        )
        return doc_id

    async def ingest_directory(
        self,
        collection: str,
        directory: Path,
        recursive: bool = True,
        extensions: Optional[set[str]] = None,
    ) -> list[str]:
        """Ingest all supported files from a directory."""
        extensions = extensions or {".md", ".txt", ".csv", ".pdf", ".docx", ".json", ".yaml", ".yml"}
        directory = Path(directory)
        doc_ids = []

        pattern = "**/*" if recursive else "*"
        for file_path in sorted(directory.glob(pattern)):
            if file_path.is_file() and file_path.suffix.lower() in extensions:
                category = file_path.parent.name if file_path.parent != directory else ""
                doc_id = await self.ingest(
                    collection,
                    file_path,
                    metadata={"title": file_path.stem, "category": category},
                )
                if doc_id:
                    doc_ids.append(doc_id)

        logger.info("Ingested %d files from %s into '%s'", len(doc_ids), directory, collection)
        return doc_ids

    # =====================================================================
    # Document Retrieval
    # =====================================================================

    async def get_document(self, collection: str, doc_id: str) -> Optional[dict]:
        """Return full document record by ID."""
        conn = self._get_conn(collection)
        row = conn.conn.execute(
            """SELECT id, filename, title, full_text, word_count,
                      source_path, doc_type, category, status, metadata,
                      created_at, updated_at
               FROM documents WHERE id = ?""",
            (doc_id,),
        ).fetchone()

        if row:
            # Lock-in hook: bump access on document open
            await self._bump_collection_access(collection)

        return dict(row) if row else None

    async def list_documents(
        self, collection: str, skip: int = 0, limit: int = 50
    ) -> dict:
        """Paginated document listing (without full_text)."""
        conn = self._get_conn(collection)
        total = conn.conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        rows = conn.conn.execute(
            """SELECT id, filename, title, word_count, category, doc_type,
                      status, created_at
               FROM documents ORDER BY created_at DESC LIMIT ? OFFSET ?""",
            (limit, skip),
        ).fetchall()
        return {
            "total": total,
            "skip": skip,
            "limit": limit,
            "documents": [dict(r) for r in rows],
        }

    # =====================================================================
    # Count & Term Stats
    # =====================================================================

    async def count(
        self, collection: str, query: str, search_type: str = "keyword"
    ) -> int:
        """Fast count of matching documents without returning results."""
        conn = self._get_conn(collection)
        if search_type == "keyword":
            try:
                row = conn.conn.execute(
                    """SELECT COUNT(DISTINCT d.id)
                       FROM chunks_fts
                       JOIN chunks c ON chunks_fts.rowid = c.rowid
                       JOIN documents d ON c.doc_id = d.id
                       WHERE chunks_fts MATCH ?""",
                    (query,),
                ).fetchone()
                return row[0] if row else 0
            except sqlite3.OperationalError:
                return 0
        else:
            results = await self.search(collection, query, search_type, 1000)
            return len(results)

    async def term_stats(self, collection: str, terms: list[str]) -> dict[str, int]:
        """Document counts for multiple terms."""
        conn = self._get_conn(collection)
        counts: dict[str, int] = {}
        for term in terms:
            try:
                row = conn.conn.execute(
                    """SELECT COUNT(DISTINCT d.id)
                       FROM chunks_fts
                       JOIN chunks c ON chunks_fts.rowid = c.rowid
                       JOIN documents d ON c.doc_id = d.id
                       WHERE chunks_fts MATCH ?""",
                    (f'"{term}"',),
                ).fetchone()
                counts[term] = row[0] if row else 0
            except sqlite3.OperationalError:
                counts[term] = 0
        return counts

    # =====================================================================
    # Entity Extraction
    # =====================================================================

    async def top_entities(
        self, collection: str, limit: int = 50, sample_size: int = 100
    ) -> dict:
        """Extract and rank entities across a sample of documents."""
        from luna.substrate.aibrarian_extractors import (
            extract_persons, extract_organizations,
        )
        conn = self._get_conn(collection)
        rows = conn.conn.execute(
            """SELECT id, full_text FROM documents
               WHERE full_text IS NOT NULL AND full_text != ''
               ORDER BY RANDOM() LIMIT ?""",
            (sample_size,),
        ).fetchall()

        person_counts: Counter = Counter()
        org_counts: Counter = Counter()

        for _, text in rows:
            if text:
                for p in extract_persons(text):
                    person_counts[p] += 1
                for o in extract_organizations(text):
                    org_counts[o] += 1

        return {
            "persons": [
                {"text": name, "count": c}
                for name, c in person_counts.most_common(limit)
            ],
            "organizations": [
                {"text": name, "count": c}
                for name, c in org_counts.most_common(limit)
            ],
            "total_documents_analyzed": len(rows),
        }

    async def search_entity(
        self, collection: str, name: str, limit: int = 50
    ) -> dict:
        """Find documents mentioning a specific entity."""
        conn = self._get_conn(collection)
        search_term = f"%{name}%"
        rows = conn.conn.execute(
            """SELECT id, title, filename, word_count,
                      substr(full_text, 1, 300) as snippet
               FROM documents WHERE full_text LIKE ?
               ORDER BY created_at DESC LIMIT ?""",
            (search_term, limit),
        ).fetchall()

        total = conn.conn.execute(
            "SELECT COUNT(*) FROM documents WHERE full_text LIKE ?",
            (search_term,),
        ).fetchone()[0]

        return {
            "entity": name,
            "document_count": total,
            "documents": [dict(r) for r in rows],
        }

    async def document_entities(self, collection: str, doc_id: str) -> dict:
        """Extract entities from a specific document."""
        from luna.substrate.aibrarian_extractors import (
            extract_persons, extract_organizations, extract_dates_simple,
        )
        conn = self._get_conn(collection)
        row = conn.conn.execute(
            "SELECT full_text FROM documents WHERE id = ?", (doc_id,)
        ).fetchone()
        if not row or not row["full_text"]:
            return {"doc_id": doc_id, "persons": [], "dates": [], "organizations": [], "total": 0}

        text = row["full_text"]
        persons = extract_persons(text)
        orgs = extract_organizations(text)
        dates = extract_dates_simple(text)
        return {
            "doc_id": doc_id,
            "persons": persons,
            "dates": dates,
            "organizations": orgs,
            "total": len(persons) + len(orgs) + len(dates),
        }

    # =====================================================================
    # Timeline
    # =====================================================================

    async def timeline(
        self,
        collection: str,
        query: str,
        limit: int = 100,
        confidence: Optional[str] = None,
    ) -> dict:
        """Extract dates from documents matching a search query."""
        from luna.substrate.aibrarian_extractors import extract_dates_from_text

        conn = self._get_conn(collection)
        try:
            rows = conn.conn.execute(
                """SELECT DISTINCT d.id, d.full_text
                   FROM chunks_fts
                   JOIN chunks c ON chunks_fts.rowid = c.rowid
                   JOIN documents d ON c.doc_id = d.id
                   WHERE chunks_fts MATCH ? LIMIT 200""",
                (query,),
            ).fetchall()
        except sqlite3.OperationalError:
            rows = []

        all_events = []
        for doc_id, full_text in rows:
            if full_text:
                all_events.extend(extract_dates_from_text(full_text, doc_id))

        if confidence:
            all_events = [e for e in all_events if e.confidence == confidence.lower()]

        all_events.sort(key=lambda e: e.date)
        all_events = all_events[:limit]

        return {
            "query": query,
            "total_events": len(all_events),
            "events": [
                {"date": e.date, "context": e.context, "doc_id": e.doc_id,
                 "confidence": e.confidence, "date_format": e.date_format}
                for e in all_events
            ],
        }

    async def timeline_range(
        self,
        collection: str,
        start: str,
        end: str,
        limit: int = 100,
        confidence: Optional[str] = None,
    ) -> dict:
        """Get events within a date range across all documents."""
        from luna.substrate.aibrarian_extractors import extract_dates_from_text
        from datetime import datetime as dt

        start_date = dt.strptime(start, "%Y-%m-%d")
        end_date = dt.strptime(end, "%Y-%m-%d")

        conn = self._get_conn(collection)
        rows = conn.conn.execute(
            "SELECT id, full_text FROM documents WHERE full_text IS NOT NULL AND full_text != ''"
        ).fetchall()

        all_events = []
        for doc_id, full_text in rows:
            if full_text:
                for e in extract_dates_from_text(full_text, doc_id):
                    try:
                        event_date = dt.strptime(e.date, "%Y-%m-%d")
                        if start_date <= event_date <= end_date:
                            all_events.append(e)
                    except ValueError:
                        continue

        if confidence:
            all_events = [e for e in all_events if e.confidence == confidence.lower()]

        all_events.sort(key=lambda e: e.date)
        all_events = all_events[:limit]

        return {
            "total_events": len(all_events),
            "events": [
                {"date": e.date, "context": e.context, "doc_id": e.doc_id,
                 "confidence": e.confidence, "date_format": e.date_format}
                for e in all_events
            ],
        }

    async def document_timeline(
        self, collection: str, doc_id: str, confidence: Optional[str] = None
    ) -> dict:
        """Get all dates extracted from a specific document."""
        from luna.substrate.aibrarian_extractors import extract_dates_from_text

        conn = self._get_conn(collection)
        row = conn.conn.execute(
            "SELECT full_text FROM documents WHERE id = ?", (doc_id,)
        ).fetchone()
        if not row or not row["full_text"]:
            return {"doc_id": doc_id, "total_events": 0, "events": []}

        events = extract_dates_from_text(row["full_text"], doc_id)
        if confidence:
            events = [e for e in events if e.confidence == confidence.lower()]

        return {
            "doc_id": doc_id,
            "total_events": len(events),
            "events": [
                {"date": e.date, "context": e.context, "doc_id": e.doc_id,
                 "confidence": e.confidence, "date_format": e.date_format}
                for e in events
            ],
        }

    # =====================================================================
    # Analytics
    # =====================================================================

    async def word_frequency(
        self, collection: str, query: str, top: int = 50
    ) -> dict:
        """Word frequency analysis on matching documents."""
        from luna.substrate.aibrarian_extractors import tokenize

        conn = self._get_conn(collection)
        try:
            rows = conn.conn.execute(
                """SELECT c.chunk_text
                   FROM chunks_fts
                   JOIN chunks c ON chunks_fts.rowid = c.rowid
                   WHERE chunks_fts MATCH ? LIMIT 500""",
                (query,),
            ).fetchall()
        except sqlite3.OperationalError:
            rows = []

        all_words: list[str] = []
        for (text,) in rows:
            if text:
                all_words.extend(tokenize(text))

        word_counts = Counter(all_words)
        total = len(all_words)
        unique = len(word_counts)

        return {
            "query": query,
            "total_words": total,
            "unique_words": unique,
            "frequencies": [
                {"word": w, "count": c, "percentage": round((c / total) * 100, 2) if total else 0}
                for w, c in word_counts.most_common(top)
            ],
        }

    async def ngrams(
        self, collection: str, query: str, n: int = 2, top: int = 30
    ) -> dict:
        """N-gram analysis on matching documents."""
        from luna.substrate.aibrarian_extractors import tokenize, extract_ngrams

        conn = self._get_conn(collection)
        try:
            rows = conn.conn.execute(
                """SELECT c.chunk_text
                   FROM chunks_fts
                   JOIN chunks c ON chunks_fts.rowid = c.rowid
                   WHERE chunks_fts MATCH ? LIMIT 500""",
                (query,),
            ).fetchall()
        except sqlite3.OperationalError:
            rows = []

        all_ngrams: list[str] = []
        for (text,) in rows:
            if text:
                words = tokenize(text)
                all_ngrams.extend(extract_ngrams(words, n))

        ngram_counts = Counter(all_ngrams)
        return {
            "query": query,
            "n": n,
            "ngrams": [
                {"phrase": phrase, "count": c}
                for phrase, c in ngram_counts.most_common(top)
            ],
        }

    async def wordcloud(
        self, collection: str, query: str, top: int = 100
    ) -> dict:
        """Wordcloud-formatted word frequency data."""
        from luna.substrate.aibrarian_extractors import tokenize

        conn = self._get_conn(collection)
        try:
            rows = conn.conn.execute(
                """SELECT c.chunk_text
                   FROM chunks_fts
                   JOIN chunks c ON chunks_fts.rowid = c.rowid
                   WHERE chunks_fts MATCH ? LIMIT 500""",
                (query,),
            ).fetchall()
        except sqlite3.OperationalError:
            rows = []

        all_words: list[str] = []
        for (text,) in rows:
            if text:
                all_words.extend(tokenize(text))

        word_counts = Counter(all_words)
        return {
            "query": query,
            "words": [
                {"text": w, "value": c}
                for w, c in word_counts.most_common(top)
            ],
        }

    async def compare_terms(
        self,
        collection: str,
        terms: list[str],
        context_window: int = 5,
        top: int = 20,
    ) -> dict:
        """Compare word contexts for multiple terms."""
        from luna.substrate.aibrarian_extractors import get_context_words, tokenize

        results = []
        conn = self._get_conn(collection)

        for term in terms:
            try:
                rows = conn.conn.execute(
                    """SELECT c.chunk_text
                       FROM chunks_fts
                       JOIN chunks c ON chunks_fts.rowid = c.rowid
                       WHERE chunks_fts MATCH ? LIMIT 200""",
                    (f'"{term}"',),
                ).fetchall()
            except sqlite3.OperationalError:
                rows = []

            doc_count = len(rows)
            all_context: list[str] = []
            for (text,) in rows:
                if text:
                    all_context.extend(get_context_words(text, term, context_window))

            context_counts = Counter(all_context)
            total_context = len(all_context)

            results.append({
                "term": term,
                "doc_count": doc_count,
                "context_words": [
                    {"word": w, "count": c,
                     "percentage": round((c / total_context) * 100, 2) if total_context else 0}
                    for w, c in context_counts.most_common(top)
                ],
            })

        return {"terms": results}

    # =====================================================================
    # Batch Similarity
    # =====================================================================

    async def batch_similarity(
        self, collection: str, doc_ids: list[str]
    ) -> dict:
        """Pairwise similarity scores between multiple documents."""
        conn = self._get_conn(collection)
        if not conn._vec_loaded:
            return {"documents": doc_ids, "pairs": [], "count": 0}

        try:
            import numpy as np
        except ImportError:
            return {"documents": doc_ids, "pairs": [], "count": 0}

        # Get average embeddings per document
        doc_embeddings: dict[str, list[float]] = {}
        for did in doc_ids:
            chunk_rows = conn.conn.execute(
                """SELECT ce.embedding FROM chunk_embeddings ce
                   JOIN chunks c ON ce.chunk_id = c.id
                   WHERE c.doc_id = ?""",
                (did,),
            ).fetchall()
            if chunk_rows:
                vecs = [_blob_to_vector(r[0]) for r in chunk_rows]
                doc_embeddings[did] = np.mean(vecs, axis=0).tolist()
            else:
                # Try doc-level embedding
                row = conn.conn.execute(
                    "SELECT embedding FROM chunk_embeddings WHERE chunk_id = ?",
                    (did,),
                ).fetchone()
                if row:
                    doc_embeddings[did] = _blob_to_vector(row[0])

        pairs = []
        keys = list(doc_embeddings.keys())
        for i, a in enumerate(keys):
            for b in keys[i + 1:]:
                vec_a = np.array(doc_embeddings[a])
                vec_b = np.array(doc_embeddings[b])
                sim = float(np.dot(vec_a, vec_b) / (np.linalg.norm(vec_a) * np.linalg.norm(vec_b) + 1e-9))
                pairs.append({"doc_a": a, "doc_b": b, "similarity": round(sim, 4)})

        pairs.sort(key=lambda p: p["similarity"], reverse=True)
        return {"documents": doc_ids, "pairs": pairs, "count": len(pairs)}

    # =====================================================================
    # Export
    # =====================================================================

    async def export_search(
        self, collection: str, query: str, limit: int = 1000, fmt: str = "json"
    ) -> dict:
        """Export search results as structured data."""
        results = await self.search(collection, query, "hybrid", limit)
        return {"query": query, "total_results": len(results), "format": fmt, "results": results}

    async def export_document(
        self, collection: str, doc_id: str, fmt: str = "json"
    ) -> Optional[dict]:
        """Export a single document."""
        return await self.get_document(collection, doc_id)

    # =====================================================================
    # Read-Only SQL
    # =====================================================================

    async def execute_sql(
        self, collection: str, query: str, limit: int = 100
    ) -> dict:
        """Execute read-only SQL against a collection's database."""
        from luna.substrate.aibrarian_extractors import validate_readonly_sql
        import time

        error = validate_readonly_sql(query)
        if error:
            raise PermissionError(error)

        conn = self._get_conn(collection)
        if "LIMIT" not in query.upper():
            query = f"{query} LIMIT {limit}"

        start = time.time()
        cursor = conn.conn.execute(query)
        rows = [dict(r) for r in cursor.fetchmany(limit)]
        elapsed = (time.time() - start) * 1000

        return {
            "query": query,
            "rows": rows,
            "row_count": len(rows),
            "execution_time_ms": round(elapsed, 2),
        }

    # =====================================================================
    # Extraction (calls Scribe via message interface)
    # =====================================================================

    async def extract(
        self, collection: str, doc_id: str, force: bool = False
    ) -> list[dict]:
        """
        Run extraction on a document.

        Deletes old extractions first (latest-wins).
        Currently a stub — wire to Scribe actor when ready.
        """
        conn = self._get_conn(collection)
        if conn.config.read_only:
            raise PermissionError(f"Collection '{collection}' is read-only")

        if not force:
            existing = conn.conn.execute(
                "SELECT COUNT(*) FROM extractions WHERE doc_id = ?", (doc_id,)
            ).fetchone()[0]
            if existing > 0:
                logger.info("Doc %s already has %d extractions (use force=True to re-extract)", doc_id, existing)
                return []

        # Delete old extractions
        conn.conn.execute("DELETE FROM extractions WHERE doc_id = ?", (doc_id,))

        # Get document text
        row = conn.conn.execute(
            "SELECT full_text FROM documents WHERE id = ?", (doc_id,)
        ).fetchone()
        if not row:
            return []

        # TODO: Wire to Scribe actor via message interface:
        #   msg = Message(type="extract_text", payload={
        #       "text": row["full_text"],
        #       "source_id": f"aibrarian:{collection}:{doc_id}",
        #       "immediate": True,
        #   })
        #   await scribe.handle(msg)
        logger.info("Extraction stub for doc %s — wire Scribe actor when ready", doc_id)
        return []

    # =====================================================================
    # Internal Helpers
    # =====================================================================

    def _get_conn(self, collection: str) -> AiBrarianConnection:
        if collection not in self.connections:
            available = list(self.connections.keys())
            raise ValueError(f"Collection '{collection}' not available. Connected: {available}")
        return self.connections[collection]

    def _get_generator(self, config: AiBrarianConfig) -> _EmbeddingGenerator:
        key = f"{config.embedding_model}:{config.embedding_dim}"
        if key not in self._generators:
            self._generators[key] = _EmbeddingGenerator(
                model=config.embedding_model, dim=config.embedding_dim
            )
        return self._generators[key]

    async def _embed_chunks(
        self,
        conn: AiBrarianConnection,
        doc_id: str,
        chunks: list[DocumentChunk],
    ) -> None:
        """Embed all chunks and store a document-level embedding (average)."""
        if not conn._vec_loaded:
            return

        gen = self._get_generator(conn.config)
        texts = [chunk.text for chunk in chunks]
        embeddings = await gen.generate_batch(texts)

        valid_embeddings = []
        for chunk, emb in zip(chunks, embeddings):
            if emb is None:
                continue
            chunk_id = f"{doc_id}:chunk:{chunk.index}"
            blob = _vector_to_blob(emb)
            conn.conn.execute(
                "INSERT OR REPLACE INTO chunk_embeddings (chunk_id, embedding) VALUES (?, ?)",
                (chunk_id, blob),
            )
            valid_embeddings.append(emb)

        # Document-level embedding = average of chunk embeddings
        if valid_embeddings:
            import numpy as np

            doc_vec = np.mean(valid_embeddings, axis=0).tolist()
            blob = _vector_to_blob(doc_vec)
            conn.conn.execute(
                "INSERT OR REPLACE INTO chunk_embeddings (chunk_id, embedding) VALUES (?, ?)",
                (doc_id, blob),
            )
