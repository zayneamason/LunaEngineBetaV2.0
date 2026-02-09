# HANDOFF: Memory Monitor Panel — Frontend Implementation

**Date:** 2026-02-08
**Author:** Architect (The Dude)
**For:** Claude Code execution agents
**Scope:** Remove Personality/Tuning tabs, add Memory Monitor panel
**Mode:** SURGICAL — exact changes specified, touch nothing else
**Backend changes:** NONE — all data comes from existing API endpoints
**Prototype:** The complete prototype JSX is embedded below in Appendix A.
It renders standalone with mock data. Convert to production per instructions.

---

## PROJECT ROOT

```
/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/
```

Frontend root: `frontend/src/`

---

## SUMMARY

Three changes:
1. **CREATE** `MemoryMonitorPanel.jsx` — new full-screen overlay panel
2. **MODIFY** `App.jsx` — remove Personality/Tuning, add Memory button + panel
3. **MODIFY** `components/index.js` — add export for new panel

No files deleted. PersonalityMonitorPanel.jsx and TuningPanel.jsx stay on disk
(just disconnected from the render tree).

---

## CHANGE 1: Create `frontend/src/components/MemoryMonitorPanel.jsx`

Create this file based on the prototype (`memory_monitor_prototype.jsx`) with
these modifications for production use:

### Replace mock data with real API calls

The prototype uses `MOCK_*` constants. Replace with actual fetches:

```javascript
const API_BASE = 'http://localhost:8000';

const fetchAll = useCallback(async () => {
  setLoading(true);
  try {
    const [memRes, extRes, histRes, clusterRes] = await Promise.all([
      fetch(`${API_BASE}/memory/stats`),
      fetch(`${API_BASE}/extraction/stats`),
      fetch(`${API_BASE}/extraction/history?limit=10`),
      fetch(`${API_BASE}/clusters/stats`),
    ]);

    if (memRes.ok) setMemStats(await memRes.json());
    if (extRes.ok) setExtStats(await extRes.json());
    if (histRes.ok) setExtHistory(await histRes.json());
    if (clusterRes.ok) setClusterStats(await clusterRes.json());

    setError(null);
  } catch (e) {
    console.error('Memory Monitor fetch failed:', e);
    setError(e.message);
  } finally {
    setLoading(false);
    setLastRefresh(new Date());
  }
}, []);
```

### Remove the wrapper div / demo scaffolding

The prototype wraps everything in `min-h-screen bg-[#0a0a0f]` for standalone
rendering. In production, the panel is a modal overlay controlled by App.jsx.

Change the component signature to match the existing panel pattern:

```javascript
const MemoryMonitorPanel = ({ isOpen, onClose }) => {
  // ... all state and fetch logic ...

  useEffect(() => {
    if (!isOpen) return;
    fetchAll();
    const interval = setInterval(fetchAll, 15000);
    return () => clearInterval(interval);
  }, [isOpen, fetchAll]);

  if (!isOpen) return null;

  const issues = memStats && extStats ? diagnoseHealth(memStats, extStats) : [];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      {/* The rest of the panel content — same as prototype but without
          the standalone wrapper, isOpen toggle button, and overlay div */}
      <GlassCard className="w-full max-w-5xl max-h-[90vh] flex flex-col" padding="p-0" hover={false}>
        {/* Header — use onClose prop for the × button */}
        {/* Tabs */}
        {/* Content */}
      </GlassCard>
    </div>
  );
};

export default MemoryMonitorPanel;
```

### Import GlassCard

Add at top:
```javascript
import GlassCard from './GlassCard';
```

### Keep everything else from prototype

- `diagnoseHealth()` function — keep as-is
- All sub-components (`StatBox`, `SectionHeader`, `TypeDistributionBar`, etc.) — keep as-is
- All three tab views (`OverviewTab`, `ExtractionTab`, `ClustersTab`) — keep as-is
- Color configs (`severityConfig`, `stateConfig`, `typeColors`) — keep as-is
- `TABS` constant — keep as-is

### Error state

Add an error display matching other panels:

```javascript
if (error && !memStats) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <GlassCard className="w-full max-w-md" padding="p-6" hover={false}>
        <div className="text-white/30 text-sm text-center">
          Memory Monitor unavailable ({error})
        </div>
        <button
          onClick={onClose}
          className="mt-4 mx-auto block text-xs text-white/40 hover:text-white/60"
        >
          Close
        </button>
      </GlassCard>
    </div>
  );
}
```

---

## CHANGE 2: Modify `frontend/src/components/index.js`

### Add:
```javascript
export { default as MemoryMonitorPanel } from './MemoryMonitorPanel';
```

### Do NOT remove existing exports
PersonalityMonitorPanel and TuningPanel exports stay — other code may import them.

---

## CHANGE 3: Modify `frontend/src/App.jsx`

All changes are in this single file. Follow this exact sequence.

### 3A: Add import

**Find:**
```javascript
import {
  GlassCard,
  GradientOrb,
  StatusDot,
  ChatPanel,
  ConsciousnessMonitor,
  EngineStatus,
  ThoughtStream,
  ContextDebugPanel,
  ConversationCache,
  PersonalityMonitorPanel,
  TuningPanel,
  VoicePanel,
  LunaQAPanel,
  VoightKampffPanel,
} from './components';
```

**Replace with:**
```javascript
import {
  GlassCard,
  GradientOrb,
  StatusDot,
  ChatPanel,
  ConsciousnessMonitor,
  EngineStatus,
  ThoughtStream,
  ContextDebugPanel,
  ConversationCache,
  VoicePanel,
  LunaQAPanel,
  VoightKampffPanel,
  MemoryMonitorPanel,
} from './components';
```

Changes: Removed `PersonalityMonitorPanel` and `TuningPanel` imports,
added `MemoryMonitorPanel`.

### 3B: Replace state declarations

**Find:**
```javascript
  // Personality monitor state
  const [personalityMode, setPersonalityMode] = useState(false);
  // Tuning panel state
  const [tuningMode, setTuningMode] = useState(false);
```

**Replace with:**
```javascript
  // Memory monitor state
  const [memoryMode, setMemoryMode] = useState(false);
```

### 3C: Replace header buttons

**Find (the Tuning and Personality buttons — lines 242-267):**
```javascript
              {/* Tuning Toggle */}
              <button
                onClick={() => setTuningMode(!tuningMode)}
                className={`px-3 py-1.5 text-xs rounded-lg border transition-all ${
                  tuningMode
                    ? 'bg-amber-500/20 border-amber-500/50 text-amber-400'
                    : 'bg-white/5 border-white/10 text-white/40 hover:border-white/20'
                }`}
              >
                ⚙️ {tuningMode ? 'TUNING' : 'Tuning'}
              </button>

              {/* Personality Monitor Toggle */}
              <button
                onClick={() => setPersonalityMode(!personalityMode)}
                className={`px-3 py-1.5 text-xs rounded-lg border transition-all ${
                  personalityMode
                    ? 'bg-violet-500/20 border-violet-500/50 text-violet-400'
                    : 'bg-white/5 border-white/10 text-white/40 hover:border-white/20'
                }`}
              >
                🧬 {personalityMode ? 'PERSONALITY' : 'Personality'}
              </button>
```

**Replace with:**
```javascript
              {/* Memory Monitor Toggle */}
              <button
                onClick={() => setMemoryMode(!memoryMode)}
                className={`px-3 py-1.5 text-xs rounded-lg border transition-all ${
                  memoryMode
                    ? 'bg-cyan-500/20 border-cyan-500/50 text-cyan-400'
                    : 'bg-white/5 border-white/10 text-white/40 hover:border-white/20'
                }`}
              >
                🧠 {memoryMode ? 'MEMORY' : 'Memory'}
              </button>
```

### 3D: Replace panel renders

**Find (the Personality and Tuning panel renders — near end of file):**
```javascript
        {/* Personality Monitor Panel */}
        <PersonalityMonitorPanel
          isOpen={personalityMode}
          onClose={() => setPersonalityMode(false)}
        />

        {/* Tuning Panel */}
        <TuningPanel
          isOpen={tuningMode}
          onClose={() => setTuningMode(false)}
        />
```

**Replace with:**
```javascript
        {/* Memory Monitor Panel */}
        <MemoryMonitorPanel
          isOpen={memoryMode}
          onClose={() => setMemoryMode(false)}
        />
```

---

## FINAL HEADER BUTTON ORDER

After changes, the header buttons left-to-right should be:

1. 🔬 QA (unchanged)
2. 🔬 VK (unchanged)
3. 🧠 Memory (NEW — replaces Tuning + Personality)
4. 🔍 Debug (unchanged)
5. Connection status dot (unchanged)

---

## API ENDPOINTS USED (all existing, no changes needed)

| Endpoint | Method | Returns |
|----------|--------|---------|
| `/memory/stats` | GET | `{total_nodes, nodes_by_type, nodes_by_lock_in, avg_lock_in, total_edges, ...}` |
| `/extraction/stats` | GET | `{scribe: {backend, extractions_count, ...}, librarian: {filings_count, ...}}` |
| `/extraction/history?limit=10` | GET | `{extractions: [{extraction_id, timestamp, objects, edges, ...}], total}` |
| `/clusters/stats` | GET | `{cluster_count, total_nodes, state_distribution, avg_lock_in, top_clusters}` |

---

## VERIFICATION CHECKLIST

- [ ] `MemoryMonitorPanel.jsx` created in `frontend/src/components/`
- [ ] `MemoryMonitorPanel` exported from `components/index.js`
- [ ] `App.jsx` imports `MemoryMonitorPanel` (not PersonalityMonitorPanel or TuningPanel)
- [ ] `App.jsx` has `memoryMode` state (not personalityMode or tuningMode)
- [ ] Header has 🧠 Memory button (no Tuning or Personality buttons)
- [ ] Memory panel renders with `isOpen={memoryMode}` and `onClose`
- [ ] PersonalityMonitorPanel and TuningPanel NOT in render tree
- [ ] PersonalityMonitorPanel.jsx and TuningPanel.jsx files still exist on disk (not deleted)
- [ ] `npm run build` succeeds with no errors
- [ ] Panel opens, shows 3 tabs (Overview, Extraction, Clusters)
- [ ] Overview tab shows diagnostic banner, stats grid, type distribution, pipeline flow, lock-in bar
- [ ] Extraction tab shows Scribe/Librarian stats and recent extraction feed
- [ ] Clusters tab shows state distribution bar, top clusters list, node lock-in
- [ ] Panel auto-refreshes every 15 seconds when open
- [ ] × button closes panel
- [ ] No console errors

---

## FILES

| File | Action | Changes |
|------|--------|---------|
| `frontend/src/components/MemoryMonitorPanel.jsx` | **CREATE** | Full panel based on prototype with real API calls |
| `frontend/src/components/index.js` | **MODIFY** | Add `MemoryMonitorPanel` export |
| `frontend/src/App.jsx` | **MODIFY** | Remove Personality/Tuning, add Memory |
| `frontend/src/components/PersonalityMonitorPanel.jsx` | NO CHANGE | Stays on disk, just not imported |
| `frontend/src/components/TuningPanel.jsx` | NO CHANGE | Stays on disk, just not imported |

---

**End of handoff.**

---

## APPENDIX A: Prototype Location

The complete prototype is available as a rendered React artifact at:
`Docs/memory_monitor_prototype.jsx`

It is 826 lines of standalone React with mock data. The implementing agent
should use this as the base for `MemoryMonitorPanel.jsx`, applying the
modifications described in Change 1 above:
- Replace mock data constants with real `fetch()` calls to the 4 API endpoints
- Change component signature to `({ isOpen, onClose })`
- Import and use `GlassCard` component
- Remove standalone wrapper div (`min-h-screen bg-[#0a0a0f]`)
- Remove the `isOpen` toggle button (App.jsx handles this)
- Add error state display

The prototype contains all sub-components, health diagnostics logic,
color configs, and tab views that should be kept as-is.
