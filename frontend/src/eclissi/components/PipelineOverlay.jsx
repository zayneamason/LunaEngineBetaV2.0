import React, { useMemo } from 'react';

/**
 * Assertion category metadata — color + label.
 */
const CATEGORY_META = {
  personality: { color: '#a78bfa', label: 'Personality' },
  structural:  { color: '#38bdf8', label: 'Structural' },
  voice:       { color: '#facc15', label: 'Voice' },
  flow:        { color: '#4ade80', label: 'Flow' },
  integration: { color: '#fb923c', label: 'Integration' },
  relationship:{ color: '#ec4899', label: 'Relationship' },
};

const SEVERITY_ICON = { critical: '!!', high: '!', medium: '~', low: '·' };

/**
 * Single pipeline node — represents one assertion result.
 */
function PipelineNode({ assertion, compact }) {
  const cat = CATEGORY_META[assertion.category] || { color: '#666', label: '?' };
  const passed = assertion.passed;

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: compact ? '4px 8px' : '6px 10px',
        borderRadius: 6,
        background: passed ? 'rgba(34,197,94,0.06)' : 'rgba(248,113,113,0.08)',
        border: `1px solid ${passed ? 'rgba(34,197,94,0.15)' : 'rgba(248,113,113,0.2)'}`,
        transition: 'all 0.2s ease',
      }}
    >
      {/* Status dot */}
      <div style={{
        width: 8, height: 8, borderRadius: '50%',
        background: passed ? '#22c55e' : '#f87171',
        flexShrink: 0,
      }} />

      {/* ID badge */}
      <span style={{
        fontSize: 10, fontWeight: 700, color: cat.color,
        background: `${cat.color}15`, padding: '1px 5px', borderRadius: 3,
        letterSpacing: 0.5,
      }}>
        {assertion.id}
      </span>

      {/* Name */}
      <span style={{
        fontSize: 11, color: passed ? '#9ca3af' : '#e5e7eb',
        flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
      }}>
        {assertion.name}
      </span>

      {/* Severity */}
      {!passed && (
        <span style={{
          fontSize: 9, color: assertion.severity === 'critical' ? '#f87171' : '#fb923c',
          fontWeight: 600,
        }}>
          {SEVERITY_ICON[assertion.severity] || ''}
        </span>
      )}
    </div>
  );
}

/**
 * PipelineOverlay — visualizes the assertion pipeline as categorized node groups.
 *
 * Props:
 *   report  — validation_end data from WebSocket (or null)
 *   compact — boolean, use compact spacing
 */
export default function PipelineOverlay({ report, compact = false }) {
  // Group assertions by category
  const groups = useMemo(() => {
    if (!report?.assertions) return [];
    const map = {};
    for (const a of report.assertions) {
      const cat = a.category || 'other';
      if (!map[cat]) map[cat] = [];
      map[cat].push(a);
    }
    // Sort: failed categories first
    return Object.entries(map).sort((a, b) => {
      const aFail = a[1].some(x => !x.passed);
      const bFail = b[1].some(x => !x.passed);
      return bFail - aFail;
    });
  }, [report]);

  if (!report) {
    return (
      <div style={{ color: 'var(--ec-text-faint)', fontSize: 11, textAlign: 'center', padding: 16 }}>
        No pipeline data yet
      </div>
    );
  }

  const total = report.total || report.assertions?.length || 0;
  const failed = report.failed_count || 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: compact ? 8 : 12 }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span className="ec-font-label" style={{ fontSize: 9, color: 'var(--ec-text-faint)' }}>
          PIPELINE {report.inference_id ? `· ${report.inference_id}` : ''}
        </span>
        <span style={{
          fontSize: 10, fontWeight: 600,
          color: failed === 0 ? '#22c55e' : '#f87171',
        }}>
          {failed === 0 ? `${total} PASS` : `${failed}/${total} FAIL`}
        </span>
      </div>

      {/* Category groups */}
      {groups.map(([category, assertions]) => {
        const meta = CATEGORY_META[category] || { color: '#666', label: category };
        const groupFailed = assertions.filter(a => !a.passed).length;

        return (
          <div key={category}>
            {/* Category header */}
            <div style={{
              display: 'flex', alignItems: 'center', gap: 6,
              marginBottom: 4,
            }}>
              <div style={{ width: 3, height: 12, borderRadius: 2, background: meta.color }} />
              <span style={{ fontSize: 9, color: meta.color, fontWeight: 600, letterSpacing: 0.8 }}>
                {meta.label.toUpperCase()}
              </span>
              {groupFailed > 0 && (
                <span style={{ fontSize: 9, color: '#f87171' }}>
                  ({groupFailed} failed)
                </span>
              )}
            </div>

            {/* Assertion nodes */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 3, paddingLeft: 9 }}>
              {assertions.map(a => (
                <PipelineNode key={a.id} assertion={a} compact={compact} />
              ))}
            </div>
          </div>
        );
      })}

      {/* Diagnosis */}
      {report.diagnosis && (
        <div style={{
          fontSize: 10, color: 'var(--ec-accent-qa)', lineHeight: 1.4,
          padding: '8px 10px', borderRadius: 6,
          background: 'rgba(248,113,113,0.06)',
          border: '1px solid rgba(248,113,113,0.12)',
          marginTop: 4,
        }}>
          {report.diagnosis}
        </div>
      )}
    </div>
  );
}
