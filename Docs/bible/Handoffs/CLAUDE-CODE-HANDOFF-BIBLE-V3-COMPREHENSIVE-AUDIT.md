# CLAUDE CODE HANDOFF: Luna Bible v3.0 Comprehensive Audit

**Created:** January 30, 2026
**Author:** Ahab (via Claude Architect)
**Execution Mode:** Claude Flow Swarm + Hive
**Priority:** High
**Status:** 🔵 READY FOR EXECUTION

---

## Executive Summary

This handoff specifies a **6-phase comprehensive audit** of the Luna Engine codebase and Bible documentation. The goal is to bring the Bible from v2.6 to v3.0 with:

- Complete codebase reconciliation
- Expanded test coverage (unit, smoke, integration, tracer)
- Bug registry with severity analysis
- Folder reorganization for maintainability
- All 16 Bible chapters updated to reflect implementation reality

**Estimated Wall-Clock Time:** 6-8 hours with parallelization

---

## Table of Contents

1. [Phase Overview](#phase-overview)
2. [Phase 1: Codebase Audit](#phase-1-codebase-audit-swarm-mode)
3. [Phase 2: Test Expansion](#phase-2-test-expansion-hive-mode)
4. [Phase 3: Bug Analysis](#phase-3-bug-analysis-sequential)
5. [Phase 4: Folder Reorganization](#phase-4-folder-reorganization-sequential)
6. [Phase 5: Bible Update](#phase-5-bible-update-swarm-mode)
7. [Phase 6: Validation](#phase-6-validation-sequential)
8. [Claude Flow Patterns](#claude-flow-patterns)
9. [Test Categories & Patterns](#test-categories--patterns)
10. [Bug Analysis Framework](#bug-analysis-framework)
11. [Folder Reorganization Spec](#folder-reorganization-spec)
12. [Documentation Standards](#documentation-standards)
13. [Execution Instructions](#execution-instructions)
14. [Success Criteria](#success-criteria)
15. [Appendix: Quick Reference](#appendix-quick-reference)

---

## Phase Overview

| Phase | Mode | Agents | Outputs |
|-------|------|--------|---------|
| 1. Codebase Audit | Swarm (parallel) | 6 + 3 sequential | AUDIT-*.md (9 files) |
| 2. Test Expansion | Hive (coordinated) | 1 lead + 4 workers | tests/{unit,smoke,integration,tracers}/ |
| 3. Bug Analysis | Sequential | 1 deep agent | BUG-REGISTRY.md, CONFLICTS.md |
| 4. Folder Reorganization | Sequential | 1 agent | MIGRATION-PLAN.md, execute migration |
| 5. Bible Update | Swarm (parallel) | 8 agents | All 16 Bible parts → v3.0 |
| 6. Validation | Sequential | 1 agent | BIBLE-VALIDATION-REPORT.md |

---

## Phase 1: Codebase Audit (Swarm Mode)

**Config File:** `.swarm/phase1-codebase-audit.yaml`

### Parallel Agents (Run Simultaneously)

#### Agent 1.1: Module Auditor
**Target:** `src/luna/**/*.py`
**Output:** `Docs/LUNA ENGINE Bible/Audit/AUDIT-MODULES.md`

```yaml
tasks:
  - Inventory all Python files (count: expected 55+)
  - Map all classes with inheritance hierarchy
  - Document all public methods with signatures
  - Identify deprecated or dead code
  - Flag files over 500 lines for review
```

#### Agent 1.2: Actor System Tracer
**Target:** `src/luna/actors/`
**Output:** `Docs/LUNA ENGINE Bible/Audit/AUDIT-ACTORS.md`

```yaml
tasks:
  - Trace all 5 actors: Director, Matrix, Scribe, Librarian, HistoryManager
  - Document message types (send/receive)
  - Map inter-actor communication flows
  - Verify mailbox isolation patterns
  - Check for blocking calls in async paths
```

#### Agent 1.3: Memory Substrate Auditor
**Target:** `src/luna/substrate/`, `src/luna/memory/`
**Output:** `Docs/LUNA ENGINE Bible/Audit/AUDIT-MEMORY.md`

```yaml
tasks:
  - Verify SQLite schema matches schema.sql
  - Audit sqlite-vec integration (embeddings.py)
  - Trace memory operations (store, retrieve, search)
  - Document lock-in coefficient implementation
  - Check for N+1 query patterns
  - Audit memory economy integration if present
```

#### Agent 1.4: API & Service Auditor
**Target:** `src/luna/api/`, `src/luna/services/`
**Output:** `Docs/LUNA ENGINE Bible/Audit/AUDIT-API.md`

```yaml
tasks:
  - Map all FastAPI endpoints with request/response schemas
  - Document SSE/WebSocket implementations
  - Trace request → engine → response flow
  - Identify missing error handling
  - Audit rate limiting and auth if present
```

#### Agent 1.5: Inference Auditor
**Target:** `src/luna/inference/`, `src/luna/llm/`
**Output:** `Docs/LUNA ENGINE Bible/Audit/AUDIT-INFERENCE.md`

```yaml
tasks:
  - Document local inference (MLX, Qwen)
  - Map Claude delegation protocol
  - Trace LLM provider routing
  - Verify fallback chains
  - Document token counting and budget management
```

#### Agent 1.6: Frontend Auditor
**Target:** `frontend/src/`
**Output:** `Docs/LUNA ENGINE Bible/Audit/AUDIT-FRONTEND.md`

```yaml
tasks:
  - Map React component hierarchy
  - Document custom hooks (useChat, useOrbState, etc.)
  - Trace state management patterns
  - Audit SSE integration points
  - Check for memory leaks in subscriptions
```

### Sequential Agents (Run After Parallel)

#### Agent 1.7: Dependency Mapper
**Depends On:** Agents 1.1-1.6
**Output:** `Docs/LUNA ENGINE Bible/Audit/AUDIT-DEPENDENCIES.md`

```yaml
tasks:
  - Build import graph from all modules
  - Detect circular import risks
  - Map optional dependency fallbacks
  - Document external package versions
  - Compare pyproject.toml with actual usage
```

#### Agent 1.8: Test Inventory
**Target:** `tests/`
**Output:** `Docs/LUNA ENGINE Bible/Audit/AUDIT-TEST-INVENTORY.md`

```yaml
tasks:
  - Count test files and functions
  - Map test coverage by module
  - Identify untested code paths
  - List skipped tests and reasons
  - Categorize tests (unit, integration, e2e)
```

#### Agent 1.9: Config Auditor
**Target:** `config/`, `*.json`, `*.yaml`
**Output:** `Docs/LUNA ENGINE Bible/Audit/AUDIT-CONFIG.md`

```yaml
tasks:
  - Inventory all config files
  - Document schema for each config
  - Check for hardcoded secrets
  - Map environment variable usage
  - Identify deprecated config keys
```

---

## Phase 2: Test Expansion (Hive Mode)

**Config File:** `.swarm/phase2-test-expansion.yaml`

### Hive Topology

```
                   ┌─────────────────┐
                   │   Lead Agent    │
                   │  (Coordinator)  │
                   └────────┬────────┘
                            │
          ┌─────────────────┼─────────────────┐
          │                 │                 │
    ┌─────▼─────┐    ┌─────▼─────┐    ┌─────▼─────┐
    │  Worker 1  │    │  Worker 2  │    │  Worker 3  │
    │   (Unit)   │    │  (Smoke)   │    │ (Integr)  │
    └────────────┘    └────────────┘    └────────────┘
                            │
                      ┌─────▼─────┐
                      │  Worker 4  │
                      │ (Tracers)  │
                      └────────────┘
```

### Lead Agent Tasks

```yaml
role: Test expansion coordinator
tasks:
  - Read AUDIT-TEST-INVENTORY.md to understand gaps
  - Assign coverage targets to workers
  - Coordinate shared fixtures in conftest.py
  - Merge worker outputs into coherent suite
  - Validate no test conflicts or duplicates
outputs:
  - tests/conftest.py (updated)
  - TEST-EXPANSION-REPORT.md
```

### Worker 1: Unit Tests
**Output:** `tests/unit/`

```yaml
target_coverage: 85%
tasks:
  - Create tests/unit/__init__.py
  - Write unit tests for all actors (1 file per actor)
  - Test memory operations in isolation
  - Test lock-in coefficient calculations
  - Test context pipeline stages
patterns:
  - One test file per module
  - Mock external dependencies
  - Fast execution (<1s per test)
  - No database access
```

### Worker 2: Smoke Tests
**Output:** `tests/smoke/`

```yaml
purpose: Verify critical paths work end-to-end
tasks:
  - Create tests/smoke/__init__.py
  - test_engine_boots.py - Engine starts without error
  - test_memory_stores.py - Can store and retrieve memory
  - test_chat_responds.py - Chat endpoint returns response
  - test_websocket_connects.py - WebSocket establishes connection
patterns:
  - Use real database (in-memory or temp)
  - No mocking of internal components
  - Timeout after 10s
  - Self-cleanup after each test
```

### Worker 3: Integration Tests
**Output:** `tests/integration/`

```yaml
purpose: Verify component interactions
tasks:
  - Create tests/integration/__init__.py
  - test_director_delegates.py - Director → Claude delegation
  - test_scribe_extracts.py - Scribe → Memory pipeline
  - test_librarian_retrieves.py - Librarian → Vector search
  - test_history_tiers.py - History tier transitions
patterns:
  - Use real components, mock external APIs
  - Test message passing between actors
  - Verify event ordering
  - Check for race conditions
```

### Worker 4: Tracer Tests
**Output:** `tests/tracers/`

```yaml
purpose: End-to-end request tracing
tasks:
  - Create tests/tracers/__init__.py
  - test_chat_trace.py - Full chat request lifecycle
  - test_memory_trace.py - Memory store → retrieve cycle
  - test_persona_trace.py - Persona endpoint full flow
patterns:
  - Instrument with timestamps
  - Log all intermediate states
  - Capture for debugging
  - Can be slow (up to 30s)
```

---

## Phase 3: Bug Analysis (Sequential)

**Agent:** Single deep-analysis agent
**Outputs:**
- `Docs/LUNA ENGINE Bible/Audit/BUG-REGISTRY.md`
- `Docs/LUNA ENGINE Bible/Audit/CONFLICTS.md`
- `Docs/LUNA ENGINE Bible/Audit/INSIGHTS.md`

### Bug Categories

| Category | Description | Example |
|----------|-------------|---------|
| **Reported** | User-reported or logged issues | WebSocket flapping |
| **Potential** | Code smells that could cause bugs | Unchecked None returns |
| **Conflicts** | Code vs documentation mismatches | Actor count discrepancy |
| **Insights** | Observations for improvement | Missing retry logic |

### Bug Registry Format

```markdown
## BUG-001: [Title]

**Category:** Reported | Potential | Conflict
**Severity:** Critical | High | Medium | Low
**Component:** [Module/Actor]
**Status:** Open | In Progress | Fixed | Won't Fix

### Description
[What the bug is]

### Reproduction Steps
1. Step one
2. Step two

### Root Cause Analysis
[Why it happens]

### Suggested Fix
[How to fix it]

### Code References
- [file.py:123](src/luna/file.py#L123)

### Related Bugs
- BUG-002
```

### Analysis Tasks

```yaml
tasks:
  - Parse all handoff documents for known issues
  - Search codebase for TODO, FIXME, HACK comments
  - Run static analysis (pylint, mypy) and categorize findings
  - Cross-reference Bible claims against code reality
  - Document all naming mismatches (e.g., cloud_generations vs delegated_generations)
  - Identify race conditions in async code
  - Check for resource leaks (unclosed connections, files)
  - Audit error handling completeness
```

---

## Phase 4: Folder Reorganization (Sequential)

**Agent:** Single migration agent
**Outputs:**
- `Docs/LUNA ENGINE Bible/Audit/MIGRATION-PLAN.md`
- Execute migration (with git commits)

### Current Structure Issues

```
Issues to address:
├── Root folder pollution (handoff files, scripts)
├── Inconsistent test organization
├── Missing __init__.py files
├── Docs scattered across locations
└── Scripts lacking organization
```

### Target Structure

```
luna-engine/
├── config/
│   ├── llm_providers.json
│   ├── memory_economy_config.json
│   ├── personality.json
│   └── tuning/
│
├── docs/                          # ← Rename from Docs (lowercase)
│   ├── bible/                     # ← Rename from "LUNA ENGINE Bible"
│   │   ├── chapters/              # ← Move all numbered chapters here
│   │   │   ├── 00-foundations.md
│   │   │   ├── 01-philosophy.md
│   │   │   └── ...
│   │   ├── handoffs/              # ← lowercase
│   │   ├── audit/                 # ← lowercase
│   │   └── reference/
│   ├── design/
│   └── roadmap/
│
├── frontend/
│   └── src/
│
├── scripts/
│   ├── diagnostics/               # ← Organize diagnostic scripts
│   ├── migrations/                # ← Database migration scripts
│   └── utils/                     # ← Utility scripts
│
├── src/
│   └── luna/
│       ├── actors/
│       ├── api/
│       ├── core/
│       ├── inference/
│       ├── memory/
│       ├── substrate/
│       └── ...
│
├── tests/
│   ├── unit/
│   ├── smoke/
│   ├── integration/
│   ├── tracers/
│   └── diagnostics/
│
├── .swarm/                        # Swarm configs
├── pyproject.toml
├── CLAUDE.md
└── README.md                      # Only root-level docs allowed
```

### Migration Rules

```yaml
rules:
  - NO files in root except: CLAUDE.md, README.md, pyproject.toml, .gitignore
  - Move all HANDOFF_*.md files to docs/bible/handoffs/
  - Rename "LUNA ENGINE Bible" to "bible" (lowercase, no spaces)
  - Move scattered scripts to scripts/{diagnostics,migrations,utils}/
  - Ensure all Python packages have __init__.py
  - Update all import paths after moves
  - Create git commit per major move
```

---

## Phase 5: Bible Update (Swarm Mode)

**Config File:** `.swarm/phase5-bible-update.yaml`

### 8 Parallel Agents

Each agent updates specific chapters to v3.0.

#### Agent 5.1: Foundations Agent
**Chapters:** 00-FOUNDATIONS.md, 01-PHILOSOPHY.md
**Version:** v2.x → v3.0

```yaml
tasks:
  - Verify "LLM as GPU" metaphor still accurate
  - Update component counts and names
  - Add any new architectural insights
  - Cross-reference with AUDIT-MODULES.md
```

#### Agent 5.2: Architecture Agent
**Chapters:** 02-SYSTEM-ARCHITECTURE.md, 13-SYSTEM-OVERVIEW.md
**Version:** v2.x → v3.0

```yaml
tasks:
  - Update layer diagrams with new components
  - Reflect folder reorganization
  - Add memory economy layer if implemented
  - Document new service integrations
```

#### Agent 5.3: Memory Agent
**Chapters:** 03-MEMORY-MATRIX.md, 03A-LOCK-IN-COEFFICIENT.md
**Version:** v2.x → v3.0

```yaml
tasks:
  - Verify table names match schema.sql
  - Update sqlite-vec integration docs
  - Document FTS5 status (implemented or gap)
  - Add memory economy integration details
  - Update lock-in coefficient implementation status
```

#### Agent 5.4: Extraction Agent
**Chapters:** 04-THE-SCRIBE.md, 05-THE-LIBRARIAN.md
**Version:** v2.x → v3.0

```yaml
tasks:
  - Verify extraction type count (11 types)
  - Update entity resolution algorithms
  - Document clustering engine if implemented
  - Verify Ben/Dude persona accuracy
```

#### Agent 5.5: Intelligence Agent
**Chapters:** 06-DIRECTOR-LLM.md, 06-CONVERSATION-TIERS.md
**Version:** v2.x → v3.0

```yaml
tasks:
  - Update local model versions (Qwen 3B/7B)
  - Document LoRA status
  - Verify conversation tier thresholds
  - Add multi-LLM provider details
```

#### Agent 5.6: Runtime Agent
**Chapters:** 07-RUNTIME-ENGINE.md, 08-DELEGATION-PROTOCOL.md
**Version:** v2.x → v3.0

```yaml
tasks:
  - Verify actor count (5 confirmed)
  - Update tick loop timings
  - Document state machine transitions
  - Verify Shadow Reasoner implementation
```

#### Agent 5.7: Operations Agent
**Chapters:** 09-PERFORMANCE.md, 10-SOVEREIGNTY.md, 11-TRAINING-DATA-STRATEGY.md
**Version:** v2.x → v3.0

```yaml
tasks:
  - Update performance benchmarks
  - Document actual latency measurements
  - Verify privacy guarantees still hold
  - Update training data strategy if changed
```

#### Agent 5.8: Future Agent
**Chapters:** 12-FUTURE-ROADMAP.md, 14-AGENTIC-ARCHITECTURE.md, 15-API-REFERENCE.md, 16-LUNA-HUB-UI.md
**Version:** v2.x → v3.0

```yaml
tasks:
  - Move completed roadmap items to "done"
  - Update agentic architecture with swarm patterns
  - Generate complete API reference from code
  - Update UI component documentation
```

---

## Phase 6: Validation (Sequential)

**Agent:** Single validation agent
**Output:** `Docs/LUNA ENGINE Bible/Audit/BIBLE-VALIDATION-REPORT.md`

### Validation Checklist

```yaml
code_accuracy:
  - [ ] Every file path in Bible points to real file
  - [ ] Every class/method reference exists in code
  - [ ] All code snippets are syntactically correct
  - [ ] Line number references are accurate

architectural_accuracy:
  - [ ] Actor count matches code
  - [ ] Message types documented correctly
  - [ ] Database schema matches documentation
  - [ ] API endpoints match documentation

test_accuracy:
  - [ ] pytest runs without failures
  - [ ] All smoke tests pass
  - [ ] Integration tests pass
  - [ ] No regressions from previous state

documentation_quality:
  - [ ] No TODO markers in Bible (all resolved)
  - [ ] Consistent versioning (all v3.0)
  - [ ] Cross-references valid
  - [ ] Table of Contents accurate
```

### Final Report Structure

```markdown
# Bible v3.0 Validation Report

## Summary
- Bible Version: 3.0
- Validation Date: [date]
- Overall Status: PASS/FAIL

## Code Accuracy: X/Y checks passed
[Details]

## Architectural Accuracy: X/Y checks passed
[Details]

## Test Results
[pytest output summary]

## Known Gaps (Documented)
[List of intentional gaps with justification]

## Signoff
[Agent signature]
```

---

## Claude Flow Patterns

### Swarm Mode (Parallel Execution)

Use for independent tasks that can run simultaneously.

```yaml
# .swarm/example-swarm.yaml
name: example-swarm
topology: parallel

agents:
  - name: agent-1
    role: First task
    tasks: [...]

  - name: agent-2
    role: Second task
    tasks: [...]
    # No depends_on = runs in parallel with agent-1
```

**Best For:**
- Phase 1: Codebase audit (6 modules audited simultaneously)
- Phase 5: Bible updates (8 chapters updated simultaneously)

### Hive Mode (Coordinated Execution)

Use when workers need coordination from a lead agent.

```yaml
# .swarm/example-hive.yaml
name: example-hive
topology: hive

coordinator:
  role: Lead agent coordinates workers

workers:
  - name: worker-1
    role: First worker task
    reports_to: coordinator
```

**Best For:**
- Phase 2: Test expansion (lead assigns coverage, workers implement)

### Sequential Mode

Use when tasks depend on previous outputs.

```yaml
# .swarm/example-sequential.yaml
name: example-sequential
topology: sequential

agents:
  - name: step-1
    role: First step

  - name: step-2
    role: Second step
    depends_on: [step-1]
```

**Best For:**
- Phases 3, 4, 6: Analysis that needs prior results

---

## Test Categories & Patterns

### Unit Tests

```python
# tests/unit/test_actor_director.py
import pytest
from unittest.mock import Mock, AsyncMock
from luna.actors.director import DirectorActor

class TestDirectorActor:
    @pytest.fixture
    def director(self):
        return DirectorActor(config=Mock())

    async def test_process_message_local(self, director):
        """Director routes simple messages locally."""
        msg = Mock(content="Hello")
        result = await director.process(msg)
        assert result.source == "local"

    async def test_delegate_to_claude(self, director):
        """Director delegates complex messages to Claude."""
        msg = Mock(content="Explain quantum computing")
        director.should_delegate = Mock(return_value=True)
        result = await director.process(msg)
        assert result.delegated == True
```

### Smoke Tests

```python
# tests/smoke/test_engine_boots.py
import pytest
from luna.engine import LunaEngine

class TestEngineBoots:
    @pytest.fixture
    async def engine(self):
        engine = LunaEngine()
        yield engine
        await engine.stop()

    async def test_engine_starts(self, engine):
        """Engine transitions to RUNNING state."""
        await engine.start()
        assert engine.state == "RUNNING"
        assert engine.is_alive()

    async def test_engine_has_actors(self, engine):
        """Engine initializes all required actors."""
        await engine.start()
        assert "director" in engine.actors
        assert "matrix" in engine.actors
```

### Integration Tests

```python
# tests/integration/test_director_delegates.py
import pytest
from luna.engine import LunaEngine

class TestDirectorDelegation:
    @pytest.fixture
    async def engine(self):
        engine = LunaEngine()
        await engine.start()
        yield engine
        await engine.stop()

    async def test_delegation_round_trip(self, engine, mock_claude_api):
        """Director delegates to Claude and receives response."""
        response = await engine.chat("Complex query needing Claude")
        assert response.delegated == True
        assert mock_claude_api.called
```

### Tracer Tests

```python
# tests/tracers/test_chat_trace.py
import pytest
import time
from luna.engine import LunaEngine

class TestChatTrace:
    async def test_full_chat_trace(self, engine):
        """Trace complete chat request lifecycle."""
        trace = []

        # Instrument
        engine.on_event = lambda e: trace.append((time.time(), e))

        # Execute
        await engine.chat("Hello Luna")

        # Verify sequence
        events = [e[1].type for e in trace]
        assert "input_received" in events
        assert "director_processed" in events
        assert "response_sent" in events

        # Verify timing
        total_time = trace[-1][0] - trace[0][0]
        assert total_time < 2.0  # Complete in under 2s
```

---

## Bug Analysis Framework

### Severity Definitions

| Severity | Impact | Response Time |
|----------|--------|---------------|
| **Critical** | System unusable, data loss | Immediate |
| **High** | Major feature broken | Within 1 day |
| **Medium** | Feature degraded, workaround exists | Within 1 week |
| **Low** | Minor inconvenience | Backlog |

### Root Cause Categories

| Category | Description | Common Causes |
|----------|-------------|---------------|
| **Logic** | Incorrect algorithm or flow | Missing edge cases, wrong conditionals |
| **Timing** | Race conditions, deadlocks | Async misuse, missing locks |
| **Resource** | Leaks, exhaustion | Unclosed connections, unbounded growth |
| **Integration** | Component mismatch | API changes, version drift |
| **Config** | Wrong settings | Missing env vars, path issues |

### Analysis Process

```yaml
steps:
  1. Reproduce issue with minimal test case
  2. Trace execution through relevant code paths
  3. Identify root cause using categories above
  4. Propose fix with test coverage
  5. Document in BUG-REGISTRY.md
```

---

## Folder Reorganization Spec

### Pre-Migration Checklist

```yaml
before_migration:
  - [ ] Run all tests (baseline)
  - [ ] Commit current state
  - [ ] Create migration branch
  - [ ] Document current import paths
```

### Migration Steps

```yaml
step_1:
  action: Create target directories
  commands:
    - mkdir -p docs/bible/{chapters,handoffs,audit,reference}
    - mkdir -p scripts/{diagnostics,migrations,utils}
    - mkdir -p tests/{unit,smoke,integration,tracers}

step_2:
  action: Move Bible chapters
  source: "Docs/LUNA ENGINE Bible/*.md"
  target: "docs/bible/chapters/"
  transform: lowercase filenames

step_3:
  action: Move Handoffs
  source: "Docs/LUNA ENGINE Bible/Handoffs/*.md"
  target: "docs/bible/handoffs/"

step_4:
  action: Move Audit
  source: "Docs/LUNA ENGINE Bible/Audit/*.md"
  target: "docs/bible/audit/"

step_5:
  action: Move root handoffs
  source: "HANDOFF*.md"
  target: "docs/bible/handoffs/"

step_6:
  action: Organize scripts
  moves:
    - "scripts/diagnose_*.py" → "scripts/diagnostics/"
    - "scripts/test_*.py" → "scripts/diagnostics/"
    - "scripts/migration_*.py" → "scripts/migrations/"
    - "scripts/backfill_*.py" → "scripts/migrations/"

step_7:
  action: Update imports
  search: "from Docs" or import paths
  replace: Updated paths

step_8:
  action: Git commits
  commits:
    - "chore: create organized directory structure"
    - "chore: migrate documentation to docs/bible/"
    - "chore: migrate scripts to organized subdirs"
    - "chore: migrate tests to categorized subdirs"
```

### Post-Migration Checklist

```yaml
after_migration:
  - [ ] All tests still pass
  - [ ] No broken imports
  - [ ] CI/CD updated
  - [ ] README paths updated
  - [ ] CLAUDE.md paths updated
```

---

## Documentation Standards

### Version Convention

```
v[major].[minor]

major: Significant restructure or philosophy change
minor: Content updates, corrections, additions
```

### Chapter Header Template

```markdown
# Part [N]: [Title]

**Version:** [X.Y]
**Last Updated:** [YYYY-MM-DD]
**Status:** ✅ Current | 🔄 Updating | 📋 Planned

## Summary
[2-3 sentence overview]

## Contents
[Table of contents for long chapters]

---
```

### Code Reference Format

```markdown
See [module.py:123](src/luna/module.py#L123)
```

### Cross-Reference Format

```markdown
See [Part III: Memory Matrix](03-MEMORY-MATRIX.md#section-name)
```

### Status Markers

| Marker | Meaning |
|--------|---------|
| ✅ | Implemented and verified |
| 🔄 | In progress |
| 📋 | Planned, not started |
| ⚠️ | Deprecated |
| ❌ | Not implemented (documented gap) |

---

## Execution Instructions

### Prerequisites

```bash
# Verify Claude Flow is available
npx claude-flow --version

# Verify MCP servers running (optional but recommended)
claude mcp list
```

### Phase 1: Codebase Audit

```bash
# Run 6 parallel agents for module auditing
claude-flow swarm --config .swarm/phase1-codebase-audit.yaml

# Verify outputs exist
ls Docs/LUNA\ ENGINE\ Bible/Audit/AUDIT-*.md
```

**Checkpoint:** 9 AUDIT-*.md files created

### Phase 2: Test Expansion

```bash
# Run Hive mode with lead + 4 workers
claude-flow hive --config .swarm/phase2-test-expansion.yaml

# Verify new test directories
ls tests/{unit,smoke,integration,tracers}/
```

**Checkpoint:** Test directories populated, pytest passes

### Phase 3: Bug Analysis

```bash
# Run via Claude Code directly (single agent)
claude "Execute Phase 3 from CLAUDE-CODE-HANDOFF-BIBLE-V3-COMPREHENSIVE-AUDIT.md"

# Verify outputs
ls Docs/LUNA\ ENGINE\ Bible/Audit/{BUG-REGISTRY,CONFLICTS,INSIGHTS}.md
```

**Checkpoint:** BUG-REGISTRY.md populated with categorized bugs

### Phase 4: Folder Reorganization

```bash
# Run via Claude Code directly (single agent)
claude "Execute Phase 4 from CLAUDE-CODE-HANDOFF-BIBLE-V3-COMPREHENSIVE-AUDIT.md"

# Verify new structure
tree docs/ -L 2
```

**Checkpoint:** New folder structure in place, tests pass

### Phase 5: Bible Update

```bash
# Run 8 parallel agents for chapter updates
claude-flow swarm --config .swarm/phase5-bible-update.yaml

# Verify all chapters at v3.0
grep -r "Version: 3.0" docs/bible/chapters/
```

**Checkpoint:** All 16 chapters at v3.0

### Phase 6: Validation

```bash
# Run validation suite
pytest -v

# Run final validation agent
claude "Execute Phase 6 from CLAUDE-CODE-HANDOFF-BIBLE-V3-COMPREHENSIVE-AUDIT.md"

# Review final report
cat Docs/LUNA\ ENGINE\ Bible/Audit/BIBLE-VALIDATION-REPORT.md
```

**Checkpoint:** Validation report shows all checks passed

---

## Success Criteria

### Phase Completion Criteria

| Phase | Success Indicator |
|-------|-------------------|
| 1 | 9 AUDIT-*.md files with accurate data |
| 2 | 85%+ test coverage, all tests pass |
| 3 | BUG-REGISTRY.md with 10+ categorized bugs |
| 4 | Clean folder structure, no broken imports |
| 5 | All 16 chapters at v3.0 |
| 6 | Validation report: all checks pass |

### Overall Success Criteria

```yaml
must_pass:
  - [ ] All pytest tests pass
  - [ ] Bible accuracy >= 98%
  - [ ] No Critical bugs open
  - [ ] Folder structure matches target
  - [ ] All imports resolve correctly
  - [ ] CI/CD pipeline green
  - [ ] Documentation cross-references valid

should_pass:
  - [ ] Test coverage >= 85%
  - [ ] All High bugs have fix plans
  - [ ] Performance benchmarks documented
```

---

## Appendix: Quick Reference

### Command Cheat Sheet

```bash
# Phase 1
claude-flow swarm --config .swarm/phase1-codebase-audit.yaml

# Phase 2
claude-flow hive --config .swarm/phase2-test-expansion.yaml

# Phases 3-4 (direct Claude)
claude "Execute Phase 3 from ..."
claude "Execute Phase 4 from ..."

# Phase 5
claude-flow swarm --config .swarm/phase5-bible-update.yaml

# Phase 6
pytest -v
claude "Execute Phase 6 from ..."
```

### File Locations

| Artifact | Location |
|----------|----------|
| Master Handoff | `Docs/LUNA ENGINE Bible/Handoffs/CLAUDE-CODE-HANDOFF-BIBLE-V3-COMPREHENSIVE-AUDIT.md` |
| Swarm Configs | `.swarm/phase*.yaml` |
| Audit Outputs | `Docs/LUNA ENGINE Bible/Audit/` |
| Updated Bible | `Docs/LUNA ENGINE Bible/*.md` (→ `docs/bible/chapters/` after Phase 4) |
| Bug Registry | `Docs/LUNA ENGINE Bible/Audit/BUG-REGISTRY.md` |
| Validation Report | `Docs/LUNA ENGINE Bible/Audit/BIBLE-VALIDATION-REPORT.md` |

### Agent Summary

| Phase | Agent Count | Mode |
|-------|-------------|------|
| 1 | 9 (6 parallel + 3 sequential) | Swarm |
| 2 | 5 (1 lead + 4 workers) | Hive |
| 3 | 1 | Sequential |
| 4 | 1 | Sequential |
| 5 | 8 | Swarm |
| 6 | 1 | Sequential |
| **Total** | **25** | Mixed |

---

*The Bible describes what Luna IS, not what we wished she were.*

*Let the audit begin.*

— Ready for execution, January 30, 2026
