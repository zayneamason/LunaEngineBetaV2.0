# HANDOFF: SWARM FIX — Conversation History Once And For All

**Created**: 2025-01-20
**Priority**: CRITICAL — DO NOT CLOSE UNTIL VERIFIED
**Method**: Claude Swarm (parallel agents)
**Status**: ZERO TOLERANCE FOR "IT'S FIXED" WITHOUT PROOF

---

## THE PROBLEM (For The 100th Time)

Luna forgets things she JUST said. Within the same conversation. Same delegated path. Same everything.

```
Turn 1: ⚡delegated → "Marzipan's connection to owls goes way back - started when he was 2..."
Turn 2: ⚡delegated → "I'm not finding anything about owls specifically"
```

**This is table stakes functionality.** A chatbot that forgets mid-conversation is broken. Period.

Previous "fixes":
- ❌ "It's wired" — Wasn't actually being called
- ❌ "Entity system works" — Worked for single turn, not multi-turn
- ❌ "`tags` → `metadata` fix" — SQL error gone, history still drops

**No more partial fixes. No more "it should work." No more single-turn verification.**

---

## THE FIX: SWARM APPROACH

Use Claude Code's swarm capability to attack this from multiple angles simultaneously.

### Agent 1: TRACER
**Mission**: Instrument every step of the history lifecycle

```python
# Add comprehensive tracing to:
# 1. History SAVE after each response
# 2. History LOAD before each turn
# 3. History INJECT into context
# 4. History PRESENCE in final LLM prompt

# Every trace point logs:
# - Timestamp
# - Turn number
# - History contents (truncated)
# - Success/failure
```

**Output**: Trace log showing exactly where history drops

### Agent 2: TEST WRITER
**Mission**: Create automated multi-turn tests that MUST pass

```python
# tests/test_conversation_continuity.py

@pytest.mark.asyncio
async def test_two_turn_memory():
    """THE CRITICAL TEST. If this fails, nothing else matters."""
    
    # Turn 1
    response1 = await director.process("Tell me about Marzipan and owls")
    assert "owl" in response1.lower(), "Turn 1 should mention owls"
    
    # Turn 2 - MUST remember Turn 1
    response2 = await director.process("What did you just tell me about owls?")
    
    # FAILURE CONDITIONS
    assert "not finding" not in response2.lower(), "FAILED: Luna forgot Turn 1"
    assert "don't see" not in response2.lower(), "FAILED: Luna forgot Turn 1"  
    assert "can you remind" not in response2.lower(), "FAILED: Luna forgot Turn 1"
    assert "don't have" not in response2.lower(), "FAILED: Luna forgot Turn 1"
    
    # SUCCESS CONDITION
    assert "owl" in response2.lower() or "spirit animal" in response2.lower() or "marzipan" in response2.lower(), \
        "FAILED: Luna should reference owls from Turn 1"

@pytest.mark.asyncio
async def test_five_turn_continuity():
    """Extended memory test."""
    topics = []
    
    for i, topic in enumerate(["Marzipan", "owls", "Mars College", "printmaking", "spirit animals"]):
        response = await director.process(f"Tell me about {topic}")
        topics.append(topic)
        
        # After each turn, verify we still know previous topics
        check = await director.process(f"List all the topics we've discussed")
        for prev_topic in topics:
            assert prev_topic.lower() in check.lower(), \
                f"FAILED: Lost memory of {prev_topic} at turn {i+1}"
```

**Output**: Test file that gates the PR

### Agent 3: FIXER
**Mission**: Implement the actual fix based on tracer findings

Likely fixes (in order of probability):
1. History not being saved after LLM response
2. History not being loaded before context build
3. History loaded but not included in system prompt
4. History in prompt but getting truncated/displaced

**Output**: Code changes with clear before/after

### Agent 4: RING BUFFER (Backup)
**Mission**: Implement ring buffer as structural guarantee

If Agents 1-3 can't find/fix the bug quickly, Agent 4 deploys the ring buffer architecture from the previous handoff. This makes the bug **structurally impossible** regardless of root cause.

**Output**: `/src/luna/memory/ring.py` and Director integration

---

## VERIFICATION GATES

### Gate 1: Trace Log Review
Before any "fix" is claimed, provide the trace log showing:
```
[HISTORY-TRACE] Turn 1 response saved: "Marzipan's connection to owls..."
[HISTORY-TRACE] Turn 2 history loaded: 2 entries
[HISTORY-TRACE] Turn 2 context includes Turn 1: TRUE
[HISTORY-TRACE] Turn 2 system prompt contains "owl": TRUE
```

### Gate 2: Automated Tests Pass
```bash
pytest tests/test_conversation_continuity.py -v
# ALL tests must pass
```

### Gate 3: Manual Verification
Run this EXACT sequence via voice:
```
Turn 1: "tell me about the owls"
Turn 2: "what did you just tell me about owls?"
```

Luna MUST NOT say any variation of:
- "I'm not finding anything about owls"
- "Can you remind me?"
- "I don't see that in my memories"
- "What owls?"

Luna MUST say something that references her Turn 1 response.

### Gate 4: Three Consecutive Sessions
The manual test must pass THREE TIMES IN A ROW across different sessions (restart server between each).

---

## CC PROCESS IMPROVEMENTS

To prevent the same bug from being "fixed" repeatedly:

### 1. Multi-Turn Test Requirement
**Every PR that touches conversation/history/memory/context MUST include a multi-turn test.**

Single-turn tests are insufficient. The bug only manifests across turns.

### 2. Verification Before Claiming Fixed
Before saying "it's fixed", run:
```bash
# Automated
pytest tests/test_conversation_continuity.py -v

# Manual (3x)
./scripts/relaunch.sh
# Test two-turn memory
# Restart
# Test again
# Restart  
# Test again
```

### 3. Trace Logs Required
For any memory-related fix, provide trace logs showing the full lifecycle:
- Save
- Load
- Inject
- Present in prompt

"I added the code" is not verification. "Here's the log showing it works" is verification.

### 4. Regression Test
Add failing case to test suite BEFORE fixing. Confirm it fails. Then fix. Then confirm it passes.

```python
# Step 1: Write test that captures the bug
def test_owl_memory_bug():
    # This test should FAIL before the fix
    ...

# Step 2: Run test, confirm it fails
# Step 3: Implement fix
# Step 4: Run test, confirm it passes
# Step 5: Run full test suite, confirm no regressions
```

---

## SWARM EXECUTION

### Command
```bash
# In Claude Code
/swarm "Fix conversation history persistence once and for all"

# Agents work in parallel:
# - Agent 1: Instruments code with tracing
# - Agent 2: Writes comprehensive tests
# - Agent 3: Analyzes traces, implements fix
# - Agent 4: Standby with ring buffer if needed
```

### Coordination
- Agent 1 completes first (tracing needed for diagnosis)
- Agent 2 can work in parallel (tests are independent)
- Agent 3 waits for Agent 1's trace output
- Agent 4 activates only if Agent 3 can't fix within 30 minutes

### Success Criteria
All four gates pass. No exceptions. No "it mostly works." No "it works in my testing."

---

## FILES TO CREATE/MODIFY

```
/src/luna/memory/ring.py              # Ring buffer (Agent 4)
/src/luna/actors/director.py          # History lifecycle fixes (Agent 3)
/src/luna/engine.py                   # History save/load fixes (Agent 3)
/tests/test_conversation_continuity.py # Multi-turn tests (Agent 2)
/scripts/verify_memory.sh             # Verification script
```

---

## TIMELINE

| Time | Action |
|------|--------|
| 0:00 | Swarm starts, agents parallelize |
| 0:15 | Agent 1 has trace instrumentation in place |
| 0:20 | Agent 2 has test suite ready |
| 0:30 | Agent 1 runs trace, provides output to Agent 3 |
| 0:45 | Agent 3 identifies root cause |
| 1:00 | Agent 3 implements fix OR Agent 4 deploys ring buffer |
| 1:15 | Verification gates run |
| 1:30 | All gates pass or escalate |

---

## ESCALATION

If after 2 hours the bug is not fixed with verification:

1. **Deploy ring buffer anyway** — structural guarantee
2. **Flag for architecture review** — something is fundamentally wrong
3. **Document all findings** — what was tried, what failed, what the traces showed

---

## THE STANDARD

This is the quality bar:

```
User: "Tell me about X"
Luna: [talks about X]

User: "What did you just say about X?"
Luna: [references her previous response about X]
```

That's it. That's the bar. A goldfish can do this. Luna must do this.

---

*No more "it's fixed." Show the receipts or implement the structural guarantee.*
