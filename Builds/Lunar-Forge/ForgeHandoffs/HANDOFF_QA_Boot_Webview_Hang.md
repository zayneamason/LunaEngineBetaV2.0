# HANDOFF — QA Boot Test Webview Hang Fix

**Date:** 2026-03-15
**Status:** Fixed
**Files modified:** `Builds/Lunar-Forge/core.py`

---

## Problem

Post-build QA always reports "Engine failed to boot within 30s" even though the binary compiled successfully. The binary hangs silently after printing `tiktoken not available, using fallback token counting (len/4)`.

## Root Cause

`run_luna.py` (the compiled entry point) decides between two boot modes:

- **Sidecar mode** (line 80): `LUNA_PORT` env var is set → runs uvicorn directly, headless
- **Standalone mode** (line 82-99): no `LUNA_PORT` → starts uvicorn in a thread, then tries `webview.create_window()` to open a native macOS window

The QA test in `core.py` passed `--server --port 8299` as **CLI args**, but `run_luna.py` doesn't parse CLI args — it only reads `LUNA_PORT` from the environment. Without that env var, the binary entered standalone mode and called `webview.create_window()`, which hangs in a headless subprocess context (no display, no event loop).

## Fix Applied

Added `env["LUNA_PORT"] = str(port)` to the QA boot environment in `core.py:1188`. This forces the binary into sidecar mode where it runs uvicorn directly without trying to create a webview window.

```python
# Before (broken):
env["LUNA_VOICE_ENABLED"] = "0"
# LUNA_PORT not set → binary tries webview → hangs

# After (fixed):
env["LUNA_VOICE_ENABLED"] = "0"
env["LUNA_PORT"] = str(port)  # sidecar mode, no webview
```

## Verification

1. Run a build from the Forge UI
2. Post-build QA should now show ENGINE BOOT: OK
3. Test prompt "Hello Luna, confirm you are operational." should get a response (if LLM keys are configured)

## Related Issue

`run_luna.py` ignores all CLI args (`--server`, `--port`, `--host`). The entry point only uses env vars (`LUNA_PORT`, `LUNA_BASE_DIR`, `LUNA_DATA_DIR`). The `--server --port 8299 --host 127.0.0.1` args passed by the QA test are silently dropped. This isn't a problem now that `LUNA_PORT` is set, but could confuse future debugging. Consider adding `argparse` to `run_luna.py` for parity with `scripts/run.py`.
