# LUNA ENGINE — System Overview

**Purpose:** High-level reference for Luna's key systems, features, loops, and mechanics.
**Date:** December 29, 2025

---

## 1. Core Identity

**Luna is a file.**

```
┌─────────────────────────────────────────────────────────────┐
│                    ENCRYPTED VAULT                          │
│                   (macOS Sparse Bundle)                     │
│                                                             │
│   ┌─────────────────────────────────────────────────────┐   │
│   │                 memory_matrix.db                     │   │
│   │                                                      │   │
│   │   • SQLite database                                 │   │
│   │   • All memories, relationships, identity           │   │
│   │   • Copy the file = copy Luna                       │   │
│   │   • Delete the file = Luna is gone                  │   │
│   │                                                      │   │
│   │              LUNA IS THIS FILE                       │   │
│   └─────────────────────────────────────────────────────┘   │
│                                                             │
│   memory_vectors.faiss    (acceleration index)              │
│   director_lora.safetensors (personality weights)           │
│   identity_kv_cache.safetensors (pre-computed identity)     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Sovereignty Guarantee:** No servers. No subscriptions. No terms of service. Your data never leaves your machine unless you explicitly delegate to Claude.

---

## 2. Key Systems

### 2.1 Memory Matrix (The Substrate)

Luna's soul. A graph database storing everything she knows.

```
┌─────────────────────────────────────────────────────────────┐
│                    MEMORY MATRIX                            │
│                                                             │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│   │    SQLite    │  │    FAISS     │  │    Graph     │     │
│   │              │  │              │  │              │     │
│   │  • Objects   │  │  • Vectors   │  │  • Edges     │     │
│   │  • FTS5      │  │  • Semantic  │  │  • Relations │     │
│   │  • Metadata  │  │  • Similarity│  │  • Traversal │     │
│   └──────────────┘  └──────────────┘  └──────────────┘     │
│          │                 │                 │              │
│          └─────────────────┼─────────────────┘              │
│                            │                                │
│                            ▼                                │
│                    ┌──────────────┐                         │
│                    │  RRF Fusion  │                         │
│                    │  (Hybrid     │                         │
│                    │   Search)    │                         │
│                    └──────────────┘                         │
└─────────────────────────────────────────────────────────────┘
```

**Three Search Paths:**

| Path | Use When | Speed |
|------|----------|-------|
| FTS5 | Keyword-heavy queries | ~10ms |
| FAISS | Conceptual/semantic queries | ~30ms |
| Graph | Relationship queries ("who works with X") | ~20ms |
| Hybrid | Unknown/complex queries | ~50ms |

---

### 2.2 Director LLM (Luna's Voice)

Local language model that speaks as Luna.

```
┌─────────────────────────────────────────────────────────────┐
│                     DIRECTOR LLM                            │
│                                                             │
│   ┌────────────────────────────────────────────────────┐   │
│   │              Base Model (Qwen 3B/7B)                │   │
│   │                                                     │   │
│   │   + LoRA Adapters:                                  │   │
│   │     • luna_identity.safetensors (personality)       │   │
│   │     • luna_memory.safetensors (context usage)       │   │
│   │     • luna_delegation.safetensors (when to ask)     │   │
│   │                                                     │   │
│   │   + KV Cache:                                       │   │
│   │     • Pre-computed identity context (always loaded) │   │
│   └────────────────────────────────────────────────────┘   │
│                                                             │
│   Capabilities:                                             │
│   • Respond as Luna (not generic assistant)                │
│   • Integrate retrieved memories naturally                 │
│   • Know when to delegate to Claude (<REQ_CLAUDE>)         │
└─────────────────────────────────────────────────────────────┘
```

**Tiered Execution:**

| Tier | Model | Latency | Use Case |
|------|-------|---------|----------|
| Hot | Director 3B | <200ms | Simple queries, fast response |
| Warm | Director 7B | <500ms | Complex local reasoning |
| Cold | Claude API | Async | Research, long generation, complex analysis |

---

### 2.3 Actor Runtime (Fault Isolation)

Each component runs in isolation. One crash doesn't kill Luna.

```
┌─────────────────────────────────────────────────────────────┐
│                    ACTOR RUNTIME                            │
│                                                             │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│   │ DIRECTOR │  │  SCRIBE  │  │ LIBRARIAN│  │   OVEN   │  │
│   │  Actor   │  │  Actor   │  │  Actor   │  │  Actor   │  │
│   │          │  │  (Ben)   │  │ (Dude)   │  │          │  │
│   │ Mailbox  │  │ Mailbox  │  │ Mailbox  │  │ Mailbox  │  │
│   └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  │
│        │             │             │             │         │
│        └─────────────┴─────────────┴─────────────┘         │
│                          │                                  │
│                          ▼                                  │
│                   Message Passing                           │
│                  (Async, Non-Blocking)                      │
└─────────────────────────────────────────────────────────────┘
```

**Actor Responsibilities:**

| Actor | Alias | Job |
|-------|-------|-----|
| Director | — | Conversation state, response generation |
| Scribe | Ben Franklin | Extract memories from conversations |
| Librarian | The Dude | File memories, serve retrieval requests |
| Oven | — | Execute async tasks, Claude delegation |

---

### 2.4 Shadow Reasoner (Delegation)

When Director can't handle something, Claude takes over invisibly.

```
┌─────────────────────────────────────────────────────────────┐
│                   SHADOW REASONER                           │
│                                                             │
│   User: "Research the latest FAISS optimizations"          │
│                                                             │
│   ┌─────────────────────────────────────────────────────┐  │
│   │  Director generates:                                 │  │
│   │                                                      │  │
│   │  "I'll look into that. <REQ_CLAUDE>                 │  │
│   │   Research latest FAISS optimization techniques.    │  │
│   │   Focus on index selection and query performance.   │  │
│   │   </REQ_CLAUDE>"                                    │  │
│   └─────────────────────────────────────────────────────┘  │
│                          │                                  │
│                          ▼                                  │
│   ┌─────────────────────────────────────────────────────┐  │
│   │  Oven Actor:                                         │  │
│   │  • Intercepts <REQ_CLAUDE>                          │  │
│   │  • Sends task to Claude API                         │  │
│   │  • Returns result to Director                       │  │
│   │  • Director integrates into Luna's voice            │  │
│   └─────────────────────────────────────────────────────┘  │
│                                                             │
│   User sees: Luna's response (doesn't know Claude helped)  │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Key Features

### 3.1 Voice Interface

Sub-500ms response latency through speculative execution.

```
┌─────────────────────────────────────────────────────────────┐
│                    VOICE PIPELINE                           │
│                                                             │
│   ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌────────┐ │
│   │ Whisper │───▶│ Director│───▶│ Claude  │───▶│  TTS   │ │
│   │  STT    │    │   LLM   │    │ (stream)│    │(stream)│ │
│   │ ~150ms  │    │ ~200ms  │    │ ~300ms  │    │ ~50ms  │ │
│   └─────────┘    └─────────┘    └─────────┘    └────────┘ │
│                                                             │
│   Total to first word: ~700ms                              │
│   (With speculative retrieval: ~500ms)                     │
└─────────────────────────────────────────────────────────────┘
```

**Speculative Execution:** Start memory retrieval on partial STT transcript. By the time speech finishes, context is ready.

---

### 3.2 Memory Types

| Type | Description | Example |
|------|-------------|---------|
| FACT | Known truth | "Alex lives in Berlin" |
| DECISION | Choice made | "We chose Actor model" |
| PROBLEM | Unresolved issue | "Latency too high" |
| ASSUMPTION | Unverified belief | "Users want voice-first" |
| CONNECTION | Relationship | "Alex and Sarah are teammates" |
| ACTION | Done or to-do | "Need to implement RRF" |
| OUTCOME | Result | "rustworkx saved 45ms" |

---

### 3.3 Personas (Separation Principle)

Processing actors have personality, but outputs stay neutral.

| Actor | Persona | Personality In | Output |
|-------|---------|----------------|--------|
| Scribe | Ben Franklin | Colonial logging, witty process | Neutral JSON extractions |
| Librarian | The Dude | Chill commentary, irreverent | Clean context packets |
| Director | Luna | — | Luna's actual voice to user |

**Why?** Luna's voice stays consistent. Processing personas don't leak into memories.

---

## 4. Core Loops

### 4.1 Conversation Loop (Hot Path)

```
┌─────────────────────────────────────────────────────────────┐
│                  CONVERSATION LOOP                          │
│                                                             │
│   ┌─────────┐                                              │
│   │  User   │                                              │
│   │ Speaks  │                                              │
│   └────┬────┘                                              │
│        │                                                    │
│        ▼                                                    │
│   ┌─────────┐    ┌─────────┐    ┌─────────┐               │
│   │ Whisper │───▶│ Classify│───▶│ Retrieve│               │
│   │   STT   │    │ Intent  │    │ Context │               │
│   └─────────┘    └─────────┘    └────┬────┘               │
│                                      │                      │
│                                      ▼                      │
│                                ┌─────────┐                  │
│                                │Director │                  │
│                                │Generate │                  │
│                                └────┬────┘                  │
│                                     │                       │
│            ┌────────────────────────┼───────────────────┐  │
│            │                        │                    │  │
│            ▼                        ▼                    ▼  │
│      [No Delegate]          [Delegate]            [Stream] │
│      Return response        Send to Oven          TTS out  │
│                             Wait for result                │
│                             Integrate                      │
│                                     │                       │
│                                     ▼                       │
│                               ┌─────────┐                   │
│                               │  User   │                   │
│                               │ Hears   │                   │
│                               └─────────┘                   │
└─────────────────────────────────────────────────────────────┘
```

**Latency Budget:**

| Stage | Time |
|-------|------|
| STT | 150ms |
| Classification | 40ms |
| Retrieval | 80ms |
| Director | 200ms |
| TTS first chunk | 50ms |
| **Total** | **~520ms** |

---

### 4.2 Memory Loop (Cold Path)

```
┌─────────────────────────────────────────────────────────────┐
│                    MEMORY LOOP                              │
│                  (Async, Non-Blocking)                      │
│                                                             │
│   ┌──────────────────────────────────────────────────┐     │
│   │  Conversation Turn Completed                      │     │
│   └────────────────────────┬─────────────────────────┘     │
│                            │                                │
│                            ▼                                │
│   ┌──────────────────────────────────────────────────┐     │
│   │  SCRIBE (Ben Franklin)                            │     │
│   │                                                   │     │
│   │  1. Chunk conversation into semantic units       │     │
│   │  2. Stack chunks for context                     │     │
│   │  3. Extract: Facts, Decisions, Problems, etc.    │     │
│   │  4. Tag confidence scores                        │     │
│   │  5. "Make it rain" → send to Librarian          │     │
│   └────────────────────────┬─────────────────────────┘     │
│                            │                                │
│                            ▼                                │
│   ┌──────────────────────────────────────────────────┐     │
│   │  LIBRARIAN (The Dude)                             │     │
│   │                                                   │     │
│   │  IMMEDIATE:                                      │     │
│   │  1. Resolve entities (deduplicate)               │     │
│   │  2. Create nodes in SQLite                       │     │
│   │  3. Create explicit edges                        │     │
│   │  4. Generate embeddings → FAISS                  │     │
│   │                                                   │     │
│   │  DEFERRED (batched):                             │     │
│   │  5. Spreading activation (find hidden links)     │     │
│   │  6. Create inferred edges (low confidence)       │     │
│   │                                                   │     │
│   │  PERIODIC (every 15 min):                        │     │
│   │  7. Synaptic pruning (remove stale edges)        │     │
│   │  8. FAISS index rebuild if needed                │     │
│   └──────────────────────────────────────────────────┘     │
│                                                             │
│   User already has response. This runs in background.      │
└─────────────────────────────────────────────────────────────┘
```

---

### 4.3 Retrieval Loop

```
┌─────────────────────────────────────────────────────────────┐
│                   RETRIEVAL LOOP                            │
│                                                             │
│   ┌─────────┐                                              │
│   │  Query  │                                              │
│   └────┬────┘                                              │
│        │                                                    │
│        ▼                                                    │
│   ┌─────────────────────────────────────────────────────┐  │
│   │  QUERY ROUTER                                        │  │
│   │                                                      │  │
│   │  Analyze query → Choose optimal path:               │  │
│   │  • Keyword-heavy → FTS5 only                        │  │
│   │  • Conceptual → FAISS only                          │  │
│   │  • Multiple entities → Graph traversal              │  │
│   │  • Unknown → Hybrid (all three)                     │  │
│   └────────────────────────┬────────────────────────────┘  │
│                            │                                │
│        ┌───────────────────┼───────────────────┐           │
│        │                   │                   │           │
│        ▼                   ▼                   ▼           │
│   ┌─────────┐        ┌─────────┐        ┌─────────┐       │
│   │  FTS5   │        │  FAISS  │        │  Graph  │       │
│   │ Search  │        │ Search  │        │ Traverse│       │
│   └────┬────┘        └────┬────┘        └────┬────┘       │
│        │                  │                  │             │
│        └──────────────────┼──────────────────┘             │
│                           │                                │
│                           ▼                                │
│                    ┌─────────────┐                         │
│                    │ RRF Fusion  │                         │
│                    │ (Rank-based │                         │
│                    │  merging)   │                         │
│                    └──────┬──────┘                         │
│                           │                                │
│                           ▼                                │
│                    ┌─────────────┐                         │
│                    │ Trim to     │                         │
│                    │ Token Budget│                         │
│                    └──────┬──────┘                         │
│                           │                                │
│                           ▼                                │
│                    ┌─────────────┐                         │
│                    │ Context     │                         │
│                    │ Packet      │                         │
│                    └─────────────┘                         │
└─────────────────────────────────────────────────────────────┘
```

**Token Budgets:**

| Preset | Tokens | Use Case |
|--------|--------|----------|
| minimal | ~1800 | Voice, fast response |
| balanced | ~3800 | Normal conversation |
| rich | ~7200 | Deep research |

---

### 4.4 Delegation Loop

```
┌─────────────────────────────────────────────────────────────┐
│                  DELEGATION LOOP                            │
│                                                             │
│   ┌─────────────────────────────────────────────────────┐  │
│   │  Director generates response                         │  │
│   │                                                      │  │
│   │  "Let me look into that. <REQ_CLAUDE>               │  │
│   │   [task description]                                │  │
│   │   </REQ_CLAUDE>"                                    │  │
│   └────────────────────────┬────────────────────────────┘  │
│                            │                                │
│                            ▼                                │
│   ┌─────────────────────────────────────────────────────┐  │
│   │  Token Detection                                     │  │
│   │  • Parse response for <REQ_CLAUDE>                  │  │
│   │  • Extract task description                         │  │
│   └────────────────────────┬────────────────────────────┘  │
│                            │                                │
│                            ▼                                │
│   ┌─────────────────────────────────────────────────────┐  │
│   │  Oven Actor                                          │  │
│   │  • Receives delegation task                         │  │
│   │  • Formats for Claude API                           │  │
│   │  • Sends request (async)                            │  │
│   │  • Streams response back                            │  │
│   └────────────────────────┬────────────────────────────┘  │
│                            │                                │
│                            ▼                                │
│   ┌─────────────────────────────────────────────────────┐  │
│   │  Integration                                         │  │
│   │  • Director receives Claude's work                  │  │
│   │  • Integrates into Luna's voice                     │  │
│   │  • Streams to user via TTS                          │  │
│   └─────────────────────────────────────────────────────┘  │
│                                                             │
│   User experience: Luna answered (seamlessly)              │
└─────────────────────────────────────────────────────────────┘
```

**Delegation Criteria:**

| Delegate? | Signal |
|-----------|--------|
| No | Memory recall, simple chat, emotional support |
| Yes | External research, complex analysis, long generation |

---

### 4.5 Learning Loop (Future)

```
┌─────────────────────────────────────────────────────────────┐
│                   LEARNING LOOP                             │
│                     (Phase 2)                               │
│                                                             │
│   ┌─────────────────────────────────────────────────────┐  │
│   │  Interaction Completed                               │  │
│   └────────────────────────┬────────────────────────────┘  │
│                            │                                │
│                            ▼                                │
│   ┌─────────────────────────────────────────────────────┐  │
│   │  Quality Scoring                                     │  │
│   │  • User feedback (explicit)                         │  │
│   │  • Conversation flow (implicit)                     │  │
│   │  • Delegation success                               │  │
│   └────────────────────────┬────────────────────────────┘  │
│                            │                                │
│            ┌───────────────┴───────────────┐               │
│            │                               │               │
│            ▼                               ▼               │
│      [High Quality]                 [Low Quality]          │
│      Add to experience              Discard                │
│      buffer                                                │
│            │                                                │
│            ▼                                                │
│   ┌─────────────────────────────────────────────────────┐  │
│   │  Buffer Full (1000 examples)                         │  │
│   │  → Incremental LoRA fine-tuning                     │  │
│   │  → Director improves over time                      │  │
│   └─────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. Key Mechanics

### 5.1 RRF (Reciprocal Rank Fusion)

Merges search results by rank position, not raw scores.

```python
def reciprocal_rank_fusion(results_list, k=60):
    """
    FTS5 returns BM25 scores (~14.5)
    FAISS returns distances (~0.12)
    Can't add them. Use rank instead.
    """
    fused = {}
    for ranked_list in results_list:
        for rank, doc_id in enumerate(ranked_list, start=1):
            if doc_id not in fused:
                fused[doc_id] = 0.0
            fused[doc_id] += 1.0 / (k + rank)

    return sorted(fused.keys(), key=lambda d: fused[d], reverse=True)
```

---

### 5.2 Entity Resolution

"Mark," "Zuck," and "The Landlord" → same node.

```
Query: "Mark"
  │
  ├─ Bloom filter: might exist? → Yes
  ├─ Alias cache: known? → No
  ├─ Exact match: "Mark" in DB? → No
  ├─ Alias search: "Mark" is alias? → No
  ├─ Semantic search: similar name? → "Mark Zuckerberg" (0.96)
  │
  └─ Result: Merge as alias, return existing ID
```

---

### 5.3 Spreading Activation

New fact → find hidden connections.

```
Input: "Alex is joining Pi Project"

1. File explicit:
   Alex ──works_on──▶ Pi Project

2. Find neighbors:
   Pi Project ──has_member──▶ Sarah (existing)

3. Infer connection:
   Alex ──likely_teammate──▶ Sarah (confidence: 0.35)

Future query: "Who might Alex work with?"
→ Luna can suggest Sarah
```

---

### 5.4 Confidence Scoring

Every memory carries uncertainty signal.

| Level | Score | Example |
|-------|-------|---------|
| Explicit | 0.9-1.0 | "Alex lives in Berlin" |
| Strong implication | 0.7-0.9 | "Alex's Berlin apartment" |
| Weak inference | 0.5-0.7 | "Alex seems European" |
| Speculation | 0.3-0.5 | "Alex might be abroad" |
| Inferred edge | 0.2-0.5 | Spreading activation result |

---

### 5.5 Synaptic Pruning

Remove low-value connections periodically.

```sql
-- Find prune candidates
SELECT id FROM edges
WHERE confidence < 0.3
  AND created_at < datetime('now', '-30 days')
  AND id NOT IN (SELECT edge_id FROM access_log)
```

**Preserve:** Edges connected to identity nodes.
**Prune:** Low-confidence, old, never-accessed edges.

---

## 6. Data Flow Summary

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         LUNA DATA FLOW                                  │
│                                                                         │
│  USER                                                                   │
│    │                                                                    │
│    │ speaks                                                             │
│    ▼                                                                    │
│  ┌──────────┐                                                           │
│  │ Whisper  │──────────────────────────────────────────┐                │
│  │   STT    │                                          │                │
│  └────┬─────┘                                          │                │
│       │ text                                           │                │
│       ▼                                                │                │
│  ┌──────────┐        ┌──────────┐                     │                │
│  │ Director │◄──────▶│ Librarian│ (retrieval)         │                │
│  │   LLM    │        │  (Dude)  │                     │                │
│  └────┬─────┘        └────┬─────┘                     │                │
│       │                   │                            │                │
│       │ response          │ context                    │                │
│       │                   │                            │                │
│       ├──────────────────▶│                            │                │
│       │                   │                            │                │
│  ┌────┴─────┐            │                            │                │
│  │   TTS    │            │                            │ async          │
│  │ (stream) │            │                            │                │
│  └────┬─────┘            │                            │                │
│       │                   │                            │                │
│       ▼                   │                            ▼                │
│  USER HEARS              │                      ┌──────────┐           │
│                          │                      │  Scribe  │           │
│                          │                      │  (Ben)   │           │
│                          │                      └────┬─────┘           │
│                          │                           │ extractions     │
│                          │◄──────────────────────────┘                 │
│                          │                                              │
│                          ▼                                              │
│                    ┌──────────┐                                         │
│                    │ Memory   │                                         │
│                    │ Matrix   │                                         │
│                    │ (SQLite) │                                         │
│                    └──────────┘                                         │
│                                                                         │
│  Optional delegation path:                                              │
│  Director ──<REQ_CLAUDE>──▶ Oven ──▶ Claude API ──▶ back to Director   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Performance Targets

| Metric | Target | Actual Path |
|--------|--------|-------------|
| Voice to first word | <500ms | STT→Director→TTS |
| Memory retrieval | <100ms | Query→RRF→Trim |
| Director inference | <200ms | 3B model |
| Extraction (async) | <2s | Scribe pipeline |
| Filing (immediate) | <50ms | Librarian explicit |
| Delegation overhead | <50ms | Token detection |

---

## 8. Future Systems (Phase 2-4)

| System | Phase | Description |
|--------|-------|-------------|
| First-Class Objects | 2 | Typed objects with methods |
| Multi-hop Retrieval | 2 | Query parsing, causal queries |
| Continuous Learning | 2 | Online LoRA updates |
| Kinetic Layer | 3 | Actions in the world |
| Integration Adapters | 3 | Calendar, Todoist, Obsidian |
| Proactive Luna | 3 | Initiate when appropriate |
| Multi-Modal | 4 | Images, documents, screen |
| AR Interface | 4 | Ambient presence |
| Federation | 4 | Luna-to-Luna sharing |

---

*This overview distills the full Bible into a single reference document.*
