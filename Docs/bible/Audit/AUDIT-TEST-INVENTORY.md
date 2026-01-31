# AUDIT-TEST-INVENTORY.md

**Generated:** 2026-01-30
**Agent:** Test Inventory
**Phase:** 1.8

## Summary
- Test files: 32
- Test functions: 494
- Coverage by module: ~70% (estimated - many modules have tests)
- Skipped tests: 2 (conditional based on platform/dependencies)

## Test File Count

| # | Test File | Test Functions | Lines |
|---|-----------|----------------|-------|
| 1 | `tests/conftest.py` | 6 fixtures | 86 |
| 2 | `tests/test_input_buffer.py` | 16 | 184 |
| 3 | `tests/test_actors.py` | 13 | 212 |
| 4 | `tests/test_api.py` | 10 | 187 |
| 5 | `tests/test_memory.py` | 15 | 211 |
| 6 | `tests/test_embeddings.py` | 11 | 153 |
| 7 | `tests/test_engine.py` | 15 | 239 |
| 8 | `tests/test_librarian.py` | 20 | 308 |
| 9 | `tests/test_consciousness.py` | 36 | 552 |
| 10 | `tests/test_lock_in.py` | 13 | 113 |
| 11 | `tests/test_actor_registration.py` | 18 | 307 |
| 12 | `tests/test_lock_in_integration.py` | 6 | 437 |
| 13 | `tests/test_extraction_pipeline.py` | 15 | 644 |
| 14 | `tests/test_agentic_wiring.py` | 18 | 341 |
| 15 | `tests/test_conversation_flow.py` | 4 | 90 |
| 16 | `tests/test_memory_retrieval_e2e.py` | 4 | 72 |
| 17 | `tests/test_scribe.py` | 18 | 392 |
| 18 | `tests/test_local_inference.py` | 17 | 256 |
| 19 | `tests/test_entity_system.py` | 37 | 1155 |
| 20 | `tests/test_voice.py` | 28 | 410 |
| 21 | `tests/test_history_manager.py` | 20 | 401 |
| 22 | `tests/test_history_integration.py` | 11 | 261 |
| 23 | `tests/test_tuning.py` | 36 | 539 |
| 24 | `tests/test_entity_system_e2e.py` | 17 | 419 |
| 25 | `tests/test_ring_buffer.py` | 26 | 265 |
| 26 | `tests/test_context_pipeline.py` | 18 | 332 |
| 27 | `tests/test_director_integration.py` | 23 | 599 |
| 28 | `tests/test_planning.py` | 20 | 238 |
| 29 | `tests/test_mcp_memory_tools.py` | 10 | 204 |
| 30 | `tests/diagnostics/test_health.py` | 11 | 287 |
| 31 | `tests/test_critical_systems.py` | 14 | 129 |
| 32 | `tests/__init__.py` | 0 | - |

**Total: 32 files, ~494 test functions**

## Test Function Count

### By Category

| Category | Count | Description |
|----------|-------|-------------|
| Unit Tests | ~380 | Isolated component tests |
| Integration Tests | ~85 | Component interaction tests |
| E2E Tests | ~20 | End-to-end flow tests |
| Smoke Tests | ~9 | Critical system availability tests |

### Top Test Files by Function Count

1. `test_entity_system.py` - 37 tests (Entity CRUD, versioning, resolution)
2. `test_consciousness.py` - 36 tests (Attention, personality, state)
3. `test_tuning.py` - 36 tests (ParamRegistry, Evaluator, Sessions)
4. `test_voice.py` - 28 tests (TTS, STT, prosody, backend)
5. `test_ring_buffer.py` - 26 tests (ConversationRing behavior)
6. `test_director_integration.py` - 23 tests (Director context pipeline)
7. `test_planning.py` - 20 tests (Query routing, delegation)
8. `test_history_manager.py` - 20 tests (History tiers, rotation)
9. `test_librarian.py` - 20 tests (Filing, wiring, pruning)

## Coverage by Module

### Fully Tested Modules (Good Coverage)

| Module Path | Test File | Coverage |
|-------------|-----------|----------|
| `src/luna/core/input_buffer.py` | `test_input_buffer.py` | HIGH |
| `src/luna/core/events.py` | `test_input_buffer.py` | HIGH |
| `src/luna/core/state.py` | `test_engine.py` | HIGH |
| `src/luna/actors/base.py` | `test_actors.py` | HIGH |
| `src/luna/actors/director.py` | `test_planning.py`, `test_director_integration.py`, `test_local_inference.py` | HIGH |
| `src/luna/actors/librarian.py` | `test_librarian.py` | HIGH |
| `src/luna/actors/scribe.py` | `test_scribe.py` | HIGH |
| `src/luna/actors/matrix.py` | `test_memory.py`, `test_lock_in_integration.py` | HIGH |
| `src/luna/actors/history_manager.py` | `test_history_manager.py`, `test_history_integration.py` | HIGH |
| `src/luna/substrate/memory.py` | `test_memory.py`, `test_lock_in_integration.py` | HIGH |
| `src/luna/substrate/embeddings.py` | `test_embeddings.py` | HIGH |
| `src/luna/substrate/database.py` | `test_memory.py` | MEDIUM |
| `src/luna/substrate/lock_in.py` | `test_lock_in.py` | HIGH |
| `src/luna/engine.py` | `test_engine.py`, `test_actor_registration.py` | HIGH |
| `src/luna/consciousness/attention.py` | `test_consciousness.py` | HIGH |
| `src/luna/consciousness/personality.py` | `test_consciousness.py` | HIGH |
| `src/luna/consciousness/state.py` | `test_consciousness.py` | HIGH |
| `src/luna/extraction/types.py` | `test_scribe.py`, `test_librarian.py` | HIGH |
| `src/luna/extraction/chunker.py` | `test_scribe.py` | HIGH |
| `src/luna/inference/local.py` | `test_local_inference.py` | HIGH |
| `src/luna/agentic/loop.py` | `test_agentic_wiring.py` | HIGH |
| `src/luna/agentic/planner.py` | `test_agentic_wiring.py` | MEDIUM |
| `src/luna/agentic/router.py` | `test_planning.py`, `test_conversation_flow.py` | HIGH |
| `src/luna/entities/resolution.py` | `test_entity_system.py`, `test_entity_system_e2e.py` | HIGH |
| `src/luna/entities/context.py` | `test_entity_system_e2e.py` | MEDIUM |
| `src/luna/memory/ring.py` | `test_ring_buffer.py` | HIGH |
| `src/luna/context/pipeline.py` | `test_context_pipeline.py`, `test_director_integration.py` | HIGH |
| `src/luna/tuning/params.py` | `test_tuning.py` | HIGH |
| `src/luna/tuning/evaluator.py` | `test_tuning.py` | HIGH |
| `src/luna/tuning/session.py` | `test_tuning.py` | HIGH |
| `src/luna/diagnostics/health.py` | `tests/diagnostics/test_health.py` | HIGH |
| `src/luna/api/server.py` | `test_api.py` | MEDIUM |
| `src/luna/tools/registry.py` | `test_agentic_wiring.py` | MEDIUM |

### Partially Tested Modules (Gaps Exist)

| Module Path | Notes |
|-------------|-------|
| `src/luna/substrate/graph.py` | Indirectly tested via memory tests |
| `src/luna/entities/models.py` | Covered by entity_system tests |
| `src/luna/entities/storage.py` | Implicitly tested |
| `src/luna/entities/bootstrap.py` | No dedicated tests |
| `src/luna/entities/lifecycle.py` | No dedicated tests |
| `src/luna/entities/reflection.py` | No dedicated tests |
| `src/luna/tools/memory_tools.py` | Tested via agentic wiring |
| `src/luna/tools/file_tools.py` | Tested via agentic wiring |

## Untested Modules

The following modules in `src/luna/` have no direct test coverage:

| Module Path | Priority | Notes |
|-------------|----------|-------|
| `src/luna/cli/console.py` | LOW | CLI wrapper, hard to unit test |
| `src/luna/cli/debug.py` | LOW | Debug utilities |
| `src/luna/core/tasks.py` | MEDIUM | Task scheduling |
| `src/luna/core/context.py` | MEDIUM | Context management |
| `src/luna/core/protected.py` | HIGH | Protection mechanisms |
| `src/luna/identity/__init__.py` | LOW | Package init |
| `src/luna/librarian/cluster_retrieval.py` | HIGH | Cluster-based retrieval |
| `src/luna/memory/cluster_manager.py` | MEDIUM | Cluster management |
| `src/luna/memory/clustering_engine.py` | MEDIUM | Clustering algorithms |
| `src/luna/memory/constellation.py` | HIGH | Memory constellation |
| `src/luna/memory/lock_in.py` | MEDIUM | Redundant with substrate lock_in? |
| `src/luna/services/clustering_service.py` | MEDIUM | Service layer |
| `src/luna/services/lockin_service.py` | MEDIUM | Service layer |
| `src/luna/services/orb_state.py` | LOW | UI state |
| `src/luna/services/performance_state.py` | LOW | Performance tracking |
| `src/luna/services/performance_orchestrator.py` | LOW | Performance orchestration |
| `src/luna/llm/base.py` | MEDIUM | Base LLM interface |
| `src/luna/llm/registry.py` | MEDIUM | Provider registry |
| `src/luna/llm/config.py` | LOW | Configuration |
| `src/luna/llm/providers/*.py` | HIGH | LLM providers (only smoke tests) |
| `src/luna/diagnostics/critical_systems.py` | MEDIUM | Critical checks |
| `src/luna/diagnostics/watchdog.py` | MEDIUM | System monitoring |
| `src/luna/substrate/local_embeddings.py` | HIGH | Local embedding generation |

## Skipped Tests

| Test | Skip Reason | File |
|------|-------------|------|
| `test_piper_synthesis` | `@pytest.mark.skipif(True, ...)` - Requires piper-tts package | `test_voice.py:42` |
| `test_apple_synthesis` | Conditional on `is_available()` - Not on macOS | `test_voice.py:69` |
| Various entity e2e tests | Skip if database not found at `~/.luna/luna.db` | `test_entity_system_e2e.py` |
| MCP memory tests | Skip if servers not running | `test_mcp_memory_tools.py` |

## Test Categories

### Unit Tests (~380 tests)
- Test single components in isolation
- Use mocks for dependencies
- Fast execution (<1 second each)

**Key Unit Test Files:**
- `test_input_buffer.py` - Buffer operations
- `test_actors.py` - Actor lifecycle
- `test_memory.py` - Memory CRUD
- `test_consciousness.py` - State management
- `test_ring_buffer.py` - Ring buffer operations
- `test_lock_in.py` - Coefficient calculations
- `test_planning.py` - Query routing

### Integration Tests (~85 tests)
- Test component interactions
- May use real database (temp files)
- Medium execution time

**Key Integration Test Files:**
- `test_lock_in_integration.py` - Lock-in across components
- `test_extraction_pipeline.py` - Scribe to Librarian flow
- `test_agentic_wiring.py` - AgentLoop connections
- `test_history_integration.py` - History tier rotation
- `test_director_integration.py` - Director pipeline

### E2E Tests (~20 tests)
- Test complete user scenarios
- Use real database (production copy)
- Longer execution time

**Key E2E Test Files:**
- `test_entity_system_e2e.py` - Marzipan memory flow
- `test_memory_retrieval_e2e.py` - Full retrieval path
- `test_mcp_memory_tools.py` - MCP tool chain

### Smoke Tests (~9 tests)
- Verify critical systems are operational
- Check environment, imports, database

**Key Smoke Test Files:**
- `test_critical_systems.py` - Environment, imports, DB checks

## Fixtures Reference

### Global Fixtures (`conftest.py`)

| Fixture | Scope | Description |
|---------|-------|-------------|
| `event_loop` | function | Creates async event loop for tests |
| `temp_data_dir` | function | Temporary directory for test data |
| `engine_config` | function | Test engine configuration |
| `input_buffer` | function | Fresh InputBuffer instance |
| `sample_event` | function | Sample TEXT_INPUT event |
| `interrupt_event` | function | Sample USER_INTERRUPT event |
| `mock_actor` | function | MockActor for testing |

### Common Test Fixtures

| Fixture | File | Description |
|---------|------|-------------|
| `memory_matrix` | Multiple | Creates isolated MemoryMatrix |
| `temp_db` | `test_health.py` | Temp SQLite with schema |
| `populated_db` | `test_health.py` | DB with sample data |
| `mock_engine` | Multiple | Engine with mocked actors |
| `mock_db` | Multiple | AsyncMock database |
| `scribe_with_mock_client` | `test_extraction_pipeline.py` | Scribe with mocked Claude |
| `director_with_pipeline` | `test_director_integration.py` | Director with context pipeline |
| `entity_resolver` | `test_entity_system.py` | Entity resolution component |

## Performance Notes

### Slow Tests (Potential Flakiness)

| Test | File | Issue |
|------|------|-------|
| `test_engine_starts_and_stops` | `test_engine.py` | Timing dependent, uses asyncio.sleep |
| `test_cognitive_ticks_increment` | `test_engine.py` | Race condition potential |
| `test_pruning_respects_lock_in` | `test_lock_in_integration.py` | Complex setup, long test |
| `test_full_extraction_pipeline` | `test_extraction_pipeline.py` | End-to-end, many async ops |
| `test_five_turn_conversation` | `test_context_pipeline.py` | Multi-step integration |

### Known Test Issues

1. **Engine Lifecycle Tests** (5 tests in `test_engine.py`)
   - Use `asyncio.wait_for` with timeouts
   - May fail under heavy load
   - Recommendation: Increase timeouts or use event-based signaling

2. **Database-Dependent Tests**
   - Many tests create temp databases
   - Can leave orphan files on failure
   - Recommendation: Add cleanup in teardown

3. **Mock Client Tests**
   - Tests mock Claude/Anthropic clients
   - Won't catch API changes
   - Recommendation: Add contract tests

## Test Execution Patterns

### Markers Used

| Marker | Count | Usage |
|--------|-------|-------|
| `@pytest.mark.asyncio` | ~180 | Async test functions |
| `@pytest.mark.skipif` | 2 | Conditional skips |

### Parametrization

Limited use of `@pytest.mark.parametrize`. Consider adding for:
- Multiple input variations in routing tests
- Different node types in memory tests
- Various entity types in entity tests

## Recommendations

### High Priority Gaps
1. **LLM Providers** - Need integration tests (not just imports)
2. **Local Embeddings** - No tests for `substrate/local_embeddings.py`
3. **Cluster Retrieval** - No tests for `librarian/cluster_retrieval.py`
4. **Memory Constellation** - No tests for `memory/constellation.py`
5. **Protected Systems** - No tests for `core/protected.py`

### Test Infrastructure Improvements
1. Add `pytest-timeout` to prevent hanging tests
2. Add `pytest-randomly` to detect order-dependent tests
3. Consider `pytest-xdist` for parallel execution
4. Add coverage reporting (`pytest-cov`)

### Missing Test Types
1. **Contract Tests** - API compatibility with Claude/Anthropic
2. **Load Tests** - Concurrent access patterns
3. **Regression Tests** - Specific bug prevention (Marzipan scenario covered)
