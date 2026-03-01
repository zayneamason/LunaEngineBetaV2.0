# HANDOFF: Corpus Engine + Document Extraction Pipeline

**Date:** 2026-02-27  
**Author:** Ahab (via Claude facilitator session)  
**For:** Claude Code  
**Priority:** HIGH — blocks data room, future databases, multi-surface access  
**Replaces:** `HANDOFF_DataRoom_Extraction_Pipeline.md` and `HANDOFF_Corpus_Engine.md` (both now archived)

---

## EXECUTIVE SUMMARY

Build a **Corpus Engine** — a substrate-level service that manages multiple document databases through a single interface. Any surface (MCP, Guardian, Luna companion, Google Sheets, Eclissi, future apps) can search, compare, and extract from any registered corpus.

Configuration lives in `corpus_registry.yaml`. Adding a new database = editing one YAML file. No code changes.

The Corpus Engine sits alongside Memory Matrix as core infrastructure. It is **not** an MCP tool — MCP tools are one of many thin wrappers that call it.

**Reference implementation:** `/Volumes/ZDrive-1/DatabaseProject/` contains a fully working legal document search system with the same patterns (chunking, FTS5, vector search, RRF fusion, entity extraction). **DO NOT depend on ZDrive-1 at runtime** — it's an external drive. Copy logic, not code. That system uses FAISS; we use sqlite-vec. Same concepts, different backend.

---

## BUILD ORDER

| Phase | What | Files |
|-------|------|-------|
| 1 | Corpus Engine skeleton + registry | `corpus_engine.py`, `corpus_schema.py`, `corpus_registry.yaml` |
| 2 | Document chunker module | `chunker.py` |
| 3 | Ingestion → extraction wiring | Modify `ingest_dataroom.py` to use `engine.ingest()` |
| 4 | Chunk embedding at ingestion | Modify `embeddings.py` |
| 5 | Similarity + co-occurrence search | Methods on `CorpusEngine` |
| 6 | Surface wrappers (MCP, API, etc.) | `corpus_tools.py`, `routes/corpus.py` |

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

EXISTING SUBSTRATE (peers, not parents)
├── MemoryMatrix        → Luna's personal memory (separate from corpora)
├── EmbeddingStore      → sqlite-vec embeddings (reuse pattern per corpus)
└── Scribe (Ben)        → extraction actor (called by engine, not modified)

STORAGE
├── corpus_registry.yaml        → which databases exist and how to reach them
├── data/corpora/dataroom.db    → first corpus (investor data room)
├── data/corpora/maxwell.db     → second corpus (if ZDrive mounted + copied)
└── data/corpora/{name}.db      → future corpora follow same schema
```

---

## PHASE 1: REGISTRY + ENGINE SKELETON

### Registry Location

`config/corpus_registry.yaml`

### Registry Format

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
    source_dir: "/Users/zayneamason/_HeyLuna_BETA/LUNA-DATAROOM"
    extract_on_ingest: true
    extraction_model: "claude-haiku"
    read_only: false
    tags: ["investor", "tapestry", "rosa"]

  maxwell_case:
    name: "Maxwell Case Documents"
    description: "~900 Bates-numbered SDNY legal documents (OCR + text extraction)"
    db_path: "/Volumes/ZDrive-1/DatabaseProject/data/documents.db"
    enabled: false
    read_only: true
    schema_type: "standard"
    tags: ["legal", "investigation", "epstein"]

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
  #   tags: ["kinoni", "uganda", "community"]
  #   chunk_size: 300
  #   chunk_overlap: 75

  # bombay_beach:
  #   name: "Bombay Beach Biennale Archive"
  #   db_path: "data/corpora/biennale.db"
  #   enabled: false
  #   create_if_missing: true
  #   tags: ["biennale", "art", "luna-witness"]
```

### Standard Corpus Schema

`src/luna/substrate/corpus_schema.py` (new file)

Any database registered as `schema_type: "standard"` must have these tables. The Corpus Engine creates them automatically when `create_if_missing: true`.

```sql
-- Documents: source files ingested into the corpus
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    title TEXT,
    full_text TEXT,
    word_count INTEGER,
    source_path TEXT,
    source_type TEXT DEFAULT 'local',
    doc_type TEXT,
    category TEXT,
    status TEXT DEFAULT 'draft',
    metadata TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Chunks: overlapping segments for search + embeddings
CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,
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
    id TEXT PRIMARY KEY,
    doc_id TEXT NOT NULL,
    chunk_index INTEGER,
    node_type TEXT NOT NULL,
    content TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,
    metadata TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (doc_id) REFERENCES documents(id) ON DELETE CASCADE
);

-- Entity mentions
CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    doc_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,
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
    INSERT INTO chunks_fts(rowid, chunk_text) VALUES (new.rowid, new.chunk_text);
END;
CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, chunk_text) VALUES ('delete', old.rowid, old.chunk_text);
END;
CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, chunk_text) VALUES ('delete', old.rowid, old.chunk_text);
    INSERT INTO chunks_fts(rowid, chunk_text) VALUES (new.rowid, new.chunk_text);
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

For `schema_type: "investigation"`, add on top of standard:

```sql
CREATE TABLE IF NOT EXISTS connections (
    id TEXT PRIMARY KEY,
    entity_a_id TEXT NOT NULL,
    entity_b_id TEXT NOT NULL,
    relationship TEXT NOT NULL,
    direction TEXT DEFAULT 'bidirectional',
    confidence TEXT DEFAULT 'confirmed',
    start_date TEXT, end_date TEXT,
    source_doc_ids TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS gaps (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    priority TEXT DEFAULT 'medium',
    status TEXT DEFAULT 'open',
    questions TEXT,
    related_entity_ids TEXT,
    resolution TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS claims (
    id TEXT PRIMARY KEY,
    claim TEXT NOT NULL,
    source_doc_id TEXT,
    verification_status TEXT DEFAULT 'unverified',
    confidence_score REAL,
    supporting_evidence TEXT,
    contradicting_evidence TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Corpus Engine

`src/luna/substrate/corpus_engine.py` (new file)

```python
"""
Corpus Engine — Universal Document Database Layer

Manages multiple document databases through a single interface.
Any Luna surface (MCP, Guardian, companion UI, Sheets, Eclissi)
calls the same methods.

Usage:
    engine = CorpusEngine("config/corpus_registry.yaml")
    await engine.initialize()
    
    results = await engine.search("dataroom", "budget solar")
    similar = await engine.similar("dataroom", doc_id, limit=5)
    hits = await engine.co_occurrence("dataroom", ["Kinoni", "grant"])
    available = engine.list_corpora()
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


class CorpusRegistry:
    def __init__(self, config_path: str | Path):
        self.config_path = Path(config_path)
        self.corpora: dict[str, CorpusConfig] = {}
        self.defaults: dict = {}
    
    def load(self) -> None:
        if not self.config_path.exists():
            logger.warning(f"Registry not found: {self.config_path}")
            return
        with open(self.config_path) as f:
            data = yaml.safe_load(f)
        self.defaults = data.get("defaults", {})
        for key, conf in data.get("corpora", {}).items():
            merged = {**self.defaults, **conf}
            self.corpora[key] = CorpusConfig(key=key, **merged)
    
    def get(self, key: str) -> Optional[CorpusConfig]:
        return self.corpora.get(key)
    
    def list_enabled(self) -> list[CorpusConfig]:
        return [c for c in self.corpora.values() if c.enabled]
    
    def resolve_db_path(self, config: CorpusConfig, project_root: Path) -> Path:
        p = Path(config.db_path)
        return p if p.is_absolute() else project_root / p


class CorpusConnection:
    def __init__(self, config: CorpusConfig, db_path: Path):
        self.config = config
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._vec_loaded = False
    
    async def connect(self) -> None:
        if not self.db_path.exists():
            if self.config.create_if_missing:
                self._create_database()
            else:
                raise FileNotFoundError(f"Corpus DB not found: {self.db_path}")
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        try:
            import sqlite_vec
            self._conn.enable_load_extension(True)
            self._conn.load_extension(sqlite_vec.loadable_path())
            self._conn.enable_load_extension(False)
            self._vec_loaded = True
        except Exception as e:
            logger.warning(f"sqlite-vec not available for {self.config.key}: {e}")
    
    def _create_database(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
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
    SUBSTRATE component — sits alongside MemoryMatrix.
    All surfaces call these methods.
    """
    
    def __init__(self, registry_path: str | Path, project_root: str | Path = None):
        self.registry = CorpusRegistry(registry_path)
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.connections: dict[str, CorpusConnection] = {}
        self._embedding_generators: dict[str, object] = {}
    
    async def initialize(self) -> None:
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
        result = []
        for config in self.registry.corpora.values():
            db_path = self.registry.resolve_db_path(config, self.project_root)
            result.append({
                "key": config.key, "name": config.name,
                "description": config.description, "enabled": config.enabled,
                "connected": config.key in self.connections,
                "read_only": config.read_only, "db_exists": db_path.exists(),
                "schema_type": config.schema_type, "tags": config.tags,
            })
        return result
    
    def _get_conn(self, corpus: str) -> CorpusConnection:
        if corpus not in self.connections:
            raise ValueError(f"Corpus '{corpus}' not available. Connected: {list(self.connections.keys())}")
        return self.connections[corpus]
    
    # === SEARCH ===
    
    async def search(self, corpus: str, query: str, search_type: str = "hybrid", limit: int = 20) -> list[dict]:
        conn = self._get_conn(corpus)
        if search_type == "keyword":
            return self._fts_search(conn, query, limit)
        elif search_type == "semantic":
            return await self._vec_search(conn, query, limit)
        else:
            kw = self._fts_search(conn, query, limit)
            sem = await self._vec_search(conn, query, limit)
            return self._rrf_fuse(kw, sem, limit)
    
    def _fts_search(self, conn: CorpusConnection, query: str, limit: int) -> list[dict]:
        cursor = conn.conn.execute("""
            SELECT d.id, d.title, d.filename, d.category,
                snippet(chunks_fts, 0, '>>>', '<<<', '...', 32) as snippet,
                bm25(chunks_fts) as score
            FROM chunks_fts
            JOIN chunks c ON chunks_fts.rowid = c.rowid
            JOIN documents d ON c.doc_id = d.id
            WHERE chunks_fts MATCH ?
            ORDER BY score LIMIT ?
        """, (query, limit))
        return [{
            "doc_id": row["id"], "title": row["title"],
            "filename": row["filename"], "category": row["category"],
            "snippet": row["snippet"], "score": -row["score"],
            "search_type": "keyword",
        } for row in cursor.fetchall()]
    
    async def _vec_search(self, conn: CorpusConnection, query: str, limit: int) -> list[dict]:
        if not conn._vec_loaded:
            return []
        # Generate query embedding, search sqlite-vec
        # (see embeddings.py EmbeddingStore.search for reference)
        ...
        return []
    
    def _rrf_fuse(self, kw_results: list, sem_results: list, limit: int, k: int = 60) -> list:
        scores = {}
        for rank, r in enumerate(kw_results):
            scores[r["doc_id"]] = {"data": r, "score": 1 / (k + rank + 1)}
        for rank, r in enumerate(sem_results):
            key = r["doc_id"]
            if key not in scores:
                scores[key] = {"data": r, "score": 0}
            scores[key]["score"] += 1 / (k + rank + 1)
        sorted_results = sorted(scores.values(), key=lambda x: x["score"], reverse=True)
        return [{**item["data"], "score": item["score"], "search_type": "hybrid"} for item in sorted_results[:limit]]
    
    # === SIMILARITY ===
    
    async def similar(self, corpus: str, doc_id: str, limit: int = 10) -> list[dict]:
        conn = self._get_conn(corpus)
        # Get doc embedding from sqlite-vec, search for neighbors
        ...
    
    async def batch_similarity(self, corpus: str, doc_ids: list[str]) -> list[dict]:
        conn = self._get_conn(corpus)
        # Pairwise cosine similarity
        ...
    
    # === CO-OCCURRENCE ===
    
    async def co_occurrence(self, corpus: str, terms: list[str], limit: int = 20) -> list[dict]:
        conn = self._get_conn(corpus)
        fts_query = " AND ".join(f'"{t}"' for t in terms)
        cursor = conn.conn.execute("""
            SELECT DISTINCT d.id, d.title, d.filename, d.category, d.word_count
            FROM chunks_fts
            JOIN chunks c ON chunks_fts.rowid = c.rowid
            JOIN documents d ON c.doc_id = d.id
            WHERE chunks_fts MATCH ? LIMIT ?
        """, (fts_query, limit))
        return [dict(row) for row in cursor.fetchall()]
    
    # === INGESTION (see Phase 3 below) ===
    
    async def ingest(self, corpus: str, file_path: Path, metadata: dict = None) -> str:
        """Ingest a document: read → chunk → embed → extract."""
        conn = self._get_conn(corpus)
        if conn.config.read_only:
            raise PermissionError(f"Corpus '{corpus}' is read-only")
        # Implementation in Phase 3
        ...
    
    async def extract(self, corpus: str, doc_id: str, force: bool = False) -> list[dict]:
        """Run Scribe extraction. Deletes old extractions first (latest-wins)."""
        conn = self._get_conn(corpus)
        if conn.config.read_only:
            raise PermissionError(f"Corpus '{corpus}' is read-only")
        ...
    
    # === STATS ===
    
    async def stats(self, corpus: str) -> dict:
        conn = self._get_conn(corpus)
        docs = conn.conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        chunks = conn.conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        words = conn.conn.execute("SELECT COALESCE(SUM(word_count), 0) FROM documents").fetchone()[0]
        extractions = conn.conn.execute("SELECT COUNT(*) FROM extractions").fetchone()[0]
        return {"corpus": corpus, "name": conn.config.name, "documents": docs, "chunks": chunks, "total_words": words, "extractions": extractions}
    
    # === LIFECYCLE ===
    
    async def reload_registry(self) -> None:
        self.registry.load()
        # Connect newly enabled, disconnect newly disabled
        ...
    
    async def shutdown(self) -> None:
        for conn in self.connections.values():
            await conn.close()
        self.connections.clear()
```

---

## PHASE 2: DOCUMENT CHUNKER

`src/luna/substrate/chunker.py` (new file)

Adapted from `/Volumes/ZDrive-1/DatabaseProject/database/fts_index.py`.

```python
"""
Document chunking for Corpus Engine.
Splits documents into overlapping chunks with sentence boundary preservation.
"""

import re
from dataclasses import dataclass

@dataclass
class DocumentChunk:
    text: str
    index: int
    start_char: int
    end_char: int
    source_id: str = ""
    word_count: int = 0

SENTENCE_BOUNDARY = re.compile(r'(?<=[.!?])\s+(?=[A-Z])')

def chunk_document(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50,
    source_id: str = "",
    preserve_sentences: bool = True,
) -> list[DocumentChunk]:
    words = text.split()
    if not words:
        return []
    
    chunks = []
    start_word = 0
    chunk_index = 0
    
    while start_word < len(words):
        end_word = min(start_word + chunk_size, len(words))
        
        if preserve_sentences and end_word < len(words):
            chunk_text = ' '.join(words[start_word:end_word])
            boundaries = list(SENTENCE_BOUNDARY.finditer(chunk_text))
            if boundaries:
                last_boundary = boundaries[-1]
                boundary_pos = last_boundary.start()
                words_to_boundary = len(chunk_text[:boundary_pos].split())
                if words_to_boundary > chunk_size * 0.6:
                    end_word = start_word + words_to_boundary
        
        chunk_words = words[start_word:end_word]
        chunk_text = ' '.join(chunk_words)
        start_char = len(' '.join(words[:start_word])) + (1 if start_word > 0 else 0)
        end_char = start_char + len(chunk_text)
        
        chunks.append(DocumentChunk(
            text=chunk_text, index=chunk_index,
            start_char=start_char, end_char=end_char,
            source_id=source_id, word_count=len(chunk_words),
        ))
        
        chunk_index += 1
        if end_word >= len(words):
            break
        start_word = end_word - overlap
    
    if not chunks:
        chunks.append(DocumentChunk(
            text=text, index=0, start_char=0, end_char=len(text),
            source_id=source_id, word_count=len(words),
        ))
    
    return chunks
```

---

## PHASE 3: INGESTION → EXTRACTION WIRING

### What Exists Today

`scripts/ingest_dataroom.py`:
- Reads file index (Google Sheets or local FILE_MAP)
- Creates/updates DOCUMENT nodes in Memory Matrix
- Tracks `last_modified` to skip unchanged files
- **Does NOT read file contents or trigger extraction**

### What to Add

Inside `CorpusEngine.ingest()`, implement the full pipeline:

```python
async def ingest(self, corpus: str, file_path: Path, metadata: dict = None) -> str:
    conn = self._get_conn(corpus)
    if conn.config.read_only:
        raise PermissionError(f"Corpus '{corpus}' is read-only")
    
    # 1. Read file content
    content = read_file_content(file_path)
    if not content or len(content.strip()) < 50:
        logger.info(f"Skipping {file_path.name} (too short)")
        return None
    
    # 2. Create/update document record
    doc_id = generate_uuid()
    conn.conn.execute("""
        INSERT OR REPLACE INTO documents (id, filename, title, full_text, word_count, 
            source_path, doc_type, category, metadata, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (doc_id, file_path.name, metadata.get("title", file_path.stem),
          content, len(content.split()), str(file_path),
          file_path.suffix.lower(), metadata.get("category"),
          json.dumps(metadata or {})))
    
    # 3. Delete old chunks + extractions (latest-wins)
    conn.conn.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))
    conn.conn.execute("DELETE FROM extractions WHERE doc_id = ?", (doc_id,))
    
    # 4. Chunk
    chunks = chunk_document(content, 
        chunk_size=conn.config.chunk_size, 
        overlap=conn.config.chunk_overlap,
        source_id=doc_id)
    
    for chunk in chunks:
        conn.conn.execute("""
            INSERT INTO chunks (id, doc_id, chunk_index, chunk_text, word_count, start_char, end_char)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (f"{doc_id}:chunk:{chunk.index}", doc_id, chunk.index,
              chunk.text, chunk.word_count, chunk.start_char, chunk.end_char))
    
    # 5. Embed chunks (Phase 4)
    await self._embed_chunks(conn, doc_id, chunks)
    
    # 6. Extract via Scribe (if configured)
    if conn.config.extract_on_ingest:
        await self._extract_document(conn, doc_id, content)
    
    conn.conn.commit()
    return doc_id
```

### File Reading Support

```python
def read_file_content(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    if suffix in ('.md', '.txt', '.csv'):
        return file_path.read_text(encoding='utf-8')
    elif suffix == '.pdf':
        import subprocess
        result = subprocess.run(['pdftotext', str(file_path), '-'], capture_output=True, text=True)
        return result.stdout if result.returncode == 0 else ""
    elif suffix == '.docx':
        import subprocess
        result = subprocess.run(['pandoc', str(file_path), '-t', 'plain'], capture_output=True, text=True)
        return result.stdout if result.returncode == 0 else ""
    else:
        logger.warning(f"Unsupported file type: {suffix}")
        return ""
```

### Modify `ingest_dataroom.py`

Replace direct Memory Matrix calls with CorpusEngine:

```python
# OLD: creates DOCUMENT nodes in Memory Matrix
# NEW: calls engine.ingest() which handles everything

engine = CorpusEngine("config/corpus_registry.yaml")
await engine.initialize()

for file_path in data_room_files:
    doc_id = await engine.ingest("dataroom", file_path, metadata={
        "title": file_path.stem,
        "category": file_path.parent.name,
    })
```

Add `--no-extract` CLI flag:

```python
parser.add_argument("--no-extract", action="store_true", help="Skip content extraction")
```

---

## PHASE 4: CHUNK EMBEDDING

During ingestion, after chunking:

```python
async def _embed_chunks(self, conn: CorpusConnection, doc_id: str, chunks: list[DocumentChunk]):
    """Embed all chunks + store document-level embedding (avg of chunks)."""
    generator = self._get_embedding_generator(conn.config)
    
    texts = [chunk.text for chunk in chunks]
    embeddings = await generator.generate_batch(texts)
    
    # Store chunk embeddings
    for chunk, embedding in zip(chunks, embeddings):
        chunk_id = f"{doc_id}:chunk:{chunk.index}"
        await self._store_embedding(conn, chunk_id, embedding)
    
    # Document-level embedding = average of chunks
    import numpy as np
    doc_embedding = np.mean(embeddings, axis=0).tolist()
    await self._store_embedding(conn, doc_id, doc_embedding)
```

### Full Pipeline Order

```
File detected (new/updated)
    → Document record created/updated
    → Old chunks + extractions deleted (latest-wins)
    → File content read
    → Chunked (Phase 2)
    → Chunks stored in corpus DB
    → Chunks embedded via sqlite-vec (Phase 4)
    → Document-level embedding stored (avg of chunks)
    → Chunks extracted via Scribe (Phase 3)
    → Extraction results stored in corpus DB
```

---

## PHASE 5: SIMILARITY + CO-OCCURRENCE

Already defined in the `CorpusEngine` class above. Key methods:

- `engine.similar(corpus, doc_id, limit)` — sqlite-vec nearest neighbors
- `engine.batch_similarity(corpus, doc_ids)` — pairwise cosine for clustering
- `engine.co_occurrence(corpus, terms, limit)` — FTS5 boolean AND

---

## PHASE 6: SURFACE WRAPPERS

### MCP Tools (`src/luna_mcp/corpus_tools.py`)

```python
@mcp_tool
async def corpus_list() -> str:
    return format_corpora(engine.list_corpora())

@mcp_tool  
async def corpus_search(corpus: str, query: str, search_type: str = "hybrid", limit: int = 10) -> str:
    results = await engine.search(corpus, query, search_type, limit)
    return format_results(results)

@mcp_tool
async def corpus_similar(corpus: str, doc_id: str, limit: int = 5) -> str:
    results = await engine.similar(corpus, doc_id, limit)
    return format_results(results)

@mcp_tool
async def corpus_co_occurrence(corpus: str, terms: str) -> str:
    term_list = [t.strip() for t in terms.split(",")]
    results = await engine.co_occurrence(corpus, term_list)
    return format_results(results)

@mcp_tool
async def corpus_stats(corpus: str) -> str:
    return format_stats(await engine.stats(corpus))

@mcp_tool
async def corpus_ingest(corpus: str, file_path: str) -> str:
    doc_id = await engine.ingest(corpus, Path(file_path))
    return f"Ingested as {doc_id}"
```

### Guardian Integration (`src/luna/surfaces/guardian.py`)

```python
async def handle_guardian_search(panel_id: str, query: str, corpus: str = "dataroom"):
    return await engine.search(corpus, query, search_type="hybrid", limit=5)
```

### Google Sheets Integration (`src/luna/api/routes/corpus.py`)

```python
@app.post("/api/corpus/search")
async def sheets_search(request: CorpusSearchRequest):
    return await engine.search(request.corpus, request.query, request.search_type, request.limit)
```

### Luna Companion

No special surface code — Director detects "search my documents for X" intent and calls engine through MCP tools.

---

## INTEGRATION WITH EXISTING SYSTEMS

### Memory Matrix Bridge

Corpus Engine and Memory Matrix are **peers**, not parent-child. Optional bridge:

```python
async def sync_to_memory_matrix(engine, matrix, corpus, doc_id):
    """Mirror corpus extractions into Memory Matrix for smart_fetch access."""
    conn = engine._get_conn(corpus)
    cursor = conn.conn.execute("SELECT * FROM extractions WHERE doc_id = ?", (doc_id,))
    for row in cursor.fetchall():
        await matrix.add_node(
            node_type=row["node_type"], content=row["content"],
            source=f"corpus:{corpus}:{doc_id}", confidence=row["confidence"],
            scope="global",
        )
```

### Scribe (Ben) Integration

Engine calls Scribe via existing message interface. **Don't modify scribe.py.**

```python
msg = Message(
    type="extract_text",
    payload={"text": document_text, "source_id": f"corpus:{corpus}:{doc_id}", "immediate": True}
)
await scribe.handle(msg)
```

### Observatory Integration

Corpus health checks can feed into the quest system:

```python
# "Corpus dataroom has 3 documents with no extractions" → quest
```

---

## FILE MAP

| File | Action | Description |
|------|--------|-------------|
| `config/corpus_registry.yaml` | CREATE | Registry of all document corpora |
| `src/luna/substrate/corpus_engine.py` | CREATE | Core engine: search, similar, co_occur, ingest, extract |
| `src/luna/substrate/corpus_schema.py` | CREATE | SQL schema strings (standard + investigation) |
| `src/luna/substrate/chunker.py` | CREATE | Document chunking module |
| `src/luna_mcp/corpus_tools.py` | CREATE | MCP tool wrappers |
| `src/luna/api/routes/corpus.py` | CREATE | FastAPI routes for HTTP surfaces |
| `scripts/ingest_dataroom.py` | MODIFY | Use CorpusEngine.ingest() |
| `src/luna/actors/scribe.py` | NO CHANGE | Called via message interface |

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
# Then: corpus_search(corpus="dataroom", query="budget")

# 3. Extraction works
# corpus_search should return snippets from extracted content, not just filenames

# 4. Co-occurrence works
# corpus_co_occurrence(corpus="dataroom", terms="Kinoni, solar")

# 5. Similarity works
# corpus_similar(corpus="dataroom", doc_id="<some_id>")

# 6. Re-ingestion replaces old extractions (latest-wins)
# Edit a file, re-run ingestion → old chunks/extractions deleted, new ones created

# 7. ZDrive corpus works when mounted, fails gracefully when not
# Set maxwell_case.enabled = true → works if drive mounted, warning if not

# 8. Adding new corpus = zero code changes
# Add YAML entry, restart → available via all surfaces
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
9. **Latest-wins versioning** — re-extraction replaces old nodes. No history tracking.

---

## DEPENDENCY

```
pyyaml  # for registry loading (add to requirements.txt if not present)
```

Everything else (sqlite-vec, sentence-transformers, etc.) is already in the project.

---

## REFERENCE CODE (ZDrive-1)

These files contain proven patterns. **Copy logic, not code** — adapt to sqlite-vec:

| ZDrive File | What to Learn |
|-------------|---------------|
| `DatabaseProject/database/fts_index.py` | Chunking: `chunk_text()` function |
| `DatabaseProject/database/vector_store.py` | Embedding pipeline: batch encode → store → search |
| `DatabaseProject/api/routes/similarity.py` | Document similarity API: single + batch |
| `DatabaseProject/api/routes/search.py` | Hybrid search with RRF fusion |
| `DatabaseProject/api/routes/entities.py` | Entity extraction patterns |
| `DatabaseProject/search.py` | CLI: co-occurrence, interactive mode |
| `PT_DatabaseProject/schema.sql` | Investigation schema: entities, connections, claims, gaps |
