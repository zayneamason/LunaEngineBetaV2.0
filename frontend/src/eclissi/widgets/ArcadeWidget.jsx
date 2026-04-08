import React, { useState, useEffect, useCallback } from 'react';

const SLIDERS = [
  { key: 'spin_speed',           label: 'Spin Speed',        min: 0.005, max: 0.12,  step: 0.005, fmt: v => v.toFixed(3) },
  { key: 'fire_cooldown_mult',   label: 'Fire Rate',         min: 0.2,   max: 3.0,   step: 0.1,   fmt: v => `${v.toFixed(1)}x` },
  { key: 'bullet_speed_mult',    label: 'Bullet Speed',      min: 0.3,   max: 3.0,   step: 0.1,   fmt: v => `${v.toFixed(1)}x` },
  { key: 'alien_speed_mult',     label: 'Alien Speed',       min: 0.2,   max: 3.0,   step: 0.1,   fmt: v => `${v.toFixed(1)}x` },
  { key: 'spawn_rate_mult',      label: 'Spawn Rate',        min: 0.3,   max: 3.0,   step: 0.1,   fmt: v => `${v.toFixed(1)}x` },
  { key: 'hp',                   label: 'Lives',             min: 1,     max: 10,    step: 1,     fmt: v => String(Math.round(v)) },
  { key: 'timer_secs',           label: 'Timer',             min: 30,    max: 600,   step: 10,    fmt: v => `${Math.round(v)}s` },
  { key: 'savage_charge_secs',   label: 'Savage Charge',     min: 5,     max: 120,   step: 5,     fmt: v => `${Math.round(v)}s` },
  { key: 'savage_duration_secs', label: 'Savage Duration',   min: 3,     max: 30,    step: 1,     fmt: v => `${Math.round(v)}s` },
  { key: 'combo_decay_secs',     label: 'Combo Decay',       min: 0.5,   max: 10,    step: 0.5,   fmt: v => `${v.toFixed(1)}s` },
  { key: 'weapon_cycle_secs',    label: 'Weapon Cycle',      min: 5,     max: 120,   step: 5,     fmt: v => `${Math.round(v)}s` },
];

const SAVAGE_DEFAULTS = {
  spin_speed: 0.045, fire_cooldown_mult: 0.6, bullet_speed_mult: 1.5,
  alien_speed_mult: 1.3, spawn_rate_mult: 1.6, hp: 3, timer_secs: 120,
  savage_charge_secs: 25, savage_duration_secs: 12, combo_decay_secs: 3.5,
  weapon_cycle_secs: 20, screen_shake: true,
};

const api = (path, body) => fetch(path, {
  method: 'POST', headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
}).then(r => r.json()).catch(() => ({}));

export default function ArcadeWidget() {
  const [games, setGames] = useState([]);
  const [status, setStatus] = useState(null);
  const [launching, setLaunching] = useState(false);
  const [tune, setTune] = useState(null);
  const [shake, setShake] = useState(true);
  const [presets, setPresets] = useState([]);
  const [presetName, setPresetName] = useState('');
  const [saveMsg, setSaveMsg] = useState('');

  // Poll games + status
  useEffect(() => {
    const poll = async () => {
      try {
        const [gRes, sRes] = await Promise.all([
          fetch('/api/arcade/games'), fetch('/api/arcade/status'),
        ]);
        if (gRes.ok) setGames((await gRes.json()).games || []);
        if (sRes.ok) setStatus(await sRes.json());
      } catch {}
    };
    poll();
    const id = setInterval(poll, 3000);
    return () => clearInterval(id);
  }, []);

  // Load tune + presets on mount
  useEffect(() => {
    fetch('/api/arcade/tune').then(r => r.json()).then(d => {
      if (!d.error) { setTune(d); setShake(d.screen_shake !== false); }
    }).catch(() => {});
    fetch('/api/arcade/presets').then(r => r.json()).then(d => {
      setPresets(d.presets || []);
    }).catch(() => {});
  }, []);

  const pushTune = useCallback((patch) => {
    setTune(prev => {
      const next = { ...prev, ...patch };
      api('/api/arcade/tune', patch);
      return next;
    });
  }, []);

  const launch = async (gameId) => {
    setLaunching(true);
    try {
      const data = await api('/api/arcade/launch', { game_id: gameId });
      if (data.success) setStatus({ running: true, game: { game_id: gameId, title: data.game, pid: data.pid } });
    } finally { setLaunching(false); }
  };

  const stop = async () => {
    await api('/api/arcade/stop', {});
    setStatus({ running: false, game: null });
  };

  const savePreset = async () => {
    if (!presetName.trim()) return;
    const res = await api('/api/arcade/presets/save', { name: presetName.trim() });
    if (res.success) {
      setSaveMsg(`Saved "${res.name}"`);
      setPresetName('');
      const p = await fetch('/api/arcade/presets').then(r => r.json());
      setPresets(p.presets || []);
      setTimeout(() => setSaveMsg(''), 2000);
    }
  };

  const loadPreset = async (name) => {
    const res = await api('/api/arcade/presets/load', { name });
    if (res.success && res.tune) {
      setTune(res.tune);
      setShake(res.tune.screen_shake !== false);
    }
  };

  const deletePreset = async (name) => {
    await api('/api/arcade/presets/delete', { name });
    setPresets(prev => prev.filter(p => p.name !== name));
  };

  const isRunning = status?.running;
  const currentGame = status?.game;

  const sliderCss = {
    width: '100%', height: 4, appearance: 'none', WebkitAppearance: 'none',
    background: 'var(--ec-border)', borderRadius: 2, outline: 'none', cursor: 'pointer',
    accentColor: 'var(--ec-accent-qa)',
  };

  const btnCss = (color, bg) => ({
    padding: '4px 10px', borderRadius: 4, border: `1px solid ${color}33`,
    background: bg, color, cursor: 'pointer', fontSize: 9, fontWeight: 600,
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 11 }}>
      {/* ── Status ── */}
      <div style={{ textAlign: 'center', padding: '4px 0' }}>
        <div className="ec-font-display" style={{
          fontSize: 13, fontWeight: 600, letterSpacing: '0.08em',
          color: isRunning ? '#22c55e' : 'var(--ec-text-faint)',
        }}>
          {isRunning ? 'GAME RUNNING' : 'READY'}
        </div>
        {isRunning && currentGame && (
          <div style={{ fontSize: 9, color: 'var(--ec-text-soft)', marginTop: 2 }}>
            {currentGame.title} &middot; PID {currentGame.pid}
          </div>
        )}
      </div>

      {/* ── Launch / Stop ── */}
      {isRunning ? (
        <button onClick={stop} style={btnCss('#ef4444', 'rgba(248,113,113,0.1)')}>STOP GAME</button>
      ) : (
        games.map(g => (
          <button key={g.id} onClick={() => launch(g.id)} disabled={launching}
            style={btnCss(launching ? 'var(--ec-text-faint)' : '#22c55e',
              launching ? 'rgba(255,255,255,0.03)' : 'rgba(34,197,94,0.12)')}>
            {launching ? '...' : `LAUNCH ${g.title.toUpperCase()}`}
          </button>
        ))
      )}
      {games.length === 0 && (
        <div style={{ fontSize: 9, color: 'var(--ec-text-faint)', textAlign: 'center' }}>pip install pyxel</div>
      )}

      {/* ── TUNING SLIDERS ── */}
      {tune && (
        <div className="ec-glass-interactive" style={{ padding: '8px 10px', borderRadius: 6 }}>
          <div className="ec-font-label" style={{ fontSize: 9, color: 'var(--ec-text-faint)', marginBottom: 6, letterSpacing: '0.1em' }}>
            TUNING &middot; LIVE
          </div>

          {SLIDERS.map(s => {
            const val = tune[s.key] ?? s.min;
            return (
              <div key={s.key} style={{ marginBottom: 5 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 1 }}>
                  <span style={{ fontSize: 9, color: 'var(--ec-text-soft)' }}>{s.label}</span>
                  <span style={{ fontSize: 9, color: 'var(--ec-text)', fontFamily: "'JetBrains Mono',monospace" }}>
                    {s.fmt(val)}
                  </span>
                </div>
                <input type="range" min={s.min} max={s.max} step={s.step} value={val}
                  onChange={e => pushTune({ [s.key]: parseFloat(e.target.value) })}
                  style={sliderCss} />
              </div>
            );
          })}

          {/* Shake toggle */}
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 2, cursor: 'pointer' }}>
            <input type="checkbox" checked={shake}
              onChange={e => { setShake(e.target.checked); pushTune({ screen_shake: e.target.checked }); }}
              style={{ accentColor: 'var(--ec-accent-qa)' }} />
            <span style={{ fontSize: 9, color: 'var(--ec-text-soft)' }}>Screen Shake</span>
          </label>

          {/* Reset defaults */}
          <button onClick={() => { pushTune(SAVAGE_DEFAULTS); setTune(prev => ({ ...prev, ...SAVAGE_DEFAULTS })); setShake(true); }}
            style={{ marginTop: 6, width: '100%', padding: '4px 0', borderRadius: 4,
              border: '1px solid var(--ec-border)', background: 'transparent',
              color: 'var(--ec-text-faint)', cursor: 'pointer', fontSize: 9 }}>
            RESET DEFAULTS
          </button>
        </div>
      )}

      {/* ── PRESETS ── */}
      {tune && (
        <div className="ec-glass-interactive" style={{ padding: '8px 10px', borderRadius: 6 }}>
          <div className="ec-font-label" style={{ fontSize: 9, color: 'var(--ec-text-faint)', marginBottom: 6, letterSpacing: '0.1em' }}>
            PRESETS
          </div>

          {/* Save current */}
          <div style={{ display: 'flex', gap: 4, marginBottom: 6 }}>
            <input
              type="text" placeholder="preset name..." value={presetName}
              onChange={e => setPresetName(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && savePreset()}
              style={{
                flex: 1, padding: '4px 8px', borderRadius: 4,
                border: '1px solid var(--ec-border)', background: 'rgba(255,255,255,0.03)',
                color: 'var(--ec-text)', fontSize: 10, outline: 'none',
                fontFamily: "'JetBrains Mono',monospace",
              }}
            />
            <button onClick={savePreset} disabled={!presetName.trim()}
              style={btnCss(presetName.trim() ? '#c084fc' : 'var(--ec-text-faint)',
                presetName.trim() ? 'rgba(192,132,252,0.12)' : 'transparent')}>
              SAVE
            </button>
          </div>
          {saveMsg && <div style={{ fontSize: 9, color: '#22c55e', marginBottom: 4 }}>{saveMsg}</div>}

          {/* Preset list */}
          {presets.length === 0 && (
            <div style={{ fontSize: 9, color: 'var(--ec-text-faint)' }}>No saved presets</div>
          )}
          {presets.map(p => (
            <div key={p.name} style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '3px 0', borderBottom: '1px solid rgba(255,255,255,0.04)',
            }}>
              <span style={{ fontSize: 10, color: 'var(--ec-text)', fontFamily: "'JetBrains Mono',monospace" }}>
                {p.name}
              </span>
              <div style={{ display: 'flex', gap: 4 }}>
                <button onClick={() => loadPreset(p.name)}
                  style={btnCss('#818cf8', 'rgba(129,140,248,0.1)')}>LOAD</button>
                <button onClick={() => deletePreset(p.name)}
                  style={btnCss('#ef4444', 'transparent')}>X</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
