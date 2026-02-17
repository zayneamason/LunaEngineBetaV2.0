# KOZMO Handoff — 2026-02-13

## For: Claude Code (implementation)

## Contents

| File | What |
|------|------|
| `HANDOFF_KOZMO_BUILD.md` | Complete build specification — Phases 1-9, all models, services, endpoints, tests |
| `scribo_overlay.jsx` | Phase 7 prototype — annotation overlay with anchor points, gutter pins, action plan sidebar |
| `lab_pipeline.jsx` | Phase 8 prototype — production queue, shot builder with camera rig, sequence storyboard |
| `codex_production_board.jsx` | Phase 9 prototype — master planning view, grouped briefs, AI chat, dependencies |

## Current State

- **Phase 1 backend:** ✅ COMPLETE (179 tests, 16 routes, 7 modules)
- **Phase 6 SCRIBO:** Design complete, prototype built (previous session)
- **Phases 7-9:** Design complete, prototypes built (this session)

## Build Order

```
Phase 6 (SCRIBO base)     → types, parser, service, routes, tests
Phase 7 (Overlay)         → overlay service, sidecar files, annotation CRUD
Phase 8 (LAB Pipeline)    → brief models, camera registry, prompt builder, queue
Phase 9 (CODEX Board)     → thin aggregation layer over LAB briefs
```

Build each phase same pattern as Phase 1: types → service → routes, tests alongside.

## New Files to Create

### Phase 7
- `src/luna/services/kozmo/overlay.py`
- `tests/test_kozmo_overlay.py`

### Phase 8
- `src/luna/services/kozmo/lab_pipeline.py`
- `src/luna/services/kozmo/camera_registry.py`
- `tests/test_kozmo_lab.py`

### Phase 9
- `src/luna/services/kozmo/production_board.py`
- `tests/test_kozmo_board.py`

## Files to Modify
- `src/luna/services/kozmo/types.py` — add Overlay + LAB Pipeline models
- `src/luna/services/kozmo/routes.py` — add ~29 new endpoints
- `src/luna/services/kozmo/project.py` — add `lab/` to project scaffolding

## Key Data Flow

```
SCRIBO overlay annotation
    → "push to LAB"
    → creates ProductionBrief (carries source text, entities, prompt)
    → lands in LAB queue (lab/briefs/*.yaml)
    → camera rigging (body/lens/focal/aperture/movement/post)
    → prompt enrichment (base + camera metadata as natural language)
    → Eden dispatch

CODEX Production Board reads LAB briefs as a planning view.
No separate storage — board is a view, not a store.
```

## Prototypes

The .jsx files are React artifacts. They render in Claude.ai's artifact viewer or any React sandbox. They contain mock data from the DWM project (The Dinosaur, The Wizard, and The Mother) showing realistic usage of all features. Use them as design targets — port the interaction patterns but use real API data.
