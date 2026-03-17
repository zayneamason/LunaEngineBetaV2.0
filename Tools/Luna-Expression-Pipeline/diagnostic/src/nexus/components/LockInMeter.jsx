import React from 'react';

export function classifyState(lockIn) {
  if (lockIn >= 0.70) return 'settled';
  if (lockIn >= 0.30) return 'fluid';
  return 'drifting';
}

export const STATE_COLORS = {
  settled: '#34d399',  // prompt/green
  fluid: '#7dd3fc',    // memory/blue
  drifting: '#f87171',  // qa/red
};

export const STATE_ICONS = {
  settled: '\u25C6',  // ◆
  fluid: '\u25C7',    // ◇
  drifting: '\u25CB',  // ○
};

export default function LockInMeter({ value, width = 60, height = 4 }) {
  const state = classifyState(value);
  const color = STATE_COLORS[state];
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <div style={{
        width, height, borderRadius: height / 2,
        background: 'rgba(58,58,80,0.15)', overflow: 'hidden',
      }}>
        <div style={{
          width: `${value * 100}%`, height: '100%', borderRadius: height / 2,
          background: color, opacity: 0.7, transition: 'width 0.6s ease',
        }} />
      </div>
      <span style={{
        fontSize: 8,
        fontFamily: "'JetBrains Mono','SF Mono',monospace",
        color, minWidth: 28,
      }}>
        {(value * 100).toFixed(0)}%
      </span>
    </div>
  );
}
