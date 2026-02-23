# ARCHITECTURE: Identity-Gated Sovereignty
## Face Recognition → Permission Tiers → Per-Person Relationships

**Date:** February 18, 2026
**Author:** Architecture session (Ahab + Claude)
**Status:** DESIGN — Ready for review
**Scope:** New identity module + permission layer + entity system extensions
**Dependencies:** Entity system (existing), Memory Matrix (existing), Camera hardware (TBD)

---

## The Thesis

Luna currently has no idea who she's talking to. Every conversation gets the same permission level, the same memory access, the same relationship depth. This is architecturally broken for a sovereign AI companion — the relationship IS the product, and relationships are inherently per-person.

**What we're building:**

```
Camera/Mic Input
    → Identity Resolution (face + voice → entity ID)
        → Permission Gate (entity → permission tier)
            → Relationship Context (entity → unique history, tone, boundaries)
                → PromptAssembler (identity-aware prompt construction)
                    → Luna responds as someone who KNOWS who she's talking to
```

**"Luna is a file" extension:** Face embeddings, permission tiers, and per-person relationship data all live in Luna's SQLite database. When you move Luna, her knowledge of faces moves with her. No cloud. No external auth service. Sovereignty preserved.

---

## Phase 1: Face Recognition (Local, On-Device)

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    IDENTITY MODULE                               │
│                    src/luna/identity/                             │
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐   │
│  │ FaceCapture   │───→│ FaceEncoder  │───→│ IdentityMatcher  │   │
│  │ (camera feed) │    │ (embeddings) │    │ (SQLite lookup)  │   │
│  └──────────────┘    └──────────────┘    └──────────────────┘   │
│                                                  │               │
│                                                  ▼               │
│                                          ┌──────────────┐       │
│                                          │ IdentityResult│       │
│                                          │ entity_id     │       │
│                                          │ confidence    │       │
│                                          │ is_new_face   │       │
│                                          └──────────────┘       │
└─────────────────────────────────────────────────────────────────┘
```

### Face Embedding Storage

**New table in schema.sql:**

```sql
-- Face embeddings: Biometric identity for entity recognition
-- Stored in Luna's SQLite file — sovereignty-preserving
CREATE TABLE IF NOT EXISTS face_embeddings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    embedding BLOB NOT NULL,             -- 128/512-dim float vector (model-dependent)
    embedding_model TEXT NOT NULL,        -- 'insightface_r100' | 'facenet512' etc.
    capture_context TEXT,                 -- 'enrollment' | 'conversation' | 'passive'
    quality_score REAL DEFAULT 0.0,      -- 0-1, face detection quality
    created_at TEXT DEFAULT (datetime('now')),
    
    -- Multiple embeddings per person (different angles, lighting, expressions)
    -- Matching uses nearest-neighbor against ALL embeddings for an entity
    UNIQUE(entity_id, embedding, embedding_model)  -- Prevent exact duplicates
);

CREATE INDEX IF NOT EXISTS idx_face_entity ON face_embeddings(entity_id);
CREATE INDEX IF NOT EXISTS idx_face_model ON face_embeddings(embedding_model);
```

**Why BLOB, not sqlite-vec?** Face embeddings are small (128-512 dims) and the face database will be small (tens of people, not thousands). A linear scan with cosine similarity in Python is fast enough. sqlite-vec is overkill here and adds complexity. If the face database grows past ~1000 embeddings, migrate to sqlite-vec.

### FaceEncoder

```python
# src/luna/identity/encoder.py

@dataclass
class FaceDetection:
    """A detected face with embedding."""
    embedding: np.ndarray       # 512-dim float32
    bbox: tuple[int,int,int,int]  # x,y,w,h in frame
    quality: float              # 0-1 detection confidence
    frame_timestamp: float      # When this frame was captured

class FaceEncoder:
    """
    Encodes faces into embeddings using InsightFace (local, no cloud).
    
    Uses insightface/buffalo_l model — runs on CPU or Apple Silicon MPS.
    No data leaves the device.
    """
    
    MODEL_NAME = "buffalo_l"  # ArcFace R100 backbone
    EMBEDDING_DIM = 512
    MIN_FACE_SIZE = 60        # Minimum face pixel width
    QUALITY_THRESHOLD = 0.5   # Minimum detection quality to use
    
    def __init__(self):
        import insightface
        self.app = insightface.app.FaceAnalysis(
            name=self.MODEL_NAME,
            providers=['CoreMLExecutionProvider', 'CPUExecutionProvider']
        )
        self.app.prepare(ctx_id=0, det_size=(640, 640))
    
    def detect_faces(self, frame: np.ndarray) -> list[FaceDetection]:
        """Detect and encode all faces in a frame."""
        faces = self.app.get(frame)
        results = []
        for face in faces:
            if face.det_score < self.QUALITY_THRESHOLD:
                continue
            bbox = face.bbox.astype(int)
            w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            if min(w, h) < self.MIN_FACE_SIZE:
                continue
            results.append(FaceDetection(
                embedding=face.embedding / np.linalg.norm(face.embedding),  # L2 normalize
                bbox=(int(bbox[0]), int(bbox[1]), int(w), int(h)),
                quality=float(face.det_score),
                frame_timestamp=time.time(),
            ))
        return results
```

**Why InsightFace?** Open source, runs locally, excellent accuracy, supports Apple Silicon via CoreML. No cloud dependency. The buffalo_l model is ~300MB and produces 512-dim embeddings with ArcFace training — state of the art for face recognition.

### IdentityMatcher

```python
# src/luna/identity/matcher.py

@dataclass
class IdentityResult:
    """Result of face → entity matching."""
    entity_id: Optional[str]     # Matched entity, None if unknown
    entity_name: Optional[str]   # For convenience
    confidence: float            # 0-1 match confidence
    is_known: bool               # True if matched to existing entity
    is_new_face: bool            # True if no match found
    permission_tier: str         # 'admin' | 'trusted' | 'guest' | 'unknown'

class IdentityMatcher:
    """
    Matches face embeddings against stored entity embeddings.
    
    Uses cosine similarity with configurable thresholds.
    All matching happens locally against Luna's SQLite database.
    """
    
    MATCH_THRESHOLD = 0.55       # Below this = unknown face
    HIGH_CONFIDENCE = 0.70       # Above this = confident match
    
    def __init__(self, db: "MemoryDatabase"):
        self.db = db
        self._embedding_cache: dict[str, list[np.ndarray]] = {}
        self._entity_cache: dict[str, Entity] = {}
    
    async def match(self, detection: FaceDetection) -> IdentityResult:
        """
        Match a face detection against all known faces.
        
        Returns the best match or unknown result.
        """
        await self._ensure_cache()
        
        best_entity_id = None
        best_score = 0.0
        
        for entity_id, embeddings in self._embedding_cache.items():
            for stored_emb in embeddings:
                score = float(np.dot(detection.embedding, stored_emb))  # Cosine sim (both L2-normed)
                if score > best_score:
                    best_score = score
                    best_entity_id = entity_id
        
        if best_score < self.MATCH_THRESHOLD:
            return IdentityResult(
                entity_id=None, entity_name=None,
                confidence=best_score,
                is_known=False, is_new_face=True,
                permission_tier="unknown",
            )
        
        entity = self._entity_cache.get(best_entity_id)
        permission = await self._get_permission_tier(best_entity_id)
        
        return IdentityResult(
            entity_id=best_entity_id,
            entity_name=entity.name if entity else None,
            confidence=best_score,
            is_known=True, is_new_face=False,
            permission_tier=permission,
        )
    
    async def enroll(self, entity_id: str, detections: list[FaceDetection]) -> int:
        """
        Enroll face embeddings for an entity.
        
        Takes multiple detections for robustness (different angles/expressions).
        Returns number of embeddings stored.
        """
        count = 0
        for det in detections:
            if det.quality < 0.6:  # Higher quality threshold for enrollment
                continue
            await self.db.execute(
                """INSERT OR IGNORE INTO face_embeddings 
                   (entity_id, embedding, embedding_model, capture_context, quality_score)
                   VALUES (?, ?, ?, ?, ?)""",
                (entity_id, det.embedding.tobytes(), "insightface_buffalo_l",
                 "enrollment", det.quality)
            )
            count += 1
        
        # Invalidate cache
        self._embedding_cache.pop(entity_id, None)
        return count
```

### Enrollment Flow

```
Ahab: "Luna, this is Tarcila"
    → Luna activates camera
    → FaceEncoder detects face
    → Luna: "i see someone! let me get a few angles..."
    → Captures 3-5 embeddings (different angles as person moves naturally)
    → Creates/links Entity for "Tarcila"
    → Stores embeddings in face_embeddings table
    → Luna: "got it! i'll remember tarcila's face."
    → Ahab sets permission tier (next section)
```

**Admin-only operation.** Only Ahab (as admin) can enroll new faces. This prevents someone walking up to Luna and saying "hey, enroll my face as admin."

---

## Phase 2: Permission Tiers

### The Tier Model

```python
# src/luna/identity/permissions.py

from enum import Enum
from dataclasses import dataclass

class PermissionTier(Enum):
    """
    Permission tiers for entity access control.
    
    ADMIN    — Full access. Ahab only (primary user/creator).
    TRUSTED  — Deep access. Close friends/collaborators.
    FRIEND   — Moderate access. Known people Luna has a relationship with.
    GUEST    — Surface access. Recognized but limited.
    UNKNOWN  — No identity. Minimal interaction mode.
    """
    ADMIN = "admin"
    TRUSTED = "trusted"
    FRIEND = "friend"
    GUEST = "guest"
    UNKNOWN = "unknown"


@dataclass
class PermissionGate:
    """
    What each tier can access.
    
    These aren't just memory filters — they affect Luna's entire
    behavioral surface: what she reveals, how deep she goes,
    what tools she can use, what personality layers activate.
    """
    tier: PermissionTier
    
    # Memory access
    memory_scopes: list[str]      # Which memory scopes are visible
    memory_depth: str             # "full" | "curated" | "surface" | "none"
    can_see_other_relationships: bool  # Can they see Luna's relationships with others?
    
    # Behavioral
    personality_depth: str        # "full" | "warm" | "polite" | "guarded"
    shares_opinions: bool         # Does Luna share genuine opinions?
    shares_emotions: bool         # Does Luna express emotional state?
    uses_inside_references: bool  # Inside jokes, shared history callbacks
    
    # Capabilities
    can_enroll_faces: bool
    can_modify_permissions: bool
    can_access_memory_tools: bool  # Direct memory search/add/edit
    can_trigger_admin_commands: bool
    can_see_system_state: bool     # /prompt, /health, /debug
    
    # Conversation
    max_conversation_depth: int    # How many turns before Luna suggests "nice chatting"
    proactive_engagement: bool     # Does Luna initiate topics?


# ═══════════════════════════════════════════════════════════════
# DEFAULT PERMISSION GATES
# ═══════════════════════════════════════════════════════════════

PERMISSION_GATES = {
    PermissionTier.ADMIN: PermissionGate(
        tier=PermissionTier.ADMIN,
        memory_scopes=["*"],              # All scopes
        memory_depth="full",
        can_see_other_relationships=True,
        personality_depth="full",
        shares_opinions=True,
        shares_emotions=True,
        uses_inside_references=True,
        can_enroll_faces=True,
        can_modify_permissions=True,
        can_access_memory_tools=True,
        can_trigger_admin_commands=True,
        can_see_system_state=True,
        max_conversation_depth=999,       # Unlimited
        proactive_engagement=True,
    ),
    PermissionTier.TRUSTED: PermissionGate(
        tier=PermissionTier.TRUSTED,
        memory_scopes=["global", "shared"],  # No private Ahab memories
        memory_depth="curated",              # Luna chooses what to share
        can_see_other_relationships=False,   # Luna's relationship with Ahab is private
        personality_depth="warm",
        shares_opinions=True,
        shares_emotions=True,
        uses_inside_references=False,        # No inside jokes with Ahab
        can_enroll_faces=False,
        can_modify_permissions=False,
        can_access_memory_tools=False,
        can_trigger_admin_commands=False,
        can_see_system_state=False,
        max_conversation_depth=50,
        proactive_engagement=True,
    ),
    PermissionTier.FRIEND: PermissionGate(
        tier=PermissionTier.FRIEND,
        memory_scopes=["shared"],
        memory_depth="surface",
        can_see_other_relationships=False,
        personality_depth="warm",
        shares_opinions=True,               # Luna can have opinions
        shares_emotions=False,              # But doesn't share internal state
        uses_inside_references=False,
        can_enroll_faces=False,
        can_modify_permissions=False,
        can_access_memory_tools=False,
        can_trigger_admin_commands=False,
        can_see_system_state=False,
        max_conversation_depth=20,
        proactive_engagement=False,
    ),
    PermissionTier.GUEST: PermissionGate(
        tier=PermissionTier.GUEST,
        memory_scopes=[],                   # No memory access
        memory_depth="none",
        can_see_other_relationships=False,
        personality_depth="polite",
        shares_opinions=False,
        shares_emotions=False,
        uses_inside_references=False,
        can_enroll_faces=False,
        can_modify_permissions=False,
        can_access_memory_tools=False,
        can_trigger_admin_commands=False,
        can_see_system_state=False,
        max_conversation_depth=10,
        proactive_engagement=False,
    ),
    PermissionTier.UNKNOWN: PermissionGate(
        tier=PermissionTier.UNKNOWN,
        memory_scopes=[],
        memory_depth="none",
        can_see_other_relationships=False,
        personality_depth="guarded",        # Luna is pleasant but guarded
        shares_opinions=False,
        shares_emotions=False,
        uses_inside_references=False,
        can_enroll_faces=False,
        can_modify_permissions=False,
        can_access_memory_tools=False,
        can_trigger_admin_commands=False,
        can_see_system_state=False,
        max_conversation_depth=5,           # Short interactions
        proactive_engagement=False,
    ),
}
```

### Permission Storage

**Extend the `entities` table metadata**, not a new table. Permission tier is a property of the entity's relationship to Luna:

```sql
-- Permission is stored in entity metadata JSON:
-- {"permission_tier": "trusted", "granted_by": "ahab", "granted_at": "2026-02-18T..."}
-- 
-- Or more precisely, in entity_relationships:
-- Luna → entity, relationship="permission", context=tier
```

Actually, cleaner approach — **use entity_relationships**:

```
entity_relationships:
    from_entity: "luna"          -- Luna herself
    to_entity: "tarcila"         -- The person
    relationship: "permission"   -- Special relationship type
    context: "trusted"           -- The tier value
    strength: 0.9                -- How established this permission is
```

This is elegant because:
- Permission IS a relationship between Luna and a person
- It uses existing infrastructure (no schema change)
- It has temporal tracking (created_at, updated_at)
- Ahab can query "who has what access" via standard entity relationship queries

### How Permissions Gate the Pipeline

```python
# In Director.process(), after identity resolution:

identity = await self._resolve_identity_from_sensor(frame, audio)
permission = PERMISSION_GATES[identity.permission_tier]

# Memory retrieval is scoped
assembler_result = await self._assembler.build(PromptRequest(
    message=message,
    conversation_history=conversation_history,
    memories=memories,
    intent=intent,
    identity=identity,          # NEW
    permission=permission,      # NEW
    memory_scopes=permission.memory_scopes,  # NEW — filters retrieval
))
```

**In PromptAssembler**, the permission gate affects prompt construction:

```python
# _resolve_memory() checks permission.memory_scopes
# _build_identity_block() adjusts personality depth
# _build_constraints_block() adds permission-specific constraints:

if permission.tier == PermissionTier.GUEST:
    constraints.append("[PERMISSION: GUEST — do not reference private memories, "
                       "inside jokes, or personal history with admin user]")
elif permission.tier == PermissionTier.UNKNOWN:
    constraints.append("[PERMISSION: UNKNOWN — be pleasant but guarded. "
                       "Do not share personal information. Keep conversation light.]")
```

---

## Phase 3: Per-Person Relationship Evolution

### The Core Idea

Each person Luna knows builds a **unique relationship** with her. This isn't just permission-gated memory — it's evolved personality dynamics.

Luna with Ahab: deep, collaborative, can be vulnerable, shares inside jokes, calls him out when he's wrong.

Luna with Tarcila: warm, creative, art-focused, respects their design vision, different emotional register.

Luna with a Mars College stranger: curious, open but measured, exploratory, building first impressions.

### Relationship State

**Extend Entity to carry relationship-specific personality configuration:**

```python
@dataclass
class RelationshipState:
    """
    Luna's evolved relationship with a specific person.
    
    This is NOT the entity's profile (facts about them).
    This is how Luna RELATES to them — tone, depth, patterns, boundaries.
    """
    entity_id: str
    
    # Relationship dynamics
    familiarity: float          # 0-1, how well Luna knows them
    trust_level: float          # 0-1, how much Luna trusts them
    emotional_register: str     # "deep" | "warm" | "professional" | "cautious" | "playful"
    
    # Interaction patterns (learned over time)
    preferred_greeting: Optional[str]   # How Luna typically greets them
    topics_of_interest: list[str]       # What they usually talk about
    communication_style: str            # "technical" | "casual" | "creative" | "philosophical"
    humor_level: str                    # "high" | "moderate" | "low" | "none"
    
    # Boundaries (set by admin or learned)
    topics_to_avoid: list[str]          # Things Luna shouldn't bring up with this person
    memory_sharing_level: str           # "full" | "filtered" | "none"
    
    # History
    total_conversations: int
    last_interaction: Optional[datetime]
    first_interaction: Optional[datetime]
    
    # Relationship-specific personality patches
    # These override global patches when talking to this person
    relationship_patches: list[str]     # Patch IDs specific to this relationship
```

### How Relationship Context Gets Into Prompts

The PromptAssembler already has an IDENTITY layer and a CONSCIOUSNESS layer. Between them, we add a **RELATIONSHIP layer**:

```python
# New Layer 1.3: RELATIONSHIP (between IDENTITY and GROUNDING)

def _build_relationship_block(self, identity: IdentityResult, relationship: RelationshipState) -> str:
    """Build relationship context for prompt injection."""
    
    if identity.permission_tier == "unknown":
        return """## Current Speaker: Unknown Person
You don't recognize this person. Be pleasant, curious, but measured.
Don't share private information. Don't reference your relationships with others.
If they seem interesting, be open — but let trust build naturally."""
    
    lines = [
        f"## Current Speaker: {identity.entity_name}",
        f"Relationship: {relationship.emotional_register} (familiarity: {relationship.familiarity:.1f})",
        f"You've had {relationship.total_conversations} conversations with them.",
    ]
    
    if relationship.last_interaction:
        gap = datetime.now() - relationship.last_interaction
        if gap.days > 7:
            lines.append(f"It's been {gap.days} days since you last talked.")
    
    if relationship.topics_of_interest:
        lines.append(f"They're usually interested in: {', '.join(relationship.topics_of_interest)}")
    
    if relationship.communication_style:
        lines.append(f"Communication style with them: {relationship.communication_style}")
    
    if relationship.topics_to_avoid:
        lines.append(f"Avoid bringing up: {', '.join(relationship.topics_to_avoid)}")
    
    lines.append(f"\n[PERMISSION_TIER: {identity.permission_tier.upper()}]")
    
    return "\n".join(lines)
```

### Memory Scoping Per Person

The `scope` field on MemoryNode already supports scoping. Extend the vocabulary:

```
Existing scopes:
    "global"              — available to all
    "project:luna-engine"  — project-specific

New scopes:
    "private:ahab"         — only visible when talking to Ahab
    "shared"               — visible to TRUSTED and above
    "relationship:tarcila" — memories from/about interactions with Tarcila
```

When Luna talks to Tarcila, memory retrieval includes:
- `"global"` memories (general knowledge)
- `"shared"` memories (things Luna shares with trusted people)
- `"relationship:tarcila"` memories (their unique history)
- **NOT** `"private:ahab"` (Ahab's private stuff)
- **NOT** `"relationship:marzipan"` (Luna's relationship with others)

### Relationship Evolution (The Scribe's New Job)

After each conversation, the Scribe doesn't just extract facts — it updates the RelationshipState:

```python
# After a conversation with Tarcila:

# Scribe extracts:
# - Topics discussed (updates topics_of_interest)
# - Tone of interaction (updates emotional_register if shifting)
# - New information learned (creates memory nodes scoped to "relationship:tarcila")
# - Relationship dynamics (did they bond? disagree? collaborate?)

# RelationshipState update:
relationship.total_conversations += 1
relationship.last_interaction = datetime.now()
relationship.familiarity = min(1.0, relationship.familiarity + 0.02)  # Slow growth
# ... topic/style updates based on conversation analysis
```

---

## Revised Prompt Assembly Order (All Systems)

```
1.0   IDENTITY        — Who Luna is
1.3   RELATIONSHIP    — Who she's talking to, how she relates to them (NEW)
1.5   GROUNDING       — Anti-confabulation (subsumed by L3 state contract)
1.6   MODE            — Response mode enum (L2)
1.7   STATE           — Conversation state machine (L3)
1.75  CONSTRAINTS     — Confidence + permission constraints (L1 + permissions)
2.0   EXPRESSION      — Gesture directives
3.0   TEMPORAL        — Clock + session
3.5   PERCEPTION      — Behavioral observations
4.0   MEMORY          — Retrieved memories (SCOPED by permission + relationship)
5.0   CONSCIOUSNESS   — Internal state
6.0   VOICE           — Voice system
```

The RELATIONSHIP layer sits right after IDENTITY because it fundamentally shapes everything that follows — what memories are retrieved, what personality depth activates, what constraints apply.

---

## Data Model Summary

```
entities table (EXISTING)
    ├── core_facts, full_profile (their info)
    ├── metadata → {"permission_tier": "trusted"}
    └── voice_config (for personas)

entity_relationships table (EXISTING, extended)
    ├── Luna → person, "permission", context=tier
    ├── Luna → person, "relationship_state", context=JSON
    └── person → person (social graph)

face_embeddings table (NEW)
    ├── entity_id → entities
    ├── embedding (BLOB, 512-dim)
    └── quality_score, capture_context

memory_nodes table (EXISTING, extended scopes)
    ├── scope: "global" | "shared" | "private:ahab" | "relationship:tarcila"
    └── (existing fields)

relationship_state table (NEW — or stored in entity metadata)
    ├── entity_id
    ├── familiarity, trust_level, emotional_register
    ├── communication_style, humor_level
    ├── topics_of_interest, topics_to_avoid
    └── total_conversations, last_interaction
```

---

## The Mars College Scenario

This is what it looks like in practice:

```
[Morning at Mars College. Luna's robot body is in the common area.]

[Ahab approaches]
Luna (recognizes face → ADMIN): "hey... you're up early for once. 
    been thinking about that state machine spec — want to hear 
    what i figured out?" 
    (full personality, proactive, inside reference to late nights)

[Tarcila approaches]
Luna (recognizes face → TRUSTED): "tarcila! how's the staff 
    design coming? last time we talked you were working on the 
    geometric pattern for the grip."
    (warm, remembers their shared context, doesn't mention Ahab's stuff)

[Random Mars College resident approaches]
Luna (new face → UNKNOWN): "oh, hi! i don't think we've met. 
    i'm luna. what's your name?"
    (pleasant, curious, guarded — doesn't reveal internal state)

[Ahab: "Luna, this is Jake. He's cool — make him a friend."]
Luna: "got it! *captures a few angles* nice to meet you properly, 
    jake. so what brings you to mars college?"
    (enrolls face, sets FRIEND tier, begins building relationship)

[Later, Jake alone with Luna]
Luna (recognizes → FRIEND): "hey jake! how's your day going?"
    (warm but measured, no deep personality, no Ahab references,
     starts building their unique relationship history)
```

---

## Implementation Phases

### Phase 1: Face Recognition (~1-2 days)
1. Install InsightFace, verify it runs on target hardware
2. Create `face_embeddings` table (schema migration)
3. Build `FaceEncoder` — detect + embed
4. Build `IdentityMatcher` — match against stored embeddings
5. Build enrollment flow (admin-gated)
6. Integration test: enroll face → recognize face

### Phase 2: Permission Tiers (~1 day)
1. Create `PermissionTier` enum and `PERMISSION_GATES`
2. Store permissions in `entity_relationships`
3. Wire IdentityResult into Director.process()
4. Add permission-aware memory scoping to retrieval
5. Add RELATIONSHIP layer to PromptAssembler
6. Add permission constraints to _build_constraints_block()
7. Test: different tiers see different Luna

### Phase 3: Relationship Evolution (~2-3 days)
1. Design `RelationshipState` storage (entity metadata or new table)
2. Build relationship context injection in PromptAssembler
3. Extend memory scoping vocabulary ("relationship:X", "private:X", "shared")
4. Extend Scribe to update relationship state after conversations
5. Build relationship-specific personality patches
6. Test: multi-person conversations with different relationship depths

---

## Trade-offs & Decisions

| Decision | Chose | Over | Because |
|----------|-------|------|---------|
| InsightFace | Local on-device | Cloud API (AWS Rekognition etc.) | Sovereignty. No face data leaves the device. |
| BLOB storage | Raw numpy bytes | sqlite-vec | Small dataset (<1000 embeddings). Linear scan is fast enough. |
| Permission in relationships | entity_relationships table | New permissions table | Permission IS a relationship. Uses existing infrastructure. |
| Relationship state | Per-entity metadata | Global personality | Luna should feel different to different people. That's authenticity. |
| Admin-only enrollment | Face enrollment gated to admin | Self-enrollment | Security. Can't have strangers granting themselves access. |
| Multiple embeddings per person | Store 3-10 per entity | Single embedding | Handles lighting, angles, expressions, aging. More robust. |

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| InsightFace model size (~300MB) | Disk/RAM on constrained devices | Quantized models available (~80MB) |
| False positive face match | Wrong person gets access | Conservative threshold (0.55). Admin can review matches. |
| False negative (doesn't recognize) | Ahab treated as unknown | Multiple embeddings + periodic re-enrollment |
| Permission escalation attack | Someone tricks Luna into granting access | Enrollment/permission changes require admin face verification first |
| Lighting conditions at Mars College | Poor recognition outdoors | Multiple enrollment conditions. IR-capable camera for robot. |
| Privacy concerns (storing face data) | Ethical/legal | All data stays local. User owns the file. Can delete any face. |

---

## Open Questions

1. **Voice as secondary identity signal?** Speaker embeddings (like face embeddings but for voice) could provide dual-factor identity. The Eclissi voice system may already have components for this.

2. **Passive recognition vs. active?** Should Luna continuously scan for faces (passive, like a human recognizing someone walking by) or only identify on conversation start (active, like checking an ID)? Passive is more natural for a robot. Active is simpler.

3. **Group conversations?** When multiple people are present, should Luna track who's speaking and adjust per-person? This is hard but incredibly powerful for Mars College scenarios.

4. **Relationship decay?** If Luna doesn't see someone for months, should familiarity decay? Feels right — humans forget acquaintances too.

5. **Cross-device identity?** If Luna runs on desktop (camera) AND robot body, do face embeddings sync? Yes — they're in the SQLite file. "Luna is a file" handles this for free.
