"""
.lun Knowledge Cartridge Schema
================================

SQL constants for the standalone `.lun` SQLite format.
A .lun file stores a document's complete node tree, comprehension
artifacts anchored to source nodes, and embeddings for search.
"""

LUN_SCHEMA = """\
-- Key-value metadata (title, source_hash, created_at, ...)
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- Document node tree — every element is a node with parent pointers
CREATE TABLE IF NOT EXISTS doc_nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id INTEGER,
    type TEXT NOT NULL,
    position INTEGER NOT NULL DEFAULT 0,
    content TEXT,
    meta_json TEXT,
    FOREIGN KEY (parent_id) REFERENCES doc_nodes(id)
);

-- LLM-generated extractions (claims, summaries, entities)
CREATE TABLE IF NOT EXISTS extractions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    content TEXT NOT NULL,
    confidence REAL DEFAULT 1.0
);

-- Anchors extractions to specific source nodes
CREATE TABLE IF NOT EXISTS claim_sources (
    claim_id INTEGER NOT NULL,
    node_id INTEGER NOT NULL,
    PRIMARY KEY (claim_id, node_id),
    FOREIGN KEY (claim_id) REFERENCES extractions(id),
    FOREIGN KEY (node_id) REFERENCES doc_nodes(id)
);

-- Embeddings stored as raw BLOBs (no vec0 — portability)
CREATE TABLE IF NOT EXISTS embeddings (
    node_id INTEGER NOT NULL,
    level TEXT NOT NULL,
    vector BLOB NOT NULL,
    PRIMARY KEY (node_id, level),
    FOREIGN KEY (node_id) REFERENCES doc_nodes(id)
);

-- FTS5 full-text index on node content
CREATE VIRTUAL TABLE IF NOT EXISTS nodes_fts USING fts5(
    content,
    content='doc_nodes',
    content_rowid='id'
);

-- FTS5 sync triggers (same pattern as aibrarian_schema.py)
CREATE TRIGGER IF NOT EXISTS nodes_fts_ai AFTER INSERT ON doc_nodes BEGIN
    INSERT INTO nodes_fts(rowid, content)
    VALUES (new.id, COALESCE(new.content, ''));
END;

CREATE TRIGGER IF NOT EXISTS nodes_fts_ad AFTER DELETE ON doc_nodes BEGIN
    INSERT INTO nodes_fts(nodes_fts, rowid, content)
    VALUES ('delete', old.id, COALESCE(old.content, ''));
END;

CREATE TRIGGER IF NOT EXISTS nodes_fts_au AFTER UPDATE ON doc_nodes BEGIN
    INSERT INTO nodes_fts(nodes_fts, rowid, content)
    VALUES ('delete', old.id, COALESCE(old.content, ''));
    INSERT INTO nodes_fts(rowid, content)
    VALUES (new.id, COALESCE(new.content, ''));
END;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_doc_nodes_parent ON doc_nodes(parent_id);
CREATE INDEX IF NOT EXISTS idx_doc_nodes_type ON doc_nodes(type);
CREATE INDEX IF NOT EXISTS idx_extractions_type ON extractions(type);
CREATE INDEX IF NOT EXISTS idx_claim_sources_node ON claim_sources(node_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_level ON embeddings(level);
"""
