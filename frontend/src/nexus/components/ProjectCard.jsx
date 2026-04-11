import React from 'react';

export default function ProjectCard({ project, isActive, onActivate, onDeactivate }) {
  const accent = `#${project.accent || 'A78BFA'}`;
  const active = isActive || project.active;

  return (
    <div
      onClick={() => (active ? onDeactivate() : onActivate(project.slug))}
      style={{
        display: 'flex', alignItems: 'center', gap: 8,
        padding: '6px 12px', borderRadius: 6, cursor: 'pointer',
        background: active ? `${accent}12` : 'var(--ec-bg-panel)',
        border: `1px solid ${active ? `${accent}40` : 'var(--ec-border)'}`,
        transition: 'all 0.2s',
        minWidth: 0,
      }}
    >
      <span style={{ fontSize: 14, lineHeight: 1 }}>{project.icon || '\u25C7'}</span>
      <div style={{ minWidth: 0 }}>
        <div className="ec-font-body" style={{
          fontSize: 10, fontWeight: 600, color: active ? accent : 'var(--ec-text-soft)',
          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
        }}>
          {project.name}
        </div>
        <div className="ec-font-mono" style={{
          fontSize: 7, color: 'var(--ec-text-faint)',
          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
        }}>
          {(project.collections || []).length} collections
        </div>
      </div>
      {active && (
        <span className="ec-font-mono" style={{
          fontSize: 6, padding: '1px 5px', borderRadius: 3,
          background: `${accent}20`, color: accent, letterSpacing: 1,
        }}>
          ACTIVE
        </span>
      )}
    </div>
  );
}
