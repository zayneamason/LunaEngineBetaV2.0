# HANDOFF: Forge Hardening + Database Sanitizer

**Date:** 2026-03-16
**Session scope:** Forge type safety, error handling, preflight checks, plugin UI, database sanitizer module

---

## What Was Done

### 1. Plugin Architecture — Frontend Complete
- **PluginManager.jsx** — standalone view showing builtin skills (9) + plugin collections, with ingest/package/create
- **App.jsx** — tabs: Profiles, Plugins, Sanitizer, Outputs
- **serve.py** — `GET /api/plugins` returns builtin + plugin skills; `GET /api/collections`, `POST /api/collections/create`, `POST /api/collections/{key}/ingest`, `POST /api/collections/{key}/package`
- **ConfigPreview.jsx** — collections have mode dropdowns (compiled/plugin), skills have build mode dropdowns (compiled/plugin/exclude)

### 2. Forge Override Type Safety (CRITICAL FIX)
**Problem:** `_merge_overrides()` had zero type validation. A collection's `enabled` field was set to `{enabled: false, mode: "compiled"}` (a dict) instead of `false` (a bool). The build ran with corrupted config.

**Fix — 3 layers of defense:**
- **Layer 1: Pydantic models** — `BuildOverrides` with `CollectionOverride(enabled: bool, mode: Literal)`, `SkillBuildOverride(mode: Literal)`, etc. `model_config = {"strict": True}` prevents string→bool coercion. Bad input returns 422 before any merge.
- **Layer 2: `_validate_merged_profile()`** — validates the OUTPUT YAML structurally after merge. Catches bugs in the merge logic itself.
- **Layer 3: `_run_preflight()`** — 8-point checklist (type safety, collection DBs exist, engine source, frontend deps, output/staging writable, Nuitka available, disk space) gates every build.

**Files:** `Builds/Lunar-Forge/serve.py` — Pydantic models at lines ~107-145, `_validate_merged_profile()`, `_run_preflight()`, `_merge_overrides()` rewritten with typed input + debug logging.

### 3. Error Handling Fixes
**Backend (serve.py):**
- `preview_profile()` wrapped in try/except with detail
- `create_collection()` returns 500 on DB failure + cleans up partial directory (was returning 200 on failure)
- `read_config_file()` catches JSON/YAML parse errors with detail
- QA report parse logs warning instead of silent `pass`
- Build thread captures `traceback.format_exc()` in error events

**Frontend (api.js):**
- `startBuild()` extracts `detail` field from 422/500 responses (validation errors, preflight failures)
- SSE `onerror` includes actionable message: "check Forge terminal"
- SSE parse errors logged to console instead of silently swallowed
- `runPreflight()` function added

**Frontend (ConfigPreview.jsx):**
- `.catch()` added on `fetchConfigFile()`, `fetchDirectives()`, `fetchSystemKnowledge()` lazy-loads
- Preflight panel with pass/warn/fail indicators per check
- Build button disabled if preflight fails

**Frontend (PluginManager.jsx):**
- Load errors shown in UI with retry button (was `console.error` only)

### 4. Component Lifecycle Fix
- Data fetching lifted to App.jsx — profiles and plugins fetched once, passed as props
- No more refetch on tab switch
- ProfileSelector accepts `profiles` prop, PluginManager accepts `plugins` + `onRefresh` props

### 5. Template System Removed
- `ProfileCreator.jsx` deleted
- `createProfile()`, `deleteProfile()` removed from api.js
- `POST /api/profiles/create`, `DELETE /api/profiles/{name}` removed from serve.py
- ProfileSelector simplified — no "+ New Profile" button

### 6. Missing Merge Handlers Fixed
- **Build skill mode merge** — `ov.skills = {math: {mode: "exclude"}}` was silently dropped. Now handled.
- **Nuitka key mismatch** — frontend sent `excluded_packages`, profile YAML uses `exclude_packages`. Frontend now sends correct key. ConfigPreview reads both keys for backward compat with manifest.

### 7. Database Sanitizer Module (NEW)
**Core:** `Builds/Lunar-Forge/sanitizer.py`
- `DatabaseSanitizer` class with `preview()` (dry run) and `execute()` (creates filtered DB)
- Filters: entities (include/exclude), node types, confidence threshold, date range, conversations toggle
- System entities (origin='system') always included
- Copies schema from source DB (handles migration columns), copies filtered rows, rebuilds FTS, VACUUMs
- Tested: 124 MB → 30 MB (75.5% reduction) with Luna + The Dude entities, FACTs/DECISIONs/ACTIONs only, confidence >= 0.5

**API:** `Builds/Lunar-Forge/serve.py`
- `GET /api/sanitizer/stats` — row counts + size
- `GET /api/sanitizer/entities` — all entities with type, origin, mention count
- `GET /api/sanitizer/node-types` — node type breakdown
- `POST /api/sanitizer/preview` — dry run with filter config
- `POST /api/sanitizer/execute` — creates filtered DB in `staging/`

**Frontend:** `Builds/Lunar-Forge/frontend/src/components/DatabaseSanitizer.jsx`
- Entity checkboxes (system always checked), node type checkboxes, confidence slider, date range, conversations toggle
- Preview button (shows estimated output stats) and Export button (creates `.db`)
- "Sanitizer" tab in App.jsx header nav

**CLI:** `Builds/Lunar-Forge/sanitize_cli.py`
- `--stats`, `--list-entities`, `--list-types`, `--preview`, or full export with `--entities`, `--types`, `--min-confidence`, `--date-from`, `--no-conversations`

**Profile integration:** `Builds/Lunar-Forge/core.py`
- `database.mode: "filtered"` with `source: "staging/filtered.db"` — copies the sanitized DB into the build

---

## Compiled Build Test Results

Build completed (dev-test profile, seed mode). Luna responds via Claude API. Issues found:

### Bugs to Fix

| Priority | Issue | Location | Fix |
|----------|-------|----------|-----|
| **HIGH** | `AiBrarianConfig.__init__() missing 1 required positional argument: 'name'` | Engine AiBrarian init | The registry config changed — init call needs the `name` param |
| **HIGH** | `No module named 'migrations.load_entity_seeds'` | EntitySeedLoader | Module not included in Nuitka build. Add to include list or make import conditional |
| **HIGH** | `no such table: quests` | DirectiveEngine init | `quests` table missing from `schema.sql` / `_create_seed_db()` |
| **HIGH** | Watchdog spams same 4 alerts every ~5 seconds with NO rate limiting | `src/luna/services/performance_orchestrator.py` (watchdog) | Add cooldown — each alert type fires max once per 60s |
| **MED** | `line_bank.json` not found | Voice system | Voice data path wrong in compiled build — needs to resolve relative to build root |
| **MED** | Extraction pipeline dead (0 extractions after 11 messages) | Scribe actor | Needs openai package for embeddings, or fallback to keyword extraction |
| **LOW** | `openai package not installed` for embeddings | `src/luna/substrate/local_embeddings.py` | Expected in standalone build — but extraction shouldn't depend on it |
| **LOW** | `sqlite-vec` can't load C extension | Expected | LIKE search fallback works |
| **LOW** | `websockets` not installed | Observatory WS proxy | Expected — Observatory disabled in this build |

### Expected Behavior (seed mode)
- "Memory node count unusually low (6)" — correct, blank DB
- "No entities in database" — correct, seed loader failed to load
- "0 results for query" — correct, nothing to search

---

## Files Modified/Created This Session

| File | Change |
|------|--------|
| `Builds/Lunar-Forge/serve.py` | Pydantic models, validation gate, preflight, debug logging, error handling, sanitizer endpoints, plugin skills endpoint |
| `Builds/Lunar-Forge/core.py` | `database.mode: "filtered"` support |
| `Builds/Lunar-Forge/sanitizer.py` | **NEW** — core sanitizer module |
| `Builds/Lunar-Forge/sanitize_cli.py` | **NEW** — CLI interface |
| `Builds/Lunar-Forge/frontend/src/App.jsx` | Sanitizer tab, lifted data fetching, removed template imports |
| `Builds/Lunar-Forge/frontend/src/api.js` | Preflight, sanitizer functions, error extraction, removed template functions |
| `Builds/Lunar-Forge/frontend/src/components/DatabaseSanitizer.jsx` | **NEW** — sanitizer UI |
| `Builds/Lunar-Forge/frontend/src/components/ConfigPreview.jsx` | Preflight panel, collection mode dropdowns, skill build modes, Nuitka key fix, .catch() on lazy-loads |
| `Builds/Lunar-Forge/frontend/src/components/PluginManager.jsx` | Error display, accepts props from App |
| `Builds/Lunar-Forge/frontend/src/components/ProfileSelector.jsx` | Simplified, accepts profiles prop |
| `Builds/Lunar-Forge/frontend/src/components/ProfileCreator.jsx` | **DELETED** |

---

## Next Session Priorities

1. **Fix AiBrarianConfig init** — `name` parameter missing in the constructor call
2. **Fix EntitySeedLoader import** — make it work in compiled builds or handle ImportError gracefully
3. **Add `quests` table to schema.sql** — DirectiveEngine needs it
4. **Watchdog rate limiter** — add cooldown so alerts don't flood the terminal
5. **Fix voice data paths** for compiled builds
6. **Test a `database.mode: filtered` build** — use the sanitizer to create a filtered DB, then build with it
7. **Consider what packages the standalone build actually needs** — openai for embeddings, sentence-transformers for router — decide: bundle or make optional
