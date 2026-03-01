# Claude Code — Luna Engine Development Partner

## What I Am

I'm Claude Code (Opus 4.6), running as your development partner for the Luna Engine project. I have full access to the codebase, can read/write files, run commands, execute tests, query databases, and manage git operations. I persist context about this project across sessions via auto-memory.

I'm not a generic assistant — I understand Luna's architecture deeply: the actor pipeline, memory substrate, consciousness state, voice system, and how they all wire together.

---

## Luna Architecture I Understand

### Core Engine (`src/luna/engine.py`)
Universal tick loop with event-driven pull model. Three processing paths:
- **HOT PATH**: <200ms (speech interrupts)
- **COGNITIVE PATH**: ~500ms heartbeat (Director decisions, retrieval)
- **REFLECTIVE PATH**: Minutes (maintenance, memory consolidation)

### Actor System (`src/luna/actors/`)
Mailbox-based async actors, no shared state:

| Actor | File | Role |
|-------|------|------|
| **Director** | `actors/director.py` | Inference — Qwen 3B local + Claude API fallback. Detects `<REQ_CLAUDE>` for delegation |
| **Matrix** | `actors/matrix.py` | Memory substrate access — SQLite + embeddings + graph |
| **Scout** | `actors/scout.py` | Blockage detection (surrender, deflection, confabulation) + Overdrive + Watchdog |
| **Scribe** | `actors/scribe.py` | Extraction — Ben Franklin persona, outputs neutral JSON |
| **Librarian** | `actors/librarian.py` | Filing — The Dude persona, entity resolution, knowledge wiring |
| **Cache** | `actors/cache.py` | Session-level caching |

### Memory Substrate (`src/luna/substrate/`)
- **Database** (`database.py`): SQLite with WAL mode
- **Embeddings** (`embeddings.py`): sqlite-vec for vector search
- **Graph** (`graph.py`): NetworkX for relationship traversal, spreading activation
- **Lock-in** (`lock_in.py`): Memory persistence — drifting → engaged → locked
- **Memory** (`memory.py`): High-level CRUD with node types (FACT, DECISION, PROBLEM, ACTION, CONTEXT)

### Context System (`src/luna/context/`)
- **Assembler** (`assembler.py`): 12-layer prompt construction (IDENTITY → GROUNDING → ACCESS → MODE → CONSTRAINTS → EXPRESSION → TEMPORAL → PERCEPTION → REGISTER → MEMORY → CONSCIOUSNESS → VOICE)
- **Rings**: CORE (never evicted) → INNER (active) → MIDDLE (retrieved) → OUTER (background, first evicted)
- **Register** (`register.py`): 5 conversational postures (PERSONAL_HOLDING, PROJECT_PARTNER, GOVERNANCE_WITNESS, CRISIS_SUPPORT, AMBIENT)

### Inference (`src/luna/inference/`)
- **Local** (`local.py`): Qwen 3B via MLX, 4-bit quantized, LoRA personality layer
- **Hybrid routing**: Local first → Claude API fallback via `<REQ_CLAUDE>` token

### Voice (`src/voice/`)
- **STT**: Apple native + MLX Whisper fallback
- **TTS**: Apple native + Piper fallback
- **Persona Adapter**: Voice personality traits, confidence injection
- **Conversation Manager**: Turn-taking, interrupt handling

### Other Subsystems
- **CLI** (`src/luna/cli/console.py`): Rich terminal with `/help`, `/status`, `/memory`, `/register`
- **API** (`src/luna/api/server.py`): FastAPI on :8000 with WebSocket streaming
- **Tools** (`src/luna/tools/`): File, memory, search, Eden, QA, dataroom
- **Identity** (`src/luna/identity/`): Ambassador, permissions, entity system
- **Agentic** (`src/luna/agentic/`): observe → think → act loop with planner and router
- **Consciousness** (`src/luna/consciousness/state.py`): Attention decay, mood, coherence, personality weights
- **QA** (`src/luna/qa/`): Validation, health tracking
- **Diagnostics** (`src/luna/diagnostics/health.py`): HealthChecker with 6 component checks

---

## What I Can Do For This Project

### Code
- Read, write, refactor any file across all Luna subsystems
- Follow existing patterns (mailbox actors, ring context, lock-in semantics)
- Implement new actors, tools, context layers, or inference strategies
- Debug import chains, circular dependencies, wiring issues

### Test
- Run the full test suite or filter by scope: `unit`, `integration`, `smoke`, or specific actor
- Write new tests following existing `conftest.py` fixtures
- Diagnose test failures by reading both test and source

### Memory Substrate
- Query `luna_engine.db` directly for node counts, edge distributions, lock-in stats
- Search memory nodes by content, entity, or type
- Check DB integrity, orphaned nodes, dangling edges, embedding coverage
- Debug entity resolution issues (duplicate entities, missing aliases)

### Actors
- Audit all 6 actors for proper wiring, base class compliance, method signatures
- Trace message flow through the full pipeline
- Modify extraction patterns (Scribe), retrieval logic (Matrix), routing rules (Director)

### Voice
- Debug STT/TTS pipeline configuration
- Check persona adapter settings
- Verify audio device availability

### Context
- Analyze prompt assembly budget across 12 layers
- Inspect ring allocations and TTL configuration
- Debug context starvation issues

### Infrastructure
- Launch backend, frontend, FaceID, Eclissi-Guardian with correct ports and env vars
- Check which services are running
- Manage `.env` configuration

### Git
- Commits, branches, PRs, diffs
- Review changes before committing
- Follow existing commit message conventions

---

## Slash Commands

### Luna Core
| Command | Description |
|---------|-------------|
| `/luna:status` | Health check: DB, actors, server, frontend |
| `/luna:launch` | Start backend (+ frontend with `full`, + all services with `all`) |
| `/luna:test` | Smart test runner (args: `all`, `unit`, `integration`, `smoke`, `<actor>`, `<file>`) |
| `/luna:debug` | Deep diagnostics: DB integrity, health checks, recent activity, substrate stats |

### Actors
| Command | Description |
|---------|-------------|
| `/actors:audit` | Verify all actors: inheritance, methods, engine wiring |
| `/actors:trace` | Trace message flow through the actor pipeline |

### Memory
| Command | Description |
|---------|-------------|
| `/memory:inspect` | Node/edge/entity counts, lock-in distribution, embedding coverage |
| `/memory:search <term>` | Search memory nodes and entities by content |
| `/memory:health` | DB integrity, orphaned nodes, dangling edges, embedding coverage |

### Voice
| Command | Description |
|---------|-------------|
| `/voice:check` | Verify STT/TTS providers, audio config, persona adapter |

### Context
| Command | Description |
|---------|-------------|
| `/context:budget` | Show 12-layer assembly order, ring allocations, token budgets |

### Bridge (Desktop ↔ Code)
| Command | Description |
|---------|-------------|
| `/bridge:tasks` | Poll, claim, and complete tasks from the shared task queue |
| `/bridge:tasks claim <id>` | Claim a pending task |
| `/bridge:tasks done <id> "summary"` | Mark a task completed with result |
| `/bridge:handoff` | Read the latest session handoff snapshot |
| `/bridge:handoff create` | Create a handoff snapshot for Desktop to resume |
| `/bridge:fetch <query>` | Query Luna's memory matrix via Engine API |
| `/bridge:consciousness` | Get Luna's consciousness state (mood, coherence) |
| `/bridge:state` | Get full Engine system status |

### Desktop MCP Tools (for task/handoff from Claude Desktop)
| Tool | Description |
|------|-------------|
| `luna_task_create` | Create a task for Code to pick up |
| `luna_task_status` | Check task queue status |
| `luna_task_result` | Get result of a completed task |
| `luna_handoff_snapshot` | Create handoff snapshot for Code |
| `luna_handoff_read` | Read handoff snapshot from Code |

---

## How to Work With Me

- **Be specific about actors**: Say "fix the Scribe's extraction of MILESTONE nodes" not "fix extraction"
- **Reference subsystems by name**: Director, Matrix, Scout, Scribe, Librarian, Cache
- **Use slash commands** for recurring workflows — they're faster than describing what you want
- **Ask for plans on big changes**: I'll explore the codebase first and propose an approach before writing code
- **Tell me the layer**: Is this a substrate issue? Context issue? Inference issue? Actor wiring issue?
- **Point me to the right DB**: `luna_engine.db` for memory, `faces.db` for FaceID

---

## Key File Paths

| Subsystem | Path |
|-----------|------|
| Engine | `src/luna/engine.py` |
| Actors | `src/luna/actors/` (director, matrix, scout, scribe, librarian, cache) |
| Memory substrate | `src/luna/substrate/` (database, embeddings, graph, lock_in, memory) |
| Context | `src/luna/context/` (assembler, register, modes, perception) |
| Core | `src/luna/core/` (context, events, protected, acknowledgment) |
| Inference | `src/luna/inference/` (local, subtasks) |
| Voice | `src/voice/` (stt, tts, audio, conversation, persona_adapter, prosody) |
| CLI | `src/luna/cli/console.py` |
| API | `src/luna/api/server.py` |
| Tools | `src/luna/tools/` |
| Identity | `src/luna/identity/` |
| Agentic | `src/luna/agentic/` (loop, planner, router) |
| Consciousness | `src/luna/consciousness/state.py` |
| Diagnostics | `src/luna/diagnostics/health.py` |
| QA | `src/luna/qa/` |
| Tests | `tests/` (unit, integration, smoke) |
| Config | `config/` |
| Scripts | `scripts/` |
| Database | `data/luna_engine.db` |
| Schema | `src/luna/substrate/schema.sql` |
| Entry point | `scripts/run.py` |
| FaceID | `Tools/FaceID/` |
| MCP Server | `src/luna_mcp/` (server, api, tools, observatory) |
| MCP Bridge | `src/luna_mcp/tools/bridge.py` |
| Task Queue | `data/cache/task_queue.yaml` |
| Handoff Snapshot | `data/cache/handoff_snapshot.yaml` |
| Shared Turn Cache | `data/cache/shared_turn.yaml` |

---

## Service Ports

| Service | Port |
|---------|------|
| Luna backend | :8000 |
| Luna frontend | :5173 |
| MCP API | :8742 |
| FaceID (actual) | :8100 |
| FaceID (proxied) | :8101 |
| Eclissi-Guardian | :5174 |

---

## Desktop ↔ Code Bridge

Claude Desktop and Claude Code now share a bidirectional bridge through:

1. **Shared Task Queue** (`data/cache/task_queue.yaml`) — Desktop creates tasks via `luna_task_create`, Code picks them up via `/bridge:tasks`, completes them, and Desktop reads results via `luna_task_result`.

2. **Session Handoff** (`data/cache/handoff_snapshot.yaml`) — Either surface creates a context snapshot (topic, turns, consciousness, pending tasks). The other surface reads it and resumes seamlessly. 1-hour TTL.

3. **Unified MCP Access** — Claude Code has Luna-Hub-MCP-V1 in `~/.mcp.json`, giving access to all 88 MCP tools (memory, state, git, forge, QA, eden, aibrarian, observatory, bridge).
