/**
 * Audio-Driven Timeline — Narration + Visual Shot Sync
 *
 * Audio track is the backbone. Visual shot cards pin to timecodes.
 * Each track strip is colored by voice entity.
 * Playhead scrubs through audio + shows current shot card.
 *
 * Props:
 *   projectSlug: string — active project
 *   briefs: array — production briefs with audio_start/audio_end
 *   onBriefSelect: (briefId) => void
 */
import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { heroUrl } from '../utils/heroUrl';

// Voice colors — matches Eclissi palette
const VOICE_COLORS = {
  bella: '#c8ff00',
  george: '#818cf8',
  gandala: '#22c55e',
  lily: '#f472b6',
  liam: '#fb923c',
  mohammed: '#38bdf8',
  lucy: '#a78bfa',
  chebel: '#fbbf24',
  maria_clara: '#f97316',
  miyomi: '#67e8f9',
  maggi: '#e879f9',
};

const RULER_HEIGHT = 28;
const TRACK_HEIGHT = 48;
const LABEL_WIDTH = 60;
const MIN_ZOOM = 3; // px per second
const MAX_ZOOM = 30;

function formatTime(seconds) {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${String(s).padStart(2, '0')}`;
}

export default function AudioTimeline({ projectSlug, briefs = [], onBriefSelect }) {
  const [timeline, setTimeline] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [zoom, setZoom] = useState(8); // px per second
  const [scrollLeft, setScrollLeft] = useState(0);
  const [playheadTime, setPlayheadTime] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const containerRef = useRef(null);
  const playRef = useRef(null);
  const lastFrameRef = useRef(null);

  // Fetch timeline data
  useEffect(() => {
    if (!projectSlug) {
      setLoading(false);
      setError('No project selected');
      return;
    }
    setLoading(true);
    setError(null);
    fetch(`/kozmo/projects/${projectSlug}/audio/timeline`)
      .then(r => {
        if (!r.ok) throw new Error(`API returned ${r.status}`);
        return r.json();
      })
      .then(data => {
        setTimeline(data);
        setError(null);
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [projectSlug]);

  const totalDuration = timeline?.total_duration || 0;
  const tracks = timeline?.tracks || [];
  const totalWidth = totalDuration * zoom;

  // Playback loop
  useEffect(() => {
    if (!isPlaying) return;
    lastFrameRef.current = performance.now();

    const tick = (now) => {
      const dt = (now - lastFrameRef.current) / 1000;
      lastFrameRef.current = now;
      setPlayheadTime(prev => {
        const next = prev + dt;
        if (next >= totalDuration) {
          setIsPlaying(false);
          return 0;
        }
        return next;
      });
      playRef.current = requestAnimationFrame(tick);
    };
    playRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(playRef.current);
  }, [isPlaying, totalDuration]);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      if (e.code === 'Space') { e.preventDefault(); setIsPlaying(p => !p); }
      if (e.code === 'Home') { setPlayheadTime(0); }
      if (e.code === 'End') { setPlayheadTime(totalDuration); }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [totalDuration]);

  // Scroll handler for zoom
  const handleWheel = useCallback((e) => {
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      setZoom(prev => Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, prev - e.deltaY * 0.02)));
    }
  }, []);

  // Click to scrub
  const handleRulerClick = useCallback((e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left + scrollLeft - LABEL_WIDTH;
    setPlayheadTime(Math.max(0, Math.min(totalDuration, x / zoom)));
  }, [scrollLeft, zoom, totalDuration]);

  // Briefs pinned to audio
  const pinnedBriefs = useMemo(() => {
    return briefs.filter(b => b.audio_start != null && b.audio_end != null);
  }, [briefs]);

  // Current track under playhead
  const currentTrack = useMemo(() => {
    return tracks.find(t => playheadTime >= t.start_time && playheadTime < t.end_time);
  }, [tracks, playheadTime]);

  if (loading) {
    return (
      <div style={{ padding: 20, color: '#5a5a72', fontFamily: "'JetBrains Mono', monospace", fontSize: 11 }}>
        Loading audio timeline...
      </div>
    );
  }

  if (error || !timeline || tracks.length === 0) {
    return (
      <div style={{ padding: 20, color: '#5a5a72', fontFamily: "'JetBrains Mono', monospace", fontSize: 11 }}>
        {error || 'No audio timeline data. Run "Build from SCRIBO" to generate.'}
      </div>
    );
  }

  const playheadX = LABEL_WIDTH + playheadTime * zoom;

  return (
    <div style={{
      background: '#0e0e18', borderRadius: 8, overflow: 'hidden',
      border: '1px solid #1e1e2e', fontFamily: "'JetBrains Mono', monospace",
    }}>
      {/* Transport Bar */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8, padding: '6px 12px',
        background: '#141420', borderBottom: '1px solid #1e1e2e',
      }}>
        <button
          onClick={() => setIsPlaying(p => !p)}
          style={{
            background: 'none', border: '1px solid #3a3a4e', borderRadius: 4,
            color: isPlaying ? '#c8ff00' : '#8a8a9e', cursor: 'pointer',
            padding: '2px 8px', fontSize: 12, fontFamily: 'inherit',
          }}
        >
          {isPlaying ? '⏸' : '▶'}
        </button>
        <button
          onClick={() => setPlayheadTime(0)}
          style={{
            background: 'none', border: '1px solid #3a3a4e', borderRadius: 4,
            color: '#8a8a9e', cursor: 'pointer', padding: '2px 8px', fontSize: 10,
            fontFamily: 'inherit',
          }}
        >
          ⏮
        </button>
        <span style={{ fontSize: 11, color: '#c8ff00', letterSpacing: 1 }}>
          {formatTime(playheadTime)}
        </span>
        <span style={{ fontSize: 9, color: '#5a5a72' }}>
          / {formatTime(totalDuration)}
        </span>
        <div style={{ flex: 1 }} />
        {currentTrack && (
          <span style={{
            fontSize: 9, color: VOICE_COLORS[currentTrack.voice] || '#8a8a9e',
            maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}>
            {currentTrack.voice?.toUpperCase()} — "{currentTrack.text?.slice(0, 60)}{currentTrack.text?.length > 60 ? '...' : ''}"
          </span>
        )}
        <div style={{ flex: 1 }} />
        <span style={{ fontSize: 8, color: '#5a5a72' }}>
          {tracks.length} tracks · Ctrl+scroll to zoom
        </span>
      </div>

      {/* Timeline area */}
      <div
        ref={containerRef}
        onWheel={handleWheel}
        onScroll={(e) => setScrollLeft(e.currentTarget.scrollLeft)}
        style={{
          overflowX: 'auto', overflowY: 'hidden', position: 'relative',
        }}
      >
        {/* Time ruler */}
        <div
          onClick={handleRulerClick}
          style={{
            height: RULER_HEIGHT, position: 'relative', cursor: 'crosshair',
            background: '#141420', borderBottom: '1px solid #1e1e2e',
            width: totalWidth + LABEL_WIDTH,
          }}
        >
          {Array.from({ length: Math.ceil(totalDuration / 10) + 1 }).map((_, i) => {
            const t = i * 10;
            return (
              <div key={t} style={{
                position: 'absolute', left: LABEL_WIDTH + t * zoom,
                top: 0, height: RULER_HEIGHT, borderLeft: '1px solid #2a2a3a',
              }}>
                <span style={{
                  position: 'absolute', top: 2, left: 4, fontSize: 8, color: '#5a5a72',
                }}>
                  {formatTime(t)}
                </span>
              </div>
            );
          })}
        </div>

        {/* Audio track strips */}
        <div style={{ position: 'relative', width: totalWidth + LABEL_WIDTH }}>
          {/* Track label gutter */}
          <div style={{
            position: 'absolute', left: 0, top: 0, width: LABEL_WIDTH,
            height: TRACK_HEIGHT + 4, background: '#0e0e18',
            borderRight: '1px solid #1e1e2e',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <span style={{ fontSize: 7, color: '#5a5a72', textTransform: 'uppercase', letterSpacing: 1.5 }}>
              AUDIO
            </span>
          </div>

          {/* Track clips */}
          <div style={{
            marginLeft: LABEL_WIDTH, height: TRACK_HEIGHT, position: 'relative',
            background: '#0a0a14',
          }}>
            {tracks.map((track) => {
              const left = track.start_time * zoom;
              const width = Math.max(track.duration * zoom, 2);
              const color = VOICE_COLORS[track.voice] || '#5a5a72';

              return (
                <div
                  key={track.id}
                  title={`${track.voice?.toUpperCase() || 'VOICE'}: ${track.text?.slice(0, 80) || track.filename}`}
                  onClick={() => setPlayheadTime(track.start_time)}
                  style={{
                    position: 'absolute', left, top: 4, width,
                    height: TRACK_HEIGHT - 8, borderRadius: 3,
                    background: `${color}18`,
                    border: `1px solid ${color}40`,
                    cursor: 'pointer',
                    overflow: 'hidden',
                    transition: 'opacity 0.15s',
                  }}
                >
                  <div style={{
                    position: 'absolute', left: 0, top: 0, bottom: 0,
                    width: 3, background: color, borderRadius: '3px 0 0 3px',
                  }} />
                  {width > 40 && (
                    <span style={{
                      position: 'absolute', left: 8, top: 3, fontSize: 7,
                      color, textTransform: 'uppercase', letterSpacing: 1,
                      fontWeight: 700,
                    }}>
                      {track.voice || '?'}
                    </span>
                  )}
                  {width > 80 && (
                    <span style={{
                      position: 'absolute', left: 8, bottom: 3, right: 4,
                      fontSize: 7, color: '#8a8a9e',
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }}>
                      {track.text?.slice(0, 50) || track.filename}
                    </span>
                  )}
                </div>
              );
            })}
          </div>

          {/* Visual briefs row (pinned to audio) */}
          {pinnedBriefs.length > 0 && (
            <>
              <div style={{
                position: 'absolute', left: 0, top: TRACK_HEIGHT + 4, width: LABEL_WIDTH,
                height: TRACK_HEIGHT, background: '#0e0e18',
                borderRight: '1px solid #1e1e2e',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <span style={{ fontSize: 7, color: '#5a5a72', textTransform: 'uppercase', letterSpacing: 1.5 }}>
                  VISUAL
                </span>
              </div>
              <div style={{
                marginLeft: LABEL_WIDTH, height: TRACK_HEIGHT, position: 'relative',
                background: '#0a0a14', borderTop: '1px solid #1e1e2e',
              }}>
                {pinnedBriefs.map((brief) => {
                  const left = brief.audio_start * zoom;
                  const width = Math.max((brief.audio_end - brief.audio_start) * zoom, 4);

                  return (
                    <div
                      key={brief.id}
                      onClick={() => onBriefSelect?.(brief.id)}
                      title={brief.title}
                      style={{
                        position: 'absolute', left, top: 4, width,
                        height: TRACK_HEIGHT - 8, borderRadius: 3,
                        background: 'rgba(200, 255, 0, 0.06)',
                        border: '1px solid rgba(200, 255, 0, 0.25)',
                        cursor: 'pointer', overflow: 'hidden',
                      }}
                    >
                      {brief.hero_frame && (
                        <img
                          src={heroUrl(brief.hero_frame, projectSlug)}
                          alt=""
                          style={{
                            position: 'absolute', left: 0, top: 0, height: '100%',
                            width: '100%', objectFit: 'cover', opacity: 0.4,
                          }}
                        />
                      )}
                      {width > 40 && (
                        <span style={{
                          position: 'absolute', left: 4, top: 3, fontSize: 7,
                          color: '#c8ff00', fontWeight: 600,
                          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                          right: 4,
                        }}>
                          {brief.title}
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            </>
          )}

          {/* Playhead */}
          <div style={{
            position: 'absolute', left: playheadTime * zoom,
            top: 0, bottom: 0, width: 1, background: '#c8ff00',
            pointerEvents: 'none', zIndex: 10,
          }}>
            <div style={{
              position: 'absolute', top: -2, left: -4, width: 0, height: 0,
              borderLeft: '4px solid transparent', borderRight: '4px solid transparent',
              borderTop: '6px solid #c8ff00',
            }} />
          </div>
        </div>
      </div>
    </div>
  );
}
