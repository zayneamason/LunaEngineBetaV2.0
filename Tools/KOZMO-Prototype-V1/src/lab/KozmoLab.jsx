/**
 * KOZMO LAB (Studio) — Production Mode
 *
 * Layout: 3-panel + bottom timeline
 *   LEFT:   Shot list (hero frame previews, camera info strips)
 *   CENTER: Hero frame canvas (21:9 CinemaScope, viewfinder overlay)
 *   RIGHT:  Tabbed controls (CAMERA | POST | AGENTS)
 *   BOTTOM: Mini timeline (proportional shot blocks, status colors)
 *
 * Camera data imported from config/cameras.js.
 * Shots use local state — will wire to shot entity API when available.
 * Design adapted from ClaudeArtifacts/kozmo_studio.jsx
 */
import React, { useState, useCallback, useMemo, useEffect } from 'react';
import { useKozmo } from '../KozmoProvider';
import {
  CAMERA_BODIES, LENS_PROFILES, CAMERA_MOVEMENTS, FILM_STOCKS,
} from '../config/cameras';

// --- Movement Icons (supplement cameras.js data) ---
const MOVEMENT_ICONS = {
  static: '◻', dolly_in: '→◎', dolly_out: '◎→',
  pan_left: '←', pan_right: '→', tilt_up: '↑', tilt_down: '↓',
  crane_up: '⤴', crane_down: '⤵', orbit_cw: '↻', orbit_ccw: '↺',
  handheld: '〰', fpv: '✈', steadicam: '≋',
};

// --- Status Config ---
const STATUS_CONFIG = {
  idea: { color: '#3a3a50', label: 'IDEA', bg: '#1a1a24' },
  draft: { color: '#6b7280', label: 'DRAFT', bg: '#1f2028' },
  rendering: { color: '#f59e0b', label: 'RENDERING', bg: '#2a2210' },
  hero_approved: { color: '#c8ff00', label: 'HERO ✓', bg: '#1a2a10' },
  approved: { color: '#4ade80', label: 'APPROVED', bg: '#102a18' },
  locked: { color: '#818cf8', label: 'LOCKED', bg: '#1a1a30' },
};

// --- Default Shot List (local state until shot API exists) ---
const DEFAULT_SHOTS = [
  { id: 'sh001', scene: 'S1', name: 'Establishing — Wide', type: 'wide', status: 'draft', heroFrame: null, camera: 'arri_alexa35', lens: 'panavision_c', focal: 40, aperture: 2.8, movement: ['dolly_in'], duration: 3, filmStock: 'kodak_5219' },
  { id: 'sh002', scene: 'S1', name: 'Character — Close Up', type: 'close', status: 'idea', heroFrame: null, camera: 'arri_alexa35', lens: 'cooke_s7i', focal: 85, aperture: 1.4, movement: ['static'], duration: 2, filmStock: 'kodak_5219' },
  { id: 'sh003', scene: 'S2', name: 'Action — Tracking', type: 'medium', status: 'idea', heroFrame: null, camera: 'red_v_raptor', lens: 'zeiss_supreme', focal: 35, aperture: 2.0, movement: ['steadicam'], duration: 4, filmStock: 'kodak_5207' },
];

// --- Agent Activity Feed (mock) ---
const INITIAL_FEED = [
  { time: 'now', agent: 'Luna', action: 'Studio mode active. Camera settings ready for Eden dispatch.', type: 'memory' },
];

// ============================================================================
// COMPONENTS
// ============================================================================

function Knob({ label, value, min, max, unit, accent = '#c8ff00' }) {
  const percentage = ((value - min) / (max - min)) * 100;
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, minWidth: 64,
    }}>
      <div style={{
        width: 48, height: 48, borderRadius: '50%', position: 'relative',
        background: `conic-gradient(${accent} ${percentage * 2.7}deg, #1a1a24 0deg)`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        cursor: 'pointer',
      }}>
        <div style={{
          width: 38, height: 38, borderRadius: '50%', background: '#0d0d14',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 11, fontWeight: 600, color: '#e8e8f0',
          fontFamily: "'SF Mono', monospace",
        }}>
          {value}{unit || ''}
        </div>
      </div>
      <span style={{
        fontSize: 8, color: '#4a4a60', textTransform: 'uppercase', letterSpacing: 1.5,
      }}>{label}</span>
    </div>
  );
}

function PillSelect({ options, selected, onChange }) {
  return (
    <div style={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
      {options.map(opt => {
        const id = opt.id || opt;
        const isActive = Array.isArray(selected) ? selected.includes(id) : selected === id;
        return (
          <button key={id} onClick={() => onChange(id)} style={{
            padding: '3px 8px', fontSize: 9, borderRadius: 4,
            border: `1px solid ${isActive ? '#c8ff00' : '#2a2a3a'}`,
            background: isActive ? 'rgba(200,255,0,0.08)' : 'transparent',
            color: isActive ? '#c8ff00' : '#6b6b80',
            cursor: 'pointer', fontFamily: 'inherit', transition: 'all 0.15s',
            letterSpacing: 0.5,
          }}>
            {MOVEMENT_ICONS[id] ? `${MOVEMENT_ICONS[id]} ` : ''}{opt.name || opt}
          </button>
        );
      })}
    </div>
  );
}

function ShotCard({ shot, selected, onClick }) {
  const st = STATUS_CONFIG[shot.status] || STATUS_CONFIG.idea;
  const camera = CAMERA_BODIES.find(c => c.id === shot.camera);
  const lens = LENS_PROFILES.find(l => l.id === shot.lens);
  const movements = shot.movement.map(m => CAMERA_MOVEMENTS.find(cm => cm.id === m));

  return (
    <div onClick={onClick} style={{
      background: selected ? '#16162a' : '#0f0f18',
      border: `1px solid ${selected ? '#c8ff0040' : '#1a1a24'}`,
      borderRadius: 8, padding: 10, cursor: 'pointer',
      transition: 'all 0.2s', position: 'relative', overflow: 'hidden',
    }}>
      {/* Hero Frame Preview */}
      <div style={{
        height: 72, borderRadius: 6, marginBottom: 8, overflow: 'hidden',
        background: shot.heroFrame ? 'none' : 'linear-gradient(135deg, #1a1a2e 0%, #0d0d18 100%)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        border: '1px solid #1a1a24',
      }}>
        {shot.heroFrame ? (
          <img src={shot.heroFrame} alt="" style={{
            width: '100%', height: '100%', objectFit: 'cover',
          }} />
        ) : (
          <span style={{ fontSize: 9, color: '#2a2a3a', letterSpacing: 2 }}>NO HERO FRAME</span>
        )}
      </div>

      {/* Header */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start',
        marginBottom: 6,
      }}>
        <div>
          <div style={{ fontSize: 10, color: '#e8e8f0', fontWeight: 600, marginBottom: 2 }}>
            {shot.name}
          </div>
          <div style={{ fontSize: 8, color: '#4a4a60' }}>
            {shot.scene} · {shot.type.toUpperCase()} · {shot.duration}s
          </div>
        </div>
        <span style={{
          fontSize: 7, padding: '2px 6px', borderRadius: 3, fontWeight: 700,
          background: st.bg, color: st.color, letterSpacing: 1,
        }}>{st.label}</span>
      </div>

      {/* Camera Info Strip */}
      <div style={{
        display: 'flex', gap: 6, fontSize: 8, color: '#4a4a60',
        padding: '4px 0', borderTop: '1px solid #1a1a24',
        marginTop: 4, paddingTop: 6,
      }}>
        <span style={{ color: '#6b6b80' }}>{camera?.name.split(' ').pop()}</span>
        <span>·</span>
        <span>{lens?.name.split(' ').pop()}</span>
        <span>·</span>
        <span>{shot.focal}mm</span>
        <span>·</span>
        <span>ƒ/{shot.aperture}</span>
        <span>·</span>
        <span>{movements.map(m => MOVEMENT_ICONS[m?.id] || m?.name).join(' ')}</span>
      </div>
    </div>
  );
}

function AgentFeedItem({ item }) {
  const colors = {
    routing: '#c8ff00', consistency: '#4ade80',
    post: '#f59e0b', memory: '#818cf8',
  };
  return (
    <div style={{
      display: 'flex', gap: 8, padding: '6px 0', borderBottom: '1px solid #1a1a2408',
    }}>
      <span style={{
        fontSize: 8, color: '#3a3a50', minWidth: 28, fontVariantNumeric: 'tabular-nums',
      }}>{item.time}</span>
      <span style={{
        fontSize: 8, color: colors[item.type] || '#6b6b80', minWidth: 52, fontWeight: 600,
      }}>{item.agent}</span>
      <span style={{ fontSize: 9, color: '#6b6b80', lineHeight: 1.4 }}>{item.action}</span>
    </div>
  );
}

// ============================================================================
// MAIN STUDIO
// ============================================================================

export default function KozmoLab({ savedState, onSaveState }) {
  const { activeProject, agentStatus, buildPrompt } = useKozmo();

  // Initialize from savedState if available
  const [shots, setShots] = useState(savedState?.shots?.length > 0 ? savedState.shots : DEFAULT_SHOTS);
  const [selectedShot, setSelectedShot] = useState(savedState?.selectedShot || 'sh001');
  const [rightPanel, setRightPanel] = useState(savedState?.rightPanel || 'camera');
  const [promptInput, setPromptInput] = useState('');
  const [generating, setGenerating] = useState(false);
  const [agentFeed, setAgentFeed] = useState(INITIAL_FEED);
  const [generatedPrompt, setGeneratedPrompt] = useState(savedState?.generatedPrompt || '');
  const [isGeneratingPrompt, setIsGeneratingPrompt] = useState(false);
  const [promptError, setPromptError] = useState(null);

  // Save state to machine whenever key state changes
  useEffect(() => {
    if (onSaveState) {
      onSaveState({
        selectedShot,
        shots,
        rightPanel,
        generatedPrompt,
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedShot, shots, rightPanel, generatedPrompt]);

  const shot = shots.find(s => s.id === selectedShot) || shots[0];
  const camera = CAMERA_BODIES.find(c => c.id === shot.camera);
  const lens = LENS_PROFILES.find(l => l.id === shot.lens);
  const filmStock = FILM_STOCKS.find(f => f.id === shot.filmStock);

  const updateShot = useCallback((field, value) => {
    setShots(prev => prev.map(s =>
      s.id === selectedShot ? { ...s, [field]: value } : s
    ));
  }, [selectedShot]);

  const addShot = useCallback(() => {
    const num = shots.length + 1;
    const id = `sh${String(num).padStart(3, '0')}`;
    setShots(prev => [...prev, {
      id, scene: `S${Math.ceil(num / 2)}`, name: `New Shot ${num}`,
      type: 'medium', status: 'idea', heroFrame: null,
      camera: 'arri_alexa35', lens: 'cooke_s7i', focal: 50, aperture: 2.0,
      movement: ['static'], duration: 3, filmStock: 'kodak_5219',
    }]);
    setSelectedShot(id);
  }, [shots]);

  const handleGenerate = useCallback(async () => {
    if (generating) return;
    const prompt = generatedPrompt || promptInput;
    if (!prompt) {
      setAgentFeed(prev => [{
        time: 'now', agent: 'Luna',
        action: 'No prompt available. Generate a prompt first using the AGENTS tab, or type one manually.',
        type: 'memory',
      }, ...prev]);
      return;
    }

    setGenerating(true);
    updateShot('status', 'rendering');
    setAgentFeed(prev => [{
      time: 'now', agent: 'Chiba',
      action: `Dispatching ${shot.id} to Eden pipeline. Camera: ${camera?.name}, Lens: ${lens?.name}`,
      type: 'routing',
    }, ...prev]);

    try {
      const res = await fetch('/eden/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt }),
      });
      if (!res.ok) throw new Error(`Eden returned ${res.status}`);
      const data = await res.json();
      const imageUrl = data.image_url || data.first_output_url;

      if (imageUrl) {
        updateShot('heroFrame', imageUrl);
        updateShot('status', 'hero_approved');
        setAgentFeed(prev => [{
          time: 'now', agent: 'Maya',
          action: `Hero frame generated for ${shot.id}. Image ready for review.`,
          type: 'consistency',
        }, ...prev]);
      } else {
        updateShot('status', 'draft');
        setAgentFeed(prev => [{
          time: 'now', agent: 'Maya',
          action: `Eden completed but no image URL returned for ${shot.id}.`,
          type: 'consistency',
        }, ...prev]);
      }
    } catch (e) {
      updateShot('status', 'draft');
      setAgentFeed(prev => [{
        time: 'now', agent: 'Luna',
        action: `Eden generation failed: ${e.message}`,
        type: 'memory',
      }, ...prev]);
    } finally {
      setGenerating(false);
    }
  }, [generating, generatedPrompt, promptInput, updateShot, shot, camera, lens]);

  const stats = useMemo(() => ({
    total: shots.length,
    approved: shots.filter(s => s.status === 'approved' || s.status === 'locked').length,
    rendering: shots.filter(s => s.status === 'rendering').length,
    duration: shots.reduce((a, s) => a + s.duration, 0),
  }), [shots]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>

      {/* TOOLBAR */}
      <div style={{
        height: 36, background: 'rgba(10, 10, 18, 0.4)', backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)', borderBottom: '1px solid #141420',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px', flexShrink: 0,
      }}>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <span style={{ fontSize: 8, color: '#3a3a50', letterSpacing: 2 }}>
            {stats.approved}/{stats.total} APPROVED
          </span>
          <span style={{ fontSize: 8, color: '#3a3a50' }}>·</span>
          <span style={{ fontSize: 8, color: '#3a3a50' }}>{stats.duration}s TOTAL</span>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={addShot} style={{
            padding: '4px 12px', fontSize: 9, borderRadius: 4,
            border: '1px solid #2a2a3a', background: 'transparent',
            color: '#6b6b80', cursor: 'pointer', fontFamily: 'inherit',
          }}>+ NEW SHOT</button>
          <button onClick={handleGenerate} style={{
            padding: '4px 14px', fontSize: 9, borderRadius: 4, border: 'none',
            background: generating ? '#2a2210' : 'linear-gradient(135deg, #c8ff00, #a0cc00)',
            color: generating ? '#f59e0b' : '#08080e',
            cursor: 'pointer', fontFamily: 'inherit', fontWeight: 700,
            letterSpacing: 1, transition: 'all 0.2s',
          }}>{generating ? '⟳ RENDERING...' : '▶ GENERATE'}</button>
        </div>
      </div>

      {/* MAIN BODY */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>

        {/* LEFT: Shot List */}
        <div style={{
          width: 280, borderRight: '1px solid #141420', background: 'rgba(10, 10, 16, 0.4)',
          backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)',
          display: 'flex', flexDirection: 'column', flexShrink: 0,
        }}>
          <div style={{
            padding: '10px 12px', borderBottom: '1px solid #141420',
            fontSize: 8, color: '#3a3a50', letterSpacing: 2,
          }}>
            SHOT LIST — {shots.length} SHOTS
          </div>
          <div style={{
            flex: 1, overflow: 'auto', padding: 8,
            display: 'flex', flexDirection: 'column', gap: 6,
          }}>
            {shots.map(s => (
              <ShotCard
                key={s.id}
                shot={s}
                selected={s.id === selectedShot}
                onClick={() => setSelectedShot(s.id)}
              />
            ))}
          </div>
        </div>

        {/* CENTER: Hero Frame Canvas */}
        <div style={{
          flex: 1, display: 'flex', flexDirection: 'column', background: 'rgba(8, 8, 14, 0.4)', backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)',
        }}>
          {/* Canvas */}
          <div style={{
            flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
            position: 'relative', overflow: 'hidden',
          }}>
            <div style={{
              width: '85%', maxWidth: 900, aspectRatio: '21/9',
              background: shot.heroFrame ? 'none'
                : 'linear-gradient(135deg, #0f0f1a 0%, #08080e 50%, #0f0f1a 100%)',
              border: '1px solid #1a1a24', borderRadius: 4,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              position: 'relative', overflow: 'hidden',
            }}>
              {shot.heroFrame ? (
                <img src={shot.heroFrame} alt="" style={{
                  width: '100%', height: '100%', objectFit: 'cover',
                }} />
              ) : (
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 14, color: '#1a1a2e', marginBottom: 8 }}>◎</div>
                  <div style={{ fontSize: 9, color: '#2a2a3a', letterSpacing: 2 }}>
                    AWAITING HERO FRAME
                  </div>
                  <div style={{ fontSize: 8, color: '#1a1a24', marginTop: 4 }}>
                    Generate or upload a reference image
                  </div>
                </div>
              )}

              {/* Viewfinder Overlay */}
              <div style={{
                position: 'absolute', inset: 0, pointerEvents: 'none',
                border: '1px solid #c8ff0010',
              }}>
                {/* Rule of thirds */}
                <div style={{ position: 'absolute', left: '33.33%', top: 0, bottom: 0, width: 1, background: '#c8ff0008' }} />
                <div style={{ position: 'absolute', left: '66.66%', top: 0, bottom: 0, width: 1, background: '#c8ff0008' }} />
                <div style={{ position: 'absolute', top: '33.33%', left: 0, right: 0, height: 1, background: '#c8ff0008' }} />
                <div style={{ position: 'absolute', top: '66.66%', left: 0, right: 0, height: 1, background: '#c8ff0008' }} />

                {/* Shot info overlay */}
                <div style={{ position: 'absolute', top: 8, left: 10, display: 'flex', gap: 8, fontSize: 8 }}>
                  <span style={{ color: '#c8ff0060', fontWeight: 700 }}>{shot.id.toUpperCase()}</span>
                  <span style={{ color: '#c8ff0030' }}>21:9 CinemaScope</span>
                </div>
                <div style={{ position: 'absolute', top: 8, right: 10, fontSize: 8, color: '#c8ff0030' }}>
                  {camera?.name} · {lens?.type === 'anamorphic' ? 'ANA ' : ''}{shot.focal}mm · ƒ/{shot.aperture}
                </div>
                <div style={{ position: 'absolute', bottom: 8, left: 10, fontSize: 8, color: '#c8ff0030' }}>
                  {shot.movement.map(m => CAMERA_MOVEMENTS.find(cm => cm.id === m)?.name).join(' + ')}
                </div>
                <div style={{ position: 'absolute', bottom: 8, right: 10, fontSize: 8, color: '#c8ff0030' }}>
                  {shot.duration}s · {filmStock?.name || 'Digital'}
                </div>

                {/* Rendering indicator */}
                {generating && shot.status === 'rendering' && (
                  <div style={{
                    position: 'absolute', top: 8, left: '50%', transform: 'translateX(-50%)',
                    display: 'flex', alignItems: 'center', gap: 6, padding: '3px 10px',
                    background: 'rgba(245,158,11,0.15)', borderRadius: 4,
                    border: '1px solid #f59e0b30',
                  }}>
                    <div style={{
                      width: 6, height: 6, borderRadius: '50%', background: '#f59e0b',
                      animation: 'pulse 1s ease-in-out infinite',
                    }} />
                    <span style={{ fontSize: 8, color: '#f59e0b', letterSpacing: 1 }}>
                      GENERATING
                    </span>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Prompt Bar */}
          <div style={{
            padding: '10px 16px', borderTop: '1px solid #141420', background: 'rgba(10, 10, 18, 0.4)', backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)',
          }}>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <span style={{ fontSize: 9, color: '#c8ff0080', fontWeight: 600 }}>PROMPT</span>
              <input
                value={promptInput}
                onChange={e => setPromptInput(e.target.value)}
                placeholder="Describe the shot... (camera settings applied automatically)"
                style={{
                  flex: 1, padding: '8px 12px', background: '#0d0d18',
                  border: '1px solid #1a1a24', borderRadius: 6, color: '#c8cad0',
                  fontFamily: 'inherit', fontSize: 11, outline: 'none',
                }}
                onFocus={e => e.target.style.borderColor = '#c8ff0040'}
                onBlur={e => e.target.style.borderColor = '#1a1a24'}
              />
              <button onClick={handleGenerate} style={{
                padding: '8px 16px', borderRadius: 6, border: 'none',
                background: '#c8ff00', color: '#08080e', fontWeight: 700,
                fontSize: 10, cursor: 'pointer', fontFamily: 'inherit',
                letterSpacing: 1, whiteSpace: 'nowrap',
              }}>
                HERO FRAME
              </button>
            </div>
          </div>
        </div>

        {/* RIGHT: Controls Panel */}
        <div style={{
          width: 320, borderLeft: '1px solid #141420', background: 'rgba(10, 10, 16, 0.4)',
          backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)',
          display: 'flex', flexDirection: 'column', flexShrink: 0,
        }}>
          {/* Panel Tabs */}
          <div style={{ display: 'flex', borderBottom: '1px solid #141420' }}>
            {[
              { id: 'camera', label: 'CAMERA' },
              { id: 'post', label: 'POST' },
              { id: 'prompt', label: 'PROMPT' },
              { id: 'agents', label: 'AGENTS' },
            ].map(tab => (
              <button key={tab.id} onClick={() => setRightPanel(tab.id)} style={{
                flex: 1, padding: '10px 0', fontSize: 8, letterSpacing: 2,
                border: 'none',
                borderBottom: rightPanel === tab.id ? '2px solid #c8ff00' : '2px solid transparent',
                background: 'transparent',
                color: rightPanel === tab.id ? '#c8ff00' : '#3a3a50',
                cursor: 'pointer', fontFamily: 'inherit', transition: 'all 0.15s',
              }}>{tab.label}</button>
            ))}
          </div>

          {/* Panel Content */}
          <div style={{ flex: 1, overflow: 'auto', padding: 12 }}>

            {/* CAMERA PANEL */}
            {rightPanel === 'camera' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                {/* Camera Body */}
                <div>
                  <div style={{ fontSize: 8, color: '#3a3a50', letterSpacing: 2, marginBottom: 8 }}>
                    CAMERA BODY
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                    {CAMERA_BODIES.map(c => (
                      <button key={c.id} onClick={() => updateShot('camera', c.id)} style={{
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                        padding: '6px 10px', borderRadius: 4, border: 'none',
                        background: shot.camera === c.id ? '#16162a' : 'transparent',
                        cursor: 'pointer', fontFamily: 'inherit', transition: 'all 0.12s',
                        textAlign: 'left',
                      }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span style={{
                            fontSize: 10,
                            color: shot.camera === c.id ? '#e8e8f0' : '#6b6b80',
                          }}>{c.name}</span>
                          <span style={{ fontSize: 7, color: '#3a3a50' }}>{c.sensor}</span>
                        </div>
                        <span style={{
                          fontSize: 6, padding: '1px 5px', borderRadius: 2, letterSpacing: 1,
                          background: shot.camera === c.id ? '#c8ff0015' : '#1a1a24',
                          color: shot.camera === c.id ? '#c8ff00' : '#3a3a50',
                          fontWeight: 700,
                        }}>{c.badge}</span>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Lens */}
                <div>
                  <div style={{ fontSize: 8, color: '#3a3a50', letterSpacing: 2, marginBottom: 8 }}>
                    LENS
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                    {LENS_PROFILES.map(l => (
                      <button key={l.id} onClick={() => updateShot('lens', l.id)} style={{
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                        padding: '6px 10px', borderRadius: 4, border: 'none',
                        background: shot.lens === l.id ? '#16162a' : 'transparent',
                        cursor: 'pointer', fontFamily: 'inherit', transition: 'all 0.12s',
                        textAlign: 'left',
                      }}>
                        <div>
                          <div style={{
                            fontSize: 10, color: shot.lens === l.id ? '#e8e8f0' : '#6b6b80',
                          }}>{l.name}</div>
                          <div style={{ fontSize: 7, color: '#3a3a50', marginTop: 1 }}>
                            {l.character}
                          </div>
                        </div>
                        <span style={{
                          fontSize: 7,
                          color: l.type === 'anamorphic' ? '#f59e0b' : '#4a4a60',
                          letterSpacing: 1, whiteSpace: 'nowrap',
                        }}>{l.type === 'anamorphic' ? 'ANA' : 'SPH'}</span>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Optics Knobs */}
                <div>
                  <div style={{ fontSize: 8, color: '#3a3a50', letterSpacing: 2, marginBottom: 10 }}>
                    OPTICS
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-around' }}>
                    <Knob label="Focal" value={shot.focal} min={12} max={200} unit="mm" />
                    <Knob label="Aperture" value={shot.aperture} min={1.2} max={22} unit="" accent="#818cf8" />
                    <Knob label="Duration" value={shot.duration} min={1} max={20} unit="s" accent="#4ade80" />
                  </div>
                </div>

                {/* Camera Movement */}
                <div>
                  <div style={{ fontSize: 8, color: '#3a3a50', letterSpacing: 2, marginBottom: 8 }}>
                    MOVEMENT <span style={{ color: '#2a2a3a' }}>· max 3</span>
                  </div>
                  <PillSelect
                    options={CAMERA_MOVEMENTS}
                    selected={shot.movement}
                    onChange={v => {
                      const current = shot.movement;
                      if (current.includes(v)) {
                        updateShot('movement', current.filter(m => m !== v));
                      } else if (current.length < 3) {
                        updateShot('movement', [...current, v]);
                      }
                    }}
                  />
                  {shot.movement.length > 0 && (
                    <div style={{ marginTop: 6, fontSize: 9, color: '#6b6b80' }}>
                      Active: {shot.movement.map(m =>
                        CAMERA_MOVEMENTS.find(cm => cm.id === m)?.name
                      ).join(' → ')}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* POST PANEL */}
            {rightPanel === 'post' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                {/* Film Stock */}
                <div>
                  <div style={{ fontSize: 8, color: '#3a3a50', letterSpacing: 2, marginBottom: 8 }}>
                    FILM STOCK
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                    {FILM_STOCKS.map(f => (
                      <button key={f.id} onClick={() => updateShot('filmStock', f.id)} style={{
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                        padding: '6px 10px', borderRadius: 4, border: 'none',
                        background: shot.filmStock === f.id ? '#16162a' : 'transparent',
                        cursor: 'pointer', fontFamily: 'inherit', transition: 'all 0.12s',
                        textAlign: 'left',
                      }}>
                        <div>
                          <div style={{
                            fontSize: 10, color: shot.filmStock === f.id ? '#e8e8f0' : '#6b6b80',
                          }}>{f.name}</div>
                          {f.character && (
                            <div style={{ fontSize: 7, color: '#3a3a50', marginTop: 1 }}>
                              {f.character}
                            </div>
                          )}
                        </div>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Color */}
                <div>
                  <div style={{ fontSize: 8, color: '#3a3a50', letterSpacing: 2, marginBottom: 10 }}>
                    COLOR
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-around' }}>
                    <Knob label="Temp" value={5600} min={2500} max={10000} unit="K" accent="#f59e0b" />
                    <Knob label="Tint" value={0} min={-50} max={50} unit="" accent="#a78bfa" />
                    <Knob label="Grain" value={25} min={0} max={100} unit="%" accent="#6b6b80" />
                  </div>
                </div>

                {/* Optical FX */}
                <div>
                  <div style={{ fontSize: 8, color: '#3a3a50', letterSpacing: 2, marginBottom: 10 }}>
                    OPTICAL FX
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-around' }}>
                    <Knob label="Bloom" value={15} min={0} max={100} unit="%" accent="#fbbf24" />
                    <Knob label="Halation" value={10} min={0} max={100} unit="%" accent="#f472b6" />
                    <Knob label="Vignette" value={30} min={0} max={100} unit="%" accent="#6b6b80" />
                  </div>
                </div>

                {/* DI Agent Status */}
                <div style={{
                  padding: 10, background: '#0d0d18', borderRadius: 6, border: '1px solid #1a1a24',
                }}>
                  <div style={{ fontSize: 8, color: '#f59e0b', letterSpacing: 2, marginBottom: 6 }}>
                    DI AGENT
                  </div>
                  <div style={{ fontSize: 9, color: '#6b6b80', lineHeight: 1.5 }}>
                    Auto-applies film stock emulation + color grade to generated frames.
                    Matches Dehancer profiles for photochemical accuracy.
                  </div>
                  <div style={{ marginTop: 8, display: 'flex', gap: 4 }}>
                    <span style={{
                      fontSize: 7, padding: '2px 6px', background: '#2a2210',
                      color: '#f59e0b', borderRadius: 3,
                    }}>ACTIVE</span>
                    <span style={{
                      fontSize: 7, padding: '2px 6px', background: '#1a1a24',
                      color: '#3a3a50', borderRadius: 3,
                    }}>LUT: {filmStock?.name || 'None'}</span>
                  </div>
                </div>
              </div>
            )}

            {/* PROMPT PANEL */}
            {rightPanel === 'prompt' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                <div style={{
                  fontSize: 8,
                  color: '#c8ff00',
                  letterSpacing: 2,
                  marginBottom: 4,
                }}>
                  EDEN PROMPT BUILDER
                </div>

                <div style={{
                  fontSize: 9,
                  color: '#6b6b80',
                  lineHeight: 1.5,
                  padding: '8px 10px',
                  background: '#0d0d18',
                  borderRadius: 4,
                  border: '1px solid #1a1a24',
                }}>
                  Generate Eden-compatible prompt from shot configuration + scene context.
                </div>

                {/* Generate Button */}
                <button
                  onClick={async () => {
                    setIsGeneratingPrompt(true);
                    setPromptError(null);
                    try {
                      // Build shot config from current shot state
                      const shotConfig = {
                        camera: {
                          angle: 'eye_level',
                          movement: shot.movement[0] || 'static',
                          distance: shot.type === 'close' ? 'close_up' : shot.type === 'wide' ? 'wide' : 'medium',
                          lens: `${shot.focal}mm`,
                          fps: 24,
                        },
                        lighting: {
                          setup: 'natural',
                          mood: 'cinematic',
                          time_of_day: 'day',
                        },
                        style: {
                          look: 'cinematic',
                          color_grade: filmStock?.colorProfile || 'neutral',
                          aspect_ratio: '2.39:1',
                        },
                      };

                      // Call buildPrompt from KozmoProvider
                      const result = await buildPrompt({
                        shot: shotConfig,
                        scene_slug: shot.scene,
                      });

                      setGeneratedPrompt(result.prompt || 'No prompt generated');
                    } catch (err) {
                      console.error('Prompt generation failed:', err);
                      setPromptError(err.message || 'Failed to generate prompt');
                    } finally {
                      setIsGeneratingPrompt(false);
                    }
                  }}
                  disabled={isGeneratingPrompt}
                  style={{
                    padding: '10px 16px',
                    borderRadius: 4,
                    border: '1px solid #c8ff0040',
                    background: isGeneratingPrompt ? 'rgba(200, 255, 0, 0.05)' : 'rgba(200, 255, 0, 0.1)',
                    color: isGeneratingPrompt ? '#6b6b80' : '#c8ff00',
                    fontSize: 10,
                    fontWeight: 600,
                    cursor: isGeneratingPrompt ? 'not-allowed' : 'pointer',
                    transition: 'all 0.15s',
                    letterSpacing: 1,
                  }}
                  onMouseEnter={(e) => {
                    if (!isGeneratingPrompt) {
                      e.target.style.background = 'rgba(200, 255, 0, 0.15)';
                      e.target.style.borderColor = '#c8ff0060';
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!isGeneratingPrompt) {
                      e.target.style.background = 'rgba(200, 255, 0, 0.1)';
                      e.target.style.borderColor = '#c8ff0040';
                    }
                  }}
                >
                  {isGeneratingPrompt ? '⏳ Generating...' : '✨ Generate Prompt'}
                </button>

                {/* Error Display */}
                {promptError && (
                  <div style={{
                    padding: '8px 10px',
                    background: 'rgba(239, 68, 68, 0.1)',
                    border: '1px solid rgba(239, 68, 68, 0.3)',
                    borderRadius: 4,
                    color: '#ef4444',
                    fontSize: 9,
                    lineHeight: 1.5,
                  }}>
                    ⚠ {promptError}
                  </div>
                )}

                {/* Prompt Display */}
                {generatedPrompt && !promptError && (
                  <div>
                    <div style={{
                      fontSize: 8,
                      color: '#3a3a50',
                      letterSpacing: 2,
                      marginBottom: 6,
                    }}>
                      GENERATED PROMPT
                    </div>
                    <textarea
                      value={generatedPrompt}
                      readOnly
                      style={{
                        width: '100%',
                        minHeight: 300,
                        padding: 10,
                        background: '#0a0a14',
                        border: '1px solid #2a2a3a',
                        borderRadius: 4,
                        color: '#c8cad0',
                        fontSize: 10,
                        fontFamily: "'JetBrains Mono', monospace",
                        lineHeight: 1.6,
                        resize: 'vertical',
                        outline: 'none',
                      }}
                    />
                    <div style={{
                      marginTop: 6,
                      fontSize: 8,
                      color: '#4a4a60',
                      fontFamily: "'JetBrains Mono', monospace",
                    }}>
                      {generatedPrompt.split(/\s+/).length} words · Ready for Eden dispatch
                    </div>
                  </div>
                )}

                {/* Shot Info */}
                <div style={{
                  marginTop: 8,
                  padding: '8px 10px',
                  background: '#0d0d18',
                  borderRadius: 4,
                  border: '1px solid #1a1a24',
                }}>
                  <div style={{ fontSize: 8, color: '#3a3a50', letterSpacing: 2, marginBottom: 6 }}>
                    SHOT CONFIG
                  </div>
                  <div style={{ fontSize: 9, color: '#6b6b80', lineHeight: 1.5 }}>
                    <div>ID: <span style={{ color: '#9ca3af' }}>{shot.id}</span></div>
                    <div>Scene: <span style={{ color: '#9ca3af' }}>{shot.scene}</span></div>
                    <div>Camera: <span style={{ color: '#9ca3af' }}>{camera?.name}</span></div>
                    <div>Lens: <span style={{ color: '#9ca3af' }}>{lens?.name} · {shot.focal}mm</span></div>
                    <div>Movement: <span style={{ color: '#9ca3af' }}>{shot.movement.join(', ')}</span></div>
                    <div>Film Stock: <span style={{ color: '#9ca3af' }}>{filmStock?.name}</span></div>
                  </div>
                </div>
              </div>
            )}

            {/* AGENTS PANEL */}
            {rightPanel === 'agents' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                <div style={{ fontSize: 8, color: '#3a3a50', letterSpacing: 2 }}>
                  AGENT ACTIVITY
                </div>
                {agentFeed.map((item, i) => (
                  <AgentFeedItem key={i} item={item} />
                ))}

                {/* Style Lock */}
                <div style={{
                  marginTop: 8, padding: 10, background: '#0d0d18', borderRadius: 6,
                  border: '1px solid #1a1a24',
                }}>
                  <div style={{ fontSize: 8, color: '#818cf8', letterSpacing: 2, marginBottom: 6 }}>
                    STYLE LOCK
                  </div>
                  <div style={{ fontSize: 9, color: '#6b6b80', lineHeight: 1.5 }}>
                    Luna tracking visual consistency across {shots.length} shots.
                    Camera: {camera?.name} · Lens: {lens?.name} · Stock: {filmStock?.name}
                  </div>
                </div>

                {/* Agent Roster */}
                <div style={{ marginTop: 4 }}>
                  <div style={{ fontSize: 8, color: '#3a3a50', letterSpacing: 2, marginBottom: 8 }}>
                    AGENT ROSTER
                  </div>
                  {[
                    { name: 'Chiba', role: 'Orchestrator', id: 'chiba', color: '#c8ff00' },
                    { name: 'Maya', role: 'Vision / Consistency', id: 'maya', color: '#4ade80' },
                    { name: 'DI Agent', role: 'Color / Post', id: 'di_agent', color: '#f59e0b' },
                    { name: 'Foley', role: 'Audio / SFX', id: 'foley', color: '#6b6b80' },
                    { name: 'Luna', role: 'Memory / Style Lock', id: 'luna', color: '#818cf8' },
                  ].map(a => {
                    const status = agentStatus[a.id] || 'standby';
                    const isActive = ['live', 'idle', 'active', 'ready'].includes(status);
                    return (
                      <div key={a.name} style={{
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                        padding: '6px 8px', borderRadius: 4, marginBottom: 2,
                      }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <div style={{
                            width: 6, height: 6, borderRadius: '50%',
                            background: isActive ? a.color : '#2a2a3a',
                            boxShadow: isActive ? `0 0 6px ${a.color}40` : 'none',
                          }} />
                          <span style={{ fontSize: 10, color: '#e8e8f0' }}>{a.name}</span>
                        </div>
                        <span style={{ fontSize: 7, color: '#3a3a50' }}>{a.role}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* BOTTOM: Mini Timeline */}
      <div style={{
        height: 56, borderTop: '1px solid #141420', background: 'rgba(6, 6, 10, 0.6)',
        backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)',
        display: 'flex', alignItems: 'center', padding: '0 16px', gap: 4,
        flexShrink: 0,
      }}>
        <span style={{
          fontSize: 8, color: '#3a3a50', letterSpacing: 2, marginRight: 12, minWidth: 60,
        }}>TIMELINE</span>
        {shots.map(s => {
          const st = STATUS_CONFIG[s.status] || STATUS_CONFIG.idea;
          const widthPx = Math.max(s.duration * 12, 32);
          return (
            <div key={s.id} onClick={() => setSelectedShot(s.id)} style={{
              width: widthPx, height: 32, borderRadius: 3,
              background: s.id === selectedShot ? '#1a1a2e' : st.bg,
              border: `1px solid ${s.id === selectedShot ? '#c8ff0040' : '#1a1a24'}`,
              cursor: 'pointer', position: 'relative', overflow: 'hidden',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              transition: 'all 0.15s',
            }}>
              <span style={{ fontSize: 7, color: st.color, fontWeight: 600 }}>
                {s.id.replace('sh0', '')}
              </span>
              {s.status === 'rendering' && (
                <div style={{
                  position: 'absolute', bottom: 0, left: 0, right: 0, height: 2,
                  background: 'linear-gradient(90deg, #f59e0b 60%, transparent 60%)',
                }} />
              )}
            </div>
          );
        })}
        <div style={{ flex: 1 }} />
        <span style={{ fontSize: 8, color: '#2a2a3a' }}>
          {stats.duration}s · {stats.total} shots · {stats.approved} locked
        </span>
      </div>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.3; }
        }
      `}</style>
    </div>
  );
}
