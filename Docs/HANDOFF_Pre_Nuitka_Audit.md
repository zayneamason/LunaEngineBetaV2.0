# HANDOFF: Pre-Nuitka Packaging Audit — Luna Engine V2

## Context

We're preparing to compile Luna Engine into a standalone Nuitka binary for Tarcila's deployment (first external user). Before we build, we need a comprehensive audit: smoke tests, unit tests, import chain validation, data file inventory, and readiness assessment.

**Reference:** `Docs/HANDOFF_Nuitka_Package_Luna_Engine.docx` — the full packaging spec.

**Project root:** `/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root`

---

## Phase 1: Import Chain Validation

Nuitka's `--include-package` only works if the import graph is clean. Run a full import sweep.

### 1A. Verify all top-level packages import cleanly

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
source .venv/bin/activate

# Test each package that Nuitka will compile
python -c "import luna; print('luna OK')"
python -c "import luna_mcp; print('luna_mcp OK')"
python -c "import voice; print('voice OK')"
python -c "import luna.api.server; print('server OK')"
python -c "import luna.engine; print('engine OK')"
```

### 1B. Deep import scan — find all transitive imports

Write and run a script that crawls every .py file under `src/luna/`, `src/luna_mcp/`, and `src/voice/`, extracts all `import` and `from X import` statements, and reports:
- **Missing packages** — imports that aren't in pyproject.toml dependencies or stdlib
- **Conditional imports** — `try/except ImportError` blocks (these may silently fail in the compiled binary)
- **Dynamic imports** — `importlib.import_module()` calls (Nuitka can't trace these)
- **Relative import issues** — any broken relative imports

Pay special attention to:
- `groq` — used for Groq inference but not in pyproject.toml
- `openai` — may be imported by provider routing
- `torch` / `transformers` / `sentence-transformers` — heavy ML deps, are they required or optional?
- `dotenv` — imported with try/except in server.py
- `sqlite_vec` — C extension, critical for memory retrieval
- `mcp` — used in luna_mcp but listed under optional [mcp] deps
- `numpy` — listed under optional [memory] deps

### 1C. Catalog all `Path(__file__)` usage

Nuitka changes where `__file__` resolves. Find every instance:

```bash
grep -rn "__file__" src/luna/ src/luna_mcp/ src/voice/ --include="*.py" | grep -v __pycache__
```

Each one is a potential runtime path failure in the compiled binary. Document them all with what they resolve to and whether they'll break.

---

## Phase 2: Run Existing Tests

### 2A. Smoke tests

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
source .venv/bin/activate
python -m pytest tests/smoke/ -v --tb=short 2>&1
```

Tests:
- `test_engine_boots.py` — engine starts without crash
- `test_chat_responds.py` — send message, get response
- `test_memory_stores.py` — memory persistence works
- `test_websocket_connects.py` — WebSocket orb connection

### 2B. Unit tests

```bash
python -m pytest tests/ -v --tb=short -x 2>&1
```

Run with `-x` (stop on first failure) initially to see the health of the test suite. Then run full:

```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -50
```

Document:
- Total tests found
- Pass/fail/skip/error counts
- Any tests that require the engine to be running (mark as integration)
- Any tests that require API keys (mark as external)

### 2C. Test the specific modules in the Nuitka compile list

For each module in the Nuitka `--include-package` list, verify it can be imported and has no obvious issues:

```python
packages = [
    'luna', 'luna_mcp', 'voice',
    'fastapi', 'uvicorn', 'pydantic', 'httpx',
    'aiosqlite', 'networkx', 'yaml',
    'anthropic', 'starlette', 'anyio',
]
for pkg in packages:
    try:
        __import__(pkg)
        print(f"✓ {pkg}")
    except Exception as e:
        print(f"✗ {pkg}: {e}")
```

---

## Phase 3: Data File Inventory

The Nuitka build uses `--include-data-dir` for runtime files. Verify every data dependency exists and is accounted for.

### 3A. Config files (config/)

Required files that must ship:
- `config/directives_seed.yaml` — directive system boot data
- `config/fallback_chain.yaml` — LLM provider routing
- `config/personality.json` — base personality config
- `config/lunascript.yaml` — LunaScript config
- `config/skills.yaml` — skills config
- `config/voice_config.yaml` ← **CHECK**: is this in config/ or src/luna/voice/data/?
- `config/llm_providers.json` — provider definitions

Files that must NOT ship (contain Ahab's credentials):
- `config/google_credentials.json`
- `config/google_token.json`
- `config/google_token_drive.json`
- `config/identity_bypass.json`
- `config/eden.json`
- `config/dataroom.json`

**Action:** List every file in config/ and categorize as SHIP or EXCLUDE.

### 3B. Voice data files

Verify these paths exist and contain expected content:
- `src/voice/piper_bin/piper/piper` — Piper binary (check arch: `file <path>`)
- `src/voice/piper_models/` — ONNX voice models (list files + sizes)
- `src/luna/voice/data/corpus.json` — voice corpus
- `src/luna/voice/data/line_bank.json` — line bank
- `src/luna/voice/data/voice_config.yaml` — voice config

### 3C. Substrate files

- `src/luna/substrate/schema.sql` — database schema (CRITICAL for seed DB creation)

Verify the schema creates all required tables by running:
```bash
sqlite3 :memory: < src/luna/substrate/schema.sql
sqlite3 :memory: ".tables"
```

### 3D. Frontend build

- `frontend/dist/` — verify it exists and contains built assets
- Check `frontend/dist/index.html` exists
- Check `frontend/dist/assets/` has JS/CSS bundles

If dist/ is stale or missing, rebuild:
```bash
cd frontend && npm run build
```

---

## Phase 4: Entry Point & Server Audit

### 4A. Create and test run_luna.py

The entry point doesn't exist yet. Create it per the handoff spec:

```python
# run_luna.py
"""Luna Engine entry point for compiled binary."""
import sys
import os

# Set working directory to the binary's location
if getattr(sys, 'frozen', False):
    os.chdir(os.path.dirname(sys.executable))

# Ensure src/ is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import uvicorn
from luna.api.server import app

if __name__ == "__main__":
    uvicorn.run(app, host='127.0.0.1', port=8000)
```

Test it:
```bash
python run_luna.py
# Should start the server on :8000
# Ctrl+C to stop
```

### 4B. Verify server boots with blank database

Critical for Tarcila's first-run experience:

```bash
# Create a temp blank DB from schema
mkdir -p /tmp/luna-test
sqlite3 /tmp/luna-test/luna.sqlite < src/luna/substrate/schema.sql

# Boot the engine pointing at the blank DB
# (Need to figure out how to override database_path — check config loading)
```

Document:
- Does the engine boot cleanly with an empty DB?
- Does directive seeding work on first boot?
- Does personality load from config (not from memory)?
- Any errors or tracebacks on blank-DB startup?

### 4C. Server endpoint health check

With the engine running, hit key endpoints:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/status
curl http://localhost:8000/qa/health
curl http://localhost:8000/qa/assertions
```

---

## Phase 5: Dependency Gap Analysis

### 5A. Compare pyproject.toml deps vs actual imports

Cross-reference what's in `pyproject.toml` dependencies (core + optional) against what's actually imported at runtime. Flag:
- **Used but not declared** — will cause ImportError in compiled binary
- **Declared but not used** — bloat in the Nuitka build
- **Optional but required** — things in [memory] or [mcp] extras that are actually needed for core function

### 5B. Missing Nuitka --include-package entries

The current Nuitka command includes:
```
luna, luna_mcp, voice, fastapi, uvicorn, pydantic, httpx,
aiosqlite, networkx, yaml, anthropic, starlette, anyio
```

Likely missing (verify by checking imports):
- `groq` — Groq provider
- `openai` — if used by any provider
- `rich` — in core deps, used for console output
- `prompt_toolkit` — in core deps
- `sqlite_vec` — critical C extension for embeddings
- `numpy` — used by memory/embeddings
- `dotenv` — python-dotenv
- `mcp` — MCP protocol library
- `websockets` — if used by WebSocket handler

### 5C. C Extension audit

These need special attention for Nuitka cross-compilation:
- `sqlite_vec` — .dylib, architecture-specific
- `numpy` — compiled C/Fortran
- `aiosqlite` — wraps sqlite3 (stdlib), should be fine
- Any torch dependencies — if imported anywhere

---

## Phase 6: Configuration Audit

### 6A. How does the engine load config?

Trace the config loading path:
- Where does it look for `.env`?
- Where does it look for `config.yaml` or equivalent?
- What environment variables does it expect?
- What happens if `.env` is missing? (Tarcila won't have one)

### 6B. LLM provider configuration

Tarcila can use any LLM provider she wants — the engine now has a Settings panel for provider configuration. Verify:
- The Settings UI (`src/luna/services/settings/`) allows switching providers at runtime
- `config/fallback_chain.yaml` — does the fallback chain degrade gracefully when only one provider key is set?
- The engine boots cleanly with zero API keys configured (first-run state)
- Provider selection persists across restarts
- What error/UX does the user see if no provider key is configured at all?

---

## Phase 7: Security & IP Audit

### 7A. Verify no secrets in committed files

```bash
grep -rn "sk-" config/ --include="*.json" --include="*.yaml"
grep -rn "gsk_" config/ --include="*.json" --include="*.yaml"
grep -rn "api_key" config/ --include="*.json" --include="*.yaml"
```

### 7B. Verify Ahab's personal data doesn't leak

Check that none of these reference personal data that would ship:
- `config/directives_seed.yaml` — should be generic, not Ahab-specific
- `config/personality.json` — should be base Luna personality
- `src/luna/voice/data/corpus.json` — check for personal content

---

## Deliverable

Produce a single markdown report: `AUDIT_Nuitka_Readiness.md`

Structure:
1. **Summary** — GO / NO-GO with blocking issues listed
2. **Import Chain** — all issues found with severity
3. **Test Results** — pass/fail counts, broken tests
4. **Data Files** — inventory with SHIP/EXCLUDE/MISSING status
5. **Entry Point** — run_luna.py test results
6. **Dependency Gaps** — missing from pyproject.toml or Nuitka command
7. **Config Audit** — how config loads, what Tarcila needs
8. **Security** — any leaked secrets or personal data
9. **Recommended Fixes** — prioritized list of what to fix before building

Place the report at:
```
/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/Docs/AUDIT_Nuitka_Readiness.md
```

---

## Scope Rules

- **READ everything, MODIFY nothing** — this is an audit, not a fix session
- Exception: creating `run_luna.py` (Phase 4A) and the final report
- Do NOT run the full engine in a way that modifies `luna_engine.db` — use temp databases
- Do NOT install new packages
- If a test requires the engine running, note it as SKIPPED with reason
- Be thorough but don't rabbit-hole — if a module is deeply broken, note it and move on
