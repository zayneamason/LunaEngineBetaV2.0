import React, { useState, useEffect } from 'react'
import { useObservatoryStore } from '../store'

const PARAM_META = {
  decay: { min: 0, max: 1, step: 0.05, label: 'Activation Decay' },
  min_activation: { min: 0, max: 1, step: 0.05, label: 'Min Activation' },
  max_hops: { min: 1, max: 5, step: 1, label: 'Max Hops' },
  token_budget: { min: 500, max: 10000, step: 500, label: 'Token Budget' },
  sim_threshold: { min: 0, max: 1, step: 0.05, label: 'Vector Sim Threshold' },
  fts5_limit: { min: 5, max: 100, step: 5, label: 'FTS5 Result Limit' },
  vector_limit: { min: 5, max: 100, step: 5, label: 'Vector Result Limit' },
  rrf_k: { min: 1, max: 200, step: 10, label: 'RRF k Parameter' },
  cluster_sim_threshold: { min: 0.5, max: 1, step: 0.01, label: 'Cluster Sim Threshold' },
}

export default function TuningPanel() {
  const { params, fetchConfig } = useObservatoryStore()
  const [localParams, setLocalParams] = useState({})

  useEffect(() => {
    setLocalParams(params)
  }, [params])

  const handleChange = (key, value) => {
    setLocalParams(prev => ({ ...prev, [key]: value }))
  }

  return (
    <div style={{
      background: '#0a0a14', border: '1px solid #1a1a2e',
      borderRadius: 6, padding: 16,
    }}>
      <div style={{ color: '#555', fontSize: 10, letterSpacing: 1, marginBottom: 12 }}>
        RETRIEVAL PARAMETERS
      </div>
      {Object.entries(PARAM_META).map(([key, meta]) => (
        <div key={key} style={{ marginBottom: 10 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
            <label style={{ color: '#888', fontSize: 11 }}>{meta.label}</label>
            <span style={{ color: '#7dd3fc', fontSize: 11 }}>
              {localParams[key] ?? '\u2014'}
            </span>
          </div>
          <input
            type="range"
            min={meta.min}
            max={meta.max}
            step={meta.step}
            value={localParams[key] ?? meta.min}
            onChange={e => handleChange(key, Number(e.target.value))}
            style={{ width: '100%', accentColor: '#7dd3fc' }}
          />
        </div>
      ))}
    </div>
  )
}
