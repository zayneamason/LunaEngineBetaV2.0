import React from 'react'
import LockInRing from './LockInRing'

const TYPE_COLORS = {
  ENTITY: '#22d3ee',
  FACT: '#38bdf8',
  DECISION: '#a78bfa',
  INSIGHT: '#facc15',
  PROBLEM: '#f87171',
  ACTION: '#4ade80',
  OUTCOME: '#fb923c',
  OBSERVATION: '#94a3b8',
}

export default function NodeCard({ node, onClose }) {
  const color = TYPE_COLORS[node.type] || '#555'
  const tags = typeof node.tags === 'string' ? JSON.parse(node.tags) : (node.tags || [])

  return (
    <div style={{
      background: '#0a0a14', border: '1px solid #1a1a2e',
      borderRadius: 6, padding: 16, boxShadow: '0 4px 24px rgba(0,0,0,0.5)',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
        <div>
          <div style={{ color, fontSize: 10, letterSpacing: 1, marginBottom: 2 }}>{node.type}</div>
          <div style={{ color: '#ddd', fontSize: 14, fontWeight: 600 }}>{node.id}</div>
        </div>
        <button onClick={onClose} style={{
          background: 'none', border: 'none', color: '#555', cursor: 'pointer',
          fontSize: 16, padding: '0 4px',
        }}>
          x
        </button>
      </div>

      {/* Content */}
      <div style={{
        color: '#999', fontSize: 12, lineHeight: 1.5,
        marginBottom: 12, maxHeight: 120, overflow: 'auto',
      }}>
        {node.content}
      </div>

      {/* Lock-in */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 10 }}>
        <LockInRing value={node.lock_in || 0} color={color} size={36} />
        <div>
          <div style={{ color: '#888', fontSize: 11 }}>Lock-in: {((node.lock_in || 0) * 100).toFixed(1)}%</div>
          <div style={{ color: '#666', fontSize: 10 }}>
            {node.lock_in >= 0.85 ? 'Crystallized' :
             node.lock_in >= 0.70 ? 'Settled' :
             node.lock_in >= 0.20 ? 'Fluid' : 'Drifting'}
          </div>
        </div>
      </div>

      {/* Stats */}
      <div style={{
        display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6,
        fontSize: 11, color: '#666', marginBottom: 10,
      }}>
        <div>Confidence: <span style={{ color: '#888' }}>{(node.confidence || 0).toFixed(2)}</span></div>
        <div>Accesses: <span style={{ color: '#888' }}>{node.access_count || 0}</span></div>
        <div>Cluster: <span style={{ color: '#888' }}>{node.cluster_id || 'none'}</span></div>
      </div>

      {/* Tags */}
      {tags.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
          {tags.map((tag, i) => (
            <span key={i} style={{
              background: '#1a1a2e', color: '#777', padding: '2px 6px',
              borderRadius: 3, fontSize: 10,
            }}>
              {tag}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}
