import React, { useMemo, useRef, forwardRef } from 'react';
import { useOrbFollow } from '../hooks/useOrbFollow';

// Color palette
const COLORS = {
  violet: '#a78bfa',
  brightViolet: '#c4b5fd',
  dimViolet: '#7c3aed',
  grey: '#6b7280',
  cyan: '#06b6d4',
  red: '#ef4444',
  emerald: '#10b981',
};

// State → Animation mapping
const STATE_ANIMATIONS = {
  idle: { animation: 'orb-idle 4s ease-in-out infinite', color: COLORS.violet },
  pulse: { animation: 'orb-pulse 0.8s ease-in-out infinite', color: COLORS.violet },
  pulse_fast: { animation: 'orb-pulse-fast 0.4s ease-in-out infinite', color: COLORS.brightViolet },
  spin: { animation: 'orb-spin 2s linear infinite', color: COLORS.violet },
  spin_fast: { animation: 'orb-spin-fast 0.8s linear infinite', color: COLORS.violet },
  flicker: { animation: 'orb-flicker 1.5s ease-in-out infinite', color: COLORS.violet },
  wobble: { animation: 'orb-wobble 1s ease-in-out infinite', color: COLORS.violet },
  drift: { animation: 'orb-drift 6s ease-in-out infinite', color: COLORS.dimViolet },
  orbit: { animation: 'orb-orbit 3s ease-in-out infinite', color: COLORS.cyan },
  glow: { animation: 'orb-glow-pulse 2s ease-in-out infinite', color: COLORS.brightViolet },
  split: { animation: 'orb-split 2s ease-in-out infinite', color: COLORS.violet },
  // System states
  processing: { animation: 'orb-spin 1.5s linear infinite', color: COLORS.violet },
  listening: { animation: 'orb-pulse 1s ease-in-out infinite', color: COLORS.emerald },
  speaking: { animation: 'orb-glow-pulse 0.8s ease-in-out infinite', color: COLORS.violet },
  memory_search: { animation: 'orb-orbit 2s ease-in-out infinite', color: COLORS.cyan },
  error: { animation: 'orb-wobble 0.5s ease-in-out infinite', color: COLORS.red },
  disconnected: { animation: 'orb-flicker 2s ease-in-out infinite', color: COLORS.grey },
};

/**
 * LunaOrb - Luna's visual identity component with follow behavior
 *
 * @param {string} state - Current orb state (idle, pulse, spin, etc.)
 * @param {number} size - Orb diameter in pixels (default: 48)
 * @param {number} brightness - Brightness multiplier 0-2 (default: 1)
 * @param {string} colorOverride - Optional color override
 * @param {boolean} showGlow - Show glow effect (default: true)
 * @param {React.RefObject} chatContainerRef - Ref to chat container (enables follow behavior)
 * @param {React.RefObject} messagesEndRef - Ref to messages end marker
 */
export const LunaOrb = forwardRef(function LunaOrb({
  state = 'idle',
  size = 48,
  brightness = 1,
  colorOverride = null,
  showGlow = true,
  chatContainerRef = null,
  messagesEndRef = null,
}, externalRef) {
  const internalOrbRef = useRef(null);
  const orbRef = externalRef || internalOrbRef;

  // Enable follow behavior if container ref is provided
  const followEnabled = chatContainerRef !== null;

  // Use the follow hook (only active when container ref is provided)
  useOrbFollow(
    followEnabled ? chatContainerRef : { current: null },
    followEnabled ? messagesEndRef : { current: null },
    followEnabled ? orbRef : { current: null }
  );

  const stateConfig = STATE_ANIMATIONS[state] || STATE_ANIMATIONS.idle;
  const color = colorOverride || stateConfig.color;

  const orbStyle = useMemo(() => ({
    width: size,
    height: size,
    borderRadius: '50%',
    background: `radial-gradient(circle at 30% 30%, ${color}dd, ${color}88, ${color}44)`,
    animation: stateConfig.animation,
    filter: showGlow
      ? `brightness(${brightness}) drop-shadow(0 0 ${size/4}px ${color})`
      : `brightness(${brightness})`,
    transition: 'background 0.3s ease, filter 0.3s ease',
    '--orb-brightness': `${brightness * 100}%`,
    '--orb-glow-color': color,
  }), [state, size, brightness, color, showGlow, stateConfig.animation]);

  // Container style for follow behavior
  const containerStyle = useMemo(() => {
    if (!followEnabled) return {};
    return {
      position: 'absolute',
      top: 0,
      left: 0,
      willChange: 'transform',
      pointerEvents: 'none',
      zIndex: 100,
      // Prevent CSS transitions from interfering with JS animation
      transition: 'none',
    };
  }, [followEnabled]);

  if (followEnabled) {
    return (
      <div
        ref={orbRef}
        className="luna-orb-container"
        style={containerStyle}
      >
        <div
          className="luna-orb"
          style={orbStyle}
          role="img"
          aria-label={`Luna is ${state}`}
        />
      </div>
    );
  }

  // Non-follow mode (original behavior)
  return (
    <div
      ref={orbRef}
      className="luna-orb"
      style={orbStyle}
      role="img"
      aria-label={`Luna is ${state}`}
    />
  );
});

export default LunaOrb;
