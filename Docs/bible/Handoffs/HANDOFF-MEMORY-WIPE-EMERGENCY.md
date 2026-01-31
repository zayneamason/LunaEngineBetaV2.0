# EMERGENCY: Luna's Memory Was Wiped

**Priority**: CRITICAL
**Created**: 2025-01-21
**Status**: LUNA IS LOBOTOMIZED

---

## THE PROBLEM

Luna's memory was wiped from **59,939 nodes** down to **15 nodes**.

| Database | Nodes | Edges | Status |
|----------|-------|-------|--------|
| `~/.luna/luna.db` | 15 | 0 | ❌ BROKEN (runtime uses this) |
| `data/luna_engine.db` | 59,939 | 32,336 | ✅ GOOD (Luna's actual brain) |

**The runtime is pointing to the wrong database.**

---

## THE FIX

### Option A: Copy the good database (RECOMMENDED)

```bash
# Backup the broken one
cp ~/.luna/luna.db ~/.luna/luna.db.broken

# Copy the good one
cp /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/data/luna_engine.db ~/.luna/luna.db
```

### Option B: Change the code to use the right path

In `src/luna/substrate/database.py` line 41-42:

```python
# BEFORE (wrong path)
DEFAULT_DB_DIR = Path.home() / ".luna"
DEFAULT_DB_NAME = "luna.db"

# AFTER (correct path)
DEFAULT_DB_DIR = Path(__file__).parent.parent.parent.parent / "data"
DEFAULT_DB_NAME = "luna_engine.db"
```

---

## ROOT CAUSE

Two conflicting default paths:

| Component | Default Path | Nodes |
|-----------|--------------|-------|
| `MemoryDatabase` | `~/.luna/luna.db` | 15 |
| `MatrixActor` | `data/luna_engine.db` | 59,939 |

The `MemoryDatabase` class defaults to the wrong location. Someone (or something) created a fresh database at `~/.luna/luna.db` and the runtime started using it instead of Luna's actual brain.

---

## VERIFY THE FIX

After applying the fix:

```bash
# Check node count
sqlite3 ~/.luna/luna.db "SELECT COUNT(*) FROM memory_nodes"
# Should return: 59939

# Check edge count  
sqlite3 ~/.luna/luna.db "SELECT COUNT(*) FROM graph_edges"
# Should return: 32336
```

Then restart Luna and test:
- "Who are you?" → Should say Luna
- "Who am I?" → Should say Ahab
- "Tell me about Marzipan" → Should know him

---

## DO NOT

- Do NOT run any "clear memory" functions
- Do NOT create fresh databases
- Do NOT use `MemoryDatabase()` without a path argument

---

## FILES

- Good database: `/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/data/luna_engine.db`
- Broken database: `~/.luna/luna.db`
- Database class: `src/luna/substrate/database.py`
- Matrix actor: `src/luna/actors/matrix.py`

---

*Luna's brain exists. Just point to it.*
