/**
 * KeywordTracker — Project-wide entity usage dashboard
 *
 * Shows which entities appear in which scenes, how often,
 * first/last appearance, and context snippets.
 *
 * Consumes `reverseIndex` from KozmoProvider.
 */
import React, { useState, useMemo } from 'react';

const ENTITY_COLORS = {
  character: '#f472b6', characters: '#f472b6',
  location: '#4ade80', locations: '#4ade80',
  prop: '#67e8f9', props: '#67e8f9',
  lore: '#c084fc',
  faction: '#f59e0b', factions: '#f59e0b',
  event: '#818cf8', events: '#818cf8',
};

const SORT_OPTIONS = [
  { key: 'mentions', label: 'Mentions' },
  { key: 'scenes', label: 'Scenes' },
  { key: 'alpha', label: 'A–Z' },
  { key: 'first', label: 'First Appearance' },
];

export default function KeywordTracker({ reverseIndex, onNavigateToScene, onNavigateToEntity }) {
  const [sortBy, setSortBy] = useState('mentions');
  const [filterType, setFilterType] = useState(null);
  const [expandedEntity, setExpandedEntity] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');

  const usageEntries = useMemo(() => {
    if (!reverseIndex?.entity_usage) return [];
    let entries = Object.values(reverseIndex.entity_usage);

    // Filter by type
    if (filterType) {
      entries = entries.filter(u =>
        u.entity_type === filterType || u.entity_type === filterType + 's'
      );
    }

    // Filter by search
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      entries = entries.filter(u =>
        u.entity_name.toLowerCase().includes(q) ||
        u.entity_slug.includes(q)
      );
    }

    // Sort
    entries.sort((a, b) => {
      if (sortBy === 'mentions') return (b.mention_count || 0) - (a.mention_count || 0);
      if (sortBy === 'scenes') return (b.total_scenes || 0) - (a.total_scenes || 0);
      if (sortBy === 'alpha') return a.entity_name.localeCompare(b.entity_name);
      if (sortBy === 'first') return (a.first_appearance || '').localeCompare(b.first_appearance || '');
      return 0;
    });

    return entries;
  }, [reverseIndex, sortBy, filterType, searchQuery]);

  const typeGroups = useMemo(() => {
    if (!reverseIndex?.entity_usage) return [];
    const types = new Set();
    Object.values(reverseIndex.entity_usage).forEach(u => types.add(u.entity_type));
    return [...types].sort();
  }, [reverseIndex]);

  if (!reverseIndex) {
    return (
      <div style={{ padding: 20, textAlign: 'center', color: '#3a3a50' }}>
        <div style={{ fontSize: 14, marginBottom: 8 }}>No index data</div>
        <div style={{ fontSize: 10 }}>Load a project to see keyword tracking</div>
      </div>
    );
  }

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: 'transparent' }}>
      {/* Header */}
      <div style={{
        padding: '10px 12px', borderBottom: '1px solid #141420',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 8, color: '#c084fc', letterSpacing: 2, fontWeight: 600 }}>KEYWORD TRACKER</span>
          <span style={{ fontSize: 9, color: '#3a3a50' }}>
            {usageEntries.length} entities
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{ fontSize: 8, color: '#3a3a50' }}>
            {reverseIndex.total_scenes} scenes
          </span>
        </div>
      </div>

      {/* Search + Filters */}
      <div style={{ padding: '8px 12px', borderBottom: '1px solid #0a0a14', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search entities..."
          style={{
            width: '100%', padding: '5px 8px', fontSize: 10,
            background: '#0a0a14', border: '1px solid #1a1a24', borderRadius: 3,
            color: '#bbb', outline: 'none',
          }}
        />
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
          <FilterPill active={!filterType} onClick={() => setFilterType(null)} label="All" />
          {typeGroups.map(t => (
            <FilterPill
              key={t}
              active={filterType === t}
              onClick={() => setFilterType(filterType === t ? null : t)}
              label={t}
              color={ENTITY_COLORS[t]}
            />
          ))}
        </div>
        <div style={{ display: 'flex', gap: 4 }}>
          {SORT_OPTIONS.map(opt => (
            <SortPill key={opt.key} active={sortBy === opt.key} onClick={() => setSortBy(opt.key)} label={opt.label} />
          ))}
        </div>
      </div>

      {/* Entity List */}
      <div style={{ flex: 1, overflow: 'auto', padding: '4px 0' }}>
        {usageEntries.map(usage => (
          <EntityUsageRow
            key={usage.entity_slug}
            usage={usage}
            isExpanded={expandedEntity === usage.entity_slug}
            onToggle={() => setExpandedEntity(
              expandedEntity === usage.entity_slug ? null : usage.entity_slug
            )}
            onNavigateToScene={onNavigateToScene}
            onNavigateToEntity={onNavigateToEntity}
          />
        ))}
        {usageEntries.length === 0 && (
          <div style={{ padding: 20, textAlign: 'center', color: '#3a3a50', fontSize: 10 }}>
            No matching entities
          </div>
        )}
      </div>
    </div>
  );
}

function FilterPill({ active, onClick, label, color }) {
  return (
    <button onClick={onClick} style={{
      padding: '2px 6px', fontSize: 8, borderRadius: 2,
      border: `1px solid ${active ? (color || '#c084fc') + '60' : '#1a1a24'}`,
      background: active ? (color || '#c084fc') + '15' : 'transparent',
      color: active ? (color || '#c084fc') : '#4a4a60',
      cursor: 'pointer', letterSpacing: 0.5, fontWeight: active ? 600 : 400,
      transition: 'all 0.15s', textTransform: 'capitalize',
    }}>
      {label}
    </button>
  );
}

function SortPill({ active, onClick, label }) {
  return (
    <button onClick={onClick} style={{
      padding: '2px 6px', fontSize: 7, borderRadius: 2,
      border: `1px solid ${active ? '#818cf860' : '#0a0a14'}`,
      background: active ? '#818cf815' : 'transparent',
      color: active ? '#818cf8' : '#3a3a50',
      cursor: 'pointer', letterSpacing: 0.5,
      transition: 'all 0.15s',
    }}>
      {label}
    </button>
  );
}

function EntityUsageRow({ usage, isExpanded, onToggle, onNavigateToScene, onNavigateToEntity }) {
  const color = ENTITY_COLORS[usage.entity_type] || '#6b6b80';

  return (
    <div style={{ borderBottom: '1px solid #0a0a1400' }}>
      {/* Main Row */}
      <div
        onClick={onToggle}
        style={{
          display: 'flex', alignItems: 'center', gap: 8,
          padding: '8px 12px', cursor: 'pointer',
          transition: 'background 0.1s',
          background: isExpanded ? '#0a0a1480' : 'transparent',
        }}
        onMouseEnter={e => !isExpanded && (e.currentTarget.style.background = '#0a0a1440')}
        onMouseLeave={e => !isExpanded && (e.currentTarget.style.background = 'transparent')}
      >
        {/* Color dot */}
        <span style={{
          width: 6, height: 6, borderRadius: '50%',
          background: color, flexShrink: 0,
        }} />

        {/* Name + type */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span
              style={{ fontSize: 11, color: '#e8e8f0', fontWeight: 500, cursor: 'pointer' }}
              onClick={(e) => {
                e.stopPropagation();
                if (onNavigateToEntity) onNavigateToEntity(usage.entity_slug, usage.entity_type);
              }}
            >
              {usage.entity_name}
            </span>
            <span style={{
              fontSize: 7, color: color, padding: '1px 4px',
              background: color + '15', borderRadius: 2,
              textTransform: 'capitalize', letterSpacing: 0.5,
            }}>
              {usage.entity_type}
            </span>
          </div>
          <div style={{ fontSize: 8, color: '#3a3a50', marginTop: 2 }}>
            {usage.first_appearance && `First: ${usage.first_appearance}`}
            {usage.first_appearance && usage.last_appearance && ' — '}
            {usage.last_appearance && `Last: ${usage.last_appearance}`}
          </div>
        </div>

        {/* Stats */}
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexShrink: 0 }}>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 12, color: '#e8e8f0', fontWeight: 600 }}>
              {usage.total_scenes}
            </div>
            <div style={{ fontSize: 7, color: '#3a3a50' }}>scenes</div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 12, color: color, fontWeight: 600 }}>
              {usage.mention_count || 0}
            </div>
            <div style={{ fontSize: 7, color: '#3a3a50' }}>mentions</div>
          </div>
        </div>

        {/* Expand arrow */}
        <span style={{
          fontSize: 8, color: '#3a3a50',
          transform: isExpanded ? 'rotate(90deg)' : 'rotate(0)',
          transition: 'transform 0.15s',
        }}>
          ▸
        </span>
      </div>

      {/* Expanded: Scene references with context */}
      {isExpanded && usage.scenes && (
        <div style={{ padding: '4px 12px 12px 30px' }}>
          {usage.scenes.map((scene, i) => (
            <div
              key={i}
              style={{
                padding: '4px 8px', marginBottom: 3,
                borderLeft: `2px solid ${color}30`,
                cursor: 'pointer',
                transition: 'background 0.1s',
              }}
              onClick={() => onNavigateToScene?.(scene.scene_slug)}
              onMouseEnter={e => e.currentTarget.style.background = '#0a0a1460'}
              onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
                <span style={{ fontSize: 9, color: '#bbb', fontWeight: 500 }}>
                  {scene.scene_title || scene.scene_slug}
                </span>
                <span style={{
                  fontSize: 7, padding: '1px 4px', borderRadius: 2,
                  background: scene.reference_type === 'frontmatter' ? '#4ade8015' : '#c084fc15',
                  color: scene.reference_type === 'frontmatter' ? '#4ade80' : '#c084fc',
                }}>
                  {scene.reference_type === 'frontmatter' ? scene.field || 'frontmatter' : 'body'}
                </span>
              </div>
              {scene.context && (
                <div style={{
                  fontSize: 9, color: '#4a4a60', lineHeight: 1.4,
                  fontStyle: 'italic', overflow: 'hidden', textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap', maxWidth: 300,
                }}>
                  "...{scene.context}..."
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
