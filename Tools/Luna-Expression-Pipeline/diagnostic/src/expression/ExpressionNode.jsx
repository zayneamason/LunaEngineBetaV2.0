import React from 'react';
import { Handle, Position } from '@xyflow/react';
import { TYPES } from './expressionData';

function Slider({ f, accent, onChange }) {
  const mn = f.min ?? 0, mx = f.max ?? 1;
  const pct = Math.max(0, Math.min(100, ((f.value - mn) / (mx - mn)) * 100));
  return (
    <div style={{ marginBottom: 5 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9, color: '#666', marginBottom: 1 }}>
        <span>{f.label}</span>
        <span style={{ color: accent, minWidth: 32, textAlign: 'right' }}>
          {typeof f.value === 'number' ? f.value.toFixed(2) : f.value}
        </span>
      </div>
      <div style={{ position: 'relative', height: 5, background: 'rgba(255,255,255,0.04)', borderRadius: 3 }}>
        <div style={{
          position: 'absolute', left: 0, top: 0, height: '100%', borderRadius: 3,
          width: `${pct}%`, background: `linear-gradient(90deg, ${accent}44, ${accent})`, transition: 'width 0.4s ease',
        }} />
        <input type="range" min={mn} max={mx} step={0.01} value={f.value}
          onChange={e => onChange(parseFloat(e.target.value))}
          onPointerDown={e => e.stopPropagation()}
          style={{ position: 'absolute', top: -4, left: 0, width: '100%', height: 14, opacity: 0, cursor: 'pointer', margin: 0 }}
        />
      </div>
    </div>
  );
}

export default function ExpressionNode({ data, selected }) {
  const t = TYPES[data.nodeType] || TYPES.dimension;
  const lit = data.lit;
  const handleStyle = { background: t.accent, width: 6, height: 6, border: '2px solid #0a0a12' };

  return (
    <div style={{
      background: t.bg,
      borderRadius: 10,
      padding: '8px 11px',
      minWidth: 200,
      maxWidth: 220,
      border: `1px solid ${lit ? t.accent : selected ? t.accent + '77' : 'rgba(255,255,255,0.06)'}`,
      boxShadow: lit ? `0 0 28px ${t.glow}, 0 0 56px ${t.glow}` : selected ? `0 0 18px ${t.glow}` : '0 2px 10px rgba(0,0,0,0.4)',
      fontFamily: "'JetBrains Mono', monospace",
      cursor: 'grab',
      transition: 'box-shadow 0.4s, border-color 0.4s',
      position: 'relative',
    }}>
      <Handle type="target" position={Position.Left} style={handleStyle} />
      <Handle type="source" position={Position.Right} style={handleStyle} />

      {lit && <div style={{
        position: 'absolute', inset: -1, borderRadius: 10, pointerEvents: 'none',
        background: `${t.accent}08`, animation: 'nflash 0.6s ease-out',
      }} />}

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 6 }}>
        <span style={{ fontSize: 11 }}>{data.icon}</span>
        <span style={{ fontSize: 9, fontWeight: 600, color: t.accent, textTransform: 'uppercase', letterSpacing: '0.4px' }}>
          {data.label}
        </span>
        <span style={{
          marginLeft: 'auto', fontSize: 7, padding: '1px 4px', borderRadius: 3,
          background: `${t.accent}12`, color: `${t.accent}88`, border: `1px solid ${t.accent}18`,
        }}>{t.label}</span>
      </div>

      {/* Fields */}
      {(data.fields || []).map(f => {
        if (f.type === 'slider') {
          return <Slider key={f.key} f={f} accent={t.accent} onChange={v => data.onChange?.(data.nodeId, f.key, v)} />;
        }
        if (f.type === 'toggle') {
          return (
            <div key={f.key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
              <span style={{ fontSize: 9, color: '#666' }}>{f.label}</span>
              <div
                onClick={e => { e.stopPropagation(); data.onChange?.(data.nodeId, f.key, !f.value); }}
                style={{
                  width: 26, height: 13, borderRadius: 7, cursor: 'pointer', position: 'relative',
                  background: f.value ? t.accent : 'rgba(255,255,255,0.08)', transition: 'background 0.2s',
                }}>
                <div style={{
                  width: 9, height: 9, borderRadius: 5, background: '#fff',
                  position: 'absolute', top: 2, left: f.value ? 15 : 2, transition: 'left 0.2s',
                }} />
              </div>
            </div>
          );
        }
        if (f.type === 'select') {
          return (
            <div key={f.key} style={{ marginBottom: 4 }}>
              <div style={{ fontSize: 9, color: '#666', marginBottom: 1 }}>{f.label}</div>
              <select value={f.value}
                onChange={e => { e.stopPropagation(); data.onChange?.(data.nodeId, f.key, e.target.value); }}
                onPointerDown={e => e.stopPropagation()}
                style={{
                  width: '100%', fontSize: 9, padding: '2px 3px', borderRadius: 3,
                  background: 'rgba(255,255,255,0.04)', color: '#aaa',
                  border: '1px solid rgba(255,255,255,0.08)', outline: 'none',
                }}>
                {(f.options || []).map(o => <option key={o} value={o}>{o}</option>)}
              </select>
            </div>
          );
        }
        if (f.type === 'readonly') {
          const val = String(f.value);
          const isOn = val.startsWith('✅') || val.startsWith('⚡') || val.startsWith('✨');
          const isWarn = val.startsWith('⚠');
          return (
            <div key={f.key} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
              <span style={{ fontSize: 9, color: '#555' }}>{f.label}</span>
              <span style={{
                fontSize: 9,
                color: val === '—' ? '#444' : isOn ? '#4ade80' : isWarn ? '#fbbf24' : '#a78bfa',
                maxWidth: 110, textAlign: 'right', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>{val}</span>
            </div>
          );
        }
        return null;
      })}
    </div>
  );
}
