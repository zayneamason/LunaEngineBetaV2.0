/**
 * GroundingOverlay -- Verification UI (Phase 3)
 *
 * Renders inline grounding indicators on Luna's responses.
 * Each sentence gets color-coded by confidence level when
 * verification mode is enabled.
 *
 * When verification mode is OFF, text renders normally.
 */

import React, { useState } from 'react';
import AnnotatedText from './AnnotatedText';
import MarkdownRenderer from './MarkdownRenderer';

// Grounding confidence level styles (subtle left-border)
const LEVEL_STYLES = {
  GROUNDED: {
    borderLeft: '2px solid rgba(74, 222, 128, 0.4)',
    background: 'rgba(74, 222, 128, 0.03)',
  },
  INFERRED: {
    borderLeft: '2px solid rgba(251, 191, 36, 0.3)',
    background: 'rgba(251, 191, 36, 0.02)',
  },
  UNGROUNDED: {
    borderLeft: '2px solid rgba(248, 113, 113, 0.3)',
    background: 'rgba(248, 113, 113, 0.02)',
  },
};

const LEVEL_COLORS = {
  GROUNDED: '#4ade80',
  INFERRED: '#fbbf24',
  UNGROUNDED: '#f87171',
};

/**
 * Tooltip shown on hover over a grounded sentence.
 */
const GroundingTooltip = ({ support, style }) => (
  <div
    style={{
      position: 'absolute',
      bottom: '100%',
      left: 0,
      marginBottom: 4,
      padding: '3px 8px',
      borderRadius: 4,
      background: 'rgba(20, 20, 30, 0.95)',
      border: '1px solid rgba(255,255,255,0.08)',
      fontSize: 10,
      color: LEVEL_COLORS[support.level] || '#888',
      whiteSpace: 'nowrap',
      pointerEvents: 'none',
      zIndex: 100,
      ...style,
    }}
  >
    {support.node_id || 'no source'} &middot; {Math.round(support.confidence * 100)}%
  </div>
);

/**
 * Expanded detail panel for a clicked sentence.
 */
const GroundingDetail = ({ support, onClose }) => (
  <div
    style={{
      marginTop: 4,
      marginBottom: 4,
      padding: '8px 10px',
      borderRadius: 4,
      background: 'rgba(20, 20, 30, 0.9)',
      border: '1px solid rgba(255,255,255,0.06)',
      fontSize: 11,
      lineHeight: 1.5,
    }}
  >
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
      <span style={{ color: LEVEL_COLORS[support.level], fontWeight: 600 }}>
        {support.level}
      </span>
      <button
        onClick={(e) => { e.stopPropagation(); onClose(); }}
        style={{
          background: 'none', border: 'none', color: '#5a5a70',
          cursor: 'pointer', fontSize: 12, padding: '0 2px',
        }}
      >
        x
      </button>
    </div>
    <div style={{ color: 'rgba(255,255,255,0.5)', marginBottom: 2 }}>
      <span style={{ color: 'rgba(255,255,255,0.7)' }}>Node:</span>{' '}
      {support.node_id || 'none'}
      {support.node_type && <span> ({support.node_type})</span>}
    </div>
    {support.source && (
      <div style={{ color: 'rgba(255,255,255,0.5)', marginBottom: 2 }}>
        <span style={{ color: 'rgba(255,255,255,0.7)' }}>Source:</span>{' '}
        {support.doc_title || support.source}
        {support.doc_title && <span style={{ opacity: 0.5 }}> ({support.source})</span>}
      </div>
    )}
    <div style={{ color: 'rgba(255,255,255,0.5)', marginBottom: 2 }}>
      <span style={{ color: 'rgba(255,255,255,0.7)' }}>Confidence:</span>{' '}
      {Math.round(support.confidence * 100)}%
    </div>
    {support.node_preview && (
      <div style={{ color: 'rgba(255,255,255,0.4)', fontStyle: 'italic', marginTop: 4 }}>
        {support.node_preview}
      </div>
    )}
  </div>
);

/**
 * Summary badge showing grounding breakdown.
 */
const GroundingSummary = ({ summary }) => {
  if (!summary) return null;
  return (
    <div
      style={{
        marginTop: 6,
        padding: '3px 8px',
        borderRadius: 3,
        border: '1px solid rgba(255,255,255,0.06)',
        background: 'rgba(255,255,255,0.02)',
        fontSize: 10,
        color: 'rgba(255,255,255,0.4)',
        display: 'inline-flex',
        gap: 8,
      }}
    >
      <span style={{ color: LEVEL_COLORS.GROUNDED }}>{summary.grounded} grounded</span>
      <span>&middot;</span>
      <span style={{ color: LEVEL_COLORS.INFERRED }}>{summary.inferred} inferred</span>
      <span>&middot;</span>
      <span style={{ color: LEVEL_COLORS.UNGROUNDED }}>{summary.ungrounded} ungrounded</span>
      <span>&middot;</span>
      <span>avg {(summary.avg_confidence || 0).toFixed(2)}</span>
    </div>
  );
};

/**
 * Source attribution badges — shows which collections/documents were used.
 */
const SourceBadges = ({ sources }) => {
  if (!sources || sources.length === 0) return null;
  return (
    <div style={{ marginTop: 4, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
      {sources.map((s, i) => (
        <span
          key={i}
          style={{
            padding: '2px 6px',
            borderRadius: 3,
            fontSize: 10,
            background: s.source?.startsWith('nexus/')
              ? 'rgba(96, 165, 250, 0.1)'
              : 'rgba(168, 85, 247, 0.1)',
            border: s.source?.startsWith('nexus/')
              ? '1px solid rgba(96, 165, 250, 0.3)'
              : '1px solid rgba(168, 85, 247, 0.3)',
            color: s.source?.startsWith('nexus/') ? '#60a5fa' : '#a855f7',
          }}
        >
          {s.doc_title || s.source?.replace('nexus/', '') || 'unknown'}
          {s.grounded_count > 0 && (
            <span style={{ opacity: 0.6, marginLeft: 3 }}>
              ({s.grounded_count})
            </span>
          )}
        </span>
      ))}
    </div>
  );
};

/**
 * Main component: wraps response text with grounding indicators.
 */
const GroundingOverlay = ({
  text,
  groundingMetadata,
  verificationMode,
  entities,
  onEntityClick,
  debugMode = true,
}) => {
  const [hoveredIdx, setHoveredIdx] = useState(null);
  const [expandedIdx, setExpandedIdx] = useState(null);

  // When no metadata available, render with markdown + entity highlighting
  if (!groundingMetadata || !groundingMetadata.supports) {
    return <MarkdownRenderer entities={entities} onEntityClick={onEntityClick}>{text}</MarkdownRenderer>;
  }

  // When verification mode is off, show markdown-rendered text with subtle summary badge
  if (!verificationMode) {
    return (
      <div>
        <MarkdownRenderer entities={entities} onEntityClick={onEntityClick}>{text}</MarkdownRenderer>
        {debugMode && <GroundingSummary summary={groundingMetadata.summary} />}
        {debugMode && <SourceBadges sources={groundingMetadata.sources_used} />}
      </div>
    );
  }

  const { supports, summary } = groundingMetadata;

  // Build a map of sentence_index -> support
  const supportMap = {};
  for (const s of supports) {
    supportMap[s.sentence_index] = s;
  }

  // Split text into sentences matching the supports
  // Use a simple split that matches the backend's splitting
  const sentences = text.split(/(?<=[.!?])\s+/).filter(s => s.trim().length > 0);

  return (
    <div>
      {sentences.map((sentence, idx) => {
        const support = supportMap[idx];
        const level = support?.level || 'UNGROUNDED';
        const style = LEVEL_STYLES[level] || {};
        const isHovered = hoveredIdx === idx;
        const isExpanded = expandedIdx === idx;

        return (
          <React.Fragment key={idx}>
            <span
              style={{
                position: 'relative',
                display: 'inline',
                paddingLeft: 6,
                marginRight: 2,
                cursor: support ? 'pointer' : 'default',
                transition: 'background 0.15s ease',
                ...style,
                ...(isHovered ? { background: `${style.background || ''}`.replace('0.0', '0.0') } : {}),
              }}
              onMouseEnter={() => support && setHoveredIdx(idx)}
              onMouseLeave={() => setHoveredIdx(null)}
              onClick={() => {
                if (support) {
                  setExpandedIdx(isExpanded ? null : idx);
                }
              }}
            >
              {isHovered && support && !isExpanded && (
                <GroundingTooltip support={support} />
              )}
              <AnnotatedText text={sentence} entities={entities} onEntityClick={onEntityClick} />
            </span>
            {' '}
            {isExpanded && support && (
              <GroundingDetail
                support={support}
                onClose={() => setExpandedIdx(null)}
              />
            )}
          </React.Fragment>
        );
      })}

      {/* Summary badge */}
      <div style={{ marginTop: 4 }}>
        <GroundingSummary summary={summary} />
        <SourceBadges sources={groundingMetadata.sources_used} />
      </div>
    </div>
  );
};

/**
 * Toggle button for verification mode.
 */
export const VerificationToggle = ({ enabled, onChange }) => (
  <button
    onClick={() => onChange(!enabled)}
    style={{
      padding: '4px 8px',
      borderRadius: 4,
      border: enabled
        ? '1px solid rgba(74, 222, 128, 0.4)'
        : '1px solid rgba(255,255,255,0.06)',
      background: enabled
        ? 'rgba(74, 222, 128, 0.1)'
        : 'rgba(255,255,255,0.03)',
      color: enabled ? '#4ade80' : '#5a5a70',
      fontSize: 11,
      cursor: 'pointer',
      transition: 'all 0.2s ease',
    }}
  >
    {enabled ? '\u2713 Verified' : '\u25CE Verify'}
  </button>
);

/**
 * Toggle button for Luna help mode.
 * ON:  Widens aperture, adds luna_system to active collections + help focus tags.
 * OFF: Restores previous aperture state.
 */
export const HelpToggle = ({ enabled, onChange }) => {
  const prevState = React.useRef(null);

  const toggle = async () => {
    if (!enabled) {
      // Save current aperture state before switching
      try {
        const res = await fetch('/api/aperture');
        if (res.ok) prevState.current = await res.json();
      } catch {}
      // Activate help mode
      try {
        await fetch('/api/aperture', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            preset: 'WIDE',
            focus_tags: ['system', 'help', 'features', 'navigation', 'settings', 'troubleshooting'],
            active_collection_keys: ['luna_system'],
          }),
        });
      } catch {}
      onChange(true);
    } else {
      // Restore previous state
      if (prevState.current) {
        try {
          await fetch('/api/aperture', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              preset: prevState.current.preset || 'BALANCED',
              focus_tags: prevState.current.focus_tags || [],
              active_collection_keys: prevState.current.active_collection_keys || [],
            }),
          });
        } catch {}
        prevState.current = null;
      } else {
        try { await fetch('/api/aperture/reset', { method: 'POST' }); } catch {}
      }
      onChange(false);
    }
  };

  return (
    <button
      onClick={toggle}
      style={{
        padding: '4px 8px',
        borderRadius: 4,
        border: enabled
          ? '1px solid rgba(96, 165, 250, 0.4)'
          : '1px solid rgba(255,255,255,0.06)',
        background: enabled
          ? 'rgba(96, 165, 250, 0.1)'
          : 'rgba(255,255,255,0.03)',
        color: enabled ? '#60a5fa' : '#5a5a70',
        fontSize: 11,
        cursor: 'pointer',
        transition: 'all 0.2s ease',
      }}
    >
      {enabled ? '\u2713 Help Mode' : '? Help'}
    </button>
  );
};

export default GroundingOverlay;
