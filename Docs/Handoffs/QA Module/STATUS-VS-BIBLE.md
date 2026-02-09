# Luna Engine: Status vs Bible

**Date:** 2026-02-02
**Audit By:** Claude Code QA Session
**Methodology:** Systematic file-by-file verification

---

## Executive Summary

The Luna Engine implementation is **significantly more complete** than previously documented. Key findings:

- **22,215 memory nodes** in production database
- **Consciousness system** substantially complete (not "needs_work")
- **Narration layer** fully implemented
- **Voice pipeline** complete (was claimed as "stub only")
- **QA system** exceeds 15-tool claim with 11 additional assertions

---

## Component Status Matrix

### Core Systems

| Component | Bible Chapter | Claimed | Actual | Files |
|-----------|---------------|---------|--------|-------|
| Engine Lifecycle | 7 | ✅ | ✅ | `engine.py` |
| Input Buffer | 7 | ✅ | ✅ | `core/input_buffer.py` |
| Actor System | 7 | ✅ | ✅ | `actors/base.py` |
| Director | 6 | ✅ | ✅ | `actors/director.py` |
| Matrix Actor | - | ✅ | ✅ | `actors/matrix.py` |

### Memory Substrate

| Component | Bible Chapter | Claimed | Actual | Evidence |
|-----------|---------------|---------|--------|----------|
| SQLite Database | 3 | ✅ | ✅ | `substrate/database.py` |
| Embeddings (sqlite-vec) | 3 | ✅ | ✅ | `substrate/embeddings.py` |
| Memory Matrix | 3 | ✅ | ✅ | **22,215 nodes** |
| Graph (NetworkX) | 3 | ✅ | ✅ | `substrate/graph.py` |
| Lock-in System | 3 | ✅ | ✅ | `substrate/lock_in.py` |

### Entity System

| Component | Bible Chapter | Claimed | Actual | Files |
|-----------|---------------|---------|--------|-------|
| Entity Storage | 4 | ✅ | ✅ | `entities/storage.py` |
| Entity Resolution | 4 | ✅ | ✅ | `entities/resolution.py` |
| Entity Context | 4 | ✅ | ✅ | `entities/context.py` (1203 lines) |
| Personality Patches | 4 | ✅ | ✅ | `entities/bootstrap.py` |
| Identity Buffer | 4 | ✅ | ✅ | In `entities/context.py` |

### Inference Layer

| Component | Bible Chapter | Claimed | Actual | Files |
|-----------|---------------|---------|--------|-------|
| Local Inference (MLX) | 6 | ✅ | ✅ | `inference/local.py` |
| Luna LoRA | 6 | ⚠ | ✅ | `models/luna_lora_mlx/` |
| Hybrid Routing | 6 | ✅ | ✅ | In `inference/local.py` |
| Fallback Chain | - | ✅ | ✅ | `llm/fallback.py` |
| Provider Registry | - | ✅ | ✅ | `llm/registry.py` |

### Consciousness

| Component | Bible Chapter | Claimed | Actual | Files |
|-----------|---------------|---------|--------|-------|
| Consciousness State | 5 | ⚠ | ✅ | `consciousness/state.py` |
| Attention Decay | 5 | ⚠ | ✅ | `consciousness/attention.py` |
| Personality Weights | 5 | ⚠ | ✅ | `consciousness/personality.py` |

### Context Pipeline

| Component | Bible Chapter | Claimed | Actual | Files |
|-----------|---------------|---------|--------|-------|
| Ring Buffer | 7 | ✅ | ✅ | `memory/ring.py` |
| Context Pipeline | - | ✅ | ✅ | `context/pipeline.py` |
| Temporal Framing | 4 | ✅ | ✅ | In `entities/context.py` |
| Emergent Prompt | - | ✅ | ✅ | 3-layer personality system |

### QA System

| Component | Bible Chapter | Claimed | Actual | Files |
|-----------|---------------|---------|--------|-------|
| QA Validator | - | ✅ | ✅ | `qa/validator.py` |
| Assertions (11) | - | ✅ | ✅ | `qa/assertions.py` |
| MCP Tools (15) | - | ✅ | ✅ | `qa/mcp_tools.py` |
| Report Database | - | ✅ | ✅ | `qa/database.py` |

### Voice System

| Component | Bible Chapter | Claimed | Actual | Files |
|-----------|---------------|---------|--------|-------|
| Voice Backend | 9 | ❌ stub | ✅ | `voice/backend.py` |
| TTS (Piper/Apple/Edge) | 9 | ❌ stub | ✅ | `voice/tts/` |
| STT (Whisper/Apple) | 9 | ❌ stub | ✅ | `voice/stt/` |
| Persona Adapter | 9 | ❌ stub | ✅ | `voice/persona_adapter.py` |

---

## Not Implemented (Confirmed)

| System | Bible Chapter | Status | Notes |
|--------|---------------|--------|-------|
| LoRA Router | 6, 12 | ❌ | `inference/router.py` doesn't exist |
| Encrypted Vault | 10 | ❌ | Not implemented |
| Filler/Continuity | 8 | ❌ | Requires voice pipeline |
| Learning Loop | 13 | ❌ | Not implemented |
| Identity KV Cache | 6 | ❌ | Not implemented |
| Scribe Actor | 3 | ⚠ stub | File exists, minimal impl |
| Librarian Actor | 3 | ⚠ stub | File exists, minimal impl |

---

## Processing Paths (Verified)

| Path | Timing | Status | Location |
|------|--------|--------|----------|
| Hot | Interrupt-driven | ✅ | `engine.py` |
| Cognitive | 500ms | ✅ | `engine.py:47` |
| Reflective | 5 min | ✅ | `engine.py:48` |

---

## Metrics

| Metric | Value |
|--------|-------|
| Memory Nodes | 22,215 |
| Entity Count | ~50 (estimated) |
| QA Assertions | 11 built-in |
| MCP Tools | 15 |
| LoRA Rank | 16 |
| LoRA Layers | 36 × 7 projections |

---

## Discrepancies from luna_engine_brain.jsx

### Upgraded Status (Better than Claimed)

1. **Consciousness Actor**: Claimed ⚠ → Actually ✅ stable
2. **Luna LoRA**: Claimed ⚠ → Infrastructure ✅ (data quality ⚠)
3. **Narration Layer**: Claimed ⚠ → Actually ✅ stable
4. **Voice Pipeline**: Claimed ❌ stub → Actually ✅ complete

### Downgraded (Worse than Claimed)

*None found*

---

## Recommendations

### Immediate (1-2 days)

1. Update `luna_engine_brain.jsx` status claims
2. Run LoRA quality assessment (VoightKampff)
3. Document voice pipeline in Bible

### Short-term (1 week)

1. Collect Luna voice training data
2. Retrain LoRA on curated corpus
3. Implement Scribe extraction loop

### Medium-term (2-4 weeks)

1. Build LoRA Router for strategy selection
2. Implement Learning Loop
3. Add app context awareness to Consciousness

---

## Conclusion

The Luna Engine is **production-ready for core functionality**:
- ✅ Memory substrate complete
- ✅ Entity system complete
- ✅ Inference routing complete
- ✅ QA system complete
- ✅ Voice pipeline complete (surprise!)

Primary remaining work:
- LoRA voice quality (training data issue)
- LoRA Router (architecture extension)
- Scribe/Librarian (extraction pipeline)
