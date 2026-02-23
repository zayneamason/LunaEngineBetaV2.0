-- ============================================================================
-- MIGRATION 004: Ambassador Protocol (Sovereign Knowledge Sharing)
-- Luna Engine v2.2
-- Date: 2026-02-23
--
-- The Ambassador Protocol enables sovereign, user-declared knowledge sharing.
-- Each user's Luna instance maintains an ambassador that projects outward
-- ONLY what the user has explicitly chosen to make visible.
--
-- Core constraints:
--   - default_action is always "deny" (fail closed)
--   - exclude rules ALWAYS override include rules
--   - ambassadors are isolated (no ambassador-to-ambassador communication)
--   - ambassadors are one-way valves (outward only)
--   - every response is auditable
-- ============================================================================

-- Ambassador protocol: the user's declared sharing rules
CREATE TABLE IF NOT EXISTS ambassador_protocol (
    owner_entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    version TEXT NOT NULL DEFAULT '0.1',
    display_name TEXT,
    protocol_json TEXT NOT NULL,       -- Full JSON protocol (rules array)
    default_action TEXT NOT NULL DEFAULT 'deny',  -- Always 'deny'
    audit_log_enabled INTEGER NOT NULL DEFAULT 1, -- Always 1
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    updated_by TEXT NOT NULL DEFAULT 'system',  -- Who last modified (for FaceID audit)

    PRIMARY KEY (owner_entity_id)
);

-- Ambassador audit log: every ambassador response is logged here
CREATE TABLE IF NOT EXISTS ambassador_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_entity_id TEXT NOT NULL,          -- Whose ambassador responded
    requester_entity_id TEXT,               -- Who asked
    requester_role TEXT,                    -- Role of the requester
    query_text TEXT,                        -- What was asked
    rule_matched TEXT,                      -- Which rule ID matched (null = denied)
    knowledge_returned TEXT,                -- JSON: what was shared
    scope_categories_matched TEXT,          -- JSON: which scope categories matched
    action TEXT NOT NULL,                   -- 'allow' or 'deny'
    created_at TEXT DEFAULT (datetime('now')),

    FOREIGN KEY (owner_entity_id) REFERENCES entities(id) ON DELETE CASCADE
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_ambassador_owner ON ambassador_protocol(owner_entity_id);
CREATE INDEX IF NOT EXISTS idx_ambassador_audit_owner ON ambassador_audit_log(owner_entity_id);
CREATE INDEX IF NOT EXISTS idx_ambassador_audit_requester ON ambassador_audit_log(requester_entity_id);
CREATE INDEX IF NOT EXISTS idx_ambassador_audit_action ON ambassador_audit_log(action);
CREATE INDEX IF NOT EXISTS idx_ambassador_audit_created ON ambassador_audit_log(created_at DESC);

-- Trigger: update timestamp on protocol modification
CREATE TRIGGER IF NOT EXISTS update_ambassador_protocol_timestamp
AFTER UPDATE ON ambassador_protocol
BEGIN
    UPDATE ambassador_protocol SET updated_at = datetime('now')
    WHERE owner_entity_id = NEW.owner_entity_id;
END;
