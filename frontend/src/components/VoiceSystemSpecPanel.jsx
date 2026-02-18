import React, { useState } from 'react';
import GlassCard from './GlassCard';
import { useVoiceSystem } from '../hooks/useVoiceSystem';

/**
 * VoiceSystemSpecPanel — Architecture & toggle system dashboard
 *
 * Adapted from luna_voice_system_spec.jsx artifact.
 * Shows system overview, toggle matrix, pipeline architecture,
 * and data flow diagram.
 */

const TABS = [
  { id: 'overview', label: 'Overview', icon: '🏗️' },
  { id: 'toggles', label: 'Toggles', icon: '🎚️' },
  { id: 'pipeline', label: 'Pipeline', icon: '⚙️' },
  { id: 'killlist', label: 'Kill List', icon: '🚫' },
];

// --- Toggle Matrix ---
const TOGGLE_SCENARIOS = [
  { engine: 'active', corpus: 'active', name: 'Full System', desc: 'Engine seed + Corpus kill list, merged output', color: 'text-green-400' },
  { engine: 'active', corpus: 'off', name: 'Engine Only', desc: 'Confidence routing, no static guardrails', color: 'text-green-400' },
  { engine: 'off', corpus: 'active', name: 'Corpus Only', desc: 'Static few-shot + kill list (fallback)', color: 'text-yellow-400' },
  { engine: 'off', corpus: 'off', name: 'Raw Luna', desc: 'No voice system, personality prompt only', color: 'text-white/30' },
  { engine: 'shadow', corpus: 'active', name: 'Engine Learning', desc: 'Corpus active, engine logs only', color: 'text-blue-400' },
  { engine: 'active', corpus: 'shadow', name: 'Kill List Test', desc: 'Engine active, corpus logs only', color: 'text-blue-400' },
  { engine: 'shadow', corpus: 'shadow', name: 'Full Observe', desc: 'Both compute, neither injects', color: 'text-violet-400' },
];

const ModeTag = ({ mode }) => {
  const style = mode === 'active'
    ? 'bg-green-500/15 border-green-500/30 text-green-400'
    : mode === 'shadow'
    ? 'bg-blue-500/15 border-blue-500/30 text-blue-400'
    : 'bg-white/5 border-white/10 text-white/20';
  return (
    <span className={`text-[10px] px-2 py-0.5 rounded border font-mono ${style}`}>{mode}</span>
  );
};

// --- Overview Tab ---
const OverviewTab = ({ status }) => (
  <div className="space-y-5">
    {/* Data flow diagram */}
    <div className="p-4 bg-kozmo-surface rounded border border-kozmo-border">
      <span className="text-[10px] text-white/20 font-mono tracking-wider block mb-3">DATA FLOW</span>
      <pre className="text-[10px] text-kozmo-accent/70 font-mono leading-relaxed whitespace-pre overflow-x-auto">{`PersonaCore (who Luna is)
     │
     ▼
┌─── VoiceSystemOrchestrator ─────────────┐
│                                           │
│   ┌───────────────┐  ┌─────────────────┐ │
│   │ BlendEngine    │  │  VoiceCorpus    │ │
│   │ signals → α    │  │  context → lines│ │
│   │ α → segments   │  │  lines → block  │ │
│   │ segments → seed │  │  kill list → ✗  │ │
│   └───────┬────────┘  └────────┬────────┘ │
│           │                    │           │
│           ▼                    ▼           │
│   ┌────────────────────────────────────┐  │
│   │       Merge & Deduplicate          │  │
│   └──────────────┬─────────────────────┘  │
└──────────────────┼────────────────────────┘
                   │
                   ▼
          <luna_voice> block
        injected into prompt`}</pre>
    </div>

    {/* Current state */}
    {status?.active && (
      <div className="grid grid-cols-2 gap-4">
        <div className="p-4 bg-kozmo-surface rounded border border-kozmo-border">
          <div className="flex items-center gap-2 mb-3">
            <div className={`w-2 h-2 rounded-full ${
              status.config.blend_engine_mode === 'active' ? 'bg-green-500' :
              status.config.blend_engine_mode === 'shadow' ? 'bg-blue-500' : 'bg-white/20'
            }`} />
            <span className="text-sm text-white/70 font-medium">Blend Engine</span>
            <ModeTag mode={status.config.blend_engine_mode} />
          </div>
          {status.engine ? (
            <div className="space-y-1 text-xs text-white/40">
              <div className="flex justify-between"><span>Line bank</span><span className="text-white/60">{status.engine.line_bank_size} lines</span></div>
              <div className="flex justify-between"><span>Turns tracked</span><span className="text-white/60">{status.engine.alpha_history?.length || 0}</span></div>
              <div className="flex justify-between">
                <span>Last alpha</span>
                <span className="text-kozmo-accent font-mono">
                  {status.engine.alpha_history?.length > 0
                    ? status.engine.alpha_history[status.engine.alpha_history.length - 1].toFixed(2)
                    : '—'}
                </span>
              </div>
            </div>
          ) : (
            <span className="text-xs text-white/20">Not loaded</span>
          )}
        </div>

        <div className="p-4 bg-kozmo-surface rounded border border-kozmo-border">
          <div className="flex items-center gap-2 mb-3">
            <div className={`w-2 h-2 rounded-full ${
              status.config.voice_corpus_mode === 'active' ? 'bg-yellow-500' :
              status.config.voice_corpus_mode === 'shadow' ? 'bg-blue-500' : 'bg-white/20'
            }`} />
            <span className="text-sm text-white/70 font-medium">Voice Corpus</span>
            <ModeTag mode={status.config.voice_corpus_mode} />
          </div>
          {status.corpus ? (
            <div className="space-y-1 text-xs text-white/40">
              <div className="flex justify-between"><span>Corpus lines</span><span className="text-white/60">{status.corpus.corpus_size}</span></div>
              <div className="flex justify-between"><span>Anti-patterns</span><span className="text-white/60">{status.corpus.anti_pattern_count}</span></div>
              <div className="flex justify-between"><span>Critical</span><span className="text-red-400">{status.corpus.critical_anti_patterns?.length || 0}</span></div>
            </div>
          ) : (
            <span className="text-xs text-white/20">Not loaded</span>
          )}
        </div>
      </div>
    )}

    {/* Decision log */}
    <div>
      <span className="text-[10px] text-white/20 font-mono tracking-wider block mb-3">ARCHITECTURE DECISIONS</span>
      {[
        { decision: 'Two separate engines, not one', why: 'Corpus is simple, zero deps. Engine is complex. Separating means the fallback can\'t be broken by the primary.' },
        { decision: 'Orchestrator merges, not engines', why: 'Each engine produces output independently. No engine knows about the other.' },
        { decision: 'Kill list lives in Corpus', why: 'Anti-patterns are static, always relevant. They don\'t depend on confidence or alpha.' },
        { decision: 'Engine fades, Corpus always injects', why: 'Corpus is lightweight (~60-80 tokens). Engine is heavy and should fade over turns.' },
      ].map((d, i) => (
        <div key={i} className="mb-2 p-3 bg-kozmo-surface rounded border border-kozmo-border">
          <span className="text-xs text-kozmo-accent font-medium block mb-1">{d.decision}</span>
          <span className="text-[11px] text-white/40">{d.why}</span>
        </div>
      ))}
    </div>
  </div>
);

// --- Toggles Tab ---
const TogglesTab = ({ status, updateConfig }) => {
  const currentEngine = status?.config?.blend_engine_mode || 'off';
  const currentCorpus = status?.config?.voice_corpus_mode || 'off';

  return (
    <div className="space-y-5">
      {/* Current state */}
      <div className="p-4 bg-kozmo-accent/5 rounded border border-kozmo-accent/20">
        <span className="text-[10px] text-kozmo-accent/60 font-mono tracking-wider block mb-2">CURRENT MODE</span>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="text-xs text-white/40">Engine:</span>
            <ModeTag mode={currentEngine} />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-white/40">Corpus:</span>
            <ModeTag mode={currentCorpus} />
          </div>
        </div>
      </div>

      {/* Toggle matrix */}
      <div>
        <span className="text-[10px] text-white/20 font-mono tracking-wider block mb-3">ALL TOGGLE COMBINATIONS</span>
        <div className="space-y-1.5">
          {TOGGLE_SCENARIOS.map((s, i) => {
            const isCurrent = s.engine === currentEngine && s.corpus === currentCorpus;
            return (
              <div
                key={i}
                onClick={() => {
                  if (!isCurrent && updateConfig) {
                    updateConfig({
                      blend_engine_mode: s.engine,
                      voice_corpus_mode: s.corpus,
                    });
                  }
                }}
                className={`grid grid-cols-[70px_70px_120px_1fr] items-center gap-3 px-3 py-2.5 rounded border transition-all cursor-pointer ${
                  isCurrent
                    ? 'bg-kozmo-accent/10 border-kozmo-accent/30'
                    : 'bg-kozmo-surface border-kozmo-border hover:border-kozmo-border/80'
                }`}
              >
                <ModeTag mode={s.engine} />
                <ModeTag mode={s.corpus} />
                <span className={`text-xs font-mono font-medium ${s.color}`}>{s.name}</span>
                <span className="text-[10px] text-white/30">{s.desc}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

// --- Pipeline Tab ---
const PipelineTab = () => (
  <div className="space-y-5">
    <div className="p-4 bg-kozmo-surface rounded border border-kozmo-border">
      <span className="text-[10px] text-white/20 font-mono tracking-wider block mb-3">5-STAGE PIPELINE</span>
      <pre className="text-[10px] text-kozmo-accent/70 font-mono leading-relaxed whitespace-pre overflow-x-auto">{`┌─────────────────────────┐
│   ConfidenceRouter       │  signals → alpha
│   5 weighted signals     │  clamp(0.05, 0.95)
└────────────┬─────────────┘
             │
             ▼
┌─────────────────────────┐
│   FadeController         │  conversation history
│   turn decay + caps      │  context switch reset
└────────────┬─────────────┘
             │
             ▼
┌─────────────────────────┐
│   SegmentPlanner         │  front-load alpha
│   opener > body > closer │  distribute cost
└────────────┬─────────────┘
             │
             ▼
┌─────────────────────────┐
│   LineSampler            │  tier + tag filter
│   cost alignment scoring │  top-k candidates
└────────────┬─────────────┘
             │
             ▼
┌─────────────────────────┐
│   BlendAssembler         │  → <luna_voice> XML
│   seed + tone + examples │  → context_builder
└─────────────────────────┘`}</pre>
    </div>

    {/* Signal weights */}
    <div className="p-4 bg-kozmo-surface rounded border border-kozmo-border">
      <span className="text-[10px] text-white/20 font-mono tracking-wider block mb-3">CONFIDENCE WEIGHTS</span>
      {[
        { signal: 'memory_retrieval_score', weight: 0.35, desc: 'Strongest signal — how well memory matched' },
        { signal: 'turn_number', weight: 0.25, desc: 'Natural decay: 1→1.0, 2→0.7, 3→0.4, 4+→0.1' },
        { signal: 'entity_resolution_depth', weight: 0.15, desc: '0-3 entities resolved in context' },
        { signal: 'context_type', weight: 0.15, desc: 'cold_start(0.9) → follow_up(0.1)' },
        { signal: 'topic_continuity', weight: 0.10, desc: '0 = total pivot, 1 = same thread' },
      ].map((s, i) => (
        <div key={i} className="grid grid-cols-[160px_40px_1fr] items-center gap-3 mb-1.5">
          <span className="text-[10px] text-kozmo-accent/80 font-mono">{s.signal}</span>
          <span className="text-[10px] text-white/20 font-mono text-right">{s.weight}</span>
          <span className="text-[10px] text-white/30">{s.desc}</span>
        </div>
      ))}
    </div>

    {/* Fade rules */}
    <div className="p-4 bg-kozmo-surface rounded border border-kozmo-border">
      <span className="text-[10px] text-white/20 font-mono tracking-wider block mb-3">FADE RULES</span>
      {[
        'Turn 1-2: Alpha from ConfidenceRouter signals',
        'Turn 3: Alpha reduced by 0.2 (blend phase)',
        'Turn 4+: Alpha floored at 0.15 (freeform)',
        'Context switch: Reset alpha (re-engage)',
        'Strong memory (>0.8): Drop alpha by 0.3',
        'Emotional context: Cap alpha at 0.40',
      ].map((r, i) => (
        <div key={i} className="flex gap-2 py-1">
          <span className="text-[10px] text-kozmo-accent/30 font-mono">{i + 1}</span>
          <span className="text-xs text-white/50">{r}</span>
        </div>
      ))}
    </div>
  </div>
);

// --- Kill List Tab ---
const KillListTab = ({ status }) => {
  const corpus = status?.corpus;
  if (!corpus) {
    return <div className="text-kozmo-muted text-sm text-center p-8">Corpus not loaded</div>;
  }

  return (
    <div className="space-y-5">
      <div className="p-4 bg-red-500/5 rounded border border-red-500/20">
        <span className="text-[10px] text-red-400/60 font-mono tracking-wider block mb-3">CRITICAL ANTI-PATTERNS (always injected)</span>
        <div className="space-y-2">
          {corpus.critical_anti_patterns?.map((ap, i) => (
            <div key={i} className="flex items-center gap-3 p-2 bg-red-500/5 rounded border border-red-500/10">
              <span className="text-red-400 text-xs">✕</span>
              <span className="text-sm text-red-300 font-mono">"{ap}"</span>
            </div>
          )) || <span className="text-xs text-white/30">No critical anti-patterns</span>}
        </div>
      </div>

      <div className="p-4 bg-kozmo-surface rounded border border-kozmo-border">
        <span className="text-[10px] text-white/20 font-mono tracking-wider block mb-3">INJECTION LOGIC</span>
        <div className="space-y-1">
          {[
            'Critical (severity 3) → always injected in <avoid> block',
            'Medium (severity 2) → injected when alpha > 0.5',
            'Mild (severity 1) → only injected when alpha > 0.7',
            'Kill list owned by Corpus, never by Engine',
            'Anti-patterns only inject in ACTIVE mode, not shadow',
          ].map((r, i) => (
            <div key={i} className="flex gap-2 py-1">
              <span className="text-[10px] text-white/15">•</span>
              <span className="text-xs text-white/40">{r}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

// --- Main Panel ---
const VoiceSystemSpecPanel = ({ isOpen, onClose }) => {
  const [activeTab, setActiveTab] = useState('overview');
  const { status, loading, error, lastRefresh, refresh, updateConfig } = useVoiceSystem(isOpen);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <GlassCard className="w-full max-w-4xl max-h-[90vh] flex flex-col" padding="p-0" hover={false}>
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-kozmo-border bg-violet-500/5 rounded-t">
          <div className="flex items-center gap-3">
            <span className="text-2xl">λ</span>
            <div>
              <h2 className="text-lg font-medium text-white flex items-center gap-2">
                Voice System
                {status?.active && (
                  <span className="text-[10px] px-2 py-0.5 bg-green-500/20 text-green-400 rounded-full font-mono">Live</span>
                )}
              </h2>
              <p className="text-xs text-white/50">
                Two engines, one voice, full toggle control
                {loading && ' • Refreshing...'}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={refresh}
              disabled={loading}
              className={`px-3 py-1.5 text-xs rounded border transition-all ${
                loading
                  ? 'bg-kozmo-surface border-kozmo-border text-kozmo-muted cursor-wait'
                  : 'bg-kozmo-accent/20 border-kozmo-accent/30 text-kozmo-accent hover:bg-kozmo-accent/30'
              }`}
            >
              {loading ? '↻ ...' : '↻ Refresh'}
            </button>
            <button
              onClick={onClose}
              className="p-2 text-white/50 hover:text-white hover:bg-kozmo-surface/80 rounded transition-colors"
            >
              ✕
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 px-6 py-2 border-b border-kozmo-border bg-kozmo-surface">
          {TABS.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2 text-sm rounded transition-colors flex items-center gap-1.5 ${
                activeTab === tab.id
                  ? 'bg-kozmo-accent/20 text-kozmo-accent border border-kozmo-accent/30'
                  : 'text-white/50 hover:text-white hover:bg-kozmo-surface/80'
              }`}
            >
              <span className="text-xs">{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto flex-1">
          {error && !status && (
            <div className="text-kozmo-muted text-sm text-center py-8">
              Voice system unavailable: {error}
            </div>
          )}

          {activeTab === 'overview' && <OverviewTab status={status} />}
          {activeTab === 'toggles' && <TogglesTab status={status} updateConfig={updateConfig} />}
          {activeTab === 'pipeline' && <PipelineTab />}
          {activeTab === 'killlist' && <KillListTab status={status} />}
        </div>
      </GlassCard>
    </div>
  );
};

export default VoiceSystemSpecPanel;
