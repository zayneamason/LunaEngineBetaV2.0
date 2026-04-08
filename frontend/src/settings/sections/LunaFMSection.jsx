import React, { useState, useEffect, useCallback } from 'react';

const CHANNEL_COLORS = {
  news: '#f87171',
  history: '#2dd4bf',
  entertainment: '#fbbf24',
};

export default function LunaFMSection() {
  const [data, setData] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    try {
      const r = await fetch('/api/settings/lunafm');
      if (r.ok) {
        setData(await r.json());
        setError(null);
      } else {
        setError('Failed to load LunaFM settings');
      }
    } catch (e) {
      setError(e.message);
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, [load]);

  const save = async (update) => {
    setSaving(true);
    try {
      const r = await fetch('/api/settings/lunafm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(update),
      });
      if (r.ok) {
        setData(await r.json());
      } else {
        setError('Save failed');
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  if (error) {
    return <div style={{ padding: 20, color: '#ef4444' }}>LunaFM: {error}</div>;
  }
  if (!data) {
    return <div style={{ padding: 20, color: 'var(--ec-text-faint)' }}>Loading LunaFM settings…</div>;
  }

  const station = data.station || {};
  const channels = data.channels || [];
  const runtime = data.runtime || null;

  return (
    <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 24, overflowY: 'auto' }}>
      <div>
        <h2 className="ec-font-display" style={{ fontSize: 24, margin: 0 }}>◉ LunaFM</h2>
        <div style={{ color: 'var(--ec-text-faint)', fontSize: 11, marginTop: 4 }}>
          Background cognitive broadcast — {channels.length} channels
          {runtime && (
            <span style={{ marginLeft: 8 }}>
              · {runtime.running ? 'running' : 'stopped'}
              {runtime.preempted && ' · preempted'}
            </span>
          )}
        </div>
      </div>

      {/* Station controls */}
      <section className="ec-glass-interactive" style={{ padding: 16, borderRadius: 8 }}>
        <div className="ec-font-label" style={{ fontSize: 10, color: 'var(--ec-text-faint)', marginBottom: 12 }}>
          STATION
        </div>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <span style={{ fontSize: 13 }}>Enabled</span>
          <input
            type="checkbox"
            checked={station.enabled !== false}
            disabled={saving}
            onChange={(e) => save({ enabled: e.target.checked })}
          />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
          <span style={{ fontSize: 13 }}>Max nodes / hour</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1, maxWidth: 280 }}>
            <input
              type="range"
              min="5"
              max="100"
              step="5"
              value={station.max_nodes_per_hour ?? 20}
              disabled={saving}
              onChange={(e) => save({ max_nodes_per_hour: parseInt(e.target.value, 10) })}
              style={{ flex: 1 }}
            />
            <span style={{ width: 32, textAlign: 'right', fontSize: 12, color: 'var(--ec-text-secondary)' }}>
              {station.max_nodes_per_hour ?? 20}
            </span>
          </div>
        </div>
      </section>

      {/* Channels */}
      <section className="ec-glass-interactive" style={{ padding: 16, borderRadius: 8 }}>
        <div className="ec-font-label" style={{ fontSize: 10, color: 'var(--ec-text-faint)', marginBottom: 12 }}>
          CHANNELS
        </div>
        {channels.map((c) => {
          const color = CHANNEL_COLORS[c.id] || 'var(--ec-accent-luna)';
          const live = runtime?.channels?.find((rc) => rc.id === c.id);
          return (
            <div
              key={c.id}
              style={{
                padding: '12px 0',
                borderTop: '1px solid var(--ec-border)',
                display: 'flex',
                flexDirection: 'column',
                gap: 8,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ width: 10, height: 10, borderRadius: '50%', background: color }} />
                <span style={{ fontWeight: 600, fontSize: 13 }}>{c.name || c.id}</span>
                {live && (
                  <span style={{ fontSize: 10, color: 'var(--ec-text-faint)', marginLeft: 8 }}>
                    {live.state} · {live.emissions_last_hour}/hr
                  </span>
                )}
                <div style={{ flex: 1 }} />
                <input
                  type="checkbox"
                  checked={c.enabled !== false}
                  disabled={saving}
                  onChange={(e) => save({ channels: { [c.id]: { enabled: e.target.checked } } })}
                />
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, paddingLeft: 18 }}>
                <span style={{ width: 72, fontSize: 11, color: 'var(--ec-text-faint)' }}>interval</span>
                <input
                  type="range"
                  min="5"
                  max="1200"
                  step="5"
                  value={c.interval_s}
                  disabled={saving || c.enabled === false}
                  onChange={(e) =>
                    save({ channels: { [c.id]: { interval_s: parseFloat(e.target.value) } } })
                  }
                  style={{ flex: 1, maxWidth: 280 }}
                />
                <span style={{ width: 48, textAlign: 'right', fontSize: 11, color: 'var(--ec-text-secondary)' }}>
                  {c.interval_s < 60 ? `${c.interval_s}s` : `${Math.round(c.interval_s / 60)}m`}
                </span>
              </div>
            </div>
          );
        })}
      </section>
    </div>
  );
}
