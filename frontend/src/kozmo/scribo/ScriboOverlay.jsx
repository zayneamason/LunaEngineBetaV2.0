/**
 * SCRIBO Overlay — Annotation overlay for the SceneEditor
 *
 * This is NOT a sidebar tab. It's a transparent overlay layer that renders
 * directly on top of the document content:
 *   - Gutter pins alongside each paragraph
 *   - Inline text highlights (highlight: { start, end })
 *   - Entity coloring (character/location underlines)
 *   - Character tag bar (scene participants)
 *   - Annotation cards anchored to paragraphs
 *   - Text selection → annotation creation flow
 *   - Action plan sidebar (toggleable)
 *   - Overlay mode: OFF / PINS / FULL
 *
 * Ported from prototype: ClaudeArtifacts/files 3/scribo_overlay.jsx
 * Wired to real API via useOverlayAPI hook.
 */
import React, { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import { useOverlayAPI } from '../hooks/useOverlayAPI';

// --- Annotation Types ---
const ANNOTATION_TYPES = {
  note: { icon: '✎', label: 'Note', color: '#fbbf24', bg: 'rgba(251, 191, 36, 0.08)', border: 'rgba(251, 191, 36, 0.25)' },
  comment: { icon: '💬', label: 'Comment', color: '#818cf8', bg: 'rgba(129, 140, 248, 0.08)', border: 'rgba(129, 140, 248, 0.25)' },
  continuity: { icon: '⚠', label: 'Continuity', color: '#f87171', bg: 'rgba(248, 113, 113, 0.08)', border: 'rgba(248, 113, 113, 0.25)' },
  agent: { icon: '◈', label: 'Agent Task', color: '#34d399', bg: 'rgba(52, 211, 153, 0.08)', border: 'rgba(52, 211, 153, 0.25)' },
  action: { icon: '▶', label: 'LAB Action', color: '#c084fc', bg: 'rgba(192, 132, 252, 0.08)', border: 'rgba(192, 132, 252, 0.25)' },
  luna: { icon: '☾', label: 'Luna', color: '#c084fc', bg: 'rgba(192, 132, 252, 0.06)', border: 'rgba(192, 132, 252, 0.2)' },
};

const ACTION_STATUS = {
  queued: { color: '#fbbf24', label: 'Queued' },
  pending: { color: '#818cf8', label: 'Pending' },
  planning: { color: '#c084fc', label: 'Planning' },
  generating: { color: '#34d399', label: 'Generating' },
  review: { color: '#38bdf8', label: 'Review' },
  complete: { color: '#4ade80', label: 'Complete' },
};

const OVERLAY_MODES = [
  { id: 'off', label: 'OFF', icon: '○' },
  { id: 'pins', label: 'PINS', icon: '◉' },
  { id: 'full', label: 'FULL', icon: '◈' },
];

// ============================================================================
// Sub-components
// ============================================================================

// --- Gutter Pin ---
function GutterPin({ count, types, onClick, isActive }) {
  const primaryType = types[0];
  const config = ANNOTATION_TYPES[primaryType] || ANNOTATION_TYPES.note;
  const hasAction = types.includes('action');
  const hasContinuity = types.includes('continuity');

  return (
    <div
      onClick={onClick}
      style={{
        position: 'relative',
        width: 20, height: 20,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        cursor: 'pointer', borderRadius: 4,
        background: isActive ? config.bg : 'transparent',
        border: `1px solid ${isActive ? config.border : 'transparent'}`,
        transition: 'all 0.15s ease',
      }}
      onMouseEnter={e => {
        e.currentTarget.style.background = config.bg;
        e.currentTarget.style.borderColor = config.border;
      }}
      onMouseLeave={e => {
        if (!isActive) {
          e.currentTarget.style.background = 'transparent';
          e.currentTarget.style.borderColor = 'transparent';
        }
      }}
    >
      <span style={{ fontSize: 10, color: config.color }}>{config.icon}</span>
      {count > 1 && (
        <span style={{
          position: 'absolute', top: -4, right: -4,
          width: 12, height: 12, borderRadius: '50%',
          background: hasContinuity ? '#f87171' : hasAction ? '#c084fc' : config.color,
          color: '#16161f', fontSize: 7, fontWeight: 700,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          {count}
        </span>
      )}
    </div>
  );
}

// --- Annotation Card ---
function AnnotationCard({ annotation, onResolve, onDelete, onPushToLab, compact = false }) {
  const config = ANNOTATION_TYPES[annotation.type] || ANNOTATION_TYPES.note;
  const [expanded, setExpanded] = useState(!compact);

  return (
    <div style={{
      borderLeft: `2px solid ${config.color}`,
      borderRadius: '0 6px 6px 0',
      background: config.bg,
      marginBottom: 6,
      overflow: 'hidden',
      opacity: annotation.resolved ? 0.5 : 1,
      transition: 'all 0.2s ease',
    }}>
      {/* Header */}
      <div
        onClick={() => compact && setExpanded(!expanded)}
        style={{
          display: 'flex', alignItems: 'center', gap: 6,
          padding: '6px 10px',
          cursor: compact ? 'pointer' : 'default',
        }}
      >
        <span style={{ color: config.color, fontSize: 11 }}>{config.icon}</span>
        <span style={{
          color: config.color, fontSize: 9,
          fontFamily: "'JetBrains Mono', monospace",
          textTransform: 'uppercase', letterSpacing: '0.06em',
        }}>
          {config.label}
        </span>
        <span style={{ color: '#3a3a4e', fontSize: 9 }}>·</span>
        <span style={{ color: '#5a5a6e', fontSize: 10 }}>{annotation.author}</span>
        {annotation.time && (
          <span style={{ color: '#3a3a4e', fontSize: 9, marginLeft: 'auto' }}>{annotation.time}</span>
        )}
        {compact && (
          <span style={{ color: '#3a3a4e', fontSize: 10, marginLeft: annotation.time ? 0 : 'auto' }}>
            {expanded ? '▾' : '▸'}
          </span>
        )}
      </div>

      {/* Body */}
      {(!compact || expanded) && (
        <div style={{ padding: '0 10px 8px' }}>
          <div style={{ color: '#cbd5e1', fontSize: 12, lineHeight: 1.6 }}>
            {annotation.text}
          </div>

          {/* Highlight range indicator */}
          {annotation.highlight && (
            <div style={{
              marginTop: 4, fontSize: 9, color: '#5a5a6e',
              fontFamily: "'JetBrains Mono', monospace",
            }}>
              chars {annotation.highlight.start}–{annotation.highlight.end}
            </div>
          )}

          {/* LAB Action */}
          {annotation.lab_action && (
            <div style={{
              marginTop: 8, padding: '8px 10px',
              background: 'rgba(192, 132, 252, 0.06)',
              borderRadius: 4, border: '1px solid rgba(192, 132, 252, 0.15)',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                <span style={{
                  color: '#c084fc', fontSize: 9,
                  fontFamily: "'JetBrains Mono', monospace",
                  textTransform: 'uppercase',
                }}>
                  ▶ LAB ACTION
                </span>
                <span style={{
                  color: ACTION_STATUS[annotation.lab_action.status]?.color || '#64748b',
                  fontSize: 9, padding: '1px 6px', borderRadius: 3,
                  background: `${ACTION_STATUS[annotation.lab_action.status]?.color || '#64748b'}15`,
                  fontFamily: "'JetBrains Mono', monospace",
                }}>
                  {annotation.lab_action.status}
                </span>
                {annotation.lab_action.assignee && (
                  <span style={{ color: '#34d399', fontSize: 9, marginLeft: 'auto' }}>
                    → {annotation.lab_action.assignee}
                  </span>
                )}
              </div>
              {annotation.lab_action.prompt && (
                <div style={{
                  color: '#94a3b8', fontSize: 11, fontStyle: 'italic',
                  padding: '4px 8px', background: 'rgba(0,0,0,0.2)', borderRadius: 3,
                }}>
                  {annotation.lab_action.prompt}
                </div>
              )}
              {annotation.lab_action.shots && (
                <div style={{ marginTop: 4 }}>
                  {annotation.lab_action.shots.map((shot, i) => (
                    <div key={i} style={{
                      display: 'flex', alignItems: 'flex-start', gap: 6,
                      padding: '3px 0', color: '#94a3b8', fontSize: 11,
                    }}>
                      <span style={{
                        color: '#c084fc', fontSize: 9, marginTop: 2,
                        fontFamily: "'JetBrains Mono', monospace",
                      }}>
                        {String(i + 1).padStart(2, '0')}
                      </span>
                      <span>{shot}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Agent Task */}
          {annotation.agent_task && (
            <div style={{
              marginTop: 8, padding: '6px 10px',
              background: 'rgba(52, 211, 153, 0.06)',
              borderRadius: 4, border: '1px solid rgba(52, 211, 153, 0.15)',
              display: 'flex', alignItems: 'center', gap: 8,
            }}>
              <span style={{ color: '#34d399', fontSize: 10 }}>◈</span>
              <span style={{
                color: '#34d399', fontSize: 10,
                fontFamily: "'JetBrains Mono', monospace",
              }}>
                {annotation.agent_task.agent}
              </span>
              <span style={{ color: '#5a5a6e', fontSize: 10 }}>
                {annotation.agent_task.action}
              </span>
              <span style={{
                marginLeft: 'auto',
                color: ACTION_STATUS[annotation.agent_task.status]?.color || '#64748b',
                fontSize: 9, padding: '1px 6px', borderRadius: 3,
                background: `${ACTION_STATUS[annotation.agent_task.status]?.color || '#64748b'}15`,
                fontFamily: "'JetBrains Mono', monospace",
              }}>
                {annotation.agent_task.status}
              </span>
            </div>
          )}

          {/* Actions row */}
          <div style={{ display: 'flex', gap: 8, marginTop: 8, alignItems: 'center' }}>
            <button
              onClick={() => onResolve?.(annotation.id)}
              style={{
                padding: '2px 8px', borderRadius: 3, border: '1px solid #282840',
                background: 'transparent', color: '#5a5a6e', fontSize: 9,
                cursor: 'pointer', fontFamily: "'JetBrains Mono', monospace",
              }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = '#4ade80'; e.currentTarget.style.color = '#4ade80'; }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = '#282840'; e.currentTarget.style.color = '#5a5a6e'; }}
            >
              {annotation.resolved ? '↩ reopen' : '✓ resolve'}
            </button>
            {annotation.lab_action && (
              <button
                onClick={() => onPushToLab?.(annotation.id)}
                style={{
                  padding: '2px 8px', borderRadius: 3,
                  border: '1px solid rgba(192, 132, 252, 0.3)',
                  background: 'rgba(192, 132, 252, 0.08)',
                  color: '#c084fc', fontSize: 9, cursor: 'pointer',
                  fontFamily: "'JetBrains Mono', monospace",
                }}
              >→ send to LAB</button>
            )}
            {annotation.agent_task && (
              <button
                onClick={() => onPushToLab?.(annotation.id)}
                style={{
                  padding: '2px 8px', borderRadius: 3,
                  border: '1px solid rgba(52, 211, 153, 0.3)',
                  background: 'rgba(52, 211, 153, 0.08)',
                  color: '#34d399', fontSize: 9, cursor: 'pointer',
                  fontFamily: "'JetBrains Mono', monospace",
                }}
              >◈ dispatch</button>
            )}
            <button
              onClick={() => onDelete?.(annotation.id)}
              style={{
                padding: '2px 6px', borderRadius: 3, border: 'none',
                background: 'transparent', color: '#3a3a4e', fontSize: 9,
                cursor: 'pointer', marginLeft: 'auto',
              }}
              onMouseEnter={e => e.currentTarget.style.color = '#f87171'}
              onMouseLeave={e => e.currentTarget.style.color = '#3a3a4e'}
            >×</button>
          </div>
        </div>
      )}
    </div>
  );
}

// --- Annotation Creator ---
function AnnotationCreator({ onAdd, onCancel, selectionRange }) {
  const [type, setType] = useState('note');
  const [text, setText] = useState('');
  const inputRef = useRef(null);

  useEffect(() => { inputRef.current?.focus(); }, []);

  const handleSubmit = () => {
    if (!text.trim()) return;
    onAdd({
      type,
      author: type === 'luna' ? 'Luna' : 'User',
      text: text.trim(),
      ...(selectionRange ? { highlight: selectionRange } : {}),
      ...(type === 'action' ? {
        lab_action: { type: 'generate_image', status: 'planning', prompt: text.trim(), assignee: 'Maya' },
      } : {}),
      ...(type === 'agent' ? {
        agent_task: { agent: 'Maya', status: 'pending', action: 'generate_reference' },
      } : {}),
    });
    setText('');
    onCancel();
  };

  return (
    <div style={{
      background: 'rgba(26, 26, 38, 0.95)', borderRadius: 6,
      border: '1px solid #282840', padding: 10, marginBottom: 6,
      backdropFilter: 'blur(12px)',
    }}>
      {selectionRange && (
        <div style={{
          fontSize: 9, color: '#5a5a6e', marginBottom: 6,
          fontFamily: "'JetBrains Mono', monospace",
        }}>
          Anchored to chars {selectionRange.start}–{selectionRange.end}
        </div>
      )}
      <div style={{ display: 'flex', gap: 3, marginBottom: 8, flexWrap: 'wrap' }}>
        {Object.entries(ANNOTATION_TYPES).map(([key, cfg]) => (
          <button
            key={key}
            onClick={() => setType(key)}
            style={{
              padding: '3px 8px', borderRadius: 3,
              border: `1px solid ${type === key ? cfg.color + '60' : '#282840'}`,
              background: type === key ? cfg.bg : 'transparent',
              color: type === key ? cfg.color : '#5a5a6e',
              fontSize: 9, cursor: 'pointer',
              fontFamily: "'JetBrains Mono', monospace",
            }}
          >
            {cfg.icon} {cfg.label}
          </button>
        ))}
      </div>
      <textarea
        ref={inputRef}
        value={text}
        onChange={e => setText(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter' && e.metaKey) handleSubmit(); if (e.key === 'Escape') onCancel(); }}
        placeholder={
          type === 'action' ? 'Describe the LAB action (image, shot sequence, etc.)...'
            : type === 'agent' ? 'Describe the agent task...'
            : type === 'continuity' ? 'Describe the continuity issue...'
            : 'Write your note...'
        }
        style={{
          width: '100%', minHeight: 60, padding: 8, borderRadius: 4,
          background: 'rgba(20, 20, 30, 0.85)', border: '1px solid #282840',
          color: '#e2e8f0', fontSize: 12, resize: 'vertical',
          outline: 'none', lineHeight: 1.5,
        }}
        onFocus={e => e.currentTarget.style.borderColor = ANNOTATION_TYPES[type].color + '40'}
        onBlur={e => e.currentTarget.style.borderColor = '#282840'}
      />
      <div style={{ display: 'flex', gap: 6, marginTop: 6, justifyContent: 'flex-end' }}>
        <button onClick={onCancel} style={{
          padding: '4px 10px', borderRadius: 4, border: '1px solid #282840',
          background: 'transparent', color: '#5a5a6e', fontSize: 11, cursor: 'pointer',
        }}>Cancel</button>
        <button onClick={handleSubmit} style={{
          padding: '4px 12px', borderRadius: 4, border: 'none',
          background: text.trim() ? ANNOTATION_TYPES[type].color + '20' : '#282840',
          color: text.trim() ? ANNOTATION_TYPES[type].color : '#3a3a4e',
          fontSize: 11, cursor: text.trim() ? 'pointer' : 'default',
        }}>Add {ANNOTATION_TYPES[type].label} ⌘↵</button>
      </div>
    </div>
  );
}

// --- Entity-highlighted Text Renderer ---
function HighlightedText({ text, entities, annotations, overlayMode }) {
  if (!text) return null;

  // Collect all highlight ranges: entity positions + annotation highlights
  const ranges = [];

  // Entity highlights (character/location coloring)
  if (entities && entities.length > 0) {
    entities.forEach(ent => {
      ranges.push({
        start: ent.start,
        end: ent.end,
        type: 'entity',
        color: ent.color,
        name: ent.name,
      });
    });
  }

  // Annotation highlight ranges (only in FULL mode)
  if (overlayMode === 'full' && annotations) {
    annotations.forEach(ann => {
      if (ann.highlight) {
        const cfg = ANNOTATION_TYPES[ann.type] || ANNOTATION_TYPES.note;
        ranges.push({
          start: ann.highlight.start,
          end: ann.highlight.end,
          type: 'annotation',
          color: cfg.color,
          annotationId: ann.id,
        });
      }
    });
  }

  if (ranges.length === 0) return <>{text}</>;

  // Sort by start position, then by length (longer first for nesting)
  const sorted = [...ranges].sort((a, b) => a.start - b.start || (b.end - b.start) - (a.end - a.start));

  // Flatten overlapping ranges into non-overlapping segments
  const parts = [];
  let lastEnd = 0;

  sorted.forEach((range, i) => {
    // Clamp to text bounds
    const start = Math.max(0, Math.min(range.start, text.length));
    const end = Math.max(start, Math.min(range.end, text.length));

    if (start > lastEnd) {
      parts.push(<span key={`t${i}`}>{text.slice(lastEnd, start)}</span>);
    }

    if (start >= lastEnd) {
      if (range.type === 'entity') {
        parts.push(
          <span key={`e${i}`} style={{
            color: range.color,
            textDecoration: 'underline',
            textDecorationColor: range.color + '40',
            textUnderlineOffset: '3px',
            cursor: 'pointer',
          }} title={range.name}>
            {text.slice(start, end)}
          </span>
        );
      } else {
        parts.push(
          <span key={`h${i}`} style={{
            background: range.color + '18',
            borderBottom: `2px solid ${range.color}50`,
            borderRadius: 1,
            padding: '0 1px',
          }}>
            {text.slice(start, end)}
          </span>
        );
      }
      lastEnd = end;
    }
  });

  if (lastEnd < text.length) {
    parts.push(<span key="last">{text.slice(lastEnd)}</span>);
  }

  return <>{parts}</>;
}

// --- Annotated Paragraph (with overlay) ---
function AnnotatedParagraph({
  paragraph, annotations, overlayMode, activeParagraph,
  onPinClick, onAddAnnotation, isCreating, onCancelCreate,
  onResolve, onDelete, onPushToLab, selectionRange,
}) {
  const paraAnnotations = annotations.filter(a => a.paragraph_id === paragraph.id);
  const isActive = activeParagraph === paragraph.id;
  const paraRef = useRef(null);

  // Text selection handler — capture selected range for annotation anchoring
  const handleMouseUp = useCallback(() => {
    if (overlayMode === 'off') return;
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed || !paraRef.current) return;

    // Check if selection is within this paragraph
    const range = sel.getRangeAt(0);
    if (!paraRef.current.contains(range.commonAncestorContainer)) return;

    // Calculate character offset from the paragraph text
    const textContent = paraRef.current.textContent || '';
    const preRange = document.createRange();
    preRange.selectNodeContents(paraRef.current);
    preRange.setEnd(range.startContainer, range.startOffset);
    const start = preRange.toString().length;
    const end = start + range.toString().length;

    if (end > start && start >= 0 && end <= textContent.length) {
      onAddAnnotation(paragraph.id, null, { start, end });
    }
  }, [overlayMode, paragraph.id, onAddAnnotation]);

  // Paragraph type styling
  const textStyle = paragraph.type === 'title' ? {
    fontSize: 18, fontWeight: 600, color: '#e2e8f0',
    fontFamily: "'Space Grotesk', sans-serif",
    letterSpacing: '0.02em', padding: '8px 0',
  } : paragraph.type === 'section' ? {
    fontSize: 13, fontWeight: 500, color: '#94a3b8',
    fontFamily: "'JetBrains Mono', monospace",
    letterSpacing: '0.06em', padding: '16px 0 4px',
    textTransform: 'uppercase',
  } : {
    fontSize: 15, color: '#cbd5e1', lineHeight: 1.85,
    fontFamily: "'Crimson Pro', 'Georgia', serif",
    textIndent: paragraph.type === 'prose' ? '1.5em' : undefined,
  };

  return (
    <div
      id={`overlay-para-${paragraph.id}`}
      style={{
        position: 'relative',
        display: 'flex',
        gap: 0,
        marginBottom: paragraph.type === 'prose' ? 20 : 8,
      }}
    >
      {/* Gutter */}
      <div style={{
        width: 28, flexShrink: 0,
        display: 'flex', flexDirection: 'column',
        alignItems: 'center',
        paddingTop: paragraph.type === 'prose' ? 4 : 0,
        gap: 4,
      }}>
        {overlayMode !== 'off' && paraAnnotations.length > 0 && (
          <GutterPin
            count={paraAnnotations.length}
            types={paraAnnotations.map(a => a.type)}
            onClick={() => onPinClick(paragraph.id)}
            isActive={isActive}
          />
        )}
        {overlayMode !== 'off' && paraAnnotations.length === 0 && paragraph.type === 'prose' && (
          <div
            onClick={() => onAddAnnotation(paragraph.id)}
            style={{
              width: 18, height: 18, borderRadius: 3,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              cursor: 'pointer', color: '#282840', fontSize: 12,
              transition: 'all 0.15s',
            }}
            onMouseEnter={e => { e.currentTarget.style.color = '#5a5a6e'; e.currentTarget.style.background = 'rgba(255,255,255,0.03)'; }}
            onMouseLeave={e => { e.currentTarget.style.color = '#282840'; e.currentTarget.style.background = 'transparent'; }}
          >
            +
          </div>
        )}
      </div>

      {/* Text + Annotations */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div ref={paraRef} onMouseUp={handleMouseUp} style={textStyle}>
          <HighlightedText
            text={paragraph.text}
            entities={paragraph.entities}
            annotations={paraAnnotations}
            overlayMode={overlayMode}
          />
        </div>

        {/* Inline annotations (full mode) */}
        {overlayMode === 'full' && isActive && paraAnnotations.length > 0 && (
          <div style={{
            marginTop: 8, marginBottom: 4,
            paddingLeft: 8,
            borderLeft: '1px solid #282840',
          }}>
            {paraAnnotations.map(ann => (
              <AnnotationCard
                key={ann.id}
                annotation={ann}
                onResolve={onResolve}
                onDelete={onDelete}
                onPushToLab={onPushToLab}
              />
            ))}
          </div>
        )}

        {/* Annotation creator */}
        {isCreating && activeParagraph === paragraph.id && (
          <div style={{ marginTop: 8 }}>
            <AnnotationCreator
              onAdd={(data) => onAddAnnotation(paragraph.id, data)}
              onCancel={onCancelCreate}
              selectionRange={selectionRange}
            />
          </div>
        )}
      </div>
    </div>
  );
}

// --- Action Plan Sidebar ---
function ActionPlanSidebar({ annotations, onJump, onPushAll }) {
  const actions = annotations.filter(a => a.lab_action || a.agent_task);
  const notes = annotations.filter(a => a.type === 'note' || a.type === 'comment');
  const issues = annotations.filter(a => a.type === 'continuity');
  const lunaInsights = annotations.filter(a => a.type === 'luna');
  const unresolved = annotations.filter(a => !a.resolved);

  const [tab, setTab] = useState('actions');

  const tabItems = [
    { id: 'actions', label: 'Actions', count: actions.length, color: '#c084fc' },
    { id: 'issues', label: 'Issues', count: issues.length, color: '#f87171' },
    { id: 'notes', label: 'Notes', count: notes.length, color: '#fbbf24' },
    { id: 'luna', label: 'Luna', count: lunaInsights.length, color: '#c084fc' },
  ];

  const currentList = tab === 'actions' ? actions
    : tab === 'issues' ? issues
    : tab === 'notes' ? notes
    : lunaInsights;

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Summary */}
      <div style={{ padding: '10px 12px', borderBottom: '1px solid #282840' }}>
        <div style={{
          fontSize: 10, color: '#5a5a6e',
          fontFamily: "'JetBrains Mono', monospace",
          textTransform: 'uppercase', letterSpacing: '0.08em',
          marginBottom: 8,
        }}>
          Overlay Summary
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4 }}>
          <div style={{ padding: '4px 8px', borderRadius: 3, background: 'rgba(18, 18, 26, 0.5)' }}>
            <div style={{ color: '#3a3a4e', fontSize: 9, fontFamily: "'JetBrains Mono', monospace" }}>Total</div>
            <div style={{ color: '#e2e8f0', fontSize: 16, fontWeight: 500 }}>{annotations.length}</div>
          </div>
          <div style={{ padding: '4px 8px', borderRadius: 3, background: 'rgba(18, 18, 26, 0.5)' }}>
            <div style={{ color: '#3a3a4e', fontSize: 9, fontFamily: "'JetBrains Mono', monospace" }}>Open</div>
            <div style={{ color: '#fbbf24', fontSize: 16, fontWeight: 500 }}>{unresolved.length}</div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', padding: '6px 8px', gap: 2, borderBottom: '1px solid #282840' }}>
        {tabItems.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            style={{
              flex: 1, padding: '4px 4px', borderRadius: 3, border: 'none',
              background: tab === t.id ? t.color + '15' : 'transparent',
              color: tab === t.id ? t.color : '#5a5a6e',
              fontSize: 9, cursor: 'pointer',
              fontFamily: "'JetBrains Mono', monospace",
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 3,
            }}
          >
            {t.label}
            <span style={{
              background: tab === t.id ? t.color + '25' : '#282840',
              color: tab === t.id ? t.color : '#3a3a4e',
              padding: '0 4px', borderRadius: 2, fontSize: 8,
            }}>
              {t.count}
            </span>
          </button>
        ))}
      </div>

      {/* List */}
      <div style={{ flex: 1, overflow: 'auto', padding: 8 }}>
        {currentList.length === 0 ? (
          <div style={{ color: '#3a3a4e', fontSize: 11, textAlign: 'center', paddingTop: 24 }}>
            No {tab} yet
          </div>
        ) : currentList.map(ann => (
          <div
            key={ann.id}
            onClick={() => onJump?.(ann.paragraph_id)}
            style={{ cursor: 'pointer' }}
          >
            <AnnotationCard annotation={ann} compact />
          </div>
        ))}
      </div>

      {/* Batch actions */}
      {tab === 'actions' && actions.length > 0 && (
        <div style={{
          padding: '8px 12px', borderTop: '1px solid #282840',
          display: 'flex', gap: 6,
        }}>
          <button
            onClick={onPushAll}
            style={{
              flex: 1, padding: '6px 10px', borderRadius: 4, border: 'none',
              background: 'rgba(192, 132, 252, 0.12)',
              color: '#c084fc', fontSize: 11, cursor: 'pointer',
            }}
          >→ Send All to LAB</button>
          <button
            onClick={onPushAll}
            style={{
              padding: '6px 10px', borderRadius: 4, border: 'none',
              background: 'rgba(52, 211, 153, 0.12)',
              color: '#34d399', fontSize: 11, cursor: 'pointer',
            }}
          >◈ Dispatch</button>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Main Overlay Component
// ============================================================================

/**
 * ScriboOverlay — renders as an overlay layer on the SceneEditor.
 *
 * Props:
 *   docSlug        — current document slug (for API calls)
 *   paragraphs     — array of { id, text, type?, entities? }
 *   sceneEntities  — characters/locations present in this scene (for tag bar)
 *   sceneMeta      — { title, part, status, location, time } for header bar
 *   sceneWordCount — word count for this scene
 *   totalWordCount — total project word count
 *   overlayMode    — 'off' | 'pins' | 'full' (controlled from parent)
 *   onModeChange   — callback to change overlay mode
 */
export default function ScriboOverlay({
  docSlug,
  paragraphs = [],
  sceneEntities = [],
  sceneMeta = {},
  sceneWordCount = 0,
  totalWordCount = 0,
  overlayMode = 'pins',
  onModeChange,
}) {
  const api = useOverlayAPI();
  const [annotations, setAnnotations] = useState([]);
  const [activeParagraph, setActiveParagraph] = useState(null);
  const [isCreating, setIsCreating] = useState(false);
  const [selectionRange, setSelectionRange] = useState(null);
  const [showActionPlan, setShowActionPlan] = useState(false);
  const [filterType, setFilterType] = useState('all');

  // Load overlay on mount / document change
  useEffect(() => {
    if (!docSlug) return;
    api.getOverlay(docSlug).then(data => {
      if (data?.annotations) setAnnotations(data.annotations);
      else setAnnotations([]);
    });
  }, [docSlug]); // eslint-disable-line react-hooks/exhaustive-deps

  const handlePinClick = useCallback((paraId) => {
    if (activeParagraph === paraId) {
      setActiveParagraph(null);
    } else {
      setActiveParagraph(paraId);
      if (overlayMode === 'pins') onModeChange?.('full');
    }
  }, [activeParagraph, overlayMode, onModeChange]);

  const handleAddAnnotation = useCallback(async (paraId, data, range) => {
    if (data) {
      // Submit annotation to API
      const payload = { ...data, paragraph_id: paraId };
      const created = await api.addAnnotation(docSlug, payload);
      if (created) {
        setAnnotations(prev => [...prev, created]);
      } else {
        // API failed (backend down, no project slug, etc.) — add locally
        const localAnn = {
          id: `local_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
          ...payload,
          resolved: false,
          created_at: new Date().toISOString(),
        };
        setAnnotations(prev => [...prev, localAnn]);
      }
      setIsCreating(false);
      setSelectionRange(null);
    } else {
      // Open creator for this paragraph
      setActiveParagraph(paraId);
      setIsCreating(true);
      if (range) setSelectionRange(range);
    }
  }, [api, docSlug]);

  const handleResolve = useCallback(async (annId) => {
    const updated = await api.resolveAnnotation(docSlug, annId);
    if (updated) {
      setAnnotations(prev => prev.map(a => a.id === annId ? updated : a));
    } else {
      // Local fallback — toggle resolved
      setAnnotations(prev => prev.map(a =>
        a.id === annId ? { ...a, resolved: !a.resolved, resolved_at: a.resolved ? null : new Date().toISOString() } : a
      ));
    }
  }, [api, docSlug]);

  const handleDelete = useCallback(async (annId) => {
    const ok = await api.deleteAnnotation(docSlug, annId);
    if (!ok) {
      // Local fallback — remove anyway
    }
    setAnnotations(prev => prev.filter(a => a.id !== annId));
  }, [api, docSlug]);

  const handlePushToLab = useCallback(async (annId) => {
    await api.pushToLab(docSlug, annId);
  }, [api, docSlug]);

  const handlePushAll = useCallback(async () => {
    await api.pushAllActions(docSlug);
  }, [api, docSlug]);

  const handleJump = useCallback((paraId) => {
    setActiveParagraph(paraId);
    onModeChange?.('full');
    const el = document.getElementById(`overlay-para-${paraId}`);
    el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, [onModeChange]);

  const filteredAnnotations = filterType === 'all'
    ? annotations
    : annotations.filter(a => a.type === filterType);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e) => {
      // ⌥A — new annotation on active paragraph
      if (e.altKey && e.key === 'a') {
        e.preventDefault();
        if (activeParagraph) {
          setIsCreating(true);
        }
      }
      // ⌘⇧O — cycle overlay mode
      if (e.metaKey && e.shiftKey && e.key === 'o') {
        e.preventDefault();
        const modes = ['off', 'pins', 'full'];
        const idx = modes.indexOf(overlayMode);
        onModeChange?.(modes[(idx + 1) % modes.length]);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [activeParagraph, overlayMode, onModeChange]);

  // If overlay is off, render nothing (parent SceneEditor shows normally)
  if (overlayMode === 'off') return null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Character / Entity Tag Bar */}
      {sceneEntities.length > 0 && (
        <div style={{
          display: 'flex', gap: 8, padding: '8px 16px 8px 44px',
          flexWrap: 'wrap', alignItems: 'center',
          borderBottom: '1px solid #282840',
          background: 'rgba(20, 20, 30, 0.4)',
          flexShrink: 0,
        }}>
          {sceneEntities.map(c => (
            <span key={c.name || c.slug} style={{
              display: 'flex', alignItems: 'center', gap: 4,
              padding: '3px 10px', borderRadius: 4,
              background: (c.color || '#64748b') + '12',
              border: `1px solid ${(c.color || '#64748b')}25`,
            }}>
              <span style={{
                width: 6, height: 6, borderRadius: '50%',
                background: c.color || '#64748b',
              }} />
              <span style={{
                color: c.color || '#64748b', fontSize: 12,
                fontFamily: "'JetBrains Mono', monospace",
              }}>
                {c.name}
              </span>
            </span>
          ))}
          {sceneMeta.location && (
            <span style={{ color: '#5a5a6e', fontSize: 11, display: 'flex', alignItems: 'center', gap: 4 }}>
              ◎ {sceneMeta.location}
            </span>
          )}
          {sceneMeta.time && (
            <span style={{ color: '#5a5a6e', fontSize: 11 }}>
              · ◑ {sceneMeta.time}
            </span>
          )}
          {sceneMeta.status && (
            <span style={{
              marginLeft: 'auto', fontSize: 10,
              padding: '2px 8px', borderRadius: 3,
              fontFamily: "'JetBrains Mono', monospace",
              textTransform: 'uppercase',
              ...(sceneMeta.status === 'draft' ? { color: '#fbbf24', background: 'rgba(251, 191, 36, 0.1)' }
                : sceneMeta.status === 'polished' ? { color: '#4ade80', background: 'rgba(74, 222, 128, 0.1)' }
                : { color: '#818cf8', background: 'rgba(129, 140, 248, 0.1)' }),
            }}>
              {sceneMeta.status}
            </span>
          )}
        </div>
      )}

      {/* Filter bar (when overlay is active) */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8, padding: '4px 16px 4px 44px',
        borderBottom: '1px solid #282840',
        background: 'rgba(20, 20, 30, 0.3)',
        flexShrink: 0,
      }}>
        <span style={{
          color: '#3a3a4e', fontSize: 9,
          fontFamily: "'JetBrains Mono', monospace",
        }}>FILTER</span>
        {[
          { id: 'all', label: 'All' },
          ...Object.entries(ANNOTATION_TYPES).map(([id, cfg]) => ({ id, label: cfg.icon })),
        ].map(f => (
          <button
            key={f.id}
            onClick={() => setFilterType(f.id)}
            style={{
              padding: '2px 6px', borderRadius: 3, border: 'none',
              background: filterType === f.id ? 'rgba(255,255,255,0.06)' : 'transparent',
              color: filterType === f.id ? '#e2e8f0' : '#3a3a4e',
              fontSize: 10, cursor: 'pointer',
            }}
          >{f.label}</button>
        ))}

        <div style={{ flex: 1 }} />

        <span style={{
          color: '#5a5a6e', fontSize: 9,
          fontFamily: "'JetBrains Mono', monospace",
        }}>
          {annotations.length} annotations ({annotations.filter(a => !a.resolved).length} open)
        </span>

        <button
          onClick={() => setShowActionPlan(!showActionPlan)}
          style={{
            padding: '3px 10px', borderRadius: 4,
            border: `1px solid ${showActionPlan ? 'rgba(192, 132, 252, 0.3)' : '#282840'}`,
            background: showActionPlan ? 'rgba(192, 132, 252, 0.08)' : 'transparent',
            color: showActionPlan ? '#c084fc' : '#5a5a6e',
            fontSize: 10, cursor: 'pointer',
            fontFamily: "'JetBrains Mono', monospace",
          }}
        >☰ Plan</button>
      </div>

      {/* Main: Paragraphs + Action Plan */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        {/* Writing surface with overlay annotations */}
        <div style={{ flex: 1, overflow: 'auto', padding: '24px 24px 80px' }}>
          <div style={{ maxWidth: 700, margin: '0 auto' }}>
            {paragraphs.map(para => (
              <AnnotatedParagraph
                key={para.id}
                paragraph={para}
                annotations={filteredAnnotations}
                overlayMode={overlayMode}
                activeParagraph={activeParagraph}
                onPinClick={handlePinClick}
                onAddAnnotation={handleAddAnnotation}
                isCreating={isCreating}
                onCancelCreate={() => { setIsCreating(false); setSelectionRange(null); }}
                onResolve={handleResolve}
                onDelete={handleDelete}
                onPushToLab={handlePushToLab}
                selectionRange={selectionRange}
              />
            ))}
          </div>
        </div>

        {/* Action Plan sidebar */}
        {showActionPlan && (
          <div style={{
            width: 280, borderLeft: '1px solid #282840',
            background: 'rgba(20, 20, 30, 0.5)', flexShrink: 0,
          }}>
            <ActionPlanSidebar
              annotations={annotations}
              onJump={handleJump}
              onPushAll={handlePushAll}
            />
          </div>
        )}
      </div>

      {/* Bottom bar: word counts + keyboard hints */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 12, padding: '6px 16px',
        borderTop: '1px solid #282840', background: 'rgba(20, 20, 30, 0.5)',
        fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#5a5a6e',
        flexShrink: 0,
      }}>
        <span>Scene: {sceneWordCount?.toLocaleString() || '—'} words</span>
        <span style={{ color: '#3a3a4e' }}>|</span>
        <span>Project: {totalWordCount?.toLocaleString() || '—'} words</span>
        <span style={{ color: '#3a3a4e' }}>|</span>
        <span>Annotations: {annotations.length} ({annotations.filter(a => !a.resolved).length} open)</span>
        {filteredAnnotations.some(a => a.lab_action || a.agent_task) && (
          <button
            onClick={handlePushAll}
            style={{
              padding: '3px 10px', borderRadius: 4, border: 'none',
              background: 'rgba(192, 132, 252, 0.12)', color: '#c084fc',
              fontSize: 10, cursor: 'pointer',
            }}
          >→ Push All to LAB</button>
        )}
        <span style={{ marginLeft: 'auto', color: '#3a3a4e' }}>
          ⌥A new annotation · ⌘⇧O overlay toggle · select text to anchor
        </span>
      </div>
    </div>
  );
}
