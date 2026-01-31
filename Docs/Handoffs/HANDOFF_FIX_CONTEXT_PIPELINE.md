# HANDOFF: Fix Context Pipeline Not Injecting Memories

**Created:** 2026-01-28
**Priority:** P0 — Luna has no knowledge without this
**Symptom:** `used_retrieval: false`, only 586 chars in prompt, memories not reaching model

---

## The Problem

Voight-Kampff Layer 3 shows:
- ❌ `used_retrieval: false` — pipeline didn't even TRY to retrieve
- ❌ Only 586 chars in prompt (just system prompt, no memories)
- ❌ 1/5 expected memory fragments found
- ❌ Luna confabulates instead of remembering (Marzipan = "candy")

**Memory Matrix has 22K+ nodes. They're not reaching the model.**

---

## The Flow (How It Should Work)

```
User message
    ↓
DirectorActor.process()
    ↓
ContextPipeline.assemble(query)  ← THIS IS BEING SKIPPED
    ↓
Retrieved memories + system prompt
    ↓
LocalInference.generate(full_prompt)
    ↓
Response with knowledge
```

**Current broken flow:**
```
User message
    ↓
DirectorActor.process()
    ↓
[SKIP] ContextPipeline  ← NOT CALLED
    ↓
System prompt only (586 chars)
    ↓
LocalInference.generate(empty_context)
    ↓
Generic slop
```

---

## Files to Investigate

### Primary: `src/luna/actors/director.py`

The Director decides routing (local vs delegation) AND should assemble context.

```python
class DirectorActor:
    async def process(self, message, ...):
        # Is context pipeline called here?
        # Is it called for BOTH local and delegation paths?
        # Or only for delegation?
```

**Key questions:**
1. Where is `ContextPipeline.assemble()` called?
2. Is it called for local inference path?
3. Is the result passed to `LocalInference.generate()`?

### Secondary: `src/luna/context/pipeline.py`

The context assembly logic.

```python
class ContextPipeline:
    async def assemble(self, query: str, ...) -> ContextResult:
        # Does this method work?
        # What does it return?
        # Is it being called at all?
```

**Add logging if needed:**
```python
async def assemble(self, query: str, ...):
    logger.info(f"[CONTEXT] assemble() called with: {query[:50]}...")
    # ... existing code
    logger.info(f"[CONTEXT] returning {len(memories)} memories, {len(result)} chars")
    return result
```

### Tertiary: `src/luna/inference/local.py`

Check how LocalInference receives context.

```python
class LocalInference:
    async def generate(self, prompt: str, context: str = None, ...):
        # Is there a context parameter?
        # Is it being used in the final prompt?
        # Or is it ignored?
```

---

## Diagnostic Steps

### Step 1: Check if assemble() is ever called

```bash
grep -n "assemble\|ContextPipeline" src/luna/actors/director.py
```

Look for:
```python
context = await self.context_pipeline.assemble(message)
# or
context = await self.pipeline.assemble(query)
```

### Step 2: Check local vs delegation paths

In `director.py`, find where routing happens:

```python
if complexity < threshold:
    # LOCAL PATH
    # Is context assembled here?
    response = await self.local_inference.generate(...)
else:
    # DELEGATION PATH
    # Is context assembled here?
    response = await self.delegate_to_provider(...)
```

**Common bug:** Context assembled for delegation but NOT for local.

### Step 3: Add tracing

Temporarily add prints to trace the flow:

```python
# In director.py
async def process(self, message, ...):
    print(f"[TRACE] Director.process called: {message[:50]}")
    
    # Before routing decision
    print(f"[TRACE] Assembling context...")
    context = await self.context_pipeline.assemble(message)
    print(f"[TRACE] Context: {len(context)} chars, used_retrieval: {context.used_retrieval}")
    
    if use_local:
        print(f"[TRACE] Using LOCAL path")
        response = await self.local_inference.generate(message, context=context)
    else:
        print(f"[TRACE] Using DELEGATION path")
        response = await self.delegate(message, context=context)
```

### Step 4: Test context pipeline directly

```python
# test_context_direct.py
import asyncio
from luna.context.pipeline import ContextPipeline

async def test():
    pipeline = ContextPipeline(...)  # init with required deps
    
    result = await pipeline.assemble("Who is Marzipan?")
    print(f"Used retrieval: {result.used_retrieval}")
    print(f"Memories: {result.memories}")
    print(f"Full context: {result.formatted[:500]}...")

asyncio.run(test())
```

If this works → problem is in Director not calling it
If this fails → problem is in ContextPipeline itself

---

## Likely Fix

Based on the symptom (`used_retrieval: false`), the most likely issue is:

**Option A: Context pipeline not called for local path**

```python
# BEFORE (broken) - in director.py
if use_local:
    # No context assembly!
    response = await self.local_inference.generate(message)

# AFTER (fixed)
if use_local:
    context = await self.context_pipeline.assemble(message)
    response = await self.local_inference.generate(message, context=context.formatted)
```

**Option B: Context assembled but not passed**

```python
# BEFORE (broken)
context = await self.context_pipeline.assemble(message)
response = await self.local_inference.generate(message)  # context not passed!

# AFTER (fixed)
context = await self.context_pipeline.assemble(message)
response = await self.local_inference.generate(message, context=context.formatted)
```

**Option C: LocalInference ignores context parameter**

```python
# BEFORE (broken) - in local.py
async def generate(self, prompt: str, context: str = None, ...):
    full_prompt = self.format_prompt(prompt)  # context ignored!

# AFTER (fixed)
async def generate(self, prompt: str, context: str = None, ...):
    full_prompt = self.format_prompt(prompt, context=context)
```

---

## Validation

After fix, run:
```bash
.venv/bin/python scripts/voight_kampff.py --layer 3
```

Expected:
- `used_retrieval: true`
- Prompt length > 1500 chars
- Memory fragments found: 4/5 or 5/5
- Captured prompt contains "Marzipan", "collaborator", etc.

Or from Luna Hub:
```
/vk
```

Then test manually:
```
hey luna, who is marzipan?
```

Expected: "Marzipan is a collaborator who helps with wellbeing and architecture..."
NOT: "Marzipan is a whimsical candy creature..."

---

## Success Criteria

- [ ] `used_retrieval: true` in Layer 3 results
- [ ] Prompt contains actual memory content (1500+ chars)
- [ ] Memory fragments present: Marzipan, Ahab, sovereignty, etc.
- [ ] Luna answers factual questions correctly
- [ ] Voight-Kampff Layer 3 passes

---

## Debugging Tips

**Check server logs during request:**
```bash
tail -f /tmp/luna_server.log | grep -E "CONTEXT|assemble|retrieval"
```

**Check Memory Matrix is accessible:**
```bash
curl http://localhost:8000/memory/stats
# Should show: nodes: 22000+, edges: 20000+
```

**Check a specific search works:**
```bash
curl "http://localhost:8000/memory/search?q=Marzipan&limit=5"
# Should return collaborator/wellbeing content
```

---

## Order of Operations

1. First verify ContextPipeline.assemble() works in isolation
2. Then trace where Director calls (or doesn't call) it
3. Then verify context is passed to LocalInference
4. Then verify LocalInference uses context in prompt
5. Run Voight-Kampff to validate

Each step narrows the failure point.
