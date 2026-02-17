CREATE TABLE IF NOT EXISTS nodes (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    content TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,
    lock_in REAL DEFAULT 0.0,
    access_count INTEGER DEFAULT 0,
    cluster_id TEXT,
    tags TEXT DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (cluster_id) REFERENCES clusters(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_id TEXT NOT NULL,
    to_id TEXT NOT NULL,
    relationship TEXT NOT NULL,
    strength REAL DEFAULT 1.0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (from_id) REFERENCES nodes(id) ON DELETE CASCADE,
    FOREIGN KEY (to_id) REFERENCES nodes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS clusters (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    lock_in REAL DEFAULT 0.0,
    state TEXT DEFAULT 'drifting',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cluster_members (
    cluster_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    PRIMARY KEY (cluster_id, node_id),
    FOREIGN KEY (cluster_id) REFERENCES clusters(id) ON DELETE CASCADE,
    FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE CASCADE
);

-- FTS5 full-text search (standalone, not external-content)
CREATE VIRTUAL TABLE IF NOT EXISTS nodes_fts USING fts5(
    content, tokenize='porter'
);

-- FTS5 sync triggers (use regular DELETE, not external-content command syntax)
CREATE TRIGGER IF NOT EXISTS nodes_ai AFTER INSERT ON nodes BEGIN
    INSERT INTO nodes_fts(rowid, content) VALUES (NEW.rowid, NEW.content);
END;
CREATE TRIGGER IF NOT EXISTS nodes_ad AFTER DELETE ON nodes BEGIN
    DELETE FROM nodes_fts WHERE rowid = OLD.rowid;
END;
CREATE TRIGGER IF NOT EXISTS nodes_au AFTER UPDATE ON nodes BEGIN
    DELETE FROM nodes_fts WHERE rowid = OLD.rowid;
    INSERT INTO nodes_fts(rowid, content) VALUES (NEW.rowid, NEW.content);
END;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(type);
CREATE INDEX IF NOT EXISTS idx_nodes_lock_in ON nodes(lock_in);
CREATE INDEX IF NOT EXISTS idx_nodes_cluster ON nodes(cluster_id);
CREATE INDEX IF NOT EXISTS idx_edges_from ON edges(from_id);
CREATE INDEX IF NOT EXISTS idx_edges_to ON edges(to_id);
CREATE INDEX IF NOT EXISTS idx_edges_rel ON edges(relationship);

-- ============================================================================
-- ENTITY SYSTEM — people, personas, places, projects as first-class objects
-- ============================================================================

CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL CHECK(type IN ('person', 'persona', 'place', 'project')),
    name TEXT NOT NULL,
    aliases TEXT DEFAULT '[]',           -- JSON array of alternate names
    avatar TEXT DEFAULT '',              -- single char or emoji
    profile TEXT,                        -- prose description (nullable = sparse profile)
    core_facts TEXT DEFAULT '{}',        -- JSON object of key-value facts
    voice_config TEXT,                   -- JSON: {tone, patterns[], constraints[]} — personas only
    mention_count INTEGER DEFAULT 0,     -- denormalized count from entity_mentions
    current_version INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS entity_relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_id TEXT NOT NULL,
    to_id TEXT NOT NULL,
    rel_type TEXT NOT NULL CHECK(rel_type IN (
        'creator', 'collaborator', 'friend', 'embodies',
        'located_at', 'works_on', 'knows', 'depends_on', 'enables'
    )),
    strength REAL DEFAULT 1.0,
    context TEXT,                        -- optional annotation
    bidirectional INTEGER DEFAULT 0,     -- 0=directed, 1=bidirectional
    created_at TEXT NOT NULL,
    FOREIGN KEY (from_id) REFERENCES entities(id) ON DELETE CASCADE,
    FOREIGN KEY (to_id) REFERENCES entities(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS entity_mentions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    mention_type TEXT DEFAULT 'reference' CHECK(mention_type IN ('subject', 'reference', 'context')),
    created_at TEXT NOT NULL,
    FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE CASCADE,
    FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE CASCADE,
    UNIQUE(entity_id, node_id)           -- one mention link per entity-node pair
);

CREATE TABLE IF NOT EXISTS entity_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    change_type TEXT NOT NULL CHECK(change_type IN ('create', 'update', 'synthesize', 'rollback')),
    summary TEXT NOT NULL,
    snapshot TEXT,                        -- JSON snapshot of entity at this version (optional)
    created_at TEXT NOT NULL,
    FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE CASCADE
);

-- ============================================================================
-- QUEST SYSTEM — habit-building quests from graph health analysis
-- ============================================================================

CREATE TABLE IF NOT EXISTS quests (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL CHECK(type IN ('main', 'side', 'contract', 'treasure_hunt', 'scavenger')),
    status TEXT NOT NULL DEFAULT 'available' CHECK(status IN ('available', 'active', 'complete', 'failed', 'expired')),
    priority TEXT DEFAULT 'medium' CHECK(priority IN ('low', 'medium', 'high', 'urgent')),
    title TEXT NOT NULL,
    subtitle TEXT,
    objective TEXT NOT NULL,
    source TEXT,                          -- what triggered this quest (e.g. "maintenance_sweep → orphan entity")
    journal_prompt TEXT,                  -- optional writing prompt for side quests
    target_lock_in REAL,                  -- lock-in of primary target at quest creation
    reward_base REAL DEFAULT 0.15,        -- base reward before level scaling
    investigation TEXT DEFAULT '{}',      -- JSON: {recalls, sources, hops}
    expires_at TEXT,                      -- ISO datetime or null
    completed_at TEXT,
    failed_at TEXT,
    fail_note TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS quest_targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quest_id TEXT NOT NULL,
    target_type TEXT NOT NULL CHECK(target_type IN ('entity', 'node', 'cluster')),
    target_id TEXT NOT NULL,
    FOREIGN KEY (quest_id) REFERENCES quests(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS quest_journal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quest_id TEXT NOT NULL,
    content TEXT NOT NULL,                -- the reflection text
    themes TEXT DEFAULT '[]',             -- JSON array of theme tags
    lock_in_delta REAL DEFAULT 0.0,       -- how much lock-in changed
    edges_created INTEGER DEFAULT 0,       -- edges added during quest
    node_id TEXT,                          -- the INSIGHT node created from this journal
    created_at TEXT NOT NULL,
    FOREIGN KEY (quest_id) REFERENCES quests(id) ON DELETE CASCADE,
    FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE SET NULL
);

-- Indexes for entity and quest tables
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type);
CREATE INDEX IF NOT EXISTS idx_entity_rels_from ON entity_relationships(from_id);
CREATE INDEX IF NOT EXISTS idx_entity_rels_to ON entity_relationships(to_id);
CREATE INDEX IF NOT EXISTS idx_entity_mentions_entity ON entity_mentions(entity_id);
CREATE INDEX IF NOT EXISTS idx_entity_mentions_node ON entity_mentions(node_id);
CREATE INDEX IF NOT EXISTS idx_quests_status ON quests(status);
CREATE INDEX IF NOT EXISTS idx_quests_type ON quests(type);
CREATE INDEX IF NOT EXISTS idx_quest_targets_quest ON quest_targets(quest_id);
CREATE INDEX IF NOT EXISTS idx_quest_targets_target ON quest_targets(target_id);
