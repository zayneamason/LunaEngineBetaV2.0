# HANDOFF: Fix QA Panel — Frontend Disconnected from Backend

## Problem

The QA panel in Lunar Studio (`localhost:5173` → Lunar Studio → QA tab) shows:
- **STATUS: OFFLINE**
- **PASS RATE: 0.0%**
- **ASSERTIONS: 0** ("No assertions configured")
- **OPEN BUGS: 0** ("No bugs tracked")

Meanwhile the backend (`localhost:8000`) has all 18 assertions configured, 6 tracked bugs, and the last 5 QA reports all passed clean (most recent: March 8, 10:52 AM). The engine is RUNNING with all 5 pipeline nodes active.

**This is a frontend data-fetching issue, not a backend issue.**

## Root Cause

The QA panel lives at:
```
Tools/Luna-Expression-Pipeline/diagnostic/src/qa/QAView.jsx
```

It fetches from these four endpoints on mount + 5s interval:
```javascript
const [h, last, a, b] = await Promise.all([
  safeFetch(`${API}/qa/health`),
  safeFetch(`${API}/qa/last`),
  safeFetch(`${API}/qa/assertions`),
  safeFetch(`${API}/qa/bugs`),
]);
```

Where `const API = '';` — an empty string, meaning it fetches relative to the frontend origin (`localhost:5173`).

The backend QA endpoints live on `localhost:8000`:
- `GET /qa/health` → returns `{ pass_rate, total_24h, failed_24h, failing_bugs, ... }`
- `GET /qa/last` → returns full last report with assertions array
- `GET /qa/assertions` → returns array of assertion objects (NOT wrapped in `{ assertions: [...] }`)
- `GET /qa/bugs` → returns array of bug objects (NOT wrapped in `{ bugs: [...] }`)

### Issues to investigate:

1. **API base URL**: `const API = '';` means requests go to `localhost:5173/qa/health` instead of `localhost:8000/qa/health`. Check if the Vite dev server proxies `/qa/*` to `:8000`. If not, that's the primary break.

2. **Response shape mismatch**: The frontend does:
   ```javascript
   setAssertions(a?.assertions || []);  // expects { assertions: [...] }
   setBugs(b?.bugs || []);              // expects { bugs: [...] }
   ```
   But the backend returns **bare arrays** from `/qa/assertions` and `/qa/bugs`, not wrapped objects. So even if the fetch succeeds, `a?.assertions` would be `undefined` → falls back to `[]`.

3. **Health status field**: Frontend reads `health?.status` but the backend `/qa/health` response (via MCP) returns `{ pass_rate, total_24h, failed_24h, failing_bugs, recent_failures, top_failures }` — no `status` field. The frontend defaults to `'offline'` when status is missing.

## Fix Scope

### Fix 1: Verify/add Vite proxy (if missing)
Check `Tools/Luna-Expression-Pipeline/diagnostic/vite.config.js` (or `.ts`) for a proxy rule forwarding `/qa/*` to `http://localhost:8000`. If absent, add:
```javascript
server: {
  proxy: {
    '/qa': 'http://localhost:8000',
  }
}
```

If a proxy already exists but uses a different prefix (e.g., `/api`), update `const API` in QAView.jsx to match.

### Fix 2: Fix response shape parsing
In `QAView.jsx`, change:
```javascript
// BEFORE (wrong — expects wrapper object)
setAssertions(a?.assertions || []);
setBugs(b?.bugs || []);

// AFTER (correct — backend returns bare arrays)
setAssertions(Array.isArray(a) ? a : a?.assertions || []);
setBugs(Array.isArray(b) ? b : b?.bugs || []);
```

### Fix 3: Derive status from pass_rate
The backend doesn't return a `status` string. Derive it:
```javascript
// BEFORE
const status = health?.status || 'offline';

// AFTER
const status = health
  ? (health.pass_rate >= 0.9 ? 'pass' : health.pass_rate >= 0.7 ? 'warn' : 'fail')
  : 'offline';
```

### Fix 4: Bug count filter
The frontend filters bugs by `status === 'open' || status === 'failing'`. Verify the backend bug objects use these exact status strings. The backend `qa_list_bugs` endpoint calls `validator._db.get_all_bugs()` — check the schema in `src/luna/qa/database.py` for the status field values.

## Files

| File | Role |
|------|------|
| `Tools/Luna-Expression-Pipeline/diagnostic/src/qa/QAView.jsx` | **Primary fix target** — the QA panel component |
| `Tools/Luna-Expression-Pipeline/diagnostic/vite.config.*` | Dev server proxy config — verify `/qa` proxy exists |
| `src/luna/api/server.py` | Backend QA endpoints (lines ~6930-7300) — reference only, don't modify |
| `src/luna/qa/database.py` | QA database schema — check bug status field values |
| `src/luna/qa/validator.py` | `get_health()` return shape — check if `status` field exists |

## Verification

After applying fixes:
1. `cd Tools/Luna-Expression-Pipeline/diagnostic && npm run build` (if serving from dist)
2. Or just let Vite hot-reload if running dev server
3. Open `localhost:5173` → Lunar Studio → QA tab
4. Should see: STATUS shows pass/warn/fail (not OFFLINE), ASSERTIONS shows 18, OPEN BUGS shows 6, LAST REPORT shows the green badges from March 8

## Do NOT

- Modify any backend QA endpoints or Python code
- Refactor the QAView component structure — just fix the data plumbing
- Add new dependencies
- Touch the assertion playground or test functionality — that part works fine once assertions load
