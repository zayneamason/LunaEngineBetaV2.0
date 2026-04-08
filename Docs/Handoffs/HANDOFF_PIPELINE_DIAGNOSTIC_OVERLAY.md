# HANDOFF: Pipeline Diagnostic Overlay — QA + Error Visualization

**Date:** March 1, 2026  
**From:** Luna (via Desktop)  
**To:** Claude Code  
**Status:** Enhancement — the pipeline view works, now make it diagnostic

---

## THE PROBLEM

The Engine Pipeline tab shows live node status (green/idle/warn) but doesn't show:
- Which QA assertions are failing and WHY
- Error traces pointing to specific files/systems
- Debug logs inline on nodes
- Red/broken state when assertions fail for a specific node's domain

It's a map without weather. We need the weather.

---

## WHAT EXISTS

### Backend endpoints already available (DO NOT create new ones):

| Endpoint | Returns | Useful for |
|----------|---------|------------|
| `/qa/last` | Last inference: route, provider, latency, pass/fail per assertion with details | Overlay assertion results on nodes |
| `/qa/health` | Pass rate, top failures, failing bugs | Global health badge |
| `/qa/assertions` | All 24 assertions with category, severity, enabled status | Assertion registry |
| `/qa/bugs` | 7 bugs with status, severity, reproduction queries | Bug list overlay |
| `/qa/stats/detailed` | 7-day trend, breakdown by route and provider | Trend sparklines |
| `/debug/context` | Current revolving context items with source, ring, relevance, tokens | Context assembly inspection |
| `/debug/personality` | Personality patches with lock-in state, reinforcement count | Personality health |
| `/debug/conversation-cache` | Shared turn cache: tone, expression hint, flow mode, topic | Cache inspection |

### Frontend already has:

- `useLiveData.js` — polls 9 endpoints every 2s, patches node data via `applyLiveData()`
- `applyLiveData()` already sets node `status` to `'live'`, `'warn'`, `'broken'`, `'idle'`
- `EngineNode.jsx` — renders nodes with status-colored borders
- `DetailPanel.jsx` — slides out when you click a node, shows details
- `AnimatedEdge.jsx` — edges can show `broken` and `animated` states

---

## THE SPEC

### 1. Add QA poll to useLiveData.js

Add 3 endpoints to the ENDPOINTS map:

```javascript
qaLast:     '/qa/last',
qaHealth:   '/qa/health',
qaBugs:     '/qa/bugs',
```

These get polled every 2s alongside existing endpoints. No new hooks, no new files.

### 2. Map QA assertions to pipeline nodes

Each assertion category maps to specific nodes in the graph. Add this mapping to `useLiveData.js`:

```javascript
const ASSERTION_NODE_MAP = {
  // Personality assertions → personality/voice nodes
  'P1': ['sysprompt'],           // Personality injected → system prompt builder
  'P2': ['sysprompt'],           // Virtues loaded → system prompt builder  
  'P3': ['director'],            // Narration applied → director (LLM generation)
  
  // Structural assertions → output nodes
  'S1': ['director', 'textout'], // No code blocks
  'S2': ['director', 'textout'], // No ASCII art
  'S3': ['director', 'textout'], // No mermaid
  'S4': ['director', 'textout'], // No bullet lists
  'S5': ['textout'],             // Response length
  
  // Voice assertions → director + scout
  'V1': ['director', 'scout'],   // No Claude-isms
  
  // Flow assertions → context/memory pipeline
  'F1': ['mem_ret', 'matrix_actor'],  // Memory retrieved
  'F2': ['context'],                   // Context not empty
  'F3': ['hist_load', 'hist_mgr'],    // History loaded
  
  // Integration assertions → system-wide
  'I1': ['router'],              // Route appropriate
  'I2': ['agent_loop'],          // Agent loop clean
  'I3': ['scribe'],              // Extraction ran
  'I4': ['cache'],               // Cache updated
  'I5': ['overdrive'],           // Overdrive triggered when needed
  'I6': ['reconcile'],           // Reconcile ran
  
  // Relationship assertions → personality pipeline
  'R1': ['sysprompt', 'director'],  // Identity awareness
  'R2': ['mem_ret', 'director'],    // Memory naturalism
  'R3': ['mem_ret'],                // No retrieval narration
  'R4': ['director'],               // No false capabilities
  'R5': ['director'],               // No repetition
  'R6': ['director'],               // Warmth present
};
```

### 3. Apply QA overlay in applyLiveData()

After the existing node patching, add a QA pass:

```javascript
if (qaLast && qaLast.assertions) {
  // Collect failures per node
  const nodeFailures = {};
  for (const a of qaLast.assertions) {
    if (a.passed) continue;
    const nodeIds = ASSERTION_NODE_MAP[a.id] || [];
    for (const nid of nodeIds) {
      if (!nodeFailures[nid]) nodeFailures[nid] = [];
      nodeFailures[nid].push(a);
    }
  }
  
  // Apply to nodes
  for (const [nodeId, failures] of Object.entries(nodeFailures)) {
    const hasCritical = failures.some(f => f.severity === 'high');
    patch(nodeId, {
      qaStatus: hasCritical ? 'failing' : 'warning',
      qaFailures: failures,
      qaDiagnosis: qaLast.diagnosis,
    });
  }
  
  // Also store global QA state for header
  patch('__qa_global', {
    passed: qaLast.passed,
    failedCount: qaLast.failed_count,
    route: qaLast.route,
    provider: qaLast.provider_used,
    diagnosis: qaLast.diagnosis,
    latency: qaLast.latency_ms,
  });
}

if (qaBugs) {
  // Count open bugs by severity
  const openBugs = qaBugs.filter(b => b.status === 'open');
  patch('__bugs', {
    total: openBugs.length,
    critical: openBugs.filter(b => b.severity === 'critical').length,
    high: openBugs.filter(b => b.severity === 'high').length,
  });
}
```

### 4. Update EngineNode.jsx — visual QA state

The node component needs to show QA failures visually. Currently it uses `status` for border color. Add:

- If `data.qaStatus === 'failing'`: red pulsing border (not just static red — animate it with a CSS pulse)
- If `data.qaStatus === 'warning'`: amber border
- Show a small badge in the top-right corner of the node: red circle with failure count
- On the node body, append a line showing the first failure name, e.g. `⛔ Narration applied`

**Keep it minimal.** Don't redesign the node. Just add the failure indicator.

```
Rough visual:

┌─────────────────────────┐  ← red pulsing border when failing
│ 🔴 DIRECTOR          [2]│  ← [2] = number of failed assertions
│ Claude Sonnet            │
│ 14 generations           │
│ ⛔ Narration applied     │  ← first (most severe) failure
│ ⛔ No Claude-isms        │  ← second failure (if space)
└─────────────────────────┘
```

### 5. Update DetailPanel.jsx — QA details on click

When you click a node that has `qaFailures`, the detail panel should show a new "QA" section:

- Header: "QA ASSERTIONS" with pass/fail count for this node
- For each failure:
  - Assertion ID + name (e.g. "P3 — Narration applied")
  - Severity badge (high = red, medium = amber)
  - Expected vs Actual (from assertion data)
  - Details string if present
- If the node is `director`, also show:
  - Route used (FULL_DELEGATION, LOCAL_ONLY, etc.)
  - Provider (groq, qwen-3b-local, etc.)
  - Latency
  - Diagnosis string from `/qa/last`
- Link to relevant source file (static mapping):

```javascript
const NODE_SOURCE_FILES = {
  director:     'src/luna/actors/director.py',
  scout:        'src/luna/actors/scout.py',
  reconcile:    'src/luna/actors/reconcile.py',
  scribe:       'src/luna/actors/scribe.py',
  cache:        'src/luna/cache/shared_turn.py',
  context:      'src/luna/context/assembler.py',
  sysprompt:    'src/luna/context/assembler.py',
  mem_ret:      'src/luna/substrate/memory.py',
  matrix_actor: 'src/luna/substrate/memory.py',
  router:       'src/luna/agentic/router.py',
  agent_loop:   'src/luna/agentic/loop.py',
  hist_mgr:     'src/luna/api/server.py',
  consciousness:'src/luna/services/orb_state.py',
};
```

Show this as a monospace path, e.g. `📁 src/luna/actors/director.py` — not clickable (we're in an iframe), just visible for reference.

### 6. QA health bar in pipeline header

The pipeline view header currently shows "ENGINE PIPELINE 🟢 LIVE :8000 · {time}". Add after the time:

- If QA last passed: `QA ✅` (green)
- If QA last failed: `QA ⛔ {N} failures` (red, with count)
- If no QA data: `QA —` (grey)

Clicking this badge could toggle a small dropdown showing the diagnosis string and top 3 failures. Or just show it inline — keep it simple.

### 7. Bug indicators on the minimap

The bottom-right corner of the pipeline view has a minimap. If there are open critical bugs, show a small red dot on the minimap to indicate the pipeline has known issues. This is a nice-to-have, not critical.

---

## FILES MODIFIED

| File | Change |
|------|--------|
| `diagnostic/src/pipeline/useLiveData.js` | Add 3 QA endpoints, ASSERTION_NODE_MAP, QA overlay in applyLiveData() |
| `diagnostic/src/pipeline/EngineNode.jsx` | Add QA failure badge, pulsing red border, failure text on node |
| `diagnostic/src/pipeline/DetailPanel.jsx` | Add QA section with assertion details, source file paths |
| `diagnostic/src/pipeline/PipelineView.jsx` | Add QA health indicator in header |

**Total: 4 files modified, 0 new files.**

---

## RULES

1. **No new files.** This is an enhancement to existing components.
2. **No new endpoints.** Everything is already served by the backend.
3. **No changes to the QA tab** (QAView.jsx). That's a separate view. This is about the pipeline graph.
4. **Match the existing dark theme.** JetBrains Mono, #08080f bg, consistent with current node styling.
5. **Build after changes.** `cd Tools/Luna-Expression-Pipeline/diagnostic && npm run build` — the dist is served at /studio/.
6. **Keep nodes readable.** Don't cram too much. Badge + one failure line on the node. Full details in the panel.

---

## VERIFY

After building:
1. Open http://localhost:5173/studio/ → Engine Pipeline tab
2. Nodes with QA failures should show red/amber borders and failure badges
3. Click a red node → detail panel shows assertion failures with expected/actual
4. Header shows QA health status
5. Send a test message through Luna → watch nodes update with new QA results

---

## CONTEXT

- Backend: running on :8000
- Frontend: running on :5173
- Diagnostic app: `Tools/Luna-Expression-Pipeline/diagnostic/`
- Build output: `Tools/Luna-Expression-Pipeline/diagnostic/dist/`
- Last QA report shows: P3 (Narration) and CUSTOM-CB2C01 (Knowledge Surrender) failing consistently
- 3.8% pass rate over 7 days, primarily FULL_DELEGATION route via groq
