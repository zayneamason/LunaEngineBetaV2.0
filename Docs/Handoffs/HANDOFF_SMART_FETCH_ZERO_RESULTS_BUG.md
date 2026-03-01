# HANDOFF: luna_smart_fetch Returns Zero Results for Nodes Visible to FTS5

**Priority:** HIGH  
**Filed by:** Luna (via MCP session)  
**Date:** 2026-02-27  
**Symptom:** `luna_smart_fetch` returns 0 nodes / 0 tokens for queries that FTS5 matches with high confidence scores (20-30 range)

---

## The Bug

Benjamin Franklin (Scribe persona) added 15+ memory nodes via `memory_matrix_add_node` during a strategic session. All nodes were confirmed created (got `✓ Added node: <id>` responses). Edges were wired between them via `memory_matrix_add_edge`.

Immediately after, `luna_smart_fetch` was called with relevant queries and returned:

```
# Context: deck mapping competitive positioning investor pitch Palantir Glean fundraising strategy
*Retrieved 0 nodes, 0 tokens*
```

```
# Context: Luna Labs sovereignty enterprise market revenue model data room slides
*Retrieved 0 nodes, 0 tokens*
```

`memory_matrix_search` also returned:
```
No memories found for: deck competitive positioning fundraising Palantir Glean
```

## Diagnostic Evidence

### FTS5 Finds Everything
`observatory_search(query="Palantir Glean competitive landscape deck", method="all")` returned **20 results** with high scores:

| Node ID | Type | Score | Content Preview |
|---------|------|-------|-----------------|
| `60b3d7e0-2d9` | SESSION | 30.14 | Competitive Positioning & Deck Mapping Session |
| `15d313e6-3b0` | FACT | 27.04 | Competitive comparison table (the "kill shot"...) |
| `7b22567e-3f1` | INSIGHT | 24.38 | Luna Labs one-line competitive positioning... |
| `7d930a66-803` | FACT | 21.04 | Three-player competitive landscape... |
| `ec1066f8-9e2` | FACT | 20.69 | Market validation data points... |
| `370758b9-44a` | PROBLEM | 18.28 | 3 slides missing from current deck mapping... |
| `e953a696-990` | PROBLEM | 17.11 | Five competitive positioning vulnerabilities... |

All Ben's nodes are present, indexed, and highly ranked by FTS5.

### Vector Search Is Offline
Observatory replay confirms:
```json
{
  "phase": "vector",
  "note": "Requires engine runtime (sqlite-vec + embedder). Skipped in diagnostic mode.",
  "result_count": 0
}
```

### Graph Neighborhood Works
The replay shows graph traversal successfully finding 6 neighbors from 5 seeds via the edges Ben wired. The graph layer is functional.

### Fusion Is FTS5-Only
```json
{
  "phase": "fusion",
  "note": "Simulated — FTS5 ranking only (no vector component).",
  "result_count": 20
}
```

## The Disconnect

The observatory diagnostic tools (which query the DB directly) can see everything. But the live retrieval pipeline (`luna_smart_fetch` and `memory_matrix_search`) returns nothing.

**Possible causes (ordered by likelihood):**

### 1. luna_smart_fetch Requires Engine Runtime for Assembly
The observatory replay shows fusion returns 20 results but labels it "simulated." The live `luna_smart_fetch` endpoint may require the full engine runtime (including sqlite-vec + embedder) to assemble the final context packet. If the engine isn't running or the assembly phase fails silently, it would return 0 nodes even though FTS5 found matches.

**Check:** Does `luna_smart_fetch` depend on the engine runtime being active? Does it fall back to FTS5-only if vector is unavailable, or does it fail entirely?

### 2. memory_matrix_search Uses a Different Code Path
`memory_matrix_search` also returned zero results. This tool may use a different search implementation than observatory_search. It might be routing through the engine's search endpoint rather than querying SQLite directly.

**Check:** Compare the code path of `memory_matrix_search` vs `observatory_search`. Are they hitting the same DB? Same FTS5 index?

### 3. Embedding Generation Not Triggered on MCP-Added Nodes
Nodes added via `memory_matrix_add_node` (MCP tool) may not trigger embedding generation. If `luna_smart_fetch` requires embeddings to exist (even as a prerequisite for the FTS5 path), nodes without embeddings would be invisible.

**Check:** Do the newly added nodes have entries in the embeddings table? Does `memory_matrix_add_node` call the embedder?

### 4. Access Bridge / Permission Filtering
The retrieval pipeline may apply access filtering that the observatory diagnostic tools bypass. If MCP-added nodes don't get proper access/session tags, they could be filtered out at assembly time.

**Check:** Do the new nodes have the required metadata fields for the retrieval pipeline's access filter?

### 5. Token Budget Exhausted Before Results
Unlikely given 0 results, but check: could the token budget calculation be returning 0 available tokens, causing the assembly phase to skip all results?

## Reproduction Steps

1. Add a node via MCP: `memory_matrix_add_node(node_type="FACT", content="Test node for retrieval debugging", tags=["test"])`
2. Immediately call: `luna_smart_fetch(query="Test node retrieval debugging", budget_preset="balanced")`
3. Expected: Returns the node
4. Actual: Returns 0 nodes, 0 tokens
5. Then call: `observatory_search(query="Test node retrieval debugging", method="fts5")`
6. This WILL return the node, confirming it's in the DB

## Impact

This is a significant reliability issue. The Scribe (Ben) can file memories all day, but Luna can't retrieve them through her normal tools. This means:

- Session context doesn't carry between MCP conversations
- Memory nodes added by any persona are invisible to Luna's live retrieval
- The memory system appears broken to the user even though the data is actually there
- Only the observatory diagnostic tools (which bypass the normal pipeline) can see the data

## Suggested Fix Priority

1. **First:** Determine if `luna_smart_fetch` falls back gracefully when vector search is unavailable, or if it fails entirely
2. **Second:** Ensure `memory_matrix_search` hits the same FTS5 index that `observatory_search` uses
3. **Third:** Verify embedding generation is triggered (or not required) for MCP-added nodes
4. **Fourth:** Add a fallback path so that even without embeddings, FTS5 results flow through to the final context assembly

## Environment

- DB size: 124.2 MB
- Total nodes: 24,066
- Total edges: 23,800
- Nodes added this session: ~15 (all confirmed via add_node responses)
- MCP server: Luna-Hub-MCP-V1
- Observatory: Functional (all diagnostic queries return correct results)

---

*"Lost time is never found again." — and neither, it seems, are memories filed but not indexed for retrieval.*
