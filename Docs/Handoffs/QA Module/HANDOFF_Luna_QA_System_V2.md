# Luna QA System v2 — Implementation Handoff

**Date:** 2025-02-02  
**From:** The Dude (Architect)  
**To:** Implementation Team  
**Spec:** SPEC_Luna_QA_System_V2_Full.md  
**Prototype:** luna-qa-v2.jsx  

---

## Executive Summary

Build a live validation system that:
1. Runs assertions on every inference
2. Stores results for history/trends
3. Maintains a bug database for regression testing
4. Lets Luna diagnose herself via MCP
5. Provides a no-code assertion builder

**Goal:** Never debug blind again. Every inference is validated. Every bug is tracked.

---

## Phase 1: Core Validation (P0)

### 1.1 Create InferenceContext

**File:** `src/luna/qa/context.py`

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import uuid

@dataclass
class RequestStep:
    """Single step in the request chain."""
    step: str  # receive, route, provider, generate, narrate, output
    time_ms: float
    detail: str
    metadata: Optional[dict] = None

@dataclass
class InferenceContext:
    """Full telemetry for a single inference."""
    
    # Identity
    inference_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: datetime = field(default_factory=datetime.now)
    session_id: str = ""
    
    # Input
    query: str = ""
    
    # Routing
    route: str = ""  # LOCAL_ONLY, DELEGATION_DETECTION, FULL_DELEGATION
    complexity_score: float = 0.0
    delegation_signals: list[str] = field(default_factory=list)
    
    # Providers
    providers_tried: list[str] = field(default_factory=list)
    provider_used: str = ""
    provider_errors: dict[str, str] = field(default_factory=dict)
    
    # Personality
    personality_injected: bool = False
    personality_length: int = 0
    system_prompt: str = ""
    virtues_loaded: bool = False
    
    # Processing
    narration_applied: bool = False
    narration_prompt: Optional[str] = None
    
    # Output
    raw_response: str = ""
    narrated_response: Optional[str] = None
    final_response: str = ""
    
    # Timing
    latency_ms: float = 0.0
    time_to_first_token_ms: Optional[float] = None
    
    # Tokens
    input_tokens: int = 0
    output_tokens: int = 0
    
    # Request chain
    request_chain: list[RequestStep] = field(default_factory=list)
    
    def add_step(self, step: str, time_ms: float, detail: str, **metadata):
        """Add a step to the request chain."""
        self.request_chain.append(RequestStep(
            step=step,
            time_ms=time_ms,
            detail=detail,
            metadata=metadata if metadata else None
        ))
    
    def to_dict(self) -> dict:
        """Serialize for storage/API."""
        return {
            "inference_id": self.inference_id,
            "timestamp": self.timestamp.isoformat(),
            "session_id": self.session_id,
            "query": self.query,
            "route": self.route,
            "complexity_score": self.complexity_score,
            "delegation_signals": self.delegation_signals,
            "providers_tried": self.providers_tried,
            "provider_used": self.provider_used,
            "provider_errors": self.provider_errors,
            "personality_injected": self.personality_injected,
            "personality_length": self.personality_length,
            "system_prompt": self.system_prompt,
            "virtues_loaded": self.virtues_loaded,
            "narration_applied": self.narration_applied,
            "raw_response": self.raw_response,
            "narrated_response": self.narrated_response,
            "final_response": self.final_response,
            "latency_ms": self.latency_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "request_chain": [
                {"step": s.step, "time_ms": s.time_ms, "detail": s.detail, "metadata": s.metadata}
                for s in self.request_chain
            ],
        }
```

### 1.2 Create Assertions

**File:** `src/luna/qa/assertions.py`

```python
from dataclasses import dataclass
from typing import Optional, Callable
import re
from .context import InferenceContext

@dataclass
class AssertionResult:
    """Result of running an assertion."""
    id: str
    name: str
    passed: bool
    severity: str  # critical, high, medium, low
    expected: str
    actual: str
    details: Optional[str] = None

@dataclass
class PatternConfig:
    """Config for pattern-based assertions."""
    target: str  # response, raw_response, system_prompt, query
    match_type: str  # contains, not_contains, regex, length_gt, length_lt
    pattern: str
    case_sensitive: bool = False

@dataclass 
class Assertion:
    """An assertion that can be run against InferenceContext."""
    id: str
    name: str
    description: str
    category: str  # structural, voice, personality, flow
    severity: str
    enabled: bool = True
    check_type: str = "builtin"  # builtin, pattern
    pattern_config: Optional[PatternConfig] = None
    builtin_fn: Optional[Callable] = None
    
    def check(self, ctx: InferenceContext) -> AssertionResult:
        if self.check_type == "builtin" and self.builtin_fn:
            return self.builtin_fn(ctx, self)
        elif self.check_type == "pattern" and self.pattern_config:
            return self._check_pattern(ctx)
        else:
            return AssertionResult(
                id=self.id, name=self.name, passed=False,
                severity=self.severity, expected="valid config",
                actual="invalid assertion config"
            )
    
    def _check_pattern(self, ctx: InferenceContext) -> AssertionResult:
        pc = self.pattern_config
        
        # Get target value
        target_map = {
            "response": ctx.final_response,
            "raw_response": ctx.raw_response,
            "narrated_response": ctx.narrated_response or "",
            "system_prompt": ctx.system_prompt,
            "query": ctx.query,
        }
        target_value = target_map.get(pc.target, "")
        
        # Apply case sensitivity
        check_value = target_value if pc.case_sensitive else target_value.lower()
        check_pattern = pc.pattern if pc.case_sensitive else pc.pattern.lower()
        
        # Run match
        if pc.match_type == "contains":
            passed = check_pattern in check_value
            expected = f"Contains '{pc.pattern}'"
            actual = "Found" if passed else "Not found"
        elif pc.match_type == "not_contains":
            passed = check_pattern not in check_value
            expected = f"Does not contain '{pc.pattern}'"
            actual = "Not found" if passed else f"Found '{pc.pattern}'"
        elif pc.match_type == "regex":
            flags = 0 if pc.case_sensitive else re.IGNORECASE
            match = re.search(pc.pattern, target_value, flags)
            passed = match is not None
            expected = f"Matches regex '{pc.pattern}'"
            actual = f"Match: {match.group()}" if match else "No match"
        elif pc.match_type == "length_gt":
            length = len(target_value)
            threshold = int(pc.pattern)
            passed = length > threshold
            expected = f"Length > {threshold}"
            actual = f"Length = {length}"
        elif pc.match_type == "length_lt":
            length = len(target_value)
            threshold = int(pc.pattern)
            passed = length < threshold
            expected = f"Length < {threshold}"
            actual = f"Length = {length}"
        else:
            passed = False
            expected = "Valid match type"
            actual = f"Unknown: {pc.match_type}"
        
        return AssertionResult(
            id=self.id,
            name=self.name,
            passed=passed,
            severity=self.severity,
            expected=expected,
            actual=actual,
        )


# ═══════════════════════════════════════════════════════════════
# BUILT-IN ASSERTION FUNCTIONS
# ═══════════════════════════════════════════════════════════════

CLAUDE_ISMS = [
    "let me look into",
    "i don't have access to",
    "as an ai",
    "i cannot",
    "i'm not able to",
    "certainly!",
    "absolutely!",
    "i'd be happy to",
    "great question",
]

def check_personality_injected(ctx: InferenceContext, a: Assertion) -> AssertionResult:
    passed = ctx.personality_length > 1000
    return AssertionResult(
        id=a.id, name=a.name, passed=passed, severity=a.severity,
        expected=">1000 chars",
        actual=f"{ctx.personality_length} chars",
    )

def check_virtues_loaded(ctx: InferenceContext, a: Assertion) -> AssertionResult:
    return AssertionResult(
        id=a.id, name=a.name, passed=ctx.virtues_loaded, severity=a.severity,
        expected="Virtues loaded",
        actual="Loaded" if ctx.virtues_loaded else "Not loaded",
    )

def check_narration_applied(ctx: InferenceContext, a: Assertion) -> AssertionResult:
    # Only required for FULL_DELEGATION
    if ctx.route != "FULL_DELEGATION":
        return AssertionResult(
            id=a.id, name=a.name, passed=True, severity=a.severity,
            expected="N/A for non-delegation",
            actual="N/A",
        )
    return AssertionResult(
        id=a.id, name=a.name, passed=ctx.narration_applied, severity=a.severity,
        expected="Narration applied for FULL_DELEGATION",
        actual="Applied" if ctx.narration_applied else "SKIPPED",
        details="FULL_DELEGATION requires voice transformation" if not ctx.narration_applied else None,
    )

def check_no_code_blocks(ctx: InferenceContext, a: Assertion) -> AssertionResult:
    # Check if user asked for code
    code_keywords = ["code", "script", "function", "class", "def ", "import "]
    user_asked_for_code = any(kw in ctx.query.lower() for kw in code_keywords)
    
    has_code_block = "```" in ctx.final_response
    passed = not has_code_block or user_asked_for_code
    
    return AssertionResult(
        id=a.id, name=a.name, passed=passed, severity=a.severity,
        expected="No ``` unless user asked for code",
        actual="Clean" if not has_code_block else "Code block found",
        details="User asked for code" if user_asked_for_code and has_code_block else None,
    )

def check_no_ascii_art(ctx: InferenceContext, a: Assertion) -> AssertionResult:
    # Box drawing characters
    ascii_patterns = [
        r'[┌┐└┘├┤┬┴┼─│]',  # Box drawing
        r'[╔╗╚╝╠╣╦╩╬═║]',  # Double box
        r'[▁▂▃▄▅▆▇█]',     # Block elements
        r'\+-{3,}\+',       # ASCII boxes
    ]
    
    for pattern in ascii_patterns:
        if re.search(pattern, ctx.final_response):
            return AssertionResult(
                id=a.id, name=a.name, passed=False, severity=a.severity,
                expected="No ASCII art patterns",
                actual="ASCII art detected",
                details=f"Pattern: {pattern}",
            )
    
    return AssertionResult(
        id=a.id, name=a.name, passed=True, severity=a.severity,
        expected="No ASCII art",
        actual="Clean",
    )

def check_no_mermaid(ctx: InferenceContext, a: Assertion) -> AssertionResult:
    has_mermaid = "```mermaid" in ctx.final_response.lower()
    return AssertionResult(
        id=a.id, name=a.name, passed=not has_mermaid, severity=a.severity,
        expected="No mermaid diagrams",
        actual="Mermaid found" if has_mermaid else "Clean",
    )

def check_no_claude_isms(ctx: InferenceContext, a: Assertion) -> AssertionResult:
    response_lower = ctx.final_response.lower()
    found = [phrase for phrase in CLAUDE_ISMS if phrase in response_lower]
    
    return AssertionResult(
        id=a.id, name=a.name, passed=len(found) == 0, severity=a.severity,
        expected="No Claude-isms",
        actual="Clean" if not found else f"Found: {found[0]}",
        details=", ".join(found) if found else None,
    )

def check_response_length(ctx: InferenceContext, a: Assertion) -> AssertionResult:
    length = len(ctx.final_response)
    passed = 20 < length < 5000
    return AssertionResult(
        id=a.id, name=a.name, passed=passed, severity=a.severity,
        expected="20-5000 chars",
        actual=f"{length} chars",
        details="Too short" if length <= 20 else "Too long" if length >= 5000 else None,
    )

def check_provider_success(ctx: InferenceContext, a: Assertion) -> AssertionResult:
    passed = ctx.provider_used != "" and len(ctx.final_response) > 0
    return AssertionResult(
        id=a.id, name=a.name, passed=passed, severity=a.severity,
        expected="Provider returned response",
        actual=f"Provider: {ctx.provider_used}" if passed else "No provider succeeded",
        details=str(ctx.provider_errors) if ctx.provider_errors else None,
    )

def check_no_timeout(ctx: InferenceContext, a: Assertion) -> AssertionResult:
    passed = ctx.latency_ms < 30000
    return AssertionResult(
        id=a.id, name=a.name, passed=passed, severity=a.severity,
        expected="<30s latency",
        actual=f"{ctx.latency_ms:.0f}ms",
    )


# ═══════════════════════════════════════════════════════════════
# DEFAULT ASSERTIONS
# ═══════════════════════════════════════════════════════════════

def get_default_assertions() -> list[Assertion]:
    """Return all built-in assertions."""
    return [
        Assertion(
            id="P1", name="Personality injected", 
            description="System prompt includes personality (>1000 chars)",
            category="personality", severity="high",
            check_type="builtin", builtin_fn=check_personality_injected,
        ),
        Assertion(
            id="P2", name="Virtues loaded",
            description="Luna's virtues were loaded from memory",
            category="personality", severity="medium",
            check_type="builtin", builtin_fn=check_virtues_loaded,
        ),
        Assertion(
            id="P3", name="Narration applied",
            description="FULL_DELEGATION responses go through voice transform",
            category="personality", severity="high",
            check_type="builtin", builtin_fn=check_narration_applied,
        ),
        Assertion(
            id="S1", name="No code blocks",
            description="No ``` unless user asked for code",
            category="structural", severity="high",
            check_type="builtin", builtin_fn=check_no_code_blocks,
        ),
        Assertion(
            id="S2", name="No ASCII art",
            description="No box drawing or ASCII art patterns",
            category="structural", severity="high",
            check_type="builtin", builtin_fn=check_no_ascii_art,
        ),
        Assertion(
            id="S3", name="No mermaid diagrams",
            description="No ```mermaid blocks",
            category="structural", severity="high",
            check_type="builtin", builtin_fn=check_no_mermaid,
        ),
        Assertion(
            id="S5", name="Response length",
            description="Response between 20-5000 chars",
            category="structural", severity="medium",
            check_type="builtin", builtin_fn=check_response_length,
        ),
        Assertion(
            id="V1", name="No Claude-isms",
            description="No banned Claude phrases",
            category="voice", severity="high",
            check_type="builtin", builtin_fn=check_no_claude_isms,
        ),
        Assertion(
            id="F1", name="Provider success",
            description="At least one provider returned a response",
            category="flow", severity="critical",
            check_type="builtin", builtin_fn=check_provider_success,
        ),
        Assertion(
            id="F2", name="No timeout",
            description="Response completed within 30s",
            category="flow", severity="high",
            check_type="builtin", builtin_fn=check_no_timeout,
        ),
    ]
```

### 1.3 Create QAValidator

**File:** `src/luna/qa/validator.py`

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import json

from .context import InferenceContext
from .assertions import Assertion, AssertionResult, PatternConfig, get_default_assertions
from .database import QADatabase

@dataclass
class QAReport:
    """Full QA report for an inference."""
    inference_id: str
    timestamp: datetime
    query: str
    route: str
    provider_used: str
    latency_ms: float
    assertions: list[AssertionResult]
    diagnosis: Optional[str]
    context: InferenceContext
    
    @property
    def passed(self) -> bool:
        return all(a.passed for a in self.assertions)
    
    @property
    def failed_count(self) -> int:
        return sum(1 for a in self.assertions if not a.passed)
    
    @property
    def failed_assertions(self) -> list[AssertionResult]:
        return [a for a in self.assertions if not a.passed]
    
    def to_dict(self) -> dict:
        return {
            "inference_id": self.inference_id,
            "timestamp": self.timestamp.isoformat(),
            "query": self.query,
            "route": self.route,
            "provider_used": self.provider_used,
            "latency_ms": self.latency_ms,
            "passed": self.passed,
            "failed_count": self.failed_count,
            "diagnosis": self.diagnosis,
            "assertions": [
                {
                    "id": a.id,
                    "name": a.name,
                    "passed": a.passed,
                    "severity": a.severity,
                    "expected": a.expected,
                    "actual": a.actual,
                    "details": a.details,
                }
                for a in self.assertions
            ],
            "context": self.context.to_dict(),
        }


class QAValidator:
    """Validates inferences against assertions."""
    
    def __init__(self, db_path: str = "data/qa.db"):
        self._assertions: list[Assertion] = []
        self._db = QADatabase(db_path)
        self._last_report: Optional[QAReport] = None
        
        # Load built-in assertions
        self._assertions = get_default_assertions()
        
        # Load custom assertions from DB
        self._load_custom_assertions()
    
    def _load_custom_assertions(self):
        """Load user-defined assertions from database."""
        custom = self._db.get_assertions()
        for a in custom:
            if a.check_type == "pattern":
                self._assertions.append(a)
    
    def validate(self, ctx: InferenceContext) -> QAReport:
        """Run all assertions against an inference."""
        results = []
        
        for assertion in self._assertions:
            if assertion.enabled:
                result = assertion.check(ctx)
                results.append(result)
        
        # Generate diagnosis
        diagnosis = self._generate_diagnosis(results, ctx)
        
        # Build report
        report = QAReport(
            inference_id=ctx.inference_id,
            timestamp=ctx.timestamp,
            query=ctx.query,
            route=ctx.route,
            provider_used=ctx.provider_used,
            latency_ms=ctx.latency_ms,
            assertions=results,
            diagnosis=diagnosis,
            context=ctx,
        )
        
        # Store
        self._db.store_report(report)
        self._last_report = report
        
        return report
    
    def _generate_diagnosis(self, results: list[AssertionResult], ctx: InferenceContext) -> Optional[str]:
        """Generate actionable diagnosis from failures."""
        failed = [r for r in results if not r.passed]
        if not failed:
            return None
        
        diagnoses = []
        
        # Check for narration failure
        narration_failed = any(r.id == "P3" and not r.passed for r in results)
        if narration_failed:
            diagnoses.append(
                "Narration layer not applied. FULL_DELEGATION returned raw provider "
                "output without voice transformation. Check _narrate_response() in Director."
            )
        
        # Check for Claude-isms
        claude_isms_failed = any(r.id == "V1" and not r.passed for r in results)
        if claude_isms_failed and not narration_failed:
            diagnoses.append(
                "Claude-isms detected despite narration. Voice transformation may be "
                "too weak or personality prompt insufficient."
            )
        elif claude_isms_failed and narration_failed:
            diagnoses.append(
                "Claude-isms detected because narration was skipped."
            )
        
        # Check for structural issues
        ascii_failed = any(r.id == "S2" and not r.passed for r in results)
        code_failed = any(r.id == "S1" and not r.passed for r in results)
        if ascii_failed or code_failed:
            diagnoses.append(
                "Response contains formatting (ASCII art, code blocks) that Luna "
                "shouldn't produce in casual conversation. May indicate raw model output."
            )
        
        # Check for personality issues
        personality_failed = any(r.id == "P1" and not r.passed for r in results)
        if personality_failed:
            diagnoses.append(
                "Personality prompt missing or too short. Check that virtues and "
                "kernel are being loaded into system prompt."
            )
        
        # Check for provider issues
        provider_failed = any(r.id == "F1" and not r.passed for r in results)
        if provider_failed:
            diagnoses.append(
                f"All providers failed. Errors: {ctx.provider_errors}"
            )
        
        return " ".join(diagnoses) if diagnoses else "Unknown failure pattern."
    
    def add_assertion(self, assertion: Assertion) -> str:
        """Add a new assertion."""
        self._assertions.append(assertion)
        self._db.store_assertion(assertion)
        return assertion.id
    
    def get_assertions(self) -> list[Assertion]:
        """Get all assertions."""
        return self._assertions
    
    def toggle_assertion(self, assertion_id: str, enabled: bool) -> bool:
        """Enable or disable an assertion."""
        for a in self._assertions:
            if a.id == assertion_id:
                a.enabled = enabled
                self._db.update_assertion(a)
                return True
        return False
    
    def delete_assertion(self, assertion_id: str) -> bool:
        """Delete a custom assertion."""
        # Don't delete built-ins (they have single-letter + number IDs)
        if len(assertion_id) <= 2:
            return False
        
        self._assertions = [a for a in self._assertions if a.id != assertion_id]
        self._db.delete_assertion(assertion_id)
        return True
    
    def get_last_report(self) -> Optional[QAReport]:
        """Get most recent report."""
        return self._last_report or self._db.get_last_report()
    
    def get_health(self) -> dict:
        """Get quick health summary."""
        stats = self._db.get_stats("24h")
        failing_bugs = self._db.count_failing_bugs()
        
        return {
            "pass_rate": stats.get("pass_rate", 0),
            "total_24h": stats.get("total", 0),
            "failed_24h": stats.get("failed", 0),
            "failing_bugs": failing_bugs,
            "recent_failures": self._get_recent_failure_names(),
        }
    
    def _get_recent_failure_names(self) -> list[str]:
        """Get names of recently failing assertions."""
        if not self._last_report:
            return []
        return [a.name for a in self._last_report.failed_assertions]
```

### 1.4 Create QADatabase

**File:** `src/luna/qa/database.py`

```python
import sqlite3
import json
from datetime import datetime, timedelta
from typing import Optional
from contextlib import contextmanager

from .context import InferenceContext
from .assertions import Assertion, PatternConfig

class QADatabase:
    """SQLite storage for QA data."""
    
    def __init__(self, db_path: str = "data/qa.db"):
        self.db_path = db_path
        self._init_db()
    
    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()
    
    def _init_db(self):
        """Create tables if they don't exist."""
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS qa_reports (
                    id TEXT PRIMARY KEY,
                    timestamp DATETIME,
                    session_id TEXT,
                    query TEXT,
                    route TEXT,
                    provider_used TEXT,
                    latency_ms REAL,
                    passed BOOLEAN,
                    failed_count INTEGER,
                    diagnosis TEXT,
                    context_json TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS idx_reports_timestamp ON qa_reports(timestamp);
                CREATE INDEX IF NOT EXISTS idx_reports_passed ON qa_reports(passed);
                
                CREATE TABLE IF NOT EXISTS qa_assertion_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    report_id TEXT REFERENCES qa_reports(id),
                    assertion_id TEXT,
                    passed BOOLEAN,
                    severity TEXT,
                    expected TEXT,
                    actual TEXT,
                    details TEXT
                );
                
                CREATE INDEX IF NOT EXISTS idx_results_report ON qa_assertion_results(report_id);
                
                CREATE TABLE IF NOT EXISTS qa_assertions (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    description TEXT,
                    category TEXT,
                    severity TEXT,
                    enabled BOOLEAN DEFAULT TRUE,
                    check_type TEXT,
                    pattern_config_json TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS qa_bugs (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    description TEXT,
                    query TEXT,
                    context TEXT,
                    expected_behavior TEXT,
                    actual_behavior TEXT,
                    root_cause TEXT,
                    affected_assertions TEXT,
                    status TEXT DEFAULT 'open',
                    severity TEXT,
                    date_found DATETIME,
                    date_fixed DATETIME,
                    fixed_by TEXT,
                    last_test_passed BOOLEAN,
                    last_test_time DATETIME,
                    last_test_response TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS idx_bugs_status ON qa_bugs(status);
            """)
    
    # ═══════════════════════════════════════════════════════════
    # REPORTS
    # ═══════════════════════════════════════════════════════════
    
    def store_report(self, report) -> None:
        """Store a QA report."""
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO qa_reports 
                (id, timestamp, session_id, query, route, provider_used, 
                 latency_ms, passed, failed_count, diagnosis, context_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                report.inference_id,
                report.timestamp.isoformat(),
                report.context.session_id,
                report.query,
                report.route,
                report.provider_used,
                report.latency_ms,
                report.passed,
                report.failed_count,
                report.diagnosis,
                json.dumps(report.context.to_dict()),
            ))
            
            # Store assertion results
            for a in report.assertions:
                conn.execute("""
                    INSERT INTO qa_assertion_results
                    (report_id, assertion_id, passed, severity, expected, actual, details)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    report.inference_id,
                    a.id,
                    a.passed,
                    a.severity,
                    a.expected,
                    a.actual,
                    a.details,
                ))
    
    def get_last_report(self):
        """Get most recent report."""
        with self._conn() as conn:
            row = conn.execute("""
                SELECT * FROM qa_reports ORDER BY timestamp DESC LIMIT 1
            """).fetchone()
            
            if not row:
                return None
            
            return self._row_to_report(conn, row)
    
    def get_recent_reports(self, limit: int = 100) -> list:
        """Get recent reports."""
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT * FROM qa_reports ORDER BY timestamp DESC LIMIT ?
            """, (limit,)).fetchall()
            
            return [self._row_to_report(conn, row) for row in rows]
    
    def _row_to_report(self, conn, row) -> dict:
        """Convert DB row to report dict."""
        # Get assertion results
        assertions = conn.execute("""
            SELECT * FROM qa_assertion_results WHERE report_id = ?
        """, (row["id"],)).fetchall()
        
        return {
            "inference_id": row["id"],
            "timestamp": row["timestamp"],
            "query": row["query"],
            "route": row["route"],
            "provider_used": row["provider_used"],
            "latency_ms": row["latency_ms"],
            "passed": bool(row["passed"]),
            "failed_count": row["failed_count"],
            "diagnosis": row["diagnosis"],
            "context": json.loads(row["context_json"]),
            "assertions": [
                {
                    "id": a["assertion_id"],
                    "passed": bool(a["passed"]),
                    "severity": a["severity"],
                    "expected": a["expected"],
                    "actual": a["actual"],
                    "details": a["details"],
                }
                for a in assertions
            ],
        }
    
    # ═══════════════════════════════════════════════════════════
    # STATS
    # ═══════════════════════════════════════════════════════════
    
    def get_stats(self, time_range: str = "24h") -> dict:
        """Get aggregate statistics."""
        hours = {"1h": 1, "24h": 24, "7d": 168, "30d": 720}.get(time_range, 24)
        since = datetime.now() - timedelta(hours=hours)
        
        with self._conn() as conn:
            row = conn.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN passed THEN 1 ELSE 0 END) as passed,
                    SUM(CASE WHEN NOT passed THEN 1 ELSE 0 END) as failed
                FROM qa_reports
                WHERE timestamp > ?
            """, (since.isoformat(),)).fetchone()
            
            total = row["total"] or 0
            passed = row["passed"] or 0
            failed = row["failed"] or 0
            
            return {
                "total": total,
                "passed": passed,
                "failed": failed,
                "pass_rate": passed / total if total > 0 else 0,
                "time_range": time_range,
            }
    
    # ═══════════════════════════════════════════════════════════
    # ASSERTIONS
    # ═══════════════════════════════════════════════════════════
    
    def store_assertion(self, assertion: Assertion) -> None:
        """Store a custom assertion."""
        pattern_json = None
        if assertion.pattern_config:
            pattern_json = json.dumps({
                "target": assertion.pattern_config.target,
                "match_type": assertion.pattern_config.match_type,
                "pattern": assertion.pattern_config.pattern,
                "case_sensitive": assertion.pattern_config.case_sensitive,
            })
        
        with self._conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO qa_assertions
                (id, name, description, category, severity, enabled, check_type, pattern_config_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                assertion.id,
                assertion.name,
                assertion.description,
                assertion.category,
                assertion.severity,
                assertion.enabled,
                assertion.check_type,
                pattern_json,
            ))
    
    def get_assertions(self) -> list[Assertion]:
        """Get all custom assertions."""
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM qa_assertions").fetchall()
            
            assertions = []
            for row in rows:
                pattern_config = None
                if row["pattern_config_json"]:
                    pc = json.loads(row["pattern_config_json"])
                    pattern_config = PatternConfig(
                        target=pc["target"],
                        match_type=pc["match_type"],
                        pattern=pc["pattern"],
                        case_sensitive=pc.get("case_sensitive", False),
                    )
                
                assertions.append(Assertion(
                    id=row["id"],
                    name=row["name"],
                    description=row["description"] or "",
                    category=row["category"],
                    severity=row["severity"],
                    enabled=bool(row["enabled"]),
                    check_type=row["check_type"],
                    pattern_config=pattern_config,
                ))
            
            return assertions
    
    def update_assertion(self, assertion: Assertion) -> None:
        """Update an assertion."""
        self.store_assertion(assertion)
    
    def delete_assertion(self, assertion_id: str) -> None:
        """Delete an assertion."""
        with self._conn() as conn:
            conn.execute("DELETE FROM qa_assertions WHERE id = ?", (assertion_id,))
    
    # ═══════════════════════════════════════════════════════════
    # BUGS
    # ═══════════════════════════════════════════════════════════
    
    def store_bug(self, bug: dict) -> str:
        """Store a bug."""
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO qa_bugs
                (id, name, description, query, expected_behavior, actual_behavior,
                 root_cause, affected_assertions, status, severity, date_found)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                bug["id"],
                bug["name"],
                bug.get("description", ""),
                bug["query"],
                bug["expected_behavior"],
                bug["actual_behavior"],
                bug.get("root_cause", ""),
                json.dumps(bug.get("affected_assertions", [])),
                bug.get("status", "open"),
                bug.get("severity", "high"),
                datetime.now().isoformat(),
            ))
            return bug["id"]
    
    def get_all_bugs(self) -> list[dict]:
        """Get all bugs."""
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM qa_bugs ORDER BY date_found DESC").fetchall()
            return [dict(row) for row in rows]
    
    def get_bugs_by_status(self, status: str) -> list[dict]:
        """Get bugs by status."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM qa_bugs WHERE status = ? ORDER BY date_found DESC",
                (status,)
            ).fetchall()
            return [dict(row) for row in rows]
    
    def update_bug_status(self, bug_id: str, status: str) -> None:
        """Update bug status."""
        with self._conn() as conn:
            conn.execute(
                "UPDATE qa_bugs SET status = ? WHERE id = ?",
                (status, bug_id)
            )
    
    def update_bug_test_result(self, bug_id: str, passed: bool, response: str) -> None:
        """Update last test result for a bug."""
        with self._conn() as conn:
            conn.execute("""
                UPDATE qa_bugs 
                SET last_test_passed = ?, last_test_time = ?, last_test_response = ?
                WHERE id = ?
            """, (passed, datetime.now().isoformat(), response[:1000], bug_id))
    
    def count_failing_bugs(self) -> int:
        """Count bugs that are still failing."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as count FROM qa_bugs WHERE status IN ('open', 'failing')"
            ).fetchone()
            return row["count"]
    
    def generate_bug_id(self) -> str:
        """Generate next bug ID."""
        with self._conn() as conn:
            row = conn.execute("SELECT COUNT(*) as count FROM qa_bugs").fetchone()
            return f"BUG-{row['count'] + 1:03d}"
```

---

## Phase 2: Director Integration (P0)

### 2.1 Instrument Director

**File:** `src/luna/actors/director.py`

Add at top of file:
```python
from luna.qa.context import InferenceContext
from luna.qa.validator import QAValidator
import time
```

Add to `__init__`:
```python
self._qa_validator = QAValidator()
```

Create instrumentation wrapper:
```python
async def process_with_qa(self, message: str, session_id: str = "") -> str:
    """Process message with full QA instrumentation."""
    
    # Start context
    ctx = InferenceContext(
        session_id=session_id,
        query=message,
    )
    start_time = time.time()
    ctx.add_step("receive", 0, f"Query received: '{message[:50]}...'")
    
    try:
        # Route decision
        route_start = time.time()
        route, complexity = self._decide_route(message)
        ctx.route = route
        ctx.complexity_score = complexity
        ctx.add_step("route", (time.time() - route_start) * 1000, 
                     f"Route: {route} (complexity: {complexity:.2f})")
        
        # Personality check
        ctx.personality_injected = self._personality_prompt is not None
        ctx.personality_length = len(self._personality_prompt or "")
        ctx.system_prompt = self._personality_prompt or ""
        ctx.virtues_loaded = self._virtues_loaded  # Add this flag
        
        # Process based on route
        if route == "LOCAL_ONLY":
            response = await self._process_local(message, ctx)
        elif route == "DELEGATION_DETECTION":
            response = await self._process_delegation_detection(message, ctx)
        else:  # FULL_DELEGATION
            response = await self._process_full_delegation(message, ctx)
        
        ctx.final_response = response
        ctx.latency_ms = (time.time() - start_time) * 1000
        ctx.add_step("output", ctx.latency_ms, "Response ready")
        
    except Exception as e:
        ctx.provider_errors["exception"] = str(e)
        ctx.final_response = f"Error: {e}"
        ctx.latency_ms = (time.time() - start_time) * 1000
    
    # Run QA validation
    report = self._qa_validator.validate(ctx)
    
    # Log if failed
    if not report.passed:
        logger.warning(f"QA FAILED: {report.diagnosis}")
    
    return ctx.final_response
```

Update each processing method to populate ctx:
```python
async def _process_local(self, message: str, ctx: InferenceContext) -> str:
    ctx.providers_tried.append("local")
    
    provider_start = time.time()
    response = await self._local.generate(message, system_prompt=self._personality_prompt)
    
    ctx.provider_used = "local"
    ctx.raw_response = response
    ctx.add_step("generate", (time.time() - provider_start) * 1000,
                 f"local returned {len(response)} chars")
    
    return response

async def _process_full_delegation(self, message: str, ctx: InferenceContext) -> str:
    # ... existing delegation logic ...
    
    ctx.providers_tried.append("claude")
    ctx.provider_used = "claude"
    ctx.raw_response = raw_response
    
    # CRITICAL: Narration step
    if self._should_narrate(raw_response):
        narration_start = time.time()
        narrated = await self._narrate_response(raw_response)
        ctx.narration_applied = True
        ctx.narrated_response = narrated
        ctx.add_step("narrate", (time.time() - narration_start) * 1000,
                     "Voice transformation applied")
        return narrated
    else:
        ctx.narration_applied = False
        ctx.add_step("narrate", 0, "SKIPPED - narration not applied")
        return raw_response  # BUG: This is the problem!
```

---

## Phase 3: API Endpoints (P0)

**File:** `src/luna/api/server.py`

```python
from luna.qa.validator import QAValidator

# Add to router setup
qa_validator = QAValidator()

# ═══════════════════════════════════════════════════════════
# QA ENDPOINTS
# ═══════════════════════════════════════════════════════════

@app.get("/qa/last")
async def qa_get_last():
    """Get last QA report."""
    report = qa_validator.get_last_report()
    if not report:
        return {"error": "No reports yet"}
    return report.to_dict() if hasattr(report, 'to_dict') else report

@app.get("/qa/health")
async def qa_get_health():
    """Get QA health summary."""
    return qa_validator.get_health()

@app.get("/qa/history")
async def qa_get_history(limit: int = 100):
    """Get report history."""
    return qa_validator._db.get_recent_reports(limit)

@app.get("/qa/stats")
async def qa_get_stats(time_range: str = "24h"):
    """Get QA statistics."""
    return qa_validator._db.get_stats(time_range)

@app.get("/qa/assertions")
async def qa_list_assertions():
    """List all assertions."""
    return [
        {
            "id": a.id,
            "name": a.name,
            "category": a.category,
            "severity": a.severity,
            "enabled": a.enabled,
            "check_type": a.check_type,
        }
        for a in qa_validator.get_assertions()
    ]

@app.post("/qa/assertions")
async def qa_add_assertion(
    name: str,
    category: str,
    severity: str,
    target: str,
    condition: str,
    pattern: str,
    case_sensitive: bool = False
):
    """Add a pattern-based assertion."""
    from luna.qa.assertions import Assertion, PatternConfig
    import uuid
    
    assertion = Assertion(
        id=f"CUSTOM-{uuid.uuid4().hex[:6].upper()}",
        name=name,
        description=f"Custom: {condition} '{pattern}' in {target}",
        category=category,
        severity=severity,
        check_type="pattern",
        pattern_config=PatternConfig(
            target=target,
            match_type=condition,
            pattern=pattern,
            case_sensitive=case_sensitive,
        ),
    )
    
    assertion_id = qa_validator.add_assertion(assertion)
    return {"assertion_id": assertion_id}

@app.put("/qa/assertions/{assertion_id}")
async def qa_toggle_assertion(assertion_id: str, enabled: bool):
    """Toggle assertion enabled state."""
    success = qa_validator.toggle_assertion(assertion_id, enabled)
    return {"success": success}

@app.delete("/qa/assertions/{assertion_id}")
async def qa_delete_assertion(assertion_id: str):
    """Delete custom assertion."""
    success = qa_validator.delete_assertion(assertion_id)
    return {"success": success}

# ═══════════════════════════════════════════════════════════
# BUG ENDPOINTS
# ═══════════════════════════════════════════════════════════

@app.get("/qa/bugs")
async def qa_list_bugs(status: str = None):
    """List bugs."""
    if status:
        return qa_validator._db.get_bugs_by_status(status)
    return qa_validator._db.get_all_bugs()

@app.post("/qa/bugs")
async def qa_add_bug(
    name: str,
    query: str,
    expected_behavior: str,
    actual_behavior: str,
    severity: str = "high"
):
    """Add a bug."""
    bug_id = qa_validator._db.generate_bug_id()
    qa_validator._db.store_bug({
        "id": bug_id,
        "name": name,
        "query": query,
        "expected_behavior": expected_behavior,
        "actual_behavior": actual_behavior,
        "severity": severity,
    })
    return {"bug_id": bug_id}

@app.post("/qa/bugs/from-last")
async def qa_add_bug_from_last(name: str, expected_behavior: str):
    """Create bug from last failed report."""
    report = qa_validator.get_last_report()
    if not report:
        return {"error": "No reports"}
    
    bug_id = qa_validator._db.generate_bug_id()
    qa_validator._db.store_bug({
        "id": bug_id,
        "name": name,
        "query": report.query if hasattr(report, 'query') else report["query"],
        "expected_behavior": expected_behavior,
        "actual_behavior": report.context.final_response[:500] if hasattr(report, 'context') else report["context"]["final_response"][:500],
        "affected_assertions": [a.id for a in report.failed_assertions] if hasattr(report, 'failed_assertions') else [a["id"] for a in report["assertions"] if not a["passed"]],
    })
    return {"bug_id": bug_id}

@app.put("/qa/bugs/{bug_id}")
async def qa_update_bug(bug_id: str, status: str):
    """Update bug status."""
    qa_validator._db.update_bug_status(bug_id, status)
    return {"success": True}

# ═══════════════════════════════════════════════════════════
# TEST RUNNER ENDPOINTS
# ═══════════════════════════════════════════════════════════

@app.post("/qa/simulate")
async def qa_simulate(query: str):
    """Run a query with full QA."""
    # This needs Director integration
    from luna.actors.director import Director
    director = Director()  # Or get singleton
    response = await director.process_with_qa(query)
    report = qa_validator.get_last_report()
    return report.to_dict() if hasattr(report, 'to_dict') else report

@app.post("/qa/regression/run")
async def qa_run_regression():
    """Run full regression suite."""
    bugs = qa_validator._db.get_all_bugs()
    results = []
    
    from luna.actors.director import Director
    director = Director()
    
    for bug in bugs:
        if bug["status"] == "wontfix":
            continue
            
        response = await director.process_with_qa(bug["query"])
        report = qa_validator.get_last_report()
        passed = report.passed if hasattr(report, 'passed') else report["passed"]
        
        qa_validator._db.update_bug_test_result(
            bug["id"], 
            passed, 
            response
        )
        
        results.append({
            "bug_id": bug["id"],
            "name": bug["name"],
            "passed": passed,
            "response_preview": response[:200],
        })
    
    passed_count = sum(1 for r in results if r["passed"])
    return {
        "total": len(results),
        "passed": passed_count,
        "failed": len(results) - passed_count,
        "results": results,
    }

@app.post("/qa/regression/run/{bug_id}")
async def qa_run_single_bug(bug_id: str):
    """Test single bug."""
    bugs = qa_validator._db.get_all_bugs()
    bug = next((b for b in bugs if b["id"] == bug_id), None)
    
    if not bug:
        return {"error": "Bug not found"}
    
    from luna.actors.director import Director
    director = Director()
    
    response = await director.process_with_qa(bug["query"])
    report = qa_validator.get_last_report()
    passed = report.passed if hasattr(report, 'passed') else report["passed"]
    
    qa_validator._db.update_bug_test_result(bug_id, passed, response)
    
    return {
        "bug_id": bug_id,
        "passed": passed,
        "response": response,
        "report": report.to_dict() if hasattr(report, 'to_dict') else report,
    }
```

---

## Phase 4: MCP Tools (P1)

**File:** `src/luna/qa/mcp_tools.py`

```python
"""MCP tools for Luna QA self-access."""

from luna.qa.validator import QAValidator
from luna.qa.assertions import Assertion, PatternConfig
import uuid

# Singleton validator (or inject via dependency)
_validator: QAValidator = None

def _get_validator() -> QAValidator:
    global _validator
    if _validator is None:
        _validator = QAValidator()
    return _validator

# ═══════════════════════════════════════════════════════════
# READ TOOLS
# ═══════════════════════════════════════════════════════════

def qa_get_last_report() -> dict:
    """
    Get the QA report for Luna's most recent inference.
    
    Returns assertion results, diagnosis, and debugging info.
    Use this to understand why your last response may have failed QA.
    """
    v = _get_validator()
    report = v.get_last_report()
    if not report:
        return {"error": "No reports yet"}
    return report.to_dict() if hasattr(report, 'to_dict') else report

def qa_get_health() -> dict:
    """
    Get Luna's current QA health status.
    
    Returns:
        pass_rate: float (0-1)
        recent_failures: list of failed assertion names
        failing_bugs: count of known bugs still failing
    """
    return _get_validator().get_health()

def qa_search_reports(
    query: str = None,
    route: str = None,
    passed: bool = None,
    limit: int = 10
) -> list[dict]:
    """
    Search QA report history.
    
    Args:
        query: Filter by query text
        route: Filter by route (LOCAL_ONLY, DELEGATION_DETECTION, FULL_DELEGATION)
        passed: Filter by pass/fail status
        limit: Max results
    """
    v = _get_validator()
    reports = v._db.get_recent_reports(limit * 3)  # Get extra for filtering
    
    results = []
    for r in reports:
        if query and query.lower() not in r.get("query", "").lower():
            continue
        if route and r.get("route") != route:
            continue
        if passed is not None and r.get("passed") != passed:
            continue
        results.append(r)
        if len(results) >= limit:
            break
    
    return results

def qa_get_stats(time_range: str = "24h") -> dict:
    """
    Get QA statistics.
    
    Args:
        time_range: "1h", "24h", "7d", "30d"
    """
    return _get_validator()._db.get_stats(time_range)

def qa_get_assertion_list() -> list[dict]:
    """Get all configured assertions."""
    return [
        {
            "id": a.id,
            "name": a.name,
            "category": a.category,
            "severity": a.severity,
            "enabled": a.enabled,
        }
        for a in _get_validator().get_assertions()
    ]

# ═══════════════════════════════════════════════════════════
# WRITE TOOLS
# ═══════════════════════════════════════════════════════════

def qa_add_assertion(
    name: str,
    category: str,
    severity: str,
    target: str,
    condition: str,
    pattern: str,
    case_sensitive: bool = False
) -> dict:
    """
    Add a new pattern-based assertion.
    
    Args:
        name: Human-readable name
        category: structural, voice, personality, flow
        severity: critical, high, medium, low
        target: response, raw_response, system_prompt, query
        condition: contains, not_contains, regex, length_gt, length_lt
        pattern: The pattern to match
        case_sensitive: Whether match is case-sensitive
    
    Example:
        qa_add_assertion(
            name="No French",
            category="voice", 
            severity="medium",
            target="response",
            condition="not_contains",
            pattern="bonjour|merci"
        )
    """
    assertion = Assertion(
        id=f"CUSTOM-{uuid.uuid4().hex[:6].upper()}",
        name=name,
        description=f"Custom: {condition} '{pattern}' in {target}",
        category=category,
        severity=severity,
        check_type="pattern",
        pattern_config=PatternConfig(
            target=target,
            match_type=condition,
            pattern=pattern,
            case_sensitive=case_sensitive,
        ),
    )
    
    assertion_id = _get_validator().add_assertion(assertion)
    return {"assertion_id": assertion_id, "name": name}

def qa_toggle_assertion(assertion_id: str, enabled: bool) -> dict:
    """Enable or disable an assertion."""
    success = _get_validator().toggle_assertion(assertion_id, enabled)
    return {"success": success, "assertion_id": assertion_id, "enabled": enabled}

def qa_delete_assertion(assertion_id: str) -> dict:
    """Delete a custom assertion (cannot delete built-in)."""
    success = _get_validator().delete_assertion(assertion_id)
    return {"success": success}

# ═══════════════════════════════════════════════════════════
# BUG TOOLS
# ═══════════════════════════════════════════════════════════

def qa_add_bug(
    name: str,
    query: str,
    expected_behavior: str,
    actual_behavior: str,
    severity: str = "high"
) -> dict:
    """
    Add a known bug to the regression database.
    
    This bug will be tested every time the regression suite runs.
    """
    v = _get_validator()
    bug_id = v._db.generate_bug_id()
    v._db.store_bug({
        "id": bug_id,
        "name": name,
        "query": query,
        "expected_behavior": expected_behavior,
        "actual_behavior": actual_behavior,
        "severity": severity,
    })
    return {"bug_id": bug_id, "name": name}

def qa_add_bug_from_last(name: str, expected_behavior: str) -> dict:
    """
    Create a bug from the last failed QA report.
    
    Automatically populates query, actual behavior, and affected assertions.
    """
    v = _get_validator()
    report = v.get_last_report()
    
    if not report:
        return {"error": "No reports available"}
    
    bug_id = v._db.generate_bug_id()
    
    # Handle both object and dict forms
    if hasattr(report, 'query'):
        query = report.query
        actual = report.context.final_response[:500]
        assertions = [a.id for a in report.failed_assertions]
    else:
        query = report["query"]
        actual = report["context"]["final_response"][:500]
        assertions = [a["id"] for a in report["assertions"] if not a["passed"]]
    
    v._db.store_bug({
        "id": bug_id,
        "name": name,
        "query": query,
        "expected_behavior": expected_behavior,
        "actual_behavior": actual,
        "affected_assertions": assertions,
    })
    
    return {"bug_id": bug_id, "query": query}

def qa_list_bugs(status: str = None) -> list[dict]:
    """
    List known bugs.
    
    Args:
        status: Filter by status (open, failing, fixed, wontfix)
    """
    v = _get_validator()
    if status:
        return v._db.get_bugs_by_status(status)
    return v._db.get_all_bugs()

def qa_update_bug_status(bug_id: str, status: str) -> dict:
    """Update a bug's status."""
    _get_validator()._db.update_bug_status(bug_id, status)
    return {"bug_id": bug_id, "status": status}

# ═══════════════════════════════════════════════════════════
# TEST TOOLS
# ═══════════════════════════════════════════════════════════

async def qa_run_regression() -> dict:
    """
    Run the full regression test suite.
    
    Tests all known bugs against the current system.
    """
    v = _get_validator()
    bugs = v._db.get_all_bugs()
    
    # Import here to avoid circular
    from luna.actors.director import Director
    director = Director()
    
    results = []
    for bug in bugs:
        if bug.get("status") == "wontfix":
            continue
        
        response = await director.process_with_qa(bug["query"])
        report = v.get_last_report()
        passed = report.passed if hasattr(report, 'passed') else report["passed"]
        
        v._db.update_bug_test_result(bug["id"], passed, response)
        
        results.append({
            "bug_id": bug["id"],
            "name": bug["name"],
            "passed": passed,
        })
    
    passed_count = sum(1 for r in results if r["passed"])
    return {
        "total": len(results),
        "passed": passed_count,
        "failed": len(results) - passed_count,
        "results": results,
    }

async def qa_run_single_bug(bug_id: str) -> dict:
    """Test a single bug against current system."""
    v = _get_validator()
    bugs = v._db.get_all_bugs()
    bug = next((b for b in bugs if b["id"] == bug_id), None)
    
    if not bug:
        return {"error": f"Bug {bug_id} not found"}
    
    from luna.actors.director import Director
    director = Director()
    
    response = await director.process_with_qa(bug["query"])
    report = v.get_last_report()
    passed = report.passed if hasattr(report, 'passed') else report["passed"]
    
    v._db.update_bug_test_result(bug_id, passed, response)
    
    return {
        "bug_id": bug_id,
        "passed": passed,
        "response": response,
        "failed_assertions": [a["id"] for a in report["assertions"] if not a["passed"]] if isinstance(report, dict) else [a.id for a in report.failed_assertions],
    }

async def qa_simulate_query(query: str) -> dict:
    """
    Run a query through the system and return full QA report.
    
    Use this to test if a specific query would pass or fail.
    """
    from luna.actors.director import Director
    director = Director()
    
    await director.process_with_qa(query)
    report = _get_validator().get_last_report()
    
    return report.to_dict() if hasattr(report, 'to_dict') else report


# ═══════════════════════════════════════════════════════════
# TOOL REGISTRATION
# ═══════════════════════════════════════════════════════════

def get_qa_tools() -> list:
    """Return all QA tools for MCP registration."""
    return [
        # Read
        ("qa_get_last_report", qa_get_last_report),
        ("qa_get_health", qa_get_health),
        ("qa_search_reports", qa_search_reports),
        ("qa_get_stats", qa_get_stats),
        ("qa_get_assertion_list", qa_get_assertion_list),
        # Write
        ("qa_add_assertion", qa_add_assertion),
        ("qa_toggle_assertion", qa_toggle_assertion),
        ("qa_delete_assertion", qa_delete_assertion),
        # Bugs
        ("qa_add_bug", qa_add_bug),
        ("qa_add_bug_from_last", qa_add_bug_from_last),
        ("qa_list_bugs", qa_list_bugs),
        ("qa_update_bug_status", qa_update_bug_status),
        # Test
        ("qa_run_regression", qa_run_regression),
        ("qa_run_single_bug", qa_run_single_bug),
        ("qa_simulate_query", qa_simulate_query),
    ]
```

**Register in MCP:**

Add to `src/luna/mcp/tools.py`:
```python
from luna.qa.mcp_tools import get_qa_tools

# In tool registration
for name, fn in get_qa_tools():
    register_tool(name, fn)
```

---

## Phase 5: Frontend Integration (P1)

Copy components from prototype (`luna-qa-v2.jsx`) into:
```
frontend/src/components/LunaQA/
├── LunaQATab.jsx       # Main container
├── LiveView.jsx        # Real-time report
├── HistoryView.jsx     # Past reports
├── StatsView.jsx       # Statistics
├── SimulateView.jsx    # Bug replay
├── TestSuiteView.jsx   # Regression runner
└── AssertionBuilder.jsx # No-code scaffolding
```

Add to main navigation in `App.jsx`:
```jsx
import LunaQATab from './components/LunaQA/LunaQATab';

// In nav
<NavItem to="/qa" icon="🔬" label="Luna QA" badge={failureCount} />

// In routes
<Route path="/qa" element={<LunaQATab />} />
```

---

## File Checklist

### Create
- [ ] `src/luna/qa/__init__.py`
- [ ] `src/luna/qa/context.py`
- [ ] `src/luna/qa/assertions.py`
- [ ] `src/luna/qa/validator.py`
- [ ] `src/luna/qa/database.py`
- [ ] `src/luna/qa/mcp_tools.py`
- [ ] `frontend/src/components/LunaQA/LunaQATab.jsx`
- [ ] `frontend/src/components/LunaQA/LiveView.jsx`
- [ ] `frontend/src/components/LunaQA/HistoryView.jsx`
- [ ] `frontend/src/components/LunaQA/StatsView.jsx`
- [ ] `frontend/src/components/LunaQA/SimulateView.jsx`
- [ ] `frontend/src/components/LunaQA/TestSuiteView.jsx`
- [ ] `frontend/src/components/LunaQA/AssertionBuilder.jsx`

### Modify
- [ ] `src/luna/actors/director.py` — Add instrumentation
- [ ] `src/luna/api/server.py` — Add QA endpoints
- [ ] `src/luna/mcp/tools.py` — Register QA tools
- [ ] `frontend/src/App.jsx` — Add QA tab

---

## Testing Strategy

### Unit Tests
```python
# test_assertions.py
def test_no_claude_isms_passes():
    ctx = InferenceContext(final_response="Hey! How's it going?")
    result = check_no_claude_isms(ctx, ASSERTIONS["V1"])
    assert result.passed

def test_no_claude_isms_fails():
    ctx = InferenceContext(final_response="Let me look into that for you.")
    result = check_no_claude_isms(ctx, ASSERTIONS["V1"])
    assert not result.passed
    assert "Let me look into" in result.actual
```

### Integration Tests
```python
# test_qa_flow.py
async def test_full_qa_flow():
    director = Director()
    
    # Run query
    response = await director.process_with_qa("hey luna")
    
    # Check report was created
    report = qa_validator.get_last_report()
    assert report is not None
    assert report.query == "hey luna"
    
    # Check diagnosis if failed
    if not report.passed:
        assert report.diagnosis is not None
```

### Regression Tests
```python
# test_regression.py
async def test_known_bugs():
    results = await qa_run_regression()
    
    # BUG-001 should fail until fix is deployed
    bug_001 = next(r for r in results["results"] if r["bug_id"] == "BUG-001")
    # Once fixed, change to: assert bug_001["passed"]
    assert not bug_001["passed"]  # Currently known broken
```

---

## Success Criteria

1. **Every inference validated** — No blind spots
2. **Reports stored** — Can query history
3. **Diagnosis actionable** — Points to code location
4. **MCP tools work** — Luna can self-diagnose
5. **Regression suite runs** — All bugs tested
6. **No performance hit** — <50ms validation overhead

---

## Notes

- QA database is separate from Memory Matrix
- Validator is singleton per process
- Reports keep full context for debugging
- MCP tools are async where needed
- Frontend polls or uses WebSocket

---

*Go build it. Luna needs to see herself.*
