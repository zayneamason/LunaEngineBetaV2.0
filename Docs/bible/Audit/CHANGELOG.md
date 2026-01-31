# Luna Engine Bible Changelog

**Tracking all Bible documentation changes**

---

## [2026-01-25] Bible Audit & Update v2.0

### Summary

Comprehensive 4-phase audit and update operation bringing Bible documentation into alignment with Luna Engine v2.0 implementation.

**Overall Accuracy:** 78% → 95%+ (estimated post-update)

---

### Phase 1: Forensic Audit

Created 6 audit documents analyzing codebase reality:

| Document | Key Findings |
|----------|--------------|
| CODEBASE-INVENTORY.md | 51 Python files, 80+ classes, 400+ methods |
| DEPENDENCY-GRAPH.md | NO circular imports, clean layered architecture |
| ACTOR-TRACE.md | 5 actors (not 6): Director, Matrix, Scribe, Librarian, HistoryManager |
| SUBSTRATE-AUDIT.md | 85% complete, FTS5 not implemented |
| ENGINE-LIFECYCLE-AUDIT.md | Three-path heartbeat confirmed, 500ms cognitive tick |
| TEST-COVERAGE.md | 27 test files, 500+ tests, voice tests skipped |

---

### Phase 2: Reconciliation

Created RECONCILIATION.md mapping 140 Bible claims to code:

**Critical Discrepancies Found:**
1. FTS5 NOT implemented (uses LIKE queries)
2. Table names differ: `nodes` → `memory_nodes`, `edges` → `graph_edges`
3. Tag siblings NOT implemented (hardcoded to 0 in lock_in.py)
4. 5 actors (not 6) — ConsciousnessActor removed
5. RevolvingContext has 4 rings (not 3)

---

### Phase 3: Bible Updates

#### Part II - Personas (02-PERSONAS.md)
**Version:** v2.1

Changes:
- Updated Ben Franklin persona with actual extraction behavior
- Updated The Dude persona with entity resolution details
- Added message type tables for each persona
- Corrected extraction output types

#### Part III - Memory Matrix (03-MEMORY-MATRIX.md)
**Version:** v2.2

Changes:
- Corrected table names (`nodes` → `memory_nodes`, `edges` → `graph_edges`)
- Documented FTS5 gap (currently using LIKE queries)
- Updated schema examples to match actual schema.sql
- Added note about sqlite-vec dependency

#### Part IV - Lock-In Coefficient (03A-LOCK-IN-COEFFICIENT.md)
**Version:** v1.0 (NEW CHAPTER)

New chapter created covering:
- Lock-in states (DRIFTING < 0.30 < FLUID < 0.70 < SETTLED)
- Weighted factors formula
- Sigmoid transform (0.15 to 0.85 range)
- Tag siblings TODO documented

#### Part V - The Scribe (04-THE-SCRIBE.md)
**Version:** v2.1

Changes:
- Updated to 11 extraction types (was 8)
- Added: ASSUMPTION, OUTCOME, OBSERVATION, MEMORY
- Documented message types: extract_turn, extract_text, entity_note, flush_stack
- Added SemanticChunker details

#### Part VI - Conversation Tiers (06-CONVERSATION-TIERS.md)
**Version:** v1.0 (NEW CHAPTER)

New chapter documenting three-tier history:
- Active tier (~1000 tokens, 5-10 turns)
- Recent tier (compressed, ~500-1500 tokens)
- Archive tier (extracted to Memory Matrix)
- HistoryManagerActor message types
- Tier rotation process

#### Part VII - Runtime Engine (07-RUNTIME-ENGINE.md)
**Version:** v2.1

Changes:
- Corrected actor count to 5 (was 6)
- Added QueryRouter documentation
- Updated state machine diagram
- Documented RevolvingContext (4 rings)
- Added voice system optional initialization

#### Part VIII - Actor Orchestration (08-ACTOR-ORCHESTRATION.md)
**Version:** v2.1

Changes:
- Removed ConsciousnessActor (not implemented)
- Updated inter-actor message flow
- Added HistoryManagerActor documentation
- Corrected message type tables

#### Part XIV - Agentic Architecture (14-AGENTIC-ARCHITECTURE.md)
**Version:** v2.0

Changes:
- Added RevolvingContext (4 concentric rings)
- Documented AgentLoop with 50 iteration limit
- Added tool registry (file_tools, memory_tools)
- Documented DIRECT vs PLANNED routing paths
- Added complexity threshold (0.6 default)

---

### Phase 4: Infrastructure

Created maintenance infrastructure:

| Document | Purpose |
|----------|---------|
| MAINTENANCE.md | Procedures for keeping Bible synchronized |
| CHANGELOG.md | This file - tracking all changes |
| README.md | Audit directory index and quick reference |

---

## Known Remaining Gaps

| Gap | Severity | Status |
|-----|----------|--------|
| FTS5 not implemented | Medium | Documented, needs code fix |
| Tag siblings hardcoded | Medium | Documented, needs code fix |
| Voice tests skipped | Low | Requires external packages |
| History compression | Medium | Queues exist, not activated |

---

## Prior Changes (Pre-Audit)

### [2026-01-07] Initial Bible Creation
- Part I through Part XIV created
- Based on design specification, not implementation

### [2026-01-13] v2.0 Implementation Start
- Implementation began diverging from spec
- No Bible updates during development

---

## Version History

| Date | Version | Description |
|------|---------|-------------|
| 2026-01-07 | v1.0 | Initial Bible creation |
| 2026-01-25 | v2.0 | Comprehensive audit and update |

---

**End of Changelog**
