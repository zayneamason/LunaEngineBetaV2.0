/**
 * KOZMO Timeline — Multi-track Video Editing Sequencer
 *
 * Controlled component: KozmoLab owns shot state, this component renders
 * the timeline and emits drag/trim/select/playback events via callbacks.
 *
 * Features:
 *   - 3 tracks (V1 PRIMARY, V2 B-ROLL, V3 VFX)
 *   - Playhead with requestAnimationFrame playback + timecode display
 *   - Transport controls (play/pause, skip, step, zoom, snap)
 *   - Drag-to-move clips with snap-to-grid
 *   - Left/right trim handles
 *   - Click-to-scrub on time ruler
 *   - Ctrl+scroll zoom, plain scroll horizontal pan
 *   - Resizable height via drag handle
 *   - Keyboard shortcuts (Space, Home, End, Arrows, Delete)
 */
import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import {
  CAMERA_BODIES, LENS_PROFILES, CAMERA_MOVEMENTS, FILM_STOCKS,
  buildCameraPrompt,
} from '../config/cameras';
import { useLabAPI } from '../hooks/useLabAPI';

// ── Constants ───────────────────────────────────────────────────────────────
const TRACK_HEIGHT = 64;
const AUDIO_TRACK_HEIGHT = 48;
const TRACK_LABELS = ['V1 — PRIMARY', 'V2 — B-ROLL', 'V3 — VFX'];
const TRACK_COLORS = ['#c8ff00', '#818cf8', '#f59e0b'];
const TRACK_COUNT = 3;

// Voice entity colors for audio tracks
const VOICE_COLORS = {
  bella: '#c8ff00', george: '#818cf8', gandala: '#22c55e',
  lily: '#f472b6', liam: '#fb923c', mohammed: '#38bdf8',
  lucy: '#a78bfa', chebel: '#fbbf24', maria_clara: '#f97316',
  miyomi: '#67e8f9', maggi: '#e879f9',
};
const LABEL_WIDTH = 80;
const RULER_HEIGHT = 26;
const TRANSPORT_HEIGHT = 32;
const SCENE_MARKER_HEIGHT = 14;
const DETAIL_BAR_HEIGHT = 40;
const FPS = 24;
const MIN_ZOOM = 2;
const MAX_ZOOM = 200;
const SNAP_THRESHOLD = 0.25; // seconds
const MIN_CLIP_DURATION = 0.5;
const COLLAPSED_TRACK_HEIGHT = 18;
const MIN_TIMELINE_HEIGHT = 60;
const MAX_TIMELINE_HEIGHT = 800;

const SCENE_COLORS = {
  S1: '#c8ff00', S2: '#22d3ee', S3: '#a78bfa', S4: '#fb923c',
  S5: '#f472b6', S6: '#34d399', S7: '#fbbf24', S8: '#6366f1',
};

// ── Utilities ───────────────────────────────────────────────────────────────

function formatTimecode(seconds) {
  const totalFrames = Math.round(Math.max(0, seconds) * FPS);
  const mm = String(Math.floor(totalFrames / (FPS * 60))).padStart(2, '0');
  const ss = String(Math.floor((totalFrames % (FPS * 60)) / FPS)).padStart(2, '0');
  const ff = String(totalFrames % FPS).padStart(2, '0');
  return `${mm}:${ss}:${ff}`;
}

function sceneColor(scene) {
  return SCENE_COLORS[scene] || '#555';
}

// ── Sub-Components ──────────────────────────────────────────────────────────

function ResizeHandle({ onMouseDown }) {
  const [hovered, setHovered] = useState(false);
  return (
    <div
      onMouseDown={onMouseDown}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        height: 5, cursor: 'row-resize', flexShrink: 0,
        background: hovered ? '#1e1e2e' : '#141420',
        borderTop: `1px solid ${hovered ? '#2a2a3a' : '#1a1a24'}`,
        transition: 'background 0.15s',
      }}
    />
  );
}

function TransportBtn({ icon, onClick, title, accent }) {
  return (
    <button onClick={onClick} title={title} style={{
      width: accent ? 30 : 24, height: 24, borderRadius: 3,
      border: `1px solid ${accent ? '#c8ff0033' : '#1a1a24'}`,
      background: accent ? 'rgba(200,255,0,0.06)' : '#0e0e18',
      color: accent ? '#c8ff00' : '#555', fontSize: accent ? 12 : 10,
      cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
      transition: 'all 0.12s', fontFamily: 'inherit',
    }}>
      {icon}
    </button>
  );
}

function TimeRuler({ zoom, totalDuration, onScrub }) {
  let majorInterval, minorInterval;
  if (zoom >= 120) { majorInterval = 1; minorInterval = 0.5; }
  else if (zoom >= 60) { majorInterval = 2; minorInterval = 1; }
  else if (zoom >= 20) { majorInterval = 5; minorInterval = 1; }
  else if (zoom >= 8) { majorInterval = 15; minorInterval = 5; }
  else if (zoom >= 4) { majorInterval = 30; minorInterval = 10; }
  else { majorInterval = 60; minorInterval = 15; }

  const ticks = [];
  for (let t = 0; t <= totalDuration; t += minorInterval) {
    const isMajor = Math.abs(t % majorInterval) < 0.01
      || Math.abs(t % majorInterval - majorInterval) < 0.01;
    ticks.push(
      <div key={t} style={{ position: 'absolute', left: t * zoom }}>
        <div style={{
          width: 1, height: isMajor ? 12 : 6,
          background: isMajor ? '#2a2a3a' : '#1a1a24',
          position: 'absolute', bottom: 0,
        }} />
        {isMajor && (
          <span style={{
            position: 'absolute', top: 2, left: 4,
            fontSize: 7, color: '#444', whiteSpace: 'nowrap',
            fontVariantNumeric: 'tabular-nums',
          }}>
            {t >= 60 ? `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, '0')}` : `${Math.floor(t)}s`}
          </span>
        )}
      </div>
    );
  }

  return (
    <div
      onMouseDown={(e) => {
        const rect = e.currentTarget.getBoundingClientRect();
        // The ruler is inside the translateX(-scrollX) wrapper, so
        // rect.left already accounts for the scroll offset.
        const x = e.clientX - rect.left;
        onScrub(Math.max(0, x / zoom));
      }}
      style={{
        height: RULER_HEIGHT, background: '#0a0a14',
        borderBottom: '1px solid #1a1a24', position: 'relative',
        cursor: 'col-resize', overflow: 'hidden', flexShrink: 0,
      }}
    >
      {ticks}
    </div>
  );
}

function ShotClip({ shot, zoom, selected, hovered, statusConfig, onSelect, onHover, onDragStart, collapsed }) {
  const left = (shot.startTime ?? 0) * zoom;
  const width = shot.duration * zoom;
  const st = statusConfig[shot.status] || statusConfig.idea;
  const sc = sceneColor(shot.scene);
  const trimW = 6;

  // Use pre-computed offset from parent if available, else fallback
  const yOffset = shot._yOffset ?? ((shot.track ?? 0) * TRACK_HEIGHT);
  const trackH = shot._trackH ?? TRACK_HEIGHT;
  const clipH = collapsed ? COLLAPSED_TRACK_HEIGHT - 4 : trackH - 10;
  const clipTop = yOffset + (collapsed ? 2 : 5);

  return (
    <div
      style={{
        position: 'absolute',
        left, top: clipTop,
        width, height: clipH,
        borderRadius: 4, overflow: 'hidden',
        background: selected ? `linear-gradient(135deg, ${st.color}14, ${st.color}08)` : hovered ? '#14141f' : '#10101a',
        border: `1px solid ${selected ? `${st.color}55` : hovered ? '#2a2a3a' : '#1a1a24'}`,
        cursor: 'pointer', zIndex: selected ? 5 : hovered ? 4 : 1,
        transition: selected || hovered ? 'none' : 'border-color 0.12s',
        pointerEvents: 'auto',
      }}
      onClick={(e) => { e.stopPropagation(); onSelect(); }}
      onMouseEnter={() => onHover(true)}
      onMouseLeave={() => onHover(false)}
    >
      {/* Scene color accent */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, height: 2,
        background: `linear-gradient(90deg, ${sc}88, ${sc}22)`,
        borderRadius: '4px 4px 0 0',
      }} />

      {/* Clip body (drag target) */}
      <div
        style={{
          padding: collapsed ? '1px 4px' : '5px 8px 4px', height: '100%',
          display: 'flex', flexDirection: 'column', justifyContent: collapsed ? 'center' : 'space-between',
          cursor: 'grab', overflow: 'hidden',
        }}
        onMouseDown={(e) => { e.preventDefault(); onDragStart('move', e.clientX); }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: collapsed ? 3 : 5, minWidth: 0 }}>
          <span style={{ fontSize: collapsed ? 6 : 7, color: sc, fontWeight: 700, letterSpacing: 1, flexShrink: 0 }}>
            {shot.id.toUpperCase()}
          </span>
          {!collapsed && width > 90 && (
            <span style={{
              fontSize: 8, color: '#777', overflow: 'hidden',
              textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1,
            }}>
              {shot.name}
            </span>
          )}
          {width > 55 && (
            <span style={{ fontSize: 6, color: st.color, fontWeight: 700, letterSpacing: 1, flexShrink: 0 }}>
              {statusConfig[shot.status]?.label || 'IDEA'}
            </span>
          )}
        </div>
        {!collapsed && width > 110 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 7, color: '#444' }}>
            <span>{shot.type?.toUpperCase?.() || shot.type}</span>
            <span style={{ color: '#2a2a3a' }}>·</span>
            <span>{shot.focal}mm</span>
            <span style={{ color: '#2a2a3a' }}>·</span>
            <span>ƒ/{shot.aperture}</span>
            {width > 180 && (
              <>
                <span style={{ color: '#2a2a3a' }}>·</span>
                <span>{Array.isArray(shot.movement) ? shot.movement.join('+') : shot.movement}</span>
              </>
            )}
          </div>
        )}
      </div>

      {/* Duration badge */}
      {!collapsed && width > 45 && (
        <div style={{
          position: 'absolute', bottom: 3, right: 7,
          fontSize: 7, color: '#333', fontWeight: 600,
        }}>
          {shot.duration.toFixed(1)}s
        </div>
      )}

      {/* Trim handle LEFT */}
      {!collapsed && (
        <div
          style={{
            position: 'absolute', left: 0, top: 0, width: trimW, height: '100%',
            cursor: 'ew-resize', zIndex: 2,
            background: selected || hovered ? `${st.color}18` : 'transparent',
            borderRight: selected || hovered ? `1px solid ${st.color}28` : 'none',
          }}
          onMouseDown={(e) => { e.preventDefault(); e.stopPropagation(); onDragStart('trimL', e.clientX); }}
        />
      )}

      {/* Trim handle RIGHT */}
      {!collapsed && (
        <div
          style={{
            position: 'absolute', right: 0, top: 0, width: trimW, height: '100%',
            cursor: 'ew-resize', zIndex: 2,
            background: selected || hovered ? `${st.color}18` : 'transparent',
            borderLeft: selected || hovered ? `1px solid ${st.color}28` : 'none',
          }}
          onMouseDown={(e) => { e.preventDefault(); e.stopPropagation(); onDragStart('trimR', e.clientX); }}
        />
      )}

      {/* Filmstrip texture */}
      {!collapsed && (
        <div style={{
          position: 'absolute', inset: 0, pointerEvents: 'none', borderRadius: 4,
          background: `repeating-linear-gradient(90deg, transparent, transparent ${zoom * 0.5 - 1}px, ${st.color}05 ${zoom * 0.5 - 1}px, ${st.color}05 ${zoom * 0.5}px)`,
        }} />
      )}
    </div>
  );
}

function ScriptRef({ track, onNavigate }) {
  if (!track) return null;
  const color = VOICE_COLORS[track.voice] || '#5a5a72';
  const hasDoc = !!track.document_slug;
  const containerLabel = track.container_slug
    ? track.container_slug.replace(/^sec_\d+_/, '').replace(/_/g, ' ')
    : null;

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 6,
      fontSize: 8, overflow: 'hidden', minWidth: 0,
    }}>
      <span style={{ color: '#2a2a3a' }}>│</span>
      <span style={{ color, fontWeight: 700, letterSpacing: 1, textTransform: 'uppercase', flexShrink: 0 }}>
        {track.voice || '?'}
      </span>
      {track.section != null && (
        <span style={{
          color: '#444', fontSize: 7, flexShrink: 0,
          padding: '0 3px', border: '1px solid #1a1a24', borderRadius: 2,
        }}>
          S{track.section}{track.lines ? ` L${track.lines}` : ''}
        </span>
      )}
      {hasDoc && (
        <span
          onClick={(e) => { e.stopPropagation(); onNavigate?.(track.document_slug, track.container_slug); }}
          title={`Open script: ${track.document_slug}`}
          style={{
            color: '#818cf8', cursor: 'pointer', fontWeight: 500,
            textDecoration: 'underline', textDecorationColor: '#818cf833',
            textUnderlineOffset: 2, whiteSpace: 'nowrap',
            overflow: 'hidden', textOverflow: 'ellipsis',
          }}
        >
          {track.document_slug.replace(/^sc_\d+_/, '').replace(/_/g, ' ')}
        </span>
      )}
      {containerLabel && (
        <span style={{ color: '#333', fontSize: 7, whiteSpace: 'nowrap' }}>
          {containerLabel}
        </span>
      )}
      {track.text && (
        <>
          <span style={{ color: '#2a2a3a' }}>│</span>
          <span style={{
            color: '#555', fontSize: 8, fontStyle: 'italic',
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            flex: 1, minWidth: 0,
          }}>
            "{track.text.slice(0, 80)}{track.text.length > 80 ? '...' : ''}"
          </span>
        </>
      )}
    </div>
  );
}

// ── Generate From Script Dialog ─────────────────────────────────────────────
function GenerateFromScript({ track, onClose, projectSlug, onShotAdd, onShotUpdate }) {
  const api = useLabAPI();
  const [camera, setCamera] = useState({
    body: 'arri_alexa35', lens: 'cooke_s7i', focal: 50, aperture: 2.8,
    movement: ['static'], duration: track?.duration || 3,
  });
  const [post, setPost] = useState({
    stock: 'kodak_5219', color_temp: 5600, grain: 0, bloom: 0, halation: 0,
  });
  const [prompt, setPrompt] = useState('');
  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState(null); // { image_url, brief_id }
  const [error, setError] = useState(null);
  const [polling, setPolling] = useState(false);

  // Auto-build prompt from [[VISUAL]] tag in scribo, fallback to scene description
  useEffect(() => {
    if (!track) return;
    if (track.visual_prompt) {
      // Use the [[VISUAL]] directive directly — this is the cinema-grade prompt
      setPrompt(track.visual_prompt);
    } else {
      // Fallback: construct from available metadata
      const parts = [];
      if (track.document_slug) {
        const sceneName = track.document_slug.replace(/^sc_\d+_/, '').replace(/_/g, ' ');
        parts.push(`Scene: ${sceneName}`);
      }
      if (track.voice) parts.push(`Character: ${track.voice}`);
      if (track.filename) parts.push(`Audio: ${track.filename.replace(/\.\w+$/, '').replace(/_/g, ' ')}`);
      setPrompt(parts.join('. '));
    }
  }, [track]);

  const cameraPromptSuffix = useMemo(() => buildCameraPrompt({
    body: camera.body, lens: camera.lens, focalMm: camera.focal,
    aperture: camera.aperture, filmStock: post.stock, movements: camera.movement,
  }), [camera, post.stock]);

  const fullPrompt = prompt + (cameraPromptSuffix ? `. ${cameraPromptSuffix}` : '');

  const handleGenerate = useCallback(async () => {
    if (!projectSlug || !prompt.trim()) return;
    setGenerating(true);
    setError(null);

    // Immediately create an empty clip on the timeline at the audio track's timecodes
    const shotId = `sh_${Date.now().toString(36)}`;
    const shotDuration = (track?.end_time ?? 0) - (track?.start_time ?? 0);
    if (onShotAdd) {
      onShotAdd({
        id: shotId,
        scene: track?.document_slug ? track.document_slug.replace(/^sc_\d+_/, 'S') : 'S1',
        name: track?.document_slug
          ? track.document_slug.replace(/^sc_\d+_/, '').replace(/_/g, ' ')
          : track?.filename || 'Generated Shot',
        type: 'medium',
        status: 'rendering',
        heroFrame: null,
        camera: camera.body || 'arri_alexa35',
        lens: camera.lens || 'cooke_s7i',
        focal: camera.focal || 50,
        aperture: camera.aperture || 2.8,
        movement: camera.movement || ['static'],
        duration: Math.max(shotDuration, 1),
        filmStock: post.stock || 'kodak_5219',
        startTime: track?.start_time ?? 0,
        track: 0,
        audio_track_id: track?.id || null,
      });
    }

    try {
      // 1. Create a production brief from script context
      const brief = await api.createBrief({
        type: 'single',
        title: track?.document_slug
          ? `Script: ${track.document_slug.replace(/^sc_\d+_/, '').replace(/_/g, ' ')}`
          : `Audio: ${track?.filename || 'clip'}`,
        prompt: prompt.trim(),
        source_scene: track?.document_slug || null,
        characters: track?.voice ? [track.voice] : [],
        audio_track_id: track?.id || null,
        audio_start: track?.start_time ?? null,
        audio_end: track?.end_time ?? null,
        camera: camera,
        post: post,
        tags: ['from-script'],
      });

      if (!brief?.id) throw new Error('Failed to create brief');

      // 2. Dispatch to Eden
      const genRes = await fetch(
        `/kozmo/projects/${projectSlug}/lab/briefs/${brief.id}/generate`,
        { method: 'POST' }
      );
      if (!genRes.ok) throw new Error(`Generate failed: ${genRes.status}`);
      const genData = await genRes.json();

      // 3. Poll for result
      setPolling(true);
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
          if (status.is_complete && status.image_url) {
            setResult({ image_url: status.image_url, brief_id: brief.id });
            // Drop the image into the timeline clip
            if (onShotUpdate) {
              onShotUpdate(shotId, {
                heroFrame: status.image_url,
                status: 'hero_approved',
              });
            }
            setPolling(false);
            setGenerating(false);
            return;
          }
          if (status.status === 'failed') {
            throw new Error('Generation failed');
          }
        } catch { /* keep polling */ }
      }
      throw new Error('Generation timed out');
    } catch (e) {
      setError(e.message);
      // Mark clip as failed
      if (onShotUpdate) {
        onShotUpdate(shotId, { status: 'draft' });
      }
      setPolling(false);
      setGenerating(false);
    }
  }, [projectSlug, prompt, track, camera, post, api, onShotAdd, onShotUpdate]);

  if (!track) return null;

  const voice = track.voice || '?';
  const color = VOICE_COLORS[voice] || '#5a5a72';

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 1000,
      background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(8px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }} onClick={onClose}>
      <div onClick={e => e.stopPropagation()} style={{
        width: 720, maxHeight: '85vh', background: '#0c0c16',
        border: '1px solid #1a1a2e', borderRadius: 10,
        display: 'flex', flexDirection: 'column', overflow: 'hidden',
        boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
      }}>
        {/* Header */}
        <div style={{
          padding: '12px 16px', borderBottom: '1px solid #141420',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ width: 3, height: 20, background: color, borderRadius: 2 }} />
            <span style={{ fontSize: 10, letterSpacing: 3, color: '#c8ff00', fontWeight: 800 }}>GENERATE FROM SCRIPT</span>
          </div>
          <button onClick={onClose} style={{
            background: 'none', border: 'none', color: '#4a4a5a', cursor: 'pointer',
            fontSize: 14, fontFamily: 'inherit',
          }}>x</button>
        </div>

        <div style={{ flex: 1, overflow: 'auto', display: 'flex' }}>
          {/* Left: Prompt + Context */}
          <div style={{ flex: 1, padding: 16, display: 'flex', flexDirection: 'column', gap: 14 }}>
            {/* Script context */}
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', fontSize: 9 }}>
              <span style={{
                padding: '3px 8px', borderRadius: 3,
                background: `${color}15`, border: `1px solid ${color}30`, color,
                fontWeight: 700, letterSpacing: 1, textTransform: 'uppercase',
              }}>{voice}</span>
              {track.document_slug && (
                <span style={{
                  padding: '3px 8px', borderRadius: 3,
                  background: '#818cf815', border: '1px solid #818cf830', color: '#818cf8',
                }}>
                  {track.document_slug.replace(/^sc_\d+_/, '').replace(/_/g, ' ')}
                </span>
              )}
              {track.container_slug && (
                <span style={{
                  padding: '3px 8px', borderRadius: 3,
                  background: '#22c55e15', border: '1px solid #22c55e30', color: '#22c55e88',
                  fontSize: 8,
                }}>
                  {track.container_slug.replace(/^sec_\d+_/, '').replace(/_/g, ' ')}
                </span>
              )}
              <span style={{
                padding: '3px 8px', borderRadius: 3,
                background: '#1a1a24', color: '#555',
              }}>
                {track.start_time?.toFixed(1)}s — {track.end_time?.toFixed(1)}s ({track.duration?.toFixed(1)}s)
              </span>
            </div>

            {/* Dialogue text preview */}
            {track.text && (
              <div style={{
                padding: 10, background: '#0a0a12', borderRadius: 6,
                border: '1px solid #1a1a20', fontSize: 11, color: '#6a6a7a',
                fontStyle: 'italic', lineHeight: 1.6,
              }}>
                <div style={{ fontSize: 7, color: '#3a3a50', letterSpacing: 2, marginBottom: 4, fontStyle: 'normal' }}>DIALOGUE</div>
                "{track.text}"
              </div>
            )}
            {/* Visual prompt source indicator */}
            {track.visual_prompt && (
              <div style={{
                padding: 10, background: '#0a120a', borderRadius: 6,
                border: '1px solid #22c55e20', fontSize: 10, color: '#8a9a8a',
                lineHeight: 1.5,
              }}>
                <div style={{ fontSize: 7, color: '#22c55e', letterSpacing: 2, marginBottom: 4 }}>[[VISUAL]] SOURCE</div>
                {track.visual_prompt}
              </div>
            )}

            {/* Prompt editor */}
            <div>
              <div style={{ fontSize: 8, color: '#3a3a50', letterSpacing: 2, marginBottom: 6 }}>SCENE PROMPT</div>
              <textarea
                value={prompt}
                onChange={e => setPrompt(e.target.value)}
                rows={4}
                style={{
                  width: '100%', padding: 10, background: '#08080e',
                  border: '1px solid #1a1a2e', borderRadius: 6, color: '#cbd5e1',
                  fontSize: 12, fontFamily: "'JetBrains Mono', monospace",
                  lineHeight: 1.6, resize: 'vertical', outline: 'none',
                }}
                placeholder="Describe the visual scene..."
              />
            </div>

            {/* Camera prompt preview */}
            {cameraPromptSuffix && (
              <div>
                <div style={{ fontSize: 8, color: '#3a3a50', letterSpacing: 2, marginBottom: 4 }}>CAMERA METADATA</div>
                <div style={{
                  padding: 8, background: '#0a0a12', borderRadius: 4,
                  border: '1px solid #1a1a20', fontSize: 9, color: '#4a4a5a',
                  fontFamily: "'JetBrains Mono', monospace",
                }}>
                  {cameraPromptSuffix}
                </div>
              </div>
            )}

            {/* Result */}
            {result && (
              <div style={{
                padding: 12, background: '#0a1a0a', borderRadius: 6,
                border: '1px solid #22c55e30',
              }}>
                <div style={{ fontSize: 8, color: '#22c55e', letterSpacing: 2, marginBottom: 8 }}>GENERATED</div>
                <img src={result.image_url} alt="Generated" style={{
                  width: '100%', borderRadius: 4, border: '1px solid #1a1a24',
                }} />
              </div>
            )}

            {/* Error */}
            {error && (
              <div style={{
                padding: 8, background: '#1a0a0a', borderRadius: 4,
                border: '1px solid #f8717130', fontSize: 10, color: '#f87171',
              }}>
                {error}
              </div>
            )}
          </div>

          {/* Right: Camera Rig */}
          <div style={{
            width: 260, borderLeft: '1px solid #141420', padding: 12,
            overflow: 'auto', flexShrink: 0,
          }}>
            <div style={{ fontSize: 8, color: '#818cf8', letterSpacing: 2, marginBottom: 10 }}>CAMERA RIG</div>

            {/* Camera Body */}
            <div style={{ marginBottom: 10 }}>
              <div style={{ fontSize: 7, color: '#3a3a50', letterSpacing: 2, marginBottom: 4 }}>BODY</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                {CAMERA_BODIES.map(c => (
                  <button key={c.id} onClick={() => setCamera(p => ({ ...p, body: c.id }))} style={{
                    display: 'flex', justifyContent: 'space-between', padding: '4px 6px',
                    borderRadius: 3, border: 'none',
                    background: camera.body === c.id ? '#16162a' : 'transparent',
                    cursor: 'pointer', fontFamily: 'inherit',
                  }}>
                    <span style={{ fontSize: 9, color: camera.body === c.id ? '#e8e8f0' : '#5a5a70' }}>{c.name}</span>
                    <span style={{ fontSize: 6, color: camera.body === c.id ? '#c8ff00' : '#2a2a3a', letterSpacing: 1 }}>{c.badge}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Lens */}
            <div style={{ marginBottom: 10 }}>
              <div style={{ fontSize: 7, color: '#3a3a50', letterSpacing: 2, marginBottom: 4 }}>LENS</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                {LENS_PROFILES.map(l => (
                  <button key={l.id} onClick={() => setCamera(p => ({ ...p, lens: l.id }))} style={{
                    display: 'flex', justifyContent: 'space-between', padding: '4px 6px',
                    borderRadius: 3, border: 'none',
                    background: camera.lens === l.id ? '#16162a' : 'transparent',
                    cursor: 'pointer', fontFamily: 'inherit', textAlign: 'left',
                  }}>
                    <div>
                      <div style={{ fontSize: 9, color: camera.lens === l.id ? '#e8e8f0' : '#5a5a70' }}>{l.name}</div>
                      <div style={{ fontSize: 6, color: '#2a2a3a' }}>{l.character}</div>
                    </div>
                    <span style={{ fontSize: 6, color: l.type === 'anamorphic' ? '#f59e0b' : '#3a3a4a' }}>
                      {l.type === 'anamorphic' ? 'ANA' : 'SPH'}
                    </span>
                  </button>
                ))}
              </div>
            </div>

            {/* Focal & Aperture */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, marginBottom: 10 }}>
              <div>
                <div style={{ fontSize: 7, color: '#3a3a50', letterSpacing: 2, marginBottom: 3 }}>FOCAL</div>
                <input type="range" min={12} max={200} value={camera.focal}
                  onChange={e => setCamera(p => ({ ...p, focal: parseInt(e.target.value) }))}
                  style={{ width: '100%', accentColor: '#818cf8' }} />
                <div style={{ fontSize: 9, color: '#e8e8f0', textAlign: 'center' }}>{camera.focal}mm</div>
              </div>
              <div>
                <div style={{ fontSize: 7, color: '#3a3a50', letterSpacing: 2, marginBottom: 3 }}>APERTURE</div>
                <input type="range" min={14} max={220} value={camera.aperture * 10}
                  onChange={e => setCamera(p => ({ ...p, aperture: parseInt(e.target.value) / 10 }))}
                  style={{ width: '100%', accentColor: '#818cf8' }} />
                <div style={{ fontSize: 9, color: '#e8e8f0', textAlign: 'center' }}>f/{camera.aperture}</div>
              </div>
            </div>

            {/* Movements */}
            <div style={{ marginBottom: 10 }}>
              <div style={{ fontSize: 7, color: '#3a3a50', letterSpacing: 2, marginBottom: 4 }}>MOVEMENT</div>
              <div style={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                {CAMERA_MOVEMENTS.map(m => {
                  const isActive = camera.movement?.includes(m.id);
                  return (
                    <button key={m.id} onClick={() => {
                      const cur = camera.movement || [];
                      if (cur.includes(m.id)) setCamera(p => ({ ...p, movement: cur.filter(x => x !== m.id) }));
                      else if (cur.length < 3) setCamera(p => ({ ...p, movement: [...cur, m.id] }));
                    }} style={{
                      padding: '2px 6px', fontSize: 7, borderRadius: 3,
                      border: `1px solid ${isActive ? '#818cf8' : '#1a1a2e'}`,
                      background: isActive ? 'rgba(129, 140, 248, 0.08)' : 'transparent',
                      color: isActive ? '#818cf8' : '#4a4a5a',
                      cursor: 'pointer', fontFamily: 'inherit',
                    }}>{m.name}</button>
                  );
                })}
              </div>
            </div>

            {/* Film Stock */}
            <div style={{ marginBottom: 10 }}>
              <div style={{ fontSize: 7, color: '#3a3a50', letterSpacing: 2, marginBottom: 4 }}>FILM STOCK</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                <button onClick={() => setPost(p => ({ ...p, stock: 'none' }))} style={{
                  padding: '4px 6px', borderRadius: 3, border: 'none',
                  background: post.stock === 'none' ? '#16162a' : 'transparent',
                  cursor: 'pointer', fontFamily: 'inherit', textAlign: 'left',
                  fontSize: 9, color: post.stock === 'none' ? '#e8e8f0' : '#5a5a70',
                }}>Digital</button>
                {FILM_STOCKS.map(f => (
                  <button key={f.id} onClick={() => setPost(p => ({ ...p, stock: f.id }))} style={{
                    padding: '4px 6px', borderRadius: 3, border: 'none',
                    background: post.stock === f.id ? '#16162a' : 'transparent',
                    cursor: 'pointer', fontFamily: 'inherit', textAlign: 'left',
                  }}>
                    <div style={{ fontSize: 9, color: post.stock === f.id ? '#e8e8f0' : '#5a5a70' }}>{f.name}</div>
                    <div style={{ fontSize: 6, color: '#2a2a3a' }}>{f.character}</div>
                  </button>
                ))}
              </div>
            </div>

            {/* Post sliders */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
              {[
                { key: 'grain', label: 'GRAIN', max: 30 },
                { key: 'bloom', label: 'BLOOM', max: 30 },
                { key: 'halation', label: 'HALATION', max: 20 },
              ].map(s => (
                <div key={s.key}>
                  <div style={{ fontSize: 6, color: '#3a3a50', letterSpacing: 2, marginBottom: 2 }}>{s.label}</div>
                  <input type="range" min={0} max={s.max} value={post[s.key]}
                    onChange={e => setPost(p => ({ ...p, [s.key]: parseInt(e.target.value) }))}
                    style={{ width: '100%', accentColor: '#818cf8' }} />
                  <div style={{ fontSize: 8, color: '#5a5a70', textAlign: 'center' }}>{post[s.key]}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div style={{
          padding: '10px 16px', borderTop: '1px solid #141420',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <span style={{ fontSize: 9, color: '#3a3a50' }}>
            {generating ? (polling ? 'Generating via Eden...' : 'Creating brief...') : 'Configure camera rig and generate'}
          </span>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={onClose} style={{
              padding: '7px 14px', borderRadius: 4, border: '1px solid #2a2a3a',
              background: 'transparent', color: '#6b6b80', fontSize: 10,
              cursor: 'pointer', fontFamily: 'inherit',
            }}>Cancel</button>
            <button
              onClick={handleGenerate}
              disabled={generating || !prompt.trim()}
              style={{
                padding: '7px 18px', borderRadius: 4, border: 'none',
                background: generating
                  ? '#333'
                  : 'linear-gradient(135deg, #c8ff00, #a0cc00)',
                color: generating ? '#666' : '#08080e',
                fontSize: 10, cursor: generating ? 'default' : 'pointer',
                fontWeight: 700, letterSpacing: 1, fontFamily: 'inherit',
              }}
            >
              {generating ? (polling ? '⟳ GENERATING...' : 'CREATING...') : '▶ GENERATE VIA EDEN'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Audio Clip Context Menu ─────────────────────────────────────────────────
function AudioContextMenu({ x, y, track, onClose, onGenerate, onNavigate }) {
  useEffect(() => {
    // Delay listener so the right-click event that opened the menu doesn't immediately close it
    const timer = setTimeout(() => {
      const close = () => onClose();
      window.addEventListener('click', close, { once: true });
      window.addEventListener('contextmenu', close, { once: true });
    }, 50);
    return () => {
      clearTimeout(timer);
      // cleanup in case menu closes before timeout fires
    };
  }, [onClose]);

  const hasScript = !!track?.document_slug;

  return (
    <div onClick={e => e.stopPropagation()} style={{
      position: 'fixed', left: x, top: y, zIndex: 999,
      background: '#12121e', border: '1px solid #2a2a3a', borderRadius: 6,
      padding: 4, minWidth: 180, boxShadow: '0 8px 30px rgba(0,0,0,0.5)',
    }}>
      <button onClick={() => { onGenerate(); onClose(); }} style={{
        display: 'flex', alignItems: 'center', gap: 8, width: '100%',
        padding: '7px 10px', borderRadius: 4, border: 'none',
        background: 'transparent', cursor: 'pointer', fontFamily: 'inherit',
        color: '#c8ff00', fontSize: 10, textAlign: 'left',
      }}>
        <span style={{ fontSize: 12 }}>◎</span> Generate Shot from Script
      </button>
      {hasScript && (
        <button onClick={() => { onNavigate(track.document_slug, track.container_slug); onClose(); }} style={{
          display: 'flex', alignItems: 'center', gap: 8, width: '100%',
          padding: '7px 10px', borderRadius: 4, border: 'none',
          background: 'transparent', cursor: 'pointer', fontFamily: 'inherit',
          color: '#818cf8', fontSize: 10, textAlign: 'left',
        }}>
          <span style={{ fontSize: 12 }}>→</span> Open in SCRIBO
        </button>
      )}
      <div style={{ height: 1, background: '#1a1a24', margin: '2px 0' }} />
      <button onClick={onClose} style={{
        display: 'flex', alignItems: 'center', gap: 8, width: '100%',
        padding: '7px 10px', borderRadius: 4, border: 'none',
        background: 'transparent', cursor: 'pointer', fontFamily: 'inherit',
        color: '#4a4a5a', fontSize: 10, textAlign: 'left',
      }}>
        <span style={{ fontSize: 12 }}>x</span> Cancel
      </button>
    </div>
  );
}

function DetailBar({ shot, statusConfig, activeAudioTrack, onNavigateToScript, onGenerateFromScript }) {
  if (!shot && !activeAudioTrack) {
    return (
      <div style={{
        height: DETAIL_BAR_HEIGHT, background: '#0a0a14', borderTop: '1px solid #141420',
        display: 'flex', alignItems: 'center', padding: '0 12px', gap: 12,
        fontSize: 9, flexShrink: 0,
      }}>
        <span style={{ color: '#444' }}>No clip selected</span>
        <span style={{ color: '#2a2a3a' }}>│</span>
        <span style={{ color: '#2a2a3a', fontSize: 8 }}>
          Click clip · Drag to move · Edges to trim · ⌘+Scroll zoom · Shift+Scroll pan · F fit · M mute · Click track label to collapse
        </span>
      </div>
    );
  }

  // Audio-only mode (no video clip selected but audio playing)
  if (!shot && activeAudioTrack) {
    return (
      <div style={{
        height: DETAIL_BAR_HEIGHT, background: '#0a0a14', borderTop: '1px solid #141420',
        display: 'flex', alignItems: 'center', padding: '0 12px', gap: 6,
        fontSize: 9, flexShrink: 0, overflow: 'hidden',
      }}>
        <span style={{ fontSize: 7, color: '#22c55e', fontWeight: 700, letterSpacing: 1 }}>SCRIPT</span>
        <ScriptRef track={activeAudioTrack} onNavigate={onNavigateToScript} />
        <div style={{ flex: 1 }} />
        <button onClick={() => onGenerateFromScript?.(activeAudioTrack)} style={{
          padding: '5px 14px', borderRadius: 4,
          border: '1px solid #c8ff0050',
          background: 'linear-gradient(135deg, #c8ff0025, #a0cc0015)',
          color: '#c8ff00', fontSize: 9, cursor: 'pointer', fontWeight: 700,
          letterSpacing: 1, fontFamily: 'inherit',
          boxShadow: '0 0 8px rgba(200,255,0,0.1)',
        }}>
          ◎ GENERATE IMAGE
        </button>
        {activeAudioTrack?.document_slug && (
          <button onClick={() => onNavigateToScript?.(activeAudioTrack.document_slug, activeAudioTrack.container_slug)} style={{
            padding: '5px 10px', borderRadius: 4,
            border: '1px solid #818cf830',
            background: '#818cf810',
            color: '#818cf8', fontSize: 9, cursor: 'pointer', fontWeight: 600,
            letterSpacing: 1, fontFamily: 'inherit',
          }}>
            SCRIBO
          </button>
        )}
      </div>
    );
  }

  const st = statusConfig[shot.status] || statusConfig.idea;
  const camera = CAMERA_BODIES.find(c => c.id === shot.camera);
  const lens = LENS_PROFILES.find(l => l.id === shot.lens);
  const stock = FILM_STOCKS.find(f => f.id === shot.filmStock);
  const moves = Array.isArray(shot.movement)
    ? shot.movement.map(m => CAMERA_MOVEMENTS.find(cm => cm.id === m)?.name || m).join(' → ')
    : shot.movement;

  return (
    <div style={{
      height: DETAIL_BAR_HEIGHT, background: '#0a0a14', borderTop: '1px solid #141420',
      display: 'flex', alignItems: 'center', padding: '0 12px', gap: 10,
      fontSize: 9, flexShrink: 0, overflow: 'hidden',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <div style={{
          width: 6, height: 6, borderRadius: '50%',
          background: st.color, boxShadow: `0 0 4px ${st.color}44`,
        }} />
        <span style={{ color: '#bbb', fontWeight: 600, whiteSpace: 'nowrap' }}>{shot.name}</span>
        <span style={{
          color: st.color, fontSize: 7, fontWeight: 700, letterSpacing: 1,
          padding: '1px 5px', border: `1px solid ${st.color}33`, borderRadius: 3,
        }}>
          {st.label}
        </span>
      </div>
      <span style={{ color: '#2a2a3a' }}>│</span>
      <DItem label="IN" value={formatTimecode(shot.startTime ?? 0)} />
      <DItem label="OUT" value={formatTimecode((shot.startTime ?? 0) + shot.duration)} />
      <DItem label="DUR" value={`${shot.duration.toFixed(1)}s`} />
      <span style={{ color: '#2a2a3a' }}>│</span>
      <DItem label="CAM" value={camera?.name || shot.camera} />
      <DItem label="" value={`${shot.focal}mm ƒ/${shot.aperture}`} />
      <DItem label="MOVE" value={moves} />
      {stock && <DItem label="STOCK" value={stock.name} />}
      {activeAudioTrack && (
        <ScriptRef track={activeAudioTrack} onNavigate={onNavigateToScript} />
      )}
      {activeAudioTrack && (
        <>
          <div style={{ flex: 1 }} />
          <button onClick={() => onGenerateFromScript?.(activeAudioTrack)} style={{
            padding: '4px 10px', borderRadius: 4,
            border: '1px solid #c8ff0040',
            background: 'linear-gradient(135deg, #c8ff0020, #a0cc0010)',
            color: '#c8ff00', fontSize: 8, cursor: 'pointer', fontWeight: 700,
            letterSpacing: 1, fontFamily: 'inherit', flexShrink: 0,
          }}>
            ◎ GENERATE
          </button>
        </>
      )}
    </div>
  );
}

function DItem({ label, value }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 3, whiteSpace: 'nowrap' }}>
      {label && <span style={{ color: '#2a2a3a', fontSize: 7, fontWeight: 700, letterSpacing: 1 }}>{label}</span>}
      <span style={{ color: '#666', fontSize: 9 }}>{value}</span>
    </div>
  );
}

// ── Main Component ──────────────────────────────────────────────────────────

export default function KozmoTimeline({
  shots, selectedShot, onSelectShot,
  onClipMove, onClipTrim, onClipDelete,
  isPlaying, onPlayPause, onStop, playheadTime, onPlayheadChange,
  timelineHeight, onResizeHeight, statusConfig,
  audioTracks = [],
  projectSlug,
  onNavigateToScript,
  onShotAdd,
  onShotUpdate,
}) {
  const [zoom, setZoom] = useState(6);
  const [scrollX, setScrollX] = useState(0);
  const [scrollY, setScrollY] = useState(0);
  const [snapEnabled, setSnapEnabled] = useState(true);
  const [audioMuted, setAudioMuted] = useState(false);
  const [audioDevices, setAudioDevices] = useState([]);
  const [selectedDevice, setSelectedDevice] = useState('');
  const [dragging, setDragging] = useState(null);
  const [scrubbing, setScrubbing] = useState(false);
  const [hoveredId, setHoveredId] = useState(null);
  const [activeAudioTrack, setActiveAudioTrack] = useState(null);
  // Collapsible tracks: { 0: true, 1: true, 2: true, audio: true }
  const [collapsedTracks, setCollapsedTracks] = useState({});
  // Generate from script dialog + context menu
  const [generateTrack, setGenerateTrack] = useState(null); // AudioTrack to generate from
  const [contextMenu, setContextMenu] = useState(null); // { x, y, track }

  // Local playhead state for smooth 60fps rendering during playback
  const [localPlayhead, setLocalPlayhead] = useState(playheadTime);

  const trackAreaRef = useRef(null);
  const rafRef = useRef(null);
  const lastFrameRef = useRef(null);
  const playheadRef = useRef(playheadTime);
  const onPlayheadChangeRef = useRef(onPlayheadChange);
  const onStopRef = useRef(onStop);

  const onSelectShotRef = useRef(onSelectShot);
  const selectedShotRef = useRef(selectedShot);
  const shotsRef = useRef(shots);

  // Keep refs in sync with latest callbacks (avoids stale closures in rAF)
  useEffect(() => { onPlayheadChangeRef.current = onPlayheadChange; }, [onPlayheadChange]);
  useEffect(() => { onStopRef.current = onStop; }, [onStop]);
  useEffect(() => { onSelectShotRef.current = onSelectShot; }, [onSelectShot]);
  useEffect(() => { selectedShotRef.current = selectedShot; }, [selectedShot]);
  useEffect(() => { shotsRef.current = shots; }, [shots]);

  // Sync external prop changes into local state (e.g. scrubbing from parent)
  useEffect(() => {
    if (!isPlaying) {
      playheadRef.current = playheadTime;
      setLocalPlayhead(playheadTime);
    }
  }, [playheadTime, isPlaying]);

  // ── Audio playback engine ─────────────────────────────────────────────
  // Pre-load HTMLAudioElements for each audio track, keyed by track id.
  const audioPoolRef = useRef({}); // { [trackId]: HTMLAudioElement }
  const audioTracksRef = useRef(audioTracks);
  useEffect(() => { audioTracksRef.current = audioTracks; }, [audioTracks]);

  // Build / update audio element pool when tracks or project change
  useEffect(() => {
    if (!projectSlug || audioTracks.length === 0) return;
    const pool = audioPoolRef.current;
    const activeIds = new Set();

    for (const track of audioTracks) {
      activeIds.add(track.id);
      if (!pool[track.id]) {
        const el = new Audio();
        el.preload = 'auto';
        el.src = `/kozmo-assets/${projectSlug}/${track.path}`;
        el.volume = 1.0;
        if (selectedDevice && typeof el.setSinkId === 'function') {
          el.setSinkId(selectedDevice).catch(() => {});
        }
        pool[track.id] = el;
      }
    }

    // Clean up removed tracks
    for (const id of Object.keys(pool)) {
      if (!activeIds.has(id)) {
        pool[id].pause();
        pool[id].src = '';
        delete pool[id];
      }
    }

    return () => {
      // Pause all on unmount
      for (const el of Object.values(audioPoolRef.current)) {
        el.pause();
      }
    };
  }, [audioTracks, projectSlug]);

  // Sync audio playback with play/pause state
  const isPlayingRef = useRef(isPlaying);
  useEffect(() => {
    isPlayingRef.current = isPlaying;
    const pool = audioPoolRef.current;
    const tracks = audioTracksRef.current;

    if (isPlaying) {
      // Start tracks that should be playing at current playhead position
      const t = playheadRef.current;
      for (const track of tracks) {
        const el = pool[track.id];
        if (!el) continue;
        if (t >= track.start_time && t < track.end_time) {
          el.currentTime = t - track.start_time;
          el.play().catch(() => {}); // ignore autoplay restrictions
        }
      }
    } else {
      // Pause all
      for (const el of Object.values(pool)) {
        el.pause();
      }
    }
  }, [isPlaying]);

  // Seek audio when scrubbing (non-playing seek)
  const seekAudioTo = useCallback((t) => {
    const pool = audioPoolRef.current;
    const tracks = audioTracksRef.current;
    for (const track of tracks) {
      const el = pool[track.id];
      if (!el) continue;
      if (t >= track.start_time && t < track.end_time) {
        el.currentTime = t - track.start_time;
      } else {
        el.pause();
        el.currentTime = 0;
      }
    }
  }, []);

  // Sync mute state to all audio elements
  useEffect(() => {
    for (const el of Object.values(audioPoolRef.current)) {
      el.muted = audioMuted;
    }
  }, [audioMuted]);

  // ── Audio output device selection (setSinkId) ─────────────────────────
  // Enumerate audio output devices on mount + when devices change
  useEffect(() => {
    async function enumerateOutputs() {
      try {
        // Need permission first — requesting mic briefly to unlock device labels
        await navigator.mediaDevices.getUserMedia({ audio: true })
          .then(stream => stream.getTracks().forEach(t => t.stop()))
          .catch(() => {});
        const devices = await navigator.mediaDevices.enumerateDevices();
        const outputs = devices.filter(d => d.kind === 'audiooutput');
        setAudioDevices(outputs);
      } catch {
        setAudioDevices([]);
      }
    }
    enumerateOutputs();
    navigator.mediaDevices?.addEventListener('devicechange', enumerateOutputs);
    return () => navigator.mediaDevices?.removeEventListener('devicechange', enumerateOutputs);
  }, []);

  // Route all audio elements to the selected output device
  useEffect(() => {
    const pool = audioPoolRef.current;
    for (const el of Object.values(pool)) {
      if (typeof el.setSinkId === 'function') {
        el.setSinkId(selectedDevice).catch(() => {});
      }
    }
  }, [selectedDevice, audioTracks]);

  // ── Track height calculations ──────────────────────────────────────────
  const totalTracksHeight = useMemo(() => {
    let h = 0;
    for (let i = 0; i < TRACK_COUNT; i++) {
      h += collapsedTracks[i] ? COLLAPSED_TRACK_HEIGHT : TRACK_HEIGHT;
    }
    if (audioTracks.length > 0) {
      h += collapsedTracks.audio ? COLLAPSED_TRACK_HEIGHT : AUDIO_TRACK_HEIGHT;
    }
    return h;
  }, [collapsedTracks, audioTracks.length]);

  // Clamp vertical scroll when tracks collapse
  useEffect(() => {
    setScrollY(y => Math.max(0, Math.min(y, Math.max(0, totalTracksHeight - 100))));
  }, [totalTracksHeight]);

  // ── Derived values ──────────────────────────────────────────────────────
  const totalDuration = useMemo(() => {
    let max = 0;
    for (const s of shots) max = Math.max(max, (s.startTime ?? 0) + s.duration);
    for (const a of audioTracks) max = Math.max(max, a.end_time || 0);
    return Math.max(max + 4, 20);
  }, [shots, audioTracks]);

  const totalWidth = totalDuration * zoom;

  const snapPoints = useMemo(() => {
    const pts = new Set([0]);
    for (const s of shots) {
      pts.add(s.startTime ?? 0);
      pts.add((s.startTime ?? 0) + s.duration);
    }
    return [...pts].sort((a, b) => a - b);
  }, [shots]);

  const sceneMarkers = useMemo(() => {
    const scenes = {};
    for (const s of shots) {
      const start = s.startTime ?? 0;
      const end = start + s.duration;
      if (!scenes[s.scene]) scenes[s.scene] = { start, end, scene: s.scene };
      else {
        scenes[s.scene].start = Math.min(scenes[s.scene].start, start);
        scenes[s.scene].end = Math.max(scenes[s.scene].end, end);
      }
    }
    return Object.values(scenes);
  }, [shots]);

  // ── Playhead → clip auto-selection ─────────────────────────────────────
  // Find which clip the playhead is over and select it.
  // Uses refs so it can be called from rAF without stale closures.
  const activeAudioRef = useRef(null);

  function selectClipAtPlayhead(t) {
    const currentShots = shotsRef.current;
    const currentSelected = selectedShotRef.current;
    // Find the topmost clip (highest track) whose time range contains t
    let best = null;
    for (const s of currentShots) {
      const start = s.startTime ?? 0;
      const end = start + s.duration;
      if (t >= start && t < end) {
        if (!best || (s.track ?? 0) > (best.track ?? 0)) best = s;
      }
    }
    if (best && best.id !== currentSelected) {
      selectedShotRef.current = best.id;
      onSelectShotRef.current(best.id);
    }

    // Track active audio clip under playhead
    const aTracks = audioTracksRef.current;
    let activeA = null;
    for (const at of aTracks) {
      if (t >= at.start_time && t < at.end_time) {
        activeA = at;
        break;
      }
    }
    if (activeA?.id !== activeAudioRef.current?.id) {
      activeAudioRef.current = activeA;
      setActiveAudioTrack(activeA);
    }
  }

  function snapTime(t, excludeId) {
    if (!snapEnabled) return Math.round(t * 10) / 10;
    for (const sp of snapPoints) {
      if (Math.abs(t - sp) < SNAP_THRESHOLD) return sp;
    }
    return Math.round(t * 10) / 10;
  }

  // ── Playback ────────────────────────────────────────────────────────────
  // rAF loop: DOM-only updates for 60fps (no React state in the hot loop)
  useEffect(() => {
    if (!isPlaying) {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      lastFrameRef.current = null;
      return;
    }

    let frameCount = 0;
    const tick = (timestamp) => {
      if (lastFrameRef.current === null) lastFrameRef.current = timestamp;
      const delta = (timestamp - lastFrameRef.current) / 1000;
      lastFrameRef.current = timestamp;

      playheadRef.current += delta;

      if (playheadRef.current >= totalDuration) {
        playheadRef.current = 0;
        onStopRef.current();
        return;
      }

      // DOM-only updates for 60fps visual movement
      const line = document.getElementById('kozmo-playhead-line');
      const tri = document.getElementById('kozmo-playhead-tri');
      const tc = document.getElementById('kozmo-timecode');
      const px = playheadRef.current * zoom;
      if (line) line.style.left = `${px}px`;
      if (tri) tri.style.left = `${px - 5}px`;
      if (tc) tc.textContent = formatTimecode(playheadRef.current);

      // Auto-select clip under playhead + audio scheduling (~10Hz, every 6 frames)
      if (frameCount++ % 6 === 0) {
        selectClipAtPlayhead(playheadRef.current);

        // Start/stop audio tracks as playhead enters/exits their ranges
        const t = playheadRef.current;
        const pool = audioPoolRef.current;
        const aTracks = audioTracksRef.current;
        for (const track of aTracks) {
          const el = pool[track.id];
          if (!el) continue;
          const inRange = t >= track.start_time && t < track.end_time;
          if (inRange && el.paused) {
            el.currentTime = t - track.start_time;
            el.play().catch(() => {});
          } else if (!inRange && !el.paused) {
            el.pause();
          }
        }
      }

      rafRef.current = requestAnimationFrame(tick);
    };

    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [isPlaying, totalDuration, zoom]);

  // When playback stops, sync the final position back to React state
  const prevPlayingRef = useRef(false);
  useEffect(() => {
    if (prevPlayingRef.current && !isPlaying) {
      // Just stopped — sync ref → React state
      setLocalPlayhead(playheadRef.current);
      onPlayheadChangeRef.current(playheadRef.current);
    }
    prevPlayingRef.current = isPlaying;
  }, [isPlaying]);

  // Auto-scroll to keep playhead visible during playback
  useEffect(() => {
    if (!isPlaying) return;
    const iv = setInterval(() => {
      setScrollX(prev => {
        const px = playheadRef.current * zoom - prev;
        const viewW = (trackAreaRef.current?.clientWidth || 600) - LABEL_WIDTH;
        if (px > viewW - 60) return playheadRef.current * zoom - viewW + 100;
        return prev;
      });
    }, 200);
    return () => clearInterval(iv);
  }, [isPlaying, zoom]);

  // ── Mouse: scrub / drag / trim ──────────────────────────────────────────
  const getTimeFromClientX = useCallback((clientX) => {
    const rect = trackAreaRef.current?.getBoundingClientRect();
    if (!rect) return 0;
    // clientX relative to trackArea left edge, minus the label column, plus scroll offset
    return Math.max(0, (clientX - rect.left - LABEL_WIDTH + scrollX) / zoom);
  }, [zoom, scrollX]);

  const handleMouseMove = useCallback((e) => {
    if (scrubbing) {
      const t = getTimeFromClientX(e.clientX);
      playheadRef.current = t;
      setLocalPlayhead(t);
      onPlayheadChange(t);
      selectClipAtPlayhead(t);
      seekAudioTo(t);
      return;
    }
    if (!dragging) return;

    const dx = e.clientX - dragging.startX;
    const timeDelta = dx / zoom;

    if (dragging.type === 'move') {
      let newStart = Math.max(0, dragging.origStart + timeDelta);
      newStart = snapTime(newStart, dragging.shotId);
      // Track detection from mouse Y
      const rect = trackAreaRef.current?.getBoundingClientRect();
      const trackAreaTop = (rect?.top || 0) + SCENE_MARKER_HEIGHT + RULER_HEIGHT;
      const relY = e.clientY - trackAreaTop;
      const newTrack = Math.max(0, Math.min(TRACK_COUNT - 1, Math.floor(relY / TRACK_HEIGHT)));
      onClipMove(dragging.shotId, newStart, newTrack);
    } else if (dragging.type === 'trimL') {
      const maxTrim = dragging.origDur - MIN_CLIP_DURATION;
      const trimAmt = Math.max(-dragging.origStart, Math.min(maxTrim, timeDelta));
      const snapped = snapTime(dragging.origStart + trimAmt, dragging.shotId);
      const actualTrim = snapped - dragging.origStart;
      onClipTrim(dragging.shotId, snapped, Math.max(MIN_CLIP_DURATION, dragging.origDur - actualTrim));
    } else if (dragging.type === 'trimR') {
      const newDur = snapTime(Math.max(MIN_CLIP_DURATION, dragging.origDur + timeDelta), dragging.shotId);
      onClipTrim(dragging.shotId, dragging.origStart, newDur);
    }
  }, [scrubbing, dragging, zoom, getTimeFromClientX, snapTime, onPlayheadChange, onClipMove, onClipTrim, seekAudioTo]);

  const handleMouseUp = useCallback(() => {
    setScrubbing(false);
    setDragging(null);
  }, []);

  useEffect(() => {
    if (!scrubbing && !dragging) return;
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [scrubbing, dragging, handleMouseMove, handleMouseUp]);

  // ── Zoom / scroll ───────────────────────────────────────────────────────
  const handleWheel = useCallback((e) => {
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      setZoom(z => Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, z - e.deltaY * 0.3)));
    } else if (e.shiftKey) {
      // Shift+scroll = horizontal pan
      e.preventDefault();
      setScrollX(x => Math.max(0, Math.min(totalWidth - 200, x + e.deltaY)));
    } else {
      // Native scroll: deltaX = horizontal, deltaY = vertical
      setScrollX(x => Math.max(0, Math.min(totalWidth - 200, x + e.deltaX)));
      setScrollY(y => Math.max(0, y + e.deltaY));
    }
  }, [totalWidth]);

  // ── Resize handle ───────────────────────────────────────────────────────
  const handleResizeDown = useCallback((e) => {
    e.preventDefault();
    const startY = e.clientY;
    const startH = timelineHeight;
    const onMove = (ev) => {
      const delta = startY - ev.clientY;
      onResizeHeight(Math.max(MIN_TIMELINE_HEIGHT, Math.min(MAX_TIMELINE_HEIGHT, startH + delta)));
    };
    const onUp = () => {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
    };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  }, [timelineHeight, onResizeHeight]);

  // ── Keyboard shortcuts ──────────────────────────────────────────────────
  const seekTo = useCallback((t) => {
    playheadRef.current = t;
    setLocalPlayhead(t);
    onPlayheadChange(t);
    selectClipAtPlayhead(t);
    seekAudioTo(t);
  }, [onPlayheadChange, seekAudioTo]);

  // Zoom-to-fit: auto-calculate zoom to show entire duration in current viewport
  const zoomToFit = useCallback(() => {
    const viewW = (trackAreaRef.current?.clientWidth || 600) - LABEL_WIDTH;
    if (totalDuration > 0 && viewW > 0) {
      const fitZoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, viewW / totalDuration));
      setZoom(fitZoom);
      setScrollX(0);
    }
  }, [totalDuration]);

  // Track collapse toggle
  const toggleTrack = useCallback((trackKey) => {
    setCollapsedTracks(prev => ({ ...prev, [trackKey]: !prev[trackKey] }));
  }, []);

  // Get effective height for a track
  const getTrackHeight = useCallback((trackKey) => {
    if (collapsedTracks[trackKey]) return COLLAPSED_TRACK_HEIGHT;
    return trackKey === 'audio' ? AUDIO_TRACK_HEIGHT : TRACK_HEIGHT;
  }, [collapsedTracks]);

  const handleKeyDown = useCallback((e) => {
    if (e.code === 'Space') {
      e.preventDefault();
      onPlayPause();
    }
    if (e.code === 'Home') seekTo(0);
    if (e.code === 'End') seekTo(totalDuration);
    if (e.code === 'ArrowLeft') seekTo(Math.max(0, playheadRef.current - 1 / FPS));
    if (e.code === 'ArrowRight') seekTo(Math.min(totalDuration, playheadRef.current + 1 / FPS));
    if ((e.code === 'Delete' || e.code === 'Backspace') && selectedShot) {
      onClipDelete(selectedShot);
    }
    if (e.code === 'KeyM') setAudioMuted(m => !m);
    if (e.code === 'KeyF' && !e.ctrlKey && !e.metaKey) zoomToFit();
  }, [totalDuration, selectedShot, onPlayPause, seekTo, onClipDelete, zoomToFit]);

  // ── Clip drag start ─────────────────────────────────────────────────────
  const handleClipDragStart = useCallback((shotId, type, startX) => {
    const s = shots.find(sh => sh.id === shotId);
    if (!s) return;
    setDragging({
      shotId, type, startX,
      origStart: s.startTime ?? 0, origDur: s.duration, origTrack: s.track ?? 0,
    });
  }, [shots]);

  // ── Scrub start on ruler ────────────────────────────────────────────────
  const handleScrub = useCallback((t) => {
    setScrubbing(true);
    playheadRef.current = t;
    setLocalPlayhead(t);
    onPlayheadChange(t);
    selectClipAtPlayhead(t);
    seekAudioTo(t);
    if (isPlaying) onPlayPause();
  }, [onPlayheadChange, isPlaying, onPlayPause, seekAudioTo]);

  const selectedShotObj = shots.find(s => s.id === selectedShot);

  // ── Render ──────────────────────────────────────────────────────────────
  return (
    <div
      style={{
        height: timelineHeight, display: 'flex', flexDirection: 'column', flexShrink: 0,
        background: 'rgba(6, 6, 10, 0.6)', backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)',
        fontFamily: "'JetBrains Mono', 'SF Mono', 'Fira Code', monospace",
        color: '#aaa', userSelect: 'none',
      }}
      tabIndex={0}
      onKeyDown={handleKeyDown}
    >
      {/* Resize Handle */}
      <ResizeHandle onMouseDown={handleResizeDown} />

      {/* Transport Bar */}
      <div style={{
        height: TRANSPORT_HEIGHT, display: 'flex', alignItems: 'center',
        padding: '0 10px', gap: 4, borderBottom: '1px solid #141420', flexShrink: 0,
      }}>
        <TransportBtn icon="⏮" onClick={() => seekTo(0)} title="Start" />
        <TransportBtn icon="◀" onClick={() => seekTo(Math.max(0, playheadRef.current - 1))} title="Back 1s" />
        <TransportBtn
          icon={isPlaying ? '⏸' : '▶'} accent
          onClick={onPlayPause}
          title="Play/Pause (Space)"
        />
        <TransportBtn icon="▶" onClick={() => seekTo(Math.min(totalDuration, playheadRef.current + 1))} title="Fwd 1s" />
        <TransportBtn icon="⏭" onClick={() => seekTo(totalDuration)} title="End" />

        {/* Timecode */}
        <div id="kozmo-timecode" style={{
          marginLeft: 8, padding: '3px 10px', background: '#0a0a12',
          border: '1px solid #1a1a24', borderRadius: 3,
          fontSize: 12, fontWeight: 700, color: '#e8e8f0', letterSpacing: 1.5,
          minWidth: 85, textAlign: 'center', fontVariantNumeric: 'tabular-nums',
        }}>
          {formatTimecode(localPlayhead)}
        </div>
        <span style={{ color: '#333', fontSize: 8, marginLeft: 4 }}>24fps</span>

        {/* Audio mute toggle */}
        {audioTracks.length > 0 && (
          <div
            onClick={() => setAudioMuted(m => !m)}
            title={audioMuted ? 'Unmute audio (M)' : 'Mute audio (M)'}
            style={{
              marginLeft: 8, display: 'flex', alignItems: 'center', gap: 3,
              cursor: 'pointer', padding: '2px 6px', borderRadius: 3,
              border: `1px solid ${audioMuted ? '#3a3a4e' : '#22c55e33'}`,
              background: audioMuted ? 'transparent' : 'rgba(34, 197, 94, 0.06)',
            }}
          >
            <span style={{ fontSize: 10 }}>{audioMuted ? '🔇' : '🔊'}</span>
            <span style={{ fontSize: 7, color: audioMuted ? '#555' : '#22c55e', letterSpacing: 1 }}>
              AUDIO
            </span>
          </div>
        )}

        {/* Audio output device selector */}
        {audioTracks.length > 0 && audioDevices.length > 1 && (
          <select
            value={selectedDevice}
            onChange={e => setSelectedDevice(e.target.value)}
            title="Audio output device"
            style={{
              marginLeft: 4, padding: '2px 4px', fontSize: 7, fontFamily: 'inherit',
              background: '#0e0e18', color: '#888', border: '1px solid #2a2a3a',
              borderRadius: 3, outline: 'none', cursor: 'pointer',
              maxWidth: 140, letterSpacing: 0.5,
            }}
          >
            {audioDevices.map(d => (
              <option key={d.deviceId} value={d.deviceId}>
                {d.label || `Output ${d.deviceId.slice(0, 8)}`}
              </option>
            ))}
          </select>
        )}

        <div style={{ flex: 1 }} />

        {/* Zoom-to-fit */}
        <TransportBtn icon="⊞" onClick={zoomToFit} title="Zoom to fit (F)" />

        {/* Zoom */}
        <span style={{ color: '#444', fontSize: 8, marginRight: 3, marginLeft: 6 }}>ZOOM</span>
        <input type="range" min={MIN_ZOOM} max={MAX_ZOOM} value={zoom}
          onChange={e => setZoom(Number(e.target.value))}
          style={{
            width: 64, height: 2, appearance: 'none',
            background: '#1a1a2e', borderRadius: 2, outline: 'none', accentColor: '#c8ff00',
          }}
        />
        <span style={{ color: '#555', fontSize: 8, minWidth: 28, textAlign: 'right' }}>{Math.round(zoom)}px</span>

        {/* Snap */}
        <div
          onClick={() => setSnapEnabled(p => !p)}
          style={{ marginLeft: 8, display: 'flex', alignItems: 'center', gap: 3, cursor: 'pointer' }}
        >
          <div style={{
            width: 5, height: 5, borderRadius: '50%',
            background: snapEnabled ? '#c8ff00' : '#333',
            transition: 'background 0.15s',
          }} />
          <span style={{ color: snapEnabled ? '#888' : '#444', fontSize: 8 }}>SNAP</span>
        </div>
      </div>

      {/* Track Area */}
      <div ref={trackAreaRef} style={{ flex: 1, display: 'flex', overflow: 'hidden', position: 'relative' }}
        onWheel={handleWheel}
      >
        {/* Track Labels — vertical scrollable, synced with track content */}
        <div style={{
          width: LABEL_WIDTH, flexShrink: 0, background: '#0a0a12',
          borderRight: '1px solid #1a1a24', zIndex: 3,
          overflow: 'hidden',
        }}>
          {/* Fixed ruler spacer */}
          <div style={{ height: SCENE_MARKER_HEIGHT + RULER_HEIGHT, flexShrink: 0 }} />
          {/* Scrollable label area synced with vertical scroll */}
          <div style={{ transform: `translateY(${-scrollY}px)` }}>
            {Array.from({ length: TRACK_COUNT }).map((_, i) => {
              const collapsed = !!collapsedTracks[i];
              const h = collapsed ? COLLAPSED_TRACK_HEIGHT : TRACK_HEIGHT;
              return (
                <div key={i}
                  onClick={() => toggleTrack(i)}
                  style={{
                    height: h, borderBottom: '1px solid #111118',
                    display: 'flex', alignItems: 'center', padding: '0 6px', gap: 4,
                    cursor: 'pointer', transition: 'height 0.15s ease',
                  }}
                  title={collapsed ? 'Click to expand' : 'Click to collapse'}
                >
                  <span style={{ fontSize: 7, color: '#333', flexShrink: 0, width: 8 }}>
                    {collapsed ? '▸' : '▾'}
                  </span>
                  <div style={{
                    width: 3, height: collapsed ? 10 : 20, borderRadius: 2,
                    background: `${TRACK_COLORS[i]}55`, transition: 'height 0.15s ease',
                  }} />
                  {!collapsed ? (
                    <div style={{ overflow: 'hidden', minWidth: 0 }}>
                      <div style={{ fontSize: 7, color: '#555', fontWeight: 600, letterSpacing: 1 }}>
                        {TRACK_LABELS[i]}
                      </div>
                      <div style={{ fontSize: 7, color: '#2a2a3a', marginTop: 1 }}>
                        {shots.filter(s => (s.track ?? 0) === i).length} clips
                      </div>
                    </div>
                  ) : (
                    <span style={{ fontSize: 6, color: '#444', letterSpacing: 1, whiteSpace: 'nowrap' }}>
                      {TRACK_LABELS[i].split(' — ')[0]}
                    </span>
                  )}
                </div>
              );
            })}
            {/* Audio track label */}
            {audioTracks.length > 0 && (() => {
              const collapsed = !!collapsedTracks.audio;
              const h = collapsed ? COLLAPSED_TRACK_HEIGHT : AUDIO_TRACK_HEIGHT;
              return (
                <div
                  onClick={() => toggleTrack('audio')}
                  style={{
                    height: h, borderBottom: '1px solid #111118',
                    borderTop: '1px solid #22c55e22',
                    display: 'flex', alignItems: 'center', padding: '0 6px', gap: 4,
                    cursor: 'pointer', transition: 'height 0.15s ease',
                  }}
                  title={collapsed ? 'Click to expand' : 'Click to collapse'}
                >
                  <span style={{ fontSize: 7, color: '#333', flexShrink: 0, width: 8 }}>
                    {collapsed ? '▸' : '▾'}
                  </span>
                  <div style={{
                    width: 3, height: collapsed ? 8 : 16, borderRadius: 2,
                    background: '#22c55e55', transition: 'height 0.15s ease',
                  }} />
                  {!collapsed ? (
                    <div style={{ overflow: 'hidden', minWidth: 0 }}>
                      <div style={{ fontSize: 7, color: '#22c55e', fontWeight: 600, letterSpacing: 1 }}>
                        A1 — AUDIO
                      </div>
                      <div style={{ fontSize: 7, color: '#2a2a3a', marginTop: 1 }}>
                        {audioTracks.length} clips
                      </div>
                    </div>
                  ) : (
                    <span style={{ fontSize: 6, color: '#22c55e88', letterSpacing: 1 }}>A1</span>
                  )}
                </div>
              );
            })()}
          </div>
        </div>

        {/* Scrollable track content */}
        <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
          {/* Everything inside shifts by -scrollX */}
          <div style={{
            position: 'relative', width: totalWidth,
            transform: `translateX(${-scrollX}px)`,
          }}>
            {/* Scene markers — fixed at top (no vertical scroll) */}
            <div style={{
              height: SCENE_MARKER_HEIGHT, position: 'relative', overflow: 'hidden',
            }}>
              {sceneMarkers.map(m => {
                const c = sceneColor(m.scene);
                return (
                  <div key={m.scene} style={{
                    position: 'absolute', left: m.start * zoom, width: (m.end - m.start) * zoom,
                    height: '100%',
                    background: `${c}08`, borderBottom: `2px solid ${c}33`,
                    display: 'flex', alignItems: 'center', paddingLeft: 5,
                  }}>
                    <span style={{ fontSize: 7, color: c, fontWeight: 700, letterSpacing: 1.5 }}>
                      {m.scene}
                    </span>
                  </div>
                );
              })}
            </div>

            {/* Time ruler — fixed at top (no vertical scroll) */}
            <TimeRuler zoom={zoom} totalDuration={totalDuration} onScrub={handleScrub} />

            {/* Playhead triangle on ruler */}
            <div id="kozmo-playhead-tri" style={{
              position: 'absolute', top: SCENE_MARKER_HEIGHT,
              left: localPlayhead * zoom - 5,
              width: 0, height: 0,
              borderLeft: '5px solid transparent', borderRight: '5px solid transparent',
              borderTop: '7px solid #c8ff00', zIndex: 6, pointerEvents: 'none',
              filter: 'drop-shadow(0 0 2px rgba(200,255,0,0.4))',
            }} />

            {/* Track lanes — vertically scrollable */}
            <div style={{ position: 'relative', overflow: 'hidden' }}>
              <div style={{ transform: `translateY(${-scrollY}px)`, position: 'relative' }}>
                {/* Track backgrounds */}
                {Array.from({ length: TRACK_COUNT }).map((_, i) => {
                  const collapsed = !!collapsedTracks[i];
                  const h = collapsed ? COLLAPSED_TRACK_HEIGHT : TRACK_HEIGHT;
                  return (
                    <div key={i} style={{
                      height: h, borderBottom: '1px solid #111118',
                      background: i % 2 === 0 ? '#0a0a10' : '#09090e',
                      transition: 'height 0.15s ease',
                    }} />
                  );
                })}

                {/* Grid lines — adaptive interval based on zoom */}
                <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
                  {(() => {
                    const gridStep = zoom >= 20 ? 1 : zoom >= 8 ? 5 : zoom >= 4 ? 10 : 30;
                    const gridMajor = gridStep * 5;
                    const lines = [];
                    for (let i = 0; i <= totalDuration; i += gridStep) {
                      lines.push(
                        <div key={i} style={{
                          position: 'absolute', left: i * zoom, top: 0, width: 1, height: '100%',
                          background: i % gridMajor === 0 ? '#1a1a2408' : '#12121a05',
                        }} />
                      );
                    }
                    return lines;
                  })()}
                </div>

                {/* Shot clips — use cumulative Y offset for collapsed tracks */}
                <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
                  {shots.map(s => {
                    // Calculate Y offset for clip based on collapsed tracks above it
                    const track = s.track ?? 0;
                    let yOffset = 0;
                    for (let t = 0; t < track; t++) {
                      yOffset += collapsedTracks[t] ? COLLAPSED_TRACK_HEIGHT : TRACK_HEIGHT;
                    }
                    const trackH = collapsedTracks[track] ? COLLAPSED_TRACK_HEIGHT : TRACK_HEIGHT;
                    const clipHidden = collapsedTracks[track];
                    return (
                      <ShotClip key={s.id} shot={{ ...s, _yOffset: yOffset, _trackH: trackH }}
                        zoom={zoom}
                        selected={s.id === selectedShot} hovered={s.id === hoveredId}
                        statusConfig={statusConfig}
                        onSelect={() => onSelectShot(s.id)}
                        onHover={h => setHoveredId(h ? s.id : null)}
                        onDragStart={(type, startX) => handleClipDragStart(s.id, type, startX)}
                        collapsed={clipHidden}
                      />
                    );
                  })}
                </div>

                {/* Audio track row */}
                {audioTracks.length > 0 && (() => {
                  const collapsed = !!collapsedTracks.audio;
                  const h = collapsed ? COLLAPSED_TRACK_HEIGHT : AUDIO_TRACK_HEIGHT;
                  return (
                    <div style={{
                      height: h, position: 'relative', zIndex: 3,
                      borderTop: '1px solid #22c55e22',
                      background: '#08080e',
                      transition: 'height 0.15s ease',
                      overflow: 'hidden',
                    }}>
                      {!collapsed && audioTracks.map(track => {
                        const left = track.start_time * zoom;
                        const width = Math.max(track.duration * zoom, 2);
                        const color = VOICE_COLORS[track.voice] || '#5a5a72';
                        const isActive = activeAudioTrack?.id === track.id;
                        const hasScript = !!track.document_slug;
                        return (
                          <div
                            key={track.id}
                            title={`${(track.voice || '?').toUpperCase()}: ${(track.visual_prompt || track.text || track.filename || '').slice(0, 100)}`}
                            onClick={() => {
                              seekTo(track.start_time);
                            }}
                            onContextMenu={(e) => {
                              e.preventDefault();
                              e.stopPropagation();
                              setContextMenu({ x: e.clientX, y: e.clientY, track });
                            }}
                            style={{
                              position: 'absolute', left, top: 4, width,
                              height: AUDIO_TRACK_HEIGHT - 8, borderRadius: 3,
                              background: isActive ? `${color}25` : `${color}15`,
                              border: `1px solid ${isActive ? `${color}66` : `${color}35`}`,
                              overflow: 'hidden',
                              cursor: 'pointer',
                              transition: 'background 0.15s, border-color 0.15s',
                            }}
                          >
                            <div style={{
                              position: 'absolute', left: 0, top: 0, bottom: 0,
                              width: 3, background: color, borderRadius: '3px 0 0 3px',
                            }} />
                            {width > 35 && (
                              <span style={{
                                position: 'absolute', left: 7, top: 3, fontSize: 7,
                                color, textTransform: 'uppercase', letterSpacing: 1,
                                fontWeight: 700,
                              }}>
                                {track.voice || '?'}
                              </span>
                            )}
                            {width > 70 && (
                              <span style={{
                                position: 'absolute', left: 7, bottom: 3, right: 24,
                                fontSize: 7, color: isActive ? '#888' : '#555',
                                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                              }}>
                                {(track.text || track.filename || '').slice(0, 50)}
                              </span>
                            )}
                            {/* Generate button — always visible on active clip, on hover for others */}
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                setGenerateTrack(track);
                              }}
                              title="Generate image from script"
                              style={{
                                position: 'absolute', right: 2, top: '50%', transform: 'translateY(-50%)',
                                width: 20, height: 20, borderRadius: 4,
                                border: `1px solid ${isActive ? '#c8ff0055' : '#c8ff0033'}`,
                                background: isActive ? 'rgba(200,255,0,0.15)' : 'rgba(200,255,0,0.06)',
                                color: '#c8ff00', fontSize: 10,
                                cursor: 'pointer', fontFamily: 'inherit',
                                display: 'flex', alignItems: 'center', justifyContent: 'center',
                                opacity: isActive ? 1 : 0.5,
                                transition: 'opacity 0.15s, background 0.15s',
                              }}
                              onMouseEnter={(e) => { e.currentTarget.style.opacity = '1'; e.currentTarget.style.background = 'rgba(200,255,0,0.25)'; }}
                              onMouseLeave={(e) => { e.currentTarget.style.opacity = isActive ? '1' : '0.5'; e.currentTarget.style.background = isActive ? 'rgba(200,255,0,0.15)' : 'rgba(200,255,0,0.06)'; }}
                            >
                              ◎
                            </button>
                          </div>
                        );
                      })}
                    </div>
                  );
                })()}

                {/* Playhead line */}
                <div id="kozmo-playhead-line" style={{
                  position: 'absolute', top: 0, bottom: 0, width: 1,
                  left: localPlayhead * zoom,
                  background: '#c8ff00', boxShadow: '0 0 6px rgba(200,255,0,0.3)',
                  zIndex: 10, pointerEvents: 'none',
                }} />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Detail Bar */}
      <DetailBar shot={selectedShotObj} statusConfig={statusConfig}
        activeAudioTrack={activeAudioTrack} onNavigateToScript={onNavigateToScript}
        onGenerateFromScript={(track) => setGenerateTrack(track)} />

      {/* Context Menu */}
      {contextMenu && (
        <AudioContextMenu
          x={contextMenu.x} y={contextMenu.y} track={contextMenu.track}
          onClose={() => setContextMenu(null)}
          onGenerate={() => setGenerateTrack(contextMenu.track)}
          onNavigate={(docSlug, containerSlug) => onNavigateToScript?.(docSlug, containerSlug)}
        />
      )}

      {/* Generate From Script Dialog */}
      {generateTrack && (
        <GenerateFromScript
          track={generateTrack}
          projectSlug={projectSlug}
          onClose={() => setGenerateTrack(null)}
          onShotAdd={onShotAdd}
          onShotUpdate={onShotUpdate}
        />
      )}
    </div>
  );
}
