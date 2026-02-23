# HANDOFF: Dual-Tier Bridge Architecture — Permission-Gated Document Access

**Date:** 2026-02-19
**Scope:** Bridge table migration, document permission filtering, tier-aware response assembly
**Status:** DESIGN COMPLETE, FaceID IMPLEMENTED — ready for bridge integration
**Prerequisite:** FaceID is live. IdentityActor runs, recognizes Ahab, injects identity context into prompts.
**Companion Docs:**
- `Dual_Tier_Bridge_Architecture.docx` (full design spec — read this first)
- `Docs/Handoffs/FacialRec/ARCHITECTURE_IDENTITY_GATED_SOVEREIGNTY.md` (identity system)
- `Docs/Handoffs/FacialRec/HANDOFF_FACEID_FRONTEND_UX.md` (browser camera, frontend)

---

## OVERVIEW

Luna has two permission systems that need to work together:

- **Luna tiers** — relational. How Luna feels about someone. Evolves through conversation. Controls tone, personality depth, emotional register, memory sharing.
- **Data room tiers** — structural. What documents someone can access. Set by admin (Ahab/Tarcila). Controls which categories of data room content Luna can reveal.

FaceID is now working — Luna knows WHO she's talking to. This handoff is about making Luna know WHAT she's allowed to tell them.

### What Exists

| What | Where | Status |
|------|-------|--------|
| FaceID pipeline (camera → FaceNet → match) | `Tools/FaceID/` | COMPLETE |
| IdentityActor (engine integration) | `src/luna/actors/identity.py` | COMPLETE |
| Identity events (`IDENTITY_RECOGNIZED/LOST`) | `src/luna/core/events.py` | COMPLETE |
| System prompt identity injection | `src/luna/engine.py` | COMPLETE |
| `access_bridge` table schema | `Tools/FaceID/src/database.py` | COMPLETE (in FaceID prototype DB) |
| Entity system (entities, relationships, mentions) | `migrations/001_entity_system.sql` | COMPLETE |
| Memory Matrix (nodes, edges, graph) | `src/luna/substrate/schema.sql` | COMPLETE |
| Data room document nodes | Memory Matrix (via MCP ingestion) | PARTIAL — documents exist but lack category metadata |
| Ahab enrolled with tier assignments | `Tools/FaceID/data/faces.db` | COMPLETE — admin/Sovereign |

### What Needs To Be Built

| What | Where | Priority |
|------|-------|----------|
| `access_bridge` table in engine DB | `migrations/002_access_bridge.sql` | **P0** |
| Async bridge lookup function | `src/luna/identity/bridge.py` | **P0** |
| Document category metadata on Memory Matrix nodes | Schema extension | **P0** |
| Permission filter function | `src/luna/identity/permissions.py` | **P0** |
| Wire filter into Director/PromptAssembler | Modify existing | **P0** |
| Tier-aware denial responses | PromptAssembler constraint | **P1** |
| Document ingestion with category tags | Ingestion pipeline | **P1** |
| Sync checker (spreadsheet ↔ Memory Matrix) | New tool | **P2** |
| Audit log for permission checks | New table | **P2** |

---

## PHASE 1: Bridge Table in Engine Database (~half day)

### New Migration: `migrations/002_access_bridge.sql`

```sql
-- ============================================================
-- MIGRATION 002: Access Bridge (Dual-Tier Permissions)
-- Luna Engine v2.0
--
-- Connects entity identity to both Luna relational tiers
-- and data room structural tiers. Single lookup at query time.
-- ============================================================

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
    -- e.g., '[1, 5, 7]' = Company Overview, Market, Go-to-Market
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
```

### Run Migration

```bash
sqlite3 data/luna_engine.db < migrations/002_access_bridge.sql
```

### Seed Initial Data

After migration, seed the bridge with current team members. These entity_ids must match existing entities in the `entities` table:

```sql
-- Ahab: Admin/Sovereign, all categories
INSERT OR REPLACE INTO access_bridge
    (entity_id, luna_tier, dataroom_tier, dataroom_categories, dataroom_tier_set_by)
VALUES ('ahab', 'admin', 1, '[1,2,3,4,5,6,7,8,9]', 'system');

-- Tarcila: Trusted/Sovereign, all categories
INSERT OR REPLACE INTO access_bridge
    (entity_id, luna_tier, dataroom_tier, dataroom_categories, dataroom_tier_set_by)
VALUES ('tarcila', 'trusted', 1, '[1,2,3,4,5,6,7,8,9]', 'ahab');

-- Cliff: Friend/Strategist, all categories (read-only)
INSERT OR REPLACE INTO access_bridge
    (entity_id, luna_tier, dataroom_tier, dataroom_categories, dataroom_tier_set_by)
VALUES ('cliff', 'friend', 2, '[1,2,3,4,5,6,7,8,9]', 'ahab');

-- Calvin: Trusted/Domain Lead, biz dev categories only
INSERT OR REPLACE INTO access_bridge
    (entity_id, luna_tier, dataroom_tier, dataroom_categories, dataroom_tier_set_by)
VALUES ('calvin', 'trusted', 3, '[1,5,7]', 'ahab');

-- Hai Dai: Friend/Domain Lead, partnerships only
INSERT OR REPLACE INTO access_bridge
    (entity_id, luna_tier, dataroom_tier, dataroom_categories, dataroom_tier_set_by)
VALUES ('hai-dai', 'friend', 3, '[8]', 'ahab');
```

**IMPORTANT:** The entity_ids above (`ahab`, `tarcila`, etc.) must match whatever IDs exist in the `entities` table. Check with:
```sql
SELECT id, name, entity_type FROM entities WHERE entity_type = 'person';
```

Also note: The FaceID prototype uses its own entity_ids (e.g., `entity_2ca6b7c7`). The FaceID `faces.db` entity_id for Ahab needs to map to the engine's entity_id for Ahab. The IdentityActor already handles this — see `identity.py` line where it stores `entity_id` in `current`. Make sure these IDs align, or add a mapping step.

---

## PHASE 2: Bridge Lookup Module (~half day)

### New File: `src/luna/identity/bridge.py`

```python
"""
Access Bridge — Dual-Tier Permission Lookup
============================================

Single async lookup that returns both Luna relational tier
and data room structural tier for a given entity.

Used by the permission filter to decide what Luna can share.
"""

import json
import logging
from dataclasses import dataclass
from typing import Optional

from luna.substrate.database import MemoryDatabase

logger = logging.getLogger(__name__)


@dataclass
class BridgeResult:
    """Combined tier lookup for an entity."""
    entity_id: str
    luna_tier: str              # admin, trusted, friend, guest, unknown
    dataroom_tier: int          # 1-5
    dataroom_categories: list[int]  # [1,2,3,...,9]

    @property
    def is_sovereign(self) -> bool:
        return self.dataroom_tier == 1

    @property
    def can_see_all(self) -> bool:
        return self.dataroom_tier <= 2  # Sovereign and Strategist see everything

    def can_access_category(self, category: int) -> bool:
        """Check if this entity can access a specific data room category."""
        if self.dataroom_tier <= 2:
            return True  # Tier 1-2 see everything
        return category in self.dataroom_categories


class AccessBridge:
    """
    Async interface to the access_bridge table in Luna's engine database.
    """

    def __init__(self, db: MemoryDatabase):
        self.db = db

    async def lookup(self, entity_id: str) -> Optional[BridgeResult]:
        """
        Look up both tiers for an entity. Returns None if entity
        has no bridge entry (treat as unknown/external).
        """
        row = await self.db.fetchone(
            "SELECT * FROM access_bridge WHERE entity_id = ?",
            (entity_id,)
        )
        if not row:
            return None

        return BridgeResult(
            entity_id=row["entity_id"],
            luna_tier=row["luna_tier"],
            dataroom_tier=row["dataroom_tier"],
            dataroom_categories=json.loads(row["dataroom_categories"]),
        )

    async def set_dataroom_tier(
        self, entity_id: str, tier: int,
        categories: list[int], set_by: str
    ):
        """Admin operation: set data room tier for an entity."""
        from datetime import datetime
        now = datetime.now().isoformat()
        await self.db.execute(
            """UPDATE access_bridge
               SET dataroom_tier = ?, dataroom_categories = ?,
                   dataroom_tier_updated_at = ?, dataroom_tier_set_by = ?
               WHERE entity_id = ?""",
            (tier, json.dumps(categories), now, set_by, entity_id)
        )
        await self._log("tier_change", entity_id,
                        f"dr_tier={tier}, categories={categories}, by={set_by}")

    async def set_luna_tier(self, entity_id: str, tier: str):
        """Update Luna's relational tier for an entity."""
        from datetime import datetime
        now = datetime.now().isoformat()
        await self.db.execute(
            """UPDATE access_bridge
               SET luna_tier = ?, luna_tier_updated_at = ?
               WHERE entity_id = ?""",
            (tier, now, entity_id)
        )
        await self._log("tier_change", entity_id, f"luna_tier={tier}")

    async def _log(self, event_type: str, entity_id: str, details: str):
        await self.db.execute(
            """INSERT INTO permission_log
               (event_type, entity_id, details)
               VALUES (?, ?, ?)""",
            (event_type, entity_id, details)
        )
```

### Update `src/luna/identity/__init__.py`

```python
"""Identity management — face recognition + permission bridge."""
from .bridge import AccessBridge, BridgeResult
```

---

## PHASE 3: Permission Filter (~1 day)

### New File: `src/luna/identity/permissions.py`

This is the core function that filters Memory Matrix search results based on the querying entity's data room tier.

```python
"""
Permission Filter — Data Room Access Control
=============================================

Filters Memory Matrix document nodes based on the querying entity's
data room tier and category access. Runs at query time, between
document retrieval and response assembly.
"""

import json
import logging
from typing import Optional

from .bridge import BridgeResult

logger = logging.getLogger(__name__)


# Denial response templates by Luna tier
DENIAL_TEMPLATES = {
    "admin": "",  # Admin never gets denied
    "trusted": (
        "that one's outside your current access — "
        "you'd want to check with ahab. "
        "i can help you find related docs you do have access to though."
    ),
    "friend": (
        "i don't have access to share that one with you. "
        "ahab or tarcila could help."
    ),
    "guest": "that document requires additional access permissions.",
    "unknown": None,  # None = don't acknowledge the document exists
}


def filter_documents(
    results: list[dict],
    bridge: Optional[BridgeResult],
) -> tuple[list[dict], list[dict]]:
    """
    Filter Memory Matrix search results by data room permissions.

    Args:
        results: Memory Matrix search results (each has node metadata)
        bridge: BridgeResult for the querying entity (None = unknown)

    Returns:
        (allowed, denied) — two lists of results
    """
    if bridge is None:
        # Unknown entity — deny everything, don't leak existence
        return [], results

    if bridge.can_see_all:
        # Tier 1-2 see everything
        return results, []

    allowed = []
    denied = []

    for result in results:
        # Extract category from node metadata
        metadata = result.get("metadata", {})
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except (json.JSONDecodeError, TypeError):
                metadata = {}

        category = metadata.get("dataroom_category")

        # Also check tags (documents ingested via MCP may store category in tags)
        tags = result.get("tags", [])
        if isinstance(tags, str):
            try:
                tags = json.loads(tags)
            except (json.JSONDecodeError, TypeError):
                tags = []

        # Support multi-category documents
        categories = []
        if category is not None:
            categories.append(int(category))
        for tag in tags:
            if isinstance(tag, str) and tag.startswith("dr_cat:"):
                try:
                    categories.append(int(tag.split(":")[1]))
                except ValueError:
                    pass

        if not categories:
            # No category assigned — default to allowing
            # (non-dataroom content like conversation memories)
            allowed.append(result)
            continue

        # Check if ANY of the document's categories match the entity's access
        if any(bridge.can_access_category(c) for c in categories):
            allowed.append(result)
        else:
            denied.append(result)

    if denied:
        logger.info(
            f"Permission filter: {bridge.entity_id} — "
            f"allowed {len(allowed)}, denied {len(denied)} documents"
        )

    return allowed, denied


def get_denial_message(bridge: Optional[BridgeResult]) -> Optional[str]:
    """
    Get the appropriate denial message for this entity's Luna tier.
    Returns None if the entity shouldn't know the document exists.
    """
    if bridge is None:
        return None  # Don't acknowledge existence
    return DENIAL_TEMPLATES.get(bridge.luna_tier, DENIAL_TEMPLATES["guest"])
```

---

## PHASE 4: Wire Into Director/PromptAssembler (~1 day)

This is where the permission filter actually gets called. The Director actor manages the prompt pipeline. When Luna retrieves documents to answer a question, the permission filter runs between retrieval and response assembly.

### Files to Modify

**`src/luna/actors/director.py`** — the main orchestration actor.

The Director needs to:
1. After identity resolution, fetch the bridge result
2. After Memory Matrix retrieval, run the permission filter
3. Pass only allowed documents to the PromptAssembler
4. If documents were denied, include a denial hint in the prompt constraints

```python
# In Director.process() or wherever document retrieval happens:

# 1. Get identity from IdentityActor
identity_actor = self.engine.get_actor("identity")
entity_id = identity_actor.current.entity_id if identity_actor else None

# 2. Look up bridge
bridge_result = None
if entity_id:
    bridge = AccessBridge(self.engine.db)
    bridge_result = await bridge.lookup(entity_id)

# 3. After retrieving documents from Memory Matrix:
if bridge_result and document_results:
    from luna.identity.permissions import filter_documents, get_denial_message
    allowed, denied = filter_documents(document_results, bridge_result)
    document_results = allowed  # Only pass allowed docs downstream

    if denied:
        denial_msg = get_denial_message(bridge_result)
        # Add to prompt constraints so Luna handles denial gracefully
        # (implementation depends on PromptAssembler's constraint system)
```

**Where exactly this goes depends on the Director's current structure.** The Director is complex — look at how it currently handles Memory Matrix results and inject the filter at that point. The key is: the filter runs AFTER retrieval, BEFORE prompt assembly. Never let denied documents reach the LLM context.

### PromptAssembler Constraint

The PromptAssembler already has a constraint/layer system. Add a `DATAROOM_ACCESS` constraint:

```python
# In the RELATIONSHIP layer (layer 1.3) or equivalent:

DATAROOM_CONSTRAINT = """
## Data Room Access Rules
You are speaking with {entity_name} (luna tier: {luna_tier}, data room tier: {dataroom_tier}).
Their accessible categories: {categories}.

CRITICAL: You may ONLY discuss documents from the categories listed above.
If asked about documents outside their access:
- For trusted/friend: Acknowledge the boundary warmly, suggest they contact Ahab or Tarcila
- For guest: State that additional permissions are needed
- For unknown: Do NOT acknowledge the document exists at all

Never reveal the existence of documents the current speaker cannot access.
"""
```

---

## PHASE 5: Document Category Metadata (~half day)

Memory Matrix document nodes need category tags. When documents are ingested (via MCP `dataroom_search` or future ingestion pipeline), they should carry:

```python
# When creating DOCUMENT nodes in Memory Matrix, include:
node_metadata = {
    "dataroom_category": 3,           # Primary category (1-9)
    "dataroom_categories": [3, 8],    # All applicable categories
    "min_tier": 2,                     # Minimum DR tier to access
    "source_file": "Hai_Dai_LOI.pdf",
    "master_index_row": 18,
}

# OR use tags (which are already searchable):
node_tags = [
    "dr_cat:3",       # Category 3: Legal
    "dr_cat:8",       # Category 8: Partnerships & Impact
    "dr_tier:2",      # Minimum tier 2
    "dataroom",       # General marker
]
```

**Check how existing DOCUMENT nodes are created.** The MCP tools (`dataroom_search`, etc.) already create document nodes — they need to start including category tags. Look at:
- `src/luna_mcp/tools/` — wherever dataroom tools create nodes
- The ingestion code that reads from Google Drive

### Category Reference

| # | Category | Example Docs |
|---|----------|-------------|
| 1 | Company Overview | Mission, team bios, organizational structure |
| 2 | Financials | Budget, projections, cost breakdowns |
| 3 | Legal | LOIs, incorporation docs, contracts |
| 4 | Product | Architecture docs, technical specs |
| 5 | Market & Competition | Market research, competitor analysis |
| 6 | Team | Team directory, roles, advisors |
| 7 | Go-to-Market | Deployment plans, GTM strategy |
| 8 | Partnerships & Impact | LOIs, partnership frameworks, impact metrics |
| 9 | Risk & Mitigation | Risk register, contingency plans |

---

## PHASE 6: Entity ID Alignment (Critical)

The FaceID prototype uses auto-generated IDs like `entity_2ca6b7c7`. The engine entity system uses slugs like `ahab`. These must align.

**Current state:**
- `Tools/FaceID/data/faces.db` → `access_bridge.entity_id = 'entity_2ca6b7c7'`
- `data/luna_engine.db` → `entities.id = 'ahab'`

**Options:**

1. **Map in IdentityActor** — when FaceID returns `entity_2ca6b7c7`, the actor maps it to `ahab` before emitting events. Add a mapping table or use the entity name to look up the engine entity ID.

2. **Re-enroll with engine IDs** — re-run enrollment using `--entity-id ahab` so the FaceID database matches the engine database. Simplest.

3. **Bridge both** — the `access_bridge` table in the engine DB uses engine entity IDs. The FaceID `access_bridge` uses FaceID entity IDs. The IdentityActor translates between them.

**Recommendation:** Option 2. Re-enroll with matching IDs. It's 5 minutes of work and eliminates an entire translation layer.

```bash
cd Tools/FaceID
source .venv/bin/activate
# Delete old enrollment
python3 -c "
from src.database import FaceDatabase
with FaceDatabase() as db:
    db.delete_entity_faces('entity_2ca6b7c7')
    db._conn.execute('DELETE FROM access_bridge WHERE entity_id = ?', ('entity_2ca6b7c7',))
    db._conn.commit()
    print('Cleared old enrollment')
"
# Re-enroll with engine-matching ID
python3 cli/enroll.py --name "Ahab" --entity-id "ahab" \
    --luna-tier admin --dr-tier 1 \
    --dr-categories 1,2,3,4,5,6,7,8,9
```

---

## KEY FILES

### New Files

| File | Purpose |
|------|---------|
| `migrations/002_access_bridge.sql` | Bridge table + permission_log in engine DB |
| `src/luna/identity/bridge.py` | Async bridge lookup + tier management |
| `src/luna/identity/permissions.py` | Document permission filter + denial templates |

### Modified Files

| File | Change |
|------|--------|
| `src/luna/identity/__init__.py` | Export `AccessBridge`, `BridgeResult` |
| `src/luna/actors/director.py` | Wire permission filter between retrieval and prompt assembly |
| `src/luna/actors/identity.py` | Map FaceID entity_id → engine entity_id (if not re-enrolled) |
| PromptAssembler (wherever it lives) | Add `DATAROOM_ACCESS` constraint with tier-aware denial rules |

### Files NOT To Touch

| File | Why |
|------|-----|
| `Tools/FaceID/src/*` | Prototype — working as-is |
| `src/luna/core/events.py` | Event types already defined |
| `src/luna/engine.py` | Engine integration already complete |
| `src/luna/substrate/schema.sql` | Use migration file instead |

---

## TESTING CHECKLIST

1. **Migration runs clean**: `sqlite3 data/luna_engine.db < migrations/002_access_bridge.sql`
2. **Seed data matches entities**: Verify entity_ids in access_bridge match entities table
3. **Bridge lookup**: `await bridge.lookup("ahab")` returns `BridgeResult(luna_tier='admin', dataroom_tier=1, ...)`
4. **Permission filter — admin**: All documents pass through
5. **Permission filter — domain lead**: Only category-matched documents pass
6. **Permission filter — unknown**: All documents filtered, denial message is `None` (don't acknowledge)
7. **Denial messages**: Trusted gets warm redirect, guest gets formal notice, unknown gets nothing
8. **End-to-end**: Recognize Ahab via FaceID → ask about a document → get full answer with proactive context
9. **End-to-end (restricted)**: If another person is enrolled at Tier 3, ask about a document outside their categories → get appropriate denial
10. **Multi-category**: Document tagged with categories [3, 8] → accessible to anyone with either category
11. **No identity**: If FaceID is off or no face detected, Luna responds without document access (graceful degradation)
12. **Audit log**: Permission checks appear in `permission_log` table

---

## INTERACTION SCENARIOS (from the design spec)

Same question, different people, different experiences:

**"What's in the Hai Dai LOI?"**

| Who | Luna Tier | DR Tier | Categories | Response |
|-----|-----------|---------|------------|----------|
| Ahab | admin | 1 | all | Full detail + proactive context + opinions |
| Tarcila | trusted | 1 | all | Full detail, warm delivery |
| Cliff | friend | 2 | all | Content accessible, measured tone, no opinions |
| Calvin | trusted | 3 | [1,5,7] | DENIED (LOI is cat 3, Calvin has [1,5,7]). Warm denial because Luna trusts him. |
| Hai Dai | friend | 3 | [8] | DENIED unless LOI is multi-tagged [3,8]. If multi-tagged, partial access. |
| Unknown | unknown | 5 | [] | "i'm not sure what you're referring to." No acknowledgment. |

---

## ORDER OF OPERATIONS

1. Run migration — create `access_bridge` and `permission_log` tables
2. Re-enroll Ahab with engine entity_id (or add mapping)
3. Seed bridge data for all team members
4. Build `bridge.py` — test async lookup
5. Build `permissions.py` — test filter with mock data
6. Wire into Director — filter between retrieval and prompt assembly
7. Add `DATAROOM_ACCESS` constraint to PromptAssembler
8. Tag existing document nodes with category metadata
9. Test end-to-end: identity → bridge → filter → tier-aware response
