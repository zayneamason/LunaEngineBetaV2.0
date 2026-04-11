import React, { useState, useRef } from 'react';

/**
 * Slider puzzle — user must drag the thumb to the end of the track
 * to trigger onConfirm.  Snaps back to start if released early.
 */
export default function SliderConfirm({ onConfirm, label = 'SLIDE TO RESET', width = 280 }) {
  const [position, setPosition] = useState(0);
  const [dragging, setDragging] = useState(false);
  const trackRef = useRef(null);
  const thumbWidth = 48;
  const maxPos = width - thumbWidth;

  const updatePosition = (clientX) => {
    if (!trackRef.current) return;
    const rect = trackRef.current.getBoundingClientRect();
    const x = Math.min(Math.max(0, clientX - rect.left - thumbWidth / 2), maxPos);
    setPosition(x);
  };

  const handleStart = (e) => {
    setDragging(true);
    e.preventDefault();
  };

  const handleMove = (e) => {
    if (!dragging) return;
    const clientX = e.touches ? e.touches[0].clientX : e.clientX;
    updatePosition(clientX);
  };

  const handleEnd = () => {
    if (!dragging) return;
    setDragging(false);
    if (position >= maxPos * 0.92) {
      onConfirm();
    }
    setPosition(0);
  };

  const pct = position / maxPos;

  return (
    <div
      ref={trackRef}
      onMouseMove={handleMove}
      onMouseUp={handleEnd}
      onMouseLeave={() => { if (dragging) { setDragging(false); setPosition(0); } }}
      onTouchMove={handleMove}
      onTouchEnd={handleEnd}
      style={{
        width,
        height: 40,
        borderRadius: 20,
        background: `linear-gradient(90deg, rgba(248,113,113,${0.08 + pct * 0.35}) 0%, rgba(248,113,113,${0.15 + pct * 0.55}) 100%)`,
        border: '1px solid var(--ec-border)',
        position: 'relative',
        cursor: 'default',
        userSelect: 'none',
        touchAction: 'none',
      }}
    >
      {/* Track label */}
      <div style={{
        position: 'absolute',
        top: '50%',
        left: '50%',
        transform: 'translate(-50%, -50%)',
        fontSize: 8,
        letterSpacing: 2,
        color: 'var(--ec-text-faint)',
        pointerEvents: 'none',
      }}>
        {label}
      </div>

      {/* Thumb */}
      <div
        onMouseDown={handleStart}
        onTouchStart={handleStart}
        style={{
          width: thumbWidth,
          height: 36,
          borderRadius: 18,
          background: pct > 0.85 ? '#f87171' : 'var(--ec-surface-2, #1a1a2e)',
          border: '1px solid var(--ec-border)',
          position: 'absolute',
          top: 2,
          left: position,
          cursor: 'grab',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 14,
          color: pct > 0.85 ? '#fff' : 'var(--ec-text-faint)',
          transition: dragging ? 'none' : 'left 0.3s ease, background 0.2s ease',
        }}
      >
        {pct > 0.85 ? '!' : '\u203A'}
      </div>
    </div>
  );
}
