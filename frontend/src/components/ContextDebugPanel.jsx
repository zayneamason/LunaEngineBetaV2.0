import React, { useState, useEffect, useCallback } from 'react';
import GlassCard from './GlassCard';

const API_BASE = 'http://localhost:8000';

// Ring colors for visual distinction
const RING_COLORS = {
  CORE: { border: 'border-yellow-500', bg: 'bg-yellow-500/10', text: 'text-yellow-400' },
  INNER: { border: 'border-red-500', bg: 'bg-red-500/10', text: 'text-red-400' },
  MIDDLE: { border: 'border-orange-500', bg: 'bg-orange-500/10', text: 'text-orange-400' },
  OUTER: { border: 'border-gray-500', bg: 'bg-gray-500/10', text: 'text-gray-400' },
};

// Source icons
const SOURCE_ICONS = {
  IDENTITY: '🧬',
  CONVERSATION: '💬',
  MEMORY: '🧠',
  TOOL: '🔧',
  TASK: '📋',
  SCRIBE: '📝',
  LIBRARIAN: '📚',
};

const ContextDebugPanel = ({ isOpen, onClose, highlightKeywords = [] }) => {
  const [contextData, setContextData] = useState(null);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedRing, setSelectedRing] = useState('ALL');
  const [expandedItems, setExpandedItems] = useState(new Set());

  const fetchContext = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/debug/context`);
      if (!res.ok) throw new Error('Failed to fetch context');
      const data = await res.json();
      setContextData(data);
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Poll context data periodically when open
  useEffect(() => {
    if (!isOpen) return;

    fetchContext();
    const interval = setInterval(fetchContext, 2000);
    return () => clearInterval(interval);
  }, [isOpen, fetchContext]);

  const toggleItem = (id) => {
    setExpandedItems(prev => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  // Highlight keywords in text
  const highlightText = (text, keywords) => {
    if (!keywords || keywords.length === 0) return text;

    // Create regex pattern for all keywords
    const pattern = keywords.map(k => k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|');
    const regex = new RegExp(`(${pattern})`, 'gi');

    const parts = text.split(regex);
    return parts.map((part, i) => {
      const isKeyword = keywords.some(k => k.toLowerCase() === part.toLowerCase());
      if (isKeyword) {
        return (
          <span key={i} className="bg-cyan-500/40 text-cyan-200 px-1 rounded font-medium">
            {part}
          </span>
        );
      }
      return part;
    });
  };

  if (!isOpen) return null;

  const filteredItems = contextData?.items?.filter(item =>
    selectedRing === 'ALL' || item.ring === selectedRing
  ) || [];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <GlassCard className="w-full max-w-4xl max-h-[90vh] flex flex-col" padding="p-0" hover={false}>
        {/* Header */}
        <div className="flex-shrink-0 px-6 py-4 border-b border-white/10 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-1 h-6 bg-gradient-to-b from-red-500 to-orange-500 rounded-full" />
            <h2 className="text-lg font-light tracking-wide text-white/90">Context Debug</h2>
            <span className="text-xs text-white/40 bg-red-500/20 px-2 py-1 rounded border border-red-500/30">
              DEBUG MODE
            </span>
          </div>
          <button
            onClick={onClose}
            className="text-white/50 hover:text-white/90 transition-colors text-xl"
          >
            ×
          </button>
        </div>

        {/* Stats Bar */}
        {contextData && (
          <div className="flex-shrink-0 px-6 py-3 bg-white/5 border-b border-white/10 flex items-center gap-6 text-sm">
            <div>
              <span className="text-white/40">Turn:</span>{' '}
              <span className="text-white/90 font-mono">{contextData.current_turn}</span>
            </div>
            <div>
              <span className="text-white/40">Tokens:</span>{' '}
              <span className="text-white/90 font-mono">
                {contextData.total_tokens}/{contextData.token_budget}
              </span>
              <span className="text-white/30 ml-1">
                ({Math.round(contextData.total_tokens / contextData.token_budget * 100)}%)
              </span>
            </div>
            <div>
              <span className="text-white/40">Items:</span>{' '}
              <span className="text-white/90 font-mono">{contextData.items?.length || 0}</span>
            </div>
          </div>
        )}

        {/* Ring Filter */}
        <div className="flex-shrink-0 px-6 py-3 border-b border-white/10 flex items-center gap-2">
          <span className="text-white/40 text-sm mr-2">Ring:</span>
          {['ALL', 'CORE', 'INNER', 'MIDDLE', 'OUTER'].map(ring => (
            <button
              key={ring}
              onClick={() => setSelectedRing(ring)}
              className={`px-3 py-1 text-xs rounded-lg border transition-all ${
                selectedRing === ring
                  ? ring === 'ALL'
                    ? 'bg-white/10 border-white/30 text-white/90'
                    : `${RING_COLORS[ring]?.bg} ${RING_COLORS[ring]?.border} ${RING_COLORS[ring]?.text}`
                  : 'bg-transparent border-white/10 text-white/40 hover:border-white/20'
              }`}
            >
              {ring}
              {contextData?.ring_stats?.[ring] && (
                <span className="ml-1 opacity-60">({contextData.ring_stats[ring].count})</span>
              )}
            </button>
          ))}
        </div>

        {/* Keywords Bar */}
        {contextData?.keywords?.length > 0 && (
          <div className="flex-shrink-0 px-6 py-3 border-b border-white/10">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-white/40 text-sm mr-2">Keywords Luna knows:</span>
              {contextData.keywords.slice(0, 15).map(keyword => (
                <span
                  key={keyword}
                  className="bg-cyan-500/20 text-cyan-300 px-2 py-0.5 rounded text-xs border border-cyan-500/30"
                >
                  {keyword}
                </span>
              ))}
              {contextData.keywords.length > 15 && (
                <span className="text-white/30 text-xs">
                  +{contextData.keywords.length - 15} more
                </span>
              )}
            </div>
          </div>
        )}

        {/* Content */}
        <div className="flex-1 min-h-0 overflow-y-auto p-4 space-y-3">
          {isLoading && !contextData && (
            <div className="flex items-center justify-center h-32 text-white/40">
              Loading context...
            </div>
          )}

          {error && (
            <div className="p-4 rounded-xl bg-red-500/10 border border-red-400/30 text-red-300 text-sm">
              {error}
            </div>
          )}

          {filteredItems.length === 0 && !isLoading && (
            <div className="flex items-center justify-center h-32 text-white/40">
              No context items in {selectedRing === 'ALL' ? 'any ring' : `${selectedRing} ring`}
            </div>
          )}

          {filteredItems.map(item => {
            const ringStyle = RING_COLORS[item.ring] || RING_COLORS.OUTER;
            const isExpanded = expandedItems.has(item.id);
            const sourceIcon = SOURCE_ICONS[item.source] || '📄';

            return (
              <div
                key={item.id}
                className={`rounded-xl border-2 ${ringStyle.border} ${ringStyle.bg} overflow-hidden transition-all`}
              >
                {/* Item Header */}
                <div
                  onClick={() => toggleItem(item.id)}
                  className="px-4 py-3 cursor-pointer flex items-center justify-between hover:bg-white/5 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-lg">{sourceIcon}</span>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className={`text-xs font-medium ${ringStyle.text}`}>
                          {item.ring}
                        </span>
                        <span className="text-white/40 text-xs">•</span>
                        <span className="text-white/60 text-xs">{item.source}</span>
                      </div>
                      <div className="text-white/40 text-xs mt-0.5">
                        {item.tokens} tokens • rel: {item.relevance} • age: {item.age_turns}/{item.ttl_turns} turns
                        {item.is_expired && (
                          <span className="ml-2 text-red-400">(EXPIRED)</span>
                        )}
                      </div>
                    </div>
                  </div>
                  <span className="text-white/40 text-lg">
                    {isExpanded ? '−' : '+'}
                  </span>
                </div>

                {/* Item Content (expanded) */}
                {isExpanded && (
                  <div className="px-4 pb-4 pt-2 border-t border-white/10">
                    <pre className="text-sm text-white/80 whitespace-pre-wrap font-mono bg-black/20 p-3 rounded-lg overflow-x-auto">
                      {highlightText(item.content, contextData?.keywords || [])}
                    </pre>
                  </div>
                )}

                {/* Preview (collapsed) */}
                {!isExpanded && (
                  <div className="px-4 pb-3">
                    <p className="text-xs text-white/50 truncate">
                      {item.content.slice(0, 100)}...
                    </p>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Footer */}
        <div className="flex-shrink-0 px-6 py-3 border-t border-white/10 flex items-center justify-between text-xs text-white/40">
          <div>
            Red box = what Luna "sees" when generating a response
          </div>
          <button
            onClick={fetchContext}
            className="px-3 py-1 rounded bg-white/10 hover:bg-white/20 transition-colors text-white/60"
          >
            Refresh
          </button>
        </div>
      </GlassCard>
    </div>
  );
};

export default ContextDebugPanel;
