# Luna Engine Bible Maintenance Guide

**Created:** January 25, 2026
**Version:** 1.0
**Purpose:** Procedures for keeping Bible documentation synchronized with codebase

---

## Overview

This guide establishes procedures for maintaining synchronization between the Luna Engine Bible (documentation) and the actual codebase implementation. The goal is to prevent documentation drift and ensure the Bible remains an accurate reference.

---

## Maintenance Triggers

### When to Update the Bible

| Trigger | Action Required |
|---------|-----------------|
| New actor added | Update Part VIII, add to ACTOR-TRACE.md |
| Schema change | Update Part III, run schema diff |
| New message type | Update relevant actor section in Part VIII |
| API endpoint added | Update Part VII, add to CODEBASE-INVENTORY.md |
| Lock-in formula change | Update Part IV (03A-LOCK-IN-COEFFICIENT.md) |
| New extraction type | Update Part V (04-THE-SCRIBE.md) |
| Test file added | Update TEST-COVERAGE.md |
| Dependency added | Update DEPENDENCY-GRAPH.md |

---

## Audit Procedures

### Quick Audit (Weekly)

```bash
# 1. Check for new/modified source files
git diff --stat HEAD~7 src/

# 2. Count files vs documented
find src -name "*.py" | wc -l  # Compare to CODEBASE-INVENTORY.md

# 3. Run tests to verify coverage
pytest tests/ --co -q | wc -l  # Compare to TEST-COVERAGE.md
```

### Full Audit (Monthly)

1. **Inventory Check**
   - Run `find src -name "*.py"` and compare to CODEBASE-INVENTORY.md
   - Note any new files not documented

2. **Actor Trace**
   - Grep for `class.*Actor` in src/luna/actors/
   - Verify all actors documented in ACTOR-TRACE.md
   - Check message types match actual `handle()` implementations

3. **Schema Verification**
   - Compare `src/luna/substrate/schema.sql` to Part III documentation
   - Check for new tables, columns, indexes

4. **Dependency Check**
   - Compare `pyproject.toml` dependencies to DEPENDENCY-GRAPH.md
   - Verify fallback paths still accurate

5. **Test Coverage**
   - Run `pytest --collect-only` and compare to TEST-COVERAGE.md
   - Update coverage matrix

---

## Bible Chapter Ownership

| Chapter | Primary File(s) | Owner Responsibility |
|---------|-----------------|---------------------|
| Part II (Personas) | actors/scribe.py, actors/librarian.py | Persona behavior |
| Part III (Memory Matrix) | substrate/*.py, schema.sql | Schema, queries |
| Part IV (Lock-In) | substrate/lock_in.py | Coefficient formula |
| Part V (Extraction) | actors/scribe.py, extraction/*.py | Extraction types |
| Part VI (Conversation Tiers) | actors/history_manager.py | Tier logic |
| Part VII (Runtime Engine) | engine.py, core/*.py | Lifecycle, ticks |
| Part VIII (Actor Orchestration) | actors/*.py | Message flow |
| Part XIV (Agentic Architecture) | agentic/*.py, context/*.py | Routing, planning |

---

## Code-to-Bible Sync Commands

### Find Undocumented Classes
```bash
# List all classes in src/
grep -r "^class " src/luna --include="*.py" | cut -d: -f2 | sort > /tmp/classes.txt

# Compare to CODEBASE-INVENTORY.md manually
```

### Find New Message Types
```bash
# Grep for message type handling
grep -r "msg.type ==" src/luna/actors --include="*.py"
grep -r "type=\"" src/luna/actors --include="*.py"
```

### Verify Schema Tables
```bash
# Extract table names from schema
grep "CREATE TABLE" src/luna/substrate/schema.sql | awk '{print $3}'
```

### Check Actor Count
```bash
# Count actor implementations
grep -l "class.*Actor" src/luna/actors/*.py | wc -l
```

---

## Update Workflow

### For Code Changes

1. **Before PR merge:**
   - Identify which Bible chapters affected
   - Add TODO comment in PR description

2. **After PR merge:**
   - Update relevant Bible chapter(s)
   - Update CHANGELOG.md with changes
   - Run quick audit commands

### For Bible Updates

1. **Create update branch:**
   ```bash
   git checkout -b docs/bible-update-YYYY-MM-DD
   ```

2. **Make changes with audit trail:**
   - Update version number in chapter header
   - Add entry to CHANGELOG.md
   - Reference specific code files/lines

3. **Verify accuracy:**
   - Cross-reference with actual code
   - Run any relevant tests

4. **PR with context:**
   - Link to code changes that triggered update
   - List specific discrepancies fixed

---

## Discrepancy Resolution

### Common Discrepancies

| Type | Resolution |
|------|------------|
| Table name mismatch | Update Bible to match schema.sql |
| Missing feature | Add "NOT IMPLEMENTED" note with TODO |
| Extra code feature | Add new section to Bible |
| Different constants | Update Bible with actual values |
| API signature change | Update Bible method signatures |

### Escalation Path

1. **Minor discrepancy:** Fix in Bible, add to CHANGELOG.md
2. **Major discrepancy:** Create investigation document in Audit/
3. **Architectural change:** Full reconciliation pass required

---

## Versioning Convention

### Bible Chapter Versions

Format: `vX.Y` where:
- X = Major revision (structure change)
- Y = Minor revision (content update)

Example: `v2.1` = Second major version, first update

### Audit Document Versions

Use date-based versioning: `YYYY-MM-DD`

---

## Automated Checks (Future)

### Planned Automation

1. **Schema diff tool** - Compare schema.sql to Part III
2. **Actor inventory** - Auto-generate actor list
3. **Message type extractor** - Parse handle() methods
4. **Test coverage reporter** - Generate coverage matrix

### CI Integration (Proposed)

```yaml
# .github/workflows/bible-check.yml
- name: Check Bible Sync
  run: |
    python scripts/bible_sync_check.py
    # Fails if discrepancies found
```

---

## Contact

For Bible maintenance questions:
- Check existing Audit/ documents first
- Review RECONCILIATION.md for known discrepancies
- Create issue in project tracker if new discrepancy found

---

**End of Maintenance Guide**
