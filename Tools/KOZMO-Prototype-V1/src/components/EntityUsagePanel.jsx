/**
 * EntityUsagePanel Component (Phase 5)
 *
 * Shows which scenes reference an entity.
 * Displays first/last appearance, total scenes, and scene list.
 */
import React, { useState, useEffect } from 'react';
import { useKozmo } from '../KozmoProvider';

export function EntityUsagePanel({ entitySlug }) {
  const { activeProject } = useKozmo();
  const [usage, setUsage] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!entitySlug || !activeProject) return;

    const fetchUsage = async () => {
      try {
        const response = await fetch(
          `/kozmo/projects/${activeProject.slug}/entities/${entitySlug}/usage`
        );

        if (response.ok) {
          const data = await response.json();
          setUsage(data);
        } else {
          console.error('Failed to fetch entity usage');
          setUsage(null);
        }
      } catch (err) {
        console.error('Failed to fetch entity usage:', err);
        setUsage(null);
      } finally {
        setLoading(false);
      }
    };

    fetchUsage();
  }, [entitySlug, activeProject]);

  if (loading) {
    return <div style={{ padding: 16, color: '#64748b', fontSize: 12 }}>Loading usage...</div>;
  }

  if (!usage || usage.status === 'not_implemented') {
    return (
      <div style={{ padding: 16, color: '#64748b', fontSize: 12 }}>
        Usage tracking not yet implemented.
        <div style={{ fontSize: 10, marginTop: 8, color: '#4a4a5a' }}>
          (Requires database integration)
        </div>
      </div>
    );
  }

  const navigateToScene = (sceneSlug) => {
    console.log('Navigate to scene:', sceneSlug);
    // TODO: Implement scene navigation
  };

  return (
    <div style={{ padding: 16 }}>
      <div style={{
        fontSize: 10,
        color: '#64748b',
        textTransform: 'uppercase',
        letterSpacing: '0.1em',
        marginBottom: 12
      }}>
        Appears In
      </div>

      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(3, 1fr)',
        gap: 12,
        marginBottom: 16
      }}>
        <div style={{
          padding: 12,
          background: 'rgba(96, 165, 250, 0.1)',
          borderRadius: 6,
          border: '1px solid rgba(96, 165, 250, 0.2)'
        }}>
          <div style={{ fontSize: 20, color: '#60a5fa', fontWeight: 600 }}>
            {usage.total_scenes || 0}
          </div>
          <div style={{ fontSize: 10, color: '#94a3b8', marginTop: 4 }}>
            Total Scenes
          </div>
        </div>

        <div style={{
          padding: 12,
          background: 'rgba(74, 222, 128, 0.1)',
          borderRadius: 6,
          border: '1px solid rgba(74, 222, 128, 0.2)'
        }}>
          <div style={{ fontSize: 12, color: '#4ade80', fontFamily: "'JetBrains Mono', monospace" }}>
            {usage.first_appearance || '—'}
          </div>
          <div style={{ fontSize: 10, color: '#94a3b8', marginTop: 4 }}>
            First Appearance
          </div>
        </div>

        <div style={{
          padding: 12,
          background: 'rgba(239, 68, 68, 0.1)',
          borderRadius: 6,
          border: '1px solid rgba(239, 68, 68, 0.2)'
        }}>
          <div style={{ fontSize: 12, color: '#ef4444', fontFamily: "'JetBrains Mono', monospace" }}>
            {usage.last_appearance || '—'}
          </div>
          <div style={{ fontSize: 10, color: '#94a3b8', marginTop: 4 }}>
            Last Appearance
          </div>
        </div>
      </div>

      <div style={{
        fontSize: 10,
        color: '#64748b',
        textTransform: 'uppercase',
        letterSpacing: '0.1em',
        marginBottom: 8
      }}>
        Scene List
      </div>

      <div style={{
        maxHeight: 300,
        overflowY: 'auto',
        border: '1px solid #2a2a3a',
        borderRadius: 6,
        background: 'rgba(10, 10, 15, 0.6)',
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)'
      }}>
        {!usage.scenes || usage.scenes.length === 0 ? (
          <div style={{ padding: 16, textAlign: 'center', color: '#4a4a5a', fontSize: 11 }}>
            No scene references found
          </div>
        ) : (
          usage.scenes.map((scene, index) => (
            <div
              key={`${scene.scene_slug}-${index}`}
              onClick={() => navigateToScene(scene.scene_slug)}
              style={{
                padding: '10px 12px',
                borderBottom: index < usage.scenes.length - 1 ? '1px solid #2a2a3a' : 'none',
                cursor: 'pointer',
                transition: 'background 0.15s'
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(96, 165, 250, 0.05)'; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
            >
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: 4
              }}>
                <span style={{
                  color: '#e2e8f0',
                  fontSize: 13,
                  fontFamily: "'Space Grotesk', sans-serif"
                }}>
                  {scene.scene_title}
                </span>
                <span style={{
                  color: '#64748b',
                  fontSize: 10,
                  fontFamily: "'JetBrains Mono', monospace"
                }}>
                  #{scene.scene_number}
                </span>
              </div>

              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <span style={{
                  fontSize: 9,
                  color: scene.reference_type === 'frontmatter' ? '#4ade80' : '#94a3b8',
                  padding: '2px 6px',
                  background: scene.reference_type === 'frontmatter' ? 'rgba(74, 222, 128, 0.1)' : 'rgba(100, 116, 139, 0.1)',
                  borderRadius: 3,
                  fontFamily: "'JetBrains Mono', monospace",
                  textTransform: 'uppercase'
                }}>
                  {scene.reference_type}
                </span>

                {scene.field && (
                  <span style={{
                    fontSize: 9,
                    color: '#64748b',
                    fontFamily: "'JetBrains Mono', monospace"
                  }}>
                    {scene.field}
                  </span>
                )}
              </div>

              {scene.context && (
                <div style={{
                  marginTop: 6,
                  fontSize: 11,
                  color: '#4a4a5a',
                  fontStyle: 'italic',
                  lineHeight: 1.4
                }}>
                  "{scene.context}"
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
