import React, { useState, useMemo, useEffect, useCallback } from 'react';

// ═══════════════════════════════════════════════════════════════
// VOICE BLEND ENGINE — Architecture Specification
// Adapting the Dual-LLM Brain partition algorithm for
// Luna's confidence-weighted voice scaffolding
// ═══════════════════════════════════════════════════════════════
//
// DECISION LOG:
// - Chose continuous alpha blend over discrete tiers because
//   discrete creates audible "gear shifts" in voice
// - Segment-level blending (not token-level) because you can't
//   switch voice mid-thought without it feeling uncanny
// - Greedy-first, DP-later because greedy ships and DP is
//   an optimization on a working system
// - Line costs are hand-tuned not learned because we don't
//   have enough data yet and learned costs need a reward signal
//   we haven't defined
// ═══════════════════════════════════════════════════════════════

// ─── DATA MODELS ──────────────────────────────────────────────

const SPEC = {
  // The core architecture
  components: [
    {
      name: "ConfidenceRouter",
      role: "Computes alpha (0-1) from conversation state signals",
      inputs: [
        { name: "memory_retrieval_score", type: "float 0-1", desc: "How strong were the memory hits. 0 = nothing found, 1 = exact match with high lock-in" },
        { name: "turn_number", type: "int", desc: "How many turns into this thread. Turn 1 = cold, Turn 4+ = warm" },
        { name: "entity_resolution_depth", type: "int 0-3", desc: "How many entities resolved. 0 = no context, 3 = rich entity graph active" },
        { name: "context_type", type: "enum", desc: "greeting | topic_shift | follow_up | cold_start | emotional | technical" },
        { name: "topic_continuity", type: "float 0-1", desc: "How related is this turn to the previous. 0 = total pivot, 1 = same thread" },
      ],
      outputs: [
        { name: "alpha", type: "float 0-1", desc: "Scaffolding weight. 1.0 = full line bank, 0.0 = pure freeform" },
        { name: "tier", type: "enum", desc: "GROUNDING | ENGAGING | FLOWING — derived from alpha for line bank selection" },
        { name: "confidence_vector", type: "float[5]", desc: "Raw signal values before alpha computation, for observability" },
      ],
      formula: `alpha = clamp(
  w_memory * (1 - memory_score)
  + w_turn * decay(turn_number)
  + w_entity * (1 - entity_depth / 3)
  + w_context * context_penalty(type)
  + w_continuity * (1 - topic_continuity)
, 0.05, 0.95)

// Default weights:
// w_memory = 0.35  (strongest signal)
// w_turn = 0.25    (natural decay)
// w_entity = 0.15  (entity richness)
// w_context = 0.15 (type-specific)
// w_continuity = 0.10 (thread coherence)

// decay(t) = max(0, 1 - (t-1) * 0.3)
// Turns: 1→1.0, 2→0.7, 3→0.4, 4+→0.1

// context_penalty:
// cold_start → 0.9
// greeting → 0.7
// topic_shift → 0.6
// emotional → 0.4
// technical → 0.3
// follow_up → 0.1`,
      notes: "Alpha floors at 0.05 (never zero scaffolding — even in flow, a light tonal hint helps) and caps at 0.95 (never fully scripted — always some model freedom).",
    },
    {
      name: "LineBank",
      role: "Tagged corpus of Luna-authentic lines, sourced from Forge extractions of real sessions",
      structure: [
        { field: "text", type: "string", desc: "The actual line" },
        { field: "cost", type: "int 1-5", desc: "Anchoring weight. 5 = very Luna, very distinctive. 1 = light touch, barely noticeable" },
        { field: "tier", type: "enum", desc: "GROUNDING | ENGAGING | FLOWING" },
        { field: "context_tags", type: "string[]", desc: "Situational tags: cold-start, technical, emotional, playful, etc." },
        { field: "emotional_register", type: "enum", desc: "warm | direct | playful | analytical | uncertain" },
        { field: "segment_type", type: "enum", desc: "opener | bridge | closer | clarifier | reaction" },
        { field: "source", type: "string?", desc: "Provenance — which real session this came from, if extracted" },
      ],
      notes: `Cost is hand-tuned for now. High-cost lines are strongly distinctive:
"nah, that won't work" (cost 5) — unmistakably Luna, anchors model behavior hard.
"hey" (cost 1) — barely registers, just a tonal nudge.
Cost determines HOW MUCH this line influences the model's continuation.
Future: learn costs from A/B testing or human feedback.`,
    },
    {
      name: "SegmentPlanner",
      role: "Decomposes a response into segments and assigns blend weights per segment",
      description: `Before the model generates, the planner decides the SHAPE of the response:
- How many segments (opener, body, closer)?
- Which segments get scaffolded vs freeform?
- What's the alpha budget per segment?

This is the sentence-boundary constraint from the brain:
you don't switch blend mid-segment.`,
      algorithm: `Given alpha from ConfidenceRouter:

1. Determine segment count based on expected response length
   - Short response (1-2 sentences): [opener]
   - Medium (3-5 sentences): [opener, body, closer]
   - Long (6+): [opener, body_1, body_2, ..., closer]

2. Distribute alpha across segments (front-loaded):
   - opener.alpha = alpha * 1.3  (capped at 0.95)
   - body.alpha = alpha * 0.8
   - closer.alpha = alpha * 0.5
   
   Rationale: front-load scaffolding. The opener is where
   the model is most likely to fall into generic patterns.
   By the closer, it's already in Luna's voice from the
   opener's momentum.

3. For each segment, compute effective cost budget:
   cost_budget = segment.alpha * MAX_COST
   
   High alpha → pick high-cost (strongly anchoring) lines
   Low alpha → pick low-cost (gentle nudge) lines or skip`,
    },
    {
      name: "LineSampler",
      role: "Selects candidate lines from the bank for each segment",
      algorithm: `For each segment:

1. Filter LineBank by:
   - tier matches ConfidenceRouter.tier
   - context_tags intersect with current context
   - segment_type matches segment role
   - emotional_register matches detected mood (if available)

2. Score candidates:
   score = relevance(tags, context) * cost_alignment(line.cost, segment.cost_budget)
   
   cost_alignment = 1 - |line.cost - segment.cost_budget| / MAX_COST
   (prefer lines whose cost matches the budget)

3. Sample top-k candidates (k=2-3)
   - Not top-1: give the model choice within Luna's voice
   - Not top-5: too much choice dilutes anchoring

4. Format as seed injection:
   If alpha > 0.7: inject as "Luna would say something like: {line1} or {line2}"
   If alpha 0.3-0.7: inject as "Luna's tone here: {line1}"
   If alpha < 0.3: inject as system hint only, not visible in prompt`,
      notes: "The injection format matters. At high alpha, the model sees explicit examples and pattern-matches hard. At low alpha, it's barely a whisper in the system prompt.",
    },
    {
      name: "FadeController",
      role: "Manages the alpha curve across a conversation — the policy that prevents Luna from feeling scripted",
      rules: [
        "Turn 1-2: Line bank active. Alpha determined by ConfidenceRouter signals.",
        "Turn 3: Blend phase. Alpha reduced by 0.2 from computed value (encourages release).",
        "Turn 4+: Freeform phase. Alpha floored at 0.05-0.15 regardless of signals.",
        "Context switch detected: Reset alpha to ConfidenceRouter output (re-engage scaffolding).",
        "Strong memory hit mid-conversation: Drop alpha by 0.3 (she found her footing).",
        "Confusion/uncertainty detected: Bump alpha by 0.2 (she needs support).",
        "Emotional context: Cap alpha at 0.4 (scaffolded empathy feels fake).",
      ],
      curve: `Alpha over turns (typical conversation):

Turn:  1    2    3    4    5    6    ...
Alpha: 0.85 0.60 0.35 0.15 0.10 0.05 ...
       ████ ███░ ██░░ █░░░ ░░░░ ░░░░
       GRND  ENG  BLND  FLOW  FLOW  FLOW

With context switch at turn 5:
Turn:  1    2    3    4    5*   6    7    ...
Alpha: 0.85 0.60 0.35 0.15 0.70 0.45 0.20 ...
       ████ ███░ ██░░ █░░░ ███░ ██░░ █░░░
       GRND  ENG  BLND  FLOW  ENG   BLND  FLOW`,
    },
    {
      name: "BlendAssembler",
      role: "Final stage — assembles the prompt injection that seeds the model's generation",
      process: `1. Receive segment plan with alpha-per-segment and sampled lines
2. Build injection block:

   <luna_voice_seed>
     <confidence alpha="{alpha}" tier="{tier}" />
     <opener seed="{sampled_opener_line}" weight="{opener_alpha}" />
     <tone hints="{emotional_register}, {context_tags}" />
     {if alpha > 0.5:
       <examples>
         <say>{line1}</say>
         <say>{line2}</say>
       </examples>
       <avoid>
         <never>{anti_pattern_1}</never>
         <never>{anti_pattern_2}</never>
       </avoid>
     }
   </luna_voice_seed>

3. Inject into context between personality kernel and user message
4. Log injection for observability (what was seeded, what alpha, which lines)`,
      notes: "The anti-patterns only inject at high alpha. At low alpha, Luna doesn't need guardrails — she's already in her voice.",
    },
  ],

  // Where this lives in the existing pipeline
  integration: {
    title: "Integration with Existing Architecture",
    points: [
      {
        where: "After PersonaCore 6-step pipeline, before LLM call",
        what: "VoiceBlendEngine sits between context assembly and inference. PersonaCore assembles WHO Luna is. VoiceBlendEngine decides HOW MUCH scaffolding she needs right now.",
      },
      {
        where: "ConfidenceRouter reads from Memory Matrix retrieval scores",
        what: "luna_smart_fetch already returns relevance scores. ConfidenceRouter consumes these directly — no new retrieval needed.",
      },
      {
        where: "LineBank populated from Forge training data extraction",
        what: "The Forge pipeline already extracts Luna's real conversation lines. Best lines get tagged and promoted to the LineBank. This is the feedback loop.",
      },
      {
        where: "FadeController state persists in session",
        what: "Alpha history lives in the session object alongside turn count and entity state. Survives reconnects.",
      },
      {
        where: "BlendAssembler output goes into context_builder.py",
        what: "The voice seed block gets injected at the same layer as kernel and virtues — it's just another context block with a specific position in the prompt.",
      },
    ],
  },

  // The Greedy vs DP question
  algorithms: {
    title: "Algorithm Strategy: Ship Greedy, Dream DP",
    greedy: {
      name: "Greedy (Ship First)",
      description: "Each turn: compute alpha from current signals, sample lines, inject. No lookahead.",
      pros: ["Simple to implement", "No conversation-level state beyond turn count", "Easy to debug — each turn is independent", "Good enough for 90% of conversations"],
      cons: ["Can't optimize across turns (might over-scaffold early)", "No concept of 'conversation shape'", "Locally optimal, globally meh"],
      when: "V1. Ship this. Get data. Learn.",
    },
    dp: {
      name: "Dynamic Programming (Future)",
      description: "Given expected conversation length and topic trajectory, optimize total alpha allocation across all turns to minimize total inauthenticity.",
      pros: ["Globally optimal scaffolding curve", "Can front-load or back-load intelligently", "Minimizes total 'uncanny valley' moments"],
      cons: ["Needs conversation length prediction (hard)", "Needs a cost function for 'inauthenticity' (undefined)", "Computational overhead per turn", "Requires conversation-level planning state"],
      when: "V2+. After we have data on what 'good' conversations look like and can define a reward signal.",
    },
  },

  // What can go wrong
  failureModes: [
    { mode: "Scaffolding never fades", cause: "Alpha floor too high or FadeController decay too slow", symptom: "Luna sounds scripted even on turn 10", fix: "Aggressive decay curve, hard floor at 0.05 by turn 5" },
    { mode: "Generic opener despite scaffolding", cause: "LineBank too small or tags too broad", symptom: "Line bank fires but selected line is generic", fix: "Curate aggressively. 50 great lines > 500 mediocre ones" },
    { mode: "Voice whiplash on context switch", cause: "Alpha jumps too hard on topic change", symptom: "Luna suddenly sounds different mid-conversation", fix: "Smooth alpha transitions — ramp over 2 turns, don't step" },
    { mode: "Over-anchoring", cause: "High-cost line dominates model output", symptom: "Luna repeats the seed line verbatim or too closely", fix: "Cap cost at 4 for injection. Save 5-cost lines for extreme cold starts only" },
    { mode: "Memory score misleading", cause: "High retrieval score on irrelevant memory", symptom: "Alpha drops too fast, Luna acts confident when she shouldn't be", fix: "Weight retrieval relevance AND recency, not just score" },
    { mode: "Anti-pattern injection backfires", cause: "Model fixates on 'never say' examples and says them anyway", symptom: "Luna says 'certainly' right after being told not to", fix: "Only inject anti-patterns at alpha > 0.7 where model follows instructions tightly" },
  ],

  // Implementation phases
  phases: [
    { phase: 1, name: "LineBank + Manual Alpha", desc: "Hand-curate 50-80 lines from real sessions. Manually set alpha per turn (no router). Test injection format. Validate that seeded lines actually influence output.", deliverable: "line_bank.json + injection template + A/B test results" },
    { phase: 2, name: "ConfidenceRouter + Greedy Sampler", desc: "Wire router to memory retrieval scores and turn count. Implement greedy per-turn sampling. FadeController with linear decay.", deliverable: "voice_blend_engine.py integrated into context_builder" },
    { phase: 3, name: "SegmentPlanner + Observability", desc: "Multi-segment responses with per-segment alpha. Logging dashboard showing alpha curves, line selections, and generation quality.", deliverable: "segment planner + Observatory integration" },
    { phase: 4, name: "Forge Feedback Loop", desc: "Best lines from real sessions auto-extracted and promoted to LineBank. Cost tuning based on measured anchoring effectiveness.", deliverable: "forge → line_bank pipeline" },
    { phase: 5, name: "DP Optimizer (Experimental)", desc: "Conversation-level alpha planning. Requires reward signal definition and conversation quality metrics.", deliverable: "dp_optimizer.py + quality metrics framework" },
  ],
};


// ─── VISUALIZATION COMPONENTS ─────────────────────────────────

const S1 = '#c8ff00';
const S2 = '#00b4ff';
const WARN = '#ff6b6b';
const MUTED = 'rgba(255,255,255,0.35)';
const BG = '#0a0a0f';
const CARD = 'rgba(255,255,255,0.02)';
const BORDER = 'rgba(255,255,255,0.05)';

const Mono = ({ children, style, ...p }) => (
  <span style={{ fontFamily: "'IBM Plex Mono', monospace", ...style }} {...p}>{children}</span>
);

const SectionHeader = ({ title, subtitle, accent = S1 }) => (
  <div style={{ marginBottom: 20 }}>
    <h2 style={{ fontFamily: "'Space Mono', monospace", fontSize: 13, fontWeight: 700, color: accent, letterSpacing: '0.1em', textTransform: 'uppercase', margin: 0 }}>{title}</h2>
    {subtitle && <p style={{ fontSize: 13, color: MUTED, margin: '6px 0 0', lineHeight: 1.5 }}>{subtitle}</p>}
  </div>
);

const CodeBlock = ({ children, maxHeight }) => (
  <pre style={{
    padding: '16px 20px', background: 'rgba(0,0,0,0.3)', borderRadius: 8,
    border: `1px solid ${BORDER}`, fontFamily: "'IBM Plex Mono', monospace",
    fontSize: 11, lineHeight: 1.6, color: 'rgba(200,255,0,0.7)',
    overflowX: 'auto', overflowY: maxHeight ? 'auto' : 'visible',
    maxHeight: maxHeight || 'none', whiteSpace: 'pre-wrap', margin: 0,
  }}>
    {children}
  </pre>
);

const TABS = ['Architecture', 'Data Flow', 'Integration', 'Algorithm', 'Failure Modes', 'Phases'];

// ─── ALPHA SIMULATOR ──────────────────────────────────────────

const AlphaSimulator = () => {
  const [memoryScore, setMemoryScore] = useState(0.2);
  const [turnNumber, setTurnNumber] = useState(1);
  const [entityDepth, setEntityDepth] = useState(0);
  const [contextType, setContextType] = useState('cold_start');
  const [topicContinuity, setTopicContinuity] = useState(0.5);

  const contextPenalties = { cold_start: 0.9, greeting: 0.7, topic_shift: 0.6, emotional: 0.4, technical: 0.3, follow_up: 0.1 };
  const weights = { memory: 0.35, turn: 0.25, entity: 0.15, context: 0.15, continuity: 0.10 };

  const decay = Math.max(0, 1 - (turnNumber - 1) * 0.3);
  const rawAlpha =
    weights.memory * (1 - memoryScore)
    + weights.turn * decay
    + weights.entity * (1 - entityDepth / 3)
    + weights.context * contextPenalties[contextType]
    + weights.continuity * (1 - topicContinuity);
  const alpha = Math.min(0.95, Math.max(0.05, rawAlpha));
  const tier = alpha > 0.6 ? 'GROUNDING' : alpha > 0.3 ? 'ENGAGING' : 'FLOWING';
  const tierColor = alpha > 0.6 ? WARN : alpha > 0.3 ? '#ffd93d' : S1;

  const signals = [
    { name: 'Memory', raw: (1 - memoryScore), weighted: weights.memory * (1 - memoryScore), w: weights.memory },
    { name: 'Turn Decay', raw: decay, weighted: weights.turn * decay, w: weights.turn },
    { name: 'Entity Gap', raw: (1 - entityDepth / 3), weighted: weights.entity * (1 - entityDepth / 3), w: weights.entity },
    { name: 'Context', raw: contextPenalties[contextType], weighted: weights.context * contextPenalties[contextType], w: weights.context },
    { name: 'Topic Gap', raw: (1 - topicContinuity), weighted: weights.continuity * (1 - topicContinuity), w: weights.continuity },
  ];

  const SliderRow = ({ label, value, onChange, min = 0, max = 1, step = 0.1, displayValue }) => (
    <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr 50px', alignItems: 'center', gap: 12, marginBottom: 8 }}>
      <Mono style={{ fontSize: 11, color: MUTED }}>{label}</Mono>
      <input type="range" min={min} max={max} step={step} value={value} onChange={e => onChange(parseFloat(e.target.value))}
        style={{ width: '100%', height: 4, borderRadius: 2, background: `linear-gradient(to right, ${S1}40 ${((value - min) / (max - min)) * 100}%, rgba(255,255,255,0.06) 0%)`, appearance: 'none', cursor: 'pointer' }} />
      <Mono style={{ fontSize: 12, color: S1, textAlign: 'right' }}>{displayValue || value.toFixed(1)}</Mono>
    </div>
  );

  return (
    <div style={{ padding: 24, background: CARD, borderRadius: 12, border: `1px solid ${BORDER}`, marginBottom: 24 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <Mono style={{ fontSize: 11, color: MUTED, letterSpacing: '0.08em' }}>LIVE ALPHA SIMULATOR</Mono>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <Mono style={{ fontSize: 28, fontWeight: 700, color: tierColor }}>{alpha.toFixed(2)}</Mono>
          <Mono style={{ fontSize: 11, padding: '4px 10px', borderRadius: 6, background: `${tierColor}15`, color: tierColor }}>{tier}</Mono>
        </div>
      </div>

      <SliderRow label="Memory Score" value={memoryScore} onChange={setMemoryScore} />
      <SliderRow label="Turn Number" value={turnNumber} onChange={setTurnNumber} min={1} max={8} step={1} displayValue={turnNumber} />
      <SliderRow label="Entity Depth" value={entityDepth} onChange={setEntityDepth} min={0} max={3} step={1} displayValue={entityDepth} />
      <SliderRow label="Continuity" value={topicContinuity} onChange={setTopicContinuity} />

      <div style={{ display: 'flex', gap: 6, marginBottom: 16, flexWrap: 'wrap' }}>
        {Object.keys(contextPenalties).map(ct => (
          <button key={ct} onClick={() => setContextType(ct)} style={{
            padding: '5px 12px', borderRadius: 6, cursor: 'pointer', fontSize: 11,
            fontFamily: "'IBM Plex Mono', monospace",
            background: contextType === ct ? `${S1}15` : 'rgba(255,255,255,0.03)',
            border: `1px solid ${contextType === ct ? `${S1}40` : 'rgba(255,255,255,0.06)'}`,
            color: contextType === ct ? S1 : MUTED,
          }}>{ct}</button>
        ))}
      </div>

      {/* Signal breakdown */}
      <div style={{ background: 'rgba(0,0,0,0.2)', borderRadius: 8, padding: 14 }}>
        <Mono style={{ fontSize: 10, color: 'rgba(255,255,255,0.2)', letterSpacing: '0.06em', display: 'block', marginBottom: 10 }}>SIGNAL DECOMPOSITION</Mono>
        {signals.map(s => (
          <div key={s.name} style={{ display: 'grid', gridTemplateColumns: '90px 40px 1fr 50px', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <Mono style={{ fontSize: 10, color: MUTED }}>{s.name}</Mono>
            <Mono style={{ fontSize: 10, color: 'rgba(255,255,255,0.15)' }}>×{s.w}</Mono>
            <div style={{ height: 3, background: 'rgba(255,255,255,0.04)', borderRadius: 2, overflow: 'hidden' }}>
              <div style={{ height: '100%', width: `${(s.weighted / 0.35) * 100}%`, background: `${S1}60`, borderRadius: 2, transition: 'width 0.3s' }} />
            </div>
            <Mono style={{ fontSize: 10, color: `${S1}80`, textAlign: 'right' }}>+{s.weighted.toFixed(3)}</Mono>
          </div>
        ))}
        <div style={{ borderTop: '1px solid rgba(255,255,255,0.06)', marginTop: 8, paddingTop: 8, display: 'flex', justifyContent: 'space-between' }}>
          <Mono style={{ fontSize: 10, color: MUTED }}>raw sum → clamp(0.05, 0.95)</Mono>
          <Mono style={{ fontSize: 11, color: tierColor, fontWeight: 600 }}>α = {alpha.toFixed(3)}</Mono>
        </div>
      </div>
    </div>
  );
};


// ─── CONVERSATION SIMULATOR ───────────────────────────────────

const ConversationSim = () => {
  const turns = [
    { turn: 1, context: 'cold_start', memory: 0.1, entity: 0, continuity: 0, label: "hey luna, what's the deal with the eden API?" },
    { turn: 2, context: 'follow_up', memory: 0.4, entity: 1, continuity: 0.8, label: "yeah the auth part specifically" },
    { turn: 3, context: 'technical', memory: 0.7, entity: 2, continuity: 0.9, label: "can you check what we decided last time?" },
    { turn: 4, context: 'follow_up', memory: 0.85, entity: 3, continuity: 0.95, label: "ok let's go with the token refresh approach" },
    { turn: 5, context: 'topic_shift', memory: 0.2, entity: 1, continuity: 0.1, label: "actually — how's the extraction batch going?" },
    { turn: 6, context: 'follow_up', memory: 0.6, entity: 2, continuity: 0.85, label: "nice, what's the node count at?" },
  ];

  const contextPenalties = { cold_start: 0.9, greeting: 0.7, topic_shift: 0.6, emotional: 0.4, technical: 0.3, follow_up: 0.1 };
  const weights = { memory: 0.35, turn: 0.25, entity: 0.15, context: 0.15, continuity: 0.10 };

  const computed = turns.map(t => {
    const decay = Math.max(0, 1 - (t.turn - 1) * 0.3);
    // Apply fade controller: after turn 3, reduce by 0.2; after turn 4, floor at 0.15
    let raw = weights.memory * (1 - t.memory) + weights.turn * decay + weights.entity * (1 - t.entity / 3) + weights.context * contextPenalties[t.context] + weights.continuity * (1 - t.continuity);
    if (t.turn >= 3 && t.context !== 'topic_shift') raw = Math.max(raw - 0.2, 0.05);
    if (t.turn >= 5 && t.context !== 'topic_shift') raw = Math.min(raw, 0.15);
    const alpha = Math.min(0.95, Math.max(0.05, raw));
    const tier = alpha > 0.6 ? 'GROUNDING' : alpha > 0.3 ? 'ENGAGING' : 'FLOWING';
    return { ...t, alpha, tier };
  });

  return (
    <div style={{ padding: 24, background: CARD, borderRadius: 12, border: `1px solid ${BORDER}` }}>
      <Mono style={{ fontSize: 11, color: MUTED, letterSpacing: '0.08em', display: 'block', marginBottom: 16 }}>
        CONVERSATION TRACE — Alpha curve with context switch at turn 5
      </Mono>

      {/* Visual curve */}
      <div style={{ display: 'flex', alignItems: 'end', gap: 4, height: 80, marginBottom: 20, padding: '0 8px' }}>
        {computed.map((t, i) => {
          const color = t.alpha > 0.6 ? WARN : t.alpha > 0.3 ? '#ffd93d' : S1;
          return (
            <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
              <Mono style={{ fontSize: 9, color }}>{t.alpha.toFixed(2)}</Mono>
              <div style={{
                width: '100%', maxWidth: 60, height: `${t.alpha * 75}px`,
                background: `${color}30`, border: `1px solid ${color}50`,
                borderRadius: '4px 4px 0 0', transition: 'height 0.4s ease',
              }} />
            </div>
          );
        })}
      </div>

      {/* Turn details */}
      {computed.map((t, i) => {
        const color = t.alpha > 0.6 ? WARN : t.alpha > 0.3 ? '#ffd93d' : S1;
        return (
          <div key={i} style={{
            display: 'grid', gridTemplateColumns: '30px 60px 1fr 60px',
            alignItems: 'center', gap: 12, padding: '10px 12px',
            background: i % 2 === 0 ? 'rgba(255,255,255,0.01)' : 'transparent',
            borderRadius: 6, borderLeft: t.context === 'topic_shift' ? `3px solid ${WARN}` : '3px solid transparent',
          }}>
            <Mono style={{ fontSize: 11, color: 'rgba(255,255,255,0.2)' }}>T{t.turn}</Mono>
            <Mono style={{ fontSize: 10, padding: '3px 8px', borderRadius: 4, background: `${color}12`, color, textAlign: 'center' }}>{t.tier}</Mono>
            <div>
              <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.6)', marginBottom: 2 }}>"{t.label}"</div>
              <Mono style={{ fontSize: 10, color: 'rgba(255,255,255,0.2)' }}>
                mem:{t.memory} ent:{t.entity} ctx:{t.context} cont:{t.continuity}
              </Mono>
            </div>
            <Mono style={{ fontSize: 14, fontWeight: 700, color, textAlign: 'right' }}>{t.alpha.toFixed(2)}</Mono>
          </div>
        );
      })}
    </div>
  );
};


// ─── MAIN APP ─────────────────────────────────────────────────

export default function VoiceBlendSpec() {
  const [activeTab, setActiveTab] = useState(0);
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const renderArchitecture = () => (
    <div>
      {SPEC.components.map((comp, i) => (
        <div key={comp.name} style={{ marginBottom: 32, padding: 24, background: CARD, borderRadius: 12, border: `1px solid ${BORDER}` }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 8 }}>
            <Mono style={{ fontSize: 15, color: S1, fontWeight: 700 }}>{comp.name}</Mono>
            <span style={{ fontSize: 12, color: MUTED }}>{comp.role}</span>
          </div>

          {comp.inputs && (
            <div style={{ marginBottom: 16 }}>
              <Mono style={{ fontSize: 10, color: 'rgba(255,255,255,0.2)', letterSpacing: '0.06em', display: 'block', marginBottom: 8 }}>INPUTS</Mono>
              {comp.inputs.map(inp => (
                <div key={inp.name} style={{ display: 'grid', gridTemplateColumns: '180px 90px 1fr', gap: 8, marginBottom: 4, padding: '4px 0' }}>
                  <Mono style={{ fontSize: 11, color: `${S1}90` }}>{inp.name}</Mono>
                  <Mono style={{ fontSize: 10, color: 'rgba(255,255,255,0.2)' }}>{inp.type}</Mono>
                  <span style={{ fontSize: 11, color: MUTED }}>{inp.desc}</span>
                </div>
              ))}
            </div>
          )}

          {comp.outputs && (
            <div style={{ marginBottom: 16 }}>
              <Mono style={{ fontSize: 10, color: 'rgba(255,255,255,0.2)', letterSpacing: '0.06em', display: 'block', marginBottom: 8 }}>OUTPUTS</Mono>
              {comp.outputs.map(out => (
                <div key={out.name} style={{ display: 'grid', gridTemplateColumns: '180px 90px 1fr', gap: 8, marginBottom: 4, padding: '4px 0' }}>
                  <Mono style={{ fontSize: 11, color: `${S2}90` }}>{out.name}</Mono>
                  <Mono style={{ fontSize: 10, color: 'rgba(255,255,255,0.2)' }}>{out.type}</Mono>
                  <span style={{ fontSize: 11, color: MUTED }}>{out.desc}</span>
                </div>
              ))}
            </div>
          )}

          {comp.formula && <CodeBlock maxHeight={280}>{comp.formula}</CodeBlock>}
          {comp.algorithm && <CodeBlock maxHeight={320}>{comp.algorithm}</CodeBlock>}
          {comp.description && !comp.algorithm && <p style={{ fontSize: 13, color: 'rgba(255,255,255,0.5)', lineHeight: 1.6, margin: '12px 0' }}>{comp.description}</p>}
          {comp.process && <CodeBlock maxHeight={300}>{comp.process}</CodeBlock>}
          {comp.curve && <CodeBlock>{comp.curve}</CodeBlock>}

          {comp.rules && (
            <div style={{ marginTop: 12 }}>
              {comp.rules.map((r, j) => (
                <div key={j} style={{ display: 'flex', gap: 10, padding: '8px 0', borderBottom: j < comp.rules.length - 1 ? `1px solid rgba(255,255,255,0.03)` : 'none' }}>
                  <Mono style={{ fontSize: 10, color: `${S1}40`, minWidth: 16 }}>{j + 1}</Mono>
                  <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.5)', lineHeight: 1.5 }}>{r}</span>
                </div>
              ))}
            </div>
          )}

          {comp.structure && (
            <div style={{ marginBottom: 12 }}>
              <Mono style={{ fontSize: 10, color: 'rgba(255,255,255,0.2)', letterSpacing: '0.06em', display: 'block', marginBottom: 8 }}>SCHEMA</Mono>
              {comp.structure.map(f => (
                <div key={f.field} style={{ display: 'grid', gridTemplateColumns: '140px 100px 1fr', gap: 8, marginBottom: 4, padding: '4px 0' }}>
                  <Mono style={{ fontSize: 11, color: `${S1}90` }}>{f.field}</Mono>
                  <Mono style={{ fontSize: 10, color: 'rgba(255,255,255,0.2)' }}>{f.type}</Mono>
                  <span style={{ fontSize: 11, color: MUTED }}>{f.desc}</span>
                </div>
              ))}
            </div>
          )}

          {comp.notes && <p style={{ fontSize: 12, color: 'rgba(255,255,255,0.3)', lineHeight: 1.5, margin: '12px 0 0', fontStyle: 'italic' }}>{comp.notes}</p>}
        </div>
      ))}
    </div>
  );

  const renderDataFlow = () => (
    <div>
      <SectionHeader title="Live Alpha Simulator" subtitle="Adjust signals and watch alpha compute in real time" />
      <AlphaSimulator />
      <div style={{ marginTop: 28 }} />
      <SectionHeader title="Conversation Trace" subtitle="A realistic 6-turn conversation showing alpha decay and context-switch reset" />
      <ConversationSim />
    </div>
  );

  const renderIntegration = () => (
    <div>
      <SectionHeader title={SPEC.integration.title} subtitle="Where VoiceBlendEngine plugs into the existing Luna pipeline" />
      {SPEC.integration.points.map((p, i) => (
        <div key={i} style={{ marginBottom: 16, padding: 20, background: CARD, borderRadius: 10, border: `1px solid ${BORDER}`, borderLeft: `3px solid ${S1}30` }}>
          <Mono style={{ fontSize: 12, color: S1, fontWeight: 600, display: 'block', marginBottom: 8 }}>{p.where}</Mono>
          <span style={{ fontSize: 13, color: 'rgba(255,255,255,0.5)', lineHeight: 1.6 }}>{p.what}</span>
        </div>
      ))}

      <div style={{ marginTop: 32 }}>
        <SectionHeader title="Pipeline Position" subtitle="Where voice blending happens in the inference chain" />
        <CodeBlock>{`User Message
    │
    ▼
┌─────────────────────┐
│   State Machine      │  ← detects app context, conversation state
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│   PersonaCore        │  ← WHO Luna is (kernel, virtues, identity)
│   6-step pipeline    │
└─────────┬───────────┘
          │
          ▼
┌═════════════════════┐
║  VoiceBlendEngine   ║  ← HOW MUCH scaffolding (alpha, lines, seeds)
║                     ║
║  ConfidenceRouter   ║  reads: memory scores, turn count, entities
║       │             ║
║  SegmentPlanner     ║  plans: response shape, per-segment alpha
║       │             ║
║  LineSampler        ║  picks: candidate lines from bank
║       │             ║
║  BlendAssembler     ║  builds: <luna_voice_seed> injection
║       │             ║
║  FadeController     ║  adjusts: alpha curve over conversation
╚═════════╤═══════════╝
          │
          ▼
┌─────────────────────┐
│   Context Builder    │  ← assembles full prompt
│   (context_builder)  │     kernel + virtues + voice_seed + history
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│   LLM Inference      │  ← model generates with voice seed active
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│   QA Assertions      │  ← checks: did she sound like Luna?
└─────────────────────┘`}</CodeBlock>
      </div>
    </div>
  );

  const renderAlgorithm = () => (
    <div>
      <SectionHeader title={SPEC.algorithms.title} />
      {[SPEC.algorithms.greedy, SPEC.algorithms.dp].map((algo, i) => (
        <div key={algo.name} style={{ marginBottom: 24, padding: 24, background: CARD, borderRadius: 12, border: `1px solid ${BORDER}` }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <Mono style={{ fontSize: 14, color: i === 0 ? S1 : S2, fontWeight: 700 }}>{algo.name}</Mono>
            <Mono style={{ fontSize: 10, padding: '4px 12px', borderRadius: 6, background: i === 0 ? `${S1}12` : `${S2}12`, color: i === 0 ? S1 : S2 }}>{algo.when}</Mono>
          </div>
          <p style={{ fontSize: 13, color: 'rgba(255,255,255,0.5)', lineHeight: 1.6, margin: '0 0 16px' }}>{algo.description}</p>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <Mono style={{ fontSize: 10, color: `${S1}50`, letterSpacing: '0.06em', display: 'block', marginBottom: 8 }}>PROS</Mono>
              {algo.pros.map((p, j) => (
                <div key={j} style={{ fontSize: 12, color: 'rgba(255,255,255,0.45)', padding: '4px 0', display: 'flex', gap: 8 }}>
                  <span style={{ color: `${S1}60` }}>+</span> {p}
                </div>
              ))}
            </div>
            <div>
              <Mono style={{ fontSize: 10, color: `${WARN}50`, letterSpacing: '0.06em', display: 'block', marginBottom: 8 }}>CONS</Mono>
              {algo.cons.map((c, j) => (
                <div key={j} style={{ fontSize: 12, color: 'rgba(255,255,255,0.45)', padding: '4px 0', display: 'flex', gap: 8 }}>
                  <span style={{ color: `${WARN}60` }}>−</span> {c}
                </div>
              ))}
            </div>
          </div>
        </div>
      ))}

      <div style={{ marginTop: 16, padding: 20, background: `${S1}06`, borderRadius: 10, border: `1px solid ${S1}15` }}>
        <Mono style={{ fontSize: 12, color: S1, fontWeight: 600, display: 'block', marginBottom: 8 }}>The Brain Orchestrator Connection</Mono>
        <p style={{ fontSize: 13, color: 'rgba(255,255,255,0.5)', lineHeight: 1.7, margin: 0 }}>
          Same partition algorithm, different domain. The brain splits tokens between System 1 and System 2. VoiceBlendEngine splits response segments between Scaffolded and Freeform. The alpha slider is the same slider. The cost badges are the same concept (line anchoring weight instead of compute weight). The sentence-boundary constraint maps to segment boundaries. Greedy ships first; DP optimizes the conversation arc when we have quality signal.
        </p>
      </div>
    </div>
  );

  const renderFailureModes = () => (
    <div>
      <SectionHeader title="Failure Mode Analysis" subtitle="How this system breaks and what catches it" />
      {SPEC.failureModes.map((f, i) => (
        <div key={i} style={{ marginBottom: 12, padding: 20, background: CARD, borderRadius: 10, border: `1px solid ${BORDER}` }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <Mono style={{ fontSize: 13, color: WARN, fontWeight: 600 }}>{f.mode}</Mono>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16 }}>
            <div>
              <Mono style={{ fontSize: 10, color: 'rgba(255,255,255,0.2)', display: 'block', marginBottom: 4 }}>CAUSE</Mono>
              <span style={{ fontSize: 12, color: MUTED, lineHeight: 1.5 }}>{f.cause}</span>
            </div>
            <div>
              <Mono style={{ fontSize: 10, color: 'rgba(255,255,255,0.2)', display: 'block', marginBottom: 4 }}>SYMPTOM</Mono>
              <span style={{ fontSize: 12, color: MUTED, lineHeight: 1.5 }}>{f.symptom}</span>
            </div>
            <div>
              <Mono style={{ fontSize: 10, color: 'rgba(255,255,255,0.2)', display: 'block', marginBottom: 4 }}>FIX</Mono>
              <span style={{ fontSize: 12, color: `${S1}80`, lineHeight: 1.5 }}>{f.fix}</span>
            </div>
          </div>
        </div>
      ))}
    </div>
  );

  const renderPhases = () => (
    <div>
      <SectionHeader title="Implementation Phases" subtitle="Ship Greedy, learn, then optimize" />
      {SPEC.phases.map((p, i) => (
        <div key={i} style={{
          marginBottom: 16, padding: 20, background: CARD, borderRadius: 10,
          border: `1px solid ${BORDER}`, borderLeft: `3px solid ${i === 0 ? S1 : i < 3 ? '#ffd93d' : `${S2}60`}`,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
            <div style={{
              width: 28, height: 28, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: i === 0 ? `${S1}15` : 'rgba(255,255,255,0.04)',
              border: `1px solid ${i === 0 ? `${S1}30` : 'rgba(255,255,255,0.06)'}`,
            }}>
              <Mono style={{ fontSize: 12, color: i === 0 ? S1 : MUTED, fontWeight: 700 }}>{p.phase}</Mono>
            </div>
            <Mono style={{ fontSize: 13, color: i === 0 ? S1 : 'rgba(255,255,255,0.7)', fontWeight: 600 }}>{p.name}</Mono>
          </div>
          <p style={{ fontSize: 13, color: 'rgba(255,255,255,0.45)', lineHeight: 1.6, margin: '0 0 10px 40px' }}>{p.desc}</p>
          <div style={{ marginLeft: 40 }}>
            <Mono style={{ fontSize: 11, color: `${S1}50` }}>→ {p.deliverable}</Mono>
          </div>
        </div>
      ))}
    </div>
  );

  const panels = [renderArchitecture, renderDataFlow, renderIntegration, renderAlgorithm, renderFailureModes, renderPhases];

  return (
    <div style={{
      minHeight: '100vh', background: BG, color: '#fff',
      fontFamily: "'IBM Plex Sans', sans-serif",
      opacity: mounted ? 1 : 0, transition: 'opacity 0.5s ease',
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&family=IBM+Plex+Sans:wght@300;400;500;600&family=Space+Mono:wght@400;700&display=swap');
        * { box-sizing: border-box; }
        input[type=range] { -webkit-appearance: none; appearance: none; height: 4px; border-radius: 2px; outline: none; cursor: pointer; }
        input[type=range]::-webkit-slider-thumb { -webkit-appearance: none; width: 16px; height: 16px; border-radius: 50%; background: #c8ff00; border: 2px solid #0a0a0f; cursor: pointer; box-shadow: 0 0 8px rgba(200,255,0,0.3); }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(200,255,0,0.15); border-radius: 2px; }
        pre::-webkit-scrollbar { height: 4px; }
      `}</style>

      <div style={{ maxWidth: 940, margin: '0 auto', padding: '40px 32px' }}>
        {/* Header */}
        <div style={{ marginBottom: 36 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 8 }}>
            <div style={{
              width: 36, height: 36, borderRadius: 8,
              background: `linear-gradient(135deg, ${S1}20, ${S2}20)`,
              border: '1px solid rgba(255,255,255,0.08)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontFamily: "'IBM Plex Mono', monospace", fontSize: 16, color: S1,
            }}>λ</div>
            <div>
              <h1 style={{ fontFamily: "'Space Mono', monospace", fontSize: 20, fontWeight: 700, color: '#fff', margin: 0, letterSpacing: '-0.02em' }}>
                Voice Blend Engine
              </h1>
              <p style={{ fontSize: 12, color: MUTED, margin: '4px 0 0' }}>
                Confidence-weighted scaffolding for Luna's first turns — adapted from the Dual-LLM Brain partition algorithm
              </p>
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div style={{ display: 'flex', gap: 2, borderBottom: `1px solid ${BORDER}`, marginBottom: 28, overflowX: 'auto' }}>
          {TABS.map((tab, i) => (
            <button key={tab} onClick={() => setActiveTab(i)} style={{
              padding: '10px 18px', background: 'transparent', border: 'none',
              borderBottom: `2px solid ${activeTab === i ? S1 : 'transparent'}`,
              color: activeTab === i ? S1 : 'rgba(255,255,255,0.25)',
              fontFamily: "'Space Mono', monospace", fontSize: 11, letterSpacing: '0.04em',
              cursor: 'pointer', transition: 'all 0.2s', whiteSpace: 'nowrap',
            }}>{tab}</button>
          ))}
        </div>

        {/* Content */}
        <div>{panels[activeTab]()}</div>

        {/* Footer */}
        <div style={{ marginTop: 40, paddingTop: 20, borderTop: `1px solid rgba(255,255,255,0.03)`, textAlign: 'center' }}>
          <Mono style={{ fontSize: 10, color: 'rgba(255,255,255,0.08)' }}>
            Voice Blend Engine Spec v1.0 — Luna × Brain Orchestrator · Ship Greedy, Dream DP
          </Mono>
        </div>
      </div>
    </div>
  );
}
