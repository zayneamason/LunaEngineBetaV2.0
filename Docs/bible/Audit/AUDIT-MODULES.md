# AUDIT-MODULES.md

**Generated:** 2026-01-30
**Agent:** Module Auditor
**Phase:** 1.1

---

## Summary

| Metric | Count |
|--------|-------|
| Total Python files | 85 |
| Total classes | 167 |
| Total public methods/functions | ~1,080 |
| Files over 500 lines | 19 |
| Dataclass definitions | 58 |
| TODO/FIXME comments | 15 |

---

## File Inventory

All Python files in `src/luna/` with line counts (sorted by size descending):

| File | Lines | Status |
|------|-------|--------|
| `api/server.py` | 4,650 | OVER 500 - Major refactoring candidate |
| `actors/director.py` | 2,184 | OVER 500 - Large but coherent |
| `substrate/memory.py` | 1,405 | OVER 500 - Core memory operations |
| `engine.py` | 1,287 | OVER 500 - Main engine file |
| `entities/context.py` | 1,202 | OVER 500 - Entity context management |
| `entities/resolution.py` | 1,159 | OVER 500 - Entity resolution system |
| `actors/librarian.py` | 1,028 | OVER 500 - Memory filing actor |
| `actors/history_manager.py` | 1,007 | OVER 500 - Conversation tiers |
| `agentic/loop.py` | 938 | OVER 500 - Agent execution loop |
| `core/context.py` | 875 | OVER 500 - Revolving context system |
| `actors/scribe.py` | 827 | OVER 500 - Extraction actor |
| `tuning/params.py` | 787 | OVER 500 - Tuning parameters |
| `entities/models.py` | 731 | OVER 500 - Entity data models |
| `diagnostics/health.py` | 641 | OVER 500 - Health checking |
| `inference/local.py` | 604 | OVER 500 - Local MLX inference |
| `memory/cluster_manager.py` | 580 | OVER 500 - Memory clustering |
| `entities/storage.py` | 575 | OVER 500 - Personality storage |
| `cli/console.py` | 541 | OVER 500 - Console interface |
| `memory/clustering_engine.py` | 504 | OVER 500 - Clustering engine |
| `substrate/graph.py` | 502 | OVER 500 - Memory graph |
| `cli/debug.py` | 495 | Near threshold |
| `agentic/planner.py` | 486 | OK |
| `tuning/evaluator.py` | 481 | OK |
| `entities/reflection.py` | 449 | OK |
| `actors/matrix.py` | 442 | OK |
| `memory/lock_in.py` | 424 | OK |
| `agentic/router.py` | 423 | OK |
| `tuning/session.py` | 420 | OK |
| `context/pipeline.py` | 379 | OK |
| `entities/lifecycle.py` | 377 | OK |
| `tools/memory_tools.py` | 372 | OK |
| `substrate/embeddings.py` | 370 | OK |
| `librarian/cluster_retrieval.py` | 360 | OK |
| `tools/file_tools.py` | 357 | OK |
| `extraction/chunker.py` | 338 | OK |
| `memory/constellation.py` | 313 | OK |
| `tools/registry.py` | 308 | OK |
| `substrate/lock_in.py` | 285 | OK |
| `diagnostics/watchdog.py` | 278 | OK |
| `services/orb_state.py` | 268 | OK |
| `services/lockin_service.py` | 267 | OK |
| `core/tasks.py` | 264 | OK |
| `consciousness/state.py` | 251 | OK |
| `extraction/types.py` | 244 | OK |
| `llm/providers/gemini_provider.py` | 233 | OK |
| `substrate/database.py` | 232 | OK |
| `services/clustering_service.py` | 222 | OK |
| `entities/bootstrap.py` | 216 | OK |
| `services/performance_orchestrator.py` | 210 | OK |
| `substrate/local_embeddings.py` | 194 | OK |
| `diagnostics/critical_systems.py` | 187 | OK |
| `consciousness/attention.py` | 181 | OK |
| `actors/base.py` | 181 | OK |
| `llm/config.py` | 174 | OK |
| `services/performance_state.py` | 172 | OK |
| `llm/providers/claude_provider.py` | 169 | OK |
| `memory/ring.py` | 161 | OK |
| `llm/providers/groq_provider.py` | 155 | OK |
| `consciousness/personality.py` | 155 | OK |
| `core/input_buffer.py` | 152 | OK |
| `llm/registry.py` | 139 | OK |
| `core/protected.py` | 135 | OK |
| `llm/base.py` | 101 | OK |
| `tools/__init__.py` | 92 | OK |
| `core/events.py` | 92 | OK |
| `entities/__init__.py` | 73 | OK |
| `llm/__init__.py` | 69 | OK |
| `agentic/__init__.py` | 52 | OK |
| `memory/__init__.py` | 43 | OK |
| `core/__init__.py` | 39 | OK |
| `inference/__init__.py` | 36 | OK |
| `core/state.py` | 35 | OK |
| `extraction/__init__.py` | 32 | OK |
| `tuning/__init__.py` | 27 | OK |
| `substrate/__init__.py` | 27 | OK |
| `services/__init__.py` | 24 | OK |
| `diagnostics/__init__.py` | 20 | OK |
| `actors/__init__.py` | 16 | OK |
| `consciousness/__init__.py` | 14 | OK |
| `__init__.py` | 10 | OK |
| `llm/providers/__init__.py` | 6 | OK |
| `cli/__init__.py` | 6 | OK |
| `librarian/__init__.py` | 5 | OK |
| `context/__init__.py` | 5 | OK |
| `api/__init__.py` | 5 | OK |
| `identity/__init__.py` | 1 | Empty placeholder |

**Total: 85 Python files, 31,892 lines of code**

---

## Class Hierarchy

### Core Engine Classes

```
LunaEngine (engine.py)
    - EngineConfig (@dataclass)
    - EngineMetrics (@dataclass)

EngineState (core/state.py, Enum)
```

### Actor System

```
Actor (ABC) - actors/base.py
    |
    +-- DirectorActor (actors/director.py)
    |       - Manages LLM inference (local + Claude)
    |       - 2,184 lines
    |
    +-- MatrixActor (actors/matrix.py)
    |       - Memory substrate interface
    |       - 442 lines
    |
    +-- ScribeActor (actors/scribe.py)
    |       - "Ben Franklin" - extraction system
    |       - 827 lines
    |
    +-- LibrarianActor (actors/librarian.py)
    |       - "The Dude" - memory filing
    |       - 1,028 lines
    |
    +-- HistoryManagerActor (actors/history_manager.py)
            - Three-tier conversation history
            - 1,007 lines

Message (@dataclass) - actors/base.py
    - Inter-actor communication
```

### Memory Substrate

```
MemoryDatabase (substrate/database.py)
    |
    +-- MemoryMatrix (substrate/memory.py)
    |       - MemoryNode (@dataclass)
    |       - Turn (@dataclass)
    |
    +-- MemoryGraph (substrate/graph.py)
            - RelationshipType (Enum)
            - Edge (@dataclass)
            - DatabaseProtocol (Protocol)

EmbeddingStore (substrate/embeddings.py)
EmbeddingGenerator (substrate/embeddings.py)
LocalEmbeddings (substrate/local_embeddings.py)

LockInConfig (@dataclass) - substrate/lock_in.py
LockInState (Enum) - substrate/lock_in.py
```

### Entity System

```
Entity (@dataclass) - entities/models.py
EntityType (Enum) - entities/models.py
ChangeType (Enum) - entities/models.py
EntityVersion (@dataclass) - entities/models.py
EntityRelationship (@dataclass) - entities/models.py
EntityMention (@dataclass) - entities/models.py
EntityUpdate (@dataclass) - entities/models.py
PersonalityPatch (@dataclass) - entities/models.py
EmergentPrompt (@dataclass) - entities/models.py
MoodState (@dataclass) - entities/models.py
PatchTopic (Enum) - entities/models.py
PatchTrigger (Enum) - entities/models.py

EntityContext (entities/context.py)
IdentityBuffer (@dataclass) - entities/context.py

EntityResolver (entities/resolution.py)
PersonalityPatchManager (entities/storage.py)
LifecycleManager (entities/lifecycle.py)
ReflectionLoop (entities/reflection.py)
```

### Context System

```
RevolvingContext (core/context.py)
    - ContextRing (IntEnum)
    - ContextSource (IntEnum)
    - ContextItem (@dataclass)
    - QueueManager

ContextPipeline (context/pipeline.py)
    - ContextPacket (@dataclass)
```

### Agentic Architecture

```
AgentLoop (agentic/loop.py)
    - AgentStatus (Enum)
    - Observation (@dataclass)
    - Action (@dataclass)
    - ActionResult (@dataclass)
    - AgentResult (@dataclass)
    - WorkingContext (@dataclass)

QueryRouter (agentic/router.py)
    - ExecutionPath (Enum)
    - RoutingDecision (@dataclass)

Planner (agentic/planner.py)
    - PlanStepType (Enum)
    - PlanStep (@dataclass)
    - Plan (@dataclass)
```

### Extraction System

```
SemanticChunker (extraction/chunker.py)
    - Turn (@dataclass)
    - Chunk (@dataclass)

ExtractionType (Enum) - extraction/types.py
ExtractedObject (@dataclass) - extraction/types.py
ExtractedEdge (@dataclass) - extraction/types.py
ExtractionOutput (@dataclass) - extraction/types.py
FilingResult (@dataclass) - extraction/types.py
ExtractionConfig (@dataclass) - extraction/types.py
```

### LLM Provider System

```
LLMProvider (Protocol) - llm/base.py
    |
    +-- ClaudeProvider (llm/providers/claude_provider.py)
    +-- GroqProvider (llm/providers/groq_provider.py)
    +-- GeminiProvider (llm/providers/gemini_provider.py)

ProviderRegistry (llm/registry.py)
ProviderConfig (@dataclass) - llm/config.py
LLMConfig (@dataclass) - llm/config.py
Message (@dataclass) - llm/base.py
ModelInfo (@dataclass) - llm/base.py
ProviderLimits (@dataclass) - llm/base.py
CompletionResult (@dataclass) - llm/base.py
ProviderStatus (Enum) - llm/base.py
```

### Consciousness System

```
ConsciousnessState (@dataclass) - consciousness/state.py
AttentionManager (consciousness/attention.py)
    - AttentionTopic (@dataclass)
PersonalityWeights (@dataclass) - consciousness/personality.py
```

### Services

```
OrbStateManager (services/orb_state.py)
    - OrbAnimation (Enum)
    - StatePriority (Enum)
    - OrbState (@dataclass)
    - ExpressionConfig

PerformanceOrchestrator (services/performance_orchestrator.py)
PerformanceState (@dataclass) - services/performance_state.py
VoiceKnobs (@dataclass) - services/performance_state.py
OrbKnobs (@dataclass) - services/performance_state.py
EmotionPreset (Enum) - services/performance_state.py

LockInService (services/lockin_service.py)
ClusteringService (services/clustering_service.py)
```

### Memory Management

```
ConversationRing (memory/ring.py)
    - Turn (@dataclass)

ClusterManager (memory/cluster_manager.py)
    - Cluster (@dataclass)
    - ClusterEdge (@dataclass)

ClusteringEngine (memory/clustering_engine.py)
LockInCalculator (memory/lock_in.py)
Constellation (@dataclass) - memory/constellation.py
ConstellationAssembler (memory/constellation.py)
ClusterRetrieval (librarian/cluster_retrieval.py)
```

### Local Inference

```
LocalInference (inference/local.py)
    - InferenceConfig (@dataclass)
    - GenerationResult (@dataclass)

HybridInference (inference/local.py)
```

### Diagnostics

```
HealthChecker (diagnostics/health.py)
    - HealthStatus (Enum)
    - HealthCheck (@dataclass)

CriticalSystemsCheck (diagnostics/critical_systems.py)
LunaWatchdog (diagnostics/watchdog.py)
    - WatchdogAlert (@dataclass)
```

### Tuning System

```
ParamRegistry (tuning/params.py)
    - ParamSpec (@dataclass)

TuningSessionManager (tuning/session.py)
    - TuningSession (@dataclass)
    - TuningIteration (@dataclass)

Evaluator (tuning/evaluator.py)
    - TestCase (@dataclass)
    - TestResult (@dataclass)
    - EvalResults (@dataclass)
```

### Tools

```
ToolRegistry (tools/registry.py)
    - Tool (@dataclass)
    - ToolResult (@dataclass)
```

### Events & Input

```
InputBuffer (core/input_buffer.py)
InputEvent (@dataclass) - core/events.py
EventType (IntEnum) - core/events.py
EventPriority (IntEnum) - core/events.py
Task (@dataclass) - core/tasks.py
TaskManager (core/tasks.py)
```

### CLI

```
LunaConsole (cli/console.py)
ChatUI (cli/console.py)
```

### API (Pydantic Models)

Located in `api/server.py` - 50+ Pydantic BaseModel classes for request/response validation including:
- MessageRequest, MessageResponse
- StatusResponse, AgenticStats
- HistoryResponse, ConsciousnessResponse
- RingBufferStatus, MemorySearchRequest
- ClusterStatsResponse, VoiceStatusResponse
- TuningParamResponse, SlashCommandResponse
- And many more...

---

## Key Method Signatures

### LunaEngine (engine.py)

```python
async def run(self) -> None
async def _boot(self) -> None
async def _cognitive_loop(self) -> None
async def _cognitive_tick(self) -> None
async def _reflective_loop(self) -> None
async def _dispatch_event(self, event: InputEvent) -> None
async def _handle_user_message(self, user_message: str, correlation_id: str) -> None
async def _process_message_agentic(self, user_message: str, correlation_id: str) -> None
async def _process_direct(self, user_message: str, correlation_id: str, memory_context: str = "", history_context: Optional[Dict] = None) -> None
async def record_conversation_turn(self, role: str, content: str, source: str = "text", tokens: Optional[int] = None) -> None
async def send_message(self, text: str) -> None
async def stop(self) -> None
def status(self) -> dict
```

### Actor (actors/base.py)

```python
async def start(self) -> None
async def stop(self) -> None
async def handle(self, msg: Message) -> None  # Abstract
async def send(self, target: "Actor", msg: Message) -> None
async def send_to_engine(self, event_type: str, payload: Any) -> None
async def on_start(self) -> None
async def on_stop(self) -> None
async def on_error(self, error: Exception, msg: Message) -> None
async def snapshot(self) -> dict
async def restore(self, state: dict) -> None
```

### DirectorActor (actors/director.py)

```python
async def handle(self, msg: Message) -> None
async def generate(self, user_message: str, system_prompt: str = "", context_window: str = "") -> str
async def generate_stream(self, user_message: str, system_prompt: str = "", context_window: str = "") -> AsyncGenerator[str, None]
async def session_end_reflection(self) -> Optional[dict]
def on_stream(self, callback: Callable[[str], None]) -> None
def remove_stream_callback(self, callback: Callable) -> None
```

### MemoryMatrix (substrate/memory.py)

```python
async def add_node(self, node_type: str, content: str, source: Optional[str] = None, metadata: Optional[dict] = None, summary: Optional[str] = None, confidence: float = 1.0, importance: float = 0.5, link_entities: bool = True) -> str
async def get_node(self, node_id: str) -> Optional[MemoryNode]
async def update_node(self, node_id: str, ...) -> bool
async def delete_node(self, node_id: str) -> bool
async def search_nodes(self, query: str, node_type: Optional[str] = None, limit: int = 10) -> list[MemoryNode]
async def fts5_search(self, query: str, node_type: Optional[str] = None, limit: int = 10) -> list[tuple[MemoryNode, float]]
async def semantic_search(self, query: str, node_type: Optional[str] = None, limit: int = 10, min_similarity: float = 0.3) -> list[tuple[MemoryNode, float]]
async def hybrid_search(self, query: str, node_type: Optional[str] = None, limit: int = 10, keyword_weight: float = 0.4, semantic_weight: float = 0.6) -> list[tuple[MemoryNode, float]]
async def get_context(self, query: str, max_tokens: int = 2000, node_types: Optional[list[str]] = None) -> list[MemoryNode]
async def record_access(self, node_id: str) -> None
async def reinforce_node(self, node_id: str) -> bool
async def get_stats(self) -> dict
```

### AgentLoop (agentic/loop.py)

```python
async def run(self, goal: str) -> AgentResult
def abort(self) -> None
def on_progress(self, callback: Callable) -> None
```

### RevolvingContext (core/context.py)

```python
def add(self, content: str, source: ContextSource, relevance: float = 1.0, metadata: Optional[Dict] = None) -> ContextItem
def set_core_identity(self, identity: str) -> None
def get_context_window(self, max_tokens: Optional[int] = None) -> str
def decay_all(self, factor: float = 0.95) -> None
def advance_turn(self) -> int
def stats(self) -> Dict[str, Any]
```

---

## Dead Code Candidates

### TODO Comments (need implementation or removal)

| File | Line | Comment |
|------|------|---------|
| `substrate/memory.py` | 1194 | `# TODO: Add network effects (locked neighbors) when graph is wired` |
| `substrate/lock_in.py` | 270 | `# TODO: Optimize with batch query` |
| `substrate/lock_in.py` | 273 | `# TODO: Implement tag sibling counting` |
| `engine.py` | 935 | `# TODO: Graph pruning, consolidation, etc.` |
| `engine.py` | 1248 | `# TODO: Flush WAL` |
| `actors/history_manager.py` | 616 | `# TODO: Notify Scribe actor to process compression` |
| `actors/history_manager.py` | 631 | `# TODO: Notify Scribe actor to process extraction` |
| `actors/director.py` | 734 | `# TODO: Implement Scribe extraction here` |
| `entities/storage.py` | 234 | `# TODO: Integrate with vector search when embeddings are available` |
| `entities/reflection.py` | 408 | `evidence_nodes=[],  # TODO: Link to actual memory nodes` |

### Potentially Unused Code

1. **`identity/__init__.py`** - 1 line, appears to be empty placeholder
2. **`memory/constellation.py`** - `Constellation` and `ConstellationAssembler` may not be fully integrated
3. **`tools/file_tools.py`** - Check if file tools are actually registered and used
4. **`tools/memory_tools.py`** - Verify tool registration in main workflow
5. **`librarian/cluster_retrieval.py`** - Appears to be newer module, verify integration

---

## Large Files (>500 lines) - Refactoring Candidates

### Critical: `api/server.py` (4,650 lines)

**Recommendation:** Split into multiple modules:
- `api/routes/chat.py` - Chat endpoints
- `api/routes/memory.py` - Memory/Matrix endpoints
- `api/routes/tuning.py` - Tuning endpoints
- `api/routes/voice.py` - Voice endpoints
- `api/routes/orb.py` - Orb state WebSocket
- `api/models/` - Pydantic models

### High Priority: `actors/director.py` (2,184 lines)

**Recommendation:** Extract specialized components:
- `actors/director/base.py` - Core DirectorActor
- `actors/director/generation.py` - Generation logic
- `actors/director/streaming.py` - Streaming handlers
- `actors/director/personality.py` - Personality/reflection

### Moderate: Files 1,000-1,500 lines

| File | Lines | Recommendation |
|------|-------|----------------|
| `substrate/memory.py` | 1,405 | Consider extracting search methods |
| `engine.py` | 1,287 | Core file, acceptable size |
| `entities/context.py` | 1,202 | Extract IdentityBuffer to separate file |
| `entities/resolution.py` | 1,159 | Consider splitting resolution strategies |
| `actors/librarian.py` | 1,028 | Acceptable - single responsibility |
| `actors/history_manager.py` | 1,007 | Acceptable - single responsibility |

---

## Decorators Used

### Standard Python Decorators

| Decorator | Count | Primary Usage |
|-----------|-------|---------------|
| `@dataclass` | 58 | Data containers throughout codebase |
| `@property` | 48 | Computed properties on classes |
| `@classmethod` | 18 | Alternative constructors (from_dict, from_row, load) |
| `@staticmethod` | 7 | Utility methods (mostly in ChatUI) |
| `@abstractmethod` | 1 | Actor.handle() in base class |

### Framework Decorators

| Decorator | Count | File |
|-----------|-------|------|
| `@app.get()` | 20+ | api/server.py |
| `@app.post()` | 30+ | api/server.py |
| `@app.websocket()` | 2 | api/server.py |
| `@asynccontextmanager` | 1 | api/server.py (lifespan) |

### Decorator Locations

```python
# @abstractmethod usage
actors/base.py:143    async def handle(self, msg: Message) -> None

# @property usage (sample)
engine.py:91          uptime_seconds
engine.py:1112        voice
engine.py:1117        director
engine.py:1122        librarian
actors/director.py:143 is_processing
actors/director.py:419 local_model_info
actors/director.py:424 is_local_loaded
actors/matrix.py:61   matrix
actors/matrix.py:66   graph
actors/matrix.py:73   is_ready
core/context.py:179   is_expired
core/context.py:187   age_turns
core/context.py:192   idle_turns
agentic/loop.py:221   status
agentic/loop.py:228   current_iteration

# @classmethod usage (sample)
substrate/memory.py:85    MemoryNode.from_row()
consciousness/state.py:157 ConsciousnessState.load()
consciousness/state.py:211 ConsciousnessState.default()
entities/models.py:142    Entity.from_row()
tuning/session.py:38      TuningIteration.from_dict()
llm/config.py:48          ProviderConfig.from_dict()
llm/config.py:78          LLMConfig.load()
```

---

## Module Dependencies (Key Imports)

### Core Dependencies
- `asyncio` - Throughout for async/await
- `logging` - All modules
- `dataclasses` - Heavy use of @dataclass
- `typing` - Type hints throughout
- `pathlib` - File path handling
- `json` - Data serialization

### External Dependencies
- `fastapi` - API server
- `pydantic` - Request/response validation
- `anthropic` - Claude API
- `networkx` - Graph operations
- `sqlite3/aiosqlite` - Database
- `tiktoken` - Token counting (optional)
- `mlx` - Local inference (optional)

### Internal Import Patterns

Most modules follow this pattern:
```python
from luna.actors.base import Actor, Message
from luna.core.events import InputEvent, EventType
from luna.substrate.memory import MemoryMatrix, MemoryNode
```

---

## Recommendations

### Immediate Actions

1. **Refactor `api/server.py`** - 4,650 lines is too large for maintainability
2. **Address TODO comments** - 15 unresolved TODOs need attention
3. **Verify unused modules** - Check if `identity/`, `tools/` are fully integrated

### Architecture Improvements

1. **Extract Pydantic models** from `api/server.py` to separate `api/models/` package
2. **Create interface protocols** for actor communication patterns
3. **Add type stubs** for external dependencies without types

### Testing Priorities

1. `engine.py` - Core orchestration
2. `substrate/memory.py` - Memory operations
3. `actors/director.py` - LLM generation
4. `core/context.py` - Context management

---

## Appendix: File Tree Structure

```
src/luna/
├── __init__.py (10)
├── engine.py (1,287)
├── actors/
│   ├── __init__.py (16)
│   ├── base.py (181)
│   ├── director.py (2,184)
│   ├── history_manager.py (1,007)
│   ├── librarian.py (1,028)
│   ├── matrix.py (442)
│   └── scribe.py (827)
├── agentic/
│   ├── __init__.py (52)
│   ├── loop.py (938)
│   ├── planner.py (486)
│   └── router.py (423)
├── api/
│   ├── __init__.py (5)
│   └── server.py (4,650)
├── cli/
│   ├── __init__.py (6)
│   ├── console.py (541)
│   └── debug.py (495)
├── consciousness/
│   ├── __init__.py (14)
│   ├── attention.py (181)
│   ├── personality.py (155)
│   └── state.py (251)
├── context/
│   ├── __init__.py (5)
│   └── pipeline.py (379)
├── core/
│   ├── __init__.py (39)
│   ├── context.py (875)
│   ├── events.py (92)
│   ├── input_buffer.py (152)
│   ├── protected.py (135)
│   ├── state.py (35)
│   └── tasks.py (264)
├── diagnostics/
│   ├── __init__.py (20)
│   ├── critical_systems.py (187)
│   ├── health.py (641)
│   └── watchdog.py (278)
├── entities/
│   ├── __init__.py (73)
│   ├── bootstrap.py (216)
│   ├── context.py (1,202)
│   ├── lifecycle.py (377)
│   ├── models.py (731)
│   ├── reflection.py (449)
│   ├── resolution.py (1,159)
│   └── storage.py (575)
├── extraction/
│   ├── __init__.py (32)
│   ├── chunker.py (338)
│   └── types.py (244)
├── identity/
│   └── __init__.py (1)
├── inference/
│   ├── __init__.py (36)
│   └── local.py (604)
├── librarian/
│   ├── __init__.py (5)
│   └── cluster_retrieval.py (360)
├── llm/
│   ├── __init__.py (69)
│   ├── base.py (101)
│   ├── config.py (174)
│   ├── registry.py (139)
│   └── providers/
│       ├── __init__.py (6)
│       ├── claude_provider.py (169)
│       ├── gemini_provider.py (233)
│       └── groq_provider.py (155)
├── memory/
│   ├── __init__.py (43)
│   ├── cluster_manager.py (580)
│   ├── clustering_engine.py (504)
│   ├── constellation.py (313)
│   ├── lock_in.py (424)
│   └── ring.py (161)
├── services/
│   ├── __init__.py (24)
│   ├── clustering_service.py (222)
│   ├── lockin_service.py (267)
│   ├── orb_state.py (268)
│   ├── performance_orchestrator.py (210)
│   └── performance_state.py (172)
├── substrate/
│   ├── __init__.py (27)
│   ├── database.py (232)
│   ├── embeddings.py (370)
│   ├── graph.py (502)
│   ├── local_embeddings.py (194)
│   ├── lock_in.py (285)
│   └── memory.py (1,405)
├── tools/
│   ├── __init__.py (92)
│   ├── file_tools.py (357)
│   ├── memory_tools.py (372)
│   └── registry.py (308)
└── tuning/
    ├── __init__.py (27)
    ├── evaluator.py (481)
    ├── params.py (787)
    └── session.py (420)
```

---

*End of Module Audit Report*
