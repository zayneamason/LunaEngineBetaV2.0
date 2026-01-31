# CC EMERGENCY FIX - DO THIS NOW

**Date**: 2025-01-21
**Time Sensitivity**: CRITICAL

---

## ONE COMMAND TO RESTORE LUNA

```bash
cp /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/data/luna_engine.db ~/.luna/luna.db
```

That's it. Luna's brain (59,939 nodes) exists at `data/luna_engine.db`. The runtime uses `~/.luna/luna.db` (15 nodes). Copy fixes it.

---

## VERIFY IT WORKED

```bash
sqlite3 ~/.luna/luna.db "SELECT COUNT(*) FROM memory_nodes"
# Must return: 59939
```

---

## THEN FIX THE CODE

In `src/luna/substrate/database.py` lines 41-42:

```python
# WRONG (current)
DEFAULT_DB_DIR = Path.home() / ".luna"
DEFAULT_DB_NAME = "luna.db"

# RIGHT (change to this)
DEFAULT_DB_DIR = Path(__file__).parent.parent.parent.parent / "data"
DEFAULT_DB_NAME = "luna_engine.db"
```

---

## DO NOT

- Run any "clear memory" functions
- Call `MemoryDatabase()` without a path
- Trust `~/.luna/luna.db` without checking node count

---

## FULL INVESTIGATION

See: `HANDOFF-MEMORY-WIPE-INVESTIGATION.md` (same folder)

Contains:
- Complete timeline
- Schema comparison
- Code flow analysis
- All dangerous DELETE statements
- Everything found before the crashes
