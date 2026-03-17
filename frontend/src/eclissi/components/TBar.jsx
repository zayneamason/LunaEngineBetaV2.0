import React from 'react';

/**
 * TBar — thin gradient line above the input bar.
 * Click toggles the Guardian Luna panel.
 * Shows extraction count + "GUARDIAN LUNA" label + chevron.
 */
export default function TBar({ extractionCount = 0, isOpen, onToggle }) {
  return (
    <div
      onClick={onToggle}
      style={{
        display: 'flex',
        alignItems: 'center',
        height: 24,
        padding: '0 12px',
        cursor: 'pointer',
        background: isOpen ? 'rgba(251,191,36,0.06)' : 'transparent',
        borderTop: '1px solid rgba(251,191,36,0.12)',
        transition: 'background 0.2s',
        flexShrink: 0,
      }}
      onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(251,191,36,0.08)'; }}
      onMouseLeave={(e) => { e.currentTarget.style.background = isOpen ? 'rgba(251,191,36,0.06)' : 'transparent'; }}
    >
      {/* Gradient line */}
      <div style={{
        flex: 1,
        height: 1,
        background: 'linear-gradient(90deg, transparent, rgba(251,191,36,0.3), rgba(192,132,252,0.2), transparent)',
      }} />

      {/* Label */}
      <span style={{
        margin: '0 12px',
        fontSize: 9,
        fontWeight: 600,
        letterSpacing: 2,
        color: isOpen ? '#fbbf24' : 'var(--ec-text-faint, #6b7280)',
        textTransform: 'uppercase',
        transition: 'color 0.2s',
      }}>
        GUARDIAN LUNA
      </span>

      {/* Extraction count */}
      {extractionCount > 0 && (
        <span style={{
          fontSize: 9,
          color: 'var(--ec-text-faint, #6b7280)',
          marginRight: 8,
        }}>
          {extractionCount} extractions
        </span>
      )}

      {/* Chevron */}
      <span style={{
        fontSize: 10,
        color: isOpen ? '#fbbf24' : 'var(--ec-text-faint, #6b7280)',
        transition: 'transform 0.2s, color 0.2s',
        transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)',
      }}>
        ▾
      </span>

      {/* Gradient line */}
      <div style={{
        flex: 1,
        height: 1,
        background: 'linear-gradient(90deg, transparent, rgba(192,132,252,0.2), rgba(251,191,36,0.3), transparent)',
      }} />
    </div>
  );
}
