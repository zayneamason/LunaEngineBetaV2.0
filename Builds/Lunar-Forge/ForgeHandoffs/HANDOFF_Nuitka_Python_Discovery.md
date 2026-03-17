# HANDOFF — Nuitka Python Discovery Fix

**Date:** 2026-03-15
**Status:** Applied — needs verification on next build
**Files modified:** `Builds/Lunar-Forge/core.py`

---

## Problem

Nuitka compilation fails with `No module named nuitka` when the Forge server is launched with a Python interpreter that doesn't have Nuitka installed.

`core.py` line 783 used `sys.executable` to invoke Nuitka:
```python
cmd = [sys.executable, "-m", "nuitka", ...]
```

On this machine, Homebrew installed Python 3.14 at `/opt/homebrew/opt/python@3.14/bin/python3.14`. If the Forge server is started via that interpreter (e.g. by a shell alias or PATH ordering), `sys.executable` resolves to 3.14 — but Nuitka is only installed on Python 3.12 at `/Library/Frameworks/Python.framework/Versions/3.12/bin/python3`.

### Evidence

**Failed build** (2026-03-15 12:31):
```
Command: /opt/homebrew/opt/python@3.14/bin/python3.14 -m nuitka --mode=app ...
/opt/homebrew/opt/python@3.14/bin/python3.14: No module named nuitka
```

**Successful build** (2026-03-15 06:41):
```
Command: /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 -m nuitka --mode=app ...
Nuitka-Options: Used command line options: ...
```

Same `core.py`, same profile — only difference was which Python started `serve.py`.

## Fix Applied

Added `BuildPipeline._find_nuitka_python()` method that probes multiple Python interpreters to find one with Nuitka installed:

1. Tries `sys.executable` first (current interpreter)
2. Falls back to `python3.12`, `python3.11`, `python3.13`, `python3` (in that order)
3. Runs `python -m nuitka --version` on each candidate
4. Returns the first one that succeeds
5. Logs which interpreter and Nuitka version was found
6. Returns `None` if no interpreter has Nuitka → compilation aborts with a clear error message

`compile_nuitka()` now calls `_find_nuitka_python()` instead of blindly using `sys.executable`.

## Workaround (if fix doesn't cover edge cases)

Start the Forge server explicitly with the Python that has Nuitka:

```bash
python3.12 serve.py
```

## Verification

1. Start Forge with Python 3.14: `python3.14 serve.py`
2. Trigger a build from the UI
3. Check build log — should show: `Found Nuitka (4.0.5) on /Library/.../python3`
4. Build should proceed past the Nuitka stage

## Future Consideration

The Forge profile YAML could support a `nuitka.python` key to pin the interpreter:
```yaml
nuitka:
  python: /Library/Frameworks/Python.framework/Versions/3.12/bin/python3
  exclude_packages: [torch, ...]
```

This wasn't implemented — the auto-discovery is sufficient for now.
