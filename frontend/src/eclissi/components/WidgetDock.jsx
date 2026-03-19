import React from 'react';

const WIDGETS = [
  { id: 'engine',  icon: '⚡', label: 'Engine',  accent: 'var(--ec-accent-luna)' },
  { id: 'voice',   icon: '🔊', label: 'Voice',   accent: 'var(--ec-accent-voice)' },
  { id: 'memory',  icon: '🧠', label: 'Memory',  accent: 'var(--ec-accent-memory)' },
  { id: 'qa',      icon: '✓',  label: 'QA',      accent: 'var(--ec-accent-qa)' },
  { id: 'divider1' },
  { id: 'prompt',  icon: '📜', label: 'Prompt',  accent: 'var(--ec-accent-prompt)' },
  { id: 'debug',   icon: '🔍', label: 'Debug',   accent: 'var(--ec-accent-debug)' },
  { id: 'vk',      icon: '🎭', label: 'VK',      accent: 'var(--ec-accent-vk)' },
  { id: 'divider2' },
  { id: 'arcade',     icon: '🕹', label: 'Arcade',     accent: 'var(--ec-accent-qa)' },
  { id: 'lunascript', icon: '◈', label: 'LunaScript', accent: 'var(--ec-accent-memory)' },
  { id: 'cache',   icon: '💾', label: 'Cache',   accent: 'var(--ec-accent-luna)' },
  { id: 'thought', icon: '💭', label: 'Thought', accent: 'var(--ec-accent-voice)' },
];

export default function WidgetDock({ activeWidget, onWidgetToggle, badges, enabledWidgets }) {
  return (
    <div
      style={{
        width: 'var(--ec-widget-rail-width, 52px)',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        paddingTop: 12,
        gap: 4,
        background: 'var(--ec-bg-raised)',
        borderRight: '1px solid var(--ec-border)',
      }}
    >
      {WIDGETS.filter((w) => w.id.startsWith('divider') || !enabledWidgets || enabledWidgets[w.id] !== false).map((w) => {
        if (w.id.startsWith('divider')) {
          return (
            <div
              key={w.id}
              style={{
                width: 24,
                height: 1,
                background: 'var(--ec-border)',
                margin: '4px 0',
              }}
            />
          );
        }

        const isActive = activeWidget === w.id;
        const badge = badges?.[w.id];

        return (
          <button
            key={w.id}
            onClick={() => onWidgetToggle(w.id)}
            title={w.label}
            style={{
              width: 36,
              height: 36,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              borderRadius: 6,
              border: '1px solid transparent',
              background: isActive ? `color-mix(in srgb, ${w.accent} 12%, transparent)` : 'transparent',
              borderColor: isActive ? `color-mix(in srgb, ${w.accent} 30%, transparent)` : 'transparent',
              cursor: 'pointer',
              transition: 'all 0.2s ease',
              fontSize: 16,
              position: 'relative',
            }}
            onMouseEnter={(e) => {
              if (!isActive) {
                e.currentTarget.style.background = 'rgba(255,255,255,0.04)';
                e.currentTarget.style.borderColor = 'var(--ec-border-hover)';
              }
            }}
            onMouseLeave={(e) => {
              if (!isActive) {
                e.currentTarget.style.background = 'transparent';
                e.currentTarget.style.borderColor = 'transparent';
              }
            }}
          >
            {w.icon}
            {badge != null && badge > 0 && (
              <span
                style={{
                  position: 'absolute',
                  top: -2,
                  right: -2,
                  width: 14,
                  height: 14,
                  borderRadius: '50%',
                  background: 'var(--ec-accent-qa)',
                  color: '#fff',
                  fontSize: 9,
                  fontWeight: 700,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                {badge}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
