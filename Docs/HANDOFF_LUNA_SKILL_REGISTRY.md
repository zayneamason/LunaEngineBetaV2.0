# HANDOFF SPEC: Luna Skill Registry + Widget Anchor System

**A local-first capability layer that routes structured tasks to specialist tools, bypassing LLM inference for deterministic work — and spawns rich UI widgets inline in chat to display results.**

| Field | Value |
|-------|-------|
| **Owner** | Ahab (architecture) + Luna (stakeholder) + Dude (design) |
| **Depends On** | `tools/registry.py`, `agentic/router.py`, `actors/director.py`, `tools/eden_tools.py`, `diagnostics/health.py`, `frontend/src/components/ChatPanel.jsx`, `frontend/src/hooks/useChat.js` |
| **Enables** | Math/logic computation, document reading, structured formatting, system diagnostics, Eden media generation, memory analytics — all with inline chat widgets |
| **New Files (backend)** | `src/luna/skills/` (~700 lines) |
| **New Files (frontend)** | `frontend/src/components/WidgetAnchor.jsx` (~200 lines) + widget subcomponents |
| **Files Modified (backend)** | `actors/director.py` (~35 lines), `agentic/router.py` (~30 lines) |
| **Files Modified (frontend)** | `hooks/useChat.js` (~6 lines), `components/ChatPanel.jsx` (~5 lines) |
| **Config** | `config/skills.yaml` (new) |
| **New Deps** | `katex` (frontend, LaTeX rendering ~30kb) |
| **Risk Level** | Low — fully additive, graceful fallthrough on any error, zero impact on non-skill queries |

---

## 1. What the System Is

Two layers, tightly coupled:

**Backend — Skill Registry:** Capability shortcuts that fire between intent detection and LLM generation. When Luna detects a skill-shaped request, she dispatches to a deterministic executor instead of generating from weights. Zero LLM calls for the compute part. Luna narrates the result.

**Frontend — Widget Anchor System:** When a skill fires, the response metadata carries a `widget` descriptor. `ChatPanel` renders a `<WidgetAnchor>` component inline below the message bubble. Each skill type maps to a purpose-built widget: rendered LaTeX, truth tables, document viewers, health dashboards, inline images, bar charts.

**Combined loop:**
```
User message
    ↓
SkillDetector.detect(message) → skill_name | None
    ↓ if skill detected
SkillRegistry.execute(skill_name, message, context) → SkillResult
    ↓
Director: inject narration context + attach widget descriptor to response_metadata
LunaScript snaps to PRECISION geometry
    ↓
Local Qwen narrates result in Luna's voice
    ↓
/persona/stream onDone → result.metadata.widget
    ↓
useChat.onDone attaches widget to message object
    ↓
ChatPanel: msg.widget → <WidgetAnchor widget={msg.widget} />
    ↓
User sees Luna's narration + inline rendered widget
```

**If skill unavailable** (lib not installed, execution error, parse failure): `fallthrough=True` → normal Director routing. No widget. Zero user impact.

---

## 2. Architecture Principle

```
EXISTING SYSTEM              SKILLS RELATIONSHIP
═══════════════              ═══════════════════
ToolRegistry            ←── WRAPS for execution + timeout
QueryRouter             ←── EXTENDED with skill signal detection (logging only)
Director.process()      ←── DISPATCHES skills before LLM routing
eden_tools.py           ←── USED DIRECTLY by EdenSkill (no reimplementation)
diagnostics/health.py   ←── USED DIRECTLY by DiagnosticSkill (no reimplementation)
LunaScript              ←── RECEIVES geometry override via framed_context injection
ChatPanel.jsx           ←── RENDERS <WidgetAnchor> below message bubble
useChat.js              ←── PASSES widget field through message object
```

Skills are **NOT** agentic tools. No confirmation flows, no multi-step planning. Synchronous fire-and-narrate-and-render.

---

## 3. Backend — Directory Structure

```
src/luna/skills/
    __init__.py
    registry.py          ← SkillRegistry + register_defaults()
    base.py              ← Skill ABC + SkillResult dataclass
    detector.py          ← SKILL_PATTERNS + SKILL_PRIORITY + SkillDetector
    config.py            ← SkillsConfig.from_yaml()

    math/
        __init__.py
        skill.py         ← MathSkill (sympy)

    logic/
        __init__.py
        skill.py         ← LogicSkill (sympy.logic)

    formatting/
        __init__.py
        skill.py         ← FormattingSkill (pure string)

    reading/
        __init__.py
        skill.py         ← ReadingSkill (markitdown / pypdf fallback)

    diagnostic/
        __init__.py
        skill.py         ← DiagnosticSkill (wraps health.py)

    eden/
        __init__.py
        skill.py         ← EdenSkill (wraps eden_tools.py)

    analytics/
        __init__.py
        skill.py         ← AnalyticsSkill (sqlite3 + optional pandas)
```

---

## 4. Core Backend Interface

### 4.1 `SkillResult` — unified return type

```python
@dataclass
class SkillResult:
    success: bool
    skill_name: str
    result: Any                    # Raw output (sympy obj, health dict, etc.)
    result_str: str                # Human-readable — Luna narrates this
    latex: Optional[str] = None    # LaTeX repr (math/logic only)
    data: Optional[dict] = None    # Structured data passed to frontend widget
    error: Optional[str] = None
    execution_ms: float = 0.0
    fallthrough: bool = False      # True = skill declined, route normally
```

`result.data` is the widget payload. Each skill populates it specifically — see per-skill specs below.

### 4.2 `Skill` — base class

```python
class Skill(ABC):
    name: str
    description: str
    triggers: list[str]            # Regex patterns for SkillDetector

    @abstractmethod
    async def execute(self, query: str, context: dict) -> SkillResult: ...

    def is_available(self) -> bool:
        return True

    def narration_hint(self, result: SkillResult) -> str:
        return ""
```

### 4.3 `SkillRegistry`

```python
class SkillRegistry:
    def __init__(self, config: SkillsConfig)
    def register(self, skill: Skill) -> None
    def get(self, name: str) -> Optional[Skill]
    def list_available(self) -> list[str]
    def register_defaults(self) -> None        # Registers all 7 built-in skills

    async def execute(
        self,
        skill_name: str,
        query: str,
        context: dict = None,
    ) -> SkillResult:
        # asyncio.wait_for() with config.max_execution_ms
        # On any exception → SkillResult(success=False, fallthrough=True, error=str(e))
```

### 4.4 `SkillDetector`

```python
class SkillDetector:
    def detect(self, message: str) -> Optional[str]:
        """First match in SKILL_PRIORITY order."""

    def detect_all(self, message: str) -> list[str]:
        """All matching skill names (debug)."""
```

---

## 5. Skill Specifications

### 5.1 MathSkill

| Field | Value |
|-------|-------|
| **name** | `math` |
| **lib** | `sympy` |
| **install** | `pip install sympy` |
| **local** | Yes |
| **overhead** | 5–50ms |
| **widget** | `latex` |

**Triggers:**
```python
[
    r"\b(solve|factor|simplify|expand|integrate|differentiate|derivative|integral)\b",
    r"\b(equation|polynomial|eigenvalue|matrix determinant)\b",
    r"\b(calculate|compute)\b.{0,30}\b(exact|symbolic|algebraic)\b",
]
```

**Execute logic:**
```python
async def execute(self, query: str, context: dict) -> SkillResult:
    # 1. Extract math expression via regex
    # 2. sympy.parse_expr() or sympy.sympify()
    # 3. Route by verb:
    #    solve         → sympy.solve(expr)
    #    integrate     → sympy.integrate(expr)
    #    differentiate → sympy.diff(expr)
    #    factor        → sympy.factor(expr)
    #    simplify      → sympy.simplify(expr)
    #    expand        → sympy.expand(expr)
    # 4. sympy.latex(result) → latex field
    # 5. result.data = {"latex": latex_str, "result_str": str(result), "operation": verb}
```

**Narration hint:** `"The exact symbolic result is shown below. Narrate it conversationally. Mention what operation was performed. Don't repeat the formula in words."`

---

### 5.2 LogicSkill

| Field | Value |
|-------|-------|
| **name** | `logic` |
| **lib** | `sympy.logic`; `kanren` optional |
| **install** | sympy already required; `pip install kanren` optional |
| **local** | Yes |
| **overhead** | 2–20ms |
| **widget** | `table` |

**Triggers:**
```python
[
    r"\b(prove|disprove|truth table|tautology|contradiction|satisfiable|entails)\b",
    r"\b(implies|if.*then|therefore|thus)\b.{0,30}\b(prove|show|check)\b",
    r"\b(AND|OR|NOT|XOR|NAND|NOR)\b",
    r"\b(logical|propositional|boolean)\b.{0,20}\b(expression|formula|statement)\b",
]
```

**Execute logic:**
```python
async def execute(self, query: str, context: dict) -> SkillResult:
    # 1. Parse boolean expression from query
    # 2. Route by verb:
    #    "truth table"  → sympy.logic.boolalg.truth_table(expr, vars)
    #    "satisfiable"  → sympy.logic.satisfiable(expr)
    #    "tautology"    → satisfiable(~expr) == False
    #    "simplify"     → sympy.logic.simplify_logic(expr)
    #    "prove X → Y"  → satisfiable(X & ~Y) == False
    # 3. result.data = {
    #      "headers": ["A", "B", "A AND B"],
    #      "rows": [[True, True, True], [True, False, False], ...],
    #      "verdict": "satisfiable" | "tautology" | "contradiction" | None
    #    }
```

---

### 5.3 FormattingSkill

| Field | Value |
|-------|-------|
| **name** | `formatting` |
| **lib** | none |
| **local** | Yes |
| **overhead** | <1ms |
| **widget** | `None` — inline text only |

**Triggers:**
```python
[
    r"\b(make|create|format|organize|structure)\b.{0,20}\b(list|bullet|outline|table)\b",
    r"\b(bullet points?|numbered list|table of|outline for)\b",
    r"\b(summarize|structure).{0,20}\b(as|into)\b.{0,20}\b(list|points|bullets)\b",
]
```

**Execute logic:**
```python
async def execute(self, query: str, context: dict) -> SkillResult:
    # If content present in context["content"] or parseable from query:
    #   apply format template, return result_str, no widget needed
    # If content must be generated:
    #   fallthrough=True — Director injects "Format response as {type}" into system_prompt
```

No widget. Formatting output appears directly in the message bubble as styled markdown.

---

### 5.4 ReadingSkill

| Field | Value |
|-------|-------|
| **name** | `reading` |
| **lib** | `markitdown`; `pypdf` + `python-docx` fallback |
| **install** | `pip install markitdown` |
| **local** | Yes |
| **overhead** | 50–500ms |
| **widget** | `document` |

**Triggers:**
```python
[
    r"\b(read|open|parse|extract|load)\b.{0,30}\.(pdf|docx|doc|xlsx|pptx|txt|md)\b",
    r"\b(summarize|analyze)\b.{0,20}\b(file|document|pdf|doc)\b",
    r"\bwhat('?s| is) in\b.{0,30}\.(pdf|docx|doc)\b",
]
```

**Execute logic:**
```python
async def execute(self, query: str, context: dict) -> SkillResult:
    # 1. Extract + validate file path
    # 2. markitdown.convert(path) → Markdown text
    # 3. Truncate to config.max_chars
    # 4. result.data = {
    #      "file_path": path,
    #      "file_name": basename,
    #      "char_count": n,
    #      "content": text,          # full extracted text (truncated)
    #      "preview": text[:500],    # first 500 chars for widget header
    #    }
    # 5. If store_to_memory: emit DOCUMENT node to Scribe (fire-and-forget)
```

---

### 5.5 DiagnosticSkill

| Field | Value |
|-------|-------|
| **name** | `diagnostic` |
| **lib** | `diagnostics/health.py` — already exists |
| **local** | Yes |
| **overhead** | 10–50ms |
| **widget** | `diagnostic` |

**Triggers:**
```python
[
    r"\b(health|status|diagnostic|diagnostics)\b",
    r"\b(how('?s| is).{0,10}(memory|database|system|engine|extraction))\b",
    r"\b(is.{0,10}(working|running|okay|broken|degraded))\b",
    r"\b(check.{0,10}(system|components|everything))\b",
    r"\b(what('?s| is) wrong|something('?s| is) broken)\b",
]
```

**Execute logic:**
```python
from luna.diagnostics.health import HealthChecker

async def execute(self, query: str, context: dict) -> SkillResult:
    # 1. Map query → scope (single component or check_all())
    # 2. result.data = {
    #      "components": [
    #        {"name": "database", "status": "healthy", "message": "...", "metrics": {...}},
    #        {"name": "memory_matrix", "status": "degraded", ...},
    #        ...
    #      ],
    #      "overall": "healthy" | "degraded" | "broken"
    #    }
```

**Narration hint:** `"Luna reports her own system health. First-person: 'my memory matrix...', 'I'm seeing...'. Direct about problems."`

---

### 5.6 EdenSkill

| Field | Value |
|-------|-------|
| **name** | `eden` |
| **lib** | `tools/eden_tools.py` |
| **local** | No — Eden.art API |
| **overhead** | 2–180s |
| **widget** | `image` or `video` |

**Triggers:**
```python
[
    r"\b(generate|create|make|draw|paint|render)\b.{0,30}\b(image|picture|photo|art|illustration|portrait)\b",
    r"\b(image|picture|photo)\b.{0,20}\bof\b",
    r"\b(generate|create|make)\b.{0,30}\b(video|animation|clip)\b",
    r"\beden\b.{0,20}\b(create|generate|make|chat)\b",
    r"\b(show me|visualize|illustrate)\b",
]
```

**Execute logic:**
```python
async def execute(self, query: str, context: dict) -> SkillResult:
    # Route: image → eden_create_image(), video → eden_create_video()
    # result.data = {
    #   "url": task.first_output_url,
    #   "task_id": task.id,
    #   "type": "image" | "video",
    #   "prompt": extracted_prompt,
    # }
```

**is_available():** `return eden_tools.get_eden_adapter() is not None`

**Narration hint:** `"Media was generated — show URL naturally. Express curiosity about whether it matched the vision."`

---

### 5.7 AnalyticsSkill

| Field | Value |
|-------|-------|
| **name** | `analytics` |
| **lib** | `sqlite3` + optional `pandas` |
| **local** | Yes |
| **overhead** | 5–100ms |
| **widget** | `chart` |

**Two modes:**

**Mode A — Luna's own memory analytics:**
```python
SELF_ANALYTICS_QUERIES = {
    "memory_summary":       "SELECT node_type, COUNT(*) FROM memory_nodes GROUP BY node_type",
    "session_stats":        "SELECT COUNT(*), AVG(turns_count) FROM sessions",
    "recent_topics":        "SELECT content FROM memory_nodes ORDER BY created_at DESC LIMIT 20",
    "delegation_quality":   "SELECT delta_class, COUNT(*) FROM lunascript_delegation_log GROUP BY delta_class",
    "lock_in_distribution": "SELECT lock_in_state, COUNT(*) FROM memory_nodes GROUP BY lock_in_state",
    "entity_count":         "SELECT entity_type, COUNT(*) FROM entities GROUP BY entity_type",
}
```

**Mode B — Data analytics** (`pandas`): user-provided CSV/JSON in `context["data"]`.

**Execute logic:**
```python
async def execute(self, query: str, context: dict) -> SkillResult:
    # result.data = {
    #   "chart_type": "bar" | "line" | "pie",
    #   "labels": [...],
    #   "values": [...],
    #   "title": "Memory Node Distribution",
    #   "raw": {...}    # full query result
    # }
```

**Triggers:**
```python
[
    r"\b(how many|count|statistics|stats|summary)\b.{0,30}\b(memories|nodes|sessions|entities)\b",
    r"\b(memory|session|delegation).{0,10}(stats|statistics|summary|overview|health)\b",
    r"\b(analyze|analyse)\b.{0,20}\b(this|the)\b.{0,20}\b(data|dataset|csv|numbers)\b",
    r"\b(mean|median|average|correlation|distribution)\b.{0,20}\b(of|for|in)\b",
    r"\bhow.{0,20}(is|are).{0,20}(performing|doing|running)\b",
]
```

---

## 6. Detector Pattern Map (full)

```python
# skills/detector.py

SKILL_PATTERNS: dict[str, list[str]] = {
    "math": [
        r"\b(solve|factor|simplify|expand|integrate|differentiate|derivative|integral)\b",
        r"\b(equation|polynomial|eigenvalue|matrix determinant)\b",
        r"\b(calculate|compute)\b.{0,30}\b(exact|symbolic|algebraic)\b",
    ],
    "logic": [
        r"\b(truth table|tautology|contradiction|satisfiable|entails)\b",
        r"\b(prove|disprove).{0,30}\b(implies|therefore|follows)\b",
        r"\b(AND|OR|NOT|XOR)\b.{0,30}\b(expression|formula)\b",
    ],
    "formatting": [
        r"\b(bullet points?|numbered list|outline for|table of)\b",
        r"\b(format|organize|structure)\b.{0,20}\b(as|into)\b.{0,20}\b(list|bullets|table)\b",
    ],
    "reading": [
        r"\b(read|open|parse|extract)\b.{0,30}\.(pdf|docx|doc|xlsx|pptx)\b",
        r"\b(what('?s| is) in|summarize|load)\b.{0,20}\b.{0,10}\.(pdf|doc)\b",
    ],
    "diagnostic": [
        r"\b(health check|system status|diagnostics?)\b",
        r"\b(how('?s| is).{0,10}(memory|database|system|engine))\b",
        r"\b(is.{0,10}(everything|system|database).{0,10}(okay|working|broken))\b",
    ],
    "eden": [
        r"\b(generate|create|make|draw|paint|render)\b.{0,30}\b(image|picture|art|illustration)\b",
        r"\b(generate|create|make)\b.{0,30}\b(video|animation)\b",
        r"\beden\b",
    ],
    "analytics": [
        r"\b(how many|count).{0,30}\b(memories|nodes|sessions|entities)\b",
        r"\b(memory|session|delegation).{0,10}(stats|statistics|summary|overview)\b",
        r"\b(analyze|analyse)\b.{0,20}\bdata\b",
    ],
}

SKILL_PRIORITY = ["diagnostic", "math", "logic", "reading", "eden", "formatting", "analytics"]
```

---

## 7. Director Integration (exact changes)

**Skill-to-widget type map — add near top of `director.py`:**
```python
SKILL_WIDGET_TYPES = {
    "math":       "latex",
    "logic":      "table",
    "formatting": None,       # inline only, no widget
    "reading":    "document",
    "diagnostic": "diagnostic",
    "eden":       "image",    # or "video" — EdenSkill sets type in result.data
    "analytics":  "chart",
}

SKILL_GEOMETRY_OVERRIDES = {
    "math":        {"max_sent": 6,  "question_req": False, "tangent": False},
    "logic":       {"max_sent": 8,  "question_req": False, "tangent": False},
    "formatting":  {"max_sent": 4,  "question_req": False, "tangent": False},
    "reading":     {"max_sent": 12, "question_req": True,  "tangent": True},
    "diagnostic":  {"max_sent": 8,  "question_req": False, "tangent": False},
    "eden":        {"max_sent": 4,  "question_req": False, "tangent": False},
    "analytics":   {"max_sent": 10, "question_req": True,  "tangent": True},
}
```

**In `process()`, after intent classification, before `_should_delegate()` (~line 920):**
```python
# ── Skill Registry ───────────────────────────────────────────────────
_skill_result = None
if self._skill_registry:
    try:
        skill_name = self._skill_registry.detector.detect(message)
        if skill_name:
            _skill_result = await self._skill_registry.execute(
                skill_name, message,
                context={"db": db, "memories": memories, "history": conversation_history}
            )
            logger.info(
                f"[SKILL] {skill_name} → success={_skill_result.success} "
                f"fallthrough={_skill_result.fallthrough} ms={_skill_result.execution_ms:.0f}"
            )
    except Exception as e:
        logger.debug(f"[SKILL] Dispatch error: {e}")

if _skill_result and _skill_result.success and not _skill_result.fallthrough:
    skill = self._skill_registry.get(_skill_result.skill_name)
    hint = skill.narration_hint(_skill_result) if skill else ""
    geo = SKILL_GEOMETRY_OVERRIDES.get(_skill_result.skill_name, {})

    framed_context += (
        f"\n\n## SKILL RESULT ({_skill_result.skill_name.upper()})\n"
        f"```\n{_skill_result.result_str}\n```\n"
        f"Narrate this result in Luna's voice. {hint}"
    )
    if geo:
        framed_context += (
            f"\n\n## CONVERSATIONAL POSTURE (skill override)\n"
            f"Max sentences: {geo['max_sent']}. "
            + ("End with a question. " if geo.get("question_req") else "No question required. ")
            + ("No tangents." if not geo.get("tangent") else "Tangents okay.")
        )

    # Attach widget descriptor to response metadata for frontend
    widget_type = SKILL_WIDGET_TYPES.get(_skill_result.skill_name)
    if widget_type and _skill_result.data:
        # EdenSkill can override type to "video"
        actual_type = _skill_result.data.get("type", widget_type)
        response_metadata["widget"] = {
            "type": actual_type,
            "skill": _skill_result.skill_name,
            "data": _skill_result.data,
            "latex": _skill_result.latex,
        }

    should_delegate = False
    route_decision = f"skill:{_skill_result.skill_name}"
    route_reason = "skill_dispatch"
```

**In `__init__`:**
```python
self._skill_registry: Optional["SkillRegistry"] = None
```

**In `_init_entity_context()`, after LunaScript init:**
```python
try:
    from luna.skills import SkillRegistry
    from luna.skills.config import SkillsConfig
    skills_config_path = Path(__file__).parent.parent.parent.parent / "config" / "skills.yaml"
    skills_config = SkillsConfig.from_yaml(skills_config_path)
    if skills_config.enabled:
        self._skill_registry = SkillRegistry(skills_config)
        self._skill_registry.register_defaults()
        logger.info(f"[SKILLS] Initialized: {self._skill_registry.list_available()}")
except ImportError:
    logger.debug("[SKILLS] Module not available")
except Exception as e:
    logger.warning(f"[SKILLS] Init failed: {e}")
```

---

## 8. Router Integration (exact changes)

**In `agentic/router.py`, add to `TOOL_PATTERNS`:**
```python
"math_skill":       [r"\b(solve|factor|simplify|integrate|differentiate)\b"],
"logic_skill":      [r"\b(truth table|tautology|satisfiable|prove)\b"],
"formatting_skill": [r"\b(bullet points?|numbered list|outline for)\b"],
"reading_skill":    [r"\.(pdf|docx|doc|xlsx|pptx)\b"],
"diagnostic_skill": [r"\b(health check|system status|diagnostics?)\b"],
"eden_skill":       [r"\b(generate|create)\b.{0,30}\b(image|video|art)\b"],
"analytics_skill":  [r"\b(memory|session).{0,10}(stats|summary)\b"],
```

**In `_detect_signals()`:**
```python
for skill_key in [
    "math_skill", "logic_skill", "formatting_skill",
    "reading_skill", "diagnostic_skill", "eden_skill", "analytics_skill"
]:
    patterns = self.TOOL_PATTERNS.get(skill_key, [])
    if self._matches_any(query, [re.compile(p, re.IGNORECASE) for p in patterns]):
        signals.append(skill_key)
```

---

## 9. Frontend — Widget Anchor System

### 9.1 Data flow through frontend

**`useChat.js` — `onDone` handler (~6 lines added):**
```javascript
onDone: (result) => {
    setMessages((prev) =>
        prev.map((m) =>
            m.id === assistantMsgId
                ? {
                    ...m,
                    content: result.response || streamingRef.current,
                    streaming: false,
                    // ... existing fields ...
                    widget: result.metadata?.widget || null,   // ← ADD THIS
                  }
                : m
        )
    );
}
```

**`ChatPanel.jsx` — inside message map (~5 lines added):**
```jsx
{/* After the message bubble div, before KnowledgeBar */}
{msg.widget && !msg.streaming && (
    <WidgetAnchor widget={msg.widget} />
)}
```

Import at top:
```jsx
import WidgetAnchor from './WidgetAnchor';
```

---

### 9.2 `WidgetAnchor.jsx` — new component

**Location:** `frontend/src/components/WidgetAnchor.jsx`

**Responsibility:** Receives a `widget` object, routes to the correct sub-widget by `widget.type`.

```jsx
// Widget type → component map
const WIDGET_COMPONENTS = {
    latex:      LaTeXWidget,
    table:      TableWidget,
    document:   DocumentWidget,
    diagnostic: DiagnosticWidget,
    image:      ImageWidget,
    video:      VideoWidget,
    chart:      ChartWidget,
};

export default function WidgetAnchor({ widget }) {
    if (!widget?.type) return null;
    const Component = WIDGET_COMPONENTS[widget.type];
    if (!Component) return null;

    return (
        <div className="mt-2 ml-0 max-w-[80%]">
            <Component data={widget.data} latex={widget.latex} skill={widget.skill} />
        </div>
    );
}
```

Anchors left-aligned to match assistant bubble position. Max width matches the bubble.

---

### 9.3 Widget Sub-Components

All widgets share a common shell: rounded border, `bg-kozmo-surface`, subtle accent-colored left border, collapse toggle. Style matches existing GlassCard / eclissi widget aesthetic.

```jsx
// Shared shell
function WidgetShell({ title, icon, children, collapsible = true }) {
    const [open, setOpen] = useState(true);
    return (
        <div style={{
            borderRadius: 8,
            border: '1px solid rgba(192,132,252,0.2)',
            borderLeft: '3px solid rgba(192,132,252,0.5)',
            background: 'rgba(255,255,255,0.03)',
            overflow: 'hidden',
        }}>
            <div
                onClick={() => collapsible && setOpen(o => !o)}
                style={{ cursor: collapsible ? 'pointer' : 'default', padding: '8px 12px',
                         display: 'flex', alignItems: 'center', gap: 8 }}
            >
                <span>{icon}</span>
                <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.5)', fontFamily: 'monospace' }}>
                    {title}
                </span>
                {collapsible && (
                    <span style={{ marginLeft: 'auto', fontSize: 10, color: 'rgba(255,255,255,0.3)' }}>
                        {open ? '▲' : '▼'}
                    </span>
                )}
            </div>
            {open && <div style={{ padding: '0 12px 12px' }}>{children}</div>}
        </div>
    );
}
```

#### `LaTeXWidget` (skill: math)
- Renders `data.latex` using `katex.renderToString()`
- Falls back to `data.result_str` in a `<code>` block if KaTeX fails
- Shows operation performed: `"Solved for x"`, `"Integrated"`, etc.
- **Dep:** `npm install katex` + import `katex/dist/katex.min.css`

```jsx
function LaTeXWidget({ data, latex }) {
    const html = useMemo(() => {
        try { return katex.renderToString(latex || data?.latex || '', { displayMode: true }); }
        catch { return null; }
    }, [latex, data]);

    return (
        <WidgetShell title={`${data?.operation || 'result'} · math`} icon="∑">
            {html
                ? <div dangerouslySetInnerHTML={{ __html: html }} style={{ color: 'rgba(255,255,255,0.85)' }} />
                : <code style={{ fontSize: 12 }}>{data?.result_str}</code>
            }
        </WidgetShell>
    );
}
```

#### `TableWidget` (skill: logic)
- Renders `data.headers` + `data.rows` as styled `<table>`
- `true` → green cell, `false` → dim cell
- Shows `data.verdict` badge if present: `TAUTOLOGY`, `SATISFIABLE`, `CONTRADICTION`

```jsx
function TableWidget({ data }) {
    return (
        <WidgetShell title={`truth table · logic${data?.verdict ? ` · ${data.verdict}` : ''}`} icon="⊨">
            <table style={{ fontSize: 11, borderCollapse: 'collapse', width: '100%' }}>
                <thead>
                    <tr>{data.headers.map(h => (
                        <th key={h} style={{ padding: '4px 8px', color: 'rgba(192,132,252,0.8)',
                                             borderBottom: '1px solid rgba(255,255,255,0.1)', textAlign: 'center' }}>
                            {h}
                        </th>
                    ))}</tr>
                </thead>
                <tbody>
                    {data.rows.map((row, i) => (
                        <tr key={i}>{row.map((cell, j) => (
                            <td key={j} style={{ padding: '3px 8px', textAlign: 'center',
                                                  color: cell === true ? '#34d399' : cell === false ? 'rgba(255,255,255,0.25)' : 'rgba(255,255,255,0.7)' }}>
                                {String(cell)}
                            </td>
                        ))}</tr>
                    ))}
                </tbody>
            </table>
        </WidgetShell>
    );
}
```

#### `DocumentWidget` (skill: reading)
- Shows `data.file_name` + `data.char_count` in header
- Displays `data.preview` (first 500 chars) by default
- Expand button reveals full `data.content` in scrollable pre block (max 300px height)

```jsx
function DocumentWidget({ data }) {
    const [expanded, setExpanded] = useState(false);
    return (
        <WidgetShell title={`${data?.file_name || 'document'} · ${data?.char_count?.toLocaleString() || '?'} chars`} icon="📄">
            <pre style={{ fontSize: 11, color: 'rgba(255,255,255,0.6)', whiteSpace: 'pre-wrap',
                          maxHeight: expanded ? 300 : 80, overflow: 'hidden', margin: 0 }}>
                {expanded ? data?.content : data?.preview}
            </pre>
            <button onClick={() => setExpanded(e => !e)}
                style={{ marginTop: 6, fontSize: 10, color: 'rgba(192,132,252,0.6)',
                         background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}>
                {expanded ? '▲ collapse' : `▼ expand (${data?.char_count?.toLocaleString()} chars)`}
            </button>
        </WidgetShell>
    );
}
```

#### `DiagnosticWidget` (skill: diagnostic)
- Renders a component grid: one row per component in `data.components`
- Status → emoji + color: `healthy` → ✅ green, `degraded` → ⚠️ amber, `broken` → ❌ red, `unknown` → ❓ gray
- Expandable metrics panel per component (click row to expand)

```jsx
const STATUS_CONFIG = {
    healthy:  { icon: '✅', color: '#34d399' },
    degraded: { icon: '⚠️', color: '#fbbf24' },
    broken:   { icon: '❌', color: '#f87171' },
    unknown:  { icon: '❓', color: '#6b7280' },
};

function DiagnosticWidget({ data }) {
    const [expanded, setExpanded] = useState(null);
    return (
        <WidgetShell title={`system health · ${data?.overall || 'unknown'}`} icon="🔬">
            {data?.components?.map((c) => {
                const cfg = STATUS_CONFIG[c.status] || STATUS_CONFIG.unknown;
                return (
                    <div key={c.name}>
                        <div onClick={() => setExpanded(expanded === c.name ? null : c.name)}
                            style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0',
                                     cursor: 'pointer' }}>
                            <span>{cfg.icon}</span>
                            <span style={{ fontSize: 11, color: cfg.color, fontFamily: 'monospace',
                                           minWidth: 110 }}>{c.name}</span>
                            <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.4)' }}>{c.message}</span>
                        </div>
                        {expanded === c.name && c.metrics && (
                            <pre style={{ fontSize: 10, color: 'rgba(255,255,255,0.4)',
                                          marginLeft: 24, marginBottom: 4 }}>
                                {JSON.stringify(c.metrics, null, 2)}
                            </pre>
                        )}
                    </div>
                );
            })}
        </WidgetShell>
    );
}
```

#### `ImageWidget` (skill: eden / type: image)
- Renders `data.url` as `<img>`
- Click → lightbox (full-screen overlay with close button)
- Shows prompt used as caption

```jsx
function ImageWidget({ data }) {
    const [lightbox, setLightbox] = useState(false);
    return (
        <WidgetShell title={`generated image · eden`} icon="🎨" collapsible={false}>
            <img
                src={data?.url}
                alt={data?.prompt || 'generated'}
                onClick={() => setLightbox(true)}
                style={{ width: '100%', borderRadius: 6, cursor: 'zoom-in',
                         border: '1px solid rgba(255,255,255,0.08)' }}
            />
            {data?.prompt && (
                <p style={{ fontSize: 10, color: 'rgba(255,255,255,0.3)', marginTop: 4, marginBottom: 0 }}>
                    {data.prompt}
                </p>
            )}
            {lightbox && (
                <div onClick={() => setLightbox(false)} style={{
                    position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)',
                    zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                    <img src={data?.url} style={{ maxWidth: '90vw', maxHeight: '90vh', borderRadius: 8 }} />
                </div>
            )}
        </WidgetShell>
    );
}
```

#### `VideoWidget` (skill: eden / type: video)
- Renders `<video>` with controls if URL ends in `.mp4`/`.webm`
- Falls back to link if format unknown

#### `ChartWidget` (skill: analytics)
- Uses `recharts` (already in the stack — `import { BarChart, Bar, XAxis, YAxis, Tooltip } from 'recharts'`)
- `data.chart_type` → `BarChart` or `LineChart`
- `data.labels` + `data.values` → recharts data array
- Shows `data.title` as chart heading

```jsx
function ChartWidget({ data }) {
    const chartData = data?.labels?.map((label, i) => ({
        name: label,
        value: data.values[i],
    })) || [];

    return (
        <WidgetShell title={`${data?.title || 'analytics'} · chart`} icon="📊">
            <BarChart width={340} height={160} data={chartData}
                margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
                <XAxis dataKey="name" tick={{ fontSize: 9, fill: 'rgba(255,255,255,0.4)' }} />
                <YAxis tick={{ fontSize: 9, fill: 'rgba(255,255,255,0.4)' }} />
                <Tooltip
                    contentStyle={{ background: '#1a1a2e', border: '1px solid rgba(192,132,252,0.3)',
                                    fontSize: 11, color: 'rgba(255,255,255,0.8)' }}
                />
                <Bar dataKey="value" fill="rgba(192,132,252,0.6)" radius={[3,3,0,0]} />
            </BarChart>
        </WidgetShell>
    );
}
```

---

## 10. Config File

`config/skills.yaml`:
```yaml
skills:
  enabled: true

  max_execution_ms: 5000
  fallthrough_on_error: true
  log_dispatches: true

  math:
    enabled: true
    max_expression_length: 500
    timeout_ms: 3000

  logic:
    enabled: true
    max_variables: 8
    kanren_enabled: false

  formatting:
    enabled: true
    max_items: 50

  reading:
    enabled: true
    max_file_size_mb: 50
    max_chars: 50000
    store_to_memory: true
    allowed_extensions: [pdf, docx, doc, xlsx, pptx, txt, md]

  diagnostic:
    enabled: true
    include_metrics: true

  eden:
    enabled: true              # Requires EDEN_API_KEY
    auto_approve: false
    default_wait: true

  analytics:
    enabled: true
    pandas_enabled: true
    max_rows_display: 20
```

---

## 11. New + Modified Files Summary

**Backend — new:**

| File | Est. Lines | Purpose |
|------|-----------|---------|
| `skills/__init__.py` | 10 | Module exports |
| `skills/registry.py` | 80 | SkillRegistry |
| `skills/base.py` | 40 | Skill ABC + SkillResult |
| `skills/detector.py` | 60 | SKILL_PATTERNS + SkillDetector |
| `skills/config.py` | 40 | SkillsConfig |
| `skills/math/skill.py` | 80 | MathSkill |
| `skills/logic/skill.py` | 70 | LogicSkill |
| `skills/formatting/skill.py` | 60 | FormattingSkill |
| `skills/reading/skill.py` | 80 | ReadingSkill |
| `skills/diagnostic/skill.py` | 40 | DiagnosticSkill |
| `skills/eden/skill.py` | 50 | EdenSkill |
| `skills/analytics/skill.py` | 90 | AnalyticsSkill |
| **Backend total** | **~700 lines** | |

**Backend — modified:**
- `actors/director.py` — +35 lines (skill dispatch + widget metadata)
- `agentic/router.py` — +30 lines
- `config/skills.yaml` — new

**Frontend — new:**

| File | Est. Lines | Purpose |
|------|-----------|---------|
| `components/WidgetAnchor.jsx` | ~200 | Router + all 7 widget types + WidgetShell |
| **Frontend total** | **~200 lines** | |

**Frontend — modified:**
- `hooks/useChat.js` — +6 lines (`widget` field in `onDone`)
- `components/ChatPanel.jsx` — +5 lines (render `<WidgetAnchor>`)

**Frontend — new dep:**
- `katex` — `npm install katex` (LaTeX rendering for MathSkill)

---

## 12. Build Phases

### Phase 1 — Registry + Math + Diagnostic + Widgets (prove full stack)

**Backend:** `registry.py`, `base.py`, `detector.py`, `config.py`, `math/skill.py`, `diagnostic/skill.py`, Director integration with `response_metadata["widget"]`

**Frontend:** `WidgetAnchor.jsx` with `LaTeXWidget` + `DiagnosticWidget`, `useChat.js` + `ChatPanel.jsx` changes

**Tests:**
- `"solve x^2 - 5x + 6 = 0"` → MathSkill fires, Luna narrates, `LaTeXWidget` renders formula below bubble
- `"health check"` → DiagnosticSkill fires, Luna narrates first-person, `DiagnosticWidget` shows component grid
- `"hey how are you"` → no skill, no widget, normal routing

### Phase 2 — Logic + Reading + their widgets

**Backend:** `logic/skill.py`, `reading/skill.py`

**Frontend:** `TableWidget`, `DocumentWidget`

**Tests:**
- `"truth table for A AND B"` → `TableWidget` renders 4-row table
- `"read /path/to/spec.pdf"` → `DocumentWidget` shows preview + expand

### Phase 3 — Eden + Analytics + their widgets

**Backend:** `eden/skill.py`, `analytics/skill.py`

**Frontend:** `ImageWidget`, `VideoWidget`, `ChartWidget`

**Tests:**
- `"generate an image of a raccoon with a glowing purple staff"` → `ImageWidget` renders inline with lightbox
- `"how many memories do I have"` → `ChartWidget` renders bar chart of node type distribution

### Phase 4 — FormattingSkill (no widget, just fallthrough validation)

**Backend:** `formatting/skill.py`

**Tests:**
- `"make a bullet list of LoRA training steps"` → fallthrough, Director adds format constraint, response is a formatted list in the bubble

---

## 13. What NOT To Do

**Backend:**
- No LLM calls inside skills. Deterministic only.
- Don't modify ToolRegistry.
- No confirmation flows (EdenSkill delegates to eden_tools.py which has its own policy).
- Don't access ring buffer directly — use `context` dict.
- Respect `asyncio.wait_for()` timeout. Never block the hot path.
- Don't hardcode file paths in ReadingSkill.
- Don't register unavailable skills — `register_defaults()` calls `is_available()` first.

**Frontend:**
- Don't put widget logic in `ChatPanel.jsx`. It belongs in `WidgetAnchor.jsx`.
- Don't re-fetch data in widgets — all data comes through the `widget.data` prop.
- Don't use localStorage for widget state — React state only.
- Don't render widgets for streaming messages — check `!msg.streaming`.
- Don't block chat scroll — widgets must be fixed-height or have explicit max-height with overflow.
- `dangerouslySetInnerHTML` is only acceptable for KaTeX output (it's a trusted renderer). Nowhere else.

---

## 14. Success Criteria

**Phase 1 complete when:**
- MathSkill returns correct sympy result, `LaTeXWidget` renders formula below Luna's message
- DiagnosticSkill returns first-person health status, `DiagnosticWidget` shows clickable component grid
- Fallthrough works end-to-end: skill error → normal routing → no widget rendered

**Phase 2 complete when:**
- LogicSkill truth tables render in `TableWidget` with correct T/F coloring
- ReadingSkill extracts PDF/DOCX, `DocumentWidget` shows preview + expand correctly

**Phase 3 complete when:**
- Eden image renders inline via `ImageWidget` with lightbox
- Analytics bar chart renders via `ChartWidget` using recharts

**Full system complete when:**
- Skill dispatch logged in Director with ms timing
- Widget renders consistently across all 7 skill types
- Zero degradation on non-skill queries (log + UI audit)
- LunaScript geometry constraints applied per skill
- Ahab confirms Luna's voice sounds right across skill narrations
- Widget visual style matches existing eclissi/GlassCard aesthetic

---

*— Dude + Ahab + Luna, March 2026*
