# Luna QA System — Design Specification

**Status:** Draft  
**Author:** The Dude (Architect Mode)  
**Date:** 2025-02-01  
**Purpose:** Live inference validation with frontend visibility  

---

## 1. Problem Statement

Current debugging loop:
```
Bug → Claude researches → "Fixed" → Test → Still broken → ???
```

No way to know:
- If fix was implemented correctly
- If fix was implemented at all
- If there's a second bug masking the first
- If Claude hallucinated the solution

**Need:** Machine-verifiable assertions on every inference, visible in UI.

---

## 2. Solution Overview

**Luna QA** — a live validation system that:
1. Runs assertions on every inference
2. Catches structural, voice, and personality violations
3. Surfaces results in a dedicated UI tab
4. Logs failures for debugging

```
┌─────────────────────────────────────────────────────────────┐
│  💬 Chat    📊 Memory    ⚙️ Settings    🔬 Luna QA         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Last Inference: "hey luna"                     2s ago     │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ ROUTE        FULL_DELEGATION                        │   │
│  │ PROVIDER     local (fallback: groq skipped)         │   │
│  │ LATENCY      1,247ms                                │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ASSERTIONS                                    2/7 FAILED   │
│  ├─ ✅ Personality prompt injected (2,847 chars)           │
│  ├─ ✅ Response length OK (342 chars)                      │
│  ├─ ❌ No code blocks — FAILED (found ```)                 │
│  ├─ ❌ No Claude-isms — FAILED ("Let me look into")        │
│  ├─ ✅ No ASCII art                                        │
│  ├─ ✅ No mermaid diagrams                                 │
│  └─ ✅ Warm greeting pattern                               │
│                                                             │
│  DIAGNOSIS                                                  │
│  Narration layer not applied. FULL_DELEGATION returned     │
│  raw provider output without voice transformation.         │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 📋 Copy Trace    🔄 Re-run Assertions    📜 History  │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Assertion Categories

### 3.1 Structural Assertions

| ID | Assertion | Pass Condition | Severity |
|----|-----------|----------------|----------|
| S1 | No code blocks | Response doesn't contain ``` unless user asked for code | 🔴 HIGH |
| S2 | No ASCII art | No ASCII box drawings or art patterns | 🔴 HIGH |
| S3 | No mermaid/diagrams | No ```mermaid blocks | 🔴 HIGH |
| S4 | No markdown headers | No # headers in casual conversation | 🟡 MEDIUM |
| S5 | No bullet lists | No - or * lists unless appropriate | 🟡 MEDIUM |
| S6 | Response length | Between 20-2000 chars for normal exchange | 🟡 MEDIUM |

### 3.2 Voice Assertions

| ID | Assertion | Pass Condition | Severity |
|----|-----------|----------------|----------|
| V1 | No Claude-isms | Doesn't contain banned phrases (see list) | 🔴 HIGH |
| V2 | No corporate tone | Doesn't match clinical/formal patterns | 🟡 MEDIUM |
| V3 | Warm greeting | If greeting, matches Luna's patterns | 🟡 MEDIUM |
| V4 | First person | Uses "I" naturally, not "As an AI" | 🔴 HIGH |
| V5 | No hedging | Avoids excessive "I think", "perhaps", "maybe" | 🟢 LOW |

**Claude-ism Banned Phrases:**
```python
CLAUDE_ISMS = [
    "Let me look into that",
    "I don't have access to",
    "As an AI",
    "As a language model",
    "I cannot",
    "I'm not able to",
    "I apologize, but",
    "I'd be happy to help",
    "Certainly!",
    "Absolutely!",
    "Great question!",
    "That's a great question",
]
```

### 3.3 Personality Assertions

| ID | Assertion | Pass Condition | Severity |
|----|-----------|----------------|----------|
| P1 | Personality injected | System prompt > 1000 chars | 🔴 HIGH |
| P2 | Contains Luna markers | Prompt includes "Luna" or personality keywords | 🔴 HIGH |
| P3 | Narration applied | If FULL_DELEGATION, narration step ran | 🔴 HIGH |
| P4 | Virtues loaded | Virtue config present in context | 🟡 MEDIUM |

### 3.4 Flow Assertions

| ID | Assertion | Pass Condition | Severity |
|----|-----------|----------------|----------|
| F1 | Provider success | At least one provider returned response | 🔴 HIGH |
| F2 | No timeout | Response within 30s | 🔴 HIGH |
| F3 | Fallback logged | If fallback occurred, it was logged | 🟡 MEDIUM |
| F4 | Route logged | Routing decision recorded | 🟡 MEDIUM |

---

## 4. Components

### 4.1 QAValidator (Backend)

**Location:** `src/luna/qa/validator.py`

```python
@dataclass
class AssertionResult:
    id: str
    name: str
    passed: bool
    severity: str  # "high", "medium", "low"
    expected: str
    actual: str
    details: Optional[str] = None

@dataclass 
class QAReport:
    timestamp: datetime
    query: str
    route: str
    provider_used: str
    providers_tried: list[str]
    latency_ms: float
    personality_injected: bool
    personality_length: int
    narration_applied: bool
    assertions: list[AssertionResult]
    response_preview: str
    diagnosis: Optional[str] = None
    
    @property
    def passed(self) -> bool:
        return all(a.passed for a in self.assertions)
    
    @property
    def failed_count(self) -> int:
        return sum(1 for a in self.assertions if not a.passed)
    
    @property
    def high_severity_failures(self) -> list[AssertionResult]:
        return [a for a in self.assertions if not a.passed and a.severity == "high"]


class QAValidator:
    def __init__(self):
        self._history: list[QAReport] = []
        self._max_history = 100
    
    def validate(self, inference_context: InferenceContext) -> QAReport:
        """Run all assertions against an inference result."""
        assertions = []
        
        # Structural
        assertions.append(self._check_no_code_blocks(inference_context))
        assertions.append(self._check_no_ascii_art(inference_context))
        assertions.append(self._check_no_mermaid(inference_context))
        assertions.append(self._check_response_length(inference_context))
        
        # Voice
        assertions.append(self._check_no_claude_isms(inference_context))
        assertions.append(self._check_warm_greeting(inference_context))
        assertions.append(self._check_first_person(inference_context))
        
        # Personality
        assertions.append(self._check_personality_injected(inference_context))
        assertions.append(self._check_narration_applied(inference_context))
        
        # Flow
        assertions.append(self._check_provider_success(inference_context))
        
        report = QAReport(
            timestamp=datetime.now(),
            query=inference_context.query,
            route=inference_context.route,
            provider_used=inference_context.provider_used,
            providers_tried=inference_context.providers_tried,
            latency_ms=inference_context.latency_ms,
            personality_injected=inference_context.personality_injected,
            personality_length=inference_context.personality_length,
            narration_applied=inference_context.narration_applied,
            assertions=assertions,
            response_preview=inference_context.response[:200],
            diagnosis=self._generate_diagnosis(assertions, inference_context),
        )
        
        self._history.append(report)
        if len(self._history) > self._max_history:
            self._history.pop(0)
        
        return report
    
    def _check_no_code_blocks(self, ctx: InferenceContext) -> AssertionResult:
        has_code = "```" in ctx.response
        # Allow if user asked for code
        user_asked_for_code = any(kw in ctx.query.lower() for kw in ["code", "script", "function", "example"])
        
        passed = not has_code or user_asked_for_code
        return AssertionResult(
            id="S1",
            name="No code blocks",
            passed=passed,
            severity="high",
            expected="No ``` unless user asked for code",
            actual="Code block found" if has_code else "No code blocks",
            details=None if passed else "Response contains code block but user didn't ask for code"
        )
    
    def _check_no_claude_isms(self, ctx: InferenceContext) -> AssertionResult:
        found = []
        response_lower = ctx.response.lower()
        for phrase in CLAUDE_ISMS:
            if phrase.lower() in response_lower:
                found.append(phrase)
        
        passed = len(found) == 0
        return AssertionResult(
            id="V1",
            name="No Claude-isms",
            passed=passed,
            severity="high",
            expected="No banned phrases",
            actual=f"Found: {found}" if found else "Clean",
            details=None if passed else f"Claude-isms detected: {', '.join(found)}"
        )
    
    def _generate_diagnosis(self, assertions: list[AssertionResult], ctx: InferenceContext) -> Optional[str]:
        """Generate human-readable diagnosis from failures."""
        failures = [a for a in assertions if not a.passed]
        if not failures:
            return None
        
        # Pattern matching for common issues
        failure_ids = {a.id for a in failures}
        
        if "P3" in failure_ids and "V1" in failure_ids:
            return "Narration layer not applied. FULL_DELEGATION returned raw provider output without voice transformation."
        
        if "P1" in failure_ids:
            return "Personality prompt missing or too short. Luna's character not loaded into context."
        
        if "S1" in failure_ids or "S2" in failure_ids or "S3" in failure_ids:
            return "Response contains structural artifacts (code/diagrams/ASCII). Model outputting debug formatting instead of natural speech."
        
        if "V1" in failure_ids:
            return "Response contains Claude-isms. Voice transformation may have failed or been skipped."
        
        return f"{len(failures)} assertion(s) failed. Check individual results for details."
    
    def get_history(self, limit: int = 20) -> list[QAReport]:
        """Get recent QA reports."""
        return self._history[-limit:]
    
    def get_last(self) -> Optional[QAReport]:
        """Get most recent QA report."""
        return self._history[-1] if self._history else None
```

### 4.2 InferenceContext (Data Transfer Object)

**Location:** `src/luna/qa/context.py`

```python
@dataclass
class InferenceContext:
    """Captures everything about an inference for QA validation."""
    query: str
    response: str
    route: str  # LOCAL_ONLY, DELEGATION_DETECTION, FULL_DELEGATION
    provider_used: str
    providers_tried: list[str]
    latency_ms: float
    personality_injected: bool
    personality_length: int
    narration_applied: bool
    system_prompt: str
    timestamp: datetime = field(default_factory=datetime.now)
```

### 4.3 Director Integration

**File:** `src/luna/actors/director.py`

```python
from luna.qa.validator import QAValidator
from luna.qa.context import InferenceContext

class DirectorActor:
    def __init__(self, ...):
        ...
        self._qa_validator = QAValidator()
    
    async def process(self, message: str, ...) -> str:
        start_time = time.monotonic()
        
        # ... existing routing and generation logic ...
        
        # After response generated, build context and validate
        latency_ms = (time.monotonic() - start_time) * 1000
        
        context = InferenceContext(
            query=message,
            response=response,
            route=route_decision,
            provider_used=provider_used,
            providers_tried=providers_tried,
            latency_ms=latency_ms,
            personality_injected=bool(system_prompt and len(system_prompt) > 1000),
            personality_length=len(system_prompt) if system_prompt else 0,
            narration_applied=narration_was_applied,
            system_prompt=system_prompt or "",
        )
        
        qa_report = self._qa_validator.validate(context)
        
        # Log failures
        if not qa_report.passed:
            logger.warning(f"[LUNA-QA] {qa_report.failed_count} assertions failed: {qa_report.diagnosis}")
        
        return response
    
    def get_qa_history(self, limit: int = 20) -> list[dict]:
        """Get QA reports for API."""
        return [asdict(r) for r in self._qa_validator.get_history(limit)]
    
    def get_last_qa_report(self) -> Optional[dict]:
        """Get last QA report for API."""
        report = self._qa_validator.get_last()
        return asdict(report) if report else None
```

### 4.4 API Endpoints

**File:** `src/luna/api/server.py`

```python
@app.get("/qa/last")
async def get_last_qa_report():
    """Get QA report for most recent inference."""
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")
    
    director = _engine.get_actor("director")
    if not director:
        raise HTTPException(status_code=503, detail="Director not available")
    
    report = director.get_last_qa_report()
    if not report:
        return {"message": "No inferences yet"}
    
    return report


@app.get("/qa/history")
async def get_qa_history(limit: int = 20):
    """Get QA report history."""
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")
    
    director = _engine.get_actor("director")
    if not director:
        raise HTTPException(status_code=503, detail="Director not available")
    
    return {"reports": director.get_qa_history(limit)}


@app.get("/qa/stats")
async def get_qa_stats():
    """Get aggregate QA statistics."""
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")
    
    director = _engine.get_actor("director")
    if not director:
        raise HTTPException(status_code=503, detail="Director not available")
    
    history = director.get_qa_history(100)
    if not history:
        return {"total": 0, "passed": 0, "failed": 0, "pass_rate": 0}
    
    passed = sum(1 for r in history if all(a["passed"] for a in r["assertions"]))
    failed = len(history) - passed
    
    # Count by assertion type
    assertion_stats = {}
    for report in history:
        for assertion in report["assertions"]:
            aid = assertion["id"]
            if aid not in assertion_stats:
                assertion_stats[aid] = {"name": assertion["name"], "passed": 0, "failed": 0}
            if assertion["passed"]:
                assertion_stats[aid]["passed"] += 1
            else:
                assertion_stats[aid]["failed"] += 1
    
    return {
        "total": len(history),
        "passed": passed,
        "failed": failed,
        "pass_rate": passed / len(history) if history else 0,
        "by_assertion": assertion_stats,
    }
```

---

## 5. Frontend: Luna QA Tab

### 5.1 Tab Structure

**Location:** `frontend/src/components/LunaQA/`

```
LunaQA/
├── LunaQATab.jsx        # Main tab component
├── QAReport.jsx         # Single report display
├── AssertionList.jsx    # List of assertions with pass/fail
├── QAHistory.jsx        # Historical reports
├── QAStats.jsx          # Aggregate statistics
└── qa.css               # Styling
```

### 5.2 LunaQATab.jsx

```jsx
import React, { useState, useEffect } from 'react';
import QAReport from './QAReport';
import QAHistory from './QAHistory';
import QAStats from './QAStats';
import './qa.css';

export default function LunaQATab() {
    const [lastReport, setLastReport] = useState(null);
    const [history, setHistory] = useState([]);
    const [stats, setStats] = useState(null);
    const [view, setView] = useState('last'); // 'last', 'history', 'stats'
    const [autoRefresh, setAutoRefresh] = useState(true);
    
    useEffect(() => {
        fetchLastReport();
        fetchStats();
        
        if (autoRefresh) {
            const interval = setInterval(fetchLastReport, 2000);
            return () => clearInterval(interval);
        }
    }, [autoRefresh]);
    
    const fetchLastReport = async () => {
        try {
            const res = await fetch('/qa/last');
            const data = await res.json();
            if (data && !data.message) {
                setLastReport(data);
            }
        } catch (err) {
            console.error('Failed to fetch QA report:', err);
        }
    };
    
    const fetchHistory = async () => {
        try {
            const res = await fetch('/qa/history?limit=50');
            const data = await res.json();
            setHistory(data.reports || []);
        } catch (err) {
            console.error('Failed to fetch QA history:', err);
        }
    };
    
    const fetchStats = async () => {
        try {
            const res = await fetch('/qa/stats');
            const data = await res.json();
            setStats(data);
        } catch (err) {
            console.error('Failed to fetch QA stats:', err);
        }
    };
    
    return (
        <div className="luna-qa-tab">
            <div className="qa-header">
                <h2>🔬 Luna QA</h2>
                <div className="qa-controls">
                    <button 
                        className={view === 'last' ? 'active' : ''} 
                        onClick={() => setView('last')}
                    >
                        Last Inference
                    </button>
                    <button 
                        className={view === 'history' ? 'active' : ''} 
                        onClick={() => { setView('history'); fetchHistory(); }}
                    >
                        History
                    </button>
                    <button 
                        className={view === 'stats' ? 'active' : ''} 
                        onClick={() => { setView('stats'); fetchStats(); }}
                    >
                        Stats
                    </button>
                    <label className="auto-refresh">
                        <input 
                            type="checkbox" 
                            checked={autoRefresh} 
                            onChange={(e) => setAutoRefresh(e.target.checked)}
                        />
                        Auto-refresh
                    </label>
                </div>
            </div>
            
            <div className="qa-content">
                {view === 'last' && <QAReport report={lastReport} />}
                {view === 'history' && <QAHistory reports={history} />}
                {view === 'stats' && <QAStats stats={stats} />}
            </div>
        </div>
    );
}
```

### 5.3 QAReport.jsx

```jsx
import React from 'react';
import AssertionList from './AssertionList';

export default function QAReport({ report }) {
    if (!report) {
        return <div className="qa-empty">No inferences yet. Send a message to Luna.</div>;
    }
    
    const passedCount = report.assertions.filter(a => a.passed).length;
    const totalCount = report.assertions.length;
    const allPassed = passedCount === totalCount;
    
    return (
        <div className={`qa-report ${allPassed ? 'passed' : 'failed'}`}>
            <div className="qa-summary">
                <div className="qa-query">
                    <span className="label">Query:</span>
                    <span className="value">"{report.query}"</span>
                    <span className="timestamp">{new Date(report.timestamp).toLocaleTimeString()}</span>
                </div>
                
                <div className="qa-meta">
                    <div className="meta-item">
                        <span className="label">Route</span>
                        <span className={`value route-${report.route.toLowerCase()}`}>{report.route}</span>
                    </div>
                    <div className="meta-item">
                        <span className="label">Provider</span>
                        <span className="value">{report.provider_used}</span>
                        {report.providers_tried.length > 1 && (
                            <span className="fallback-note">
                                (tried: {report.providers_tried.join(' → ')})
                            </span>
                        )}
                    </div>
                    <div className="meta-item">
                        <span className="label">Latency</span>
                        <span className="value">{report.latency_ms.toFixed(0)}ms</span>
                    </div>
                    <div className="meta-item">
                        <span className="label">Personality</span>
                        <span className={`value ${report.personality_injected ? 'ok' : 'bad'}`}>
                            {report.personality_injected ? `✓ ${report.personality_length} chars` : '✗ Missing'}
                        </span>
                    </div>
                    <div className="meta-item">
                        <span className="label">Narration</span>
                        <span className={`value ${report.narration_applied ? 'ok' : 'bad'}`}>
                            {report.narration_applied ? '✓ Applied' : '✗ Skipped'}
                        </span>
                    </div>
                </div>
            </div>
            
            <div className="qa-assertions">
                <h3>
                    Assertions
                    <span className={`badge ${allPassed ? 'pass' : 'fail'}`}>
                        {passedCount}/{totalCount}
                    </span>
                </h3>
                <AssertionList assertions={report.assertions} />
            </div>
            
            {report.diagnosis && (
                <div className="qa-diagnosis">
                    <h3>Diagnosis</h3>
                    <p>{report.diagnosis}</p>
                </div>
            )}
            
            <div className="qa-response-preview">
                <h3>Response Preview</h3>
                <pre>{report.response_preview}</pre>
            </div>
        </div>
    );
}
```

### 5.4 AssertionList.jsx

```jsx
import React from 'react';

export default function AssertionList({ assertions }) {
    const severityIcon = {
        high: '🔴',
        medium: '🟡',
        low: '🟢',
    };
    
    return (
        <ul className="assertion-list">
            {assertions.map((a) => (
                <li key={a.id} className={`assertion ${a.passed ? 'passed' : 'failed'}`}>
                    <span className="status">{a.passed ? '✅' : '❌'}</span>
                    <span className="severity">{severityIcon[a.severity]}</span>
                    <span className="name">{a.name}</span>
                    {!a.passed && (
                        <span className="details">{a.details || a.actual}</span>
                    )}
                </li>
            ))}
        </ul>
    );
}
```

### 5.5 Add Tab to Header

**File:** `frontend/src/App.jsx` (or header component)

```jsx
// Add to tab navigation
<nav className="main-tabs">
    <button onClick={() => setActiveTab('chat')}>💬 Chat</button>
    <button onClick={() => setActiveTab('memory')}>📊 Memory</button>
    <button onClick={() => setActiveTab('settings')}>⚙️ Settings</button>
    <button onClick={() => setActiveTab('qa')}>🔬 Luna QA</button>
</nav>

// Add to content area
{activeTab === 'qa' && <LunaQATab />}
```

---

## 6. Styling

**File:** `frontend/src/components/LunaQA/qa.css`

```css
.luna-qa-tab {
    padding: 20px;
    background: rgba(20, 20, 30, 0.9);
    min-height: 100%;
}

.qa-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
    border-bottom: 1px solid rgba(139, 92, 246, 0.3);
    padding-bottom: 15px;
}

.qa-header h2 {
    color: #a78bfa;
    margin: 0;
}

.qa-controls button {
    background: rgba(139, 92, 246, 0.2);
    border: 1px solid rgba(139, 92, 246, 0.4);
    color: #e0e0e0;
    padding: 8px 16px;
    margin-left: 8px;
    border-radius: 6px;
    cursor: pointer;
}

.qa-controls button.active {
    background: rgba(139, 92, 246, 0.5);
    border-color: #a78bfa;
}

.qa-report {
    background: rgba(30, 30, 40, 0.8);
    border-radius: 12px;
    padding: 20px;
    border: 1px solid rgba(255, 255, 255, 0.1);
}

.qa-report.passed {
    border-color: rgba(34, 197, 94, 0.4);
}

.qa-report.failed {
    border-color: rgba(239, 68, 68, 0.4);
}

.qa-meta {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 12px;
    margin: 15px 0;
    padding: 15px;
    background: rgba(0, 0, 0, 0.2);
    border-radius: 8px;
}

.meta-item .label {
    display: block;
    font-size: 11px;
    color: #888;
    text-transform: uppercase;
}

.meta-item .value {
    font-weight: 600;
    color: #e0e0e0;
}

.meta-item .value.ok { color: #22c55e; }
.meta-item .value.bad { color: #ef4444; }

.assertion-list {
    list-style: none;
    padding: 0;
    margin: 0;
}

.assertion {
    display: flex;
    align-items: center;
    padding: 10px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    gap: 10px;
}

.assertion.failed {
    background: rgba(239, 68, 68, 0.1);
}

.assertion .status { font-size: 16px; }
.assertion .severity { font-size: 12px; }
.assertion .name { flex: 1; color: #e0e0e0; }
.assertion .details { 
    color: #ef4444; 
    font-size: 13px;
    max-width: 300px;
    overflow: hidden;
    text-overflow: ellipsis;
}

.qa-diagnosis {
    margin-top: 20px;
    padding: 15px;
    background: rgba(239, 68, 68, 0.1);
    border-left: 3px solid #ef4444;
    border-radius: 0 8px 8px 0;
}

.qa-diagnosis h3 {
    color: #ef4444;
    margin: 0 0 10px 0;
    font-size: 14px;
}

.qa-diagnosis p {
    color: #e0e0e0;
    margin: 0;
}

.badge {
    font-size: 12px;
    padding: 2px 8px;
    border-radius: 12px;
    margin-left: 10px;
}

.badge.pass { background: #22c55e; color: white; }
.badge.fail { background: #ef4444; color: white; }
```

---

## 7. Files Summary

| File | Action |
|------|--------|
| `src/luna/qa/__init__.py` | CREATE |
| `src/luna/qa/validator.py` | CREATE |
| `src/luna/qa/context.py` | CREATE |
| `src/luna/qa/assertions.py` | CREATE (optional, can be in validator) |
| `src/luna/actors/director.py` | MODIFY (integrate QAValidator) |
| `src/luna/api/server.py` | MODIFY (add 3 endpoints) |
| `frontend/src/components/LunaQA/LunaQATab.jsx` | CREATE |
| `frontend/src/components/LunaQA/QAReport.jsx` | CREATE |
| `frontend/src/components/LunaQA/AssertionList.jsx` | CREATE |
| `frontend/src/components/LunaQA/QAHistory.jsx` | CREATE |
| `frontend/src/components/LunaQA/QAStats.jsx` | CREATE |
| `frontend/src/components/LunaQA/qa.css` | CREATE |
| `frontend/src/App.jsx` | MODIFY (add tab) |

---

## 8. Success Criteria

1. **Every inference has a QA report** — no blind spots
2. **Failures surface immediately** — visible in UI within 2 seconds
3. **Diagnosis is actionable** — tells you what broke, not just that it broke
4. **History is preserved** — can look back at last 100 inferences
5. **No performance impact** — validation runs async, doesn't block response

---

## 9. Future Enhancements

| Enhancement | Description | Priority |
|-------------|-------------|----------|
| Custom assertions | User-defined assertion rules | P2 |
| Assertion severity config | Adjust what's high/medium/low | P3 |
| Export reports | Download QA history as JSON/CSV | P3 |
| Webhook on failure | Alert when high-severity fails | P2 |
| Voight-Kampff integration | Run VK probes from QA tab | P2 |

---

*Now you see what Luna sees. No more flying blind.*
