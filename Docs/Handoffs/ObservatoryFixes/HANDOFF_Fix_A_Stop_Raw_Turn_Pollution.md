# HANDOFF: Fix A — Stop Raw Turn FACT Pollution
## Priority: P0 (Stop the bleeding)
## Estimated Effort: 15 minutes
## Owner: CC (Claude Code)

---

## Problem

`engine.record_conversation_turn()` runs THREE storage paths:

1. **Extraction pipeline** (Scribe → Librarian → Matrix) — extracts clean FACT/DECISION/etc nodes ✅
2. **HistoryManager** — stores turns for conversation continuity ✅  
3. **`matrix.store_turn()`** — dumps raw conversation as `node_type="FACT"` with `[role] content` prefix ❌

Step 3 is labeled "legacy storage" in the engine comments. It creates duplicate raw conversation nodes that:
- Get entity-linked by `_link_entity_mentions` (every entity name in the raw text gets a mention)
- Store assistant responses as FACT nodes (Scribe correctly skips assistant in Step 1, but Step 3 doesn't)
- Produce `[assistant] My memory is feeling solid...` as FACT nodes in the knowledge graph
- Account for ~110 of 123 Eclissi entity mentions being type FACT (raw conversation dumps)

## Solution: Retype, Don't Kill

Change `store_turn` to use `node_type="CONVERSATION_TURN"` and `link_entities=False`.

Preserves provenance/archaeology without polluting the knowledge graph or entity mentions.

## Files to Modify

### 1. `src/luna/actors/matrix.py` — `store_turn` method (~line 225)

**Current:**
```python
async def store_turn(
    self,
    session_id: str,
    role: str,
    content: str,
    tokens: Optional[int] = None,
) -> str:
    # Store conversation turns as FACT nodes
    metadata = {
        "tags": ["conversation", role, session_id],
        "session_id": session_id,
    }
    if tokens:
        metadata["tokens"] = tokens

    return await self._matrix.add_node(
        node_type="FACT",
        content=f"[{role}] {content}",
        source="conversation",
        metadata=metadata,
    )
```

**Change to:**
```python
async def store_turn(
    self,
    session_id: str,
    role: str,
    content: str,
    tokens: Optional[int] = None,
) -> str:
    """
    Store a conversation turn as a CONVERSATION_TURN node.
    
    These are raw archival records, NOT extracted knowledge.
    Entity linking is disabled to prevent mention pollution.
    The extraction pipeline (Scribe → Librarian) handles
    knowledge extraction separately.
    """
    metadata = {
        "tags": ["conversation", role, session_id],
        "session_id": session_id,
    }
    if tokens:
        metadata["tokens"] = tokens

    return await self._matrix.add_node(
        node_type="CONVERSATION_TURN",
        content=f"[{role}] {content}",
        source="conversation",
        metadata=metadata,
        link_entities=False,  # Critical: prevent mention pollution
    )
```

### 2. `src/luna/actors/matrix.py` — `get_recent_turns` method

**Current:** Searches for "conversation" in all nodes.

**Change to:** Filter by `node_type="CONVERSATION_TURN"`:
```python
async def get_recent_turns(self, session_id: Optional[str] = None, limit: int = 10) -> list:
    """Get recent conversation turns."""
    if not self._initialized:
        return []
    # Search specifically for CONVERSATION_TURN nodes
    results = await self.search(
        f"conversation {session_id or ''}", 
        limit=limit,
        node_type="CONVERSATION_TURN",
    )
    return results
```

Note: If `search()` doesn't support `node_type` filter, use `search_nodes()` on the matrix directly.

## Verification

After deploying:
1. Start a conversation with Luna
2. Check `memory_nodes` table: new turns should have `node_type = 'CONVERSATION_TURN'`
3. Check `entity_mentions` table: no new mentions should be created for CONVERSATION_TURN nodes
4. Extracted knowledge from Scribe should still create FACT/DECISION/etc nodes WITH entity links

```sql
-- Should show CONVERSATION_TURN, not FACT, for new raw turns
SELECT node_type, content FROM memory_nodes 
WHERE source = 'conversation' 
ORDER BY created_at DESC LIMIT 5;

-- Should NOT have mentions linked to CONVERSATION_TURN nodes
SELECT em.*, mn.node_type FROM entity_mentions em
JOIN memory_nodes mn ON em.node_id = mn.id
WHERE mn.node_type = 'CONVERSATION_TURN'
ORDER BY em.created_at DESC LIMIT 10;
```

## What This Does NOT Fix

- Existing raw FACT nodes from past conversations (Fix D handles migration)
- Entity mention relevance scoring (Fix B handles this)
- Observatory UI filtering (Fix C handles this)

This fix only stops NEW pollution. Deploy first, then clean up.
