import React, { useState, useEffect } from 'react';

// ═══════════════════════════════════════════════════════════════
// LUNA VOICE SYSTEM — Unified Handoff Specification
// Two engines. One voice. Full toggle control.
// ═══════════════════════════════════════════════════════════════
//
// SYSTEM OVERVIEW:
// ┌─────────────────────────────────────────────────────┐
// │              Luna Voice System                       │
// │                                                      │
// │  ┌──────────────┐     ┌──────────────────────────┐  │
// │  │ Voice Corpus  │     │  Voice Blend Engine       │  │
// │  │ (Fallback)    │     │  (Primary)                │  │
// │  │               │     │                           │  │
// │  │ Static lines  │     │ ConfidenceRouter          │  │
// │  │ Few-shot      │     │ SegmentPlanner            │  │
// │  │ Kill list     │     │ LineSampler               │  │
// │  │ Context tags  │     │ FadeController            │  │
// │  │               │     │ BlendAssembler            │  │
// │  └───────┬───────┘     └────────────┬─────────────┘  │
// │          │                          │                 │
// │          ▼                          ▼                 │
// │  ┌──────────────────────────────────────────────┐    │
// │  │         VoiceSystemOrchestrator               │    │
// │  │   Priority: Engine > Corpus > None            │    │
// │  │   Modes: active / shadow / off                │    │
// │  └──────────────────┬───────────────────────────┘    │
// │                     │                                 │
// │                     ▼                                 │
// │              <luna_voice> block                       │
// │         injected into context_builder                 │
// └─────────────────────────────────────────────────────┘
// ═══════════════════════════════════════════════════════════════

const S1 = '#c8ff00';
const S2 = '#00b4ff';
const WARN = '#ff6b6b';
const PURPLE = '#b388ff';
const MUTED = 'rgba(255,255,255,0.35)';
const BG = '#0a0a0f';
const CARD = 'rgba(255,255,255,0.02)';
const BORDER = 'rgba(255,255,255,0.05)';

const Mono = ({ children, style, ...p }) => (
  <span style={{ fontFamily: "'IBM Plex Mono', monospace", ...style }} {...p}>{children}</span>
);

const Code = ({ children, maxHeight, accent = S1 }) => (
  <pre style={{
    padding: '16px 20px', background: 'rgba(0,0,0,0.3)', borderRadius: 8,
    border: `1px solid ${BORDER}`, fontFamily: "'IBM Plex Mono', monospace",
    fontSize: 11, lineHeight: 1.65, color: `${accent}90`,
    overflowX: 'auto', overflowY: maxHeight ? 'auto' : 'visible',
    maxHeight: maxHeight || 'none', whiteSpace: 'pre-wrap', margin: 0,
  }}>{children}</pre>
);

const SectionHead = ({ title, subtitle, accent = S1 }) => (
  <div style={{ marginBottom: 20 }}>
    <h2 style={{ fontFamily: "'Space Mono', monospace", fontSize: 13, fontWeight: 700, color: accent, letterSpacing: '0.1em', textTransform: 'uppercase', margin: 0 }}>{title}</h2>
    {subtitle && <p style={{ fontSize: 13, color: MUTED, margin: '6px 0 0', lineHeight: 1.5 }}>{subtitle}</p>}
  </div>
);

const SchemaField = ({ name, type, desc, required = true, color = S1 }) => (
  <div style={{ display: 'grid', gridTemplateColumns: '180px 120px 1fr', gap: 8, marginBottom: 3, padding: '5px 0', borderBottom: '1px solid rgba(255,255,255,0.02)' }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <Mono style={{ fontSize: 11, color: `${color}aa` }}>{name}</Mono>
      {!required && <Mono style={{ fontSize: 8, color: 'rgba(255,255,255,0.15)', padding: '1px 4px', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 3 }}>opt</Mono>}
    </div>
    <Mono style={{ fontSize: 10, color: 'rgba(255,255,255,0.2)' }}>{type}</Mono>
    <span style={{ fontSize: 11, color: MUTED }}>{desc}</span>
  </div>
);

const TABS = ['Overview', 'Pydantic Models', 'Services', 'Config & Toggles', 'File Layout', 'Phases'];

// ─── TAB CONTENT ──────────────────────────────────────────────

const Overview = () => (
  <div>
    <SectionHead title="System Architecture" subtitle="Two engines, one orchestrator, full toggle control. The Blend Engine is smart. The Corpus is reliable. Together they cover every scenario." />

    <Code>{`PRIORITY CHAIN:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Engine ON + Corpus ON  → Engine produces seed, Corpus provides kill list
  Engine ON + Corpus OFF → Engine only, no static guardrails  
  Engine OFF + Corpus ON → Static few-shot injection (the fallback)
  Engine OFF + Corpus OFF → Raw Luna, personality prompt only
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SHADOW MODE (per-engine):
  Engine shadow  → computes everything, logs everything, injects nothing
  Corpus shadow  → selects lines, logs selection, injects nothing
  Both shadow    → full observability, zero impact on output

DATA FLOW:
  
  PersonaCore (who Luna is)
       │
       ▼
  ┌─── VoiceSystemOrchestrator ───────────────────────┐
  │                                                     │
  │   ┌─────────────────────┐  ┌───────────────────┐   │
  │   │  VoiceBlendEngine   │  │  VoiceCorpus      │   │
  │   │                     │  │                    │   │
  │   │  signals ──► alpha  │  │  context ──► lines │   │
  │   │  alpha ──► segments │  │  lines ──► block   │   │
  │   │  segments ──► lines │  │  kill list ──► ✗   │   │
  │   │  lines ──► seed     │  │                    │   │
  │   └────────┬────────────┘  └────────┬──────────┘   │
  │            │                        │               │
  │            ▼                        ▼               │
  │   ┌────────────────────────────────────────────┐   │
  │   │          Merge & Deduplicate                │   │
  │   │  Engine seed + Corpus kill list + tone      │   │
  │   └────────────────┬───────────────────────────┘   │
  └────────────────────┼───────────────────────────────┘
                       │
                       ▼
              <luna_voice> block
            injected into prompt
                       │
                       ▼
              context_builder.py`}</Code>

    <div style={{ marginTop: 28 }}>
      <SectionHead title="Decision Log" subtitle="Key architectural choices and their trade-offs" />
      {[
        { decision: "Two separate engines, not one", why: "Corpus is dead simple, zero dependencies. Engine is complex, many failure modes. Separating them means the fallback can't be broken by the primary.", tradeoff: "Slight duplication in line storage. Worth it for isolation." },
        { decision: "Orchestrator merges outputs, not engines", why: "Each engine produces its own output independently. The orchestrator decides what to inject. No engine knows about the other.", tradeoff: "Orchestrator has merge logic. But it's trivial — just concatenate blocks." },
        { decision: "Shadow mode per-engine, not system-wide", why: "You might want Engine active + Corpus shadow (testing if the kill list adds value). Or Engine shadow + Corpus active (safe mode with observability).", tradeoff: "Config is slightly more complex. Worth it for A/B testing flexibility." },
        { decision: "Kill list lives in Corpus, not Engine", why: "Anti-patterns are static. They don't depend on confidence or alpha. They're always relevant. The Corpus owns them.", tradeoff: "Engine can't customize anti-patterns per-tier. Acceptable — the kill list is universal." },
        { decision: "Corpus injects on every turn, Engine fades", why: "The Corpus is lightweight (few-shot examples + kill list). It's cheap to always include. The Engine is heavy and should fade. Different lifecycle = different components.", tradeoff: "Slight token overhead from always-on corpus. ~60-80 tokens. Negligible." },
      ].map((d, i) => (
        <div key={i} style={{ marginBottom: 12, padding: '16px 20px', background: CARD, borderRadius: 10, border: `1px solid ${BORDER}` }}>
          <Mono style={{ fontSize: 12, color: S1, fontWeight: 600, display: 'block', marginBottom: 8 }}>{d.decision}</Mono>
          <p style={{ fontSize: 12, color: 'rgba(255,255,255,0.5)', lineHeight: 1.6, margin: '0 0 6px' }}>{d.why}</p>
          <Mono style={{ fontSize: 11, color: 'rgba(255,255,255,0.25)', fontStyle: 'italic' }}>Trade-off: {d.tradeoff}</Mono>
        </div>
      ))}
    </div>
  </div>
);

const PydanticModels = () => (
  <div>
    <SectionHead title="Pydantic Models" subtitle="All data models for both engines and the orchestrator. These are the contracts." />

    {/* VoiceSystemConfig */}
    <div style={{ marginBottom: 28, padding: 24, background: CARD, borderRadius: 12, border: `1px solid ${BORDER}` }}>
      <Mono style={{ fontSize: 14, color: PURPLE, fontWeight: 700, display: 'block', marginBottom: 4 }}>VoiceSystemConfig</Mono>
      <span style={{ fontSize: 12, color: MUTED, display: 'block', marginBottom: 16 }}>Top-level configuration. Lives in voice_config.yaml, loaded at startup.</span>
      <Code accent={PURPLE}>{`class EngineMode(str, Enum):
    ACTIVE = "active"      # Computes + injects
    SHADOW = "shadow"      # Computes + logs, no injection
    OFF = "off"            # Doesn't run at all

class VoiceSystemConfig(BaseModel):
    """Top-level voice system configuration."""
    
    # Engine toggles
    blend_engine_mode: EngineMode = EngineMode.ACTIVE
    voice_corpus_mode: EngineMode = EngineMode.ACTIVE
    
    # Engine-specific overrides
    alpha_override: Optional[float] = None  # None = computed, 0.0-1.0 = forced
    corpus_tier_override: Optional[str] = None  # None = auto, "GROUNDING"/"ENGAGING"/"FLOWING"
    
    # Component-level bypass (Blend Engine only)
    bypass_confidence_router: bool = False
    bypass_segment_planner: bool = False
    bypass_line_sampler: bool = False
    bypass_fade_controller: bool = False
    
    # Paths
    line_bank_path: str = "data/voice/line_bank.json"
    corpus_path: str = "data/voice/corpus.json"
    
    # Observability
    log_alpha: bool = True
    log_line_selection: bool = True
    log_injection: bool = False  # Verbose — logs actual seed block
    log_shadow_diff: bool = True  # Logs what shadow mode WOULD have injected
    
    @validator('alpha_override')
    def validate_alpha(cls, v):
        if v is not None and not (0.0 <= v <= 1.0):
            raise ValueError('alpha must be 0.0-1.0')
        return v`}</Code>
    </div>

    {/* Line models */}
    <div style={{ marginBottom: 28, padding: 24, background: CARD, borderRadius: 12, border: `1px solid ${BORDER}` }}>
      <Mono style={{ fontSize: 14, color: S1, fontWeight: 700, display: 'block', marginBottom: 4 }}>Line Models</Mono>
      <span style={{ fontSize: 12, color: MUTED, display: 'block', marginBottom: 16 }}>Shared by both Corpus and Engine. The line is the atomic unit.</span>
      <Code>{`class EmotionalRegister(str, Enum):
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

class ConfidenceTier(str, Enum):
    GROUNDING = "GROUNDING"    # Low confidence, high scaffolding
    ENGAGING = "ENGAGING"      # Medium confidence, moderate scaffolding
    FLOWING = "FLOWING"        # High confidence, minimal scaffolding

class VoiceLine(BaseModel):
    """A single line from Luna's voice palette."""
    id: str                                    # Unique ID, e.g. "grnd_001"
    text: str                                  # The actual line
    cost: int = Field(ge=1, le=5)              # Anchoring weight. 5 = very Luna.
    tier: ConfidenceTier                       # Which tier this belongs to
    context_tags: list[str] = []               # Situational tags
    emotional_register: EmotionalRegister      # Emotional coloring
    segment_type: SegmentType                  # Where in response this fits
    source: Optional[str] = None               # Provenance — real session ID if extracted
    
class AntiPattern(BaseModel):
    """A phrase Luna should never say."""
    phrase: str                                # The forbidden phrase
    reason: str                                # Why — for observability logs
    severity: int = Field(ge=1, le=3)          # 1=mild, 3=critical (always inject)
    
class LineBank(BaseModel):
    """The complete voice line collection."""
    version: str                               # Schema version
    lines: list[VoiceLine]                     # All lines
    anti_patterns: list[AntiPattern]           # Kill list
    updated_at: datetime                       # Last modification
    
    def by_tier(self, tier: ConfidenceTier) -> list[VoiceLine]:
        return [l for l in self.lines if l.tier == tier]
    
    def by_tags(self, tags: list[str]) -> list[VoiceLine]:
        tag_set = set(tags)
        return [l for l in self.lines if tag_set & set(l.context_tags)]
    
    def critical_anti_patterns(self) -> list[AntiPattern]:
        return [a for a in self.anti_patterns if a.severity == 3]`}</Code>
    </div>

    {/* Confidence signals */}
    <div style={{ marginBottom: 28, padding: 24, background: CARD, borderRadius: 12, border: `1px solid ${BORDER}` }}>
      <Mono style={{ fontSize: 14, color: S2, fontWeight: 700, display: 'block', marginBottom: 4 }}>Confidence & Blending Models</Mono>
      <span style={{ fontSize: 12, color: MUTED, display: 'block', marginBottom: 16 }}>Blend Engine internals. These flow through the pipeline.</span>
      <Code accent={S2}>{`class ContextType(str, Enum):
    GREETING = "greeting"
    COLD_START = "cold_start"
    TOPIC_SHIFT = "topic_shift"
    FOLLOW_UP = "follow_up"
    EMOTIONAL = "emotional"
    TECHNICAL = "technical"
    CREATIVE = "creative"
    MEMORY_RECALL = "memory_recall"

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
    signals: ConfidenceSignals          # Echo back for logging
    signal_contributions: dict[str, float]  # Per-signal breakdown
    fade_adjustment: float = 0.0        # FadeController delta
    fade_reason: Optional[str] = None   # Why fade adjusted

class ResponseSegment(BaseModel):
    """A planned segment of the response."""
    segment_type: SegmentType
    alpha: float = Field(ge=0.0, le=1.0)
    cost_budget: float
    selected_lines: list[VoiceLine] = []  # Filled by LineSampler

class SegmentPlan(BaseModel):
    """Full response plan."""
    segments: list[ResponseSegment]
    total_alpha: float                   # Weighted average alpha
    expected_length: str                 # "short" | "medium" | "long"`}</Code>
    </div>

    {/* Voice seed output */}
    <div style={{ marginBottom: 28, padding: 24, background: CARD, borderRadius: 12, border: `1px solid ${BORDER}` }}>
      <Mono style={{ fontSize: 14, color: S1, fontWeight: 700, display: 'block', marginBottom: 4 }}>VoiceSeed — The Output</Mono>
      <span style={{ fontSize: 12, color: MUTED, display: 'block', marginBottom: 16 }}>What actually gets injected into the prompt. This is the contract with context_builder.</span>
      <Code>{`class VoiceSeedSource(str, Enum):
    ENGINE = "engine"          # From VoiceBlendEngine
    CORPUS = "corpus"          # From VoiceCorpus
    MERGED = "merged"          # Both contributed
    NONE = "none"              # No voice system active

class VoiceSeed(BaseModel):
    """The voice injection block. Only contract with context_builder."""
    source: VoiceSeedSource
    
    # Confidence (from Engine, or default)
    alpha: float = 0.5
    tier: ConfidenceTier = ConfidenceTier.ENGAGING
    
    # Line seeds (from Engine or Corpus)
    opener_seed: Optional[str] = None
    opener_weight: float = 0.0
    tone_hints: list[str] = []
    
    # Examples (from Engine at high alpha, or Corpus always)
    example_lines: list[str] = []
    
    # Anti-patterns (from Corpus)
    anti_patterns: list[str] = []
    
    # Observability
    engine_active: bool = False
    corpus_active: bool = False
    
    def to_prompt_block(self) -> str:
        """Render as the XML block for context_builder injection."""
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
        return "\\n".join(parts)
    
    def token_estimate(self) -> int:
        """Approximate token count of the injection block."""
        block = self.to_prompt_block()
        return len(block.split()) + len(block) // 4  # rough estimate`}</Code>
    </div>
  </div>
);

const Services = () => (
  <div>
    <SectionHead title="Service Architecture" subtitle="Three services. Clean interfaces. Each owns its domain." />

    {/* VoiceCorpusService */}
    <div style={{ marginBottom: 28, padding: 24, background: CARD, borderRadius: 12, border: `1px solid ${BORDER}` }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
        <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#ffd93d' }} />
        <Mono style={{ fontSize: 14, color: '#ffd93d', fontWeight: 700 }}>VoiceCorpusService</Mono>
        <Mono style={{ fontSize: 10, color: 'rgba(255,255,255,0.15)', padding: '2px 8px', background: 'rgba(255,255,255,0.03)', borderRadius: 4 }}>THE FALLBACK</Mono>
      </div>
      <span style={{ fontSize: 12, color: MUTED, display: 'block', marginBottom: 16 }}>Static few-shot injection. No alpha, no confidence routing. Just curated examples of how Luna talks and what she never says. Simple, reliable, always works.</span>
      <Code accent="#ffd93d">{`class VoiceCorpusService:
    """Static voice corpus — the reliable fallback.
    
    No confidence routing. No alpha. No segment planning.
    Just: here's how Luna talks, here's what she never says.
    
    This is deliberately simple. If the Blend Engine is the
    smart system, the Corpus is the safety net that catches
    Luna when the smart system is off, broken, or learning.
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
        1. Pick tier from turn number (simple threshold)
        2. Filter lines by context_type tags
        3. If emotional_register provided, prefer matching lines
        4. Select top 2-3 examples by cost (prefer high-cost = distinctive)
        5. Always include critical anti-patterns
        
        Returns VoiceSeed with source=CORPUS
        """
        # Simple tier mapping — no alpha math
        if turn_number <= 1:
            tier = ConfidenceTier.GROUNDING
        elif turn_number <= 2:
            tier = ConfidenceTier.ENGAGING
        else:
            tier = ConfidenceTier.FLOWING
        
        # Override if configured
        if self.config.corpus_tier_override:
            tier = ConfidenceTier(self.config.corpus_tier_override)
        
        # Filter lines
        candidates = self.bank.by_tier(tier)
        if context_type:
            tagged = [l for l in candidates 
                      if context_type.value in l.context_tags]
            if tagged:  # Don't empty the pool
                candidates = tagged
        
        if emotional_register:
            reg_match = [l for l in candidates 
                         if l.emotional_register == emotional_register]
            if reg_match:
                candidates = reg_match
        
        # Sort by cost descending (most distinctive first)
        candidates.sort(key=lambda l: l.cost, reverse=True)
        selected = candidates[:3]
        
        # Build seed
        return VoiceSeed(
            source=VoiceSeedSource.CORPUS,
            alpha=0.5,  # Fixed — corpus doesn't compute alpha
            tier=tier,
            opener_seed=selected[0].text if selected else None,
            opener_weight=0.5,
            tone_hints=[r.value for r in 
                       set(l.emotional_register for l in selected)],
            example_lines=[l.text for l in selected],
            anti_patterns=[a.phrase for a in 
                          self.bank.critical_anti_patterns()],
            engine_active=False,
            corpus_active=True,
        )
    
    def _load_bank(self, path: str) -> LineBank:
        """Load line bank from JSON. Fail loud if missing."""
        with open(path) as f:
            return LineBank.model_validate_json(f.read())`}</Code>
    </div>

    {/* VoiceBlendEngine */}
    <div style={{ marginBottom: 28, padding: 24, background: CARD, borderRadius: 12, border: `1px solid ${BORDER}` }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
        <div style={{ width: 8, height: 8, borderRadius: '50%', background: S1 }} />
        <Mono style={{ fontSize: 14, color: S1, fontWeight: 700 }}>VoiceBlendEngine</Mono>
        <Mono style={{ fontSize: 10, color: 'rgba(255,255,255,0.15)', padding: '2px 8px', background: 'rgba(255,255,255,0.03)', borderRadius: 4 }}>THE PRIMARY</Mono>
      </div>
      <span style={{ fontSize: 12, color: MUTED, display: 'block', marginBottom: 16 }}>Confidence-weighted scaffolding. Computes alpha from live signals, plans segments, samples lines, fades over turns. The smart system.</span>
      <Code>{`class VoiceBlendEngine:
    """Confidence-weighted voice scaffolding engine.
    
    Pipeline: signals → alpha → segments → lines → seed
    Each stage is independently bypassable via config.
    """
    
    # Weight constants
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
        self._alpha_history: list[float] = []  # For FadeController
        self._turn_history: list[ContextType] = []
    
    def generate_seed(self, signals: ConfidenceSignals) -> VoiceSeed:
        """Full pipeline: signals → alpha → segments → lines → seed"""
        
        # Stage 1: Confidence Router
        confidence = self._compute_confidence(signals)
        
        # Stage 2: Fade Controller
        confidence = self._apply_fade(confidence, signals)
        
        # Stage 3: Segment Planner
        plan = self._plan_segments(confidence)
        
        # Stage 4: Line Sampler
        plan = self._sample_lines(plan, signals)
        
        # Stage 5: Assemble
        seed = self._assemble_seed(confidence, plan)
        
        # Record history
        self._alpha_history.append(confidence.alpha)
        self._turn_history.append(signals.context_type)
        
        return seed
    
    def _compute_confidence(self, s: ConfidenceSignals) -> ConfidenceResult:
        """Stage 1: Compute alpha from signals."""
        if self.config.bypass_confidence_router:
            return ConfidenceResult(
                alpha=self.config.alpha_override or 0.5,
                tier=ConfidenceTier.ENGAGING,
                signals=s, signal_contributions={}, 
            )
        
        if self.config.alpha_override is not None:
            alpha = self.config.alpha_override
        else:
            decay = max(0.0, 1.0 - (s.turn_number - 1) * 0.3)
            ctx_pen = self.CONTEXT_PENALTIES.get(s.context_type, 0.5)
            
            contributions = {
                "memory": self.W_MEMORY * (1 - s.memory_retrieval_score),
                "turn": self.W_TURN * decay,
                "entity": self.W_ENTITY * (1 - s.entity_resolution_depth / 3),
                "context": self.W_CONTEXT * ctx_pen,
                "continuity": self.W_CONTINUITY * (1 - s.topic_continuity),
            }
            
            raw = sum(contributions.values())
            alpha = max(0.05, min(0.95, raw))
        
        tier = (ConfidenceTier.GROUNDING if alpha > 0.6
                else ConfidenceTier.ENGAGING if alpha > 0.3
                else ConfidenceTier.FLOWING)
        
        return ConfidenceResult(
            alpha=alpha, tier=tier, signals=s,
            signal_contributions=contributions,
        )
    
    def _apply_fade(
        self, conf: ConfidenceResult, signals: ConfidenceSignals
    ) -> ConfidenceResult:
        """Stage 2: FadeController adjusts alpha over conversation."""
        if self.config.bypass_fade_controller:
            return conf
        
        alpha = conf.alpha
        reason = None
        adjustment = 0.0
        
        # Context switch detection
        is_switch = (self._turn_history and 
                     signals.context_type == ContextType.TOPIC_SHIFT)
        
        if is_switch:
            reason = "context switch — alpha reset"
            # Don't apply turn-based fade on switches
        elif signals.turn_number >= 4:
            adjustment = -0.15
            alpha = max(0.05, min(alpha + adjustment, 0.15))
            reason = f"turn {signals.turn_number} — floor at 0.15"
        elif signals.turn_number >= 3:
            adjustment = -0.2
            alpha = max(0.05, alpha + adjustment)
            reason = f"turn {signals.turn_number} — blend phase"
        
        # Emotional cap
        if signals.context_type == ContextType.EMOTIONAL:
            if alpha > 0.4:
                alpha = 0.4
                reason = (reason or "") + " + emotional cap at 0.40"
        
        # Strong memory hit
        if signals.memory_retrieval_score > 0.8:
            alpha = max(0.05, alpha - 0.3)
            reason = (reason or "") + " + strong memory → drop 0.3"
        
        # Recompute tier
        tier = (ConfidenceTier.GROUNDING if alpha > 0.6
                else ConfidenceTier.ENGAGING if alpha > 0.3
                else ConfidenceTier.FLOWING)
        
        return ConfidenceResult(
            alpha=alpha, tier=tier, signals=signals,
            signal_contributions=conf.signal_contributions,
            fade_adjustment=adjustment,
            fade_reason=reason,
        )
    
    def _plan_segments(self, conf: ConfidenceResult) -> SegmentPlan:
        """Stage 3: Plan response segments with per-segment alpha."""
        if self.config.bypass_segment_planner:
            return SegmentPlan(
                segments=[ResponseSegment(
                    segment_type=SegmentType.OPENER,
                    alpha=conf.alpha,
                    cost_budget=conf.alpha * 5,
                )],
                total_alpha=conf.alpha,
                expected_length="medium",
            )
        
        # Front-load: opener strong, body moderate, closer light
        segments = [
            ResponseSegment(
                segment_type=SegmentType.OPENER,
                alpha=min(0.95, conf.alpha * 1.3),
                cost_budget=min(0.95, conf.alpha * 1.3) * 5,
            ),
            ResponseSegment(
                segment_type=SegmentType.BRIDGE,
                alpha=conf.alpha * 0.8,
                cost_budget=conf.alpha * 0.8 * 5,
            ),
            ResponseSegment(
                segment_type=SegmentType.CLOSER,
                alpha=conf.alpha * 0.5,
                cost_budget=conf.alpha * 0.5 * 5,
            ),
        ]
        
        # Drop closer if alpha is already low
        if conf.alpha < 0.3:
            segments = segments[:1]  # Opener only
        
        avg_alpha = sum(s.alpha for s in segments) / len(segments)
        return SegmentPlan(
            segments=segments, total_alpha=avg_alpha,
            expected_length="short" if len(segments) == 1 else "medium",
        )
    
    def _sample_lines(
        self, plan: SegmentPlan, signals: ConfidenceSignals
    ) -> SegmentPlan:
        """Stage 4: Sample candidate lines for each segment."""
        if self.config.bypass_line_sampler:
            return plan
        
        for segment in plan.segments:
            candidates = self.bank.by_tier(
                ConfidenceTier.GROUNDING if segment.alpha > 0.6
                else ConfidenceTier.ENGAGING if segment.alpha > 0.3
                else ConfidenceTier.FLOWING
            )
            
            # Filter by segment type
            typed = [l for l in candidates 
                     if l.segment_type == segment.segment_type]
            if typed:
                candidates = typed
            
            # Score by cost alignment
            for c in candidates:
                cost_align = 1 - abs(c.cost - segment.cost_budget) / 5
                c._score = cost_align  # Temp attribute
            
            candidates.sort(key=lambda l: getattr(l, '_score', 0), reverse=True)
            segment.selected_lines = candidates[:3]
        
        return plan
    
    def _assemble_seed(
        self, conf: ConfidenceResult, plan: SegmentPlan
    ) -> VoiceSeed:
        """Stage 5: Build the VoiceSeed output."""
        opener_lines = (plan.segments[0].selected_lines 
                       if plan.segments else [])
        
        return VoiceSeed(
            source=VoiceSeedSource.ENGINE,
            alpha=conf.alpha,
            tier=conf.tier,
            opener_seed=opener_lines[0].text if opener_lines else None,
            opener_weight=plan.segments[0].alpha if plan.segments else 0,
            tone_hints=list(set(
                l.emotional_register.value 
                for s in plan.segments 
                for l in s.selected_lines
            )),
            example_lines=[l.text for l in opener_lines[:2]],
            anti_patterns=[],  # Engine doesn't own anti-patterns
            engine_active=True,
            corpus_active=False,
        )
    
    def reset_conversation(self):
        """Reset fade state for new conversation."""
        self._alpha_history.clear()
        self._turn_history.clear()
    
    def _load_bank(self, path: str) -> LineBank:
        with open(path) as f:
            return LineBank.model_validate_json(f.read())`}</Code>
    </div>

    {/* Orchestrator */}
    <div style={{ marginBottom: 28, padding: 24, background: CARD, borderRadius: 12, border: `1px solid ${BORDER}` }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
        <div style={{ width: 8, height: 8, borderRadius: '50%', background: PURPLE }} />
        <Mono style={{ fontSize: 14, color: PURPLE, fontWeight: 700 }}>VoiceSystemOrchestrator</Mono>
        <Mono style={{ fontSize: 10, color: 'rgba(255,255,255,0.15)', padding: '2px 8px', background: 'rgba(255,255,255,0.03)', borderRadius: 4 }}>THE ROUTER</Mono>
      </div>
      <span style={{ fontSize: 12, color: MUTED, display: 'block', marginBottom: 16 }}>Manages both engines. Decides what runs. Merges outputs. Owns the toggle logic. This is the only thing context_builder talks to.</span>
      <Code accent={PURPLE}>{`class VoiceSystemOrchestrator:
    """Manages both voice engines. Single entry point for context_builder.
    
    Priority: Engine > Corpus > None
    
    Merge rules:
    - Engine provides: alpha, tier, opener_seed, example_lines, tone_hints
    - Corpus provides: anti_patterns, fallback example_lines
    - If both active: engine seed + corpus kill list = merged output
    - If only corpus: corpus seed + corpus kill list
    - If only engine: engine seed, no kill list
    - If neither: empty VoiceSeed (source=NONE)
    """
    
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
        """Generate the voice injection block for context_builder.
        
        This is THE interface. context_builder calls this once per turn
        and gets back a string to inject into the prompt. That's it.
        
        Returns empty string if both engines are off.
        """
        engine_seed = None
        corpus_seed = None
        
        # Run Blend Engine
        if self.engine:
            engine_seed = self.engine.generate_seed(signals)
            if self.config.blend_engine_mode == EngineMode.SHADOW:
                self._logger.log_shadow("engine", engine_seed)
                engine_seed = None  # Don't inject
        
        # Run Voice Corpus
        if self.corpus:
            corpus_seed = self.corpus.generate_seed(
                context_type, turn_number, emotional_register
            )
            if self.config.voice_corpus_mode == EngineMode.SHADOW:
                self._logger.log_shadow("corpus", corpus_seed)
                corpus_seed = None  # Don't inject
        
        # Merge
        final = self._merge(engine_seed, corpus_seed)
        
        # Log
        self._logger.log_generation(signals, engine_seed, corpus_seed, final)
        
        return final.to_prompt_block()
    
    def _merge(
        self,
        engine_seed: Optional[VoiceSeed],
        corpus_seed: Optional[VoiceSeed],
    ) -> VoiceSeed:
        """Merge engine and corpus outputs."""
        
        if not engine_seed and not corpus_seed:
            return VoiceSeed(source=VoiceSeedSource.NONE)
        
        if engine_seed and not corpus_seed:
            return engine_seed
        
        if corpus_seed and not engine_seed:
            return corpus_seed
        
        # Both active — merge
        return VoiceSeed(
            source=VoiceSeedSource.MERGED,
            # Engine wins on confidence
            alpha=engine_seed.alpha,
            tier=engine_seed.tier,
            # Engine wins on opener
            opener_seed=engine_seed.opener_seed,
            opener_weight=engine_seed.opener_weight,
            # Merge tone hints (deduplicate)
            tone_hints=list(set(
                engine_seed.tone_hints + corpus_seed.tone_hints
            )),
            # Engine examples take priority, corpus fills gaps
            example_lines=(
                engine_seed.example_lines or corpus_seed.example_lines
            ),
            # Corpus ALWAYS provides anti-patterns
            anti_patterns=corpus_seed.anti_patterns,
            engine_active=True,
            corpus_active=True,
        )
    
    def on_conversation_start(self):
        """Reset state for new conversation."""
        if self.engine:
            self.engine.reset_conversation()
    
    def on_config_change(self, new_config: VoiceSystemConfig):
        """Hot-reload config without restart."""
        self.config = new_config
        # Rebuild engines based on new modes
        if new_config.blend_engine_mode == EngineMode.OFF:
            self.engine = None
        elif not self.engine:
            self.engine = VoiceBlendEngine(new_config)
        
        if new_config.voice_corpus_mode == EngineMode.OFF:
            self.corpus = None
        elif not self.corpus:
            self.corpus = VoiceCorpusService(new_config)`}</Code>
    </div>
  </div>
);

const ConfigToggles = () => (
  <div>
    <SectionHead title="Configuration & Toggle System" subtitle="Every combination works. Every combination is testable. Shadow mode gives observability without risk." />

    <Code accent={PURPLE}>{`# voice_config.yaml — THE CONFIG FILE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

voice_system:

  # ─── ENGINE MODES ─────────────────────
  # active  = computes + injects into prompt
  # shadow  = computes + logs, NO injection
  # off     = doesn't run at all
  
  blend_engine_mode: "active"     # Primary: confidence-weighted scaffolding
  voice_corpus_mode: "active"     # Fallback: static few-shot + kill list

  # ─── OVERRIDES ────────────────────────
  alpha_override: null             # null = computed | 0.0-1.0 = forced
  corpus_tier_override: null       # null = auto | "GROUNDING" | "ENGAGING" | "FLOWING"

  # ─── COMPONENT BYPASS (Engine only) ───
  bypass:
    confidence_router: false       # true → default alpha 0.5
    segment_planner: false         # true → single segment, uniform alpha
    line_sampler: false            # true → no line injection, metadata only
    fade_controller: false         # true → no cross-turn memory, per-turn only

  # ─── PATHS ────────────────────────────
  line_bank_path: "data/voice/line_bank.json"
  corpus_path: "data/voice/corpus.json"

  # ─── OBSERVABILITY ────────────────────
  logging:
    alpha_per_turn: true           # Log alpha value each turn
    line_selection: true           # Log which lines were sampled
    injection_block: false         # Log the actual XML block (verbose)
    shadow_diff: true              # Log what shadow mode WOULD have done
    token_overhead: true           # Log token cost of injection`}</Code>

    <div style={{ marginTop: 28 }}>
      <SectionHead title="Toggle Scenarios" subtitle="Every valid combination and what it does" />
      {[
        { engine: 'active', corpus: 'active', name: 'Full System', desc: 'Engine computes alpha + samples lines. Corpus provides kill list. Merged output. This is the target state.', color: S1 },
        { engine: 'active', corpus: 'off', name: 'Engine Only', desc: 'Confidence routing + scaffolding, but no static anti-patterns. For testing if the kill list adds value.', color: S1 },
        { engine: 'off', corpus: 'active', name: 'Corpus Only (Fallback)', desc: 'Static few-shot injection + kill list. No alpha, no confidence routing. Simple and reliable. Ship this first.', color: '#ffd93d' },
        { engine: 'off', corpus: 'off', name: 'Raw Luna', desc: 'No voice system at all. Personality prompt only. This is the control group for A/B testing.', color: MUTED },
        { engine: 'shadow', corpus: 'active', name: 'Engine Learning', desc: 'Corpus active (safe). Engine computes but doesn\'t inject — just logs. See what it WOULD do. Zero risk.', color: S2 },
        { engine: 'active', corpus: 'shadow', name: 'Kill List Testing', desc: 'Engine active. Corpus computes but doesn\'t inject kill list — logs what it would block. Tests if anti-patterns help.', color: S2 },
        { engine: 'shadow', corpus: 'shadow', name: 'Full Observability', desc: 'Both compute, neither injects. Pure logging mode. Raw Luna output + full logs of what both systems would have done.', color: PURPLE },
      ].map((s, i) => (
        <div key={i} style={{ display: 'grid', gridTemplateColumns: '80px 80px 140px 1fr', alignItems: 'center', gap: 12, padding: '12px 16px', background: CARD, borderRadius: 8, border: `1px solid ${BORDER}`, marginBottom: 6 }}>
          <Mono style={{ fontSize: 10, color: s.engine === 'active' ? S1 : s.engine === 'shadow' ? S2 : 'rgba(255,255,255,0.15)', padding: '3px 8px', background: s.engine === 'active' ? `${S1}12` : s.engine === 'shadow' ? `${S2}12` : 'rgba(255,255,255,0.02)', borderRadius: 4, textAlign: 'center' }}>{s.engine}</Mono>
          <Mono style={{ fontSize: 10, color: s.corpus === 'active' ? '#ffd93d' : s.corpus === 'shadow' ? S2 : 'rgba(255,255,255,0.15)', padding: '3px 8px', background: s.corpus === 'active' ? 'rgba(255,217,61,0.12)' : s.corpus === 'shadow' ? `${S2}12` : 'rgba(255,255,255,0.02)', borderRadius: 4, textAlign: 'center' }}>{s.corpus}</Mono>
          <Mono style={{ fontSize: 11, color: s.color, fontWeight: 600 }}>{s.name}</Mono>
          <span style={{ fontSize: 11, color: MUTED, lineHeight: 1.4 }}>{s.desc}</span>
        </div>
      ))}
    </div>
    
    <div style={{ marginTop: 28 }}>
      <SectionHead title="Hot Reload" subtitle="Config changes take effect without restart" />
      <Code accent={PURPLE}>{`# context_builder.py integration point — the ONLY touchpoint

class ContextBuilder:
    def __init__(self, ...existing_params, voice_config_path: str = None):
        self.voice_system: Optional[VoiceSystemOrchestrator] = None
        if voice_config_path:
            config = VoiceSystemConfig.from_yaml(voice_config_path)
            self.voice_system = VoiceSystemOrchestrator(config)
    
    def build_context(self, ...existing_params) -> str:
        """Existing context building + voice injection."""
        
        # ... existing kernel, virtues, memory assembly ...
        
        # Voice injection — one call, one string, done
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
            voice=voice_block,      # ← NEW. Empty string if off.
            memory=memory_block,
            history=history_block,
        )`}</Code>
    </div>
  </div>
);

const FileLayout = () => (
  <div>
    <SectionHead title="File Layout" subtitle="Where everything lives in the project tree" />
    <Code>{`src/luna/voice/
├── __init__.py
├── models.py              # All Pydantic models (shared)
│   ├── VoiceLine
│   ├── AntiPattern
│   ├── LineBank
│   ├── ConfidenceSignals
│   ├── ConfidenceResult
│   ├── ResponseSegment
│   ├── SegmentPlan
│   ├── VoiceSeed
│   └── VoiceSystemConfig
│
├── corpus_service.py      # VoiceCorpusService (the fallback)
├── blend_engine.py        # VoiceBlendEngine (the primary)
├── orchestrator.py        # VoiceSystemOrchestrator (the router)
├── logger.py              # VoiceSystemLogger (observability)
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
    ├── test_toggle_scenarios.py   # Every mode combination
    └── fixtures/
        ├── sample_bank.json
        └── sample_config.yaml

# Integration point (existing file):
src/luna/engine/context_builder.py
  └── imports VoiceSystemOrchestrator
  └── calls generate_voice_block() once per turn`}</Code>

    <div style={{ marginTop: 28 }}>
      <SectionHead title="Data Files" subtitle="What the JSON looks like" />
      <Code accent="#ffd93d">{`// corpus.json — minimal, curated, always ships
{
  "version": "1.0",
  "updated_at": "2026-02-16T00:00:00Z",
  "lines": [
    {
      "id": "grnd_001",
      "text": "hmm, I have some thoughts but catch me up first",
      "cost": 4,
      "tier": "GROUNDING",
      "context_tags": ["cold-start", "honest"],
      "emotional_register": "warm",
      "segment_type": "opener",
      "source": null
    },
    {
      "id": "eng_001",
      "text": "ok so the [topic] — is this the [specific A] or [specific B]?",
      "cost": 4,
      "tier": "ENGAGING",
      "context_tags": ["clarifying", "tracking"],
      "emotional_register": "direct",
      "segment_type": "clarifier",
      "source": null
    },
    {
      "id": "flow_001",
      "text": "honestly? I think [direct opinion]. here's why —",
      "cost": 3,
      "tier": "FLOWING",
      "context_tags": ["opinionated"],
      "emotional_register": "direct",
      "segment_type": "opener",
      "source": null
    }
    // ... 50-80 total lines
  ],
  "anti_patterns": [
    { "phrase": "certainly", "reason": "butler energy", "severity": 3 },
    { "phrase": "I'd be happy to", "reason": "service desk energy", "severity": 3 },
    { "phrase": "That's a great question!", "reason": "teacher's pet energy", "severity": 3 },
    { "phrase": "How can I help", "reason": "call center energy", "severity": 3 },
    { "phrase": "As an AI", "reason": "identity crisis energy", "severity": 3 },
    { "phrase": "Is there anything else", "reason": "checkout counter energy", "severity": 2 },
    { "phrase": "I appreciate you sharing", "reason": "therapy bot energy", "severity": 2 }
  ]
}`}</Code>
    </div>
  </div>
);

const Phases = () => (
  <div>
    <SectionHead title="Implementation Phases" subtitle="Ship the fallback first. Add intelligence later. Each phase is independently deployable." />
    {[
      {
        phase: 1, name: "Voice Corpus (Fallback)",
        desc: "Ship the simple system first. Curate 50-80 lines from real sessions. Build VoiceCorpusService. Wire into context_builder. Toggle on/off. This alone makes Luna sound better.",
        deliverables: ["models.py (VoiceLine, AntiPattern, LineBank, VoiceSeed)", "corpus_service.py", "corpus.json (hand-curated)", "voice_config.yaml (corpus_mode only)", "context_builder integration", "test_corpus.py + test_toggle_scenarios.py"],
        effort: "2-3 days", color: '#ffd93d', priority: 'SHIP FIRST',
      },
      {
        phase: 2, name: "Confidence Router + Greedy Sampler",
        desc: "Add the brain. ConfidenceRouter reads signals from existing pipeline (memory scores, turn count, entities). Greedy per-turn alpha computation. LineSampler scores and selects from the bank.",
        deliverables: ["models.py (ConfidenceSignals, ConfidenceResult, SegmentPlan)", "blend_engine.py (router + sampler, no fade yet)", "orchestrator.py (merge logic)", "test_engine.py"],
        effort: "2-3 days", color: S1, priority: 'CORE',
      },
      {
        phase: 3, name: "FadeController + Segment Planner",
        desc: "Add conversation memory. Alpha decay over turns. Context switch detection. Per-segment alpha distribution with front-loading.",
        deliverables: ["blend_engine.py (add fade + segment planner)", "test_engine.py (conversation trace tests)"],
        effort: "1-2 days", color: S1, priority: 'REFINEMENT',
      },
      {
        phase: 4, name: "Observability + Shadow Mode",
        desc: "Add logging. Shadow mode support. Observatory integration so you can see alpha curves, line selections, and A/B comparison in real time.",
        deliverables: ["logger.py", "Observatory dashboard panel", "shadow mode in orchestrator"],
        effort: "1-2 days", color: S2, priority: 'MEASUREMENT',
      },
      {
        phase: 5, name: "Forge Integration",
        desc: "Close the feedback loop. Best lines from real sessions auto-extracted by Forge and promoted to the line bank. Cost tuning based on measured anchoring effectiveness.",
        deliverables: ["Forge → line_bank pipeline", "Auto-extraction rules", "Cost calibration framework"],
        effort: "2-3 days", color: PURPLE, priority: 'FEEDBACK LOOP',
      },
    ].map((p, i) => (
      <div key={i} style={{
        marginBottom: 16, padding: 24, background: CARD, borderRadius: 12,
        border: `1px solid ${BORDER}`, borderLeft: `3px solid ${p.color}40`,
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{
              width: 32, height: 32, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: `${p.color}12`, border: `1.5px solid ${p.color}30`,
            }}>
              <Mono style={{ fontSize: 14, color: p.color, fontWeight: 700 }}>{p.phase}</Mono>
            </div>
            <div>
              <Mono style={{ fontSize: 14, color: p.color, fontWeight: 700 }}>{p.name}</Mono>
              <Mono style={{ fontSize: 10, color: `${p.color}60`, display: 'block', marginTop: 2 }}>{p.priority} · {p.effort}</Mono>
            </div>
          </div>
        </div>
        <p style={{ fontSize: 13, color: 'rgba(255,255,255,0.5)', lineHeight: 1.6, margin: '0 0 14px 44px' }}>{p.desc}</p>
        <div style={{ marginLeft: 44, display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {p.deliverables.map((d, j) => (
            <Mono key={j} style={{ fontSize: 10, color: `${p.color}70`, padding: '4px 10px', background: `${p.color}08`, borderRadius: 4, border: `1px solid ${p.color}15` }}>{d}</Mono>
          ))}
        </div>
      </div>
    ))}

    <div style={{ marginTop: 28, padding: 20, background: `${S1}06`, borderRadius: 12, border: `1px solid ${S1}15` }}>
      <Mono style={{ fontSize: 12, color: S1, fontWeight: 600, display: 'block', marginBottom: 8 }}>Invariants (must always be true)</Mono>
      {[
        "Both engines off → prompt is identical to pre-voice-system Luna",
        "Shadow mode → zero impact on model output, full logging",
        "Corpus alone → works without Engine ever being built",
        "Engine alone → works without Corpus (no kill list, but functional)",
        "Config change → takes effect next turn, no restart",
        "VoiceSeed.to_prompt_block() → empty string when source=NONE",
        "context_builder → only talks to VoiceSystemOrchestrator, never engines directly",
      ].map((inv, i) => (
        <div key={i} style={{ display: 'flex', gap: 10, padding: '6px 0' }}>
          <Mono style={{ fontSize: 10, color: `${S1}40` }}>✓</Mono>
          <Mono style={{ fontSize: 11, color: 'rgba(255,255,255,0.5)' }}>{inv}</Mono>
        </div>
      ))}
    </div>
  </div>
);


// ─── MAIN ─────────────────────────────────────────────────────

export default function VoiceSystemSpec() {
  const [activeTab, setActiveTab] = useState(0);
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const panels = [Overview, PydanticModels, Services, ConfigToggles, FileLayout, Phases];
  const Panel = panels[activeTab];

  return (
    <div style={{
      minHeight: '100vh', background: BG, color: '#fff',
      fontFamily: "'IBM Plex Sans', sans-serif",
      opacity: mounted ? 1 : 0, transition: 'opacity 0.5s ease',
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&family=IBM+Plex+Sans:wght@300;400;500;600&family=Space+Mono:wght@400;700&display=swap');
        * { box-sizing: border-box; }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(200,255,0,0.15); border-radius: 2px; }
        pre::-webkit-scrollbar { height: 4px; }
      `}</style>

      <div style={{ maxWidth: 960, margin: '0 auto', padding: '40px 32px' }}>
        {/* Header */}
        <div style={{ marginBottom: 32 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 6 }}>
            <div style={{
              width: 36, height: 36, borderRadius: 8,
              background: `linear-gradient(135deg, ${S1}20, ${PURPLE}20)`,
              border: '1px solid rgba(255,255,255,0.08)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontFamily: "'IBM Plex Mono', monospace", fontSize: 16, color: S1,
            }}>λ</div>
            <div>
              <h1 style={{ fontFamily: "'Space Mono', monospace", fontSize: 20, fontWeight: 700, color: '#fff', margin: 0 }}>
                Luna Voice System
              </h1>
              <p style={{ fontSize: 12, color: MUTED, margin: '4px 0 0' }}>
                Handoff Specification — Two engines, one voice, full toggle control
              </p>
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div style={{ display: 'flex', gap: 2, borderBottom: `1px solid ${BORDER}`, marginBottom: 28, overflowX: 'auto' }}>
          {TABS.map((tab, i) => (
            <button key={tab} onClick={() => setActiveTab(i)} style={{
              padding: '10px 16px', background: 'transparent', border: 'none',
              borderBottom: `2px solid ${activeTab === i ? S1 : 'transparent'}`,
              color: activeTab === i ? S1 : 'rgba(255,255,255,0.25)',
              fontFamily: "'Space Mono', monospace", fontSize: 11, letterSpacing: '0.04em',
              cursor: 'pointer', transition: 'all 0.2s', whiteSpace: 'nowrap',
            }}>{tab}</button>
          ))}
        </div>

        {/* Content */}
        <Panel />

        {/* Footer */}
        <div style={{ marginTop: 40, paddingTop: 20, borderTop: '1px solid rgba(255,255,255,0.03)', textAlign: 'center' }}>
          <Mono style={{ fontSize: 10, color: 'rgba(255,255,255,0.08)' }}>
            Luna Voice System Spec v1.0 — CC Handoff · Ship Corpus, Add Engine, Dream DP
          </Mono>
        </div>
      </div>
    </div>
  );
}
