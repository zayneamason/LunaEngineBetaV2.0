import React, { useState, useEffect } from 'react';

const SLIDER_STYLE = {
  width: '100%',
  accentColor: '#a78bfa',
};

export function VoiceTuningPanel({ data, onUpdate, onClose }) {
  const [values, setValues] = useState(data?.current || {});
  const ranges = data?.ranges || {};

  useEffect(() => {
    if (data?.current) setValues(data.current);
  }, [data]);

  const handleChange = (key, value) => {
    const newValues = { ...values, [key]: parseFloat(value) };
    setValues(newValues);
    onUpdate(newValues);
  };

  const applyPreset = async (presetName) => {
    await fetch(`/slash/emotion/${presetName}`);
    const newData = await fetch('/slash/voice-tuning').then(r => r.json());
    if (newData.data?.current) setValues(newData.data.current);
  };

  const testVoice = () => {
    fetch('/voice/speak', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: "Testing voice settings. How does this sound?" })
    });
  };

  return (
    <div className="tuning-panel glass-card" style={{
      padding: '1rem',
      minWidth: 300,
      background: 'rgba(0, 0, 0, 0.8)',
      backdropFilter: 'blur(10px)',
      borderRadius: '12px',
      border: '1px solid rgba(255, 255, 255, 0.1)',
      color: 'white',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
        <h3 style={{ margin: 0 }}>Voice Tuning</h3>
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

      {/* Presets */}
      <div style={{ marginBottom: '1rem' }}>
        <label style={{ fontSize: '0.8rem', opacity: 0.7 }}>Quick Presets</label>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginTop: '0.25rem' }}>
          {data?.presets?.map(p => (
            <button
              key={p}
              onClick={() => applyPreset(p)}
              style={{
                padding: '0.25rem 0.5rem',
                borderRadius: '4px',
                border: '1px solid rgba(255,255,255,0.2)',
                background: 'rgba(255,255,255,0.1)',
                color: 'inherit',
                cursor: 'pointer',
                fontSize: '0.75rem',
              }}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {/* Sliders */}
      {Object.entries(ranges).map(([key, config]) => (
        <div key={key} style={{ marginBottom: '1rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem' }}>
            <label>{config.label}</label>
            <span style={{ opacity: 0.7 }}>{values[key]?.toFixed(2)}</span>
          </div>
          <input
            type="range"
            min={config.min}
            max={config.max}
            step={config.step}
            value={values[key] || config.min}
            onChange={(e) => handleChange(key, e.target.value)}
            style={SLIDER_STYLE}
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.65rem', opacity: 0.5 }}>
            <span>{config.inverted ? 'Fast' : config.min}</span>
            <span>{config.inverted ? 'Slow' : config.max}</span>
          </div>
        </div>
      ))}

      {/* Test button */}
      <button
        onClick={testVoice}
        style={{
          width: '100%',
          padding: '0.5rem',
          borderRadius: '6px',
          border: 'none',
          background: '#a78bfa',
          color: 'white',
          cursor: 'pointer',
          fontWeight: 'bold',
        }}
      >
        Test Voice
      </button>
    </div>
  );
}

export default VoiceTuningPanel;
