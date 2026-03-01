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
    metadata TEXT,  -- JSON for extra data
    scope TEXT NOT NULL DEFAULT 'global'  -- Memory scope: 'global' or 'project:{slug}'
);

-- Conversation turns - raw conversation history
-- Three-tier system: active (recent), recent (compressed), archive (Memory Matrix)
CREATE TABLE IF NOT EXISTS conversation_turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,  -- user, assistant, system
    content TEXT NOT NULL,
    tokens INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    metadata TEXT,  -- JSON for extra data
    -- History tier columns
    tier TEXT DEFAULT 'active',  -- 'active', 'recent', 'archive'
    compressed TEXT,  -- Compressed summary (for recent tier)
    compressed_at REAL,  -- Timestamp of compression
    archived_at REAL,  -- Timestamp of archival
    context_refs TEXT  -- JSON array of referenced context IDs
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
    scope TEXT NOT NULL DEFAULT 'global',  -- Edge scope: 'global' or 'project:{slug}'
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
    session_id TEXT PRIMARY KEY,
    started_at REAL NOT NULL,
    ended_at REAL,
    app_context TEXT,
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
-- HISTORY SYSTEM TABLES
-- Three-tier conversation history: Active -> Recent -> Archive
-- ============================================================================

-- Compression queue for background processing
CREATE TABLE IF NOT EXISTS compression_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    turn_id INTEGER NOT NULL,
    status TEXT DEFAULT 'pending',
    queued_at REAL NOT NULL,
    processed_at REAL,
    FOREIGN KEY (turn_id) REFERENCES conversation_turns(id)
);

-- Extraction queue for archival to Memory Matrix
CREATE TABLE IF NOT EXISTS extraction_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    turn_id INTEGER NOT NULL,
    status TEXT DEFAULT 'pending',
    queued_at REAL NOT NULL,
    processed_at REAL,
    FOREIGN KEY (turn_id) REFERENCES conversation_turns(id)
);

-- History embeddings for semantic search on Recent tier
CREATE TABLE IF NOT EXISTS history_embeddings (
    turn_id INTEGER PRIMARY KEY,
    embedding BLOB NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (turn_id) REFERENCES conversation_turns(id)
);

-- ============================================================================
-- FULL-TEXT SEARCH (FTS5)
-- ============================================================================

-- FTS5 virtual table for fast text search with stemming
-- Porter stemmer: "collaborate" matches "collaborator", "collaboration"
CREATE VIRTUAL TABLE IF NOT EXISTS memory_nodes_fts USING fts5(
    content,
    summary,
    content='memory_nodes',
    content_rowid='rowid',
    tokenize='porter unicode61'
);

-- Trigger: Keep FTS5 in sync on INSERT
CREATE TRIGGER IF NOT EXISTS memory_nodes_fts_insert
AFTER INSERT ON memory_nodes
BEGIN
    INSERT INTO memory_nodes_fts(rowid, content, summary)
    VALUES (NEW.rowid, NEW.content, NEW.summary);
END;

-- Trigger: Keep FTS5 in sync on UPDATE
CREATE TRIGGER IF NOT EXISTS memory_nodes_fts_update
AFTER UPDATE OF content, summary ON memory_nodes
BEGIN
    UPDATE memory_nodes_fts
    SET content = NEW.content, summary = NEW.summary
    WHERE rowid = NEW.rowid;
END;

-- Trigger: Keep FTS5 in sync on DELETE
CREATE TRIGGER IF NOT EXISTS memory_nodes_fts_delete
AFTER DELETE ON memory_nodes
BEGIN
    DELETE FROM memory_nodes_fts WHERE rowid = OLD.rowid;
END;

-- ============================================================================
-- INDEXES
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_nodes_type ON memory_nodes(node_type);
CREATE INDEX IF NOT EXISTS idx_nodes_created ON memory_nodes(created_at);
CREATE INDEX IF NOT EXISTS idx_nodes_importance ON memory_nodes(importance DESC);
CREATE INDEX IF NOT EXISTS idx_nodes_accessed ON memory_nodes(last_accessed DESC);
CREATE INDEX IF NOT EXISTS idx_nodes_lock_in ON memory_nodes(lock_in DESC);
CREATE INDEX IF NOT EXISTS idx_nodes_lock_in_state ON memory_nodes(lock_in_state);
-- NOTE: idx_nodes_scope and idx_nodes_scope_type created in database.py migration
-- (scope column may not exist on pre-v2.1 databases until ALTER TABLE runs)

CREATE INDEX IF NOT EXISTS idx_turns_session ON conversation_turns(session_id);
CREATE INDEX IF NOT EXISTS idx_turns_created ON conversation_turns(created_at);
CREATE INDEX IF NOT EXISTS idx_turns_tier_timestamp ON conversation_turns(tier, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_turns_session_tier ON conversation_turns(session_id, tier);

CREATE INDEX IF NOT EXISTS idx_compression_pending ON compression_queue(status, queued_at);
CREATE INDEX IF NOT EXISTS idx_extraction_pending ON extraction_queue(status, queued_at);

CREATE INDEX IF NOT EXISTS idx_sessions_started ON sessions(started_at DESC);

CREATE INDEX IF NOT EXISTS idx_edges_from ON graph_edges(from_id);
CREATE INDEX IF NOT EXISTS idx_edges_to ON graph_edges(to_id);
CREATE INDEX IF NOT EXISTS idx_edges_relationship ON graph_edges(relationship);
-- NOTE: idx_edges_scope created in database.py migration

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

-- ============================================================================
-- ENTITY SYSTEM TABLES
-- First-class entities: people, personas, places, projects
-- ============================================================================

-- Entities: First-class objects Luna knows about
CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,              -- Slug: 'ahab', 'marzipan', 'ben-franklin'
    entity_type TEXT NOT NULL,        -- 'person' | 'persona' | 'place' | 'project'
    name TEXT NOT NULL,
    aliases TEXT,                     -- JSON array: ["Zayne", "Ahab"]
    core_facts TEXT,                  -- JSON blob (~500 tokens max)
    full_profile TEXT,                -- Markdown, can be lengthy
    voice_config TEXT,                -- JSON: tone, patterns, constraints (for personas)
    current_version INTEGER DEFAULT 1,
    metadata TEXT,                    -- Flexible JSON blob
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Entity relationships: Graph of connections between entities
CREATE TABLE IF NOT EXISTS entity_relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_entity TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    to_entity TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    relationship TEXT NOT NULL,       -- 'creator', 'friend', 'collaborator', 'embodies'
    strength REAL DEFAULT 0.5,        -- 0-1, for relevance weighting
    bidirectional INTEGER DEFAULT 0,  -- If true, relationship goes both ways
    context TEXT,                     -- "Met at Mars College 2025"
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    UNIQUE(from_entity, to_entity, relationship)
);

-- Entity mentions: Links entities to Memory Matrix nodes
CREATE TABLE IF NOT EXISTS entity_mentions (
    entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    node_id TEXT NOT NULL REFERENCES memory_nodes(id) ON DELETE CASCADE,
    mention_type TEXT NOT NULL,       -- 'subject', 'author', 'reference'
    confidence REAL DEFAULT 1.0,
    context_snippet TEXT,             -- Brief excerpt showing mention
    created_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (entity_id, node_id)
);

-- Entity versions: Full history of profile changes (append-only)
CREATE TABLE IF NOT EXISTS entity_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    core_facts TEXT,
    full_profile TEXT,
    voice_config TEXT,
    change_type TEXT NOT NULL,        -- 'create' | 'update' | 'synthesize' | 'rollback'
    change_summary TEXT,              -- Human-readable: "Added Mars College location"
    changed_by TEXT NOT NULL,         -- 'scribe' | 'librarian' | 'manual'
    change_source TEXT,               -- node_id or conversation_id that triggered
    created_at TEXT DEFAULT (datetime('now')),
    valid_from TEXT DEFAULT (datetime('now')),
    valid_until TEXT,                 -- NULL = current version
    UNIQUE(entity_id, version)
);

-- Entity indexes
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name);
CREATE INDEX IF NOT EXISTS idx_ent_relationships_from ON entity_relationships(from_entity);
CREATE INDEX IF NOT EXISTS idx_ent_relationships_to ON entity_relationships(to_entity);
CREATE INDEX IF NOT EXISTS idx_ent_relationships_type ON entity_relationships(relationship);
CREATE INDEX IF NOT EXISTS idx_mentions_entity ON entity_mentions(entity_id);
CREATE INDEX IF NOT EXISTS idx_mentions_node ON entity_mentions(node_id);
CREATE INDEX IF NOT EXISTS idx_versions_current ON entity_versions(entity_id, valid_until);
CREATE INDEX IF NOT EXISTS idx_versions_temporal ON entity_versions(entity_id, valid_from, valid_until);

-- Entity triggers
CREATE TRIGGER IF NOT EXISTS update_entity_timestamp
AFTER UPDATE ON entities
BEGIN
    UPDATE entities SET updated_at = datetime('now') WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_ent_relationship_timestamp
AFTER UPDATE ON entity_relationships
BEGIN
    UPDATE entity_relationships SET updated_at = datetime('now') WHERE id = NEW.id;
END;

-- ============================================================================
-- TUNING SYSTEM TABLES
-- Automated parameter tuning with iteration tracking
-- ============================================================================

-- Tuning sessions: Track tuning runs
CREATE TABLE IF NOT EXISTS tuning_sessions (
    session_id TEXT PRIMARY KEY,
    focus TEXT NOT NULL,              -- 'memory', 'routing', 'latency', 'all'
    started_at TEXT NOT NULL,
    ended_at TEXT,
    notes TEXT,
    best_iteration INTEGER DEFAULT 0,
    best_score REAL DEFAULT 0.0,
    base_params TEXT                  -- JSON: starting parameter snapshot
);

-- Tuning iterations: Individual parameter experiments
CREATE TABLE IF NOT EXISTS tuning_iterations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    iteration_num INTEGER NOT NULL,
    params_changed TEXT NOT NULL,     -- JSON: parameters changed this iteration
    param_snapshot TEXT NOT NULL,     -- JSON: full parameter state
    eval_results TEXT NOT NULL,       -- JSON: evaluation results
    score REAL NOT NULL,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (session_id) REFERENCES tuning_sessions(session_id)
);

-- Tuning indexes
CREATE INDEX IF NOT EXISTS idx_tuning_sessions_started ON tuning_sessions(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_tuning_iterations_session ON tuning_iterations(session_id);
CREATE INDEX IF NOT EXISTS idx_tuning_iterations_score ON tuning_iterations(score DESC);

-- ============================================================================
-- APERTURE & LIBRARY COGNITION TABLES
-- Collection-level lock-in and annotation bridge system
-- ============================================================================

-- Collection lock-in: Luna's internal state about external Aibrarian collections
-- Lives in engine DB, NOT in individual collection databases
CREATE TABLE IF NOT EXISTS collection_lock_in (
    collection_key TEXT PRIMARY KEY,
    lock_in REAL DEFAULT 0.15,
    state TEXT DEFAULT 'drifting',         -- drifting, fluid, settled
    access_count INTEGER DEFAULT 0,        -- Searches + document opens
    annotation_count INTEGER DEFAULT 0,    -- Bookmarks + notes + flags
    connected_collections INTEGER DEFAULT 0,  -- Cross-references
    entity_overlap_count INTEGER DEFAULT 0,   -- Entities shared with Matrix
    last_accessed_at TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Collection annotations: Bridge from collections into Memory Matrix
-- Each annotation creates a Matrix node with source=aibrarian provenance
CREATE TABLE IF NOT EXISTS collection_annotations (
    id TEXT PRIMARY KEY,
    collection_key TEXT NOT NULL,
    doc_id TEXT NOT NULL,
    chunk_index INTEGER,
    annotation_type TEXT NOT NULL,          -- bookmark, note, flag
    content TEXT,                            -- Luna's note text
    matrix_node_id TEXT,                    -- ID of Matrix node created
    created_at TEXT DEFAULT (datetime('now'))
);

-- Collection lock-in indexes
CREATE INDEX IF NOT EXISTS idx_coll_lock_in_state ON collection_lock_in(state);
CREATE INDEX IF NOT EXISTS idx_coll_lock_in_score ON collection_lock_in(lock_in DESC);

-- Collection annotation indexes
CREATE INDEX IF NOT EXISTS idx_annotations_collection ON collection_annotations(collection_key);
CREATE INDEX IF NOT EXISTS idx_annotations_type ON collection_annotations(annotation_type);
CREATE INDEX IF NOT EXISTS idx_annotations_doc ON collection_annotations(collection_key, doc_id);
