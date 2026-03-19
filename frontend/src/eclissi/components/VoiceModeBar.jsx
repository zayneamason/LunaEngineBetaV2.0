import React, { useState, useEffect, useRef } from 'react';

const BAR_COUNT = 7;

/**
 * VoiceModeBar — horizontal bar above the chat input showing voice state.
 * Shows real audio levels while listening, transcription text after processing,
 * and clear state labels throughout the voice cycle.
 */
export default function VoiceModeBar({
  voiceState,
  isListening,
  isSpeaking,
  isThinking,
  transcription,
  audioLevel = 0,
  hint,
  onClose,
}) {
  // Recording duration timer
  const [elapsed, setElapsed] = useState(0);
  const timerRef = useRef(null);

  useEffect(() => {
    if (isListening) {
      setElapsed(0);
      timerRef.current = setInterval(() => setElapsed((t) => t + 1), 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [isListening]);

  // Determine display state
  const showTranscription = !isListening && !isSpeaking && transcription;
  const showHint = !isListening && !isSpeaking && !isThinking && !showTranscription && hint;
  const label = isListening
    ? 'LISTENING'
    : isThinking
    ? (showTranscription ? '' : 'PROCESSING')
    : isSpeaking
    ? 'SPEAKING'
    : showTranscription
    ? ''
    : showHint
    ? ''
    : 'VOICE ACTIVE';

  const accentColor = isListening
    ? 'var(--ec-accent-luna, #c084fc)'
    : isSpeaking
    ? '#22c55e'
    : isThinking
    ? 'var(--ec-accent-debug, #f59e0b)'
    : 'var(--ec-text-faint, #5a5a70)';

  // Clamp audio level for bar heights (0-1 range, boost low values)
  const level = Math.min(1, audioLevel * 5);

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: '8px 16px',
        background: 'rgba(18,18,26,0.6)',
        backdropFilter: 'blur(12px)',
        WebkitBackdropFilter: 'blur(12px)',
        borderBottom: '1px solid var(--ec-border, rgba(255,255,255,0.06))',
        animation: 'tpanel-slide-left 0.3s ease-out',
        minHeight: 40,
      }}
    >
      {/* Audio level bars — real data when listening, animated when speaking */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 2, height: 28, flexShrink: 0 }}>
        {Array.from({ length: BAR_COUNT }).map((_, i) => {
          let barHeight;
          if (isListening) {
            // Real audio level with per-bar variation
            const variation = 0.6 + 0.4 * Math.sin(i * 1.3);
            barHeight = Math.max(3, level * 24 * variation);
          } else if (isSpeaking) {
            barHeight = 6; // base height — CSS animation overrides via keyframes
          } else {
            barHeight = 4;
          }
          return (
            <div
              key={i}
              style={{
                width: 3,
                borderRadius: 2,
                background: accentColor,
                height: barHeight,
                transition: isListening ? 'height 0.08s ease-out' : 'height 0.3s ease',
                animation: isSpeaking ? `ec-waveform 0.8s ease-in-out infinite` : 'none',
                animationDelay: isSpeaking ? `${i * 0.1}s` : undefined,
                '--ec-wave-h': `${14 + (i % 3) * 5}px`,
              }}
            />
          );
        })}
      </div>

      {/* Status label or transcription text */}
      <div style={{ flex: 1, minWidth: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
        {showTranscription ? (
          <span
            style={{
              fontSize: 12,
              color: 'var(--ec-text, #e0e0e0)',
              fontFamily: 'var(--ec-font-mono, monospace)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              opacity: 0.9,
            }}
          >
            <span style={{ color: 'var(--ec-text-faint, #5a5a70)', marginRight: 6 }}>You:</span>
            {transcription}
          </span>
        ) : showHint ? (
          <span
            style={{
              fontSize: 11,
              color: 'var(--ec-accent-qa, #f87171)',
              fontFamily: 'var(--ec-font-mono, monospace)',
              opacity: 0.8,
              animation: 'ec-pulse 2s ease-in-out 1',
            }}
          >
            {hint}
          </span>
        ) : (
          <>
            {label && (
              <span
                style={{
                  fontSize: 10,
                  color: accentColor,
                  letterSpacing: '2px',
                  fontFamily: 'var(--ec-font-label, sans-serif)',
                }}
              >
                {label}
              </span>
            )}
            {isThinking && !showTranscription && (
              <span style={{ fontSize: 10, color: accentColor, animation: 'ec-pulse 1s ease-in-out infinite' }}>
                ...
              </span>
            )}
          </>
        )}

        {/* Recording timer */}
        {isListening && (
          <span
            style={{
              fontSize: 10,
              color: 'var(--ec-text-faint, #5a5a70)',
              fontFamily: 'var(--ec-font-mono, monospace)',
              marginLeft: 'auto',
              flexShrink: 0,
            }}
          >
            {elapsed}s
          </span>
        )}
      </div>

      {/* TTS status */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexShrink: 0 }}>
        <div
          style={{
            width: 5,
            height: 5,
            borderRadius: '50%',
            background: isSpeaking ? '#22c55e' : 'var(--ec-text-faint, #5a5a70)',
            animation: isSpeaking ? 'ec-speaking-glow 1.5s ease-in-out infinite' : 'none',
          }}
        />
        <span style={{ fontSize: 8, color: 'var(--ec-text-faint, #5a5a70)', fontFamily: 'var(--ec-font-mono, monospace)' }}>
          TTS
        </span>
      </div>

      {/* Close button */}
      <button
        onClick={onClose}
        style={{
          background: 'none',
          border: 'none',
          color: 'var(--ec-text-faint, #5a5a70)',
          cursor: 'pointer',
          padding: 4,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          borderRadius: 4,
          transition: 'color 0.2s',
          flexShrink: 0,
        }}
        onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--ec-text, #e0e0e0)'; }}
        onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--ec-text-faint, #5a5a70)'; }}
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <line x1="18" y1="6" x2="6" y2="18" />
          <line x1="6" y1="6" x2="18" y2="18" />
        </svg>
      </button>
    </div>
  );
}
