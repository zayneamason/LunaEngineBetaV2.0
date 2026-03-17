# HANDOFF: Lunar Forge React Frontend

## What Was Done (2026-03-15)

### Luna.app Production Build — COMPLETE
- Tauri shell bundles engine via `bundle.resources` → `Contents/Resources/engine/`
- `main.rs` has chmod fix for Tauri permission stripping + corrected `LUNA_BASE_DIR`
- Post-build `scripts/fix-permissions.sh` for belt-and-suspenders
- Stale `src-tauri/binaries/` (362MB) removed
- Symlink: `src-tauri/engine/` → `Lunar-Forge/output/luna-only-macos-arm64-0.1.0/`
- Luna.app launches, engine boots, Director connects, Luna responds

### Issues Found During First Launch
1. **schema.sql path mismatch** — Engine looked for `data/schema.sql`, Forge puts it at `data/user/schema.sql`. Fixed in source (`substrate/database.py` — added `data/user/` candidate) and copied file in current build.
2. **Dataroom leak in FALLBACK_PERSONALITY** — `director.py:156-159` had hardcoded "investor data room" capabilities text. Removed from source. Needs rebuild to take effect in binary.
3. **Owner name saved as "hello"** — Welcome Wizard saved first attempt before user corrected. Fixed manually in `~/Library/Application Support/Luna/config/`. The wizard UX worked but the error display confused the user into thinking it failed.
4. **API keys missing on first launch** — Expected. Forge builds ship with empty `secrets.json`. Keys injected from dev `.env` into user data dir.

### Source Fixes Made (need Forge rebuild)
- `src/luna/substrate/database.py` — added `data/user/schema.sql` path candidate
- `src/luna/actors/director.py` — removed dataroom capabilities from FALLBACK_PERSONALITY

### Data Boundary Audit
Full audit at `Docs/AUDIT_data_system_boundaries.md` — 514 lines covering every file, table, and config. Key findings:
- Forge `luna-only` profile produces clean builds (seed mode, poison term scan)
- FALLBACK_PERSONALITY was the main code-level leak (now fixed)
- Fresh installs work but have minor UX issues (low-memory warning, entity seed loading bug)

---

## What's Next: Forge React Frontend

### Goal
Replace the CLI (`python build.py --profile luna-only`) and TUI (`python -m Lunar-Forge`) with a React web UI for managing builds.

### Backend Already Has
- **`core.py` BuildPipeline class** (1259 lines) — 9-step pipeline with `on_progress` callback that emits `(message, pct)` tuples
- **`build.py` CLI** — `cmd_build()`, `cmd_preview()`, `cmd_list_profiles()` already parse profiles and invoke pipeline
- **Profile system** — YAML profiles in `profiles/` (luna-only, tarcila, rosa-demo, dev-test)
- **Build reports** — `BUILD_REPORT.md` generated in output dir with stats
- **Data leak verification** — 6-point check in `verify_clean_build()`

### Architecture Suggestion
```
Lunar-Forge/
├── frontend/           ← NEW React app (Vite)
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── ProfileSelector.jsx
│   │   │   ├── BuildProgress.jsx
│   │   │   ├── BuildReport.jsx
│   │   │   ├── OutputManager.jsx
│   │   │   └── ConfigPreview.jsx
│   │   └── hooks/
│   │       └── useBuild.js
│   └── package.json
├── serve.py            ← NEW FastAPI server wrapping core.py
├── build.py            (existing CLI)
├── core.py             (existing pipeline)
├── tui/                (existing TUI)
└── profiles/           (existing)
```

### Frontend Features
1. **Profile selector** — List profiles with metadata (name, db mode, collection count), select one
2. **Config preview** — Dry-run view showing what will be built (reuse `cmd_preview()` logic)
3. **Build trigger** — Start build button, streams progress via SSE/WebSocket
4. **Live progress** — 9-step progress bar with current step name and percentage
5. **Build report** — Display BUILD_REPORT.md contents after completion, highlight verification results
6. **Output manager** — List past builds in `output/`, show sizes, allow deletion

### Backend API (`serve.py`)
```
GET  /api/profiles              → list available profiles
GET  /api/profiles/:name        → preview (dry-run) for a profile
POST /api/build                 → start build (returns build ID)
GET  /api/build/:id/progress    → SSE stream of (message, pct) events
GET  /api/build/:id/report      → build report after completion
GET  /api/outputs               → list output directories with sizes
DELETE /api/outputs/:name       → delete an output
```

Progress streaming: The `on_progress` callback in `BuildPipeline.build()` currently prints to stdout. Wrap it to push events into an `asyncio.Queue`, serve that queue as SSE on `/api/build/:id/progress`.

### Key Files to Read
| File | What | Lines |
|------|------|-------|
| `core.py` | BuildPipeline, 9-step pipeline, verify_clean_build | All (1259) |
| `build.py` | CLI entry, cmd_build/cmd_preview/cmd_list_profiles | All (178) |
| `profiles/luna-only.yaml` | Example profile structure | All |
| `tui/app.py` | Existing TUI (Textual) — reference for UI flow | — |

### Constraints
- Frontend served from `Lunar-Forge/frontend/dist/` by `serve.py`
- `serve.py` runs on a different port than Luna Engine (suggest `:8200`)
- Build runs in a background thread (Nuitka takes ~38 min)
- Only one build at a time (mutex on BuildPipeline)
- Don't modify `core.py` internals — wrap with API layer

### Launch
```bash
cd Builds/Lunar-Forge
python serve.py  # starts FastAPI on :8200, serves React frontend
```
