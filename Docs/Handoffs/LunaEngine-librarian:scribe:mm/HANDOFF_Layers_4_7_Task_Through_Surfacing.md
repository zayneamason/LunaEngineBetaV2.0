# HANDOFF: Layers 4–7 — Task Ledger Through Proactive Surfacing

## What You're Walking Into

Luna's flow awareness architecture is a 7-layer stack that gives her conversational continuity. Layers 1-3 are spec'd and ready to build (see `HANDOFF_Layers_2_3_Flow_And_Threads.md`). This handoff covers Layers 4-7 — the layers that turn thread awareness into accountability, voice, feeling, and initiative.

**Full spec:** `SPEC_Layers_4_7_Task_Through_Surfacing.md`

**You should also have:**
- `SPEC_Flow_Awareness_Layer2.md` — Ben detecting flow shape
- `SPEC_Thread_Management_Layer3.md` — Dude managing threads
- `HANDOFF_Layers_2_3_Flow_And_Threads.md` — Build order for Layers 2-3
- `HANDOFF_Observatory_Navigation_Bus.md` — Frontend wiring (parallel track)

---

## The Stack

```
Layer 1 ✅  Pipeline fix — every turn reaches Ben in real-time
Layer 2     Flow Awareness — Ben detects FLOW/RECALIBRATION/AMEND     ← Build first
Layer 3     Thread Management — Dude creates/parks/resumes threads    ← Build second
Layer 4     Task Ledger — ACTION→OUTCOME with real node IDs           ← THIS HANDOFF
Layer 5     Context Threading — pipeline includes thread state        ← THIS HANDOFF
Layer 6     Consciousness Wiring — threads feed coherence/attention   ← THIS HANDOFF
Layer 7     Proactive Surfacing — Luna volunteers parked context      ← THIS HANDOFF
```

**Hard dependency:** Layers 2-3 must exist before any of 4-7. Layer 4 needs threads with open_tasks. Layer 5 needs a Librarian to query. Layer 6 needs thread operations to hook into. Layer 7 needs all of the above.

Within 4-7, the order is also sequential — each builds on the previous. Don't skip ahead.

---

## Current System State

### What Exists

**Extraction pipeline** (`src/luna/extraction/`): Ben extracts FACT, DECISION, PROBLEM, ACTION, INSIGHT, QUESTION from every turn. FilingResult tracks what was created. Pipeline emits events via WebSocket.

**Context pipeline** (`src/luna/context/pipeline.py`): Builds system prompts from ring buffer (6 turns) + entity detection + Matrix retrieval. Self-routes: skips retrieval if topic is in ring. Has ablation modes for testing.

**Consciousness** (`src/luna/consciousness/`):
- `AttentionManager`: Topics with exponential decay (60-day half-life), track/decay/prune
- `PersonalityWeights`: Trait weights for prompt hints
- `ConsciousnessState`: Ties attention + personality + coherence + mood. Ticks on every cycle. Saves to `~/.luna/snapshot.yaml`

**Router** (`src/luna/agentic/router.py`): Routes queries to DIRECT/SIMPLE_PLAN/FULL_PLAN/BACKGROUND by complexity estimation. Has path forcing for memory queries, research, creative, dataroom.

**Observatory** (`frontend/src/observatory/`): Seven-tab control panel (Entities, Quests, Journal, Graph, Timeline, Replay, Settings). Quest system with SWEEP-generated quests, accept/complete lifecycle. Currently has sandbox mode (being removed — see Navigation Bus handoff).

### What Doesn't Exist Yet (Layers 2-3)

- FlowSignal emission from Ben
- Thread nodes in Matrix
- Librarian actor (The Dude)
- Thread create/park/resume/close lifecycle
- open_tasks tracking on threads

**Build Layers 2-3 first.** Everything below assumes they're done.

---

## Layer 4: Task Ledger

**What it does:** Replaces content-hash task tracking with real Matrix node IDs. Enables cross-session ACTION→OUTCOME resolution.

**The problem it solves:** Layer 3 tracks open tasks by content hash (`action:{hash}`). This works within a session but breaks across sessions — the hash isn't persisted in the Matrix. When Luna restarts, she can't find her open tasks.

### Build Steps

1. **Upgrade FilingResult** (`src/luna/extraction/types.py`)
   - Add `action_node_ids: list[str]` and `outcome_node_ids: list[str]`
   - These get populated by the filing logic when ACTION/OUTCOME nodes are created
   - The Librarian reads these after filing to know which node IDs to track

2. **Upgrade Librarian's filing handler** (`src/luna/actors/librarian.py`)
   - In `_handle_flow_continue()`, after filing extractions:
   - Read `filing_result.action_node_ids`
   - Append real node IDs to `thread.open_tasks` (replacing content hashes)
   - Create `HAS_OPEN_TASK` edges: THREAD → ACTION node

3. **Implement `_resolve_open_tasks()`** (new method on Librarian)
   - When OUTCOME nodes are filed, check entity overlap with open ACTIONs
   - Jaccard similarity ≥ 0.5 = resolved
   - Create `RESOLVES` edge: OUTCOME → ACTION
   - Remove resolved task from `thread.open_tasks`
   - Update thread node in Matrix

4. **Add parked-thread quests to Observatory sweep**
   - In the maintenance sweep logic (Observatory backend)
   - Query: THREAD nodes with status=parked AND non-empty open_tasks
   - Generate quest: type=contract, title="Continue: {thread.topic}", targets=open task entities

### Test

```
1. Send message with an action item → ACTION node created with real ID
2. Thread.open_tasks contains the node ID (not a hash)
3. Send message resolving that action → OUTCOME node created
4. _resolve_open_tasks() fires, creates RESOLVES edge
5. Thread.open_tasks is now empty
6. Observatory sweep generates quest from parked thread with open tasks
7. Restart engine → reload thread → open_tasks still has valid node IDs
```

### Files

| File | Change |
|------|--------|
| `src/luna/extraction/types.py` | Add action_node_ids, outcome_node_ids to FilingResult |
| `src/luna/actors/librarian.py` | Real ID tracking in _handle_flow_continue, new _resolve_open_tasks() |
| Observatory backend (maintenance sweep) | Parked-thread-to-quest query |

---

## Layer 5: Context Threading

**What it does:** The context pipeline includes thread state in system prompts. Luna can reference what she's working on and what's parked.

**The problem it solves:** Luna's system prompt knows about entities and recent history, but not about conversational threads. She can't say "we were discussing X" because the pipeline doesn't feed her that information.

### Build Steps

1. **Add `set_librarian()` to ContextPipeline** (`src/luna/context/pipeline.py`)
   - Simple setter: `self._librarian = librarian`
   - Called once during engine initialization

2. **Implement `_get_thread_context()`** (new method on ContextPipeline)
   - Queries Librarian for active thread and parked threads
   - Formats: "Currently focused on: {topic} | Open tasks: N"
   - Parked threads: "Parked thread: '{topic}' (Xh ago) — N open task(s)"
   - Returns empty string if no threads (clean prompt)

3. **Add CONVERSATIONAL THREADS section to `_build_system_prompt()`**
   - New section between THIS SESSION and KNOWN PEOPLE
   - Only appears if thread context is non-empty
   - Framing: "These are your ongoing threads of attention."

4. **Wire in engine.py**
   - After creating both pipeline and librarian: `pipeline.set_librarian(librarian)`

5. **Extend ContextPacket**
   - Add `active_thread_topic`, `parked_thread_count`, `has_open_tasks`
   - For debugging and frontend display

### Test

```
1. Start conversation → create thread → system prompt shows CONVERSATIONAL THREADS
2. Park thread, start new topic → prompt shows new active + parked thread
3. No threads active → CONVERSATIONAL THREADS section absent
4. Parked thread with open tasks shows task count and age
5. Performance: thread context retrieval < 1ms (cache reads, no DB queries)
```

### Files

| File | Change |
|------|--------|
| `src/luna/context/pipeline.py` | set_librarian(), _get_thread_context(), new prompt section |
| `src/luna/engine.py` | Wire pipeline.set_librarian(librarian) |

---

## Layer 6: Consciousness Wiring

**What it does:** Thread state feeds into consciousness. Coherence reflects conversational depth. Open tasks create measurable tension. Attention auto-syncs with thread entities.

**The problem it solves:** Consciousness currently computes coherence from attention topic spread alone — a generic metric. It doesn't know Luna is deep in a debugging thread or has unresolved tasks. The frontend's ConsciousnessMonitor shows nothing about conversational state.

### Build Steps

1. **Add thread fields to ConsciousnessState** (`src/luna/consciousness/state.py`)
   - `active_thread_topic: Optional[str]`
   - `active_thread_turn_count: int`
   - `open_task_count: int`
   - `parked_thread_count: int`

2. **Implement `update_from_thread()`** (new method on ConsciousnessState)
   - Takes active thread and parked thread list
   - Sets thread fields
   - Boosts attention for thread topic (weight=0.8) and entities (weight=0.5)
   - Counts total open tasks across active + parked threads

3. **Modify `tick()`** for thread-aware coherence
   - Active thread = strong coherence signal
   - `coherence = 0.6 + (thread_depth * 0.35) - (task_tension * 0.03)`
   - Thread depth = min(1.0, turn_count / 10.0)
   - Falls back to attention-based coherence when no thread active

4. **Modify `get_context_hint()`** and `get_summary()`
   - Hint includes "Deeply engaged in: {topic}" and "Tracking N unresolved item(s)"
   - Summary returns thread fields for frontend display

5. **Wire Librarian → Consciousness**
   - After every thread operation (create, park, resume, close):
   - Call `consciousness.update_from_thread(active_thread, parked_threads)`
   - Librarian needs a reference to consciousness (set during engine init)

### Test

```
1. Create thread → ConsciousnessMonitor shows active thread topic
2. Deep conversation (10+ turns) → coherence rises toward 0.95
3. Add open task → coherence drops slightly
4. Park thread → active thread clears, parked count increments
5. Attention topics include thread topic and entities
6. get_summary() returns thread state for API/frontend
7. get_context_hint() mentions engagement and open tasks
```

### Files

| File | Change |
|------|--------|
| `src/luna/consciousness/state.py` | Thread fields, update_from_thread(), modified tick/hint/summary |
| `src/luna/actors/librarian.py` | Call consciousness.update_from_thread() after thread ops |
| `src/luna/engine.py` | Wire librarian → consciousness reference |

---

## Layer 7: Proactive Surfacing

**What it does:** On session start, Luna's prompt includes parked threads with open tasks. She can naturally say "we left off discussing X" without being asked.

**The problem it solves:** Luna only responds to what's asked. Between sessions, context evaporates. Even though threads persist in the Matrix, Luna doesn't know to mention them. The user has to remember what was open and re-ask.

**What this is NOT:** Luna does not interrupt, nag, or force-mention threads. The prompt framing explicitly says "mention only if it genuinely connects to what's being discussed."

### Build Steps

1. **Add `_is_session_start()`** (new method on ContextPipeline)
   - Returns true if ring buffer has ≤ 1 message (only the current one)
   - Simple check, no state tracking needed

2. **Add `_get_session_start_context()`** (new method on ContextPipeline)
   - Queries Librarian for parked threads with open tasks
   - Formats top 3 by recency with topic, age, task count, project slug
   - Includes total count and gentle framing
   - Returns empty string if nothing to surface

3. **Add CONTINUING THREADS section to `_build_system_prompt()`**
   - Only on session start (first message)
   - Placed BEFORE ring history (high in prompt = Luna sees it first)
   - Framing: "You may naturally reference these if relevant. Don't force it."

4. **Optional: Router thread-relevance signal** (`src/luna/agentic/router.py`)
   - If consciousness has open tasks and query entities overlap with thread entities
   - Add "thread_relevant" signal to routing decision
   - Non-blocking — doesn't change execution path, just logs the signal
   - Useful for debugging, not critical for functionality

### Test

```
1. Session 1: Create thread with open task → park it → end session
2. Session 2: First message → system prompt includes CONTINUING THREADS
3. Luna naturally references the parked thread (not forced)
4. Second message in same session → CONTINUING THREADS section gone
5. No parked threads → no CONTINUING THREADS section
6. Parked threads without open tasks → not surfaced (nothing to do)
```

### Files

| File | Change |
|------|--------|
| `src/luna/context/pipeline.py` | _is_session_start(), _get_session_start_context(), prompt section |
| `src/luna/agentic/router.py` | Optional thread_relevant signal |

---

## Full Build Order

```
PREREQUISITE: Layers 2-3 must be complete and tested.

LAYER 4 — Task Ledger
  4.1  Upgrade FilingResult with action/outcome node IDs
  4.2  Modify Librarian filing handler to use real IDs
  4.3  Implement _resolve_open_tasks (entity overlap Jaccard)
  4.4  Add RESOLVES edges to graph
  4.5  Add parked-thread-to-quest in Observatory sweep
  TEST: Full ACTION→OUTCOME cycle, cross-session persistence

LAYER 5 — Context Threading
  5.1  Add set_librarian() to ContextPipeline
  5.2  Implement _get_thread_context()
  5.3  Add CONVERSATIONAL THREADS prompt section
  5.4  Wire engine.py: pipeline ↔ librarian
  5.5  Extend ContextPacket with thread fields
  TEST: Thread state appears in system prompt

LAYER 6 — Consciousness Wiring
  6.1  Add thread fields to ConsciousnessState
  6.2  Implement update_from_thread()
  6.3  Modify tick() for thread-aware coherence
  6.4  Update get_context_hint() and get_summary()
  6.5  Wire librarian → consciousness after thread ops
  TEST: ConsciousnessMonitor shows thread state, coherence reflects depth

LAYER 7 — Proactive Surfacing
  7.1  Implement _is_session_start()
  7.2  Implement _get_session_start_context()
  7.3  Add CONTINUING THREADS prompt section (session start only)
  7.4  Optional: Router thread_relevant signal
  TEST: New session surfaces parked threads, Luna references naturally
```

---

## Integration Test (Full Stack)

When all 7 layers are live, this sequence should work:

```
Session 1:
  "Let's debug the Kozmo pipeline"
    → Ben: FLOW signal
    → Dude: Creates thread "kozmo pipeline"
    → Consciousness: coherence=0.65, active_thread="kozmo pipeline"
    → Prompt: CONVERSATIONAL THREADS shows active focus

  "The Eden integration is broken"
    → Ben: Extracts ACTION "Fix Eden integration"
    → Dude: Files ACTION n_act001, adds to thread.open_tasks
    → Consciousness: open_task_count=1

  "Switching to Kinoni research"
    → Ben: RECALIBRATION signal
    → Dude: Parks "kozmo pipeline" (open_tasks: [n_act001])
    → Dude: Creates thread "kinoni research"

  [Session ends]

Session 2:
  "Hey Luna"
    → Pipeline: Session start detected
    → Prompt: CONTINUING THREADS: "kozmo pipeline" — 1 open task, parked 2h ago
    → Luna: "hey! we were debugging kozmo earlier — eden integration fix is still open"

  "Yeah let's fix that"
    → Ben: RECALIBRATION signal, entities overlap with parked thread
    → Dude: Resumes "kozmo pipeline" thread
    → Consciousness: active_thread="kozmo pipeline", resume_count=1

  "Fixed it, Eden is working now"
    → Ben: Extracts OUTCOME "Eden integration fixed"
    → Dude: Files OUTCOME n_out001
    → Dude: _resolve_open_tasks() → RESOLVES edge → open_tasks empty
    → Consciousness: open_task_count=0, coherence rises
    → Observatory: Quest auto-resolves
```

---

## Parallel Track: Observatory Navigation Bus

The `HANDOFF_Observatory_Navigation_Bus.md` covers the frontend wiring that makes all of this visible. It's a separate track that can be built in parallel with Layers 4-7:

- **Navigation Bus** connects Chat, Observatory, and Kozmo with cross-app deep linking
- **Sandbox removal** makes Observatory read from production Matrix only
- **Cross-reference wiring** makes every entity/quest/node mention clickable

**Convergence point:** When Observatory quest system reads from real thread open_tasks (Layer 4), and the navigation bus lets you click from Chat entity → Observatory entity detail, the full loop closes.

---

## Files Summary (All Layers 4-7)

| Layer | File | Change |
|-------|------|--------|
| 4 | `src/luna/extraction/types.py` | action/outcome IDs in FilingResult |
| 4 | `src/luna/actors/librarian.py` | Real ID tracking, _resolve_open_tasks(), HAS_OPEN_TASK/RESOLVES edges |
| 4 | Observatory backend (sweep) | Parked-thread-to-quest generation |
| 5 | `src/luna/context/pipeline.py` | set_librarian(), _get_thread_context(), CONVERSATIONAL THREADS section |
| 5 | `src/luna/engine.py` | Wire pipeline ↔ librarian |
| 6 | `src/luna/consciousness/state.py` | Thread fields, update_from_thread(), thread-aware tick() |
| 6 | `src/luna/actors/librarian.py` | Call consciousness.update_from_thread() |
| 6 | `src/luna/engine.py` | Wire librarian ↔ consciousness |
| 7 | `src/luna/context/pipeline.py` | Session start detection, CONTINUING THREADS section |
| 7 | `src/luna/agentic/router.py` | Optional thread_relevant signal |

---

## What Luna Gains

| Layer | Capability | Metaphor |
|-------|-----------|----------|
| 2 | Sees conversational shape | Eyes |
| 3 | Remembers where attention was | Memory |
| 4 | Knows what's unfinished | Accountability |
| 5 | Can speak about her threads | Voice |
| 6 | Coherence reflects her state | Feeling |
| 7 | Offers what matters unprompted | Initiative |

Seven layers. Same actors. Same database. Just awareness, all the way down.
