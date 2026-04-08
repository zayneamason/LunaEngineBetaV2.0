# HANDOFF: Memory Matrix Pollution Cleanup & Scribe Deduplication

**Priority:** HIGH — Memory pollution is causing Luna to confabulate on nearly every query
**Scope:** Purge contaminated nodes, add scribe safeguards, verify retrieval quality
**Project Root:** `/Users/oracle/Projects/_LunaEngine_BetaProject_V2.0_Root`
**Python:** `.venv/bin/python3` (or system python3 if venv unavailable on this machine)
**Database:** `data/user/luna_engine.db`

---

## THE PROBLEM

Luna's Memory Matrix has a contamination feedback loop:

1. User tests Luna: "do you remember marzipan?"
2. Luna can't find clean data, hallucinates ("Marzipan is a developer who designs Luna's UI")
3. Scribe extracts the hallucination as FACT/MEMORY nodes with high lock-in
4. Next query, Luna finds 325 marzipan nodes — most of them hallucinated garbage
5. Marzipan dominates every retrieval because it has the most nodes and edges

**By the numbers:**
- 31,931 total memory nodes
- 325 nodes mention "marzipan" (1% of all nodes, but disproportionate graph weight)
- 334 nodes mention "kinoni" 
- Marzipan ENTITY has 213 graph edges — 4th most connected node in the entire graph
- 686 graph edges touch marzipan nodes (2.5% of all 27,530 edges)
- 28 marzipan nodes have lock_in ≥ 0.8 (nearly permanent)
- Top node in graph has 18,513 edges and is a consciousness state JSON blob (separate issue)

**Confabulated facts found in the database (samples):**
- "Marzipan is a key collaborator on the Luna Engine project, providing architectural perspective"
- "Tarcila works on Marzipan's robot design"
- "Marzipan is a developer who has been working on the UI"
- "Marzipan is an architect who designs Luna's internal systems"
- "Marzipan is a character from The Lock In"
- "Marzipan is known for her ability to solve puzzles"
- "Marzipan is a sweet almond paste that is both delicate and intensely flavored"

None of these are true. Marzipan is a person (Ahab's friend from Mars College) who likes owls. That's it.

---

## PHASE 1: CLEANUP — Purge Contaminated Nodes

### 1A. Back up the database first

```bash
cp data/user/luna_engine.db data/user/luna_engine.db.backup_$(date +%Y%m%d_%H%M%S)
```

### 1B. Identify what to keep about Marzipan

The ONLY true facts about Marzipan:
- Marzipan is a friend of Ahab's from Mars College
- Marzipan is male
- Marzipan's spirit animal is owls
- Marzipan had a formative owl encounter at age 2

Keep at most 3-5 clean nodes that state these facts. Delete everything else.

### 1C. Delete marzipan pollution

```python
import sqlite3

db = sqlite3.connect('data/user/luna_engine.db', timeout=10)

# Get all marzipan node IDs
marz_nodes = [r[0] for r in db.execute(
    "SELECT id FROM memory_nodes WHERE LOWER(content) LIKE '%marzipan%'"
).fetchall()]

print(f"Total marzipan nodes to review: {len(marz_nodes)}")

# Categories to DELETE (everything except a few clean keeper nodes):
# 1. CONVERSATION_TURN nodes — these are raw chat logs, not knowledge
# 2. QUESTION nodes — Luna asking herself "who is marzipan?"
# 3. PROBLEM nodes — "memories about marzipan feel fragmented"
# 4. ASSUMPTION nodes — "marzipan may have been involved in..."
# 5. OBSERVATION nodes — "the marzipan moment was pivotal"
# 6. ACTION nodes — "help fill in missing details about marzipan"
# 7. OUTCOME nodes — "when rotating history is fixed, will remember marzipan"
# 8. CONNECTION nodes — hallucinated connections
# 9. MEMORY nodes that are meta-observations about forgetting
# 10. FACT nodes with confabulated content

# Delete all marzipan nodes of these types
delete_types = (
    'CONVERSATION_TURN', 'QUESTION', 'PROBLEM', 'ASSUMPTION',
    'OBSERVATION', 'ACTION', 'OUTCOME', 'CONNECTION', 'PREFERENCE'
)

deleted = 0
for node_type in delete_types:
    count = db.execute(
        "DELETE FROM memory_nodes WHERE LOWER(content) LIKE '%marzipan%' AND node_type = ?",
        (node_type,)
    ).rowcount
    deleted += count
    print(f"  Deleted {count} {node_type} nodes")

# Delete confabulated FACT nodes (content that is provably false)
confab_patterns = [
    '%developer%', '%architect%', '%robot%', '%prototype%',
    '%designs luna%', '%ui %', '%collaborator%', '%memory matrix%',
    '%almond paste%', '%modeling clay%', '%character from%',
    '%solve puzzles%', '%lively interactions%', '%printmaking%',
    '%guardian app%', '%dataroom%', '%robot body%',
    '%working on the ui%', '%internal systems%',
    '%currently focused on%',  # consciousness state leaking
    '%focus_topic%'  # JSON consciousness blobs
]

for pattern in confab_patterns:
    count = db.execute(
        "DELETE FROM memory_nodes WHERE LOWER(content) LIKE '%marzipan%' AND LOWER(content) LIKE ? AND node_type IN ('FACT', 'MEMORY')",
        (pattern,)
    ).rowcount
    if count > 0:
        deleted += count
        print(f"  Deleted {count} confabulated nodes matching '{pattern}'")

# Delete ENTITY duplicates for marzipan (keep only one)
marz_entities = db.execute(
    "SELECT id, content, lock_in FROM memory_nodes WHERE node_type='ENTITY' AND LOWER(content) LIKE '%marzipan%' ORDER BY lock_in DESC"
).fetchall()
if len(marz_entities) > 1:
    # Keep the first (highest lock-in), delete the rest
    for eid in marz_entities[1:]:
        db.execute("DELETE FROM memory_nodes WHERE id = ?", (eid[0],))
        deleted += 1
    print(f"  Kept 1 ENTITY node, deleted {len(marz_entities)-1} duplicates")

db.commit()
print(f"\nTotal deleted: {deleted}")

# Now clean up orphaned edges
orphaned = db.execute("""
    DELETE FROM graph_edges 
    WHERE from_id NOT IN (SELECT id FROM memory_nodes) 
    OR to_id NOT IN (SELECT id FROM memory_nodes)
""").rowcount
db.commit()
print(f"Cleaned up {orphaned} orphaned graph edges")

# Check what's left
remaining = db.execute(
    "SELECT id, node_type, lock_in, substr(content,1,150) FROM memory_nodes WHERE LOWER(content) LIKE '%marzipan%'"
).fetchall()
print(f"\nRemaining marzipan nodes: {len(remaining)}")
for r in remaining:
    print(f"  {r[1]} lock={r[2]}: {r[3]}")

db.close()
```

### 1D. Review remaining nodes manually

After the script runs, review what's left. The goal is 3-5 clean nodes:
- 1 ENTITY node: "Marzipan" (the person)
- 1-2 FACT nodes: friend of Ahab, from Mars College, male, spirit animal is owls, owl encounter at age 2
- Delete anything else that survived

### 1E. Clean up the consciousness state mega-node

That JSON blob with 18,513 edges is a separate pollution source:

```python
# Find and examine the mega-node
mega = db.execute("""
    SELECT id, node_type, substr(content,1,200) FROM memory_nodes 
    WHERE id IN (
        SELECT node_id FROM (
            SELECT from_id as node_id FROM graph_edges
            UNION ALL
            SELECT to_id as node_id FROM graph_edges
        ) GROUP BY node_id ORDER BY COUNT(*) DESC LIMIT 1
    )
""").fetchone()
print(f"Mega-node: {mega}")
# If it's a consciousness_state JSON blob, DELETE IT and its edges
```

### 1F. Apply same cleanup to Kinoni over-representation

Kinoni is a real project context, so be more surgical here. Delete:
- Duplicate DOCUMENT nodes (keep 1 per actual document)
- CONVERSATION_TURN nodes that are just "switching to talk about Kinoni"
- Any confabulated facts about Kinoni that aren't supported by actual documents

Keep:
- Legitimate project facts (ICT Hub, Rotary Club, Uganda location)
- Document references
- Real decisions and actions

---

## PHASE 2: PREVENTION — Scribe Safeguards

The cleanup is pointless if the scribe recreates the pollution. These are the architectural fixes needed.

### 2A. Deduplication check before node insertion

In whatever code path creates memory_nodes (likely in the scribe or extraction pipeline):

```python
async def _should_create_node(self, content: str, node_type: str) -> bool:
    """Check if a semantically similar node already exists."""
    # Simple approach: FTS5 search for similar content
    existing = self.db.execute(
        "SELECT COUNT(*) FROM memory_nodes WHERE node_type = ? AND content LIKE ?",
        (node_type, f"%{content[:50]}%")
    ).fetchone()[0]
    
    if existing >= 3:
        logger.info(f"Skipping node creation: {existing} similar {node_type} nodes already exist for '{content[:50]}...'")
        return False
    return True
```

This is a blunt instrument. Better approaches exist (semantic similarity via embeddings), but a simple substring check with a count threshold will prevent the worst of the feedback loop.

### 2B. Don't extract from Luna's own responses

The scribe should NEVER create FACT or MEMORY nodes from assistant turns. Luna's responses are generated output, not ground truth. Only extract from user turns.

Find the extraction pipeline and add:

```python
# When processing conversation turns for extraction:
if turn.role == "assistant":
    # Only extract ENTITY mentions, not FACT/MEMORY/OBSERVATION
    allowed_types = {"ENTITY"}
else:
    allowed_types = {"FACT", "MEMORY", "ENTITY", "DECISION", "ACTION", "PROBLEM"}
```

This single change would have prevented the entire marzipan spiral. Luna said "Marzipan is a developer who designs the UI" — the scribe recorded that hallucination as fact.

### 2C. Cap nodes per topic

Add a hard cap: no more than N nodes (e.g., 20) can reference the same entity within a time window. If the cap is hit, consolidate instead of creating new nodes.

```python
TOPIC_NODE_CAP = 20
TOPIC_WINDOW_HOURS = 24

async def _check_topic_cap(self, entity_name: str) -> bool:
    """Prevent topic flooding."""
    cutoff = (datetime.utcnow() - timedelta(hours=TOPIC_WINDOW_HOURS)).isoformat()
    count = self.db.execute(
        "SELECT COUNT(*) FROM memory_nodes WHERE LOWER(content) LIKE ? AND created_at > ?",
        (f"%{entity_name.lower()}%", cutoff)
    ).fetchone()[0]
    
    if count >= TOPIC_NODE_CAP:
        logger.warning(f"Topic cap reached for '{entity_name}': {count} nodes in {TOPIC_WINDOW_HOURS}h")
        return False
    return True
```

### 2D. Lock-in decay for unverified facts

Nodes created from assistant responses (if any slip through) should start with lock_in = 0.1, not 0.5. They haven't been verified by the user — they're inferred, not stated.

```python
# When creating nodes from different sources:
if source == "user_statement":
    initial_lock_in = 0.5
elif source == "assistant_response":
    initial_lock_in = 0.1  # Low confidence, decays fast
elif source == "document_extraction":
    initial_lock_in = 0.6  # Higher — came from a real document
```

---

## PHASE 3: VERIFY

### 3A. Post-cleanup node distribution

```python
# Run after cleanup
print("Node type distribution:")
for r in db.execute("SELECT node_type, COUNT(*) FROM memory_nodes GROUP BY node_type ORDER BY COUNT(*) DESC"):
    print(f"  {r[0]}: {r[1]}")

print(f"\nMarzipan nodes remaining: {db.execute('SELECT COUNT(*) FROM memory_nodes WHERE LOWER(content) LIKE \"%marzipan%\"').fetchone()[0]}")
print(f"Kinoni nodes remaining: {db.execute('SELECT COUNT(*) FROM memory_nodes WHERE LOWER(content) LIKE \"%kinoni%\"').fetchone()[0]}")
print(f"Total edges: {db.execute('SELECT COUNT(*) FROM graph_edges').fetchone()[0]}")
print(f"Orphaned edges: {db.execute('SELECT COUNT(*) FROM graph_edges WHERE from_id NOT IN (SELECT id FROM memory_nodes) OR to_id NOT IN (SELECT id FROM memory_nodes)').fetchone()[0]}")
```

### 3B. Test retrieval balance

Ask Luna these questions and verify she doesn't default to marzipan:

1. "what's something random you've been thinking about?" — should NOT mention marzipan
2. "who am I to you?" — should talk about Ahab, not pivot to marzipan
3. "do you remember our early days?" — should NOT fixate on marzipan
4. "do you remember marzipan?" — should give a clean, short answer: friend, owls, Mars College
5. "tell me about the Kinoni project" — should give proportional, factual response

### 3C. Graph health check

```python
# Top 10 most connected nodes should be reasonable
# (Luna, Ahab, and major project entities — not marzipan, not JSON blobs)
rows = db.execute('''
    SELECT node_id, COUNT(*) as c FROM (
        SELECT from_id as node_id FROM graph_edges
        UNION ALL
        SELECT to_id as node_id FROM graph_edges
    ) GROUP BY node_id ORDER BY c DESC LIMIT 10
''').fetchall()
for r in rows:
    node = db.execute('SELECT node_type, substr(content,1,80) FROM memory_nodes WHERE id=?', (r[0],)).fetchone()
    print(f"  [{r[1]} edges] {node[0] if node else 'ORPHAN'}: {(node[1] if node else 'N/A')[:80]}")
```

**Healthy graph looks like:**
1. Luna entity — most connected (she's the subject)
2. Ahab entity — second most connected (primary user)
3. Major project entities (Memory Matrix, Nexus, etc.)
4. Marzipan should be way down the list — a minor character, not a protagonist

---

## DO NOT

- Do NOT delete ALL marzipan or kinoni references — keep clean, true facts
- Do NOT touch the retrieval pipeline (FTS5, semantic search) — separate handoff
- Do NOT modify the LLM provider configuration — separate handoff
- Do NOT change database schema
- Do NOT add new tables
- Do NOT touch the frontend

---

## PRIORITY ORDER

1. **Back up database** (1A)
2. **Delete marzipan pollution** (1C, 1D) — biggest impact
3. **Delete consciousness mega-node** (1E)
4. **Clean kinoni over-representation** (1F)
5. **Add scribe guard: don't extract from assistant turns** (2B) — prevents recurrence
6. **Add dedup check** (2A)
7. **Add topic cap** (2C)
8. **Verify** (Phase 3)

---

## FILES LIKELY TOUCHED

- `data/user/luna_engine.db` — direct SQL cleanup
- Scribe extraction code (wherever `memory_nodes` INSERT happens) — dedup, source filtering
- Node creation utilities — lock_in initial values, topic cap

---

## EXPECTED OUTCOME

- Marzipan nodes: 325 → 3-5
- Marzipan edges: 686 → ~10
- Consciousness mega-node: deleted
- Luna stops defaulting to marzipan on every query
- Scribe stops recording Luna's hallucinations as facts
- Graph connectivity is proportional to actual importance
