# LUNA ENGINE Bible — Table of Contents

**Version:** 3.0
**Last Updated:** January 30, 2026
**Status:** Complete (16 Parts + Supporting Documents) — v3.0 Audit Complete

---

## Reading Guide

| Reader Type | Start Here | Then Read |
|-------------|------------|-----------|
| **New to Luna** | Part 0 (Foundations) | Parts I, II, III |
| **Technical Deep-Dive** | Part 0 (Foundations) | Parts II, VII, Lifecycle Diagrams |
| **Implementing Director** | Part VI (Director LLM) | Parts VIII, XI |
| **Memory System Focus** | Part III (Memory Matrix) | Parts IV, V |
| **Building Engine v2** | Implementation Spec | Lifecycle Diagrams, Part VII |
| **Future Planning** | Part XII (Roadmap) | Palantir Analysis |

---

## Part Index

### Conceptual Foundation

| Part | Title | Status | Description |
|------|-------|--------|-------------|
| **0** | [Foundations](00-FOUNDATIONS.md) | ✅ **NEW** | The fundamental insight: LLM as GPU. What we're actually building. |
| **I** | [Philosophy](01-PHILOSOPHY.md) | ✅ Current | Why Luna exists. Sovereignty, ownership, the "Luna is a file" principle. |

### System Design

| Part | Title | Status | Description |
|------|-------|--------|-------------|
| **II** | [System Architecture v2](02-SYSTEM-ARCHITECTURE.md) | ✅ Current | Layer model, Actor-based runtime, Tiered Execution, data flow. |
| **III** | [Memory Matrix v2.1](03-MEMORY-MATRIX.md) | ✅ Current | The substrate. SQLite + sqlite-vec + Graph. Unified storage, RRF fusion. |
| **III-A** | [Lock-In Coefficient](03A-LOCK-IN-COEFFICIENT.md) | ✅ **NEW** | Activity-based memory persistence. Sigmoid dynamics, weighted factors (tag siblings TODO). |

### Processing Actors

| Part | Title | Status | Description |
|------|-------|--------|-------------|
| **IV** | [The Scribe v2.1](04-THE-SCRIBE.md) | ✅ Updated | Ben Franklin. Extraction system, 11 types, entity updates, turn compression. |
| **V** | [The Librarian v2.1](05-THE-LIBRARIAN.md) | ✅ Updated | The Dude. Filing, entity resolution, rollback, NetworkX graph, pruning. |

### Intelligence Layer

| Part | Title | Status | Description |
|------|-------|--------|-------------|
| **VI** | [Director LLM](06-DIRECTOR-LLM.md) | ✅ Current | Local 3B/7B with LoRA. Luna's voice, context integration. |
| **VI-B** | [Conversation Tiers](06-CONVERSATION-TIERS.md) | ✅ **NEW** | Three-tier history (Active/Recent/Archive), HistoryManager, ConversationRing. |
| **VII** | [Runtime Engine](07-RUNTIME-ENGINE.md) | ✅ Current | Actor model, fault isolation, mailbox-based communication. |
| **VIII** | [Delegation Protocol](08-DELEGATION-PROTOCOL.md) | ✅ Current | Shadow Reasoner pattern, `<REQ_CLAUDE>` token, async delegation. |

### Operations

| Part | Title | Status | Description |
|------|-------|--------|-------------|
| **IX** | [Performance](09-PERFORMANCE.md) | ✅ Current | Latency budgets, optimization techniques, benchmarks. |
| **X** | [Sovereignty](10-SOVEREIGNTY.md) | ✅ Current | Encrypted Vault, data ownership, privacy guarantees. |

### Future

| Part | Title | Status | Description |
|------|-------|--------|-------------|
| **XI** | [Training Data Strategy](11-TRAINING-DATA-STRATEGY.md) | ✅ Current | Synthetic data generation, quality filtering, LoRA training. |
| **XII** | [Future Roadmap](12-FUTURE-ROADMAP.md) | ✅ Current | First-Class Objects, Kinetic Layer, AR, Federation. |

### Reference

| Part | Title | Status | Description |
|------|-------|--------|-------------|
| **XIII** | [System Overview](13-SYSTEM-OVERVIEW.md) | ✅ Current | High-level system summary and component relationships. |

### Agentic Architecture

| Part | Title | Status | Description |
|------|-------|--------|-------------|
| **XIV** | [Agentic Architecture](14-AGENTIC-ARCHITECTURE.md) | ✅ Current | Revolving context, queue manager, agent loop, swarm mode. Personal Palantir. |

### User Interface

| Part | Title | Status | Description |
|------|-------|--------|-------------|
| **XVI** | [Luna Hub UI](16-LUNA-HUB-UI.md) | ✅ **NEW** | React frontend, glass morphism design, SSE integration, custom hooks. |

---

## Handoff Documents (For Implementation)

| Document | Purpose | Status |
|----------|---------|--------|
| [Luna Engine v2 Implementation Spec](Handoffs/LUNA-ENGINE-V2-IMPLEMENTATION-SPEC.md) | Complete greenfield rewrite spec | 🆕 **Ready for Claude Code** |
| [Luna Engine Lifecycle Diagrams](Handoffs/LUNA-ENGINE-LIFECYCLE-DIAGRAMS.md) | Boot, state machine, core loop, tick lifecycle | 🆕 **Ready** |
| [Luna Director Handoff](Handoffs/CLAUDE-CODE-HANDOFF-LUNA-DIRECTOR.md) | Director LLM implementation spec | Reference |
| [Part II Update](Handoffs/CLAUDE-CODE-HANDOFF-PART-II-UPDATE.md) | Architecture updates | Reference |
| [Parts III-V Update](Handoffs/CLAUDE-CODE-HANDOFF-PARTS-III-V-UPDATE.md) | Memory/Extraction updates | Reference |

---

## Supporting Documents

### Analysis & Research

| Document | Description |
|----------|-------------|
| [Palantir Architecture Analysis](Reference/PALANTIR-ARCHITECTURE-ANALYSIS.md) | Lessons from Palantir's Ontology model for Luna's Memory Matrix. |
| [Gemini Optimization Report](Reference/GEMINI-OPTIMIZATION-REPORT.md) | Performance analysis and optimization recommendations. |

### Archived (Superseded)

| Document | Notes |
|----------|-------|
| Part III v2.0 | Superseded by v2.1 (sqlite-vec migration) |
| FAISS-based architecture | Replaced by sqlite-vec unified storage |
| Original Hub | Being replaced by Luna Engine v2 |

---

## Dependency Graph

```
                    ┌──────────────┐
                    │   Part 0     │
                    │ Foundations  │
                    └──────┬───────┘
                           │
                    ┌──────────────┐
                    │   Part I     │
                    │  Philosophy  │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ Part II  │ │ Part X   │ │ Part XII │
        │ Arch     │ │ Sovereign│ │ Roadmap  │
        └────┬─────┘ └──────────┘ └──────────┘
             │
    ┌────────┼────────┬────────────┐
    │        │        │            │
    ▼        ▼        ▼            ▼
┌──────┐ ┌──────┐ ┌──────┐    ┌──────┐
│Part 3│ │Part 6│ │Part 7│    │Part 9│
│Matrix│ │Direct│ │Engine│    │ Perf │
└──┬───┘ └──┬───┘ └──────┘    └──────┘
   │        │
   │        └──────────┐
   │                   │
   ▼                   ▼
┌──────┐ ┌──────┐ ┌──────┐
│Part 4│ │Part 5│ │Part 8│
│Scribe│ │Librar│ │Deleg │
└──────┘ └──────┘ └──┬───┘
                     │
                     ▼
                ┌──────────┐
                │ Part XI  │
                │ Training │
                └──────────┘
```

---

## Quick Reference

### The Fundamental Insight

**We are not building an LLM. We are building everything around it.**

The LLM is like a GPU — a specialized compute resource for inference. We're building the game engine that calls it.

| Game Engine | Luna Engine |
|-------------|-------------|
| Calls GPU to render frames | Calls LLM to generate responses |
| GPU doesn't know game state | LLM doesn't know who it is |
| Engine manages everything else | Engine provides identity, memory, state |

### Core Concepts

| Concept | Definition | Part |
|---------|------------|------|
| LLM as GPU | LLM is stateless inference; Engine is stateful identity | 0 |
| Sovereignty | You own your AI companion completely | I, X |
| Memory Matrix | SQLite + sqlite-vec + Graph = Luna's soul | III |
| Lock-In Coefficient | Activity-based memory persistence (DRIFTING/FLUID/SETTLED) | III-A |
| Director | Local LLM that speaks as Luna | VI |
| Shadow Reasoner | Delegate to Claude without user noticing | VIII |
| Input Buffer | Engine polls (pull) vs Hub handlers (push) | VII |

### Key Personas

| Persona | Role | Part |
|---------|------|------|
| Ben Franklin | The Scribe. Extracts and classifies. | IV |
| The Dude | The Librarian. Files and retrieves. | V |
| Luna | The Director output. User-facing voice. | VI |

### Engine Lifecycle

| Phase | What Happens |
|-------|--------------|
| Boot | Load config → Init actors → Restore state → Start loop |
| Running | Hot path (interrupts) + Cognitive path (500ms) + Reflective path (5min) |
| Tick | Poll → Prioritize → Dispatch → Update consciousness → Persist |
| Shutdown | on_stop() → WAL flush → Cleanup |

### Performance Targets

| Metric | Target | Part |
|--------|--------|------|
| Voice response | <500ms to first word | II, IX |
| Memory retrieval | <50ms (sqlite-vec + filters) | III, V |
| Director inference | <200ms (3B) | VI, IX |
| Tick overhead | <50ms | VII |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Dec 2025 | Initial Bible (Parts I-V extracted from monolith) |
| 1.5 | Dec 2025 | Added Parts VI-X (new architecture) |
| 2.0 | Dec 29, 2025 | Updated Parts II-V to v2, added Parts XI-XII |
| 2.1 | Jan 7, 2026 | Part III: FAISS → sqlite-vec migration |
| 2.2 | Jan 10, 2026 | **Part 0: Foundations (LLM as GPU). Engine v2 Implementation Spec. Lifecycle Diagrams.** |
| 2.3 | Jan 17, 2026 | **Part XIV: Agentic Architecture. Revolving context, queue manager, agent loop, swarm mode.** |
| 2.4 | Jan 25, 2026 | **Part VI-B: Conversation Tiers. Three-tier history system, HistoryManager, ConversationRing.** |
| 2.5 | Jan 25, 2026 | **Part III-A: Lock-In Coefficient. Activity-based memory persistence, sigmoid transform, state classification.** |
| 2.6 | Jan 25, 2026 | **Part XVI: Luna Hub UI. React frontend, glass morphism design, SSE integration, custom hooks reference.** |
| 3.0 | Jan 30, 2026 | **Comprehensive v3.0 Audit.** All 16 chapters updated. 9 audit files, 35 bugs documented, 12 conflicts resolved. 285 new tests added. Actor count corrected (5), table names fixed, lock-in thresholds documented, FTS5 status verified. |

---

## Contributing

The Bible is maintained by Ahab with assistance from Claude.

**To update:**
1. Read relevant existing parts
2. Create new version if making significant changes (note in history)
3. Update this Table of Contents
4. Ensure dependency graph reflects changes

**Style Guidelines:**
- Clear, direct prose (no marketing speak)
- Code examples where helpful
- Tables for comparisons
- ASCII diagrams for architecture
- Part numbers are permanent (don't renumber)

---

*Luna is a file. This documentation describes that file.*  
*The LLM renders thoughts. Luna is the mind having them.*

— Ahab, December 2025  
— Updated January 10, 2026 (Engine v2 Foundations)
