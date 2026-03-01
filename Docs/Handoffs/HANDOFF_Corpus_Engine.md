# HANDOFF: Corpus Engine — Universal Document Database Layer

**Date:** 2026-02-27  
**Author:** Ahab (via Claude facilitator session)  
**For:** Claude Code  
**Priority:** HIGH — blocks data room, future databases, multi-surface access  
**Supersedes:** `HANDOFF_DataRoom_Extraction_Pipeline.md` (Tasks 3-4 replaced; Tasks 1-2, 5 still valid)

---

## EXECUTIVE SUMMARY

Build a **Corpus Engine** — a substrate-level service that manages multiple document databases through a single interface. Any surface (MCP, Guardian, Luna companion, Google Sheets integration, Eclissi, future apps) can search, compare, and extract from any registered corpus without knowing the backend details.

Configuration lives in `corpus_registry.yaml`. Adding a new database = editing one YAML file. No code changes.

The Corpus Engine sits alongside Memory Matrix as core infrastructure. It is **not** an MCP tool — MCP tools are one of many thin wrappers that call it.

---

## ARCHITECTURE

```
SURFACES (thin wrappers — call CorpusEngine methods)
├── MCP Tools           → corpus_search, corpus_similar, corpus_list
├── Guardian App        → panel queries, knowledge steward searches
├── Luna Companion UI   → conversational "search my documents" 
├── Google Sheets       → Apps Script webhook → FastAPI → CorpusEngine
├── Eclissi Framework   → cultural knowledge corpus queries
└── Future surfaces     → same interface, zero new code

SUBSTRATE (the new piece)
├── CorpusEngine        → search, similar, co_occur, ingest, extract
├── CorpusRegistry      → loads corpus_registry.yaml, validates, resolves paths
└── CorpusConnection    → per-corpus SQLite connection pool + FTS5 + sqlite-vec

STORAGE
├── corpus_registry.yaml        → which databases exist and how to reach them
├── data/corpora/dataroom.db    → first corpus (investor data room)
├── data/corpora/maxwell.db     → second corpus (if ZDrive mounted + copied)
└── data/corpora/{name}.db      → future corpora follow same schema
```

---

## THE REGISTRY

### Location

`config/corpus_registry.yaml`

### Format

```yaml
# Luna Corpus Registry
# ====================
# Each corpus is an independent document database that Luna can search.
# Adding a new corpus = adding a new entry here. No code changes needed.
#
# Schema types:
#   "standard"      — documents + chunks + FTS5 + embeddings (default)
#   "investigation"  — standard + entities + connections + gaps + claims
#
# Path resolution:
#   Relative paths resolve from Luna project root.
#   Absolute paths used as-is (e.g., external drives).
#   If db_path doesn't exist and create_if_missing is true, 
#   CorpusEngine creates an empty database with the correct schema.

schema_version: 1

defaults:
  chunk_size: 500
  chunk_overlap: 50
  embedding_model: "local-minilm"
  embedding_dim: 384
  schema_type: "standard"

corpora:

  dataroom:
    name: "Project Tapestry Data Room"
    description: "Investor-facing documents organized by category"
    db_path: "data/corpora/dataroom.db"
    enabled: true
    create_if_missing: true
    # Source directory for local ingestion
    source_dir: "/Users/zayneamason/_HeyLuna_BETA/LUNA-DATAROOM"
    # Extraction config
    extract_on_ingest: true
    extraction_model: "claude-haiku"  # or "local" for offline
    # Access control
    read_only: false
    # Tags for discovery
    tags: ["investor", "tapestry", "rosa"]

  maxwell_case:
    name: "Maxwell Case Documents"
    description: "~900 Bates-numbered SDNY legal documents (OCR + text extraction)"
    db_path: "/Volumes/ZDrive-1/DatabaseProject/data/documents.db"
    enabled: false   # enable when ZDrive is mounted
    read_only: true  # never modify the original
    schema_type: "standard"
    tags: ["legal", "investigation", "epstein"]
    # No source_dir — already built
    # No extract_on_ingest — already extracted

  thiel_investigation:
    name: "Thiel Investigation"
    description: "Entity/connection graph for PT investigation"
    db_path: "/Volumes/ZDrive-1/PT_DatabaseProject/data/thiel.db"
    enabled: false
    read_only: true
    schema_type: "investigation"
    tags: ["investigation", "thiel", "palantir"]

  # --- FUTURE EXAMPLES ---
  
  # kinoni_knowledge:
  #   name: "Kinoni Community Knowledge"
  #   description: "Cultural knowledge base for ICT Hub deployment"
  #   db_path: "data/corpora/kinoni.db"
  #   enabled: false
  #   create_if_missing: true
  #   schema_type: "standard"
  #   tags: ["kinoni", "uganda", "community"]
  #   # Custom chunking for oral tradition transcripts
  #   chunk_size: 300
  #   chunk_overlap: 75

  # bombay_beach:
  #   name: "Bombay Beach Biennale Archive"
  #   description: "Installation docs, scripts, audience transcripts"
  #   db_path: "data/corpora/biennale.db"
  #   enabled: false
  #   create_if_missing: true
  #   tags: ["biennale", "art", "luna-witness"]
```

---

## STANDARD CORPUS SCHEMA

Any database registered as `schema_type: "standard"` must have these tables. The Corpus Engine creates them automatically when `create_if_missing: true`.

```sql
-- Documents: source files ingested into the corpus
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,           -- UUID
    filename TEXT NOT NULL,
    title TEXT,                    -- human-readable title
    full_text TEXT,                -- complete extracted text
    word_count INTEGER,
    source_path TEXT,              -- where the file came from
    source_type TEXT DEFAULT 'local',  -- local, gdrive, url
    doc_type TEXT,                 -- pdf, docx, md, txt, csv
    category TEXT,                 -- corpus-specific grouping
    status TEXT DEFAULT 'draft',   -- draft, final, needs_review
    metadata TEXT,                 -- JSON blob for flexible fields
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Chunks: overlapping segments for search + embeddings
CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,           -- UUID
    doc_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    word_count INTEGER,
    start_char INTEGER,
    end_char INTEGER,
    FOREIGN KEY (doc_id) REFERENCES documents(id) ON DELETE CASCADE
);

-- Extracted knowledge (populated by Scribe)
CREATE TABLE IF NOT EXISTS extractions (
    id TEXT PRIMARY KEY,           -- UUID
    doc_id TEXT NOT NULL,
    chunk_index INTEGER,
    node_type TEXT NOT NULL,       -- FACT, DECISION, INSIGHT, PROBLEM, ACTION
    content TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,
    metadata TEXT,                 -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (doc_id) REFERENCES documents(id) ON DELETE CASCADE
);

-- Entity mentions (populated by NER or regex extraction)
CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    doc_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,     -- person, org, date, location
    entity_value TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,
    FOREIGN KEY (doc_id) REFERENCES documents(id) ON DELETE CASCADE
);

-- FTS5 on chunks for keyword search
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    chunk_text,
    content='chunks',
    content_rowid='rowid'
);

-- FTS5 sync triggers
CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
    INSERT INTO chunks_fts(rowid, chunk_text)
    VALUES (new.rowid, new.chunk_text);
END;

CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, chunk_text)
    VALUES ('delete', old.rowid, old.chunk_text);
END;

CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, chunk_text)
    VALUES ('delete', old.rowid, old.chunk_text);
    INSERT INTO chunks_fts(rowid, chunk_text)
    VALUES (new.rowid, new.chunk_text);
END;

-- sqlite-vec embeddings (created at runtime by CorpusEngine)
-- CREATE VIRTUAL TABLE IF NOT EXISTS chunk_embeddings USING vec0(
--     chunk_id TEXT PRIMARY KEY,
--     embedding FLOAT[384]
-- );

-- Indexes
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id);
CREATE INDEX IF NOT EXISTS idx_extractions_doc ON extractions(doc_id);
CREATE INDEX IF NOT EXISTS idx_extractions_type ON extractions(node_type);
CREATE INDEX IF NOT EXISTS idx_entities_doc ON entities(doc_id);
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_documents_category ON documents(category);
```

### Investigation Schema Extension

For `schema_type: "investigation"`, add these tables on top of standard:

```sql
-- Connections between entities (adapted from PT_DatabaseProject)
CREATE TABLE IF NOT EXISTS connections (
    id TEXT PRIMARY KEY,
    entity_a_id TEXT NOT NULL,
    entity_b_id TEXT NOT NULL,
    relationship TEXT NOT NULL,
    direction TEXT DEFAULT 'bidirectional',
    confidence TEXT DEFAULT 'confirmed',
    start_date TEXT,
    end_date TEXT,
    source_doc_ids TEXT,  -- JSON array
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Investigation gaps / open questions
CREATE TABLE IF NOT EXISTS gaps (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    priority TEXT DEFAULT 'medium',
    status TEXT DEFAULT 'open',
    questions TEXT,          -- JSON array
    related_entity_ids TEXT, -- JSON array
    resolution TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Claims requiring verification
CREATE TABLE IF NOT EXISTS claims (
    id TEXT PRIMARY KEY,
    claim TEXT NOT NULL,
    source_doc_id TEXT,
    verification_status TEXT DEFAULT 'unverified',
    confidence_score REAL,
    supporting_evidence TEXT,    -- JSON array
    contradicting_evidence TEXT, -- JSON array
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## CORPUS ENGINE

### Location

`src/luna/substrate/corpus_engine.py` (new file)

### Interface

```python
"""
Corpus Engine — Universal Document Database Layer

Manages multiple document databases through a single interface.
Any Luna surface (MCP, Guardian, companion UI, Sheets, Eclissi)
calls the same methods.

Usage:
    engine = CorpusEngine("config/corpus_registry.yaml")
    await engine.initialize()
    
    # Search
    results = await engine.search("dataroom", "budget solar")
    
    # Similar documents  
    similar = await engine.similar("dataroom", doc_id, limit=5)
    
    # Co-occurrence
    hits = await engine.co_occurrence("dataroom", ["Kinoni", "grant"])
    
    # List available corpora
    available = engine.list_corpora()
    
    # Ingest a document
    doc_id = await engine.ingest("dataroom", file_path, metadata={})
"""

import yaml
import sqlite3
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class CorpusConfig:
    """Configuration for a single corpus."""
    key: str                          # registry key (e.g., "dataroom")
    name: str
    description: str = ""
    db_path: str = ""
    enabled: bool = True
    read_only: bool = False
    create_if_missing: bool = False
    schema_type: str = "standard"     # "standard" or "investigation"
    source_dir: str = ""
    extract_on_ingest: bool = True
    extraction_model: str = "claude-haiku"
    chunk_size: int = 500
    chunk_overlap: int = 50
    embedding_model: str = "local-minilm"
    embedding_dim: int = 384
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class CorpusRegistry:
    """Loads and manages corpus configurations from YAML."""
    
    def __init__(self, config_path: str | Path):
        self.config_path = Path(config_path)
        self.corpora: dict[str, CorpusConfig] = {}
        self.defaults: dict = {}
    
    def load(self) -> None:
        """Load registry from YAML file."""
        if not self.config_path.exists():
            logger.warning(f"Registry not found: {self.config_path}")
            return
        
        with open(self.config_path) as f:
            data = yaml.safe_load(f)
        
        self.defaults = data.get("defaults", {})
        
        for key, conf in data.get("corpora", {}).items():
            # Merge defaults with corpus-specific config
            merged = {**self.defaults, **conf}
            self.corpora[key] = CorpusConfig(key=key, **merged)
    
    def get(self, key: str) -> Optional[CorpusConfig]:
        """Get corpus config by key."""
        return self.corpora.get(key)
    
    def list_enabled(self) -> list[CorpusConfig]:
        """List all enabled corpora."""
        return [c for c in self.corpora.values() if c.enabled]
    
    def resolve_db_path(self, config: CorpusConfig, project_root: Path) -> Path:
        """Resolve db_path to absolute path."""
        p = Path(config.db_path)
        if p.is_absolute():
            return p
        return project_root / p


class CorpusConnection:
    """Manages a single corpus database connection."""
    
    def __init__(self, config: CorpusConfig, db_path: Path):
        self.config = config
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._vec_loaded = False
    
    async def connect(self) -> None:
        """Open database connection and load extensions."""
        if not self.db_path.exists():
            if self.config.create_if_missing:
                self._create_database()
            else:
                raise FileNotFoundError(f"Corpus DB not found: {self.db_path}")
        
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        
        # Try to load sqlite-vec
        try:
            import sqlite_vec
            self._conn.enable_load_extension(True)
            self._conn.load_extension(sqlite_vec.loadable_path())
            self._conn.enable_load_extension(False)
            self._vec_loaded = True
        except Exception as e:
            logger.warning(f"sqlite-vec not available for {self.config.key}: {e}")
    
    def _create_database(self) -> None:
        """Create empty database with standard schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        # Execute schema SQL based on config.schema_type
        conn.executescript(STANDARD_SCHEMA)
        if self.config.schema_type == "investigation":
            conn.executescript(INVESTIGATION_SCHEMA)
        conn.close()
        logger.info(f"Created corpus database: {self.db_path}")
    
    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("Not connected")
        return self._conn
    
    async def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None


class CorpusEngine:
    """
    Universal document database interface.
    
    This is a SUBSTRATE component — sits alongside MemoryMatrix.
    All surfaces (MCP, Guardian, UI, Sheets, Eclissi) call these methods.
    """
    
    def __init__(
        self,
        registry_path: str | Path,
        project_root: str | Path = None,
    ):
        self.registry = CorpusRegistry(registry_path)
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.connections: dict[str, CorpusConnection] = {}
        self._embedding_generators: dict[str, object] = {}
    
    async def initialize(self) -> None:
        """Load registry and connect to enabled corpora."""
        self.registry.load()
        
        for config in self.registry.list_enabled():
            db_path = self.registry.resolve_db_path(config, self.project_root)
            try:
                conn = CorpusConnection(config, db_path)
                await conn.connect()
                self.connections[config.key] = conn
                logger.info(f"Corpus connected: {config.key} ({config.name})")
            except Exception as e:
                logger.warning(f"Failed to connect corpus {config.key}: {e}")
    
    def list_corpora(self) -> list[dict]:
        """List available corpora with status."""
        result = []
        for config in self.registry.corpora.values():
            db_path = self.registry.resolve_db_path(config, self.project_root)
            result.append({
                "key": config.key,
                "name": config.name,
                "description": config.description,
                "enabled": config.enabled,
                "connected": config.key in self.connections,
                "read_only": config.read_only,
                "db_exists": db_path.exists(),
                "schema_type": config.schema_type,
                "tags": config.tags,
            })
        return result
    
    def _get_conn(self, corpus: str) -> CorpusConnection:
        """Get connection for a corpus, raising if not available."""
        if corpus not in self.connections:
            raise ValueError(
                f"Corpus '{corpus}' not available. "
                f"Connected: {list(self.connections.keys())}"
            )
        return self.connections[corpus]
    
    # =========================================================================
    # SEARCH
    # =========================================================================
    
    async def search(
        self,
        corpus: str,
        query: str,
        search_type: str = "hybrid",  # keyword, semantic, hybrid
        limit: int = 20,
    ) -> list[dict]:
        """
        Search a corpus. Works across all surfaces.
        
        Args:
            corpus: Registry key (e.g., "dataroom")
            query: Search query
            search_type: "keyword" (FTS5), "semantic" (vec), "hybrid" (RRF)
            limit: Max results
        
        Returns:
            List of {doc_id, title, snippet, score, ...}
        """
        conn = self._get_conn(corpus)
        
        if search_type == "keyword":
            return self._fts_search(conn, query, limit)
        elif search_type == "semantic":
            return await self._vec_search(conn, query, limit)
        else:  # hybrid
            kw = self._fts_search(conn, query, limit)
            sem = await self._vec_search(conn, query, limit)
            return self._rrf_fuse(kw, sem, limit)
    
    def _fts_search(self, conn: CorpusConnection, query: str, limit: int) -> list[dict]:
        """FTS5 keyword search."""
        cursor = conn.conn.execute("""
            SELECT
                d.id, d.title, d.filename, d.category,
                snippet(chunks_fts, 0, '>>>', '<<<', '...', 32) as snippet,
                bm25(chunks_fts) as score
            FROM chunks_fts
            JOIN chunks c ON chunks_fts.rowid = c.rowid
            JOIN documents d ON c.doc_id = d.id
            WHERE chunks_fts MATCH ?
            ORDER BY score
            LIMIT ?
        """, (query, limit))
        
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
    
    async def _vec_search(self, conn: CorpusConnection, query: str, limit: int) -> list[dict]:
        """sqlite-vec semantic search."""
        if not conn._vec_loaded:
            return []
        
        # Generate query embedding
        generator = self._get_embedding_generator(conn.config)
        query_vec = await generator.generate(query)
        
        # Search — implementation depends on sqlite-vec table structure
        # (see embeddings.py EmbeddingStore.search for reference)
        ...
        return []
    
    def _rrf_fuse(self, kw_results: list, sem_results: list, limit: int, k: int = 60) -> list:
        """Reciprocal Rank Fusion of keyword + semantic results."""
        scores = {}
        
        for rank, r in enumerate(kw_results):
            key = r["doc_id"]
            scores[key] = {"data": r, "score": 0}
            scores[key]["score"] += 1 / (k + rank + 1)
        
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
    
    # =========================================================================
    # SIMILARITY
    # =========================================================================
    
    async def similar(
        self,
        corpus: str,
        doc_id: str,
        limit: int = 10,
    ) -> list[dict]:
        """Find documents similar to a given document."""
        conn = self._get_conn(corpus)
        # Get doc embedding, search for neighbors
        # (implementation uses sqlite-vec)
        ...
    
    async def batch_similarity(
        self,
        corpus: str,
        doc_ids: list[str],
    ) -> list[dict]:
        """Pairwise similarity between documents."""
        conn = self._get_conn(corpus)
        ...
    
    # =========================================================================
    # CO-OCCURRENCE
    # =========================================================================
    
    async def co_occurrence(
        self,
        corpus: str,
        terms: list[str],
        limit: int = 20,
    ) -> list[dict]:
        """Find documents containing ALL specified terms."""
        conn = self._get_conn(corpus)
        
        fts_query = " AND ".join(f'"{t}"' for t in terms)
        
        cursor = conn.conn.execute("""
            SELECT DISTINCT
                d.id, d.title, d.filename, d.category, d.word_count
            FROM chunks_fts
            JOIN chunks c ON chunks_fts.rowid = c.rowid
            JOIN documents d ON c.doc_id = d.id
            WHERE chunks_fts MATCH ?
            LIMIT ?
        """, (fts_query, limit))
        
        return [dict(row) for row in cursor.fetchall()]
    
    # =========================================================================
    # INGESTION
    # =========================================================================
    
    async def ingest(
        self,
        corpus: str,
        file_path: Path,
        metadata: dict = None,
    ) -> str:
        """
        Ingest a document into a corpus.
        
        1. Read file content
        2. Create document record
        3. Chunk text
        4. Generate embeddings
        5. Optionally trigger extraction
        
        Returns:
            doc_id of the created document
        """
        conn = self._get_conn(corpus)
        if conn.config.read_only:
            raise PermissionError(f"Corpus '{corpus}' is read-only")
        
        # Read, chunk, embed, extract...
        ...
    
    async def extract(
        self,
        corpus: str,
        doc_id: str,
        force: bool = False,
    ) -> list[dict]:
        """
        Run Scribe extraction on a document.
        Deletes old extractions first (latest-wins).
        """
        conn = self._get_conn(corpus)
        if conn.config.read_only:
            raise PermissionError(f"Corpus '{corpus}' is read-only")
        ...
    
    # =========================================================================
    # STATS
    # =========================================================================
    
    async def stats(self, corpus: str) -> dict:
        """Get corpus statistics."""
        conn = self._get_conn(corpus)
        
        docs = conn.conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        chunks = conn.conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        words = conn.conn.execute("SELECT COALESCE(SUM(word_count), 0) FROM documents").fetchone()[0]
        extractions = conn.conn.execute("SELECT COUNT(*) FROM extractions").fetchone()[0]
        
        return {
            "corpus": corpus,
            "name": conn.config.name,
            "documents": docs,
            "chunks": chunks,
            "total_words": words,
            "extractions": extractions,
        }
    
    # =========================================================================
    # LIFECYCLE
    # =========================================================================
    
    async def reload_registry(self) -> None:
        """Hot-reload registry without restarting."""
        self.registry.load()
        # Connect any newly enabled corpora
        # Disconnect any newly disabled corpora
        ...
    
    async def shutdown(self) -> None:
        """Close all connections."""
        for conn in self.connections.values():
            await conn.close()
        self.connections.clear()
```

---

## SURFACE WRAPPERS

Each surface is a thin wrapper. They all call `CorpusEngine` methods.

### MCP Tools (`src/luna_mcp/corpus_tools.py`)

```python
@mcp_tool
async def corpus_list() -> str:
    """List all available document corpora."""
    return format_corpora(engine.list_corpora())

@mcp_tool  
async def corpus_search(corpus: str, query: str, search_type: str = "hybrid", limit: int = 10) -> str:
    """Search a document corpus."""
    results = await engine.search(corpus, query, search_type, limit)
    return format_results(results)

@mcp_tool
async def corpus_similar(corpus: str, doc_id: str, limit: int = 5) -> str:
    """Find documents similar to a given document."""
    results = await engine.similar(corpus, doc_id, limit)
    return format_results(results)

@mcp_tool
async def corpus_co_occurrence(corpus: str, terms: str) -> str:
    """Find documents containing ALL comma-separated terms."""
    term_list = [t.strip() for t in terms.split(",")]
    results = await engine.co_occurrence(corpus, term_list)
    return format_results(results)

@mcp_tool
async def corpus_stats(corpus: str) -> str:
    """Get statistics for a corpus."""
    return format_stats(await engine.stats(corpus))

@mcp_tool
async def corpus_ingest(corpus: str, file_path: str) -> str:
    """Ingest a document into a corpus."""
    doc_id = await engine.ingest(corpus, Path(file_path))
    return f"Ingested as {doc_id}"
```

### Guardian Integration (`src/luna/surfaces/guardian.py`)

```python
# Guardian's knowledge panel calls the same engine
async def handle_guardian_search(panel_id: str, query: str, corpus: str = "dataroom"):
    """Called by Guardian's search panel."""
    return await engine.search(corpus, query, search_type="hybrid", limit=5)
```

### Google Sheets Integration (`src/luna/surfaces/sheets_webhook.py`)

```python
# Apps Script sends HTTP POST to Luna's FastAPI
@app.post("/api/corpus/search")
async def sheets_search(request: CorpusSearchRequest):
    """Endpoint for Google Sheets integration."""
    return await engine.search(
        request.corpus,
        request.query,
        request.search_type,
        request.limit,
    )
```

### Luna Companion (conversational)

```python
# Director detects "search my documents for X" intent
# Calls engine.search() through the standard tool interface
# No special surface code needed — goes through MCP
```

---

## INTEGRATION WITH EXISTING SYSTEMS

### Memory Matrix Bridge

The Corpus Engine and Memory Matrix are **peers**, not parent-child. They can talk to each other:

```python
# Corpus extraction results can be mirrored into Memory Matrix
# (for use by smart_fetch, Observatory, etc.)
async def sync_to_memory_matrix(
    engine: CorpusEngine,
    matrix: MemoryMatrix,
    corpus: str,
    doc_id: str,
):
    """
    After extraction, optionally mirror key facts into Memory Matrix.
    This makes corpus knowledge available through Luna's normal
    recall pipeline (smart_fetch, constellation assembly).
    """
    conn = engine._get_conn(corpus)
    cursor = conn.conn.execute(
        "SELECT * FROM extractions WHERE doc_id = ?",
        (doc_id,)
    )
    
    for row in cursor.fetchall():
        await matrix.add_node(
            node_type=row["node_type"],
            content=row["content"],
            source=f"corpus:{corpus}:{doc_id}",
            confidence=row["confidence"],
            scope="global",
        )
```

### Observatory Integration

The Observatory already has quest/maintenance systems. Corpus health checks can feed into it:

```python
# "Corpus dataroom has 3 documents with no extractions" → quest
# "Corpus maxwell_case has stale entities" → quest
```

### Scribe (Ben) Integration

The Scribe's `extract_text` message handler already does extraction. The Corpus Engine calls it the same way any other component would:

```python
# Don't modify scribe.py
# Just send it the standard message:
msg = Message(
    type="extract_text",
    payload={
        "text": document_text,
        "source_id": f"corpus:{corpus}:{doc_id}",
        "immediate": True,
    }
)
await scribe.handle(msg)
```

---

## FILE MAP

| File | Action | Description |
|------|--------|-------------|
| `config/corpus_registry.yaml` | CREATE | Registry of all document corpora |
| `src/luna/substrate/corpus_engine.py` | CREATE | Core engine: search, similar, co_occur, ingest |
| `src/luna/substrate/corpus_schema.py` | CREATE | SQL schema strings (standard + investigation) |
| `src/luna/substrate/chunker.py` | CREATE | Document chunking (from previous handoff, unchanged) |
| `src/luna_mcp/corpus_tools.py` | CREATE | MCP tool wrappers |
| `src/luna/api/routes/corpus.py` | CREATE | FastAPI routes for HTTP surfaces (Sheets, etc.) |
| `scripts/ingest_dataroom.py` | MODIFY | Use CorpusEngine.ingest() instead of direct Matrix calls |
| `src/luna/actors/scribe.py` | NO CHANGE | Scribe is called, not modified |

### Unchanged from Previous Handoff

These tasks are still valid and should be implemented as specified in `HANDOFF_DataRoom_Extraction_Pipeline.md`:
- **Task 1:** Ingestion → Extraction wiring (now calls `engine.ingest()`)
- **Task 2:** Document chunking module (`substrate/chunker.py`)
- **Task 5:** Embed document chunks at ingestion

---

## VERIFICATION

```bash
# 1. Registry loads correctly
python -c "
from luna.substrate.corpus_engine import CorpusEngine
e = CorpusEngine('config/corpus_registry.yaml')
print(e.list_corpora())
"

# 2. Dataroom corpus created and searchable
python scripts/ingest_dataroom.py --local --force
# Then via MCP: corpus_search(corpus="dataroom", query="budget")

# 3. Co-occurrence works
# Via MCP: corpus_co_occurrence(corpus="dataroom", terms="Kinoni, solar")

# 4. ZDrive corpus works when mounted
# Edit registry: set maxwell_case.enabled = true
# Via MCP: corpus_search(corpus="maxwell_case", query="flight log")

# 5. ZDrive corpus gracefully fails when unmounted
# Set enabled=true, disconnect drive → connection warning, no crash

# 6. Adding new corpus requires zero code changes
# Add entry to YAML, restart → available
```

---

## NON-NEGOTIABLES

1. **YAML config, not code** — new corpus = new YAML entry. Period.
2. **Substrate, not surface** — CorpusEngine is infrastructure, not an MCP tool.
3. **One SQLite file per corpus** — sovereignty model. Each corpus is portable.
4. **Standard schema convention** — all corpora follow the same table structure.
5. **Offline-first** — semantic search falls back to keyword if embeddings unavailable.
6. **Read-only flag respected** — external databases are never modified.
7. **No ZDrive runtime dependency** — external drives are optional, graceful degradation.
8. **Scribe stays untouched** — extraction uses existing message interface.

---

## DEPENDENCY

```
pyyaml  # for registry loading (add to requirements.txt if not present)
```

Everything else (sqlite-vec, sentence-transformers, etc.) is already in the project.
