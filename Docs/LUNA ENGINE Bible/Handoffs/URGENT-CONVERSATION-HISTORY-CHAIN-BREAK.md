# URGENT HANDOFF: Conversation History Chain Break

**Created**: 2025-01-20
**Priority**: CRITICAL - ROOT CAUSE IDENTIFIED
**Author**: Architecture Session (Dude)

---

## THE BUG

Luna cannot remember ANYTHING said within the same conversation session because **conversation history is never passed through the pipeline**.

The infrastructure EXISTS at every layer but IS NOT WIRED UP.

---

## ROOT CAUSE ANALYSIS

### The Broken Chain

```
VoiceBackend.process_and_respond()
    ↓ hub.process_message(message=user_text, interface="voice")  ← NO HISTORY
        ↓ POST /persona/process {message, interface}  ← NO HISTORY
            ↓ _persona_core.process_query(query=..., budget=...)  ← NO HISTORY
```

### Layer-by-Layer Breakdown

| Layer | File | Has History? | Passes It? |
|-------|------|--------------|------------|
| ConversationManager | `src/voice/conversation/manager.py` | ✅ `get_messages_for_llm()` exists | ❌ Never called |
| VoiceBackend | `src/voice/backend.py` | ✅ Has `self.conversation` | ❌ Doesn't pass to hub |
| HubClient | `src/voice/hub_client.py` | ❌ No param | ❌ Can't pass |
| Hub API | `src/hub/api.py` line 560 | ❌ No param in request model | ❌ Can't pass |
| PersonaCore | `src/persona/core.py` | ✅ `conversation_history` param exists | 🚫 Never receives |

---

## THE FIXES

### Fix 1: Hub API - Accept conversation_history

**File**: `src/hub/api.py`

```python
# Around line 23 - Update request model
class ProcessMessageRequest(BaseModel):
    message: str
    interface: str = "desktop"
    session_id: Optional[str] = None
    generate_response: bool = True
    conversation_history: Optional[List[dict]] = None  # ADD THIS


# Around line 586 - Pass to PersonaCore
result = await _persona_core.process_query(
    query=request.message,
    budget=budget,
    generate_response=request.generate_response,
    conversation_history=request.conversation_history  # ADD THIS
)
```

### Fix 2: HubClient - Accept and pass conversation_history

**File**: `src/voice/hub_client.py`

```python
# Around line 53 - Update method signature
async def process_message(
    self,
    message: str,
    interface: str = "voice",
    session_id: Optional[str] = None,
    generate_response: bool = True,
    conversation_history: Optional[list] = None  # ADD THIS
) -> Optional[HubResponse]:


# Around line 72 - Add to payload
payload = {
    "message": message,
    "interface": interface,
    "generate_response": generate_response
}
if session_id:
    payload["session_id"] = session_id
if conversation_history:  # ADD THIS
    payload["conversation_history"] = conversation_history  # ADD THIS
```

### Fix 3: VoiceBackend - Pass conversation history

**File**: `src/voice/backend.py`

```python
# Around line 295 in process_and_respond() - Update hub call
hub_response = await self.hub.process_message(
    message=user_text,
    interface="voice",
    conversation_history=self.conversation.get_messages_for_llm()  # ADD THIS
)
```

---

## VERIFICATION

After implementing, test with:

```bash
# In voice session:
User: "Tell me about Mars College"
Luna: [responds with info about Mars College]
User: "What did I just ask you about?"
Luna: "You just asked me about Mars College"  # SHOULD WORK NOW
```

Before fix: Luna says "I don't have context about what we were discussing"
After fix: Luna correctly references the previous turn

---

## WHY THIS MATTERS

Without this fix:
- Luna appears to have amnesia within conversations
- Users must repeat context every message
- The "personality" feels fake because there's no conversational continuity
- Memory Matrix can provide long-term recall, but short-term is completely broken

This is a **3-line fix across 3 files** that enables conversation continuity.

---

## FILES TO MODIFY

1. `src/hub/api.py` - Add `conversation_history` to request model and pass to PersonaCore
2. `src/voice/hub_client.py` - Add param and include in payload
3. `src/voice/backend.py` - Pass `self.conversation.get_messages_for_llm()`

---

## TESTING CHECKLIST

- [ ] Hub API accepts conversation_history in request
- [ ] HubClient passes history when calling Hub
- [ ] VoiceBackend passes ConversationManager history
- [ ] PersonaCore receives and uses history
- [ ] Luna can reference previous turns in conversation
- [ ] Marzipan test: Ask about him, then ask "who did I just mention?" - should work

---

*This is the root cause. Fix these 3 files and Luna will remember conversations.*
