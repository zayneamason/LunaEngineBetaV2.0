import React, { useState, useEffect } from 'react'
import { useStore } from '../store'

const ENTITY_TYPES = {
  person: { color: '#f472b6', icon: '●', bg: '#2a1228' },
  persona: { color: '#c084fc', icon: '◉', bg: '#1e1638' },
  place: { color: '#34d399', icon: '◆', bg: '#0f2418' },
  project: { color: '#67e8f9', icon: '◈', bg: '#0e2a2e' },
}

const LOCK_IN_COLORS = {
  drifting: '#64748b',
  fluid: '#3b82f6',
  settled: '#22c55e',
  crystallized: '#f59e0b',
}

export default function EntitiesView() {
  const { entities, selectedEntityId, entityDetail, selectEntity, fetchEntityDetail, fetchEntities } = useStore()
  const [typeFilter, setTypeFilter] = useState(null)

  useEffect(() => {
    fetchEntities(typeFilter)
  }, [typeFilter])

  const filtered = entities.filter(e => !typeFilter || e.type === typeFilter)

  return (
    <div style={{ display: 'flex', height: '100%' }}>
      {/* Left: Entity list */}
      <div style={{
        width: 320,
        borderRight: '1px solid #1a1a2e',
        background: '#0a0a14',
        display: 'flex',
        flexDirection: 'column',
      }}>
        {/* Header */}
        <div style={{ padding: '12px 16px', borderBottom: '1px solid #1a1a2e' }}>
          <div style={{ color: '#aaa', fontSize: 12, marginBottom: 8 }}>
            ENTITIES ({filtered.length})
          </div>
          {/* Type filters */}
          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
            {[null, 'person', 'persona', 'place', 'project'].map(type => (
              <button
                key={type || 'all'}
                onClick={() => setTypeFilter(type)}
                style={{
                  background: typeFilter === type ? '#2a2a3e' : '#1a1a2e',
                  border: '1px solid ' + (typeFilter === type ? '#444' : '#2a2a3e'),
                  color: typeFilter === type ? '#7dd3fc' : '#777',
                  padding: '4px 10px',
                  borderRadius: 4,
                  fontSize: 11,
                  cursor: 'pointer',
                }}
              >
                {type || 'All'}
              </button>
            ))}
          </div>
        </div>

        {/* Entity list */}
        <div style={{ flex: 1, overflow: 'auto' }}>
          {filtered.map(entity => {
            const config = ENTITY_TYPES[entity.type] || ENTITY_TYPES.person
            const isSelected = selectedEntityId === entity.id

            return (
              <div
                key={entity.id}
                onClick={() => {
                  selectEntity(entity.id)
                  fetchEntityDetail(entity.id)
                }}
                style={{
                  padding: 12,
                  borderBottom: '1px solid #1a1a2e',
                  cursor: 'pointer',
                  background: isSelected ? '#1a1a2e' : 'transparent',
                  transition: 'background 0.1s',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  {/* Avatar */}
                  <div style={{
                    width: 36,
                    height: 36,
                    borderRadius: '50%',
                    background: config.bg,
                    border: `2px solid ${config.color}`,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: config.color,
                    fontSize: 16,
                    fontWeight: 600,
                  }}>
                    {entity.avatar || config.icon}
                  </div>

                  {/* Info */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{
                      color: config.color,
                      fontSize: 13,
                      fontWeight: 600,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}>
                      {entity.name}
                    </div>
                    <div style={{ color: '#666', fontSize: 10, textTransform: 'uppercase', letterSpacing: 1 }}>
                      {entity.type}
                    </div>
                  </div>

                  {/* Mention count badge */}
                  <div style={{
                    background: '#1a1a2e',
                    color: '#888',
                    fontSize: 10,
                    padding: '2px 6px',
                    borderRadius: 3,
                  }}>
                    {entity.mention_count || 0}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Right: Entity detail */}
      <div style={{ flex: 1, background: '#06060e', overflow: 'auto', padding: 24 }}>
        {!entityDetail ? (
          <div style={{ color: '#555', textAlign: 'center', paddingTop: 60 }}>
            Select an entity to view details
          </div>
        ) : (
          <EntityDetail entity={entityDetail} />
        )}
      </div>
    </div>
  )
}

function EntityDetail({ entity }) {
  const [tab, setTab] = useState('profile')
  const config = ENTITY_TYPES[entity.entity.type] || ENTITY_TYPES.person

  const aliases = JSON.parse(entity.entity.aliases || '[]')
  const coreFacts = JSON.parse(entity.entity.core_facts || '{}')

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 24 }}>
        <div style={{
          width: 60,
          height: 60,
          borderRadius: '50%',
          background: config.bg,
          border: `3px solid ${config.color}`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: config.color,
          fontSize: 24,
          fontWeight: 700,
        }}>
          {entity.entity.avatar || config.icon}
        </div>
        <div>
          <div style={{ color: config.color, fontSize: 20, fontWeight: 700, marginBottom: 4 }}>
            {entity.entity.name}
          </div>
          <div style={{ color: '#666', fontSize: 11, textTransform: 'uppercase', letterSpacing: 1 }}>
            {entity.entity.type} · v{entity.entity.current_version} · {entity.entity.mention_count} mentions
          </div>
        </div>
      </div>

      {/* Aliases */}
      {aliases.length > 0 && (
        <div style={{ display: 'flex', gap: 6, marginBottom: 20, flexWrap: 'wrap' }}>
          {aliases.map((alias, i) => (
            <span key={i} style={{
              background: '#1a1a2e',
              color: '#888',
              padding: '4px 10px',
              borderRadius: 4,
              fontSize: 11,
            }}>
              {alias}
            </span>
          ))}
        </div>
      )}

      {/* Tabs */}
      <div style={{ borderBottom: '1px solid #1a1a2e', marginBottom: 20, display: 'flex', gap: 16 }}>
        {['profile', 'knowledge', 'quests', 'history'].map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              background: 'none',
              border: 'none',
              color: tab === t ? '#7dd3fc' : '#666',
              borderBottom: tab === t ? '2px solid #7dd3fc' : '2px solid transparent',
              padding: '8px 4px',
              cursor: 'pointer',
              fontSize: 12,
              textTransform: 'uppercase',
              letterSpacing: 1,
            }}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === 'profile' && (
        <div>
          {/* Profile text */}
          {entity.entity.profile && (
            <div style={{
              color: '#aaa',
              fontSize: 14,
              lineHeight: 1.6,
              fontFamily: '"Crimson Pro", serif',
              fontStyle: 'italic',
              marginBottom: 20,
              padding: 16,
              background: '#0a0a14',
              borderLeft: '3px solid ' + config.color,
            }}>
              {entity.entity.profile}
            </div>
          )}

          {/* Core facts */}
          {Object.keys(coreFacts).length > 0 && (
            <div>
              <div style={{ color: '#888', fontSize: 11, marginBottom: 8, textTransform: 'uppercase', letterSpacing: 1 }}>
                Core Facts
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: 8, fontSize: 12 }}>
                {Object.entries(coreFacts).map(([key, value]) => (
                  <React.Fragment key={key}>
                    <div style={{ color: '#666' }}>{key}:</div>
                    <div style={{ color: '#aaa' }}>{value}</div>
                  </React.Fragment>
                ))}
              </div>
            </div>
          )}

          {/* Relationships */}
          {entity.relationships.length > 0 && (
            <div style={{ marginTop: 20 }}>
              <div style={{ color: '#888', fontSize: 11, marginBottom: 8, textTransform: 'uppercase', letterSpacing: 1 }}>
                Relationships ({entity.relationships.length})
              </div>
              {entity.relationships.map((rel, i) => (
                <div key={i} style={{
                  padding: 8,
                  background: '#0a0a14',
                  marginBottom: 4,
                  borderRadius: 4,
                  fontSize: 12,
                }}>
                  <span style={{ color: '#888' }}>{rel.from_id === entity.entity.id ? '→' : '←'}</span>{' '}
                  <span style={{ color: '#7dd3fc' }}>{rel.rel_type}</span>{' '}
                  <span style={{ color: '#aaa' }}>({rel.from_id === entity.entity.id ? rel.to_id : rel.from_id})</span>
                  {rel.context && <span style={{ color: '#666', marginLeft: 8 }}>· {rel.context}</span>}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {tab === 'knowledge' && (
        <div>
          {entity.mentions.length === 0 ? (
            <div style={{ color: '#555', textAlign: 'center', paddingTop: 40 }}>
              No knowledge nodes linked
            </div>
          ) : (
            entity.mentions.map((mention, i) => (
              <div key={i} style={{
                padding: 12,
                background: '#0a0a14',
                marginBottom: 8,
                borderRadius: 4,
                borderLeft: '3px solid ' + (mention.lock_in >= 0.85 ? LOCK_IN_COLORS.crystallized :
                  mention.lock_in >= 0.70 ? LOCK_IN_COLORS.settled :
                  mention.lock_in >= 0.20 ? LOCK_IN_COLORS.fluid : LOCK_IN_COLORS.drifting),
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                  <span style={{ color: '#888', fontSize: 10, textTransform: 'uppercase' }}>
                    {mention.type}
                  </span>
                  <span style={{ color: '#666', fontSize: 10 }}>
                    Lock-in: {(mention.lock_in * 100).toFixed(0)}%
                  </span>
                </div>
                <div style={{ color: '#aaa', fontSize: 13, lineHeight: 1.5 }}>
                  {mention.content}
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {tab === 'quests' && (
        <div>
          {entity.quests.length === 0 ? (
            <div style={{ color: '#555', textAlign: 'center', paddingTop: 40 }}>
              No quests targeting this entity
            </div>
          ) : (
            entity.quests.map((quest, i) => (
              <div key={i} style={{
                padding: 12,
                background: '#0a0a14',
                marginBottom: 8,
                borderRadius: 4,
              }}>
                <div style={{ color: '#7dd3fc', fontSize: 13, fontWeight: 600, marginBottom: 4 }}>
                  {quest.title}
                </div>
                <div style={{ color: '#666', fontSize: 11, marginBottom: 8 }}>
                  {quest.subtitle}
                </div>
                <div style={{ color: '#888', fontSize: 10 }}>
                  Status: <span style={{ color: quest.status === 'complete' ? '#4ade80' : quest.status === 'active' ? '#7dd3fc' : '#aaa' }}>
                    {quest.status}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {tab === 'history' && (
        <div>
          {entity.versions.map((version, i) => (
            <div key={i} style={{
              padding: 12,
              background: '#0a0a14',
              marginBottom: 8,
              borderRadius: 4,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                <span style={{ color: '#7dd3fc', fontSize: 12 }}>
                  v{version.version}
                </span>
                <span style={{ color: '#666', fontSize: 10 }}>
                  {new Date(version.created_at).toLocaleDateString()}
                </span>
              </div>
              <div style={{ color: '#888', fontSize: 11, marginBottom: 4, textTransform: 'uppercase' }}>
                {version.change_type}
              </div>
              <div style={{ color: '#aaa', fontSize: 12 }}>
                {version.summary}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
