# Part XII: Future Roadmap

**Version:** 3.0
**Date:** January 30, 2026
**Status:** CURRENT
**Note:** This document tracks implemented features and planned capabilities.

---

## 12.1 Roadmap Overview

Luna's development follows a phased approach, with each phase building on the previous:

```
┌─────────────────────────────────────────────────────────────┐
│  PHASE 1: FOUNDATION                                        │
│  Memory Matrix, Director LLM, Voice Interface               │
│  Status: COMPLETE                                           │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  PHASE 2: INTELLIGENCE (Current)                            │
│  Agentic Architecture, Advanced Retrieval, MCP Integration  │
│  Status: In Progress (70% Complete)                         │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  PHASE 3: AGENCY                                            │
│  Kinetic Layer, Autonomous Actions, Integrations            │
│  Status: Design Phase                                       │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  PHASE 4: EXPANSION                                         │
│  Multi-Modal, AR Interface, Federation                      │
│  Status: Vision                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 12.2 Phase 1: Foundation (COMPLETE)

### What Was Built

| Component | Status | Description |
|-----------|--------|-------------|
| Memory Matrix | DONE | SQLite + sqlite-vec + NetworkX graph substrate |
| Director LLM | DONE | Local Qwen 3B + Claude delegation |
| Voice Interface | DONE | Whisper STT + Piper TTS |
| Scribe (Ben) | DONE | Extraction system with lock-in memory |
| Librarian (Dude) | DONE | Filing and retrieval with clustering |
| Actor System | DONE | Message-based actor isolation |
| Ring Buffer | DONE | Configurable conversation memory (2-20 turns) |

### Phase 1 Exit Criteria

- [x] Sub-500ms voice response latency (achieved with local inference)
- [x] Memory retrieval accuracy >85% (hybrid search with FTS5 + semantic)
- [x] Director handles 80%+ of queries locally (QueryRouter implemented)
- [x] Delegation works seamlessly (Claude API integration)
- [x] Actor-based fault isolation (Director, Matrix, Scribe, Librarian)

---

## 12.3 Phase 2: Intelligence (CURRENT)

### Implemented in Phase 2

| Component | Status | Description |
|-----------|--------|-------------|
| **Agentic Architecture** | DONE | AgentLoop, Planner, QueryRouter |
| **Revolving Context** | DONE | 4-ring model (CORE, INNER, MIDDLE, OUTER) |
| **Queue Manager** | DONE | Per-source queues with weighted priorities |
| **Tool Registry** | DONE | MCP-compatible tool definitions |
| **File Tools** | DONE | read_file, write_file, list_directory, file_exists |
| **Memory Tools** | DONE | memory_query, memory_store, memory_context |
| **MCP Integration** | DONE | 41 MCP tools, FastMCP server |
| **API Server** | DONE | 74 endpoints, SSE streaming, WebSocket |
| **Luna Hub UI** | DONE | 20 React components, 5 custom hooks |
| **Performance Layer** | DONE | Orb state, gesture detection, emotion presets |
| **Hybrid Search** | DONE | FTS5 + semantic + graph traversal |
| **Clustering Engine** | DONE | Memory clustering with constellation assembly |

### In Progress

| Component | Status | Description |
|-----------|--------|-------------|
| **Lock-in Memory** | 80% | Access-based consolidation with pruning |
| **Continuous Learning** | PLANNED | Online learning from interactions |
| **SwarmCoordinator** | PLANNED | Parallel execution management |

### 2A: First-Class Objects

**Current:** Nodes are typed with lock-in states (drifting, fluid, settled).

**Future:** Objects with methods, relationships, and domain logic.

```python
# Current
node = MemoryNode(
    type="DECISION",
    content="We chose Actor model for fault isolation"
)
# Can only search by text

# Future
decision = Decision(
    choice="Actor model",
    alternatives=["MonoBehaviour", "Event-driven"],
    rationale="Fault isolation between components",
    made_by=[Person("Ahab")],
    made_at=datetime(2025, 12, 15)
)
# Can query: decision.get_consequences()
# Can query: decision.is_superseded()
# Can query: decision.get_related_decisions()
```

**Object Taxonomy:**

| Object Type | Key Methods | Relationships |
|-------------|-------------|---------------|
| `Person` | `get_conversations()`, `get_decisions()` | knows, works_with, mentioned_in |
| `Project` | `get_timeline()`, `get_open_questions()` | has_member, uses_technology, blocked_by |
| `Decision` | `get_consequences()`, `is_superseded()` | decided_by, affects, supersedes |
| `Problem` | `get_attempts()`, `is_resolved()` | blocks, caused_by, resolved_by |
| `Insight` | `get_evidence()`, `validate()` | derived_from, supports, contradicts |
| `Event` | `get_participants()`, `get_outcomes()` | caused_by, resulted_in, occurred_at |

**Implementation Path:**

1. Define object schemas (Python dataclasses)
2. Migration script: existing nodes → typed objects
3. Update Scribe extraction to output objects
4. Update Librarian to wire object relationships
5. Update Director context assembly to use objects

---

### 2B: Advanced Retrieval

**Current:** Hybrid search (FTS5 + semantic + graph) with smart-fetch budget management.

**Implemented:**
- FTS5 full-text search
- sqlite-vec semantic search
- Graph traversal with spreading activation
- Smart-fetch with token budget presets (minimal/balanced/rich)
- Constellation assembly for context building

**Future:** Query understanding + multi-hop reasoning.

```
┌─────────────────────────────────────────────────────────────┐
│  QUERY UNDERSTANDING                                        │
│                                                              │
│  "What led to the decision about the Actor model?"          │
│                                                              │
│  Parsed:                                                    │
│  - Target: Decision (Actor model)                           │
│  - Relationship: caused_by / led_to                         │
│  - Depth: Multi-hop (need predecessors)                     │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  MULTI-HOP RETRIEVAL                                        │
│                                                              │
│  Hop 1: Find "Actor model" decision                         │
│  Hop 2: Traverse caused_by edges                            │
│  Hop 3: Gather context from predecessor nodes               │
│                                                              │
│  Result: Decision + Problems it solved + Alternatives tried │
└─────────────────────────────────────────────────────────────┘
```

**Capabilities:**

| Capability | Current | Phase 2 |
|------------|---------|---------|
| Keyword search | ✅ FTS5 | ✅ FTS5 |
| Semantic search | ✅ sqlite-vec | ✅ sqlite-vec + reranking |
| Graph traversal | ✅ Multi-hop | Multi-hop with query parsing |
| Spreading activation | ✅ Implemented | Trace dependencies |
| Temporal queries | Partial | "What happened last week?" |
| Causal queries | ❌ | "What led to X?" |
| Counterfactual | ❌ | "What if we hadn't chosen X?" |

---

### 2C: Continuous Learning

**Current:** Lock-in based memory consolidation. Tuning system for parameter optimization.

**Implemented:**
- Lock-in coefficients (0.0-1.0) with access-based reinforcement
- Synaptic pruning for low-value edges and drifting nodes
- Tuning sessions with parameter evaluation and iteration history
- Voice tuning parameters (pitch, rate, volume)

**Future:** Online learning from interactions, experience replay, incremental fine-tuning.

```python
class ContinuousLearner:
    """Learn from Luna's interactions over time."""

    def __init__(self, director: Director):
        self.director = director
        self.experience_buffer = ExperienceBuffer(max_size=10000)
        self.update_threshold = 1000  # Examples before fine-tuning

    async def on_interaction(self, interaction: Interaction):
        """Called after each conversation turn."""
        # 1. Score the interaction
        quality = await self.score_interaction(interaction)

        # 2. Add to experience buffer if high quality
        if quality.score > 0.7:
            self.experience_buffer.add(
                context=interaction.context,
                input=interaction.user_input,
                output=interaction.luna_response,
                score=quality.score
            )

        # 3. Trigger fine-tuning if buffer full
        if len(self.experience_buffer) >= self.update_threshold:
            await self.fine_tune_increment()

    async def fine_tune_increment(self):
        """Incremental LoRA update."""
        examples = self.experience_buffer.sample(n=500)

        # Small learning rate, few steps
        await self.director.fine_tune(
            examples=examples,
            learning_rate=1e-5,
            steps=100
        )

        self.experience_buffer.clear()
```

**Learning Signals:**

| Signal | Source | What It Teaches |
|--------|--------|-----------------|
| User corrections | "No, I meant..." | Improve understanding |
| Explicit feedback | "That was helpful" | Reinforce good patterns |
| Re-asks | User asks same thing differently | Query wasn't understood |
| Delegation success | Claude's answer used | Delegation was appropriate |
| Conversation flow | No interruptions | Response was on-target |

---

## 12.4 Phase 3: Agency

### 3A: Kinetic Layer

**Current:** Luna is read-only. She can query memories but not act on the world.

**Future:** Luna can take actions with user permission.

```
┌─────────────────────────────────────────────────────────────┐
│  CURRENT: READ-ONLY                                         │
│                                                              │
│  User: "Remind me to call Alex tomorrow"                    │
│  Luna: "I'll remember that."                                │
│        (Stores in memory, but no actual reminder)           │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  FUTURE: KINETIC                                            │
│                                                              │
│  User: "Remind me to call Alex tomorrow"                    │
│  Luna: "Done. I've set a reminder for 9am tomorrow.         │
│         Want me to also draft talking points?"              │
│        (Actually creates calendar event + offers more)      │
└─────────────────────────────────────────────────────────────┘
```

**Action Types:**

| Action | Target | Permission Level |
|--------|--------|------------------|
| Create reminder | Calendar | Auto (user configured) |
| Send message | Email/SMS | Requires confirmation |
| Create note | Obsidian/Notes | Auto |
| File management | Local filesystem | Auto (within vault) |
| Web request | Approved APIs | Auto |
| Purchase | Payment systems | Always confirm |

**Governance Framework:**

```python
@dataclass
class ActionGovernance:
    """Rules for what Luna can do autonomously."""

    # Autonomous actions (no confirmation needed)
    autonomous: list[str] = [
        "create_memory",
        "create_reminder",
        "create_note",
        "backup_vault",
    ]

    # Actions requiring confirmation
    confirm_required: list[str] = [
        "send_email",
        "send_message",
        "delete_*",
        "modify_calendar",
    ]

    # Actions Luna should never take
    forbidden: list[str] = [
        "financial_transaction",
        "post_to_social_media",
        "share_personal_data",
        "execute_arbitrary_code",
    ]

    def check(self, action: Action) -> GovernanceResult:
        if self.matches(action, self.forbidden):
            return GovernanceResult.DENIED
        if self.matches(action, self.confirm_required):
            return GovernanceResult.NEEDS_CONFIRMATION
        if self.matches(action, self.autonomous):
            return GovernanceResult.ALLOWED
        return GovernanceResult.NEEDS_CONFIRMATION  # Default: ask
```

---

### 3B: Integration Adapters

**Purpose:** Connect Luna to external systems while maintaining sovereignty.

```
┌─────────────────────────────────────────────────────────────┐
│                       LUNA CORE                             │
│                    (Encrypted Vault)                        │
└────────────────────────┬────────────────────────────────────┘
                         │
          ┌──────────────┼──────────────┐
          │              │              │
          ▼              ▼              ▼
    ┌──────────┐   ┌──────────┐   ┌──────────┐
    │ Calendar │   │  Notes   │   │  Tasks   │
    │ Adapter  │   │ Adapter  │   │ Adapter  │
    └────┬─────┘   └────┬─────┘   └────┬─────┘
         │              │              │
         ▼              ▼              ▼
    ┌──────────┐   ┌──────────┐   ┌──────────┐
    │  macOS   │   │ Obsidian │   │ Todoist  │
    │ Calendar │   │          │   │          │
    └──────────┘   └──────────┘   └──────────┘
```

**Adapter Contract:**

```python
class IntegrationAdapter(ABC):
    """Base class for external system adapters."""

    @abstractmethod
    async def execute(self, action: Action) -> ActionResult:
        """Execute an action in the external system."""
        pass

    @abstractmethod
    def validate(self, action: Action) -> ValidationResult:
        """Validate action before execution."""
        pass

    @abstractmethod
    async def sync(self) -> SyncResult:
        """Sync state from external system to Memory Matrix."""
        pass

class ObsidianAdapter(IntegrationAdapter):
    def __init__(self, vault_path: str):
        self.vault_path = vault_path

    async def execute(self, action: Action) -> ActionResult:
        if action.type == "create_note":
            path = self.vault_path / action.params["filename"]
            path.write_text(action.params["content"])
            return ActionResult(success=True, artifact=str(path))
        # ... other action types

    async def sync(self) -> SyncResult:
        """Import Obsidian notes as memory nodes."""
        notes = self.scan_vault()
        for note in notes:
            if self.is_new_or_modified(note):
                await self.scribe.process_document(note)
        return SyncResult(imported=len(notes))
```

**Initial Adapters (Phase 3A):**

| Adapter | Platform | Actions |
|---------|----------|---------|
| Calendar | macOS Calendar | Create/read events |
| Notes | Obsidian | Create/read/link notes |
| Tasks | Todoist | Create/complete tasks |
| Filesystem | Local | Read/write within vault |

---

### 3C: Proactive Luna

**Current:** Luna responds to prompts.

**Future:** Luna initiates when appropriate.

```python
class ProactiveTrigger:
    """Conditions under which Luna might initiate."""

    triggers = [
        # Time-based
        TimeTrigger(
            condition="morning",
            action="Offer daily briefing",
            permission="user_enabled_briefings"
        ),

        # Context-based
        ContextTrigger(
            condition="calendar_event_starting_soon",
            action="Remind with relevant context",
            permission="always"  # User expects this
        ),

        # Pattern-based
        PatternTrigger(
            condition="user_mentioned_same_problem_3x",
            action="Offer to help solve systematically",
            permission="user_enabled_proactive"
        ),

        # Insight-based
        InsightTrigger(
            condition="discovered_connection_user_might_value",
            action="Share insight at appropriate moment",
            permission="user_enabled_insights"
        ),
    ]
```

**Proactive Governance:**

| Mode | Luna Initiates? | Use Case |
|------|-----------------|----------|
| Silent | Never | User wants reactive-only |
| Gentle | Reminders only | Minimal interruption |
| Active | Insights + reminders | Engaged companion |
| Full | Pattern + suggestions | Maximum agency |

---

## 12.5 Phase 4: Expansion

### 4A: Multi-Modal Input

**Current:** Voice and text.

**Future:** Images, documents, screen context.

| Input Type | Capability | Implementation |
|------------|------------|----------------|
| Voice | ✅ Current | Whisper local |
| Text | ✅ Current | Direct input |
| Images | Planned | Local vision model |
| Screenshots | Planned | OCR + vision |
| Documents | Planned | PDF/Word parsing |
| Screen context | Planned | Accessibility APIs |

**Use Cases:**

- "What's in this screenshot?"
- "Remember this receipt" (photo)
- "Summarize this PDF"
- "What app am I looking at?" (screen context)

---

### 4B: AR Interface

**Vision:** Luna as ambient presence via AR glasses.

```
┌─────────────────────────────────────────────────────────────┐
│  AR GLASSES VIEW                                            │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                                                      │   │
│  │     [You're looking at: Conference room]            │   │
│  │                                                      │   │
│  │     Luna (subtle overlay):                          │   │
│  │     "Sarah mentioned she'd be here at 2pm.          │   │
│  │      You wanted to discuss the Actor model."        │   │
│  │                                                      │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
│  Luna provides context without being asked.                 │
│  Triggered by: location, people recognition, time.          │
└─────────────────────────────────────────────────────────────┘
```

**Technical Requirements:**

- Low-latency inference (<200ms)
- Minimal battery impact
- Privacy-preserving (on-device when possible)
- Graceful offline mode

**Hardware Targets:**

| Device | Status | Notes |
|--------|--------|-------|
| Meta Ray-Ban | Future | Limited compute |
| Apple Vision Pro | Future | Full compute available |
| Custom glasses | Vision | Purpose-built for Luna |

---

### 4C: Multi-User Luna

**Current:** Single user, single Luna.

**Future:** Shared contexts with boundaries.

```
┌─────────────────────────────────────────────────────────────┐
│  MULTI-USER MODEL                                           │
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   Ahab's    │  │   Sarah's   │  │   Shared    │         │
│  │   Private   │  │   Private   │  │   Workspace │         │
│  │   Memory    │  │   Memory    │  │   Memory    │         │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘         │
│         │                │                │                 │
│         └────────────────┼────────────────┘                 │
│                          │                                  │
│                          ▼                                  │
│                  ┌───────────────┐                          │
│                  │  Luna Core    │                          │
│                  │  (Context     │                          │
│                  │   Switching)  │                          │
│                  └───────────────┘                          │
└─────────────────────────────────────────────────────────────┘
```

**Privacy Boundaries:**

| Memory Type | Ahab Sees | Sarah Sees |
|-------------|-----------|------------|
| Ahab's private | ✅ | ❌ |
| Sarah's private | ❌ | ✅ |
| Shared workspace | ✅ | ✅ |
| Cross-references | Anonymized | Anonymized |

---

### 4D: Federation

**Vision:** Luna instances that can communicate while maintaining sovereignty.

```
┌──────────────┐         ┌──────────────┐
│   Ahab's     │◄───────►│   Sarah's    │
│    Luna      │ Secure  │    Luna      │
│              │ Channel │              │
└──────────────┘         └──────────────┘
       │                        │
       │    ┌──────────────┐    │
       └───►│   Shared     │◄───┘
            │   Context    │
            │   (Encrypted)│
            └──────────────┘
```

**Federation Principles:**

| Principle | Implementation |
|-----------|----------------|
| Opt-in only | No data shared without explicit consent |
| End-to-end encrypted | Even transit servers can't read |
| Revocable | Can withdraw shared context anytime |
| Auditable | Can see what's been shared |
| Minimal | Share only what's needed |

**Use Cases:**

- Couples sharing calendar context
- Teams sharing project context
- Families sharing household context

---

## 12.6 Non-Goals

Things Luna will **not** pursue:

| Non-Goal | Reason |
|----------|--------|
| Cloud-hosted Luna | Contradicts sovereignty |
| Subscription model | Contradicts ownership |
| Data monetization | Contradicts privacy |
| General assistant | Luna is personal, not generic |
| Competing with ChatGPT | Different philosophy entirely |
| Mobile-first | Desktop/voice first, mobile later |

---

## 12.7 Success Metrics by Phase

### Phase 1 (Foundation) - ACHIEVED

| Metric | Target | Actual |
|--------|--------|--------|
| Voice latency | <500ms | ~350ms (local Qwen) |
| Local handling rate | >80% | 85%+ (QueryRouter) |
| Memory retrieval accuracy | >85% | 87% (hybrid search) |
| Daily active usage | User's primary AI | Active development |

### Phase 2 (Intelligence) - IN PROGRESS

| Metric | Target | Status |
|--------|--------|--------|
| Agentic task completion | >90% | 92% (AgentLoop) |
| API endpoint coverage | 50+ | 74 endpoints |
| MCP tool coverage | 30+ | 41 tools |
| UI component coverage | 15+ | 20 components |
| Multi-hop retrieval accuracy | >75% | Testing |
| Object method success rate | >90% | PLANNED |
| Learning improvement | +5% accuracy/month | PLANNED |

### Phase 3 (Agency)

| Metric | Target |
|--------|--------|
| Action success rate | >95% |
| User trust (survey) | >4.5/5 |
| Proactive relevance | >80% useful |

### Phase 4 (Expansion)

| Metric | Target |
|--------|--------|
| Multi-modal accuracy | >85% |
| AR latency | <200ms |
| Federation adoption | >2 users connected |

---

## 12.8 The Destination

Luna, fully realized:

> A sovereign AI companion that knows your context, respects your privacy, takes action on your behalf when permitted, learns and grows with you, connects with others' Lunas when you choose, and remains yours—completely, permanently, unconditionally.

Not a product. Not a service. A tool you own.

That's the destination.

---

## 12.9 Implementation Summary (v3.0)

### Done (Phase 1 + Phase 2 Partial)

| Category | Items Completed |
|----------|-----------------|
| **Engine Core** | Tick loops, Actor system, State machine, Input buffer |
| **Actors** | Director, Matrix, Scribe, Librarian, HistoryManager |
| **Memory** | SQLite + sqlite-vec + NetworkX, FTS5, Hybrid search |
| **Agentic** | AgentLoop, Planner, QueryRouter, ToolRegistry |
| **API** | 74 endpoints, 4 SSE streams, 1 WebSocket |
| **MCP** | 41 tools, FastMCP server, Auto-session recording |
| **Frontend** | 20 components, 5 hooks, Glass morphism design |
| **Voice** | Whisper STT, Piper TTS, Push-to-talk, Hands-free |
| **Tuning** | Parameter system, Sessions, Evaluation scoring |
| **Performance** | Orb state, Gesture detection, Emotion presets |

### Planned (Phase 2 Remaining + Phase 3+)

| Category | Items Planned |
|----------|---------------|
| **Memory** | First-class objects, Causal queries, Counterfactuals |
| **Learning** | Online learning, Experience buffer, Incremental fine-tuning |
| **Agency** | Kinetic layer, Calendar/Notes adapters, Proactive triggers |
| **Parallel** | SwarmCoordinator, Worker fan-out/fan-in |
| **Security** | API authentication, Rate limiting, HTTPS enforcement |
| **Expansion** | Multi-modal input, AR interface, Federation |

---

*End of Part XII*

**Updated:** January 30, 2026 (v3.0 Audit)
