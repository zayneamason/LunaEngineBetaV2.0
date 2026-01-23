# Claude Code Handoff: Bible Part II Update

**Task:** Update Part II (System Architecture) to reflect new architecture  
**Priority:** Documentation alignment  
**Dependencies:** Read the new Part VI-X in `LUNA ENGINE Bible/` first  
**Date:** December 29, 2025

---

## Summary

Part II: System Architecture is **outdated**. It reflects the v1.0 design where Claude API was the primary reasoning engine. The new architecture has:

1. **Director LLM** (local 3B/7B) as Luna's actual mind
2. **Runtime Engine** with Actor model for fault isolation
3. **Encrypted Vault** as the outer container
4. **Shadow Reasoner** pattern for cloud delegation

The current Part II needs surgical updates, not a full rewrite. The bones are good — the Layer Model concept is still valid — but the details are stale.

---

## Section-by-Section Changes

### 2.1 The Layer Model (Diagram Update)

**Current:** 3 layers (Interfaces → Runtime → Constitutional)

**Needed:** 4 layers + Vault wrapper

```
┌─────────────────────────────────────────────────────────────┐
│                    ENCRYPTED VAULT                          │
│              (LunaVault.sparsebundle)                       │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                LAYER 2: INTERFACES                    │  │
│  │       Voice / Desktop / Mobile / MCP / AR             │  │
│  │              (Thin clients, stateless)                │  │
│  └───────────────────────────────────────────────────────┘  │
│                            │                                │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              LAYER 1.5: RUNTIME ENGINE                │  │
│  │                                                       │  │
│  │   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐ │  │
│  │   │DIRECTOR │  │ MATRIX  │  │  VOICE  │  │  OVEN   │ │  │
│  │   │  ACTOR  │  │  ACTOR  │  │  ACTOR  │  │  ACTOR  │ │  │
│  │   │         │  │         │  │         │  │         │ │  │
│  │   │ 3B/7B   │  │ SQLite  │  │ STT/TTS │  │ Claude  │ │  │
│  │   │ LoRA    │  │ FAISS   │  │ Audio   │  │ Deleg.  │ │  │
│  │   └─────────┘  └─────────┘  └─────────┘  └─────────┘ │  │
│  │                                                       │  │
│  │          Actor mailboxes, fault isolation             │  │
│  └───────────────────────────────────────────────────────┘  │
│                            │                                │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              LAYER 1: COGNITIVE TEAM                  │  │
│  │                                                       │  │
│  │      ┌──────────┐              ┌──────────┐          │  │
│  │      │  SCRIBE  │              │ LIBRARIAN│          │  │
│  │      │ (Ben)    │─────────────▶│ (Dude)   │          │  │
│  │      │          │  extractions │          │          │  │
│  │      │ Chunking │              │ Filing   │          │  │
│  │      │ Extract  │              │ Edges    │          │  │
│  │      └──────────┘              └──────────┘          │  │
│  │                                                       │  │
│  │           Event-driven memory processing              │  │
│  └───────────────────────────────────────────────────────┘  │
│                            │                                │
│  ┌───────────────────────────────────────────────────────┐  │
│  │            LAYER 0.5: ACCELERATION                    │  │
│  │                                                       │  │
│  │    memory_vectors.faiss    identity_buffer.safetensors│  │
│  │    (semantic search)       (pre-computed KV cache)    │  │
│  │                                                       │  │
│  │              Derived. Rebuildable.                    │  │
│  └───────────────────────────────────────────────────────┘  │
│                            │                                │
│  ┌───────────────────────────────────────────────────────┐  │
│  │            LAYER 0: CONSTITUTIONAL                    │  │
│  │                                                       │  │
│  │                  memory_matrix.db                     │  │
│  │                                                       │  │
│  │                 LUNA IS THIS FILE                     │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Key changes:**
- Add Vault as outermost container
- Add Layer 1.5: Runtime Engine with Actor boxes
- Rename Layer 1 to "Cognitive Team" (Scribe/Librarian)
- Add `identity_buffer.safetensors` to Layer 0.5
- Show Actor pattern explicitly

---

### 2.2 Component Overview (Table Update)

**Current table is missing key components. Replace with:**

| Component | Alias | Function | Layer | New in v2 |
|-----------|-------|----------|-------|-----------|
| **Vault** | Shell | Encrypted container, sovereignty boundary | Outer | ✅ |
| **Runtime Engine** | Nervous System | Actor orchestration, tick loop, fault isolation | 1.5 | ✅ |
| **Director LLM** | Mind | Local 3B/7B model that IS Luna | 1.5 | ✅ |
| **Scribe** | Ben Franklin | Conversation → structured extractions | 1 | - |
| **Librarian** | The Dude | Extractions → filed nodes + edges | 1 | - |
| **Oven** | Shadow Reasoner | Async Claude delegation | 1.5 | Updated |
| **Memory Matrix** | Soul | SQLite + FTS5 + Graph | 0 | - |
| **FAISS Index** | Reflex | Semantic vector search | 0.5 | - |
| **KV Cache** | Identity Buffer | Pre-computed personality context | 0.5 | ✅ |

---

### 2.3 Data Flow (Major Rewrite)

**Current:** Linear flow (Whisper → Classify → Search → Claude → TTS)

**Needed:** Parallel speculative flow with local LLM primary

```
                         USER STARTS SPEAKING
                                  │
            ┌─────────────────────┴─────────────────────┐
            │                                           │
            ▼                                           ▼
    ┌──────────────┐                          ┌──────────────┐
    │   WHISPER    │                          │ SPECULATIVE  │
    │   (stream)   │                          │  RETRIEVAL   │
    │              │                          │              │
    │  Partial     │─────────────────────────▶│ Start search │
    │  transcripts │    trigger on partial    │ on partial   │
    └──────────────┘                          └──────────────┘
            │                                           │
            │ Final transcript                          │ Results ready
            ▼                                           ▼
    ┌──────────────────────────────────────────────────────────┐
    │                    DIRECTOR LLM (LOCAL)                   │
    │                                                           │
    │   ┌─────────────┐     ┌─────────────┐     ┌───────────┐  │
    │   │  KV Cache   │     │   Context   │     │  Generate │  │
    │   │  (pre-warm) │────▶│  Assembly   │────▶│  Response │  │
    │   │   ~5ms      │     │   ~10ms     │     │  ~250ms   │  │
    │   └─────────────┘     └─────────────┘     └───────────┘  │
    │                                                  │        │
    │                              ┌───────────────────┤        │
    │                              │ <REQ_CLAUDE>?     │        │
    │                              ▼                   ▼        │
    │                       ┌───────────┐      ┌───────────┐   │
    │                       │  DELEGATE │      │  STREAM   │   │
    │                       │  to Oven  │      │  to TTS   │   │
    │                       └───────────┘      └───────────┘   │
    │                                                           │
    └───────────────────────────────────────────────────────────┘
                                  │
                                  ▼
                         USER HEARS LUNA
                       (<500ms to first word)
```

**Key changes:**
- Speculative retrieval runs PARALLEL to STT
- Director LLM is PRIMARY (not Claude)
- KV cache pre-warming
- `<REQ_CLAUDE>` delegation signal triggers Oven
- Target latency now <500ms (was ~700ms)

---

### 2.4 New Section: Actor Model

**Add this section (doesn't exist in v1):**

```markdown
## 2.4 Actor Model

Each runtime component is an isolated Actor with its own mailbox:

| Actor | Responsibility | Failure Mode |
|-------|---------------|--------------|
| Director | LLM inference, state machine | Returns graceful error |
| Matrix | SQLite/FAISS/Graph ops | Returns empty results |
| Voice | STT/TTS/Audio I/O | Silence, retry |
| Scribe | Extraction, classification | Queue for later |
| Librarian | Filing, edge creation | Queue for later |
| Oven | Claude delegation | Timeout, local fallback |

**Why Actors?**
- If FAISS crashes during search, Matrix Actor returns empty results
- Director handles gracefully ("I'm having trouble remembering...")
- System doesn't freeze — one actor's failure is contained

**Communication:** Async message passing, not direct function calls.
```

---

### 2.5 New Section: Tiered Execution

**Add this section (referenced in v1 Part VIII but needs updating):**

```markdown
## 2.5 Tiered Execution

| Tier | Model | Latency | Use Case |
|------|-------|---------|----------|
| Hot | Local 3B + LoRA | <500ms | Conversation, greetings, memory recall |
| Warm | Local 7B + LoRA | <2s | Complex reasoning, multi-step |
| Cold | Claude API | 2-10s | Research, code gen, document analysis |

**Routing:**
- Director LLM learns when to delegate (trained behavior)
- Outputs `<REQ_CLAUDE>` token when task exceeds local capability
- Not hardcoded rules — intuition from training

**Fallback:**
- If Claude unavailable → Warm tier handles (reduced quality)
- If Warm unavailable → Hot tier handles (best effort)
- Luna ALWAYS responds — graceful degradation
```

---

## Files to Reference

Before updating Part II, CC should read:

1. `LUNA ENGINE Bible/BIBLE-UPDATE-PART-VI-DIRECTOR-LLM.md` — Director architecture
2. `LUNA ENGINE Bible/BIBLE-UPDATE-PART-VII-RUNTIME-ENGINE.md` — Actor model details
3. `LUNA ENGINE Bible/BIBLE-UPDATE-PART-IX-PERFORMANCE.md` — Latency budget breakdown
4. `LUNA ENGINE Bible/BIBLE-UPDATE-PART-X-SOVEREIGNTY.md` — Vault architecture
5. `LUNA ENGINE Bible/GEMINI-OPTIMIZATION-REPORT.md` — Performance patterns

---

## What to Keep

These parts of current Part II are still valid:

- ✅ The Layer concept (0, 0.5, 1, 2)
- ✅ "LUNA IS THIS FILE" messaging
- ✅ Constitutional layer as foundation
- ✅ Derived/rebuildable concept for acceleration layer
- ✅ Hot/Warm/Cold path concept (needs detail updates)

---

## Deliverable

Update `LUNA-CORE-DESIGN-BIBLE.md` Part II in place, OR create:
`LUNA ENGINE Bible/BIBLE-UPDATE-PART-II-SYSTEM-ARCHITECTURE.md`

Recommend: Create new file in Bible folder, keep original for reference until full merge.

---

## Validation

Part II is correct when:
- [ ] Diagram shows Vault as outer container
- [ ] Diagram shows Actor boxes in Runtime Engine layer
- [ ] Component table includes Director LLM, Runtime Engine, KV Cache
- [ ] Data flow shows speculative retrieval
- [ ] Data flow shows local LLM as primary, Claude as delegation
- [ ] Actor Model section exists
- [ ] Tiered Execution section updated with 3B/7B/Claude
- [ ] Latency target is <500ms (not ~700ms)

---

*This handoff prepared by Claude (Architect) for Claude Code implementation.*
