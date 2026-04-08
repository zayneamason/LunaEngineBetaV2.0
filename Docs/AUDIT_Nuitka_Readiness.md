# AUDIT: Nuitka Packaging Readiness — Luna Engine V2

**Date:** 2026-03-10
**Auditor:** Claude Code (automated)
**Verdict:** ❌ NO-GO — 4 blocking issues must be resolved before building

---

## 1. Summary

### Blocking Issues

| # | Issue | Phase | Fix Effort |
|---|-------|-------|-----------|
| 1 | **40+ `__file__` path references** will break under Nuitka — no centralized path resolution | P1C | Medium (new `luna.core.paths` module) |
| 2 | **15+ undeclared dependencies** missing from pyproject.toml / Nuitka command | P5A/B | Low (add to pyproject.toml + Nuitka flags) |
| 3 | **numpy & sqlite_vec** are "optional" but required for core function | P5A | Low (move to core deps) |
| 4 | **Hardcoded absolute path** `/Users/zayneamason/` in `config/aibrarian_registry.yaml` | P7B | Trivial |

### Non-Blocking Concerns

- Piper binary is x86_64-only (runs under Rosetta on Apple Silicon)
- 2 dynamic `importlib` sites for FaceID modules
- 19 failing tests (assertion mismatches from code evolution, not import errors)
- `config/identity_bypass.json` hardcodes "ahab" entity
- `config/directives_seed.yaml` has `authored_by: ahab` fields
- ~126 MB data payload (voice models + frontend + configs)

---

## 2. Import Chain (Phase 1)

### 1A. Top-Level Imports — All Pass

| Import | Status |
|--------|--------|
| `import luna` | ✓ OK |
| `import luna_mcp` | ✓ OK |
| `import voice` | ✓ OK |
| `import luna.api.server` | ✓ OK (tiktoken fallback warning) |
| `import luna.engine` | ✓ OK (tiktoken fallback warning) |

### 1B. Import Scan Results

**Used but NOT declared in pyproject.toml:**

| Package | Import Site | Style | Severity |
|---------|------------|-------|----------|
| `groq` | `llm/providers/groq_provider.py` | Lazy (try/except) | HIGH |
| `openai` | `substrate/embeddings.py` | Lazy | HIGH |
| `google-generativeai` | `llm/providers/gemini_provider.py` | Lazy | HIGH |
| `python-dotenv` | `api/server.py` | try/except | MEDIUM |
| `tiktoken` | `core/context.py` | try/except (fallback exists) | LOW |
| `sentence-transformers` | `substrate/aibrarian_engine.py`, `substrate/local_embeddings.py` | Conditional | MEDIUM |
| `websockets` | `api/server.py` | Top-level | MEDIUM |
| `sounddevice` | `voice/audio/capture.py` | Voice-only | LOW |
| `speech_recognition` | `voice/stt/apple.py` | Conditional | LOW |
| `sympy` | `skills/logic/skill.py`, `skills/math/skill.py` | Conditional | LOW |
| `markitdown` | `skills/reading/skill.py` | Conditional | LOW |
| `pypdf` | `skills/reading/skill.py` | Conditional | LOW |
| `persona_forge` | `luna_mcp/tools/forge.py` | sys.path hack | HIGH |
| `voight_kampff` | `api/server.py` | Conditional | LOW |
| `mcp` | `luna_mcp/server.py` | Direct | HIGH (if shipping MCP) |

**Optional but actually required for core function:**

| Package | Declared In | Used By | Verdict |
|---------|------------|---------|---------|
| `numpy` | `[memory]` optional | clustering, embeddings, voice, acknowledgment (6+ files) | **MUST be core** |
| `sqlite-vec` | `[memory]` optional | AiBrarian, embedding search | **MUST be core** |

**80+ conditional imports** across the codebase — well-defended with try/except fallbacks, but Nuitka's static tracer won't follow them. Each needs `--include-package` or `--include-module`.

### 1C. `__file__` Usage — 73 References

**CRITICAL**: 40+ sites use `Path(__file__).parent.parent...` chains to resolve paths to `config/`, `data/`, `models/`, `Tools/`, `scripts/`. Under Nuitka, `__file__` resolves differently and all of these will break.

**Highest-impact fix:** Create `luna.core.paths` module:
```python
# luna/core/paths.py
import sys, os
from pathlib import Path

def project_root() -> Path:
    if getattr(sys, 'frozen', False):  # Nuitka compiled
        return Path(sys.executable).parent
    return Path(__file__).resolve().parents[3]  # src/luna/core -> project root
```

Then replace all `Path(__file__).parents[N]` chains with `project_root()` calls.

**Pattern breakdown:**

| Target | Count | Risk |
|--------|-------|------|
| `config/` directory | ~15 | HIGH |
| `data/` directory (DB, JSON) | ~12 | HIGH |
| `scripts/` directory | 2 | HIGH |
| `Tools/FaceID/` | 3 | HIGH |
| Same-dir relative (schema, fixtures) | ~10 | MEDIUM |
| `frontend/dist/` | 3 | MEDIUM |

### Dynamic Imports (2 sites — HIGH risk)

1. **`actors/identity.py:184-190`** — `importlib.util.spec_from_file_location` loads FaceID modules from `Tools/FaceID/src/`
2. **`api/server.py:5924-5929`** — Same pattern for `faceid_database`

Nuitka cannot trace these. Must bundle `Tools/FaceID/src/` via `--include-data-dir` or refactor to static imports.

### sys.path Manipulation (3 sites)

1. `actors/identity.py:143-145` — inserts `Tools/FaceID/`
2. `engine.py:742` — inserts `scripts/` for migration seeds
3. `luna_mcp/tools/forge.py:21` — inserts `Tools/persona_forge/src/`

---

## 3. Test Results (Phase 2)

### 2A. Smoke Tests

Directory exists at `tests/smoke/` with 4 test files:
- `test_engine_boots.py` — engine lifecycle
- `test_chat_responds.py` — chat round-trip
- `test_memory_stores.py` — memory persistence
- `test_websocket_connects.py` — WebSocket/SSE

**Status:** NOT RUN — require a live engine loop. Mark as integration tests.

### 2B. Unit Test Results

| Metric | Count |
|--------|-------|
| Total collected | 1,932 |
| Runnable (unit + top-level) | 1,745 |
| **Passed** | **1,726** |
| **Failed** | **19** |
| **Skipped** | **13** |
| Integration/smoke (not run) | 174 |
| **Pass rate** | **98.9%** |

**19 Failures by root cause:**

| Cause | Count | Fix |
|-------|-------|-----|
| Skill detector returns `DetectionResult` object, tests compare to string | 9 | Update assertions to use `.skill` attribute |
| Librarian edge-case handling (method signature changed) | 3 | Update test expectations |
| Cache actor type mapping outdated | 1 | Update extraction type list |
| Assembler token budget exceeded (expects <800, actual 1601) | 1 | Adjust threshold or prompt |
| Memory confidence directive wording changed | 1 | Update substring match |
| Memory matrix search returns 0 results | 1 | Investigate seed data |
| Scribe extraction config defaults changed | 1 | Update default values |
| Eden skill `is_available()` returns True unexpectedly | 1 | Check availability logic |

**None of these failures indicate import or packaging issues.**

### 2C. Compile-List Package Imports — All Pass

All 13 packages (`luna`, `luna_mcp`, `voice`, `fastapi`, `uvicorn`, `pydantic`, `httpx`, `aiosqlite`, `networkx`, `yaml`, `anthropic`, `starlette`, `anyio`) import cleanly.

---

## 4. Data Files (Phase 3)

### 4A. Config Files

**SHIP (11 files):**

| File | Size |
|------|------|
| `directives_seed.yaml` | 1.6 KB |
| `fallback_chain.yaml` | 208 B |
| `personality.json` | 4.1 KB |
| `lunascript.yaml` | 1.7 KB |
| `skills.yaml` | 1.5 KB |
| `llm_providers.json` | 913 B |
| `local_inference.json` | 382 B |
| `luna.launch.json` | 1.3 KB |
| `aibrarian_registry.yaml` | 2.5 KB |
| `memory_economy_config.json` | 1.1 KB |
| `projects/` (directory, 4 files) | — |

**EXCLUDE (6 files — contain credentials):**
- `google_credentials.json`
- `google_token.json`
- `google_token_drive.json`
- `identity_bypass.json`
- `eden.json`
- `dataroom.json`

**MISSING:** `voice_config.yaml` not in `config/` — lives at `src/luna/voice/data/voice_config.yaml`

### 4B. Voice Data Files

| File | Size | Status |
|------|------|--------|
| `src/voice/piper_bin/piper/piper` | 3.1 MB | SHIP (x86_64 Mach-O — no arm64) |
| `src/voice/piper_models/en_US-amy-medium.onnx` | 60 MB | SHIP |
| `src/voice/piper_models/en_US-amy-medium.onnx.json` | 4.8 KB | SHIP |
| `src/voice/piper_models/en_US-lessac-medium.onnx` | 60 MB | SHIP |
| `src/voice/piper_models/en_US-lessac-medium.onnx.json` | 4.8 KB | SHIP |
| `src/luna/voice/data/corpus.json` | 5.4 KB | SHIP |
| `src/luna/voice/data/line_bank.json` | 7.7 KB | SHIP |
| `src/luna/voice/data/voice_config.yaml` | 462 B | SHIP |

**Warning:** Piper binary is x86_64-only. Runs under Rosetta 2 on Apple Silicon. Total voice payload: ~123 MB.

### 4C. Substrate Files

`src/luna/substrate/schema.sql` — 16 KB, validates cleanly. Creates 19 tables including FTS.

### 4D. Frontend Build

`frontend/dist/` exists and is complete:
- `index.html` (877 B)
- `assets/index-B3Uunx68.js` (1.3 MB)
- `assets/index-CsAAAqR3.css` (79 KB)
- 57 KaTeX font files (~850 KB)

**Total data payload: ~126 MB**

---

## 5. Entry Point (Phase 4)

**NOT CREATED** — per scope rules, this is the one file the auditor was authorized to create. The spec from the handoff doc is:

```python
# run_luna.py
"""Luna Engine entry point for compiled binary."""
import sys, os

if getattr(sys, 'frozen', False):
    os.chdir(os.path.dirname(sys.executable))

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import uvicorn
from luna.api.server import app

if __name__ == "__main__":
    uvicorn.run(app, host='127.0.0.1', port=8000)
```

**Note:** This entry point should use the `project_root()` helper once `luna.core.paths` exists, and should handle the Nuitka `__compiled__` attribute in addition to `sys.frozen`.

---

## 6. Dependency Gaps (Phase 5)

### Missing from Nuitka `--include-package`

**Current:** `luna, luna_mcp, voice, fastapi, uvicorn, pydantic, httpx, aiosqlite, networkx, yaml, anthropic, starlette, anyio`

**Must add:**

| Package | Priority | Reason |
|---------|----------|--------|
| `numpy` | CRITICAL | Core memory/clustering/voice |
| `sqlite_vec` | CRITICAL | Vector search (C extension + .dylib) |
| `rich` | HIGH | CLI console output |
| `prompt_toolkit` | HIGH | Interactive CLI |
| `groq` | HIGH | LLM provider (lazy import) |
| `openai` | HIGH | Embedding provider (lazy import) |
| `google.generativeai` | HIGH | LLM provider (lazy import) |
| `pydantic_core` | MEDIUM | Rust extension, internal to pydantic |
| `dotenv` | MEDIUM | .env loading |
| `httpcore` | MEDIUM | Internal dep of httpx |
| `h11` | MEDIUM | Internal dep of uvicorn |
| `certifi` | MEDIUM | TLS certs for httpx |
| `idna` | MEDIUM | Domain encoding for httpx |
| `sniffio` | LOW | Dep of anyio |
| `mcp` | HIGH (if shipping MCP) | MCP protocol |

### C Extension Special Handling

| Extension | Nuitka Action |
|-----------|--------------|
| `sqlite_vec` | `--include-package=sqlite_vec` + `--include-data-files` for the `.dylib` |
| `numpy` | `--include-package=numpy` (exclude `numpy.distutils` to save ~10 MB) |
| `pydantic_core` | `--include-package=pydantic_core` (Rust .so) |
| `mlx` / `mlx_lm` | EXCLUDE from initial build (200MB+, macOS-only, optional) |
| `torch` / `transformers` | NOT used — do not include |

---

## 7. Config Audit (Phase 6)

### How config loads

1. `.env` loaded via `load_dotenv()` at server startup (conditional on file existence)
2. `config/secrets.json` injected into `os.environ` during FastAPI lifespan (Settings panel persistence)
3. Individual subsystems load from `config/` via `Path(__file__)` relative paths

**If `.env` is missing:** Engine boots fine. Keys can come from `secrets.json` (Settings panel) or direct env vars.

**If no API keys at all:** Engine boots, but first inference request raises `AllProvidersFailedError`. Local inference (MLX + Qwen) still works without keys.

### Settings panel works for any LLM provider

- `POST /api/settings/llm` accepts provider config, API keys, fallback chain, model selection
- Changes persist to `config/llm_providers.json`, `config/fallback_chain.yaml`, `config/secrets.json`
- `/api/settings/llm/test` endpoint validates keys before committing
- Provider selection persists across restarts
- Fallback chain degrades gracefully — skips unavailable providers, uses first available

### Key environment variables

| Variable | Required? | Purpose |
|----------|-----------|---------|
| `ANTHROPIC_API_KEY` | For Claude | LLM inference |
| `GROQ_API_KEY` | For Groq | LLM inference |
| `GOOGLE_API_KEY` | For Gemini | LLM inference |
| `EDEN_API_KEY` | Optional | AI art generation |
| `TAVILY_API_KEY` | Optional | Web search |
| `LUNA_BASE_PATH` | Optional | Override project root |
| `LUNA_FACEID_ENABLED` | Optional | Enable FaceID |

---

## 8. Security (Phase 7)

### Secrets

- **`.env` contains live API keys** but is gitignored — NOT tracked
- **`config/secrets.json`** does not exist on disk (created by Settings panel on first use) — gitignored
- **`config/llm_providers.json`** contains only env var names, not actual keys — CLEAN
- **No secrets in git** — verified

### Personal Data Leaks

| File | Issue | Severity |
|------|-------|----------|
| `config/aibrarian_registry.yaml` | Hardcoded path `/Users/zayneamason/_HeyLuna_BETA/LUNA-DATAROOM` | **HIGH — will crash** |
| `config/identity_bypass.json` | Hardcoded `"entity_id": "ahab"` | HIGH — should be auto-generated |
| `config/directives_seed.yaml` | `authored_by: ahab` on all directives | LOW — cosmetic |
| `config/personality.json` | `"subtopic": "ahab_partnership"` in bootstrap | LOW — cosmetic |
| `config/projects/kinoni-ict-hub.yaml` | Real names (Ahab, Hai Dai, Tarcila) | MEDIUM — privacy |

`src/luna/voice/data/corpus.json` — CLEAN, no personal identifiers.

---

## 9. Recommended Fixes (Prioritized)

### P0 — Blockers (must fix before Nuitka build)

1. **Create `luna/core/paths.py`** — centralized `project_root()` with Nuitka-aware fallback. Replace all 40+ `Path(__file__).parents[N]` chains. This is the single highest-impact fix.

2. **Move `numpy` and `sqlite-vec` to core dependencies** in pyproject.toml. They are not optional.

3. **Add all used-but-undeclared packages** to pyproject.toml (groq, openai, google-generativeai, python-dotenv, websockets, at minimum).

4. **Fix hardcoded path** in `config/aibrarian_registry.yaml` — replace `/Users/zayneamason/...` with a relative path or env var.

### P1 — High Priority

5. **Expand Nuitka `--include-package` list** with all packages from Section 6.

6. **Add `--include-data-files` for `sqlite_vec` `.dylib`** — without this, all vector search breaks silently.

7. **Genericize `config/identity_bypass.json`** — replace "ahab" with a first-run registration flow or generic default.

8. **Bundle `Tools/FaceID/src/`** via `--include-data-dir` or refactor dynamic imports to static imports.

### P2 — Medium Priority

9. **Fix the 19 failing tests** — mostly assertion updates for evolved interfaces.

10. **Build arm64 Piper binary** or acquire a universal binary for Apple Silicon native support.

11. **Create `run_luna.py` entry point** using the `project_root()` helper.

12. **Remove personal references** from `config/directives_seed.yaml` and `config/projects/kinoni-ict-hub.yaml` before distribution.

### P3 — Low Priority

13. **Exclude `numpy.distutils`** from Nuitka build to save ~10 MB.

14. **Consider excluding MLX** from initial Nuitka build (200 MB+, macOS-only).

15. **Add `.nuitka-exclude` manifest** for the 6 credential files in `config/`.
