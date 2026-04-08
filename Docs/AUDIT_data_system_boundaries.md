# Luna Engine — Data/System Boundary Audit

**Date:** 2026-03-15
**Scope:** Investigation only — no code changes
**Root:** `_LunaEngine_BetaProject_V2.0_Root/`

---

## 1. File System Inventory

### 1.1 `data/` Directory

| Path (relative to root) | Category | Mutable? | Notes |
|---|---|---|---|
| `data/luna_engine.db` | **MIXED** | Yes | 130 MB. System schema + 25k+ user memory nodes + 3k conversation turns + 115 entities + 498 sessions. **Primary contamination point.** |
| `data/luna_engine.db-shm` / `-wal` | **MIXED** | Yes | WAL journal for above |
| `data/luna_engine.db.pre-cleanup` | **DEV** | No | 130 MB backup from Feb 19 cleanup. Should never ship. |
| `data/eclissi.db` | **MIXED** | Yes | 557 KB. Legacy DB with 261 FACT nodes. Contains pre-migration user data. |
| `data/eclissi.db-shm` / `-wal` | **MIXED** | Yes | WAL journal for above |
| `data/qa.db` | **USER** | Yes | 3.9 MB. QA reports (309), bugs (10), assertion results (4,850). All user-generated from testing sessions. |
| `data/memory_matrix.db` | **DEAD** | No | 0 bytes. Empty file, unused. Memory matrix lives in luna_engine.db. |
| `data/alias_cache.json` | **USER** | Yes | Runtime alias resolution cache. Contents: `[]` (empty). |
| `data/entity_review_queue.json` | **USER** | Yes | Entity review queue state. |
| `data/entity_stoplist.json` | **SYSTEM** | No | Stoplist for entity extraction (generic terms to ignore). Ships with install. |
| `data/hygiene_sweep_state.json` | **USER** | Yes | Memory hygiene sweep progress state. |
| `data/observatory_config.json` | **USER** | Yes | Observatory tuning configuration. |
| `data/.DS_Store` | **DEV** | No | macOS artifact. Should never ship. |
| `data/aibrarian/` | **MIXED** | — | See §7 Aibrarian A
udit below |
| `data/aibrarian/luna_system.db` | **SYSTEM** | Read-only | 27 chunks, 10 documents. System help docs. Safe to ship. |
| `data/aibrarian/kinoni.db` | **DEV** | Yes | 883 chunks, 16 documents. Kinoni community knowledge. Should never ship in generic build. |
| `data/aibrarian/dataroom.db` | **DEV** | Yes | 27 chunks, 18 documents. Investor-facing data room. Should never ship. |
| `data/guardian/` | **DEV** | No | Kinoni Guardian demo fixture data. See §8. |
| `data/guardian/conversations/` | **DEV** | No | 5 JSON files (amara, elder, musoke, wasswa threads). ~1.1 MB total. |
| `data/guardian/entities/` | **DEV** | No | `entities_updated.json` (16 KB), `relationships_updated.json` (9 KB). Kinoni-specific. |
| `data/guardian/knowledge_nodes/` | **DEV** | No | 5 JSON files (actions, decisions, facts, insights, milestones). ~170 KB. |
| `data/guardian/membrane/` | **DEV** | No | `consent_events.json`, `scope_transitions.json`. Kinoni governance data. |
| `data/guardian/org_timeline/` | **DEV** | No | `knowledge_graph.json` (203 KB), `timeline_events.json` (100 KB). |
| `data/journal/` | **USER** | Yes | 42 markdown files. Music listening journal entries (Beethoven, Mozart, Pink Floyd, etc.). Personal data. |
| `data/kozmo_projects/` | **USER** | Yes | 5 project directories (crooked-nail, dinosaur-wizard-mother, luna-manifesto, mimos, test). User-created Kozmo projects. |
| `data/cache/` | **USER** | Yes | Runtime caches: `handoff_snapshot.yaml`, `shared_turn.yaml`, `task_queue.yaml`. |
| `data/backups/` | **DEV** | No | 3 files: pre-intent-layer DB backup, 2 SQL backup dumps from Jan 28. |
| `data/diagnostics/` | **DEV** | No | `archaeology_run_baseline_*.json`, `prompt_archaeology.jsonl`. Debug/investigation data. |
| `data/corpora/` | **SYSTEM** | No | Empty directory. Scaffolding only. |
| `data/projects/` | **SYSTEM** | No | Empty directory. Scaffolding only. |
| `data/Luna-System-Knowledge/` | **SYSTEM** | Read-only | 10 markdown files + README + registry YAML. Luna's self-knowledge base. Ships with install. |

### 1.2 `config/` Directory

| Path (relative to root) | Category | Mutable? | Notes |
|---|---|---|---|
| `config/owner.yaml` | **USER** | Yes | Contains `entity_id: "ahab"`, `display_name: "Ahab"`, `aliases: ["Zayne", "Zayne Mason"]`, `admin_contacts: ["Ahab", "Tarcila"]`. **HIGH severity leak.** |
| `config/identity_bypass.json` | **USER/DEV** | Yes | Contains `entity_id: "ahab"`, `entity_name: "Ahab"`, `luna_tier: "admin"`, `dataroom_tier: 1`, `dataroom_categories: [1-9]`. **HIGH severity leak.** |
| `config/personality.json` | **MIXED** | Yes | System defaults (patch storage config, mood analysis, reflection loop, lifecycle) + bootstrap seed patch definitions that reference owner relationship. System structure, but bootstrap_002 populates from owner config. |
| `config/aibrarian_registry.yaml` | **MIXED** | Yes | System collection definitions (luna_system) + DEV collections (dataroom, kinoni) + **ABSOLUTE PATHS to external drives** (`/Volumes/ZDrive-1/DatabaseProject/data/documents.db`, `/Volumes/ZDrive-1/PT_DatabaseProject/data/thiel.db`). **HIGH — external paths will break on any other machine.** |
| `config/directives_seed.yaml` | **SYSTEM** | No | Seed directives and skills. All entries have `authored_by: system`. Safe to ship. |
| `config/llm_providers.json` | **MIXED** | Yes | Provider list is SYSTEM. API key env var names are SYSTEM. But `current_provider` is USER preference. No actual secrets in file (keys come from env vars). Low risk. |
| `config/fallback_chain.yaml` | **SYSTEM** | Yes | `chain: [claude, local]`. System default. |
| `config/luna.launch.json` | **SYSTEM** | Yes | Service ports and profiles. System defaults. No user data. |
| `config/eden.json` | **SYSTEM** | Yes | Eden API config with policy defaults. No user data. |
| `config/dataroom.json` | **DEV** | Yes | Contains Google Sheet ID, credentials path, token path, Drive folder ID. **All dev-specific.** |
| `config/google_credentials.json` | **DEV/SECRET** | Yes | Contains Google OAuth `client_id`, `client_secret`. **MUST NEVER SHIP.** |
| `config/google_token.json` | **DEV/SECRET** | Yes | Contains OAuth access token, refresh token, client secret. **MUST NEVER SHIP.** |
| `config/google_token_drive.json` | **DEV/SECRET** | Yes | Drive-specific OAuth token. **MUST NEVER SHIP.** |
| `config/memory_economy_config.json` | **SYSTEM** | Yes | Tuning parameters for memory economy. System defaults. |
| `config/local_inference.json` | **SYSTEM** | Yes | Qwen model config, generation params. System defaults. |
| `config/lunascript.yaml` | **SYSTEM** | Yes | Cognitive signature system config. System defaults. |
| `config/skills.yaml` | **SYSTEM** | Yes | Skill registry and detection config. System defaults. |
| `config/projects/projects.yaml` | **MIXED** | Yes | Contains `kinoni-ict-hub` and `eclipse-dataroom` project definitions. Project list is dev-specific but the schema/structure is system. |
| `config/projects/kinoni-ict-hub.yaml` | **DEV** | Yes | Kinoni-specific search chain config. |
| `config/projects/eclipse-dataroom.yaml` | **DEV** | Yes | Eclipse dataroom search chain config. |
| `config/projects/_example.yaml` | **SYSTEM** | No | Template for new projects. |
| `config/.DS_Store` | **DEV** | No | macOS artifact. |

---

## 2. Database Table Audit — `luna_engine.db`

**50 tables total** (including FTS shadow tables and virtual tables).

### Core Tables

| Table | Row Count | Category | Partition Column? | Notes |
|---|---|---|---|---|
| `memory_nodes` | ~25,282 | **MIXED** | `source` (partial) | **PRIMARY CONTAMINATION.** 19,968 rows from `eclissi_migration`, 2,528 from `conversation`, plus session-sourced extractions. No `system` vs `user` flag. `source` column helps but doesn't cleanly separate. |
| `conversation_turns` | 3,113 | **USER** | None | Purely user conversation history. |
| `entities` | 115 | **MIXED** | None | 8 personas (system: Luna, The Dude, etc.) + 50 persons (user: Ahab, Tarcila, etc.) + 3 places + 54 projects. No `origin` column to distinguish system-seeded vs user-discovered. |
| `entity_versions` | 234 | **MIXED** | `changed_by` | 115 by `resolver`, 115 by `scribe`, 4 by `seed_loader`. `seed_loader` entries are system. |
| `sessions` | 498 | **USER** | None | All user sessions. |
| `clusters` | 195 | **USER** | None | Memory clusters from clustering engine. All user-generated. |
| `cluster_members` | 4,316 | **USER** | None | Cluster membership. |
| `cluster_edges` | 0 | — | — | Empty. |
| `quests` | 280 | **USER** | None | Observatory quests. User-initiated. |
| `quest_targets` | 338 | **USER** | None | Quest targets. |
| `quest_journal` | 0 | — | — | Empty. |
| `nodes` | 0 | — | — | Observatory nodes (unused in current version). |
| `edges` | 0 | — | — | Observatory edges (unused). |
| `access_bridge` | 5 | **USER** | None | FaceID access bridge entries. |
| `permission_log` | 35 | **USER** | None | Permission audit log. |
| `ambassador_audit_log` | 0 | — | — | Empty. |
| `ambassador_protocol` | 0 | — | — | Empty. |
| `consciousness_snapshots` | 0 | — | — | Empty. |
| `compression_queue` | — | **USER** | — | Memory compression queue. |
| `extraction_queue` | — | **USER** | — | Entity extraction queue. |
| `entity_mentions` | — | **USER** | — | Mention tracking from conversations. |
| `entity_relationships` | — | **USER** | — | Discovered relationships between entities. |
| `graph_edges` | 26,850 | **USER** | None | Knowledge graph edges. **No `source` or `origin` column** — impossible to distinguish system vs conversation-derived edges. Dominant types: RELATED_TO (20,430), MENTIONS (3,162), RELATES_TO (616). |
| `entity_mentions` | 16,306 | **USER** | — | Entity-to-node mention links. `ahab` has 3,073 mention links alone. |
| `history_embeddings` | — | **USER** | — | Conversation history embeddings. |
| `collection_annotations` | — | **USER** | — | Aibrarian collection annotations. |
| `collection_lock_in` | — | **USER** | — | Collection lock-in scores. |

### LunaScript Tables

| Table | Row Count | Category | Notes |
|---|---|---|---|
| `lunascript_baselines` | 21 | **SYSTEM** | Cognitive signature baselines. System-calibrated but from user data. **MIXED** in practice. |
| `lunascript_patterns` | 0 | — | Empty. |
| `lunascript_state` | 1 | **USER** | Current LunaScript state. |
| `lunascript_feedback` | 7 | **USER** | User feedback on delegated responses. |
| `lunascript_delegation_log` | 71 | **USER** | Delegation log entries. |
| `lunascript_correlations` | 9 | **USER** | Feature correlations. |

### Tuning Tables

| Table | Row Count | Category | Notes |
|---|---|---|---|
| `tuning_sessions` | 3 | **USER** | Tuning session records. |
| `tuning_iterations` | 13 | **USER** | Tuning iteration records. |

---

## 3. Database Table Audit — `eclissi.db`

Legacy database from pre-engine Eclissi era.

| Table | Category | Notes |
|---|---|---|
| `memory_nodes` (261 FACT rows) | **USER** | Legacy user data. All FACT type. |
| `conversation_turns` | **USER** | Legacy conversations. |
| `entities`, `entity_versions`, `entity_mentions`, `entity_relationships` | **USER** | Legacy entity data. |
| `sessions` | **USER** | Legacy sessions. |
| Other tables mirror luna_engine.db schema | **USER** | — |

**Verdict:** Entirely user data. Should never ship.

---

## 4. Database Table Audit — `qa.db`

| Table | Row Count | Category | Notes |
|---|---|---|---|
| `qa_assertions` | 1 | **MIXED** | System-defined assertion templates + user assertions. |
| `qa_reports` | 309 | **USER** | QA simulation reports from dev testing. |
| `qa_bugs` | 10 | **USER** | Tracked bugs. |
| `qa_events` | 291 | **USER** | QA event log. |
| `qa_assertion_results` | 4,850 | **USER** | Test result history. |

**Verdict:** Mostly user data from development QA sessions. Should not ship with user data.

---

## 5. Config File Audit

### 5.1 Files Where System and User Keys Coexist (MIXED)

| File | System Keys | User/Dev Keys | Severity |
|---|---|---|---|
| `personality.json` | `personality_patch_storage.*`, `emergent_prompt.*`, `mood_analysis.*`, `reflection_loop.*`, `lifecycle.*` | `bootstrap.seed_patches` — bootstrap_002 populates content from owner config at runtime | LOW — structure is system, content is dynamic |
| `aibrarian_registry.yaml` | Schema config, `defaults.*`, `luna_system` collection | `dataroom`, `kinoni_knowledge` collections, `maxwell_case` and `thiel_investigation` with absolute paths to `/Volumes/ZDrive-1/` | **HIGH** — external drive paths will crash on other machines |
| `llm_providers.json` | Provider definitions, model lists, env var names | `current_provider` preference | LOW — no actual secrets |
| `projects/projects.yaml` | Schema structure | `kinoni-ict-hub`, `eclipse-dataroom` project definitions | MEDIUM — dev project definitions |

### 5.2 Pure User/Dev Files (Should Never Ship)

| File | Severity | Notes |
|---|---|---|
| `owner.yaml` | **HIGH** | Contains `entity_id: "ahab"`, aliases `["Zayne", "Zayne Mason"]` |
| `identity_bypass.json` | **HIGH** | FaceID bypass with `entity_id: "ahab"`, admin tier |
| `google_credentials.json` | **CRITICAL** | OAuth client_id + client_secret |
| `google_token.json` | **CRITICAL** | OAuth access + refresh tokens |
| `google_token_drive.json` | **CRITICAL** | Drive OAuth tokens |
| `dataroom.json` | **HIGH** | Google Sheet ID, Drive folder ID |
| `projects/kinoni-ict-hub.yaml` | MEDIUM | Kinoni search chain config |
| `projects/eclipse-dataroom.yaml` | MEDIUM | Eclipse search chain config |

### 5.3 Pure System Files (Safe to Ship)

| File | Notes |
|---|---|
| `directives_seed.yaml` | All `authored_by: system` |
| `luna.launch.json` | Service ports and profiles |
| `eden.json` | Eden API defaults + policy |
| `fallback_chain.yaml` | Inference fallback order |
| `memory_economy_config.json` | Tuning parameters |
| `local_inference.json` | Qwen model config |
| `lunascript.yaml` | Cognitive signature config |
| `skills.yaml` | Skill registry |
| `projects/_example.yaml` | Template |

---

## 6. Entity System Audit

### 6.1 Entity Classification

**Persona entities (8 total) — SYSTEM:**
- `luna`, `the-dude`, `fairy-orchestrator`, `memory-matrix`, `voice-luna`, `desktop-luna`, `the-crew`, `ben-franklin`
- These are Luna's internal personas. Should ship with every install.

**Person entities (50 total) — USER:**
- `ahab`, `tarcila`, `claude-code`, `marzipan`, `kirby`, `gandala`, `kamau`, `yulia`, `alex`, `dr.-carol-myles`, etc.
- All discovered through conversations with the owner. Should never ship.

**Place entities (3) — USER:** `mars-college`, `stanford-university`, `olukomera`

**Project entities (54) — MIXED:**
- Some are system-relevant (`luna-engine`, `eclissi`, `visual-orb`)
- Most are user-specific (`canonical-spatial-ui-prototype`, `personacore`, `raccoon-robot`, `guardian`, etc.)

### 6.2 Entity Loading Path

1. `engine.py:_boot()` → calls `_ensure_entity_seeds_loaded()` (line 352)
2. Seed entities loaded from YAML files in `data/entities/` (if directory exists) or from bootstrap code
3. `entities/resolution.py` resolves entity mentions via SQLite `entities` table
4. `entities/context.py` builds the IdentityBuffer with `user_entity` from owner config
5. `entity_versions` tracks changes with `changed_by`: `resolver` (runtime), `scribe` (conversation extraction), `seed_loader` (bootstrap)

### 6.3 No Partition Column

The `entities` table has **no `origin` or `source` column** to distinguish system-seeded personas from user-discovered people. The only signal is:
- `entity_type='persona'` → likely system
- `entity_versions.changed_by='seed_loader'` → system (but only 4 rows)
- Everything else → user

---

## 7. Aibrarian Collection Audit

| Collection DB | Category | Chunks | Documents | Notes |
|---|---|---|---|---|
| `luna_system.db` | **SYSTEM** | 27 | 10 | System help docs. `read_only: true` in registry. Safe to ship. |
| `kinoni.db` | **DEV** | 883 | 16 | Kinoni community knowledge. Community-specific. Should never ship in generic build. |
| `dataroom.db` | **DEV** | 27 | 18 | Investor data room documents. Should never ship. |

### External Path References in `aibrarian_registry.yaml`

| Collection | Path | Risk |
|---|---|---|
| `maxwell_case` | `/Volumes/ZDrive-1/DatabaseProject/data/documents.db` | **HIGH** — absolute path to external drive. Will not exist on any other machine. Currently `enabled: false`. |
| `thiel_investigation` | `/Volumes/ZDrive-1/PT_DatabaseProject/data/thiel.db` | **HIGH** — same issue. Currently `enabled: false`. |

These are disabled, so they won't crash the engine, but they leak dev machine topology into the config.

---

## 8. Guardian Data Audit

`data/guardian/` — **Entirely DEV/Kinoni-specific.** Should never ship in a generic build.

| Subdirectory | Files | Size | Content |
|---|---|---|---|
| `conversations/` | 5 JSON files | ~1.1 MB | Amara, elder, musoke, wasswa conversation threads |
| `entities/` | 2 JSON files | 25 KB | Kinoni community entities and relationships |
| `knowledge_nodes/` | 5 JSON files | 170 KB | Actions, decisions, facts, insights, milestones |
| `membrane/` | 2 JSON files | 8 KB | Consent events, scope transitions |
| `org_timeline/` | 2 JSON files | 303 KB | Knowledge graph, timeline events |

The `GuardianMemoryBridge` class (`src/luna/services/guardian/memory_bridge.py`) syncs this data into luna_engine.db's `memory_nodes` table with scope `project:kinoni-ict-hub`. This means Guardian activation **writes Kinoni data directly into the main DB**, further contaminating it.

---

## 9. Startup Contamination Trace

### Boot Sequence (`engine.py:_boot()`)

| Step | Files Read | Files Written | Contamination Risk |
|---|---|---|---|
| 1. MatrixActor init | `data/luna_engine.db` (connects + loads graph) | Creates DB if missing (applies `schema.sql`) | If DB doesn't exist, creates clean. If exists, loads all user data. |
| 2. DirectorActor init | `config/personality.json` (expression config) | None | Reads bootstrap seed patch defs. Low risk. |
| 3. ScribeActor, LibrarianActor, CacheActor, HistoryManagerActor | None at init | None | Lazy initialization. |
| 4. IdentityActor (if FaceID enabled) | `config/identity_bypass.json` | None | **Reads `entity_id: "ahab"` bypass.** Fresh install without this file = different behavior. |
| 5. Eden adapter init | `config/eden.json` | None | System config, no user data. |
| 6. `_ensure_entity_seeds_loaded()` | Entity YAML seed files | Writes seed entities to `entities` table | Writes bootstrap personas (Luna, The Dude, etc.) to DB. System data, but mixed into same table. |
| 7. `ConsciousnessState.load()` | `data/snapshot.yaml` (if exists) | None | State snapshot. User data if exists, graceful if missing. |
| 8. AiBrarianEngine init | `config/aibrarian_registry.yaml` | None | **Reads registry with dev collection paths.** Won't crash if DBs missing, but loads kinoni/dataroom configs. |
| 9. CollectionLockInEngine | `luna_engine.db` (collection_lock_in table) | Bootstraps `luna_system` tracking | Writes system bootstrap row. |
| 10. DirectiveEngine init | `config/directives_seed.yaml`, `luna_engine.db` | Seeds directives to DB on first run | System directives written to same DB as user data. |
| 11. Owner config | `config/owner.yaml` (via `get_owner()`) | None | **Assumes owner.yaml exists.** Falls back gracefully to empty config if missing. |

### Fresh Install Behavior

On a clean install (no `data/luna_engine.db`, no `config/owner.yaml`):
- Engine creates DB from `schema.sql` — clean
- No owner configured — falls back to "unconfigured instance"
- Identity bypass missing — IdentityActor uses fallback
- **No crash**, but several features degraded (no owner recognition, no entity matching)

**Specific fresh-install issues found:**

1. **MatrixActor "low memory" warning** (`actors/matrix.py:112-117`): If node count < 1000, warns "Luna's brain should have 50k+ nodes". This fires on **every fresh install** and is misleading — the threshold is based on Ahab's dev instance scale.

2. **Entity seed loading bug** (`engine.py:721`): `_ensure_entity_seeds_loaded()` checks `matrix._memory` but the actual attribute is `matrix._matrix`. Entity seeds **silently fail to auto-load**, leaving Luna without her self-entity in the DB (falls back to hardcoded defaults in `context.py:648`).

3. **Relative path hardcoding** (`api/server.py:5689,5861`): Uses `Path("data/luna_engine.db")` instead of `data_dir()`. Would break in Tauri mode where `LUNA_DATA_DIR` points elsewhere. Same issue in `tuning/session.py:96`.

4. Missing Guardian fixture data at `data/guardian/` causes `GuardianMemoryBridge` to log warnings but not crash.

**Key finding:** The engine handles missing files gracefully. The problem is **contamination in existing files**, not missing-file crashes. But bugs #1 and #2 would cause confusing behavior on fresh installs.

---

## 10. Memory Matrix Contamination Map

### memory_nodes by node_type

| node_type | Count | System Origin | User Origin | Notes |
|---|---|---|---|---|
| FACT | 20,676 | ~0 | ~20,676 | 19,673 from eclissi_migration. Purely user-accumulated knowledge. |
| CONVERSATION_TURN | 2,557 | 0 | 2,557 | 2,478 from `conversation` source, 79 from `eclissi_migration`. **Purely user data.** |
| ENTITY | 919 | 0 | 919 | Entity nodes extracted from conversations. Session-sourced. |
| OBSERVATION | 522 | 0 | 522 | Behavioral observations. Session-sourced. |
| QUESTION | 364 | 0 | 364 | Questions asked during sessions. |
| MEMORY | 259 | 0 | 259 | Explicit memory saves. |
| PREFERENCE | 161 | 0 | 161 | User preference nodes. 41 from `test` source. |
| PROBLEM | 171 | 0 | 171 | Problem descriptions from sessions. |
| DECISION | 142 | 0 | 142 | Decision records. |
| ACTION | 130 | 0 | 130 | Action records. |
| ASSUMPTION | 85 | 0 | 85 | Assumption records. |
| DOCUMENT | 79 | 0 | 79 | Document references. |
| THREAD | 76 | 0 | 76 | Thread markers. All from `librarian` source. |
| OUTCOME | 35 | 0 | 35 | Outcome records. |
| PARENT | 26 | 0 | 26 | Parent references (hierarchical). |
| PERSON_BRIEFING | 17 | 0 | 17 | Person briefing summaries. |
| CONNECTION | 10 | 0 | 10 | Connection nodes. |
| CATEGORY | 9 | 0 | 9 | Category markers. Likely from dataroom. |
| PERSONALITY_REFLECTION | 5 | **~5** | **~5** | **KEY CONTAMINATION POINT.** All 5 have `patch_` ID prefix and `metadata.bootstrap: true` in JSON blob, but **`source` is NULL** — harder to filter programmatically. Actively being reinforced at runtime (reinforcement_count 5-15), blurring system vs earned. Content references "Ahab" directly. |
| PROJECT | 4 | 0 | 4 | Project status nodes. |
| PROJECT_STATUS | 1 | 0 | 1 | Project status. |
| GOVERNANCE_RECORD | 1 | 0 | 1 | Guardian governance. |
| INSIGHT | 31 | 0 | 31 | Insights from sessions. |
| SESSION | 2 | 0 | 2 | Session markers. |
| MILESTONE | 1 | 0 | 1 | Milestone marker. |

### Source Analysis

| Source | Row Count | Category |
|---|---|---|
| `eclissi_migration` | 19,968 | USER — migrated from legacy Eclissi DB |
| `conversation` | 2,528 | USER — extracted from conversations |
| `conversation_extractor` | 261 | USER — extraction pipeline output |
| Session IDs (e.g., `b625e7d5`) | ~2,500 | USER — per-session extractions |
| `test` / `smoke_test` | 125 | DEV — test data. Should not ship. |
| `librarian` | 76 | USER — thread management |
| `mcp` | 64 | USER — MCP tool interactions |
| `api` | 50 | USER — API interactions |
| `history_turn_*` | ~500+ | USER — history re-extraction |
| `gdrive:*` | ~80 | DEV — Google Drive document extractions |
| `dataroom:category:*` | 9 | DEV — dataroom category extractions |

### Ahab References in Memory

- **719 memory_nodes** contain "ahab" or "Ahab" in content
- PERSONALITY_REFLECTION nodes explicitly reference "Ahab" (e.g., "Ahab prefers direct technical discussion", "Ahab treats Luna as a peer collaborator", "Ahab has ADD")
- These are baked into the memory, not cleanly separable

### Entity Table Analysis

- **4 seed_loader entities** (system-bootstrapped personas)
- **115 resolver-created entities** (extracted from conversations — user data)
- **115 scribe-created versions** (enriched by scribe — user data)
- No `origin` or `is_system` column exists

---

## 11. Hardcoded Reference Audit (grep)

### "ahab" references in source code

All in comments/docstrings as examples — not functional hardcoding:
- `entities/context.py:95` — docstring example: `# Slug: 'ahab', 'marzipan'`
- `entities/models.py:8,29,120,123` — docstring examples
- `core/owner.py:71` — docstring: `'Ahab or Tarcila'`
- `actors/scribe.py:70` — docstring example
- `services/kozmo/types.py:368` — comment: `# "Ahab", "Luna", etc.`

**Verdict:** No functional hardcoding of "ahab" in source. All references are illustrative. The actual identity comes from `config/owner.yaml` at runtime. **Clean.**

### "kinoni" references in source code

Functional references exist in:
- `services/guardian/memory_bridge.py:102,132` — hardcoded search query `"Kinoni"` and text template `"in the Kinoni community"`
- `services/guardian/demo_protocols.py:183,192` — `_KINONI_PROTOCOLS` dict, `kinoni-ict-hub` project check
- `substrate/collection_annotations.py:27` — example: `"Cross-ref Kinoni budget"`
- `tools/aperture_tools.py:277` — docstring example
- `substrate/aibrarian_engine.py:15` — docstring example

**Verdict:** Guardian module has functional Kinoni references, but they're scoped behind `active_project == "kinoni-ict-hub"` checks. Won't activate unless project is configured. **MEDIUM risk** — the code ships but doesn't execute without project config.

### "zayne" references in source code

Only in docstring/comment examples alongside "ahab":
- `entities/resolution.py:240` — comment example
- `entities/models.py:123` — comment example

**Verdict:** Clean. No functional hardcoding.

---

## 12. Forge Build Pipeline Analysis

### Current Protections (`verify_clean_build()`)

The Forge checks 6 things post-build:

1. **Database row counts** — Checks `conversation_turns`, `memory_nodes`, `entities`, `sessions` for count > 0 → violation
2. **Owner identity** — Checks `owner.yaml` for non-empty `entity_id` → violation
3. **Poison terms** — Scans all `.yaml`/`.json` in config/ for: `ahab`, `kinoni`, `zayne`, `nakaseke`, `zayneamason` → violation
4. **Project files** — Checks `projects.yaml` for non-empty project list → violation
5. **Aibrarian collections** — Only allows collections listed in profile's `enabled` set → violation for extras
6. **Identity bypass** — Checks `identity_bypass.json` for non-empty `entity_id` → violation

### What the Forge Does NOT Catch

| Gap | Risk | Description |
|---|---|---|
| `eclissi.db` | HIGH | Legacy DB is not checked or excluded |
| `qa.db` | HIGH | QA database not checked |
| `data/journal/` | HIGH | 42 personal journal entries not checked |
| `data/guardian/` | MEDIUM | Kinoni fixture data not checked (may or may not be included) |
| `data/kozmo_projects/` | HIGH | User's Kozmo project data not checked |
| `data/backups/` | HIGH | DB backups not checked |
| `data/diagnostics/` | LOW | Debug data not checked |
| `data/cache/` | MEDIUM | Runtime caches not checked |
| `config/google_credentials.json` | **CRITICAL** | OAuth secrets not in poison term scan |
| `config/google_token*.json` | **CRITICAL** | OAuth tokens not checked |
| `config/dataroom.json` | HIGH | Google Sheet IDs not checked |
| `config/aibrarian_registry.yaml` external paths | HIGH | `/Volumes/ZDrive-1/` paths pass poison term check |
| `data/luna_engine.db.pre-cleanup` | HIGH | 130 MB backup copy not checked |
| `data/memory_matrix.db` | LOW | Dead file, 0 bytes |
| `lunascript_baselines` table | LOW | Baselines calibrated from user data |
| `.DS_Store` files | LOW | macOS artifacts |
| Missing poison terms | MEDIUM | `tarcila`, `musoke`, `wasswa`, `amara` (Guardian entity names) not in poison list |
| Unchecked DB tables | MEDIUM | `graph_edges`, `ambassador_protocol`, `ambassador_audit_log`, `collection_lock_in`, `collection_annotations` not verified empty |
| No binary string scan | MEDIUM | Compiled Nuitka binary preserves string literals — docstrings with "Ahab", "Kinoni" survive compilation |
| `server.py` relative paths | MEDIUM | Lines 5689, 5861 use `Path("data/luna_engine.db")` instead of `data_dir()` — breaks in Tauri mode |

### `assemble_data()` behavior

- **mode=seed**: Creates blank DB from schema.sql — clean
- **mode=copy**: Copies existing `luna_engine.db` — **leaks everything**
- Collections: Only copies profile-enabled collections — partially safe, depends on profile config

---

## 13. Contamination Summary

| Component | Severity | Type | Description |
|---|---|---|---|
| `luna_engine.db` memory_nodes | **HIGH** | MIXED system+user | 25k+ nodes from conversations, migrations, and bootstrapping share one table with no partition column. Source column exists but doesn't cleanly separate system vs user. |
| `luna_engine.db` entities | **HIGH** | MIXED system+user | 8 system personas + 107 user-discovered entities in same table with no origin flag. |
| `luna_engine.db` conversation_turns | **HIGH** | USER in system DB | 3,113 turns of owner's conversations baked into the primary database. |
| `config/owner.yaml` | **HIGH** | USER | Contains `entity_id: "ahab"`, display name, aliases. Identity leaks to any build. |
| `config/identity_bypass.json` | **HIGH** | USER/DEV | FaceID bypass with entity_id, admin tier, dataroom categories. |
| `config/google_credentials.json` | **CRITICAL** | SECRET | OAuth client_id + client_secret. |
| `config/google_token.json` | **CRITICAL** | SECRET | OAuth access + refresh tokens. |
| `config/google_token_drive.json` | **CRITICAL** | SECRET | Drive OAuth tokens. |
| `config/dataroom.json` | **HIGH** | DEV | Google Sheet ID, Drive folder ID for investor docs. |
| `config/aibrarian_registry.yaml` | **HIGH** | MIXED | System defaults + dev collections + external drive paths (`/Volumes/ZDrive-1/`). |
| `data/aibrarian/kinoni.db` | **HIGH** | DEV | 883 chunks of Kinoni community data. |
| `data/aibrarian/dataroom.db` | **HIGH** | DEV | 27 chunks of investor documents. |
| `data/eclissi.db` | **HIGH** | USER | Legacy 261-node database. |
| `data/qa.db` | **HIGH** | USER | 309 reports, 10 bugs, 4,850 results from dev testing. |
| `data/guardian/` | **MEDIUM** | DEV | 1.6 MB of Kinoni fixture data (conversations, entities, knowledge). |
| `data/journal/` | **HIGH** | USER | 42 personal music journal entries. |
| `data/kozmo_projects/` | **HIGH** | USER | 5 user-created project directories. |
| `data/backups/` | **HIGH** | DEV | DB backups including 130 MB pre-cleanup copy. |
| `data/luna_engine.db.pre-cleanup` | **HIGH** | DEV | 130 MB stale backup in data root. |
| `data/diagnostics/` | **LOW** | DEV | Debug/archaeology data. |
| `config/projects/projects.yaml` | **MEDIUM** | MIXED | Dev project definitions mixed with schema. |
| `config/projects/kinoni-ict-hub.yaml` | **MEDIUM** | DEV | Kinoni-specific config. |
| `config/projects/eclipse-dataroom.yaml` | **MEDIUM** | DEV | Eclipse-specific config. |
| `personality.json` bootstrap_002 | **LOW** | MIXED | Bootstrap patch dynamically references owner from config. |
| `data/observatory_config.json` | **LOW** | USER | Observatory tuning state. |
| `data/entity_review_queue.json` | **LOW** | USER | Entity review queue. |
| `data/hygiene_sweep_state.json` | **LOW** | USER | Sweep progress state. |
| `data/cache/` | **LOW** | USER | Runtime caches, ephemeral. |
| `.DS_Store` files | **LOW** | DEV | macOS artifacts. |
| Guardian source code `"Kinoni"` refs | **MEDIUM** | CODE | Functional Kinoni references in Guardian module, behind project check. |
| LunaScript baselines | **LOW** | MIXED | 21 baselines calibrated from owner's usage patterns. |

---

## 14. Open Questions

1. **PERSONALITY_REFLECTION partitioning**: Bootstrap patches have `metadata: {"bootstrap": true}` embedded in a JSON text blob. Is this reliable enough to use as a partition signal, or do we need a SQL column?

2. **Entity seed list**: Which of the 8 persona entities are truly system-required vs. nice-to-have? (e.g., `ben-franklin` is a persona but seems project-specific.)

3. **Guardian fixture data**: Should the Guardian module ship with empty `data/guardian/` scaffolding and populate from a fresh data source, or should some subset of Guardian data be considered system-level demo content?

4. **eclissi.db**: Is this DB still read from anywhere, or is it fully superseded by luna_engine.db? If dead, it can simply be excluded.

5. **qa.db assertions**: The 1 assertion in `qa_assertions` — is it a system-provided assertion template, or user-created?

6. **LunaScript baselines**: These are calibrated from the owner's writing patterns. Should a fresh install start with no baselines (cold start) or ship with generic baselines?

7. **Forge profile `database.mode: copy`**: Under what circumstances would anyone use `copy` mode? This directly leaks the entire dev database. Should it be removed or require an explicit `--include-user-data` flag?

8. **Entity seed loading bug**: `engine.py:721` references `matrix._memory` but the attribute is `matrix._matrix`. This means entity seeds never auto-load on fresh installs. Is this a known issue or an unintended regression?

9. **MatrixActor node threshold**: `matrix.py:112-117` warns if < 1000 nodes ("Luna's brain should have 50k+ nodes"). Should this be removed for production builds, or replaced with a first-run welcome message?

10. **Hardcoded relative paths**: `server.py:5689,5861` and `tuning/session.py:96` use `Path("data/luna_engine.db")` instead of `data_dir()`. These will break when `LUNA_DATA_DIR` is set (Tauri mode). Should these be fixed in Phase 2 or before?
