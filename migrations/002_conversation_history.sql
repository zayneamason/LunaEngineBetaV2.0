-- ============================================================================
-- MIGRATION 002: Conversation History System
-- Luna Engine v2.1
-- Date: 2026-01-20
--
-- Implements three-tier conversation history:
-- - Active: Last 5-10 turns, always loaded
-- - Recent: Last 50-100 turns, compressed summaries
-- - Archive: Extracted to Memory Matrix
-- ============================================================================

-- ============================================================================
-- SESSIONS TABLE (New)
-- ============================================================================
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    started_at REAL NOT NULL,
    ended_at REAL,
    app_context TEXT NOT NULL DEFAULT 'terminal',
    metadata TEXT
);

CREATE INDEX IF NOT EXISTS idx_session_active ON sessions(ended_at);
CREATE INDEX IF NOT EXISTS idx_session_started ON sessions(started_at DESC);

-- ============================================================================
-- EXTEND conversation_turns
-- Note: SQLite doesn't support adding CHECK constraints via ALTER TABLE,
-- so we add columns without the constraint and enforce in application layer
-- ============================================================================

-- Add tier column (active, recent, archived)
ALTER TABLE conversation_turns ADD COLUMN tier TEXT DEFAULT 'active';

-- Add compression columns
ALTER TABLE conversation_turns ADD COLUMN compressed TEXT;
ALTER TABLE conversation_turns ADD COLUMN compressed_at REAL;

-- Add archive tracking
ALTER TABLE conversation_turns ADD COLUMN archived_at REAL;

-- Add context references (JSON: which memories/entities were active)
ALTER TABLE conversation_turns ADD COLUMN context_refs TEXT;

-- Add indexes for tier queries
CREATE INDEX IF NOT EXISTS idx_turns_tier_timestamp ON conversation_turns(tier, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_turns_session_tier ON conversation_turns(session_id, tier);

-- ============================================================================
-- FTS5 VIRTUAL TABLE for keyword search on compressed summaries
-- ============================================================================
CREATE VIRTUAL TABLE IF NOT EXISTS history_fts USING fts5(
    compressed,
    content=conversation_turns,
    content_rowid=id,
    tokenize='porter unicode61'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS history_fts_insert AFTER INSERT ON conversation_turns
WHEN new.compressed IS NOT NULL
BEGIN
    INSERT INTO history_fts(rowid, compressed) VALUES (new.id, new.compressed);
END;

CREATE TRIGGER IF NOT EXISTS history_fts_update AFTER UPDATE OF compressed ON conversation_turns
WHEN new.compressed IS NOT NULL
BEGIN
    INSERT OR REPLACE INTO history_fts(rowid, compressed) VALUES (new.id, new.compressed);
END;

CREATE TRIGGER IF NOT EXISTS history_fts_delete AFTER DELETE ON conversation_turns BEGIN
    DELETE FROM history_fts WHERE rowid = old.id;
END;

-- ============================================================================
-- VECTOR EMBEDDINGS for semantic search (uses sqlite-vec)
-- Dimension matches existing memory_embeddings (1536 for OpenAI)
-- ============================================================================
CREATE VIRTUAL TABLE IF NOT EXISTS history_embeddings USING vec0(
    turn_id INTEGER PRIMARY KEY,
    embedding FLOAT[1536]
);

-- ============================================================================
-- COMPRESSION QUEUE for Ben Franklin processing
-- ============================================================================
CREATE TABLE IF NOT EXISTS compression_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    turn_id INTEGER NOT NULL,
    queued_at REAL NOT NULL,
    processed_at REAL,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'processing', 'completed', 'failed')),
    FOREIGN KEY (turn_id) REFERENCES conversation_turns(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_compression_queue_status ON compression_queue(status, queued_at);

-- ============================================================================
-- EXTRACTION QUEUE for Memory Matrix archival
-- ============================================================================
CREATE TABLE IF NOT EXISTS extraction_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    turn_id INTEGER NOT NULL,
    queued_at REAL NOT NULL,
    processed_at REAL,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'processing', 'completed', 'failed')),
    extracted_nodes TEXT,  -- JSON array of Memory Matrix node IDs
    FOREIGN KEY (turn_id) REFERENCES conversation_turns(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_extraction_queue_status ON extraction_queue(status, queued_at);

-- ============================================================================
-- END MIGRATION
-- ============================================================================
