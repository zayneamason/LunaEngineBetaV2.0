import React, { useState, useEffect } from 'react';
import { ORB_FOLLOW_CONFIG, ORB_PHYSICS_RANGES, updateOrbPhysics } from '../config/orbFollow';

export function OrbSettingsPanel({ data, onUpdate, onClose }) {
  const [values, setValues] = useState(data?.current || {});
  const ranges = data?.ranges || {};
  const animations = data?.animations || [];
  const colorPresets = data?.color_presets || {};

  // Physics state — read live from the mutable config
  const [physics, setPhysics] = useState(() => {
    const p = {};
    for (const key of Object.keys(ORB_PHYSICS_RANGES)) p[key] = ORB_FOLLOW_CONFIG[key];
    return p;
  });

  useEffect(() => {
    if (data?.current) setValues(data.current);
  }, [data]);

  const handleChange = (key, value) => {
    const parsed = typeof value === 'string' && !isNaN(parseFloat(value))
      ? parseFloat(value)
      : value;
    const newValues = { ...values, [key]: parsed };
    setValues(newValues);
    onUpdate(newValues);
  };

  const handlePhysics = (key, raw) => {
    const val = parseFloat(raw);
    const next = { ...physics, [key]: val };
    setPhysics(next);
    updateOrbPhysics({ [key]: val });
  };

  const sectionLabel = { fontSize: '0.75rem', opacity: 0.5, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '0.5rem', marginTop: '1rem' };

  return (
    <div className="settings-panel glass-card" style={{
      padding: '1rem',
      minWidth: 320,
      maxHeight: '80vh',
      overflowY: 'auto',
      background: 'rgba(0, 0, 0, 0.85)',
      backdropFilter: 'blur(12px)',
      borderRadius: '12px',
      border: '1px solid rgba(255, 255, 255, 0.1)',
      color: 'white',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
        <h3 style={{ margin: 0 }}>Orb Settings</h3>
        <button
          onClick={onClose}
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            color: 'white',
            fontSize: '1.2rem',
          }}
        >
          x
        </button>
      </div>

      {/* === Physics Tuning === */}
      <div style={sectionLabel}>Drift Physics</div>
      {Object.entries(ORB_PHYSICS_RANGES).map(([key, cfg]) => (
        <div key={key} style={{ marginBottom: '0.6rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem' }}>
            <label>{cfg.label}</label>
            <span style={{ opacity: 0.6, fontFamily: 'monospace' }}>
              {physics[key]?.toFixed?.(cfg.step < 0.01 ? 4 : cfg.step < 1 ? 3 : 1)}
            </span>
          </div>
          <input
            type="range"
            min={cfg.min}
            max={cfg.max}
            step={cfg.step}
            value={physics[key] ?? cfg.min}
            onChange={(e) => handlePhysics(key, e.target.value)}
            style={{ width: '100%', accentColor: '#a78bfa' }}
          />
        </div>
      ))}

      {/* === Animation selector (from backend) === */}
      {animations.length > 0 && (
        <>
          <div style={sectionLabel}>Animation</div>
          <select
            value={values.animation || 'idle'}
            onChange={(e) => handleChange('animation', e.target.value)}
            style={{
              width: '100%',
              padding: '0.5rem',
              borderRadius: '4px',
              border: '1px solid rgba(255,255,255,0.2)',
              background: 'rgba(0,0,0,0.3)',
              color: 'inherit',
            }}
          >
            {animations.map(a => <option key={a} value={a}>{a}</option>)}
          </select>
        </>
      )}

      {/* === Color presets (from backend) === */}
      {Object.keys(colorPresets).length > 0 && (
        <>
          <div style={sectionLabel}>Color</div>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            {Object.entries(colorPresets).map(([name, hex]) => (
              <button
                key={name}
                onClick={() => handleChange('color', hex)}
                title={name}
                style={{
                  width: 28,
                  height: 28,
                  borderRadius: '50%',
                  border: values.color === hex ? '2px solid white' : '2px solid transparent',
                  background: hex,
                  cursor: 'pointer',
                }}
              />
            ))}
            <input
              type="color"
              value={values.color || '#a78bfa'}
              onChange={(e) => handleChange('color', e.target.value)}
              style={{ width: 28, height: 28, border: 'none', borderRadius: '50%', cursor: 'pointer' }}
            />
          </div>
        </>
      )}

      {/* === Backend sliders (from /slash/orb-settings) === */}
      {Object.keys(ranges).length > 0 && (
        <>
          <div style={sectionLabel}>Renderer</div>
          {Object.entries(ranges).map(([key, config]) => (
            <div key={key} style={{ marginBottom: '0.6rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem' }}>
                <label>{config.label}</label>
                <span style={{ opacity: 0.6 }}>{values[key]?.toFixed?.(3) || values[key]}</span>
              </div>
              <input
                type="range"
                min={config.min}
                max={config.max}
                step={config.step}
                value={values[key] || config.min}
                onChange={(e) => handleChange(key, e.target.value)}
                style={{ width: '100%', accentColor: values.color || '#a78bfa' }}
              />
            </div>
          ))}
        </>
      )}

      <div style={{ fontSize: '0.65rem', opacity: 0.4, textAlign: 'center', marginTop: '0.75rem' }}>
        Changes apply in real-time
      </div>
    </div>
  );
}

export default OrbSettingsPanel;
