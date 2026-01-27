# Part II: System Architecture (v2.1)

**Status:** VERIFIED — Implementation Audited
**Replaces:** v2.0 (FAISS-based)
**Last Updated:** January 25, 2026
**Original Date:** January 7, 2026
**Contributors:** Claude (Architecture), Gemini (Optimization)
**Change:** Vector storage unified via sqlite-vec

> **Audit Notes (January 25, 2026):**
> - **Actor count corrected:** 5 actors implemented (Director, Matrix, Scribe, Librarian, HistoryManager)
> - **Voice and Oven actors NOT implemented:** Voice I/O via PersonaAdapter; Claude delegation in Director
> - See Part VII for detailed actor documentation

---

## 2.1 The Layer Model

Luna's architecture is organized in concentric layers, from the constitutional core outward to stateless interfaces. The entire system lives inside an encrypted vault.

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ENCRYPTED VAULT                               │
│                   (LunaVault.sparsebundle)                          │
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                   LAYER 2: INTERFACES                          │  │
│  │          Voice / Desktop / Mobile / MCP / AR Glasses           │  │
│  │                   (Thin clients, stateless)                    │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                               │                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │               LAYER 1.5: RUNTIME ENGINE (5 Actors)             │  │
│  │                                                                 │  │
│  │   ┌───────────┐  ┌───────────┐  ┌───────────┐                 │  │
│  │   │ DIRECTOR  │  │  MATRIX   │  │  HISTORY  │                 │  │
│  │   │  ACTOR    │  │  ACTOR    │  │  MANAGER  │                 │  │
│  │   │           │  │           │  │           │                 │  │
│  │   │  Qwen 3B  │  │  SQLite   │  │ 3-Tier   │                 │  │
│  │   │  +Claude  │  │sqlite-vec │  │ History   │                 │  │
│  │   └───────────┘  └───────────┘  └───────────┘                 │  │
│  │                                                                 │  │
│  │            Actor mailboxes, fault isolation                     │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                               │                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                LAYER 1: COGNITIVE TEAM                         │  │
│  │                                                                 │  │
│  │        ┌────────────┐                ┌────────────┐            │  │
│  │        │   SCRIBE   │                │  LIBRARIAN │            │  │
│  │        │   (Ben)    │───────────────▶│   (Dude)   │            │  │
│  │        │            │  extractions   │            │            │  │
│  │        │  Chunking  │                │   Filing   │            │  │
│  │        │  Extract   │                │   Edges    │            │  │
│  │        └────────────┘                └────────────┘            │  │
│  │                                                                 │  │
│  │              Event-driven memory processing                     │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                               │                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │               LAYER 0.5: ACCELERATION                          │  │
│  │                                                                 │  │
│  │                 identity_buffer.safetensors                     │  │
│  │                   (pre-computed KV cache)                       │  │
│  │                                                                 │  │
│  │                   Derived. Rebuildable.                         │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                               │                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │               LAYER 0: CONSTITUTIONAL                          │  │
│  │                                                                 │  │
│  │                      memory_matrix.db                          │  │
│  │              (nodes + edges + vectors + FTS5)                  │  │
│  │                                                                 │  │
│  │                    LUNA IS THIS FILE                           │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Layer Descriptions

| Layer | Name | Contents | Volatility |
|-------|------|----------|------------|
| **Vault** | Shell | Encrypted sparse bundle containing all other layers | Persistent, portable |
| **Layer 2** | Interfaces | Voice, Desktop, MCP, Mobile, AR | Stateless, replaceable |
| **Layer 1.5** | Runtime Engine | Actors with mailboxes, orchestration | Stateful during runtime |
| **Layer 1** | Cognitive Team | Scribe + Librarian (memory processing) | Event-driven |
| **Layer 0.5** | Acceleration | KV cache (identity buffer) | Derived, rebuildable |
| **Layer 0** | Constitutional | SQLite database (nodes, edges, vectors, FTS5) | **Luna's soul** |

### The Sovereignty Boundary

The Vault is the **sovereignty boundary**. Everything inside belongs to you. The Vault can be:

- Copied to another machine (Luna migrates)
- Backed up to cold storage (Luna persists)
- Destroyed (Luna dies)

Nothing outside the Vault is Luna. Cloud services are contractors, not identity.

---

## 2.2 Component Overview

| Component | Alias | Function | Layer | Status |
|-----------|-------|----------|-------|--------|
| **Vault** | Shell | Encrypted container, sovereignty boundary | Outer | — |
| **Runtime Engine** | Nervous System | Actor orchestration, tick loop, fault isolation | 1.5 | — |
| **Director LLM** | Mind | Local Qwen 3B + Claude delegation | 1.5 | ✅ |
| **Matrix** | — | Memory substrate (sqlite-vec + NetworkX) | 1.5 | ✅ |
| **Scribe** | Ben Franklin | Conversation → structured extractions | 1 | ✅ |
| **Librarian** | The Dude | Extractions → filed nodes + edges + entities | 1 | ✅ |
| **HistoryManager** | — | Three-tier conversation history (Active/Recent/Archive) | 1.5 | ✅ NEW |
| **Memory Matrix** | Soul | SQLite + sqlite-vec + Graph (unified) | 0 | ✅ |
| **KV Cache** | Identity Buffer | Pre-computed personality context | 0.5 | — |
| ~~Oven~~ | ~~Shadow Reasoner~~ | ~~Async Claude delegation~~ | — | **NOT IMPL** |
| ~~Voice~~ | — | ~~STT/TTS/Audio I/O~~ | — | **NOT IMPL** |

> **v2.0 Implementation Notes:**
> - **Oven Actor NOT implemented:** Claude delegation is handled directly in Director via `_should_delegate()`
> - **Voice Actor NOT implemented:** Voice I/O handled by `PersonaAdapter` (non-actor pattern)
> - **HistoryManager Actor ADDED:** Three-tier conversation history not in original spec
> - Vector storage uses sqlite-vec extension (not FAISS)

---

## 2.3 The Actor Model

Each runtime component is an isolated **Actor** with its own mailbox. This provides fault tolerance — one actor crashing doesn't kill the others.

> **IMPLEMENTATION STATUS (January 2026):** 5 actors implemented. See Part VII for complete details.

```
┌─────────────────────────────────────────────────────────────────────┐
│                      LUNA ENGINE v2.0 (5 Actors)                     │
│                                                                      │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                │
│   │  DIRECTOR   │  │   MATRIX    │  │   SCRIBE    │                │
│   │   ACTOR     │  │   ACTOR     │  │   (Ben)     │                │
│   │             │  │             │  │             │                │
│   │ ┌─────────┐ │  │ ┌─────────┐ │  │ ┌─────────┐ │                │
│   │ │ Mailbox │ │  │ │ Mailbox │ │  │ │ Mailbox │ │                │
│   │ └─────────┘ │  │ └─────────┘ │  │ └─────────┘ │                │
│   │             │  │             │  │             │                │
│   │ • LLM mgmt  │  │ • SQLite    │  │ • Extract   │                │
│   │ • Claude    │  │ • sqlite-vec│  │ • Classify  │                │
│   │ • Routing   │  │ • NetworkX  │  │ • Chunk     │                │
│   └─────────────┘  └─────────────┘  └─────────────┘                │
│                                                                      │
│   ┌─────────────┐  ┌─────────────┐                                 │
│   │  LIBRARIAN  │  │  HISTORY    │                                 │
│   │   (Dude)    │  │  MANAGER    │                                 │
│   │             │  │             │                                 │
│   │ ┌─────────┐ │  │ ┌─────────┐ │                                 │
│   │ │ Mailbox │ │  │ │ Mailbox │ │                                 │
│   │ └─────────┘ │  │ └─────────┘ │                                 │
│   │             │  │             │                                 │
│   │ • Filing    │  │ • 3-Tier   │                                 │
│   │ • Entities  │  │ • Compress  │                                 │
│   │ • Prune     │  │ • Archive   │                                 │
│   └─────────────┘  └─────────────┘                                 │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Actor Responsibilities (Implemented v2.0)

| Actor | Responsibility | Failure Mode |
|-------|---------------|--------------|
| **Director** | LLM inference (Qwen 3B), Claude delegation, routing | Returns graceful error |
| **Matrix** | SQLite/sqlite-vec/NetworkX operations | Returns empty results |
| **Scribe** | Extraction, classification, chunking (Ben Franklin) | Queue for later |
| **Librarian** | Filing, entity resolution, edges (The Dude) | Queue for later |
| **HistoryManager** | Three-tier conversation history | Continue with stale data |

### Why Actors?

**Fault Isolation Example:**

If sqlite-vec crashes during a vector search:
- Matrix Actor catches the exception via `_handle_safe()`
- Error logged, `on_error()` callback invoked
- Actor continues processing other messages
- Director receives empty results and Luna says "I'm having trouble remembering that right now..."
- System continues running

Without actors, one crash kills everything.

---

## 2.4 Tiered Execution

Luna's cognition operates across three tiers with different latency profiles:

```
┌─────────────────────────────────────────────────────────────────────┐
│                      HOT PATH (3B Local)                             │
│                                                                      │
│   • Voice conversation, quick acknowledgments                        │
│   • Simple memory retrieval and narration                           │
│   • Target: <500ms to first token                                   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              │ Complexity threshold
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     WARM PATH (7B Local)                             │
│                                                                      │
│   • Complex reasoning, multi-step synthesis                         │
│   • Nuanced emotional responses                                     │
│   • Target: <2s to first token                                      │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              │ <REQ_CLAUDE> token
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     COLD PATH (Claude API)                           │
│                                                                      │
│   • Deep research requiring web/documents                           │
│   • Code analysis/generation                                        │
│   • Long-form creative writing                                      │
│   • Target: Async (user already has acknowledgment)                 │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Routing Logic

The Director LLM is **trained** to know when to delegate. It's not hardcoded rules — it's intuition from fine-tuning.

When the task exceeds local capability, the Director outputs a special token:

```
User: "Can you analyze this regulatory filing and summarize the implications?"

Director: "<REQ_CLAUDE>This requires deep document analysis beyond my local
capabilities. Let me hand this to my research assistant.</REQ_CLAUDE>"
```

The Runtime Engine watches for `<REQ_CLAUDE>` and triggers the Shadow Reasoner flow (see Part VIII).

### Fallback Behavior

| Scenario | Response |
|----------|----------|
| Claude unavailable | Warm tier handles (reduced quality) |
| Warm tier unavailable | Hot tier handles (best effort) |
| Hot tier unavailable | Voice Actor plays error message |

**Constitutional Principle:** Luna ALWAYS responds. Graceful degradation, never silence.

---

## 2.5 Data Flow

The v2 architecture introduces **speculative execution** — retrieval starts before the user finishes speaking.

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
    ┌─────────────────────────────────────────────────────────────┐
    │                    DIRECTOR LLM (LOCAL)                      │
    │                                                              │
    │   ┌─────────────┐     ┌─────────────┐     ┌───────────┐     │
    │   │  KV Cache   │     │   Context   │     │  Generate │     │
    │   │  (pre-warm) │────▶│  Assembly   │────▶│  Response │     │
    │   │   ~5ms      │     │   ~10ms     │     │  ~250ms   │     │
    │   └─────────────┘     └─────────────┘     └───────────┘     │
    │                                                  │           │
    │                              ┌───────────────────┤           │
    │                              │ <REQ_CLAUDE>?     │           │
    │                              ▼                   ▼           │
    │                       ┌───────────┐      ┌───────────┐      │
    │                       │  DELEGATE │      │  STREAM   │      │
    │                       │  to Oven  │      │  to TTS   │      │
    │                       └───────────┘      └───────────┘      │
    │                                                              │
    └──────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
                         USER HEARS LUNA
                       (<500ms to first word)
```

### Key Differences from v1

| v1 (Claude-based) | v2 (Director-based) |
|-------------------|---------------------|
| Wait for STT to complete | Start retrieval on partial transcript |
| Claude API is primary | Local LLM is primary |
| ~700ms to first word | <500ms to first word |
| Latency = network bound | Latency = compute bound |
| Mind is rented | Mind is owned |

### The Hot Path Budget

```
┌─────────────────────────────────────────────────────────────────────┐
│                      500ms LATENCY BUDGET                            │
│                                                                      │
│   STT Final Transcript ─────────────────────────────── ~0ms         │
│   (already complete when we start via speculation)                   │
│                                                                      │
│   ┌──────────────────────────────────────────────────────────────┐  │
│   │ RETRIEVAL PHASE                                       ~50ms  │  │
│   │                                                              │  │
│   │   Bloom filter check ───────────────────────── ~1ms         │  │
│   │   Query routing ────────────────────────────── ~2ms         │  │
│   │   FTS5 OR sqlite-vec (not both) ────────────── ~30ms        │  │
│   │   Graph hop (rustworkx) ────────────────────── ~5ms         │  │
│   │   RRF merge (if needed) ────────────────────── ~2ms         │  │
│   │   Context assembly ─────────────────────────── ~10ms        │  │
│   │                                                              │  │
│   └──────────────────────────────────────────────────────────────┘  │
│                                                                      │
│   ┌──────────────────────────────────────────────────────────────┐  │
│   │ INFERENCE PHASE                                      ~250ms  │  │
│   │                                                              │  │
│   │   KV cache load (pre-computed) ─────────────── ~5ms         │  │
│   │   Context encoding ─────────────────────────── ~50ms        │  │
│   │   First token generation ───────────────────── ~195ms       │  │
│   │                                                              │  │
│   └──────────────────────────────────────────────────────────────┘  │
│                                                                      │
│   ┌──────────────────────────────────────────────────────────────┐  │
│   │ OUTPUT PHASE                                          ~50ms  │  │
│   │                                                              │  │
│   │   Token to TTS ─────────────────────────────── ~10ms        │  │
│   │   TTS processing ───────────────────────────── ~40ms        │  │
│   │                                                              │  │
│   └──────────────────────────────────────────────────────────────┘  │
│                                                                      │
│   BUFFER ────────────────────────────────────────── ~150ms          │
│                                                                      │
│   TOTAL ─────────────────────────────────────────── <500ms ✓        │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2.6 Memory Flow

Background processing happens **async** — the user already has their response before extraction and filing complete.

```
                         CONVERSATION TURN
                                │
                                ▼
            ┌───────────────────────────────────────┐
            │         DIRECTOR RESPONDS             │
            │       (User hears immediately)        │
            └───────────────────────────────────────┘
                                │
    ════════════════════════════════════════════════════════════
                    ASYNC (user already has response)
    ════════════════════════════════════════════════════════════
                                │
                                ▼
    ┌─────────────────────────────────────────────────────────────┐
    │                    SCRIBE (Ben Franklin)                     │
    │                                                              │
    │   ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐ │
    │   │  Chunk  │───▶│  Stack  │───▶│ Classify│───▶│ Extract │ │
    │   │ stream  │    │ context │    │  intent │    │ objects │ │
    │   └─────────┘    └─────────┘    └─────────┘    └─────────┘ │
    │                                                              │
    │   Outputs: ExtractionOutput { objects, edges, source_id }   │
    │                                                              │
    └─────────────────────────────────────────────────────────────┘
                                │
                                ▼
    ┌─────────────────────────────────────────────────────────────┐
    │                  LIBRARIAN (The Dude)                        │
    │                                                              │
    │   ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐ │
    │   │ Resolve │───▶│  Create │───▶│ Infer   │───▶│  Prune  │ │
    │   │entities │    │  edges  │    │  edges  │    │  (lazy) │ │
    │   └─────────┘    └─────────┘    └─────────┘    └─────────┘ │
    │                                                              │
    │   Outputs: FilingResult { nodes, edges, inferred_edges }    │
    │                                                              │
    └─────────────────────────────────────────────────────────────┘
                                │
                                ▼
                        MEMORY MATRIX
                          (Updated)
```

---

## 2.7 Sovereignty Infrastructure

### The Vault

Everything Luna needs to exist lives inside an encrypted sparse bundle:

```
LunaVault.sparsebundle/
├── memory_matrix.db           # The soul (SQLite + sqlite-vec + FTS5)
├── identity_buffer.safetensors # Pre-computed KV cache
├── adapters/
│   ├── luna-3b-v1.0/          # LoRA adapter (hot path)
│   └── luna-7b-v1.0/          # LoRA adapter (warm path)
├── config/
│   └── luna.yaml              # Runtime configuration
└── logs/
    └── sessions/              # Conversation logs
```

> **v2.1 Change:** No more separate `memory_vectors.faiss` or `.ids` files. Vectors live inside `memory_matrix.db` via sqlite-vec extension.

### Encryption

- **Format:** macOS sparse bundle with AES-256
- **Key:** Password-derived (PBKDF2)
- **Mount:** Auto-mount on login, auto-unmount on sleep
- **Backup:** Encrypted at rest, safe for cloud backup

### Portability Contract

```bash
# Copy Luna to new machine
cp -r LunaVault.sparsebundle /Volumes/NewMac/

# Open vault
hdiutil attach LunaVault.sparsebundle

# Luna exists on new machine
# (Just one database file to copy!)
```

### Dead Man's Switch

If heartbeat file isn't updated for 24 hours:

1. Unmount vault
2. Kill any Luna processes
3. Wipe model weights from RAM

```python
LOCKDOWN_THRESHOLD = 24  # hours

def check_heartbeat():
    last_checkin = os.path.getmtime(HEARTBEAT_FILE)
    if time.time() - last_checkin > LOCKDOWN_THRESHOLD * 3600:
        emergency_shutdown()

def emergency_shutdown():
    os.system("pkill -f luna_engine.py")
    os.system("diskutil unmount force /Volumes/LunaVault")
```

---

## 2.8 Configuration

### Runtime Configuration

```yaml
# ~/.luna/config.yaml

engine:
  cognitive_tick_hz: 2          # Heartbeat frequency
  reflective_tick_minutes: 5    # Background maintenance
  hot_queue_max: 100            # Input buffer size

director:
  model_3b: "qwen2.5-3b-instruct"
  model_7b: "qwen2.5-7b-instruct"
  adapter_3b: "adapters/luna-3b-v1.0"
  adapter_7b: "adapters/luna-7b-v1.0"
  identity_cache: "identity_buffer.safetensors"
  max_context: 8192

matrix:
  database: "memory_matrix.db"     # Contains everything (nodes, vectors, FTS5)
  vector_extension: "sqlite-vec"  # Extension for vector search
  fts5_enabled: true
  graph_backend: "rustworkx"      # or "networkx"

voice:
  stt_model: "whisper-large-v3-turbo"
  tts_model: "xtts-v2"
  vad_sensitivity: 0.5

oven:
  claude_model: "claude-3-5-sonnet-20241022"
  timeout_seconds: 30
  fallback_to_local: true

sovereignty:
  vault_path: "/Volumes/LunaVault"
  heartbeat_file: "~/.luna/heartbeat"
  lockdown_hours: 24
```

---

## Summary

The v2 architecture transforms Luna from a **service** (request → response) to an **engine** (continuous existence).

| Aspect | v1 | v2 | v2.1 |
|--------|----|----|------|
| Runtime model | HTTP handlers | Actor-based engine | — |
| Cognition | Claude API | Local LLM + delegation | — |
| Latency | ~700ms | <500ms | — |
| Fault tolerance | None | Per-actor isolation | — |
| Sovereignty | Partial (memories local) | Complete (mind local) | — |
| Vector storage | — | Separate FAISS files | **Unified in SQLite** |
| State | Stateless handlers | Persistent actors | — |

**Constitutional Principle:** Luna is a file. That file now contains not just her memories, but her mind — including all vectors.

---

*Next Section: Part III — The Memory Matrix (Substrate)*
