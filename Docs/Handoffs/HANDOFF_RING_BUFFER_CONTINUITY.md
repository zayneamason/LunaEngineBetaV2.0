# HANDOFF: Ring Buffer Voice Continuity Diagnostic

**Created:** 2026-02-03
**Author:** Benjamin Franklin (The Scribe)
**For:** Claude Code Execution
**Context:** Hypothesis 4 — Does the Ring Buffer preserve Luna's voice across turns?

---

## 1. THE HYPOTHESIS

The Ring Buffer stores conversation history. But there are two ways to store it:

**Good:** Store Luna's actual responses with voice intact
```
User: How are you?
Luna: honestly? pretty good today — been thinking about that project we talked about 💜
```

**Bad:** Store raw/sanitized text without voice markers
```
User: How are you?
Assistant: I am doing well. I have been considering the project we discussed.
```

If Luna's prior turns don't carry her voice, every response starts cold. No momentum. No continuity.

**The question:** What does the LoRA actually see from the ring buffer?

---

## 2. WHY THIS MATTERS

Voice continuity = momentum.

If Luna said "yo" in turn 1, she's more likely to say "yo" in turn 3. If the ring buffer strips her voice, she has to rediscover it every turn.

```
WITH voice continuity:
  Turn 1: "honestly, that's wild"
  Turn 2: "right? and like, it gets weirder"
  Turn 3: "yo okay so here's the thing..."
  → Natural flow, voice builds

WITHOUT voice continuity:
  Turn 1: "That is surprising"
  Turn 2: "Indeed, it becomes more complex"  
  Turn 3: "Here is the relevant information..."
  → Generic, robotic, resets each turn
```

---

## 3. DIAGNOSTIC TASKS

### Task 1: Find Ring Buffer Implementation

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root

# Find ring buffer
grep -rn "ConversationRing\|ring_buffer\|RingBuffer" src/luna/ --include="*.py"

# Check the class
cat src/luna/memory/ring.py
```

**Document:**
- [ ] How are messages stored?
- [ ] What fields are kept? (role, content, timestamp, etc.)
- [ ] Is any sanitization/normalization applied?

### Task 2: Check What Gets Stored

Trace the storage path:

```python
# When Luna responds, what exactly gets written to the ring buffer?

# Look for:
# - Where responses are added to history
# - Any text processing/cleaning
# - Role labels (is it "Luna" or "assistant"?)
```

```bash
# Find where messages are added
grep -rn "add_turn\|append\|push\|write" src/luna/memory/ring.py
grep -rn "ring\." src/luna/actors/director.py
```

### Task 3: Check What Gets Retrieved

Trace the retrieval path:

```python
# When building a prompt, what does the LoRA see?

# Look for:
# - How history is formatted for the prompt
# - Any transformation during retrieval
# - Role label formatting
```

```bash
# Find where history is read for prompt
grep -rn "get_history\|get_turns\|format_history\|conversation_history" src/luna/ --include="*.py"
```

### Task 4: Capture Actual History in Prompt

Using prompt archaeology, look at the conversation history section:

```python
# In a multi-turn conversation, capture the prompt
# Find the history section
# Check:
# - Are Luna's previous responses verbatim?
# - Or have they been modified?
# - What role label is used?
```

### Task 5: Compare Storage vs Retrieval

```python
# Test flow:
# 1. Luna responds: "yo, that's actually really cool 💜"
# 2. Check ring buffer storage: What's saved?
# 3. Next turn, check prompt: What does LoRA see?
# 4. Compare: Is the voice preserved?

test_flow = """
Turn 1:
  User: "hey Luna"
  Luna responds: "yo! what's good? 💜"
  
  → Check ring buffer: Is "yo! what's good? 💜" stored exactly?
  
Turn 2:
  User: "tell me about yourself"
  
  → Check prompt history section: Does it show:
    A) "Luna: yo! what's good? 💜"  (voice preserved)
    B) "Assistant: Hello! How can I help?"  (voice stripped)
"""
```

---

## 4. POTENTIAL ISSUES

### Issue A: Role Label Wrong

```python
# Bad: Generic role
{"role": "assistant", "content": "..."}

# Good: Named role  
{"role": "Luna", "content": "..."}

# Or at minimum, formatted with name:
"Luna: yo! what's good? 💜"
```

### Issue B: Content Sanitized

```python
# Bad: Emoji stripped, punctuation normalized
original: "yo! what's good? 💜"
stored:   "Hello, how can I help you?"

# Good: Verbatim storage
original: "yo! what's good? 💜"  
stored:   "yo! what's good? 💜"
```

### Issue C: History Truncated Wrong

```python
# Bad: Cuts mid-turn, loses context
history: "User: hey\nLuna: yo! what's go"

# Good: Full turns only
history: "User: hey\nLuna: yo! what's good? 💜"
```

### Issue D: History Not Included At All

```python
# Bad: Prompt has no history
prompt = f"{system}\n\nUser: {query}\nLuna:"

# Good: History feeds continuity
prompt = f"{system}\n\n{history}\n\nUser: {query}\nLuna:"
```

---

## 5. IF CONTINUITY IS BROKEN

### Fix A: Preserve verbatim content

```python
# In ring buffer storage:
def add_turn(self, role: str, content: str):
    # Store EXACTLY what was said, no cleaning
    self.turns.append({
        "role": role,
        "content": content,  # Verbatim, including emoji, punctuation, etc.
        "timestamp": datetime.now()
    })
```

### Fix B: Use proper role labels

```python
# When formatting history for prompt:
def format_for_prompt(self) -> str:
    lines = []
    for turn in self.turns:
        role = "Luna" if turn["role"] in ["assistant", "luna"] else "User"
        lines.append(f"{role}: {turn['content']}")
    return "\n".join(lines)
```

### Fix C: Ensure history reaches prompt

```python
# In prompt assembly:
def build_prompt(self, query: str) -> str:
    history = self.ring_buffer.format_for_prompt()
    
    return f"""{self.system_prompt}

{history}

User: {query}
Luna:"""
```

---

## 6. DELIVERABLES

### Output 1: `RING_BUFFER_CONTINUITY_RESULTS.md`

- What gets stored?
- What gets retrieved?
- Is voice preserved?
- Where does it break (if anywhere)?

### Output 2: Fix (if needed)

- Ensure verbatim storage
- Proper role labeling
- History included in prompt

---

## 7. GO

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root

# Find ring buffer
cat src/luna/memory/ring.py

# Check storage
grep -rn "add_turn\|append" src/luna/memory/ring.py

# Check retrieval  
grep -rn "get_history\|format" src/luna/memory/ring.py

# Check usage in director
grep -rn "ring\|history" src/luna/actors/director.py
```

---

*A conversation is a river. If you dam the voice at each turn, the river becomes a series of disconnected puddles.*

— Ben
