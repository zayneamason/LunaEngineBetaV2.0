import React from 'react';

const WAVE_HEIGHTS = ['18px', '24px', '14px', '22px', '16px'];
const WAVE_DELAYS = ['0s', '0.15s', '0.3s', '0.1s', '0.25s'];

/**
 * VoiceModeBar — horizontal bar above the chat input showing voice state.
 * Contains animated waveform, status label, TTS indicator, close button.
 */
export default function VoiceModeBar({ voiceState, isListening, isSpeaking, isThinking, onClose }) {
  const label = isListening
    ? 'LISTENING'
    : isSpeaking
    ? 'SPEAKING'
    : isThinking
    ? 'THINKING'
    : 'VOICE ACTIVE';

  const accentColor = isListening
    ? 'var(--ec-accent-luna)'
    : isSpeaking
    ? 'var(--ec-accent-voice)'
    : isThinking
    ? 'var(--ec-accent-debug)'
    : 'var(--ec-text-faint)';

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: '8px 16px',
        background: 'rgba(18,18,26,0.6)',
        backdropFilter: 'blur(12px)',
        WebkitBackdropFilter: 'blur(12px)',
        borderBottom: '1px solid var(--ec-border)',
        animation: 'tpanel-slide-left 0.3s ease-out',
      }}
    >
      {/* Waveform */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 2, height: 28 }}>
        {WAVE_HEIGHTS.map((h, i) => (
          <div
            key={i}
            style={{
              width: 3,
              borderRadius: 2,
              background: accentColor,
              animation: isListening || isSpeaking
                ? `ec-waveform 0.8s ease-in-out infinite`
                : 'none',
              animationDelay: WAVE_DELAYS[i],
              height: isListening || isSpeaking ? undefined : 6,
              '--ec-wave-h': h,
            }}
          />
        ))}
      </div>

      {/* Status label */}
      <span
        className="ec-font-label"
        style={{
          fontSize: 10,
          color: accentColor,
          letterSpacing: '2px',
        }}
      >
        {label}
      </span>

      {/* Spacer */}
      <div style={{ flex: 1 }} />

      {/* TTS status */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        <div
          style={{
            width: 5,
            height: 5,
            borderRadius: '50%',
            background: isSpeaking ? '#22c55e' : 'var(--ec-text-faint)',
            animation: isSpeaking ? 'ec-speaking-glow 1.5s ease-in-out infinite' : 'none',
          }}
        />
        <span className="ec-font-mono" style={{ fontSize: 8, color: 'var(--ec-text-faint)' }}>
          TTS
        </span>
      </div>

      {/* Close button */}
      <button
        onClick={onClose}
        style={{
          background: 'none',
          border: 'none',
          color: 'var(--ec-text-faint)',
          cursor: 'pointer',
          padding: 4,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          borderRadius: 4,
          transition: 'color 0.2s',
        }}
        onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--ec-text)'; }}
        onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--ec-text-faint)'; }}
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <line x1="18" y1="6" x2="6" y2="18" />
          <line x1="6" y1="6" x2="18" y2="18" />
        </svg>
      </button>
    </div>
  );
}
