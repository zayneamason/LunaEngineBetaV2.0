import React, { useState, useEffect } from 'react';

export function OrbSettingsPanel({ data, onUpdate, onClose }) {
  const [values, setValues] = useState(data?.current || {});
  const ranges = data?.ranges || {};
  const animations = data?.animations || [];
  const colorPresets = data?.color_presets || {};

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

  return (
    <div className="settings-panel glass-card" style={{
      padding: '1rem',
      minWidth: 300,
      background: 'rgba(0, 0, 0, 0.8)',
      backdropFilter: 'blur(10px)',
      borderRadius: '12px',
      border: '1px solid rgba(255, 255, 255, 0.1)',
      color: 'white',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
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

      {/* Animation selector */}
      <div style={{ marginBottom: '1rem' }}>
        <label style={{ fontSize: '0.8rem', opacity: 0.7 }}>Animation</label>
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
            marginTop: '0.25rem',
          }}
        >
          {animations.map(a => <option key={a} value={a}>{a}</option>)}
        </select>
      </div>

      {/* Color presets */}
      <div style={{ marginBottom: '1rem' }}>
        <label style={{ fontSize: '0.8rem', opacity: 0.7 }}>Color</label>
        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.25rem', flexWrap: 'wrap' }}>
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
      </div>

      {/* Sliders */}
      {Object.entries(ranges).map(([key, config]) => (
        <div key={key} style={{ marginBottom: '0.75rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem' }}>
            <label>{config.label}</label>
            <span style={{ opacity: 0.7 }}>{values[key]?.toFixed?.(3) || values[key]}</span>
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

      {/* Preview text */}
      <div style={{ fontSize: '0.7rem', opacity: 0.5, textAlign: 'center', marginTop: '0.5rem' }}>
        Changes apply in real-time
      </div>
    </div>
  );
}

export default OrbSettingsPanel;
