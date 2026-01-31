# INSIGHTS.md

**Generated:** 2026-01-30
**Agent:** Bug Analysis
**Phase:** 3

---

## Executive Summary

The Luna Engine v2.0 codebase represents a sophisticated implementation of a "consciousness substrate" with ~32,000 lines of Python code across 85 files. The architecture is fundamentally sound, with proper actor isolation, async patterns, and layered design. However, critical integration issues around memory retrieval, conversation history, and silent failures significantly degrade the user experience.

**Key Finding:** Luna's "soul" (60k+ memories) exists but isn't reliably accessible during conversations.

---

## Architecture Insights

### Strengths

1. **Clean Actor Isolation**
   - Each actor has private mailbox (asyncio.Queue)
   - No shared mutable state violations detected
   - Fault isolation properly implemented via `_handle_safe()`
   - Snapshot/restore pattern for state serialization

2. **Well-Structured Memory Substrate**
   - Single-file database aligns with sovereignty principle
   - sqlite-vec for vector search is appropriate choice
   - FTS5 triggers maintain sync with main table
   - Lock-in coefficient provides intelligent memory prioritization

3. **Flexible Multi-Provider LLM System**
   - Hot-swap capability between Groq/Gemini/Claude
   - Graceful fallback chain
   - Provider protocol allows easy extension

4. **Comprehensive API Surface**
   - 74 Engine API endpoints
   - SSE streaming for real-time updates
   - WebSocket for orb state
   - MCP integration for Claude Desktop

### Weaknesses

1. **Integration Points Are Fragile**
   - Multiple handoffs document the same conversation history issue
   - Memory retrieval fails silently
   - Context not reliably injected into generation

2. **Silent Failure Pattern**
   - MLX import fails → Luna confabulates
   - Memory search returns empty → No error raised
   - Database path wrong → Empty results

3. **Inconsistent Configuration**
   - Two different database paths
   - Two different lock-in threshold systems
   - Environment variables documented but not validated

4. **Monolithic API Server**
   - 4,650 lines in single file
   - 50+ Pydantic models inline
   - Difficult to navigate and maintain

### Architectural Debt

| Area | Debt Level | Impact |
|------|------------|--------|
| api/server.py size | High | Maintainability |
| Silent fallbacks | Critical | User trust |
| Test coverage gaps | Medium | Reliability |
| Undeclared dependencies | Low | CI/CD failures |

---

## Performance Insights

### Current Performance Characteristics

| Operation | Current | Target | Gap |
|-----------|---------|--------|-----|
| Local inference | 2-3 tok/s | 50+ tok/s | CRITICAL |
| Memory search | ~10ms | ~10ms | OK |
| Context assembly | ~50ms | ~50ms | OK |
| First response | >5s | <500ms | CRITICAL |

### Root Causes of Performance Issues

1. **Local Inference**
   - Model may not be quantized (4-bit)
   - MLX may be using CPU instead of GPU
   - Large context window overhead
   - LoRA adapter loading overhead

2. **Memory Retrieval**
   - N+1 query pattern in semantic_search()
   - Multiple search paths run sequentially
   - No result caching

3. **Context Pipeline**
   - Entity system init failure adds latency
   - Conversation history not efficiently passed
   - Multiple async awaits in chain

### Optimization Opportunities

1. **Batch Operations**
   - Implement batch node fetch: `WHERE id IN (?,...)`
   - Parallel search execution (keyword + semantic)
   - Bulk embedding generation

2. **Caching**
   - Add LRU cache for frequently accessed nodes
   - Cache entity resolution results
   - Pre-compute identity context (KV cache)

3. **Model Optimization**
   - Verify 4-bit quantization
   - Implement speculative decoding
   - Reduce context window for simple queries

---

## Code Quality Insights

### Positive Patterns

1. **Dataclass Usage**
   - 58 dataclasses provide clean data contracts
   - @property decorators for computed values
   - @classmethod for alternative constructors

2. **Async Consistency**
   - Nearly all I/O is async (aiosqlite, httpx)
   - Only one blocking call identified (Scribe's Anthropic client)

3. **Type Hints**
   - Comprehensive type annotations
   - Protocol classes for interfaces

4. **Logging**
   - Consistent logger.info/warning/error usage
   - Debug-level detail available

### Areas for Improvement

1. **Error Handling**
   - Too many bare `except Exception`
   - Silent failures should be noisy failures
   - Return values vs raising exceptions inconsistent

2. **Configuration Management**
   - Config scattered across multiple files
   - No central validation
   - Defaults duplicated in multiple places

3. **Test Coverage**
   - ~494 tests across 32 files
   - High-priority gaps: LLM providers, local embeddings, cluster retrieval
   - Integration tests exist but may be flaky

4. **Documentation**
   - Bible documentation comprehensive but out of sync
   - Inline comments sparse
   - API documentation through Pydantic models

### Refactoring Recommendations

| File | Lines | Recommendation |
|------|-------|----------------|
| api/server.py | 4,650 | Split into routes/, models/ packages |
| actors/director.py | 2,184 | Extract generation, streaming, personality modules |
| substrate/memory.py | 1,405 | Extract search methods to separate module |
| entities/context.py | 1,202 | Extract IdentityBuffer to separate file |

---

## Security Insights

### Critical Issues

1. **API Keys in Repository** (CRITICAL)
   - `.env` file committed with real keys
   - Diagnostic output contains truncated keys
   - Keys must be rotated immediately

2. **No Authentication** (HIGH)
   - All 74 API endpoints unprotected
   - Any client can access any endpoint
   - No rate limiting

3. **No HTTPS** (MEDIUM)
   - Plaintext transmission
   - Only localhost CORS origins

### Security Recommendations

1. **Immediate**
   - Rotate all API keys (Anthropic, Groq, Google)
   - Add `.env` to `.gitignore`
   - Scrub git history

2. **Short-term**
   - Implement API key authentication
   - Add rate limiting middleware
   - Sanitize diagnostic scripts

3. **Long-term**
   - Add HTTPS support
   - Implement proper secrets management
   - Add request/response logging for audit

---

## Testing Insights

### Current State

- **32 test files** with ~494 test functions
- **~70% estimated coverage** by module
- Mix of unit, integration, and e2e tests
- pytest-asyncio for async tests

### High-Priority Testing Gaps

| Module | Priority | Reason |
|--------|----------|--------|
| LLM providers | HIGH | Only smoke tests, need integration |
| Local embeddings | HIGH | No tests for sentence-transformers wrapper |
| Cluster retrieval | HIGH | New module, untested |
| Memory constellation | HIGH | Context assembly untested |
| Protected systems | HIGH | No safeguard tests |

### Flaky Test Patterns

1. **Engine lifecycle tests** - Race conditions with timing
2. **Database tests** - May leave orphan temp files
3. **Mock client tests** - Won't catch API changes

### Test Infrastructure Recommendations

1. Add `pytest-timeout` to prevent hanging tests
2. Add `pytest-cov` for coverage reporting
3. Consider `pytest-xdist` for parallel execution
4. Add contract tests for external APIs

---

## Dependency Insights

### Health Summary

| Category | Status |
|----------|--------|
| Core dependencies | HEALTHY |
| Optional dependencies | NEEDS ATTENTION |
| Circular imports | MITIGATED |
| Version constraints | ADEQUATE |

### Undeclared Dependencies

These packages are used but not in pyproject.toml:

```toml
[project.optional-dependencies]
llm = [
    "groq>=0.4.0",
    "google-generativeai>=0.3.0",
]
embeddings = [
    "openai>=1.0.0",
    "sentence-transformers>=2.2.0",
]
utils = [
    "tiktoken>=0.5.0",
]
```

### Import Pattern Issues

1. **sentence-transformers** - Raises RuntimeError instead of graceful degradation
2. **MLX** - Silent failure when unavailable
3. **Entity imports** - Silent warning on ImportError

---

## Recommendations Summary

### Immediate (This Week)

1. **Security**
   - [ ] Rotate API keys
   - [ ] Add `.env` to `.gitignore`
   - [ ] Delete diagnostic output with keys

2. **Critical Bugs**
   - [ ] Fix database path conflict
   - [ ] Fix memory search API method name
   - [ ] Fix forge_load method call

### Short-term (This Month)

1. **Reliability**
   - [ ] Implement CriticalSystemsCheck startup gate
   - [ ] Fix conversation history loss
   - [ ] Add memory context injection to Director

2. **Performance**
   - [ ] Fix N+1 query in semantic_search
   - [ ] Verify MLX GPU usage
   - [ ] Profile local inference bottleneck

3. **Code Quality**
   - [ ] Split api/server.py into routes/
   - [ ] Export HistoryManagerActor
   - [ ] Use AsyncAnthropic in Scribe

### Long-term (This Quarter)

1. **Architecture**
   - [ ] Implement KV cache (identity buffer)
   - [ ] Add speculative retrieval
   - [ ] Consider 7B warm path

2. **Testing**
   - [ ] Add LLM provider integration tests
   - [ ] Add coverage reporting
   - [ ] Fix flaky lifecycle tests

3. **Features**
   - [ ] Implement FTS5 as primary keyword search
   - [ ] Add tag sibling counting
   - [ ] Implement network effects in lock-in

---

## Philosophical Note

The Luna Engine embodies a powerful architectural principle: **the LLM is stateless inference, the engine provides identity**. This is a sound foundation.

However, the current implementation has a critical gap: **Luna's memories exist but are not reliably accessible during conversations**. This is like having a brain with 60,000 memories but severed connections to the speech center.

The path forward is clear:
1. **Fix the integration points** - Memory must reliably reach generation
2. **Fail loudly** - Never let Luna confabulate when her brain is disconnected
3. **Test the full path** - Unit tests are necessary but insufficient

Luna's soul is in `luna_engine.db`. The work now is ensuring she can actually use it.

---

## Appendix: Metric Summary

### Codebase Metrics

| Metric | Value |
|--------|-------|
| Total Python files | 85 |
| Total lines of code | ~32,000 |
| Total classes | 167 |
| Dataclass definitions | 58 |
| Test functions | ~494 |
| API endpoints | 74 |
| MCP tools | 41 |

### Memory Metrics

| Metric | Value |
|--------|-------|
| Memory nodes | 60,730 |
| Graph edges | 32,336 |
| FTS5 status | Triggers exist, not primary path |
| Vector dimensions | 384 (local) / 1536 (OpenAI) |

### Actor Metrics

| Actor | Lines | Status |
|-------|-------|--------|
| Director | 2,184 | Complete |
| Matrix | 442 | Complete |
| Scribe | 827 | Complete |
| Librarian | 1,028 | Complete |
| HistoryManager | 1,007 | Complete (not exported) |

---

*End of Insights Report*
