import React from 'react'

const ACTOR_COLORS = {
  matrix: '#38bdf8',
  search: '#a78bfa',
  activation: '#f87171',
  clusters: '#4ade80',
  lock_in: '#facc15',
  admin: '#fb923c',
}

export default function EventCard({ event }) {
  const color = ACTOR_COLORS[event.actor] || '#666'
  const time = new Date(event.timestamp * 1000)
  const timeStr = time.toLocaleTimeString('en-US', { hour12: false, fractionalSecondDigits: 1 })

  return (
    <div style={{
      borderLeft: `2px solid ${color}`,
      padding: '6px 12px',
      marginBottom: 4,
      background: '#0a0a14',
      borderRadius: '0 3px 3px 0',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 3 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ color, fontSize: 11, fontWeight: 600 }}>
            {event.type.replace(/_/g, ' ')}
          </span>
          <span style={{ color: '#444', fontSize: 10 }}>{event.actor}</span>
        </div>
        <span style={{ color: '#444', fontSize: 10 }}>{timeStr}</span>
      </div>
      {event.payload && (
        <div style={{ color: '#666', fontSize: 11, lineHeight: 1.4 }}>
          {formatPayload(event.payload)}
        </div>
      )}
    </div>
  )
}

function formatPayload(payload) {
  const entries = Object.entries(payload)
  if (entries.length === 0) return null

  return entries.map(([k, v]) => {
    const display = Array.isArray(v)
      ? v.length > 3 ? `[${v.slice(0, 3).join(', ')}... +${v.length - 3}]` : `[${v.join(', ')}]`
      : typeof v === 'number' ? (Number.isInteger(v) ? v : v.toFixed(2))
      : String(v).length > 60 ? String(v).slice(0, 60) + '...'
      : String(v)
    return `${k}: ${display}`
  }).join(' / ')
}
