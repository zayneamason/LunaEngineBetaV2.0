-- ============================================================
-- MIGRATION 001: Entity System
-- Luna Engine v2.0
--
-- First-class entities with versioning, relationships, and mentions.
-- Run with: sqlite3 ~/.luna/luna.db < migrations/001_entity_system.sql
-- ============================================================

-- ============================================================
-- ENTITIES: First-class objects Luna knows about
-- ============================================================
CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,              -- Slug: 'ahab', 'marzipan', 'ben-franklin'
    entity_type TEXT NOT NULL,        -- 'person' | 'persona' | 'place' | 'project'
    name TEXT NOT NULL,
    aliases TEXT,                     -- JSON array: ["Zayne", "Ahab"]

    -- Structured profile (always available, ~500 tokens max)
    core_facts TEXT,                  -- JSON blob

    -- Extended profile (loaded on demand)
    full_profile TEXT,                -- Markdown, can be lengthy

    -- For personas: voice/behavior parameters
    voice_config TEXT,                -- JSON: tone, patterns, constraints

    -- Current version pointer
    current_version INTEGER DEFAULT 1,

    -- Metadata
    metadata TEXT,                    -- Flexible JSON blob
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- ============================================================
-- ENTITY RELATIONSHIPS: Graph of connections
-- ============================================================
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

-- ============================================================
-- ENTITY MENTIONS: Links entities to Memory Matrix nodes
-- ============================================================
CREATE TABLE IF NOT EXISTS entity_mentions (
    entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    node_id TEXT NOT NULL REFERENCES memory_nodes(id) ON DELETE CASCADE,
    mention_type TEXT NOT NULL,       -- 'subject', 'author', 'reference'
    confidence REAL DEFAULT 1.0,
    context_snippet TEXT,             -- Brief excerpt showing mention
    created_at TEXT DEFAULT (datetime('now')),

    PRIMARY KEY (entity_id, node_id)
);

-- ============================================================
-- ENTITY VERSIONS: Full history of profile changes
-- ============================================================
CREATE TABLE IF NOT EXISTS entity_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,

    -- Snapshot of entity state at this version
    core_facts TEXT,
    full_profile TEXT,
    voice_config TEXT,

    -- Change metadata
    change_type TEXT NOT NULL,        -- 'create' | 'update' | 'synthesize' | 'rollback'
    change_summary TEXT,              -- Human-readable: "Added Mars College location"
    changed_by TEXT NOT NULL,         -- 'scribe' | 'librarian' | 'manual'
    change_source TEXT,               -- node_id or conversation_id that triggered

    -- Temporal validity
    created_at TEXT DEFAULT (datetime('now')),
    valid_from TEXT DEFAULT (datetime('now')),
    valid_until TEXT,                 -- NULL = current version

    UNIQUE(entity_id, version)
);

-- ============================================================
-- INDEXES
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name);

CREATE INDEX IF NOT EXISTS idx_relationships_from ON entity_relationships(from_entity);
CREATE INDEX IF NOT EXISTS idx_relationships_to ON entity_relationships(to_entity);
CREATE INDEX IF NOT EXISTS idx_relationships_type ON entity_relationships(relationship);

CREATE INDEX IF NOT EXISTS idx_mentions_entity ON entity_mentions(entity_id);
CREATE INDEX IF NOT EXISTS idx_mentions_node ON entity_mentions(node_id);

-- Fast lookup of current version
CREATE INDEX IF NOT EXISTS idx_versions_current
ON entity_versions(entity_id, valid_until)
WHERE valid_until IS NULL;

-- Temporal queries
CREATE INDEX IF NOT EXISTS idx_versions_temporal
ON entity_versions(entity_id, valid_from, valid_until);

-- ============================================================
-- TRIGGERS
-- ============================================================

-- Update timestamp on entity modification
CREATE TRIGGER IF NOT EXISTS update_entity_timestamp
AFTER UPDATE ON entities
BEGIN
    UPDATE entities SET updated_at = datetime('now') WHERE id = NEW.id;
END;

-- Update timestamp on relationship modification
CREATE TRIGGER IF NOT EXISTS update_relationship_timestamp
AFTER UPDATE ON entity_relationships
BEGIN
    UPDATE entity_relationships SET updated_at = datetime('now') WHERE id = NEW.id;
END;
