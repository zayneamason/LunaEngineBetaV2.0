import React from 'react';
import { Handle, Position } from '@xyflow/react';
import { typeStyles, statusColors } from './pipelineData';

export default function EngineNode({ data, selected }) {
  const s = statusColors[data.status] || statusColors.idle;
  const t = typeStyles[data.nodeType] || typeStyles.process;
  const handleStyle = { background: t.accent, width: 7, height: 7, border: '2px solid #0a0a12' };
  const isBroken = data.status === 'broken';
  const qaFailing = data.qaStatus === 'failing';
  const qaWarning = data.qaStatus === 'warning';
  const qaActive = qaFailing || qaWarning;

  // Trace state
  const traceActive = data.traceActive;
  const traceFailed = data.traceFailed;
  const tracePassed = data.tracePassed;

  const borderColor = selected ? t.accent
    : traceFailed ? 'rgba(239,68,68,0.7)'
    : tracePassed ? 'rgba(34,197,94,0.6)'
    : traceActive ? 'rgba(6,182,212,0.5)'
    : qaFailing ? 'rgba(239,68,68,0.6)'
    : qaWarning ? 'rgba(245,158,11,0.5)'
    : isBroken ? 'rgba(239,68,68,0.5)'
    : 'rgba(255,255,255,0.06)';

  const animName = traceFailed ? 'pulse-qa-red 1.5s ease-in-out infinite'
    : traceActive ? 'pulse-trace 2s ease-in-out infinite'
    : qaFailing ? 'pulse-qa-red 1.5s ease-in-out infinite'
    : qaWarning ? 'pulse-qa-amber 2s ease-in-out infinite'
    : isBroken ? 'pulse-red 2s ease-in-out infinite'
    : undefined;

  const boxShadow = traceFailed ? '0 0 24px rgba(239,68,68,0.35)'
    : tracePassed ? '0 0 18px rgba(34,197,94,0.25)'
    : traceActive ? '0 0 20px rgba(6,182,212,0.2)'
    : qaFailing ? '0 0 24px rgba(239,68,68,0.3)'
    : qaWarning ? '0 0 18px rgba(245,158,11,0.2)'
    : isBroken ? `0 0 24px ${s.glow}`
    : selected ? `0 0 20px ${t.accent}33` : '0 2px 12px rgba(0,0,0,0.3)';

  return (
    <div style={{
      background: t.bg,
      borderRadius: 10,
      padding: '12px 16px',
      minWidth: 170,
      maxWidth: 240,
      border: `2px solid ${borderColor}`,
      boxShadow,
      fontFamily: "'JetBrains Mono', monospace",
      cursor: 'grab',
      animation: animName,
      position: 'relative',
    }}>
      <Handle type="target" position={Position.Left} style={handleStyle} />
      <Handle type="source" position={Position.Right} style={handleStyle} />
      <Handle type="target" position={Position.Top} id="top" style={handleStyle} />
      <Handle type="source" position={Position.Bottom} id="bottom" style={handleStyle} />

      {/* Trace phase badge */}
      {traceActive && data.tracePhase && (
        <div style={{
          position: 'absolute', top: -8, left: -8,
          width: 20, height: 20, borderRadius: '50%',
          background: traceFailed ? '#ef4444' : tracePassed ? '#22c55e' : '#06b6d4',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 11, color: '#fff', fontWeight: 700,
          boxShadow: `0 0 8px ${traceFailed ? 'rgba(239,68,68,0.5)' : tracePassed ? 'rgba(34,197,94,0.4)' : 'rgba(6,182,212,0.4)'}`,
          border: '2px solid #0a0a12',
          zIndex: 5,
        }}>{data.tracePhase}</div>
      )}

      {/* QA failure badge */}
      {qaActive && data.qaFailures && !traceActive && (
        <div style={{
          position: 'absolute', top: -6, right: -6,
          width: 18, height: 18, borderRadius: '50%',
          background: qaFailing ? '#ef4444' : '#f59e0b',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 9, fontWeight: 700, color: '#fff',
          boxShadow: `0 0 8px ${qaFailing ? 'rgba(239,68,68,0.5)' : 'rgba(245,158,11,0.4)'}`,
          border: '2px solid #0a0a12',
        }}>{data.qaFailures.length}</div>
      )}

      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
        <div style={{
          width: 7, height: 7, borderRadius: '50%', flexShrink: 0,
          background: traceFailed ? '#ef4444' : tracePassed ? '#22c55e' : traceActive ? '#06b6d4'
            : qaFailing ? '#ef4444' : qaWarning ? '#f59e0b' : s.dot,
          boxShadow: traceActive || data.status !== 'idle' || qaActive
            ? `0 0 6px ${traceFailed ? 'rgba(239,68,68,0.5)' : traceActive ? 'rgba(6,182,212,0.4)'
              : qaFailing ? 'rgba(239,68,68,0.5)' : qaWarning ? 'rgba(245,158,11,0.4)' : s.glow}` : 'none',
          animation: traceFailed ? 'pulse-red 1s ease-in-out infinite'
            : traceActive ? 'pulse-trace-dot 1.5s ease-in-out infinite'
            : qaFailing ? 'pulse-red 1s ease-in-out infinite'
            : data.status === 'live' ? 'pulse-green 2.5s ease-in-out infinite'
            : data.status === 'broken' ? 'pulse-red 1s ease-in-out infinite'
            : data.status === 'warn' ? 'pulse-warn 2s ease-in-out infinite' : 'none',
        }} />
        <div style={{
          width: 24, height: 24, borderRadius: 5,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: t.iconBg, fontSize: 13, flexShrink: 0,
        }}>{data.icon}</div>
        <div style={{
          fontSize: 10.5, fontWeight: 600, textTransform: 'uppercase',
          letterSpacing: '0.4px',
          color: traceFailed ? '#f87171' : tracePassed ? '#4ade80' : traceActive ? '#06b6d4'
            : qaFailing ? '#f87171' : t.accent,
          lineHeight: 1.2,
        }}>{data.label}</div>
      </div>

      <div style={{
        fontSize: 10, color: '#777790', lineHeight: 1.55, whiteSpace: 'pre-line',
      }}>{data.body}</div>

      {/* Inline QA failure lines (max 2) */}
      {qaActive && data.qaFailures && !traceActive && data.qaFailures.slice(0, 2).map((f, i) => (
        <div key={i} style={{
          fontSize: 9, color: f.severity === 'high' ? '#f87171' : '#f59e0b',
          marginTop: i === 0 ? 4 : 1, lineHeight: 1.3,
        }}>⛔ {f.name || f.id}</div>
      ))}
    </div>
  );
}
