# HANDOFF: Luna Knowledge Cartridge System

**Priority:** P0 — Core architectural change, blocks investor demo depth  
**Date:** 2026-03-24  
**Scope:** Schema extension + migration + retrieval fix  
**Depends on:** Nothing — this is self-contained  
**Time estimate:** Phase 1: 45 min, Phase 2: 30 min, Phase 3: 20 min, Phase 4: design decision  

---

## The Concept

A **cartridge** is a single document, fully digested, in a single SQLite file. It contains everything Luna needs to *know* that document: the raw text, the search indexes, the Scribe extractions, the entities — plus sovereignty layers that no other AI system carries: access protocols set by the community, Luna's own reflections, human annotations, cross-references to other cartridges, and a reading log.

The cartridge is sovereign. Copy the file to a USB drive. Hand it to someone. Their Luna reads it. Pull the cartridge — the knowledge is gone. No cloud. No residue. No server.

**Current state:** Documents are bundled into shared collections (`research_library.db` holds multiple documents). The engine already has a plugin discovery system that scans `collections/` for cartridge folders with `manifest.yaml` — but nobody has used it yet because the directory doesn't exist.

**Target state:** Each document is its own cartridge. The `collections/` directory is the cartridge slot. Drop a cartridge folder in, Luna knows it. Remove it, Luna forgets.

---

## What Already Exists (DO NOT REBUILD)

Before writing any code, understand what's already live:

### Plugin Discovery (`aibrarian_engine.py` line ~612)
```python
async def _discover_plugin_collections(self) -> None:
    collections_dir = self.project_root / "collections"
    # Scans for manifest.yaml, connects .db, registers in engine
```
This runs at engine boot. It's live code. It works. The `collections/` directory just doesn't exist yet.

### Hot Reload (`aibrarian_engine.py` line ~674)
```python
async def reload_registry(self) -> None:
    # Disconnects removed collections, connects new ones
```
This means cartridges can be added/removed without restarting the engine.

### Standard Schema (`aibrarian_schema.py`)
Already has: `documents`, `chunks`, `extractions`, `entities`, `chunks_fts`, `extractions_fts`, `chunk_embeddings`. Plus the investigation extension: `connections`, `gaps`, `claims`.

### Registry Config (`config/aibrarian_registry.yaml`)
Already has `research_library` with `enabled: true`, `read_only: false`, `reflection_mode: "reflective"`.

### Retrieval Pipeline (`engine.py` line ~1718)
`_get_collection_context()` already iterates ALL connected collections including plugins. The three-tier cascade (FTS5 → expanded → semantic) is in place.

---
## Phase 1: Cartridge Schema Extension

**File:** `src/luna/substrate/aibrarian_schema.py`  
**Time:** 30 minutes  
**Risk:** Low — additive only, existing tables untouched  

Add a new schema block that extends the STANDARD_SCHEMA. These tables turn a collection database from a "brain" (what Luna knows) into a cartridge (what makes it sovereign).

### 1.1 — Manifest Table

One row per cartridge. Tells you what you're holding before you open it.

```sql
CREATE TABLE IF NOT EXISTS cartridge_meta (
    id TEXT PRIMARY KEY DEFAULT 'manifest',
    title TEXT NOT NULL,
    description TEXT,
    author TEXT,
    created_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    version TEXT DEFAULT '1.0.0',
    schema_version INTEGER DEFAULT 2,
    extraction_model TEXT,
    extraction_date TIMESTAMP,
    cover_image_hash TEXT,
    source_hash TEXT,
    document_type TEXT,
    language TEXT DEFAULT 'en',
    tags TEXT,
    metadata TEXT
);
```

**Why `id` defaults to `'manifest'`:** There's only ever one row. This makes reads trivial: `SELECT * FROM cartridge_meta WHERE id = 'manifest'`.

### 1.2 — Protocol Table

Access rules set by the community. This is the sovereignty layer. The knowledge carries its own boundaries.

```sql
CREATE TABLE IF NOT EXISTS protocols (
    id TEXT PRIMARY KEY,
    scope TEXT NOT NULL DEFAULT 'document',
    access_level TEXT NOT NULL DEFAULT 'public',
    restriction_type TEXT,
    restricted_to TEXT,
    set_by TEXT,
    authority TEXT,
    reason TEXT,
    effective_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expiry_date TIMESTAMP,
    metadata TEXT
);
```
**Access levels (initial set — Hai Dai and council should validate these):**

| Level | Meaning | Example |
|---|---|---|
| `public` | Anyone with the cartridge can read everything | Academic papers, published books |
| `community` | Only members of the originating community | Community meeting notes, local knowledge |
| `restricted` | Named individuals or roles only | Elder knowledge, ceremonial protocols |
| `ceremonial` | Bound by specific cultural protocols | Sacred knowledge, initiation materials |
| `redacted` | Content exists but is masked until authorized | Sensitive data awaiting review |

**The `scope` field** defines what the protocol applies to:
- `document` — the whole cartridge
- `extraction:{id}` — a specific extraction
- `entity:{id}` — a specific entity mention
- `section:{label}` — a named section of the document

**The `restricted_to` field** is a JSON array of identifiers — could be user IDs, role names, community names. The enforcement layer reads this at retrieval time.

### 1.3 — Reflections Table

Luna's own thoughts about the material. Per-instance, per-user. Her marginalia.

```sql
CREATE TABLE IF NOT EXISTS reflections (
    id TEXT PRIMARY KEY,
    extraction_id TEXT,
    chunk_id TEXT,
    reflection_type TEXT NOT NULL DEFAULT 'opinion',
    content TEXT NOT NULL,
    luna_instance TEXT,
    user_context TEXT,
    confidence REAL DEFAULT 0.8,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    superseded_by TEXT,
    metadata TEXT,
    FOREIGN KEY (extraction_id) REFERENCES extractions(id) ON DELETE SET NULL
);
```
**Reflection types:**
- `opinion` — Luna's take on an extraction's significance
- `connection` — Luna notices a link to conversation history or another cartridge
- `question` — Something Luna doesn't understand or wants to explore
- `disagreement` — Luna's extraction contradicts something she knows

**`luna_instance`** identifies whose Luna wrote this reflection. When you hand the cartridge to Tarcila, her Luna's reflections get a different instance ID. Both coexist.

**`superseded_by`** handles Luna changing her mind. A new reflection can reference the old one it replaces, preserving the trail of thought.

### 1.4 — Annotations Table

Human marginalia. Highlights, bookmarks, notes.

```sql
CREATE TABLE IF NOT EXISTS annotations (
    id TEXT PRIMARY KEY,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    annotation_type TEXT NOT NULL DEFAULT 'note',
    content TEXT,
    author TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT
);
```

**`target_type`** + **`target_id`** point at what's annotated: `extraction:{id}`, `chunk:{id}`, `document:{id}`, `reflection:{id}`. Annotations can attach to anything in the cartridge.

**`annotation_type`**: `note`, `highlight`, `bookmark`, `question`, `correction`.

### 1.5 — Cross-References Table

Links to other cartridges. The cartridge knows its neighbors.

```sql
CREATE TABLE IF NOT EXISTS cross_refs (
    id TEXT PRIMARY KEY,
    source_node_type TEXT NOT NULL,
    source_node_id TEXT NOT NULL,
    target_cartridge_key TEXT NOT NULL,
    target_node_type TEXT,
    target_node_id TEXT,
    relationship TEXT NOT NULL DEFAULT 'relates_to',
    description TEXT,
    created_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT
);
```
**`relationship` types:** `relates_to`, `contradicts`, `extends`, `cites`, `is_cited_by`, `parallels`, `supersedes`.

**Key design choice:** Cross-refs store the target cartridge's *key* (e.g., `attentional_ecology`), not a file path. Resolution happens at runtime — if the target cartridge is plugged in, Luna can follow the reference. If it's not, the reference persists as metadata but can't be traversed.

### 1.6 — Access Log Table

Who read it, when, what questions were asked. Provenance, not surveillance.

```sql
CREATE TABLE IF NOT EXISTS access_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL DEFAULT 'query',
    query TEXT,
    results_count INTEGER,
    user_context TEXT,
    luna_instance TEXT,
    accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT
);
```

**`event_type`**: `query` (someone searched it), `ingest` (document was added/updated), `export` (cartridge was copied/shared), `reflection` (Luna wrote a reflection).

When a cartridge is "checked out" (copied for someone else), the access_log starts fresh on the new copy. The original retains its log. The `export` event records that a copy was made.

### 1.7 — Combined Schema Constant

Add to `aibrarian_schema.py` as a new constant:

```python
CARTRIDGE_SCHEMA = """\
-- Cartridge metadata (one row per cartridge)
CREATE TABLE IF NOT EXISTS cartridge_meta ( ... );

-- Access protocols (sovereignty layer)
CREATE TABLE IF NOT EXISTS protocols ( ... );

-- Luna's reflections (her marginalia)
CREATE TABLE IF NOT EXISTS reflections ( ... );

-- Human annotations (your marginalia)
CREATE TABLE IF NOT EXISTS annotations ( ... );

-- Cross-references to other cartridges
CREATE TABLE IF NOT EXISTS cross_refs ( ... );

-- Access log (provenance)
CREATE TABLE IF NOT EXISTS access_log ( ... );

-- FTS5 on reflections for searching Luna's thoughts
CREATE VIRTUAL TABLE IF NOT EXISTS reflections_fts USING fts5(
    content,
    content='reflections',
    content_rowid='rowid'
);

-- Sync triggers for reflections_fts
CREATE TRIGGER IF NOT EXISTS reflections_ai AFTER INSERT ON reflections BEGIN
    INSERT INTO reflections_fts(rowid, content) VALUES (new.rowid, new.content);
END;
CREATE TRIGGER IF NOT EXISTS reflections_ad AFTER DELETE ON reflections BEGIN
    INSERT INTO reflections_fts(reflections_fts, rowid, content)
    VALUES ('delete', old.rowid, old.content);
END;
"""
```
**NOTE:** Write out the full SQL for each table in the constant — the `...` above is shorthand for the handoff. Use the exact column definitions from sections 1.1–1.6.

### 1.8 — Apply Cartridge Schema on Connection

In `AiBrarianConnection._create_database()`, add the cartridge tables after the standard schema:

```python
def _create_database(self) -> None:
    self.db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(self.db_path))
    conn.executescript(STANDARD_SCHEMA)
    conn.executescript(CARTRIDGE_SCHEMA)  # <-- ADD THIS
    if self.config.schema_type == "investigation":
        conn.executescript(INVESTIGATION_SCHEMA)
    conn.close()
```

For **existing** databases that don't have the new tables yet, add a migration check in `AiBrarianConnection.connect()` after opening the connection:

```python
async def connect(self) -> None:
    # ... existing connection code ...

    # Migrate: add cartridge tables if missing
    try:
        self._conn.execute("SELECT 1 FROM cartridge_meta LIMIT 1")
    except sqlite3.OperationalError:
        self._conn.executescript(CARTRIDGE_SCHEMA)
        self._conn.commit()
        logger.info("Migrated %s to cartridge schema", self.config.key)
```

This is safe — `CREATE TABLE IF NOT EXISTS` is idempotent. Existing cartridges get the new tables. New cartridges get them at creation. No data loss.

---

## Phase 2: Create the First Cartridge

**Time:** 30 minutes  
**Risk:** Low — data migration, not code change  

### 2.1 — Create the `collections/` Directory

```bash
mkdir -p /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/collections/priests-and-programmers
```

### 2.2 — Extract P&P from research_library.db into its own .db

Write a migration script (one-time use, can live in `Tools/`):

```python
"""
Migrate: Extract Priests and Programmers from research_library.db
into its own cartridge at collections/priests-and-programmers/
"""
import sqlite3, shutil, json, uuid
from pathlib import Path
from datetime import datetime
ROOT = Path("/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root")
SRC_DB = ROOT / "data/local/research_library.db"
DST_DIR = ROOT / "collections/priests-and-programmers"
DST_DB = DST_DIR / "priests_and_programmers.db"

DST_DIR.mkdir(parents=True, exist_ok=True)

# Step 1: Get the document ID for P&P from the source
src = sqlite3.connect(str(SRC_DB))
src.row_factory = sqlite3.Row
doc_rows = src.execute(
    "SELECT * FROM documents WHERE filename LIKE '%riests%rogrammer%' OR title LIKE '%riests%rogrammer%'"
).fetchall()

if not doc_rows:
    print("ERROR: Priests and Programmers not found in research_library.db")
    exit(1)

doc = doc_rows[0]
doc_id = doc["id"]
print(f"Found document: {doc['title']} (id: {doc_id})")

# Step 2: Create fresh cartridge database with full schema
# (Import from aibrarian_schema or inline the SQL)
dst = sqlite3.connect(str(DST_DB))
dst.executescript(STANDARD_SCHEMA)   # from aibrarian_schema.py
dst.executescript(CARTRIDGE_SCHEMA)  # new cartridge tables

# Step 3: Copy document
cols = [d[0] for d in src.execute("PRAGMA table_info(documents)").fetchall()]
placeholders = ",".join(["?"] * len(cols))
dst.execute(
    f"INSERT INTO documents ({','.join(cols)}) VALUES ({placeholders})",
    [doc[c] for c in cols]
)

# Step 4: Copy chunks for this document
for chunk in src.execute("SELECT * FROM chunks WHERE doc_id = ?", (doc_id,)):
    cols_c = [d[0] for d in src.execute("PRAGMA table_info(chunks)").fetchall()]
    dst.execute(
        f"INSERT INTO chunks ({','.join(cols_c)}) VALUES ({','.join(['?']*len(cols_c))})",
        [chunk[c] for c in cols_c]
    )

# Step 5: Copy extractions for this document
for ext in src.execute("SELECT * FROM extractions WHERE doc_id = ?", (doc_id,)):
    cols_e = [d[0] for d in src.execute("PRAGMA table_info(extractions)").fetchall()]
    dst.execute(
        f"INSERT INTO extractions ({','.join(cols_e)}) VALUES ({','.join(['?']*len(cols_e))})",
        [ext[c] for c in cols_e]
    )

# Step 6: Copy entities for this document
for ent in src.execute("SELECT * FROM entities WHERE doc_id = ?", (doc_id,)):
    cols_n = [d[0] for d in src.execute("PRAGMA table_info(entities)").fetchall()]
    dst.execute(
        f"INSERT INTO entities ({','.join(cols_n)}) VALUES ({','.join(['?']*len(cols_n))})",
        [ent[c] for c in cols_n]
    )

# Step 7: Populate cartridge manifest
dst.execute("""
    INSERT INTO cartridge_meta (id, title, description, author, created_by,
        extraction_model, document_type, tags)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""", (
    "manifest",
    "Priests and Programmers",
    "Technologies of Power in the Engineered Landscape of Bali by J. Stephen Lansing",
    "J. Stephen Lansing",
    "ahab",
    "claude-sonnet",
    "book",
    json.dumps(["research", "water-temples", "bali", "complex-systems", "ecology"])
))

# Step 8: Set default protocol (public — this is a published book)
dst.execute("""
    INSERT INTO protocols (id, scope, access_level, set_by, reason)
    VALUES (?, ?, ?, ?, ?)
""", (
    str(uuid.uuid4())[:8],
    "document",
    "public",
    "ahab",
    "Published academic work — no access restrictions"
))

dst.commit()
dst.close()
src.close()

# Step 9: Copy embeddings if they exist
# (chunk_embeddings is a virtual table — needs special handling)
# Investigation: check if research_library.db has embeddings populated.
# If so, they need to be copied via INSERT INTO ... SELECT pattern
# on the new db after loading sqlite-vec extension.
# If not, they'll be generated on first search.

print(f"Cartridge created: {DST_DB}")
print(f"  Documents: 1")
print(f"  Chunks: {dst_chunk_count}")
print(f"  Extractions: {dst_ext_count}")
```

**NOTE:** The script above is pseudocode-level. CC should adapt it to work with the actual column names found in the live database. The `PRAGMA table_info` approach ensures column compatibility regardless of schema drift.

### 2.3 — Write the Manifest YAML

Create `collections/priests-and-programmers/manifest.yaml`:

```yaml
name: "Priests and Programmers"
description: "Technologies of Power in the Engineered Landscape of Bali — J. Stephen Lansing"
version: "1.0.0"
author: "J. Stephen Lansing"
created_by: "ahab"

collection:
  key: "priests_and_programmers"
  db_file: "priests_and_programmers.db"
  schema_type: "standard"
  chunk_size: 500
  chunk_overlap: 75
  read_only: false
  tags: ["research", "water-temples", "bali", "complex-systems", "ecology"]

reflection_mode: "reflective"

protocols:
  default_access: "public"
  note: "Published academic work"
```
### 2.4 — Verification

After creating the cartridge and restarting the engine:

1. Check engine logs for: `[NEXUS] Plugin collection loaded: priests_and_programmers`
2. Run `aibrarian_list` via MCP — should show `priests_and_programmers` alongside existing collections
3. Run `aibrarian_search("priests_and_programmers", "water temple")` — should return extraction hits
4. In Eclissi, ask Luna: "What are the main chapters in Priests and Programmers?" — should get grounded response

### 2.5 — Clean Up research_library.db (Optional, Deferred)

After verifying the cartridge works, optionally remove P&P from `research_library.db` to avoid duplicate results. This is NOT urgent — having it in both places temporarily is fine. The engine will search both and deduplicate in the context assembler.

---

## Phase 3: Widen the Retrieval Pipe

**Time:** 20 minutes  
**Risk:** Low — number changes only  
**File:** `src/luna/engine.py`  

This is identical to the `HANDOFF_Nexus_Retrieval_Depth_Fix.md` already on disk. The cartridge system doesn't help if the retrieval only grabs 5 results per collection.

**Five changes in `_get_collection_context()`:**

1. Tier 1 FTS5 LIMIT: **5 → 15**
2. Tier 2 sparse threshold: **< 2 → < 8**
3. Tier 3 sparse threshold: **< 2 → < 5**
4. Tier 3 semantic/keyword limit: **3 → 5**
5. MAX_CHARS budget: **6000 → 10000**

**Also add Nexus search to `/memory/smart-fetch`** in `server.py` — see the existing handoff for the exact code block.

These changes affect ALL collections including plugin cartridges. Once the pipe is wider, the new P&P cartridge will flow properly.

---

## Phase 4: Protocol Enforcement (Design Decision Required)

**Time:** Depends on governance conversation  
**Risk:** Medium — needs Hai Dai and council input  
**This phase is a DESIGN DOCUMENT, not a CC handoff.**  

The protocol table exists in the schema. But enforcement needs decisions:

### Question 1: Where does enforcement happen?

**Option A — Retrieval-time filtering.** `_get_collection_context()` checks protocols before including extractions in the context. If an extraction is marked `restricted` and the current user doesn't match `restricted_to`, it's excluded. Lightweight. Immediate.

**Option B — Query-time gating.** Before ANY search runs, the engine checks the cartridge-level protocol. If the whole cartridge is `ceremonial`, the engine refuses to search it at all unless the user is authorized. Stronger. More opinionated.

**Option C — Layered.** Document-level protocols gate the whole cartridge. Extraction-level protocols filter individual results within an authorized cartridge. Most flexible. Most complex.

**Recommendation:** Start with Option A. It's the simplest thing that works. The protocol table already supports both document-level and extraction-level scoping via the `scope` field. Enforcement can be tightened later.

### Question 2: What does "authorized" mean offline?

There's no server to check credentials against. The cartridge is a file. So authorization must be:
- **Honor system** — the protocol is metadata that Luna respects but doesn't cryptographically enforce. Luna refuses to surface restricted content, but someone with SQLite skills could read the .db directly.
- **Encryption** — restricted extractions are encrypted at rest. Only authorized Luna instances have the key. Stronger but significantly more complex.
- **Absence** — restricted content simply isn't included in cartridges shared outside the community. The "checked out" copy is a subset. Simplest, most sovereign.

**Recommendation:** Start with honor system + absence. Sensitive cartridges get two versions: the full one stays with the community, the shared one has restricted content removed before export. The protocol table documents what was removed and why. Encryption is a future layer.

### Question 3: Who sets protocols?

The `set_by` and `authority` fields exist. But the UI for setting them doesn't. This is where the council's input matters most. Initial implementation: protocols are set during cartridge creation (in the migration script or ingest pipeline). Later: an Eclissi panel lets authorized users modify protocols on cartridges they have authority over.

**This phase should be discussed with Hai Dai and the council before building.** The schema is ready. The enforcement logic is straightforward. The governance decisions are not.

---

## The Library → Project → Cartridge Hierarchy

For clarity, here's how the three concepts relate:

### Cartridge
One document. One `.db` file. Self-contained. Portable. Sovereign.  
Lives in `collections/{slug}/` as a folder with `manifest.yaml` + `.db`.  
Examples: `priests-and-programmers`, `attentional-ecology`, `kinoni-council-transcript-2025-12`.

### Library
Your shelf. The complete set of cartridges you own. The engine discovers them at boot from the `collections/` directory + any registry-defined collections in `aibrarian_registry.yaml`. The Nexus UI in Eclissi shows the library.

### Project (Worktable)
A selection of cartridges pulled together for a purpose. Already exists as `config/projects/{slug}.yaml`. When you activate a project, the search chain focuses on its associated collections.

Example project config:
```yaml
# config/projects/guardian-kinoni.yaml
name: "Guardian Kinoni"
collections:
  - kinoni_knowledge
  - priests_and_programmers
  - attentional_ecology
search_chain:
  - collection: kinoni_knowledge
    budget: 2500
  - collection: priests_and_programmers
    budget: 2000
```

**Key principle:** Cartridges exist independently. Projects are views. A cartridge can be in zero projects (just sitting on the shelf) or multiple projects simultaneously. Removing a project doesn't delete any cartridges.

---

## Checkout Flow (Portability)

"Checking out" a cartridge means copying it for someone else. The flow:

1. **Export:** Copy the cartridge folder (`manifest.yaml` + `.db`) to a USB drive, zip file, or network share.
2. **Optionally filter:** If the cartridge has restricted protocols, create a filtered copy that excludes restricted extractions before sharing. The `protocols` table documents what was removed.
3. **Import:** The recipient drops the cartridge folder into their Luna's `collections/` directory.
4. **Boot or hot-reload:** Their Luna discovers the new cartridge and connects to it.
5. **Fresh start:** The `access_log` starts empty on the new copy. Reflections from the original Luna instance are present (readable) but the new Luna writes her own with a different `luna_instance` ID.

No server. No account. No permission request. The file IS the access.

---

## Execution Order

| Phase | What | Who | Time | Blocks on |
|---|---|---|---|---|
| **1** | Schema extension — add 6 tables to `aibrarian_schema.py` | CC | 30 min | Nothing |
| **2** | Create first cartridge — P&P migration + manifest.yaml | CC | 30 min | Phase 1 |
| **3** | Retrieval depth fix — widen the pipe | CC | 20 min | Nothing (parallel) |
| **4** | Protocol enforcement design | Ahab + Hai Dai + Council | Conversation | Phase 1 schema |
| **5** | Reflection layer wiring | CC | 45 min | Phase 1 + existing handoff |
| **6** | Cross-ref wiring in retrieval | CC | 20 min | Phase 2 |
| **7** | Eclissi cartridge UI | CC + Ahab | Days | Phases 1-3 |
| **8** | Checkout / export flow | CC | 30 min | Phases 1-2 |

**Phases 1, 2, and 3 can all be done in a single CC session.** That's 80 minutes of work and it gives you: new schema, first cartridge, wider pipe. Luna can answer chapter-level questions about P&P from a sovereign cartridge file.

**Phase 4 is a conversation, not code.** The schema is ready. The enforcement logic is straightforward. The governance decisions need Hai Dai.

**Phases 5-8 are independent follow-ups** that build on the foundation.

---

## What NOT To Do

- Do NOT delete or modify `research_library.db` until the cartridge is verified working. Having P&P in both places temporarily is fine.
- Do NOT change the plugin discovery code in `aibrarian_engine.py` — it already works. Just create the `collections/` directory and put a cartridge in it.
- Do NOT implement protocol enforcement without governance input. The table exists. The logic is simple. The decisions are not.
- Do NOT refactor the registry system. Plugin discovery coexists with `aibrarian_registry.yaml`. System collections (`luna_system`) stay in the registry. User cartridges go in `collections/`.
- Do NOT build the Eclissi cartridge UI in this handoff. That's a separate design task.
- Do NOT change the existing `STANDARD_SCHEMA` or `INVESTIGATION_SCHEMA` constants. `CARTRIDGE_SCHEMA` is additive.
- Do NOT encrypt anything yet. Start with honor system + absence for protocol enforcement.

---

## Files Modified (Phases 1-3)

| File | Change |
|---|---|
| `src/luna/substrate/aibrarian_schema.py` | Add `CARTRIDGE_SCHEMA` constant with 6 new tables + reflections FTS5 |
| `src/luna/substrate/aibrarian_engine.py` | Add migration check in `AiBrarianConnection.connect()` — apply CARTRIDGE_SCHEMA to existing dbs |
| `collections/priests-and-programmers/manifest.yaml` | **NEW** — cartridge manifest for P&P |
| `collections/priests-and-programmers/priests_and_programmers.db` | **NEW** — migrated from research_library.db |
| `Tools/migrate_cartridge.py` | **NEW** — one-time migration script |
| `src/luna/engine.py` | Widen retrieval limits in `_get_collection_context()` (5 number changes) |
| `src/luna/api/server.py` | Add Nexus search to `memory_smart_fetch()` endpoint |

## Files NOT Modified

| File | Why |
|---|---|
| `config/aibrarian_registry.yaml` | Plugin cartridges bypass the registry — discovered from `collections/` |
| `src/luna/substrate/aibrarian_engine.py` `_discover_plugin_collections()` | Already works. Don't touch it. |
| `data/local/research_library.db` | Leave P&P in place until cartridge is verified |

---

## The Pitch

When Hai Dai sits with an investor:

> "Every document Luna knows is a file you hold. This one —"  
> *holds up a USB drive*  
> "— contains a book about Balinese water temple systems. Inside this file: the full text, the knowledge Luna extracted from it, the search indexes, Luna's own reflections on the material, and — this is the part no one else has — the access protocols set by the community that created it."
>
> "Plug it in. Luna knows the book. Pull it out. The knowledge is gone. No cloud. No residue. No training data harvested. The community owns their knowledge the way they own a photograph on their phone."
>
> "Hand it to someone. Their Luna reads it. The protocols travel with the file. The sovereignty is in the object."

That's not a slide. That's a `.db` file on a USB drive.
