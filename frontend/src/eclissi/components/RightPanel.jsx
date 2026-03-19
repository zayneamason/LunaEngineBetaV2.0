import React from 'react';

const WIDGET_TITLES = {
  engine:  { label: 'ENGINE STATUS',  accent: 'var(--ec-accent-luna)' },
  voice:   { label: 'VOICE BLEND',    accent: 'var(--ec-accent-voice)' },
  memory:  { label: 'MEMORY MONITOR', accent: 'var(--ec-accent-memory)' },
  qa:      { label: 'QA ASSERTIONS',  accent: 'var(--ec-accent-qa)' },
  prompt:  { label: 'PROMPT INSPECTOR', accent: 'var(--ec-accent-prompt)' },
  debug:   { label: 'CONTEXT DEBUG',  accent: 'var(--ec-accent-debug)' },
  vk:      { label: 'VOIGHT-KAMPFF',  accent: 'var(--ec-accent-vk)' },
  cache:   { label: 'SHARED TURN CACHE', accent: 'var(--ec-accent-luna)' },
  thought: { label: 'THOUGHT STREAM', accent: 'var(--ec-accent-voice)' },
  arcade:  { label: 'ARCADE',         accent: 'var(--ec-accent-qa)' },
};

export default function RightPanel({ activeWidget, onClose, children }) {
  const isOpen = activeWidget != null;
  const title = WIDGET_TITLES[activeWidget] || { label: '', accent: 'var(--ec-accent-luna)' };

  return (
    <div
      className="ec-glass-panel"
      style={{
        width: 'var(--ec-right-panel-width, 320px)',
        height: '100%',
        background: 'var(--ec-bg-panel)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        transition: `transform var(--ec-duration-panel, 0.5s) var(--ec-ease-panel), opacity var(--ec-duration-fade, 0.35s) ease`,
        transform: isOpen ? 'translateX(0)' : 'translateX(100%)',
        opacity: isOpen ? 1 : 0,
        position: isOpen ? 'relative' : 'absolute',
        right: 0,
        top: 0,
      }}
    >
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '12px 16px',
          borderBottom: '1px solid var(--ec-border)',
          flexShrink: 0,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div
            style={{
              width: 3,
              height: 14,
              background: title.accent,
              borderRadius: 2,
            }}
          />
          <span
            className="ec-font-label"
            style={{
              fontSize: 11,
              color: 'var(--ec-text-soft)',
            }}
          >
            {title.label}
          </span>
        </div>
        <button
          onClick={onClose}
          style={{
            width: 24,
            height: 24,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderRadius: 4,
            border: '1px solid var(--ec-border)',
            background: 'transparent',
            color: 'var(--ec-text-faint)',
            cursor: 'pointer',
            fontSize: 12,
            transition: 'all 0.2s ease',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.borderColor = 'var(--ec-border-hover)';
            e.currentTarget.style.color = 'var(--ec-text-soft)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.borderColor = 'var(--ec-border)';
            e.currentTarget.style.color = 'var(--ec-text-faint)';
          }}
        >
          ✕
        </button>
      </div>

      {/* Body */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '12px 16px',
        }}
      >
        {children}
      </div>
    </div>
  );
}
