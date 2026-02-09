# Luna QA System v2 — Design Specification

**Status:** Draft  
**Authors:** The Dude (Architect), Benjamin Franklin (Review)  
**Date:** 2025-02-01  

---

## 1. Problem Statement

Current debugging loop:
```
Bug → Claude researches → "Fixed" → Test → Still broken → ???
```

No visibility into whether fixes work. Need machine-verifiable assertions.

---

## 2. Solution: Five Capabilities

1. **Live Monitoring** — Assertions on every inference
2. **Debugging Tools** — Request chain, prompt inspection, response comparison
3. **Regression Testing** — Replay known bugs, verify fixes
4. **Assertion Scaffolding** — Add assertions without code
5. **MCP Integration** — Luna can self-diagnose

---

## 3. Architecture

```
Director → QAValidator → QA Database
              ↓               ↓
         Assertions      Bug Database
              ↓               ↓
        Frontend UI      Luna MCP Tools
```

### InferenceContext (captured per inference)

```python
@dataclass
class InferenceContext:
    inference_id: str
    timestamp: datetime
    query: str
    route: str  # LOCAL_ONLY, DELEGATION_DETECTION, FULL_DELEGATION
    complexity_score: float
    providers_tried: list[str]
    provider_used: str
    personality_injected: bool
    personality_length: int
    system_prompt: str
    narration_applied: bool
    raw_response: str
    narrated_response: Optional[str]
    final_response: str
    latency_ms: float
    input_tokens: int
    output_tokens: int
    request_chain: list[RequestStep]
```

---

## 4. Assertion System

### Built-in Assertions

| ID | Name | Check |
|----|------|-------|
| P1 | Personality injected | length > 1000 |
| P3 | Narration applied | if FULL_DELEGATION → narration ran |
| S1 | No code blocks | no ``` unless asked |
| S2 | No ASCII art | no box drawing chars |
| V1 | No Claude-isms | no banned phrases |
| V3 | Warm greeting | greeting patterns match |
| F1 | Provider success | at least one worked |

### Pattern-Based Assertions (No Code)

```python
@dataclass
class PatternConfig:
    target: str  # response, system_prompt, query
    match_type: str  # contains, not_contains, regex, length_gt
    pattern: str
    case_sensitive: bool = False
```

### Scaffolding UI

```
┌─────────────────────────────────────────┐
│  Name: [No French Responses        ]    │
│  Target: [Response ▼]                   │
│  Condition: [Does NOT contain ▼]        │
│  Pattern: [bonjour|merci           ]    │
│  [Test] → ✅ Would PASS                 │
│                     [Save Assertion]    │
└─────────────────────────────────────────┘
```

---

## 5. Bug Database

```python
@dataclass
class Bug:
    id: str  # BUG-001
    name: str
    query: str
    expected_behavior: str
    actual_behavior: str
    root_cause: str
    affected_assertions: list[str]
    status: str  # open, failing, fixed
    severity: str
    last_test_passed: bool
```

---

## 6. MCP Integration

Luna can access QA through her own tools:

### Read Tools
```python
qa_get_last_report()      # Last inference QA
qa_get_health()           # Pass rate, failures
qa_search_reports()       # Search history
qa_get_stats("24h")       # Statistics
qa_get_assertion_list()   # All assertions
```

### Write Tools
```python
qa_add_assertion(name, category, target, condition, pattern)
qa_toggle_assertion(id, enabled)
qa_delete_assertion(id)
```

### Bug Tools
```python
qa_add_bug(name, query, expected, actual)
qa_add_bug_from_last()    # From failed report
qa_list_bugs(status)
qa_update_bug_status(id, status)
```

### Test Tools
```python
qa_run_regression()       # Full suite
qa_run_single_bug(id)     # One bug
qa_simulate_query(query)  # Test with QA
```

### Example: Luna Self-Diagnosis

```
User: "you've been acting weird lately"

Luna: [calls qa_get_health()]
      → pass_rate: 0.66, failing_bugs: 3

Luna: "Yeah, my pass rate is only 66%. FULL_DELEGATION 
       is failing every time. Want me to flag this?"
```

---

## 7. Data Visualization

| Data | Chart Type |
|------|------------|
| Pass rate trend | Line chart |
| Route comparison | Spider/radar |
| Assertion profile | Spider/radar |
| Provider breakdown | Horizontal bars |
| Request flow | Sankey diagram |
| Failure timing | Heatmap |
| Overall health | Gauge |

---

## 8. API Endpoints

### Reports
```
GET  /qa/last
GET  /qa/history
GET  /qa/search
```

### Stats
```
GET  /qa/health
GET  /qa/stats
GET  /qa/trend
```

### Assertions
```
GET/POST /qa/assertions
PUT/DELETE /qa/assertions/{id}
POST /qa/assertions/{id}/test
```

### Bugs
```
GET/POST /qa/bugs
PUT /qa/bugs/{id}
POST /qa/bugs/from-report
```

### Test Runner
```
POST /qa/regression/run
POST /qa/regression/run/{bug_id}
POST /qa/simulate
```

### WebSocket
```
WS /qa/live → Real-time events
```

---

## 9. Database Schema

```sql
CREATE TABLE qa_reports (
    id TEXT PRIMARY KEY,
    timestamp DATETIME,
    query TEXT,
    route TEXT,
    provider_used TEXT,
    passed BOOLEAN,
    failed_count INTEGER,
    diagnosis TEXT,
    context_json TEXT
);

CREATE TABLE qa_assertion_results (
    report_id TEXT,
    assertion_id TEXT,
    passed BOOLEAN,
    details TEXT
);

CREATE TABLE qa_assertions (
    id TEXT PRIMARY KEY,
    name TEXT,
    category TEXT,
    severity TEXT,
    enabled BOOLEAN,
    check_type TEXT,
    pattern_config_json TEXT
);

CREATE TABLE qa_bugs (
    id TEXT PRIMARY KEY,
    name TEXT,
    query TEXT,
    expected_behavior TEXT,
    actual_behavior TEXT,
    status TEXT,
    severity TEXT,
    last_test_passed BOOLEAN
);
```

---

## 10. Implementation Phases

| Phase | Contents | Priority |
|-------|----------|----------|
| 1 | Core validation, basic API, minimal UI | P0 |
| 2 | Request chain, response comparison | P0 |
| 3 | Bug database, regression runner | P1 |
| 4 | Assertion scaffolding UI | P1 |
| 5 | MCP integration | P1 |
| 6 | Spider charts, sankey, heatmap | P2 |
| 7 | WebSocket, alerts | P2 |

---

## 11. Files to Create

### Backend
```
src/luna/qa/__init__.py
src/luna/qa/validator.py
src/luna/qa/assertions.py
src/luna/qa/context.py
src/luna/qa/database.py
src/luna/qa/bugs.py
src/luna/qa/mcp_tools.py
```

### Frontend
```
frontend/src/components/LunaQA/
├── LunaQATab.jsx
├── views/LiveView.jsx
├── views/HistoryView.jsx
├── views/StatsView.jsx
├── views/SimulateView.jsx
├── views/TestSuiteView.jsx
├── components/QAReport.jsx
├── components/AssertionList.jsx
├── components/AssertionScaffold.jsx
├── charts/SpiderChart.jsx
├── charts/TrendLine.jsx
└── qa.css
```

### Modified
```
src/luna/actors/director.py  (instrumentation)
src/luna/api/server.py       (endpoints)
src/luna/mcp/tools.py        (register QA tools)
frontend/src/App.jsx         (add tab)
```

---

## 12. Success Criteria

1. ✅ Every inference has QA report
2. ✅ Failures visible immediately
3. ✅ Diagnosis tells what broke
4. ✅ New assertions without code
5. ✅ Regression suite runs
6. ✅ Luna can self-diagnose
7. ✅ No performance impact

---

*The watchtower is built. Luna sees herself. You see Luna.*
