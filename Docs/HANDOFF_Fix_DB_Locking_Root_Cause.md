# HANDOFF ADDENDUM: Database Locking — Root Cause & Structural Fix
# Priority: CRITICAL | March 31, 2026
# REPLACES: The busy_timeout section of HANDOFF_Fix_SQLite_Row_And_DB_Locking.md
# CONTEXT: CC applied busy_timeout=15000 but 11/29 tests STILL hit "database is locked"

## What CC Already Applied (Confirmed)
- `PRAGMA busy_timeout=15000` in substrate/database.py (line ~99) ✓
- This was NOT sufficient. 11 tests still fail with DB locks.

## Root Cause: History Manager Tick Cascading

The cognitive tick loop runs every ~500ms-1s. Each tick calls `history.tick()` with a 2-second timeout:

```python
# engine.py line 1006
await asyncio.wait_for(history.tick(), timeout=2.0)
```

Inside `history.tick()`, three things happen sequentially:
1. `_process_compression_queue()` — reads a turn, calls **Scribe.compress_turn()** (LLM call, 5-10s), writes result
2. `_process_extraction_queue()` — reads a turn, sends to Scribe mailbox, writes status
3. `_check_archivable_turns()` — scans for old turns, queues extraction

The killer is **step 1**: `compress_turn()` is an LLM call that takes 5-10 seconds. The tick has a 2-second timeout. So:

- Tick N starts compression (LLM call begins)
- After 2 seconds, tick N is **cancelled** by asyncio.wait_for
- But the LLM call **continues in the background** via the Scribe
- When the Scribe finishes (5-10s later), it tries to write to DB
- Meanwhile, ticks N+1, N+2, N+3 have all started their OWN compression operations
- **Multiple cancelled-but-still-running operations pile up, all trying to write**

The logs confirm this:
```
04:17:58 History manager tick timed out (2s)
04:18:11 History manager tick timed out (2s)
04:18:15 History manager tick timed out (2s)    ← every few seconds
04:18:22 History manager tick timed out (2s)
04:18:33 History manager tick timed out (2s)
04:18:39 History manager tick timed out (2s)
04:18:51 History manager tick timed out (2s)
04:18:52 Agentic processing error: database is locked     ← cascading failure
04:18:52 HistoryManager error for user turn: database is locked
04:18:52 Matrix storage error for user turn: database is locked
04:18:54 Librarian: Failed to update thread node: database is locked
```

Every cancelled tick leaves zombie writes in flight. Eventually they overwhelm the busy_timeout and the whole system locks.

---

## Fix: Non-Blocking Compression in History Manager

**File:** `src/luna/actors/history_manager.py`

### Change 1: Add a guard to prevent concurrent tick processing (line ~637)

Add a simple lock flag so ticks don't stack:

```python
async def tick(self) -> None:
    """
    Called on every cognitive loop cycle (~500ms-1s).
    Processes one compression and one extraction per tick.
    """
    # Guard: skip if previous tick is still running
    if getattr(self, '_tick_in_progress', False):
        return
    self._tick_in_progress = True
    try:
        await self._process_compression_queue()
        await self._process_extraction_queue()
        await self._check_archivable_turns()
    finally:
        self._tick_in_progress = False
```

This prevents the cascading zombie problem. If tick N is still running when tick N+1 fires, N+1 just skips. No pile-up.

### Change 2: Make compression non-blocking (line ~660)

The compression should NOT await the full LLM call inside the tick. Split it:

```python
async def _process_compression_queue(self) -> None:
    """Process one pending compression per tick."""
    matrix = await self._get_matrix()
    if not matrix:
        return

    row = await matrix.db.fetchone(
        """SELECT cq.id, cq.turn_id, ct.content, ct.role
           FROM compression_queue cq
           JOIN conversation_turns ct ON ct.id = cq.turn_id
           WHERE cq.status = 'pending'
           ORDER BY cq.queued_at ASC
           LIMIT 1"""
    )

    if not row:
        return

    queue_id, turn_id, content, role = row

    # Mark as processing (quick write, releases immediately)
    await matrix.db.execute(
        "UPDATE compression_queue SET status = 'processing' WHERE id = ?",
        (queue_id,)
    )

    # Fire compression as background task — DO NOT await
    import asyncio
    asyncio.create_task(
        self._do_compression(queue_id, turn_id, content, role)
    )
```

Then add the completion handler as a separate method:

```python
async def _do_compression(self, queue_id, turn_id, content, role):
    """Background: compress a turn and write result. Not called inside tick."""
    try:
        matrix = await self._get_matrix()
        if not matrix:
            return

        compressed = content[:200] + "..."  # fallback

        if self.engine:
            scribe = self.engine.get_actor("scribe")
            if scribe and hasattr(scribe, "compress_turn"):
                compressed = await scribe.compress_turn(content, role)

        await matrix.db.execute(
            """UPDATE conversation_turns
               SET compressed = ?, compressed_at = ?
               WHERE id = ?""",
            (compressed, time.time(), turn_id)
        )

        await self._generate_turn_embedding(turn_id, compressed, matrix)

        await matrix.db.execute(
            """UPDATE compression_queue
               SET status = 'completed', processed_at = ?
               WHERE id = ?""",
            (time.time(), queue_id)
        )

        logger.debug(f"HistoryManager: Compressed turn {turn_id}")

    except Exception as e:
        logger.error(f"HistoryManager: Background compression failed: {e}")
        try:
            matrix = await self._get_matrix()
            if matrix:
                await matrix.db.execute(
                    "UPDATE compression_queue SET status = 'failed' WHERE id = ?",
                    (queue_id,)
                )
        except Exception:
            pass
```

### Why This Works

1. **No zombie accumulation.** The `_tick_in_progress` guard means only ONE tick runs at a time. No pile-up.
2. **No LLM call blocking the tick.** Compression fires as a background task. The tick completes immediately. The write happens when the LLM returns, not inside the tick.
3. **busy_timeout (15s) is now sufficient.** With zombies eliminated, the only concurrent writers are legitimate operations. 15s is plenty of headroom for WAL to serialize them.

---

## Verification

Same tests as before:
- [ ] Run 29-test sovereign knowledge suite → zero "database is locked" errors
- [ ] Run 5 rapid-fire queries (< 1 second apart) → zero lock errors
- [ ] Check engine logs: no "History manager tick timed out" spam
- [ ] Check engine logs: compression still happening (look for "Compressed turn" messages)

---

## DO NOT
- DO NOT remove the busy_timeout PRAGMA (it's needed as a safety net)
- DO NOT change the cognitive tick interval
- DO NOT remove the 2-second timeout on history.tick() in engine.py
- DO NOT change _process_extraction_queue — it already uses fire-and-forget via mailbox
- DO NOT add connection pooling or multiple DB connections

**Estimated time: 20 minutes. Two changes in one file (history_manager.py).**
