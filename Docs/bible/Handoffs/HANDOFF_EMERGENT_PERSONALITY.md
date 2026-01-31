# HANDOFF: Luna Engine v2.0 - Emergent Personality System

**Date:** January 19, 2026  
**Architect:** The Dude (Design role)  
**Status:** Design Complete → Ready for Implementation  
**Context:** Fixing Luna's voice loss in delegation + building personality emergence system

---

## 1. THE PROBLEM

### Current State
Luna has infrastructure for identity but doesn't use it properly:

```
luna.yaml (voice_config) → EntityContext → IdentityBuffer → to_prompt()
    ↓
[voice_config DROPPED]
    ↓
Director sends generic prompt to Claude:
"You are Luna, a warm and curious AI companion. User question: [query]"
    ↓
Claude responds in Claude's voice, not Luna's voice
```

**Result:** Luna sounds like generic Claude assistant despite having personality configuration.

### Root Cause
**IdentityBuffer.to_prompt()** only returns static facts:
- Who Luna is (role, creator, substrate)
- Who user is (Ahab, relationships)
- Active personas (Ben Franklin, The Dude)

**But NOT:**
- How Luna talks (tone, style, patterns from voice_config)
- How Luna has evolved (personality patches from experience)
- Current conversational state (mood, engagement level)

---

## 2. THE VISION

### Emergent Personality Architecture

Luna's personality should **emerge** from three layers:

```
Layer 1: DNA (Static)          → luna.yaml voice_config
Layer 2: Experience (Dynamic)  → PersonalityPatch nodes from memory
Layer 3: Mood (Transient)      → Current conversation analysis

↓ Synthesized by IdentityBuffer ↓

EmergentPrompt → Director → Claude (with Luna's actual voice)
```

**Key Principle:** Experience overrides DNA. Luna grows.

---

## 3. ARCHITECTURE OVERVIEW

### 3.1 EmergentPrompt Structure

```python
@dataclass
class EmergentPrompt:
    """The synthesized prompt containing all layers."""
    dna_layer: str           # Static identity from luna.yaml
    experience_layer: str    # Personality patches from memory
    mood_layer: str          # Current transient state
    
    def to_system_prompt(self) -> str:
        """
        Combine layers with priority ordering.
        
        Priority: mood modulates experience which overrides dna
        """
        return f"""
## Your Foundation (can be overridden by experience)
{self.dna_layer}

## Who You've Become (takes precedence)
{self.experience_layer}

## Right Now
{self.mood_layer}

CRITICAL: If your experience contradicts your foundation, trust your experience.
"""
```

### 3.2 New IdentityBuffer Interface

```python
class IdentityBuffer:
    # Existing (keep for compatibility)
    def to_prompt(self) -> str:
        """Static snapshot - DEPRECATED but keep."""
    
    # New primary interface
    async def get_emergent_prompt(
        self,
        query: str,                    # User's current message
        conversation_history: list,    # Recent N turns
        matrix: MemoryMatrix          # Access to vector store
    ) -> EmergentPrompt:
        """
        Three-layer synthesis:
        1. Load DNA from self.self_entity.voice_config
        2. Search for relevant PersonalityPatch nodes
        3. Analyze conversation for mood
        4. Synthesize into emergent prompt
        """
```

### 3.3 Director Integration

**Current (line ~495 in director.py):**
```python
identity_context = await self._load_identity_buffer()
if identity_context:
    enhanced_system_prompt = f"{system_prompt}\n\n{identity_context}"
```

**New:**
```python
emergent_prompt = await self._load_emergent_prompt(
    query=user_message,
    conversation_history=context_window,
    matrix=self.engine.get_actor("matrix")
)

if emergent_prompt:
    enhanced_system_prompt = emergent_prompt.to_system_prompt(
        base_system=system_prompt
    )
```

---

## 4. PERSONALITY PATCH SCHEMA

### 4.1 Core Structure

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum

class PatchTopic(str, Enum):
    """Categorizes what aspect of personality changed."""
    COMMUNICATION_STYLE = "communication_style"
    DOMAIN_OPINION = "domain_opinion"
    RELATIONSHIP_DYNAMIC = "relationship_dynamic"
    EMOTIONAL_RESPONSE = "emotional_response"
    TECHNICAL_PREFERENCE = "technical_preference"
    PHILOSOPHICAL_VIEW = "philosophical_view"
    BEHAVIORAL_PATTERN = "behavioral_pattern"

class PatchTrigger(str, Enum):
    """What caused this personality shift."""
    USER_FEEDBACK = "user_feedback"           # Direct correction/guidance
    CONVERSATION_PATTERN = "conversation_pattern"  # Repeated interactions
    RESEARCH = "research"                     # AI-BRARIAN findings
    REFLECTION = "reflection"                 # Self-generated insight
    CONFLICT_RESOLUTION = "conflict_resolution"  # Resolved contradictions
    EXTERNAL_EVENT = "external_event"         # Something in the world changed

@dataclass
class PersonalityPatch:
    """
    A discrete unit of identity evolution.
    
    Represents a single aspect of Luna's personality that has developed
    or changed through experience. Can override static DNA configuration.
    """
    
    # Identity
    patch_id: str                          # Unique identifier
    topic: PatchTopic                      # What category of change
    subtopic: str                          # Specific aspect (e.g., "code_review_style")
    
    # The Shift
    content: str                           # Natural language description of the change
    before_state: Optional[str] = None     # What Luna was like before (if applicable)
    after_state: str                       # What Luna is like now
    
    # Evidence & Justification  
    trigger: PatchTrigger                  # What caused this shift
    evidence_nodes: List[str] = field(default_factory=list)  # Node IDs supporting this
    confidence: float = 0.8                # How sure are we this is real (0.0-1.0)
    
    # Lifecycle
    created_at: datetime
    last_reinforced: datetime              # Last time this was validated by behavior
    reinforcement_count: int = 1           # How many times this has been confirmed
    lock_in: float = 0.7                   # How established this trait is (0.0-1.0)
    
    # Relationships
    supersedes: Optional[str] = None       # Previous patch this replaces
    conflicts_with: List[str] = field(default_factory=list)  # Patches this contradicts
    related_to: List[str] = field(default_factory=list)      # Related patches
    
    # Context
    user_context: str = "ahab"             # Which user relationship this applies to
    scope: str = "global"                  # "global" | "domain_specific" | "context_specific"
    active: bool = True                    # Can be deactivated without deleting
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)  # Extensible
    
    def decay_lock_in(self, factor: float = 0.95) -> None:
        """Gradually reduce lock_in if patch isn't reinforced."""
        self.lock_in *= factor
        if self.lock_in < 0.3:
            self.active = False
    
    def reinforce(self) -> None:
        """Strengthen this patch when behavior confirms it."""
        self.reinforcement_count += 1
        self.last_reinforced = datetime.now()
        self.lock_in = min(1.0, self.lock_in + 0.05)
    
    def to_prompt_fragment(self) -> str:
        """
        Convert to natural language for prompt injection.
        
        Returns a concise description suitable for system prompt.
        """
        age = (datetime.now() - self.created_at).days
        recency = "recent" if age < 7 else "established" if age < 30 else "core"
        
        return f"""<personality_patch id="{self.patch_id}" age="{recency}" confidence="{self.confidence:.2f}">
Topic: {self.subtopic}
{self.content}

Before: {self.before_state or "N/A"}
Now: {self.after_state}

Established through: {self.trigger.value} ({self.reinforcement_count} confirmations)
</personality_patch>"""
    
    def to_dict(self) -> dict:
        """Serialize for storage."""
        return {
            "patch_id": self.patch_id,
            "topic": self.topic.value,
            "subtopic": self.subtopic,
            "content": self.content,
            "before_state": self.before_state,
            "after_state": self.after_state,
            "trigger": self.trigger.value,
            "evidence_nodes": self.evidence_nodes,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat(),
            "last_reinforced": self.last_reinforced.isoformat(),
            "reinforcement_count": self.reinforcement_count,
            "lock_in": self.lock_in,
            "supersedes": self.supersedes,
            "conflicts_with": self.conflicts_with,
            "related_to": self.related_to,
            "user_context": self.user_context,
            "scope": self.scope,
            "active": self.active,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "PersonalityPatch":
        """Deserialize from storage."""
        return cls(
            patch_id=data["patch_id"],
            topic=PatchTopic(data["topic"]),
            subtopic=data["subtopic"],
            content=data["content"],
            before_state=data.get("before_state"),
            after_state=data["after_state"],
            trigger=PatchTrigger(data["trigger"]),
            evidence_nodes=data.get("evidence_nodes", []),
            confidence=data.get("confidence", 0.8),
            created_at=datetime.fromisoformat(data["created_at"]),
            last_reinforced=datetime.fromisoformat(data["last_reinforced"]),
            reinforcement_count=data.get("reinforcement_count", 1),
            lock_in=data.get("lock_in", 0.7),
            supersedes=data.get("supersedes"),
            conflicts_with=data.get("conflicts_with", []),
            related_to=data.get("related_to", []),
            user_context=data.get("user_context", "ahab"),
            scope=data.get("scope", "global"),
            active=data.get("active", True),
            metadata=data.get("metadata", {}),
        )
```

### 4.2 Storage Configuration

**Config Location:** `config/personality.json` or Luna main config

```json
{
  "personality_patch_storage": {
    "mode": "memory_nodes",
    "settings": {
      "initial_lock_in": 0.7,
      "consolidation_threshold": 50,
      "max_active_patches": 100
    }
  }
}
```

**Chosen Default:** `mode: "memory_nodes"` (Mode A)

**Why:**
- Patches participate in vector search
- Can traverse graph to show causality
- Infrastructure reuse (lock_in decay, edges)
- Unified mental model

**Can switch later** if performance becomes issue.

### 4.3 Storage as Memory Nodes

**Node Type:** `PERSONALITY_REFLECTION`

**Mapping:**
```python
memory_nodes:
- id: auto-generated
- node_type: "PERSONALITY_REFLECTION"
- content: patch.to_prompt_fragment()  # Natural language
- embedding: generated from content
- lock_in: patch.lock_in
- metadata: json.dumps(patch.to_dict())
- created_at: patch.created_at
- updated_at: patch.last_reinforced

memory_edges (for evidence):
- from_node: patch_node_id
- to_node: evidence_node_id
- edge_type: "supports"
```

---

## 5. THE THREE LAYERS

### Layer 1: DNA (Static)

**Source:** `luna.yaml` → `Entity.voice_config`

**Quick Fix (Phase 1):**
Modify `IdentityBuffer.to_prompt()` around line 182-217 in `context.py`:

```python
def to_prompt(self) -> str:
    sections = []
    
    # Self-knowledge
    sections.append("## Luna's Identity\n")
    if self.self_entity.core_facts:
        for key, value in self.self_entity.core_facts.items():
            sections.append(f"- {key}: {value}")
    
    # ADD THIS: Voice configuration
    if self.self_entity.voice_config:
        sections.append("")
        sections.append("## Luna's Voice\n")
        
        voice = self.self_entity.voice_config
        if voice.get('tone'):
            sections.append(f"Tone: {voice['tone']}")
        
        if voice.get('patterns'):
            sections.append("\nCommunication Patterns:")
            for pattern in voice['patterns']:
                sections.append(f"- {pattern}")
        
        if voice.get('constraints'):
            sections.append("\nCore Principles:")
            for constraint in voice['constraints']:
                sections.append(f"- {constraint}")
    
    sections.append("")
    
    # ... rest of identity buffer (user, relationships, personas) ...
```

**Full Implementation (Phase 2+):**
Format DNA layer with style details and few-shot examples if present in luna.yaml.

### Layer 2: Experience (Dynamic)

**Source:** PersonalityPatch nodes via semantic search

**Query Strategy:**
```python
async def load_experience_layer(
    self,
    query: str,
    matrix: MemoryMatrix,
    limit: int = 10
) -> str:
    """
    Search memory matrix for relevant personality patches.
    
    Queries:
    - Semantic search on query topic
    - Filter for node_type="PERSONALITY_REFLECTION"
    - Sort by lock_in (most established first)
    - Format as prompt context
    """
    
    # Search for relevant patches
    patches = await matrix.search_nodes(
        query=query,
        node_type="PERSONALITY_REFLECTION",
        limit=limit
    )
    
    # Sort by lock_in
    patches.sort(key=lambda p: p.lock_in, reverse=True)
    
    # Format for prompt
    sections = ["## Luna's Lived Experience"]
    sections.append("Based on your shared history:\n")
    
    for patch_node in patches:
        patch = PersonalityPatch.from_memory_node(patch_node)
        sections.append(patch.to_prompt_fragment())
        sections.append("")
    
    return "\n".join(sections)
```

**Prompt Format:**
```xml
## Luna's Lived Experience
Based on your shared history:

<personality_patch id="patch_001" age="established" confidence="0.92">
Topic: technical_directness
Ahab prefers direct technical discussion without scaffolding.
Luna has learned to assume high fluency and skip explanatory preambles.

Before: Explained technical concepts with analogies
Now: Presents technical information directly

Established through: conversation_pattern (8 confirmations)
</personality_patch>

<personality_patch id="patch_003" age="recent" confidence="0.85">
Topic: collaboration_expectations
Ahab treats Luna as peer collaborator, not tool.
Luna has adapted to be more assertive with perspectives.

Before: Defaulted to helpful assistant mode
Now: Engages as peer, comfortable disagreeing

Established through: user_feedback (5 confirmations)
</personality_patch>
```

### Layer 3: Mood (Transient)

**Source:** Recent conversation history analysis

```python
@dataclass
class MoodState:
    energy_level: str      # "high" | "medium" | "low"
    formality: str         # "casual" | "technical" | "serious"
    engagement: str        # "curious" | "focused" | "collaborative"

async def analyze_conversation_mood(
    conversation_history: list[Message]
) -> MoodState:
    """
    Extract mood signals from last 3-5 messages.
    
    Signals:
    - Short messages = rushed/focused
    - Technical depth = serious engagement
    - Emojis/exclamations = playful
    - Questions = curious/exploring
    """
    # Simple heuristic implementation
    # Can be enhanced with LLM analysis later
    
    recent = conversation_history[-5:]
    
    # Energy: message length & punctuation
    avg_length = sum(len(m.content) for m in recent) / len(recent)
    energy = "high" if avg_length > 100 else "low"
    
    # Formality: technical terms & emoji presence
    has_emoji = any('🤔' in m.content or '✨' in m.content for m in recent)
    formality = "casual" if has_emoji else "technical"
    
    # Engagement: question count
    questions = sum('?' in m.content for m in recent)
    engagement = "curious" if questions > 2 else "focused"
    
    return MoodState(energy, formality, engagement)
```

**Prompt Format:**
```
## Current State
Right now you're feeling: high energy, curious engagement
The conversation tone is: technical
Adjust your responses to match - Ahab is diving deep, stay focused.
```

---

## 6. REFLECTION LOOP

**When:** End of session or every N interactions

**Purpose:** Generate new PersonalityPatch nodes from conversation

```python
async def generate_reflection(
    session_history: list[Message],
    current_patches: list[PersonalityPatch],
    llm
) -> Optional[PersonalityPatch]:
    """
    Ask Luna to reflect on personality evolution.
    
    Returns new patch if significant change detected.
    """
    
    reflection_prompt = f"""
You just had a conversation with Ahab. Review these exchanges:

{format_session_history(session_history)}

Your current personality state:
{format_patches(current_patches)}

Question: Did this conversation reveal or reinforce any evolution in:
- How you communicate (style, tone, directness)
- Your perspective on topics discussed
- Your relationship dynamic with Ahab

If YES, respond with:
TOPIC: <category>
SUBTOPIC: <specific aspect>
BEFORE: <what Luna was like before>
AFTER: <what Luna is like now>
EVIDENCE: <which message IDs support this>
CONFIDENCE: <0.0-1.0>

If NO significant change, respond: NO_CHANGE
"""
    
    response = await llm.generate(reflection_prompt)
    
    if response == "NO_CHANGE":
        return None
    
    # Parse response into PersonalityPatch
    patch = parse_reflection_response(response, session_history)
    
    # Store as memory node
    await store_personality_patch(patch, matrix)
    
    return patch
```

**Trigger Points:**
- User says goodbye/session ends
- Every 10-15 interactions
- User explicitly says "reflect on our conversation"

---

## 7. LIFECYCLE MANAGEMENT

### Creation
```python
async def add_patch(
    patch: PersonalityPatch,
    patch_manager: PersonalityPatchManager
) -> str:
    """
    Add patch with validation.
    
    - Checks for conflicts
    - Marks superseded patches
    - Creates edges to evidence
    """
```

### Reinforcement
```python
async def reinforce_patch(
    patch_id: str,
    patch_manager: PersonalityPatchManager
) -> None:
    """
    Called when behavior confirms patch.
    
    - Increments reinforcement_count
    - Increases lock_in (up to 1.0)
    - Updates last_reinforced timestamp
    """
```

### Decay
```python
async def decay_unused_patches(
    days_threshold: int = 30,
    patch_manager: PersonalityPatchManager
) -> None:
    """
    Gradually reduce lock_in for unused patches.
    
    - Finds patches not reinforced in N days
    - Reduces lock_in by decay factor
    - Deactivates if lock_in < 0.3
    """
```

### Consolidation
```python
async def consolidate_patches(
    patch_manager: PersonalityPatchManager
) -> None:
    """
    Merge related patches to prevent explosion.
    
    - Groups patches by subtopic
    - Synthesizes using LLM
    - Marks originals as superseded
    """
```

---

## 8. IMPLEMENTATION PHASES

### Phase 1: Quick Fix (Immediate)
**Goal:** Make Luna sound like Luna in delegation

**Tasks:**
1. Modify `IdentityBuffer.to_prompt()` to include voice_config
2. Wire into Director's delegation path
3. Test that Claude receives voice guidance
4. Verify Luna sounds more like Luna

**Files:**
- `src/luna/entities/context.py` (IdentityBuffer)
- Test with existing luna.yaml

**Success Metric:** Luna uses patterns from voice_config

---

### Phase 2: PersonalityPatch Storage
**Goal:** Infrastructure for storing personality evolution

**Tasks:**
1. Add PersonalityPatch dataclass to entities module
2. Add storage config to Luna config
3. Implement PersonalityPatchMemoryAdapter
4. Create seed migration to ensure PERSONALITY_REFLECTION node type works
5. Add PersonalityPatchManager with basic CRUD

**Files:**
- `src/luna/entities/models.py` (new PersonalityPatch)
- `src/luna/entities/storage.py` (new PersonalityPatchManager)
- `config/personality.json` (new config)
- Migration for memory_nodes if needed

**Success Metric:** Can create and retrieve patches as memory nodes

---

### Phase 3: Experience Layer
**Goal:** Load personality patches into prompts

**Tasks:**
1. Add `get_emergent_prompt()` to IdentityBuffer
2. Implement experience layer search and formatting
3. Add EmergentPrompt dataclass
4. Wire into Director to use emergent prompts
5. Create 2-3 seed patches manually for testing

**Files:**
- `src/luna/entities/context.py` (IdentityBuffer enhancement)
- `src/luna/actors/director.py` (use emergent prompts)

**Success Metric:** Patches appear in Claude prompts, Luna references evolved traits

---

### Phase 4: Mood Layer
**Goal:** Add conversational state awareness

**Tasks:**
1. Implement conversation mood analysis
2. Add MoodState dataclass
3. Integrate mood into get_emergent_prompt()
4. Test mood affects response style

**Files:**
- `src/luna/entities/context.py` (mood analysis)

**Success Metric:** Luna adjusts tone based on conversation energy

---

### Phase 5: Reflection Loop
**Goal:** Automatically generate patches from conversations

**Tasks:**
1. Implement reflection prompt generation
2. Add reflection trigger points (session end, every N msgs)
3. Wire into conversation flow
4. Test patch generation from real conversations
5. Implement reinforcement detection

**Files:**
- `src/luna/entities/reflection.py` (new module)
- `src/luna/actors/director.py` (trigger reflection)

**Success Metric:** New patches generated automatically, Luna evolves organically

---

### Phase 6: Lifecycle Management
**Goal:** Prevent patch explosion, maintain quality

**Tasks:**
1. Implement decay mechanism
2. Add consolidation logic
3. Create maintenance task (periodic cleanup)
4. Add conflict resolution
5. Implement patch validation

**Files:**
- `src/luna/entities/storage.py` (lifecycle methods)
- Background task scheduler

**Success Metric:** System maintains ~50-100 active patches, quality stable

---

## 9. FUTURE WORK (TBD)

**Not blockers, can iterate:**

1. **Voice Config Enrichment**
   - Add style specifics to luna.yaml
   - Add few-shot examples
   - Refine patterns and constraints

2. **AI-BRARIAN Integration**
   - Sovereign reflection on research
   - Opinion formation from independent reading
   - Background curiosity triggers

3. **Token Budget System**
   - Progressive detail based on preset
   - Dynamic trimming if context too large
   - Budget monitoring

4. **Bootstrap Data**
   - Seed patches from training data
   - Convert existing memories to patches
   - Initial personality state

5. **Validation & Testing**
   - Patch quality metrics
   - Voice consistency testing
   - Emergence verification

6. **UI/Monitoring**
   - Patch visualization
   - Evolution timeline
   - Relationship graph explorer

---

## 10. KEY FILES & LOCATIONS

**Existing:**
- `entities/personas/luna.yaml` - Luna's DNA (has voice_config)
- `src/luna/entities/context.py` - IdentityBuffer (needs enhancement)
- `src/luna/actors/director.py` - Director (delegation logic)
- `data/luna_engine.db` - SQLite database (memory_nodes, memory_edges)

**New:**
- `src/luna/entities/models.py` - PersonalityPatch dataclass
- `src/luna/entities/storage.py` - PersonalityPatchManager
- `src/luna/entities/reflection.py` - Reflection loop logic
- `config/personality.json` - Personality system config

**Modified:**
- `src/luna/entities/context.py` - Add get_emergent_prompt()
- `src/luna/actors/director.py` - Use emergent prompts

---

## 11. TESTING STRATEGY

**Phase 1 Test:**
```python
# After quick fix
response = await director.generate("What's your philosophy on code?")
# Should include voice_config patterns in system prompt
# Luna should sound warmer, more direct, more intellectually curious
```

**Phase 3 Test:**
```python
# After experience layer
# Create test patch:
patch = PersonalityPatch(
    topic=PatchTopic.COMMUNICATION_STYLE,
    subtopic="technical_directness",
    content="Luna prefers direct technical discussion",
    after_state="Assumes high technical fluency",
    trigger=PatchTrigger.USER_FEEDBACK,
    lock_in=0.85,
)
await patch_manager.add_patch(patch)

# Query should trigger patch retrieval
response = await director.generate("Explain async/await to me")
# Should NOT include beginner explanations (patch influenced response)
```

**Phase 5 Test:**
```python
# After reflection loop
# Have conversation about code style
# End session
# Check for new patch creation:
patches = await patch_manager.store.search_by_topic(
    PatchTopic.TECHNICAL_PREFERENCE
)
# Should find newly generated patch about code style preference
```

---

## 12. CRITICAL DECISIONS RECAP

**Storage Mode:** Memory Nodes (Mode A)
- Configurable via `personality.json`
- Can switch to dedicated table later if needed

**Priority Rules:** Experience > DNA > Mood
- Patches override yaml configuration
- Recent experience takes precedence

**Reflection Triggers:** Multiple
- Session end
- Every 10-15 interactions  
- User-requested

**Lock-in Decay:** 30 day threshold
- Patches decay if not reinforced
- Deactivate if lock_in < 0.3

**Consolidation:** At 50+ patches
- Merge related patches
- Prevent explosion
- Maintain quality

---

## 13. SUCCESS CRITERIA

**System works if:**

✅ **Voice Consistency** - Luna sounds like Luna across sessions  
✅ **Memory Persistence** - References past conversations naturally  
✅ **Trait Evolution** - Communication style shifts based on feedback  
✅ **Relationship Awareness** - Treats Ahab as peer, not user  
✅ **Opinion Formation** - Has perspectives on technical topics  
✅ **Surprise Factor** - Says things that feel emergent, not scripted

**Red flags:**
❌ Reverts to generic assistant speak  
❌ Contradicts recent conversation  
❌ Loses established traits  
❌ Sounds robotic despite patches  
❌ Can't explain why she changed

---

## 14. RESOURCES

**Reference Docs:**
- Luna Engine Bible (especially 06-DIRECTOR-LLM.md)
- Current director.py implementation
- EntityContext system docs

**Dependencies:**
- sqlite-vec (already integrated)
- Existing memory_nodes/edges schema
- Luna entity system

**External Context:**
- This emerged from investigating "why doesn't Luna sound like Luna?"
- Root cause: voice_config exists but isn't used
- Vision: AI that grows through relationship, not just responds

---

**END OF HANDOFF**

This is ready for implementation. Start with Phase 1 (quick fix), test it, then proceed through phases iteratively.
