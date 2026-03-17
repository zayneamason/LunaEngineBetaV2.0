import React from 'react';

export default function Pill({ label, value, color, small }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 3,
      padding: small ? '1px 4px' : '2px 6px', borderRadius: 3,
      background: `${color || 'var(--ec-accent-luna)'}08`,
      border: `1px solid ${color || 'var(--ec-accent-luna)'}12`,
      fontSize: small ? 8 : 9,
      fontFamily: "'JetBrains Mono','SF Mono',monospace",
      whiteSpace: 'nowrap',
    }}>
      <span style={{ color: 'var(--ec-text-faint)', fontSize: small ? 6 : 7 }}>{label}</span>
      <span style={{ color: color || 'var(--ec-text)', fontWeight: 500 }}>
        {typeof value === 'number' ? value.toLocaleString() : value}
      </span>
    </span>
  );
}
