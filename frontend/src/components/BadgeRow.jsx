import React from 'react';

/**
 * BadgeRow — configurable badge strip below assistant messages.
 * Extracted from ChatPanel to support badge visibility toggling.
 */
export default function BadgeRow({ msg, badgeConfig, debugMode = true }) {
  if (!msg.model && !msg.delegated && !msg.local && !msg.fallback && !msg.accessDeniedCount && !msg.lunascript) {
    return null;
  }

  return (
    <div className="mt-2 flex items-center gap-3 text-xs">
      {/* Route indicator — debug only */}
      {debugMode && badgeConfig.route && (msg.delegated ? (
        <span className="flex items-center gap-1 text-fuchsia-400">
          <span>⚡</span>
          <span>delegated</span>
        </span>
      ) : msg.local ? (
        <span className="flex items-center gap-1 text-emerald-400">
          <span>●</span>
          <span>local</span>
        </span>
      ) : msg.fallback ? (
        <span className="flex items-center gap-1 text-amber-400">
          <span>☁</span>
          <span>cloud</span>
        </span>
      ) : null)}

      {debugMode && badgeConfig.model && msg.model && (
        <span className="text-kozmo-muted">{msg.model}</span>
      )}
      {debugMode && badgeConfig.tokens && msg.tokens && (
        <span className="text-kozmo-muted">{msg.tokens} tokens</span>
      )}
      {badgeConfig.latency && msg.latency && (
        <span className="text-kozmo-muted">{msg.latency}ms</span>
      )}
      {badgeConfig.access_filter && msg.accessDeniedCount > 0 && (
        <span className="flex items-center gap-1 text-amber-400/60">
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor"
            strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
            <path d="M7 11V7a5 5 0 0 1 10 0v4" />
          </svg>
          <span>{msg.accessDeniedCount} filtered</span>
        </span>
      )}
      {debugMode && badgeConfig.lunascript && msg.lunascript && (
        <>
          {msg.lunascript.glyph && (
            <span className="text-violet-400" title={msg.lunascript.position || ''}>
              {msg.lunascript.glyph}
            </span>
          )}
          {msg.lunascript.classification && (
            <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
              msg.lunascript.classification === 'RESONANCE' ? 'bg-emerald-500/15 text-emerald-400' :
              msg.lunascript.classification === 'DRIFT' ? 'bg-red-500/15 text-red-400' :
              msg.lunascript.classification === 'EXPANSION' ? 'bg-blue-500/15 text-blue-400' :
              msg.lunascript.classification === 'COMPRESSION' ? 'bg-amber-500/15 text-amber-400' :
              'bg-gray-500/15 text-gray-400'
            }`}>
              {msg.lunascript.classification}
            </span>
          )}
        </>
      )}
    </div>
  );
}
