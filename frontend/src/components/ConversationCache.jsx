import React, { useState, useEffect, useCallback } from 'react';
import GlassCard from './GlassCard';

const API_BASE = 'http://localhost:8000';

/**
 * ConversationCache - Shows the 20 turns Luna remembers
 *
 * This displays Luna's actual conversation memory - what she sees when
 * generating responses. Different from the UI's localStorage chat history.
 */
const ConversationCache = ({ isConnected }) => {
  const [cache, setCache] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [isExpanded, setIsExpanded] = useState(false);

  const fetchCache = useCallback(async () => {
    if (!isConnected) return;

    setIsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/debug/conversation-cache`);
      if (!res.ok) throw new Error('Failed to fetch conversation cache');
      const data = await res.json();
      setCache(data);
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setIsLoading(false);
    }
  }, [isConnected]);

  // Poll for updates
  useEffect(() => {
    if (!isConnected) {
      setCache(null);
      return;
    }

    fetchCache();
    const interval = setInterval(fetchCache, 2000);
    return () => clearInterval(interval);
  }, [isConnected, fetchCache]);

  if (!isConnected) {
    return null;
  }

  const itemCount = cache?.items?.length || 0;
  const maxTurns = cache?.max_turns || 20;
  const usagePercent = Math.round((itemCount / (maxTurns * 2)) * 100); // *2 for user+assistant per turn

  return (
    <GlassCard className="transition-all duration-300" padding="p-0" hover={false}>
      {/* Header - Always visible */}
      <div
        onClick={() => setIsExpanded(!isExpanded)}
        className="px-4 py-3 cursor-pointer flex items-center justify-between hover:bg-white/5 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="w-1 h-6 bg-gradient-to-b from-cyan-400 to-emerald-400 rounded-full" />
          <div>
            <h3 className="text-sm font-medium text-white/80">Conversation Cache</h3>
            <p className="text-xs text-white/40">
              {itemCount} messages Luna remembers
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Turn counter */}
          <div className="text-xs text-white/40">
            Turn {cache?.current_turn || 0}
          </div>

          {/* Usage bar */}
          <div className="w-16 h-1.5 bg-white/10 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-cyan-400 to-emerald-400 transition-all duration-500"
              style={{ width: `${Math.min(usagePercent, 100)}%` }}
            />
          </div>

          {/* Expand/collapse */}
          <span className="text-white/40 text-sm">
            {isExpanded ? '−' : '+'}
          </span>
        </div>
      </div>

      {/* Expanded content */}
      {isExpanded && (
        <div className="border-t border-white/10">
          {/* Stats bar */}
          <div className="px-4 py-2 bg-white/5 flex items-center gap-4 text-xs">
            <div>
              <span className="text-white/40">Messages:</span>{' '}
              <span className="text-white/80 font-mono">{itemCount}</span>
            </div>
            <div>
              <span className="text-white/40">Tokens:</span>{' '}
              <span className="text-white/80 font-mono">{cache?.total_tokens || 0}</span>
            </div>
            <div>
              <span className="text-white/40">Max turns:</span>{' '}
              <span className="text-white/80 font-mono">{maxTurns}</span>
            </div>
          </div>

          {/* Message list */}
          <div className="max-h-64 overflow-y-auto p-3 space-y-2">
            {error && (
              <div className="text-red-400 text-xs p-2 bg-red-500/10 rounded">
                {error}
              </div>
            )}

            {itemCount === 0 && !isLoading && !error && (
              <div className="text-white/30 text-xs text-center py-4">
                No conversation in cache yet
              </div>
            )}

            {cache?.items?.map((item, i) => (
              <div
                key={i}
                className={`rounded-lg px-3 py-2 text-xs ${
                  item.role === 'user'
                    ? 'bg-violet-500/10 border border-violet-400/20 ml-4'
                    : 'bg-emerald-500/10 border border-emerald-400/20 mr-4'
                }`}
              >
                {/* Message header */}
                <div className="flex items-center justify-between mb-1">
                  <span className={`font-medium ${
                    item.role === 'user' ? 'text-violet-400' : 'text-emerald-400'
                  }`}>
                    {item.role === 'user' ? 'You' : 'Luna'}
                  </span>
                  <span className="text-white/30">
                    T{item.turn} • {Math.round(item.relevance * 100)}%
                  </span>
                </div>

                {/* Message content - truncated */}
                <p className="text-white/70 line-clamp-2">
                  {item.content}
                </p>

                {/* Age indicator */}
                {item.age_turns > 0 && (
                  <div className="mt-1 text-white/20">
                    {item.age_turns} turn{item.age_turns !== 1 ? 's' : ''} ago
                  </div>
                )}
              </div>
            ))}

            {isLoading && itemCount === 0 && (
              <div className="flex justify-center py-4">
                <div className="flex items-center gap-2 text-white/40 text-xs">
                  <div className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
                  Loading...
                </div>
              </div>
            )}
          </div>

          {/* Footer hint */}
          <div className="px-4 py-2 border-t border-white/10 text-xs text-white/30">
            This is what Luna "remembers" when responding - older messages expire after {maxTurns} turns
          </div>
        </div>
      )}
    </GlassCard>
  );
};

export default ConversationCache;
