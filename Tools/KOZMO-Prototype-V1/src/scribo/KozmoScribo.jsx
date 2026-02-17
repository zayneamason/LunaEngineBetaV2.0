/**
 * KOZMO SCRIBO — The Writer's Room
 *
 * Layout: 3-panel
 *   LEFT:   Story tree navigation + quick stats
 *   CENTER: Scene editor (mixed Fountain/prose) + word count bar
 *   RIGHT:  Agent chat + Codex sidebar (tabbed)
 *
 * Wired to KozmoProvider for real API data.
 * Design adapted from ClaudeArtifacts/scribo.jsx
 */
import React, { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import { useKozmo } from '../KozmoProvider';
import { EntityAutocomplete } from './EntityAutocomplete';
import { ValidationFeedback } from './ValidationFeedback';
import { validateFrontmatter } from '../utils/frontmatterValidator';

// ============================================================================
// Constants
// ============================================================================

const STATUS = {
  polished: { color: '#4ade80', label: 'Polished', bg: 'rgba(74, 222, 128, 0.1)' },
  revised: { color: '#818cf8', label: 'Revised', bg: 'rgba(129, 140, 248, 0.1)' },
  draft: { color: '#fbbf24', label: 'Draft', bg: 'rgba(251, 191, 36, 0.1)' },
  idea: { color: '#64748b', label: 'Idea', bg: 'rgba(100, 116, 139, 0.1)' },
  'in-progress': { color: '#c084fc', label: 'In Progress', bg: 'rgba(192, 132, 252, 0.1)' },
};

const TYPE_ICONS = { root: '◈', series: '◈', act: '◆', chapter: '§', scene: '¶' };

const AGENTS = [
  { id: 'luna', name: 'Luna', role: 'Memory & Context', color: '#c084fc', status: 'active', avatar: '☾' },
  { id: 'maya', name: 'Maya', role: 'Visual Design', color: '#34d399', status: 'idle', avatar: '◐' },
  { id: 'chiba', name: 'Chiba', role: 'Orchestrator', color: '#818cf8', status: 'idle', avatar: '◈' },
  { id: 'ben', name: 'Ben', role: 'The Scribe', color: '#fbbf24', status: 'idle', avatar: '✎' },
];

const TYPE_COLORS = {
  characters: '#4ade80', character: '#4ade80',
  locations: '#f59e0b', location: '#f59e0b',
  props: '#a78bfa', prop: '#a78bfa',
};

const entityColor = (e) => e?.data?.color || e?.color || TYPE_COLORS[e?.type] || '#64748b';

// ============================================================================
// Helpers
// ============================================================================

function normalizeNode(node) {
  if (!node) return null;
  return {
    id: node.id,
    title: node.title,
    type: node.type,
    icon: TYPE_ICONS[node.type] || '¶',
    status: node.status || 'idea',
    wordCount: node.word_count ?? node.wordCount ?? 0,
    children: (node.children || []).map(normalizeNode),
  };
}

function findNode(tree, id) {
  if (!tree) return null;
  if (tree.id === id) return tree;
  if (tree.children) {
    for (const child of tree.children) {
      const found = findNode(child, id);
      if (found) return found;
    }
  }
  return null;
}

function buildPath(tree, id, trail = []) {
  if (!tree) return null;
  if (tree.id === id) return [...trail, tree];
  if (tree.children) {
    for (const child of tree.children) {
      const found = buildPath(child, id, [...trail, tree]);
      if (found) return found;
    }
  }
  return null;
}

// ============================================================================
// Components
// ============================================================================

function StoryTree({ tree, selected, onSelect, depth = 0, expanded, onToggle, onDelete }) {
  const [isHovered, setIsHovered] = useState(false);
  const isExpanded = expanded.has(tree.id);
  const isSelected = selected === tree.id;
  const hasChildren = tree.children && tree.children.length > 0;
  const status = STATUS[tree.status] || STATUS.idea;
  const isScene = tree.type === 'scene';

  return (
    <div>
      <div
        style={{
          display: 'flex', alignItems: 'center', gap: 8,
          padding: '6px 8px 6px ' + (12 + depth * 16) + 'px',
          cursor: 'pointer', borderRadius: 4,
          background: isSelected ? 'rgba(192, 132, 252, 0.12)' : 'transparent',
          borderLeft: isSelected ? '2px solid #c084fc' : '2px solid transparent',
          transition: 'all 0.15s ease',
          position: 'relative',
        }}
        onMouseEnter={(e) => {
          setIsHovered(true);
          if (!isSelected) e.currentTarget.style.background = 'rgba(255,255,255,0.03)';
        }}
        onMouseLeave={(e) => {
          setIsHovered(false);
          if (!isSelected) e.currentTarget.style.background = 'transparent';
        }}
      >
        <div
          onClick={() => {
            onSelect(tree.id, tree);
            if (hasChildren) onToggle(tree.id);
          }}
          style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1 }}
        >
          {hasChildren && (
            <span style={{ color: '#4a4a5a', fontSize: 10, width: 12, textAlign: 'center', flexShrink: 0 }}>
              {isExpanded ? '▾' : '▸'}
            </span>
          )}
          {!hasChildren && <span style={{ width: 12, flexShrink: 0 }} />}
          <span style={{ color: status.color, fontSize: 11, flexShrink: 0 }}>{tree.icon}</span>
          <span style={{
            color: isSelected ? '#e2e8f0' : '#94a3b8',
            fontSize: 13, fontFamily: "'Space Grotesk', sans-serif",
            flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            fontWeight: isSelected ? 500 : 400,
          }}>
            {tree.title}
          </span>
          <span style={{
            color: status.color, fontSize: 9, padding: '1px 6px',
            background: status.bg, borderRadius: 3,
            fontFamily: "'JetBrains Mono', monospace", flexShrink: 0,
          }}>
            {tree.wordCount ? (tree.wordCount / 1000).toFixed(1) + 'k' : ''}
          </span>
        </div>

        {/* Delete button (only for scenes, only on hover) */}
        {isScene && isHovered && onDelete && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onDelete(tree.id);
            }}
            style={{
              padding: '2px 6px',
              background: 'rgba(239, 68, 68, 0.1)',
              border: '1px solid rgba(239, 68, 68, 0.3)',
              borderRadius: 3,
              color: '#ef4444',
              fontSize: 9,
              cursor: 'pointer',
              transition: 'all 0.15s',
              flexShrink: 0,
            }}
            onMouseEnter={(e) => {
              e.target.style.background = 'rgba(239, 68, 68, 0.2)';
              e.target.style.borderColor = 'rgba(239, 68, 68, 0.5)';
            }}
            onMouseLeave={(e) => {
              e.target.style.background = 'rgba(239, 68, 68, 0.1)';
              e.target.style.borderColor = 'rgba(239, 68, 68, 0.3)';
            }}
            title="Delete scene"
          >
            ×
          </button>
        )}
      </div>
      {hasChildren && isExpanded && tree.children.map(child => (
        <StoryTree
          key={child.id}
          tree={child}
          selected={selected}
          onSelect={onSelect}
          depth={depth + 1}
          expanded={expanded}
          onToggle={onToggle}
          onDelete={onDelete}
        />
      ))}
    </div>
  );
}

function Breadcrumb({ path, onNavigate }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '0 4px' }}>
      {path.map((item, i) => (
        <span key={item.id} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          {i > 0 && <span style={{ color: '#2a2a3a', fontSize: 11 }}>›</span>}
          <span
            onClick={() => onNavigate(item.id, item)}
            style={{
              color: i === path.length - 1 ? '#e2e8f0' : '#4a4a5a',
              fontSize: 12, cursor: 'pointer',
              fontFamily: "'JetBrains Mono', monospace",
              transition: 'color 0.15s',
            }}
            onMouseEnter={e => e.currentTarget.style.color = '#c084fc'}
            onMouseLeave={e => e.currentTarget.style.color = i === path.length - 1 ? '#e2e8f0' : '#4a4a5a'}
          >
            {item.icon} {item.title.length > 25 ? item.title.slice(0, 25) + '…' : item.title}
          </span>
        </span>
      ))}
    </div>
  );
}

function LunaNoteDisplay({ note }) {
  const typeColors = {
    continuity: { border: '#f87171', icon: '⚠', label: 'CONTINUITY' },
    tone: { border: '#818cf8', icon: '♪', label: 'TONE' },
    thematic: { border: '#c084fc', icon: '◇', label: 'THEME' },
    production: { border: '#fbbf24', icon: '▲', label: 'PRODUCTION' },
    character: { border: '#4ade80', icon: '◉', label: 'CHARACTER' },
  };
  const t = typeColors[note.type] || typeColors.thematic;

  return (
    <div style={{
      display: 'flex', gap: 10, padding: '8px 12px', marginBottom: 6,
      borderLeft: `2px solid ${t.border}`, borderRadius: '0 4px 4px 0',
      background: 'rgba(18, 18, 26, 0.6)',
    }}>
      <span style={{ color: t.border, fontSize: 11, flexShrink: 0, fontFamily: "'JetBrains Mono', monospace" }}>
        {t.icon} {t.label}
      </span>
      <span style={{ color: '#94a3b8', fontSize: 12, lineHeight: 1.5, fontStyle: 'italic' }}>
        {note.text}
      </span>
    </div>
  );
}

// ============================================================================
// Frontmatter Editor Component
// ============================================================================

function FrontmatterEditor({ scene, isEditing, onChange, entities }) {
  const fm = scene?.frontmatter || {};

  // Local state for editing
  const [draft, setDraft] = useState({
    characters_present: fm.characters_present || [],
    location: fm.location || '',
    time: fm.time || '',
    status: fm.status || 'draft',
  });

  // Validation state
  const [validation, setValidation] = useState({ errors: [], warnings: [], suggestions: [] });

  // Update draft when scene changes
  useEffect(() => {
    setDraft({
      characters_present: fm.characters_present || [],
      location: fm.location || '',
      time: fm.time || '',
      status: fm.status || 'draft',
    });
  }, [scene?.slug]);

  // Run validation when draft or entities change (only in edit mode)
  useEffect(() => {
    if (isEditing) {
      const results = validateFrontmatter(draft, entities, {
        sceneNumber: extractSceneNumber(scene?.slug),
      });
      setValidation(results);
    }
  }, [draft, entities, isEditing, scene]);

  const handleUpdate = (field, value) => {
    const updated = { ...draft, [field]: value };
    setDraft(updated);
    onChange(updated);
  };

  const handleValidationAction = async (action) => {
    switch (action.type) {
      case 'add_props':
        const updatedProps = [...(draft.props || []), ...action.props];
        handleUpdate('props', updatedProps);
        break;

      case 'set_time':
        handleUpdate('time', action.time);
        break;

      case 'fix_status':
        if (action.validValues && action.validValues.length > 0) {
          handleUpdate('status', action.validValues[0]);
        }
        break;

      case 'create_entity':
        // TODO: Wire to entity creation modal
        console.log('Create entity:', action);
        alert(`To create "${action.entityName}" as a ${action.entityType}, switch to CODEX tab`);
        break;

      case 'view_entity':
        // TODO: Wire to navigation
        console.log('View entity:', action.entitySlug);
        break;

      case 'define_relationship':
        // TODO: Wire to relationship editor
        console.log('Define relationship:', action);
        break;

      default:
        console.warn('Unknown action type:', action.type);
    }
  };

  // Filter entities by type
  const characterEntities = entities.filter(e => e.type === 'character' || e.type === 'characters');
  const locationEntities = entities.filter(e => e.type === 'location' || e.type === 'locations');

  if (!isEditing) {
    // Read-only display (existing design)
    return (
      <div style={{
        display: 'flex', gap: 12, padding: '10px 16px',
        borderBottom: '1px solid #1e1e2e', flexWrap: 'wrap', alignItems: 'center',
      }}>
        {draft.characters_present?.map(cid => {
          const ent = entities.find(e => e.id === cid || e.slug === cid);
          return ent ? (
            <span key={cid} style={{
              display: 'flex', alignItems: 'center', gap: 4, padding: '2px 8px',
              background: entityColor(ent) + '15', borderRadius: 3, border: `1px solid ${entityColor(ent)}30`,
            }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: entityColor(ent) }} />
              <span style={{ color: entityColor(ent), fontSize: 11, fontFamily: "'JetBrains Mono', monospace" }}>
                {ent.name}
              </span>
            </span>
          ) : (
            <span key={cid} style={{
              display: 'flex', alignItems: 'center', gap: 4, padding: '2px 8px',
              background: '#64748b15', borderRadius: 3, border: '1px solid #64748b30',
            }}>
              <span style={{ color: '#64748b', fontSize: 11, fontFamily: "'JetBrains Mono', monospace" }}>
                {cid}
              </span>
            </span>
          );
        })}
        <span style={{ color: '#4a4a5a', fontSize: 11, fontFamily: "'JetBrains Mono', monospace" }}>
          ◎ {entities.find(e => e.id === draft.location || e.slug === draft.location)?.name || draft.location || '—'}
        </span>
        <span style={{ color: '#4a4a5a', fontSize: 11, fontFamily: "'JetBrains Mono', monospace" }}>
          ◑ {draft.time || '—'}
        </span>
        <span style={{
          marginLeft: 'auto', color: STATUS[draft.status]?.color || '#64748b',
          fontSize: 10, padding: '2px 8px', borderRadius: 3,
          background: STATUS[draft.status]?.bg || 'transparent',
          fontFamily: "'JetBrains Mono', monospace", textTransform: 'uppercase',
        }}>
          {draft.status || 'draft'}
        </span>
      </div>
    );
  }

  // Edit mode form
  return (
    <div style={{
      padding: '16px',
      borderBottom: '1px solid #1e1e2e',
      background: 'rgba(192, 132, 252, 0.03)',
    }}>
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: '16px',
      }}>
        {/* Characters Present */}
        <div>
          <label style={{
            display: 'block',
            fontSize: 11,
            color: '#94a3b8',
            fontFamily: "'Space Grotesk', sans-serif",
            fontWeight: 600,
            marginBottom: 8,
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
          }}>
            Characters Present
          </label>
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 6,
            maxHeight: 200,
            overflowY: 'auto',
            padding: '8px',
            background: '#0a0a0f',
            borderRadius: 4,
            border: '1px solid #2a2a3a',
          }}>
            {characterEntities.length > 0 ? characterEntities.map(char => (
              <label key={char.id || char.slug} style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                cursor: 'pointer',
                padding: '4px 6px',
                borderRadius: 3,
                transition: 'background 0.15s',
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(100, 116, 139, 0.1)'; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
              >
                <input
                  type="checkbox"
                  checked={draft.characters_present.includes(char.id || char.slug)}
                  onChange={(e) => {
                    const charId = char.id || char.slug;
                    const chars = e.target.checked
                      ? [...draft.characters_present, charId]
                      : draft.characters_present.filter(s => s !== charId);
                    handleUpdate('characters_present', chars);
                  }}
                  style={{ cursor: 'pointer' }}
                />
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: entityColor(char) }} />
                <span style={{
                  color: '#cbd5e1',
                  fontSize: 12,
                  fontFamily: "'JetBrains Mono', monospace",
                }}>
                  {char.name}
                </span>
              </label>
            )) : (
              <div style={{ color: '#4a4a5a', fontSize: 11, fontStyle: 'italic', padding: 8 }}>
                No characters defined yet
              </div>
            )}
          </div>
        </div>

        {/* Location & Time */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Location */}
          <div>
            <label style={{
              display: 'block',
              fontSize: 11,
              color: '#94a3b8',
              fontFamily: "'Space Grotesk', sans-serif",
              fontWeight: 600,
              marginBottom: 8,
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
            }}>
              ◎ Location
            </label>
            <select
              value={draft.location}
              onChange={(e) => handleUpdate('location', e.target.value)}
              style={{
                width: '100%',
                padding: '8px',
                background: '#0a0a0f',
                border: '1px solid #2a2a3a',
                borderRadius: 4,
                color: '#cbd5e1',
                fontSize: 12,
                fontFamily: "'JetBrains Mono', monospace",
                outline: 'none',
                cursor: 'pointer',
              }}
              onFocus={(e) => { e.target.style.borderColor = '#c084fc40'; }}
              onBlur={(e) => { e.target.style.borderColor = '#2a2a3a'; }}
            >
              <option value="">— Select location —</option>
              {locationEntities.map(loc => (
                <option key={loc.id || loc.slug} value={loc.id || loc.slug}>
                  {loc.name}
                </option>
              ))}
            </select>
            {locationEntities.length === 0 && (
              <div style={{ color: '#4a4a5a', fontSize: 10, fontStyle: 'italic', marginTop: 4 }}>
                No locations defined yet
              </div>
            )}
          </div>

          {/* Time */}
          <div>
            <label style={{
              display: 'block',
              fontSize: 11,
              color: '#94a3b8',
              fontFamily: "'Space Grotesk', sans-serif",
              fontWeight: 600,
              marginBottom: 8,
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
            }}>
              ◑ Time of Day
            </label>
            <input
              type="text"
              value={draft.time}
              onChange={(e) => handleUpdate('time', e.target.value)}
              placeholder="DAY, NIGHT, 3:00 PM, etc."
              style={{
                width: '100%',
                padding: '8px',
                background: '#0a0a0f',
                border: '1px solid #2a2a3a',
                borderRadius: 4,
                color: '#cbd5e1',
                fontSize: 12,
                fontFamily: "'JetBrains Mono', monospace",
                outline: 'none',
              }}
              onFocus={(e) => { e.target.style.borderColor = '#c084fc40'; }}
              onBlur={(e) => { e.target.style.borderColor = '#2a2a3a'; }}
            />
          </div>

          {/* Status */}
          <div>
            <label style={{
              display: 'block',
              fontSize: 11,
              color: '#94a3b8',
              fontFamily: "'Space Grotesk', sans-serif",
              fontWeight: 600,
              marginBottom: 8,
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
            }}>
              Status
            </label>
            <select
              value={draft.status}
              onChange={(e) => handleUpdate('status', e.target.value)}
              style={{
                width: '100%',
                padding: '8px',
                background: '#0a0a0f',
                border: '1px solid #2a2a3a',
                borderRadius: 4,
                color: STATUS[draft.status]?.color || '#cbd5e1',
                fontSize: 12,
                fontFamily: "'JetBrains Mono', monospace",
                outline: 'none',
                cursor: 'pointer',
              }}
              onFocus={(e) => { e.target.style.borderColor = '#c084fc40'; }}
              onBlur={(e) => { e.target.style.borderColor = '#2a2a3a'; }}
            >
              <option value="idea">Idea</option>
              <option value="draft">Draft</option>
              <option value="in-progress">In Progress</option>
              <option value="revised">Revised</option>
              <option value="polished">Polished</option>
            </select>
          </div>
        </div>
      </div>

      {/* Validation Feedback (only show in edit mode if there are issues) */}
      {isEditing && (validation.errors.length > 0 || validation.warnings.length > 0 || validation.suggestions.length > 0) && (
        <ValidationFeedback
          validationResults={validation}
          onActionClick={handleValidationAction}
        />
      )}
    </div>
  );
}

// Helper function for extracting scene number
function extractSceneNumber(sceneSlug) {
  if (!sceneSlug) return null;
  const match = sceneSlug.match(/(\d+)/);
  return match ? parseInt(match[1], 10) : null;
}

// ============================================================================
// Scene Editor Component
// ============================================================================

function SceneEditor({ content, entities }) {
  const { saveDocument } = useKozmo();

  // Edit mode state
  const [isEditing, setIsEditing] = useState(false);
  const [draftBody, setDraftBody] = useState('');
  const [draftFrontmatter, setDraftFrontmatter] = useState({});
  const [isDirty, setIsDirty] = useState(false);
  const [lastSaved, setLastSaved] = useState(null);
  const [isSaving, setIsSaving] = useState(false);

  // Initialize draft when content changes
  useEffect(() => {
    if (content) {
      setDraftBody(content.body || '');
      setDraftFrontmatter(content.frontmatter || {
        characters_present: [],
        location: '',
        time: '',
        status: 'draft',
      });
      setIsDirty(false);
      setIsEditing(false);
    }
  }, [content?.slug]);

  // Warn on unsaved changes
  useEffect(() => {
    const handleBeforeUnload = (e) => {
      if (isDirty) {
        e.preventDefault();
        e.returnValue = '';
      }
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [isDirty]);

  // Auto-save: Save 30 seconds after last change
  useEffect(() => {
    if (!isDirty || !isEditing || !content?.slug) return;

    const autoSaveTimer = setTimeout(async () => {
      setIsSaving(true);
      const success = await saveDocument(content.slug, {
        ...content,
        body: draftBody,
        frontmatter: draftFrontmatter,
        status: draftFrontmatter.status,
      });
      if (success) {
        setIsDirty(false);
        setLastSaved(new Date());
      }
      setIsSaving(false);
    }, 30000); // 30 seconds

    return () => clearTimeout(autoSaveTimer);
  }, [isDirty, isEditing, draftBody, draftFrontmatter, content, saveDocument]);

  const handleSave = async () => {
    if (!content?.slug) return;
    setIsSaving(true);
    const success = await saveDocument(content.slug, {
      ...content,
      body: draftBody,
      frontmatter: draftFrontmatter,
      status: draftFrontmatter.status,
    });
    if (success) {
      setIsDirty(false);
      setIsEditing(false);
      setLastSaved(new Date());
    }
    setIsSaving(false);
  };

  const handleCancel = () => {
    if (isDirty && !window.confirm('Discard unsaved changes?')) {
      return;
    }
    setDraftBody(content.body || '');
    setDraftFrontmatter(content.frontmatter || {
      characters_present: [],
      location: '',
      time: '',
      status: 'draft',
    });
    setIsDirty(false);
    setIsEditing(false);
  };

  const [cursorPosition, setCursorPosition] = useState(0);
  const textareaRef = useRef(null);

  const handleChange = (e) => {
    setDraftBody(e.target.value);
    setCursorPosition(e.target.selectionStart);
    setIsDirty(true);
  };

  const handleAutocompleteSelect = (entity) => {
    if (!textareaRef.current) return;

    const textarea = textareaRef.current;
    const text = draftBody;
    const cursorPos = textarea.selectionStart;

    // Find the start of the @mention
    let mentionStart = cursorPos - 1;
    while (mentionStart > 0 && text[mentionStart - 1] !== '@') {
      mentionStart--;
    }
    if (text[mentionStart - 1] === '@') mentionStart--; // Include the @

    // Replace @query with @EntityName
    const before = text.slice(0, mentionStart);
    const after = text.slice(cursorPos);
    const newText = before + `@${entity.name}` + after;
    const newCursorPos = mentionStart + entity.name.length + 1; // +1 for @

    setDraftBody(newText);
    setIsDirty(true);

    // Restore focus and cursor position
    setTimeout(() => {
      textarea.focus();
      textarea.setSelectionRange(newCursorPos, newCursorPos);
      setCursorPosition(newCursorPos);
    }, 0);
  };

  if (!content) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#4a4a5a' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 48, marginBottom: 16, opacity: 0.3 }}>¶</div>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 16 }}>Select a scene to begin writing</div>
          <div style={{ fontSize: 13, marginTop: 8, color: '#2a2a3a' }}>or create a new scene with ⌘N</div>
        </div>
      </div>
    );
  }

  const fm = content.frontmatter || {};
  const body = isEditing ? draftBody : (content.body || '');
  const lines = body.split('\n');
  const lunaNotes = content.luna_notes || content.lunaNotes || [];

  // Helper function for inline Fountain formatting + entity references
  const formatInlineText = (text, options = {}) => {
    const { enableEntityLinks = false, frontmatterLocation = null } = options;

    // Escape HTML to prevent XSS
    let escaped = text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');

    // FEATURE 1: @EntityName explicit references (check before Fountain formatting)
    if (enableEntityLinks) {
      escaped = escaped.replace(/@([A-Z][A-Za-z\s]+)/g, (match, entityName) => {
        const entity = entities.find(e =>
          e.name.toLowerCase() === entityName.trim().toLowerCase()
        );
        if (entity) {
          const color = entity.color || '#4ade80';
          return `<span class="entity-ref" data-entity="${entity.slug}" data-entity-type="${entity.type}" style="color: ${color}; text-shadow: 0 0 6px ${color}60; cursor: pointer; text-decoration: underline dotted; text-underline-offset: 2px;">@${entityName}</span>`;
        }
        return match;
      });
    }

    // FEATURE 2: Smart location detection from frontmatter
    if (enableEntityLinks && frontmatterLocation) {
      const locationEntity = entities.find(e =>
        e.slug === frontmatterLocation || e.id === frontmatterLocation
      );
      if (locationEntity && locationEntity.name) {
        // Highlight any mention of the location name in the text
        const locationPattern = new RegExp(`\\b(${locationEntity.name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})\\b`, 'gi');
        escaped = escaped.replace(locationPattern, (match) => {
          const color = locationEntity.color || '#22d3ee';
          return `<span class="location-ref" data-entity="${locationEntity.slug}" style="color: ${color}; text-shadow: 0 0 4px ${color}40; cursor: pointer; border-bottom: 1px dotted ${color}60;">${match}</span>`;
        });
      }
    }

    // Apply Fountain formatting (order matters!)
    // ***bold italic*** (must be first to avoid conflicts)
    escaped = escaped.replace(/\*\*\*(.*?)\*\*\*/g, '<strong><em>$1</em></strong>');
    // **bold**
    escaped = escaped.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    // *italic*
    escaped = escaped.replace(/\*(.*?)\*/g, '<em>$1</em>');
    // _underline_
    escaped = escaped.replace(/_(.*?)_/g, '<u>$1</u>');

    return <span dangerouslySetInnerHTML={{ __html: escaped }} />;
  };

  // FEATURE 3: Navigate to CODEX handler
  const handleEntityClick = (e) => {
    const target = e.target;
    if (target.classList.contains('entity-ref') || target.classList.contains('location-ref') || target.classList.contains('character-link')) {
      const entitySlug = target.dataset.entity;
      const entityType = target.dataset.entityType;
      if (entitySlug && onNavigateToEntity) {
        // Navigate to CODEX with selected entity
        onNavigateToEntity(entitySlug, entityType);
      }
    }
  };

  const renderLine = (line, idx) => {
    const trimmed = line.trim();

    // Scene heading: INT., EXT., INT./EXT., I/E (highest priority — check first)
    const sceneHeadingPattern = /^(INT\.|EXT\.|INT\.\/EXT\.|I\/E\.?)\s/i;
    if (sceneHeadingPattern.test(trimmed)) {
      return (
        <div key={idx} style={{
          color: '#22d3ee', // CYBERPUNK: Neon cyan
          fontFamily: "'Space Grotesk', sans-serif",
          fontWeight: 700,
          fontSize: 13,
          paddingTop: 20,
          paddingBottom: 4,
          textTransform: 'uppercase',
          letterSpacing: '0.02em',
          borderBottom: '1px solid #22d3ee40',
          textShadow: '0 0 10px #22d3ee80',
        }}>
          {formatInlineText(trimmed)}
        </div>
      );
    }

    // Transition: ends with TO: or specific keywords
    const transitionPattern = /TO:$|^(FADE IN|FADE OUT\.|FADE TO BLACK\.)$/i;
    if (transitionPattern.test(trimmed)) {
      return (
        <div key={idx} style={{
          color: '#f472b6', // CYBERPUNK: Hot pink
          fontSize: 12,
          paddingTop: 12,
          paddingBottom: 12,
          textAlign: 'right',
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
          textShadow: '0 0 8px #f472b680',
        }}>
          {formatInlineText(trimmed)}
        </div>
      );
    }

    // Character name (ALL CAPS, standalone)
    if (/^[A-Z][A-Z\s]{2,}$/.test(trimmed)) {
      const entity = entities.find(e => e.name.toUpperCase() === trimmed);
      return (
        <div key={idx} style={{
          color: entity ? entity.color : '#c084fc', // CYBERPUNK: Electric purple
          fontFamily: "'Space Grotesk', sans-serif",
          fontWeight: 600, fontSize: 14,
          paddingTop: 16, paddingBottom: 2,
          textAlign: 'center', letterSpacing: '0.05em',
          textShadow: entity ? `0 0 8px ${entity.color}60` : '0 0 8px #c084fc60',
          cursor: entity ? 'pointer' : 'default',
          position: 'relative',
        }}
        onClick={handleEntityClick}
        className={entity ? 'character-link' : ''}
        data-entity={entity?.slug}
        data-entity-type={entity?.type}
        title={entity ? `Click to view ${entity.name} in CODEX` : undefined}
        >
          {formatInlineText(trimmed)}
        </div>
      );
    }

    // Parenthetical
    if (/^\(.*\)$/.test(trimmed)) {
      return (
        <div key={idx} style={{
          color: '#06b6d4', // CYBERPUNK: Muted cyan
          fontStyle: 'italic', fontSize: 13,
          textAlign: 'center', padding: '1px 0',
        }}>
          {formatInlineText(trimmed)}
        </div>
      );
    }

    // Dialogue (line after character name or parenthetical)
    const prevNonEmpty = lines.slice(0, idx).filter(l => l.trim()).pop()?.trim() || '';
    const isAfterCharacter = /^[A-Z][A-Z\s]{2,}$/.test(prevNonEmpty) || /^\(.*\)$/.test(prevNonEmpty);
    if (isAfterCharacter && trimmed && !/^[A-Z][A-Z\s]{2,}$/.test(trimmed)) {
      return (
        <div key={idx} style={{
          color: '#e0f2fe', // CYBERPUNK: Soft cyan-white
          fontSize: 14, lineHeight: 1.7,
          textAlign: 'center', maxWidth: '70%', margin: '0 auto',
          padding: '2px 0',
        }}
        onClick={handleEntityClick}>
          {formatInlineText(trimmed, { enableEntityLinks: true, frontmatterLocation: fm.location })}
        </div>
      );
    }

    // Production notes: [[like this]]
    if (/^\[\[.*\]\]$/.test(trimmed)) {
      const noteText = trimmed.slice(2, -2); // Remove [[ ]]
      return (
        <div key={idx} style={{
          color: '#a78bfa', // CYBERPUNK: Purple
          fontSize: 11,
          fontStyle: 'italic',
          padding: '4px 8px',
          margin: '8px 0',
          opacity: 0.7,
          borderLeft: '2px solid #a78bfa',
          background: 'rgba(167, 139, 250, 0.08)',
          textShadow: '0 0 6px #a78bfa40',
        }}>
          NOTE: {formatInlineText(noteText)}
        </div>
      );
    }

    // Empty line
    if (!trimmed) {
      return <div key={idx} style={{ height: 14 }} />;
    }

    // Action / Prose (default)
    return (
      <div key={idx} style={{
        color: '#bae6fd', // CYBERPUNK: Cyan-tinted light grey
        fontSize: 14, lineHeight: 1.8,
        padding: '2px 0',
        fontFamily: "'Crimson Pro', 'Georgia', serif",
      }}
      onClick={handleEntityClick}>
        {formatInlineText(trimmed, { enableEntityLinks: true, frontmatterLocation: fm.location })}
      </div>
    );
  };

  const handleFrontmatterChange = (updatedFrontmatter) => {
    setDraftFrontmatter(updatedFrontmatter);
    setIsDirty(true);
  };

  return (
    <div style={{ height: '100%', overflow: 'auto' }}>
      {/* Frontmatter editor */}
      <FrontmatterEditor
        scene={content}
        isEditing={isEditing}
        onChange={handleFrontmatterChange}
        entities={entities}
      />

      {/* Writing surface */}
      <div style={{ padding: '32px 48px 80px', maxWidth: 720, margin: '0 auto' }}>
        {isEditing ? (
          <div style={{ position: 'relative' }}>
            <textarea
              ref={textareaRef}
              value={draftBody}
              onChange={handleChange}
              placeholder="Write your content here...

Use ALL CAPS for character names
(Parentheticals) for character direction
Mix prose and dialogue freely

This editor supports any content type — screenplays, novels, game docs, campaign notes..."
              spellCheck={true}
              autoFocus
              style={{
              width: '100%',
              minHeight: '500px',
              fontFamily: "'Courier Prime', 'Courier New', monospace",
              fontSize: '14px',
              lineHeight: 1.8,
              padding: '16px',
              border: '1px solid #2a2a3a',
              borderRadius: '4px',
              resize: 'vertical',
              background: '#0a0a0f',
              color: '#cbd5e1',
              outline: 'none',
            }}
            onFocus={(e) => {
              e.target.style.borderColor = '#c084fc40';
            }}
            onBlur={(e) => {
              e.target.style.borderColor = '#2a2a3a';
            }}
          />
          <EntityAutocomplete
            textareaRef={textareaRef}
            entities={entities}
            onSelect={handleAutocompleteSelect}
            cursorPosition={cursorPosition}
          />
          </div>
        ) : (
          <div>{lines.map(renderLine)}</div>
        )}

        {/* Edit controls */}
        <div style={{
          display: 'flex',
          gap: '8px',
          marginTop: '24px',
          paddingTop: '16px',
          borderTop: '1px solid #1e1e2e',
          alignItems: 'center',
        }}>
          {!isEditing ? (
            <>
              <button
                onClick={() => setIsEditing(true)}
                style={{
                  padding: '8px 16px',
                  borderRadius: '4px',
                  border: '1px solid #c084fc40',
                  background: 'rgba(192, 132, 252, 0.1)',
                  color: '#c084fc',
                  fontSize: '13px',
                  fontFamily: "'Space Grotesk', sans-serif",
                  fontWeight: 500,
                  cursor: 'pointer',
                  transition: 'all 0.15s',
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
                ✎ Edit
              </button>
              <div style={{
                fontSize: '11px',
                color: '#4a4a5a',
                fontFamily: "'JetBrains Mono', monospace",
              }}>
                {body.split(/\s+/).filter(w => w.length > 0).length} words
              </div>
            </>
          ) : (
            <>
              <button
                onClick={handleSave}
                disabled={!isDirty}
                style={{
                  padding: '8px 16px',
                  borderRadius: '4px',
                  border: '1px solid #4ade8040',
                  background: isDirty ? 'rgba(74, 222, 128, 0.1)' : 'rgba(74, 222, 128, 0.05)',
                  color: isDirty ? '#4ade80' : '#2a4a3a',
                  fontSize: '13px',
                  fontFamily: "'Space Grotesk', sans-serif",
                  fontWeight: 500,
                  cursor: isDirty ? 'pointer' : 'not-allowed',
                  opacity: isDirty ? 1 : 0.5,
                  transition: 'all 0.15s',
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
                ✓ Save
              </button>
              <button
                onClick={handleCancel}
                style={{
                  padding: '8px 16px',
                  borderRadius: '4px',
                  border: '1px solid #64748b40',
                  background: 'transparent',
                  color: '#64748b',
                  fontSize: '13px',
                  fontFamily: "'Space Grotesk', sans-serif",
                  fontWeight: 500,
                  cursor: 'pointer',
                  transition: 'all 0.15s',
                }}
                onMouseEnter={(e) => {
                  e.target.style.borderColor = '#64748b60';
                  e.target.style.color = '#94a3b8';
                }}
                onMouseLeave={(e) => {
                  e.target.style.borderColor = '#64748b40';
                  e.target.style.color = '#64748b';
                }}
              >
                × Cancel
              </button>
              {/* Save status indicator */}
              {isSaving ? (
                <div style={{
                  fontSize: '11px',
                  color: '#60a5fa',
                  fontFamily: "'JetBrains Mono', monospace",
                }}>
                  ⟳ Saving...
                </div>
              ) : isDirty ? (
                <div style={{
                  fontSize: '11px',
                  color: '#fbbf24',
                  fontFamily: "'JetBrains Mono', monospace",
                }}>
                  ● Unsaved changes (auto-saves in 30s)
                </div>
              ) : lastSaved ? (
                <div style={{
                  fontSize: '11px',
                  color: '#4ade80',
                  fontFamily: "'JetBrains Mono', monospace",
                }}>
                  ✓ Saved {new Date(lastSaved).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </div>
              ) : null}
              <div style={{
                fontSize: '11px',
                color: '#4a4a5a',
                fontFamily: "'JetBrains Mono', monospace",
                marginLeft: 'auto',
              }}>
                {draftBody.split(/\s+/).filter(w => w.length > 0).length} words
              </div>
            </>
          )}
        </div>
      </div>

      {/* Luna notes */}
      <LunaNotesSection
        scene={content}
        isEditing={isEditing}
        saveDocument={saveDocument}
      />
    </div>
  );
}

// ============================================================================
// Luna Notes Section Component
// ============================================================================

function LunaNotesSection({ scene, isEditing, saveDocument }) {
  const [newNote, setNewNote] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  const lunaNotes = scene?.luna_notes || scene?.lunaNotes || [];

  const handleAddNote = async () => {
    if (!newNote.trim() || !scene?.slug) return;

    setIsSaving(true);
    try {
      const updatedNotes = [
        ...lunaNotes,
        {
          timestamp: new Date().toISOString(),
          content: newNote.trim(),
        },
      ];

      await saveDocument(scene.slug, {
        ...scene,
        luna_notes: updatedNotes,
      });

      setNewNote('');
    } catch (err) {
      console.error('Failed to add Luna note:', err);
    } finally {
      setIsSaving(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      handleAddNote();
    }
  };

  return (
    <div style={{ padding: '0 48px 48px', maxWidth: 720, margin: '0 auto' }}>
      <div style={{
        fontSize: 10,
        color: '#4a4a5a',
        fontFamily: "'JetBrains Mono', monospace",
        textTransform: 'uppercase',
        letterSpacing: '0.1em',
        padding: '12px 0 8px',
        borderTop: '1px solid #1e1e2e',
        marginBottom: 8,
      }}>
        ☾ Luna's Notes
      </div>

      {/* Existing notes */}
      {lunaNotes.map((note, i) => (
        <LunaNoteDisplay key={i} note={note} />
      ))}

      {/* Add note form (only in edit mode) */}
      {isEditing && (
        <div style={{
          marginTop: lunaNotes.length > 0 ? 16 : 0,
          padding: 12,
          background: 'rgba(192, 132, 252, 0.05)',
          border: '1px solid #2a2a3a',
          borderRadius: 4,
        }}>
          <textarea
            value={newNote}
            onChange={(e) => setNewNote(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Add a note about this scene... (⌘+Enter to save)"
            rows={3}
            style={{
              width: '100%',
              padding: 8,
              background: '#0a0a0f',
              border: '1px solid #2a2a3a',
              borderRadius: 3,
              color: '#cbd5e1',
              fontSize: 12,
              fontFamily: "'JetBrains Mono', monospace",
              lineHeight: 1.6,
              resize: 'vertical',
              outline: 'none',
            }}
            onFocus={(e) => {
              e.target.style.borderColor = '#c084fc40';
            }}
            onBlur={(e) => {
              e.target.style.borderColor = '#2a2a3a';
            }}
          />
          <div style={{
            display: 'flex',
            gap: 8,
            marginTop: 8,
            alignItems: 'center',
          }}>
            <button
              onClick={handleAddNote}
              disabled={!newNote.trim() || isSaving}
              style={{
                padding: '6px 12px',
                borderRadius: 3,
                border: '1px solid #c084fc40',
                background: newNote.trim() && !isSaving ? 'rgba(192, 132, 252, 0.1)' : 'transparent',
                color: newNote.trim() && !isSaving ? '#c084fc' : '#4a4a5a',
                fontSize: 11,
                fontFamily: "'Space Grotesk', sans-serif",
                fontWeight: 500,
                cursor: newNote.trim() && !isSaving ? 'pointer' : 'not-allowed',
                opacity: newNote.trim() && !isSaving ? 1 : 0.5,
                transition: 'all 0.15s',
              }}
              onMouseEnter={(e) => {
                if (newNote.trim() && !isSaving) {
                  e.target.style.background = 'rgba(192, 132, 252, 0.15)';
                  e.target.style.borderColor = '#c084fc60';
                }
              }}
              onMouseLeave={(e) => {
                if (newNote.trim() && !isSaving) {
                  e.target.style.background = 'rgba(192, 132, 252, 0.1)';
                  e.target.style.borderColor = '#c084fc40';
                }
              }}
            >
              {isSaving ? '⏳ Saving...' : '+ Add Note'}
            </button>
            <div style={{
              fontSize: 10,
              color: '#4a4a5a',
              fontFamily: "'JetBrains Mono', monospace",
              fontStyle: 'italic',
            }}>
              {newNote.trim() ? `${newNote.trim().split(/\s+/).length} words` : ''}
            </div>
          </div>
        </div>
      )}

      {/* Empty state */}
      {lunaNotes.length === 0 && !isEditing && (
        <div style={{
          color: '#4a4a5a',
          fontSize: 11,
          fontStyle: 'italic',
          padding: 12,
        }}>
          No notes yet. Enter edit mode to add observations about this scene.
        </div>
      )}
    </div>
  );
}

function CodexSidebar({ entities, sceneCharacters }) {
  const [filter, setFilter] = useState('scene');

  const filtered = filter === 'scene'
    ? entities.filter(e => sceneCharacters?.includes(e.id))
    : filter === 'characters'
      ? entities.filter(e => e.type === 'character')
      : entities;

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{
        padding: '12px 12px 8px', borderBottom: '1px solid #1e1e2e',
        display: 'flex', gap: 4,
      }}>
        {['scene', 'characters', 'all'].map(f => (
          <button key={f} onClick={() => setFilter(f)} style={{
            padding: '3px 8px', borderRadius: 3, border: 'none',
            background: filter === f ? 'rgba(192, 132, 252, 0.15)' : 'transparent',
            color: filter === f ? '#c084fc' : '#4a4a5a',
            fontSize: 10, cursor: 'pointer', fontFamily: "'JetBrains Mono', monospace",
            textTransform: 'uppercase', letterSpacing: '0.05em',
          }}>
            {f}
          </button>
        ))}
      </div>
      <div style={{ flex: 1, overflow: 'auto', padding: 8 }}>
        {filtered.length === 0 ? (
          <div style={{ color: '#2a2a3a', fontSize: 12, textAlign: 'center', paddingTop: 24 }}>
            No entities in current scope
          </div>
        ) : filtered.map(entity => (
          <div key={entity.id} style={{
            padding: '10px 12px', marginBottom: 4, borderRadius: 6,
            background: 'rgba(18, 18, 26, 0.5)', cursor: 'pointer',
            border: '1px solid transparent', transition: 'border-color 0.15s',
          }}
          onMouseEnter={e => e.currentTarget.style.borderColor = entity.color + '40'}
          onMouseLeave={e => e.currentTarget.style.borderColor = 'transparent'}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <span style={{
                width: 8, height: 8, borderRadius: '50%', background: entity.color, flexShrink: 0,
              }} />
              <span style={{
                color: '#e2e8f0', fontSize: 13, fontFamily: "'Space Grotesk', sans-serif", fontWeight: 500,
              }}>
                {entity.name}
              </span>
              <span style={{
                color: '#4a4a5a', fontSize: 10, fontFamily: "'JetBrains Mono', monospace", marginLeft: 'auto',
              }}>
                {entity.type}
              </span>
            </div>
            <div style={{ color: '#64748b', fontSize: 11, paddingLeft: 16 }}>
              {entity.role}{entity.scenes > 0 ? ` · ${entity.scenes} scenes` : ''}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function AgentChat({ messages, agents, onSend }) {
  const [input, setInput] = useState('');
  const chatEnd = useRef(null);

  useEffect(() => {
    chatEnd.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = () => {
    if (!input.trim()) return;
    onSend(input.trim());
    setInput('');
  };

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Agent roster */}
      <div style={{
        padding: '10px 12px', borderBottom: '1px solid #1e1e2e',
        display: 'flex', gap: 6, flexWrap: 'wrap',
      }}>
        {agents.map(a => (
          <div key={a.id} style={{
            display: 'flex', alignItems: 'center', gap: 4, padding: '3px 8px',
            borderRadius: 3, background: a.status === 'active' ? a.color + '15' : 'transparent',
            border: `1px solid ${a.status === 'active' ? a.color + '40' : '#1e1e2e'}`,
            cursor: 'pointer',
          }}>
            <span style={{ fontSize: 11 }}>{a.avatar}</span>
            <span style={{
              color: a.status === 'active' ? a.color : '#4a4a5a',
              fontSize: 10, fontFamily: "'JetBrains Mono', monospace",
            }}>
              {a.name}
            </span>
            <span style={{
              width: 5, height: 5, borderRadius: '50%',
              background: a.status === 'active' ? a.color : '#2a2a3a',
            }} />
          </div>
        ))}
      </div>

      {/* Messages */}
      <div style={{ flex: 1, overflow: 'auto', padding: '12px' }}>
        {messages.length === 0 && (
          <div style={{ color: '#2a2a3a', fontSize: 12, textAlign: 'center', paddingTop: 24, fontStyle: 'italic' }}>
            Talk to your agents about the current scene...
          </div>
        )}
        {messages.map(msg => {
          const agent = agents.find(a => a.id === msg.agent);
          const isUser = msg.agent === 'user';

          return (
            <div key={msg.id} style={{
              marginBottom: 12,
              display: 'flex', flexDirection: 'column',
              alignItems: isUser ? 'flex-end' : 'flex-start',
            }}>
              {!isUser && (
                <div style={{
                  display: 'flex', alignItems: 'center', gap: 4, marginBottom: 3,
                }}>
                  <span style={{ fontSize: 10 }}>{agent?.avatar}</span>
                  <span style={{
                    color: agent?.color || '#64748b', fontSize: 10,
                    fontFamily: "'JetBrains Mono', monospace",
                  }}>
                    {agent?.name || msg.agent}
                  </span>
                  <span style={{ color: '#2a2a3a', fontSize: 9 }}>{msg.time}</span>
                </div>
              )}
              <div style={{
                padding: '8px 12px', borderRadius: isUser ? '10px 10px 2px 10px' : '10px 10px 10px 2px',
                background: isUser ? 'rgba(192, 132, 252, 0.12)' : 'rgba(18, 18, 26, 0.8)',
                border: `1px solid ${isUser ? '#c084fc20' : '#1e1e2e'}`,
                maxWidth: '85%',
              }}>
                <span style={{
                  color: isUser ? '#e2e8f0' : '#cbd5e1',
                  fontSize: 13, lineHeight: 1.5,
                }}>
                  {msg.text}
                </span>
              </div>
              {isUser && (
                <span style={{ color: '#2a2a3a', fontSize: 9, marginTop: 2 }}>{msg.time}</span>
              )}
            </div>
          );
        })}
        <div ref={chatEnd} />
      </div>

      {/* Input */}
      <div style={{
        padding: '10px 12px', borderTop: '1px solid #1e1e2e',
        display: 'flex', gap: 8,
      }}>
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSend()}
          placeholder="Talk to your agents..."
          style={{
            flex: 1, padding: '8px 12px', borderRadius: 6,
            background: 'rgba(10, 10, 15, 0.8)', border: '1px solid #1e1e2e',
            color: '#e2e8f0', fontSize: 13, outline: 'none',
            fontFamily: "'Space Grotesk', sans-serif",
          }}
          onFocus={e => e.currentTarget.style.borderColor = '#c084fc40'}
          onBlur={e => e.currentTarget.style.borderColor = '#1e1e2e'}
        />
        <button
          onClick={handleSend}
          style={{
            padding: '8px 14px', borderRadius: 6, border: 'none',
            background: input.trim() ? 'rgba(192, 132, 252, 0.2)' : 'transparent',
            color: input.trim() ? '#c084fc' : '#2a2a3a',
            cursor: input.trim() ? 'pointer' : 'default',
            fontSize: 13, fontFamily: "'Space Grotesk', sans-serif",
          }}
        >
          Send
        </button>
      </div>
    </div>
  );
}

function WordCountBar({ scene, total }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 12, padding: '6px 16px',
      borderTop: '1px solid #1e1e2e', background: 'rgba(10, 10, 15, 0.4)', backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)',
      fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#4a4a5a',
    }}>
      <span>Scene: {scene?.toLocaleString() || '—'} words</span>
      <span style={{ color: '#2a2a3a' }}>|</span>
      <span>Project: {total?.toLocaleString() || '—'} words</span>
      <span style={{ marginLeft: 'auto', color: '#2a2a3a' }}>⌘K commands · ⌘/ agents · ⌘B codex</span>
    </div>
  );
}

// ============================================================================
// Create Form
// ============================================================================

function collectContainers(node, result = []) {
  if (!node) return result;
  if (node.children && node.children.length > 0) {
    result.push({ id: node.id, title: node.title, type: node.type });
    node.children.forEach(c => collectContainers(c, result));
  }
  return result;
}

function CreateStoryItemForm({ mode, tree, onClose, onCreateScene, onCreateContainer }) {
  const [title, setTitle] = useState('');
  const [container, setContainer] = useState('');
  const [level, setLevel] = useState('chapter');
  const [parent, setParent] = useState('');

  const containers = useMemo(() => tree ? collectContainers(tree) : [], [tree]);

  const handleCreate = async () => {
    if (!title.trim()) return;
    if (mode === 'scene') {
      await onCreateScene({
        container: container || containers[0]?.id || 'story',
        title: title.trim(),
        type: 'scene',
      });
    } else {
      await onCreateContainer({
        parent: parent || null,
        title: title.trim(),
        level,
      });
    }
    onClose();
  };

  return (
    <div style={{
      position: 'absolute', inset: 0, background: 'rgba(8,8,14,0.9)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100,
    }}>
      <div style={{
        width: 340, padding: 20, background: 'rgba(13, 13, 24, 0.6)', backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)', borderRadius: 8,
        border: '1px solid #60a5fa30',
      }}>
        <div style={{ fontSize: 10, color: '#60a5fa', letterSpacing: 2, marginBottom: 16 }}>
          {mode === 'scene' ? 'NEW SCENE' : 'NEW CONTAINER'}
        </div>

        {/* Title */}
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 8, color: '#3a3a50', letterSpacing: 2, marginBottom: 6 }}>TITLE</div>
          <input
            value={title}
            onChange={e => setTitle(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleCreate()}
            autoFocus
            placeholder={mode === 'scene' ? 'Scene title...' : 'Container title...'}
            style={{
              width: '100%', padding: '6px 10px', background: '#08080e',
              border: '1px solid #1a1a24', borderRadius: 4, color: '#c8cad0',
              fontFamily: 'inherit', fontSize: 11, outline: 'none',
            }}
          />
        </div>

        {mode === 'scene' ? (
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 8, color: '#3a3a50', letterSpacing: 2, marginBottom: 6 }}>CONTAINER</div>
            <select
              value={container}
              onChange={e => setContainer(e.target.value)}
              style={{
                width: '100%', padding: '6px 10px', background: '#08080e',
                border: '1px solid #1a1a24', borderRadius: 4, color: '#c8cad0',
                fontFamily: 'inherit', fontSize: 10, outline: 'none',
              }}
            >
              <option value="">Select container...</option>
              {containers.map(c => (
                <option key={c.id} value={c.id}>{c.title} ({c.type})</option>
              ))}
            </select>
          </div>
        ) : (
          <>
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 8, color: '#3a3a50', letterSpacing: 2, marginBottom: 6 }}>LEVEL</div>
              <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                {['act', 'chapter', 'sequence', 'section'].map(l => (
                  <button key={l} onClick={() => setLevel(l)} style={{
                    padding: '4px 10px', fontSize: 9, borderRadius: 4,
                    border: `1px solid ${level === l ? '#60a5fa' : '#2a2a3a'}`,
                    background: level === l ? 'rgba(96,165,250,0.08)' : 'transparent',
                    color: level === l ? '#60a5fa' : '#6b6b80',
                    cursor: 'pointer', fontFamily: 'inherit',
                  }}>{l}</button>
                ))}
              </div>
            </div>
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 8, color: '#3a3a50', letterSpacing: 2, marginBottom: 6 }}>PARENT (optional)</div>
              <select
                value={parent}
                onChange={e => setParent(e.target.value)}
                style={{
                  width: '100%', padding: '6px 10px', background: '#08080e',
                  border: '1px solid #1a1a24', borderRadius: 4, color: '#c8cad0',
                  fontFamily: 'inherit', fontSize: 10, outline: 'none',
                }}
              >
                <option value="">Root level</option>
                {containers.map(c => (
                  <option key={c.id} value={c.id}>{c.title} ({c.type})</option>
                ))}
              </select>
            </div>
          </>
        )}

        {/* Actions */}
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button onClick={onClose} style={{
            padding: '6px 14px', borderRadius: 4, border: '1px solid #1a1a24',
            background: 'transparent', color: '#3a3a50', fontSize: 10,
            cursor: 'pointer', fontFamily: 'inherit',
          }}>cancel</button>
          <button
            onClick={handleCreate}
            disabled={!title.trim()}
            style={{
              padding: '6px 14px', borderRadius: 4, border: 'none',
              background: title.trim() ? '#60a5fa' : '#1a1a24',
              color: title.trim() ? '#08080e' : '#3a3a50',
              fontWeight: 700, fontSize: 10,
              cursor: title.trim() ? 'pointer' : 'not-allowed',
              fontFamily: 'inherit',
            }}>
            CREATE
          </button>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Generate Scene Form (Phase 6)
// ============================================================================

function GenerateSceneForm({ entities, onClose, onGenerate }) {
  const [selectedChars, setSelectedChars] = useState([]);
  const [location, setLocation] = useState('');
  const [goal, setGoal] = useState('');
  const [style, setStyle] = useState('fountain');
  const [isGenerating, setIsGenerating] = useState(false);
  const [result, setResult] = useState(null);

  const characters = Object.values(entities).filter(e =>
    e.type === 'character' || e.type === 'characters'
  );
  const locations = Object.values(entities).filter(e =>
    e.type === 'location' || e.type === 'locations'
  );

  const handleGenerate = async () => {
    if (!selectedChars.length || !location || !goal.trim()) return;
    setIsGenerating(true);
    setResult(null);
    try {
      const res = await onGenerate(selectedChars, location, goal, style);
      if (res) setResult(res);
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div style={{
      position: 'absolute', inset: 0, background: 'rgba(8,8,14,0.9)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100,
    }}>
      <div style={{
        width: 460, maxHeight: '80vh', overflow: 'auto', padding: 20,
        background: 'rgba(13, 13, 24, 0.6)', backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)', borderRadius: 8, border: '1px solid #c084fc30',
      }}>
        <div style={{ fontSize: 10, color: '#c084fc', letterSpacing: 2, marginBottom: 16 }}>
          AI SCENE GENERATOR
        </div>

        {!result ? (
          <>
            {/* Characters */}
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 8, color: '#3a3a50', letterSpacing: 2, marginBottom: 6 }}>CHARACTERS</div>
              <div style={{
                maxHeight: 120, overflow: 'auto', padding: 8, background: '#0a0a0f',
                borderRadius: 4, border: '1px solid #2a2a3a',
              }}>
                {characters.length > 0 ? characters.map(c => (
                  <label key={c.slug} style={{
                    display: 'flex', alignItems: 'center', gap: 8, padding: '3px 0', cursor: 'pointer',
                  }}>
                    <input
                      type="checkbox"
                      checked={selectedChars.includes(c.slug)}
                      onChange={(e) => {
                        setSelectedChars(e.target.checked
                          ? [...selectedChars, c.slug]
                          : selectedChars.filter(s => s !== c.slug));
                      }}
                    />
                    <span style={{ fontSize: 10, color: '#c8cad0' }}>{c.name}</span>
                  </label>
                )) : (
                  <div style={{ fontSize: 9, color: '#3a3a50', fontStyle: 'italic' }}>
                    No characters defined. Create some in CODEX first.
                  </div>
                )}
              </div>
            </div>

            {/* Location */}
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 8, color: '#3a3a50', letterSpacing: 2, marginBottom: 6 }}>LOCATION</div>
              <select
                value={location}
                onChange={e => setLocation(e.target.value)}
                style={{
                  width: '100%', padding: '6px 10px', background: '#0a0a0f',
                  border: '1px solid #2a2a3a', borderRadius: 4, color: '#c8cad0',
                  fontFamily: 'inherit', fontSize: 10, outline: 'none',
                }}
              >
                <option value="">Select location...</option>
                {locations.map(l => (
                  <option key={l.slug} value={l.slug}>{l.name}</option>
                ))}
              </select>
            </div>

            {/* Goal */}
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 8, color: '#3a3a50', letterSpacing: 2, marginBottom: 6 }}>SCENE GOAL</div>
              <textarea
                value={goal}
                onChange={e => setGoal(e.target.value)}
                placeholder="What should happen in this scene..."
                rows={3}
                style={{
                  width: '100%', padding: '6px 10px', background: '#0a0a0f',
                  border: '1px solid #2a2a3a', borderRadius: 4, color: '#c8cad0',
                  fontFamily: 'inherit', fontSize: 10, outline: 'none', resize: 'vertical',
                }}
              />
            </div>

            {/* Style */}
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 8, color: '#3a3a50', letterSpacing: 2, marginBottom: 6 }}>FORMAT</div>
              <div style={{ display: 'flex', gap: 4 }}>
                {['fountain', 'prose'].map(s => (
                  <button key={s} onClick={() => setStyle(s)} style={{
                    padding: '4px 10px', fontSize: 9, borderRadius: 4,
                    border: `1px solid ${style === s ? '#c084fc' : '#2a2a3a'}`,
                    background: style === s ? 'rgba(192,132,252,0.08)' : 'transparent',
                    color: style === s ? '#c084fc' : '#6b6b80',
                    cursor: 'pointer', fontFamily: 'inherit',
                  }}>{s}</button>
                ))}
              </div>
            </div>

            {/* Actions */}
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button onClick={onClose} style={{
                padding: '6px 14px', borderRadius: 4, border: '1px solid #1a1a24',
                background: 'transparent', color: '#3a3a50', fontSize: 10,
                cursor: 'pointer', fontFamily: 'inherit',
              }}>cancel</button>
              <button
                onClick={handleGenerate}
                disabled={isGenerating || !selectedChars.length || !location || !goal.trim()}
                style={{
                  padding: '6px 14px', borderRadius: 4, border: 'none',
                  background: (selectedChars.length && location && goal.trim()) ? '#c084fc' : '#1a1a24',
                  color: (selectedChars.length && location && goal.trim()) ? '#08080e' : '#3a3a50',
                  fontWeight: 700, fontSize: 10,
                  cursor: (selectedChars.length && location && goal.trim()) ? 'pointer' : 'not-allowed',
                  fontFamily: 'inherit',
                }}>
                {isGenerating ? 'Generating...' : 'GENERATE'}
              </button>
            </div>
          </>
        ) : (
          <>
            {/* Generated result */}
            <div style={{
              marginBottom: 12, padding: 12, background: '#0a0a0f', borderRadius: 6,
              border: '1px solid #4ade8030', maxHeight: 300, overflow: 'auto',
            }}>
              <pre style={{
                fontSize: 11, color: '#c8cad0', lineHeight: 1.6, whiteSpace: 'pre-wrap',
                fontFamily: "'Courier Prime', monospace", margin: 0,
              }}>{result.body}</pre>
            </div>
            {result.meta && (
              <div style={{ fontSize: 8, color: '#3a3a50', marginBottom: 12 }}>
                Tokens: {result.meta.tokens_used} | Model: {result.meta.model}
              </div>
            )}
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button onClick={() => setResult(null)} style={{
                padding: '6px 14px', borderRadius: 4, border: '1px solid #1a1a24',
                background: 'transparent', color: '#3a3a50', fontSize: 10,
                cursor: 'pointer', fontFamily: 'inherit',
              }}>Re-generate</button>
              <button onClick={() => {
                // Copy to clipboard for manual paste into scene
                navigator.clipboard.writeText(result.body).catch(() => {});
                onClose();
              }} style={{
                padding: '6px 14px', borderRadius: 4, border: 'none',
                background: '#4ade80', color: '#08080e', fontWeight: 700,
                fontSize: 10, cursor: 'pointer', fontFamily: 'inherit',
              }}>Copy & Close</button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

export default function KozmoScribo({ savedState, onSaveState, onSetDirty, onNavigateToEntity }) {
  const {
    activeProject, entities,
    storyTree: rawTree, currentDocument, scriboStats,
    fetchStoryTree, fetchDocument, fetchScriboStats,
    createDocument, createContainer, searchStory, deleteDocument,
    generateScene,
  } = useKozmo();

  // UI state - initialize from savedState if available
  const [selected, setSelected] = useState(savedState?.selectedScene || null);
  const [expanded, setExpanded] = useState(
    savedState?.expandedNodes ? new Set(savedState.expandedNodes) : new Set()
  );
  const [rightPanel, setRightPanel] = useState(savedState?.rightPanel || 'chat');
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const [chatMessages, setChatMessages] = useState([]);
  const [showCreateForm, setShowCreateForm] = useState(null); // null | 'scene' | 'container'
  const [showGenerateForm, setShowGenerateForm] = useState(false);
  const [searchQuery, setSearchQuery] = useState(savedState?.searchQuery || '');
  const [searchResults, setSearchResults] = useState(savedState?.searchResults || null);
  const [isSearching, setIsSearching] = useState(false);

  // Save state to machine whenever key state changes
  useEffect(() => {
    if (onSaveState) {
      onSaveState({
        selectedScene: selected,
        expandedNodes: Array.from(expanded),
        searchQuery,
        searchResults,
        rightPanel,
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected, expanded, searchQuery, searchResults, rightPanel]);

  // Normalize tree from API format (snake_case → camelCase, add icons)
  const tree = useMemo(() => rawTree ? normalizeNode(rawTree) : null, [rawTree]);

  // Build entities brief for CODEX sidebar
  const entitiesBrief = useMemo(() => {
    return Object.entries(entities).map(([slug, e]) => ({
      id: slug,
      name: e.name,
      role: e.data?.role || e.data?.desc || '',
      color: entityColor(e),
      type: e.type?.replace(/s$/, '') || 'entity',
      scenes: (e.data?.scenes || []).length,
      status: e.status || 'active',
    }));
  }, [entities]);

  // Auto-expand root and first-level children when tree loads
  useEffect(() => {
    if (tree) {
      const ids = new Set([tree.id]);
      (tree.children || []).forEach(c => ids.add(c.id));
      setExpanded(ids);
    }
  }, [tree?.id]);

  // Fetch tree on mount / project change
  useEffect(() => {
    if (activeProject) {
      fetchStoryTree();
      fetchScriboStats();
    }
  }, [activeProject?.slug]);

  // Handle node selection — fetch document for leaf nodes
  const handleSelect = useCallback(async (id, node) => {
    setSelected(id);
    if (node && (!node.children || node.children.length === 0)) {
      await fetchDocument(id);
    }
  }, [fetchDocument]);

  const handleToggle = useCallback((id) => {
    setExpanded(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }, []);

  const handleChatSend = useCallback(async (text) => {
    const userMsg = {
      id: Date.now(),
      agent: 'user',
      text,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };
    setChatMessages(prev => [...prev, userMsg]);

    try {
      const res = await fetch('/api/message', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      });
      if (!res.ok) throw new Error(`${res.status}`);
      const data = await res.json();
      setChatMessages(prev => [...prev, {
        id: Date.now() + 1,
        agent: 'luna',
        text: data.text || data.response || 'No response',
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      }]);
    } catch (e) {
      setChatMessages(prev => [...prev, {
        id: Date.now() + 1,
        agent: 'luna',
        text: `Error: ${e.message}`,
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      }]);
    }
  }, []);

  // Derived state
  const currentNode = tree ? findNode(tree, selected) : null;
  const breadcrumb = tree ? (buildPath(tree, selected) || []) : [];
  const sceneCharacters = currentDocument?.frontmatter?.characters_present || [];
  const sceneWordCount = currentDocument?.word_count || currentNode?.wordCount;
  const totalWordCount = tree?.wordCount || scriboStats?.total_words || 0;

  // Stats for left sidebar
  const stats = useMemo(() => {
    if (scriboStats) {
      return [
        { label: 'Scenes', value: String(scriboStats.document_count || 0) },
        { label: 'Words', value: totalWordCount > 1000 ? (totalWordCount / 1000).toFixed(1) + 'k' : String(totalWordCount) },
        { label: 'Containers', value: String(scriboStats.container_count || 0) },
        { label: 'Draft', value: String(scriboStats.status_breakdown?.draft || 0) },
      ];
    }
    return [
      { label: 'Scenes', value: '—' },
      { label: 'Words', value: '—' },
      { label: 'Containers', value: '—' },
      { label: 'Draft', value: '—' },
    ];
  }, [scriboStats, totalWordCount]);

  // Search handler
  const handleSearch = useCallback(async () => {
    if (!searchQuery.trim()) {
      setSearchResults(null);
      return;
    }

    setIsSearching(true);
    try {
      const results = await searchStory(searchQuery);
      setSearchResults(results);
    } catch (err) {
      console.error('Search failed:', err);
      setSearchResults([]);
    } finally {
      setIsSearching(false);
    }
  }, [searchQuery, searchStory]);

  // Clear search
  const handleClearSearch = useCallback(() => {
    setSearchQuery('');
    setSearchResults(null);
  }, []);

  // Delete document handler
  const handleDelete = useCallback(async (docSlug) => {
    if (!window.confirm('Delete this scene permanently? This cannot be undone.')) {
      return;
    }

    try {
      await deleteDocument(docSlug);
      await fetchStoryTree();
      await fetchScriboStats();

      // If deleted doc was selected, clear selection
      if (selected === docSlug) {
        setSelected(null);
      }
    } catch (err) {
      console.error('Delete failed:', err);
      alert('Failed to delete scene. Please try again.');
    }
  }, [deleteDocument, fetchStoryTree, fetchScriboStats, selected]);

  // Display tree (either search results or full tree)
  const displayTree = searchResults ? { ...tree, children: searchResults } : tree;

  return (
    <div style={{
      width: '100%', height: '100%', display: 'flex', flexDirection: 'column',
      background: '#0a0a0f', color: '#e2e8f0',
      fontFamily: "'Space Grotesk', -apple-system, sans-serif",
    }}>
      {/* Create Form Overlay */}
      {showCreateForm && (
        <CreateStoryItemForm
          mode={showCreateForm}
          tree={tree}
          onClose={() => setShowCreateForm(null)}
          onCreateScene={async (data) => {
            const result = await createDocument(data);
            if (result) {
              await fetchStoryTree();
              await fetchScriboStats();
            }
          }}
          onCreateContainer={async (data) => {
            const result = await createContainer(data);
            if (result) {
              await fetchStoryTree();
              await fetchScriboStats();
            }
          }}
        />
      )}

      {/* AI Scene Generation Overlay */}
      {showGenerateForm && (
        <GenerateSceneForm
          entities={entities}
          onClose={() => setShowGenerateForm(false)}
          onGenerate={generateScene}
        />
      )}

      {/* Google Fonts */}
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@300;400;500&family=Crimson+Pro:ital,wght@0,300;0,400;0,500;1,300;1,400&display=swap');
      `}</style>

      {/* Top bar with breadcrumb */}
      <div style={{
        display: 'flex', alignItems: 'center', height: 36,
        borderBottom: '1px solid #1e1e2e', padding: '0 12px',
        background: 'rgba(10, 10, 15, 0.4)', backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)',
        gap: 12, flexShrink: 0,
      }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 6,
          padding: '3px 10px', borderRadius: 4,
          background: 'rgba(96, 165, 250, 0.1)',
          border: '1px solid rgba(96, 165, 250, 0.2)',
        }}>
          <span style={{ color: '#60a5fa', fontSize: 11, fontWeight: 600, letterSpacing: '0.08em' }}>
            SCRIBO
          </span>
        </div>
        {breadcrumb.length > 0 && (
          <Breadcrumb path={breadcrumb} onNavigate={handleSelect} />
        )}
        <div style={{ flex: 1 }} />
      </div>

      {/* Main content */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        {/* Left: Story tree */}
        {!leftCollapsed && (
          <div style={{
            width: 260, borderRight: '1px solid #1e1e2e', display: 'flex', flexDirection: 'column',
            background: 'rgba(10, 10, 15, 0.4)', backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)', flexShrink: 0,
          }}>
            <div style={{
              padding: '10px 12px', borderBottom: '1px solid #1e1e2e',
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            }}>
              <span style={{
                fontSize: 10, color: '#4a4a5a', fontFamily: "'JetBrains Mono', monospace",
                textTransform: 'uppercase', letterSpacing: '0.1em',
              }}>
                Story
              </span>
              <span
                onClick={() => setLeftCollapsed(true)}
                style={{ color: '#2a2a3a', fontSize: 12, cursor: 'pointer' }}
              >
                ◂
              </span>
            </div>

            {/* Search bar */}
            <div style={{
              padding: '8px 12px',
              borderBottom: '1px solid #1e1e2e',
              background: 'rgba(10, 10, 15, 0.6)',
            }}>
              <div style={{ position: 'relative' }}>
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleSearch();
                    if (e.key === 'Escape') handleClearSearch();
                  }}
                  placeholder="Search scenes..."
                  style={{
                    width: '100%',
                    padding: '6px 28px 6px 8px',
                    background: '#0a0a0f',
                    border: '1px solid #2a2a3a',
                    borderRadius: 3,
                    color: '#cbd5e1',
                    fontSize: 11,
                    fontFamily: "'JetBrains Mono', monospace",
                    outline: 'none',
                  }}
                  onFocus={(e) => { e.target.style.borderColor = '#c084fc40'; }}
                  onBlur={(e) => { e.target.style.borderColor = '#2a2a3a'; }}
                />
                {searchQuery && (
                  <button
                    onClick={handleClearSearch}
                    style={{
                      position: 'absolute',
                      right: 4,
                      top: '50%',
                      transform: 'translateY(-50%)',
                      background: 'transparent',
                      border: 'none',
                      color: '#4a4a5a',
                      cursor: 'pointer',
                      fontSize: 12,
                      padding: 4,
                    }}
                    title="Clear search"
                  >
                    ×
                  </button>
                )}
              </div>
              {searchResults !== null && (
                <div style={{
                  marginTop: 6,
                  fontSize: 9,
                  color: '#4a4a5a',
                  fontFamily: "'JetBrains Mono', monospace",
                }}>
                  {isSearching ? 'Searching...' : `${searchResults.length} result${searchResults.length !== 1 ? 's' : ''}`}
                </div>
              )}
            </div>

            <div style={{ flex: 1, overflow: 'auto', padding: '4px 0' }}>
              {displayTree ? (
                <StoryTree
                  tree={displayTree}
                  selected={selected}
                  onSelect={handleSelect}
                  expanded={expanded}
                  onToggle={handleToggle}
                  onDelete={handleDelete}
                />
              ) : (
                <div style={{ padding: 16, color: '#2a2a3a', fontSize: 12, textAlign: 'center' }}>
                  No story structure yet
                </div>
              )}
            </div>

            {/* Create buttons */}
            <div style={{
              borderTop: '1px solid #1e1e2e', padding: '6px 12px',
              display: 'flex', alignItems: 'center', gap: 6,
            }}>
              <button onClick={() => setShowCreateForm('scene')} style={{
                padding: '3px 8px', fontSize: 8, borderRadius: 3,
                border: '1px dashed #60a5fa40', background: 'transparent',
                color: '#60a5fa', cursor: 'pointer', fontFamily: 'inherit',
              }}>+ Scene</button>
              <button onClick={() => setShowCreateForm('container')} style={{
                padding: '3px 8px', fontSize: 8, borderRadius: 3,
                border: '1px dashed #4a4a5a40', background: 'transparent',
                color: '#4a4a5a', cursor: 'pointer', fontFamily: 'inherit',
              }}>+ Container</button>
              <button onClick={() => setShowGenerateForm(true)} style={{
                padding: '3px 8px', fontSize: 8, borderRadius: 3,
                border: '1px dashed #c084fc40', background: 'transparent',
                color: '#c084fc', cursor: 'pointer', fontFamily: 'inherit',
              }}>AI Gen</button>
            </div>

            {/* Quick stats */}
            <div style={{
              padding: '10px 12px', borderTop: '1px solid #1e1e2e',
              display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4,
            }}>
              {stats.map(s => (
                <div key={s.label} style={{
                  padding: '4px 8px', borderRadius: 3,
                  background: 'rgba(18, 18, 26, 0.5)',
                }}>
                  <div style={{ color: '#2a2a3a', fontSize: 9, fontFamily: "'JetBrains Mono', monospace" }}>
                    {s.label}
                  </div>
                  <div style={{ color: '#64748b', fontSize: 14, fontWeight: 500 }}>{s.value}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Collapse toggle (left) */}
        {leftCollapsed && (
          <div
            onClick={() => setLeftCollapsed(false)}
            style={{
              width: 24, borderRight: '1px solid #1e1e2e',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              cursor: 'pointer', color: '#2a2a3a', fontSize: 12,
              background: 'rgba(10, 10, 15, 0.4)',
            }}
          >
            ▸
          </div>
        )}

        {/* Center: Editor */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
          <SceneEditor content={currentDocument} entities={entitiesBrief} />
          <WordCountBar scene={sceneWordCount} total={totalWordCount} />
        </div>

        {/* Collapse toggle (right) */}
        {rightCollapsed && (
          <div
            onClick={() => setRightCollapsed(false)}
            style={{
              width: 24, borderLeft: '1px solid #1e1e2e',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              cursor: 'pointer', color: '#2a2a3a', fontSize: 12,
              background: 'rgba(10, 10, 15, 0.4)',
            }}
          >
            ◂
          </div>
        )}

        {/* Right: Chat or Codex */}
        {!rightCollapsed && (
          <div style={{
            width: 300, borderLeft: '1px solid #1e1e2e', display: 'flex', flexDirection: 'column',
            background: 'rgba(10, 10, 15, 0.4)', backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)', flexShrink: 0,
          }}>
            <div style={{
              padding: '10px 12px', borderBottom: '1px solid #1e1e2e',
              display: 'flex', alignItems: 'center', gap: 4,
            }}>
              {[
                { id: 'chat', label: 'AGENTS', icon: '◈' },
                { id: 'codex', label: 'CODEX', icon: '◆' },
              ].map(tab => (
                <button key={tab.id} onClick={() => setRightPanel(tab.id)} style={{
                  flex: 1, padding: '4px 8px', borderRadius: 3, border: 'none',
                  background: rightPanel === tab.id ? 'rgba(192, 132, 252, 0.12)' : 'transparent',
                  color: rightPanel === tab.id ? '#c084fc' : '#4a4a5a',
                  fontSize: 10, cursor: 'pointer', fontFamily: "'JetBrains Mono', monospace",
                  letterSpacing: '0.05em', display: 'flex', alignItems: 'center',
                  justifyContent: 'center', gap: 4,
                }}>
                  <span>{tab.icon}</span> {tab.label}
                </button>
              ))}
              <span
                onClick={() => setRightCollapsed(true)}
                style={{ color: '#2a2a3a', fontSize: 12, cursor: 'pointer', marginLeft: 4 }}
              >
                ▸
              </span>
            </div>
            <div style={{ flex: 1, overflow: 'hidden' }}>
              {rightPanel === 'chat' ? (
                <AgentChat messages={chatMessages} agents={AGENTS} onSend={handleChatSend} />
              ) : (
                <CodexSidebar entities={entitiesBrief} sceneCharacters={sceneCharacters} />
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
