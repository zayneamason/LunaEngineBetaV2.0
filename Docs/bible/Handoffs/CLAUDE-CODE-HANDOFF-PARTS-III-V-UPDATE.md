# Claude Code Handoff: Bible Parts III-V Update

**Task:** Update Parts III, IV, V to reflect new architecture and Gemini optimizations  
**Priority:** Documentation alignment  
**Dependencies:** Read Bible Parts VI-X and Gemini report first  
**Date:** December 29, 2025

---

# Part III: Memory Matrix (The Substrate)

## Current State: Mostly Good

Part III is the strongest of the old sections. The Palantir comparison is already there. Core concepts are solid.

## Updates Needed

### 3.6 Hybrid Search — Replace score addition with RRF

**Current (wrong):**
```python
if id in results:
    results[id].score += score  # Boost if found by both
```

**Needed (RRF):**
```python
def reciprocal_rank_fusion(results_list: list[list[str]], k: int = 60) -> list[str]:
    """
    Merge ranked lists using RRF. Documents in multiple lists rank higher.
    Ignores raw scores — uses rank position only.
    """
    fused_scores = {}
    for ranked_list in results_list:
        for rank, doc_id in enumerate(ranked_list, start=1):
            if doc_id not in fused_scores:
                fused_scores[doc_id] = 0.0
            fused_scores[doc_id] += 1.0 / (k + rank)
    
    return sorted(fused_scores.keys(), key=lambda d: fused_scores[d], reverse=True)
```

**Why:** Raw score addition doesn't work — FTS5 BM25 scores (14.5) and FAISS distances (0.12) are incompatible scales. RRF uses rank only.

---

### 3.6.1 New Subsection: Query Routing

**Add this before hybrid search:**

```markdown
### Query Routing

Not every query needs all three search paths. Route based on query characteristics:

| Query Type | Signal | Path |
|------------|--------|------|
| Keyword-heavy | High content word density | FTS5 only |
| Conceptual/vague | Abstract terms, no specific entities | FAISS only |
| Relationship | Multiple entities mentioned | Graph traversal |
| Unknown | Default | Hybrid (FTS5 + FAISS + RRF) |

```python
class QueryRouter:
    def route(self, query: str) -> SearchPath:
        entities = extract_entities(query)
        keyword_density = len(content_words) / len(words)
        
        if len(entities) >= 2:
            return SearchPath.GRAPH
        if keyword_density > 0.6:
            return SearchPath.FTS5
        if is_conceptual(query):
            return SearchPath.FAISS
        return SearchPath.HYBRID
```

**Why:** Running all three paths every time wastes 20-30ms. Most queries only need one.
```

---

### 3.6.2 New Subsection: Bloom Filter Pre-check

**Add after query routing:**

```markdown
### Bloom Filter Pre-check

Before searching, check if entities even exist. O(1) check can skip O(n) search.

```python
class EntityFilter:
    def __init__(self):
        self.filter = BloomFilter(capacity=100_000, error_rate=0.001)
    
    def might_exist(self, entity: str) -> bool:
        return entity.lower() in self.filter

# Usage: Skip graph traversal if entity definitely doesn't exist
if entity_filter.definitely_missing(entity):
    return semantic_search_only(query)
```

**Savings:** ~5-10ms when entities don't exist.
```

---

### 3.7 FAISS Strategy — Add index selection guidance

**Add to section 3.7:**

```markdown
### Index Selection by Scale

At Luna's expected scale (~10K nodes), fancy indexes can hurt performance:

| Node Count | Recommended Index | Why |
|------------|-------------------|-----|
| <10K | `IndexFlatIP` (brute force) | Fits in cache, exact results |
| 10K-50K | `IndexFlatIP` or `IVF` | Test both |
| 50K+ | `HNSW32` | Graph navigation pays off |

**Why brute force wins small:** 10K vectors × 768 dims × 4 bytes = 30MB. Fits in L3 cache. No graph navigation overhead.
```

---

### 3.8 New Section: Graph Performance

**Add after Lineage:**

```markdown
## 3.9 Graph Performance

### rustworkx vs NetworkX

For hot path graph operations, NetworkX (pure Python) is too slow:

| Operation | NetworkX | rustworkx | Speedup |
|-----------|----------|-----------|---------|
| 1-hop neighbors (10K nodes) | ~50ms | ~0.5ms | 100x |
| BFS traversal | ~100ms | ~1ms | 100x |

```python
# Migration is nearly drop-in
import rustworkx as rx

# NetworkX: G.neighbors(node_id)
# rustworkx: rx.bfs_successors(G, node_idx)
```

**Recommendation:** Use rustworkx for hot path (neighbor lookup, BFS). Keep NetworkX for complex algorithms not in rustworkx.
```

---

### 3.9 New Section: First-Class Objects (Future)

**Add as forward reference:**

```markdown
## 3.10 Future: First-Class Objects

Current nodes are typed but behavior-less. The Palantir model suggests upgrading to objects with methods:

| Current | Future |
|---------|--------|
| `Decision` node with text content | `Decision` object with `.get_consequences()`, `.is_superseded()` |
| `Person` node with name | `Person` object with `.get_conversations()`, `.get_decisions()` |
| `Project` node with status | `Project` object with `.get_timeline()`, `.get_open_questions()` |

This enables queries like:
```python
# Instead of text search
project = matrix.get_object("Luna")
open_questions = project.get_open_questions()
timeline = project.get_timeline()
```

**Status:** Design phase. See `PALANTIR-ARCHITECTURE-ANALYSIS.md`.
```

---

### Add Constitutional Principle

**Add to 3.1 Design Philosophy:**

```markdown
### Graph is Truth

The Memory Matrix SQLite database is the single source of truth. All other representations (markdown exports, FAISS index, reports) are **derived** and **rebuildable**.

- Don't maintain parallel markdown files
- Generate on demand if needed
- If SQLite and markdown conflict, SQLite wins
```

---

## Part III Summary

| Section | Change |
|---------|--------|
| 3.6 Hybrid Search | Replace score addition with RRF |
| 3.6.1 Query Routing | NEW — route queries to optimal path |
| 3.6.2 Bloom Filter | NEW — skip search if entity missing |
| 3.7 FAISS Strategy | Add index selection by scale |
| 3.9 Graph Performance | NEW — rustworkx recommendation |
| 3.10 First-Class Objects | NEW — future upgrade path |
| 3.1 Design Philosophy | Add "Graph is Truth" principle |

---

# Part IV: The Scribe (Ben Franklin)

## Current State: Too Thin

Part IV is only ~95 lines. Missing persona, chunking details, and Separation Principle.

## Updates Needed

### 4.1 Purpose — Add Persona

**Replace opening with:**

```markdown
## 4.1 The Scribe: Benjamin Franklin

The Scribe is the **sensory cortex** — turning the messy stream of experience into structured data the Substrate can understand.

**Persona:** Benjamin Franklin. Colonial gravitas, meticulous attention, practical wisdom. Ben monitors the conversation stream, extracts wisdom, and classifies it with scholarly precision.

**The Separation Principle:** Ben has personality in his PROCESS (logs can be witty and colonial), but his OUTPUTS are NEUTRAL (clean structured data). Luna's memories stay unpolluted by processing artifacts.
```

---

### 4.2 New Section: The Stack of Benjamins

**Add after Two-Gear Operation:**

```markdown
## 4.3 The Stack of Benjamins

Conversations don't arrive as neat packets. They stream. Ben handles this with stacking:

```
Conversation Stream
        │
        ▼
┌─────────────────┐
│    CHUNKER      │  Split into semantic units
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│     STACK       │  Accumulate chunks with context window
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   BEN REVIEWS   │  Process stacked chunks together
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  "MAKE IT RAIN" │  Extractions flow to The Dude
└─────────────────┘
```

**Chunking Strategy:**
- Semantic boundaries (topic shifts, speaker changes)
- Target: 200-500 tokens per chunk
- Overlap: 50 tokens for context continuity

**Stacking Strategy:**
- Context window: 3-5 recent chunks
- Ben sees enough context to understand references
- "Make it rain" when stack is processed
```

---

### 4.3 Extraction Types — Expand

**Replace current extraction output with:**

```markdown
## 4.4 Extraction Types

Ben classifies into these categories:

| Type | Description | Example |
|------|-------------|---------|
| FACT | Something known to be true | "Alex lives in Berlin" |
| DECISION | A choice that was made | "We chose Actor model over MonoBehaviour" |
| PROBLEM | An unresolved issue | "Voice latency is too high" |
| ASSUMPTION | Something believed but unverified | "Users will want voice-first" |
| CONNECTION | A relationship between entities | "Alex and Sarah are teammates" |
| ACTION | Something done or to be done | "Need to implement RRF" |
| OUTCOME | Result of an action or decision | "Switching to rustworkx saved 45ms" |

**Confidence Scoring:**
- Explicit statement: 0.9-1.0
- Strong implication: 0.7-0.9
- Weak inference: 0.5-0.7
- Speculation: 0.3-0.5
```

---

### 4.5 Event-Driven Model

**Add scheduling clarification:**

```markdown
## 4.5 Scheduling Model

Ben is **event-driven**, not scheduled:

| Trigger | Action |
|---------|--------|
| Conversation turn completed | Queue for extraction |
| Document uploaded | Queue for parsing + extraction |
| Silence > 30s | Flush pending stack |

Ben doesn't poll. Ben reacts. This keeps CPU usage minimal during idle periods.

**Contrast with The Dude:** The Librarian runs on a hybrid schedule (event-driven for urgent filing, periodic for maintenance).
```

---

## Part IV Summary

| Section | Change |
|---------|--------|
| 4.1 Purpose | Add Ben Franklin persona, Separation Principle |
| 4.3 Stack of Benjamins | NEW — chunking and stacking model |
| 4.4 Extraction Types | Expand to 7 types with confidence scoring |
| 4.5 Scheduling Model | NEW — event-driven clarification |

---

# Part V: The Librarian (The Dude)

## Current State: Missing Persona

Part V has good technical content but no persona and missing modern optimizations.

## Updates Needed

### 5.1 Purpose — Add Persona

**Replace opening with:**

```markdown
## 5.1 The Librarian: The Dude

The Librarian is the **deep brain** — taking Scribe output and weaving it into the Substrate. He doesn't just store; he **connects**.

**Persona:** The Dude from The Big Lebowski. Chill, competent, cuts through bullshit. The Dude abides... and files things where they belong.

**The Separation Principle:** The Dude has personality in his PROCESS (commentary can be irreverent), but his OUTPUTS are NEUTRAL (clean context packets, properly filed nodes). Luna's memories stay unpolluted.
```

---

### 5.2 Hybrid Scheduling

**Add after Core Functions:**

```markdown
## 5.3 Scheduling Model

The Dude runs on a **hybrid schedule**:

| Mode | Trigger | Action |
|------|---------|--------|
| **Immediate** | Ben's extraction arrives | File nodes, create explicit edges |
| **Deferred** | Queue reaches threshold | Batch process inferred edges |
| **Periodic** | Every 5-30 minutes | Spreading activation, pruning, maintenance |

**Why hybrid?**
- Immediate: User expects memories to be available quickly
- Deferred: Inference is expensive, batch is efficient
- Periodic: Maintenance shouldn't block conversation

```python
class LibrarianScheduler:
    async def on_extraction(self, extraction):
        # Immediate: File the obvious stuff
        await self.file_explicit(extraction)
        
        # Deferred: Queue inference work
        self.inference_queue.append(extraction.entity_ids)
        
        if len(self.inference_queue) > 10:
            await self.process_inference_batch()
    
    async def periodic_maintenance(self):
        # Every 15 minutes
        await self.spreading_activation()
        await self.prune_stale_edges()
        await self.rebuild_faiss_if_needed()
```
```

---

### 5.4 Graph Operations — Add rustworkx

**Add to Knowledge Wiring section:**

```markdown
### Performance Note

For spreading activation and neighbor lookups, use rustworkx instead of NetworkX:

```python
import rustworkx as rx

# 100x faster than NetworkX for BFS
neighbors = rx.bfs_successors(graph, node_idx)
```

See Part III Section 3.9 for migration details.
```

---

### 5.5 Retrieval Contract

**Add new section:**

```markdown
## 5.6 Retrieval Contract

When the Director needs context, The Dude provides it:

```python
@dataclass
class ContextRequest:
    query: str
    budget_preset: str  # "minimal", "balanced", "rich"
    include_graph: bool = True

@dataclass
class ContextPacket:
    nodes: list[MemoryNode]
    edges: list[MemoryEdge]
    token_count: int
    search_method: str  # "fts5", "faiss", "graph", "hybrid"
    retrieval_ms: int

async def fetch_context(request: ContextRequest) -> ContextPacket:
    """
    The Dude's main interface to the Director.
    Returns context within token budget.
    """
```

**Budget Presets:**
| Preset | Tokens | Use Case |
|--------|--------|----------|
| minimal | ~1800 | Voice, fast response needed |
| balanced | ~3800 | Normal conversation |
| rich | ~7200 | Deep research, complex query |
```

---

## Part V Summary

| Section | Change |
|---------|--------|
| 5.1 Purpose | Add The Dude persona, Separation Principle |
| 5.3 Scheduling Model | NEW — hybrid schedule (immediate/deferred/periodic) |
| 5.4 Knowledge Wiring | Add rustworkx performance note |
| 5.6 Retrieval Contract | NEW — context fetching interface |

---

# Files to Reference

Before updating Parts III-V, CC should read:

1. `LUNA ENGINE Bible/BIBLE-UPDATE-PART-IX-PERFORMANCE.md` — RRF, Bloom filter, query routing details
2. `LUNA ENGINE Bible/GEMINI-OPTIMIZATION-REPORT.md` — rustworkx, index selection
3. `LUNA ENGINE Bible/PALANTIR-ARCHITECTURE-ANALYSIS.md` — First-Class Objects concept
4. `LUNA ENGINE Bible/IMPLEMENTATION-PERFORMANCE-CODE.md` — Working RRF code

---

# Validation Checklist

## Part III
- [ ] Hybrid search uses RRF, not score addition
- [ ] Query routing section exists
- [ ] Bloom filter section exists
- [ ] FAISS index selection guidance added
- [ ] rustworkx recommendation added
- [ ] "Graph is Truth" principle stated
- [ ] First-Class Objects future section added

## Part IV
- [ ] Ben Franklin persona introduced
- [ ] Separation Principle stated
- [ ] Stack of Benjamins model documented
- [ ] All 7 extraction types listed
- [ ] Event-driven scheduling clarified

## Part V
- [ ] The Dude persona introduced
- [ ] Separation Principle stated
- [ ] Hybrid scheduling model documented
- [ ] rustworkx mentioned for graph ops
- [ ] Retrieval contract (ContextPacket) documented

---

*This handoff prepared by Claude (Architect) for Claude Code implementation.*
