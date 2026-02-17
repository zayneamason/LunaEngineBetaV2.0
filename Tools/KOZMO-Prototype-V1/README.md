# KOZMO Prototype V1

AI filmmaking platform. CODEX (world bible) + LAB (production studio).

## Architecture

See: `../../Docs/ARCHITECTURE_KOZMO.md`

That document is the single source of truth for KOZMO's system design —
project layer, entity schemas, agent architecture, camera system, API
endpoints, and build phases. Read it before touching anything here.

## What This Is

A standalone-capable React app currently hosted inside Eclissi (the Luna
Engine frontend). KOZMO talks to the Luna Engine backend (FastAPI on :8000)
for project data, Eden operations, and Luna intelligence.

## Quick Start

```bash
cd Tools/KOZMO-Prototype-V1
npm install
npm run dev
# → http://localhost:5174
```

Requires Luna Engine backend running on :8000 for any API calls.
UI renders without the backend — you just won't have data.

## Structure

```
src/
├── main.jsx              Entry point (standalone or Eclissi-embedded)
├── App.jsx               Root — CODEX/LAB mode switching
├── KozmoProvider.jsx     React context (project, agents, connection)
│
├── codex/                KOZMO CODEX — World Bible
│   └── KozmoCodex.jsx   3-panel: file tree | entity card | agent panel
│
├── lab/                  KOZMO LAB — Production Studio
│   └── KozmoLab.jsx     3-panel + timeline: shots | canvas | controls
│
├── shared/               Components shared across modes
│   └── index.js          (stubs — extract from mode roots as patterns form)
│
├── hooks/                API integration
│   ├── useKozmoProject.js    Project + entity CRUD
│   ├── useEdenAdapter.js     Eden generation via Luna backend
│   ├── useAgentDispatch.js   Agent task queue lifecycle
│   └── useLunaAPI.js         Luna Engine health + messages
│
└── config/
    └── cameras.js        Camera bodies, lenses, film stocks, movements
```

## Eclissi Integration

KOZMO has no hard dependency on Eclissi. The coupling point is
`KozmoProvider.jsx` — it wraps everything KOZMO needs.

**Standalone:** `main.jsx` renders `<KozmoApp />` as root.
**Eclissi-hosted:** Eclissi imports `<KozmoApp />` as a route/page.

## Dev Ports

| Service        | Port  |
|----------------|-------|
| Luna Engine    | 8000  |
| Eclissi        | 5173  |
| KOZMO (standalone) | 5174 |

## Key Decisions

- **YAML source of truth** — project data lives as `.yaml` files, git-tracked
- **Project isolation** — separate graph DB per project, never in Luna's memory
- **Camera via prompt enrichment** — camera metadata → text appended to Eden prompts
- **Standalone-capable** — can extract from Eclissi with zero refactoring
- **Chat over forms** — agent dispatch flows through natural language
