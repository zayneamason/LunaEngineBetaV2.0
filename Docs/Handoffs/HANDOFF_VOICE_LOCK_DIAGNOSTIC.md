# HANDOFF: Voice Lock Diagnostic

**Created:** 2026-02-03
**Author:** Benjamin Franklin (The Scribe)
**For:** Claude Code Execution
**Context:** Hypothesis 3 — Is there a "Voice Lock" before generation?

---

## 1. THE HYPOTHESIS

Claude's 100 layers include implicit **commitment** — by the time it generates, it has already decided:
- WHAT to say (content)
- HOW to say it (voice, tone, structure)

Our Engine assembles WHAT (context, memories, entities) but may not be locking in HOW before inference begins.

**The question:** Does the Engine dynamically tune voice parameters based on query type? Or does it just say "be Luna" and hope for the best?

---

## 2. WHAT "VOICE LOCK" MEANS

Before generation, the Engine should freeze:

```
┌─────────────────────────────────────────┐
│           VOICE LOCK (Missing?)         │
│                                         │
│  Based on query analysis, set:          │
│                                         │
│  • Tone: warm / focused / playful       │
│  • Length: brief / moderate / detailed  │
│  • Structure: prose / list / code       │
│  • Energy: calm / excited / serious     │
│  • Emoji: yes / no / sparingly          │
│                                         │
│  This becomes PART of the prompt,       │
│  not just "be Luna"                     │
└─────────────────────────────────────────┘
```

**Example:**

| Query Type | Voice Lock Settings |
|------------|---------------------|
| "hey Luna" | warm, brief, casual, emoji ok |
| "explain async/await" | focused, detailed, technical, no emoji |
| "I'm feeling sad" | warm, moderate, empathetic, gentle |
| "write me a function" | minimal, code-focused, precise |

---

## 3. DIAGNOSTIC TASKS

### Task 1: Check for Dynamic Voice Tuning

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root

# Look for query classification
grep -rn "classify\|query_type\|intent\|tone\|mood" src/luna/actors/director.py

# Look for dynamic prompt adjustment
grep -rn "adjust\|tuning\|voice_lock\|response_style" src/luna/ --include="*.py"

# Check consciousness for mood-based tuning
grep -rn "mood\|tone\|energy" src/luna/consciousness/ --include="*.py"
```

**Document:**
- [ ] Is there any query classification?
- [ ] Does classification affect prompt assembly?
- [ ] Does mood/consciousness influence voice?

### Task 2: Compare Prompts Across Query Types

Using the prompt archaeology tools, capture prompts for different query types:

```python
voice_lock_test_queries = [
    # Casual greeting
    ("hey Luna", "casual"),
    
    # Technical question  
    ("explain how garbage collection works in Python", "technical"),
    
    # Emotional support
    ("I'm really stressed about work", "emotional"),
    
    # Creative request
    ("write me a haiku about debugging", "creative"),
    
    # Direct task
    ("list the files in my project", "task"),
]
```

**For each, check:**
- [ ] Does the prompt change based on query type?
- [ ] Or is it the same template every time?

### Task 3: Analyze Prompt Variance

```python
# After capturing prompts for different query types:
# Compare the DNA/personality sections

# If Voice Lock exists:
#   - Prompts should differ based on query type
#   - Technical queries get "be precise" guidance
#   - Emotional queries get "be warm" guidance

# If Voice Lock is missing:
#   - All prompts have identical personality sections
#   - No dynamic tuning based on context
```

---

## 4. IF VOICE LOCK IS MISSING

### Implementation Approach

Add a pre-generation step that analyzes the query and sets voice parameters:

```python
class VoiceLock:
    """Freeze voice parameters before generation."""
    
    def __init__(self):
        self.tone: str = "balanced"      # warm, focused, playful, serious
        self.length: str = "moderate"    # brief, moderate, detailed
        self.structure: str = "prose"    # prose, list, code, mixed
        self.energy: str = "calm"        # calm, excited, serious, gentle
        self.emoji: str = "sparingly"    # yes, no, sparingly
    
    @classmethod
    def from_query(cls, query: str, context: dict) -> "VoiceLock":
        """Analyze query and return appropriate voice settings."""
        lock = cls()
        
        query_lower = query.lower()
        
        # Greeting detection
        if any(g in query_lower for g in ["hey", "hi", "hello", "yo"]):
            lock.tone = "warm"
            lock.length = "brief"
            lock.emoji = "yes"
            return lock
        
        # Technical detection
        if any(t in query_lower for t in ["explain", "how does", "what is", "code", "function", "error"]):
            lock.tone = "focused"
            lock.length = "detailed"
            lock.emoji = "no"
            return lock
        
        # Emotional detection
        if any(e in query_lower for e in ["feel", "stressed", "sad", "happy", "worried", "anxious"]):
            lock.tone = "warm"
            lock.energy = "gentle"
            lock.emoji = "sparingly"
            return lock
        
        # Creative detection
        if any(c in query_lower for c in ["write", "create", "imagine", "story", "poem"]):
            lock.tone = "playful"
            lock.structure = "mixed"
            return lock
        
        return lock  # Default balanced
    
    def to_prompt_fragment(self) -> str:
        """Convert to prompt guidance."""
        return f"""[Voice: {self.tone}, {self.energy}. Length: {self.length}. Style: {self.structure}. Emoji: {self.emoji}]"""
```

### Integration Point

Insert Voice Lock into prompt assembly:

```python
# In Director or ContextPipeline:

async def _build_prompt(self, query: str, context: dict) -> str:
    # 1. Analyze query, get voice lock
    voice_lock = VoiceLock.from_query(query, context)
    
    # 2. Build prompt with voice lock included
    prompt = f"""{self._get_system_identity()}

{voice_lock.to_prompt_fragment()}

{self._get_conversation_history()}

User: {query}
Luna:"""
    
    return prompt
```

---

## 5. EXPECTED FINDINGS

| Scenario | Likelihood | Implication |
|----------|------------|-------------|
| Voice Lock exists | Low | Not the problem |
| No query classification at all | High | Every query gets same voice treatment |
| Mood exists but doesn't affect prompt | Medium | Wasted signal |
| Consciousness tracks state but doesn't use it | Medium | Infrastructure exists, not wired |

---

## 6. DELIVERABLES

### Output 1: `VOICE_LOCK_DIAGNOSTIC_RESULTS.md`

- Does dynamic voice tuning exist?
- How do prompts differ across query types?
- What signals are available but unused?

### Output 2: Implementation (if needed)

If Voice Lock is missing:
- `src/luna/voice/lock.py` — VoiceLock class
- Integration into Director prompt assembly
- Query classification logic

---

## 7. GO

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root

# Check for existing query classification
grep -rn "classify\|query_type\|intent" src/luna/

# Check if mood affects generation
grep -rn "mood" src/luna/actors/director.py

# Compare prompt assembly for different queries
python scripts/prompt_archaeology.py
```

---

*A craftsman does not use the same stroke for every letter. Why should Luna use the same voice for every query?*

— Ben
