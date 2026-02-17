/**
 * ProjectSettings — Slide-over drawer for project configuration
 *
 * Media sync path, camera defaults, aspect ratio.
 * Wired to PUT /kozmo/projects/{slug}/settings.
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useKozmo } from '../KozmoProvider';
import { useSettingsAPI } from '../hooks/useSettingsAPI';
import { CAMERA_BODIES, LENS_PROFILES, FILM_STOCKS } from '../config/cameras';

const ASPECT_RATIOS = ['16:9', '21:9', '2.39:1', '4:3'];

export default function ProjectSettings({ onClose }) {
  const { activeProject } = useKozmo();
  const { getSettings, updateSettings, loading, error } = useSettingsAPI();

  const current = getSettings();
  const [syncPath, setSyncPath] = useState(current.media_sync_path || '');
  const [camera, setCamera] = useState(current.default_camera || 'arri_alexa35');
  const [lens, setLens] = useState(current.default_lens || 'cooke_s7i');
  const [stock, setStock] = useState(current.default_film_stock || 'kodak_5219');
  const [aspect, setAspect] = useState(current.aspect_ratio || '21:9');
  const [saved, setSaved] = useState(false);

  // Sync with provider when project reloads
  useEffect(() => {
    const s = getSettings();
    setSyncPath(s.media_sync_path || '');
    setCamera(s.default_camera || 'arri_alexa35');
    setLens(s.default_lens || 'cooke_s7i');
    setStock(s.default_film_stock || 'kodak_5219');
    setAspect(s.aspect_ratio || '21:9');
  }, [activeProject?.slug]);

  const handleSave = useCallback(async () => {
    setSaved(false);
    const result = await updateSettings({
      media_sync_path: syncPath || null,
      default_camera: camera,
      default_lens: lens,
      default_film_stock: stock,
      aspect_ratio: aspect,
    });
    if (result) setSaved(true);
  }, [syncPath, camera, lens, stock, aspect, updateSettings]);

  const selectStyle = {
    width: '100%', padding: '6px 8px', borderRadius: 4,
    background: '#0a0a14', border: '1px solid #1a1a2e',
    color: '#e2e8f0', fontSize: 10, fontFamily: "'JetBrains Mono', monospace",
    outline: 'none', cursor: 'pointer',
  };

  return (
    <div style={{
      position: 'fixed', top: 0, right: 0, bottom: 0, left: 0, zIndex: 1000,
      display: 'flex', justifyContent: 'flex-end',
    }}>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: 'absolute', inset: 0,
          background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(4px)',
        }}
      />

      {/* Drawer */}
      <div style={{
        position: 'relative', width: 380, height: '100%', overflowY: 'auto',
        background: 'rgba(16, 16, 26, 0.95)', borderLeft: '1px solid #1e1e30',
        backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)',
      }}>
        {/* Header */}
        <div style={{
          padding: '16px 16px 12px', borderBottom: '1px solid #1e1e30',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <div>
            <div style={{ fontSize: 12, fontWeight: 700, color: '#e2e8f0' }}>
              Project Settings
            </div>
            <div style={{
              fontSize: 9, color: '#4a4a6a', fontFamily: "'JetBrains Mono', monospace",
              marginTop: 2,
            }}>
              {activeProject?.name || 'No project'}
            </div>
          </div>
          <button onClick={onClose} style={{
            background: 'transparent', border: 'none', color: '#5a5a72',
            fontSize: 16, cursor: 'pointer', padding: '4px 8px',
          }}>x</button>
        </div>

        <div style={{ padding: 16 }}>
          {/* Media Sync Path */}
          <div style={{ marginBottom: 20 }}>
            <label style={{
              display: 'block', fontSize: 9, color: '#c8ff00', fontWeight: 700,
              marginBottom: 6, fontFamily: "'JetBrains Mono', monospace",
            }}>
              MEDIA SYNC PATH
            </label>
            <div style={{ fontSize: 9, color: '#4a4a6a', marginBottom: 8 }}>
              Generated assets will be copied to this external directory with meaningful filenames.
            </div>
            <input
              value={syncPath}
              onChange={e => setSyncPath(e.target.value)}
              placeholder="/path/to/media/directory"
              style={{
                width: '100%', padding: '8px 10px', borderRadius: 4,
                background: '#0a0a14', border: '1px solid #1a1a2e',
                color: '#e2e8f0', fontSize: 11, fontFamily: "'JetBrains Mono', monospace",
                outline: 'none', boxSizing: 'border-box',
              }}
              onFocus={e => e.target.style.borderColor = '#c8ff0030'}
              onBlur={e => e.target.style.borderColor = '#1a1a2e'}
            />
            {current.media_sync_path && (
              <div style={{
                marginTop: 6, fontSize: 9, color: '#4ade80',
                fontFamily: "'JetBrains Mono', monospace",
              }}>
                + Sync active -> {current.media_sync_path}
              </div>
            )}
          </div>

          {/* Camera Defaults */}
          <div style={{
            display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 20,
          }}>
            <div>
              <div style={{
                fontSize: 8, color: '#4a4a6a', fontWeight: 700, marginBottom: 4,
                fontFamily: "'JetBrains Mono', monospace",
              }}>DEFAULT CAMERA</div>
              <select value={camera} onChange={e => setCamera(e.target.value)} style={selectStyle}>
                {CAMERA_BODIES.map(c => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </div>
            <div>
              <div style={{
                fontSize: 8, color: '#4a4a6a', fontWeight: 700, marginBottom: 4,
                fontFamily: "'JetBrains Mono', monospace",
              }}>DEFAULT LENS</div>
              <select value={lens} onChange={e => setLens(e.target.value)} style={selectStyle}>
                {LENS_PROFILES.map(l => (
                  <option key={l.id} value={l.id}>{l.name}</option>
                ))}
              </select>
            </div>
            <div>
              <div style={{
                fontSize: 8, color: '#4a4a6a', fontWeight: 700, marginBottom: 4,
                fontFamily: "'JetBrains Mono', monospace",
              }}>FILM STOCK</div>
              <select value={stock} onChange={e => setStock(e.target.value)} style={selectStyle}>
                {FILM_STOCKS.map(s => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
            </div>
            <div>
              <div style={{
                fontSize: 8, color: '#4a4a6a', fontWeight: 700, marginBottom: 4,
                fontFamily: "'JetBrains Mono', monospace",
              }}>ASPECT RATIO</div>
              <select value={aspect} onChange={e => setAspect(e.target.value)} style={selectStyle}>
                {ASPECT_RATIOS.map(r => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Save */}
          <button onClick={handleSave} disabled={loading} style={{
            width: '100%', padding: '10px 0', borderRadius: 4,
            border: '1px solid rgba(200,255,0,0.3)',
            background: 'rgba(200,255,0,0.08)', color: '#c8ff00',
            fontSize: 11, fontWeight: 600, cursor: loading ? 'wait' : 'pointer',
            fontFamily: "'JetBrains Mono', monospace",
            opacity: loading ? 0.6 : 1,
          }}>
            {loading ? 'Saving...' : saved ? '+ Saved' : 'Save Settings'}
          </button>

          {error && (
            <div style={{ marginTop: 8, fontSize: 9, color: '#f87171' }}>
              Error: {error}
            </div>
          )}

          {/* Sync behavior explanation */}
          <div style={{
            marginTop: 20, padding: 10, borderRadius: 4,
            background: 'rgba(200,255,0,0.03)', border: '1px solid rgba(200,255,0,0.1)',
          }}>
            <div style={{
              fontSize: 9, color: '#c8ff00', fontWeight: 700, marginBottom: 6,
              fontFamily: "'JetBrains Mono', monospace",
            }}>
              SYNC BEHAVIOR
            </div>
            <div style={{ fontSize: 10, color: '#94a3b8', lineHeight: 1.5 }}>
              When Eden generates an image and <code style={{ color: '#c8ff00', fontSize: 9 }}>media_sync_path</code> is set:
            </div>
            <div style={{ marginTop: 6, fontSize: 10, color: '#64748b', lineHeight: 1.6 }}>
              1. Saved to <code style={{ color: '#818cf8', fontSize: 9 }}>lab/assets/{'{'}_id{'}'}.png</code><br />
              2. Registered in <code style={{ color: '#818cf8', fontSize: 9 }}>media_library.yaml</code><br />
              3. Copied to sync path as <code style={{ color: '#818cf8', fontSize: 9 }}>{'{'}_scene{'}'}_{'{'}_id{'}'}.png</code>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
