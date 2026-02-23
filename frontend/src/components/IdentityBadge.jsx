import React, { useState } from 'react';

/**
 * IdentityBadge — Shows who Luna currently sees via FaceID.
 *
 * Displays as a compact badge in the header when someone is recognized.
 * Includes a reset button for re-enrollment.
 */

const DR_TIER_LABELS = {
  1: 'Sovereign',
  2: 'Strategist',
  3: 'Domain',
  4: 'Advisor',
  5: 'External',
};

const TIER_COLORS = {
  admin:   { bg: 'rgba(16,185,129,0.15)', border: 'rgba(16,185,129,0.4)', text: '#10b981', dot: '#10b981' },
  trusted: { bg: 'rgba(59,130,246,0.15)', border: 'rgba(59,130,246,0.4)', text: '#3b82f6', dot: '#3b82f6' },
  friend:  { bg: 'rgba(251,191,36,0.15)', border: 'rgba(251,191,36,0.4)', text: '#fbbf24', dot: '#fbbf24' },
  guest:   { bg: 'rgba(148,163,184,0.15)', border: 'rgba(148,163,184,0.4)', text: '#94a3b8', dot: '#94a3b8' },
  unknown: { bg: 'rgba(239,68,68,0.15)',   border: 'rgba(239,68,68,0.4)',   text: '#ef4444', dot: '#ef4444' },
};

const IdentityBadge = ({ isPresent, entityName, lunaTier, dataroomTier, confidence, onReset }) => {
  const [showReset, setShowReset] = useState(false);
  const [pinInput, setPinInput] = useState('');
  const [resetError, setResetError] = useState('');

  if (!isPresent || !entityName) return null;

  const colors = TIER_COLORS[lunaTier] || TIER_COLORS.unknown;

  const handleReset = async () => {
    setResetError('');
    if (onReset) {
      const result = await onReset(pinInput);
      if (result && !result.success) {
        setResetError(result.error || 'Reset failed');
        return;
      }
    }
    setShowReset(false);
    setPinInput('');
  };

  return (
    <div className="relative flex items-center gap-1">
      <div
        className="flex items-center gap-2 px-3 py-1.5 rounded-md text-xs transition-all duration-500"
        style={{
          background: colors.bg,
          border: `1px solid ${colors.border}`,
          opacity: isPresent ? 1 : 0,
        }}
      >
        <div
          className="w-2 h-2 rounded-full animate-pulse"
          style={{ background: colors.dot, boxShadow: `0 0 6px ${colors.dot}` }}
        />
        <span style={{ color: colors.text, fontWeight: 600 }}>{entityName}</span>
        <span style={{ color: colors.text, opacity: 0.6, fontSize: 10 }}>{lunaTier}</span>
        {dataroomTier != null && (
          <span style={{ color: colors.text, opacity: 0.35, fontSize: 9 }}>
            {DR_TIER_LABELS[dataroomTier] || `T${dataroomTier}`}
          </span>
        )}
        <span style={{ color: 'rgba(255,255,255,0.3)', fontSize: 10 }}>
          {(confidence * 100).toFixed(0)}%
        </span>
      </div>

      {/* Small reset button */}
      <button
        onClick={() => setShowReset(!showReset)}
        className="p-1.5 rounded border border-transparent text-white/20 hover:text-red-400/80 hover:border-red-500/30 transition-all"
        title="Reset FaceID"
      >
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor"
          strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M1 4v6h6" />
          <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" />
        </svg>
      </button>

      {/* Reset dropdown */}
      {showReset && (
        <div className="absolute right-0 top-full mt-1 w-56 p-3 rounded border border-kozmo-border bg-kozmo-surface shadow-xl z-50"
          style={{ boxShadow: '0 8px 32px rgba(0,0,0,0.6)' }}>
          <p className="text-[10px] text-white/50 mb-2">Reset & re-enroll face data</p>
          <input
            type="password"
            maxLength={4}
            placeholder="PIN (if set)"
            value={pinInput}
            onChange={(e) => setPinInput(e.target.value.replace(/\D/g, ''))}
            className="w-full px-2 py-1.5 mb-2 text-xs rounded border border-kozmo-border bg-kozmo-bg text-white/80 placeholder-white/30 focus:outline-none focus:border-red-500/50"
          />
          {resetError && <p className="text-[10px] text-red-400 mb-2">{resetError}</p>}
          <div className="flex gap-2">
            <button
              onClick={handleReset}
              className="flex-1 px-2 py-1.5 text-xs rounded border border-red-500/40 text-red-400 hover:bg-red-500/10 transition-all"
            >
              Reset & Enroll
            </button>
            <button
              onClick={() => { setShowReset(false); setPinInput(''); setResetError(''); }}
              className="px-2 py-1.5 text-xs rounded border border-kozmo-border text-kozmo-muted hover:text-white/60 transition-all"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default IdentityBadge;
