import React, { useMemo, useState } from 'react'

const ENTITY_COLORS = {
  // Observatory entity types
  person: '#f472b6',
  persona: '#c084fc',
  place: '#34d399',
  project: '#67e8f9',
  // Kozmo entity types
  character: '#f472b6',
  characters: '#f472b6',
  location: '#4ade80',
  locations: '#4ade80',
  prop: '#67e8f9',
  props: '#67e8f9',
  lore: '#c084fc',
  faction: '#f59e0b',
  factions: '#f59e0b',
}

function EntityTooltip({ entity, style }) {
  const color = ENTITY_COLORS[entity.type] || '#888'
  const profile = entity.profile || entity.full_profile || ''
  const snippet = profile.length > 120 ? profile.slice(0, 118) + '..' : profile

  return (
    <div
      style={{
        position: 'absolute',
        bottom: '100%',
        left: '50%',
        transform: 'translateX(-50%)',
        marginBottom: 6,
        background: '#0a0a14',
        border: `1px solid ${color}44`,
        borderRadius: 6,
        padding: '10px 12px',
        width: 240,
        zIndex: 50,
        pointerEvents: 'none',
        boxShadow: `0 4px 20px rgba(0,0,0,0.6), 0 0 8px ${color}22`,
        ...style,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
        <span style={{ color, fontWeight: 700, fontSize: 13 }}>{entity.name}</span>
        <span style={{
          background: `${color}22`,
          color,
          fontSize: 9,
          padding: '1px 6px',
          borderRadius: 3,
          textTransform: 'uppercase',
          letterSpacing: 1,
          fontWeight: 600,
        }}>
          {entity.type}
        </span>
      </div>
      {snippet && (
        <div style={{ color: '#999', fontSize: 11, lineHeight: 1.4 }}>
          {snippet}
        </div>
      )}
      {entity.mention_count > 0 && (
        <div style={{ color: '#555', fontSize: 10, marginTop: 4 }}>
          {entity.mention_count} mentions
        </div>
      )}
    </div>
  )
}

function EntitySpan({ text, entity, onClick }) {
  const [hovered, setHovered] = useState(false)
  const color = ENTITY_COLORS[entity.type] || '#888'

  return (
    <span
      style={{
        position: 'relative',
        color,
        cursor: onClick ? 'pointer' : 'default',
        borderBottom: `1px dotted ${color}66`,
        transition: 'background 0.15s',
        background: hovered ? `${color}15` : 'transparent',
        borderRadius: 2,
        padding: '0 1px',
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={(e) => {
        if (onClick) {
          e.stopPropagation()
          onClick(entity.id)
        }
      }}
    >
      {text}
      {hovered && <EntityTooltip entity={entity} />}
    </span>
  )
}

export default function AnnotatedText({ text, entities, onEntityClick }) {
  const { regex, lookup } = useMemo(() => {
    if (!entities || entities.length === 0) return { regex: null, lookup: null }

    const map = new Map()
    for (const entity of entities) {
      if (entity.name) {
        map.set(entity.name.toLowerCase(), entity)
      }
      try {
        const aliases = typeof entity.aliases === 'string'
          ? JSON.parse(entity.aliases || '[]')
          : (entity.aliases || [])
        for (const alias of aliases) {
          if (alias && alias.length > 1) {
            map.set(alias.toLowerCase(), entity)
          }
        }
      } catch { /* skip bad aliases */ }
    }

    // Sort by length DESC so "Luna Beta" matches before "Luna"
    const terms = [...map.keys()]
      .filter(t => t.length > 1)
      .sort((a, b) => b.length - a.length)

    if (terms.length === 0) return { regex: null, lookup: null }

    const escaped = terms.map(t => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
    const pattern = new RegExp(`\\b(${escaped.join('|')})\\b`, 'gi')
    console.debug(`[AnnotatedText] ${terms.length} entity terms from ${entities.length} entities`)
    return { regex: pattern, lookup: map }
  }, [entities])

  if (!text || !regex || !lookup) {
    return <>{text || ''}</>
  }

  // Split text into segments
  const parts = []
  let lastIndex = 0
  let match

  // Reset regex state
  regex.lastIndex = 0
  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ type: 'text', value: text.slice(lastIndex, match.index) })
    }
    const entity = lookup.get(match[0].toLowerCase())
    if (entity) {
      parts.push({ type: 'entity', value: match[0], entity })
    } else {
      parts.push({ type: 'text', value: match[0] })
    }
    lastIndex = match.index + match[0].length
  }
  if (lastIndex < text.length) {
    parts.push({ type: 'text', value: text.slice(lastIndex) })
  }

  return (
    <>
      {parts.map((part, i) =>
        part.type === 'entity' ? (
          <EntitySpan
            key={i}
            text={part.value}
            entity={part.entity}
            onClick={onEntityClick}
          />
        ) : (
          <React.Fragment key={i}>{part.value}</React.Fragment>
        )
      )}
    </>
  )
}
