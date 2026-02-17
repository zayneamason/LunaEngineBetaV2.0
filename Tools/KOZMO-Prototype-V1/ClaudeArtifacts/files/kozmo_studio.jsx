import { useState, useCallback, useRef, useEffect, useMemo } from "react";

// ============================================================================
// KOZMO STUDIO — Production Interface
// Cinema-grade shot creation with agent intelligence
// ============================================================================

// --- Camera Presets (from Higgsfield research) ---
const CAMERA_BODIES = [
  { id: "arri_alexa35", name: "ARRI Alexa 35", profile: "cinema", sensor: "S35", colorScience: "ARRI LogC4", badge: "CINEMA" },
  { id: "red_v_raptor", name: "RED V-Raptor", profile: "cinema", sensor: "VV", colorScience: "REDWideGamut", badge: "CINEMA" },
  { id: "sony_venice2", name: "Sony Venice 2", profile: "cinema", sensor: "FF", colorScience: "S-Gamut3", badge: "CINEMA" },
  { id: "bmpcc_6k", name: "Blackmagic 6K", profile: "indie", sensor: "S35", colorScience: "Blackmagic Film", badge: "INDIE" },
  { id: "16mm_bolex", name: "16mm Bolex", profile: "film", sensor: "S16", colorScience: "Kodak 7219", badge: "FILM" },
  { id: "vhs_camcorder", name: "VHS Camcorder", profile: "lo-fi", sensor: "1/3\"", colorScience: "Composite", badge: "LO-FI" },
];

const LENS_PROFILES = [
  { id: "cooke_s7i", name: "Cooke S7/i", type: "spherical", character: "Warm, organic flares", focalRange: [18, 135] },
  { id: "panavision_c", name: "Panavision C-Series", type: "anamorphic", character: "Classic oval bokeh, blue streaks", focalRange: [35, 100] },
  { id: "zeiss_supreme", name: "Zeiss Supreme", type: "spherical", character: "Clean, clinical precision", focalRange: [15, 200] },
  { id: "atlas_mercury", name: "Atlas Mercury", type: "anamorphic", character: "Modern ana, warm tones", focalRange: [28, 100] },
  { id: "canon_k35", name: "Canon K35", type: "spherical", character: "70s softness, vintage glow", focalRange: [18, 85] },
  { id: "helios_44", name: "Helios 44-2", type: "spherical", character: "Swirly bokeh, Soviet glass", focalRange: [58, 58] },
];

const CAMERA_MOVEMENTS = [
  { id: "static", name: "Static", icon: "◻" },
  { id: "dolly_in", name: "Dolly In", icon: "→◎" },
  { id: "dolly_out", name: "Dolly Out", icon: "◎→" },
  { id: "pan_left", name: "Pan Left", icon: "←" },
  { id: "pan_right", name: "Pan Right", icon: "→" },
  { id: "tilt_up", name: "Tilt Up", icon: "↑" },
  { id: "tilt_down", name: "Tilt Down", icon: "↓" },
  { id: "crane_up", name: "Crane Up", icon: "⤴" },
  { id: "crane_down", name: "Crane Down", icon: "⤵" },
  { id: "orbit_cw", name: "Orbit CW", icon: "↻" },
  { id: "orbit_ccw", name: "Orbit CCW", icon: "↺" },
  { id: "handheld", name: "Handheld", icon: "〰" },
  { id: "fpv", name: "FPV Drone", icon: "✈" },
  { id: "steadicam", name: "Steadicam", icon: "≋" },
];

const FILM_STOCKS = [
  { id: "none", name: "None (Digital Clean)", family: "digital" },
  { id: "kodak_5219", name: "Kodak 5219 (500T)", family: "kodak", character: "Warm tungsten, cinema standard" },
  { id: "kodak_5207", name: "Kodak 5207 (250D)", family: "kodak", character: "Daylight, neutral palette" },
  { id: "fuji_eterna", name: "Fuji Eterna Vivid", family: "fuji", character: "Rich greens, cooler shadows" },
  { id: "cinestill_800", name: "CineStill 800T", family: "cinestill", character: "Halation halos, neon warmth" },
  { id: "ilford_hp5", name: "Ilford HP5+ (B&W)", family: "ilford", character: "Punchy contrast, classic grain" },
];

// --- Shot List Data ---
const SHOT_LIST = [
  { id: "sh001", scene: "S1", name: "Crooked Nail — Establishing", type: "wide", status: "approved", heroFrame: "https://placehold.co/400x170/1a1a2e/c8ff00?text=HERO+FRAME", camera: "arri_alexa35", lens: "panavision_c", focal: 40, aperture: 2.8, movement: ["dolly_in"], duration: 3, filmStock: "kodak_5219" },
  { id: "sh002", scene: "S1", name: "Cornelius — Close Up", type: "close", status: "hero_approved", heroFrame: "https://placehold.co/400x170/1a1a2e/4ade80?text=CORNELIUS+CU", camera: "arri_alexa35", lens: "cooke_s7i", focal: 85, aperture: 1.4, movement: ["static"], duration: 2, filmStock: "kodak_5219" },
  { id: "sh003", scene: "S1", name: "Mordecai enters — OTS", type: "ots", status: "rendering", heroFrame: null, camera: "arri_alexa35", lens: "panavision_c", focal: 50, aperture: 2.0, movement: ["pan_right", "dolly_in"], duration: 4, filmStock: "kodak_5219" },
  { id: "sh004", scene: "S2", name: "The Road — Wide Tracking", type: "wide", status: "draft", heroFrame: null, camera: "red_v_raptor", lens: "zeiss_supreme", focal: 24, aperture: 5.6, movement: ["steadicam"], duration: 6, filmStock: "kodak_5207" },
  { id: "sh005", scene: "S3", name: "Tavern Interior — Mordecai", type: "medium", status: "draft", heroFrame: null, camera: "bmpcc_6k", lens: "canon_k35", focal: 35, aperture: 2.0, movement: ["handheld"], duration: 3, filmStock: "cinestill_800" },
  { id: "sh006", scene: "S4", name: "Princess Reveal — Low Angle", type: "low", status: "idea", heroFrame: null, camera: "arri_alexa35", lens: "atlas_mercury", focal: 40, aperture: 2.0, movement: ["crane_up", "dolly_in"], duration: 5, filmStock: "kodak_5219" },
];

const STATUS_CONFIG = {
  idea: { color: "#3a3a50", label: "IDEA", bg: "#1a1a24" },
  draft: { color: "#6b7280", label: "DRAFT", bg: "#1f2028" },
  rendering: { color: "#f59e0b", label: "RENDERING", bg: "#2a2210" },
  hero_approved: { color: "#c8ff00", label: "HERO ✓", bg: "#1a2a10" },
  approved: { color: "#4ade80", label: "APPROVED", bg: "#102a18" },
  locked: { color: "#818cf8", label: "LOCKED", bg: "#1a1a30" },
};

// --- Agent Activity Feed ---
const AGENT_FEED = [
  { time: "2:34", agent: "Chiba", action: "Routed sh003 to Eden (img2vid pipeline)", type: "routing" },
  { time: "2:33", agent: "Maya", action: "Reference anchor locked — Cornelius facial geometry", type: "consistency" },
  { time: "2:31", agent: "DI Agent", action: "Applied Kodak 5219 LUT + Dehancer grain to sh001", type: "post" },
  { time: "2:28", agent: "Luna", action: "Style lock verified: camera profile consistent across S1 shots", type: "memory" },
  { time: "2:25", agent: "Chiba", action: "Hero frame approved for sh002 — dispatching animation", type: "routing" },
];

// ============================================================================
// COMPONENTS
// ============================================================================

function Knob({ label, value, min, max, unit, onChange, accent = "#c8ff00" }) {
  const percentage = ((value - min) / (max - min)) * 100;
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4, minWidth: 64 }}>
      <div style={{
        width: 48, height: 48, borderRadius: "50%", position: "relative",
        background: `conic-gradient(${accent} ${percentage * 2.7}deg, #1a1a24 0deg)`,
        display: "flex", alignItems: "center", justifyContent: "center",
        cursor: "pointer",
      }}>
        <div style={{
          width: 38, height: 38, borderRadius: "50%", background: "#0d0d14",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 11, fontWeight: 600, color: "#e8e8f0",
          fontFamily: "'SF Mono', monospace",
        }}>
          {value}{unit || ""}
        </div>
      </div>
      <span style={{ fontSize: 8, color: "#4a4a60", textTransform: "uppercase", letterSpacing: 1.5 }}>{label}</span>
    </div>
  );
}

function PillSelect({ options, value, onChange, size = "sm" }) {
  const pad = size === "sm" ? "3px 8px" : "5px 12px";
  const fs = size === "sm" ? 9 : 10;
  return (
    <div style={{ display: "flex", gap: 3, flexWrap: "wrap" }}>
      {options.map(opt => (
        <button key={opt.id || opt} onClick={() => onChange(opt.id || opt)}
          style={{
            padding: pad, fontSize: fs, borderRadius: 4,
            border: `1px solid ${(opt.id || opt) === value ? "#c8ff00" : "#2a2a3a"}`,
            background: (opt.id || opt) === value ? "rgba(200,255,0,0.08)" : "transparent",
            color: (opt.id || opt) === value ? "#c8ff00" : "#6b6b80",
            cursor: "pointer", fontFamily: "inherit", transition: "all 0.15s",
            letterSpacing: 0.5,
          }}>
          {opt.icon ? `${opt.icon} ` : ""}{opt.name || opt}
        </button>
      ))}
    </div>
  );
}

function ShotCard({ shot, selected, onClick }) {
  const st = STATUS_CONFIG[shot.status];
  const camera = CAMERA_BODIES.find(c => c.id === shot.camera);
  const lens = LENS_PROFILES.find(l => l.id === shot.lens);
  const movements = shot.movement.map(m => CAMERA_MOVEMENTS.find(cm => cm.id === m));

  return (
    <div onClick={onClick} style={{
      background: selected ? "#16162a" : "#0f0f18",
      border: `1px solid ${selected ? "#c8ff0040" : "#1a1a24"}`,
      borderRadius: 8, padding: 10, cursor: "pointer",
      transition: "all 0.2s", position: "relative", overflow: "hidden",
    }}>
      {/* Hero Frame Preview */}
      <div style={{
        height: 80, borderRadius: 6, marginBottom: 8, overflow: "hidden",
        background: shot.heroFrame ? "none" : "linear-gradient(135deg, #1a1a2e 0%, #0d0d18 100%)",
        display: "flex", alignItems: "center", justifyContent: "center",
        border: "1px solid #1a1a24",
      }}>
        {shot.heroFrame ? (
          <img src={shot.heroFrame} alt="" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
        ) : (
          <span style={{ fontSize: 9, color: "#2a2a3a", letterSpacing: 2 }}>NO HERO FRAME</span>
        )}
      </div>

      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 6 }}>
        <div>
          <div style={{ fontSize: 10, color: "#e8e8f0", fontWeight: 600, marginBottom: 2 }}>{shot.name}</div>
          <div style={{ fontSize: 8, color: "#4a4a60" }}>{shot.scene} · {shot.type.toUpperCase()} · {shot.duration}s</div>
        </div>
        <span style={{
          fontSize: 7, padding: "2px 6px", borderRadius: 3, fontWeight: 700,
          background: st.bg, color: st.color, letterSpacing: 1,
        }}>{st.label}</span>
      </div>

      {/* Camera Info Strip */}
      <div style={{
        display: "flex", gap: 6, fontSize: 8, color: "#4a4a60",
        padding: "4px 0", borderTop: "1px solid #1a1a24",
        marginTop: 4, paddingTop: 6,
      }}>
        <span style={{ color: "#6b6b80" }}>{camera?.name.split(" ").pop()}</span>
        <span>·</span>
        <span>{lens?.name.split(" ").pop()}</span>
        <span>·</span>
        <span>{shot.focal}mm</span>
        <span>·</span>
        <span>ƒ/{shot.aperture}</span>
        <span>·</span>
        <span>{movements.map(m => m?.icon).join(" ")}</span>
      </div>
    </div>
  );
}

function AgentFeedItem({ item }) {
  const colors = {
    routing: "#c8ff00",
    consistency: "#4ade80",
    post: "#f59e0b",
    memory: "#818cf8",
  };
  return (
    <div style={{ display: "flex", gap: 8, padding: "6px 0", borderBottom: "1px solid #1a1a2408" }}>
      <span style={{ fontSize: 8, color: "#3a3a50", minWidth: 28, fontVariantNumeric: "tabular-nums" }}>{item.time}</span>
      <span style={{ fontSize: 8, color: colors[item.type] || "#6b6b80", minWidth: 52, fontWeight: 600 }}>{item.agent}</span>
      <span style={{ fontSize: 9, color: "#6b6b80", lineHeight: 1.4 }}>{item.action}</span>
    </div>
  );
}

// ============================================================================
// MAIN STUDIO
// ============================================================================
export default function KozmoStudio() {
  const [shots, setShots] = useState(SHOT_LIST);
  const [selectedShot, setSelectedShot] = useState("sh001");
  const [rightPanel, setRightPanel] = useState("camera"); // camera | agents | post
  const [viewMode, setViewMode] = useState("grid"); // grid | list | timeline
  const [promptInput, setPromptInput] = useState("");
  const [generating, setGenerating] = useState(false);

  const shot = shots.find(s => s.id === selectedShot) || shots[0];
  const camera = CAMERA_BODIES.find(c => c.id === shot.camera);
  const lens = LENS_PROFILES.find(l => l.id === shot.lens);
  const filmStock = FILM_STOCKS.find(f => f.id === shot.filmStock);

  const updateShot = useCallback((field, value) => {
    setShots(prev => prev.map(s => s.id === selectedShot ? { ...s, [field]: value } : s));
  }, [selectedShot]);

  const handleGenerate = useCallback(() => {
    if (generating) return;
    setGenerating(true);
    updateShot("status", "rendering");
    setTimeout(() => {
      setGenerating(false);
      updateShot("status", "hero_approved");
      updateShot("heroFrame", "https://placehold.co/400x170/1a1a2e/c8ff00?text=GENERATED");
    }, 3000);
  }, [generating, updateShot]);

  // Stats
  const stats = useMemo(() => ({
    total: shots.length,
    approved: shots.filter(s => s.status === "approved" || s.status === "locked").length,
    rendering: shots.filter(s => s.status === "rendering").length,
    duration: shots.reduce((a, s) => a + s.duration, 0),
  }), [shots]);

  return (
    <div style={{
      display: "flex", flexDirection: "column", height: "100vh",
      background: "#08080e", color: "#c8cad0",
      fontFamily: "'DM Mono', 'SF Mono', 'Cascadia Code', monospace",
      fontSize: 12, overflow: "hidden",
    }}>

      {/* ═══ TITLE BAR ═══ */}
      <div style={{
        height: 38, background: "#06060a", borderBottom: "1px solid #141420",
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "0 16px", flexShrink: 0,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: 10, letterSpacing: 4, color: "#c8ff00", fontWeight: 800 }}>KOZMO</span>
          <span style={{ fontSize: 10, letterSpacing: 2, color: "#2a2a3a" }}>STUDIO</span>
          <div style={{ width: 1, height: 14, background: "#1a1a24", margin: "0 4px" }} />
          <span style={{ fontSize: 9, color: "#3a3a50" }}>The Dinosaur, The Wizard, and The Mother</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 16, fontSize: 8, color: "#3a3a50" }}>
          <span>{stats.approved}/{stats.total} shots approved</span>
          <span>{stats.rendering} rendering</span>
          <span>{stats.duration}s total</span>
          <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#4ade80", boxShadow: "0 0 8px #4ade8060" }} />
          <span style={{ color: "#4ade80" }}>EDEN CONNECTED</span>
        </div>
      </div>

      {/* ═══ TOOLBAR ═══ */}
      <div style={{
        height: 36, background: "#0a0a12", borderBottom: "1px solid #141420",
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "0 16px", flexShrink: 0,
      }}>
        <div style={{ display: "flex", gap: 2 }}>
          {["grid", "list", "timeline"].map(v => (
            <button key={v} onClick={() => setViewMode(v)} style={{
              padding: "4px 10px", fontSize: 9, borderRadius: 4, border: "none",
              background: viewMode === v ? "#1a1a2e" : "transparent",
              color: viewMode === v ? "#c8ff00" : "#4a4a60",
              cursor: "pointer", fontFamily: "inherit", textTransform: "uppercase", letterSpacing: 1,
            }}>{v}</button>
          ))}
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button style={{
            padding: "4px 12px", fontSize: 9, borderRadius: 4,
            border: "1px solid #2a2a3a", background: "transparent",
            color: "#6b6b80", cursor: "pointer", fontFamily: "inherit",
          }}>+ NEW SHOT</button>
          <button onClick={handleGenerate} style={{
            padding: "4px 14px", fontSize: 9, borderRadius: 4, border: "none",
            background: generating ? "#2a2210" : "linear-gradient(135deg, #c8ff00, #a0cc00)",
            color: generating ? "#f59e0b" : "#08080e",
            cursor: "pointer", fontFamily: "inherit", fontWeight: 700,
            letterSpacing: 1, transition: "all 0.2s",
          }}>{generating ? "⟳ RENDERING..." : "▶ GENERATE"}</button>
        </div>
      </div>

      {/* ═══ MAIN BODY ═══ */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>

        {/* ─── LEFT: Shot List ─── */}
        <div style={{
          width: 280, borderRight: "1px solid #141420", background: "#0a0a10",
          display: "flex", flexDirection: "column", flexShrink: 0,
        }}>
          <div style={{
            padding: "10px 12px", borderBottom: "1px solid #141420",
            fontSize: 8, color: "#3a3a50", letterSpacing: 2, textTransform: "uppercase",
          }}>
            SHOT LIST — {shots.length} SHOTS
          </div>
          <div style={{ flex: 1, overflow: "auto", padding: 8, display: "flex", flexDirection: "column", gap: 6 }}>
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

        {/* ─── CENTER: Hero Frame Canvas ─── */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", background: "#08080e" }}>
          {/* Canvas */}
          <div style={{
            flex: 1, display: "flex", alignItems: "center", justifyContent: "center",
            position: "relative", overflow: "hidden",
          }}>
            {/* Aspect ratio frame */}
            <div style={{
              width: "85%", maxWidth: 900, aspectRatio: "21/9",
              background: shot.heroFrame ? "none" : "linear-gradient(135deg, #0f0f1a 0%, #08080e 50%, #0f0f1a 100%)",
              border: "1px solid #1a1a24", borderRadius: 4,
              display: "flex", alignItems: "center", justifyContent: "center",
              position: "relative", overflow: "hidden",
            }}>
              {shot.heroFrame ? (
                <img src={shot.heroFrame} alt="" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
              ) : (
                <div style={{ textAlign: "center" }}>
                  <div style={{ fontSize: 14, color: "#1a1a2e", marginBottom: 8 }}>◎</div>
                  <div style={{ fontSize: 9, color: "#2a2a3a", letterSpacing: 2 }}>AWAITING HERO FRAME</div>
                  <div style={{ fontSize: 8, color: "#1a1a24", marginTop: 4 }}>Generate or upload a reference image</div>
                </div>
              )}

              {/* Viewfinder Overlay */}
              <div style={{
                position: "absolute", inset: 0, pointerEvents: "none",
                border: "1px solid #c8ff0010",
              }}>
                {/* Rule of thirds */}
                <div style={{ position: "absolute", left: "33.33%", top: 0, bottom: 0, width: 1, background: "#c8ff0008" }} />
                <div style={{ position: "absolute", left: "66.66%", top: 0, bottom: 0, width: 1, background: "#c8ff0008" }} />
                <div style={{ position: "absolute", top: "33.33%", left: 0, right: 0, height: 1, background: "#c8ff0008" }} />
                <div style={{ position: "absolute", top: "66.66%", left: 0, right: 0, height: 1, background: "#c8ff0008" }} />

                {/* Shot info overlay */}
                <div style={{ position: "absolute", top: 8, left: 10, display: "flex", gap: 8, fontSize: 8 }}>
                  <span style={{ color: "#c8ff0060", fontWeight: 700 }}>{shot.id.toUpperCase()}</span>
                  <span style={{ color: "#c8ff0030" }}>21:9 CinemaScope</span>
                </div>
                <div style={{ position: "absolute", top: 8, right: 10, fontSize: 8, color: "#c8ff0030" }}>
                  {camera?.name} · {lens?.type === "anamorphic" ? "ANA " : ""}{shot.focal}mm · ƒ/{shot.aperture}
                </div>
                <div style={{ position: "absolute", bottom: 8, left: 10, fontSize: 8, color: "#c8ff0030" }}>
                  {shot.movement.map(m => CAMERA_MOVEMENTS.find(cm => cm.id === m)?.name).join(" + ")}
                </div>
                <div style={{ position: "absolute", bottom: 8, right: 10, fontSize: 8, color: "#c8ff0030" }}>
                  {shot.duration}s · {filmStock?.name || "Digital"}
                </div>

                {/* Recording indicator */}
                {generating && (
                  <div style={{
                    position: "absolute", top: 8, left: "50%", transform: "translateX(-50%)",
                    display: "flex", alignItems: "center", gap: 6, padding: "3px 10px",
                    background: "rgba(245,158,11,0.15)", borderRadius: 4, border: "1px solid #f59e0b30",
                  }}>
                    <div style={{
                      width: 6, height: 6, borderRadius: "50%", background: "#f59e0b",
                      animation: "pulse 1s ease-in-out infinite",
                    }} />
                    <span style={{ fontSize: 8, color: "#f59e0b", letterSpacing: 1 }}>GENERATING</span>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Prompt Bar */}
          <div style={{
            padding: "10px 16px", borderTop: "1px solid #141420",
            background: "#0a0a12",
          }}>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <span style={{ fontSize: 9, color: "#c8ff0080", fontWeight: 600 }}>PROMPT</span>
              <input
                value={promptInput}
                onChange={e => setPromptInput(e.target.value)}
                placeholder="Describe the shot... (camera settings applied automatically)"
                style={{
                  flex: 1, padding: "8px 12px", background: "#0d0d18", border: "1px solid #1a1a24",
                  borderRadius: 6, color: "#c8cad0", fontFamily: "inherit", fontSize: 11,
                  outline: "none",
                }}
                onFocus={e => e.target.style.borderColor = "#c8ff0040"}
                onBlur={e => e.target.style.borderColor = "#1a1a24"}
              />
              <button onClick={handleGenerate} style={{
                padding: "8px 16px", borderRadius: 6, border: "none",
                background: "#c8ff00", color: "#08080e", fontWeight: 700,
                fontSize: 10, cursor: "pointer", fontFamily: "inherit",
                letterSpacing: 1, whiteSpace: "nowrap",
              }}>
                HERO FRAME
              </button>
            </div>
          </div>
        </div>

        {/* ─── RIGHT: Controls Panel ─── */}
        <div style={{
          width: 320, borderLeft: "1px solid #141420", background: "#0a0a10",
          display: "flex", flexDirection: "column", flexShrink: 0,
        }}>
          {/* Panel Tabs */}
          <div style={{
            display: "flex", borderBottom: "1px solid #141420",
          }}>
            {[
              { id: "camera", label: "CAMERA" },
              { id: "post", label: "POST" },
              { id: "agents", label: "AGENTS" },
            ].map(tab => (
              <button key={tab.id} onClick={() => setRightPanel(tab.id)} style={{
                flex: 1, padding: "10px 0", fontSize: 8, letterSpacing: 2,
                border: "none", borderBottom: rightPanel === tab.id ? "2px solid #c8ff00" : "2px solid transparent",
                background: "transparent",
                color: rightPanel === tab.id ? "#c8ff00" : "#3a3a50",
                cursor: "pointer", fontFamily: "inherit", transition: "all 0.15s",
              }}>{tab.label}</button>
            ))}
          </div>

          {/* Panel Content */}
          <div style={{ flex: 1, overflow: "auto", padding: 12 }}>

            {/* ═══ CAMERA PANEL ═══ */}
            {rightPanel === "camera" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

                {/* Camera Body */}
                <div>
                  <div style={{ fontSize: 8, color: "#3a3a50", letterSpacing: 2, marginBottom: 8 }}>CAMERA BODY</div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
                    {CAMERA_BODIES.map(c => (
                      <button key={c.id} onClick={() => updateShot("camera", c.id)} style={{
                        display: "flex", justifyContent: "space-between", alignItems: "center",
                        padding: "6px 10px", borderRadius: 4, border: "none",
                        background: shot.camera === c.id ? "#16162a" : "transparent",
                        cursor: "pointer", fontFamily: "inherit", transition: "all 0.12s",
                      }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <span style={{ fontSize: 10, color: shot.camera === c.id ? "#e8e8f0" : "#6b6b80" }}>{c.name}</span>
                          <span style={{ fontSize: 7, color: "#3a3a50" }}>{c.sensor}</span>
                        </div>
                        <span style={{
                          fontSize: 6, padding: "1px 5px", borderRadius: 2, letterSpacing: 1,
                          background: shot.camera === c.id ? "#c8ff0015" : "#1a1a24",
                          color: shot.camera === c.id ? "#c8ff00" : "#3a3a50",
                          fontWeight: 700,
                        }}>{c.badge}</span>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Lens */}
                <div>
                  <div style={{ fontSize: 8, color: "#3a3a50", letterSpacing: 2, marginBottom: 8 }}>LENS</div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
                    {LENS_PROFILES.map(l => (
                      <button key={l.id} onClick={() => updateShot("lens", l.id)} style={{
                        display: "flex", justifyContent: "space-between", alignItems: "center",
                        padding: "6px 10px", borderRadius: 4, border: "none",
                        background: shot.lens === l.id ? "#16162a" : "transparent",
                        cursor: "pointer", fontFamily: "inherit", transition: "all 0.12s",
                        textAlign: "left",
                      }}>
                        <div>
                          <div style={{ fontSize: 10, color: shot.lens === l.id ? "#e8e8f0" : "#6b6b80" }}>{l.name}</div>
                          <div style={{ fontSize: 7, color: "#3a3a50", marginTop: 1 }}>{l.character}</div>
                        </div>
                        <span style={{
                          fontSize: 7, color: l.type === "anamorphic" ? "#f59e0b" : "#4a4a60",
                          letterSpacing: 1, whiteSpace: "nowrap",
                        }}>{l.type === "anamorphic" ? "ANA" : "SPH"}</span>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Focal / Aperture / Duration Knobs */}
                <div>
                  <div style={{ fontSize: 8, color: "#3a3a50", letterSpacing: 2, marginBottom: 10 }}>OPTICS</div>
                  <div style={{ display: "flex", justifyContent: "space-around" }}>
                    <Knob label="Focal" value={shot.focal} min={12} max={200} unit="mm"
                      onChange={v => updateShot("focal", v)} />
                    <Knob label="Aperture" value={shot.aperture} min={1.2} max={22} unit=""
                      onChange={v => updateShot("aperture", v)} accent="#818cf8" />
                    <Knob label="Duration" value={shot.duration} min={1} max={20} unit="s"
                      onChange={v => updateShot("duration", v)} accent="#4ade80" />
                  </div>
                </div>

                {/* Camera Movement */}
                <div>
                  <div style={{ fontSize: 8, color: "#3a3a50", letterSpacing: 2, marginBottom: 8 }}>
                    MOVEMENT <span style={{ color: "#2a2a3a" }}>· max 3</span>
                  </div>
                  <PillSelect
                    options={CAMERA_MOVEMENTS}
                    value={shot.movement[0]}
                    onChange={v => {
                      const current = shot.movement;
                      if (current.includes(v)) {
                        updateShot("movement", current.filter(m => m !== v));
                      } else if (current.length < 3) {
                        updateShot("movement", [...current, v]);
                      }
                    }}
                  />
                  {shot.movement.length > 0 && (
                    <div style={{ marginTop: 6, fontSize: 9, color: "#6b6b80" }}>
                      Active: {shot.movement.map(m => CAMERA_MOVEMENTS.find(cm => cm.id === m)?.name).join(" → ")}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* ═══ POST PANEL ═══ */}
            {rightPanel === "post" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                {/* Film Stock */}
                <div>
                  <div style={{ fontSize: 8, color: "#3a3a50", letterSpacing: 2, marginBottom: 8 }}>FILM STOCK</div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
                    {FILM_STOCKS.map(f => (
                      <button key={f.id} onClick={() => updateShot("filmStock", f.id)} style={{
                        display: "flex", justifyContent: "space-between", alignItems: "center",
                        padding: "6px 10px", borderRadius: 4, border: "none",
                        background: shot.filmStock === f.id ? "#16162a" : "transparent",
                        cursor: "pointer", fontFamily: "inherit", transition: "all 0.12s",
                        textAlign: "left",
                      }}>
                        <div>
                          <div style={{ fontSize: 10, color: shot.filmStock === f.id ? "#e8e8f0" : "#6b6b80" }}>{f.name}</div>
                          {f.character && <div style={{ fontSize: 7, color: "#3a3a50", marginTop: 1 }}>{f.character}</div>}
                        </div>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Color Grading (placeholder controls) */}
                <div>
                  <div style={{ fontSize: 8, color: "#3a3a50", letterSpacing: 2, marginBottom: 10 }}>COLOR</div>
                  <div style={{ display: "flex", justifyContent: "space-around" }}>
                    <Knob label="Temp" value={5600} min={2500} max={10000} unit="K" accent="#f59e0b" />
                    <Knob label="Tint" value={0} min={-50} max={50} unit="" accent="#a78bfa" />
                    <Knob label="Grain" value={25} min={0} max={100} unit="%" accent="#6b6b80" />
                  </div>
                </div>

                {/* Bloom / Halation */}
                <div>
                  <div style={{ fontSize: 8, color: "#3a3a50", letterSpacing: 2, marginBottom: 10 }}>OPTICAL FX</div>
                  <div style={{ display: "flex", justifyContent: "space-around" }}>
                    <Knob label="Bloom" value={15} min={0} max={100} unit="%" accent="#fbbf24" />
                    <Knob label="Halation" value={10} min={0} max={100} unit="%" accent="#f472b6" />
                    <Knob label="Vignette" value={30} min={0} max={100} unit="%" accent="#6b6b80" />
                  </div>
                </div>

                {/* DI Agent Status */}
                <div style={{
                  padding: 10, background: "#0d0d18", borderRadius: 6, border: "1px solid #1a1a24",
                }}>
                  <div style={{ fontSize: 8, color: "#f59e0b", letterSpacing: 2, marginBottom: 6 }}>DI AGENT</div>
                  <div style={{ fontSize: 9, color: "#6b6b80", lineHeight: 1.5 }}>
                    Auto-applies film stock emulation + color grade to generated frames.
                    Matches Dehancer profiles for photochemical accuracy.
                  </div>
                  <div style={{ marginTop: 8, display: "flex", gap: 4 }}>
                    <span style={{ fontSize: 7, padding: "2px 6px", background: "#2a2210", color: "#f59e0b", borderRadius: 3 }}>ACTIVE</span>
                    <span style={{ fontSize: 7, padding: "2px 6px", background: "#1a1a24", color: "#3a3a50", borderRadius: 3 }}>LUT: {filmStock?.name || "None"}</span>
                  </div>
                </div>
              </div>
            )}

            {/* ═══ AGENTS PANEL ═══ */}
            {rightPanel === "agents" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                <div style={{ fontSize: 8, color: "#3a3a50", letterSpacing: 2 }}>AGENT ACTIVITY</div>
                {AGENT_FEED.map((item, i) => (
                  <AgentFeedItem key={i} item={item} />
                ))}

                <div style={{ marginTop: 8, padding: 10, background: "#0d0d18", borderRadius: 6, border: "1px solid #1a1a24" }}>
                  <div style={{ fontSize: 8, color: "#818cf8", letterSpacing: 2, marginBottom: 6 }}>STYLE LOCK</div>
                  <div style={{ fontSize: 9, color: "#6b6b80", lineHeight: 1.5 }}>
                    Luna is tracking visual consistency across {shots.length} shots.
                    Camera: {camera?.name} · Lens: {lens?.name} · Stock: {filmStock?.name}
                  </div>
                  <div style={{ marginTop: 6, fontSize: 8, color: "#4a4a60" }}>
                    Character anchors: Cornelius ✓ · Mordecai ✓ · Constance — · Princess —
                  </div>
                </div>

                {/* Agent Roster */}
                <div style={{ marginTop: 4 }}>
                  <div style={{ fontSize: 8, color: "#3a3a50", letterSpacing: 2, marginBottom: 8 }}>AGENT ROSTER</div>
                  {[
                    { name: "Chiba", role: "Orchestrator", status: "active", color: "#c8ff00" },
                    { name: "Maya", role: "Vision / Consistency", status: "active", color: "#4ade80" },
                    { name: "DI Agent", role: "Color / Post", status: "active", color: "#f59e0b" },
                    { name: "Foley", role: "Audio / SFX", status: "standby", color: "#6b6b80" },
                    { name: "Luna", role: "Memory / Style Lock", status: "active", color: "#818cf8" },
                  ].map(a => (
                    <div key={a.name} style={{
                      display: "flex", justifyContent: "space-between", alignItems: "center",
                      padding: "6px 8px", borderRadius: 4, marginBottom: 2,
                    }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <div style={{
                          width: 6, height: 6, borderRadius: "50%",
                          background: a.status === "active" ? a.color : "#2a2a3a",
                          boxShadow: a.status === "active" ? `0 0 6px ${a.color}40` : "none",
                        }} />
                        <span style={{ fontSize: 10, color: "#e8e8f0" }}>{a.name}</span>
                      </div>
                      <span style={{ fontSize: 7, color: "#3a3a50" }}>{a.role}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ═══ BOTTOM BAR — Mini Timeline ═══ */}
      <div style={{
        height: 64, borderTop: "1px solid #141420", background: "#06060a",
        display: "flex", alignItems: "center", padding: "0 16px", gap: 4,
        flexShrink: 0,
      }}>
        <span style={{ fontSize: 8, color: "#3a3a50", letterSpacing: 2, marginRight: 12, minWidth: 60 }}>TIMELINE</span>
        {shots.map(s => {
          const st = STATUS_CONFIG[s.status];
          const widthPx = Math.max(s.duration * 12, 32);
          return (
            <div key={s.id} onClick={() => setSelectedShot(s.id)}
              style={{
                width: widthPx, height: 32, borderRadius: 3,
                background: s.id === selectedShot ? "#1a1a2e" : st.bg,
                border: `1px solid ${s.id === selectedShot ? "#c8ff0040" : "#1a1a24"}`,
                cursor: "pointer", position: "relative", overflow: "hidden",
                display: "flex", alignItems: "center", justifyContent: "center",
                transition: "all 0.15s",
              }}>
              <span style={{ fontSize: 7, color: st.color, fontWeight: 600 }}>{s.id.replace("sh0", "")}</span>
              {s.status === "rendering" && (
                <div style={{
                  position: "absolute", bottom: 0, left: 0, right: 0, height: 2,
                  background: `linear-gradient(90deg, #f59e0b 60%, transparent 60%)`,
                }} />
              )}
            </div>
          );
        })}
        <div style={{ flex: 1 }} />
        <span style={{ fontSize: 8, color: "#2a2a3a" }}>
          {shots.reduce((a, s) => a + s.duration, 0)}s · {shots.length} shots · {shots.filter(s => s.status === "approved" || s.status === "locked").length} locked
        </span>
      </div>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.3; }
        }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #1a1a24; border-radius: 2px; }
        ::-webkit-scrollbar-thumb:hover { background: #2a2a3a; }
        * { box-sizing: border-box; }
      `}</style>
    </div>
  );
}
