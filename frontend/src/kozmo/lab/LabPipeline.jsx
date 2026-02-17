/**
 * LAB Pipeline — Production Brief Queue + Camera Rig Builder
 *
 * Queue of production briefs from SCRIBO → camera rigging → prompt enrichment → Eden.
 * Ported from prototype: ClaudeArtifacts/files 3/lab_pipeline.jsx
 * Wired to real API via useLabAPI hook.
 */
import React, { useState, useCallback, useMemo, useEffect } from 'react';
import { useKozmo } from '../KozmoProvider';
import { useLabAPI } from '../hooks/useLabAPI';
import {
  CAMERA_BODIES, LENS_PROFILES, CAMERA_MOVEMENTS, FILM_STOCKS,
  buildCameraPrompt,
} from '../config/cameras';
import { heroUrl } from '../utils/heroUrl';

// --- Status Config ---
const STATUS_CONFIG = {
  planning: { color: '#64748b', label: 'Planning', icon: '○' },
  rigging: { color: '#fbbf24', label: 'Rigging', icon: '◎' },
  queued: { color: '#c084fc', label: 'Queued', icon: '◉' },
  generating: { color: '#34d399', label: 'Generating', icon: '⟳' },
  review: { color: '#38bdf8', label: 'Review', icon: '◈' },
  approved: { color: '#4ade80', label: 'Approved', icon: '✓' },
  locked: { color: '#4ade80', label: 'Locked', icon: '◆' },
};

const PRIORITY_CONFIG = {
  critical: { color: '#f87171', label: 'Critical' },
  high: { color: '#fb923c', label: 'High' },
  medium: { color: '#fbbf24', label: 'Medium' },
  low: { color: '#64748b', label: 'Low' },
};

const MOVEMENT_ICONS = {
  static: '◻', dolly_in: '→◎', dolly_out: '◎→',
  pan_left: '←', pan_right: '→', tilt_up: '↑', tilt_down: '↓',
  crane_up: '⤴', crane_down: '⤵', orbit_cw: '↻', orbit_ccw: '↺',
  handheld: '〰', steadicam: '≋',
};

// --- Brief Card ---
// Voice entity colors for audio source badges
const VOICE_COLORS = {
  bella: '#c8ff00', george: '#818cf8', gandala: '#22c55e',
  lily: '#f472b6', liam: '#fb923c', mohammed: '#38bdf8',
  lucy: '#a78bfa', chebel: '#fbbf24', maria_clara: '#f97316',
  miyomi: '#67e8f9', maggi: '#e879f9',
};

function BriefCard({ brief, isSelected, onClick, audioTrack }) {
  const st = STATUS_CONFIG[brief.status] || STATUS_CONFIG.planning;
  const pr = PRIORITY_CONFIG[brief.priority] || PRIORITY_CONFIG.medium;

  return (
    <div onClick={onClick} style={{
      background: isSelected ? '#16162a' : '#0f0f18',
      border: `1px solid ${isSelected ? '#818cf840' : '#1a1a24'}`,
      borderRadius: 6, padding: 10, cursor: 'pointer', transition: 'all 0.15s',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 4 }}>
        <div style={{ fontSize: 11, color: '#e2e8f0', fontWeight: 500, lineHeight: 1.3, flex: 1 }}>
          {brief.title}
        </div>
        <span style={{
          fontSize: 7, padding: '2px 6px', borderRadius: 3, fontWeight: 700,
          background: st.color + '15', color: st.color, letterSpacing: 1,
          marginLeft: 6, whiteSpace: 'nowrap',
        }}>{st.label.toUpperCase()}</span>
      </div>
      <div style={{ display: 'flex', gap: 6, fontSize: 9, color: '#4a4a5a', alignItems: 'center' }}>
        <span style={{
          padding: '1px 4px', borderRadius: 2,
          background: pr.color + '15', color: pr.color,
          fontSize: 7, fontWeight: 600,
        }}>{pr.label}</span>
        <span>{brief.type}</span>
        {brief.assignee && <span style={{ color: '#34d399' }}>→ {brief.assignee}</span>}
        {brief.shots?.length > 0 && <span>{brief.shots.length} shots</span>}
      </div>
      {/* Audio source mapping */}
      {audioTrack && (
        <div style={{
          marginTop: 6, display: 'flex', gap: 4, alignItems: 'center',
          fontSize: 7, color: '#4a4a5a',
        }}>
          <span style={{
            width: 6, height: 6, borderRadius: '50%',
            background: VOICE_COLORS[audioTrack.voice] || '#5a5a72',
            flexShrink: 0,
          }} />
          <span style={{
            color: VOICE_COLORS[audioTrack.voice] || '#5a5a72',
            fontWeight: 700, letterSpacing: 1, textTransform: 'uppercase',
          }}>{audioTrack.voice || '?'}</span>
          <span style={{ color: '#2a2a3a' }}>·</span>
          <span>{audioTrack.start_time?.toFixed(1)}s — {audioTrack.end_time?.toFixed(1)}s</span>
        </div>
      )}
      {brief.status === 'generating' && brief.progress != null && (
        <div style={{ marginTop: 6, height: 3, borderRadius: 2, background: '#1a1a24', overflow: 'hidden' }}>
          <div style={{ width: `${brief.progress}%`, height: '100%', background: '#34d399', transition: 'width 0.5s ease' }} />
        </div>
      )}
    </div>
  );
}

// --- Camera Rig Panel ---
function CameraRigPanel({ camera, post, onCameraChange, onPostChange }) {
  const cam = camera || { body: 'arri_alexa35', lens: 'cooke_s7i', focal: 50, aperture: 2.8, movement: ['static'], duration: 3 };
  const postCfg = post || { stock: 'none', color_temp: 5600, grain: 0, bloom: 0, halation: 0 };

  const updateCam = (field, value) => onCameraChange({ ...cam, [field]: value });
  const updatePost = (field, value) => onPostChange({ ...postCfg, [field]: value });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Camera Body */}
      <div>
        <div style={{ fontSize: 8, color: '#3a3a50', letterSpacing: 2, marginBottom: 6 }}>CAMERA BODY</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {CAMERA_BODIES.map(c => (
            <button key={c.id} onClick={() => updateCam('body', c.id)} style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              padding: '5px 8px', borderRadius: 4, border: 'none',
              background: cam.body === c.id ? '#16162a' : 'transparent',
              cursor: 'pointer', fontFamily: 'inherit',
            }}>
              <span style={{ fontSize: 10, color: cam.body === c.id ? '#e8e8f0' : '#6b6b80' }}>{c.name}</span>
              <span style={{ fontSize: 7, color: cam.body === c.id ? '#c8ff00' : '#3a3a50', letterSpacing: 1 }}>{c.badge}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Lens */}
      <div>
        <div style={{ fontSize: 8, color: '#3a3a50', letterSpacing: 2, marginBottom: 6 }}>LENS</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {LENS_PROFILES.map(l => (
            <button key={l.id} onClick={() => updateCam('lens', l.id)} style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              padding: '5px 8px', borderRadius: 4, border: 'none',
              background: cam.lens === l.id ? '#16162a' : 'transparent',
              cursor: 'pointer', fontFamily: 'inherit', textAlign: 'left',
            }}>
              <div>
                <div style={{ fontSize: 10, color: cam.lens === l.id ? '#e8e8f0' : '#6b6b80' }}>{l.name}</div>
                <div style={{ fontSize: 7, color: '#3a3a50' }}>{l.character}</div>
              </div>
              <span style={{ fontSize: 7, color: l.type === 'anamorphic' ? '#f59e0b' : '#4a4a60' }}>
                {l.type === 'anamorphic' ? 'ANA' : 'SPH'}
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* Focal & Aperture */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        <div>
          <div style={{ fontSize: 8, color: '#3a3a50', letterSpacing: 2, marginBottom: 4 }}>FOCAL</div>
          <input type="range" min={12} max={200} value={cam.focal} onChange={e => updateCam('focal', parseInt(e.target.value))}
            style={{ width: '100%', accentColor: '#818cf8' }} />
          <div style={{ fontSize: 10, color: '#e8e8f0', textAlign: 'center' }}>{cam.focal}mm</div>
        </div>
        <div>
          <div style={{ fontSize: 8, color: '#3a3a50', letterSpacing: 2, marginBottom: 4 }}>APERTURE</div>
          <input type="range" min={14} max={220} value={cam.aperture * 10} onChange={e => updateCam('aperture', parseInt(e.target.value) / 10)}
            style={{ width: '100%', accentColor: '#818cf8' }} />
          <div style={{ fontSize: 10, color: '#e8e8f0', textAlign: 'center' }}>f/{cam.aperture}</div>
        </div>
      </div>

      {/* Movements */}
      <div>
        <div style={{ fontSize: 8, color: '#3a3a50', letterSpacing: 2, marginBottom: 6 }}>MOVEMENT <span style={{ color: '#2a2a3a' }}>· max 3</span></div>
        <div style={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
          {CAMERA_MOVEMENTS.map(m => {
            const isActive = cam.movement?.includes(m.id);
            return (
              <button key={m.id} onClick={() => {
                const current = cam.movement || [];
                if (current.includes(m.id)) updateCam('movement', current.filter(x => x !== m.id));
                else if (current.length < 3) updateCam('movement', [...current, m.id]);
              }} style={{
                padding: '3px 8px', fontSize: 9, borderRadius: 4,
                border: `1px solid ${isActive ? '#818cf8' : '#2a2a3a'}`,
                background: isActive ? 'rgba(129, 140, 248, 0.08)' : 'transparent',
                color: isActive ? '#818cf8' : '#6b6b80',
                cursor: 'pointer', fontFamily: 'inherit',
              }}>
                {MOVEMENT_ICONS[m.id] || ''} {m.name}
              </button>
            );
          })}
        </div>
      </div>

      {/* Film Stock */}
      <div>
        <div style={{ fontSize: 8, color: '#3a3a50', letterSpacing: 2, marginBottom: 6 }}>FILM STOCK</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <button onClick={() => updatePost('stock', 'none')} style={{
            padding: '5px 8px', borderRadius: 4, border: 'none',
            background: postCfg.stock === 'none' ? '#16162a' : 'transparent',
            cursor: 'pointer', fontFamily: 'inherit', textAlign: 'left',
            fontSize: 10, color: postCfg.stock === 'none' ? '#e8e8f0' : '#6b6b80',
          }}>Digital (None)</button>
          {FILM_STOCKS.map(f => (
            <button key={f.id} onClick={() => updatePost('stock', f.id)} style={{
              padding: '5px 8px', borderRadius: 4, border: 'none',
              background: postCfg.stock === f.id ? '#16162a' : 'transparent',
              cursor: 'pointer', fontFamily: 'inherit', textAlign: 'left',
            }}>
              <div style={{ fontSize: 10, color: postCfg.stock === f.id ? '#e8e8f0' : '#6b6b80' }}>{f.name}</div>
              <div style={{ fontSize: 7, color: '#3a3a50' }}>{f.character}</div>
            </button>
          ))}
        </div>
      </div>

      {/* Post sliders */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        {[
          { key: 'grain', label: 'Grain', max: 30, color: '#6b6b80' },
          { key: 'bloom', label: 'Bloom', max: 30, color: '#fbbf24' },
          { key: 'halation', label: 'Halation', max: 20, color: '#f472b6' },
        ].map(s => (
          <div key={s.key}>
            <div style={{ fontSize: 8, color: '#3a3a50', letterSpacing: 2, marginBottom: 4 }}>{s.label.toUpperCase()}</div>
            <input type="range" min={0} max={s.max} value={postCfg[s.key]} onChange={e => updatePost(s.key, parseInt(e.target.value))}
              style={{ width: '100%', accentColor: s.color }} />
            <div style={{ fontSize: 9, color: '#6b6b80', textAlign: 'center' }}>{postCfg[s.key]}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// --- Sequence Storyboard ---
function SequenceStoryboard({ shots, selectedShot, onSelectShot, projectSlug }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
      {(shots || []).map(shot => {
        const st = STATUS_CONFIG[shot.status] || STATUS_CONFIG.planning;
        return (
          <div
            key={shot.id}
            onClick={() => onSelectShot(shot.id)}
            style={{
              background: selectedShot === shot.id ? '#16162a' : '#0f0f18',
              border: `1px solid ${selectedShot === shot.id ? '#818cf840' : '#1a1a24'}`,
              borderRadius: 6, padding: 8, cursor: 'pointer', transition: 'all 0.15s',
            }}
          >
            <div style={{ aspectRatio: '21/9', borderRadius: 4, background: '#0a0a14', marginBottom: 6, display: 'flex', alignItems: 'center', justifyContent: 'center', border: '1px solid #1a1a24' }}>
              {shot.hero_frame ? (
                <img src={heroUrl(shot.hero_frame, projectSlug)} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: 3 }} />
              ) : (
                <span style={{ fontSize: 8, color: '#2a2a3a' }}>◎</span>
              )}
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 10, color: '#e2e8f0', fontWeight: 500 }}>{shot.title}</span>
              <span style={{ fontSize: 7, color: st.color }}>{st.icon}</span>
            </div>
            <div style={{ fontSize: 9, color: '#4a4a5a', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {shot.prompt}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ============================================================================
// Main LAB Pipeline
// ============================================================================

export default function LabPipeline({ audioTracks = [], onSelectAudioTrack }) {
  const { activeProject } = useKozmo();
  const projectSlug = activeProject?.slug;
  const api = useLabAPI();
  const [briefs, setBriefs] = useState([]);
  const [selectedBrief, setSelectedBrief] = useState(null);
  const [selectedShot, setSelectedShot] = useState(null);
  const [statusFilter, setStatusFilter] = useState('all');
  const [enrichedPrompt, setEnrichedPrompt] = useState('');
  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState(null);

  // Local camera/post state for editing
  const [camera, setCamera] = useState(null);
  const [post, setPost] = useState(null);

  // Refresh briefs from API
  const refreshBriefs = useCallback(() => {
    if (!projectSlug) return;
    api.listBriefs().then(data => {
      if (Array.isArray(data)) setBriefs(data);
    });
  }, [projectSlug, api]);

  // Load briefs when project is available
  useEffect(() => {
    if (!projectSlug) return;
    api.listBriefs().then(data => {
      if (Array.isArray(data)) setBriefs(data);
    });
  }, [projectSlug]); // eslint-disable-line react-hooks/exhaustive-deps

  const brief = briefs.find(b => b.id === selectedBrief);

  // Sync local camera/post when brief changes
  useEffect(() => {
    if (brief) {
      setCamera(brief.camera || { body: 'arri_alexa35', lens: 'cooke_s7i', focal: 50, aperture: 2.8, movement: ['static'], duration: 3 });
      setPost(brief.post || { stock: 'none', color_temp: 5600, grain: 0, bloom: 0, halation: 0 });
      setSelectedShot(null);
      setEnrichedPrompt('');
    }
  }, [selectedBrief]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSaveRig = useCallback(async () => {
    if (!brief) return;
    const updated = await api.applyRig(brief.id, camera, post);
    if (updated) setBriefs(prev => prev.map(b => b.id === brief.id ? updated : b));
  }, [api, brief, camera, post]);

  const handlePreviewPrompt = useCallback(async () => {
    if (!brief) return;
    const result = await api.previewPrompt(brief.id, selectedShot);
    if (result?.enriched_prompt) setEnrichedPrompt(result.enriched_prompt);
  }, [api, brief, selectedShot]);

  // Generate via Eden — dispatches the selected brief to Eden and polls for result
  const handleGenerateEden = useCallback(async () => {
    if (!brief || generating) return;
    if (!projectSlug) {
      setGenError('No project selected. Open a project first.');
      return;
    }
    setGenerating(true);
    setGenError(null);

    try {
      // Save rig first if camera/post are set
      if (camera) {
        await api.applyRig(brief.id, camera, post);
      }

      // Dispatch to Eden
      const genRes = await fetch(
        `/kozmo/projects/${projectSlug}/lab/briefs/${brief.id}/generate`,
        { method: 'POST' }
      );
      if (!genRes.ok) {
        const errData = await genRes.json().catch(() => ({}));
        throw new Error(errData.detail || `Eden dispatch returned ${genRes.status}`);
      }
      const genData = await genRes.json();

      // Update status to generating
      setBriefs(prev => prev.map(b =>
        b.id === brief.id ? { ...b, status: 'generating', eden_task_id: genData.task_id } : b
      ));

      // Poll for result
      let attempts = 0;
      while (attempts < 60) {
        await new Promise(r => setTimeout(r, 3000));
        attempts++;
        try {
          const statusRes = await fetch(
            `/kozmo/projects/${projectSlug}/lab/briefs/${brief.id}/generation-status`
          );
          if (!statusRes.ok) continue;
          const status = await statusRes.json();

          if (status.is_complete) {
            setBriefs(prev => prev.map(b =>
              b.id === brief.id ? {
                ...b,
                status: 'review',
                hero_frame: status.image_url || status.local_path,
              } : b
            ));
            return;
          }
          if (status.status === 'failed') {
            throw new Error(status.error || 'Generation failed');
          }
        } catch (e) {
          if (e.message && e.message !== 'Generation failed') continue;
          throw e;
        }
      }
      throw new Error('Generation timed out');
    } catch (e) {
      setGenError(e.message);
      setBriefs(prev => prev.map(b =>
        b.id === brief.id ? { ...b, status: 'rigging' } : b
      ));
    } finally {
      setGenerating(false);
    }
  }, [api, brief, camera, post, generating, projectSlug]);

  const filteredBriefs = statusFilter === 'all' ? briefs : briefs.filter(b => b.status === statusFilter);

  // Build audio track lookup by document_slug for brief-to-clip mapping
  const audioTrackMap = useMemo(() => {
    const map = {};
    for (const t of audioTracks) {
      if (t.document_slug) map[t.document_slug] = t;
    }
    return map;
  }, [audioTracks]);

  // Find unmapped audio clips (no brief exists with this source_scene)
  const unmappedAudio = useMemo(() => {
    const mappedSlugs = new Set(briefs.map(b => b.source_scene).filter(Boolean));
    return audioTracks.filter(t => t.document_slug && !mappedSlugs.has(t.document_slug));
  }, [audioTracks, briefs]);

  const stats = useMemo(() => ({
    total: briefs.length,
    shots: briefs.reduce((n, b) => n + (b.type === 'sequence' ? (b.shots?.length || 0) : 1), 0),
    generating: briefs.filter(b => b.status === 'generating').length,
    rigging: briefs.filter(b => b.status === 'rigging').length,
  }), [briefs]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Top Bar */}
      <div style={{
        display: 'flex', alignItems: 'center', height: 36, padding: '0 16px',
        borderBottom: '1px solid #141420', background: 'rgba(10, 10, 18, 0.4)',
        backdropFilter: 'blur(20px)', flexShrink: 0,
      }}>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', fontSize: 8, color: '#3a3a50', letterSpacing: 2 }}>
          <span>{stats.total} BRIEFS</span>
          <span>·</span>
          <span>{stats.shots} SHOTS</span>
          {stats.generating > 0 && <><span>·</span><span style={{ color: '#34d399' }}>{stats.generating} GENERATING</span></>}
          {stats.rigging > 0 && <><span>·</span><span style={{ color: '#fbbf24' }}>{stats.rigging} RIGGING</span></>}
          {unmappedAudio.length > 0 && <><span>·</span><span style={{ color: '#22c55e' }}>{unmappedAudio.length} UNMAPPED</span></>}
        </div>
        {unmappedAudio.length > 0 && (
          <button onClick={async () => {
            // Bulk create briefs from all unmapped audio clips
            for (const track of unmappedAudio) {
              const brief = await api.createBrief({
                type: 'single',
                title: track.document_slug
                  ? `Script: ${track.document_slug.replace(/^sc_\d+_/, '').replace(/_/g, ' ')}`
                  : `Audio: ${track.filename || 'clip'}`,
                prompt: track.visual_prompt || `Scene from ${track.document_slug || track.filename}`,
                source_scene: track.document_slug || null,
                characters: track.voice ? [track.voice] : [],
                tags: ['from-script'],
              });
              if (brief?.id) setBriefs(prev => [...prev, brief]);
            }
            refreshBriefs();
          }} style={{
            padding: '3px 10px', borderRadius: 4, border: '1px solid #22c55e40',
            background: 'rgba(34, 197, 94, 0.08)', color: '#22c55e',
            fontSize: 8, cursor: 'pointer', fontFamily: 'inherit', fontWeight: 600,
            letterSpacing: 1,
          }}>
            + MAP ALL CLIPS
          </button>
        )}
      </div>

      {/* API error banner */}
      {api.error && (
        <div style={{
          padding: '6px 16px', background: '#1a0a0a',
          borderBottom: '1px solid #f8717130', fontSize: 9, color: '#f87171',
        }}>
          API Error: {api.error}
        </div>
      )}

      {/* Main */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        {/* Queue (Left) */}
        <div style={{
          width: 300, borderRight: '1px solid #141420', background: 'rgba(10, 10, 16, 0.4)',
          display: 'flex', flexDirection: 'column', flexShrink: 0,
        }}>
          {/* Status Filter */}
          <div style={{ padding: '8px 10px', borderBottom: '1px solid #141420', display: 'flex', gap: 3, flexWrap: 'wrap' }}>
            <button onClick={() => setStatusFilter('all')} style={{
              padding: '3px 8px', borderRadius: 3, border: 'none', fontSize: 9,
              background: statusFilter === 'all' ? 'rgba(255,255,255,0.06)' : 'transparent',
              color: statusFilter === 'all' ? '#e2e8f0' : '#4a4a5a', cursor: 'pointer',
            }}>All</button>
            {Object.entries(STATUS_CONFIG).map(([id, cfg]) => (
              <button key={id} onClick={() => setStatusFilter(id)} style={{
                padding: '3px 8px', borderRadius: 3, border: 'none', fontSize: 9,
                background: statusFilter === id ? cfg.color + '15' : 'transparent',
                color: statusFilter === id ? cfg.color : '#4a4a5a', cursor: 'pointer',
              }}>{cfg.icon} {cfg.label}</button>
            ))}
          </div>

          {/* Brief List */}
          <div style={{ flex: 1, overflow: 'auto', padding: 8, display: 'flex', flexDirection: 'column', gap: 4 }}>
            {filteredBriefs.length === 0 && unmappedAudio.length === 0 ? (
              <div style={{ color: '#2a2a3a', fontSize: 11, textAlign: 'center', paddingTop: 40 }}>No briefs yet</div>
            ) : filteredBriefs.map(b => (
              <BriefCard
                key={b.id} brief={b}
                isSelected={b.id === selectedBrief}
                onClick={() => setSelectedBrief(b.id)}
                audioTrack={b.source_scene ? audioTrackMap[b.source_scene] : null}
              />
            ))}

            {/* Unmapped audio clips — create brief from script */}
            {unmappedAudio.length > 0 && (
              <>
                <div style={{
                  fontSize: 7, color: '#22c55e', letterSpacing: 2, marginTop: 12, marginBottom: 4,
                  padding: '4px 4px', borderTop: '1px solid #22c55e22',
                }}>
                  UNMAPPED AUDIO · {unmappedAudio.length} clips
                </div>
                {unmappedAudio.map(track => {
                  const color = VOICE_COLORS[track.voice] || '#5a5a72';
                  return (
                    <div key={track.id} onClick={async () => {
                      // Auto-create a brief from this audio clip
                      const brief = await api.createBrief({
                        type: 'single',
                        title: track.document_slug
                          ? `Script: ${track.document_slug.replace(/^sc_\d+_/, '').replace(/_/g, ' ')}`
                          : `Audio: ${track.filename || 'clip'}`,
                        prompt: track.visual_prompt || `Scene from ${track.document_slug || track.filename}`,
                        source_scene: track.document_slug || null,
                        characters: track.voice ? [track.voice] : [],
                        tags: ['from-script'],
                      });
                      if (brief?.id) {
                        setBriefs(prev => [...prev, brief]);
                        setSelectedBrief(brief.id);
                      }
                    }} style={{
                      background: '#0f0f18', border: '1px solid #22c55e20',
                      borderRadius: 6, padding: '8px 10px', cursor: 'pointer',
                      transition: 'all 0.15s', borderLeft: `3px solid ${color}`,
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
                        <span style={{
                          fontSize: 8, color, fontWeight: 700,
                          letterSpacing: 1, textTransform: 'uppercase',
                        }}>{track.voice || '?'}</span>
                        <span style={{ fontSize: 9, color: '#6a6a7a', flex: 1 }}>
                          {(track.document_slug || track.filename || '').replace(/^sc_\d+_/, '').replace(/_/g, ' ')}
                        </span>
                        <span style={{
                          fontSize: 7, padding: '2px 6px', borderRadius: 3,
                          background: '#22c55e15', color: '#22c55e', fontWeight: 600,
                        }}>+ CREATE BRIEF</span>
                      </div>
                      <div style={{ fontSize: 7, color: '#4a4a5a' }}>
                        {track.start_time?.toFixed(1)}s — {track.end_time?.toFixed(1)}s ({track.duration?.toFixed(1)}s)
                      </div>
                    </div>
                  );
                })}
              </>
            )}
          </div>
        </div>

        {/* Detail (Center + Right) */}
        {brief ? (
          <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
            {/* Center: Content */}
            <div style={{ flex: 1, overflow: 'auto', padding: 16 }}>
              <div style={{ maxWidth: 700, margin: '0 auto' }}>
                {/* Brief header */}
                <div style={{ marginBottom: 16 }}>
                  <div style={{ fontSize: 16, color: '#e2e8f0', fontWeight: 600, marginBottom: 4 }}>{brief.title}</div>
                  <div style={{ display: 'flex', gap: 8, fontSize: 10, color: '#4a4a5a' }}>
                    <span style={{ color: (STATUS_CONFIG[brief.status] || STATUS_CONFIG.planning).color }}>{brief.status}</span>
                    <span>·</span>
                    <span>{brief.type}</span>
                    {brief.source_scene && <><span>·</span><span>from {brief.source_scene}</span></>}
                    {brief.assignee && <><span>·</span><span style={{ color: '#34d399' }}>{brief.assignee}</span></>}
                  </div>
                </div>

                {/* Audio source clip */}
                {brief.source_scene && audioTrackMap[brief.source_scene] && (() => {
                  const at = audioTrackMap[brief.source_scene];
                  const color = VOICE_COLORS[at.voice] || '#5a5a72';
                  return (
                    <div style={{
                      marginBottom: 12, padding: '8px 10px', borderRadius: 6,
                      background: '#08100e', border: '1px solid #22c55e20',
                      display: 'flex', alignItems: 'center', gap: 8,
                    }}>
                      <div style={{
                        width: 4, height: 24, borderRadius: 2, background: color,
                      }} />
                      <div style={{ flex: 1 }}>
                        <div style={{ display: 'flex', gap: 6, alignItems: 'center', fontSize: 9 }}>
                          <span style={{ color, fontWeight: 700, letterSpacing: 1, textTransform: 'uppercase' }}>
                            {at.voice || '?'}
                          </span>
                          <span style={{ color: '#4a4a5a' }}>·</span>
                          <span style={{ color: '#6a6a7a' }}>
                            {at.start_time?.toFixed(1)}s — {at.end_time?.toFixed(1)}s
                          </span>
                          <span style={{ color: '#4a4a5a' }}>·</span>
                          <span style={{ color: '#22c55e88', fontSize: 7, letterSpacing: 1 }}>MAPPED</span>
                        </div>
                        {at.visual_prompt && (
                          <div style={{ fontSize: 8, color: '#5a6a5a', marginTop: 2, fontStyle: 'italic' }}>
                            [[VISUAL]]: {at.visual_prompt.slice(0, 100)}{at.visual_prompt.length > 100 ? '...' : ''}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })()}

                {/* Hero Frame */}
                {brief.hero_frame && (
                  <div style={{ marginBottom: 16 }}>
                    <div style={{ fontSize: 8, color: '#3a3a50', letterSpacing: 2, marginBottom: 6 }}>HERO FRAME</div>
                    <img src={heroUrl(brief.hero_frame, projectSlug)} alt="" style={{
                      width: '100%', borderRadius: 6, border: '1px solid #1a1a24',
                      aspectRatio: '21/9', objectFit: 'cover',
                    }} />
                  </div>
                )}

                {/* Prompt */}
                <div style={{ marginBottom: 16 }}>
                  <div style={{ fontSize: 8, color: '#3a3a50', letterSpacing: 2, marginBottom: 6 }}>SCENE PROMPT</div>
                  <div style={{
                    padding: 12, background: '#0a0a14', borderRadius: 6, border: '1px solid #1a1a24',
                    color: '#cbd5e1', fontSize: 13, lineHeight: 1.7,
                  }}>{brief.prompt}</div>
                </div>

                {/* Sequence storyboard */}
                {brief.type === 'sequence' && brief.shots?.length > 0 && (
                  <div style={{ marginBottom: 16 }}>
                    <div style={{ fontSize: 8, color: '#3a3a50', letterSpacing: 2, marginBottom: 6 }}>SEQUENCE — {brief.shots.length} SHOTS</div>
                    <SequenceStoryboard shots={brief.shots} selectedShot={selectedShot} onSelectShot={setSelectedShot} projectSlug={projectSlug} />
                  </div>
                )}

                {/* Enriched prompt preview */}
                <div style={{ marginBottom: 16 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                    <div style={{ fontSize: 8, color: '#3a3a50', letterSpacing: 2 }}>ENRICHED PROMPT</div>
                    <button onClick={handlePreviewPrompt} style={{
                      padding: '2px 8px', borderRadius: 3, border: '1px solid #818cf840',
                      background: 'rgba(129, 140, 248, 0.08)', color: '#818cf8',
                      fontSize: 9, cursor: 'pointer',
                    }}>Preview</button>
                  </div>
                  {enrichedPrompt ? (
                    <div style={{
                      padding: 12, background: '#0a0a14', borderRadius: 6, border: '1px solid #1a1a24',
                      color: '#94a3b8', fontSize: 11, lineHeight: 1.6, fontFamily: "'JetBrains Mono', monospace",
                      whiteSpace: 'pre-wrap',
                    }}>{enrichedPrompt}</div>
                  ) : (
                    <div style={{ color: '#2a2a3a', fontSize: 10, fontStyle: 'italic' }}>Click Preview to generate enriched prompt with camera metadata</div>
                  )}
                </div>

                {/* Characters */}
                {brief.characters?.length > 0 && (
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 16 }}>
                    {brief.characters.map(c => (
                      <span key={c} style={{
                        padding: '3px 10px', borderRadius: 4,
                        background: 'rgba(74, 222, 128, 0.08)', border: '1px solid rgba(74, 222, 128, 0.2)',
                        color: '#4ade80', fontSize: 10,
                      }}>{c}</span>
                    ))}
                  </div>
                )}

                {/* Action buttons */}
                <div style={{ display: 'flex', gap: 8 }}>
                  <button onClick={handleSaveRig} style={{
                    padding: '8px 16px', borderRadius: 4, border: 'none',
                    background: 'rgba(129, 140, 248, 0.12)', color: '#818cf8',
                    fontSize: 11, cursor: 'pointer', fontWeight: 600,
                  }}>Save Rig</button>
                  <button onClick={handleGenerateEden} disabled={generating} style={{
                    padding: '8px 16px', borderRadius: 4, border: 'none',
                    background: generating
                      ? '#2a2210'
                      : 'linear-gradient(135deg, #c8ff00, #a0cc00)',
                    color: generating ? '#f59e0b' : '#08080e',
                    fontSize: 11, cursor: generating ? 'default' : 'pointer',
                    fontWeight: 700, letterSpacing: 1,
                    transition: 'all 0.2s',
                  }}>{generating ? '⟳ GENERATING...' : '▶ Generate via Eden'}</button>
                </div>
                {genError && (
                  <div style={{
                    marginTop: 8, padding: 8, background: '#1a0a0a', borderRadius: 4,
                    border: '1px solid #f8717130', fontSize: 10, color: '#f87171',
                  }}>
                    {genError}
                  </div>
                )}
              </div>
            </div>

            {/* Right: Camera Rig */}
            <div style={{
              width: 320, borderLeft: '1px solid #141420', background: 'rgba(10, 10, 16, 0.4)',
              overflow: 'auto', padding: 12, flexShrink: 0,
            }}>
              <div style={{ fontSize: 8, color: '#818cf8', letterSpacing: 2, marginBottom: 12 }}>CAMERA RIG</div>
              <CameraRigPanel camera={camera} post={post} onCameraChange={setCamera} onPostChange={setPost} />
            </div>
          </div>
        ) : (
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 24, color: '#1a1a24', marginBottom: 8 }}>◎</div>
              <div style={{ fontSize: 11, color: '#2a2a3a' }}>Select a brief from the queue</div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
