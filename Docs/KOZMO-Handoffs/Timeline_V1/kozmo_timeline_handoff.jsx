import { useState, useCallback, useMemo, useRef, useEffect } from "react";

// ============================================================================
// KOZMO TIMELINE — Handoff Spec Prototype
// 
// For CC implementation. Three panels:
// - VIEWPORT: Camera monitor showing container at playhead
// - TIMELINE: NLE tracks with containers + visible clips
// - SPEC: Integration map as implementation contract
// ============================================================================

const C = {
  bg: "#06060c", surface: "#0a0a14", border: "#1a1a24",
  text: "#e8e8f0", muted: "#6b6b80", dim: "#3a3a50", accent: "#c8ff00",
  video: "#818cf8", audio: "#22d3ee", image: "#4ade80", effect: "#f59e0b",
};

// --- Assets (simplified — just what clips reference) ---
const ASSETS = {
  "a01": { id: "a01", type: "video", name: "crooked_nail_wide.mp4", duration: 4.2 },
  "a02": { id: "a02", type: "audio", name: "atmo_desert_wind.wav", duration: 12.0 },
  "a03": { id: "a03", type: "video", name: "cornelius_cu_hero.mp4", duration: 2.8 },
  "a04": { id: "a04", type: "audio", name: "dialogue_cornelius.wav", duration: 2.5 },
  "a06": { id: "a06", type: "video", name: "mordecai_ots_anim.mp4", duration: 3.8 },
  "a07": { id: "a07", type: "audio", name: "score_tension_bed.wav", duration: 18.0 },
  "a08": { id: "a08", type: "audio", name: "foley_boots.wav", duration: 3.2 },
  "a09": { id: "a09", type: "video", name: "road_tracking.mp4", duration: 5.5 },
};

const MEDIA_COLORS = { video: C.video, audio: C.audio, image: C.image };

// --- Containers: clips visible, effects count only ---
const CONTAINERS = {
  ct01: {
    id: "ct01", label: "Crooked Nail — Wide", position: 0, duration: 4.2, locked: false,
    camera: { body: "ARRI Alexa 35", lens: "Panavision C", focal: 40, aperture: 2.8, movement: "dolly_in" },
    clips: [
      { id: "cl01", assetId: "a01", mediaType: "video", inPoint: 0, outPoint: 4.2 },
      { id: "cl02", assetId: "a02", mediaType: "audio", inPoint: 0, outPoint: 4.2 },
    ],
    fxCount: 3, groupId: null,
  },
  ct02: {
    id: "ct02", label: "Cornelius CU", position: 4.2, duration: 2.8, locked: true,
    camera: { body: "ARRI Alexa 35", lens: "Cooke S7/i", focal: 85, aperture: 1.4, movement: "static" },
    clips: [
      { id: "cl03", assetId: "a03", mediaType: "video", inPoint: 0, outPoint: 2.8 },
      { id: "cl04", assetId: "a04", mediaType: "audio", inPoint: 0, outPoint: 2.5 },
    ],
    fxCount: 2, groupId: "grp01",
  },
  ct03: {
    id: "ct03", label: "Mordecai OTS", position: 7.0, duration: 3.8, locked: false,
    camera: { body: "ARRI Alexa 35", lens: "Panavision C", focal: 50, aperture: 2.0, movement: "pan_right + dolly_in" },
    clips: [
      { id: "cl05", assetId: "a06", mediaType: "video", inPoint: 0, outPoint: 3.8 },
      { id: "cl06", assetId: "a08", mediaType: "audio", inPoint: 0, outPoint: 3.2 },
    ],
    fxCount: 3, groupId: "grp01",
  },
  ct04: {
    id: "ct04", label: "Score — Tension", position: 0, duration: 12.0, locked: false,
    camera: null,
    clips: [
      { id: "cl07", assetId: "a07", mediaType: "audio", inPoint: 0, outPoint: 12.0 },
    ],
    fxCount: 1, groupId: null,
  },
  ct05: {
    id: "ct05", label: "Road — Tracking", position: 10.8, duration: 5.5, locked: false,
    camera: { body: "RED V-Raptor", lens: "Zeiss Supreme", focal: 24, aperture: 5.6, movement: "steadicam" },
    clips: [
      { id: "cl08", assetId: "a09", mediaType: "video", inPoint: 0, outPoint: 5.5 },
    ],
    fxCount: 1, groupId: null,
  },
};

const TRACKS = [
  { id: "V1", label: "V1", type: "video", containerIds: ["ct01", "ct02", "ct03", "ct05"] },
  { id: "A1", label: "A1", type: "audio", containerIds: ["ct01", "ct02", "ct03"] },
  { id: "A2", label: "A2", type: "audio", containerIds: ["ct04"] },
];

const GROUPS = {
  grp01: { id: "grp01", label: "SC1 Sync", containerIds: ["ct02", "ct03"] },
};

const TOTAL_DUR = 16.3;
const PX_S = 58;
const FPS = 24;

// ============================================================================
// SPEC DATA — Implementation contracts for CC
// ============================================================================

const SPEC_SECTIONS = [
  {
    id: "data-model",
    title: "Data Model",
    priority: "P0",
    items: [
      { label: "Timeline", desc: "Root object. Holds tracks[], containers{}, groups{}. Serializes to timeline.yaml" },
      { label: "Track", desc: "Horizontal lane. Has id, label, typeHint (video|audio|mixed), containerIds[]. No data — just ordering" },
      { label: "Container", desc: "Unit of editing. Position + duration on timeline. Holds clips[] + effectChain. Owns camera metadata" },
      { label: "Clip", desc: "Time-positioned ref to MediaAssetRef. Has inPoint, outPoint, mediaType. Lightweight — no effects" },
      { label: "EffectChain", desc: "Ordered effect list on Container, not Clip. All clips share one chain. Want per-clip? Split first" },
      { label: "ContainerGroup", desc: "Logical link. Containers move together but keep own effect chains. Not a merge" },
    ],
  },
  {
    id: "sync-protocol",
    title: "View Sync Protocol",
    priority: "P0",
    items: [
      { label: "Playhead → Viewport", desc: "currentTime → find container on V1 where pos ≤ time < pos+dur → render that frame + camera HUD" },
      { label: "Playhead → Studio", desc: "currentTime → container.briefId → highlight shot card (when Studio view exists)" },
      { label: "Container select", desc: "Click container in Timeline → Compositor shows its clips + chain. Click shot in Studio → scroll Timeline" },
      { label: "Single source of truth", desc: "Timeline state is the authority. Views are projections. No local copies of container data" },
    ],
  },
  {
    id: "container-ops",
    title: "Container Operations",
    priority: "P1",
    items: [
      { label: "Create", desc: "Drag asset from CODEX → Container(clips=[Clip(assetRef)]) at drop position. Track auto-assigned by mediaType" },
      { label: "Razor", desc: "Cut container at time T → two containers. Both get COPIES of effect chain. Clips split at T" },
      { label: "Split Clip", desc: "Extract clip from multi-clip container → new Container inherits effect chain copy" },
      { label: "Merge", desc: "Source clips append to target. Target's effect chain WINS, source chain DROPPED. Confirm dialog required" },
      { label: "Group", desc: "Link containers. Move together, keep independent chains. Visual badge only, no data merge" },
    ],
  },
  {
    id: "asset-flow",
    title: "Asset Pipeline",
    priority: "P1",
    items: [
      { label: "CODEX → Timeline", desc: "Drag MediaAsset → creates Container. Video → V track, Audio → A track. Position at playhead or drop" },
      { label: "LAB → Timeline", desc: "ProductionBrief.complete event → auto-create Container at brief.audio_start position if set" },
      { label: "Non-destructive", desc: "Clips hold MediaAssetRef pointers. Trim, split, reorder never touch source files" },
      { label: "Filesystem", desc: "timeline.yaml in project root. Assets in {project}/assets/{type}/. Refs are relative paths" },
    ],
  },
  {
    id: "existing-gap",
    title: "Current State → Target",
    priority: "P0",
    items: [
      { label: "AudioTimeline", desc: "Exists but flat list of AudioTrack objects. No container model. REPLACE with Container system" },
      { label: "ProductionBrief", desc: "Has audio sync fields but no clip abstraction. ADD container_id field for timeline binding" },
      { label: "MediaAsset", desc: "Exists but disconnected from timeline positioning. WRAP in MediaAssetRef for clip usage" },
      { label: "Merge/Split/Group", desc: "None exist. BUILD as Container methods with event emissions for view sync" },
    ],
  },
  {
    id: "files",
    title: "Implementation Files",
    priority: "ref",
    items: [
      { label: "NEW: types.py", desc: "Timeline, Track, Container, Clip, EffectChain, ContainerGroup, MediaAssetRef Pydantic models" },
      { label: "NEW: timeline_service.py", desc: "CRUD + operations (create, razor, split, merge, group). Event bus for view sync" },
      { label: "MODIFY: audio_timeline.py", desc: "Deprecate → migrate to Container model. Keep AudioTrack as legacy adapter" },
      { label: "MODIFY: types.py (existing)", desc: "Add container_id to ProductionBrief. Add MediaAssetRef wrapper" },
      { label: "NEW: timeline.yaml schema", desc: "Serialization format. Tracks → containerIds, Containers → clips + effectChain" },
      { label: "MODIFY: routes.py", desc: "Add /api/kozmo/timeline/* endpoints. WebSocket events for real-time sync" },
    ],
  },
];

// ============================================================================
// COMPONENTS
// ============================================================================

function TrackHeader({ track, active }) {
  const c = track.type === "video" ? C.video : C.audio;
  return (
    <div style={{
      width: 44, height: 56, background: active ? "#10101e" : C.surface,
      borderBottom: `1px solid ${C.border}`, borderRight: `1px solid ${C.border}`,
      display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
      flexShrink: 0,
    }}>
      <span style={{ fontSize: 10, fontWeight: 700, color: c }}>{track.label}</span>
      <span style={{ fontSize: 7, color: C.dim, marginTop: 1 }}>{track.type}</span>
    </div>
  );
}

function ContainerBlock({ ct, selected, grouped, onClick }) {
  const w = ct.duration * PX_S;
  const x = ct.position * PX_S;

  return (
    <div onClick={() => onClick(ct.id)} style={{
      position: "absolute", left: x, top: 3, bottom: 3, width: w,
      background: selected ? "#14142a" : "#0c0c18",
      border: `1.5px solid ${selected ? C.accent + "70" : "#1a1a30"}`,
      borderRadius: 5, cursor: "pointer", overflow: "hidden",
      transition: "border-color 0.1s",
    }}>
      {/* Clip strips */}
      <div style={{ display: "flex", flexDirection: "column", height: "100%", padding: 3, gap: 2 }}>
        {/* Label row */}
        <div style={{
          display: "flex", alignItems: "center", gap: 4,
          fontSize: 9, fontWeight: 600, color: selected ? C.text : "#777",
          overflow: "hidden", whiteSpace: "nowrap", lineHeight: 1,
        }}>
          <span style={{ overflow: "hidden", textOverflow: "ellipsis" }}>{ct.label}</span>
          {ct.locked && <span style={{ color: C.accent, fontSize: 7 }}>🔒</span>}
          {grouped && <span style={{ color: "#ec4899", fontSize: 7 }}>⫘</span>}
        </div>

        {/* Clip bars */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 1 }}>
          {ct.clips.map(clip => {
            const asset = ASSETS[clip.assetId];
            const clipW = ((clip.outPoint - clip.inPoint) / ct.duration) * 100;
            const col = MEDIA_COLORS[clip.mediaType] || C.muted;
            return (
              <div key={clip.id} style={{
                height: clip.mediaType === "video" ? 14 : 10,
                width: `${clipW}%`,
                background: `${col}18`,
                borderLeft: `2px solid ${col}`,
                borderRadius: 2, display: "flex", alignItems: "center", paddingLeft: 4,
                overflow: "hidden",
              }}>
                <span style={{ fontSize: 7, color: `${col}aa`, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                  {asset?.name?.split(".")[0] || clip.assetId}
                </span>
              </div>
            );
          })}
        </div>

        {/* FX count badge */}
        {ct.fxCount > 0 && (
          <div style={{
            position: "absolute", bottom: 3, right: 4,
            fontSize: 7, color: C.effect, opacity: 0.6,
          }}>
            {ct.fxCount}fx
          </div>
        )}
      </div>
    </div>
  );
}

function Playhead({ time, height }) {
  return (
    <div style={{
      position: "absolute", left: 44 + time * PX_S, top: 0, width: 1, height,
      background: C.accent, zIndex: 20, pointerEvents: "none",
    }}>
      <div style={{
        position: "absolute", top: -1, left: -4, width: 9, height: 6,
        background: C.accent, borderRadius: "1px 1px 0 0",
        clipPath: "polygon(0 0, 100% 0, 50% 100%)",
      }} />
    </div>
  );
}

function Ruler({ dur }) {
  const marks = [];
  for (let t = 0; t <= dur; t += 1) marks.push(t);
  return (
    <div style={{ height: 18, position: "relative", marginLeft: 44, borderBottom: `1px solid ${C.border}`, background: C.surface }}>
      {marks.map(t => (
        <div key={t} style={{ position: "absolute", left: t * PX_S }}>
          <div style={{ width: 1, height: t % 5 === 0 ? 8 : 4, background: t % 5 === 0 ? "#2a2a3a" : "#15151f" }} />
          {t % 5 === 0 && <span style={{ fontSize: 7, color: C.dim, position: "absolute", top: 8, left: 2 }}>{t}s</span>}
        </div>
      ))}
    </div>
  );
}

function ViewportPanel({ ct, time }) {
  if (!ct) return (
    <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", background: "#08080e" }}>
      <span style={{ color: C.dim, fontSize: 10 }}>No container at playhead</span>
    </div>
  );
  const cam = ct.camera;
  const rel = time - ct.position;
  const pct = ct.duration > 0 ? (rel / ct.duration) * 100 : 0;
  const tc = `${Math.floor(rel / 60).toString().padStart(2, "0")}:${Math.floor(rel % 60).toString().padStart(2, "0")}:${Math.floor((rel % 1) * FPS).toString().padStart(2, "0")}`;

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", background: "#08080e" }}>
      <div style={{
        flex: 1, margin: 6, borderRadius: 4, position: "relative", overflow: "hidden",
        background: "linear-gradient(135deg, #0c0c18 0%, #101020 50%, #0a0a16 100%)",
        border: `1px solid ${C.border}`,
      }}>
        {/* Letterbox */}
        <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: "11%", background: "#000" }} />
        <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, height: "11%", background: "#000" }} />

        {/* Center */}
        <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <span style={{ fontSize: 10, color: "#222" }}>{ct.label}</span>
        </div>

        {/* HUD */}
        {cam && (
          <>
            <div style={{ position: "absolute", top: "13%", left: 8, fontSize: 8, color: "#2a2a3a", lineHeight: 1.5 }}>
              <div style={{ fontWeight: 600 }}>{cam.body}</div>
              <div>{cam.lens} · {cam.focal}mm · ƒ/{cam.aperture}</div>
            </div>
            <div style={{ position: "absolute", top: "13%", right: 8, fontSize: 8, color: "#2a2a3a", textAlign: "right", lineHeight: 1.5 }}>
              <div style={{ fontVariantNumeric: "tabular-nums" }}>{tc}</div>
              <div>{cam.movement}</div>
            </div>
          </>
        )}

        {/* Progress */}
        <div style={{ position: "absolute", bottom: "13%", left: 8, right: 8, height: 2, background: "#1a1a24", borderRadius: 1 }}>
          <div style={{ width: `${Math.min(100, Math.max(0, pct))}%`, height: "100%", background: C.accent, borderRadius: 1, transition: "width 0.08s" }} />
        </div>
      </div>
    </div>
  );
}

function SpecPanel() {
  const [expanded, setExpanded] = useState("data-model");
  const priColors = { P0: C.accent, P1: C.effect, ref: C.muted };

  return (
    <div style={{ flex: 1, overflowY: "auto", padding: "6px 8px" }}>
      {SPEC_SECTIONS.map(sec => {
        const open = expanded === sec.id;
        return (
          <div key={sec.id} style={{
            marginBottom: 4, background: "#0a0a16", borderRadius: 5,
            border: `1px solid ${open ? C.accent + "25" : C.border}`,
          }}>
            <div onClick={() => setExpanded(open ? null : sec.id)} style={{
              padding: "6px 8px", cursor: "pointer",
              display: "flex", alignItems: "center", gap: 6,
            }}>
              <span style={{
                fontSize: 7, fontWeight: 700, color: priColors[sec.priority],
                border: `1px solid ${priColors[sec.priority]}40`,
                padding: "1px 4px", borderRadius: 2,
              }}>{sec.priority}</span>
              <span style={{ fontSize: 10, color: C.text, fontWeight: 600, flex: 1 }}>{sec.title}</span>
              <span style={{ fontSize: 8, color: C.dim, transform: open ? "rotate(90deg)" : "none", transition: "transform 0.12s" }}>▶</span>
            </div>
            {open && (
              <div style={{ padding: "0 8px 8px" }}>
                {sec.items.map((item, i) => (
                  <div key={i} style={{ display: "flex", gap: 6, padding: "4px 0", borderTop: i > 0 ? `1px solid ${C.border}` : "none" }}>
                    <span style={{ fontSize: 9, color: C.accent, fontWeight: 600, minWidth: 90, flexShrink: 0 }}>{item.label}</span>
                    <span style={{ fontSize: 9, color: C.muted, lineHeight: 1.5 }}>{item.desc}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ============================================================================
// MAIN
// ============================================================================

export default function KozmoTimeline() {
  const [playhead, setPlayhead] = useState(5.0);
  const [selected, setSelected] = useState("ct02");
  const [playing, setPlaying] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!playing) return;
    const iv = setInterval(() => {
      setPlayhead(p => { const n = p + 0.05; return n > TOTAL_DUR ? 0 : n; });
    }, 50);
    return () => clearInterval(iv);
  }, [playing]);

  const ctAtPlayhead = useMemo(() => {
    return Object.values(CONTAINERS).find(c =>
      TRACKS[0].containerIds.includes(c.id) &&
      playhead >= c.position && playhead < c.position + c.duration
    );
  }, [playhead]);

  const selCt = CONTAINERS[selected];

  const onTimelineClick = useCallback(e => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left - 44;
    if (x >= 0) setPlayhead(Math.max(0, Math.min(TOTAL_DUR, x / PX_S)));
  }, []);

  return (
    <div style={{
      width: "100%", height: "100vh", background: C.bg,
      fontFamily: "'JetBrains Mono', 'SF Mono', monospace",
      color: C.text, display: "flex", flexDirection: "column",
      overflow: "hidden", userSelect: "none",
    }}>
      {/* ═══ BAR ═══ */}
      <div style={{
        height: 32, background: C.surface, borderBottom: `1px solid ${C.border}`,
        display: "flex", alignItems: "center", padding: "0 10px", gap: 8, flexShrink: 0,
      }}>
        <span style={{ color: C.accent, fontWeight: 800, fontSize: 11, letterSpacing: 2 }}>KOZMO</span>
        <span style={{ color: "#1a1a24" }}>·</span>
        <span style={{ color: C.dim, fontSize: 9, letterSpacing: 1 }}>TIMELINE</span>
        <div style={{ flex: 1 }} />
        <button onClick={() => setPlayhead(0)} style={{ background: "none", border: "none", color: C.muted, fontSize: 9, cursor: "pointer", padding: "2px 4px" }}>⏮</button>
        <button onClick={() => setPlaying(!playing)} style={{
          background: playing ? `${C.accent}12` : "none", border: `1px solid ${playing ? C.accent + "30" : C.border}`,
          borderRadius: 3, color: playing ? C.accent : C.muted, fontSize: 10, padding: "2px 8px", cursor: "pointer",
        }}>{playing ? "⏸" : "▶"}</button>
        <span style={{ fontSize: 9, color: C.muted, fontVariantNumeric: "tabular-nums", minWidth: 40 }}>{playhead.toFixed(1)}s</span>
      </div>

      {/* ═══ BODY ═══ */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>

        {/* VIEWPORT */}
        <div style={{ width: 300, borderRight: `1px solid ${C.border}`, display: "flex", flexDirection: "column", flexShrink: 0 }}>
          <div style={{ height: 22, padding: "0 8px", borderBottom: `1px solid ${C.border}`, display: "flex", alignItems: "center" }}>
            <span style={{ fontSize: 8, color: C.accent, fontWeight: 700, letterSpacing: "0.1em" }}>VIEWPORT</span>
            <div style={{ flex: 1 }} />
            {ctAtPlayhead && <span style={{ fontSize: 8, color: C.dim }}>{ctAtPlayhead.id}</span>}
          </div>
          <ViewportPanel ct={ctAtPlayhead} time={playhead} />
        </div>

        {/* CENTER — TIMELINE */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
          <Ruler dur={TOTAL_DUR} />
          <div style={{ flex: 1, position: "relative", overflowX: "auto", overflowY: "hidden" }} onClick={onTimelineClick}>
            {TRACKS.map((track, ti) => (
              <div key={track.id} style={{ display: "flex", height: 56 }}>
                <TrackHeader track={track} active={selCt && track.containerIds.includes(selCt.id)} />
                <div style={{
                  flex: 1, position: "relative", borderBottom: `1px solid ${C.border}`,
                  background: ti % 2 === 0 ? "#08080f" : "#0a0a12",
                  minWidth: TOTAL_DUR * PX_S,
                }}>
                  {Array.from({ length: Math.ceil(TOTAL_DUR) }).map((_, i) => (
                    <div key={i} style={{ position: "absolute", left: i * PX_S, top: 0, width: 1, height: "100%", background: i % 5 === 0 ? "#12121c" : "#0b0b12" }} />
                  ))}
                  {track.containerIds.map(id => CONTAINERS[id]).filter(Boolean)
                    .filter(c => {
                      if (track.type === "video") return c.clips.some(cl => cl.mediaType === "video" || cl.mediaType === "image");
                      return true;
                    })
                    .map(c => (
                      <ContainerBlock key={c.id} ct={c} selected={selected === c.id}
                        grouped={!!c.groupId} onClick={setSelected} />
                    ))}
                </div>
              </div>
            ))}
            <Playhead time={playhead} height={TRACKS.length * 56} />
          </div>

          {/* Container info bar */}
          <div style={{
            height: 40, borderTop: `1px solid ${C.border}`, background: C.surface,
            display: "flex", alignItems: "center", padding: "0 10px", gap: 8, flexShrink: 0, fontSize: 9,
          }}>
            {selCt ? (
              <>
                <span style={{ fontWeight: 700, color: C.text }}>{selCt.label}</span>
                {selCt.locked && <span style={{ color: C.accent, fontSize: 7, border: `1px solid ${C.accent}30`, padding: "1px 4px", borderRadius: 2 }}>LOCKED</span>}
                {selCt.groupId && <span style={{ color: "#ec4899", fontSize: 7, border: `1px solid #ec489930`, padding: "1px 4px", borderRadius: 2 }}>⫘ {GROUPS[selCt.groupId]?.label}</span>}
                <span style={{ color: C.dim }}>·</span>
                <span style={{ color: C.muted }}>{selCt.clips.length} clips</span>
                <span style={{ color: C.dim }}>·</span>
                <span style={{ color: C.effect }}>{selCt.fxCount}fx</span>
                <span style={{ color: C.dim }}>·</span>
                <span style={{ color: C.muted }}>{selCt.duration.toFixed(1)}s</span>
                {selCt.camera && (
                  <>
                    <span style={{ color: C.dim }}>·</span>
                    <span style={{ color: C.dim }}>{selCt.camera.focal}mm ƒ/{selCt.camera.aperture}</span>
                  </>
                )}
              </>
            ) : (
              <span style={{ color: C.dim }}>Select a container</span>
            )}
          </div>
        </div>

        {/* RIGHT — SPEC */}
        <div style={{ width: 280, borderLeft: `1px solid ${C.border}`, display: "flex", flexDirection: "column", flexShrink: 0 }}>
          <div style={{ height: 22, padding: "0 8px", borderBottom: `1px solid ${C.border}`, display: "flex", alignItems: "center" }}>
            <span style={{ fontSize: 8, color: C.effect, fontWeight: 700, letterSpacing: "0.1em" }}>HANDOFF SPEC</span>
          </div>
          <SpecPanel />
        </div>
      </div>

      <style>{`
        ::-webkit-scrollbar { width: 3px; height: 3px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #1a1a24; border-radius: 2px; }
        * { box-sizing: border-box; }
      `}</style>
    </div>
  );
}
