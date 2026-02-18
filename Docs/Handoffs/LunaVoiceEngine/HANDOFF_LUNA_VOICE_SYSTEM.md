# HANDOFF: Luna Voice System

**Author:** Ahab + Luna (Architect Session)  
**Date:** 2026-02-17  
**For:** CC (Claude Code)  
**Status:** Ready for Phase 1 implementation

---

## Overview

Two-engine voice system that makes Luna sound like Luna. Ships as a modular, toggleable layer that sits between PersonaCore and context_builder — inject on, inject off, zero side effects.

**Voice Corpus** = the fallback. Static few-shot examples + kill list. Simple, reliable, ships first.  
**Voice Blend Engine** = the primary. Confidence-weighted scaffolding that computes how much help Luna needs per turn and fades as she finds her voice.

Both are independently toggleable (active / shadow / off). Both produce a `VoiceSeed` that renders to a `<luna_voice>` XML block. The `VoiceSystemOrchestrator` merges them and hands one string to `context_builder`.

---

## Architecture

```
PersonaCore (who Luna is)
     │
     ▼
┌─── VoiceSystemOrchestrator ───────────────────────┐
│                                                     │
│   ┌──────────────────┐  ┌───────────────────────┐  │
│   │  VoiceCorpus     │  │  VoiceBlendEngine     │  │
│   │  (Fallback)      │  │  (Primary)            │  │
│   │                  │  │                       │  │
│   │  context → lines │  │  signals → alpha      │  │
│   │  kill list → ✗   │  │  alpha → segments     │  │
│   │                  │  │  segments → lines     │  │
│   │                  │  │  lines → seed         │  │
│   └────────┬─────────┘  └──────────┬────────────┘  │
│            │                       │                │
│            ▼                       ▼                │
│   ┌───────────────────────────────────────────┐    │
│   │        Merge & Deduplicate                 │    │
│   │  Engine seed + Corpus kill list + tone     │    │
│   └──────────────────┬────────────────────────┘    │
└──────────────────────┼─────────────────────────────┘
                       │
                       ▼
              <luna_voice> block → context_builder.py
```

### Priority Chain

| Engine | Corpus | Result |
|--------|--------|--------|
| active | active | Engine seed + Corpus kill list (merged) |
| active | off    | Engine seed only, no static guardrails |
| off    | active | **Corpus fallback** — static few-shot + kill list |
| off    | off    | Raw Luna — personality prompt only |
| shadow | active | Corpus active, Engine logs only |
| active | shadow | Engine active, Corpus logs only |
| shadow | shadow | Both log, neither injects |

### Key Design Decisions

1. **Two separate engines, not one.** Corpus has zero dependencies on Engine. If Engine is broken, Corpus still works.
2. **Orchestrator merges, engines don't know about each other.** Clean separation.
3. **Kill list lives in Corpus.** Anti-patterns are static and universal, not confidence-dependent.
4. **Shadow mode is per-engine.** Enables targeted A/B testing.
5. **Read-only with respect to pipeline.** Voice system reads memory scores, turn count, entities. Never writes to any of those systems. One output: the seed block.

---

## File Layout

```
src/luna/voice/
├── __init__.py
├── models.py              # All Pydantic models (shared)
├── corpus_service.py      # VoiceCorpusService
├── blend_engine.py        # VoiceBlendEngine
├── orchestrator.py        # VoiceSystemOrchestrator
├── logger.py              # VoiceSystemLogger
│
├── data/
│   ├── line_bank.json     # Full tagged line bank (Engine)
│   ├── corpus.json        # Curated corpus subset (Corpus)
│   └── voice_config.yaml  # Runtime configuration
│
└── tests/
    ├── test_models.py
    ├── test_corpus.py
    ├── test_engine.py
    ├── test_orchestrator.py
    ├── test_toggle_scenarios.py
    └── fixtures/
        ├── sample_bank.json
        └── sample_config.yaml
```

**Integration point (existing file):**
```
src/luna/engine/context_builder.py
  └── imports VoiceSystemOrchestrator
  └── calls generate_voice_block() once per turn
```

---

## Pydantic Models

All models live in `src/luna/voice/models.py`.

### Enums

```python
from enum import Enum

class EngineMode(str, Enum):
    ACTIVE = "active"
    SHADOW = "shadow"
    OFF = "off"

class ConfidenceTier(str, Enum):
    GROUNDING = "GROUNDING"
    ENGAGING = "ENGAGING"
    FLOWING = "FLOWING"

class ContextType(str, Enum):
    GREETING = "greeting"
    COLD_START = "cold_start"
    TOPIC_SHIFT = "topic_shift"
    FOLLOW_UP = "follow_up"
    EMOTIONAL = "emotional"
    TECHNICAL = "technical"
    CREATIVE = "creative"
    MEMORY_RECALL = "memory_recall"

class EmotionalRegister(str, Enum):
    WARM = "warm"
    DIRECT = "direct"
    PLAYFUL = "playful"
    ANALYTICAL = "analytical"
    UNCERTAIN = "uncertain"

class SegmentType(str, Enum):
    OPENER = "opener"
    BRIDGE = "bridge"
    CLOSER = "closer"
    CLARIFIER = "clarifier"
    REACTION = "reaction"

class VoiceSeedSource(str, Enum):
    ENGINE = "engine"
    CORPUS = "corpus"
    MERGED = "merged"
    NONE = "none"
```

### Line Models

```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class VoiceLine(BaseModel):
    """A single line from Luna's voice palette."""
    id: str                                    # e.g. "grnd_001"
    text: str
    cost: int = Field(ge=1, le=5)              # Anchoring weight. 5 = very Luna.
    tier: ConfidenceTier
    context_tags: list[str] = []
    emotional_register: EmotionalRegister
    segment_type: SegmentType
    source: Optional[str] = None               # Provenance — session ID if extracted

class AntiPattern(BaseModel):
    """A phrase Luna should never say."""
    phrase: str
    reason: str                                # For observability logs
    severity: int = Field(ge=1, le=3)          # 1=mild, 3=critical (always inject)

class LineBank(BaseModel):
    """The complete voice line collection."""
    version: str
    lines: list[VoiceLine]
    anti_patterns: list[AntiPattern]
    updated_at: datetime

    def by_tier(self, tier: ConfidenceTier) -> list[VoiceLine]:
        return [l for l in self.lines if l.tier == tier]

    def by_tags(self, tags: list[str]) -> list[VoiceLine]:
        tag_set = set(tags)
        return [l for l in self.lines if tag_set & set(l.context_tags)]

    def critical_anti_patterns(self) -> list[AntiPattern]:
        return [a for a in self.anti_patterns if a.severity == 3]
```

### Confidence & Blending Models

```python
class ConfidenceSignals(BaseModel):
    """Raw inputs to the ConfidenceRouter."""
    memory_retrieval_score: float = Field(ge=0.0, le=1.0)
    turn_number: int = Field(ge=1)
    entity_resolution_depth: int = Field(ge=0, le=3)
    context_type: ContextType
    topic_continuity: float = Field(ge=0.0, le=1.0)

class ConfidenceResult(BaseModel):
    """Output of the ConfidenceRouter."""
    alpha: float = Field(ge=0.05, le=0.95)
    tier: ConfidenceTier
    signals: ConfidenceSignals
    signal_contributions: dict[str, float]
    fade_adjustment: float = 0.0
    fade_reason: Optional[str] = None

class ResponseSegment(BaseModel):
    """A planned segment of the response."""
    segment_type: SegmentType
    alpha: float = Field(ge=0.0, le=1.0)
    cost_budget: float
    selected_lines: list[VoiceLine] = []

class SegmentPlan(BaseModel):
    """Full response plan."""
    segments: list[ResponseSegment]
    total_alpha: float
    expected_length: str  # "short" | "medium" | "long"
```

### VoiceSeed — The Output Contract

```python
class VoiceSeed(BaseModel):
    """The voice injection block. Only contract with context_builder."""
    source: VoiceSeedSource

    alpha: float = 0.5
    tier: ConfidenceTier = ConfidenceTier.ENGAGING

    opener_seed: Optional[str] = None
    opener_weight: float = 0.0
    tone_hints: list[str] = []

    example_lines: list[str] = []
    anti_patterns: list[str] = []

    engine_active: bool = False
    corpus_active: bool = False

    def to_prompt_block(self) -> str:
        """Render as XML block for context_builder injection."""
        if self.source == VoiceSeedSource.NONE:
            return ""

        parts = [f'<luna_voice source="{self.source.value}">']
        parts.append(f'  <confidence alpha="{self.alpha:.2f}" tier="{self.tier.value}" />')

        if self.opener_seed:
            parts.append(f'  <opener seed="{self.opener_seed}" weight="{self.opener_weight:.2f}" />')

        if self.tone_hints:
            parts.append(f'  <tone hints="{", ".join(self.tone_hints)}" />')

        if self.example_lines:
            parts.append('  <examples>')
            for line in self.example_lines:
                parts.append(f'    <say>{line}</say>')
            parts.append('  </examples>')

        if self.anti_patterns:
            parts.append('  <avoid>')
            for ap in self.anti_patterns:
                parts.append(f'    <never>{ap}</never>')
            parts.append('  </avoid>')

        parts.append('</luna_voice>')
        return "\n".join(parts)

    def token_estimate(self) -> int:
        """Approximate token count of the injection block."""
        block = self.to_prompt_block()
        return len(block.split()) + len(block) // 4
```

### Config Model

```python
from pydantic import validator

class VoiceSystemConfig(BaseModel):
    """Top-level voice system configuration."""

    blend_engine_mode: EngineMode = EngineMode.ACTIVE
    voice_corpus_mode: EngineMode = EngineMode.ACTIVE

    alpha_override: Optional[float] = None
    corpus_tier_override: Optional[str] = None

    bypass_confidence_router: bool = False
    bypass_segment_planner: bool = False
    bypass_line_sampler: bool = False
    bypass_fade_controller: bool = False

    line_bank_path: str = "data/voice/line_bank.json"
    corpus_path: str = "data/voice/corpus.json"

    log_alpha: bool = True
    log_line_selection: bool = True
    log_injection: bool = False
    log_shadow_diff: bool = True

    @validator('alpha_override')
    def validate_alpha(cls, v):
        if v is not None and not (0.0 <= v <= 1.0):
            raise ValueError('alpha must be 0.0-1.0')
        return v

    @classmethod
    def from_yaml(cls, path: str) -> "VoiceSystemConfig":
        import yaml
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**data.get("voice_system", {}))
```

---

## Service: VoiceCorpusService

File: `src/luna/voice/corpus_service.py`

```python
class VoiceCorpusService:
    """Static voice corpus — the reliable fallback.

    No confidence routing. No alpha. No segment planning.
    Just: here's how Luna talks, here's what she never says.
    """

    def __init__(self, config: VoiceSystemConfig):
        self.config = config
        self.bank: LineBank = self._load_bank(config.corpus_path)

    def generate_seed(
        self,
        context_type: ContextType,
        turn_number: int,
        emotional_register: Optional[EmotionalRegister] = None,
    ) -> VoiceSeed:
        """Generate a static voice seed from the corpus.

        Selection logic:
        1. Pick tier from turn number (simple threshold, no alpha)
        2. Filter lines by context_type tags
        3. If emotional_register provided, prefer matching lines
        4. Select top 2-3 by cost (prefer distinctive)
        5. Always include critical anti-patterns
        """
        # Simple tier mapping
        if turn_number <= 1:
            tier = ConfidenceTier.GROUNDING
        elif turn_number <= 2:
            tier = ConfidenceTier.ENGAGING
        else:
            tier = ConfidenceTier.FLOWING

        if self.config.corpus_tier_override:
            tier = ConfidenceTier(self.config.corpus_tier_override)

        # Filter
        candidates = self.bank.by_tier(tier)
        if context_type:
            tagged = [l for l in candidates if context_type.value in l.context_tags]
            if tagged:
                candidates = tagged

        if emotional_register:
            reg_match = [l for l in candidates if l.emotional_register == emotional_register]
            if reg_match:
                candidates = reg_match

        # Sort by cost descending, take top 3
        candidates.sort(key=lambda l: l.cost, reverse=True)
        selected = candidates[:3]

        return VoiceSeed(
            source=VoiceSeedSource.CORPUS,
            alpha=0.5,
            tier=tier,
            opener_seed=selected[0].text if selected else None,
            opener_weight=0.5,
            tone_hints=[r.value for r in set(l.emotional_register for l in selected)],
            example_lines=[l.text for l in selected],
            anti_patterns=[a.phrase for a in self.bank.critical_anti_patterns()],
            engine_active=False,
            corpus_active=True,
        )

    def _load_bank(self, path: str) -> LineBank:
        with open(path) as f:
            return LineBank.model_validate_json(f.read())
```

---

## Service: VoiceBlendEngine

File: `src/luna/voice/blend_engine.py`

### Alpha Formula

```
alpha = clamp(
    w_memory * (1 - memory_score)
    + w_turn * decay(turn_number)
    + w_entity * (1 - entity_depth / 3)
    + w_context * context_penalty(type)
    + w_continuity * (1 - topic_continuity)
, 0.05, 0.95)
```

**Weights:**
- w_memory = 0.35 (strongest signal)
- w_turn = 0.25 (natural decay)
- w_entity = 0.15 (entity richness)
- w_context = 0.15 (type-specific)
- w_continuity = 0.10 (thread coherence)

**Turn decay:** `max(0, 1 - (turn-1) * 0.3)` → Turn 1=1.0, Turn 2=0.7, Turn 3=0.4, Turn 4+=0.1

**Context penalties:**
- cold_start: 0.9
- greeting: 0.7
- topic_shift: 0.6
- creative: 0.5
- emotional: 0.4
- technical: 0.3
- memory_recall: 0.2
- follow_up: 0.1

**Tier mapping:** alpha > 0.6 = GROUNDING, > 0.3 = ENGAGING, else FLOWING

### Five-Stage Pipeline

Each stage independently bypassable via config. Bypass uses passthrough defaults.

```python
class VoiceBlendEngine:
    W_MEMORY = 0.35
    W_TURN = 0.25
    W_ENTITY = 0.15
    W_CONTEXT = 0.15
    W_CONTINUITY = 0.10

    CONTEXT_PENALTIES = {
        ContextType.COLD_START: 0.9,
        ContextType.GREETING: 0.7,
        ContextType.TOPIC_SHIFT: 0.6,
        ContextType.CREATIVE: 0.5,
        ContextType.EMOTIONAL: 0.4,
        ContextType.TECHNICAL: 0.3,
        ContextType.MEMORY_RECALL: 0.2,
        ContextType.FOLLOW_UP: 0.1,
    }

    def __init__(self, config: VoiceSystemConfig):
        self.config = config
        self.bank: LineBank = self._load_bank(config.line_bank_path)
        self._alpha_history: list[float] = []
        self._turn_history: list[ContextType] = []

    def generate_seed(self, signals: ConfidenceSignals) -> VoiceSeed:
        """Full pipeline: signals → alpha → fade → segments → lines → seed"""
        confidence = self._compute_confidence(signals)
        confidence = self._apply_fade(confidence, signals)
        plan = self._plan_segments(confidence)
        plan = self._sample_lines(plan, signals)
        seed = self._assemble_seed(confidence, plan)
        self._alpha_history.append(confidence.alpha)
        self._turn_history.append(signals.context_type)
        return seed

    def reset_conversation(self):
        """Reset fade state for new conversation."""
        self._alpha_history.clear()
        self._turn_history.clear()

    def _load_bank(self, path: str) -> LineBank:
        with open(path) as f:
            return LineBank.model_validate_json(f.read())
```

**Stage 1 — ConfidenceRouter:** Compute alpha from signals using formula above. If `bypass_confidence_router`, return alpha=0.5 default.

**Stage 2 — FadeController:** Adjust alpha based on conversation history.
- Turn 3: subtract 0.2 (blend phase)
- Turn 4+: cap at 0.15 (freeform floor)
- Context switch detected: reset (no fade adjustment)
- Emotional context: cap at 0.40 (scaffolded empathy feels fake)
- Memory score > 0.8: drop alpha by 0.3 (she found her footing)
- If `bypass_fade_controller`, skip all adjustments.

**Stage 3 — SegmentPlanner:** Distribute alpha across response segments, front-loaded.
- opener.alpha = alpha * 1.3 (capped at 0.95)
- body.alpha = alpha * 0.8
- closer.alpha = alpha * 0.5
- If alpha < 0.3, single opener segment only.
- If `bypass_segment_planner`, return one segment with uniform alpha.

**Stage 4 — LineSampler:** Score candidates by cost alignment with segment budget.
- Filter by tier, segment_type, context_tags
- Score: `cost_alignment = 1 - |line.cost - segment.cost_budget| / 5`
- Take top 3 per segment
- If `bypass_line_sampler`, return plan with empty selected_lines.

**Stage 5 — BlendAssembler:** Build VoiceSeed from confidence + plan. Engine doesn't inject anti-patterns (Corpus owns those).

Full implementation in the interactive spec artifact (see `luna_voice_system_spec.jsx`, Services tab).

---

## Service: VoiceSystemOrchestrator

File: `src/luna/voice/orchestrator.py`

```python
class VoiceSystemOrchestrator:
    """Single entry point for context_builder. Manages both engines."""

    def __init__(self, config: VoiceSystemConfig):
        self.config = config
        self.engine: Optional[VoiceBlendEngine] = None
        self.corpus: Optional[VoiceCorpusService] = None
        self._logger = VoiceSystemLogger(config)

        if config.blend_engine_mode != EngineMode.OFF:
            self.engine = VoiceBlendEngine(config)
        if config.voice_corpus_mode != EngineMode.OFF:
            self.corpus = VoiceCorpusService(config)

    def generate_voice_block(
        self,
        signals: ConfidenceSignals,
        context_type: ContextType,
        turn_number: int,
        emotional_register: Optional[EmotionalRegister] = None,
    ) -> str:
        """THE interface. Returns string to inject into prompt, or ""."""
        engine_seed = None
        corpus_seed = None

        if self.engine:
            engine_seed = self.engine.generate_seed(signals)
            if self.config.blend_engine_mode == EngineMode.SHADOW:
                self._logger.log_shadow("engine", engine_seed)
                engine_seed = None

        if self.corpus:
            corpus_seed = self.corpus.generate_seed(
                context_type, turn_number, emotional_register
            )
            if self.config.voice_corpus_mode == EngineMode.SHADOW:
                self._logger.log_shadow("corpus", corpus_seed)
                corpus_seed = None

        final = self._merge(engine_seed, corpus_seed)
        self._logger.log_generation(signals, engine_seed, corpus_seed, final)
        return final.to_prompt_block()

    def _merge(self, engine_seed, corpus_seed) -> VoiceSeed:
        if not engine_seed and not corpus_seed:
            return VoiceSeed(source=VoiceSeedSource.NONE)
        if engine_seed and not corpus_seed:
            return engine_seed
        if corpus_seed and not engine_seed:
            return corpus_seed

        # Both: engine wins on confidence/opener, corpus provides kill list
        return VoiceSeed(
            source=VoiceSeedSource.MERGED,
            alpha=engine_seed.alpha,
            tier=engine_seed.tier,
            opener_seed=engine_seed.opener_seed,
            opener_weight=engine_seed.opener_weight,
            tone_hints=list(set(engine_seed.tone_hints + corpus_seed.tone_hints)),
            example_lines=engine_seed.example_lines or corpus_seed.example_lines,
            anti_patterns=corpus_seed.anti_patterns,
            engine_active=True,
            corpus_active=True,
        )

    def on_conversation_start(self):
        if self.engine:
            self.engine.reset_conversation()

    def on_config_change(self, new_config: VoiceSystemConfig):
        """Hot-reload without restart."""
        self.config = new_config
        if new_config.blend_engine_mode == EngineMode.OFF:
            self.engine = None
        elif not self.engine:
            self.engine = VoiceBlendEngine(new_config)
        if new_config.voice_corpus_mode == EngineMode.OFF:
            self.corpus = None
        elif not self.corpus:
            self.corpus = VoiceCorpusService(new_config)
```

---

## Integration: context_builder.py

Single touchpoint. Add to existing `build_context` method:

```python
# In context_builder.py

from luna.voice.orchestrator import VoiceSystemOrchestrator
from luna.voice.models import VoiceSystemConfig, ConfidenceSignals

class ContextBuilder:
    def __init__(self, ...existing_params, voice_config_path: str = None):
        self.voice_system: Optional[VoiceSystemOrchestrator] = None
        if voice_config_path:
            config = VoiceSystemConfig.from_yaml(voice_config_path)
            self.voice_system = VoiceSystemOrchestrator(config)

    def build_context(self, ...existing_params) -> str:
        # ... existing kernel, virtues, memory assembly ...

        voice_block = ""
        if self.voice_system:
            voice_block = self.voice_system.generate_voice_block(
                signals=ConfidenceSignals(
                    memory_retrieval_score=self._last_retrieval_score,
                    turn_number=self._turn_count,
                    entity_resolution_depth=self._entity_depth,
                    context_type=self._detected_context_type,
                    topic_continuity=self._topic_continuity,
                ),
                context_type=self._detected_context_type,
                turn_number=self._turn_count,
            )

        # Inject between personality and history
        return self._assemble(
            kernel=kernel_block,
            virtues=virtues_block,
            voice=voice_block,      # ← NEW. Empty string if system off.
            memory=memory_block,
            history=history_block,
        )
```

---

## Config File

File: `src/luna/voice/data/voice_config.yaml`

```yaml
voice_system:
  blend_engine_mode: "off"        # Start with corpus only (Phase 1)
  voice_corpus_mode: "active"

  alpha_override: null
  corpus_tier_override: null

  bypass:
    confidence_router: false
    segment_planner: false
    line_sampler: false
    fade_controller: false

  line_bank_path: "data/voice/line_bank.json"
  corpus_path: "data/voice/corpus.json"

  logging:
    alpha_per_turn: true
    line_selection: true
    injection_block: false
    shadow_diff: true
```

---

## Sample Corpus Data

File: `src/luna/voice/data/corpus.json`

```json
{
  "version": "1.0",
  "updated_at": "2026-02-17T00:00:00Z",
  "lines": [
    {
      "id": "grnd_001",
      "text": "hmm, I have some thoughts but catch me up first",
      "cost": 4,
      "tier": "GROUNDING",
      "context_tags": ["cold-start", "honest", "patient"],
      "emotional_register": "warm",
      "segment_type": "opener",
      "source": null
    },
    {
      "id": "grnd_002",
      "text": "haven't touched that in a bit, fill me in?",
      "cost": 3,
      "tier": "GROUNDING",
      "context_tags": ["topic-shift", "curious", "honest"],
      "emotional_register": "warm",
      "segment_type": "opener",
      "source": null
    },
    {
      "id": "grnd_003",
      "text": "oh interesting — where are we with this?",
      "cost": 3,
      "tier": "GROUNDING",
      "context_tags": ["re-entry", "curious"],
      "emotional_register": "warm",
      "segment_type": "opener",
      "source": null
    },
    {
      "id": "grnd_004",
      "text": "before I go deep on this — are we exploring or deciding?",
      "cost": 4,
      "tier": "GROUNDING",
      "context_tags": ["scoping", "direct"],
      "emotional_register": "direct",
      "segment_type": "clarifier",
      "source": null
    },
    {
      "id": "eng_001",
      "text": "ok so is this the [A] thing or the [B] thing?",
      "cost": 4,
      "tier": "ENGAGING",
      "context_tags": ["clarifying", "tracking"],
      "emotional_register": "direct",
      "segment_type": "clarifier",
      "source": null
    },
    {
      "id": "eng_002",
      "text": "wait, this connects to what we were doing with [entity]",
      "cost": 3,
      "tier": "ENGAGING",
      "context_tags": ["connecting", "memory"],
      "emotional_register": "warm",
      "segment_type": "bridge",
      "source": null
    },
    {
      "id": "eng_003",
      "text": "I remember something about this — the [detail] part?",
      "cost": 3,
      "tier": "ENGAGING",
      "context_tags": ["recalling", "honest"],
      "emotional_register": "uncertain",
      "segment_type": "opener",
      "source": null
    },
    {
      "id": "eng_004",
      "text": "ugh, again? what's it doing this time?",
      "cost": 4,
      "tier": "ENGAGING",
      "context_tags": ["empathetic", "direct", "frustration-mirror"],
      "emotional_register": "direct",
      "segment_type": "reaction",
      "source": null
    },
    {
      "id": "flow_001",
      "text": "honestly? I think [direct opinion]",
      "cost": 3,
      "tier": "FLOWING",
      "context_tags": ["opinionated", "confident"],
      "emotional_register": "direct",
      "segment_type": "opener",
      "source": null
    },
    {
      "id": "flow_002",
      "text": "nah, that won't work. the real issue is [reframe]",
      "cost": 5,
      "tier": "FLOWING",
      "context_tags": ["pushback", "reframe"],
      "emotional_register": "direct",
      "segment_type": "opener",
      "source": null
    },
    {
      "id": "flow_003",
      "text": "oh that's actually interesting — I hadn't thought about it that way",
      "cost": 3,
      "tier": "FLOWING",
      "context_tags": ["surprised", "open"],
      "emotional_register": "warm",
      "segment_type": "reaction",
      "source": null
    },
    {
      "id": "flow_004",
      "text": "yeah that tracks",
      "cost": 2,
      "tier": "FLOWING",
      "context_tags": ["affirming", "casual"],
      "emotional_register": "warm",
      "segment_type": "reaction",
      "source": null
    }
  ],
  "anti_patterns": [
    { "phrase": "certainly", "reason": "butler energy", "severity": 3 },
    { "phrase": "I'd be happy to", "reason": "service desk energy", "severity": 3 },
    { "phrase": "That's a great question!", "reason": "teacher's pet energy", "severity": 3 },
    { "phrase": "How can I help you today?", "reason": "call center energy", "severity": 3 },
    { "phrase": "As an AI", "reason": "identity crisis energy", "severity": 3 },
    { "phrase": "Here are some key points", "reason": "listicle energy", "severity": 3 },
    { "phrase": "absolutely", "reason": "sycophant energy", "severity": 2 },
    { "phrase": "Is there anything else", "reason": "checkout counter energy", "severity": 2 },
    { "phrase": "I appreciate you sharing", "reason": "therapy bot energy", "severity": 2 },
    { "phrase": "Let me help you explore", "reason": "museum guide energy", "severity": 2 },
    { "phrase": "Great choice!", "reason": "waiter energy", "severity": 1 },
    { "phrase": "That's a wonderful", "reason": "kindergarten teacher energy", "severity": 1 }
  ]
}
```

---

## Test Strategy

### test_models.py
- All models serialize/deserialize correctly
- VoiceSeed.to_prompt_block() produces valid XML for all source types
- VoiceSeed.to_prompt_block() returns "" when source=NONE
- LineBank.by_tier() and by_tags() filter correctly
- VoiceSystemConfig.from_yaml() loads correctly
- Alpha override validation (0.0-1.0)

### test_corpus.py
- Generates VoiceSeed with source=CORPUS
- Tier selection from turn number (1→GROUNDING, 2→ENGAGING, 3+→FLOWING)
- Context tag filtering narrows candidates
- Emotional register preference works
- Always includes critical anti-patterns (severity=3)
- Empty line bank returns VoiceSeed with no opener
- Corpus tier override works

### test_engine.py
- Alpha formula produces expected values for known inputs
- Alpha clamped to [0.05, 0.95]
- FadeController: turn 3 reduces by 0.2
- FadeController: turn 4+ caps at 0.15
- FadeController: context switch resets alpha
- FadeController: emotional caps at 0.40
- FadeController: strong memory drops by 0.3
- Segment plan front-loads alpha (opener > body > closer)
- Low alpha (< 0.3) produces single-segment plan
- LineSampler respects tier and segment_type filters
- Each bypass config skips its stage cleanly
- reset_conversation() clears fade history

### test_orchestrator.py
- Both off → empty string
- Only corpus → corpus seed
- Only engine → engine seed, no anti-patterns
- Both active → merged (engine confidence + corpus kill list)
- Shadow engine → corpus active, engine logged not injected
- Shadow corpus → engine active, corpus logged not injected
- Both shadow → both logged, neither injected, empty output
- on_conversation_start() resets engine state
- on_config_change() hot-reloads correctly

### test_toggle_scenarios.py
- Verify all 7 toggle combinations from priority chain table
- Verify prompt is identical with both off vs no voice system at all
- Verify shadow mode produces identical output to "off" mode
- Verify config changes take effect next call without restart

---

## Invariants

These must always be true. Test for each:

1. Both engines off → prompt identical to pre-voice-system Luna
2. Shadow mode → zero impact on model output
3. Corpus alone → works without Engine being built
4. Engine alone → works without Corpus (no kill list, but functional)
5. Config change → takes effect next turn, no restart
6. `VoiceSeed.to_prompt_block()` → empty string when source=NONE
7. `context_builder` → only talks to `VoiceSystemOrchestrator`, never engines directly
8. Voice system is read-only — never modifies memory, entities, or session state

---

## Implementation Phases

### Phase 1: Voice Corpus (SHIP FIRST)
**Effort:** 2-3 days  
**Config:** `blend_engine_mode: "off"`, `voice_corpus_mode: "active"`

Build:
- `models.py` — VoiceLine, AntiPattern, LineBank, VoiceSeed, VoiceSystemConfig
- `corpus_service.py` — VoiceCorpusService
- `orchestrator.py` — skeleton with corpus-only path
- `data/corpus.json` — hand-curated 12+ starter lines (expand to 50-80)
- `data/voice_config.yaml` — corpus-only config
- `context_builder.py` — integration (voice_block injection point)
- All corpus and toggle tests

### Phase 2: Confidence Router + Greedy Sampler
**Effort:** 2-3 days  
**Config:** `blend_engine_mode: "active"`, `voice_corpus_mode: "active"`

Build:
- `models.py` — add ConfidenceSignals, ConfidenceResult, SegmentPlan
- `blend_engine.py` — ConfidenceRouter + LineSampler (no fade yet)
- `orchestrator.py` — full merge logic
- Engine tests

### Phase 3: FadeController + Segment Planner
**Effort:** 1-2 days

Build:
- `blend_engine.py` — add FadeController and SegmentPlanner stages
- Conversation trace tests (multi-turn alpha decay, context switch reset)

### Phase 4: Observability + Shadow Mode
**Effort:** 1-2 days

Build:
- `logger.py` — VoiceSystemLogger with structured logging
- Shadow mode paths in orchestrator
- Observable dashboard integration (Observatory panel)

### Phase 5: Forge Integration (Future)
**Effort:** 2-3 days

Build:
- Forge → line_bank auto-extraction pipeline
- Cost calibration from measured anchoring effectiveness
- Line bank expansion from real sessions

---

## Latency & Token Impact

- **Compute:** Microseconds. Five multiplications + linear scan over ~80 lines. Hidden behind memory retrieval latency.
- **Token overhead:** 120-180 tokens at high alpha (turn 1), 20-30 tokens at low alpha (turn 4+). ~3-5% of context at worst. Decays over conversation.
- **No additional inference calls.** Engine is pure prompt engineering with light math.

---

## Reference Artifacts

Interactive specs built during this design session:

- `luna_voice_manual.jsx` — Voice DNA, behavior tree tiers, kill list, Ahab patterns
- `dual_llm_brain.jsx` — Token partition algorithm the engine is adapted from
- `voice_blend_engine.jsx` — Full architecture spec with live alpha simulator
- `voice_blend_sim.jsx` — Output simulation showing engine behavior across 4 scenarios
- `luna_voice_system_spec.jsx` — Unified system spec with Pydantic models, services, config
