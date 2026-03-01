# ◈ Luna Engine — Pipeline Diagnostic

Interactive node-graph diagnostic tool for the Luna Engine pipeline.
Built with React Flow + Vite.

## Quick Start

```bash
cd luna-diagnostic
npm install
npm run dev
```

Opens at `http://localhost:5173`

## What It Shows

Full Luna Engine architecture as a draggable node graph:

- **33 nodes** — every actor, ring, guard, input/output path
- **41+ edges** — animated blue = data flow, animated red = broken pipe
- **Click any node** → detail panel with description, source file, status, connections
- **Drag nodes** to rearrange the layout
- **Minimap** for orientation
- **Snap-to-grid** for clean alignment

### Color Legend

| Color | Type |
|-------|------|
| Cyan | Input (Voice, Text, FaceID) |
| Indigo | Process (Tick, Dispatch, Router, Director) |
| Green | Memory (Matrix DB, Dataroom, Scribe, Librarian) |
| Purple | Guard (Scout, Overdrive, Watchdog, Reconcile) |
| Pink | Context (Revolving Context, Rings) |
| Yellow | Output (TTS, Text Response) |
| **Red** | **BROKEN** (Memory Retrieval, Matrix Actor, MIDDLE/OUTER rings) |

### The Break

The red nodes and edges tell the story:

```
dispatch → mem_retrieval → matrix_actor.get_context() → RETURNS EMPTY
                        → context.add(MEMORY) NEVER FIRES
                        → MIDDLE ring: 0 items, OUTER ring: 0 items
                        → Director has no memory → confabulates or surrenders
```

Meanwhile, Dataroom (direct SQL) and History (conversation turns) work fine.

## Project Structure

```
src/
  App.jsx           — Main React Flow canvas + layout
  EngineNode.jsx    — Custom node component (status dots, type colors)
  AnimatedEdge.jsx  — Custom edge with animated particles
  DetailPanel.jsx   — Slide-out detail panel on node click
  data.js           — All node/edge definitions, styles, legend
  index.css         — Global styles + React Flow overrides
  main.jsx          — React entry point
```

## Live Data (Future)

The Vite proxy is pre-configured to forward `/api/*` to `localhost:8000`.
To add live status polling:

```javascript
// In App.jsx, add:
useEffect(() => {
  const poll = setInterval(async () => {
    const res = await fetch('/api/debug/context');
    const data = await res.json();
    // Update node statuses based on live data
  }, 2000);
  return () => clearInterval(poll);
}, []);
```

## Stack

- **React 18** + **Vite 6**
- **@xyflow/react** (React Flow v12) — MIT license, free forever
- **JetBrains Mono** — monospace font
