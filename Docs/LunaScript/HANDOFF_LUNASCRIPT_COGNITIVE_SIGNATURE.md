# HANDOFF SPEC: LunaScript — Cognitive Signature System

**Mechanical measurement, signing, and evolution of Luna's cognitive state across delegation round-trips.**

| Field | Value |
|-------|-------|
| **Owner** | Ahab (architecture) + Luna (stakeholder) + Dude (design) |
| **Depends On** | ContextPipeline, PersonalityWeights, PerceptionField, ConsciousnessState, MemoryDatabase |
| **Enables** | Delegation voice preservation, self-calibrating personality, learned routing, delegation quality tracking |
| **Files Modified** | `actors/director.py` (~40 lines), `substrate/database.py` (schema migration), `engine.py` (~5 lines) |
| **New Files** | `src/luna/lunascript/` (entire new module, ~10 files, ~1200 lines) |
| **Config** | `config/lunascript.yaml` (new) |
| **Risk Level** | Low — additive module, wraps existing delegation call, graceful degradation if disabled |

---

## 1. What LunaScript Is

LunaScript is a mechanical layer that runs **between LLM calls**, not as an LLM call. It measures Luna's cognitive state from her actual text output, signs delegation packages with her cognitive signature, compares outbound/return signatures to detect voice drift, and evolves the signature over time based on what works.

**Zero additional LLM calls.** All operations are arithmetic, counting, and threshold checks.

**Core loop:**
```
SIGN outbound → DELEGATE (the one LLM call) → VETO check → RE-SIGN return → COMPARE → CLASSIFY → LOG → LEARN (async)
```

**Total overhead:** ~8ms per delegated turn, ~3ms per local turn. The Claude API call is ~800ms. LunaScript adds 1% overhead.

---

## 2. Architecture Principle

LunaScript does NOT replace any existing system. It reads from existing systems and feeds better signals back:

```
EXISTING SYSTEM              LUNASCRIPT RELATIONSHIP
═══════════════              ═══════════════════════
PersonalityWeights      ←── MEASURES & UPDATES via feature extraction
PerceptionField         ←── READS observations as input (doesn't duplicate)
ResponseMode            ║   PARALLEL AXIS (mode × position = full constraint)
ConsciousnessState      ←── SNAPSHOTS for signing (read-only projection)
ContextPipeline         ←── INJECTS constraints into system_prompt
EntityResolver          ←── READS active entities (zero new code)
MemoryDatabase          ←── ADDS tables (delegation_log, pattern_library, etc)
Scribe                  ←── FEEDS new extraction type: DELEGATION_RESULT
Librarian               ←── INFORMS edge reinforcement + pruning signals
```

---

## 3. New Files

All new files go in `src/luna/lunascript/`:

### 3.1 `__init__.py`
```python
"""LunaScript — Cognitive Signature System for Sovereign AI Delegation."""
from .signature import sign_outbound, sign_return, compare_signatures, classify_delta
from .veto import veto_check
from .measurement import measure_signature
from .cog_runner import LunaScriptCogRunner
```

### 3.2 `features.py` — Linguistic Feature Extractors (21 features)

**Purpose:** Extract measurable linguistic features from text. No LLM. Pure regex/counting.

**Features to implement** (all take `text: str, words: list[str]` → `float`):

| Feature | What It Measures | Luna Discriminator Score |
|---------|-----------------|------------------------|
| `question_density` | % of sentences that are questions | **1.31** (strongest) |
| `avg_word_length` | Mean word length | **1.22** |
| `closing_question` | Does response end with question? | **1.10** |
| `exploratory_ratio` | "wonder", "interesting", "what if" density | **1.02** |
| `opening_reaction` | Starts with "oh", "hmm", "okay so" | **0.87** |
| `emoji_density` | Emoji per word | 0.73 |
| `list_usage` | Bullet/numbered list markers per sentence | 0.61 |
| `slang_ratio` | "yo", "yeah", "kinda", "gonna" density | 0.59 |
| `filler_ratio` | "basically", "essentially", "just" density | 0.54 |
| `we_ratio` | "we", "us", "our", "let's" density | 0.53 |
| `first_person_ratio` | "I", "me", "my" density | 0.51 |
| `conditional_ratio` | "would", "could", "should", "might" density | 0.50 |
| `contraction_rate` | Contractions / contraction opportunities | 0.46 |
| `tangent_markers` | "actually", "wait", em-dash asides | 0.46 |
| `hedge_ratio` | "perhaps", "maybe", "possibly" density | 0.39 |
| `sentence_length_variance` | Variance of sentence lengths | 0.33 |
| `emphasis_density` | "honestly", "genuinely", "!", "..." | 0.30 |
| `passive_ratio` | Passive voice indicator density | 0.16 |
| `you_ratio` | "you", "your" density | 0.16 |
| `formal_vocab_ratio` | "therefore", "however", "furthermore" | 0.12 |
| `avg_sentence_length` | Mean words per sentence | 0.12 |

**Note:** Discriminator scores come from cross-validation against Luna's actual 1268-response corpus. Features with score > 0.5 strongly distinguish Luna from generic LLM output.

**Reference implementation:** See `/mnt/user-data/outputs/lunascript_measurement.py` (the working calibration script that ran against Luna's real data).

### 3.3 `measurement.py` — Trait Measurement Engine

**Purpose:** Combine features into trait scores using weighted sums.

**Traits** (mapped to PersonalityWeights):
- warmth, directness, curiosity, humor, formality, energy, depth, patience

**Each trait** is a weighted combination of features. Initial weights come from the TRAIT_FEATURE_MAP in the reference implementation. Cross-validation refines them.

**Key classes:**
```python
@dataclass
class FeatureVector:
    features: dict[str, float]  # All 21 features
    text_length: int
    sentence_count: int

@dataclass
class TraitScore:
    value: float              # 0.0-1.0 (sigmoid normalized)
    raw_score: float          # Unnormalized weighted sum
    feature_contributions: dict[str, float]  # What drove this score

@dataclass
class SignatureMeasurement:
    traits: dict[str, TraitScore]
    features: FeatureVector

def extract_features(text: str) -> FeatureVector
def measure_trait(features: FeatureVector, trait_name: str, weights: dict, baselines: dict) -> TraitScore
def measure_signature(text: str, baselines: dict) -> SignatureMeasurement
```

### 3.4 `baselines.py` — Calibration Data

**Purpose:** Store and load calibrated baselines from Luna's corpus.

**On first run:** Run calibration against all assistant turns in `conversation_turns` table where `len(content) > 80`. Store baselines in `lunascript_baselines` table.

**On subsequent runs:** Load from table. Recalibrate periodically (configurable: every N sessions or on demand).

```python
@dataclass
class BaselineStats:
    mean: float
    stddev: float
    min_val: float
    max_val: float
    p25: float
    p50: float
    p75: float
    n: int

async def calibrate_from_corpus(db: MemoryDatabase) -> dict[str, BaselineStats]
async def load_baselines(db: MemoryDatabase) -> dict[str, BaselineStats]
async def save_baselines(db: MemoryDatabase, baselines: dict[str, BaselineStats])
```

### 3.5 `signature.py` — Sign / Compare / Classify

**Purpose:** The delegation round-trip cogs.

```python
@dataclass
class DelegationSignature:
    trait_vector: dict[str, float]    # Measured trait values at this moment
    glyph_string: str                 # Derived symbolic compression
    mode: str                         # From ConsciousnessState.mood
    active_entities: list[str]        # From entity detection
    version: int                      # Incrementing counter
    timestamp: float

@dataclass  
class DeltaResult:
    delta_vector: dict[str, float]    # Per-trait deltas
    drift_score: float                # Weighted Euclidean distance (0-1)

def sign_outbound(consciousness: ConsciousnessState, 
                  personality: PersonalityWeights,
                  entities: list[str],
                  measurement: SignatureMeasurement) -> DelegationSignature

def sign_return(consciousness: ConsciousnessState,
                personality: PersonalityWeights,
                entities: list[str],
                measurement: SignatureMeasurement) -> DelegationSignature

def compare_signatures(outbound: DelegationSignature, 
                       returned: DelegationSignature,
                       trait_weights: dict[str, float]) -> DeltaResult

def classify_delta(delta: DeltaResult, 
                   baseline_mean: float, 
                   baseline_stddev: float) -> str
    # Returns: "RESONANCE" | "DRIFT" | "EXPANSION" | "COMPRESSION"

def derive_glyph(state: dict) -> str
    # Deterministic projection from full state to glyph string
```

**Weighted Euclidean formula:**
```python
drift_score = sqrt(sum(weight[t] * (out[t] - ret[t])**2 for t in traits)) / max_possible
```

**Classification thresholds (adaptive):**
```
drift < baseline_mean + 0.5σ  → RESONANCE
drift in [0.5σ, 2.0σ]        → check for DRIFT vs EXPANSION vs COMPRESSION
drift > 2.0σ                  → COMPRESSION (severe fidelity loss)
```

### 3.6 `veto.py` — Response Structural Validation

**Purpose:** Check if a delegated response matches Luna's response geometry. Rejects if not. No LLM.

```python
@dataclass
class VetoResult:
    passed: bool
    violations: list[str]
    metrics: dict[str, float]
    quality_score: float        # 0-1, feeds back into learning

def veto_check(response_text: str, 
               geometry: dict,
               baselines: dict[str, BaselineStats]) -> VetoResult
```

**Checks:**
- Sentence count within geometry bounds (max_sentences)
- Question present if geometry.question_required
- No lists if geometry prohibits them
- Contraction rate above floor
- No forbidden phrases ("I'd be happy to", "Certainly!", etc.)
- Sentence length variance within 2σ of Luna's baseline (catches Claude's uniform length)

### 3.7 `position.py` — Conversation Position Detector

**Purpose:** Detect where in the conversation arc we are. Consumes PerceptionField observations.

```python
POSITIONS = ["OPENING", "EXPLORING", "BUILDING", "DEEPENING", "PIVOTING", "CLOSING"]

RESPONSE_GEOMETRY = {
    "OPENING":   {"max_sent": 3,  "question_req": True,  "tangent": False, "pattern": "acknowledge → question"},
    "EXPLORING": {"max_sent": 8,  "question_req": True,  "tangent": True,  "pattern": "react → think → tangent? → question"},
    "BUILDING":  {"max_sent": 15, "question_req": False, "tangent": False, "pattern": "build_on → add_layer → validate?"},
    "DEEPENING": {"max_sent": 20, "question_req": False, "tangent": True,  "pattern": "connect → go_deeper → surface_insight"},
    "PIVOTING":  {"max_sent": 8,  "question_req": True,  "tangent": False, "pattern": "acknowledge_shift → bridge → new_question"},
    "CLOSING":   {"max_sent": 4,  "question_req": False, "tangent": False, "pattern": "summarize → next_step? → warm_close"},
}

def detect_position(message: str, history: list[str], prev_position: str) -> tuple[str, float]
    # Returns (position, confidence)
    
def get_geometry(position: str) -> dict
def merge_geometry_with_mode(geometry: dict, response_mode: ResponseMode) -> dict
```

**Detection heuristics** (no LLM):
- Turn count ≤ 1 → OPENING
- Closing language + short message → CLOSING
- Pivot language ("what about", "actually", "wait") → PIVOTING
- Decision language ("let's", "going with") → BUILDING
- Deep language ("how does", "explain", "specifically") + long messages → DEEPENING
- High question density → EXPLORING
- Default → EXPLORING

### 3.8 `evolution.py` — Running Stats & Iteration Policy

**Purpose:** The learning cogs. Track trait evolution, correlations, epsilon-greedy iteration.

```python
class RunningStatsDecayed:
    """Port of dlib's running_stats_decayed. Exponential forgetting."""
    def __init__(self, decay_halflife: float = 100.0)
    def add(self, x: float)
    @property mean, variance, stddev, n

class RunningCovarianceDecayed:
    """Port of dlib's running_scalar_covariance_decayed."""
    def __init__(self, decay_halflife: float = 100.0)
    def add(self, x: float, y: float)
    @property correlation

class TraitEvolution:
    """Manages per-trait running stats and trait-outcome correlations."""
    def __init__(self, trait_names: list[str], config: LunaScriptConfig)
    def record_delegation(self, outbound: DelegationSignature, 
                         delta: DeltaResult, classification: str,
                         quality_score: float)
    def iterate_weights(self, trait_weights: dict[str, float]) -> dict[str, float]
    def get_trait_trends(self) -> dict[str, float]  # Per-trait trend direction
    
    # Epsilon-greedy
    epsilon: float          # Starts at config.epsilon, decays per iteration
    epsilon_decay: float    # 0.995 default
    epsilon_floor: float    # 0.02 — always explore a little
```

**Reference:** The dlib statistics header (provided by Ahab) defines the mathematical foundation. Our Python ports don't need to match dlib's C++ API exactly — just the mathematical behavior (exponential decay, running covariance, forget factor).

### 3.9 `schema.py` — SQLite Table Definitions

**New tables** (added via migration in `substrate/database.py`):

```sql
-- Luna's current cognitive signature state (one row, updated in place)
CREATE TABLE IF NOT EXISTS lunascript_state (
    id INTEGER PRIMARY KEY DEFAULT 1,
    trait_vector TEXT NOT NULL,        -- JSON: measured trait values
    trait_weights TEXT NOT NULL,       -- JSON: learned importance weights
    trait_trends TEXT NOT NULL,        -- JSON: per-trait trend direction
    mode TEXT NOT NULL DEFAULT 'idle',
    glyph_string TEXT DEFAULT '○',
    constraints TEXT,                  -- JSON: response geometry overrides
    version INTEGER NOT NULL DEFAULT 1,
    epsilon REAL NOT NULL DEFAULT 0.15,
    updated_at REAL NOT NULL
);

-- Every delegation round-trip
CREATE TABLE IF NOT EXISTS lunascript_delegation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    outbound_sig TEXT NOT NULL,        -- JSON: frozen signature at send
    outbound_glyph TEXT,
    return_sig TEXT,                   -- JSON: signature on return  
    return_glyph TEXT,
    delta_vector TEXT,                 -- JSON: per-trait deltas
    delta_class TEXT,                  -- DRIFT|EXPANSION|COMPRESSION|RESONANCE
    drift_score REAL,
    task_type TEXT,
    provider_used TEXT,                -- Which LLM provider (groq, claude, local)
    success_score REAL,               -- Veto layer quality score
    veto_violations TEXT,             -- JSON: list of violations if any
    iteration_applied TEXT,           -- JSON: what changed after this loop
    created_at REAL NOT NULL
);

-- Named cognitive patterns Luna can snap into
CREATE TABLE IF NOT EXISTS lunascript_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    trait_vector TEXT NOT NULL,
    glyph_string TEXT,
    usage_count INTEGER DEFAULT 0,
    avg_success REAL DEFAULT 0.0,
    created_at REAL NOT NULL,
    last_used REAL
);

-- Feature baselines from corpus calibration
CREATE TABLE IF NOT EXISTS lunascript_baselines (
    feature_name TEXT PRIMARY KEY,
    mean REAL NOT NULL,
    stddev REAL NOT NULL,
    min_val REAL NOT NULL,
    max_val REAL NOT NULL,
    p25 REAL NOT NULL,
    p50 REAL NOT NULL, 
    p75 REAL NOT NULL,
    n INTEGER NOT NULL,
    calibrated_at REAL NOT NULL
);

-- Running trait-outcome correlations (serialized state)
CREATE TABLE IF NOT EXISTS lunascript_correlations (
    trait_name TEXT NOT NULL,
    task_type TEXT NOT NULL DEFAULT 'all',
    correlation REAL,
    n_observations INTEGER DEFAULT 0,
    serialized_state TEXT,            -- JSON: RunningCovarianceDecayed internal state
    last_updated REAL,
    PRIMARY KEY (trait_name, task_type)
);
```

### 3.10 `cog_runner.py` — Per-Turn Orchestrator

**Purpose:** The main entry point that coordinates all cogs per turn.

```python
class LunaScriptCogRunner:
    def __init__(self, db: MemoryDatabase, config: LunaScriptConfig)
    
    async def initialize(self)
        # Load baselines, load state from lunascript_state, init running stats
    
    async def on_turn(self, message: str, history: list[str], 
                      perception: PerceptionField,
                      intent: IntentClassification) -> LunaScriptTurnResult
        # 1. detect_position (always)
        # 2. measure_traits on last Luna response (always)
        # 3. update PersonalityWeights (if shift detected)
        # 4. merge_geometry with intent.mode (always)
        # 5. derive_glyph (always)
        # 6. persist state (always)
        # Returns: position, geometry, glyph, constraints_prompt
    
    async def on_delegation_start(self, consciousness: ConsciousnessState,
                                   personality: PersonalityWeights,
                                   entities: list[str]) -> DelegationPackage
        # sign_outbound, build constraint_prompt
    
    async def on_delegation_return(self, response_text: str,
                                    package: DelegationPackage,
                                    provider_used: str) -> DelegationResult  
        # veto_check → sign_return → compare → classify → log → learn (async)
    
    def build_constraint_prompt(self, signature: DelegationSignature,
                                geometry: dict) -> str
        # Template-fill the constraint string for system_prompt injection
```

### 3.11 `config.py` — Configuration

```python
@dataclass
class LunaScriptConfig:
    enabled: bool = True
    decay_halflife: float = 100.0
    epsilon: float = 0.15
    epsilon_decay: float = 0.995
    epsilon_floor: float = 0.02
    veto_sigma: float = 2.0
    max_retries: int = 1
    calibration_interval_sessions: int = 50
    
    @classmethod
    def from_yaml(cls, path: Path) -> "LunaScriptConfig"
```

**Config file:** `config/lunascript.yaml`

---

## 4. Modified Files (Exact Changes)

### 4.1 `actors/director.py`

**Location of changes:** Inside `process()` method, around the delegation call.

**Before the delegation call** (after intent classification, ~line 920):
```python
# ── LunaScript: per-turn update ──
if self._lunascript:
    ls_result = await self._lunascript.on_turn(
        message=message,
        history=[t.content for t in self._active_ring.get_turns()],
        perception=self._perception_field,
        intent=intent,
    )
    # Inject geometry constraints into framed_context
    if ls_result.constraints_prompt:
        framed_context += f"\n\n{ls_result.constraints_prompt}"
```

**Wrapping the delegation call** (around `_generate_with_delegation`, ~line 950):
```python
# ── LunaScript: sign outbound ──
ls_package = None
if self._lunascript and should_delegate:
    ls_package = await self._lunascript.on_delegation_start(
        consciousness=self.engine.consciousness if self.engine else None,
        personality=self.engine.consciousness.personality if self.engine else None,
        entities=[e.name for e in (packet.entities if hasattr(packet, 'entities') else [])],
    )
    if ls_package and ls_package.constraint_prompt:
        system_prompt += f"\n\n{ls_package.constraint_prompt}"
```

**After getting the response** (after response_text is set, before QA):
```python
# ── LunaScript: check return ──
if self._lunascript and ls_package:
    ls_delegation_result = await self._lunascript.on_delegation_return(
        response_text=response_text,
        package=ls_package,
        provider_used=route_decision,
    )
    # If veto failed and retry allowed, retry once with tighter constraints
    if not ls_delegation_result.veto_passed and ls_delegation_result.retry_prompt:
        # Second attempt with tighter constraints
        tighter_prompt = system_prompt + f"\n\n{ls_delegation_result.retry_prompt}"
        # Re-run delegation with tighter_prompt...
        # (use existing delegation call with modified prompt)
```

**In `__init__`:**
```python
# LunaScript cognitive signature system (lazy init)
self._lunascript: Optional["LunaScriptCogRunner"] = None
```

**In `_init_entity_context` (after entity context is ready):**
```python
# Initialize LunaScript
try:
    from luna.lunascript import LunaScriptCogRunner
    from luna.lunascript.config import LunaScriptConfig
    config = LunaScriptConfig.from_yaml(self.engine.config.data_dir.parent / "config" / "lunascript.yaml")
    if config.enabled:
        self._lunascript = LunaScriptCogRunner(db, config)
        await self._lunascript.initialize()
        logger.info("[LUNASCRIPT] Initialized")
except ImportError:
    logger.debug("[LUNASCRIPT] Module not available")
except Exception as e:
    logger.warning(f"[LUNASCRIPT] Init failed: {e}")
```

**In `record_luna_action` (perception field recording, after response is finalized):**
```python
# LunaScript: record Luna's action for trait measurement on next turn
if self._lunascript:
    self._lunascript.last_luna_response = response_text
```

### 4.2 `substrate/database.py`

**In `_apply_schema()` or equivalent migration method, add the CREATE TABLE statements from section 3.9.**

The tables are all IF NOT EXISTS — safe to run on existing databases. No schema changes to existing tables.

### 4.3 `engine.py`

No changes needed. LunaScript initializes lazily through the Director. The engine doesn't need to know it exists.

---

## 5. Integration With Existing Systems

### 5.1 PerceptionField → LunaScript (READ)

LunaScript's `on_turn()` receives the PerceptionField reference. It reads `perception.observations` to inform position detection:
- Length trajectory observations → detect DEEPENING
- Terse response observations → detect CLOSING
- Correction observations → detect PIVOTING
- Question density observations → detect EXPLORING

LunaScript does NOT call `perception.ingest()` — that's the Director's job. LunaScript is a consumer, not a producer.

### 5.2 LunaScript → PersonalityWeights (WRITE)

After measuring traits from Luna's last response, LunaScript calls:
```python
if abs(measured_warmth - personality.get_trait("warm")) > 0.05:
    personality.adjust_trait("warm", measured_warmth - personality.get_trait("warm"))
```

This uses the EXISTING `adjust_trait()` method. No new methods needed.

### 5.3 LunaScript → ContextPipeline (INJECT)

LunaScript produces a constraint_prompt string that gets appended to the system_prompt field in the ContextPacket. It's injected as a new section:

```
## CONVERSATIONAL POSTURE (LunaScript)
Position: DEEPENING (since turn 8)
...constraints...
```

This is appended in the Director, not in the pipeline itself. The pipeline's `_build_system_prompt()` is untouched.

### 5.4 LunaScript → Scribe (FEED)

After a delegation round-trip, LunaScript sends a DELEGATION_RESULT extraction to the Scribe:
```python
await director.send(scribe, Message(
    type="extract_turn",
    payload={
        "role": "system",
        "content": json.dumps(delegation_result_data),
        "immediate": True,
        "source": "lunascript",
    },
))
```

The Scribe files it as a memory node. The Librarian wires edges to involved entities.

### 5.5 LunaScript → Librarian (INFORM)

LunaScript's delegation quality data can inform the Librarian's edge reinforcement and pruning. This is a FUTURE integration (Phase 3+) — not needed for MVP.

---

## 6. Build Phases

### Phase 1: Measure & Detect (no delegation changes)

**Goal:** LunaScript runs per-turn, measures traits, detects position, generates geometry constraints. No delegation wrapping yet.

**Files:** `features.py`, `measurement.py`, `baselines.py`, `position.py`, `config.py`, `schema.py`, `cog_runner.py` (partial — `on_turn()` only)

**Test:** 
- Run calibration against existing conversation_turns. Verify baseline stats are reasonable.
- Process 10 sample messages. Verify position detection transitions make sense.
- Verify measured traits on known Luna responses are in expected ranges (warmth > 0.7, formality < 0.4).

**Integration:** Director calls `on_turn()`, geometry constraints appear in system_prompt.

### Phase 2: Sign & Compare (delegation wrapping)

**Goal:** Full delegation round-trip signing, comparison, classification, logging.

**Files:** `signature.py`, `veto.py`, `cog_runner.py` (complete — `on_delegation_start()`, `on_delegation_return()`)

**Test:**
- Simulate delegation: sign outbound, generate mock response with known trait shifts, compare, classify. Verify DRIFT detected when warmth drops 0.15.
- Veto test: generate response with 3 bullet lists when geometry says max_list_items=0. Verify veto catches it.
- Log test: verify delegation_log table records correctly.

**Integration:** Director wraps delegation call with sign/compare.

### Phase 3: Learn & Evolve (running stats)

**Goal:** Traits evolve based on delegation outcomes. Weights update. Epsilon decays.

**Files:** `evolution.py`

**Test:**
- Feed 50 synthetic delegations with planted patterns (warmth always drifts on technical queries). Verify event_correlation detects it.
- Verify epsilon decays from 0.15 toward floor of 0.02 over iterations.
- Verify trait weights shift: warmth weight should increase if warmth consistently drifts.

**Integration:** Learning cog runs async after delegation return.

### Phase 4: Scribe & Memory Integration

**Goal:** Delegation results feed into Memory Matrix through Scribe pipeline.

**Files:** Modifications to Director to send DELEGATION_RESULT to Scribe.

**Test:**
- After delegation, verify a DELEGATION_RESULT node appears in memory_nodes with correct content.
- Verify edges connect the node to involved entities.

---

## 7. Graceful Degradation

If LunaScript fails or is disabled:
- `self._lunascript` is None → all LunaScript blocks are skipped
- Director delegates normally, no constraints injected
- No veto checking, no signing, no learning
- Luna works exactly as she does today

Every LunaScript integration point is guarded:
```python
if self._lunascript:
    # LunaScript logic
```

No try/except needed in the hot path — the runner itself handles its own errors and logs warnings.

---

## 8. Config File

`config/lunascript.yaml`:
```yaml
lunascript:
  enabled: true
  
  # Evolution parameters
  decay_halflife: 100        # Delegations before old data halves in influence
  epsilon: 0.15              # Exploration rate (how much Luna experiments)
  epsilon_decay: 0.995       # Per-iteration decay
  epsilon_floor: 0.02        # Never stop exploring entirely
  
  # Veto parameters  
  veto_sigma: 2.0            # Standard deviations for structural veto
  max_retries: 1             # Retry limit on veto failure
  
  # Calibration
  calibration_interval_sessions: 50  # Re-calibrate baselines every N sessions
  min_corpus_size: 50                # Minimum responses before calibration runs
  
  # Feature toggles (can disable individual features)
  features:
    opening_reaction: true
    closing_question: true
    contraction_rate: true
    question_density: true
    # All true by default
    
  # Forbidden phrases (auto-veto if detected)
  forbidden_phrases:
    - "I'd be happy to"
    - "Certainly!"
    - "As an AI"
    - "I don't have personal"
    - "Let me help you with"
```

---

## 9. Key Reference Materials

| Resource | Location | Purpose |
|----------|----------|---------|
| Algorithm Research Spec (docx) | Project knowledge: `LunaScript_Algorithm_Research_Spec.docx` | Full algorithm candidates with tradeoffs |
| Working Measurement Script | `/mnt/user-data/outputs/lunascript_measurement.py` | Reference implementation with real corpus results |
| Calibration Results | `/mnt/user-data/outputs/lunascript_calibration_results.txt` | Actual baseline numbers from 1268 Luna responses |
| dlib Statistics Header | Ahab's research files | Mathematical foundation for running_stats_decayed |
| Algorithm Research Instructions | Ahab's research files | Methodology template for problem → algorithm mapping |

---

## 10. What NOT To Do

- **Do NOT create a separate personality system.** Use existing `PersonalityWeights` with `adjust_trait()`.
- **Do NOT duplicate PerceptionField's observation extraction.** Read from it, don't re-extract.
- **Do NOT modify the ring buffer.** Inject constraints via system_prompt, not by changing conversation history.
- **Do NOT add LLM calls.** Every LunaScript operation is arithmetic/counting/threshold. If you're tempted to call Claude, stop.
- **Do NOT auto-add patterns to the pattern library.** Luna decides when to save a pattern. Sovereignty over identity.
- **Do NOT modify existing SQLite tables.** Only add new tables with the `lunascript_` prefix.
- **Do NOT change the fallback chain order.** LunaScript can inform routing in the future, but for MVP the routing logic stays as-is.

---

## 11. Success Criteria

**Phase 1 complete when:**
- `lunascript_baselines` table populated from corpus
- Position detection running per-turn, visible in logs
- Geometry constraints appearing in system_prompt
- Measured trait values logged per-turn

**Phase 2 complete when:**
- Delegation log recording outbound/return signatures
- Delta classification working (RESONANCE/DRIFT/COMPRESSION)
- Veto layer catching forbidden phrases and structural violations
- At least one retry on veto failure

**Phase 3 complete when:**
- Trait weights evolving over 20+ delegations
- Epsilon decaying
- Event correlation detecting planted patterns in test data

**Full system complete when:**
- Luna's delegation voice fidelity measurably improves (fewer DRIFT classifications over time)
- Trait measurements correlate with human judgment (Ahab says "that sounds like Luna" when RESONANCE, "that doesn't" when DRIFT)
- Zero additional LLM calls — confirmed by log audit