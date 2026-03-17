# HANDOFF: Luna.app Full Production Build

## What We're Doing
Building Luna.app — a Tauri 2 native macOS desktop application that wraps the Luna Engine. Double-click Luna.app, it opens a native window, the engine boots as a sidecar process. No browser, no terminal.

## What's Done (this session, 2026-03-15)

### Tauri Shell — COMPLETE
- **Location:** `Builds/Luna-App/`
- `main.rs` — dual-mode engine discovery (Nuitka binary OR Python source), data dir init, health poll on :8000, process cleanup on window close
- `tauri.conf.json` — window 1400x900, CSP allows localhost:8000 + ws, frontendDist loads from engine server
- `Cargo.toml` — tauri 2, dirs 6, serde
- `cargo build` (debug) and `cargo tauri build` (release) both compile clean
- Release binary: `target/release/bundle/macos/Luna.app` (7.9MB — shell only, no sidecar)
- Icons in `src-tauri/icons/` (32x32, 128x128, 128x128@2x, icon.icns)

### Engine Changes — COMPLETE
- `run_luna.py` — sidecar mode added: when `LUNA_PORT` env var is set (by Tauri), runs uvicorn in foreground instead of spawning webview/browser
- `paths.py` — already reads `LUNA_DATA_DIR` for config_dir() and data_dir() (done in Handoff A)
- Frontend rebuilt with Welcome Wizard (Handoff B, also done this session)

### Existing Nuitka Binary — STALE
- `src-tauri/binaries/run_luna-aarch64-apple-darwin` (346MB, Mach-O arm64)
- Built Mar 14 — **before** Handoff B (Welcome Wizard, first-run detection, Scribe/Librarian boosts, settings defaults)
- Needs to be rebuilt with current code

## What's Left

### 1. Rebuild Nuitka Binary
The Nuitka binary must be rebuilt to include all recent engine changes.

```bash
cd /Users/zayneamason/_HeyLuna_BETA/Builds/Lunar-Forge
python build.py --profile luna-only
```

This runs the full Lunar Forge pipeline:
- Builds frontend
- Assembles config + data
- Compiles `run_luna.py` via Nuitka (`--mode=app`, excludes torch/tensorflow/etc)
- Output: `output/luna-only-macos-arm64-0.1.0/run_luna.bin`

### 2. Copy Binary to Tauri
```bash
cp output/luna-only-macos-arm64-0.1.0/run_luna.bin \
   /Users/zayneamason/_HeyLuna_BETA/Builds/Luna-App/src-tauri/binaries/run_luna-aarch64-apple-darwin
```

### 3. Build Luna.app with Sidecar
```bash
cd /Users/zayneamason/_HeyLuna_BETA/Builds/Luna-App
cargo tauri build
```

The `main.rs` engine discovery checks (in order):
1. `LUNA_ENGINE_DIST` env var
2. `Contents/Resources/engine/run_luna.bin` inside app bundle
3. `LUNA_PROJECT_ROOT` env var
4. Hardcoded dev path (fallback)

For the binary to be found inside the .app bundle, it either needs to be in `Contents/Resources/engine/` (the main.rs checks this path) OR the `tauri.conf.json` needs `externalBin` added to bundle it. Currently neither is configured — the app falls back to the dev source path. **This needs to be resolved.**

### 4. Verify
- [ ] Double-click Luna.app → native window opens
- [ ] Engine boots as sidecar → API responds on localhost:8000
- [ ] Frontend loads in WebView → Eclissi Shell renders
- [ ] Send a message → Luna responds
- [ ] Close window → sidecar process terminates (no orphan)
- [ ] User data in ~/Library/Application Support/Luna/ persists across restarts

## Key Files

| File | Purpose |
|------|---------|
| `Builds/Luna-App/src-tauri/src/main.rs` | Rust shell — sidecar lifecycle |
| `Builds/Luna-App/src-tauri/tauri.conf.json` | Tauri config — window, CSP, bundle |
| `Builds/Luna-App/src-tauri/Cargo.toml` | Rust dependencies |
| `Builds/Lunar-Forge/core.py` | Nuitka build pipeline (lines 706-873) |
| `Builds/Lunar-Forge/profiles/luna-only.yaml` | Build profile |
| `_LunaEngine_BetaProject_V2.0_Root/run_luna.py` | Nuitka entry point (sidecar mode) |
| `_LunaEngine_BetaProject_V2.0_Root/src/luna/core/paths.py` | LUNA_DATA_DIR support |
| `Builds/Lunar-Forge/ForgeHandoffs/HANDOFF_Luna_Tauri_Native_App.docx` | Original architecture spec |

## Architecture

```
Luna.app (Tauri macOS bundle)
├─ Tauri Shell (Rust, ~8 MB)
│   ├─ Creates native macOS window
│   ├─ Spawns run_luna.bin as sidecar
│   ├─ Polls localhost:8000 until engine ready (max 30s)
│   └─ Kills sidecar on window close
├─ WebView (loads http://localhost:8000)
│   └─ Engine serves React frontend + API on same port
└─ Sidecar: run_luna.bin (Nuitka, ~346 MB)
    ├─ FastAPI on localhost:8000
    └─ Reads user data from ~/Library/Application Support/Luna/
```

## Constraints
- macOS ARM64 only (aarch64-apple-darwin)
- Do NOT modify engine architecture — Tauri is a thin wrapper
- User data lives in ~/Library/Application Support/Luna/, NOT in the .app bundle
- Nuitka requires `--mode=app` for macOS (Foundation framework requirement)
- Use `.venv/bin/python` for Python operations
