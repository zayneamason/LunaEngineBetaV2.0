-- Luna Engine Memory Matrix Schema
-- SQLite database with sqlite-vec for embeddings

-- ============================================================================
-- CORE TABLES
-- ============================================================================

-- Memory nodes - facts, decisions, problems, actions
CREATE TABLE IF NOT EXISTS memory_nodes (
    id TEXT PRIMARY KEY,
    node_type TEXT NOT NULL,  -- FACT, DECISION, PROBLEM, ACTION, CONTEXT
    content TEXT NOT NULL,
    summary TEXT,  -- Short summary for display
    source TEXT,  -- Where this came from (conversation, file, etc.)
    confidence REAL DEFAULT 1.0,  -- 0-1 confidence score
    importance REAL DEFAULT 0.5,  -- 0-1 importance score
    access_count INTEGER DEFAULT 0,  -- Times retrieved (for lock-in)
    reinforcement_count INTEGER DEFAULT 0,  -- Times explicitly reinforced (for lock-in)
    lock_in REAL DEFAULT 0.15,  -- Lock-in coefficient (0.15-0.85)
    lock_in_state TEXT DEFAULT 'drifting',  -- drifting, fluid, settled
    last_accessed TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    metadata TEXT  -- JSON for extra data
);

-- Conversation turns - raw conversation history
CREATE TABLE IF NOT EXISTS conversation_turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,  -- user, assistant, system
    content TEXT NOT NULL,
    tokens INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    metadata TEXT  -- JSON for extra data
);

-- Graph edges - relationships between nodes
CREATE TABLE IF NOT EXISTS graph_edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_id TEXT NOT NULL,
    to_id TEXT NOT NULL,
    relationship TEXT NOT NULL,  -- DEPENDS_ON, RELATES_TO, CAUSED_BY, etc.
    strength REAL DEFAULT 1.0,  -- 0-1 edge weight
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    metadata TEXT,
    FOREIGN KEY (from_id) REFERENCES memory_nodes(id),
    FOREIGN KEY (to_id) REFERENCES memory_nodes(id),
    UNIQUE(from_id, to_id, relationship)
);

-- Consciousness snapshots - periodic state saves
CREATE TABLE IF NOT EXISTS consciousness_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tick_count INTEGER NOT NULL,
    attention_state TEXT,  -- JSON
    personality_state TEXT,  -- JSON
    active_topics TEXT,  -- JSON array
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Sessions - track conversation sessions
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    ended_at TEXT,
    turns_count INTEGER DEFAULT 0,
    metadata TEXT  -- JSON
);

-- ============================================================================
-- VECTOR EMBEDDINGS TABLE
-- Created by sqlite-vec extension
-- ============================================================================

-- This will be created dynamically when sqlite-vec is loaded:
-- CREATE VIRTUAL TABLE IF NOT EXISTS memory_embeddings USING vec0(
--     id TEXT PRIMARY KEY,
--     embedding FLOAT[1536]  -- OpenAI/Anthropic embedding dimension
-- );

-- ============================================================================
-- INDEXES
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_nodes_type ON memory_nodes(node_type);
CREATE INDEX IF NOT EXISTS idx_nodes_created ON memory_nodes(created_at);
CREATE INDEX IF NOT EXISTS idx_nodes_importance ON memory_nodes(importance DESC);
CREATE INDEX IF NOT EXISTS idx_nodes_accessed ON memory_nodes(last_accessed DESC);
CREATE INDEX IF NOT EXISTS idx_nodes_lock_in ON memory_nodes(lock_in DESC);
CREATE INDEX IF NOT EXISTS idx_nodes_lock_in_state ON memory_nodes(lock_in_state);

CREATE INDEX IF NOT EXISTS idx_turns_session ON conversation_turns(session_id);
CREATE INDEX IF NOT EXISTS idx_turns_created ON conversation_turns(created_at);

CREATE INDEX IF NOT EXISTS idx_edges_from ON graph_edges(from_id);
CREATE INDEX IF NOT EXISTS idx_edges_to ON graph_edges(to_id);
CREATE INDEX IF NOT EXISTS idx_edges_relationship ON graph_edges(relationship);

CREATE INDEX IF NOT EXISTS idx_snapshots_tick ON consciousness_snapshots(tick_count);

-- ============================================================================
-- TRIGGERS
-- ============================================================================

-- Update timestamp on node modification
CREATE TRIGGER IF NOT EXISTS update_node_timestamp
AFTER UPDATE ON memory_nodes
BEGIN
    UPDATE memory_nodes SET updated_at = datetime('now') WHERE id = NEW.id;
END;

-- Increment access count and update last_accessed
CREATE TRIGGER IF NOT EXISTS track_node_access
AFTER UPDATE OF access_count ON memory_nodes
BEGIN
    UPDATE memory_nodes SET last_accessed = datetime('now') WHERE id = NEW.id;
END;
