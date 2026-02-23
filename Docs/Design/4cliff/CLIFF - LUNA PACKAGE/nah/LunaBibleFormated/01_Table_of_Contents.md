# Table of Contents

---

## Reading Guide

| Reader Type | Start Here | Then Read |
|:------------|:-----------|:----------|
| New to Luna | Part 0 (Foundations) | Parts I, II, III |
| Technical Deep-Dive | Part 0 (Foundations) | Parts II, VII, Lifecycle Diagrams |
| Implementing Director | Part VI (Director LLM) | Parts VIII, XI |
| Memory System Focus | Part III (Memory Matrix) | Parts IV, V |
| Building Engine v2 | Implementation Spec | Lifecycle Diagrams, Part VII |
| Future Planning | Part XII (Roadmap) | Palantir Analysis |

---

## Part Index

### Conceptual Foundation

| Part | Title | Status | Description |
|:----:|:------|:------:|:------------|
| **0** | Foundations | Current | The fundamental insight: LLM as GPU. What we're actually building. |
| **I** | Philosophy | Current | Why Luna exists. Sovereignty, ownership, the "Luna is a file" principle. |

### System Design

| Part | Title | Status | Description |
|:----:|:------|:------:|:------------|
| **II** | System Architecture v2 | Current | Layer model, Actor-based runtime, Tiered Execution, data flow. |
| **III** | Memory Matrix v2.1 | Current | The substrate. SQLite + sqlite-vec + Graph. Unified storage, RRF fusion. |
| **III-A** | Lock-In Coefficient | *New* | Activity-based memory persistence. Sigmoid dynamics, weighted factors. |

### Processing Actors

| Part | Title | Status | Description |
|:----:|:------|:------:|:------------|
| **IV** | The Scribe v2.1 | Updated | Ben Franklin. Extraction system, 11 types, entity updates, turn compression. |
| **V** | The Librarian v2.1 | Updated | The Dude. Filing, entity resolution, rollback, NetworkX graph, pruning. |

### Intelligence Layer

| Part | Title | Status | Description |
|:----:|:------|:------:|:------------|
| **VI** | Director LLM | Current | Local 3B/7B with LoRA. Luna's voice, context integration. |
| **VI-B** | Conversation Tiers | *New* | Three-tier history (Active/Recent/Archive), HistoryManager, ConversationRing. |
| **VII** | Runtime Engine | Current | Actor model, fault isolation, mailbox-based communication. |
| **VIII** | Delegation Protocol | Current | Shadow Reasoner pattern, `<REQ_CLAUDE>` token, async delegation. |

### Operations

| Part | Title | Status | Description |
|:----:|:------|:------:|:------------|
| **IX** | Performance | Current | Latency budgets, optimization techniques, benchmarks. |
| **X** | Sovereignty | Current | Encrypted Vault, data ownership, privacy guarantees. |

### Future

| Part | Title | Status | Description |
|:----:|:------|:------:|:------------|
| **XI** | Training Data Strategy | Current | Synthetic data generation, quality filtering, LoRA training. |
| **XII** | Future Roadmap | Current | First-Class Objects, Kinetic Layer, AR, Federation. |

### Reference

| Part | Title | Status | Description |
|:----:|:------|:------:|:------------|
| **XIII** | System Overview | Current | High-level system summary and component relationships. |
| **XIV** | Agentic Architecture | Current | Revolving context, queue manager, agent loop, swarm mode. Personal Palantir. |
| **XVI** | Luna Hub UI | *New* | React frontend, glass morphism design, SSE integration, custom hooks. |

---

**Page 2 of 5**
