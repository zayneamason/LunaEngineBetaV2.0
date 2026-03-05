import React from 'react';
import Pill from './Pill';
import LockInMeter, { classifyState, STATE_COLORS, STATE_ICONS } from './LockInMeter';
import AnnotationSidebar from './AnnotationSidebar';

const MONO = "'JetBrains Mono','SF Mono',monospace";
const BODY = "'DM Sans',system-ui,sans-serif";
const LABEL = "'Bebas Neue',system-ui,sans-serif";

const DOC_ICON = { pdf: '\uD83D\uDCC4', xlsx: '\uD83D\uDCCA', json: '\uD83D\uDD17', md: '\uD83D\uDCDD', py: '\uD83D\uDC0D' };

const PATTERN_COLORS = {
  ceremonial: '#f97316',
  emergent:   '#34d399',
  utilitarian:'#60a5fa',
};

const PATTERN_LABELS = {
  ceremonial: 'CEREMON',
  emergent:   'EMERGENT',
  utilitarian:'UTIL',
};

function PatternBadge({ pattern }) {
  const p = pattern || 'utilitarian';
  const color = PATTERN_COLORS[p] || PATTERN_COLORS.utilitarian;
  const label = PATTERN_LABELS[p] || p.toUpperCase().slice(0, 7);
  return (
    <span style={{
      padding: '1px 5px', borderRadius: 2,
      fontSize: 7, fontFamily: MONO,
      color, border: `1px solid ${color}40`,
      background: `${color}0a`,
      letterSpacing: 0.8, flexShrink: 0,
    }}>{label}</span>
  );
}

function FloorAlert({ lockIn, floor, pattern }) {
  if (pattern !== 'ceremonial') return null;
  if (!floor || lockIn > floor + 0.05) return null;
  const atFloor = lockIn <= floor;
  return (
    <span style={{
      padding: '1px 5px', borderRadius: 2,
      fontSize: 7, fontFamily: MONO,
      color: atFloor ? '#f43f5e' : '#fbbf24',
      border: `1px solid ${atFloor ? '#f43f5e40' : '#fbbf2440'}`,
      background: atFloor ? '#f43f5e0a' : '#fbbf240a',
      flexShrink: 0,
    }}>
      {atFloor ? '\u26A0 AT FLOOR' : '\u26A0 NEAR FLOOR'}
    </span>
  );
}

export function CompactRow({ col, onExpand, onIngest, onToggle }) {
  const stateColor = STATE_COLORS[col.state] || STATE_COLORS.fluid;
  const icon = STATE_ICONS[col.state] || STATE_ICONS.fluid;
  const opacity = col.state === 'drifting' ? 0.45 : col.state === 'fluid' ? 0.75 : 1;
  const annotationCount = col.access?.annotations || 0;

  return (
    <div
      onClick={() => onExpand(col.key)}
      style={{
        display: 'grid',
        gridTemplateColumns: '24px 1fr 200px 120px 80px 100px',
        alignItems: 'center',
        padding: '8px 14px',
        background: 'var(--ec-bg-panel)',
        borderRadius: 8,
        border: '1px solid var(--ec-border)',
        cursor: 'pointer',
        opacity,
        transition: 'all 0.3s',
        gap: 8,
      }}
      onMouseOver={e => { e.currentTarget.style.borderColor = `${col.color}25`; e.currentTarget.style.opacity = Math.max(opacity, 0.8); }}
      onMouseOut={e => { e.currentTarget.style.borderColor = 'var(--ec-border)'; e.currentTarget.style.opacity = opacity; }}
    >
      {/* State indicator */}
      <div style={{ textAlign: 'center' }}>
        <span style={{ color: stateColor, fontSize: 10 }}>{icon}</span>
      </div>

      {/* Name + annotation count */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, overflow: 'hidden' }}>
        <div style={{ width: 3, height: 12, borderRadius: 1, background: col.color, flexShrink: 0, opacity: col.state === 'drifting' ? 0.3 : 0.8 }} />
        <span style={{
          fontSize: 11, fontFamily: BODY,
          color: col.state === 'drifting' ? 'var(--ec-text-faint)' : 'var(--ec-text-soft)',
          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
        }}>
          {col.label}
        </span>
        {annotationCount > 0 && (
          <span style={{ fontSize: 8, color: '#fbbf24', flexShrink: 0 }}>{'\uD83D\uDCCC'}{annotationCount}</span>
        )}
        <PatternBadge pattern={col.ingestion_pattern} />
        <FloorAlert lockIn={col.lockIn} floor={col.floor} pattern={col.ingestion_pattern} />
      </div>

      {/* Stats */}
      <div style={{ display: 'flex', gap: 4 }}>
        <Pill label="D" value={col.stats?.documents || 0} color={col.color} small />
        <Pill label="E" value={col.stats?.entities || 0} color="#7dd3fc" small />
        <Pill
          label="W"
          value={
            (col.stats?.words || 0) > 999
              ? `${((col.stats?.words || 0) / 1000).toFixed(0)}k`
              : (col.stats?.words || 0)
          }
          color="var(--ec-text-faint)"
          small
        />
      </div>

      {/* Lock-in meter */}
      <LockInMeter value={col.lockIn} />

      {/* State label */}
      <div style={{
        fontSize: 7, fontFamily: LABEL, letterSpacing: 1.5, color: stateColor,
        textAlign: 'center',
      }}>
        {(col.state || 'fluid').toUpperCase()}
      </div>

      {/* Actions */}
      <div style={{ display: 'flex', gap: 4, justifyContent: 'flex-end' }} onClick={e => e.stopPropagation()}>
        <div onClick={() => onIngest(col)} style={{
          padding: '2px 8px', borderRadius: 3, cursor: 'pointer',
          border: `1px solid ${col.color}30`, background: `${col.color}08`,
          fontSize: 8, fontFamily: MONO, color: col.color,
        }}>+INGEST</div>
        <div onClick={() => onToggle?.(col.key)} style={{
          padding: '2px 6px', borderRadius: 3, cursor: 'pointer',
          border: '1px solid var(--ec-border)', fontSize: 8, fontFamily: MONO,
          color: 'var(--ec-text-muted)',
        }}>{col._shelved ? 'WAKE' : 'SHELVE'}</div>
      </div>
    </div>
  );
}

export function ExpandedRow({ col, docs = [], annotations = [], onCollapse, onIngest, onCreateAnnotation }) {
  const stateColor = STATE_COLORS[col.state] || STATE_COLORS.fluid;
  const icon = STATE_ICONS[col.state] || STATE_ICONS.fluid;

  return (
    <div style={{
      background: 'var(--ec-bg-panel)', borderRadius: 10, overflow: 'hidden',
      border: `1px solid ${col.color}20`,
      boxShadow: `0 4px 20px ${col.color}06`,
    }}>
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', padding: '10px 14px', gap: 10,
        borderBottom: '1px solid var(--ec-border)', background: `${col.color}04`,
      }}>
        <span style={{ color: stateColor, fontSize: 11 }}>{icon}</span>
        <div style={{ width: 3, height: 16, borderRadius: 2, background: col.color }} />
        <div style={{ flex: 1 }}>
          <div style={{ fontFamily: LABEL, fontSize: 11, letterSpacing: 1.5, color: col.color }}>
            {col.key.toUpperCase().replace(/_/g, ' ')}
          </div>
          <div style={{ fontSize: 9, color: 'var(--ec-text-faint)', fontFamily: BODY }}>{col.label}</div>
        </div>
        <LockInMeter value={col.lockIn} width={80} />
        <span style={{ fontSize: 8, fontFamily: LABEL, letterSpacing: 1.5, color: stateColor }}>
          {(col.state || 'fluid').toUpperCase()}
        </span>
        <PatternBadge pattern={col.ingestion_pattern} />
        <FloorAlert lockIn={col.lockIn} floor={col.floor} pattern={col.ingestion_pattern} />
        <div onClick={() => onIngest(col)} style={{
          padding: '4px 10px', borderRadius: 4, cursor: 'pointer',
          border: `1px solid ${col.color}40`, background: `${col.color}12`,
          fontSize: 9, fontFamily: MONO, color: col.color,
        }}>+ INGEST</div>
        <div onClick={() => onCollapse(col.key)} style={{
          padding: '4px 6px', borderRadius: 4, cursor: 'pointer',
          border: '1px solid var(--ec-border)', fontSize: 10, color: 'var(--ec-text-faint)',
        }}>{'\u25BE'}</div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 240px', borderTop: '1px solid var(--ec-border)' }}>
        {/* Stats + Tags */}
        <div style={{ padding: '10px 14px', borderRight: '1px solid var(--ec-border)' }}>
          <div style={{ fontSize: 7, fontFamily: LABEL, letterSpacing: 1.5, color: 'var(--ec-text-muted)', marginBottom: 8 }}>
            STATS & TAGS
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 8 }}>
            <Pill label="DOCS" value={col.stats?.documents || 0} color={col.color} />
            <Pill label="CHUNKS" value={col.stats?.chunks || 0} color="var(--ec-text-soft)" />
            <Pill label="WORDS" value={col.stats?.words || 0} color="var(--ec-text-soft)" />
            <Pill label="ENTITIES" value={col.stats?.entities || 0} color="#7dd3fc" />
          </div>
          <div style={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
            {(col.tags || []).map(t => (
              <span key={t} style={{
                padding: '1px 5px', borderRadius: 2, fontSize: 7, fontFamily: MONO,
                color: 'var(--ec-text-muted)', background: 'rgba(58,58,80,0.1)',
              }}>{t}</span>
            ))}
          </div>

          {/* Lock-in breakdown */}
          <div style={{ marginTop: 10 }}>
            <div style={{ fontSize: 7, fontFamily: LABEL, letterSpacing: 1.5, color: 'var(--ec-text-muted)', marginBottom: 4 }}>
              LOCK-IN FACTORS
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 3, fontSize: 8, fontFamily: MONO, color: 'var(--ec-text-faint)' }}>
              <span>Access: {col.access?.count ?? 0}</span>
              <span>Annotations: {col.access?.annotations ?? 0}</span>
              <span>Connections: {col.access?.connections ?? 0}</span>
              <span>Entity overlap: {col.access?.entityOverlap ?? 0}</span>
            </div>
          </div>
        </div>

        {/* Documents */}
        <div style={{ padding: '10px 14px', borderRight: '1px solid var(--ec-border)' }}>
          <div style={{ fontSize: 7, fontFamily: LABEL, letterSpacing: 1.5, color: 'var(--ec-text-muted)', marginBottom: 8 }}>
            DOCUMENTS
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 3, maxHeight: 200, overflow: 'auto' }}>
            {docs.length === 0 && (
              <div style={{ fontSize: 9, color: 'var(--ec-text-muted)', fontStyle: 'italic' }}>Loading documents...</div>
            )}
            {docs.map((doc, i) => {
              const ext = (doc.title || doc.path || '').split('.').pop()?.toLowerCase() || '';
              return (
                <div key={doc.id || i} style={{
                  padding: '5px 8px', borderRadius: 4, background: 'var(--ec-bg-card)',
                  border: '1px solid var(--ec-border)', display: 'flex', alignItems: 'center', gap: 6,
                  fontSize: 10, color: 'var(--ec-text-soft)', fontFamily: BODY, cursor: 'pointer',
                }}
                  onMouseOver={e => e.currentTarget.style.borderColor = 'var(--ec-border-hover)'}
                  onMouseOut={e => e.currentTarget.style.borderColor = 'var(--ec-border)'}
                >
                  <span style={{ fontSize: 9 }}>{DOC_ICON[ext] || '\uD83D\uDCC1'}</span>
                  <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {doc.title || doc.path || doc.id}
                  </span>
                  <div style={{ width: 4, height: 4, borderRadius: '50%', background: '#34d399' }} />
                </div>
              );
            })}
          </div>
        </div>

        {/* Annotations */}
        <AnnotationSidebar
          annotations={annotations}
          onCreateAnnotation={onCreateAnnotation}
        />
      </div>
    </div>
  );
}
