# Palantir Architecture Analysis: Lessons for Luna

**Date:** December 29, 2025  
**Source:** Gemini analysis of Palantir Foundry/Gotham/AIP  
**Purpose:** Validate Luna architecture, identify upgrade paths

> ⚠️ **Historical Note (Jan 2026):** This document references FAISS for vector storage. As of v2.1, Luna uses **sqlite-vec** for unified storage (vectors in SQLite). The architectural patterns and analysis remain valid.

---

## The Core Insight

> "Palantir's 'Ontology' is just a massive, enterprise-grade version of your Memory Matrix."

Palantir isn't building apps. They're building a **semantic substrate** that apps sit on top of. This is exactly what Luna's Memory Matrix should be.

---

## Pattern Mapping

| Palantir Concept | Luna Equivalent | Gap Analysis |
|------------------|-----------------|--------------|
| Dynamic Ontology | Memory Matrix (SQLite + NetworkX + sqlite-vec) | Luna's nodes are still "text chunks" — need First-Class Objects |
| Objects (Flight, Pilot, etc.) | Nodes (FACT, DECISION, PERSON) | Luna needs richer object schemas with behaviors |
| Semantic Layer | Graph relationships | ✅ Aligned |
| Kinetic Layer (Write-Back) | ❌ Missing | Luna is read-only — can't trigger external actions |
| Apollo (Deployment) | Sovereignty Infrastructure | ✅ Aligned — local-first, portable, air-gapped capable |
| AIP (LLM + Ontology) | Director LLM + Memory Matrix | ✅ Aligned — LLM anchored to data, not hallucinating |
| OSDK (Ontology SDK) | MCP Tools | Luna's MCP tools query Matrix — similar pattern |
| Gaia (Object Store) | SQLite + sqlite-vec | Same concept, different scale |

---

## The Three Layers

### 1. Semantic Layer (Luna Has This)

Instead of raw text, users interact with **Objects**:

```
Palantir: "Flight 202" → linked to Pilot, Fuel, Destination
Luna: "Project Luna" → linked to Ahab, Mars College, Sovereignty goals
```

Luna's Memory Matrix already does this with typed nodes and edges. The graph IS the semantic layer.

### 2. Kinetic Layer (Luna Needs This)

> "Most AI systems are 'Read-Only'. Palantir allows 'Write-Back'."

Current Luna:
- Can query memories ✅
- Can store memories ✅
- Can trigger Claude delegation ✅
- **Cannot trigger external actions** ❌

Future Luna with Kinetic Layer:
- "Create a task in Todoist for this decision"
- "Send this summary to Obsidian"
- "Trigger the backup script"
- "Post this to my private API"

This is the **Oven Actor** extended — not just Claude delegation, but action execution.

### 3. Deployment Layer (Luna Has This)

Apollo's "run anywhere" philosophy = Luna's Sovereignty Infrastructure:

| Apollo | Luna |
|--------|------|
| Public cloud | ❌ Never |
| Private on-prem | ✅ Your Mac |
| Air-gapped tactical edge | ✅ Encrypted vault, offline-capable |
| Autonomous deployment | ✅ Portable sparse bundle |

Luna is actually MORE sovereign than Palantir here — Palantir still runs on customer infrastructure with Palantir control. Luna runs on YOUR infrastructure with YOUR control.

---

## The Big Lesson

> "Decouple the Data from the Use-Case."

Palantir doesn't build a "Supply Chain App" — they build a "Supply Chain Ontology" and let users build 100 apps on top.

**Luna implication:**

Don't build "Voice Luna" and "Desktop Luna" as separate apps. Build the **Memory Matrix as a platform**, then Voice/Desktop/MCP are just interfaces.

```
Current Architecture:
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│    Voice    │  │   Desktop   │  │     MCP     │
│    Luna     │  │    Luna     │  │    Luna     │
└──────┬──────┘  └──────┬──────┘  └──────┬──────┘
       │                │                │
       └────────────────┼────────────────┘
                        │
                        ▼
               ┌─────────────────┐
               │  Memory Matrix  │
               │   (Substrate)   │
               └─────────────────┘

This is correct! The Matrix is the platform.
Apps are just views into it.
```

---

## The Object Schema Upgrade

### Current Luna Node Schema

```python
@dataclass
class MemoryNode:
    id: str
    node_type: str  # "FACT", "DECISION", "PERSON", etc.
    content: str    # Just text
    embedding: np.ndarray
    created_at: datetime
    tags: list[str]
    metadata: dict
```

**Problem:** `content` is just text. The node doesn't "know" anything about itself.

### Proposed First-Class Object Schema

```python
from abc import ABC, abstractmethod

class LunaObject(ABC):
    """Base class for all first-class objects in Luna's ontology."""
    id: str
    created_at: datetime
    updated_at: datetime
    source: str  # Where this came from
    confidence: float  # How certain are we
    
    @abstractmethod
    def summarize(self) -> str:
        """Human-readable summary."""
        pass
    
    @abstractmethod
    def get_related(self) -> list['LunaObject']:
        """Get semantically related objects."""
        pass

@dataclass
class Person(LunaObject):
    name: str
    relationship: str  # "creator", "collaborator", "mentioned"
    contact: Optional[str]
    first_mentioned: datetime
    last_mentioned: datetime
    interaction_count: int
    
    # Behaviors
    def get_conversations(self) -> list['Conversation']:
        """All conversations involving this person."""
        pass
    
    def get_decisions(self) -> list['Decision']:
        """Decisions this person was involved in."""
        pass

@dataclass
class Project(LunaObject):
    name: str
    status: str  # "active", "paused", "completed", "abandoned"
    started: datetime
    goals: list[str]
    technologies: list[str]
    
    # Relationships
    people: list[Person]
    decisions: list['Decision']
    documents: list['Document']
    
    # Behaviors
    def get_timeline(self) -> list['Event']:
        """Chronological events in this project."""
        pass
    
    def get_open_questions(self) -> list['Question']:
        """Unresolved questions about this project."""
        pass

@dataclass
class Decision(LunaObject):
    title: str
    choice: str  # What was decided
    alternatives: list[str]  # What was considered
    rationale: str  # Why this choice
    made_by: list[Person]
    made_at: datetime
    superseded_by: Optional['Decision']
    
    # Behaviors
    def get_consequences(self) -> list['Event']:
        """What happened as a result of this decision."""
        pass
    
    def is_still_valid(self) -> bool:
        """Has this been superseded?"""
        return self.superseded_by is None

@dataclass
class Insight(LunaObject):
    content: str
    derived_from: list[LunaObject]  # What led to this insight
    confidence: float
    validated: bool
    
    # Behaviors
    def get_supporting_evidence(self) -> list[LunaObject]:
        """Objects that support this insight."""
        pass

@dataclass
class Event(LunaObject):
    description: str
    occurred_at: datetime
    participants: list[Person]
    location: Optional[str]
    caused_by: Optional[LunaObject]
    resulted_in: list[LunaObject]
```

### Why This Matters

| Text Chunks | First-Class Objects |
|-------------|---------------------|
| "We decided to use Actor model" | `Decision(choice="Actor model", alternatives=["MonoBehaviour", "Event-driven"], rationale="Fault isolation")` |
| "Talked to Gemini about optimization" | `Person(name="Gemini", relationship="collaborator").get_conversations()` |
| "Luna project started Dec 2025" | `Project(name="Luna", started=...).get_timeline()` |

The object knows things. It has behaviors. It can answer questions about itself.

---

## The Kinetic Layer Design

### Action Objects

```python
@dataclass
class Action(LunaObject):
    """An action Luna can take in the world."""
    name: str
    target_system: str  # "todoist", "obsidian", "filesystem", "api"
    parameters: dict
    requires_confirmation: bool
    executed_at: Optional[datetime]
    result: Optional[str]
    
    async def execute(self) -> ActionResult:
        """Execute the action via the appropriate adapter."""
        adapter = get_adapter(self.target_system)
        return await adapter.execute(self.parameters)

@dataclass
class ActionAdapter(ABC):
    """Adapter for external system integration."""
    
    @abstractmethod
    async def execute(self, params: dict) -> ActionResult:
        pass
    
    @abstractmethod
    def validate(self, params: dict) -> bool:
        pass

class TodoistAdapter(ActionAdapter):
    async def execute(self, params: dict) -> ActionResult:
        # Create task via Todoist API
        pass

class ObsidianAdapter(ActionAdapter):
    async def execute(self, params: dict) -> ActionResult:
        # Write to Obsidian vault
        pass

class FilesystemAdapter(ActionAdapter):
    async def execute(self, params: dict) -> ActionResult:
        # File operations within vault
        pass
```

### Governed Actions

Like Palantir's AIP, Luna should have **guardrails**:

```python
@dataclass
class ActionGovernance:
    """Rules for what Luna can do autonomously."""
    
    # Actions that require human confirmation
    requires_confirmation: list[str] = [
        "delete_*",
        "send_*",
        "post_*",
        "execute_*"
    ]
    
    # Actions Luna can do autonomously
    autonomous: list[str] = [
        "create_note",
        "update_memory",
        "backup_*"
    ]
    
    # Actions Luna should never do
    forbidden: list[str] = [
        "network_request_*",  # Unless to approved hosts
        "system_command_*"
    ]
```

---

## Implementation Priority

### Phase 1: Object Schema (Next)
- Define First-Class Objects for Luna's domain
- Migrate existing nodes to typed objects
- Add object behaviors (methods, not just data)

### Phase 2: Object SDK (After)
- Like Palantir's OSDK
- Director LLM queries objects, not raw text
- Objects return structured data, not strings

### Phase 3: Kinetic Layer (Future)
- Action objects and adapters
- Governance rules
- Write-back to external systems

---

## The Meta-Insight

Palantir's $50B valuation comes from one thing:

> **They made data legible to decision-makers.**

The CEO and the data scientist see the same "Flight 202" object. They speak the same language.

Luna's version:

> **Make your life legible to yourself.**

Past-you and present-you see the same "Project Luna" object. You speak the same language across time.

That's the real value of the Memory Matrix as a semantic substrate.

---

*This analysis should inform the next phase of Bible development and implementation planning.*
