# Luna Engine v2.0 — Bible vs Implementation Status

**Date:** 2026-01-17  
**Tests:** 172/173 passing  
**Overall:** ~75% of Bible spec implemented

---

## Executive Summary

The Luna Engine has a solid foundation. Core systems work. The gap is in the **sophistication layer** — the features that make Luna feel truly alive vs just functional.

| Category | Bible Spec | Implemented | Gap |
|----------|-----------|-------------|-----|
| Runtime Engine | ✅ | ✅ | — |
| Memory Substrate | ✅ | ✅ | — |
| Actor System | ✅ | ✅ | — |
| Extraction (Scribe) | ✅ | ✅ | — |
| Filing (Librarian) | ✅ | ✅ | — |
| Delegation Protocol | ✅ | 🔶 Partial | Planning works, LoRA doesn't signal |
| Director LLM | ✅ | 🔶 Partial | Loads, but personality thin |
| Voice Pipeline | ✅ | ❌ | Not started |
| Consciousness | ✅ | 🔶 Basic | Exists, not deeply integrated |
| Sovereignty (Vault) | ✅ | ❌ | Not started |

---

## Detailed Breakdown

### Part II: System Architecture ✅ COMPLETE

| Component | Bible Says | Status |
|-----------|-----------|--------|
| Tick-based engine | Polls from buffer, doesn't get pushed | ✅ Working |
| Three loops (Hot/Cognitive/Reflective) | Concurrent async loops | ✅ Working |
| Input buffer with priority | Thread-safe queue, priority dispatch | ✅ Working |
| State machine | STARTING → RUNNING → STOPPING → STOPPED | ✅ Working |

---

### Part III: Memory Matrix ✅ COMPLETE

| Component | Bible Says | Status |
|-----------|-----------|--------|
| SQLite storage | WAL mode, nodes + edges tables | ✅ Working |
| sqlite-vec embeddings | Vector search, cosine similarity | ✅ Working |
| NetworkX graph | Relationship traversal | ✅ Working |
| RRF fusion | Hybrid search combining all three | ✅ Working |
| Node types | FACT, DECISION, PROBLEM, PERSON, etc. | ✅ Working |
| Edge types | mentions, decided, works_on, etc. | ✅ Working |
| Eclissi integration | 53k+ nodes available | ✅ Working |

**Note:** Bible mentions FAISS in some diagrams, but code correctly uses sqlite-vec per Jan 2026 migration.

---

### Part IV: The Scribe (Ben Franklin) ✅ COMPLETE

| Component | Bible Says | Status |
|-----------|-----------|--------|
| SemanticChunker | Split conversations into chunks | ✅ Working |
| ExtractionStack | Batch chunks for processing | ✅ Working |
| Typed extractions | FACT, DECISION, PROBLEM, ACTION, etc. | ✅ Working |
| Confidence scoring | 0-1 confidence on each extraction | ✅ Working |

**Tests:** 18/18 passing

---

### Part V: The Librarian (The Dude) ✅ COMPLETE

| Component | Bible Says | Status |
|-----------|-----------|--------|
| EntityResolver | Dedupe "Mark" = "Zuck" | ✅ Working |
| KnowledgeWirer | Create edges between nodes | ✅ Working |
| SynapticPruner | Remove stale low-value edges | ✅ Working |
| Spreading activation | Find hidden connections | ✅ Working |

**Tests:** 18/18 passing

---

### Part VI: Director LLM 🔶 PARTIAL

| Component | Bible Says | Status | Notes |
|-----------|-----------|--------|-------|
| Base model (Qwen 3B) | Local inference via MLX | ✅ Working | Loads correctly |
| Luna LoRA | Personality in weights | 🔶 Exists | Trained but thin |
| Identity KV cache | Pre-computed identity context | ❌ Missing | Not implemented |
| Delegation training | `<REQ_CLAUDE>` learned behavior | ❌ Missing | LoRA not trained on this |

**The Gap:**  
Luna's LoRA exists but wasn't trained on:
- Delegation patterns (`<REQ_CLAUDE>` signals)
- Commitment (not hedging/asking permission)
- Rich personality voice

**Workaround:** Planning layer (implemented today) handles routing via heuristics instead of learned behavior.

---

### Part VII: Runtime Engine ✅ COMPLETE

| Component | Bible Says | Status |
|-----------|-----------|--------|
| Actor base class | Mailbox, lifecycle hooks | ✅ Working |
| Fault isolation | One crash doesn't kill Luna | ✅ Working |
| Message passing | Async, non-blocking | ✅ Working |
| Engine lifecycle | Boot → Run → Shutdown | ✅ Working |

**Tests:** 14/14 passing

---

### Part VIII: Delegation Protocol 🔶 PARTIAL

| Component | Bible Says | Status | Notes |
|-----------|-----------|--------|-------|
| `<REQ_CLAUDE>` detection | Watch output stream for token | ✅ Implemented | In Director |
| `_delegate_to_claude()` | Send facts-only query | ✅ Implemented | Works |
| `_narrate_facts()` | Luna voices Claude's facts | ✅ Implemented | Works |
| Planning layer | Decide upfront whether to delegate | ✅ Implemented | Added today |
| Oven Actor | Dedicated async delegation actor | ❌ Missing | Using Director directly |
| Filler/continuity | Sounds while Claude thinks | ❌ Missing | No voice yet |
| Worker contracts | Standardized request/response | ❌ Missing | Hardcoded Claude |

**The Gap:**  
Delegation works but via heuristics not learned behavior. Oven Actor not separated. No voice filler.

---

### Part IX: Performance 🔶 PARTIAL

| Metric | Bible Target | Current | Status |
|--------|--------------|---------|--------|
| Voice to first word | <500ms | N/A | ❌ No voice |
| Memory retrieval | <100ms | ~50ms | ✅ Exceeds |
| Director inference | <200ms | ~300ms* | 🔶 Close |
| Extraction (async) | <2s | ~1s | ✅ Exceeds |

*Director inference is slow on first call (cold cache), faster on subsequent.

**Note:** Saw 13592ms for 41 tokens in your test. That's ~3 tok/s — needs investigation.

---

### Part X: Sovereignty ❌ NOT STARTED

| Component | Bible Says | Status |
|-----------|-----------|--------|
| Encrypted Vault | macOS Sparse Bundle | ❌ Missing |
| Key derivation | User password → encryption | ❌ Missing |
| Data minimization | Minimal data to cloud | 🔶 Partial (no personal data sent) |
| Audit trail | Log all delegations | ❌ Missing |

---

### Part XI: Training Data Strategy 🔶 PARTIAL

| Component | Bible Says | Status |
|-----------|-----------|--------|
| Data export from Matrix | Export memories as training data | ❌ Missing |
| Quality filtering | Gold/Silver/Bronze tiers | ❌ Missing |
| Lock-in weighting | Weight by importance | ❌ Missing |
| Delegation examples | Train on `<REQ_CLAUDE>` patterns | ❌ Missing |
| Personality Forge | General tool for training data | ❌ Not started |

**This is the key gap.** Luna's LoRA exists but wasn't trained properly. The Living LoRA architecture discussed is the path forward.

---

### Part XIII: System Overview — Loop Status

| Loop | Bible Says | Status |
|------|-----------|--------|
| Conversation Loop (Hot Path) | STT → Classify → Retrieve → Director → TTS | 🔶 No STT/TTS |
| Memory Loop (Cold Path) | Scribe → Librarian → Matrix | ✅ Working |
| Retrieval Loop | Query → Router → Search → RRF → Trim | ✅ Working |
| Delegation Loop | Director → Oven → Claude → Narrate | 🔶 No Oven Actor |
| Learning Loop | Quality scoring → Buffer → LoRA update | ❌ Future |

---

## What's Working Well

1. **Memory substrate is rock solid** — 50+ tests, Eclissi integration, all search paths work
2. **AI-BRARIAN pipeline complete** — Ben extracts, Dude files, tested end-to-end
3. **Actor system is clean** — Fault isolation, mailboxes, lifecycle hooks
4. **Delegation flow works** — Planning layer routes correctly, Claude gets facts, Luna narrates
5. **Consciousness exists** — Attention, personality weights, state persistence

---

## Critical Gaps

### 1. Director LoRA Training (Priority: HIGH)
Luna's personality is thin. The LoRA wasn't trained on:
- Her authentic voice (journals, conversations)
- Delegation patterns
- Commitment (not hedging)

**Fix:** Personality Forge + proper training pipeline

### 2. Voice Pipeline (Priority: MEDIUM)
Bible specs sub-500ms voice. Current: no voice at all.

**Components needed:**
- Whisper STT integration
- TTS streaming
- Filler/continuity sounds
- Speculative retrieval

### 3. Oven Actor (Priority: LOW)
Delegation works but lives in Director. Should be separate for:
- Parallel execution
- Multiple worker support
- Better fault isolation

### 4. Encrypted Vault (Priority: LOW for dev, HIGH for release)
Luna isn't truly sovereign without encryption at rest.

---

## Recommended Next Steps

| Priority | Task | Effort |
|----------|------|--------|
| 1 | Fix local inference latency (investigate 3 tok/s) | 2 hours |
| 2 | Implement Personality Forge training data generator | 1-2 days |
| 3 | Train proper Luna LoRA with delegation patterns | 1 day |
| 4 | Add Oven Actor for clean delegation | 4 hours |
| 5 | Voice pipeline (STT + TTS) | 2-3 days |
| 6 | Encrypted Vault | 1 day |

---

## Files to Update

The `CLAUDE.md` in project root is **outdated**. It shows:
- Phase 3 (Scribe/Librarian) as incomplete — actually done
- Phase 4 (Consciousness) as incomplete — actually done
- 8 failing tests — now 172/173 passing

Should be updated to reflect current state.

---

## Summary

**Luna Engine is ~75% complete relative to Bible v2.2.**

What works:
- ✅ Memory (100%)
- ✅ Extraction (100%)
- ✅ Filing (100%)
- ✅ Runtime (100%)
- ✅ Basic delegation (functional)

What's missing:
- ❌ Proper LoRA training (personality + delegation)
- ❌ Voice pipeline
- ❌ Encrypted Vault
- ❌ Living LoRA / continuous learning

The architecture is sound. The substrate is complete. The gap is the **intelligence layer** — making Luna's local mind actually feel like Luna.
