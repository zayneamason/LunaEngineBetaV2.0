import React from 'react';
import { Handle, Position } from '@xyflow/react';
import { typeStyles, statusColors } from './data';

export default function EngineNode({ data, selected }) {
  const s = statusColors[data.status] || statusColors.idle;
  const t = typeStyles[data.nodeType] || typeStyles.process;
  const handleStyle = { background: t.accent, width: 7, height: 7, border: '2px solid #0a0a12' };
  const isBroken = data.status === 'broken';

  return (
    <div style={{
      background: t.bg,
      borderRadius: 10,
      padding: '12px 16px',
      minWidth: 170,
      maxWidth: 240,
      border: `1px solid ${selected ? t.accent : isBroken ? 'rgba(239,68,68,0.5)' : 'rgba(255,255,255,0.06)'}`,
      boxShadow: isBroken
        ? `0 0 24px ${s.glow}`
        : selected ? `0 0 20px ${t.accent}33` : '0 2px 12px rgba(0,0,0,0.3)',
      fontFamily: "'JetBrains Mono', monospace",
      cursor: 'grab',
      animation: isBroken ? 'pulse-red 2s ease-in-out infinite' : undefined,
    }}>
      <Handle type="target" position={Position.Left} style={handleStyle} />
      <Handle type="source" position={Position.Right} style={handleStyle} />
      <Handle type="target" position={Position.Top} id="top" style={handleStyle} />
      <Handle type="source" position={Position.Bottom} id="bottom" style={handleStyle} />

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
        <div style={{
          width: 7, height: 7, borderRadius: '50%', flexShrink: 0,
          background: s.dot,
          boxShadow: data.status !== 'idle' ? `0 0 6px ${s.glow}` : 'none',
          animation: data.status === 'live' ? 'pulse-green 2.5s ease-in-out infinite'
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
          letterSpacing: '0.4px', color: t.accent, lineHeight: 1.2,
        }}>{data.label}</div>
      </div>

      {/* Body */}
      <div style={{
        fontSize: 10, color: '#777790', lineHeight: 1.55, whiteSpace: 'pre-line',
      }}>{data.body}</div>
    </div>
  );
}
