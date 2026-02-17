/**
 * KOZMO CODEX — World Bible Mode
 *
 * Layout: 3-panel + bottom relationship map
 *   LEFT:   File tree (entity browser grouped by type)
 *   CENTER: Entity card (tabbed: overview, details, scenes, refs)
 *   RIGHT:  Agent command center (roster, quick actions, chat, queue)
 *   BOTTOM: Relationship mini-map
 *
 * Wired to KozmoProvider for real API data.
 * Design adapted from ClaudeArtifacts/kozmo_codex.jsx
 */
import React, { useState, useCallback, useMemo, useRef, useEffect } from 'react';
import { useKozmo } from '../KozmoProvider';
import { useKozmoChat } from '../hooks/useKozmoChat';
import KozmoChat from '../components/KozmoChat';
import BulkImportModal from './BulkImportModal';
import { EntityUsagePanel } from '../components/EntityUsagePanel';
import AnnotatedText from '../../components/AnnotatedText';
import ProductionBoard from './ProductionBoard';
import MediaLibrary from './MediaLibrary';

// ============================================================================
// HELPERS
// ============================================================================

/** Access entity field from entity.data.X or entity.X (API may nest differently) */
const d = (entity, key) => entity?.data?.[key] ?? entity?.[key];

/** Entity color: from data, or fallback by type */
const TYPE_COLORS = {
  characters: '#4ade80', character: '#4ade80',
  locations: '#f59e0b', location: '#f59e0b',
  props: '#a78bfa', prop: '#a78bfa',
  lore: '#c8ff00',
  events: '#818cf8', event: '#818cf8',
  factions: '#f472b6', faction: '#f472b6',
};
const entityColor = (entity) => d(entity, 'color') || TYPE_COLORS[entity?.type] || '#6b6b80';

// ============================================================================
// FILE TREE
// ============================================================================

function FileTree({ grouped, selected, onSelect, searchQuery, onSearchChange }) {
  const [expanded, setExpanded] = useState({
    characters: true, locations: true, props: true, lore: true, events: true,
  });

  const groups = [
    { key: 'characters', label: 'CHARACTERS', icon: '◉' },
    { key: 'locations', label: 'LOCATIONS', icon: '◈' },
    { key: 'props', label: 'PROPS', icon: '◇' },
    { key: 'lore', label: 'LORE', icon: '◆' },
    { key: 'events', label: 'EVENTS', icon: '⬡' },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ padding: '8px 10px', borderBottom: '1px solid #1e1e30' }}>
        <input
          value={searchQuery}
          onChange={e => onSearchChange(e.target.value)}
          placeholder="Search entities..."
          style={{
            width: '100%', padding: '5px 8px', background: '#18182a',
            border: '1px solid #24243a', borderRadius: 4, color: '#c8cad0',
            fontFamily: 'inherit', fontSize: 9, outline: 'none',
          }}
          onFocus={e => e.target.style.borderColor = '#c8ff0030'}
          onBlur={e => e.target.style.borderColor = '#24243a'}
        />
      </div>
      <div style={{ flex: 1, overflow: 'auto', padding: '4px 0' }}>
        {groups.map(g => {
          const items = grouped[g.key] || [];
          return (
            <div key={g.key}>
              <button
                onClick={() => setExpanded(e => ({ ...e, [g.key]: !e[g.key] }))}
                style={{
                  width: '100%', display: 'flex', alignItems: 'center', gap: 6,
                  padding: '6px 10px', background: 'transparent', border: 'none',
                  color: '#5a5a72', cursor: 'pointer', fontFamily: 'inherit',
                  fontSize: 8, letterSpacing: 2, textAlign: 'left',
                }}>
                <span style={{
                  fontSize: 6,
                  transform: expanded[g.key] ? 'rotate(90deg)' : 'rotate(0deg)',
                  transition: '0.15s',
                }}>▶</span>
                <span>{g.icon}</span>
                <span>{g.label}</span>
                <span style={{ color: '#3a3a4e', marginLeft: 'auto' }}>{items.length}</span>
              </button>
              {expanded[g.key] && items.map(item => {
                const color = entityColor(item);
                const isSelected = selected === item.slug;
                return (
                  <button
                    key={item.slug}
                    onClick={() => onSelect(item.type, item.slug)}
                    style={{
                      width: '100%', display: 'flex', alignItems: 'center', gap: 8,
                      padding: '5px 10px 5px 28px',
                      background: isSelected ? '#1c1c3a' : 'transparent',
                      border: 'none',
                      borderLeft: isSelected ? `2px solid ${color}` : '2px solid transparent',
                      color: isSelected ? '#e8e8f0' : '#6b6b80',
                      cursor: 'pointer', fontFamily: 'inherit', fontSize: 10,
                      textAlign: 'left', transition: 'all 0.1s',
                    }}>
                    <span style={{
                      width: 5, height: 5, borderRadius: '50%',
                      background: color, flexShrink: 0, opacity: 0.7,
                    }} />
                    <span style={{
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }}>{item.name}</span>
                    {d(item, 'references')?.lora && (
                      <span style={{
                        fontSize: 6, color: '#4ade80', marginLeft: 'auto', letterSpacing: 1,
                      }}>LoRA</span>
                    )}
                  </button>
                );
              })}
              {expanded[g.key] && items.length === 0 && (
                <div style={{
                  padding: '4px 28px', fontSize: 8, color: '#24243a', fontStyle: 'italic',
                }}>empty</div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ============================================================================
// RELATIONSHIP BADGE
// ============================================================================

function RelationshipBadge({ rel, allEntities, onNavigate, annotatedEntities }) {
  const target = allEntities.find(
    e => e.slug === rel.entity || e.slug === rel.slug || e.name === rel.entity
  );
  const color = target ? entityColor(target) : '#4a4a62';

  return (
    <div
      onClick={() => target && onNavigate(target.type, target.slug)}
      style={{
        display: 'flex', alignItems: 'flex-start', gap: 8, padding: '6px 8px',
        borderRadius: 4, cursor: target ? 'pointer' : 'default',
        background: '#16161f', border: '1px solid #1e1e30',
        transition: 'border-color 0.15s',
      }}
      onMouseEnter={e => target && (e.currentTarget.style.borderColor = color + '40')}
      onMouseLeave={e => e.currentTarget.style.borderColor = '#1e1e30'}>
      <span style={{
        width: 5, height: 5, borderRadius: '50%',
        background: color, flexShrink: 0, marginTop: 4,
      }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
          <span style={{ fontSize: 10, color: '#e8e8f0' }}>
            {target?.name || rel.entity}
          </span>
          <span style={{
            fontSize: 7, color: '#4a4a62', padding: '1px 4px',
            background: '#1e1e30', borderRadius: 2, letterSpacing: 0.5,
          }}>{rel.type}</span>
        </div>
        {rel.detail && (
          <div style={{ fontSize: 9, color: '#5a5a72', lineHeight: 1.4 }}>
            <AnnotatedText text={rel.detail} entities={annotatedEntities || []} onEntityClick={(slug) => {
              const t = allEntities.find(e => e.slug === slug || e.id === slug);
              if (t) onNavigate(t.type, t.slug);
            }} />
          </div>
        )}
      </div>
    </div>
  );
}

// ============================================================================
// ENTITY CARD
// ============================================================================

function EntityCard({ entity, entityType, allEntities, onNavigate, onUpdate, annotatedEntities, usageByEntity, reverseIndex, activeProject }) {
  const [section, setSection] = useState('overview');
  const [isEditing, setIsEditing] = useState(false);
  const [draftData, setDraftData] = useState({});
  const [isDirty, setIsDirty] = useState(false);

  const type = entityType || entity?.type;
  const isCharacter = type === 'character' || type === 'characters';
  const sectionTabs = isCharacter
    ? ['overview', 'details', 'scenes', 'refs']
    : ['overview', 'scenes', 'refs'];

  const color = entityColor(entity);
  const traits = d(entity, 'traits');
  const arc = d(entity, 'arc');
  const voice = d(entity, 'voice');
  const physical = d(entity, 'physical');
  const wardrobe = d(entity, 'wardrobe');
  const relationships = d(entity, 'relationships') || [];
  const references = d(entity, 'references') || {};
  const props = d(entity, 'props') || [];
  const scenes = d(entity, 'scenes') || [];
  const tags = entity?.tags || d(entity, 'tags') || [];
  const lunaNotes = d(entity, 'luna_notes');
  const role = d(entity, 'role');
  const desc = d(entity, 'desc') || d(entity, 'description');
  const mood = d(entity, 'mood');
  const lighting = d(entity, 'lighting');
  const cameraSuggestion = d(entity, 'camera_suggestion');
  const significance = d(entity, 'significance');
  const firstAppearance = d(entity, 'first_appearance');

  // Initialize draft data when entity changes
  React.useEffect(() => {
    if (entity) {
      setDraftData(entity.data || {});
      setIsDirty(false);
      setIsEditing(false);
    }
  }, [entity?.slug]);

  // Edit handlers
  const handleEdit = () => {
    setDraftData(entity.data || {});
    setIsEditing(true);
    setIsDirty(false);
  };

  const handleSave = async () => {
    if (!entity?.slug || !onUpdate) return;

    try {
      await onUpdate(type, entity.slug, { data: draftData });
      setIsEditing(false);
      setIsDirty(false);
    } catch (err) {
      console.error('Failed to update entity:', err);
      alert('Failed to save changes. Please try again.');
    }
  };

  const handleCancel = () => {
    if (isDirty && !window.confirm('Discard unsaved changes?')) return;
    setDraftData(entity.data || {});
    setIsEditing(false);
    setIsDirty(false);
  };

  const handleFieldChange = (key, value) => {
    setDraftData({ ...draftData, [key]: value });
    setIsDirty(true);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Entity Header */}
      <div style={{
        padding: '16px 20px', borderBottom: '1px solid #1e1e30',
        background: `linear-gradient(135deg, ${color}06 0%, transparent 60%)`,
      }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: color }} />
              <span style={{
                fontSize: 18, color: '#e8e8f0', fontWeight: 700, letterSpacing: -0.5,
              }}>{entity?.name}</span>
            </div>
            {role && (
              <div style={{ fontSize: 11, color, marginBottom: 6, marginLeft: 16, opacity: 0.8 }}>
                {role}
              </div>
            )}
            {desc && (
              <div style={{
                fontSize: 10, color: '#6b6b80', lineHeight: 1.5, marginLeft: 16, maxWidth: 500,
              }}>
                <AnnotatedText text={desc} entities={annotatedEntities || []} onEntityClick={(slug) => {
                  const t = allEntities.find(e => e.slug === slug || e.id === slug);
                  if (t) onNavigate(t.type, t.slug);
                }} />
              </div>
            )}
            {mood && (
              <div style={{ fontSize: 10, color: '#6b6b80', marginLeft: 16 }}>
                Mood: <span style={{ color: '#9ca3af' }}>{mood}</span>
              </div>
            )}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4 }}>
            {/* Edit/Save/Cancel buttons */}
            {onUpdate && (
              !isEditing ? (
                <button
                  onClick={handleEdit}
                  style={{
                    padding: '4px 12px',
                    borderRadius: 3,
                    border: '1px solid #c084fc40',
                    background: 'rgba(192, 132, 252, 0.1)',
                    color: '#c084fc',
                    fontSize: 9,
                    fontWeight: 600,
                    cursor: 'pointer',
                    transition: 'all 0.15s',
                    letterSpacing: 0.5,
                  }}
                  onMouseEnter={(e) => {
                    e.target.style.background = 'rgba(192, 132, 252, 0.15)';
                    e.target.style.borderColor = '#c084fc60';
                  }}
                  onMouseLeave={(e) => {
                    e.target.style.background = 'rgba(192, 132, 252, 0.1)';
                    e.target.style.borderColor = '#c084fc40';
                  }}
                >
                  ✎ EDIT
                </button>
              ) : (
                <div style={{ display: 'flex', gap: 4 }}>
                  <button
                    onClick={handleSave}
                    disabled={!isDirty}
                    style={{
                      padding: '4px 10px',
                      borderRadius: 3,
                      border: '1px solid #4ade8040',
                      background: isDirty ? 'rgba(74, 222, 128, 0.1)' : 'rgba(74, 222, 128, 0.05)',
                      color: isDirty ? '#4ade80' : '#2a4a3a',
                      fontSize: 9,
                      fontWeight: 600,
                      cursor: isDirty ? 'pointer' : 'not-allowed',
                      opacity: isDirty ? 1 : 0.5,
                      transition: 'all 0.15s',
                      letterSpacing: 0.5,
                    }}
                    onMouseEnter={(e) => {
                      if (isDirty) {
                        e.target.style.background = 'rgba(74, 222, 128, 0.15)';
                        e.target.style.borderColor = '#4ade8060';
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (isDirty) {
                        e.target.style.background = 'rgba(74, 222, 128, 0.1)';
                        e.target.style.borderColor = '#4ade8040';
                      }
                    }}
                  >
                    ✓ SAVE
                  </button>
                  <button
                    onClick={handleCancel}
                    style={{
                      padding: '4px 10px',
                      borderRadius: 3,
                      border: '1px solid #64748b40',
                      background: 'transparent',
                      color: '#64748b',
                      fontSize: 9,
                      fontWeight: 600,
                      cursor: 'pointer',
                      transition: 'all 0.15s',
                      letterSpacing: 0.5,
                    }}
                    onMouseEnter={(e) => {
                      e.target.style.background = 'rgba(100, 116, 139, 0.1)';
                      e.target.style.borderColor = '#64748b60';
                    }}
                    onMouseLeave={(e) => {
                      e.target.style.background = 'transparent';
                      e.target.style.borderColor = '#64748b40';
                    }}
                  >
                    × CANCEL
                  </button>
                </div>
              )
            )}

            <span style={{
              fontSize: 7, padding: '2px 8px', borderRadius: 3, letterSpacing: 1.5,
              background: '#1e1e30', color: '#5a5a72', fontWeight: 600,
            }}>{(type || '').toUpperCase()}</span>
            {entity?.status && (
              <span style={{
                fontSize: 7, padding: '2px 8px', borderRadius: 3, letterSpacing: 1,
                background: entity.status === 'active' ? '#0a2010' : '#24243a',
                color: entity.status === 'active' ? '#4ade80' : '#4a4a62',
              }}>{entity.status.toUpperCase()}</span>
            )}
          </div>
        </div>

        {/* Section Tabs */}
        <div style={{ display: 'flex', gap: 2, marginTop: 14, marginLeft: 16 }}>
          {sectionTabs.map(t => (
            <button key={t} onClick={() => setSection(t)} style={{
              padding: '4px 10px', fontSize: 8, letterSpacing: 1.5,
              borderRadius: 3, border: 'none', textTransform: 'uppercase',
              background: section === t ? '#24243e' : 'transparent',
              color: section === t ? '#c8ff00' : '#4a4a62',
              cursor: 'pointer', fontFamily: 'inherit', transition: 'all 0.12s',
            }}>{t}</button>
          ))}
        </div>
      </div>

      {/* Section Content */}
      <div style={{ flex: 1, overflow: 'auto', padding: '16px 20px' }}>

        {/* Edit Mode - JSON Editor */}
        {isEditing && section === 'overview' && (
          <div>
            <div style={{
              fontSize: 9,
              color: '#c084fc',
              marginBottom: 8,
              padding: '8px 12px',
              background: 'rgba(192, 132, 252, 0.05)',
              borderRadius: 4,
              border: '1px solid rgba(192, 132, 252, 0.2)',
            }}>
              ✎ Editing entity data — modify the JSON below. Changes will be saved to entity.data field.
            </div>
            <textarea
              value={JSON.stringify(draftData, null, 2)}
              onChange={(e) => {
                try {
                  const parsed = JSON.parse(e.target.value);
                  setDraftData(parsed);
                  setIsDirty(true);
                } catch {
                  // Keep typing, will parse on valid JSON
                  // Allow invalid intermediate states
                  if (e.target.value !== JSON.stringify(draftData, null, 2)) {
                    setIsDirty(true);
                  }
                }
              }}
              onBlur={(e) => {
                // Try to parse and reformat on blur
                try {
                  const parsed = JSON.parse(e.target.value);
                  setDraftData(parsed);
                } catch (err) {
                  alert('Invalid JSON. Please fix syntax errors.\n\n' + err.message);
                  // Reset to last valid state
                  e.target.value = JSON.stringify(draftData, null, 2);
                }
              }}
              style={{
                width: '100%',
                minHeight: 400,
                padding: 12,
                background: '#16161f',
                border: '1px solid #3a3a4e',
                borderRadius: 4,
                color: '#c8cad0',
                fontSize: 11,
                fontFamily: "'JetBrains Mono', monospace",
                lineHeight: 1.6,
                resize: 'vertical',
                outline: 'none',
              }}
              onFocus={(e) => {
                e.target.style.borderColor = '#c084fc40';
              }}
              spellCheck={false}
            />
            <div style={{
              marginTop: 8,
              fontSize: 9,
              color: '#5a5a72',
              fontFamily: "'JetBrains Mono', monospace",
            }}>
              {isDirty ? '● Unsaved changes' : 'No changes'} • {Object.keys(draftData).length} fields
            </div>
          </div>
        )}

        {/* Read-Only Overview */}
        {!isEditing && section === 'overview' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {/* Traits */}
            {traits && Array.isArray(traits) && traits.length > 0 && (
              <div>
                <div style={{ fontSize: 8, color: '#4a4a62', letterSpacing: 2, marginBottom: 6 }}>TRAITS</div>
                <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  {traits.map(t => (
                    <span key={t} style={{
                      fontSize: 9, padding: '3px 8px', borderRadius: 3,
                      background: '#18182a', border: '1px solid #24243a', color: '#9ca3af',
                    }}>{t}</span>
                  ))}
                </div>
              </div>
            )}

            {/* Arc */}
            {arc && (
              <div>
                <div style={{ fontSize: 8, color: '#4a4a62', letterSpacing: 2, marginBottom: 6 }}>ARC</div>
                <div style={{
                  fontSize: 11, color: '#c8cad0', lineHeight: 1.5, padding: '8px 12px',
                  background: '#16161f', borderRadius: 6, borderLeft: `2px solid ${color}30`,
                }}>{typeof arc === 'string' ? arc : arc.summary}</div>
                {arc.turning_point && (
                  <div style={{ fontSize: 8, color: '#5a5a72', marginTop: 4, marginLeft: 14 }}>
                    Turning point: <span style={{ color: '#6b6b80' }}>
                      {arc.turning_point.replace(/_/g, ' ')}
                    </span>
                  </div>
                )}
              </div>
            )}

            {/* Voice */}
            {voice && (
              <div>
                <div style={{ fontSize: 8, color: '#4a4a62', letterSpacing: 2, marginBottom: 6 }}>VOICE</div>
                <div style={{
                  fontSize: 10, color: '#6b6b80', lineHeight: 1.5, padding: '8px 12px',
                  background: '#16161f', borderRadius: 6,
                }}>
                  {voice.speech_pattern || (typeof voice === 'string' ? voice : '')}
                  {voice.verbal_tics?.length > 0 && (
                    <div style={{ marginTop: 6, fontSize: 9, color: '#5a5a72' }}>
                      {voice.verbal_tics.map((t, i) => <div key={i}>• {t}</div>)}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Camera Suggestion (locations) */}
            {cameraSuggestion && (
              <div>
                <div style={{ fontSize: 8, color: '#4a4a62', letterSpacing: 2, marginBottom: 6 }}>CAMERA NOTES</div>
                <div style={{
                  fontSize: 10, color: '#9ca3af', lineHeight: 1.5, padding: '8px 12px',
                  background: '#16161f', borderRadius: 6, borderLeft: '2px solid #f59e0b30',
                }}>{cameraSuggestion}</div>
              </div>
            )}

            {/* Lighting (locations) */}
            {lighting && (
              <div>
                <div style={{ fontSize: 8, color: '#4a4a62', letterSpacing: 2, marginBottom: 6 }}>LIGHTING</div>
                <div style={{ fontSize: 10, color: '#6b6b80', lineHeight: 1.5 }}>{lighting}</div>
              </div>
            )}

            {/* Significance (props) */}
            {significance && (
              <div>
                <div style={{ fontSize: 8, color: '#4a4a62', letterSpacing: 2, marginBottom: 6 }}>SIGNIFICANCE</div>
                <div style={{ fontSize: 10, color: '#6b6b80', lineHeight: 1.5 }}>{significance}</div>
              </div>
            )}

            {/* Relationships */}
            {relationships.length > 0 && (
              <div>
                <div style={{ fontSize: 8, color: '#4a4a62', letterSpacing: 2, marginBottom: 6 }}>RELATIONSHIPS</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {relationships.map((r, i) => (
                    <RelationshipBadge key={i} rel={r} allEntities={allEntities} onNavigate={onNavigate} annotatedEntities={annotatedEntities} />
                  ))}
                </div>
              </div>
            )}

            {/* Luna Notes */}
            {lunaNotes && (
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                  <span style={{ fontSize: 8, color: '#818cf8', letterSpacing: 2 }}>LUNA</span>
                </div>
                <div style={{
                  fontSize: 10, color: '#9ca3af', lineHeight: 1.6, padding: '10px 12px',
                  background: '#180f2a', borderRadius: 6, border: '1px solid #818cf820',
                  fontStyle: 'italic',
                }}>
                  <AnnotatedText text={lunaNotes} entities={annotatedEntities || []} onEntityClick={(slug) => {
                    const t = allEntities.find(e => e.slug === slug || e.id === slug);
                    if (t) onNavigate(t.type, t.slug);
                  }} />
                </div>
              </div>
            )}
          </div>
        )}

        {section === 'details' && isCharacter && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {physical && typeof physical === 'object' && (
              <div>
                <div style={{ fontSize: 8, color: '#4a4a62', letterSpacing: 2, marginBottom: 8 }}>PHYSICAL</div>
                {Object.entries(physical).map(([k, v]) => (
                  <div key={k} style={{
                    display: 'flex', gap: 12, padding: '4px 0',
                    borderBottom: '1px solid #18182a',
                  }}>
                    <span style={{
                      fontSize: 9, color: '#4a4a62', minWidth: 80, textTransform: 'capitalize',
                    }}>{k.replace(/_/g, ' ')}</span>
                    <span style={{ fontSize: 10, color: '#9ca3af', lineHeight: 1.4 }}>{v}</span>
                  </div>
                ))}
              </div>
            )}
            {wardrobe && typeof wardrobe === 'object' && (
              <div>
                <div style={{ fontSize: 8, color: '#4a4a62', letterSpacing: 2, marginBottom: 8 }}>WARDROBE</div>
                {Object.entries(wardrobe).map(([k, v]) => (
                  <div key={k} style={{
                    display: 'flex', gap: 12, padding: '4px 0',
                    borderBottom: '1px solid #18182a',
                  }}>
                    <span style={{
                      fontSize: 9, color: '#4a4a62', minWidth: 80, textTransform: 'capitalize',
                    }}>{k}</span>
                    <span style={{ fontSize: 10, color: '#9ca3af', lineHeight: 1.4 }}>{v}</span>
                  </div>
                ))}
              </div>
            )}
            {props.length > 0 && (
              <div>
                <div style={{ fontSize: 8, color: '#4a4a62', letterSpacing: 2, marginBottom: 6 }}>PROPS</div>
                {props.map((p, i) => (
                  <div key={i}
                    onClick={() => onNavigate('props', p.entity || p.slug)}
                    style={{
                      display: 'flex', gap: 8, padding: '6px 8px', borderRadius: 4,
                      cursor: 'pointer', background: '#16161f', border: '1px solid #1e1e30',
                      marginBottom: 4,
                    }}>
                    <span style={{ fontSize: 10, color: '#a78bfa' }}>
                      {(p.entity || p.slug || p.name || '').replace(/_/g, ' ')}
                    </span>
                    {p.note && (
                      <span style={{ fontSize: 9, color: '#5a5a72' }}>— {p.note}</span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {section === 'scenes' && (
          <div>
            {/* Live usage from reverse index */}
            <EntityUsagePanel entitySlug={entity?.slug} />

            {/* Static scene data from entity YAML (fallback) */}
            {scenes.length > 0 && (
              <div style={{ marginTop: 16, borderTop: '1px solid #1e1e30', paddingTop: 12 }}>
                <div style={{ fontSize: 8, color: '#4a4a62', letterSpacing: 2, marginBottom: 8 }}>ENTITY DATA</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                  {scenes.map(s => (
                    <div key={s} style={{
                      display: 'flex', alignItems: 'center', gap: 8, padding: '6px 10px',
                      background: '#16161f', borderRadius: 4, border: '1px solid #1e1e30',
                    }}>
                      <span style={{ fontSize: 10, color: '#c8ff00', fontWeight: 600, minWidth: 60 }}>
                        {String(s).replace(/_/g, ' ').toUpperCase()}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {firstAppearance && (
              <div style={{
                marginTop: 8, fontSize: 9, color: '#f59e0b', padding: '6px 10px',
                background: '#2a221008', borderRadius: 4, border: '1px solid #f59e0b20',
              }}>
                First appearance: {firstAppearance.replace(/_/g, ' ')}
              </div>
            )}
          </div>
        )}

        {section === 'refs' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div>
              <div style={{ fontSize: 8, color: '#4a4a62', letterSpacing: 2, marginBottom: 8 }}>
                REFERENCE IMAGES
              </div>
              {references?.images?.length > 0 ? (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
                  {references.images.map((img, i) => {
                    // Full URL (from Eden CDN) or relative path (local asset)
                    const src = img.startsWith('http')
                      ? img
                      : `/kozmo-assets/${activeProject?.slug}/assets/refs/${entity?.type}/${img}`;
                    return (
                      <div key={i} style={{
                        aspectRatio: '4/3',
                        background: 'linear-gradient(135deg, #1e1e30, #16161f)',
                        borderRadius: 6, border: '1px solid #24243a',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        overflow: 'hidden', position: 'relative',
                      }}>
                        <img
                          src={src}
                          alt={`${entity?.name || 'Entity'} ref ${i + 1}`}
                          style={{
                            width: '100%', height: '100%', objectFit: 'cover',
                          }}
                          onError={(e) => {
                            e.target.style.display = 'none';
                            e.target.nextSibling.style.display = 'flex';
                          }}
                        />
                        <span style={{
                          display: 'none', position: 'absolute', inset: 0,
                          alignItems: 'center', justifyContent: 'center',
                          fontSize: 8, color: '#3a3a4e', textAlign: 'center', padding: 8,
                        }}>{img}</span>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div style={{
                  padding: 20, background: '#16161f', borderRadius: 6,
                  border: '1px dashed #24243a', textAlign: 'center',
                }}>
                  <div style={{ fontSize: 9, color: '#3a3a4e', marginBottom: 4 }}>
                    No references yet
                  </div>
                  <div style={{ fontSize: 8, color: '#24243a' }}>
                    Click "Generate Reference Art" above
                  </div>
                </div>
              )}
            </div>
            <div>
              <div style={{ fontSize: 8, color: '#4a4a62', letterSpacing: 2, marginBottom: 6 }}>
                LoRA MODEL
              </div>
              {references?.lora ? (
                <div style={{
                  padding: '8px 12px', background: '#143018', borderRadius: 6,
                  border: '1px solid #4ade8020',
                  display: 'flex', alignItems: 'center', gap: 8,
                }}>
                  <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#4ade80' }} />
                  <span style={{ fontSize: 10, color: '#4ade80' }}>{references.lora}</span>
                  <span style={{ fontSize: 7, color: '#2a5a30', marginLeft: 'auto' }}>TRAINED</span>
                </div>
              ) : (
                <div style={{
                  padding: '8px 12px', background: '#16161f', borderRadius: 6,
                  border: '1px dashed #24243a',
                  display: 'flex', alignItems: 'center', gap: 8,
                }}>
                  <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#3a3a4e' }} />
                  <span style={{ fontSize: 10, color: '#4a4a62' }}>Not trained</span>
                  <span style={{ fontSize: 8, color: '#24243a', marginLeft: 'auto' }}>
                    Needs 3-10 ref images
                  </span>
                </div>
              )}
            </div>
            {/* Usage & Co-Appearance Stats */}
            {(() => {
              const usage = usageByEntity?.[entity?.slug];
              if (!usage) return null;
              // Find co-appearing entities from reverse index scene_entities
              const coAppearances = {};
              if (reverseIndex?.scene_entities) {
                Object.values(reverseIndex.scene_entities).forEach(entitySlugs => {
                  if (entitySlugs.includes(entity?.slug)) {
                    entitySlugs.forEach(s => {
                      if (s !== entity?.slug) {
                        coAppearances[s] = (coAppearances[s] || 0) + 1;
                      }
                    });
                  }
                });
              }
              const coList = Object.entries(coAppearances)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 8);

              return (
                <div>
                  <div style={{ fontSize: 8, color: '#4a4a62', letterSpacing: 2, marginBottom: 8 }}>
                    USAGE STATS
                  </div>
                  <div style={{ display: 'flex', gap: 12, marginBottom: 10 }}>
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: 16, color: '#e8e8f0', fontWeight: 700 }}>{usage.total_scenes}</div>
                      <div style={{ fontSize: 7, color: '#4a4a62' }}>scenes</div>
                    </div>
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: 16, color: entityColor(entity), fontWeight: 700 }}>{usage.mention_count || 0}</div>
                      <div style={{ fontSize: 7, color: '#4a4a62' }}>mentions</div>
                    </div>
                  </div>
                  {coList.length > 0 && (
                    <>
                      <div style={{ fontSize: 8, color: '#4a4a62', letterSpacing: 2, marginBottom: 6 }}>
                        CO-APPEARS WITH
                      </div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                        {coList.map(([slug, count]) => {
                          const coEntity = allEntities.find(e => e.slug === slug);
                          const coColor = coEntity ? entityColor(coEntity) : '#5a5a72';
                          return (
                            <span
                              key={slug}
                              onClick={() => coEntity && onNavigate(coEntity.type, coEntity.slug)}
                              style={{
                                fontSize: 8, padding: '2px 6px', borderRadius: 2,
                                background: coColor + '12', color: coColor,
                                border: `1px solid ${coColor}20`,
                                cursor: coEntity ? 'pointer' : 'default',
                              }}
                            >
                              {coEntity?.name || slug} ({count})
                            </span>
                          );
                        })}
                      </div>
                    </>
                  )}
                </div>
              );
            })()}

            {tags.length > 0 && (
              <div>
                <div style={{ fontSize: 8, color: '#4a4a62', letterSpacing: 2, marginBottom: 6 }}>
                  TAGS
                </div>
                <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  {tags.map(t => (
                    <span key={t} style={{
                      fontSize: 8, padding: '2px 6px', borderRadius: 2,
                      background: '#18182a', color: '#5a5a72',
                    }}>{t}</span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ============================================================================
// CREATE ENTITY FORM
// ============================================================================

function CreateEntityForm({ onClose }) {
  const { createEntity, loading } = useKozmo();
  const [type, setType] = useState('characters');
  const [name, setName] = useState('');
  const [tags, setTags] = useState('');

  const handleCreate = async () => {
    if (!name.trim()) return;
    const tagList = tags.split(',').map(t => t.trim()).filter(Boolean);
    const result = await createEntity(type, name.trim(), {}, tagList);
    if (result) onClose();
  };

  return (
    <div style={{
      position: 'absolute', inset: 0, background: 'rgba(8,8,14,0.9)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100,
    }}>
      <div style={{
        width: 340, padding: 20, background: 'rgba(22, 22, 36, 0.6)', backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)', borderRadius: 8,
        border: '1px solid #c8ff0030',
      }}>
        <div style={{
          fontSize: 10, color: '#c8ff00', letterSpacing: 2, marginBottom: 16,
        }}>NEW ENTITY</div>

        {/* Type selector */}
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 8, color: '#4a4a62', letterSpacing: 2, marginBottom: 6 }}>TYPE</div>
          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
            {['characters', 'locations', 'props', 'lore', 'events'].map(t => (
              <button key={t} onClick={() => setType(t)} style={{
                padding: '4px 10px', fontSize: 9, borderRadius: 4,
                border: `1px solid ${type === t ? '#c8ff00' : '#3a3a4e'}`,
                background: type === t ? 'rgba(200,255,0,0.08)' : 'transparent',
                color: type === t ? '#c8ff00' : '#6b6b80',
                cursor: 'pointer', fontFamily: 'inherit',
              }}>{t}</button>
            ))}
          </div>
        </div>

        {/* Name */}
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 8, color: '#4a4a62', letterSpacing: 2, marginBottom: 6 }}>NAME</div>
          <input
            value={name}
            onChange={e => setName(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleCreate()}
            autoFocus
            placeholder="Entity name..."
            style={{
              width: '100%', padding: '6px 10px', background: '#12121c',
              border: '1px solid #24243a', borderRadius: 4, color: '#c8cad0',
              fontFamily: 'inherit', fontSize: 11, outline: 'none',
            }}
          />
        </div>

        {/* Tags */}
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 8, color: '#4a4a62', letterSpacing: 2, marginBottom: 6 }}>
            TAGS (comma-separated)
          </div>
          <input
            value={tags}
            onChange={e => setTags(e.target.value)}
            placeholder="main_cast, act_1..."
            style={{
              width: '100%', padding: '6px 10px', background: '#12121c',
              border: '1px solid #24243a', borderRadius: 4, color: '#c8cad0',
              fontFamily: 'inherit', fontSize: 10, outline: 'none',
            }}
          />
        </div>

        {/* Actions */}
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button onClick={onClose} style={{
            padding: '6px 14px', borderRadius: 4, border: '1px solid #24243a',
            background: 'transparent', color: '#4a4a62', fontSize: 10,
            cursor: 'pointer', fontFamily: 'inherit',
          }}>cancel</button>
          <button
            onClick={handleCreate}
            disabled={loading || !name.trim()}
            style={{
              padding: '6px 14px', borderRadius: 4, border: 'none',
              background: name.trim() ? '#c8ff00' : '#24243a',
              color: name.trim() ? '#12121c' : '#4a4a62',
              fontWeight: 700, fontSize: 10,
              cursor: name.trim() ? 'pointer' : 'not-allowed',
              fontFamily: 'inherit',
            }}>
            {loading ? '...' : 'CREATE'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// MAIN CODEX
// ============================================================================

const AGENTS = [
  { id: 'chiba', name: 'Chiba', role: 'Orchestrator', color: '#c8ff00' },
  { id: 'maya', name: 'Maya', role: 'Vision', color: '#4ade80' },
  { id: 'di_agent', name: 'DI Agent', role: 'Post', color: '#f59e0b' },
  { id: 'luna', name: 'Luna', role: 'Context', color: '#818cf8' },
  { id: 'foley', name: 'Foley', role: 'Audio', color: '#6b6b80' },
];

export default function KozmoCodex({ savedState, onSaveState }) {
  const {
    activeProject, entities, selectedEntity, selectEntity,
    annotatedEntities: kozmoAnnotatedEntities,
    usageByEntity, reverseIndex,
    agentStatus, generationQueue, updateEntity,
    generateEntityRef,
  } = useKozmo();

  // Initialize from savedState if available
  const [searchQuery, setSearchQuery] = useState(savedState?.searchQuery || '');
  const [showCreateForm, setShowCreateForm] = useState(savedState?.showCreateForm || false);
  const [showBulkImport, setShowBulkImport] = useState(false);
  const [codexView, setCodexView] = useState(savedState?.codexView || 'entities'); // 'entities' | 'board'
  const { messages: agentChat, isStreaming: chatStreaming, send: chatSend, stop: chatStop, setPageContext } = useKozmoChat();
  const [generatingRef, setGeneratingRef] = useState(false);

  // Save state to machine whenever key state changes
  useEffect(() => {
    if (onSaveState) {
      onSaveState({
        searchQuery,
        showCreateForm,
        codexView,
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchQuery, showCreateForm, codexView]);

  // Auto-select entity when navigating from SCRIBO
  useEffect(() => {
    if (savedState?.selectedEntitySlug && savedState?.selectedEntityType) {
      const slug = savedState.selectedEntitySlug;
      const type = savedState.selectedEntityType;

      // Only select if entity exists and isn't already selected
      if (entities[slug] && selectedEntity?.slug !== slug) {
        selectEntity(type, slug);
      }
    }
  }, [savedState?.selectedEntitySlug, savedState?.selectedEntityType, entities, selectEntity, selectedEntity?.slug]);

  // Group entities by type
  const allEntitiesList = useMemo(() => Object.values(entities), [entities]);

  const grouped = useMemo(() => {
    const groups = { characters: [], locations: [], props: [], lore: [], events: [] };
    allEntitiesList.forEach(e => {
      const type = e.type || 'lore';
      const key = type.endsWith('s') ? type : type + 's';
      if (!groups[key]) groups[key] = [];
      groups[key].push(e);
    });
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      const filter = items => items.filter(e =>
        e.name?.toLowerCase().includes(q) ||
        e.slug?.includes(q) ||
        e.tags?.some(t => t.includes(q)) ||
        d(e, 'luna_notes')?.toLowerCase().includes(q)
      );
      return Object.fromEntries(
        Object.entries(groups).map(([k, v]) => [k, filter(v)])
      );
    }
    return groups;
  }, [allEntitiesList, searchQuery]);

  const entity = selectedEntity?.entity;
  const entityType = selectedEntity?.type;

  // Feed page context to Luna so she knows what entity is on screen
  useEffect(() => {
    const parts = [];
    if (activeProject?.name) parts.push(`Project: ${activeProject.name}`);
    if (entity?.name) parts.push(`Entity: ${entity.name} (${entityType || 'unknown'})`);
    if (d(entity, 'desc') || d(entity, 'description')) parts.push(`Description: ${(d(entity, 'desc') || d(entity, 'description')).slice(0, 300)}`);
    if (d(entity, 'luna_notes')) parts.push(`Luna's notes: ${d(entity, 'luna_notes').slice(0, 300)}`);
    const rels = d(entity, 'relationships');
    if (rels?.length) parts.push(`Relationships: ${rels.slice(0, 5).map(r => `${r.type}: ${r.entity}`).join(', ')}`);
    setPageContext(parts.length ? parts.join('\n') : '');
  }, [activeProject?.name, entity?.name, entity?.slug, entityType, setPageContext]);

  // Navigate to entity
  const handleNavigate = useCallback((type, slug) => {
    selectEntity(type, slug);
    const target = entities[slug];
    if (target) {
      const refs = d(target, 'references');
      const imgCount = refs?.images?.length || 0;
      console.log(`[CODEX] ${target.name} loaded. ${imgCount} reference images.`);
    }
  }, [selectEntity, entities]);

  // Agent chat — wired to Luna via useKozmoChat (streaming)

  // Relationship mini-map — outgoing + incoming
  const relationshipNodes = useMemo(() => {
    if (!entity) return [];
    const outgoing = (d(entity, 'relationships') || []).map(r => {
      const targetSlug = r.entity || r.slug;
      const target = entities[targetSlug] || allEntitiesList.find(e => e.name === r.entity);
      return target ? { ...target, relType: r.type, direction: 'out' } : null;
    }).filter(Boolean);

    // Find incoming relationships (other entities that reference this one)
    const entitySlug = entity?.slug;
    const incoming = [];
    const outSlugs = new Set(outgoing.map(n => n.slug));
    allEntitiesList.forEach(other => {
      if (other.slug === entitySlug) return;
      if (outSlugs.has(other.slug)) return; // Already shown as outgoing
      const otherRels = d(other, 'relationships') || [];
      const rel = otherRels.find(r => r.entity === entitySlug || r.slug === entitySlug);
      if (rel) {
        incoming.push({ ...other, relType: rel.type, direction: 'in' });
      }
    });

    return [...outgoing, ...incoming];
  }, [entity, entities, allEntitiesList]);

  const eColor = entity ? entityColor(entity) : '#c8ff00';

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', height: '100%', position: 'relative',
    }}>
      {showCreateForm && <CreateEntityForm onClose={() => setShowCreateForm(false)} />}
      <BulkImportModal isOpen={showBulkImport} onClose={() => setShowBulkImport(false)} />

      {/* VIEW TOGGLE: Entities vs Production Board */}
      <div style={{
        height: 36, display: 'flex', alignItems: 'center', gap: 8,
        padding: '0 16px', borderBottom: '1px solid #1e1e30',
        background: 'rgba(20, 20, 28, 0.4)', backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)',
        flexShrink: 0,
      }}>
        {[
          { id: 'entities', label: 'WORLD BIBLE', icon: '◆' },
          { id: 'board', label: 'PRODUCTION BOARD', icon: '▦' },
          { id: 'library', label: 'ASSET LIBRARY', icon: '◎' },
        ].map(v => (
          <button key={v.id} onClick={() => setCodexView(v.id)} style={{
            padding: '4px 12px', fontSize: 9, borderRadius: 4, border: 'none',
            background: codexView === v.id ? 'rgba(200, 255, 0, 0.08)' : 'transparent',
            color: codexView === v.id ? '#c8ff00' : '#5a5a72',
            cursor: 'pointer', fontFamily: 'inherit', fontWeight: codexView === v.id ? 600 : 400,
            letterSpacing: 1, transition: 'all 0.15s',
          }}>
            {v.icon} {v.label}
          </button>
        ))}
      </div>

      {/* ASSET LIBRARY VIEW */}
      {codexView === 'library' ? (
        <div style={{ flex: 1, overflow: 'hidden' }}>
          <MediaLibrary />
        </div>
      ) : codexView === 'board' ? (
        <div style={{ flex: 1, overflow: 'hidden' }}>
          <ProductionBoard />
        </div>
      ) : (
      <>
      {/* MAIN BODY */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>

        {/* LEFT: File Tree */}
        <div style={{
          width: 220, borderRight: '1px solid #1e1e30', background: 'rgba(20, 20, 28, 0.4)',
          backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)',
          display: 'flex', flexDirection: 'column', flexShrink: 0,
        }}>
          <FileTree
            grouped={grouped}
            selected={selectedEntity?.slug}
            onSelect={handleNavigate}
            searchQuery={searchQuery}
            onSearchChange={setSearchQuery}
          />
          <div style={{
            borderTop: '1px solid #1e1e30', padding: '6px 10px',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          }}>
            <div style={{ display: 'flex', gap: 4 }}>
              <button onClick={() => setShowCreateForm(true)} style={{
                padding: '3px 8px', fontSize: 8, borderRadius: 3,
                border: '1px dashed #c8ff0040', background: 'transparent',
                color: '#c8ff00', cursor: 'pointer', fontFamily: 'inherit',
              }}>+ New</button>
              <button onClick={() => setShowBulkImport(true)} style={{
                padding: '3px 8px', fontSize: 8, borderRadius: 3,
                border: '1px dashed #4ade8040', background: 'transparent',
                color: '#4ade80', cursor: 'pointer', fontFamily: 'inherit',
              }}>↓ Import</button>
            </div>
            <span style={{ fontSize: 7, color: '#24243a' }}>
              {activeProject?.slug && `projects/${activeProject.slug}/`}
            </span>
          </div>
        </div>

        {/* CENTER: Entity View */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: 'rgba(16, 16, 26, 0.4)', backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)' }}>
          {entity ? (
            <EntityCard
              entity={entity}
              entityType={entityType}
              allEntities={allEntitiesList}
              annotatedEntities={kozmoAnnotatedEntities}
              usageByEntity={usageByEntity}
              reverseIndex={reverseIndex}
              activeProject={activeProject}
              onNavigate={handleNavigate}
              onUpdate={updateEntity}
            />
          ) : (
            <div style={{
              flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 20, color: '#24243a', marginBottom: 8 }}>◎</div>
                <div style={{ fontSize: 12, color: '#4a4a62' }}>Select an entity</div>
                <div style={{ fontSize: 9, color: '#24243a', marginTop: 4 }}>
                  or create one with + New
                </div>
              </div>
            </div>
          )}
        </div>

        {/* RIGHT: Agent Panel */}
        <div style={{
          width: 320, borderLeft: '1px solid #1e1e30', background: 'rgba(20, 20, 28, 0.4)',
          backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)',
          display: 'flex', flexDirection: 'column', flexShrink: 0,
        }}>
          {/* Agent Roster */}
          <div style={{ padding: '10px 12px', borderBottom: '1px solid #1e1e30' }}>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {AGENTS.map(a => {
                const status = agentStatus[a.id] || 'standby';
                const isActive = ['live', 'idle', 'active', 'ready'].includes(status);
                return (
                  <div key={a.id} style={{
                    display: 'flex', alignItems: 'center', gap: 4, padding: '3px 8px',
                    borderRadius: 4,
                    background: isActive ? `${a.color}08` : '#18182a',
                    border: `1px solid ${isActive ? a.color + '20' : '#1e1e30'}`,
                  }} title={`${a.name} (${a.role}) — ${status}`}>
                    <div style={{
                      width: 5, height: 5, borderRadius: '50%',
                      background: status === 'standby' ? '#3a3a4e' : a.color,
                      boxShadow: status !== 'standby' ? `0 0 4px ${a.color}40` : 'none',
                    }} />
                    <span style={{
                      fontSize: 8, color: status === 'standby' ? '#4a4a62' : '#9ca3af',
                    }}>{a.name}</span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Quick Actions */}
          {entity && (
            <div style={{ padding: '10px 12px', borderBottom: '1px solid #1e1e30' }}>
              <div style={{
                fontSize: 7, color: '#4a4a62', letterSpacing: 2, marginBottom: 6,
              }}>ACTIONS · {entity.name?.toUpperCase()}</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                {[
                  { label: 'Generate Reference Art', icon: '◎', agent: 'Maya', color: '#4ade80', action: 'generate-ref' },
                  { label: 'Create Eden Prompt', icon: '✦', agent: 'Chiba', color: '#c8ff00' },
                  { label: 'Run Continuity Check', icon: '⚡', agent: 'Luna', color: '#818cf8' },
                  { label: 'Open in Studio', icon: '▶', agent: '→ Studio', color: '#6b6b80' },
                ].map((action, i) => (
                  <button key={i}
                    disabled={action.action === 'generate-ref' && generatingRef}
                    onClick={async () => {
                      if (action.action === 'generate-ref' && generateEntityRef && entity) {
                        setGeneratingRef(true);
                        chatSend(`generate reference art for ${entity.name}`);
                        try {
                          const result = await generateEntityRef(entity.type, entity.slug);
                          if (result) {
                            console.log(`[CODEX] Reference art generated: ${result.filename}`);
                          } else {
                            console.warn('[CODEX] Generation failed. Check EDEN_API_KEY.');
                          }
                        } catch (e) {
                          console.error(`[CODEX] Generate error: ${e.message}`);
                        } finally {
                          setGeneratingRef(false);
                        }
                        return;
                      }
                      // Dispatch action to Luna
                      chatSend(`${action.label.toLowerCase()} for ${entity?.name || 'entity'}`);
                    }}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 8, width: '100%',
                      padding: '6px 10px', borderRadius: 4, border: 'none',
                      background: 'transparent',
                      cursor: (action.action === 'generate-ref' && generatingRef) ? 'wait' : 'pointer',
                      fontFamily: 'inherit', textAlign: 'left', transition: 'background 0.1s',
                      opacity: (action.action === 'generate-ref' && generatingRef) ? 0.5 : 1,
                    }}
                    onMouseEnter={e => e.currentTarget.style.background = '#1c1c30'}
                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                    <span style={{ fontSize: 12, color: action.color, width: 16 }}>
                      {(action.action === 'generate-ref' && generatingRef) ? '⟳' : action.icon}
                    </span>
                    <span style={{ fontSize: 9, color: '#9ca3af', flex: 1 }}>
                      {(action.action === 'generate-ref' && generatingRef) ? 'Generating...' : action.label}
                    </span>
                    <span style={{ fontSize: 7, color: '#3a3a4e' }}>{action.agent}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Agent Chat — Luna streaming */}
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            <div style={{ padding: '8px 12px', borderBottom: '1px solid #1e1e30' }}>
              <div style={{ fontSize: 7, color: '#818cf8', letterSpacing: 2 }}>
                LUNA + EDEN AGENTS
              </div>
            </div>
            <KozmoChat
              messages={agentChat}
              isStreaming={chatStreaming}
              onSend={chatSend}
              onStop={chatStop}
              placeholder={entity ? `Ask about ${entity.name}...` : 'Select an entity...'}
            />
          </div>

          {/* Generation Queue */}
          <div style={{ borderTop: '1px solid #1e1e30', maxHeight: 120, overflow: 'auto' }}>
            <div style={{
              padding: '6px 12px', fontSize: 7, color: '#4a4a62',
              letterSpacing: 2, borderBottom: '1px solid #18182a',
            }}>
              QUEUE · {generationQueue.length}
            </div>
            {generationQueue.length === 0 && (
              <div style={{
                padding: '8px 12px', fontSize: 8, color: '#24243a', fontStyle: 'italic',
              }}>No active tasks</div>
            )}
            {generationQueue.map((item, i) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: 8, padding: '5px 12px',
                borderBottom: '1px solid #0d0d1a',
              }}>
                <div style={{
                  width: 5, height: 5, borderRadius: '50%',
                  background: item.status === 'complete' ? '#4ade80'
                    : item.status === 'running' ? '#f59e0b' : '#4a4a62',
                }} />
                <span style={{
                  fontSize: 8, color: '#6b6b80', flex: 1,
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}>
                  {item.task || item.description}
                </span>
                {item.agent && (
                  <span style={{ fontSize: 7, color: '#3a3a4e' }}>{item.agent}</span>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* BOTTOM: Relationship Mini-Map */}
      <div style={{
        height: 52, borderTop: '1px solid #1e1e30', background: 'rgba(14, 14, 22, 0.6)',
        backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)',
        display: 'flex', alignItems: 'center', padding: '0 16px',
        flexShrink: 0, gap: 12,
      }}>
        <span style={{ fontSize: 8, color: '#4a4a62', letterSpacing: 2, minWidth: 50 }}>
          GRAPH
        </span>

        {entity ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            {/* Center node */}
            <div style={{
              width: 24, height: 24, borderRadius: '50%',
              background: `${eColor}15`, border: `2px solid ${eColor}`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 7, color: eColor, fontWeight: 700,
            }}>{entity.name?.charAt(0)}</div>

            {/* Connected nodes (outgoing + incoming) */}
            {relationshipNodes.slice(0, 6).map((node, i) => {
              const nColor = entityColor(node);
              const isIncoming = node.direction === 'in';
              return (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 2 }}
                  onClick={() => handleNavigate(node.type, node.slug)}>
                  <div style={{
                    width: 16 + (i * 3), height: 1,
                    background: `${nColor}30`,
                    borderTop: isIncoming ? `1px dashed ${nColor}40` : 'none',
                  }} />
                  <div style={{
                    padding: '3px 8px', borderRadius: 10,
                    background: `${nColor}10`,
                    border: `1px ${isIncoming ? 'dashed' : 'solid'} ${nColor}25`,
                    fontSize: 8, color: nColor, cursor: 'pointer',
                    whiteSpace: 'nowrap', transition: 'all 0.15s',
                  }}
                    onMouseEnter={e => {
                      e.currentTarget.style.background = `${nColor}20`;
                      e.currentTarget.style.borderColor = `${nColor}50`;
                    }}
                    onMouseLeave={e => {
                      e.currentTarget.style.background = `${nColor}10`;
                      e.currentTarget.style.borderColor = `${nColor}25`;
                    }}
                    title={isIncoming ? `${node.name} → ${node.relType} → ${entity.name}` : `${entity.name} → ${node.relType} → ${node.name}`}>
                    <span style={{ fontSize: 6, opacity: 0.6, marginRight: 3 }}>
                      {isIncoming ? '←' : ''}{node.relType}{isIncoming ? '' : '→'}
                    </span>
                    {node.name}
                  </div>
                </div>
              );
            })}
            {relationshipNodes.length > 6 && (
              <span style={{ fontSize: 8, color: '#4a4a62', marginLeft: 4 }}>
                +{relationshipNodes.length - 6} more
              </span>
            )}
          </div>
        ) : (
          <span style={{ fontSize: 8, color: '#24243a' }}>
            Select an entity to view relationships
          </span>
        )}

        <div style={{ flex: 1 }} />
        <div style={{ fontSize: 7, color: '#24243a', display: 'flex', gap: 12 }}>
          <span>◉ character</span>
          <span>◈ location</span>
          <span>◇ prop</span>
          <span>◆ lore</span>
        </div>
      </div>
      </>
      )}
    </div>
  );
}
