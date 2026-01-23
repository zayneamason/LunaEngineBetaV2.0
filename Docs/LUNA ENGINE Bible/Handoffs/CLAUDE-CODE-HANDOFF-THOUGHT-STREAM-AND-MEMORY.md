# HANDOFF: Thought Stream & Memory Context Fixes

**Created**: 2026-01-21
**Priority**: HIGH
**Symptom**: Luna says "my memory's a bit fuzzy" and Thought Stream shows only "Connected to Luna's mind..."

---

## WHAT THIS FIXES

| Before | After |
|--------|-------|
| Thought Stream dead on simple queries | Shows progress for ALL queries |
| "What were we talking about?" → Empty memory | Returns recent conversation turns |
| No visibility during Claude delegation | Shows `[DIRECT]` or `[OK]` status |

---

## ROOT CAUSE ANALYSIS

### Problem 1: No Progress Emissions on DIRECT Path

**Location**: `src/luna/engine.py` → `_process_direct()`

The Thought Stream SSE endpoint (`/thoughts`) shows data from `_on_progress_callbacks`. These only fire when `_emit_progress()` is called. The DIRECT path (simple queries) goes straight to Director mailbox without any progress emissions.

### Problem 2: Keyword Search Fails for Backward References

**Location**: `src/luna/substrate/memory.py` → `get_context()` (around line 475)

Query: "what were we just talking about?"
- Stopwords filtered: "what", "were", "we", "just", "about"
- Keywords left: "talking"
- Search: `WHERE content LIKE '%talking%'`
- Result: Empty (unless someone literally said "talking")

Conversation turns ARE stored in `memory_nodes` with `metadata LIKE '%"conversation"%'` but keyword search doesn't find them.

---

## FIX 1: Emit Progress for DIRECT Queries

**File**: `src/luna/engine.py`

### Step 1A: Add emission in `_process_direct()`

Find `_process_direct` method (search for `async def _process_direct`). Add this line near the top:

```python
async def _process_direct(
    self,
    user_message: str,
    correlation_id: str,
    memory_context: str = "",
    history_context: Optional[Dict[str, Any]] = None
) -> None:
    """Direct path - skip planning, go straight to Director."""
    
    # === ADD THIS LINE ===
    await self._emit_progress(f"[DIRECT] {user_message[:40]}...")
    
    # ... rest of existing code unchanged ...
```

### Step 1B: Add completion emission in `_handle_actor_message()`

Find the `generation_complete` case in `_handle_actor_message` method. Add emission after extracting the text:

```python
case "generation_complete":
    data = payload.get("data", {})
    text = data.get("text", "")
    
    # === ADD THESE LINES ===
    tokens = data.get("output_tokens", 0)
    route = "local" if data.get("local") else "delegated"
    await self._emit_progress(f"[OK] {route}: {tokens} tokens")
    
    # ... rest of existing code unchanged ...
```

---

## FIX 2: Conversation Fallback for Backward References

**File**: `src/luna/substrate/memory.py`

### Find the `get_context` method and replace the keyword extraction section

Find this code (around line 475):
```python
# Extract meaningful words (3+ chars, not stopwords)
words = [w.strip(".,!?;:'\"()[]{}") for w in query.lower().split()]
keywords = [w for w in words if len(w) >= 3 and w not in stopwords]

if not keywords:
    # Fall back to original behavior if no keywords found
    keywords = [query]

logger.debug(f"Context search keywords: {keywords}")
```

Replace with:
```python
# Extract meaningful words (3+ chars, not stopwords)
words = [w.strip(".,!?;:'\"()[]{}") for w in query.lower().split()]
keywords = [w for w in words if len(w) >= 3 and w not in stopwords]

# Detect backward reference patterns (need recent conversation, not keyword search)
backward_patterns = [
    "what were we", "what did we", "what was that",
    "earlier", "before", "last time", "just now",
    "you said", "you mentioned", "we discussed", "we talked",
    "remember when", "do you remember", "recall",
    "where were we", "continue", "going back"
]
is_backward_ref = any(p in query.lower() for p in backward_patterns)

# For backward references OR no keywords: fetch recent conversation directly
if is_backward_ref or not keywords:
    logger.info(f"Context: backward_ref={is_backward_ref}, keywords={keywords or 'empty'} → fetching conversation")
    
    # Query conversation turns stored as FACT nodes with conversation tag
    conversation_rows = await self.db.fetchall("""
        SELECT * FROM memory_nodes
        WHERE metadata LIKE '%"conversation"%'
        ORDER BY created_at DESC
        LIMIT 15
    """)
    
    if conversation_rows:
        results = []
        total_chars = 0
        max_chars = max_tokens * 4  # ~4 chars per token
        
        for row in conversation_rows:
            node = MemoryNode.from_row(row)
            if total_chars + len(node.content) > max_chars:
                break
            results.append(node)
            total_chars += len(node.content)
            await self.record_access(node.id)
        
        logger.info(f"Context: returning {len(results)} conversation turns ({total_chars} chars)")
        return results
    
    # No conversation found - fall through to keyword search
    logger.debug("Context: no conversation found, falling back to keyword search")

if not keywords:
    keywords = [query]

logger.debug(f"Context search keywords: {keywords}")
```

**That's it.** No merge logic needed - if backward reference detected, return conversation and exit. Otherwise continue with normal keyword search.

---

## TESTING

### Thought Stream
```
Send: "hi luna"
Expected: Thought Stream shows "[DIRECT] hi luna..."
Expected: After response shows "[OK] delegated: 94 tokens"
```

### Memory
```
Send: "what were we talking about?"
Expected: Luna recalls recent conversation, NOT "my memory's a bit fuzzy"

Send: "do you remember what I said?"
Expected: Returns actual recent user messages
```

---

## FILES CHANGED

1. `src/luna/engine.py` - 2 small additions (~4 lines total)
2. `src/luna/substrate/memory.py` - Replace ~10 lines with ~30 lines

---

## EXECUTION

1. Fix 1 first (2 minutes) - Immediate UI feedback
2. Fix 2 second (5 minutes) - Fixes actual memory issue

Both are independent. Test each separately.
