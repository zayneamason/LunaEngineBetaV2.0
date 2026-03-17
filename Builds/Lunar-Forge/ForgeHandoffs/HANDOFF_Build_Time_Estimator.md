# HANDOFF — Build Time Estimator

**Date:** 2026-03-15
**Status:** Not yet implemented
**Modifies:** `Builds/Lunar-Forge/serve.py`, `Builds/Lunar-Forge/frontend/src/components/BuildEstimator.jsx`

---

## Problem

Builds take 20-60+ minutes depending on configuration. There's no feedback before clicking "Start Build" to tell you how long it will take. You click build, wait an hour, and only then find out the scope was larger than expected.

## Goal

Show an estimated build time in the BuildEstimator sticky bar (already implemented in the Intelligence Layer) before the user clicks Build. The estimate updates live as toggles change.

## Estimation Model

Build time is dominated by Nuitka compilation, which scales with the number of Python modules being compiled to C. The model is simple: base time + per-package time for each included package category.

### Time Components (M1/M2 Apple Silicon benchmarks)

| Component | Estimated Time | Notes |
|---|---|---|
| **Base** (staging + config + data + secrets + frontend build) | ~2 min | Mostly `npm run build` for frontend |
| **Nuitka core** (luna package + stdlib) | ~15 min | The minimum Nuitka compile |
| **onnxruntime** | +8 min | Large native extension |
| **pyobjc (Foundation/AppKit)** | +5 min | macOS framework bindings, required for `--mode=app` |
| **sympy** (if not excluded) | +10 min | ~600 modules, massive compile |
| **scipy** (if not excluded) | +8 min | Large numerical library |
| **networkx** | +3 min | Graph library, many submodules |
| **pydantic** | +3 min | Validation framework |
| **Each additional `include-package`** | +1-3 min | Depends on package size |
| **Post-Nuitka** (QA, output move) | ~1 min | Fast |
| **First build penalty** | +5-10 min | No C compiler cache yet |

### Estimation Formula

```
estimate_minutes = 2                           # base (staging, config, frontend)
                 + 15                          # nuitka core
                 + 8                           # onnxruntime (always included)
                 + (5 if macos else 0)         # pyobjc
                 + (10 if sympy_included)      # sympy
                 + (8 if scipy_included)       # scipy
                 + 1                           # post-process + QA
                 + (8 if first_build else 0)   # no cache penalty
```

Where `sympy_included` / `scipy_included` = NOT in the profile's `exclude_packages` list.

`first_build` = no `.nuitka_cache` directory exists in staging or engine root.

### Cache Detection

Nuitka caches compiled C objects. After the first build, subsequent builds reuse the cache and are ~40% faster. The estimator should check:
```python
has_cache = (ENGINE_ROOT / "run_luna.build").exists()
```

## Implementation

### 1. Backend: New endpoint

**`GET /api/build/estimate`** in `serve.py`

Accepts query params matching the current config state (or reads from the most recent profile preview). Returns:

```json
{
  "estimated_minutes": 31,
  "breakdown": {
    "base": 2,
    "nuitka_core": 15,
    "onnxruntime": 8,
    "pyobjc": 5,
    "sympy": 0,
    "scipy": 0,
    "post_process": 1,
    "cache_penalty": 0
  },
  "has_cache": true,
  "platform": "macos-arm64",
  "excluded_packages": ["torch", "sympy", "scipy", "..."]
}
```

Logic:
- Read the profile's `exclude_packages` list
- Check known heavy packages against the exclusion list
- Check if Nuitka cache exists
- Sum up the time components
- Return estimate + breakdown

### 2. Backend: Historical calibration

After each successful build, record the actual duration and package set:

```python
# In _merge_overrides or post-build:
history_file = FORGE_ROOT / "logs" / "build_times.json"
```

Format:
```json
[
  {
    "profile": "dev-test",
    "duration_seconds": 1847,
    "excluded_packages": ["torch", "scipy"],
    "platform": "macos-arm64",
    "has_cache": false,
    "timestamp": "2026-03-15T12:31:00"
  }
]
```

If history exists, use the average of similar builds (same platform, similar exclusion set) instead of the static model. Fall back to the static model when no history matches.

### 3. Frontend: Display in BuildEstimator

Modify `BuildEstimator.jsx` to fetch the estimate and display it:

```
~31 min est. | 120 MB | 4 pages | 8 widgets
```

- Fetch `/api/build/estimate?profile={name}` when the component mounts and when exclusion list changes
- Show the time in minutes, rounded
- Color code: green (<20 min), yellow (20-40 min), red (>40 min)
- Tooltip or expandable breakdown showing where the time goes

### 4. Frontend: Breakdown tooltip

On hover or click of the time estimate, show the component breakdown:

```
Build Time Breakdown
  Base (staging, config, frontend)    2 min
  Nuitka core (luna + stdlib)        15 min
  onnxruntime                         8 min
  pyobjc (macOS frameworks)           5 min
  Post-processing + QA                1 min
  ────────────────────────────────────
  Total                             ~31 min

  Tip: Add 'sympy' to exclusions to save ~10 min
```

The "Tip" line should appear when a known heavy package (sympy, scipy) is NOT in the exclusion list, suggesting the user add it.

## Constraints

- Estimates are rough — ±30% accuracy is fine. The goal is order-of-magnitude feedback ("5 min" vs "45 min"), not precision.
- Do NOT block or delay the build. The estimate is informational only.
- Historical calibration is optional for v1 — the static model is good enough to start.
- The estimator should work even if no builds have ever been run (static model fallback).

## Success Criteria

1. BuildEstimator shows a time estimate before clicking Build
2. Estimate changes when exclusion list is modified (adding sympy drops ~10 min)
3. First build shows higher estimate than subsequent builds (cache penalty)
4. After a build completes, the next estimate is closer to actual (if historical calibration is implemented)
5. Heavy package warning tips appear when sympy/scipy are not excluded
