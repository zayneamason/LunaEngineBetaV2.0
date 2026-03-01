import React from 'react';

export default function TabButton({ label, accent, isActive, onClick }) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: '6px 16px',
        fontSize: 11,
        letterSpacing: 1.5,
        cursor: 'pointer',
        border: '1px solid transparent',
        borderRadius: 4,
        background: isActive ? `color-mix(in srgb, ${accent} 8%, transparent)` : 'transparent',
        borderColor: isActive ? `color-mix(in srgb, ${accent} 30%, transparent)` : 'transparent',
        color: isActive ? accent : 'var(--ec-text-faint)',
        transition: 'all 0.2s ease',
        fontFamily: "'Bebas Neue', sans-serif",
        textTransform: 'uppercase',
      }}
      onMouseEnter={(e) => {
        if (!isActive) {
          e.currentTarget.style.color = 'var(--ec-text-soft)';
          e.currentTarget.style.borderColor = 'var(--ec-border-hover)';
        }
      }}
      onMouseLeave={(e) => {
        if (!isActive) {
          e.currentTarget.style.color = 'var(--ec-text-faint)';
          e.currentTarget.style.borderColor = 'transparent';
        }
      }}
    >
      {label}
    </button>
  );
}
