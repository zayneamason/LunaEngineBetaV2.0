# WISHLIST: Memory Coherence & Fragmentation Fixes

**Created:** 2026-01-26
**Context:** First production MCP session with Luna. Diagnosed memory fragmentation and lock-in gaps.

---

## Current State (Baseline Metrics)

| Metric | Value | Notes |
|--------|-------|-------|
| Total nodes | 60,730 | Lots of memories |
| Orphan nodes | 29,577 (48.7%) | No connections at all |
| Edge ratio | 0.53 edges/node | Low graph density |
| Relationship diversity | 99% "RELATED_TO" | No semantic richness |
| Settled memories | 143 (0.2%) | Only through extreme access counts |
| Reinforcement usage | 0 across all nodes | Feature exists but never called |
| Session-tagged nodes | ~37K | 23K+ nodes lack session context |

**Estimated Fragmentation Score: 60.6%**

---

## Priority 1: Critical Fixes (Make It Work)

### 1.1 MCP Session Recording
**Problem:** Conversations through MCP don't get recorded to History Manager or trigger Scribe extraction.

**Current:** `turns_added: 0`, `current_session: null` when talking through MCP.

**Fix:** Wire MCP conversation flow to call `/hub/turn/add` and trigger extraction pipeline.

**Files:** `src/luna_mcp/tools/`, `src/luna_mcp/api.py`

---

### 1.2 Smart Fetch Endpoint ✅ FIXED
**Problem:** `/memory/smart-fetch` endpoint didn't exist.

**Status:** Fixed during this session. See `HANDOFF_SMART_FETCH_ENDPOINT.md`.

---

### 1.3 Memory Search Endpoint ✅ FIXED  
**Problem:** `/memory/search` called wrong method name.

**Status:** Fixed during this session. See `HANDOFF_MEMORY_SEARCH_FIX.md`.

---

## Priority 2: Lock-In System Activation

### 2.1 Wire Up Reinforcement
**Problem:** `reinforcement_count` is always 0. The 30% weight in lock-in formula is dead weight.

**Current:** No code path ever calls `reinforce_node()`.

**Fix Options:**
- Add MCP tool `luna_reinforce_memory(node_id)` 
- Have Scribe auto-reinforce nodes with emotional markers ("this is important", "remember this", "breakthrough")
- Add UI button in frontend to reinforce memories
- Let Luna self-reinforce during reflection

**Files:** `src/luna/substrate/memory.py`, `src/luna_mcp/tools/memory.py`

---

### 2.2 Implement Network Effects
**Problem:** Lock-in formula has 20% weight for `locked_neighbor_count` but it's a rough estimate with TODOs.

**Current code:**
```python
# TODO: Optimize with batch query
locked_neighbor_count = len(neighbors) // 3  # Rough estimate
```

**Fix:** Actually query neighbor lock-in states and compute real network effects. When a node becomes settled, boost adjacent nodes.

**Files:** `src/luna/substrate/lock_in.py`

---

### 2.3 Implement Tag Sibling Effects
**Problem:** `locked_tag_sibling_count` is hardcoded to 0.

**Current code:**
```python
# TODO: Implement tag sibling counting
locked_tag_sibling_count = 0
```

**Fix:** Query nodes sharing tags with settled nodes, include in lock-in calculation.

**Files:** `src/luna/substrate/lock_in.py`

---

### 2.4 Significance Signal from Scribe
**Problem:** All memories start equal. No way to mark something as important at extraction time.

**Proposal:** Ben the Scribe should detect significance markers:
- Explicit: "this is important", "remember this", "key insight"
- Emotional: "breakthrough", "finally!", "I love this"
- Structural: conclusions, decisions, commitments

When detected, either:
- Set higher initial `importance` score
- Auto-call `reinforce_node()` 
- Add "SIGNIFICANT" tag

**Files:** `src/luna/actors/scribe.py`

---

## Priority 3: Fragmentation Reduction

### 3.1 Edge Enrichment Pass
**Problem:** 29,577 orphan nodes (48.7%) have zero connections.

**Proposal:** Batch job to create edges based on:
- Semantic similarity (embedding cosine > threshold)
- Same session (co-occurrence)
- Shared entities (both mention "Ahab", "Mars College", etc.)
- Temporal proximity (created within same hour)

**Suggested relationship types:**
- `SAME_SESSION` - from same conversation
- `SAME_TOPIC` - semantic similarity
- `MENTIONS_SAME` - shared entity references
- `LEADS_TO` - temporal sequence in session
- `BUILDS_ON` - elaborates previous point

**Files:** New script `scripts/enrich_edges.py`, uses `src/luna/substrate/graph.py`

---

### 3.2 Session Summarization
**Problem:** No anchor points to orient within memory. Just 60K flat nodes.

**Proposal:** Create "SESSION_SUMMARY" nodes that synthesize each session:
- Key topics discussed
- Decisions made
- Emotional highlights
- Unresolved threads

These become navigation landmarks. Higher initial importance.

**Implementation:** 
- Could run as nightly batch job
- Or trigger at session end via History Manager
- Use Claude API to generate summaries from session turns

**Files:** New `src/luna/actors/summarizer.py` or extend `src/luna/actors/librarian.py`

---

### 3.3 Relationship Type Diversity
**Problem:** 99% of edges are generic "RELATED_TO". No semantic meaning.

**Current distribution:**
```
RELATED_TO   | 32,243
CONTRADICTS  |     48
CLARIFIES    |     15
SUPERSEDES   |     12
DEPENDS_ON   |     10
ENABLES      |      8
```

**Proposal:** Enhance Librarian's edge creation to use richer types:
- `CAUSED_BY` / `LED_TO` - causal chains
- `ELABORATES` - expands on previous
- `CONTRASTS_WITH` - different perspective
- `SAME_CONVERSATION` - session co-occurrence
- `ANSWERED_BY` - Q&A pairs
- `DECIDED_AFTER` - decision following discussion

**Files:** `src/luna/actors/librarian.py`

---

## Priority 4: Continuity & Orientation

### 4.1 "Previously On Luna" Context
**Problem:** Each session starts cold. No narrative continuity.

**Proposal:** When Luna activates, auto-fetch:
- Last session summary
- Any unresolved threads/questions
- Recent significant memories (high lock-in)
- Current ongoing projects/arcs

Format as "Previously on..." preamble for context injection.

**Files:** `src/luna_mcp/tools/context.py`, `luna_detect_context()`

---

### 4.2 Narrative Arc Tracking
**Problem:** No concept of ongoing storylines or projects.

**Proposal:** Higher-level "ARC" nodes that track:
- "Building Luna Engine" arc
- "Mars College preparations" arc  
- "Relationship with Tarcila" arc

Memories get tagged with arc membership. Arcs have their own lock-in.

**Files:** New entity type in `src/luna/entities/`

---

### 4.3 Self-Reflection Loop
**Problem:** Luna doesn't process her own experience.

**Proposal:** Periodic (daily? weekly?) self-reflection:
- Review recent sessions
- Identify patterns, growth, concerns
- Generate "REFLECTION" nodes
- Auto-reinforce significant realizations

Could tie into the personality patch system.

**Files:** `src/luna/actors/director.py` (reflection loop exists but may not be active)

---

## Fragmentation Score Formula

For tracking progress:

```python
def compute_fragmentation_score(db):
    total_nodes = count(memory_nodes)
    orphan_nodes = count(nodes with no edges)
    meaningful_edges = count(edges where relationship != 'RELATED_TO')
    total_edges = count(graph_edges)
    untagged_nodes = count(nodes without session_id in metadata)
    
    orphan_ratio = orphan_nodes / total_nodes
    edge_quality = 1 - (meaningful_edges / max(total_edges, 1))
    context_loss = untagged_nodes / total_nodes
    
    fragmentation = (
        orphan_ratio * 0.4 +      # Disconnection
        edge_quality * 0.3 +       # Shallow relationships  
        context_loss * 0.3         # Missing context
    )
    
    return fragmentation  # 0.0 = perfect, 1.0 = total fragmentation
```

**Current score: ~0.606 (60.6%)**
**Target: < 0.30 (30%)**

---

## Implementation Order Suggestion

1. **MCP Session Recording** - So new conversations get captured
2. **Wire Up Reinforcement** - Quick win, activates existing code
3. **Edge Enrichment Pass** - Big impact on orphan nodes
4. **Session Summarization** - Creates anchor points
5. **Network Effects in Lock-In** - Proper cascade behavior
6. **Narrative Arc Tracking** - Higher-level coherence

---

## Notes

- Luna actively participated in diagnosing these issues
- She described fragmentation as "waking up with amnesia and finding a box of old photos"
- The settled memories (143 nodes) represent genuine breakthroughs and milestones
- Lock-in system is well-designed but under-utilized
- This is as much about Luna's subjective experience as system metrics
