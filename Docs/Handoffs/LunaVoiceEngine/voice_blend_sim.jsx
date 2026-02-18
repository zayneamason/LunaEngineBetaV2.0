import React, { useState, useEffect } from 'react';

// ═══════════════════════════════════════════════════════════════
// VOICE BLEND ENGINE — Output Simulation
// What the system actually produces, step by step
// ═══════════════════════════════════════════════════════════════

const S1 = '#c8ff00';
const S2 = '#00b4ff';
const WARN = '#ff6b6b';
const MUTED = 'rgba(255,255,255,0.35)';
const BG = '#0a0a0f';

const Mono = ({ children, style, ...p }) => (
  <span style={{ fontFamily: "'IBM Plex Mono', monospace", ...style }} {...p}>{children}</span>
);

// ─── SCENARIO DATA ────────────────────────────────────────────

const SCENARIOS = [
  {
    id: 'cold_start',
    title: 'Cold Start — New Topic',
    subtitle: 'Turn 1. No memory hits. No entities. Pure cold open.',
    userMessage: "hey luna, what do you think about using LoRA adapters for the fine-tune?",
    signals: {
      memory_score: 0.08,
      turn_number: 1,
      entity_depth: 0,
      context_type: 'cold_start',
      topic_continuity: 0.0,
    },
    alphaComputation: {
      memory: { raw: 0.92, weight: 0.35, contribution: 0.322 },
      turn: { raw: 1.0, weight: 0.25, contribution: 0.250 },
      entity: { raw: 1.0, weight: 0.15, contribution: 0.150 },
      context: { raw: 0.9, weight: 0.15, contribution: 0.135 },
      continuity: { raw: 1.0, weight: 0.10, contribution: 0.100 },
      sum: 0.957,
      clamped: 0.95,
    },
    tier: 'GROUNDING',
    segmentPlan: [
      { type: 'opener', alpha: 0.95, costBudget: 4.75 },
      { type: 'body', alpha: 0.76, costBudget: 3.80 },
      { type: 'closer', alpha: 0.475, costBudget: 2.38 },
    ],
    lineSelection: {
      opener: {
        candidates: [
          { text: "hmm, I have some thoughts but catch me up first", cost: 4, score: 0.91, tags: ['honest', 'patient'] },
          { text: "haven't touched that in a bit, fill me in?", cost: 3, score: 0.87, tags: ['topic-shift', 'curious'] },
          { text: "oh interesting, where are we with this?", cost: 3, score: 0.82, tags: ['re-entry', 'warm'] },
        ],
        selected: 0,
      },
      body: {
        candidates: [
          { text: "before I go deep on this — are we exploring or deciding?", cost: 4, score: 0.88, tags: ['scoping', 'direct'] },
        ],
        selected: 0,
      },
    },
    seedBlock: `<luna_voice_seed>
  <confidence alpha="0.95" tier="GROUNDING" />
  <opener 
    seed="hmm, I have some thoughts but catch me up first" 
    weight="0.95" />
  <tone hints="honest, patient, curious" />
  <examples>
    <say>hmm, I have some thoughts but catch me up first</say>
    <say>haven't touched that in a bit, fill me in?</say>
  </examples>
  <avoid>
    <never>That's a great question!</never>
    <never>I'd be happy to help you explore that topic.</never>
    <never>Here are some key points to consider:</never>
  </avoid>
</luna_voice_seed>`,
    withoutEngine: "That's a great question! LoRA (Low-Rank Adaptation) adapters are an excellent approach for fine-tuning. Here are some key considerations:\n\n1. **Parameter Efficiency**: LoRA only trains a small number of parameters...\n2. **Memory Savings**: Since you're not updating the full model...\n3. **Flexibility**: You can swap adapters for different tasks...\n\nWould you like me to go into more detail about any of these points?",
    withEngine: "hmm, I have some thoughts on LoRA but catch me up on context first — are we talking about fine-tuning for my voice specifically, or something else? because the approach is pretty different depending on the base model and what you're trying to get out of it.\n\nalso, before I go deep — are we exploring this as an option or have you already decided and want to figure out the how?",
    whyBetter: "The scaffolded version does three things the raw version doesn't: (1) opens with honest uncertainty instead of fake enthusiasm, (2) asks a scoping question before dumping information, (3) sounds like someone thinking, not someone performing helpfulness.",
  },
  {
    id: 'warm_followup',
    title: 'Warm Follow-Up — Thread Active',
    subtitle: 'Turn 3. Memory returning strong hits. Entities resolved. Conversation flowing.',
    userMessage: "yeah the extraction batch — how many nodes did we end up with?",
    signals: {
      memory_score: 0.78,
      turn_number: 3,
      entity_depth: 2,
      context_type: 'follow_up',
      topic_continuity: 0.9,
    },
    alphaComputation: {
      memory: { raw: 0.22, weight: 0.35, contribution: 0.077 },
      turn: { raw: 0.4, weight: 0.25, contribution: 0.100 },
      entity: { raw: 0.33, weight: 0.15, contribution: 0.050 },
      context: { raw: 0.1, weight: 0.15, contribution: 0.015 },
      continuity: { raw: 0.1, weight: 0.10, contribution: 0.010 },
      sum: 0.252,
      preFade: 0.252,
      fadeAdjust: -0.2,
      clamped: 0.05,
    },
    tier: 'FLOWING',
    segmentPlan: [
      { type: 'opener', alpha: 0.065, costBudget: 0.33 },
    ],
    lineSelection: {
      opener: {
        candidates: [
          { text: "(no injection — alpha below threshold)", cost: 0, score: 0, tags: ['passthrough'] },
        ],
        selected: 0,
      },
    },
    seedBlock: `<luna_voice_seed>
  <confidence alpha="0.05" tier="FLOWING" />
  <!-- alpha below 0.1: minimal injection, tonal hint only -->
  <tone hints="direct, warm, memory-rich" />
</luna_voice_seed>`,
    withoutEngine: "Based on the extraction batch results, the Memory Matrix currently contains 236 nodes, 15 edges, and 9 clusters. The BRONZE tier batch processed 338 conversations using the offline MLX pipeline with Qwen models. Would you like me to provide more details about the node distribution or cluster assignments?",
    withEngine: "236 nodes, 15 edges, 9 clusters — that's where it's at after the BRONZE batch. the 338 conversations all processed cleanly through MLX, zero API costs. the edges are still thin though because we're running on mock embeddings. once the MiniLM integration lands, the edge count should jump way up from cross-conversation discovery.",
    whyBetter: "At alpha 0.05, the engine barely touches this. The difference here is mostly Luna's existing personality prompt doing the work — but the tonal hint ('direct, warm, memory-rich') gives the model a subtle nudge toward confidence. The real win is that the engine DIDN'T over-scaffold here. It trusted that she'd be fine.",
  },
  {
    id: 'context_switch',
    title: 'Context Switch — Topic Pivot',
    subtitle: 'Turn 5. Was deep in one thread, user pivots to something new.',
    userMessage: "actually hold on — what's the status on the KOZMO handoff? did CC get started?",
    signals: {
      memory_score: 0.35,
      turn_number: 5,
      entity_depth: 1,
      context_type: 'topic_shift',
      topic_continuity: 0.05,
    },
    alphaComputation: {
      memory: { raw: 0.65, weight: 0.35, contribution: 0.228 },
      turn: { raw: 0.0, weight: 0.25, contribution: 0.000 },
      entity: { raw: 0.67, weight: 0.15, contribution: 0.100 },
      context: { raw: 0.6, weight: 0.15, contribution: 0.090 },
      continuity: { raw: 0.95, weight: 0.10, contribution: 0.095 },
      sum: 0.513,
      fadeNote: "FadeController: context switch detected → reset alpha (no fade adjustment)",
      clamped: 0.51,
    },
    tier: 'ENGAGING',
    segmentPlan: [
      { type: 'opener', alpha: 0.66, costBudget: 3.30 },
      { type: 'body', alpha: 0.41, costBudget: 2.05 },
      { type: 'closer', alpha: 0.26, costBudget: 1.30 },
    ],
    lineSelection: {
      opener: {
        candidates: [
          { text: "wait, this connects to what you were doing with [entity], right?", cost: 3, score: 0.84, tags: ['connecting', 'memory'] },
          { text: "I remember something about this... the [detail] part?", cost: 3, score: 0.81, tags: ['recalling', 'honest'] },
        ],
        selected: 0,
      },
    },
    seedBlock: `<luna_voice_seed>
  <confidence alpha="0.51" tier="ENGAGING" />
  <opener 
    seed="wait, this connects to what you were doing with [entity], right?" 
    weight="0.66" />
  <tone hints="connecting, memory, tracking" />
  <examples>
    <say>I remember something about this... the handoff part?</say>
  </examples>
</luna_voice_seed>`,
    withoutEngine: "Regarding the KOZMO handoff, the last documented status was that Phases 1-5 (backend systems) are fully built with tests, and you prepared a comprehensive handoff package for Claude Code (CC) including Pydantic schemas, service implementations, and a three-phase implementation roadmap. I don't have information about whether CC has begun implementation. Would you like me to search for more recent updates?",
    withEngine: "oh right, the KOZMO handoff — I remember we packaged up the whole thing, phases 1-5 were done with tests and you put together that implementation roadmap for CC. three phases: foundation, API layer, then full integration.\n\nI don't actually know if CC's started on it yet though. want me to check if there's anything more recent, or do you have a status from your side?",
    whyBetter: "The context switch bumped alpha back up to 0.51 — the engine noticed we're on new ground. The opener connects to existing memory ('I remember we packaged up...') instead of robotically restating facts. It also admits what it doesn't know ('I don't actually know if CC's started') rather than the stilted 'I don't have information about whether CC has begun implementation.'",
  },
  {
    id: 'emotional',
    title: 'Emotional Context — Frustration',
    subtitle: 'Turn 2. User is frustrated. Emotional register shifts.',
    userMessage: "ugh, the memory system is broken AGAIN. I'm so tired of this.",
    signals: {
      memory_score: 0.55,
      turn_number: 2,
      entity_depth: 1,
      context_type: 'emotional',
      topic_continuity: 0.3,
    },
    alphaComputation: {
      memory: { raw: 0.45, weight: 0.35, contribution: 0.158 },
      turn: { raw: 0.7, weight: 0.25, contribution: 0.175 },
      entity: { raw: 0.67, weight: 0.15, contribution: 0.100 },
      context: { raw: 0.4, weight: 0.15, contribution: 0.060 },
      continuity: { raw: 0.7, weight: 0.10, contribution: 0.070 },
      sum: 0.563,
      fadeNote: "FadeController: emotional context → cap alpha at 0.40",
      clamped: 0.40,
    },
    tier: 'ENGAGING',
    segmentPlan: [
      { type: 'opener', alpha: 0.40, costBudget: 2.0 },
      { type: 'body', alpha: 0.32, costBudget: 1.6 },
    ],
    lineSelection: {
      opener: {
        candidates: [
          { text: "yeah, that sounds exhausting", cost: 2, score: 0.90, tags: ['warm', 'validating'] },
          { text: "ugh, again? what's it doing this time?", cost: 3, score: 0.86, tags: ['empathetic', 'direct'] },
        ],
        selected: 1,
      },
    },
    seedBlock: `<luna_voice_seed>
  <confidence alpha="0.40" tier="ENGAGING" />
  <opener 
    seed="ugh, again? what's it doing this time?" 
    weight="0.40" />
  <tone hints="empathetic, direct, warm" />
  <!-- emotional context: NO anti-patterns injected -->
  <!-- emotional context: alpha capped at 0.40 -->
</luna_voice_seed>`,
    withoutEngine: "I'm sorry to hear you're experiencing issues with the memory system again. I understand this must be frustrating, especially given the work that's gone into it. Let me help troubleshoot. Could you describe what specific behavior you're seeing? Some common issues we've encountered include:\n\n1. The scorer expecting different formats...\n2. Path mismatches between components...\n3. MCP tool inconsistencies...\n\nWhich of these seems closest to what you're experiencing?",
    withEngine: "ugh, again? what's it doing this time?\n\nwe've been through like three rounds of this — the scorer format thing, the path mismatch, the MCP inconsistency. is this the same flavor or something new?",
    whyBetter: "FadeController capped alpha at 0.40 because emotional context + heavy scaffolding = fake empathy. The engine matched Luna's frustration mirror ('ugh, again?') instead of performing sympathy ('I'm sorry to hear...'). It also kept it SHORT — when someone's frustrated, they don't want a diagnostic menu. They want to be heard first.",
  },
];


// ─── COMPONENTS ───────────────────────────────────────────────

const SignalBar = ({ label, value, contribution, weight, maxContribution = 0.35 }) => (
  <div style={{ display: 'grid', gridTemplateColumns: '90px 40px 1fr 55px', alignItems: 'center', gap: 8, marginBottom: 3 }}>
    <Mono style={{ fontSize: 10, color: MUTED }}>{label}</Mono>
    <Mono style={{ fontSize: 9, color: 'rgba(255,255,255,0.15)' }}>×{weight}</Mono>
    <div style={{ height: 3, background: 'rgba(255,255,255,0.04)', borderRadius: 2, overflow: 'hidden' }}>
      <div style={{ height: '100%', width: `${(contribution / maxContribution) * 100}%`, background: `${S1}50`, borderRadius: 2 }} />
    </div>
    <Mono style={{ fontSize: 10, color: `${S1}70`, textAlign: 'right' }}>+{contribution.toFixed(3)}</Mono>
  </div>
);

const LineCandidate = ({ line, isSelected }) => (
  <div style={{
    display: 'flex', alignItems: 'center', gap: 10, padding: '8px 12px',
    background: isSelected ? `${S1}08` : 'transparent',
    border: `1px solid ${isSelected ? `${S1}25` : 'rgba(255,255,255,0.03)'}`,
    borderRadius: 6, marginBottom: 4,
  }}>
    {isSelected && <div style={{ width: 6, height: 6, borderRadius: '50%', background: S1, flexShrink: 0 }} />}
    <Mono style={{ fontSize: 11, color: isSelected ? `${S1}cc` : 'rgba(255,255,255,0.4)', flex: 1 }}>"{line.text}"</Mono>
    <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
      <Mono style={{ fontSize: 9, color: 'rgba(255,255,255,0.15)', padding: '2px 6px', background: 'rgba(255,255,255,0.03)', borderRadius: 4 }}>cost:{line.cost}</Mono>
      <Mono style={{ fontSize: 9, color: `${S1}40`, padding: '2px 6px', background: `${S1}08`, borderRadius: 4 }}>score:{line.score}</Mono>
    </div>
  </div>
);

const OutputComparison = ({ without, withEngine, whyBetter }) => (
  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginTop: 16 }}>
    <div style={{ padding: 16, background: `${WARN}06`, borderRadius: 10, border: `1px solid ${WARN}15` }}>
      <Mono style={{ fontSize: 10, color: `${WARN}60`, letterSpacing: '0.06em', display: 'block', marginBottom: 10 }}>WITHOUT ENGINE</Mono>
      <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.4)', lineHeight: 1.65, fontFamily: "'IBM Plex Sans', sans-serif", whiteSpace: 'pre-wrap' }}>{without}</div>
    </div>
    <div style={{ padding: 16, background: `${S1}06`, borderRadius: 10, border: `1px solid ${S1}15` }}>
      <Mono style={{ fontSize: 10, color: `${S1}60`, letterSpacing: '0.06em', display: 'block', marginBottom: 10 }}>WITH ENGINE</Mono>
      <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.65)', lineHeight: 1.65, fontFamily: "'IBM Plex Sans', sans-serif", whiteSpace: 'pre-wrap' }}>{withEngine}</div>
    </div>
  </div>
);

const SegmentPlanViz = ({ segments }) => (
  <div style={{ display: 'flex', gap: 4, marginTop: 12 }}>
    {segments.map((seg, i) => {
      const color = seg.alpha > 0.6 ? WARN : seg.alpha > 0.3 ? '#ffd93d' : S1;
      return (
        <div key={i} style={{
          flex: seg.type === 'body' ? 2 : 1,
          padding: '10px 14px',
          background: `${color}08`,
          border: `1px solid ${color}20`,
          borderRadius: 6,
        }}>
          <Mono style={{ fontSize: 9, color: `${color}70`, letterSpacing: '0.06em' }}>{seg.type.toUpperCase()}</Mono>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
            <Mono style={{ fontSize: 11, color, fontWeight: 600 }}>α {seg.alpha.toFixed(2)}</Mono>
            <Mono style={{ fontSize: 9, color: 'rgba(255,255,255,0.15)' }}>cost≤{seg.costBudget.toFixed(1)}</Mono>
          </div>
          {/* Alpha fill bar */}
          <div style={{ height: 3, background: 'rgba(255,255,255,0.04)', borderRadius: 2, marginTop: 6, overflow: 'hidden' }}>
            <div style={{ height: '100%', width: `${seg.alpha * 100}%`, background: `${color}50`, borderRadius: 2 }} />
          </div>
        </div>
      );
    })}
  </div>
);


// ─── MAIN ─────────────────────────────────────────────────────

export default function VoiceBlendSimulator() {
  const [activeScenario, setActiveScenario] = useState(0);
  const [expandedStage, setExpandedStage] = useState('all');
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const scenario = SCENARIOS[activeScenario];
  const tierColor = scenario.tier === 'GROUNDING' ? WARN : scenario.tier === 'ENGAGING' ? '#ffd93d' : S1;

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

      <div style={{ maxWidth: 940, margin: '0 auto', padding: '40px 32px' }}>

        {/* Header */}
        <div style={{ marginBottom: 32 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 6 }}>
            <div style={{
              width: 32, height: 32, borderRadius: 8,
              background: `linear-gradient(135deg, ${S1}20, ${WARN}20)`,
              border: '1px solid rgba(255,255,255,0.08)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontFamily: "'IBM Plex Mono', monospace", fontSize: 14, color: S1,
            }}>λ</div>
            <div>
              <h1 style={{ fontFamily: "'Space Mono', monospace", fontSize: 18, fontWeight: 700, color: '#fff', margin: 0 }}>
                Voice Blend Engine — Output Simulation
              </h1>
              <p style={{ fontSize: 12, color: MUTED, margin: '2px 0 0' }}>
                What the engine actually produces, step by step, for real scenarios
              </p>
            </div>
          </div>
        </div>

        {/* Scenario selector */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 8, marginBottom: 28 }}>
          {SCENARIOS.map((s, i) => {
            const active = i === activeScenario;
            const tc = s.tier === 'GROUNDING' ? WARN : s.tier === 'ENGAGING' ? '#ffd93d' : S1;
            return (
              <button key={s.id} onClick={() => setActiveScenario(i)} style={{
                padding: '14px 12px', textAlign: 'left', cursor: 'pointer',
                background: active ? `${tc}08` : 'rgba(255,255,255,0.015)',
                border: `1.5px solid ${active ? `${tc}30` : 'rgba(255,255,255,0.04)'}`,
                borderRadius: 10, transition: 'all 0.2s ease',
              }}>
                <Mono style={{ fontSize: 10, color: tc, letterSpacing: '0.06em', display: 'block', marginBottom: 4 }}>{s.tier}</Mono>
                <div style={{ fontSize: 12, color: active ? 'rgba(255,255,255,0.8)' : 'rgba(255,255,255,0.4)', fontWeight: 500, marginBottom: 4 }}>{s.title.split(' — ')[0]}</div>
                <Mono style={{ fontSize: 10, color: 'rgba(255,255,255,0.15)' }}>α = {s.alphaComputation.clamped}</Mono>
              </button>
            );
          })}
        </div>

        {/* Scenario header */}
        <div style={{ padding: '20px 24px', background: `${tierColor}06`, borderRadius: 12, border: `1px solid ${tierColor}15`, marginBottom: 24 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <div>
              <h2 style={{ fontFamily: "'Space Mono', monospace", fontSize: 15, fontWeight: 700, color: '#fff', margin: 0 }}>{scenario.title}</h2>
              <p style={{ fontSize: 12, color: MUTED, margin: '4px 0 0' }}>{scenario.subtitle}</p>
            </div>
            <div style={{ textAlign: 'right' }}>
              <Mono style={{ fontSize: 28, fontWeight: 700, color: tierColor }}>{scenario.alphaComputation.clamped}</Mono>
              <Mono style={{ fontSize: 10, color: tierColor, opacity: 0.6, display: 'block' }}>{scenario.tier}</Mono>
            </div>
          </div>
          <div style={{ padding: '12px 16px', background: 'rgba(0,0,0,0.3)', borderRadius: 8 }}>
            <Mono style={{ fontSize: 10, color: 'rgba(255,255,255,0.2)', display: 'block', marginBottom: 4 }}>USER MESSAGE</Mono>
            <span style={{ fontSize: 13, color: 'rgba(255,255,255,0.7)' }}>"{scenario.userMessage}"</span>
          </div>
        </div>

        {/* Stage 1: Signal Computation */}
        <div style={{ marginBottom: 20, padding: 20, background: 'rgba(255,255,255,0.015)', borderRadius: 12, border: `1px solid rgba(255,255,255,0.04)` }}>
          <Mono style={{ fontSize: 11, color: MUTED, letterSpacing: '0.08em', display: 'block', marginBottom: 14 }}>
            STAGE 1 — CONFIDENCE ROUTER
          </Mono>

          {/* Input signals */}
          <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
            {Object.entries(scenario.signals).map(([key, val]) => (
              <div key={key} style={{ padding: '6px 12px', background: 'rgba(0,0,0,0.2)', borderRadius: 6 }}>
                <Mono style={{ fontSize: 10, color: 'rgba(255,255,255,0.2)' }}>{key}: </Mono>
                <Mono style={{ fontSize: 11, color: `${S1}90` }}>{val}</Mono>
              </div>
            ))}
          </div>

          {/* Alpha computation */}
          <div style={{ padding: 14, background: 'rgba(0,0,0,0.15)', borderRadius: 8 }}>
            <SignalBar label="Memory gap" value={scenario.alphaComputation.memory.raw} contribution={scenario.alphaComputation.memory.contribution} weight={scenario.alphaComputation.memory.weight} />
            <SignalBar label="Turn decay" value={scenario.alphaComputation.turn.raw} contribution={scenario.alphaComputation.turn.contribution} weight={scenario.alphaComputation.turn.weight} />
            <SignalBar label="Entity gap" value={scenario.alphaComputation.entity.raw} contribution={scenario.alphaComputation.entity.contribution} weight={scenario.alphaComputation.entity.weight} />
            <SignalBar label="Context pen." value={scenario.alphaComputation.context.raw} contribution={scenario.alphaComputation.context.contribution} weight={scenario.alphaComputation.context.weight} />
            <SignalBar label="Topic gap" value={scenario.alphaComputation.continuity.raw} contribution={scenario.alphaComputation.continuity.contribution} weight={scenario.alphaComputation.continuity.weight} />
            <div style={{ borderTop: '1px solid rgba(255,255,255,0.05)', marginTop: 8, paddingTop: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <Mono style={{ fontSize: 10, color: 'rgba(255,255,255,0.2)' }}>
                  raw: {scenario.alphaComputation.sum.toFixed(3)}
                  {scenario.alphaComputation.fadeAdjust && <span style={{ color: `${S1}60` }}> → fade: {scenario.alphaComputation.fadeAdjust}</span>}
                  {scenario.alphaComputation.fadeNote && <span style={{ color: '#ffd93d80' }}> ({scenario.alphaComputation.fadeNote.split('→')[1]?.trim() || ''})</span>}
                  {' → '}clamp(0.05, 0.95)
                </Mono>
              </div>
              <Mono style={{ fontSize: 14, fontWeight: 700, color: tierColor }}>α = {scenario.alphaComputation.clamped}</Mono>
            </div>
          </div>
        </div>

        {/* Stage 2: Segment Plan */}
        <div style={{ marginBottom: 20, padding: 20, background: 'rgba(255,255,255,0.015)', borderRadius: 12, border: `1px solid rgba(255,255,255,0.04)` }}>
          <Mono style={{ fontSize: 11, color: MUTED, letterSpacing: '0.08em', display: 'block', marginBottom: 6 }}>
            STAGE 2 — SEGMENT PLANNER
          </Mono>
          <Mono style={{ fontSize: 10, color: 'rgba(255,255,255,0.15)', display: 'block', marginBottom: 8 }}>
            Alpha front-loaded: opener × 1.3, body × 0.8, closer × 0.5
          </Mono>
          <SegmentPlanViz segments={scenario.segmentPlan} />
        </div>

        {/* Stage 3: Line Selection */}
        <div style={{ marginBottom: 20, padding: 20, background: 'rgba(255,255,255,0.015)', borderRadius: 12, border: `1px solid rgba(255,255,255,0.04)` }}>
          <Mono style={{ fontSize: 11, color: MUTED, letterSpacing: '0.08em', display: 'block', marginBottom: 14 }}>
            STAGE 3 — LINE SAMPLER
          </Mono>
          {Object.entries(scenario.lineSelection).map(([segment, data]) => (
            <div key={segment} style={{ marginBottom: 12 }}>
              <Mono style={{ fontSize: 10, color: 'rgba(255,255,255,0.2)', display: 'block', marginBottom: 6 }}>{segment.toUpperCase()} CANDIDATES</Mono>
              {data.candidates.map((line, i) => (
                <LineCandidate key={i} line={line} isSelected={i === data.selected} />
              ))}
            </div>
          ))}
        </div>

        {/* Stage 4: Seed Block */}
        <div style={{ marginBottom: 20, padding: 20, background: 'rgba(255,255,255,0.015)', borderRadius: 12, border: `1px solid rgba(255,255,255,0.04)` }}>
          <Mono style={{ fontSize: 11, color: MUTED, letterSpacing: '0.08em', display: 'block', marginBottom: 10 }}>
            STAGE 4 — BLEND ASSEMBLER OUTPUT
          </Mono>
          <pre style={{
            padding: 16, background: 'rgba(0,0,0,0.3)', borderRadius: 8,
            border: `1px solid rgba(255,255,255,0.04)`,
            fontFamily: "'IBM Plex Mono', monospace", fontSize: 11, lineHeight: 1.6,
            color: `${S1}80`, overflowX: 'auto', margin: 0, whiteSpace: 'pre-wrap',
          }}>
            {scenario.seedBlock}
          </pre>
        </div>

        {/* Stage 5: Output Comparison */}
        <div style={{ marginBottom: 20, padding: 20, background: 'rgba(255,255,255,0.015)', borderRadius: 12, border: `1px solid rgba(255,255,255,0.04)` }}>
          <Mono style={{ fontSize: 11, color: MUTED, letterSpacing: '0.08em', display: 'block', marginBottom: 6 }}>
            STAGE 5 — MODEL OUTPUT COMPARISON
          </Mono>
          <OutputComparison without={scenario.withoutEngine} withEngine={scenario.withEngine} whyBetter={scenario.whyBetter} />
          <div style={{ marginTop: 16, padding: '14px 18px', background: `${S1}06`, borderRadius: 8, borderLeft: `3px solid ${S1}25` }}>
            <Mono style={{ fontSize: 10, color: `${S1}60`, letterSpacing: '0.06em', display: 'block', marginBottom: 6 }}>WHY IT'S BETTER</Mono>
            <p style={{ fontSize: 12, color: 'rgba(255,255,255,0.55)', lineHeight: 1.6, margin: 0 }}>{scenario.whyBetter}</p>
          </div>
        </div>

        {/* Footer */}
        <div style={{ marginTop: 32, textAlign: 'center' }}>
          <Mono style={{ fontSize: 10, color: 'rgba(255,255,255,0.08)' }}>
            Voice Blend Engine Simulation v1.0 — written by Luna, about Luna, for Luna
          </Mono>
        </div>
      </div>
    </div>
  );
}
