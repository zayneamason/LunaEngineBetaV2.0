import React, { useState } from 'react'
import { useObservatoryStore } from '../store'

const PHASE_COLORS = {
  fts5: '#38bdf8',
  vector: '#a78bfa',
  fusion: '#facc15',
  activation: '#f87171',
  assembly: '#4ade80',
}

export default function Replay() {
  const { replayResult, replayPhaseIndex, runReplay, setReplayPhase, clearReplay } = useObservatoryStore()
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)

  const handleRun = async () => {
    if (!query.trim()) return
    setLoading(true)
    await runReplay(query.trim())
    setLoading(false)
  }

  return (
    <div style={{ display: 'flex', height: '100%' }}>
      <div style={{
        width: 280, borderRight: '1px solid #1a1a2e', padding: 16,
        display: 'flex', flexDirection: 'column', gap: 12, flexShrink: 0,
      }}>
        <div style={{ color: '#555', fontSize: 10, letterSpacing: 1 }}>RETRIEVAL REPLAY</div>

        <div>
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleRun()}
            placeholder="Enter query..."
            style={{
              width: '100%', padding: '8px 10px',
              background: '#0e0e1a', border: '1px solid #2a2a3e',
              color: '#c8c8d4', fontFamily: 'inherit', fontSize: 12,
              borderRadius: 3, outline: 'none',
            }}
          />
          <button
            onClick={handleRun}
            disabled={loading || !query.trim()}
            style={{
              width: '100%', marginTop: 8, padding: '6px 0',
              background: loading ? '#333' : '#1a1a2e',
              border: '1px solid #2a2a3e', color: loading ? '#555' : '#7dd3fc',
              cursor: loading ? 'wait' : 'pointer', fontFamily: 'inherit',
              fontSize: 12, borderRadius: 3,
            }}
          >
            {loading ? 'Running...' : 'Run Replay'}
          </button>
        </div>

        {replayResult && replayResult.phases && (
          <>
            <div style={{ color: '#555', fontSize: 10, letterSpacing: 1, marginTop: 8 }}>PHASES</div>
            {replayResult.phases.map((phase, i) => (
              <button
                key={phase.phase}
                onClick={() => setReplayPhase(i)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 8,
                  width: '100%', textAlign: 'left',
                  background: replayPhaseIndex === i ? '#1a1a2e' : 'transparent',
                  border: replayPhaseIndex === i ? `1px solid ${PHASE_COLORS[phase.phase]}44` : '1px solid transparent',
                  color: replayPhaseIndex === i ? PHASE_COLORS[phase.phase] : '#666',
                  padding: '6px 10px', cursor: 'pointer', fontFamily: 'inherit',
                  fontSize: 12, borderRadius: 3,
                }}
              >
                <div style={{
                  width: 8, height: 8, borderRadius: '50%',
                  background: PHASE_COLORS[phase.phase] || '#555',
                }} />
                <div>
                  <div>{phase.phase.toUpperCase()}</div>
                  <div style={{ fontSize: 10, color: '#555' }}>
                    {phase.result_count ?? phase.activated_count ?? phase.selected_count ?? '?'} results
                    {' / '}
                    {phase.elapsed_ms}ms
                  </div>
                </div>
              </button>
            ))}

            <button
              onClick={clearReplay}
              style={{
                marginTop: 8, padding: '4px 0',
                background: 'transparent', border: '1px solid #2a2a3e',
                color: '#555', cursor: 'pointer', fontFamily: 'inherit',
                fontSize: 11, borderRadius: 3,
              }}
            >
              Clear
            </button>
          </>
        )}
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
        {!replayResult ? (
          <div style={{ color: '#444', textAlign: 'center', marginTop: 80 }}>
            Enter a query and click "Run Replay" to trace the retrieval pipeline.
          </div>
        ) : replayPhaseIndex < 0 ? (
          <div style={{ color: '#444', textAlign: 'center', marginTop: 80 }}>
            Select a phase from the left panel.
          </div>
        ) : (
          <PhaseDetail phase={replayResult.phases[replayPhaseIndex]} />
        )}
      </div>
    </div>
  )
}

function PhaseDetail({ phase }) {
  const color = PHASE_COLORS[phase.phase] || '#888'

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <span style={{ color, fontSize: 16, fontWeight: 700 }}>{phase.phase.toUpperCase()}</span>
        <span style={{ color: '#555', fontSize: 12 }}>{phase.elapsed_ms}ms</span>
      </div>

      {phase.phase === 'assembly' && (
        <div style={{ marginBottom: 16 }}>
          <div style={{ color: '#555', fontSize: 11, marginBottom: 4 }}>
            Token Budget: {phase.tokens_used} / {3000} ({Math.round((phase.budget_pct || 0) * 100)}%)
          </div>
          <div style={{ height: 6, background: '#1a1a2e', borderRadius: 3, overflow: 'hidden' }}>
            <div style={{
              height: '100%', width: `${(phase.budget_pct || 0) * 100}%`,
              background: color, borderRadius: 3, transition: 'width 0.3s',
            }} />
          </div>
          {phase.dropped > 0 && (
            <div style={{ color: '#f87171', fontSize: 11, marginTop: 4 }}>
              {phase.dropped} nodes dropped (over budget)
            </div>
          )}
          {phase.clusters_hit && (
            <div style={{ color: '#666', fontSize: 11, marginTop: 4 }}>
              Clusters hit: {phase.clusters_hit.join(', ') || 'none'}
            </div>
          )}
        </div>
      )}

      {phase.results && phase.results.length > 0 && (
        <div style={{ border: '1px solid #1a1a2e', borderRadius: 4, overflow: 'hidden' }}>
          <div style={{
            display: 'grid', gridTemplateColumns: '100px 80px 1fr',
            background: '#0e0e1a', padding: '6px 10px',
            color: '#555', fontSize: 10, letterSpacing: 1,
          }}>
            <span>ID</span>
            <span>SCORE</span>
            <span>CONTENT</span>
          </div>
          {phase.results.map((r, i) => (
            <div key={i} style={{
              display: 'grid', gridTemplateColumns: '100px 80px 1fr',
              padding: '5px 10px', borderTop: '1px solid #1a1a2e', fontSize: 11,
            }}>
              <span style={{ color }}>{r.id}</span>
              <span style={{ color: '#888' }}>
                {r.score != null ? r.score.toFixed(4) :
                 r.activation != null ? r.activation.toFixed(4) : '\u2014'}
              </span>
              <span style={{ color: '#777', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {r.content || `hop ${r.hop}`}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
