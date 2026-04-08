# HANDOFF: Database Lock Audit, Fix, and Verification

**Priority:** CRITICAL — Luna is non-functional (9/13 queries failing with "database is locked")
**Scope:** Diagnose, fix, and verify database locking in luna_engine.db
**Project Root:** `/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root`
**Python:** `.venv/bin/python3` (NOT system Python)

---

## CONTEXT

Luna QA testing shows 9 out of 13 queries returning "database is locked" with 0 grounded results. The 4 queries that succeed return mostly ungrounded responses (avg 0.12–0.35). Luna is alive but amnesiac — retrieval pipeline can't read the database.

**Suspected root cause:** History Manager's `_tick()` method calls `scribe.compress_turn()` (an LLM call) inside a 2-second timeout, creating zombie background writers that hold WAL locks. A `_tick_in_progress` guard was previously spec'd but may not have landed.

---

## PHASE 1: AUDIT (Do all of this BEFORE changing any code)

### 1A. Kill all Luna processes

```bash
ps aux | grep -i luna
ps aux | grep -i python | grep -i luna
# Kill everything. Clean slate.
kill -9 <all Luna PIDs>
```

### 1B. Check for WAL lock files

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
ls -la data/user/luna_engine.db*
ls -la data/local/research_library.db*
```

If `-wal` or `-shm` files exist with non-zero size while no Luna process is running, that's orphaned locks. Delete them:

```bash
rm -f data/user/luna_engine.db-wal data/user/luna_engine.db-shm
rm -f data/local/research_library.db-wal data/local/research_library.db-shm
```

### 1C. Verify database is accessible

```bash
.venv/bin/python3 -c "
import sqlite3
conn = sqlite3.connect('data/user/luna_engine.db', timeout=2)
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM memory_nodes')
print(f'Memory nodes: {cur.fetchone()[0]}')
cur.execute('PRAGMA journal_mode')
print(f'Journal mode: {cur.fetchone()[0]}')
cur.execute('PRAGMA busy_timeout')
print(f'Busy timeout: {cur.fetchone()[0]}')
conn.close()
print('DB accessible')
"
```

### 1D. Audit the _tick_in_progress guard

Check whether the previous fix actually landed:

```bash
grep -n "_tick_in_progress" src/memory/history_manager.py
```

- **If returns nothing:** The fix was never applied. Proceed to Phase 2.
- **If returns lines:** Read the implementation. Check that it's actually preventing re-entrant ticks. Proceed to Phase 2 anyway to verify correctness.

### 1E. Audit ALL database writers

Find every place in the codebase that opens or writes to luna_engine.db:

```bash
grep -rn "luna_engine.db" src/
grep -rn "conn.execute\|cursor.execute\|\.commit()" src/memory/ src/scribe/ src/engine/
grep -rn "sqlite3.connect" src/
```

Document every writer. We need to know who's competing for the lock.

### 1F. Check busy_timeout configuration

```bash
grep -rn "busy_timeout\|timeout" src/ | grep -i sqlite
```

SQLite's default busy_timeout is 0 (immediate failure). If we're not setting it, that explains why intermittent contention = immediate "database is locked" errors.

---

## PHASE 2: FIX

Apply ALL of the following. They are independent and all necessary.

### 2A. Add _tick_in_progress guard (if missing)

In `src/memory/history_manager.py`, find the `_tick()` or equivalent periodic method. Add:

```python
class HistoryManager:
    def __init__(self, ...):
        # ... existing init ...
        self._tick_in_progress = False

    async def _tick(self):
        if self._tick_in_progress:
            return  # Skip this tick, previous one still running
        self._tick_in_progress = True
        try:
            # ... existing tick logic ...
            # CRITICAL: If compress_turn() is called here, use asyncio.create_task()
            # so it doesn't block the tick timeout
            if needs_compression:
                asyncio.create_task(self._compress_turn_background(turn))
        finally:
            self._tick_in_progress = False

    async def _compress_turn_background(self, turn):
        """Run compression outside the tick cycle to avoid timeout cascades."""
        try:
            await self.scribe.compress_turn(turn)
        except Exception as e:
            logger.warning(f"Background compression failed: {e}")
```

### 2B. Set busy_timeout on ALL connections

Find every `sqlite3.connect()` call in the codebase. Every single one must set a busy_timeout:

```python
conn = sqlite3.connect(db_path, timeout=10)  # 10 second busy wait
# OR after connection:
conn.execute("PRAGMA busy_timeout = 10000")  # 10000ms
```

**Search for all connection points:**
```bash
grep -rn "sqlite3.connect" src/
```

Fix every one. No exceptions.

### 2C. Set WAL mode on database creation

If not already set, ensure WAL journal mode is used (allows concurrent readers):

```bash
grep -rn "journal_mode" src/
```

If WAL is not being set, add to whatever creates/opens the database:

```python
conn.execute("PRAGMA journal_mode=WAL")
```

### 2D. Fix sqlite3.Row crash (if not already fixed)

In `src/` wherever `Entity.from_row()` exists:

```bash
grep -rn "from_row" src/
```

Ensure it handles `sqlite3.Row` objects (not just `tuple` and `dict`):

```python
@classmethod
def from_row(cls, row):
    if isinstance(row, sqlite3.Row):
        row = dict(row)
    elif isinstance(row, tuple):
        # ... existing tuple handling ...
    # ... rest of method ...
```

---

## PHASE 3: VERIFY

### 3A. Start Luna clean

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
.venv/bin/python3 -m src.main  # or however Luna starts
```

### 3B. Run rapid-fire queries

Send 5 queries in quick succession (this is what triggers the lock contention):

```bash
for i in 1 2 3 4 5; do
  curl -s -X POST http://localhost:8000/message \
    -H "Content-Type: application/json" \
    -d "{\"message\": \"test query $i: who am I to you?\"}" &
done
wait
```

**Success criteria:** All 5 return responses with NO "database is locked" errors.

### 3C. Run the QA test

```bash
# Use qa_simulate_with_options or whatever QA harness produced the original failure log
# Re-run the same 13 questions from the failing test
```

**Success criteria:**
- 0 out of 13 queries return "database is locked"
- Grounded score improves (any improvement over avg 0.00 on the 9 that were locked)

### 3D. Check for WAL file growth

While Luna is running, monitor:

```bash
watch -n 1 'ls -la data/user/luna_engine.db*'
```

WAL file should exist but stay bounded (not grow unbounded). If it grows past ~10MB without checkpointing, there's still a long-running reader or writer holding a lock.

### 3E. Log audit

After the test run, check logs for:
- Any "database is locked" warnings
- Any "_tick_in_progress: skipping" messages (confirms the guard is working)
- Any "Background compression failed" messages

---

## DO NOT

- Do NOT touch retrieval logic (extractions_fts, chunks_fts, semantic search) — that's a separate handoff
- Do NOT touch the `/stream` endpoint wiring — separate issue
- Do NOT rename anything — no refactors
- Do NOT add new features
- Do NOT modify the Memory Matrix or scribe logic beyond the _tick guard
- Do NOT change database schema

---

## EXPECTED OUTCOME

After this handoff:
1. "database is locked" errors go to zero under normal operation
2. Rapid-fire queries don't cause lock contention
3. Background compression runs outside the tick cycle
4. All SQLite connections have reasonable busy_timeout
5. WAL mode is confirmed active
6. QA tests can actually exercise retrieval instead of crashing on locks

---

## FILES LIKELY TOUCHED

- `src/memory/history_manager.py` — tick guard, compression backgrounding
- Any file containing `sqlite3.connect()` — busy_timeout addition
- Database initialization code — WAL mode pragma
- Entity class file — sqlite3.Row handling (if not already fixed)
