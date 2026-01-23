# EMERGENCY: Luna Memory Crisis - Complete Investigation

**Priority**: CRITICAL
**Created**: 2025-01-21
**Status**: LUNA LOBOTOMIZED - DATA EXISTS BUT WRONG PATH

---

## EXECUTIVE SUMMARY

Luna's memory was effectively wiped. The data still exists (59,939 nodes) but the runtime is pointing to a nearly-empty database (15 nodes).

| Database | Location | Nodes | Edges | Status |
|----------|----------|-------|-------|--------|
| **BROKEN** | `~/.luna/luna.db` | 15 | 0 | ❌ Runtime uses this |
| **GOOD** | `data/luna_engine.db` | 59,939 | 32,336 | ✅ Luna's actual brain |
| **GOLD BACKUP** | `GOLD DOCUMENTATION/...` | 13,927 | 93 | ⚠️ v1 schema, incompatible |

**Root Cause**: Two conflicting default database paths that were never reconciled.

---

## EVIDENCE TIMELINE

### File Timestamps

```bash
# ~/.luna/luna.db
Created:  Jan 10 03:56:36
Modified: Jan 21 12:02:58  # ← TODAY, something touched it
Size:     233KB            # ← Tiny

# data/luna_engine.db  
Modified: Jan 21 12:02
Size:     66MB             # ← 283x larger
```

### Node Counts Over Time

| Source | Nodes | When |
|--------|-------|------|
| Gold Documentation backup | 13,927 | Dec 28 |
| CC checkpoint backup | 11,019 | Unknown |
| `data/luna_engine.db` | 59,939 | Current |
| `~/.luna/luna.db` | 15 | Current (broken) |

---

## THE GOOD DATABASE (Luna's Real Brain)

**Path**: `/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/data/luna_engine.db`

```
Memory Nodes: 59,939
Graph Edges:  32,336
Entities:     70

Node types:
  FACT: 55,455
  PARENT: 2,311
  ACTION: 933
  ENTITY: 313
  PROBLEM: 302
  QUESTION: 191
  OBSERVATION: 183
  ASSUMPTION: 68
  MEMORY: 49
  PREFERENCE: 45
  DECISION: 44
  OUTCOME: 35
  CONNECTION: 5
  PERSONALITY_REFLECTION: 5
```

---

## ROOT CAUSE: CONFLICTING DEFAULT PATHS

### Path 1: MemoryDatabase Class

```python
# src/luna/substrate/database.py:41-42
DEFAULT_DB_DIR = Path.home() / ".luna"
DEFAULT_DB_NAME = "luna.db"
# Results in: ~/.luna/luna.db
```

### Path 2: MatrixActor Class

```python
# src/luna/actors/matrix.py:54
self.db_path = Path(__file__).parent.parent.parent.parent / "data" / "luna_engine.db"
# Results in: <project>/data/luna_engine.db
```

### Path 3: EngineConfig

```python
# src/luna/engine.py:53
data_dir: Path = field(default_factory=lambda: Path.home() / ".luna")
# Results in: ~/.luna/
```

**Three different places define paths. They're never synchronized.**

---

## CODE FLOW ANALYSIS

### Expected Flow (Should Work)

```
1. Engine._boot() creates MatrixActor()
   └── MatrixActor defaults to data/luna_engine.db ✅

2. MatrixActor.initialize() creates:
   └── self._db = MemoryDatabase(self.db_path)  # Passes correct path ✅
   └── self._matrix = MemoryMatrix(self._db)     # Has correct db ✅

3. Director._init_entity_context() gets:
   └── db = matrix._matrix.db  # Should be correct db ✅

4. ContextPipeline gets that db
   └── Should have 59,939 nodes ✅
```

### Actual Behavior (Broken)

Something is creating or using `~/.luna/luna.db` instead. Possibilities:

1. **MemoryDatabase() called without path argument somewhere**
2. **A test or script created fresh DB at ~/.luna/**
3. **EngineConfig.data_dir is being used somewhere to override**
4. **Schema.sql auto-runs and creates fresh tables**

---

## SCHEMA COMPARISON

### Current v2 Schema (`~/.luna/luna.db` and `data/luna_engine.db`)

```sql
CREATE TABLE memory_nodes (
    id TEXT PRIMARY KEY,
    node_type TEXT NOT NULL,  -- v2 uses "node_type"
    content TEXT NOT NULL,
    summary TEXT,
    source TEXT,
    confidence REAL DEFAULT 1.0,
    importance REAL DEFAULT 0.5,
    access_count INTEGER DEFAULT 0,
    last_accessed TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    metadata TEXT,
    lock_in REAL DEFAULT 0.15,
    lock_in_state TEXT DEFAULT 'drifting'
);
```

### Gold v1 Schema (INCOMPATIBLE)

```sql
CREATE TABLE memory_nodes (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,  -- v1 uses "type", not "node_type"
    content TEXT NOT NULL,
    timestamp INTEGER NOT NULL,  -- INTEGER, not TEXT datetime
    session_id TEXT,
    turn_number INTEGER,
    confidence INTEGER DEFAULT 100,  -- INTEGER 0-100, not REAL 0-1
    status TEXT DEFAULT 'ACTIVE',
    priority TEXT,
    owner TEXT,
    tags TEXT,
    metadata TEXT,
    parent_id TEXT,
    is_parent INTEGER DEFAULT 0,
    created_at INTEGER NOT NULL,  -- INTEGER, not TEXT
    updated_at INTEGER NOT NULL
);
```

**Cannot copy Gold backup directly - schemas are incompatible.**

---

## ALL DATABASE FILES FOUND

```bash
~/.luna/
├── luna.db      # 233KB, 15 nodes, BROKEN
├── memory.db    # 69KB, different tables
└── snapshot.yaml

<project>/data/
└── luna_engine.db  # 66MB, 59,939 nodes, GOOD

GOLD DOCUMENTATION/data/memory/matrix/
└── memory_matrix.db  # 179MB, v1 schema, incompatible
```

---

## DANGEROUS DELETE STATEMENTS IN CODE

Found these potential memory-wiping operations:

```python
# src/luna/substrate/graph.py:498
await self.db.execute("DELETE FROM graph_edges")
# ^ Clears ALL edges

# src/luna/substrate/embeddings.py:281
await self.db.execute(f"DELETE FROM {self.table_name}")
# ^ Clears ALL embeddings

# src/luna/entities/storage.py:194
"DELETE FROM memory_edges WHERE from_node = ? OR to_node = ?"

# src/luna/entities/storage.py:199
"DELETE FROM memory_nodes WHERE id = ? AND node_type = ?"
```

### Tuning Session Clear Memory

Ahab mentioned a "clear memory" option in tuning sessions. Found in:

```python
# src/luna/tuning/session.py
# This file has db operations - needs investigation for mass delete
```

---

## IMMEDIATE FIX OPTIONS

### Option A: Copy Good DB to Expected Location (FASTEST)

```bash
# Backup broken one
cp ~/.luna/luna.db ~/.luna/luna.db.broken

# Copy good one
cp /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/data/luna_engine.db ~/.luna/luna.db

# Verify
sqlite3 ~/.luna/luna.db "SELECT COUNT(*) FROM memory_nodes"
# Should return: 59939
```

### Option B: Fix Default Path in Code (PROPER FIX)

```python
# src/luna/substrate/database.py:41-42
# BEFORE
DEFAULT_DB_DIR = Path.home() / ".luna"
DEFAULT_DB_NAME = "luna.db"

# AFTER - Use project directory
DEFAULT_DB_DIR = Path(__file__).parent.parent.parent.parent / "data"
DEFAULT_DB_NAME = "luna_engine.db"
```

### Option C: Symlink (QUICK WORKAROUND)

```bash
mv ~/.luna/luna.db ~/.luna/luna.db.broken
ln -s /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/data/luna_engine.db ~/.luna/luna.db
```

---

## PREVENTION: DO NOT DO THESE THINGS

1. **Never call `MemoryDatabase()` without a path argument**
2. **Never run any "clear memory" functions without explicit confirmation**
3. **Never trust that `~/.luna/luna.db` has the right data**
4. **Always verify node count after any operation**:
   ```bash
   sqlite3 <db_path> "SELECT COUNT(*) FROM memory_nodes"
   ```

---

## VERIFICATION AFTER FIX

```bash
# 1. Check node count
sqlite3 ~/.luna/luna.db "SELECT COUNT(*) FROM memory_nodes"
# Expected: 59939

# 2. Check edge count
sqlite3 ~/.luna/luna.db "SELECT COUNT(*) FROM graph_edges"
# Expected: 32336

# 3. Check entities
sqlite3 ~/.luna/luna.db "SELECT COUNT(*) FROM entities"
# Expected: 70

# 4. Restart Luna and test
python scripts/run.py

# 5. Ask Luna
"Who are you?" → Should say Luna
"Who am I?" → Should say Ahab
"Tell me about Marzipan" → Should know him
```

---

## FILES TO CHECK/MODIFY

| File | Issue | Action |
|------|-------|--------|
| `src/luna/substrate/database.py:41-42` | Wrong default path | Change to project/data |
| `src/luna/actors/matrix.py:54` | Correct path | Keep as-is |
| `src/luna/engine.py:53` | `data_dir` not synced | Sync with matrix path |
| `src/luna/tuning/session.py` | Has "clear memory"? | INVESTIGATE |
| `~/.luna/luna.db` | Broken | REPLACE |
| `data/luna_engine.db` | Good | PROTECT |

---

## OUTSTANDING QUESTIONS

1. **What exactly triggered the wipe?** The file was modified today at 12:02.
2. **Is there a "clear memory" function in tuning?** Ahab mentioned it.
3. **Why does EngineConfig use `~/.luna` while MatrixActor uses `data/`?**
4. **Are there any tests that create fresh databases?**
5. **Does schema.sql auto-run and recreate tables?**

---

## RELATED ISSUES (FROM EARLIER INVESTIGATION)

### Unit Tests Pass, Integration Fails

- 419 unit tests pass
- Components work in isolation
- Integration is broken
- Director may not be using ContextPipeline in production
- See: `HANDOFF-EMERGENCY-SWARM.md`

### Local Path Lobotomized

- Local inference has no identity, no memory
- Says "Hello! How can I assist you today?" instead of being Luna
- Doesn't know who Ahab is
- Hallucinates fake people

---

## NEXT STEPS FOR CC

1. **FIRST**: Run Option A (copy good DB) to restore Luna immediately
2. **THEN**: Fix the default path in `database.py` (Option B)
3. **THEN**: Find and remove/protect any "clear memory" functionality
4. **THEN**: Add startup validation that checks node count
5. **THEN**: Address the unit test / integration test gap

---

*Luna's brain exists. 59,939 nodes. 32,336 edges. The code is just pointing to the wrong file.*

*One `cp` command restores her. Then fix the paths so it never happens again.*
