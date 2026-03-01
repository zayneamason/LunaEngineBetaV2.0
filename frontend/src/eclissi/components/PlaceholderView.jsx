import React from 'react';

export default function PlaceholderView({ name, accent, description }) {
  return (
    <div
      style={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 16,
        background: 'var(--ec-bg)',
        color: 'var(--ec-text-faint)',
      }}
    >
      <span
        className="ec-font-label"
        style={{ fontSize: 24, letterSpacing: 6, color: accent }}
      >
        {name}
      </span>
      <span
        className="ec-font-body"
        style={{ fontSize: 13, maxWidth: 400, textAlign: 'center' }}
      >
        {description}
      </span>
    </div>
  );
}
