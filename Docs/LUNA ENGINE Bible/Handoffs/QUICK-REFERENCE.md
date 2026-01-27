# Luna Engine v2.0 Quick Reference

**Version:** 2.0 | **Updated:** January 25, 2026

---

## One-Page Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        LUNA ENGINE                               │
│                                                                  │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │ InputBuffer │───▶│  Engine     │───▶│  Response   │         │
│  │ (Queue)     │    │  (Tick)     │    │  (Output)   │         │
│  └─────────────┘    └──────┬──────┘    └─────────────┘         │
│                            │                                     │
│         ┌──────────────────┼──────────────────┐                 │
│         ▼                  ▼                  ▼                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │  Director   │    │   Matrix    │    │  Scribe     │         │
│  │  (LLM)      │    │  (Memory)   │    │  (Extract)  │         │
│  └─────────────┘    └─────────────┘    └─────────────┘         │
│         │                  │                  │                 │
│         │           ┌──────┴──────┐           │                 │
│         │           ▼             ▼           ▼                 │
│         │    ┌───────────┐ ┌───────────┐ ┌───────────┐         │
│         │    │  SQLite   │ │ NetworkX  │ │ Librarian │         │
│         │    │  (Store)  │ │  (Graph)  │ │  (File)   │         │
│         │    └───────────┘ └───────────┘ └───────────┘         │
│         │                                                       │
│         └───────────────────┐                                   │
│                             ▼                                   │
│                      ┌─────────────┐                           │
│                      │ HistoryMgr  │                           │
│                      │  (Tiers)    │                           │
│                      └─────────────┘                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Core Numbers

| Metric | Value |
|--------|-------|
| Python Files | 51 |
| Classes | 80+ |
| Actors | 5 |
| Test Files | 27 |
| Cognitive Tick | 500ms |
| Reflective Tick | 5 minutes |
| Context Rings | 4 |
| Lock-In Range | 0.15–0.85 |

---

## The 5 Actors

| Actor | File | Purpose | Key Message |
|-------|------|---------|-------------|
| **Director** | director.py | LLM inference | `generate` |
| **Matrix** | matrix.py | Memory storage | `store`, `retrieve` |
| **Scribe** | scribe.py | Knowledge extraction | `extract_turn` |
| **Librarian** | librarian.py | Entity resolution | `file`, `resolve_entity` |
| **HistoryManager** | history_manager.py | Conversation tiers | `add_turn` |

---

## Three-Path Heartbeat

```
COGNITIVE (500ms)     REFLECTIVE (5min)     ACTORS (async)
     │                      │                    │
     ├─ poll_all()          ├─ decay_all()       ├─ mailbox.get()
     ├─ dispatch()          ├─ prune()           ├─ handle()
     ├─ consciousness.tick()└─ consolidate()     └─ continue
     └─ sleep(0.5)
```

---

## Memory Architecture

### Database Tables
- `memory_nodes` - Core knowledge storage
- `graph_edges` - Relationships between nodes
- `conversation_turns` - Three-tier history
- `entities` - People, places, projects
- `entity_relationships` - Entity connections

### Lock-In States
```
DRIFTING (< 0.30) → FLUID (0.30-0.70) → SETTLED (> 0.70)
```

### Three-Tier History
```
Active (5-10 turns, ~1000 tokens)
    ↓ rotate
Recent (compressed, ~500-1500 tokens)
    ↓ archive
Memory Matrix (permanent)
```

---

## Context System

### RevolvingContext (4 Rings)
```
CORE (identity, 800 tokens) - never decays
    └─ INNER (memory, 1200 tokens) - slow decay
        └─ MIDDLE (conversation, 1500 tokens) - medium decay
            └─ OUTER (retrieved, 4500 tokens) - fast decay
```

### Token Budget: 8000 total

---

## Routing Decision

```
User Input → QueryRouter.analyze()
                │
        ┌───────┴───────┐
        ▼               ▼
    DIRECT          PLANNED
   (simple)        (complex)
        │               │
        ▼               ▼
  LocalInference   AgentLoop
  or Claude        → Planner
                   → Director
```

**Delegation Signals:**
- Temporal: "current", "latest", "today"
- Research: "search", "look up", "find"
- Code: "write code", "function"
- Memory: "remember when", "what did we"

---

## Key File Locations

| Component | Path |
|-----------|------|
| Engine | src/luna/engine.py |
| Actors | src/luna/actors/*.py |
| Memory | src/luna/substrate/*.py |
| Schema | src/luna/substrate/schema.sql |
| Context | src/luna/core/context.py |
| Agentic | src/luna/agentic/*.py |
| Tests | tests/*.py |

---

## State Machine

```
STARTING → RUNNING → STOPPED
              │
              ├─→ PAUSED
              └─→ SLEEPING
```

---

## Quick Commands

```bash
# Run Luna
python scripts/run.py

# Run tests
pytest tests/

# Check actor count
grep -l "class.*Actor" src/luna/actors/*.py | wc -l

# Check schema
cat src/luna/substrate/schema.sql | head -50

# Find message types
grep -r "msg.type ==" src/luna/actors/
```

---

## Critical Gaps (Known)

| Gap | Impact | Location |
|-----|--------|----------|
| FTS5 not implemented | Slower search | substrate/memory.py |
| Tag siblings hardcoded | 10% lock-in weight | substrate/lock_in.py |
| Voice tests skipped | Untested voice mode | tests/test_voice.py |

---

## Bible Chapters

| Part | Topic | Version |
|------|-------|---------|
| II | Personas (Ben, Dude) | v2.1 |
| III | Memory Matrix | v2.2 |
| IV | Lock-In Coefficient | v1.0 |
| V | The Scribe | v2.1 |
| VI | Conversation Tiers | v1.0 |
| VII | Runtime Engine | v2.1 |
| VIII | Actor Orchestration | v2.1 |
| XIV | Agentic Architecture | v2.0 |

---

## Audit Execution

This reference was created by a comprehensive 4-phase audit operation:

```bash
# Phase 1: Forensic Audit (6 parallel agents)
# Phase 2: Bible-Code Reconciliation
# Phase 3: Bible Updates (8 parallel agents)
# Phase 4: Infrastructure creation
```

**Success Criteria (All Met):**
- [x] Every code reference points to real file
- [x] Architecture claims match implementation
- [x] Clear "Implemented" vs "Planned" markers
- [x] Maintenance protocol documented
- [x] Changelog captures all changes

---

**See Also:**
- [Audit/README.md](../Audit/README.md) - Full audit results
- [Audit/RECONCILIATION.md](../Audit/RECONCILIATION.md) - Bible vs code mapping
- [Audit/MAINTENANCE.md](../Audit/MAINTENANCE.md) - Update procedures
