import React, { useState, useMemo } from 'react';
import GlassCard from './GlassCard';
import { useVoiceSystem } from '../hooks/useVoiceSystem';

/**
 * VoiceBlendPanel — Live Voice Blend Engine dashboard
 *
 * Adapted from voice_blend_engine.jsx artifact.
 * Shows alpha gauge, signal decomposition, conversation trace,
 * fade timeline, and live alpha simulator.
 */

const TABS = [
  { id: 'live', label: 'Live', icon: '⚡' },
  { id: 'simulator', label: 'Simulator', icon: '🎛️' },
  { id: 'history', label: 'History', icon: '📈' },
  { id: 'config', label: 'Config', icon: '⚙️' },
];

// --- Alpha gauge ---
const AlphaGauge = ({ alpha, tier }) => {
  const tierColor = tier === 'GROUNDING'
    ? 'text-red-400' : tier === 'ENGAGING'
    ? 'text-yellow-400' : 'text-green-400';
  const tierBg = tier === 'GROUNDING'
    ? 'bg-red-500' : tier === 'ENGAGING'
    ? 'bg-yellow-500' : 'bg-green-500';
  const pct = (alpha * 100).toFixed(0);

  return (
    <div className="flex items-center gap-4">
      <div className="flex-1">
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs text-white/50 font-mono">ALPHA</span>
          <div className="flex items-center gap-2">
            <span className={`text-2xl font-bold font-mono ${tierColor}`}>{alpha.toFixed(2)}</span>
            <span className={`text-[10px] px-2 py-0.5 rounded ${tierBg}/20 ${tierColor} font-mono`}>{tier}</span>
          </div>
        </div>
        <div className="h-2 bg-kozmo-border rounded-full overflow-hidden">
          <div
            className={`h-full ${tierBg} rounded-full transition-all duration-500`}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>
    </div>
  );
};

// --- Signal bar ---
const SignalBar = ({ name, weight, raw, weighted }) => (
  <div className="grid grid-cols-[90px_30px_1fr_50px] items-center gap-2 mb-1">
    <span className="text-[10px] text-white/40 font-mono truncate">{name}</span>
    <span className="text-[10px] text-white/15 font-mono">×{weight}</span>
    <div className="h-1.5 bg-kozmo-border rounded-full overflow-hidden">
      <div
        className="h-full bg-kozmo-accent/60 rounded-full transition-all duration-300"
        style={{ width: `${Math.min(100, (weighted / 0.35) * 100)}%` }}
      />
    </div>
    <span className="text-[10px] text-kozmo-accent/80 font-mono text-right">+{weighted.toFixed(3)}</span>
  </div>
);

// --- Alpha Simulator (from artifact) ---
const AlphaSimulator = ({ simulate }) => {
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
    + weights.context * (contextPenalties[contextType] || 0.5)
    + weights.continuity * (1 - topicContinuity);
  const alpha = Math.min(0.95, Math.max(0.05, rawAlpha));
  const tier = alpha > 0.6 ? 'GROUNDING' : alpha > 0.3 ? 'ENGAGING' : 'FLOWING';

  const signals = [
    { name: 'Memory', raw: (1 - memoryScore), weighted: weights.memory * (1 - memoryScore), w: weights.memory },
    { name: 'Turn Decay', raw: decay, weighted: weights.turn * decay, w: weights.turn },
    { name: 'Entity Gap', raw: (1 - entityDepth / 3), weighted: weights.entity * (1 - entityDepth / 3), w: weights.entity },
    { name: 'Context', raw: contextPenalties[contextType] || 0.5, weighted: weights.context * (contextPenalties[contextType] || 0.5), w: weights.context },
    { name: 'Topic Gap', raw: (1 - topicContinuity), weighted: weights.continuity * (1 - topicContinuity), w: weights.continuity },
  ];

  const contextTypes = Object.keys(contextPenalties);

  const SliderRow = ({ label, value, onChange, min = 0, max = 1, step = 0.1, displayValue }) => (
    <div className="grid grid-cols-[100px_1fr_40px] items-center gap-3 mb-2">
      <span className="text-[11px] text-white/40 font-mono">{label}</span>
      <input
        type="range" min={min} max={max} step={step} value={value}
        onChange={e => onChange(parseFloat(e.target.value))}
        className="w-full h-1 bg-kozmo-border rounded appearance-none cursor-pointer accent-kozmo-accent"
      />
      <span className="text-xs text-kozmo-accent font-mono text-right">{displayValue ?? value.toFixed(1)}</span>
    </div>
  );

  return (
    <div className="space-y-4">
      <AlphaGauge alpha={alpha} tier={tier} />

      <div className="p-4 bg-kozmo-surface rounded border border-kozmo-border">
        <SliderRow label="Memory" value={memoryScore} onChange={setMemoryScore} />
        <SliderRow label="Turn" value={turnNumber} onChange={setTurnNumber} min={1} max={8} step={1} displayValue={turnNumber} />
        <SliderRow label="Entity Depth" value={entityDepth} onChange={setEntityDepth} min={0} max={3} step={1} displayValue={entityDepth} />
        <SliderRow label="Continuity" value={topicContinuity} onChange={setTopicContinuity} />

        <div className="flex gap-1.5 flex-wrap mt-3">
          {contextTypes.map(ct => (
            <button
              key={ct}
              onClick={() => setContextType(ct)}
              className={`px-2.5 py-1 text-[10px] font-mono rounded border transition-all ${
                contextType === ct
                  ? 'bg-kozmo-accent/15 border-kozmo-accent/40 text-kozmo-accent'
                  : 'bg-kozmo-surface border-kozmo-border text-white/30 hover:text-white/50'
              }`}
            >
              {ct}
            </button>
          ))}
        </div>
      </div>

      {/* Signal decomposition */}
      <div className="p-3 bg-black/20 rounded">
        <span className="text-[10px] text-white/20 font-mono tracking-wider block mb-2">SIGNAL DECOMPOSITION</span>
        {signals.map(s => (
          <SignalBar key={s.name} name={s.name} weight={s.w} raw={s.raw} weighted={s.weighted} />
        ))}
        <div className="border-t border-white/5 mt-2 pt-2 flex justify-between">
          <span className="text-[10px] text-white/20 font-mono">raw → clamp(0.05, 0.95)</span>
          <span className={`text-[11px] font-mono font-semibold ${
            tier === 'GROUNDING' ? 'text-red-400' : tier === 'ENGAGING' ? 'text-yellow-400' : 'text-green-400'
          }`}>
            α = {alpha.toFixed(3)}
          </span>
        </div>
      </div>
    </div>
  );
};

// --- Conversation Trace ---
const ConversationTrace = ({ alphaHistory, turnHistory }) => {
  if (!alphaHistory || alphaHistory.length === 0) {
    return (
      <div className="text-kozmo-muted text-sm text-center p-8">
        No conversation history yet. Start chatting to see alpha curve.
      </div>
    );
  }

  const maxAlpha = Math.max(...alphaHistory, 0.1);

  return (
    <div className="space-y-4">
      {/* Visual bars */}
      <div className="flex items-end gap-1 h-20 px-2">
        {alphaHistory.map((a, i) => {
          const color = a > 0.6 ? 'bg-red-500' : a > 0.3 ? 'bg-yellow-500' : 'bg-green-500';
          const textColor = a > 0.6 ? 'text-red-400' : a > 0.3 ? 'text-yellow-400' : 'text-green-400';
          return (
            <div key={i} className="flex-1 flex flex-col items-center gap-1">
              <span className={`text-[9px] font-mono ${textColor}`}>{a.toFixed(2)}</span>
              <div
                className={`w-full max-w-[48px] ${color}/30 border border-current/50 rounded-t transition-all`}
                style={{ height: `${(a / maxAlpha) * 60}px`, borderColor: color.replace('bg-', 'rgba(') }}
              />
            </div>
          );
        })}
      </div>

      {/* Turn details */}
      <div className="space-y-1">
        {alphaHistory.map((a, i) => {
          const tier = a > 0.6 ? 'GRND' : a > 0.3 ? 'ENG' : 'FLOW';
          const textColor = a > 0.6 ? 'text-red-400' : a > 0.3 ? 'text-yellow-400' : 'text-green-400';
          const ctx = turnHistory?.[i] || '?';
          return (
            <div key={i} className={`grid grid-cols-[30px_50px_1fr_50px] items-center gap-2 px-3 py-1.5 rounded ${
              i % 2 === 0 ? 'bg-white/[0.01]' : ''
            }`}>
              <span className="text-[10px] text-white/20 font-mono">T{i + 1}</span>
              <span className={`text-[10px] px-2 py-0.5 rounded ${textColor} bg-current/10 text-center font-mono`}>{tier}</span>
              <span className="text-[10px] text-white/30 font-mono">{ctx}</span>
              <span className={`text-sm font-bold font-mono ${textColor} text-right`}>{a.toFixed(2)}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
};

// --- Config Tab ---
const ConfigTab = ({ status, updateConfig, resetConversation }) => {
  if (!status?.active) {
    return <div className="text-kozmo-muted text-sm text-center p-8">Voice system not loaded</div>;
  }

  const config = status.config;
  const engine = status.engine;
  const corpus = status.corpus;

  const ModeButton = ({ label, current, options, onChange }) => (
    <div className="mb-3">
      <span className="text-[10px] text-white/40 font-mono block mb-1">{label}</span>
      <div className="flex gap-1">
        {options.map(opt => (
          <button
            key={opt}
            onClick={() => onChange(opt)}
            className={`px-3 py-1.5 text-[10px] font-mono rounded border transition-all ${
              current === opt
                ? opt === 'active' ? 'bg-green-500/15 border-green-500/40 text-green-400'
                : opt === 'shadow' ? 'bg-blue-500/15 border-blue-500/40 text-blue-400'
                : 'bg-white/5 border-white/10 text-white/30'
                : 'bg-kozmo-surface border-kozmo-border text-white/20 hover:text-white/40'
            }`}
          >
            {opt}
          </button>
        ))}
      </div>
    </div>
  );

  const ToggleRow = ({ label, value, field }) => (
    <div className="flex items-center justify-between py-1.5">
      <span className="text-xs text-white/50">{label}</span>
      <button
        onClick={() => updateConfig({ [field]: !value })}
        className={`w-8 h-4 rounded-full transition-all ${value ? 'bg-kozmo-accent' : 'bg-kozmo-border'}`}
      >
        <div className={`w-3 h-3 rounded-full bg-white transition-all ${value ? 'ml-4' : 'ml-0.5'}`} />
      </button>
    </div>
  );

  return (
    <div className="space-y-5">
      {/* Engine modes */}
      <div className="grid grid-cols-2 gap-4">
        <div className="p-4 bg-kozmo-surface rounded border border-kozmo-border">
          <ModeButton
            label="BLEND ENGINE"
            current={config.blend_engine_mode}
            options={['active', 'shadow', 'off']}
            onChange={v => updateConfig({ blend_engine_mode: v })}
          />
          {engine && (
            <div className="text-[10px] text-white/30 font-mono space-y-1 mt-2">
              <div>Lines: {engine.line_bank_size}</div>
              <div>Turns: {engine.alpha_history?.length || 0}</div>
            </div>
          )}
        </div>
        <div className="p-4 bg-kozmo-surface rounded border border-kozmo-border">
          <ModeButton
            label="VOICE CORPUS"
            current={config.voice_corpus_mode}
            options={['active', 'shadow', 'off']}
            onChange={v => updateConfig({ voice_corpus_mode: v })}
          />
          {corpus && (
            <div className="text-[10px] text-white/30 font-mono space-y-1 mt-2">
              <div>Lines: {corpus.corpus_size}</div>
              <div>Anti-patterns: {corpus.anti_pattern_count}</div>
            </div>
          )}
        </div>
      </div>

      {/* Bypasses */}
      {engine && (
        <div className="p-4 bg-kozmo-surface rounded border border-kozmo-border">
          <span className="text-[10px] text-white/30 font-mono tracking-wider block mb-2">COMPONENT BYPASS</span>
          <ToggleRow label="Confidence Router" value={engine.bypasses.confidence_router} field="bypass_confidence_router" />
          <ToggleRow label="Fade Controller" value={engine.bypasses.fade_controller} field="bypass_fade_controller" />
          <ToggleRow label="Segment Planner" value={engine.bypasses.segment_planner} field="bypass_segment_planner" />
          <ToggleRow label="Line Sampler" value={engine.bypasses.line_sampler} field="bypass_line_sampler" />
        </div>
      )}

      {/* Anti-patterns */}
      {corpus?.critical_anti_patterns?.length > 0 && (
        <div className="p-4 bg-kozmo-surface rounded border border-kozmo-border">
          <span className="text-[10px] text-white/30 font-mono tracking-wider block mb-2">KILL LIST (critical)</span>
          <div className="flex flex-wrap gap-1.5">
            {corpus.critical_anti_patterns.map((ap, i) => (
              <span key={i} className="text-[10px] px-2 py-1 bg-red-500/10 border border-red-500/20 text-red-400 rounded font-mono">
                {ap}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Reset */}
      <button
        onClick={resetConversation}
        className="w-full py-2 text-xs font-mono text-white/40 bg-kozmo-surface border border-kozmo-border rounded hover:text-white/60 hover:border-kozmo-border/80 transition-all"
      >
        Reset Conversation State
      </button>
    </div>
  );
};

// --- Main Panel ---
const VoiceBlendPanel = ({ isOpen, onClose }) => {
  const [activeTab, setActiveTab] = useState('live');
  const { status, loading, error, lastRefresh, refresh, updateConfig, simulate, resetConversation } = useVoiceSystem(isOpen);

  if (!isOpen) return null;

  const engine = status?.engine;
  const lastAlpha = engine?.alpha_history?.length > 0
    ? engine.alpha_history[engine.alpha_history.length - 1]
    : null;
  const lastTier = lastAlpha != null
    ? (lastAlpha > 0.6 ? 'GROUNDING' : lastAlpha > 0.3 ? 'ENGAGING' : 'FLOWING')
    : null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <GlassCard className="w-full max-w-4xl max-h-[90vh] flex flex-col" padding="p-0" hover={false}>
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-kozmo-border bg-kozmo-accent/5 rounded-t">
          <div className="flex items-center gap-3">
            <span className="text-2xl">λ</span>
            <div>
              <h2 className="text-lg font-medium text-white flex items-center gap-2">
                Voice Blend Engine
                {status?.active && (
                  <span className="text-[10px] px-2 py-0.5 bg-green-500/20 text-green-400 rounded-full font-mono">
                    {status.config?.blend_engine_mode}
                  </span>
                )}
              </h2>
              <p className="text-xs text-white/50">
                {lastRefresh ? `Last: ${lastRefresh.toLocaleTimeString()}` : 'Loading...'}
                {loading && ' • Refreshing...'}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {lastAlpha != null && (
              <div className="flex items-center gap-2 mr-3">
                <span className={`text-xl font-bold font-mono ${
                  lastTier === 'GROUNDING' ? 'text-red-400' : lastTier === 'ENGAGING' ? 'text-yellow-400' : 'text-green-400'
                }`}>{lastAlpha.toFixed(2)}</span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${
                  lastTier === 'GROUNDING' ? 'bg-red-500/15 text-red-400'
                  : lastTier === 'ENGAGING' ? 'bg-yellow-500/15 text-yellow-400'
                  : 'bg-green-500/15 text-green-400'
                }`}>{lastTier}</span>
              </div>
            )}
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

          {activeTab === 'live' && (
            <div className="space-y-5">
              {lastAlpha != null ? (
                <>
                  <AlphaGauge alpha={lastAlpha} tier={lastTier} />
                  {/* Signal contributions from last computation */}
                  {engine?.alpha_history?.length > 0 && (
                    <div className="p-4 bg-kozmo-surface rounded border border-kozmo-border">
                      <span className="text-[10px] text-white/20 font-mono tracking-wider block mb-2">ENGINE STATE</span>
                      <div className="grid grid-cols-3 gap-3">
                        <div className="text-center">
                          <div className="text-lg font-bold text-kozmo-accent font-mono">{engine.alpha_history.length}</div>
                          <div className="text-[10px] text-white/30">turns</div>
                        </div>
                        <div className="text-center">
                          <div className="text-lg font-bold text-kozmo-accent font-mono">{engine.line_bank_size}</div>
                          <div className="text-[10px] text-white/30">lines</div>
                        </div>
                        <div className="text-center">
                          <div className="text-lg font-bold text-kozmo-accent font-mono">
                            {Object.values(engine.bypasses || {}).filter(Boolean).length}
                          </div>
                          <div className="text-[10px] text-white/30">bypasses</div>
                        </div>
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <div className="text-kozmo-muted text-sm text-center py-8">
                  {status?.active ? 'No alpha computed yet. Start a conversation.' : 'Voice system not loaded.'}
                </div>
              )}
            </div>
          )}

          {activeTab === 'simulator' && (
            <AlphaSimulator simulate={simulate} />
          )}

          {activeTab === 'history' && (
            <ConversationTrace
              alphaHistory={engine?.alpha_history || []}
              turnHistory={engine?.turn_history || []}
            />
          )}

          {activeTab === 'config' && (
            <ConfigTab
              status={status}
              updateConfig={updateConfig}
              resetConversation={resetConversation}
            />
          )}
        </div>
      </GlassCard>
    </div>
  );
};

export default VoiceBlendPanel;
