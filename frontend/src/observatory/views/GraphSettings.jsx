import React from 'react'
import { useObservatoryStore } from '../store'

const NODE_SHAPES = [
  { value: 'circle', label: 'Circle' },
  { value: 'diamond', label: 'Diamond' },
  { value: 'square', label: 'Square' },
  { value: 'hexagon', label: 'Hexagon' },
  { value: 'ring', label: 'Ring (Hollow)' },
]

const PRESETS = {
  default: { chargeStrength: -30, linkDistance: 30, radialStrength: 0, radialRadius: 200, collideRadius: 0, alphaDecay: 0.02, velocityDecay: 0.3, cooldownTicks: 100 },
  spherical: { chargeStrength: -120, linkDistance: 40, radialStrength: 0.08, radialRadius: 220, collideRadius: 8, alphaDecay: 0.015, velocityDecay: 0.3, cooldownTicks: 200 },
  tight: { chargeStrength: -60, linkDistance: 20, radialStrength: 0.15, radialRadius: 150, collideRadius: 6, alphaDecay: 0.02, velocityDecay: 0.4, cooldownTicks: 150 },
  exploded: { chargeStrength: -300, linkDistance: 80, radialStrength: 0, radialRadius: 400, collideRadius: 12, alphaDecay: 0.01, velocityDecay: 0.2, cooldownTicks: 300 },
  clustered: { chargeStrength: -40, linkDistance: 15, radialStrength: 0.03, radialRadius: 180, collideRadius: 5, alphaDecay: 0.025, velocityDecay: 0.35, cooldownTicks: 120 },
}

const SLIDERS = [
  { key: 'chargeStrength', label: 'Charge Strength', min: -500, max: 0, step: 10, desc: 'Repulsion between nodes (more negative = more spread)' },
  { key: 'linkDistance', label: 'Link Distance', min: 5, max: 200, step: 5, desc: 'Ideal distance between connected nodes' },
  { key: 'radialStrength', label: 'Radial Strength', min: 0, max: 0.5, step: 0.01, desc: 'Force pulling nodes toward radial ring (0 = off)' },
  { key: 'radialRadius', label: 'Radial Radius', min: 50, max: 600, step: 10, desc: 'Radius of the radial constraint ring' },
  { key: 'collideRadius', label: 'Collision Radius', min: 0, max: 30, step: 1, desc: 'Minimum spacing between nodes (0 = off)' },
  { key: 'alphaDecay', label: 'Alpha Decay', min: 0.001, max: 0.1, step: 0.001, desc: 'How quickly the simulation cools down' },
  { key: 'velocityDecay', label: 'Velocity Decay', min: 0.05, max: 0.8, step: 0.05, desc: 'Damping — higher = nodes settle faster' },
  { key: 'cooldownTicks', label: 'Cooldown Ticks', min: 50, max: 500, step: 10, desc: 'Simulation steps before freezing' },
]

export default function GraphSettings() {
  const { graphSettings, setGraphSettings, galaxyNodeBudget, setGalaxyNodeBudget, recomputeLayout } = useObservatoryStore()
  const [recomputing, setRecomputing] = React.useState(false)

  const update = (key, value) => {
    setGraphSettings({ ...graphSettings, [key]: value })
  }

  const applyPreset = (name) => {
    const preset = PRESETS[name]
    if (preset) setGraphSettings({ ...graphSettings, ...preset })
  }

  const reheat = () => {
    setGraphSettings({ ...graphSettings, _reheat: Date.now() })
  }

  return (
    <div style={{
      height: '100%',
      overflow: 'auto',
      padding: 24,
      display: 'flex',
      gap: 24,
    }}>
      {/* Left column: Force tuning */}
      <div style={{ flex: 1, maxWidth: 480 }}>
        <div style={{ color: '#555', fontSize: 10, letterSpacing: 1, marginBottom: 16 }}>
          FORCE SIMULATION
        </div>

        {/* Presets */}
        <div style={{ marginBottom: 20 }}>
          <div style={{ color: '#888', fontSize: 11, marginBottom: 8 }}>Presets</div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {Object.keys(PRESETS).map(name => (
              <button
                key={name}
                onClick={() => applyPreset(name)}
                style={{
                  background: '#1a1a2e',
                  border: '1px solid #2a2a3e',
                  color: '#7dd3fc',
                  padding: '4px 12px',
                  borderRadius: 3,
                  cursor: 'pointer',
                  fontSize: 11,
                  fontFamily: 'inherit',
                  textTransform: 'capitalize',
                  transition: 'all 0.15s',
                }}
                onMouseEnter={e => { e.target.style.borderColor = '#7dd3fc'; e.target.style.background = '#1a1a3e' }}
                onMouseLeave={e => { e.target.style.borderColor = '#2a2a3e'; e.target.style.background = '#1a1a2e' }}
              >
                {name}
              </button>
            ))}
          </div>
        </div>

        {/* Sliders */}
        {SLIDERS.map(({ key, label, min, max, step, desc }) => (
          <div key={key} style={{ marginBottom: 14 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
              <label style={{ color: '#888', fontSize: 11 }}>{label}</label>
              <span style={{ color: '#7dd3fc', fontSize: 11, fontVariantNumeric: 'tabular-nums' }}>
                {graphSettings[key]}
              </span>
            </div>
            <input
              type="range"
              min={min}
              max={max}
              step={step}
              value={graphSettings[key]}
              onChange={e => update(key, Number(e.target.value))}
              style={{ width: '100%', accentColor: '#7dd3fc' }}
            />
            <div style={{ color: '#444', fontSize: 10, marginTop: 1 }}>{desc}</div>
          </div>
        ))}

        {/* Reheat button */}
        <button
          onClick={reheat}
          style={{
            background: '#22d3ee22',
            border: '1px solid #22d3ee44',
            color: '#22d3ee',
            padding: '8px 20px',
            borderRadius: 4,
            cursor: 'pointer',
            fontSize: 12,
            fontFamily: 'inherit',
            fontWeight: 600,
            marginTop: 8,
            transition: 'all 0.15s',
          }}
          onMouseEnter={e => { e.target.style.borderColor = '#22d3ee'; e.target.style.background = '#22d3ee33' }}
          onMouseLeave={e => { e.target.style.borderColor = '#22d3ee44'; e.target.style.background = '#22d3ee22' }}
        >
          REHEAT SIMULATION
        </button>
      </div>

      {/* Right column: Node style */}
      <div style={{ flex: 1, maxWidth: 400 }}>
        <div style={{ color: '#555', fontSize: 10, letterSpacing: 1, marginBottom: 16 }}>
          NODE STYLE
        </div>

        {/* Node shape */}
        <div style={{ marginBottom: 20 }}>
          <div style={{ color: '#888', fontSize: 11, marginBottom: 8 }}>Shape</div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {NODE_SHAPES.map(({ value, label }) => {
              const active = graphSettings.nodeShape === value
              return (
                <button
                  key={value}
                  onClick={() => update('nodeShape', value)}
                  style={{
                    background: active ? '#7dd3fc22' : '#1a1a2e',
                    border: `1px solid ${active ? '#7dd3fc' : '#2a2a3e'}`,
                    color: active ? '#7dd3fc' : '#888',
                    padding: '4px 12px',
                    borderRadius: 3,
                    cursor: 'pointer',
                    fontSize: 11,
                    fontFamily: 'inherit',
                    transition: 'all 0.15s',
                  }}
                >
                  {label}
                </button>
              )
            })}
          </div>
        </div>

        {/* Node size */}
        <div style={{ marginBottom: 14 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
            <label style={{ color: '#888', fontSize: 11 }}>Base Node Size</label>
            <span style={{ color: '#7dd3fc', fontSize: 11 }}>{graphSettings.nodeBaseSize}</span>
          </div>
          <input
            type="range" min={2} max={16} step={1}
            value={graphSettings.nodeBaseSize}
            onChange={e => update('nodeBaseSize', Number(e.target.value))}
            style={{ width: '100%', accentColor: '#7dd3fc' }}
          />
        </div>

        {/* Lock-in scale */}
        <div style={{ marginBottom: 14 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
            <label style={{ color: '#888', fontSize: 11 }}>Lock-in Size Scale</label>
            <span style={{ color: '#7dd3fc', fontSize: 11 }}>{graphSettings.lockInScale}</span>
          </div>
          <input
            type="range" min={0} max={20} step={1}
            value={graphSettings.lockInScale}
            onChange={e => update('lockInScale', Number(e.target.value))}
            style={{ width: '100%', accentColor: '#7dd3fc' }}
          />
          <div style={{ color: '#444', fontSize: 10, marginTop: 1 }}>
            How much lock-in score inflates node size
          </div>
        </div>

        {/* Show labels threshold */}
        <div style={{ marginBottom: 14 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
            <label style={{ color: '#888', fontSize: 11 }}>Label Zoom Threshold</label>
            <span style={{ color: '#7dd3fc', fontSize: 11 }}>{graphSettings.labelZoomThreshold}x</span>
          </div>
          <input
            type="range" min={0.5} max={5} step={0.25}
            value={graphSettings.labelZoomThreshold}
            onChange={e => update('labelZoomThreshold', Number(e.target.value))}
            style={{ width: '100%', accentColor: '#7dd3fc' }}
          />
          <div style={{ color: '#444', fontSize: 10, marginTop: 1 }}>
            Zoom level at which node labels appear (lower = always visible)
          </div>
        </div>

        {/* Show lock-in rings */}
        <div style={{ marginBottom: 14 }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={graphSettings.showLockInRings}
              onChange={e => update('showLockInRings', e.target.checked)}
              style={{ accentColor: '#7dd3fc' }}
            />
            <span style={{ color: '#888', fontSize: 11 }}>Show lock-in rings</span>
          </label>
        </div>

        {/* Show activation glow */}
        <div style={{ marginBottom: 14 }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={graphSettings.showActivationGlow}
              onChange={e => update('showActivationGlow', e.target.checked)}
              style={{ accentColor: '#7dd3fc' }}
            />
            <span style={{ color: '#888', fontSize: 11 }}>Show activation glow</span>
          </label>
        </div>

        {/* Link opacity */}
        <div style={{ marginBottom: 14 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
            <label style={{ color: '#888', fontSize: 11 }}>Link Opacity</label>
            <span style={{ color: '#7dd3fc', fontSize: 11 }}>{graphSettings.linkOpacity}</span>
          </div>
          <input
            type="range" min={0} max={1} step={0.05}
            value={graphSettings.linkOpacity}
            onChange={e => update('linkOpacity', Number(e.target.value))}
            style={{ width: '100%', accentColor: '#7dd3fc' }}
          />
        </div>

        {/* Link width scale */}
        <div style={{ marginBottom: 14 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
            <label style={{ color: '#888', fontSize: 11 }}>Link Width Scale</label>
            <span style={{ color: '#7dd3fc', fontSize: 11 }}>{graphSettings.linkWidthScale}</span>
          </div>
          <input
            type="range" min={0.1} max={5} step={0.1}
            value={graphSettings.linkWidthScale}
            onChange={e => update('linkWidthScale', Number(e.target.value))}
            style={{ width: '100%', accentColor: '#7dd3fc' }}
          />
        </div>

        {/* Globe section */}
        <div style={{ color: '#555', fontSize: 10, letterSpacing: 1, marginTop: 24, marginBottom: 16 }}>
          GLOBE
        </div>

        {/* Globe style */}
        <div style={{ marginBottom: 20 }}>
          <div style={{ color: '#888', fontSize: 11, marginBottom: 8 }}>Globe Style</div>
          <div style={{ display: 'flex', gap: 6 }}>
            {['solid', 'wireframe', 'none'].map(style => {
              const active = graphSettings.globeStyle === style
              return (
                <button
                  key={style}
                  onClick={() => update('globeStyle', style)}
                  style={{
                    background: active ? '#7dd3fc22' : '#1a1a2e',
                    border: `1px solid ${active ? '#7dd3fc' : '#2a2a3e'}`,
                    color: active ? '#7dd3fc' : '#888',
                    padding: '4px 12px',
                    borderRadius: 3,
                    cursor: 'pointer',
                    fontSize: 11,
                    fontFamily: 'inherit',
                    textTransform: 'capitalize',
                    transition: 'all 0.15s',
                  }}
                >
                  {style}
                </button>
              )
            })}
          </div>
        </div>

        {/* Auto rotate */}
        <div style={{ marginBottom: 14 }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={graphSettings.autoRotate}
              onChange={e => update('autoRotate', e.target.checked)}
              style={{ accentColor: '#7dd3fc' }}
            />
            <span style={{ color: '#888', fontSize: 11 }}>Auto rotate</span>
          </label>
        </div>

        {/* Phantom count */}
        <div style={{ marginBottom: 14 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
            <label style={{ color: '#888', fontSize: 11 }}>Phantom Particles</label>
            <span style={{ color: '#7dd3fc', fontSize: 11 }}>{graphSettings.phantomCount}</span>
          </div>
          <input
            type="range" min={0} max={5000} step={250}
            value={graphSettings.phantomCount}
            onChange={e => update('phantomCount', Number(e.target.value))}
            style={{ width: '100%', accentColor: '#7dd3fc' }}
          />
          <div style={{ color: '#444', fontSize: 10, marginTop: 1 }}>
            Background particles on globe (0 = none, higher = denser field)
          </div>
        </div>

        {/* Particles & Physics section */}
        <div style={{ color: '#555', fontSize: 10, letterSpacing: 1, marginTop: 24, marginBottom: 16 }}>
          PARTICLES &amp; PHYSICS
        </div>

        {[
          { key: 'rotationSpeed', label: 'Rotation Speed', min: 0, max: 5, step: 0.1, desc: 'Auto-rotation speed multiplier (0 = frozen, 5 = fast)' },
          { key: 'momentumDecay', label: 'Momentum Decay', min: 0.85, max: 0.995, step: 0.005, desc: 'Drag momentum fade (lower = stops fast, higher = floaty)' },
          { key: 'phantomDrift', label: 'Phantom Drift', min: 0, max: 5, step: 0.1, desc: 'Background particle movement speed' },
          { key: 'phantomAlpha', label: 'Phantom Brightness', min: 0, max: 3, step: 0.1, desc: 'Phantom particle opacity multiplier' },
          { key: 'phantomSize', label: 'Phantom Size', min: 0.2, max: 4, step: 0.1, desc: 'Phantom particle size multiplier' },
          { key: 'twinkleSpeed', label: 'Twinkle Speed', min: 0, max: 5, step: 0.1, desc: 'Phantom twinkle animation speed' },
          { key: 'clusterScale', label: 'Node Scale', min: 0.3, max: 4, step: 0.1, desc: 'Cluster / node dot size multiplier' },
          { key: 'globeRadiusScale', label: 'Globe Radius', min: 0.3, max: 2, step: 0.05, desc: 'Globe / sphere radius multiplier' },
          { key: 'depthFade', label: 'Depth Fade', min: 0, max: 2, step: 0.1, desc: 'How much back-facing nodes dim (0 = uniform, 2 = heavy)' },
        ].map(({ key, label, min, max, step, desc }) => (
          <div key={key} style={{ marginBottom: 14 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
              <label style={{ color: '#888', fontSize: 11 }}>{label}</label>
              <span style={{ color: '#7dd3fc', fontSize: 11, fontVariantNumeric: 'tabular-nums' }}>
                {graphSettings[key]}
              </span>
            </div>
            <input
              type="range" min={min} max={max} step={step}
              value={graphSettings[key]}
              onChange={e => update(key, Number(e.target.value))}
              style={{ width: '100%', accentColor: '#7dd3fc' }}
            />
            <div style={{ color: '#444', fontSize: 10, marginTop: 1 }}>{desc}</div>
          </div>
        ))}

        {/* Reset physics to defaults */}
        <button
          onClick={() => {
            const defaults = {
              rotationSpeed: 1, momentumDecay: 0.96, phantomDrift: 1,
              phantomAlpha: 1, phantomSize: 1, twinkleSpeed: 1,
              clusterScale: 1, globeRadiusScale: 1, depthFade: 1,
            }
            setGraphSettings({ ...graphSettings, ...defaults })
          }}
          style={{
            background: '#fb923c22',
            border: '1px solid #fb923c44',
            color: '#fb923c',
            padding: '6px 16px',
            borderRadius: 4,
            cursor: 'pointer',
            fontSize: 11,
            fontFamily: 'inherit',
            fontWeight: 600,
            marginTop: 4,
            marginBottom: 8,
            transition: 'all 0.15s',
          }}
          onMouseEnter={e => { e.target.style.borderColor = '#fb923c'; e.target.style.background = '#fb923c33' }}
          onMouseLeave={e => { e.target.style.borderColor = '#fb923c44'; e.target.style.background = '#fb923c22' }}
        >
          RESET PHYSICS
        </button>

        {/* Semantic Zoom section */}
        <div style={{ color: '#555', fontSize: 10, letterSpacing: 1, marginTop: 24, marginBottom: 16 }}>
          SEMANTIC ZOOM
        </div>

        {/* Galaxy node budget */}
        <div style={{ marginBottom: 14 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
            <label style={{ color: '#888', fontSize: 11 }}>Galaxy Node Budget</label>
            <span style={{ color: '#7dd3fc', fontSize: 11 }}>{galaxyNodeBudget}</span>
          </div>
          <input
            type="range" min={50} max={500} step={10}
            value={galaxyNodeBudget}
            onChange={e => setGalaxyNodeBudget(Number(e.target.value))}
            style={{ width: '100%', accentColor: '#7dd3fc' }}
          />
          <div style={{ color: '#444', fontSize: 10, marginTop: 1 }}>
            Max nodes shown when drilling into a cluster (galaxy view)
          </div>
        </div>

        {/* Recompute layout */}
        <button
          onClick={async () => {
            setRecomputing(true)
            try { await recomputeLayout() } finally { setRecomputing(false) }
          }}
          disabled={recomputing}
          style={{
            background: recomputing ? '#333' : '#a78bfa22',
            border: `1px solid ${recomputing ? '#444' : '#a78bfa44'}`,
            color: recomputing ? '#666' : '#a78bfa',
            padding: '8px 20px',
            borderRadius: 4,
            cursor: recomputing ? 'default' : 'pointer',
            fontSize: 12,
            fontFamily: 'inherit',
            fontWeight: 600,
            marginTop: 8,
            transition: 'all 0.15s',
          }}
        >
          {recomputing ? 'RECOMPUTING...' : 'RECOMPUTE CLUSTER LAYOUT'}
        </button>
        <div style={{ color: '#444', fontSize: 10, marginTop: 4 }}>
          Re-runs spring layout on cluster centroids (Universe view positions)
        </div>
      </div>
    </div>
  )
}
