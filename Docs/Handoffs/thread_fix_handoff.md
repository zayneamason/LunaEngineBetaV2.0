# Thread System Fix — Claude Code Handoff

## What Changed

**File:** `src/luna/actors/scribe.py`
**Commit:** `fix: wire flow assessment into immediate extraction path`

A single code path was missing flow assessment. The `immediate=True` branch in `ScribeActor._handle_extract_turn()` bypassed `_assess_flow()`, which meant `FlowSignal` was never attached to extractions, and the Librarian's thread management code never received a signal to create THREAD nodes.

### The Fix (Diff)

In `_handle_extract_turn()`, the `immediate` block changed from:

```python
if immediate and chunks:
    extraction, entity_updates = await self._extract_chunks(chunks)
    if not extraction.is_empty():
        await self._send_to_librarian(extraction)
    for update in entity_updates:
        await self._send_entity_update_to_librarian(update)
    return
```

To:

```python
if immediate and chunks:
    extraction, entity_updates = await self._extract_chunks(chunks)

    # Assess conversational flow (Layer 2)
    raw_text = "\n".join(chunk.content for chunk in chunks)
    flow_signal = self._assess_flow(extraction, raw_text)
    extraction.flow_signal = flow_signal

    # Log flow state
    logger.info(...)

    # Send to Librarian when flow signal exists, even on empty extractions
    if not extraction.is_empty() or extraction.flow_signal is not None:
        await self._send_to_librarian(extraction)

    for update in entity_updates:
        await self._send_entity_update_to_librarian(update)
    return
```

### Why It Was Broken

Every call from `engine.py:_trigger_extraction()` sends `immediate=True`. The batched path (`_process_stack()`) was the only place that called `_assess_flow()`. Since immediate mode always returned early, `_process_stack()` never ran, and the entire thread system was dark.

---

## Verification Tasks

### 1. Confirm the Fix Compiles and Doesn't Break Imports

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
python -c "from luna.actors.scribe import ScribeActor; print('OK')"
```

### 2. Trace the Full Signal Chain

Verify that these steps connect end-to-end:

| Step | Location | What Happens |
|------|----------|-------------|
| 1 | `engine.py:_trigger_extraction()` | Sends `extract_turn` with `immediate=True` to Scribe |
| 2 | `scribe.py:_handle_extract_turn()` | Extracts chunks, **now calls `_assess_flow()`** |
| 3 | `scribe.py:_assess_flow()` | Produces `FlowSignal` (mode, topic, entities, continuity) |
| 4 | `scribe.py:_send_to_librarian()` | Sends `ExtractionOutput` with `flow_signal` attached |
| 5 | `librarian.py:_handle_file()` | Deserializes `ExtractionOutput.from_dict()` including `flow_signal` |
| 6 | `librarian.py:_process_flow_signal()` | Routes to `_handle_flow_continue`, `_handle_recalibration`, or `_handle_amend` |
| 7 | `librarian.py:_create_thread()` | Creates THREAD node via `matrix.add_node(node_type="THREAD", ...)` |
| 8 | `librarian.py:_notify_consciousness()` | Calls `consciousness.update_from_thread()` |

**Check:** Does `ExtractionOutput.to_dict()` → `ExtractionOutput.from_dict()` correctly round-trip the `flow_signal` field? (It should — `from_dict` has `FlowSignal.from_dict(flow_data) if flow_data else None`)

### 3. Check for Duplicate Flow Assessment

The batched path in `_process_stack()` still runs `_assess_flow()` independently. Verify there's no scenario where both paths fire for the same turn:

- When `immediate=True`: chunks are processed and method returns. Stack is never populated.
- When `immediate=False` (or not set): chunks go to stack, `_process_stack()` fires at batch threshold.

**Expected:** Mutually exclusive. No double-assessment possible.

### 4. Verify Entity Hint Gating Still Works

The entity hint gating (`_last_entity_hints`) consumes and resets hints before reaching the immediate block. Confirm:

- If `_last_entity_hints == []` (empty list from NER): extraction is skipped entirely, flow assessment does NOT run. This is correct — pure chat turns shouldn't create threads.
- If `_last_entity_hints == None` (no hints received): extraction proceeds normally with flow assessment.
- If `_last_entity_hints` has entities: extraction proceeds normally with flow assessment.

### 5. Check `_assess_flow` State Accumulation

`_assess_flow()` uses instance state:
- `self._recent_entities` (deque, maxlen=5)
- `self._current_topic`
- `self._current_entities`
- `self._turn_count_in_flow`
- `self._open_actions`

**Verify:** This state accumulates correctly across immediate calls. Each call to `_assess_flow()` should update these fields, so the next call has history to compare against. The first call will always produce `entity_overlap=1.0` (no history), which maps to `ConversationMode.FLOW`, which creates the initial thread. Subsequent calls compare against accumulated history.

### 6. Verify Thread Node Persistence

Check that `matrix.add_node(node_type="THREAD", ...)` in `librarian.py:_create_thread()` actually writes to the SQLite database. Specifically:

```bash
# After running Luna with a few conversation turns, check:
sqlite3 data/memory_matrix.db "SELECT COUNT(*) FROM nodes WHERE node_type = 'THREAD'"
```

If count is still 0 after the fix, the break is deeper — possibly in MatrixActor or the database layer.

### 7. Edge Cases to Consider

- **Empty extraction + flow signal:** The fix sends to Librarian even when extraction is empty (matching `_process_stack()` behavior). Verify Librarian handles this: `_wire_extraction()` returns empty `FilingResult`, then `_process_flow_signal()` runs. The `filing_result` will have empty `action_node_ids` and `outcome_node_ids`, which is fine.

- **Very short messages (< 10 chars):** Filtered at `engine.py:_trigger_extraction()` before reaching Scribe. No flow assessment. This means very short messages create gaps in flow tracking. Acceptable for now.

- **Assistant turns:** Filtered at top of `_handle_extract_turn()` with `role == "assistant"` check. No flow assessment on Luna's own responses. Correct behavior.

---

## Architecture Context

### The 7-Layer Flow System

| Layer | Component | Status |
|-------|-----------|--------|
| 1 | Extraction (Scribe) | ✅ Working |
| 2 | Flow Assessment (Scribe._assess_flow) | ✅ **Fixed** — now runs on immediate path |
| 3 | Thread Management (Librarian) | ✅ Working — was waiting for signals |
| 4 | Task Ledger (Librarian, ACTION/OUTCOME tracking) | ✅ Working — wired into thread flow |
| 5 | Public Accessors (get_active_thread, get_parked_threads) | ✅ Working |
| 6 | Consciousness Wiring (_notify_consciousness) | ⚠️ Needs verification — does set_consciousness() get called during engine init? |
| 7 | Context Register (proposed) | ❌ Not yet implemented |

### Key Files

```
src/luna/actors/scribe.py          — Extraction + flow assessment
src/luna/actors/librarian.py       — Thread management + filing
src/luna/extraction/types.py       — FlowSignal, Thread, ConversationMode models
src/luna/consciousness/state.py    — ConsciousnessState.update_from_thread()
src/luna/engine.py                 — _trigger_extraction() call site
```

### Downstream Question

Once THREAD nodes are being created, verify that `consciousness.update_from_thread()` is actually wired. The Librarian has `set_consciousness()` and `_notify_consciousness()`, but someone needs to call `librarian.set_consciousness(consciousness_instance)` during engine initialization. If that call is missing, threads will be created and persisted but consciousness won't know about them.

Check `engine.py` init/setup for something like:
```python
librarian.set_consciousness(self.consciousness)
```
