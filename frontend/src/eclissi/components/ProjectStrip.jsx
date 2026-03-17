import React, { useState, useEffect } from 'react';

export default function ProjectStrip({ onProjectChange }) {
  const [projects, setProjects] = useState([]);
  const [activeProject, setActiveProject] = useState(null);

  useEffect(() => {
    let id;
    const poll = async () => {
      try {
        const res = await fetch('/api/projects');
        if (!res.ok) return;
        const data = await res.json();
        setProjects(data.projects || []);
        const active = data.active || null;
        setActiveProject(active);
        onProjectChange?.(active);
      } catch {}
    };
    poll();
    id = setInterval(poll, 10000);
    return () => clearInterval(id);
  }, []);

  const toggle = async (slug) => {
    if (activeProject === slug) {
      await fetch('/project/deactivate', { method: 'POST' });
      setActiveProject(null);
      onProjectChange?.(null);
    } else {
      await fetch('/project/activate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ slug }),
      });
      setActiveProject(slug);
      onProjectChange?.(slug);
    }
  };

  if (projects.length === 0) return null;

  const activeInfo = projects.find(p => p.slug === activeProject);

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      gap: 4,
      padding: '6px 16px',
      borderBottom: '1px solid rgba(255,255,255,0.04)',
      flexShrink: 0,
    }}>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        {projects.map(p => {
          const isActive = activeProject === p.slug;
          const accent = p.accent || '#a78bfa';
          return (
            <button
              key={p.slug}
              onClick={() => toggle(p.slug)}
              style={{
                fontSize: 10,
                fontFamily: "'JetBrains Mono', monospace",
                padding: '4px 12px',
                borderRadius: 5,
                cursor: 'pointer',
                background: isActive ? `${accent}15` : 'rgba(255,255,255,0.03)',
                color: isActive ? accent : '#555',
                border: `1px solid ${isActive ? accent + '33' : 'rgba(255,255,255,0.06)'}`,
                transition: 'all 0.2s ease',
              }}
            >
              {p.icon || '\u25C8'} {p.name || p.slug}
            </button>
          );
        })}
      </div>
      {activeInfo && (
        <div style={{
          fontSize: 9,
          fontFamily: "'JetBrains Mono', monospace",
          color: activeInfo.accent || '#a78bfa',
          opacity: 0.6,
        }}>
          Focused on {activeInfo.name || activeInfo.slug}
          {activeInfo.collections?.length > 0
            ? ` \u2014 ${activeInfo.collections.join(' + ')}`
            : ''}
        </div>
      )}
    </div>
  );
}
