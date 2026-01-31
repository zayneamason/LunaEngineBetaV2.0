# CLAUDE-CODE-HANDOFF: Folder Reorganization

**Created:** 2026-01-31
**Status:** APPROVED FOR EXECUTION
**Risk Level:** MEDIUM
**Estimated Time:** 30-45 minutes

---

## Executive Summary

Reorganize Luna Engine folder structure to eliminate spaces in paths, consolidate scattered handoffs, and categorize scripts. **Keep "Docs" uppercase** per user preference.

### Scope

| Action | Status |
|--------|--------|
| Rename "LUNA ENGINE Bible" → "bible" | ✅ APPROVED |
| Move root HANDOFF*.md files | ✅ APPROVED |
| Move root CLAUDE-CODE*.md files | ✅ APPROVED |
| Organize scripts into subdirs | ✅ APPROVED |
| Move bible chapters to chapters/ | ✅ APPROVED |
| Rename "Docs" → "docs" | ❌ EXCLUDED |

---

## Pre-Flight Checklist

**STOP. Execute these checks before ANY file operations:**

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root

# 1. Verify clean git state
git status
# REQUIRED: Working tree clean OR all changes committed

# 2. Create safety branch
git checkout -b refactor/folder-reorg-$(date +%Y%m%d)

# 3. Run tests to establish baseline
pytest tests/ -q --tb=no
# RECORD: Number of passed/failed tests

# 4. Verify critical files exist
ls -la CLAUDE.md pyproject.toml
# REQUIRED: Both files exist

# 5. Backup CLAUDE.md
cp CLAUDE.md CLAUDE.md.backup
```

**GATE 1: All 5 checks must pass before proceeding.**

---

## Phase 1: Create Directory Structure

### 1.1 Create New Directories

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root

# Bible subdirectories
mkdir -p "Docs/LUNA ENGINE Bible/chapters"
mkdir -p "Docs/LUNA ENGINE Bible/roadmap"

# Script subdirectories  
mkdir -p scripts/diagnostics
mkdir -p scripts/migrations
mkdir -p scripts/utils
```

### 1.2 Verify Phase 1

```bash
# Verify directories created
ls -la "Docs/LUNA ENGINE Bible/" | grep -E "^d"
ls -la scripts/ | grep -E "^d"
```

**Expected output:** chapters, roadmap dirs in Bible; diagnostics, migrations, utils in scripts

**GATE 2: Directory structure verified before proceeding.**

---

## Phase 2: Rename "LUNA ENGINE Bible" → "bible"

### 2.1 Execute Rename

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root

# Two-step rename for case-insensitive filesystem safety
git mv "Docs/LUNA ENGINE Bible" "Docs/bible_temp"
git mv "Docs/bible_temp" "Docs/bible"
```

### 2.2 Verify Phase 2

```bash
# Verify rename
ls -la Docs/
# REQUIRED: "bible" directory exists, "LUNA ENGINE Bible" gone

# Verify contents preserved
ls "Docs/bible/" | head -5
# REQUIRED: Shows existing files (Audit, Handoffs, etc.)
```

### 2.3 Commit Phase 2

```bash
git add -A
git commit -m "refactor: rename 'LUNA ENGINE Bible' to 'bible' (no spaces)

Removes spaces from path for CLI compatibility.
Contents preserved, structure unchanged.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

**GATE 3: Bible directory renamed and committed.**

---

## Phase 3: Move Bible Chapters to chapters/

### 3.1 Move Chapter Files

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/Docs/bible

# Move all numbered chapter files
git mv 00-FOUNDATIONS.md chapters/
git mv 00-TABLE-OF-CONTENTS.md chapters/
git mv 01-PHILOSOPHY.md chapters/
git mv 02-SYSTEM-ARCHITECTURE.md chapters/
git mv 03-MEMORY-MATRIX.md chapters/
git mv 03A-LOCK-IN-COEFFICIENT.md chapters/
git mv 04-THE-SCRIBE.md chapters/
git mv 05-THE-LIBRARIAN.md chapters/
git mv 06-CONVERSATION-TIERS.md chapters/
git mv 06-DIRECTOR-LLM.md chapters/
git mv 07-RUNTIME-ENGINE.md chapters/
git mv 08-DELEGATION-PROTOCOL.md chapters/
git mv 09-PERFORMANCE.md chapters/
git mv 10-SOVEREIGNTY.md chapters/
git mv 11-TRAINING-DATA-STRATEGY.md chapters/
git mv 12-FUTURE-ROADMAP.md chapters/
git mv 13-SYSTEM-OVERVIEW.md chapters/
git mv 14-AGENTIC-ARCHITECTURE.md chapters/
git mv 15-API-REFERENCE.md chapters/
git mv 16-LUNA-HUB-UI.md chapters/
```

### 3.2 Verify Phase 3

```bash
# Count chapters moved
ls Docs/bible/chapters/*.md | wc -l
# REQUIRED: 20 files

# Verify no numbered files left in bible root
ls Docs/bible/*.md 2>/dev/null | grep -E "^[0-9]" | wc -l
# REQUIRED: 0 files
```

### 3.3 Commit Phase 3

```bash
git add -A
git commit -m "refactor: move bible chapters to chapters/ subdirectory

Moves 20 numbered .md files to Docs/bible/chapters/
Keeps bible root clean with only subdirectories.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

**GATE 4: Chapters moved and committed.**

---

## Phase 4: Consolidate Handoffs

### 4.1 Move Root HANDOFF*.md Files (18 files)

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root

# Move each file individually to track errors
git mv HANDOFF-MEMORY-ECONOMY-INTEGRATION.md Docs/bible/Handoffs/ 2>/dev/null || echo "SKIP: HANDOFF-MEMORY-ECONOMY-INTEGRATION.md not found"
git mv HANDOFF_AGENTIC_WIRING.md Docs/bible/Handoffs/ 2>/dev/null || echo "SKIP: HANDOFF_AGENTIC_WIRING.md not found"
git mv HANDOFF_EMERGENT_PERSONALITY.md Docs/bible/Handoffs/ 2>/dev/null || echo "SKIP: HANDOFF_EMERGENT_PERSONALITY.md not found"
git mv HANDOFF_EMERGENT_PERSONALITY_TBD.md Docs/bible/Handoffs/ 2>/dev/null || echo "SKIP: HANDOFF_EMERGENT_PERSONALITY_TBD.md not found"
git mv HANDOFF_ENTITY_SYSTEM.md Docs/bible/Handoffs/ 2>/dev/null || echo "SKIP: HANDOFF_ENTITY_SYSTEM.md not found"
git mv HANDOFF_FORGE_MCP_BUGFIX.md Docs/bible/Handoffs/ 2>/dev/null || echo "SKIP: HANDOFF_FORGE_MCP_BUGFIX.md not found"
git mv HANDOFF_HYBRID_SEARCH.md Docs/bible/Handoffs/ 2>/dev/null || echo "SKIP: HANDOFF_HYBRID_SEARCH.md not found"
git mv HANDOFF_LUNA_ORB_EMOTION_SYSTEM.md Docs/bible/Handoffs/ 2>/dev/null || echo "SKIP: HANDOFF_LUNA_ORB_EMOTION_SYSTEM.md not found"
git mv HANDOFF_MCP_CONVERSATION_RECORDING.md Docs/bible/Handoffs/ 2>/dev/null || echo "SKIP: HANDOFF_MCP_CONVERSATION_RECORDING.md not found"
git mv HANDOFF_MEMORY_AND_INFERENCE_FIX.md Docs/bible/Handoffs/ 2>/dev/null || echo "SKIP: HANDOFF_MEMORY_AND_INFERENCE_FIX.md not found"
git mv HANDOFF_MEMORY_MATRIX_BRAIN_SCRUB.md Docs/bible/Handoffs/ 2>/dev/null || echo "SKIP: HANDOFF_MEMORY_MATRIX_BRAIN_SCRUB.md not found"
git mv HANDOFF_MEMORY_SEARCH_FIX.md Docs/bible/Handoffs/ 2>/dev/null || echo "SKIP: HANDOFF_MEMORY_SEARCH_FIX.md not found"
git mv HANDOFF_Multi_LLM_Provider_System.md Docs/bible/Handoffs/ 2>/dev/null || echo "SKIP: HANDOFF_Multi_LLM_Provider_System.md not found"
git mv HANDOFF_PERSONA_STREAM_ROUTING.md Docs/bible/Handoffs/ 2>/dev/null || echo "SKIP: HANDOFF_PERSONA_STREAM_ROUTING.md not found"
git mv HANDOFF_PIPELINE_INTEGRATION.md Docs/bible/Handoffs/ 2>/dev/null || echo "SKIP: HANDOFF_PIPELINE_INTEGRATION.md not found"
git mv HANDOFF_SMART_FETCH_ENDPOINT.md Docs/bible/Handoffs/ 2>/dev/null || echo "SKIP: HANDOFF_SMART_FETCH_ENDPOINT.md not found"
git mv HANDOFF_UNIFIED_TURN_API.md Docs/bible/Handoffs/ 2>/dev/null || echo "SKIP: HANDOFF_UNIFIED_TURN_API.md not found"
git mv HANDOFF_VOICE_MEMORY_GAP.md Docs/bible/Handoffs/ 2>/dev/null || echo "SKIP: HANDOFF_VOICE_MEMORY_GAP.md not found"
```

### 4.2 Move Root CLAUDE-CODE*.md Files (6 files)

```bash
git mv CLAUDE-CODE-HANDOFF.md Docs/bible/Handoffs/ 2>/dev/null || echo "SKIP: CLAUDE-CODE-HANDOFF.md not found"
git mv CLAUDE-CODE-HANDOFF-ENABLE-LOCAL.md Docs/bible/Handoffs/ 2>/dev/null || echo "SKIP: CLAUDE-CODE-HANDOFF-ENABLE-LOCAL.md not found"
git mv CLAUDE-CODE-HANDOFF-LUNA-HUB-MCP.md Docs/bible/Handoffs/ 2>/dev/null || echo "SKIP: CLAUDE-CODE-HANDOFF-LUNA-HUB-MCP.md not found"
git mv CLAUDE-CODE-HANDOFF-MCP-MEMORY-DIAGNOSTIC.md Docs/bible/Handoffs/ 2>/dev/null || echo "SKIP: CLAUDE-CODE-HANDOFF-MCP-MEMORY-DIAGNOSTIC.md not found"
git mv CLAUDE-CODE-HANDOFF-MCP-PLUGIN-WIRING.md Docs/bible/Handoffs/ 2>/dev/null || echo "SKIP: CLAUDE-CODE-HANDOFF-MCP-PLUGIN-WIRING.md not found"
git mv CLAUDE-CODE-HANDOFF-PLANNING-LAYER.md Docs/bible/Handoffs/ 2>/dev/null || echo "SKIP: CLAUDE-CODE-HANDOFF-PLANNING-LAYER.md not found"
```

### 4.3 Move Stray Files

```bash
git mv STATUS-VS-BIBLE.md Docs/bible/Audit/ 2>/dev/null || echo "SKIP: STATUS-VS-BIBLE.md not found"
git mv WISHLIST_MEMORY_COHERENCE.md Docs/bible/roadmap/ 2>/dev/null || echo "SKIP: WISHLIST_MEMORY_COHERENCE.md not found"
```

### 4.4 Move Docs/HANDOFF*.md Files (4 files)

```bash
git mv Docs/HANDOFF_CRITICAL_SYSTEMS_AUDIT_AND_SAFEGUARDS.md Docs/bible/Handoffs/ 2>/dev/null || echo "SKIP: not found"
git mv Docs/HANDOFF_LUNA_ORB_FOLLOW_BEHAVIOR.md Docs/bible/Handoffs/ 2>/dev/null || echo "SKIP: not found"
git mv Docs/HANDOFF_PERFORMANCE_LAYER_UNIFIED.md Docs/bible/Handoffs/ 2>/dev/null || echo "SKIP: not found"
git mv Docs/HANDOFF_PIPER_TTS_BINARY_WRAPPER.md Docs/bible/Handoffs/ 2>/dev/null || echo "SKIP: not found"
```

### 4.5 Verify Phase 4

```bash
# Count handoffs in root (should be 0 or near 0)
ls *.md 2>/dev/null | grep -iE "handoff|claude-code" | wc -l
# TARGET: 0

# Count handoffs in consolidated location
ls Docs/bible/Handoffs/*.md | wc -l
# TARGET: 30+ files
```

### 4.6 Commit Phase 4

```bash
git add -A
git commit -m "refactor: consolidate handoff documents into Docs/bible/Handoffs/

- Move 18 HANDOFF*.md files from root
- Move 6 CLAUDE-CODE*.md files from root  
- Move 4 HANDOFF*.md files from Docs/
- Move STATUS-VS-BIBLE.md to Audit/
- Move WISHLIST*.md to roadmap/

Co-Authored-By: Claude <noreply@anthropic.com>"
```

**GATE 5: Handoffs consolidated and committed.**

---

## Phase 5: Organize Scripts

### 5.1 Move Diagnostic Scripts (14 files)

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root

git mv scripts/diagnose_mcp_memory.py scripts/diagnostics/ 2>/dev/null || echo "SKIP"
git mv scripts/diagnostic_snapshot.py scripts/diagnostics/ 2>/dev/null || echo "SKIP"
git mv scripts/run_all_diagnostics.sh scripts/diagnostics/ 2>/dev/null || echo "SKIP"
git mv scripts/test_chat_flow.py scripts/diagnostics/ 2>/dev/null || echo "SKIP"
git mv scripts/test_clusters.py scripts/diagnostics/ 2>/dev/null || echo "SKIP"
git mv scripts/test_llm_providers.py scripts/diagnostics/ 2>/dev/null || echo "SKIP"
git mv scripts/test_matrix_connection.py scripts/diagnostics/ 2>/dev/null || echo "SKIP"
git mv scripts/test_mcp_pipeline.py scripts/diagnostics/ 2>/dev/null || echo "SKIP"
git mv scripts/test_memory_economy_full.py scripts/diagnostics/ 2>/dev/null || echo "SKIP"
git mv scripts/test_websocket.py scripts/diagnostics/ 2>/dev/null || echo "SKIP"
git mv scripts/voice_diagnostics.py scripts/diagnostics/ 2>/dev/null || echo "SKIP"
git mv scripts/verify_independence.py scripts/diagnostics/ 2>/dev/null || echo "SKIP"
git mv scripts/verify_deps.py scripts/diagnostics/ 2>/dev/null || echo "SKIP"
git mv scripts/verify_memory.sh scripts/diagnostics/ 2>/dev/null || echo "SKIP"
```

### 5.2 Move Migration Scripts (8 files)

```bash
git mv scripts/backfill_embeddings.py scripts/migrations/ 2>/dev/null || echo "SKIP"
git mv scripts/backfill_entities_from_memories.py scripts/migrations/ 2>/dev/null || echo "SKIP"
git mv scripts/backfill_entity_mentions.py scripts/migrations/ 2>/dev/null || echo "SKIP"
git mv scripts/bootstrap_db.py scripts/migrations/ 2>/dev/null || echo "SKIP"
git mv scripts/load_entity_seeds.py scripts/migrations/ 2>/dev/null || echo "SKIP"
git mv scripts/migration_001_memory_economy.py scripts/migrations/ 2>/dev/null || echo "SKIP"
git mv scripts/populate_fts5.py scripts/migrations/ 2>/dev/null || echo "SKIP"
git mv scripts/matrix_scrubber.py scripts/migrations/ 2>/dev/null || echo "SKIP"
```

### 5.3 Move Utility Scripts (11 files)

```bash
# NOTE: run.py stays at scripts/run.py (main entry point)
git mv scripts/tune.py scripts/utils/ 2>/dev/null || echo "SKIP"
git mv scripts/monitor.py scripts/utils/ 2>/dev/null || echo "SKIP"
git mv scripts/inspect_state.py scripts/utils/ 2>/dev/null || echo "SKIP"
git mv scripts/git_forensics.sh scripts/utils/ 2>/dev/null || echo "SKIP"
git mv scripts/launch_app.sh scripts/utils/ 2>/dev/null || echo "SKIP"
git mv scripts/relaunch.sh scripts/utils/ 2>/dev/null || echo "SKIP"
git mv scripts/stop.sh scripts/utils/ 2>/dev/null || echo "SKIP"
git mv scripts/watch.sh scripts/utils/ 2>/dev/null || echo "SKIP"
git mv scripts/convert_peft_to_mlx.py scripts/utils/ 2>/dev/null || echo "SKIP"
git mv scripts/benchmark_local_inference.py scripts/utils/ 2>/dev/null || echo "SKIP"
git mv scripts/voight_kampff.py scripts/utils/ 2>/dev/null || echo "SKIP"
```

### 5.4 Verify Phase 5

```bash
# Verify run.py still at scripts root
ls scripts/run.py
# REQUIRED: File exists

# Count files in each subdir
echo "diagnostics: $(ls scripts/diagnostics/ 2>/dev/null | wc -l)"
echo "migrations: $(ls scripts/migrations/ 2>/dev/null | wc -l)"
echo "utils: $(ls scripts/utils/ 2>/dev/null | wc -l)"

# Verify main entry point works
python scripts/run.py --help 2>/dev/null || echo "WARNING: run.py help failed"
```

### 5.5 Commit Phase 5

```bash
git add -A
git commit -m "refactor: organize scripts into categorized subdirectories

- scripts/diagnostics/: diagnostic and test scripts
- scripts/migrations/: database and data migration scripts  
- scripts/utils/: utility and operational scripts
- Keep run.py at scripts/run.py as main entry point

Co-Authored-By: Claude <noreply@anthropic.com>"
```

**GATE 6: Scripts organized and committed.**

---

## Phase 6: Update CLAUDE.md Paths

### 6.1 Update Path References

Edit `/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/CLAUDE.md`:

**Find and replace these patterns:**

| Old Pattern | New Pattern |
|-------------|-------------|
| `Docs/LUNA ENGINE Bible/` | `Docs/bible/` |
| `LUNA ENGINE Bible` | `bible` |
| `Docs/bible/Handoffs/` paths stay same | (no change needed) |

**Specific replacements:**

```
OLD: └── Docs/LUNA ENGINE Bible/    # Full specification
NEW: └── Docs/bible/                # Full specification

OLD: See `Docs/LUNA ENGINE Bible/` for full specification
NEW: See `Docs/bible/` for full specification

OLD: `Docs/LUNA ENGINE Bible/Handoffs/CLAUDE-CODE-HANDOFF-TEST-FIXES...`
NEW: `Docs/bible/Handoffs/CLAUDE-CODE-HANDOFF-TEST-FIXES...`
```

### 6.2 Update Internal Cross-References

Check and update any cross-references in moved files:

```bash
# Find files with old path references
grep -r "LUNA ENGINE Bible" Docs/bible/ --include="*.md" -l

# For each file found, update the path
# Example: sed -i '' 's/LUNA ENGINE Bible/bible/g' <file>
```

### 6.3 Verify Phase 6

```bash
# Verify no old paths remain in CLAUDE.md
grep "LUNA ENGINE Bible" CLAUDE.md
# REQUIRED: No matches

# Verify new paths are correct
grep "Docs/bible" CLAUDE.md | head -3
# REQUIRED: Shows updated paths
```

### 6.4 Commit Phase 6

```bash
git add -A
git commit -m "refactor: update path references in CLAUDE.md and documentation

- Update CLAUDE.md with new Docs/bible/ paths
- Update cross-references in documentation files

Co-Authored-By: Claude <noreply@anthropic.com>"
```

**GATE 7: Path references updated and committed.**

---

## Phase 7: Final Verification

### 7.1 Run Full Test Suite

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root

# Run all tests
pytest tests/ -v --tb=short

# Compare to baseline from pre-flight
# REQUIRED: Same or better pass rate
```

### 7.2 Verify Key Operations

```bash
# 1. Verify imports work
python -c "from src.luna.engine import LunaEngine; print('OK: Engine imports')"

# 2. Verify scripts run
python scripts/run.py --help

# 3. Verify documentation accessible
ls Docs/bible/chapters/00-TABLE-OF-CONTENTS.md
ls Docs/bible/Handoffs/
ls Docs/bible/Audit/

# 4. Verify no broken symlinks
find . -type l ! -exec test -e {} \; -print
# REQUIRED: No output (no broken links)
```

### 7.3 Final Git Status

```bash
git status
# REQUIRED: Clean working tree

git log --oneline -6
# REQUIRED: 6 commits from this migration
```

### 7.4 Merge to Main (Optional)

```bash
# If all checks pass:
git checkout main
git merge refactor/folder-reorg-$(date +%Y%m%d)

# Or create PR for review
```

---

## Rollback Procedure

### If Any Phase Fails

```bash
# Option 1: Reset current phase
git reset --hard HEAD

# Option 2: Reset to before migration
git checkout main
git branch -D refactor/folder-reorg-*

# Option 3: Restore CLAUDE.md from backup
cp CLAUDE.md.backup CLAUDE.md
```

### Emergency Recovery

```bash
# If tests fail after migration:
git log --oneline -10  # Find commit before migration
git reset --hard <commit-before-migration>
```

---

## Post-Migration Checklist

- [ ] All tests pass (same or better than baseline)
- [ ] `python scripts/run.py --help` works
- [ ] CLAUDE.md paths verified correct
- [ ] No HANDOFF*.md files in root
- [ ] No CLAUDE-CODE*.md files in root
- [ ] scripts/ has subdirectories (diagnostics, migrations, utils)
- [ ] Docs/bible/chapters/ has 20 .md files
- [ ] Git history preserved (`git log --follow` works)
- [ ] CLAUDE.md.backup can be deleted

---

## Summary of Changes

### Files Moved

| Source | Destination | Count |
|--------|-------------|-------|
| Root HANDOFF*.md | Docs/bible/Handoffs/ | ~18 |
| Root CLAUDE-CODE*.md | Docs/bible/Handoffs/ | ~6 |
| Docs/HANDOFF*.md | Docs/bible/Handoffs/ | ~4 |
| Bible chapters | Docs/bible/chapters/ | 20 |
| scripts/*.py (diagnostic) | scripts/diagnostics/ | ~14 |
| scripts/*.py (migration) | scripts/migrations/ | ~8 |
| scripts/*.py (utility) | scripts/utils/ | ~11 |

### Directories Renamed

| Old | New |
|-----|-----|
| `Docs/LUNA ENGINE Bible/` | `Docs/bible/` |

### Directories Created

| Path | Purpose |
|------|---------|
| `Docs/bible/chapters/` | Numbered bible chapters |
| `Docs/bible/roadmap/` | Wishlist/roadmap items |
| `scripts/diagnostics/` | Test and diagnostic scripts |
| `scripts/migrations/` | Database migration scripts |
| `scripts/utils/` | Utility scripts |

---

## Execution Notes for Claude Code

1. **Execute phases sequentially** - Each gate must pass before proceeding
2. **Use `2>/dev/null || echo "SKIP"` pattern** - Gracefully handle missing files
3. **Commit after each phase** - Enables granular rollback
4. **Run tests after Phase 7 only** - Full suite takes time
5. **Update CLAUDE.md carefully** - This file controls your own behavior

**DO NOT:**
- Skip pre-flight checks
- Combine phases into single commits
- Ignore "SKIP" messages (investigate if many appear)
- Proceed past a failed gate

---

*End of Handoff*
