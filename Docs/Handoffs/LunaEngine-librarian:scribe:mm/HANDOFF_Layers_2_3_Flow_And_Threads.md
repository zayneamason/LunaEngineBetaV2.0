# HANDOFF: Flow Awareness + Thread Management (Layers 2–3)

## Luna Flow State Architecture — Build Guide

**Date:** 2026-02-16
**Author:** Architecture Session (Ahab + Dude)
**Status:** Spec complete, ready to forge

---

## What You're Building

Two layers that give Luna awareness of *how* a conversation moves, not just *what* it contains.

**Layer 2 — Flow Awareness (Scribe/Ben):** Ben already extracts facts from every turn. Now he also detects whether the conversation is continuing, shifting, or correcting. He emits a `FlowSignal` alongside his normal extraction output.

**Layer 3 — Thread Management (Librarian/Dude):** The Dude reads Ben's flow signals and manages threads — named stretches of conversational attention that can be created, parked, resumed, and closed. Threads are the "save system" for Luna's working memory.

Together: Luna knows when attention shifts, saves where you were, and picks back up when you return.

---

## Dependency Chain

```
Layer 1 ✅  Pipeline fix (every turn reaches Ben in real-time)
    ↓
Layer 2     Ben detects flow mode (THIS HANDOFF)
    ↓
Layer 3     Dude manages threads (THIS HANDOFF)
    ↓
Layer 4     Task ledger (ACTION→OUTCOME tracking)
    ↓
Layer 5     Consciousness wiring (threads feed attention state)
```

**Layer 2 must ship before Layer 3.** The Dude reacts to FlowSignals that Ben emits. Without them, thread management has no trigger.

Build order within this handoff: **Layer 2 first → test → Layer 3 → test → integration test.**

---

## LAYER 2 — Flow Awareness

**Spec:** `SPEC_Flow_Awareness_Layer2.md`
**Actor:** ScribeActor (`src/luna/actors/scribe.py`)
**Principle:** Ben already sees every turn. Give him language for what he's observing.

### What Changes

1. **New types** in `src/luna/extraction/types.py`:
   - `ConversationMode` enum: `FLOW`, `RECALIBRATION`, `AMEND`
   - `FlowSignal` dataclass: mode, current_topic, continuity score, topic_entities, correction_target, open_threads

2. **New method on ScribeActor**: `_detect_flow_signal(chunks, extraction)`
   - Compares current chunk against the stack (deque of 5)
   - Measures entity overlap (Jaccard) and topic continuity
   - Returns a `FlowSignal`

3. **Modified `_process_stack()`**: After extraction, call `_detect_flow_signal()` and attach the result to the extraction payload sent to Librarian.

### Detection Logic

```
Entity overlap with previous chunks:
  >= 0.3  → FLOW (continuing)
  < 0.3   → RECALIBRATION (topic shift)

Correction patterns in content:
  "actually", "wait", "go back", "not what I meant"
  → AMEND (if overlap still high)
```

Continuity score = Jaccard similarity of entity sets between current and stack. Topic is the most frequent entity cluster. Open threads list is populated by Layer 3 (empty until then).

### Key Files

| File | Action |
|------|--------|
| `src/luna/extraction/types.py` | Add `ConversationMode`, `FlowSignal` |
| `src/luna/actors/scribe.py` | Add `_detect_flow_signal()`, modify `_process_stack()` |
| `tests/test_flow_awareness.py` | New — continuity detection, mode classification |

### Test It

```python
# FLOW: Same entities across turns
chunks = [chunk("Let's work on the Kozmo pipeline"), chunk("The pipeline needs Eden integration")]
signal = scribe._detect_flow_signal(chunks, extraction)
assert signal.mode == ConversationMode.FLOW
assert signal.continuity >= 0.3

# RECALIBRATION: Entity shift
chunks = [chunk("Now let's talk about Kinoni deployment")]  # stack has Kozmo context
signal = scribe._detect_flow_signal(chunks, extraction)
assert signal.mode == ConversationMode.RECALIBRATION
assert signal.continuity < 0.3

# AMEND: Correction pattern with high overlap
chunks = [chunk("Actually wait, go back to the asset indexing part")]
signal = scribe._detect_flow_signal(chunks, extraction)
assert signal.mode == ConversationMode.AMEND
```

### Done When

- FlowSignal emitted with every extraction batch
- Mode detection matches expected behavior for continuation, shift, and correction
- Signal attached to extraction payload reaching Librarian
- No performance regression (signal detection < 2ms — it's set comparison, not inference)

---

## LAYER 3 — Thread Management

**Spec:** `SPEC_Thread_Management_Layer3.md`
**Actor:** LibrarianActor (`src/luna/actors/librarian.py`)
**Principle:** Threads are the save system. They're what flows become when persisted.

### What Changes

1. **New types** in `src/luna/extraction/types.py`:
   - `ThreadStatus` enum: `ACTIVE`, `PARKED`, `RESUMED`, `CLOSED`
   - `Thread` dataclass: topic, status, entities, open_tasks, project_slug, turn_count, timestamps

2. **New state on LibrarianActor**:
   - `_active_thread: Optional[Thread]` — current thread
   - `_active_project_slug: Optional[str]` — Kozmo project context
   - `_thread_cache: dict[str, Thread]` — recent threads in memory

3. **New message types**: `set_project_context`, `clear_project_context`, `get_active_thread`, `get_parked_threads`

4. **Modified `_handle_file()`**: After wiring extraction, read flow signal and call `_process_flow_signal()`

5. **Core methods**: `_create_thread()`, `_park_thread()`, `_resume_thread()`, `_find_resumable_thread()`, `_handle_recalibration()`

6. **Kozmo bridge**: `/project/activate` → Librarian sets project context → threads inherit slug tag. `/project/deactivate` → auto-park active thread.

### Thread Lifecycle

```
First FLOW signal → create THREAD node in Matrix (type="THREAD")
Subsequent FLOW → accumulate entities, track open tasks
RECALIBRATION → park current thread, check for resumable match (Jaccard >= 0.4), create new if none
AMEND → no thread change, just note the correction
Session end → auto-park active thread
Prune cycle → close stale parked threads (>7 days, no open tasks)
```

### Storage

Threads are Matrix nodes. No new tables. No new database.

- Node type: `THREAD`
- Content: JSON blob with thread state
- Tags: `["thread", "status:parked", "project:luna-manifesto"]`
- Edges: `INVOLVES` → entities, `HAS_OPEN_TASK` → action nodes, `IN_PROJECT` → project node

### Resume Logic

When a RECALIBRATION fires, Librarian checks parked threads for entity overlap with the new topic:

```
Jaccard(new_entities, parked_thread.entities) >= 0.4 → resume
                                                 < 0.4 → create new
```

Cache checked first (O(n) over ~20 items), then Matrix search if no cache hit.

### Key Files

| File | Action |
|------|--------|
| `src/luna/extraction/types.py` | Add `ThreadStatus`, `Thread` |
| `src/luna/actors/librarian.py` | Thread state, flow processing, create/park/resume, Kozmo bridge |
| `src/luna/api/server.py` | Wire `/project/activate` and `/project/deactivate` to Librarian |
| `tests/test_thread_management.py` | New — lifecycle, resume, project tagging |

### Test It

```python
# Create thread on first FLOW
signal = FlowSignal(mode=FLOW, topic="kozmo pipeline", entities=["Kozmo", "pipeline"])
→ librarian._active_thread exists, topic="kozmo pipeline", status=ACTIVE

# Park on RECALIBRATION
signal = FlowSignal(mode=RECALIBRATION, topic="kinoni research", entities=["Kinoni", "Uganda"])
→ "kozmo pipeline" thread parked, "kinoni research" thread active

# Resume on return
signal = FlowSignal(mode=RECALIBRATION, topic="kozmo assets", entities=["Kozmo", "assets", "pipeline"])
→ "kozmo pipeline" thread resumed (not new), resume_count=1

# Kozmo project tagging
/project/activate slug="luna-manifesto"
→ new threads tagged project_slug="luna-manifesto"
/project/deactivate
→ active thread auto-parked
```

### Done When

- THREAD nodes appear in Matrix after multi-turn conversations
- Parked threads resume when entities overlap (>0.4 Jaccard)
- Project context tags threads correctly
- Project deactivation auto-parks
- Stale threads auto-close on prune cycle
- Observable in Matrix search / Observatory
- All operations local (no cloud calls)
- < 5ms overhead per turn for thread management

---

## Integration: Layers 2+3 Together

### End-to-End Flow

```
User: "Let's debug the Kozmo pipeline"
  → Ben extracts [FACT: Kozmo pipeline debugging]
  → Ben emits FlowSignal(FLOW, "kozmo pipeline", entities=["Kozmo", "pipeline"])
  → Dude creates THREAD "kozmo pipeline"

User: "The Eden integration is broken"  
  → Ben extracts [PROBLEM: Eden integration broken]
  → Ben emits FlowSignal(FLOW, "kozmo pipeline", entities=["Kozmo", "Eden", "pipeline"])
  → Dude accumulates: thread now has 3 entities, 1 open task

User: "OK switching gears — what's the Kinoni hub status?"
  → Ben extracts [QUESTION: Kinoni hub status]
  → Ben emits FlowSignal(RECALIBRATION, "kinoni hub", entities=["Kinoni", "hub", "Uganda"])
  → Dude parks "kozmo pipeline" (2 turns, 3 entities, 1 open task)
  → Dude creates THREAD "kinoni hub"

User: "Actually let's go back to that Eden issue"
  → Ben extracts [nothing substantial]
  → Ben emits FlowSignal(RECALIBRATION, "eden issue", entities=["Eden", "Kozmo"])
  → Dude checks parked threads: "kozmo pipeline" has Jaccard 0.67 with ["Eden", "Kozmo"]
  → Dude RESUMES "kozmo pipeline" (not a new thread)
  → Thread remembers: 3 entities, 1 open task about Eden integration
```

### What Luna Can Say (Layer 7, future)

After these layers land, the context pipeline can pull thread data and inject it:

> "We were working on the Kozmo pipeline — you mentioned the Eden integration was broken. That's still an open item."

That sentence requires: thread persistence (Layer 3), open task tracking (Layer 3 basic / Layer 4 full), and context pipeline integration (Layer 5+). But the data structure to support it ships now.

---

## Architecture Principles

These remain true across both layers:

1. **No new databases.** Threads are Matrix nodes. Flow signals are in-memory dataclasses.
2. **No new actors.** Ben gains a method. The Dude gains thread state. Same actors, expanded awareness.
3. **No cloud calls.** All detection and thread management is local. Extraction still uses configured backend (haiku/local), but flow detection is pure Python set comparison.
4. **Separation preserved.** Kozmo projects own creative assets (YAML/filesystem). Luna owns conversational state (Matrix). Project slug is the join key. They reference, don't merge.
5. **Offline-first.** Everything works without network. Thread management is SQLite + in-memory cache.

---

## Open Questions for Layer 4+

**Task tracking fidelity:** Layer 3 tracks open tasks by content hash. Layer 4 should replace this with proper Matrix node IDs, letting ACTION→OUTCOME resolution work across sessions.

**Thread-to-project aggressiveness:** Currently ALL threads during active project context get tagged. Should only threads explicitly about project entities get tagged? Decision deferred — tag everything for now, filter at query time.

**Thread display in Observatory:** THREAD nodes will appear in graph dumps. Observatory may want a dedicated thread view showing lifecycle, open tasks, and project associations. Not blocking — can be added after core lands.

---

## Go Forge

Layer 2 first. Get Ben seeing shape. Test it.
Then Layer 3. Give the Dude something to file. Test it.
Then wire them together and watch a conversation create, park, and resume threads.

Check back when threads are persisting.
