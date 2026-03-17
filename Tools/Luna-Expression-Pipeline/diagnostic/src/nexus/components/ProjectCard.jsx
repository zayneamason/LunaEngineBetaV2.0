import React from 'react';

const MONO = "'JetBrains Mono','SF Mono',monospace";
const BODY = "'DM Sans',system-ui,sans-serif";

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
      <span style={{ fontSize: 14, lineHeight: 1 }}>{project.icon || '◇'}</span>
      <div style={{ minWidth: 0 }}>
        <div style={{
          fontSize: 10, fontWeight: 600, color: active ? accent : 'var(--ec-text-soft)',
          fontFamily: BODY, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
        }}>
          {project.name}
        </div>
        <div style={{
          fontSize: 7, fontFamily: MONO, color: 'var(--ec-text-faint)',
          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
        }}>
          {(project.collections || []).length} collections · {project.ingestion_pattern || 'utilitarian'}
        </div>
      </div>
      {active && (
        <span style={{
          fontSize: 6, fontFamily: MONO, padding: '1px 5px', borderRadius: 3,
          background: `${accent}20`, color: accent, letterSpacing: 1,
        }}>
          ACTIVE
        </span>
      )}
    </div>
  );
}
