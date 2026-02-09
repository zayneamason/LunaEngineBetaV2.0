# HANDOFF: Implement Voice Lock

**Created:** 2026-02-03
**Updated:** 2026-02-03 (converted from diagnostic to implementation)
**Author:** Benjamin Franklin (The Scribe)
**For:** Claude Code Execution
**Complexity:** S (2-4 hours)

---

## 1. CONTEXT

**What exists:** Mood Layer — analyzes conversation *history* to set energy/formality/engagement

**What's missing:** Voice Lock — analyzes the current *query* to tune voice parameters

**The difference:**

| Aspect | Mood Layer (exists) | Voice Lock (new) |
|--------|---------------------|------------------|
| Input | Last 5 messages | Current query |
| Purpose | Conversational momentum | Query-specific tuning |
| Example | "We've been casual" | "This question needs technical tone" |

They complement each other. Mood Layer says "where we've been", Voice Lock says "where this query needs to go."

---

## 2. IMPLEMENTATION SPEC

### 2.1 Create VoiceLock Class

**File:** `src/luna/voice/lock.py` (new file)

```python
"""
Voice Lock — Query-based voice parameter tuning.

Analyzes the current query to determine appropriate voice settings
before generation begins. Complements the Mood Layer which analyzes
conversation history.
"""

from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class VoiceLock:
    """
    Frozen voice parameters for a single generation.
    
    Set based on query analysis, injected into prompt before generation.
    """
    
    tone: str = "balanced"       # warm | focused | playful | serious | balanced
    length: str = "moderate"     # brief | moderate | detailed
    structure: str = "prose"     # prose | list | code | mixed
    energy: str = "calm"         # calm | gentle | engaged | energetic
    emoji: str = "sparingly"     # yes | no | sparingly
    
    def to_prompt_fragment(self) -> str:
        """Format for injection into prompt."""
        return (
            f"[For this response: {self.tone} tone, {self.energy} energy, "
            f"{self.length} length, {self.structure} structure, emoji: {self.emoji}]"
        )
    
    @classmethod
    def from_query(cls, query: str, context: Optional[dict] = None) -> "VoiceLock":
        """
        Analyze query and return appropriate voice settings.
        
        Args:
            query: The user's current message
            context: Optional context dict (for future enhancement)
        
        Returns:
            VoiceLock with settings tuned to query type
        """
        lock = cls()
        query_lower = query.lower().strip()
        
        # === GREETING DETECTION ===
        greeting_markers = ["hey", "hi ", "hello", "yo ", "sup", "what's up", "howdy"]
        if any(query_lower.startswith(g) or query_lower == g.strip() for g in greeting_markers):
            lock.tone = "warm"
            lock.length = "brief"
            lock.energy = "engaged"
            lock.emoji = "yes"
            logger.debug(f"VoiceLock: greeting detected → warm/brief")
            return lock
        
        # === TECHNICAL/EXPLANATION DETECTION ===
        technical_markers = [
            "explain", "how does", "how do", "what is", "what's the difference",
            "why does", "can you describe", "walk me through",
            "code", "function", "error", "bug", "debug", "implement",
            "api", "database", "async", "await", "class", "method"
        ]
        if any(t in query_lower for t in technical_markers):
            lock.tone = "focused"
            lock.length = "detailed"
            lock.structure = "mixed"  # prose with code if needed
            lock.emoji = "no"
            logger.debug(f"VoiceLock: technical detected → focused/detailed")
            return lock
        
        # === EMOTIONAL SUPPORT DETECTION ===
        emotional_markers = [
            "feel", "feeling", "stressed", "sad", "anxious", "worried",
            "overwhelmed", "frustrated", "happy", "excited", "scared",
            "lonely", "tired", "exhausted", "burned out", "burnout"
        ]
        if any(e in query_lower for e in emotional_markers):
            lock.tone = "warm"
            lock.energy = "gentle"
            lock.length = "moderate"
            lock.emoji = "sparingly"
            logger.debug(f"VoiceLock: emotional detected → warm/gentle")
            return lock
        
        # === CREATIVE REQUEST DETECTION ===
        creative_markers = [
            "write", "create", "imagine", "story", "poem", "haiku",
            "brainstorm", "ideas for", "come up with", "make up"
        ]
        if any(c in query_lower for c in creative_markers):
            lock.tone = "playful"
            lock.energy = "energetic"
            lock.structure = "mixed"
            lock.emoji = "sparingly"
            logger.debug(f"VoiceLock: creative detected → playful/energetic")
            return lock
        
        # === TASK/COMMAND DETECTION ===
        task_markers = [
            "list", "show me", "find", "search", "get", "fetch",
            "run", "execute", "do", "make", "set", "update", "delete"
        ]
        if any(t in query_lower for t in task_markers):
            lock.tone = "focused"
            lock.length = "brief"
            lock.structure = "list" if "list" in query_lower else "prose"
            lock.emoji = "no"
            logger.debug(f"VoiceLock: task detected → focused/brief")
            return lock
        
        # === QUESTION DETECTION (general) ===
        if query_lower.endswith("?") or query_lower.startswith(("what", "who", "where", "when", "why", "how", "is ", "are ", "can ", "do ", "does ")):
            lock.tone = "balanced"
            lock.length = "moderate"
            lock.energy = "engaged"
            logger.debug(f"VoiceLock: question detected → balanced/engaged")
            return lock
        
        # === DEFAULT ===
        logger.debug(f"VoiceLock: no pattern matched → default balanced")
        return lock


def classify_query_type(query: str) -> str:
    """
    Simple query type classification for logging/debugging.
    
    Returns: greeting | technical | emotional | creative | task | question | general
    """
    lock = VoiceLock.from_query(query)
    
    if lock.tone == "warm" and lock.length == "brief":
        return "greeting"
    elif lock.tone == "focused" and lock.length == "detailed":
        return "technical"
    elif lock.tone == "warm" and lock.energy == "gentle":
        return "emotional"
    elif lock.tone == "playful":
        return "creative"
    elif lock.tone == "focused" and lock.length == "brief":
        return "task"
    elif lock.energy == "engaged":
        return "question"
    else:
        return "general"
```

### 2.2 Integration into Context Pipeline

**File:** `src/luna/entities/context.py`

Add Voice Lock alongside Mood Layer:

```python
# At top of file, add import:
from luna.voice.lock import VoiceLock

# In build_emergent_prompt() or equivalent, after mood_layer:

async def build_emergent_prompt(
    self,
    query: str,
    conversation_history: list,
    patch_manager=None,
    limit: int = 5
) -> EmergentPrompt:
    """Build the three-layer personality prompt."""
    
    # Layer 1: DNA (Static from config)
    dna_layer = self._build_dna_layer()
    
    # Layer 2: Experience (Personality patches from memory)
    experience_layer = ""
    if patch_manager:
        experience_layer = await self._build_experience_layer(
            query, patch_manager, limit
        )
    
    # Layer 3: Mood (Transient from conversation history)
    mood_layer = self._build_mood_layer(conversation_history)
    
    # Layer 4: Voice Lock (NEW - from current query)
    voice_lock = VoiceLock.from_query(query)
    voice_lock_layer = voice_lock.to_prompt_fragment()
    
    return EmergentPrompt(
        dna_layer=dna_layer,
        experience_layer=experience_layer,
        mood_layer=mood_layer,
        voice_lock_layer=voice_lock_layer,  # NEW
    )
```

### 2.3 Update EmergentPrompt Model

**File:** `src/luna/entities/models.py`

Add voice_lock_layer to the dataclass:

```python
@dataclass
class EmergentPrompt:
    """
    The synthesized prompt containing all personality layers.
    
    Four-layer personality model:
    - dna_layer: Static identity from luna.yaml voice_config
    - experience_layer: PersonalityPatch nodes from memory
    - mood_layer: Transient state from conversation analysis
    - voice_lock_layer: Query-specific voice tuning (NEW)
    """
    
    dna_layer: str
    experience_layer: str
    mood_layer: str
    voice_lock_layer: str = ""  # NEW - defaults to empty
    
    def to_system_prompt(self, base_system: str = "") -> str:
        """Combine all layers into a complete system prompt."""
        sections = []
        
        if base_system:
            sections.append(base_system)
            sections.append("")
        
        sections.append("# Your Foundation")
        sections.append(self.dna_layer)
        sections.append("")
        
        if self.experience_layer:
            sections.append("## Who You've Become (takes precedence)")
            sections.append(self.experience_layer)
            sections.append("")
        
        if self.mood_layer:
            sections.append("## Conversation Context")
            sections.append(self.mood_layer)
            sections.append("")
        
        # NEW: Voice Lock comes last (most immediate guidance)
        if self.voice_lock_layer:
            sections.append("## For This Response")
            sections.append(self.voice_lock_layer)
            sections.append("")
        
        sections.append("CRITICAL: If your experience contradicts your foundation, trust your experience.")
        
        return "\n".join(sections)
```

---

## 3. FILE CHANGES SUMMARY

| File | Action |
|------|--------|
| `src/luna/voice/__init__.py` | Create (new package) |
| `src/luna/voice/lock.py` | Create (VoiceLock class) |
| `src/luna/entities/context.py` | Modify (add voice_lock call) |
| `src/luna/entities/models.py` | Modify (add voice_lock_layer field) |

---

## 4. TESTING

### Unit Test: `tests/test_voice_lock.py`

```python
"""Test Voice Lock classification."""

import pytest
from luna.voice.lock import VoiceLock, classify_query_type


class TestVoiceLock:
    """Test VoiceLock query analysis."""
    
    def test_greeting_detection(self):
        lock = VoiceLock.from_query("hey Luna")
        assert lock.tone == "warm"
        assert lock.length == "brief"
        assert lock.emoji == "yes"
    
    def test_technical_detection(self):
        lock = VoiceLock.from_query("explain how async/await works")
        assert lock.tone == "focused"
        assert lock.length == "detailed"
        assert lock.emoji == "no"
    
    def test_emotional_detection(self):
        lock = VoiceLock.from_query("I'm feeling really stressed today")
        assert lock.tone == "warm"
        assert lock.energy == "gentle"
    
    def test_creative_detection(self):
        lock = VoiceLock.from_query("write me a poem about debugging")
        assert lock.tone == "playful"
        assert lock.energy == "energetic"
    
    def test_task_detection(self):
        lock = VoiceLock.from_query("list all the files in my project")
        assert lock.tone == "focused"
        assert lock.length == "brief"
    
    def test_default_balanced(self):
        lock = VoiceLock.from_query("tell me about yourself")
        assert lock.tone == "balanced"
    
    def test_to_prompt_fragment(self):
        lock = VoiceLock(tone="warm", energy="gentle", length="moderate")
        fragment = lock.to_prompt_fragment()
        assert "warm" in fragment
        assert "gentle" in fragment


class TestClassifyQueryType:
    """Test query type classification helper."""
    
    def test_greeting(self):
        assert classify_query_type("hey Luna") == "greeting"
    
    def test_technical(self):
        assert classify_query_type("how does garbage collection work") == "technical"
    
    def test_emotional(self):
        assert classify_query_type("I feel overwhelmed") == "emotional"
```

---

## 5. EXECUTION SEQUENCE

```
1. Create src/luna/voice/ directory
2. Create src/luna/voice/__init__.py
3. Create src/luna/voice/lock.py with VoiceLock class
4. Update src/luna/entities/models.py (add voice_lock_layer)
5. Update src/luna/entities/context.py (call VoiceLock.from_query)
6. Create tests/test_voice_lock.py
7. Run tests: uv run pytest tests/test_voice_lock.py -v
8. Run full suite: uv run pytest --tb=short
```

---

## 6. VERIFICATION

After implementation:

```bash
# Run the new tests
uv run pytest tests/test_voice_lock.py -v

# Check prompt archaeology (when API available)
python scripts/prompt_archaeology.py

# Verify voice_lock_layer appears in captured prompts
```

---

## 7. GO

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root

# Create the voice package
mkdir -p src/luna/voice
touch src/luna/voice/__init__.py

# Then implement lock.py and update the other files
```

---

*The Mood Layer tells Luna where she's been. The Voice Lock tells her where this moment needs to go.*

— Ben
