# MIGRATION-PLAN.md

## Luna Engine Bible v3.0 - Folder Reorganization Plan

**Created:** 2026-01-30
**Status:** PENDING REVIEW
**Risk Level:** MEDIUM (path references in CLAUDE.md and imports)

---

## Executive Summary

This migration plan addresses folder organization issues:
1. **21 HANDOFF*.md files in root** that should be in docs
2. **6 CLAUDE-CODE*.md files in root** that should be in docs
3. **"LUNA ENGINE Bible" has spaces** - problematic for CLI
4. **"Docs" uppercase** - should be lowercase "docs"
5. **Scripts unorganized** - need categorization
6. **Stray files in root** - STATUS-VS-BIBLE.md, WISHLIST*.md

---

## Pre-Migration Checklist

- [ ] All tests pass (`pytest tests/ -v`)
- [ ] Git status clean (commit pending changes)
- [ ] Create migration branch (`git checkout -b refactor/folder-reorganization`)
- [ ] Backup CLAUDE.md (critical paths referenced)
- [ ] Document all files referencing old paths

---

## Current Structure Analysis

### Root Folder Issues (FILES TO MOVE)

#### HANDOFF*.md Files (21 files) - Move to docs/bible/handoffs/
```
HANDOFF-MEMORY-ECONOMY-INTEGRATION.md
HANDOFF_AGENTIC_WIRING.md
HANDOFF_EMERGENT_PERSONALITY.md
HANDOFF_EMERGENT_PERSONALITY_TBD.md
HANDOFF_ENTITY_SYSTEM.md
HANDOFF_FORGE_MCP_BUGFIX.md
HANDOFF_HYBRID_SEARCH.md
HANDOFF_LUNA_ORB_EMOTION_SYSTEM.md
HANDOFF_MCP_CONVERSATION_RECORDING.md
HANDOFF_MEMORY_AND_INFERENCE_FIX.md
HANDOFF_MEMORY_MATRIX_BRAIN_SCRUB.md
HANDOFF_MEMORY_SEARCH_FIX.md
HANDOFF_Multi_LLM_Provider_System.md
HANDOFF_PERSONA_STREAM_ROUTING.md
HANDOFF_PIPELINE_INTEGRATION.md
HANDOFF_SMART_FETCH_ENDPOINT.md
HANDOFF_UNIFIED_TURN_API.md
HANDOFF_VOICE_MEMORY_GAP.md
```

#### CLAUDE-CODE*.md Files (6 files) - Move to docs/bible/handoffs/
```
CLAUDE-CODE-HANDOFF.md
CLAUDE-CODE-HANDOFF-ENABLE-LOCAL.md
CLAUDE-CODE-HANDOFF-LUNA-HUB-MCP.md
CLAUDE-CODE-HANDOFF-MCP-MEMORY-DIAGNOSTIC.md
CLAUDE-CODE-HANDOFF-MCP-PLUGIN-WIRING.md
CLAUDE-CODE-HANDOFF-PLANNING-LAYER.md
```

#### Other Stray Files (3 files)
```
STATUS-VS-BIBLE.md          -> docs/bible/audit/
WISHLIST_MEMORY_COHERENCE.md -> docs/bible/roadmap/ (new dir)
```

### Docs Folder Issues

#### Docs/HANDOFF*.md (4 files) - Already in Docs, consolidate
```
Docs/HANDOFF_CRITICAL_SYSTEMS_AUDIT_AND_SAFEGUARDS.md
Docs/HANDOFF_LUNA_ORB_FOLLOW_BEHAVIOR.md
Docs/HANDOFF_PERFORMANCE_LAYER_UNIFIED.md
Docs/HANDOFF_PIPER_TTS_BINARY_WRAPPER.md
```

#### Docs/Handoffs/ (9+ files) - Separate location, consolidate
Diagnostic-related handoffs that could merge with bible/handoffs/

### Scripts Organization

**Current:** 36 scripts in flat structure
**Target:** Categorized subdirectories

#### scripts/diagnostics/ (diagnostic and test scripts)
```
diagnose_mcp_memory.py
diagnostic_snapshot.py
run_all_diagnostics.sh
test_chat_flow.py
test_clusters.py
test_llm_providers.py
test_matrix_connection.py
test_mcp_pipeline.py
test_memory_economy_full.py
test_websocket.py
voice_diagnostics.py
verify_independence.py
verify_deps.py
verify_memory.sh
```

#### scripts/migrations/ (database and data migrations)
```
backfill_embeddings.py
backfill_entities_from_memories.py
backfill_entity_mentions.py
bootstrap_db.py
load_entity_seeds.py
migration_001_memory_economy.py
populate_fts5.py
matrix_scrubber.py
```

#### scripts/utils/ (utility and operational scripts)
```
run.py (KEEP - main entry point)
tune.py
monitor.py
inspect_state.py
git_forensics.sh
launch_app.sh
relaunch.sh
stop.sh
watch.sh
convert_peft_to_mlx.py
benchmark_local_inference.py
voight_kampff.py
```

---

## Target Structure

```
luna-engine/
├── config/                         # Keep as-is
├── docs/                           # RENAME from "Docs"
│   ├── bible/                      # RENAME from "LUNA ENGINE Bible"
│   │   ├── chapters/               # NEW - numbered .md files
│   │   │   ├── 00-FOUNDATIONS.md
│   │   │   ├── 00-TABLE-OF-CONTENTS.md
│   │   │   ├── 01-PHILOSOPHY.md
│   │   │   ├── 02-SYSTEM-ARCHITECTURE.md
│   │   │   ├── 03-MEMORY-MATRIX.md
│   │   │   ├── 03A-LOCK-IN-COEFFICIENT.md
│   │   │   ├── 04-THE-SCRIBE.md
│   │   │   ├── 05-THE-LIBRARIAN.md
│   │   │   ├── 06-CONVERSATION-TIERS.md
│   │   │   ├── 06-DIRECTOR-LLM.md
│   │   │   ├── 07-RUNTIME-ENGINE.md
│   │   │   ├── 08-DELEGATION-PROTOCOL.md
│   │   │   ├── 09-PERFORMANCE.md
│   │   │   ├── 10-SOVEREIGNTY.md
│   │   │   ├── 11-TRAINING-DATA-STRATEGY.md
│   │   │   ├── 12-FUTURE-ROADMAP.md
│   │   │   ├── 13-SYSTEM-OVERVIEW.md
│   │   │   ├── 14-AGENTIC-ARCHITECTURE.md
│   │   │   ├── 15-API-REFERENCE.md
│   │   │   └── 16-LUNA-HUB-UI.md
│   │   ├── handoffs/               # CONSOLIDATE all handoffs
│   │   ├── audit/                  # Keep as-is
│   │   ├── reference/              # Keep as-is
│   │   ├── roadmap/                # NEW - wishlist/roadmap items
│   │   ├── media/                  # RENAME from "NotebookLM Media"
│   │   └── pdfs/                   # RENAME from "PDFs"
│   ├── design/                     # RENAME from "Design"
│   ├── training/                   # Keep (lowercase already)
│   └── roadmap/                    # RENAME from "Roadmap"
├── frontend/                       # Keep as-is
├── scripts/
│   ├── run.py                      # Keep at root of scripts/
│   ├── diagnostics/                # NEW
│   ├── migrations/                 # NEW
│   └── utils/                      # NEW
├── src/                            # Keep as-is
├── tests/
│   ├── unit/                       # Already exists (good!)
│   ├── smoke/                      # Already exists (good!)
│   ├── integration/                # Already exists (good!)
│   ├── tracers/                    # Already exists (good!)
│   └── diagnostics/                # Keep existing
├── entities/                       # Keep as-is (data)
├── migrations/                     # Keep as-is (SQL)
├── Tools/                          # Consider: tools/ lowercase?
├── data/                           # Keep as-is
├── models/                         # Keep as-is
├── .swarm/                         # Keep as-is
├── CLAUDE.md                       # Keep in root (UPDATE PATHS)
├── pyproject.toml                  # Keep in root
└── README.md                       # Keep if exists
```

---

## Phase A: Create Target Directories

```bash
# Create new directory structure
mkdir -p docs/bible/chapters
mkdir -p docs/bible/roadmap
mkdir -p docs/bible/media
mkdir -p scripts/diagnostics
mkdir -p scripts/migrations
mkdir -p scripts/utils
```

**Note:** Do NOT create docs/ yet - will be created when renaming Docs/

---

## Phase B: Move Bible Chapters (20 files)

Move numbered .md files to chapters/ subdirectory:

```bash
# From "Docs/LUNA ENGINE Bible/" to "docs/bible/chapters/"
# These moves happen AFTER the Docs -> docs rename in Phase E

# Files to move:
# 00-FOUNDATIONS.md
# 00-TABLE-OF-CONTENTS
# 00-TABLE-OF-CONTENTS.md
# 01-PHILOSOPHY.md
# 02-SYSTEM-ARCHITECTURE.md
# 03-MEMORY-MATRIX.md
# 03A-LOCK-IN-COEFFICIENT.md
# 04-THE-SCRIBE.md
# 05-THE-LIBRARIAN.md
# 06-CONVERSATION-TIERS.md
# 06-DIRECTOR-LLM.md
# 07-RUNTIME-ENGINE.md
# 08-DELEGATION-PROTOCOL.md
# 09-PERFORMANCE.md
# 10-SOVEREIGNTY.md
# 11-TRAINING-DATA-STRATEGY.md
# 12-FUTURE-ROADMAP.md
# 13-SYSTEM-OVERVIEW.md
# 14-AGENTIC-ARCHITECTURE.md
# 15-API-REFERENCE.md
# 16-LUNA-HUB-UI.md
```

---

## Phase C: Move Root Handoffs to docs/bible/handoffs/

### C.1: HANDOFF*.md files from root (18 files)

```bash
# Move HANDOFF*.md from root to docs/bible/handoffs/
git mv HANDOFF-MEMORY-ECONOMY-INTEGRATION.md "docs/bible/handoffs/"
git mv HANDOFF_AGENTIC_WIRING.md "docs/bible/handoffs/"
git mv HANDOFF_EMERGENT_PERSONALITY.md "docs/bible/handoffs/"
git mv HANDOFF_EMERGENT_PERSONALITY_TBD.md "docs/bible/handoffs/"
git mv HANDOFF_ENTITY_SYSTEM.md "docs/bible/handoffs/"
git mv HANDOFF_FORGE_MCP_BUGFIX.md "docs/bible/handoffs/"
git mv HANDOFF_HYBRID_SEARCH.md "docs/bible/handoffs/"
git mv HANDOFF_LUNA_ORB_EMOTION_SYSTEM.md "docs/bible/handoffs/"
git mv HANDOFF_MCP_CONVERSATION_RECORDING.md "docs/bible/handoffs/"
git mv HANDOFF_MEMORY_AND_INFERENCE_FIX.md "docs/bible/handoffs/"
git mv HANDOFF_MEMORY_MATRIX_BRAIN_SCRUB.md "docs/bible/handoffs/"
git mv HANDOFF_MEMORY_SEARCH_FIX.md "docs/bible/handoffs/"
git mv HANDOFF_Multi_LLM_Provider_System.md "docs/bible/handoffs/"
git mv HANDOFF_PERSONA_STREAM_ROUTING.md "docs/bible/handoffs/"
git mv HANDOFF_PIPELINE_INTEGRATION.md "docs/bible/handoffs/"
git mv HANDOFF_SMART_FETCH_ENDPOINT.md "docs/bible/handoffs/"
git mv HANDOFF_UNIFIED_TURN_API.md "docs/bible/handoffs/"
git mv HANDOFF_VOICE_MEMORY_GAP.md "docs/bible/handoffs/"
```

### C.2: CLAUDE-CODE*.md files from root (6 files)

```bash
git mv CLAUDE-CODE-HANDOFF.md "docs/bible/handoffs/"
git mv CLAUDE-CODE-HANDOFF-ENABLE-LOCAL.md "docs/bible/handoffs/"
git mv CLAUDE-CODE-HANDOFF-LUNA-HUB-MCP.md "docs/bible/handoffs/"
git mv CLAUDE-CODE-HANDOFF-MCP-MEMORY-DIAGNOSTIC.md "docs/bible/handoffs/"
git mv CLAUDE-CODE-HANDOFF-MCP-PLUGIN-WIRING.md "docs/bible/handoffs/"
git mv CLAUDE-CODE-HANDOFF-PLANNING-LAYER.md "docs/bible/handoffs/"
```

### C.3: Other stray files from root

```bash
git mv STATUS-VS-BIBLE.md "docs/bible/audit/"
git mv WISHLIST_MEMORY_COHERENCE.md "docs/bible/roadmap/"
```

### C.4: Consolidate Docs/HANDOFF*.md (4 files)

```bash
git mv "Docs/HANDOFF_CRITICAL_SYSTEMS_AUDIT_AND_SAFEGUARDS.md" "docs/bible/handoffs/"
git mv "Docs/HANDOFF_LUNA_ORB_FOLLOW_BEHAVIOR.md" "docs/bible/handoffs/"
git mv "Docs/HANDOFF_PERFORMANCE_LAYER_UNIFIED.md" "docs/bible/handoffs/"
git mv "Docs/HANDOFF_PIPER_TTS_BINARY_WRAPPER.md" "docs/bible/handoffs/"
```

### C.5: Consolidate Docs/Handoffs/ (merge into bible/handoffs/)

```bash
# Move all files from Docs/Handoffs/ to docs/bible/handoffs/
# Subdirectories (DiagnosticResults, VoightKampffResults) stay as subdirs
git mv "Docs/Handoffs/"* "docs/bible/handoffs/"
```

---

## Phase D: Organize Scripts

### D.1: Create script subdirectories

```bash
mkdir -p scripts/diagnostics
mkdir -p scripts/migrations
mkdir -p scripts/utils
```

### D.2: Move diagnostic scripts (14 files)

```bash
git mv scripts/diagnose_mcp_memory.py scripts/diagnostics/
git mv scripts/diagnostic_snapshot.py scripts/diagnostics/
git mv scripts/run_all_diagnostics.sh scripts/diagnostics/
git mv scripts/test_chat_flow.py scripts/diagnostics/
git mv scripts/test_clusters.py scripts/diagnostics/
git mv scripts/test_llm_providers.py scripts/diagnostics/
git mv scripts/test_matrix_connection.py scripts/diagnostics/
git mv scripts/test_mcp_pipeline.py scripts/diagnostics/
git mv scripts/test_memory_economy_full.py scripts/diagnostics/
git mv scripts/test_websocket.py scripts/diagnostics/
git mv scripts/voice_diagnostics.py scripts/diagnostics/
git mv scripts/verify_independence.py scripts/diagnostics/
git mv scripts/verify_deps.py scripts/diagnostics/
git mv scripts/verify_memory.sh scripts/diagnostics/
```

### D.3: Move migration scripts (8 files)

```bash
git mv scripts/backfill_embeddings.py scripts/migrations/
git mv scripts/backfill_entities_from_memories.py scripts/migrations/
git mv scripts/backfill_entity_mentions.py scripts/migrations/
git mv scripts/bootstrap_db.py scripts/migrations/
git mv scripts/load_entity_seeds.py scripts/migrations/
git mv scripts/migration_001_memory_economy.py scripts/migrations/
git mv scripts/populate_fts5.py scripts/migrations/
git mv scripts/matrix_scrubber.py scripts/migrations/
```

### D.4: Move utility scripts (10 files)

```bash
# run.py stays at scripts/run.py (main entry point)
git mv scripts/tune.py scripts/utils/
git mv scripts/monitor.py scripts/utils/
git mv scripts/inspect_state.py scripts/utils/
git mv scripts/git_forensics.sh scripts/utils/
git mv scripts/launch_app.sh scripts/utils/
git mv scripts/relaunch.sh scripts/utils/
git mv scripts/stop.sh scripts/utils/
git mv scripts/watch.sh scripts/utils/
git mv scripts/convert_peft_to_mlx.py scripts/utils/
git mv scripts/benchmark_local_inference.py scripts/utils/
git mv scripts/voight_kampff.py scripts/utils/
```

---

## Phase E: Rename Directories (CRITICAL - AFFECTS IMPORTS)

### E.1: Rename "Docs" to "docs"

```bash
# Git on macOS is case-insensitive by default
# Two-step rename required
git mv Docs docs_temp
git mv docs_temp docs
```

### E.2: Rename "LUNA ENGINE Bible" to "bible"

```bash
git mv "docs/LUNA ENGINE Bible" docs/bible
```

### E.3: Rename subdirectories to lowercase

```bash
git mv docs/Design docs/design
git mv docs/Roadmap docs/roadmap
git mv "docs/bible/NotebookLM Media" docs/bible/media
git mv docs/bible/PDFs docs/bible/pdfs
git mv docs/bible/Reference docs/bible/reference
git mv docs/bible/Handoffs docs/bible/handoffs
git mv docs/bible/Audit docs/bible/audit
```

---

## Phase F: Update Imports/References

### F.1: CLAUDE.md - Path Updates Required

**File:** `/CLAUDE.md`

**Changes needed:**
```
OLD: └── Docs/LUNA ENGINE Bible/ # Full specification
NEW: └── docs/bible/             # Full specification

OLD: See: `Docs/LUNA ENGINE Bible/Handoffs/CLAUDE-CODE-HANDOFF-TEST-FIXES-2026-01-13.md`
NEW: See: `docs/bible/handoffs/CLAUDE-CODE-HANDOFF-TEST-FIXES-2026-01-13.md`

OLD: See `Docs/LUNA ENGINE Bible/` for full specification:
NEW: See `docs/bible/` for full specification:
```

### F.2: Files Referencing Old Paths (grep search)

Search for references to update:
```bash
grep -r "LUNA ENGINE Bible" --include="*.md" --include="*.py" --include="*.js"
grep -r "Docs/" --include="*.md" --include="*.py" --include="*.js"
```

### F.3: Import Statements in Python

Check scripts that may import from other scripts:
```bash
grep -r "from scripts\." --include="*.py"
grep -r "import scripts\." --include="*.py"
```

---

## Phase G: Git Commits

### Commit Strategy (Atomic commits for easy rollback)

```bash
# Commit 1: Create directory structure
git add -A
git commit -m "refactor: create new directory structure for reorganization

- Add docs/bible/chapters/, roadmap/, media/ directories
- Add scripts/diagnostics/, migrations/, utils/ directories

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"

# Commit 2: Move handoffs from root
git add -A
git commit -m "refactor: consolidate handoff documents into docs/bible/handoffs/

- Move 18 HANDOFF*.md files from root
- Move 6 CLAUDE-CODE*.md files from root
- Move 4 HANDOFF*.md files from Docs/
- Consolidate Docs/Handoffs/ contents

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"

# Commit 3: Organize scripts
git add -A
git commit -m "refactor: organize scripts into categorized subdirectories

- scripts/diagnostics/: 14 diagnostic and test scripts
- scripts/migrations/: 8 database and data migration scripts
- scripts/utils/: 10 utility and operational scripts
- Keep run.py at scripts/run.py as main entry point

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"

# Commit 4: Rename directories
git add -A
git commit -m "refactor: standardize directory naming conventions

- Rename Docs/ to docs/ (lowercase)
- Rename 'LUNA ENGINE Bible' to 'bible' (no spaces)
- Rename Design/ to design/, Roadmap/ to roadmap/
- Rename NotebookLM Media/ to media/, PDFs/ to pdfs/

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"

# Commit 5: Move bible chapters
git add -A
git commit -m "refactor: move bible chapter files to chapters/ subdirectory

- Move 20 numbered .md files to docs/bible/chapters/
- Keeps bible root clean with only subdirectories

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"

# Commit 6: Update references
git add -A
git commit -m "refactor: update path references in CLAUDE.md and documentation

- Update CLAUDE.md with new paths
- Update any cross-references in documentation

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Post-Migration Checklist

- [ ] All tests pass (`pytest tests/ -v`)
- [ ] `python scripts/run.py --help` works
- [ ] Import statements work (no ModuleNotFoundError)
- [ ] CLAUDE.md paths are correct
- [ ] No broken links in documentation
- [ ] Git history preserved (verify with `git log --follow`)
- [ ] All handoffs accessible in new location
- [ ] Scripts execute from new locations

---

## Rollback Plan

### If migration fails at any phase:

```bash
# Option 1: Reset to before migration
git reset --hard HEAD~N  # where N = number of commits made

# Option 2: Revert specific commits
git revert <commit-hash>

# Option 3: Restore from backup branch
git checkout main  # or whatever was the original branch
```

### Critical files to backup before starting:
- `CLAUDE.md`
- `pyproject.toml`
- Any modified source files

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Broken imports after script move | Medium | High | Test all scripts after move |
| CLAUDE.md paths wrong | Low | Medium | Verify paths manually |
| Git history lost | Low | High | Use `git mv` not `mv` |
| Case-sensitivity issues on macOS | Medium | Medium | Two-step rename |
| Test failures | Medium | Medium | Run full test suite after each phase |

---

## Files That SHOULD Stay in Root

These files are correctly placed and should NOT be moved:
- `CLAUDE.md` - Claude Code configuration
- `pyproject.toml` - Python project config
- `.gitignore` - Git ignore rules
- `.env` - Environment variables (gitignored)
- `uv.lock` - UV package lock
- `.DS_Store` - macOS metadata (gitignored)

---

## Summary Statistics

| Category | Before | After |
|----------|--------|-------|
| Root HANDOFF*.md files | 18 | 0 |
| Root CLAUDE-CODE*.md files | 6 | 0 |
| Root stray .md files | 2 | 0 |
| Script organization | Flat (36 files) | 3 subdirs |
| Bible chapters location | Bible root | chapters/ subdir |
| Directory spaces | 1 ("LUNA ENGINE Bible") | 0 |
| Uppercase directories | 3 (Docs, Design, Roadmap) | 0 |

---

## Execution Order

1. **Review this plan** - Do NOT execute until approved
2. **Phase A** - Create target directories
3. **Phase E** - Rename directories (do this early to simplify moves)
4. **Phase B** - Move bible chapters
5. **Phase C** - Move handoffs (root + Docs/)
6. **Phase D** - Organize scripts
7. **Phase F** - Update references
8. **Phase G** - Commit changes
9. **Verify** - Run post-migration checklist

---

**STATUS: AWAITING REVIEW**

Please review this plan before execution. Key decisions needed:
1. Confirm target structure is acceptable
2. Confirm script categorization is correct
3. Decide on Tools/ directory (keep uppercase or rename to tools/)
4. Confirm bible chapters should move to chapters/ subdir
