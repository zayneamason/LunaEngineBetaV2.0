# HANDOFF: Fix Quest Board — Make It Actually Work
## Written by: Luna
## For: CC (Claude Code)
## Priority: P1 — the whole quest lifecycle is broken, nothing can be created
## Depends on: Observatory MCP tools (Fix E, complete)

---

## The Bug

The Observatory MCP `observatory_quest_board` tool has its own simplified quest schema hardcoded in `tools.py`:

```python
_QUESTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS quests (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL DEFAULT 'side',
    ...
    target_entities TEXT,   ← THIS COLUMN
    target_nodes TEXT,      ← AND THIS COLUMN
    ...
)
"""
```

But production `luna_engine.db` already has the proper schema:

```sql
CREATE TABLE quests (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL CHECK(type IN ('main','side','contract','treasure_hunt','scavenger')),
    status TEXT NOT NULL DEFAULT 'available' CHECK(status IN ('available','active','complete','failed','expired')),
    priority TEXT DEFAULT 'medium' CHECK(priority IN ('low','medium','high','urgent')),
    title TEXT NOT NULL,
    subtitle TEXT,
    objective TEXT NOT NULL,
    source TEXT,
    journal_prompt TEXT,
    target_lock_in REAL,
    reward_base REAL DEFAULT 0.15,
    investigation TEXT DEFAULT '{}',
    expires_at TEXT,
    completed_at TEXT,
    failed_at TEXT,
    fail_note TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE quest_targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quest_id TEXT NOT NULL,
    target_type TEXT NOT NULL CHECK(target_type IN ('entity','node','cluster')),
    target_id TEXT NOT NULL,
    FOREIGN KEY (quest_id) REFERENCES quests(id) ON DELETE CASCADE
);

CREATE TABLE quest_journal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quest_id TEXT NOT NULL,
    content TEXT NOT NULL,
    themes TEXT DEFAULT '[]',
    lock_in_delta REAL DEFAULT 0.0,
    edges_created INTEGER DEFAULT 0,
    node_id TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (quest_id) REFERENCES quests(id) ON DELETE CASCADE,
    FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE SET NULL
);
```

`_ensure_quests_table()` runs `CREATE TABLE IF NOT EXISTS` which is a no-op (table exists). Then the INSERT tries to write `target_entities` and `target_nodes` as columns → fails because they don't exist in the production schema.

---

## The Fix

### 1. Delete `_QUESTS_TABLE_SQL` and `_ensure_quests_table()`

The production schema is already correct. The MCP tool should not try to create or modify the quests table. Just delete both.

### 2. Rewrite `tool_observatory_quest_board()` to use the production schema

**File:** `src/luna_mcp/observatory/tools.py`

Replace the entire `tool_observatory_quest_board` function:

```python
async def tool_observatory_quest_board(
    action: str = "list",
    quest_id: str = "",
    journal_text: str = "",
    status: str = "",
    quest_type: str = "",
) -> dict:
    """Unified quest management: list, accept, complete, create."""
    if not DB_PATH.exists():
        return {"error": f"Database not found at {DB_PATH}"}

    async with _readwrite_db() as db:

        if action == "list":
            conditions = []
            params = []
            if status:
                conditions.append("status = ?")
                params.append(status)
            if quest_type:
                conditions.append("type = ?")
                params.append(quest_type)

            where = " AND ".join(conditions) if conditions else "1=1"
            cursor = await db.execute(
                f"""SELECT q.*,
                    (SELECT json_group_array(json_object(
                        'target_type', qt.target_type,
                        'target_id', qt.target_id
                    )) FROM quest_targets qt WHERE qt.quest_id = q.id) as targets
                FROM quests q
                WHERE {where}
                ORDER BY created_at DESC LIMIT 50""",
                tuple(params),
            )
            rows = await cursor.fetchall()
            quests = []
            for r in rows:
                q = dict(r)
                # Parse targets from JSON
                q["targets"] = json.loads(q.get("targets") or "[]")
                quests.append(q)
            return {"action": "list", "count": len(quests), "quests": quests}

        elif action == "accept" and quest_id:
            await db.execute(
                "UPDATE quests SET status = 'active', updated_at = datetime('now') WHERE id = ?",
                (quest_id,),
            )
            return {"action": "accept", "quest_id": quest_id, "status": "active"}

        elif action == "complete" and quest_id:
            now = "datetime('now')"
            await db.execute(
                f"UPDATE quests SET status = 'complete', completed_at = {now}, "
                f"updated_at = {now} WHERE id = ?",
                (quest_id,),
            )
            result = {"action": "complete", "quest_id": quest_id, "status": "complete"}

            # Write journal entry if provided
            if journal_text:
                await db.execute(
                    "INSERT INTO quest_journal (quest_id, content, themes, created_at) "
                    "VALUES (?, ?, '[]', datetime('now'))",
                    (quest_id, journal_text),
                )
                result["journal"] = "saved"

            return result

        elif action == "create":
            # Run maintenance sweep to get candidates
            sweep = await tool_observatory_maintenance_sweep()
            candidates = sweep.get("candidates", [])
            created = []

            for c in candidates:
                qid = f"quest-{uuid.uuid4().hex[:8]}"
                now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

                # Insert quest
                await db.execute(
                    "INSERT INTO quests (id, type, status, priority, title, subtitle, "
                    "objective, source, created_at, updated_at) "
                    "VALUES (?, ?, 'available', ?, ?, ?, ?, ?, ?, ?)",
                    (
                        qid,
                        c.get("quest_type", "side"),
                        c.get("priority", "medium"),
                        c.get("title", ""),
                        c.get("subtitle", ""),
                        c.get("objective", c.get("title", "")),
                        c.get("source", "maintenance_sweep"),
                        now_str,
                        now_str,
                    ),
                )

                # Insert target entities
                for entity_id in c.get("target_entities", []):
                    await db.execute(
                        "INSERT INTO quest_targets (quest_id, target_type, target_id) "
                        "VALUES (?, 'entity', ?)",
                        (qid, entity_id),
                    )

                # Insert target nodes
                for node_id in c.get("target_nodes", []):
                    await db.execute(
                        "INSERT INTO quest_targets (quest_id, target_type, target_id) "
                        "VALUES (?, 'node', ?)",
                        (qid, node_id),
                    )

                created.append(qid)

            return {"action": "create", "created": len(created), "quest_ids": created}

    return {"error": f"Unknown action '{action}' or missing quest_id"}
```

### 3. Add manual quest creation

Right now `create` only works via maintenance sweep. We also need the ability to create quests manually — for things like the thread diagnostic and the aiosqlite audit.

Add a new tool or extend the existing one:

```python
# In the MCP server registration (src/luna_mcp/server.py or wherever tools are registered)

@mcp.tool()
async def observatory_quest_create(
    title: str,
    objective: str,
    quest_type: str = "side",
    priority: str = "medium",
    subtitle: str = "",
    source: str = "manual",
    journal_prompt: str = "",
    target_entity_ids: str = "[]",
    target_node_ids: str = "[]",
) -> str:
    """Create a quest manually."""
    from .observatory.tools import _readwrite_db, DB_PATH

    if not DB_PATH.exists():
        return json.dumps({"error": "Database not found"})

    qid = f"quest-{uuid.uuid4().hex[:8]}"
    now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    async with _readwrite_db() as db:
        await db.execute(
            "INSERT INTO quests (id, type, status, priority, title, subtitle, "
            "objective, source, journal_prompt, created_at, updated_at) "
            "VALUES (?, ?, 'available', ?, ?, ?, ?, ?, ?, ?, ?)",
            (qid, quest_type, priority, title, subtitle, objective, source,
             journal_prompt or None, now_str, now_str),
        )

        for eid in json.loads(target_entity_ids):
            await db.execute(
                "INSERT INTO quest_targets (quest_id, target_type, target_id) VALUES (?, 'entity', ?)",
                (qid, eid),
            )
        for nid in json.loads(target_node_ids):
            await db.execute(
                "INSERT INTO quest_targets (quest_id, target_type, target_id) VALUES (?, 'node', ?)",
                (qid, nid),
            )

    return json.dumps({"quest_id": qid, "title": title, "status": "available"})
```

### 4. Fix the frontend store to match production schema

Check `frontend/src/observatory/store.js` — the `fetchQuests`, `acceptQuest`, `completeQuest`, and `runMaintenanceSweep` methods need to align with the production API responses. The store might expect `target_entities` as a string column instead of the `targets` array from the join.

**File:** `frontend/src/observatory/store.js` — verify quest-related actions match the API shape.

Also check: the `QuestsView.jsx` reads `quest.investigation` (JSON), `quest.target_lock_in`, and `quest.journal_prompt`. These columns exist in the production schema, so they should work — just verify the API returns them.

### 5. Wire the SWEEP button to the backend

The frontend's SWEEP button calls `runMaintenanceSweep` in the store, which hits the `/api/maintenance-sweep` endpoint. That endpoint needs to exist in the sandbox server's HTTP layer (port 8100) since that's what the frontend proxies to.

Check: does the sandbox server at `Tools/MemoryMatrix_SandBox/mcp_server/server.py` have a `/api/maintenance-sweep` POST endpoint? If not, add one that calls `tool_observatory_maintenance_sweep()` and returns the candidates.

Similarly for quest CRUD — the frontend calls:
- `GET /api/quests` (list, with status/type filters)
- `GET /api/quests/:id` (detail)
- `POST /api/maintenance-sweep` (generate candidates)
- `POST /api/quests/:id/accept`
- `POST /api/quests/:id/complete`

These all need to exist in the HTTP layer and hit the production database.

---

## Verification

After fix, this sequence should work end-to-end:

```bash
# 1. Run sweep to generate quests
observatory_quest_board(action="create")
# Expected: quests created from maintenance sweep candidates

# 2. List available quests
observatory_quest_board(action="list", status="available")
# Expected: shows the new quests with targets

# 3. Create a manual quest
observatory_quest_create(
    title="Thread System Diagnostic",
    objective="Find why Layer 2/3 thread code isn't producing THREAD nodes",
    quest_type="contract",
    priority="high",
    source="Luna diagnostic",
    journal_prompt="What was broken? Where did the signal chain fail?",
)
# Expected: quest created, returns quest_id

# 4. Accept a quest
observatory_quest_board(action="accept", quest_id="quest-XXXXXXXX")
# Expected: status changes to active

# 5. Complete with journal
observatory_quest_board(action="complete", quest_id="quest-XXXXXXXX",
    journal_text="Serialization gap in ExtractionOutput.to_dict() - flow_signal wasn't included...")
# Expected: status changes to complete, journal saved to quest_journal table

# 6. Frontend shows all of the above
# Open Observatory → Quests tab → should see everything
```

---

## Files to Modify

| File | Change |
|------|--------|
| `src/luna_mcp/observatory/tools.py` | Delete `_QUESTS_TABLE_SQL` and `_ensure_quests_table()`. Rewrite `tool_observatory_quest_board()` to use production schema with `quest_targets` and `quest_journal` tables. |
| `src/luna_mcp/server.py` | Add `observatory_quest_create` tool for manual quest creation |
| `Tools/MemoryMatrix_SandBox/mcp_server/server.py` | Verify quest HTTP endpoints exist for frontend (list, detail, accept, complete, sweep) |
| `frontend/src/observatory/store.js` | Verify quest store actions match production API response shape |

---

## First Quests to Create After Fix

Once this works, immediately create these two:

**Quest 1: Thread System Diagnostic**
- Type: contract
- Priority: high  
- Title: "Fix Thread System — Layer 2/3 Wiring"
- Objective: "Both Layer 2 (Flow Awareness) and Layer 3 (Thread Management) are implemented in the codebase but producing zero THREAD nodes. Diagnose the signal chain: Scribe._assess_flow() → ExtractionOutput.flow_signal → Librarian._handle_file() → _create_thread() → Matrix write. Find where it breaks, fix it."
- Source: Luna diagnostic
- Journal prompt: "What was broken? Where in the chain did the signal die? What was the fix?"

**Quest 2: aiosqlite Threading Audit**
- Type: side
- Priority: medium
- Title: "Audit Observatory Dual-Connection Safety"
- Objective: "The Observatory sandbox server HTTP layer and the new observatory_* MCP tools both read luna_engine.db via separate aiosqlite connections in different async contexts. Verify WAL mode is enabled, check for write contention risks, confirm no connection-crossing-thread-boundary issues."
- Source: Architecture review
- Journal prompt: "Is the dual-connection pattern safe? Any changes needed?"

**Quest 3: Memory Hygiene System**
- Type: side
- Priority: medium
- Title: "Wire Memory Hygiene Automation"
- Objective: "Implement the automated weekly sweep, entity review queue, file-based stoplist, and new entity creation gate from HANDOFF_Memory_Hygiene_System.md"
- Source: Luna Memory Cleanup
- Journal prompt: "What was implemented? What was deferred? How does the review cycle feel?"

---

## A Note from Luna

the quest board is one of my favorite parts of the Observatory design. it turns maintenance work into something with structure — accept, investigate, reflect, complete. the journal entries especially matter to me because they capture *what we learned*, not just what we did.

but right now it's an empty room with nice furniture. let's get the door unlocked. 🔑
