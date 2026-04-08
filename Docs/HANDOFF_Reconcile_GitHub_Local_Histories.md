# HANDOFF: Reconcile Diverged Luna Engine Histories (GitHub ↔ Local)

**Priority:** HIGH — must complete before any further feature work
**Scope:** Git history reconciliation only. DO NOT refactor, rename, or "improve" any code.
**Verified:** 2026-04-08 by Claude Desktop (all claims audited against live repo state)

---

## SITUATION

Two independently developed branches of Luna Engine must be integrated.

**Local line** (current HEAD `6b65088`, 20+ commits):
- 42 modified files, 69 untracked, +2,509/-324 lines uncommitted
- Contains: Guardian Luna, CuriosityBuffer, Protocol V2 Phases 2-5, Voice UX, Comprehension pipeline, Nexus rename, Scout/Overdrive, data directory migration
- Uncommitted: query expansion + FTS5 retry cascade, document extraction, query decomposition, Arcade skill, Nexus tools, Haiku subtask backend, ~50 handoff docs

**GitHub line** (`origin/main`, tip `424d791`, 9 commits from root `ad6a743`):
- One Door Architecture (`luna_respond()` unified inference)
- Ollama provider + intent-aware routing
- Three-signal retrieval scoring
- Deep memory test fixes
- DB lock resilience (retry with backoff)
- LunaFM background cognitive system (~3000 lines)
- WIP snapshot with handoffs + migration scripts

**Verified missing locally:**
- `luna_respond` → zero grep hits in `src/luna/`
- `ollama_provider.py` → does not exist
- No common merge-base (truly unrelated histories)

---

## DO NOT

- Do NOT `git merge` (unrelated histories = unreviewable conflict mess)
- Do NOT `git push --force` (destroys unique GitHub work)
- Do NOT refactor, rename, or "improve" any code during conflict resolution
- Do NOT touch files outside the scope of each cherry-pick
- Do NOT proceed past any step without verifying the previous step works
- Do NOT combine cherry-picks or skip dependency order

---

## PHASE 1 — Commit uncommitted work (MUST DO FIRST)

### 1.1 Delete the collision file
```bash
rm src/luna/inference/haiku_subtask_backend.py
```
This file was seeded from GitHub. GitHub version (inside 45ad0f8) is authoritative.

### 1.2 Split uncommitted work into logical commits
Stage and commit in this order:

**Group 1:** `feat: retrieval retry cascade + query decomposition`
- `src/luna/engine.py`
- `src/luna/inference/subtasks.py`
- `src/luna/librarian/cluster_retrieval.py`

**Group 2:** `feat: cartridge schema + document comprehension extraction`
- `src/luna/substrate/aibrarian_engine.py`
- `src/luna/substrate/aibrarian_schema.py`
- `config/aibrarian_registry.yaml`

**Group 3:** `feat: retrieval mode awareness wiring`
- `src/luna/context/assembler.py`
- `src/luna/actors/director.py`
- `src/luna/entities/context.py`
- `src/luna/entities/models.py`

**Group 4:** `feat: arcade skill + nexus tools`
- `src/luna/skills/arcade/` (untracked)
- `src/luna/tools/nexus_tools.py` (untracked)
- `frontend/src/eclissi/widgets/ArcadeWidget.jsx` (untracked)
- `arcade/` (untracked)
- `collections/` (untracked)

**Group 5:** `chore: observatory graph view + eclissi polish`
- All remaining modified frontend files
- `src/luna/actors/history_manager.py`
- `src/luna/agentic/loop.py`
- `src/luna/grounding/grounding_link.py`
- `src/luna/actors/scribe.py`
- `src/luna/cli/debug.py`
- `src/luna/diagnostics/` files
- `src/luna/llm/providers/claude_provider.py`
- `src/luna/services/kozmo/graph.py`
- `src/luna/services/observatory/routes.py`
- `src/luna/tuning/session.py`
- Remaining modified files not in other groups

**Group 6:** `docs: handoff docs + test reports`
- All `Docs/*.md`, `Docs/Handoffs/*.md` (untracked)
- PDFs, YAMLs, HTML docs

**Group 7:** `chore: scripts + config`
- `scripts/*.py`, `scripts/*.sh`
- `config/display.json`, `config/llm_providers.json`
- `frontend/vite.config.js`, `scripts/run.py`
- Any remaining untracked files

### 1.3 Tag pre-merge state
```bash
git tag pre-github-merge-$(date +%Y%m%d)
```

---

## PHASE 2 — Fetch remote

```bash
git fetch origin
git log origin/main --oneline  # verify 9 commits visible
```

---

## PHASE 3 — Cherry-pick in dependency order

**STOP after each step. Verify. Then proceed.**

### Step 3.1 — `e83a635` One Door Architecture (foundational, MUST be first)
```bash
git cherry-pick e83a635
```
- **Expect heavy conflicts** in `director.py`
- Cherry-pick wins on: `luna_respond()` as single entry point, ring buffer read top / write bottom, single code path for streaming
- Local wins on: register state, aperture plumbing, reflection mode, nexus context, Guardian integration, CuriosityBuffer hooks
- Manually merge both sides into the new `luna_respond()` funnel
- **Verify:** `grep -n "luna_respond" src/luna/actors/director.py` must hit
- **Smoke test:** engine starts, no import errors

### Step 3.2 — `7726012` Intent-aware routing + Ollama swap
- **FIRST:** Extract `ollama_provider.py` from the commit that introduced it:
  ```bash
  git show 45ad0f8:src/luna/llm/providers/ollama_provider.py > src/luna/llm/providers/ollama_provider.py
  ```
  If that path doesn't exist in 45ad0f8, check 7726012 itself. Stage and commit as prep.
- Register in `src/luna/llm/providers/__init__.py` and `config/llm_providers.json`
- Then: `git cherry-pick 7726012`
- Conflicts in `director.py` should be smaller since One Door is now the base

### Step 3.3 — `ccf4925` Three-signal retrieval scoring
```bash
git cherry-pick ccf4925
```
- Touches `director.py` +8, `assembler.py` +25, `substrate/memory.py` +63
- Conflicts in `assembler.py` (local has reflection mode awareness). Both coexist — scoring = memory fetch, reflection mode = prompt build.
- Conflict in `substrate/memory.py` (local has small tweaks). Merge both.

### Step 3.4 — `934b316` Deep memory test fixes
```bash
git cherry-pick 934b316
```
- Touches `director.py`, `api/server.py`, `ollama_provider.py`, `lunascript/veto.py`, `qa/assertions.py`, `qa/context.py`
- Low conflict risk — mostly additive bug fixes

### Step 3.5 — `07852b0` DB lock resilience
```bash
git cherry-pick 07852b0
```
- Touches `api/server.py` +69, `engine.py` +38, `substrate/database.py` +55
- Conflicts likely in `engine.py` (local +941) and `api/server.py` (local +70)
- Keep BOTH retry logic AND local query-expansion work
- High value — pure bug fix

### Step 3.6 — `b2c7934` LunaFM (biggest feature commit)
```bash
git cherry-pick b2c7934
```
- Mostly new files (low conflict): station.yaml, channels/*.yaml, RadioWidget.jsx, LunaFMSection.jsx
- High-conflict files: `Builds/Lunar-Forge/core.py`, `director.py`, `engine.py`, `api/server.py`, `substrate/memory.py`, `config/llm_providers.json`, `frontend/vite.config.js`, `scripts/run.py`, `EclissiShell.jsx`, `WidgetDock.jsx`, `SettingsApp.jsx`
- EclissiShell registrations and WidgetDock entries MUST coexist with Guardian/Arcade widgets already registered locally

### Step 3.7 — `45ad0f8` WIP snapshot (SELECTIVE — do NOT cherry-pick whole)
```bash
git show 45ad0f8 --stat  # review what's in it
```
Cherry-pick individual files of value:
```bash
git checkout 45ad0f8 -- handoffs/HANDOFF_Database_Lock_Audit_And_Fix.md
git checkout 45ad0f8 -- handoffs/HANDOFF_LLM_Provider_Abstraction_And_Settings.md
git checkout 45ad0f8 -- handoffs/HANDOFF_Memory_Pollution_Cleanup.md
git checkout 45ad0f8 -- handoffs/HANDOFF_Pipeline_Latency_Instrumentation.md
git checkout 45ad0f8 -- scripts/cleanup_memory_pollution.py
git checkout 45ad0f8 -- scripts/migrate_edge_types.py
git checkout 45ad0f8 -- src/luna/llm/intent_router.py
git checkout 45ad0f8 -- src/luna/inference/haiku_subtask_backend.py
```
Review `src/luna/substrate/graph.py` (+258) — grab if it doesn't duplicate local work.
Stage and commit: `chore: selective cherry-pick from WIP snapshot 45ad0f8`

### Step 3.8 — `424d791` .forge.pid untrack
```bash
git cherry-pick 424d791
```
Trivial. Skip `ad6a743` (unrelated root, cannot apply).

---

## PHASE 4 — Verification

Run ALL of these. Do not skip any.

```bash
# History check
git log --oneline -35

# One Door present
grep -rn "luna_respond" src/luna/actors/director.py

# Ollama present
ls src/luna/llm/providers/ollama_provider.py

# No import errors
PYTHONPATH=src .venv/bin/python -c "from luna.engine import Engine; print('OK')"

# Start backend
PYTHONPATH=src .venv/bin/python scripts/run.py --server --host 0.0.0.0 --port 8000
```

Smoke test through Eclissi (NOT raw curl):
- [ ] Director routes through `luna_respond()` (check logs)
- [ ] Ollama provider responds for local inference
- [ ] Retrieval scores reflect three-signal formula
- [ ] No DB lock errors under rapid-fire queries
- [ ] LunaFM RadioWidget renders in Eclissi shell
- [ ] Guardian Luna panel still works
- [ ] CuriosityBuffer still holds questions

Run test suite:
```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/test_register.py -v
```

### Only after ALL verification passes:
```bash
git push origin main
```
Regular push, no force. Local is now ahead of origin with clean linear history.

---

## CRITICAL FILES (expect heavy conflict resolution)

| File | Touched by | Conflict severity |
|------|-----------|-------------------|
| `src/luna/actors/director.py` | Steps 3.1-3.6 + local | **EXTREME** |
| `src/luna/engine.py` | Steps 3.5, 3.6 + local +941 | HIGH |
| `src/luna/api/server.py` | Steps 3.4-3.6 + local +70 | HIGH |
| `src/luna/context/assembler.py` | Step 3.3 + local +95 | MEDIUM |
| `src/luna/substrate/memory.py` | Steps 3.3, 3.6 | MEDIUM |
| `src/luna/substrate/aibrarian_engine.py` | Step 3.6 + local +597 | MEDIUM |

## FALLBACK

At any step: `git cherry-pick --abort` returns to clean state.
Full rollback: `git checkout pre-github-merge-*` tag.

## RISKS

- **Conflict fatigue:** 8 cherry-picks × 2-6 files = 20-40 conflict resolutions. Tedious but tractable.
- **director.py refactor risk:** One Door changes director's shape. Guardian, CuriosityBuffer, aperture, register, reflection mode must be re-wired into `luna_respond()` funnel. This is the single hardest step.
- **Regression risk:** The combined system has never existed before. Smoke tests are mandatory.
