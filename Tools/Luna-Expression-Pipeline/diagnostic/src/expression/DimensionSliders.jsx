import React from 'react';

const DIMS = [
  { key: 'd_val', label: 'Valence', icon: '☀️', min: -1, max: 1, color: '#a78bfa' },
  { key: 'd_aro', label: 'Arousal', icon: '🔥', min: 0, max: 1, color: '#fb7185' },
  { key: 'd_cert', label: 'Certainty', icon: '🎯', min: 0, max: 1, color: '#38bdf8' },
  { key: 'd_eng', label: 'Engagement', icon: '🌊', min: 0, max: 1, color: '#4ade80' },
  { key: 'd_warm', label: 'Warmth', icon: '💛', min: 0, max: 1, color: '#fbbf24' },
];

export default function DimensionSliders({ dims, liveDims, locked, onDimChange, onLockToggle }) {
  return (
    <div style={{ fontFamily: "'JetBrains Mono', monospace" }}>
      <div style={{ fontSize: 9, color: '#555', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
        Dimensions
      </div>
      {DIMS.map(d => {
        const value = dims?.[d.key] ?? 0.5;
        const liveValue = liveDims?.[d.key];
        const isLocked = locked?.[d.key];
        const pct = Math.max(0, Math.min(100, ((value - d.min) / (d.max - d.min)) * 100));

        return (
          <div key={d.key} style={{ marginBottom: 8 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 2 }}>
              <span style={{ fontSize: 10 }}>{d.icon}</span>
              <span style={{ fontSize: 8.5, color: '#666', flex: 1 }}>{d.label}</span>
              <span style={{ fontSize: 8.5, color: d.color, minWidth: 36, textAlign: 'right' }}>
                {value.toFixed(2)}
              </span>
              {liveValue !== undefined && (
                <span style={{ fontSize: 7, color: '#444', minWidth: 30, textAlign: 'right' }}>
                  ({liveValue.toFixed(2)})
                </span>
              )}
              <div
                onClick={() => onLockToggle?.(d.key)}
                style={{
                  cursor: 'pointer', fontSize: 10, marginLeft: 4,
                  opacity: isLocked ? 1 : 0.3,
                  transition: 'opacity 0.2s',
                }}
                title={isLocked ? 'Override active — click to unlock' : 'Click to lock & override'}
              >
                {isLocked ? '🔒' : '🔓'}
              </div>
            </div>
            <div style={{ position: 'relative', height: 4, background: 'rgba(255,255,255,0.04)', borderRadius: 2 }}>
              <div style={{
                position: 'absolute', left: 0, top: 0, height: '100%', borderRadius: 2,
                width: `${pct}%`,
                background: `linear-gradient(90deg, ${d.color}44, ${d.color})`,
                transition: 'width 0.3s ease',
              }} />
              <input
                type="range"
                min={d.min}
                max={d.max}
                step={0.01}
                value={value}
                onChange={e => onDimChange?.(d.key, parseFloat(e.target.value))}
                disabled={!isLocked}
                style={{
                  position: 'absolute', top: -6, left: 0, width: '100%', height: 16,
                  opacity: 0, cursor: isLocked ? 'pointer' : 'default', margin: 0,
                }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
