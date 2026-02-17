import React, { useState } from 'react'
import { useStore } from '../store'
import EventCard from '../components/EventCard'

const EVENT_TYPES = [
  'node_created', 'edge_added', 'access_recorded', 'lock_in_changed',
  'search_fts5_done', 'search_vector_done', 'search_fusion_done',
  'activation_started', 'activation_hop', 'activation_done',
  'constellation_assembled', 'sandbox_reset', 'sandbox_seeded',
]

export default function Timeline() {
  const { events } = useStore()
  const [filter, setFilter] = useState(null)

  const filtered = filter
    ? events.filter(e => e.type === filter)
    : events

  return (
    <div style={{ display: 'flex', height: '100%' }}>
      {/* Filter sidebar */}
      <div style={{
        width: 180, borderRight: '1px solid #1a1a2e', padding: 12,
        overflowY: 'auto', flexShrink: 0,
      }}>
        <div style={{ color: '#555', fontSize: 10, marginBottom: 8, letterSpacing: 1 }}>
          FILTER BY TYPE
        </div>
        <button
          onClick={() => setFilter(null)}
          style={{
            display: 'block', width: '100%', textAlign: 'left',
            background: !filter ? '#1a1a2e' : 'transparent',
            border: 'none', color: !filter ? '#7dd3fc' : '#666',
            padding: '4px 8px', cursor: 'pointer', fontFamily: 'inherit',
            fontSize: 11, borderRadius: 3, marginBottom: 2,
          }}
        >
          All ({events.length})
        </button>
        {EVENT_TYPES.map(type => {
          const count = events.filter(e => e.type === type).length
          if (count === 0) return null
          return (
            <button
              key={type}
              onClick={() => setFilter(type)}
              style={{
                display: 'block', width: '100%', textAlign: 'left',
                background: filter === type ? '#1a1a2e' : 'transparent',
                border: 'none', color: filter === type ? '#7dd3fc' : '#666',
                padding: '4px 8px', cursor: 'pointer', fontFamily: 'inherit',
                fontSize: 11, borderRadius: 3, marginBottom: 2,
              }}
            >
              {type.replace(/_/g, ' ')} ({count})
            </button>
          )
        })}
      </div>

      {/* Event stream */}
      <div style={{ flex: 1, overflowY: 'auto', padding: 12 }}>
        {filtered.length === 0 ? (
          <div style={{ color: '#444', textAlign: 'center', marginTop: 80 }}>
            No events yet. Use MCP tools to interact with the sandbox.
          </div>
        ) : (
          filtered.map((event, i) => (
            <EventCard key={`${event.timestamp}-${i}`} event={event} />
          ))
        )}
      </div>
    </div>
  )
}
