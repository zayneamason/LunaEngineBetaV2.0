-- ============================================================================
-- MIGRATION 003: Access Bridge (Dual-Tier Permissions)
-- Luna Engine v2.1
-- Date: 2026-02-19
--
-- Connects entity identity to both Luna relational tiers
-- and data room structural tiers. Single lookup at query time.
-- ============================================================================

-- Bridge: connects entity identity to both permission systems
CREATE TABLE IF NOT EXISTS access_bridge (
    entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,

    -- Luna's relational tier (evolves organically through conversation)
    luna_tier TEXT NOT NULL DEFAULT 'unknown',
    -- Values: 'admin' | 'trusted' | 'friend' | 'guest' | 'unknown'
    luna_tier_updated_at TEXT,

    -- Data room structural tier (set deliberately by Tier 1 members)
    dataroom_tier INTEGER DEFAULT 5,
    -- Values: 1 (Sovereign) | 2 (Strategist) | 3 (Domain Lead)
    --         4 (Advisor)  | 5 (External/None)
    dataroom_categories TEXT DEFAULT '[]',
    -- JSON array of accessible category numbers (1-9)
    dataroom_tier_updated_at TEXT,
    dataroom_tier_set_by TEXT,

    created_at TEXT DEFAULT (datetime('now')),

    PRIMARY KEY (entity_id)
);

-- Index for fast lookup during recognition flow
CREATE INDEX IF NOT EXISTS idx_bridge_entity ON access_bridge(entity_id);

-- Audit log for all permission checks and tier changes
CREATE TABLE IF NOT EXISTS permission_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,  -- 'check', 'grant', 'deny', 'tier_change'
    entity_id TEXT,
    entity_name TEXT,
    details TEXT,              -- JSON: what was checked, what was denied, why
    confidence REAL,
    created_at TEXT DEFAULT (datetime('now'))
);
