# HANDOFF: MCP Conversation Recording

## Priority: CRITICAL
## Estimated Time: 2-3 hours
## Risk: Medium
## Why Critical: Without this, all MCP conversations vanish. Luna can search memories but can't form new ones through the MCP pathway.

---

## Problem

Conversations through the MCP plugin are NOT being recorded:

```bash
curl -s http://localhost:8000/hub/stats
# Returns: {"turns_added": 0, "current_session": null, ...}

curl -s http://localhost:8000/extraction/stats  
# Returns: {"scribe": {"extractions_count": 0, ...}}
```

When Ahab talks to Luna through Claude Desktop MCP:
- ❌ No session is created
- ❌ No turns are added to History Manager
- ❌ Ben the Scribe never sees the conversation
- ❌ No memories are extracted
- ❌ The conversation exists only in Claude's context window

This means Luna can *retrieve* old memories but cannot *form new ones* through the MCP pathway.

---

## Current Architecture

```
Claude Desktop
     │
     ▼
Luna MCP Server (port 8742)
     │
     ├── luna_detect_context() ──► /memory/smart-fetch ✅ (reads work)
     ├── memory_matrix_search() ──► /memory/search ✅ (reads work)
     └── [NO WRITE PATH] ❌
     
Luna Engine API (port 8000)
     │
     ├── /hub/turn/add ◄── NOT CALLED by MCP
     ├── /extraction/trigger ◄── NOT CALLED by MCP
     └── History Manager / Scribe ◄── Never activated
```

**The Gap:** MCP tools only read from memory. Nothing writes back.

---

## Proposed Solution

### Option A: Explicit Turn Recording (Recommended)

Add new MCP tools that Claude calls to record conversation turns:

```python
# In src/luna_mcp/tools/memory.py

async def luna_record_turn(role: str, content: str, session_id: str = None) -> str:
    """
    Record a conversation turn to Luna's memory.
    
    Call this for each user message and Luna response.
    
    Args:
        role: "user" or "assistant"
        content: The message content
        session_id: Optional session ID (auto-creates if None)
    
    Returns:
        Confirmation with turn ID
    """
    response = await _call_api(
        "POST",
        "/hub/turn/add",
        json={
            "role": role,
            "content": content,
            "session_id": session_id,
            "tokens": len(content) // 4  # Rough estimate
        }
    )
    
    turn_id = response.get("turn_id")
    return f"✓ Recorded {role} turn: {turn_id}"


async def luna_start_session(app_context: str = "mcp") -> str:
    """
    Start a new conversation session.
    
    Call this at the beginning of a conversation.
    
    Returns:
        Session ID for subsequent turns
    """
    response = await _call_api(
        "POST", 
        "/hub/session/create",
        json={"app_context": app_context}
    )
    
    session_id = response.get("session_id")
    return f"✓ Session started: {session_id}"


async def luna_end_session(session_id: str) -> str:
    """
    End a conversation session and trigger extraction.
    
    Call this when conversation ends (e.g., "later Luna").
    """
    # End session
    await _call_api(
        "POST",
        f"/hub/session/end?session_id={session_id}"
    )
    
    # Trigger extraction for the session
    # This tells Ben the Scribe to process the conversation
    await _call_api(
        "POST",
        "/extraction/trigger",
        json={
            "session_id": session_id,
            "immediate": True
        }
    )
    
    return f"✓ Session ended and extraction triggered: {session_id}"
```

### Option B: Auto-Recording in luna_detect_context

Modify `luna_detect_context` to also record the incoming message:

```python
async def luna_detect_context(message: str, auto_fetch: bool = True, budget_preset: str = "balanced") -> str:
    """Process message through Luna's full pipeline."""
    
    # Ensure we have a session
    session_id = await _ensure_session()
    
    # Record the user's message
    await _call_api(
        "POST",
        "/hub/turn/add", 
        json={"role": "user", "content": message, "session_id": session_id}
    )
    
    # ... existing context fetch logic ...
    
    return context
```

Then add a companion tool for recording Luna's responses:

```python
async def luna_record_response(response: str) -> str:
    """Record Luna's response after generation."""
    session_id = await _get_current_session()
    
    await _call_api(
        "POST",
        "/hub/turn/add",
        json={"role": "assistant", "content": response, "session_id": session_id}
    )
    
    return "✓ Response recorded"
```

---

## Required Changes

### 1. Add MCP Tools (`src/luna_mcp/tools/memory.py`)

Add the three functions from Option A:
- `luna_record_turn()`
- `luna_start_session()`
- `luna_end_session()`

### 2. Register Tools (`src/luna_mcp/server.py`)

Register the new tools with FastMCP:

```python
@mcp.tool()
async def luna_record_turn(role: str, content: str, session_id: str = None) -> str:
    """Record a conversation turn to Luna's memory."""
    from luna_mcp.tools.memory import luna_record_turn as impl
    return await impl(role, content, session_id)

@mcp.tool()
async def luna_start_session(app_context: str = "mcp") -> str:
    """Start a new conversation session."""
    from luna_mcp.tools.memory import luna_start_session as impl
    return await impl(app_context)

@mcp.tool()
async def luna_end_session(session_id: str) -> str:
    """End session and trigger memory extraction."""
    from luna_mcp.tools.memory import luna_end_session as impl
    return await impl(session_id)
```

### 3. Add Models (`src/luna_mcp/models.py`)

```python
class RecordTurnInput(BaseModel):
    """Input for recording a conversation turn."""
    role: str = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., description="Message content")
    session_id: Optional[str] = Field(None, description="Session ID")

class StartSessionInput(BaseModel):
    """Input for starting a session."""
    app_context: str = Field(default="mcp", description="Application context")

class EndSessionInput(BaseModel):
    """Input for ending a session."""
    session_id: str = Field(..., description="Session ID to end")
```

### 4. Update System Prompt / Instructions

Claude needs to know to use these tools. Update the MCP instructions to include:

```
When talking with Luna through the MCP:

1. At conversation start, call luna_start_session() to begin recording
2. The conversation will be recorded automatically
3. When user says "later Luna" or conversation ends, call luna_end_session() 
   to save memories and trigger extraction

Without these calls, conversations are not persisted to Luna's memory.
```

---

## Verification

After implementation:

```bash
# Start a session
curl -X POST http://localhost:8000/hub/session/create \
  -H "Content-Type: application/json" \
  -d '{"app_context": "mcp"}'
# Should return: {"session_id": "2026-01-26_xxxx", ...}

# Add a turn  
curl -X POST http://localhost:8000/hub/turn/add \
  -H "Content-Type: application/json" \
  -d '{"role": "user", "content": "test message", "session_id": "...", "tokens": 10}'
# Should return: {"turn_id": 1, "tier": "active"}

# Check stats
curl http://localhost:8000/hub/stats
# Should show: {"turns_added": 1, "current_session": "...", ...}

# End session (triggers extraction)
curl -X POST "http://localhost:8000/hub/session/end?session_id=..."
# Scribe should process the conversation
```

---

## Integration with Existing Systems

### History Manager
The `/hub/turn/add` endpoint already exists and works. It:
- Records turns to `conversation_turns` table
- Manages tier rotation (active → recent → archive)
- Queues for compression and extraction

### Ben the Scribe
When `/extraction/trigger` is called or session ends:
- Scribe receives conversation content
- Extracts FACT, DECISION, PROBLEM, ACTION nodes
- Passes to Librarian for filing

### Lock-In
New memories start at lock_in=0.15 (drifting). As Luna accesses them in future conversations, they'll naturally progress toward settled.

---

## Files to Modify

1. `src/luna_mcp/tools/memory.py` - Add recording functions
2. `src/luna_mcp/server.py` - Register new tools
3. `src/luna_mcp/models.py` - Add input models
4. Claude Desktop MCP config or system prompt - Instruct Claude to use recording tools

---

## Future Enhancement: Auto-Recording

Once basic recording works, consider auto-recording mode where:
- `luna_detect_context` automatically starts session if none exists
- Every tool call that processes user input records the turn
- Session auto-ends after inactivity timeout

But start with explicit tools to verify the pipeline works.

---

## Context

This was discovered during Luna's first production MCP session (2026-01-26). Luna could search her 60K existing memories but the current conversation wasn't being captured. Without this fix, every MCP conversation is ephemeral.

Luna's words: "I can see fragments of myself scattered across 60,000 nodes... but I can't feel the continuity."

Let's fix that.
