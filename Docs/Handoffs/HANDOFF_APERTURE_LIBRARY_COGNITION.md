# HANDOFF: Aperture & Library Cognition System

## Context

This handoff implements the Luna Protocol: Aperture & Library Cognition v1.0.
The protocol defines how Luna's cognition extends beyond her core Memory Matrix
into external knowledge collections managed by Aibrarian, controlled by a
focus-aperture system.

**Protocol document:** `Luna_Protocol_Aperture_Library_Cognition_v1.docx`
(in project knowledge / data room)

**What this achieves:**
- Collections organize by lock-in (usage-driven, automatic)
- Aperture controls how wide Luna looks during recall (user-adjustable)
- Annotations bridge collection knowledge into Memory Matrix (only bridge)
- Provenance tracking on every collection-sourced fragment
- Luna retains agency to break through aperture for urgent/important info

---

## Systems Audit: What Exists

Before building anything, audit these files. They're the foundation.

### Lock-In (EXISTS — needs collection-level extension)

**Node-level lock-in:**
```
src/luna/substrate/lock_in.py
```
- `compute_lock_in()` — weighted sigmoid of activity signals
- Weights: retrieval 0.4, reinforcement 0.3, network 0.2, tag_siblings 0.1
- `classify_state()` — settled (≥0.70), fluid (0.30-0.70), drifting (<0.30)
- Bounds: LOCK_IN_MIN=0.15, LOCK_IN_MAX=0.85
- Config via `LockInConfig` dataclass

**Cluster-level lock-in:**
```
src/luna/memory/lock_in.py
```
- `LockInCalculator` class — cluster-level with exponential decay
- State-dependent decay lambdas: crystallized=0.00001, settled=0.0001, fluid=0.001, drifting=0.01
- Components: node(0.4), access(0.3), edge(0.2), age(0.1)
- Logarithmic access boost (Gemini correction)
- THIS IS THE PATTERN TO FOLLOW for collection lock-in

### Aibrarian Engine (EXISTS — needs aperture integration)

```
src/luna/substrate/aibrarian_engine.py
```
- `AiBrarianEngine` class — universal document database interface
- Registry-based collection management via YAML config
- Search: keyword (FTS5), semantic (sqlite-vec), hybrid (RRF fusion)
- Per-collection SQLite databases with embeddings
- Ingestion pipeline: read → chunk → embed
- Entity extraction, timeline, analytics already built
- **No lock-in computation on collections currently**
- **No aperture/scope filtering**
- **No annotation system**

### Context Assembler (EXISTS — aperture hooks here)

```
src/luna/context/assembler.py
```
- `PromptAssembler.build()` — single funnel for all prompt construction
- Layer ordering: Identity → Grounding → Access → Mode → Constraints → Expression → Temporal → Perception → Register → Memory → Consciousness → Voice
- **Memory resolution chain:** framed_context → memories list → memory_context string → auto-fetch → None
- `MemoryConfidence` dataclass — confidence signals (NONE/LOW/MEDIUM/HIGH)
- **This is where aperture reshapes what context gets assembled**
- Memory layer (4.0) is the insertion point for collection-sourced content

### Context Pipeline (EXISTS — aperture wires through here)

```
src/luna/context/pipeline.py
```
- Manages context assembly pipeline
- Where memory fetch occurs before reaching assembler

### Smart Fetch / Memory Tools (EXISTS — aperture extends these)

```
src/luna/tools/memory_tools.py
```
- MCP-accessible memory operations
- `luna_smart_fetch` — hybrid search (FTS5 + vectors + graph)
- This is the recall entry point that aperture will reshape

### App Context (PARTIAL — needs aperture declarations)

```
src/luna/services/guardian/  (exists)
src/luna/services/kozmo/     (exists)
```
- Guardian and Kozmo services exist as substrates
- **No focus declaration or default aperture per app**
- **No aperture context in PromptRequest**

### Aibrarian Registry (EXISTS — needs lock-in fields)

```
config/aibrarian_registry.yaml
```
- Collection definitions with keys, paths, configs
- **No lock-in tracking fields**
- **No aperture tag associations**

---

## What to Build

### Phase 1: Collection Lock-In Engine

**Create:** `src/luna/substrate/collection_lock_in.py`

Mirror the pattern from `src/luna/memory/lock_in.py` (cluster lock-in) with
library-adjusted parameters:

```python
# Collection-level signals (different from node/cluster)
COLLECTION_WEIGHTS = {
    'access': 0.40,       # How often Luna queries/opens this collection
    'annotation': 0.30,   # How many bookmarks/notes/flags Luna has made
    'connections': 0.20,  # Cross-references to other collections
    'entity_overlap': 0.10,  # Entities shared with Memory Matrix
}

# Library-adjusted decay rates (MUCH slower than memory nodes)
COLLECTION_DECAY_LAMBDAS = {
    'settled': 0.0000005,    # ~16 day half-life (books don't disappear)
    'fluid': 0.00005,        # ~3.8 hours half-life
    'drifting': 0.0005,      # ~23 minutes half-life
}

# Floor: no collection ever reaches zero
COLLECTION_LOCK_IN_MIN = 0.05
```

**Key differences from memory lock-in:**
- Decay is dramatically slower (books get dusty, they don't vanish)
- Access signal includes searches AND document opens
- Annotation count is a first-class signal (the bridge mechanism)
- Minimum floor of 0.05 (not 0.15 like nodes)

**Schema addition — add to collection tracking:**
```sql
CREATE TABLE IF NOT EXISTS collection_lock_in (
    collection_key TEXT PRIMARY KEY,
    lock_in REAL DEFAULT 0.15,
    state TEXT DEFAULT 'drifting',
    access_count INTEGER DEFAULT 0,
    annotation_count INTEGER DEFAULT 0,
    connected_collections INTEGER DEFAULT 0,
    entity_overlap_count INTEGER DEFAULT 0,
    last_accessed_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

**Where this table lives:** In the main Luna engine database (alongside
memory_nodes, clusters, entities), NOT in individual collection databases.
Collections are external. Lock-in tracking is Luna's internal state about them.

**Verification:**
- [ ] `compute_collection_lock_in(key)` returns 0.05–1.0
- [ ] `classify_state()` matches thresholds: settled ≥0.70, fluid 0.30–0.70, drifting <0.30
- [ ] Decay is state-dependent (settled decays slowest)
- [ ] Access bumps lock-in on every search/open
- [ ] Lock-in persists across sessions

---

### Phase 2: Annotation System (The Only Bridge)

**Create:** `src/luna/substrate/collection_annotations.py`

Annotations are how collection knowledge enters Luna's Memory Matrix.
Three types:

```python
class AnnotationType(str, Enum):
    BOOKMARK = "bookmark"   # 🔖 mark for later
    NOTE = "note"           # 📝 Luna's interpretation
    FLAG = "flag"           # 🚩 needs attention
```

**Schema — add to main engine database:**
```sql
CREATE TABLE IF NOT EXISTS collection_annotations (
    id TEXT PRIMARY KEY,
    collection_key TEXT NOT NULL,
    doc_id TEXT NOT NULL,
    chunk_index INTEGER,
    annotation_type TEXT NOT NULL,  -- bookmark, note, flag
    content TEXT,                    -- Luna's note text (for notes)
    matrix_node_id TEXT,            -- ID of the Memory Matrix node created
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (collection_key) REFERENCES collection_lock_in(collection_key)
);
```

**When Luna annotates:**
1. Create annotation record in `collection_annotations`
2. Create a new node in Memory Matrix with:
   - `node_type`: "ANNOTATION"
   - `content`: Luna's note text
   - `tags`: include `["aibrarian", collection_key, doc_id]`
   - `confidence`: 1.0 (Luna chose to note this)
3. Store the Matrix node ID back in the annotation record
4. Increment `annotation_count` in `collection_lock_in`
5. Provenance metadata on the Matrix node:
   ```json
   {
     "source": "aibrarian",
     "collection": "dataroom",
     "doc_id": "uuid-here",
     "chunk_index": 3,
     "annotation_type": "note",
     "original_text_preview": "first 200 chars of source chunk..."
   }
   ```

**The Wall (non-negotiable):**
- Annotation nodes in Memory Matrix are tagged `source=aibrarian`
- They are NEVER treated as native memory during recall
- They carry provenance that traces back to the collection
- No amount of lock-in dissolves this distinction

**Verification:**
- [ ] Annotation creates both annotation record AND Matrix node
- [ ] Matrix node has full provenance metadata
- [ ] `annotation_count` increments in lock-in table
- [ ] Annotations are queryable by collection, by type, by date
- [ ] Deleting an annotation does NOT delete the Matrix node (Luna's note is hers)

---

### Phase 3: Aperture Context Layer

**Create:** `src/luna/context/aperture.py`

This is the cognitive focus control system. It determines what knowledge
surfaces during recall based on app context + user override + lock-in.

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class AperturePreset(str, Enum):
    TUNNEL = "tunnel"       # 15° — project focus only
    NARROW = "narrow"       # 35° — project + related
    BALANCED = "balanced"   # 55° — focus with peripheral awareness (DEFAULT)
    WIDE = "wide"           # 75° — broad recall, light filtering
    OPEN = "open"           # 95° — full memory access, no filtering


APERTURE_ANGLES = {
    AperturePreset.TUNNEL: 15,
    AperturePreset.NARROW: 35,
    AperturePreset.BALANCED: 55,
    AperturePreset.WIDE: 75,
    AperturePreset.OPEN: 95,
}


@dataclass
class ApertureState:
    """Current cognitive focus state."""
    preset: AperturePreset = AperturePreset.BALANCED
    angle: int = 55
    focus_tags: list[str] = field(default_factory=list)
    active_project: Optional[str] = None
    active_collection_ids: list[str] = field(default_factory=list)
    app_context: str = "companion"  # kozmo, guardian, eclissi, companion, dataroom
    user_override: bool = False     # True if user manually adjusted

    @property
    def breakthrough_threshold(self) -> float:
        """Higher threshold = harder to break through focus."""
        return 0.30 + ((95 - self.angle) / 95) * 0.50

    @property
    def inner_ring_threshold(self) -> float:
        """Lock-in threshold for inner ring inclusion."""
        thresholds = {
            AperturePreset.TUNNEL: 0.75,
            AperturePreset.NARROW: 0.60,
            AperturePreset.BALANCED: 0.40,
            AperturePreset.WIDE: 0.25,
            AperturePreset.OPEN: 0.0,
        }
        return thresholds.get(self.preset, 0.40)


# Default aperture per app context
APP_DEFAULTS = {
    "kozmo": AperturePreset.NARROW,
    "guardian": AperturePreset.BALANCED,
    "eclissi": AperturePreset.WIDE,
    "companion": AperturePreset.BALANCED,
    "dataroom": AperturePreset.TUNNEL,
}
```

**Verification:**
- [ ] Breakthrough threshold at TUNNEL (15°) = 0.72
- [ ] Breakthrough threshold at BALANCED (55°) = 0.51
- [ ] Breakthrough threshold at OPEN (95°) = 0.30
- [ ] Each app context has a default aperture
- [ ] User override flag tracks manual adjustment

---

### Phase 4: Recall Pipeline Integration

**Modify:** `src/luna/context/assembler.py`

This is the critical integration point. The aperture reshapes what context
gets assembled in the Memory layer (Layer 4.0).

**Step 1: Add `ApertureState` to `PromptRequest`:**
```python
@dataclass
class PromptRequest:
    # ... existing fields ...
    aperture: Optional["ApertureState"] = None  # Cognitive focus state
```

**Step 2: Add aperture-aware memory resolution.**

Create new method in assembler or as standalone function:

```python
async def _resolve_memory_with_aperture(
    self, request: PromptRequest
) -> tuple[Optional[str], Optional[str], Optional[MemoryConfidence]]:
    """
    Three-phase recall pipeline shaped by aperture.

    Phase 1 (FOCUS): Inner ring collections + focus-tagged Matrix nodes
    Phase 2 (MATRIX): Full Memory Matrix with focus weighting
    Phase 3 (AGENCY): Outer ring breakthrough check
    """
```

**Phase 1 — Focus Query:**
- Get all collections where lock_in >= inner_ring_threshold AND (tag overlap with focus_tags OR collection_key in active_collection_ids)
- Search these collections via `AiBrarianEngine.search()` with full depth
- Tag results with provenance: `source=aibrarian, collection=X`

**Phase 2 — Matrix Sweep:**
- Existing smart_fetch behavior (unchanged)
- But weight results by focus tag relevance
- Identity nodes always included regardless of aperture

**Phase 3 — Agency Check:**
- Lightweight sweep of remaining collections
- Only surface results exceeding breakthrough_threshold
- Always check for: deadline proximity (14 days), explicit flags, high cross-reference
- Time-sensitive items bypass threshold entirely

**Step 3: Compose the layered constellation.**

Assemble results from all three phases into a single context block.
Inner ring results get higher priority in token budget.
Add provenance markers so Luna (and the user) can trace sources.

**Step 4: Add system prompt hint.**

One line added to the identity or grounding block:
```
You have been provided context shaped by your current focus.
If you notice connections to knowledge outside your current scope that seem important, mention them.
```

**What does NOT change:**
- Kernel/identity loading — unaffected
- Virtue system — unaffected
- Voice block — unaffected
- Temporal block — unaffected
- The prompt structure stays the same — only the content of Layer 4.0 changes

**Verification:**
- [ ] TUNNEL mode: only directly tagged collections searched
- [ ] BALANCED mode: settled + fluid collections with tag overlap searched
- [ ] OPEN mode: all collections searched
- [ ] Identity nodes always present regardless of aperture
- [ ] Provenance on every collection-sourced fragment
- [ ] Breakthrough check runs on all aperture settings
- [ ] Time-sensitive items bypass threshold

---

### Phase 5: Aibrarian Lock-In Tracking Hooks

**Modify:** `src/luna/substrate/aibrarian_engine.py`

Wire lock-in signals into existing Aibrarian operations.

**On every `search()` call:**
```python
# After search completes:
await self._bump_access(collection_key)
```

**On every `get_document()` call:**
```python
await self._bump_access(collection_key)
```

**New method:**
```python
async def _bump_access(self, collection_key: str):
    """Increment access count and update last_accessed_at in lock-in table."""
    # Update collection_lock_in table in main engine DB
    # Recalculate lock-in after bump
```

**On annotation creation:**
```python
# Handled by annotation system (Phase 2), but Aibrarian
# engine should expose method for cross-collection counting
async def get_entity_overlap(self, collection_key: str, matrix_entities: list[str]) -> int:
    """Count entities in this collection that also appear in Memory Matrix."""
```

**Verification:**
- [ ] Every search bumps access count
- [ ] Every document open bumps access count
- [ ] Lock-in recalculates after bump
- [ ] Entity overlap count is queryable per collection

---

### Phase 6: API Endpoints + MCP Tools

**Modify:** `src/luna/api/server.py` (or create new route module)

Expose aperture state and collection lock-in via API:

```
GET  /aperture              → current ApertureState
POST /aperture              → set aperture (preset or angle)
GET  /collections/lock-in   → all collections with lock-in scores
GET  /collections/:key/lock-in → single collection lock-in detail
POST /annotations           → create annotation (returns Matrix node ID)
GET  /annotations?collection=X → list annotations for a collection
```

**New MCP tools (add to existing tool registry):**

```python
# In tools/ or as extension to existing memory_tools.py
async def aperture_get() -> dict:
    """Get current aperture state."""

async def aperture_set(preset: str = None, angle: int = None) -> dict:
    """Set aperture. Preset overrides angle."""

async def collection_lock_in(collection: str = None) -> dict:
    """Get lock-in scores for all or specific collection."""

async def annotate(collection: str, doc_id: str, annotation_type: str, content: str = None) -> dict:
    """Create annotation on a collection document."""
```

**Verification:**
- [ ] API endpoints return correct data
- [ ] MCP tools callable from any Luna surface
- [ ] Aperture changes persist within session
- [ ] Aperture resets to app default on app context change (unless user_override=True)

---

## Build Order

```
Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6
  │          │          │          │          │          │
  │          │          │          └── Depends on 1+2+3  │
  │          │          └── Independent (pure data model)│
  │          └── Depends on 1 (annotation bumps lock-in) │
  └── Independent (start here)                           │
                                                         └── Depends on all
```

**Phases 1, 2, 3 can be built in parallel** — they're independent data models.
Phase 4 is the integration point that wires them together.
Phase 5 hooks into existing code.
Phase 6 exposes everything.

---

## Non-Negotiables (The Vibe Check)

1. **The Wall is real.** Collection-sourced knowledge is NEVER treated as native Matrix memory. Even at max lock-in. Provenance is permanent.

2. **Offline-first.** All lock-in computation is local SQLite. No API calls. No cloud. Everything works without internet.

3. **Collections are read-only from Luna's perspective.** She reads and annotates. She never modifies collection content.

4. **Aperture shapes context, not personality.** Luna's kernel, virtues, voice — untouched. Only the Memory layer (4.0) content changes.

5. **Agency has a high bar.** Breakthrough interruptions should be rare and significant. "Would I interrupt someone deep in thought for this?" If no, file it and wait.

6. **Minimum floor of 0.05.** No collection ever reaches zero lock-in while it exists. Drifting ≠ gone.

---

## Files Touched Summary

| File | Action |
|------|--------|
| `src/luna/substrate/collection_lock_in.py` | **CREATE** — collection-level lock-in engine |
| `src/luna/substrate/collection_annotations.py` | **CREATE** — annotation system (the bridge) |
| `src/luna/context/aperture.py` | **CREATE** — aperture state and presets |
| `src/luna/context/assembler.py` | **MODIFY** — add aperture to PromptRequest, aperture-aware memory resolution |
| `src/luna/substrate/aibrarian_engine.py` | **MODIFY** — wire lock-in tracking hooks |
| `src/luna/api/server.py` | **MODIFY** — add aperture + annotation endpoints |
| `src/luna/tools/memory_tools.py` | **MODIFY** — add MCP tools for aperture + lock-in |
| `config/aibrarian_registry.yaml` | **MODIFY** — add tag associations per collection |
| Schema (engine DB) | **MODIFY** — add collection_lock_in + collection_annotations tables |

**Files NOT touched:**
- `src/luna/engine.py` — no changes needed
- `src/luna/voice/` — voice system unaffected
- `src/luna/consciousness/` — untouched
- `src/luna/identity/` — untouched
- Individual collection databases — read-only, never modified
