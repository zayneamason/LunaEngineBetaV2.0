# Persona Forge Ingestion Pipeline Runbook

## Goal

**Start:** 147 examples, 77.7% health, big gaps in emotional_presence/context_recall/greeting  
**End:** 400-500 examples, 85%+ health, balanced coverage

---

## Pipeline Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        INGESTION PIPELINE                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐     │
│  │  SOURCE  │───▶│  READ    │───▶│  CLAUDE  │───▶│  ADD     │     │
│  │  LIST    │    │  RAW     │    │  EXTRACT │    │  EXAMPLE │     │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘     │
│       │                                               │            │
│       │         ┌──────────────────────────────┐     │            │
│       └────────▶│     PROGRESS TRACKING        │◀────┘            │
│                 │  • forge_assay() after batch │                  │
│                 │  • forge_gaps() to steer     │                  │
│                 │  • forge_search() to dedupe  │                  │
│                 └──────────────────────────────┘                  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Source Inventory

| Source | Count | Format | Quality | Best For |
|--------|-------|--------|---------|----------|
| Existing JSONL | 147 | Ready | 77% health | Baseline |
| Conversation Turns | 456 | SQLite | ✅ Gold | greeting, acknowledgment |
| Alpha Session Notes | 76 files | Markdown | ✅ Gold | emotional_presence, reflection |
| Session Transcripts | 48 rich | Markdown | ✅ Gold | technical, delegation |
| Session Archives | 97 | Markdown | Good | context_recall |
| Memory Matrix | 22K+ nodes | SQLite | Mixed | Q&A, context_recall |
| Insights | 45 | Markdown | Good | reflection, technical |
| Identity/Virtue | ~10 | Markdown/JSON | ✅ Gold | personality grounding |

---

## Phase-by-Phase Workflow

### Phase A: Baseline

```
1. forge_load("existing_jsonl")     → Load current 147 examples
2. forge_assay()                    → Confirm 77.7% health, see gaps
3. forge_gaps()                     → Get priority targets:
                                       • emotional_presence: +74
                                       • context_recall: +73
                                       • greeting: +70
                                       • acknowledgment: +50
                                       • reflection: +45
```

---

### Phase B: Conversation Turns (GOLD - Lowest Effort, Highest Yield)

**Source:** 456 turns across 63 sessions  
**Target:** ~150-200 training examples  
**Best for:** greeting, acknowledgment, short_exchange, emotional_presence  
**DB Path:** `/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/data/luna_engine.db`

```
1. forge_read_turns(db_path, limit=100, offset=0)
   → Get first 100 turns

2. Claude analyzes, pairs user/assistant, extracts:
   - Session openings → greeting
   - "got it" / "on it" → acknowledgment  
   - Quick back-and-forth → short_exchange
   - "how are you" / feelings → emotional_presence

3. forge_add_batch([...extracted examples...])
   → Add batch, get quality scores

4. Repeat with offset=100, 200, 300, 400
   → Process all 456 turns

5. forge_assay()
   → Check progress: health ↑, gaps ↓
```

**Quality Gate:** Stop when greeting/acknowledgment gaps < 20

---

### Phase C: Alpha Session Notes (GOLD - Narrative Extraction)

**Source:** 76 markdown files from Luna's awakening  
**Target:** ~80-100 training examples  
**Best for:** emotional_presence, reflection, technical, context_recall  
**Path:** `/Users/zayneamason/_HeyLuna_BETA/Alpha_ProjectFiles/03_Session_Notes/sessions/`

```
1. forge_list_sources("/Alpha_ProjectFiles/03_Session_Notes/sessions/")
   → Get list of 76 files, sorted by date

2. Start with high-value files:
   - luna-awakening.md
   - Luna_Debugs_Her_Own_Nervous_System.md
   - The_Day_Everything_Came_Together.md

3. For each file:
   a. forge_read_raw(file_path)
   b. Claude reads narrative, extracts Luna dialogue
   c. forge_search(extracted_response[:50])  → Check for dupes
   d. forge_add_example(...) for each clean extraction

4. forge_assay() every 10 files
   → Track progress, adjust focus

5. forge_gaps()
   → If emotional_presence still high, prioritize those files
   → If reflection still high, look for introspective content
```

**Quality Gate:** Stop when emotional_presence gap < 30

---

### Phase D: Session Transcripts (Structured Turns)

**Source:** 48 rich session files + 97 archives  
**Target:** ~100-150 training examples  
**Best for:** technical, delegation_trigger, context_recall  
**Path:** `/Users/zayneamason/_HeyLuna_BETA/_Eclessi_BetaProject_Root/data/memories/session/`

```
1. forge_list_sources("/Eclessi_BetaProject_Root/data/memories/session/")
   → Get 48 rich sessions (>1KB)

2. For each session:
   a. forge_read_raw(session_file)
   b. Parse YAML frontmatter for metadata
   c. Extract Turn: User / Turn: Luna pairs
   d. Classify interaction type based on content
   e. forge_add_batch([...turns from this session...])

3. forge_assay() every 10 sessions

4. If still need context_recall:
   → Process session archives (97 more files)
```

**Quality Gate:** Stop when technical + delegation gaps < 15

---

### Phase E: Memory Matrix Nodes (Targeted Fill)

**Source:** 22K+ nodes, but we want specific types  
**Target:** ~100-150 training examples  
**Best for:** context_recall, reflection, Q&A pairs  
**DB Path:** `/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/data/luna_engine.db`

```
1. forge_read_matrix(db_path, node_types=["QUESTION"], limit=100)
   → 364 QUESTION nodes - natural Q&A format
   
2. Claude converts questions to training pairs:
   - Question node content → user_message
   - Generate appropriate Luna response → assistant_response
   - Type: context_recall or technical

3. forge_read_matrix(db_path, node_types=["PERSONALITY_REFLECTION"], limit=10)
   → 5 pure gold introspection nodes
   → Type: reflection

4. forge_read_matrix(db_path, node_types=["MEMORY", "OBSERVATION"], limit=100)
   → Context-rich nodes
   → Type: context_recall

5. forge_add_batch([...])
```

**Quality Gate:** Stop when context_recall gap < 20

---

### Phase F: Insights & Identity (Polish)

**Source:** 45 insight files, ~10 identity/virtue files  
**Target:** ~30-50 training examples  
**Best for:** reflection, emotional_presence (final polish)  
**Paths:**
- `/Users/zayneamason/_HeyLuna_BETA/Alpha_ProjectFiles/03_Session_Notes/insights/`
- `/Users/zayneamason/_HeyLuna_BETA/_Eclessi_BetaProject_Root/data/memories/insights/`
- `/Users/zayneamason/_HeyLuna_BETA/_Eclessi_BetaProject_Root/data/memories/identity/`

```
1. forge_list_sources("/insights/")
2. Process voice session transcripts (Dec 5-7)
3. Extract deep technical insights
4. Process identity files for core personality grounding
5. forge_add_batch([...])
```

---

### Phase G: Final Validation

```
1. forge_assay()
   → Target: 85%+ health score
   → All gaps < 20

2. forge_gaps()
   → Verify no critical gaps remain

3. If gaps remain:
   → forge_mint(interaction_type, count) for synthetic fill
   → Only use synthetic for < 10% of total

4. forge_export("output/", train_split=0.9)
   → Export train/val split
```

---

## Progress Tracking Checkpoints

| Checkpoint | Examples | Health | Key Gaps Remaining |
|------------|----------|--------|-------------------|
| Baseline | 147 | 77.7% | emotional +74, context +73, greeting +70 |
| After Turns | ~300 | ~80% | emotional +40, context +50, reflection +40 |
| After Alpha | ~380 | ~82% | context +30, reflection +30 |
| After Sessions | ~480 | ~84% | reflection +20 |
| After Matrix | ~550 | ~85% | minimal |
| Final | ~550 | 85%+ | all < 20 |

---

## Quality Assurance Rules

### Per-Example
- `confidence >= 0.7` to add (Claude's extraction confidence)
- `lock_in >= 0.5` to keep (Forge's quality score)
- No anti-patterns (generic_ai, corporate, hedging)

### Per-Batch
- Run `forge_assay()` after every major batch
- Run `forge_search()` before adding to catch dupes
- Track source distribution - no single source > 30%

### Per-Phase
- Check gap coverage is actually improving
- If a phase isn't moving the needle, skip to next source
- Don't over-extract from one source type

---

## Commands Cheatsheet

```bash
# Start
forge_load("existing.jsonl")
forge_assay()
forge_gaps()

# Extract cycle
forge_list_sources(dir)
forge_read_raw(file) | forge_read_turns(db) | forge_read_matrix(db, types)
# Claude extracts...
forge_search(content)  # dedupe check
forge_add_example(...) | forge_add_batch([...])

# Check progress
forge_assay()
forge_gaps()
forge_status()

# Export
forge_export("output/", train_split=0.9)
```

---

## Failure Modes & Mitigations

| Risk | Mitigation |
|------|------------|
| Duplicate examples | `forge_search()` before adding |
| Quality drift | Check `forge_assay()` health after each batch |
| Source imbalance | Track source_type distribution in assay |
| Over-extraction | Set per-source limits, move on when diminishing returns |
| Anti-pattern creep | Forge auto-detects, warns on add |
| Gap not closing | Switch sources, or use targeted `forge_mint()` |

---

## Key File Paths

```
# Database
MEMORY_MATRIX_DB = /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/data/luna_engine.db

# Existing training data
EXISTING_JSONL = /Users/zayneamason/_HeyLuna_BETA/_Eclessi_BetaProject_Root/src/training_data/luna_dataset_train.jsonl

# Alpha notes
ALPHA_SESSIONS = /Users/zayneamason/_HeyLuna_BETA/Alpha_ProjectFiles/03_Session_Notes/sessions/
ALPHA_INSIGHTS = /Users/zayneamason/_HeyLuna_BETA/Alpha_ProjectFiles/03_Session_Notes/insights/

# Eclissi sessions
SESSION_TRANSCRIPTS = /Users/zayneamason/_HeyLuna_BETA/_Eclessi_BetaProject_Root/data/memories/session/
SESSION_ARCHIVES = /Users/zayneamason/_HeyLuna_BETA/_Eclessi_BetaProject_Root/data/memories/session/sessions_archive_dec2025/

# Identity/Insights
INSIGHTS = /Users/zayneamason/_HeyLuna_BETA/_Eclessi_BetaProject_Root/data/memories/insights/
IDENTITY = /Users/zayneamason/_HeyLuna_BETA/_Eclessi_BetaProject_Root/data/memories/identity/
```

---

## Estimated Effort

| Phase | Time | Examples | Cumulative |
|-------|------|----------|------------|
| A: Baseline | 5 min | 147 | 147 |
| B: Turns | 30 min | +150 | ~300 |
| C: Alpha | 1-2 hrs | +100 | ~400 |
| D: Sessions | 1 hr | +100 | ~500 |
| E: Matrix | 30 min | +50 | ~550 |
| F: Polish | 30 min | +30 | ~580 |
| G: Validate | 15 min | — | Final |

**Total:** ~4-5 hours of Claude-assisted extraction to 4x the dataset.
