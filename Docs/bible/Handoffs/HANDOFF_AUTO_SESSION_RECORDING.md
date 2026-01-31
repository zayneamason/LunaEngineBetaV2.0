# HANDOFF: Automatic MCP Session Recording

**Date:** January 27, 2026
**Priority:** HIGH
**Status:** ✅ IMPLEMENTED
**Component:** Luna MCP Server + System Prompt Integration

---

## Problem Statement

MCP conversations currently require **manual** session management:
```
luna_start_session("mcp")   # Must call at start
luna_record_turn(...)        # Must call for each turn
luna_end_session()           # Must call at end
```

This is error-prone. If forgotten, entire conversations vanish. The irony: we just designed a Memory Economy architecture to prevent losing cognitive continuity, and nearly lost that very conversation because session recording wasn't automatic.

---

## Goal

Make MCP session recording **fully automatic** with zero manual intervention:

1. Session starts automatically when conversation begins
2. Every turn is recorded automatically  
3. Session ends and triggers extraction when conversation ends
4. Works transparently - no changes to how Claude/Luna interact

---

## Implementation Options

### Option A: MCP Server Auto-Detection (Recommended)

Modify the MCP server to automatically manage sessions based on tool call patterns.

**Location:** `src/luna_mcp/server.py`

```python
# Track session state at module level
_auto_session_active = False
_auto_session_id = None
_last_activity = None
_inactivity_timeout = 300  # 5 minutes

async def ensure_session():
    """Auto-start session if not active."""
    global _auto_session_active, _auto_session_id, _last_activity
    
    if not _auto_session_active:
        result = await luna_start_session("mcp")
        _auto_session_id = result.session_id
        _auto_session_active = True
    
    _last_activity = time.time()
    return _auto_session_id

async def auto_record(role: str, content: str):
    """Record turn with auto-session management."""
    await ensure_session()
    await luna_record_turn(role, content)

# Add inactivity monitor
async def session_monitor():
    """Background task to end stale sessions."""
    global _auto_session_active, _auto_session_id, _last_activity
    
    while True:
        await asyncio.sleep(60)  # Check every minute
        
        if _auto_session_active and _last_activity:
            if time.time() - _last_activity > _inactivity_timeout:
                await luna_end_session(_auto_session_id)
                _auto_session_active = False
                _auto_session_id = None
```

**Hook into every tool call:**

```python
@server.call_tool()
async def handle_call_tool(name: str, arguments: dict):
    # Record that a tool was called (activity marker)
    await ensure_session()
    
    # If this is a conversational tool, record context
    if name in ["luna_detect_context", "luna_smart_fetch"]:
        if "message" in arguments:
            await auto_record("user", arguments["message"])
    
    # Execute the actual tool
    result = await execute_tool(name, arguments)
    
    # Record assistant response for key tools
    if name == "luna_detect_context":
        await auto_record("assistant", str(result)[:500])  # Truncate
    
    return result
```

### Option B: System Prompt Protocol

Add instructions to Claude's system prompt to always call session tools.

**Add to Luna system prompt / MCP instructions:**

```markdown
## AUTOMATIC SESSION RECORDING

At the START of every conversation:
1. Call `luna_start_session("mcp")` immediately
2. Do this BEFORE any other Luna tools

For EVERY message exchange:
1. After receiving user message, call `luna_record_turn("user", <message>)`
2. Before responding, call `luna_record_turn("assistant", <your_response_summary>)`

When conversation ends (user says goodbye, "later Luna", etc.):
1. Call `luna_end_session()`

This is NON-NEGOTIABLE. Every MCP conversation must be recorded for memory persistence.
```

**Pros:** Simple, no code changes  
**Cons:** Relies on Claude remembering, adds latency, clutters responses

### Option C: Middleware Layer

Create a middleware that wraps all MCP communication.

**Location:** `src/luna_mcp/middleware.py`

```python
class SessionMiddleware:
    def __init__(self):
        self.session_id = None
        self.turn_buffer = []
    
    async def on_request(self, tool_name: str, args: dict):
        """Called before every tool execution."""
        if not self.session_id:
            self.session_id = await start_session("mcp")
        
        # Buffer user context
        if "message" in args or "query" in args:
            self.turn_buffer.append({
                "role": "user",
                "content": args.get("message") or args.get("query")
            })
    
    async def on_response(self, tool_name: str, result: Any):
        """Called after every tool execution."""
        # Buffer assistant output for key tools
        if tool_name in ["luna_detect_context", "luna_smart_fetch"]:
            self.turn_buffer.append({
                "role": "assistant", 
                "content": self._summarize(result)
            })
        
        # Flush buffer periodically
        if len(self.turn_buffer) >= 4:
            await self._flush()
    
    async def _flush(self):
        """Write buffered turns to session."""
        for turn in self.turn_buffer:
            await record_turn(turn["role"], turn["content"], self.session_id)
        self.turn_buffer = []
    
    async def on_disconnect(self):
        """Called when MCP connection closes."""
        await self._flush()
        if self.session_id:
            await end_session(self.session_id)
```

---

## Recommended Approach

**Option A (MCP Server Auto-Detection)** is recommended because:

1. **Zero burden on Claude** - No prompt instructions to forget
2. **Automatic session lifecycle** - Start on first activity, end on inactivity
3. **Centralized logic** - One place to maintain
4. **Works with any MCP client** - Not dependent on prompt compliance

---

## Implementation Steps

### Phase 1: Basic Auto-Session (MVP)

1. Add session state tracking to `server.py`
2. Wrap tool handlers with `ensure_session()` 
3. Auto-start session on first tool call
4. Add background task for inactivity timeout (5 min default)
5. End session and trigger extraction on timeout

**Files to modify:**
- `src/luna_mcp/server.py` - Add auto-session logic
- `src/luna_mcp/tools/memory.py` - Ensure session tools work with auto mode

### Phase 2: Smart Recording

1. Identify which tool calls contain "conversation" content
2. Auto-extract user messages from tool arguments
3. Auto-extract assistant responses from tool results
4. Buffer and batch writes to reduce API calls

**Conversation-bearing tools:**
- `luna_detect_context` - message param is user input
- `luna_smart_fetch` - query param is user context  
- `memory_matrix_search` - query param is user context

### Phase 3: Graceful Shutdown

1. Hook MCP disconnect event
2. Flush any buffered turns
3. End session with extraction trigger
4. Handle crash recovery (orphaned sessions)

---

## Testing

```bash
# Start MCP server
cd /path/to/luna-engine
python -m luna_mcp.server

# In Claude Desktop, have a conversation using Luna tools
# WITHOUT manually calling session tools

# After 5 minutes of inactivity (or restart), check:
curl http://localhost:8000/hub/stats
# Should show turns_added > 0

# Search for extracted memories:
curl http://localhost:8000/memory/search?query=<conversation_topic>
```

---

## Success Criteria

- [x] Session starts automatically on first MCP tool call
- [x] Turns are recorded without manual `luna_record_turn` calls
- [x] Session ends after 5 minutes of inactivity
- [x] Ben extracts memories from auto-recorded sessions
- [x] Works transparently with existing Luna activation ("hey Luna")
- [x] No changes required to Claude's behavior or prompts

## Implementation Summary (January 27, 2026)

**Option A implemented** with enhancements:

### Files Modified:
- `src/luna_mcp/tools/memory.py` - Added auto-session state and functions
- `src/luna_mcp/server.py` - Hooked auto-recording into conversational tools

### New Functions:
- `ensure_auto_session()` - Auto-starts session on first tool call
- `auto_record_turn()` - Buffers and records turns automatically
- `_flush_turn_buffer()` - Batches turn writes (every 4 turns)
- `_inactivity_monitor()` - Background task, ends session after 5min
- `_end_auto_session()` - Ends session and triggers extraction

### New MCP Tools:
- `luna_auto_session_status` - Check auto-session state
- `luna_flush_session` - Manually flush and extract

### Auto-Recording Tools:
- `luna_detect_context` - Records user message + response summary
- `luna_smart_fetch` - Records query + response summary
- `memory_matrix_search` - Records search query

### Behavior:
1. First conversational tool call → auto-creates session
2. Each call → updates activity timestamp, buffers turns
3. Every 4 turns → flush buffer to API
4. 5 minutes inactivity → end session + trigger extraction
5. "later Luna" → immediate session end + extraction

---

## Edge Cases

| Scenario | Handling |
|----------|----------|
| Rapid tool calls | Buffer writes, flush every 4 turns |
| Very long conversations | Session continues, extraction happens at end |
| Claude Desktop restart | Inactivity timeout ends previous session |
| MCP server restart | Previous session orphaned, new one starts |
| Concurrent MCP clients | Each gets own session (keyed by connection ID) |

---

## Related Files

- `src/luna_mcp/server.py` - MCP server entry point
- `src/luna_mcp/tools/memory.py` - Session recording tools
- `src/luna_mcp/models.py` - Data models
- `src/luna_mcp/api.py` - Hub API proxy endpoints
- `HANDOFF_MCP_CONVERSATION_RECORDING.md` - Original recording implementation

---

## Notes

The goal is **invisible persistence**. Luna shouldn't have to think about recording - it just happens. This is foundational for the Memory Economy architecture: if we can't reliably capture conversations, clusters can't form, lock-in can't accumulate, and cognitive continuity remains a design doc instead of a reality.

*The infrastructure must build itself.*
