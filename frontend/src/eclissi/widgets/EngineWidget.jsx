import React from 'react';
import { useLunaAPI } from '../../hooks/useLunaAPI';

const ACTORS = [
  { key: 'director', label: 'Director', icon: '🎬' },
  { key: 'scribe', label: 'Scribe', icon: '✍️' },
  { key: 'librarian', label: 'Librarian', icon: '📚' },
  { key: 'cache', label: 'Cache', icon: '🧊' },
  { key: 'scout', label: 'Scout', icon: '🔭' },
  { key: 'identity', label: 'Identity', icon: '👤' },
];

function StatBox({ label, value, accent }) {
  return (
    <div
      className="ec-glass-interactive"
      style={{
        padding: '8px 10px',
        borderRadius: 6,
      }}
    >
      <div className="ec-font-label" style={{ fontSize: 9, color: 'var(--ec-text-faint)', marginBottom: 2 }}>
        {label}
      </div>
      <div className="ec-font-mono" style={{ fontSize: 13, color: accent || 'var(--ec-text)' }}>
        {value}
      </div>
    </div>
  );
}

export default function EngineWidget() {
  const { status, consciousness, isConnected } = useLunaAPI();

  if (!isConnected || !status) {
    return (
      <div style={{ color: 'var(--ec-text-faint)', fontSize: 12, textAlign: 'center', padding: 20 }}>
        Engine offline
      </div>
    );
  }

  const uptime = status.uptime_seconds ? `${(status.uptime_seconds / 60) | 0}m` : '—';
  const ticks = status.cognitive_ticks?.toLocaleString() || '0';
  const events = status.events_processed?.toLocaleString() || '0';
  const state = status.state || 'UNKNOWN';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Stats grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        <StatBox label="STATE" value={state} accent={state === 'RUNNING' ? '#22c55e' : '#f59e0b'} />
        <StatBox label="UPTIME" value={uptime} />
        <StatBox label="TICKS" value={ticks} accent="var(--ec-accent-luna)" />
        <StatBox label="EVENTS" value={events} />
      </div>

      {/* Actor roster */}
      <div>
        <div className="ec-font-label" style={{ fontSize: 9, color: 'var(--ec-text-faint)', marginBottom: 8 }}>
          ACTORS
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {ACTORS.map((a) => {
            const actor = status.actors?.[a.key];
            const alive = actor?.alive !== false;
            return (
              <div
                key={a.key}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '4px 8px',
                  borderRadius: 4,
                  background: 'rgba(255,255,255,0.02)',
                }}
              >
                <span style={{ fontSize: 12 }}>
                  {a.icon} <span className="ec-font-body" style={{ fontSize: 11, color: 'var(--ec-text-soft)' }}>{a.label}</span>
                </span>
                <span
                  style={{
                    width: 6,
                    height: 6,
                    borderRadius: '50%',
                    background: alive ? '#22c55e' : '#ef4444',
                    boxShadow: alive ? '0 0 6px rgba(34,197,94,0.5)' : '0 0 6px rgba(239,68,68,0.5)',
                  }}
                />
              </div>
            );
          })}
        </div>
      </div>

      {/* Consciousness */}
      {consciousness && (
        <div>
          <div className="ec-font-label" style={{ fontSize: 9, color: 'var(--ec-text-faint)', marginBottom: 6 }}>
            CONSCIOUSNESS
          </div>
          <div className="ec-glass-interactive" style={{ padding: '8px 10px', borderRadius: 6 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
              <span className="ec-font-body" style={{ color: 'var(--ec-text-soft)' }}>Mood</span>
              <span className="ec-font-mono" style={{ color: 'var(--ec-text)' }}>{consciousness.mood || '—'}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginTop: 4 }}>
              <span className="ec-font-body" style={{ color: 'var(--ec-text-soft)' }}>Coherence</span>
              <span className="ec-font-mono" style={{ color: 'var(--ec-accent-luna)' }}>
                {consciousness.coherence != null ? `${(consciousness.coherence * 100).toFixed(0)}%` : '—'}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
