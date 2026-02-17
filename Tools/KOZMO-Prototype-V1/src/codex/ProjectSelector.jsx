/**
 * ProjectSelector — Landing screen when no project is loaded
 *
 * Shows existing projects or a create form.
 * Wired to /kozmo/projects API via KozmoProvider.
 */
import React, { useState } from 'react';
import { useKozmo } from '../KozmoProvider';

export default function ProjectSelector() {
  const { projects, createProject, loadProject, deleteProject, engineConnected, loading } = useKozmo();
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [confirmDelete, setConfirmDelete] = useState(null);

  const handleCreate = async () => {
    if (!newName.trim()) return;
    const result = await createProject(newName.trim());
    if (result) {
      await loadProject(result.slug);
      setNewName('');
      setShowCreate(false);
    }
  };

  const handleDelete = async (slug) => {
    await deleteProject(slug);
    setConfirmDelete(null);
  };

  if (!engineConnected) {
    return (
      <div style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        height: '100%', gap: 16,
      }}>
        <div style={{
          width: 48, height: 48, borderRadius: '50%', border: '2px solid #f8717140',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <div style={{ width: 12, height: 12, borderRadius: '50%', background: '#f87171', animation: 'pulse 2s infinite' }} />
        </div>
        <div style={{ fontSize: 12, color: '#6b6b80' }}>Waiting for Luna Engine...</div>
        <div style={{ fontSize: 9, color: '#3a3a50' }}>Start the engine on port 8200</div>
      </div>
    );
  }

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      height: '100%', gap: 24,
    }}>
      <div style={{ textAlign: 'center', marginBottom: 8 }}>
        <div style={{ fontSize: 10, letterSpacing: 4, color: '#c8ff00', fontWeight: 800, marginBottom: 8 }}>KOZMO</div>
        <div style={{ fontSize: 14, color: '#9ca3af', fontWeight: 300 }}>Select a project or create one</div>
      </div>

      {/* Project List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, width: 360 }}>
        {projects.map(p => (
          <div key={p.slug} style={{
            display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px',
            background: '#0a0a14', borderRadius: 6, border: '1px solid #1a1a24',
            cursor: 'pointer', transition: 'all 0.15s',
          }}
            onMouseEnter={e => { e.currentTarget.style.borderColor = '#c8ff0030'; e.currentTarget.style.background = '#0d0d18'; }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = '#1a1a24'; e.currentTarget.style.background = '#0a0a14'; }}
            onClick={() => loadProject(p.slug)}>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 13, color: '#e8e8f0', fontWeight: 500 }}>{p.name}</div>
              <div style={{ fontSize: 9, color: '#3a3a50', marginTop: 2 }}>
                {p.slug} · v{p.version || '0.1.0'}
                {p.entity_types && ` · ${p.entity_types.length} entity types`}
              </div>
            </div>
            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              {confirmDelete === p.slug ? (
                <>
                  <button onClick={(e) => { e.stopPropagation(); handleDelete(p.slug); }}
                    style={{
                      padding: '4px 10px', borderRadius: 4, border: '1px solid #f8717140',
                      background: '#1a0a0a', color: '#f87171', fontSize: 9, cursor: 'pointer', fontFamily: 'inherit',
                    }}>delete</button>
                  <button onClick={(e) => { e.stopPropagation(); setConfirmDelete(null); }}
                    style={{
                      padding: '4px 8px', borderRadius: 4, border: 'none',
                      background: 'transparent', color: '#3a3a50', fontSize: 9, cursor: 'pointer', fontFamily: 'inherit',
                    }}>cancel</button>
                </>
              ) : (
                <button onClick={(e) => { e.stopPropagation(); setConfirmDelete(p.slug); }}
                  style={{
                    padding: '4px 8px', borderRadius: 4, border: 'none',
                    background: 'transparent', color: '#2a2a3a', fontSize: 9, cursor: 'pointer', fontFamily: 'inherit',
                  }}
                  onMouseEnter={e => e.currentTarget.style.color = '#f87171'}
                  onMouseLeave={e => e.currentTarget.style.color = '#2a2a3a'}>
                  ×
                </button>
              )}
            </div>
          </div>
        ))}

        {projects.length === 0 && !showCreate && (
          <div style={{ textAlign: 'center', padding: 20, color: '#2a2a3a', fontSize: 10 }}>
            No projects yet
          </div>
        )}
      </div>

      {/* Create Form */}
      {showCreate ? (
        <div style={{
          display: 'flex', gap: 8, width: 360,
        }}>
          <input
            value={newName}
            onChange={e => setNewName(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleCreate()}
            placeholder="Project name..."
            autoFocus
            style={{
              flex: 1, padding: '8px 12px', background: '#0d0d18',
              border: '1px solid #c8ff0030', borderRadius: 4, color: '#c8cad0',
              fontFamily: 'inherit', fontSize: 11, outline: 'none',
            }}
          />
          <button onClick={handleCreate} disabled={loading || !newName.trim()}
            style={{
              padding: '8px 16px', borderRadius: 4, border: 'none',
              background: newName.trim() ? '#c8ff00' : '#1a1a24',
              color: newName.trim() ? '#08080e' : '#3a3a50',
              fontWeight: 700, fontSize: 10, cursor: newName.trim() ? 'pointer' : 'not-allowed',
              fontFamily: 'inherit',
            }}>
            {loading ? '...' : 'CREATE'}
          </button>
          <button onClick={() => { setShowCreate(false); setNewName(''); }}
            style={{
              padding: '8px 12px', borderRadius: 4, border: '1px solid #1a1a24',
              background: 'transparent', color: '#3a3a50', fontSize: 10,
              cursor: 'pointer', fontFamily: 'inherit',
            }}>
            cancel
          </button>
        </div>
      ) : (
        <button onClick={() => setShowCreate(true)}
          style={{
            padding: '10px 24px', borderRadius: 6, border: '1px dashed #c8ff0040',
            background: 'transparent', color: '#c8ff00', fontSize: 11,
            cursor: 'pointer', fontFamily: 'inherit', letterSpacing: 1,
            transition: 'all 0.15s',
          }}
          onMouseEnter={e => { e.currentTarget.style.background = '#c8ff0008'; e.currentTarget.style.borderColor = '#c8ff0060'; }}
          onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.borderColor = '#c8ff0040'; }}>
          + New Project
        </button>
      )}
    </div>
  );
}
