import React, { useState, useEffect, useCallback } from 'react';
import GlassCard from './GlassCard';

const API_BASE = 'http://127.0.0.1:8000';

// Layer definitions with colors
const LAYERS = [
  { key: 'identity',      label: 'IDENTITY',      color: 'yellow',  metaKey: 'identity_source' },
  { key: 'expression',    label: 'EXPRESSION',     color: 'orange',  metaKey: null },
  { key: 'temporal',      label: 'TEMPORAL',       color: 'blue',    metaKey: 'gap_category' },
  { key: 'memory',        label: 'MEMORY',         color: 'purple',  metaKey: 'memory_source' },
  { key: 'consciousness', label: 'CONSCIOUSNESS',  color: 'cyan',    metaKey: null },
  { key: 'voice',         label: 'VOICE',          color: 'pink',    metaKey: null },
];

const COLOR_MAP = {
  yellow: { dot: 'bg-yellow-400', border: 'border-yellow-500/30', bg: 'bg-yellow-500/10', text: 'text-yellow-400' },
  orange: { dot: 'bg-orange-400', border: 'border-orange-500/30', bg: 'bg-orange-500/10', text: 'text-orange-400' },
  blue:   { dot: 'bg-blue-400',   border: 'border-blue-500/30',   bg: 'bg-blue-500/10',   text: 'text-blue-400' },
  purple: { dot: 'bg-purple-400', border: 'border-purple-500/30', bg: 'bg-purple-500/10', text: 'text-purple-400' },
  cyan:   { dot: 'bg-cyan-400',   border: 'border-cyan-500/30',   bg: 'bg-cyan-500/10',   text: 'text-cyan-400' },
  pink:   { dot: 'bg-pink-400',   border: 'border-pink-500/30',   bg: 'bg-pink-500/10',   text: 'text-pink-400' },
};

// Determine layer status from assembler metadata
function getLayerStatus(layer, meta) {
  if (!meta) return { active: false, detail: '–' };

  switch (layer.key) {
    case 'identity':
      return { active: true, detail: meta.identity_source || 'unknown' };
    case 'expression':
      // Expression is active if identity isn't fallback (engine was available)
      return { active: meta.identity_source !== 'fallback', detail: meta.identity_source !== 'fallback' ? 'active' : 'off' };
    case 'temporal':
      return { active: !!meta.temporal_injected, detail: meta.gap_category || 'off' };
    case 'memory':
      return { active: !!meta.memory_source, detail: meta.memory_source || 'none' };
    case 'consciousness':
      return { active: meta.identity_source !== 'fallback', detail: meta.identity_source !== 'fallback' ? 'active' : 'off' };
    case 'voice':
      return { active: !!meta.voice_injected, detail: meta.voice_injected ? 'active' : 'off' };
    default:
      return { active: false, detail: '–' };
  }
}

const PromptInspectorPanel = ({ isOpen, onClose }) => {
  const [promptData, setPromptData] = useState(null);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [showRaw, setShowRaw] = useState(false);

  const fetchPrompt = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/slash/prompt`);
      if (!res.ok) throw new Error('Failed to fetch prompt');
      const json = await res.json();
      setPromptData(json);
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Poll when open
  useEffect(() => {
    if (!isOpen) return;
    fetchPrompt();
    const interval = setInterval(fetchPrompt, 3000);
    return () => clearInterval(interval);
  }, [isOpen, fetchPrompt]);

  if (!isOpen) return null;

  const data = promptData?.data || {};
  const meta = data.assembler || null;
  const route = data.route_decision || 'unknown';
  const length = data.length || 0;
  const available = data.available;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <GlassCard className="w-full max-w-2xl max-h-[85vh] flex flex-col" padding="p-0" hover={false}>
        {/* Header */}
        <div className="flex-shrink-0 px-6 py-4 border-b border-kozmo-border flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-1 h-6 bg-gradient-to-b from-cyan-500 to-blue-500 rounded-full" style={{ boxShadow: '0 0 12px rgba(6,182,212,0.5), 0 0 4px rgba(6,182,212,0.8)' }} />
            <h2 className="text-lg font-display font-semibold tracking-tight text-white/90">Prompt Inspector</h2>
            {available && (
              <span className={`text-xs px-2 py-1 rounded border ${
                route === 'local'
                  ? 'bg-green-500/20 border-green-500/30 text-green-400'
                  : 'bg-blue-500/20 border-blue-500/30 text-blue-400'
              }`}>
                {route === 'local' ? '🏠 local' : '☁️ delegated'}
              </span>
            )}
          </div>
          <button onClick={onClose} className="text-kozmo-muted hover:text-white transition-colors text-xl">×</button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {error && (
            <div className="text-red-400 text-sm bg-red-500/10 border border-red-500/30 rounded px-3 py-2">
              {error}
            </div>
          )}

          {!available && !error && (
            <div className="text-kozmo-muted text-sm text-center py-8">
              No prompt available. Send a message first.
            </div>
          )}

          {available && (
            <>
              {/* Stats bar */}
              <div className="flex items-center gap-4 text-xs text-kozmo-muted">
                <span>{length.toLocaleString()} chars</span>
                {meta && (
                  <>
                    <span>~{meta.prompt_tokens} tokens</span>
                    {meta.parked_thread_count > 0 && (
                      <span className="text-orange-400">{meta.parked_thread_count} parked thread{meta.parked_thread_count !== 1 ? 's' : ''}</span>
                    )}
                  </>
                )}
              </div>

              {/* Layer Stack */}
              <div className="space-y-1.5">
                <div className="text-xs text-kozmo-muted uppercase tracking-wider mb-2">Assembly Layers</div>
                {LAYERS.map((layer, i) => {
                  const status = getLayerStatus(layer, meta);
                  const colors = COLOR_MAP[layer.color];
                  return (
                    <div
                      key={layer.key}
                      className={`flex items-center gap-3 px-3 py-2 rounded border ${
                        status.active
                          ? `${colors.bg} ${colors.border}`
                          : 'bg-white/[0.02] border-kozmo-border/50'
                      }`}
                    >
                      <span className="text-kozmo-muted text-xs w-4">{i + 1}.</span>
                      <div className={`w-2 h-2 rounded-full ${status.active ? colors.dot : 'bg-white/20'}`} />
                      <span className={`text-xs font-mono w-28 ${status.active ? colors.text : 'text-kozmo-muted/50'}`}>
                        {layer.label}
                      </span>
                      <span className={`text-xs ${status.active ? 'text-white/70' : 'text-kozmo-muted/40'}`}>
                        {status.detail}
                      </span>
                    </div>
                  );
                })}
              </div>

              {/* Raw prompt toggle */}
              <div>
                <button
                  onClick={() => setShowRaw(!showRaw)}
                  className="text-xs text-kozmo-muted hover:text-white transition-colors flex items-center gap-1"
                >
                  <span className="transform transition-transform" style={{ display: 'inline-block', transform: showRaw ? 'rotate(90deg)' : 'rotate(0deg)' }}>▶</span>
                  Raw Prompt
                </button>
                {showRaw && (
                  <pre className="mt-2 text-xs text-white/60 bg-black/40 border border-kozmo-border/50 rounded p-3 overflow-x-auto max-h-60 overflow-y-auto whitespace-pre-wrap break-words">
                    {data.full_prompt || data.preview || '(empty)'}
                  </pre>
                )}
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="flex-shrink-0 px-6 py-3 border-t border-kozmo-border flex items-center justify-between">
          <span className="text-xs text-kozmo-muted">
            {isLoading ? 'Refreshing...' : 'Polls every 3s'}
          </span>
          <button
            onClick={fetchPrompt}
            className="text-xs text-kozmo-muted hover:text-kozmo-accent transition-colors"
          >
            🔄
          </button>
        </div>
      </GlassCard>
    </div>
  );
};

export default PromptInspectorPanel;
