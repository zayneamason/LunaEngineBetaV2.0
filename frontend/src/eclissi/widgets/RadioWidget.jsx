import React, { useState, useEffect, useRef } from 'react';

const CHANNEL_COLORS = {
  news: '#f87171',
  history: '#2dd4bf',
  entertainment: '#fbbf24',
  unknown: '#94a3b8',
};

const STATE_COLORS = {
  idle: '#64748b',
  scanning: '#3b82f6',
  surveying: '#3b82f6',
  sampling: '#3b82f6',
  processing: '#f59e0b',
  analyzing: '#f59e0b',
  associating: '#f59e0b',
  consolidating: '#f59e0b',
  evaluating: '#f59e0b',
  emitting: '#22c55e',
  cooldown: '#475569',
  paused: '#ef4444',
};

const TRAIT_NAMES = [
  'curiosity', 'warmth', 'depth', 'energy',
  'directness', 'formality', 'humor', 'patience',
];

const APERTURE_PRESETS = [
  { key: 'TUNNEL',   sigma: 0.01 },
  { key: 'NARROW',   sigma: 0.02 },
  { key: 'BALANCED', sigma: 0.05 },
  { key: 'WIDE',     sigma: 0.10 },
  { key: 'OPEN',     sigma: 0.20 },
];

function fmtUptime(s) {
  if (!s || s < 1) return '—';
  if (s < 60) return `${Math.round(s)}s`;
  if (s < 3600) return `${Math.round(s / 60)}m`;
  return `${Math.round(s / 360) / 10}h`;
}

function fmtTime(iso) {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch {
    return '';
  }
}

function ChannelCard({ channel }) {
  const color = CHANNEL_COLORS[channel.id] || 'var(--ec-accent-luna)';
  const stateColor = STATE_COLORS[channel.state] || '#64748b';
  return (
    <div
      className="ec-glass-interactive"
      style={{
        flex: 1,
        minWidth: 0,
        padding: '8px 10px',
        borderRadius: 6,
        borderLeft: `2px solid ${color}`,
        display: 'flex',
        flexDirection: 'column',
        gap: 4,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span
          style={{
            width: 8,
            height: 8,
            borderRadius: '50%',
            background: stateColor,
            boxShadow: channel.is_active ? `0 0 6px ${stateColor}` : 'none',
            transition: 'background 0.25s',
          }}
        />
        <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--ec-text-primary)' }}>
          {channel.name || channel.id}
        </span>
      </div>
      <div style={{ fontSize: 9, color: 'var(--ec-text-faint)', textTransform: 'uppercase' }}>
        {channel.state}
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9, color: 'var(--ec-text-secondary)' }}>
        <span>{channel.interval_s}s</span>
        <span>{channel.emissions_last_hour}/hr</span>
      </div>
    </div>
  );
}

function ArtifactRow({ a }) {
  const channelId = (a.source || '').split(':')[1] || 'unknown';
  const color = CHANNEL_COLORS[channelId] || 'var(--ec-accent-luna)';
  return (
    <div
      style={{
        padding: '6px 10px',
        borderLeft: `2px solid ${color}`,
        background: 'rgba(255,255,255,0.02)',
        borderRadius: 3,
        marginBottom: 4,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9, color: 'var(--ec-text-faint)', marginBottom: 2 }}>
        <span style={{ color, fontWeight: 600 }}>
          [{channelId}] {a.node_type}
        </span>
        <span>{fmtTime(a.created_at)}</span>
      </div>
      <div style={{ fontSize: 11, color: 'var(--ec-text-secondary)', lineHeight: 1.3 }}>
        {a.content}
      </div>
    </div>
  );
}

function TraitBar({ name, value, nudge }) {
  const pct = Math.round((value || 0) * 100);
  const color = CHANNEL_COLORS[nudge?.source] || 'var(--ec-accent-memory)';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 10 }}>
      <span style={{ width: 64, color: 'var(--ec-text-faint)', textTransform: 'capitalize' }}>{name}</span>
      <div style={{ flex: 1, height: 5, background: 'rgba(255,255,255,0.06)', borderRadius: 3, overflow: 'hidden' }}>
        <div
          style={{
            width: `${pct}%`,
            height: '100%',
            background: nudge ? color : 'var(--ec-accent-memory)',
            borderRadius: 3,
            transition: 'width 0.3s, background 0.3s',
          }}
        />
      </div>
      <span style={{ width: 24, textAlign: 'right', color: 'var(--ec-text-secondary)' }}>{pct}</span>
      {nudge && (
        <span
          style={{
            width: 42,
            textAlign: 'right',
            fontSize: 9,
            color: nudge.delta > 0 ? '#22c55e' : '#ef4444',
            opacity: nudge.faded ? 0.3 : 1,
            transition: 'opacity 0.8s',
          }}
          title={`from ${nudge.source}`}
        >
          {nudge.delta > 0 ? '+' : ''}{nudge.delta.toFixed(2)}
        </span>
      )}
    </div>
  );
}

export default function RadioWidget() {
  const [status, setStatus] = useState(null);
  const [artifacts, setArtifacts] = useState([]);
  const [pollution, setPollution] = useState(null);
  const [traits, setTraits] = useState(null);
  const [aperture, setAperture] = useState(null);
  const [nudges, setNudges] = useState({}); // trait -> { delta, source, ts, faded }
  const [error, setError] = useState(null);
  const nudgeTimers = useRef({});

  const showNudge = (trait, delta, source) => {
    setNudges((prev) => ({
      ...prev,
      [trait]: { delta, source, ts: Date.now(), faded: false },
    }));
    if (nudgeTimers.current[trait]) clearTimeout(nudgeTimers.current[trait]);
    nudgeTimers.current[trait] = setTimeout(() => {
      setNudges((prev) => {
        const next = { ...prev };
        if (next[trait]) next[trait] = { ...next[trait], faded: true };
        return next;
      });
      setTimeout(() => {
        setNudges((prev) => {
          const next = { ...prev };
          delete next[trait];
          return next;
        });
      }, 1000);
    }, 5000);
  };

  useEffect(() => {
    let cancelled = false;

    const bootstrap = async () => {
      try {
        const [sRes, aRes, pRes, tRes] = await Promise.all([
          fetch('/lunafm/status'),
          fetch('/lunafm/artifacts?limit=15'),
          fetch('/lunafm/pollution'),
          fetch('/lunafm/traits'),
        ]);
        if (cancelled) return;
        if (sRes.ok) { setStatus(await sRes.json()); setError(null); }
        if (aRes.ok) { const d = await aRes.json(); setArtifacts(d.artifacts || []); }
        if (pRes.ok) setPollution(await pRes.json());
        if (tRes.ok) {
          const d = await tRes.json();
          setTraits(d.traits || {});
          setAperture(d.aperture || null);
        }
      } catch {
        if (!cancelled) setError('connection failed');
      }
    };
    bootstrap();

    const statusPoll = setInterval(async () => {
      if (cancelled) return;
      try {
        const r = await fetch('/lunafm/status');
        if (r.ok) setStatus(await r.json());
      } catch {}
    }, 3000);

    const pollutionPoll = setInterval(async () => {
      if (cancelled) return;
      try {
        const r = await fetch('/lunafm/pollution');
        if (r.ok) setPollution(await r.json());
      } catch {}
    }, 15000);

    const traitsPoll = setInterval(async () => {
      if (cancelled) return;
      try {
        const r = await fetch('/lunafm/traits');
        if (r.ok) {
          const d = await r.json();
          setTraits(d.traits || {});
          setAperture(d.aperture || null);
        }
      } catch {}
    }, 5000);

    const es = new EventSource('/lunafm/stream');
    es.addEventListener('hello', (e) => {
      try { setStatus(JSON.parse(e.data)); setError(null); } catch {}
    });
    es.addEventListener('emission', (e) => {
      try {
        const ev = JSON.parse(e.data);
        const artifact = {
          id: ev.node_id,
          node_type: ev.node_type,
          source: `lunafm:${ev.channel}`,
          content: ev.content,
          lock_in: ev.lock_in,
          created_at: ev.timestamp,
          metadata: JSON.stringify(ev.metadata || {}),
        };
        setArtifacts((prev) => [artifact, ...prev].slice(0, 30));
      } catch {}
    });
    es.addEventListener('state_change', (e) => {
      try {
        const ev = JSON.parse(e.data);
        setStatus((prev) => {
          if (!prev) return prev;
          const channels = (prev.channels || []).map((c) =>
            c.id === ev.channel ? { ...c, state: ev.to, is_active: ev.to !== 'idle' } : c
          );
          return { ...prev, channels };
        });
      } catch {}
    });
    es.addEventListener('trait_nudge', (e) => {
      try {
        const ev = JSON.parse(e.data);
        setTraits((prev) => ({ ...(prev || {}), [ev.trait]: ev.new_value }));
        showNudge(ev.trait, ev.delta, ev.source);
      } catch {}
    });
    es.onerror = () => {
      if (!cancelled) setError('stream disconnected');
    };

    return () => {
      cancelled = true;
      clearInterval(statusPoll);
      clearInterval(pollutionPoll);
      clearInterval(traitsPoll);
      Object.values(nudgeTimers.current).forEach(clearTimeout);
      es.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (error && !status) {
    return (
      <div style={{ textAlign: 'center', padding: 24, color: 'var(--ec-text-faint)', fontSize: 12 }}>
        LunaFM: {error}
      </div>
    );
  }

  if (!status) {
    return (
      <div style={{ textAlign: 'center', padding: 24, color: 'var(--ec-text-faint)', fontSize: 12 }}>
        Loading LunaFM…
      </div>
    );
  }

  if (!status.running) {
    return (
      <div style={{ textAlign: 'center', padding: 24, color: 'var(--ec-text-faint)', fontSize: 12 }}>
        LunaFM not running
      </div>
    );
  }

  const channels = status.channels || [];
  const totalEmissions = channels.reduce((s, c) => s + (c.emissions_last_hour || 0), 0);
  const spectral = status.spectral;
  const hasTraits = traits && Object.keys(traits).length > 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Station header */}
      <div style={{ textAlign: 'center', padding: '4px 0' }}>
        <div className="ec-font-display" style={{ fontSize: 22, fontWeight: 300, color: 'var(--ec-accent-voice)' }}>
          ◉ LunaFM
        </div>
        <div style={{ fontSize: 10, color: 'var(--ec-text-faint)', marginTop: 2 }}>
          {channels.length} channels · {totalEmissions}/hr · {fmtUptime(status.uptime_s)} up
          {status.preempted && <span style={{ color: '#ef4444', marginLeft: 6 }}>· PREEMPTED</span>}
        </div>
        {spectral && spectral.last_computed && (
          <div style={{ fontSize: 9, color: 'var(--ec-text-faint)', marginTop: 2 }}>
            spectral: {spectral.node_count}n · {spectral.edge_count}e · λ₁={Number(spectral.fiedler).toExponential(1)}
          </div>
        )}
      </div>

      {/* Channel cards */}
      <div style={{ display: 'flex', gap: 6 }}>
        {channels.map((c) => (
          <ChannelCard key={c.id} channel={c} />
        ))}
      </div>

      {/* Pollution */}
      {pollution?.buckets && (
        <div className="ec-glass-interactive" style={{ padding: '8px 10px', borderRadius: 6 }}>
          <div className="ec-font-label" style={{ fontSize: 9, color: 'var(--ec-text-faint)', marginBottom: 6 }}>
            POLLUTION
          </div>
          {['1h', '24h', 'total'].map((bucket) => {
            const b = pollution.buckets[bucket] || {};
            const entries = Object.entries(b);
            const total = entries.reduce((s, [, v]) => s + v, 0);
            return (
              <div key={bucket} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 10, color: 'var(--ec-text-secondary)', marginBottom: 2 }}>
                <span style={{ width: 32, color: 'var(--ec-text-faint)' }}>{bucket}</span>
                <span style={{ width: 28, textAlign: 'right' }}>{total}</span>
                <span style={{ flex: 1, color: 'var(--ec-text-faint)', fontSize: 9 }}>
                  {entries.length === 0 ? '—' : entries.map(([k, v]) => `${k}:${v}`).join(' · ')}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {/* Thought stream */}
      <div className="ec-glass-interactive" style={{ padding: '10px 12px', borderRadius: 6 }}>
        <div className="ec-font-label" style={{ fontSize: 9, color: 'var(--ec-text-faint)', marginBottom: 8 }}>
          THOUGHT STREAM
        </div>
        {artifacts.length === 0 ? (
          <div style={{ fontSize: 11, color: 'var(--ec-text-faint)', textAlign: 'center', padding: 8 }}>
            No artifacts yet
          </div>
        ) : (
          <div style={{ maxHeight: 260, overflowY: 'auto' }}>
            {artifacts.map((a) => (
              <ArtifactRow key={a.id} a={a} />
            ))}
          </div>
        )}
      </div>

      {/* Tuning — Section 3 */}
      <div className="ec-glass-interactive" style={{ padding: '10px 12px', borderRadius: 6 }}>
        <div className="ec-font-label" style={{ fontSize: 9, color: 'var(--ec-text-faint)', marginBottom: 8 }}>
          TUNING
        </div>

        {/* Aperture pills */}
        <div style={{ marginBottom: 10 }}>
          <div style={{ fontSize: 9, color: 'var(--ec-text-faint)', marginBottom: 4 }}>
            APERTURE {aperture && <span style={{ color: 'var(--ec-text-secondary)' }}>σ={aperture.sigma.toFixed(2)}</span>}
          </div>
          <div style={{ display: 'flex', gap: 4 }}>
            {APERTURE_PRESETS.map((p) => {
              const active = aperture?.preset === p.key;
              return (
                <div
                  key={p.key}
                  style={{
                    flex: 1,
                    textAlign: 'center',
                    padding: '4px 2px',
                    borderRadius: 4,
                    fontSize: 8,
                    fontWeight: active ? 700 : 400,
                    background: active ? 'color-mix(in srgb, var(--ec-accent-voice) 20%, transparent)' : 'rgba(255,255,255,0.03)',
                    color: active ? 'var(--ec-accent-voice)' : 'var(--ec-text-faint)',
                    border: active ? '1px solid var(--ec-accent-voice)' : '1px solid transparent',
                  }}
                >
                  {p.key}
                </div>
              );
            })}
          </div>
        </div>

        {/* Trait bars */}
        <div style={{ fontSize: 9, color: 'var(--ec-text-faint)', marginBottom: 4 }}>COGNITIVE STATE</div>
        {hasTraits ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {TRAIT_NAMES.map((name) => (
              <TraitBar
                key={name}
                name={name}
                value={traits[name] ?? 0.5}
                nudge={nudges[name]}
              />
            ))}
          </div>
        ) : (
          <div style={{ fontSize: 10, color: 'var(--ec-text-faint)', textAlign: 'center', padding: 6 }}>
            No LunaScript state yet — send a message to initialize
          </div>
        )}
      </div>
    </div>
  );
}
