import { useState, useCallback, useRef, useEffect, useMemo } from "react";

// ============================================================================
// KOZMO LAB — Production Pipeline
// From SCRIBO annotation → Production Brief → Camera Rig → Eden Dispatch
// Queue → Shot Builder → Sequence Storyboard
// ============================================================================

// --- Camera System ---
const CAMERA_BODIES = [
  { id: "arri_alexa35", name: "ARRI Alexa 35", badge: "CINEMA", color: "#4ade80" },
  { id: "red_v_raptor", name: "RED V-Raptor", badge: "CINEMA", color: "#4ade80" },
  { id: "sony_venice2", name: "Sony Venice 2", badge: "CINEMA", color: "#4ade80" },
  { id: "bmpcc_6k", name: "Blackmagic 6K", badge: "INDIE", color: "#fbbf24" },
  { id: "16mm_bolex", name: "16mm Bolex", badge: "FILM", color: "#f472b6" },
  { id: "vhs_camcorder", name: "VHS Camcorder", badge: "LO-FI", color: "#f87171" },
];

const LENS_PROFILES = [
  { id: "cooke_s7i", name: "Cooke S7/i", type: "spherical", character: "Warm, organic flares", range: [18, 135] },
  { id: "panavision_c", name: "Panavision C-Series", type: "anamorphic", character: "Oval bokeh, blue streaks", range: [35, 100] },
  { id: "zeiss_supreme", name: "Zeiss Supreme", type: "spherical", character: "Clinical precision", range: [15, 200] },
  { id: "atlas_mercury", name: "Atlas Mercury", type: "anamorphic", character: "Modern ana, warm", range: [28, 100] },
  { id: "canon_k35", name: "Canon K35", type: "spherical", character: "70s softness, vintage", range: [18, 85] },
  { id: "helios_44", name: "Helios 44-2", type: "spherical", character: "Swirly bokeh, Soviet", range: [58, 58] },
];

const MOVEMENTS = [
  { id: "static", name: "Static", icon: "◻" },
  { id: "dolly_in", name: "Dolly In", icon: "→◎" },
  { id: "dolly_out", name: "Dolly Out", icon: "◎→" },
  { id: "pan_left", name: "Pan L", icon: "←" },
  { id: "pan_right", name: "Pan R", icon: "→" },
  { id: "tilt_up", name: "Tilt Up", icon: "↑" },
  { id: "tilt_down", name: "Tilt Down", icon: "↓" },
  { id: "crane_up", name: "Crane Up", icon: "⤴" },
  { id: "crane_down", name: "Crane Down", icon: "⤵" },
  { id: "orbit_cw", name: "Orbit CW", icon: "↻" },
  { id: "handheld", name: "Handheld", icon: "〰" },
  { id: "steadicam", name: "Steadicam", icon: "≋" },
];

const FILM_STOCKS = [
  { id: "none", name: "Digital Clean", character: "No grain" },
  { id: "kodak_5219", name: "Kodak 5219 (500T)", character: "Warm tungsten, cinema" },
  { id: "kodak_5207", name: "Kodak 5207 (250D)", character: "Daylight, neutral" },
  { id: "fuji_eterna", name: "Fuji Eterna Vivid", character: "Rich greens, cool" },
  { id: "cinestill_800", name: "CineStill 800T", character: "Halation, neon warmth" },
  { id: "ilford_hp5", name: "Ilford HP5+ (B&W)", character: "Punchy contrast" },
];

// --- Production Briefs (from SCRIBO annotations) ---
const INITIAL_BRIEFS = [
  {
    id: "pb_001",
    type: "single",
    status: "rigging",
    priority: "high",
    title: "Blackstone Hollow — Establishing Shot",
    sourceScene: "Part One: The Departure",
    sourceAnnotation: "a3",
    sourceParagraph: "They had lived together for seven years in the cottage at Blackstone Hollow...",
    prompt: "Establishing wide shot, stone cottage at Blackstone Hollow, overgrown garden, morning mist, oversized doorframe for a dinosaur, fantasy realism",
    characters: ["Cornelius", "Mordecai"],
    location: "Blackstone Hollow",
    assignee: "Maya",
    createdAt: "2:20 PM",
    camera: {
      body: "arri_alexa35", lens: "cooke_s7i", focal: 24, aperture: 5.6,
      movement: ["static"], duration: 4.0,
    },
    post: {
      stock: "kodak_5219", colorTemp: 5200, grain: 8, bloom: 5, halation: 0,
    },
    heroFrame: null,
    edenTaskId: null,
  },
  {
    id: "pb_002",
    type: "sequence",
    status: "planning",
    priority: "high",
    title: "The Road North — Travel Montage",
    sourceScene: "Part One: The Departure",
    sourceAnnotation: "a7",
    sourceParagraph: "The road north was not kind to creatures of his size...",
    assignee: "Chiba",
    createdAt: "2:31 PM",
    characters: ["Cornelius"],
    location: "The Road North",
    shots: [
      {
        id: "pb_002_01", title: "Low Branch Duck",
        prompt: "Cornelius the dinosaur ducking under a low oak branch on a forest path, dappled morning light filtering through leaves, fantasy realism",
        status: "rigging",
        camera: { body: "arri_alexa35", lens: "panavision_c", focal: 40, aperture: 2.8, movement: ["dolly_in"], duration: 3.0 },
        post: { stock: "kodak_5219", colorTemp: 5600, grain: 10, bloom: 3, halation: 0 },
        heroFrame: null,
      },
      {
        id: "pb_002_02", title: "Narrow Bridge",
        prompt: "Narrow stone bridge over rushing river, massive gentle dinosaur testing it with one cautious foot, vertigo angle from below, fantasy realism",
        status: "planning",
        camera: { body: "arri_alexa35", lens: "zeiss_supreme", focal: 18, aperture: 4.0, movement: ["tilt_up"], duration: 3.5 },
        post: { stock: "kodak_5219", colorTemp: 5600, grain: 10, bloom: 0, halation: 0 },
        heroFrame: null,
      },
      {
        id: "pb_002_03", title: "Scale — The Vast Road",
        prompt: "Extreme wide shot, vast green rolling landscape under grey sky, tiny dinosaur figure on a winding dirt road, sense of epic scale and loneliness, fantasy realism",
        status: "planning",
        camera: { body: "arri_alexa35", lens: "zeiss_supreme", focal: 135, aperture: 8.0, movement: ["static"], duration: 5.0 },
        post: { stock: "kodak_5207", colorTemp: 5600, grain: 5, bloom: 8, halation: 0 },
        heroFrame: null,
      },
      {
        id: "pb_002_04", title: "The Satchel Detail",
        prompt: "Close-up of worn leather satchel bouncing on dinosaur's hip as he walks, shallow depth of field, texture detail on leather and scales, fantasy realism",
        status: "planning",
        camera: { body: "arri_alexa35", lens: "cooke_s7i", focal: 85, aperture: 1.8, movement: ["handheld"], duration: 2.5 },
        post: { stock: "kodak_5219", colorTemp: 5200, grain: 15, bloom: 0, halation: 0 },
        heroFrame: null,
      },
    ],
  },
  {
    id: "pb_003",
    type: "reference",
    status: "pending",
    priority: "medium",
    title: "Cornelius in the Garden — Reference Art",
    sourceScene: "Part One: The Departure",
    sourceAnnotation: "a5",
    sourceParagraph: "Cornelius maintained the garden, read voraciously...",
    prompt: "Gentle dinosaur tending a vegetable garden in morning light, peaceful domestic scene, overgrown cottage in background, warm golden hour, fantasy realism",
    characters: ["Cornelius"],
    location: "Blackstone Hollow",
    assignee: "Maya",
    createdAt: "2:24 PM",
    camera: null,
    post: null,
    heroFrame: null,
    edenTaskId: null,
  },
  {
    id: "pb_004",
    type: "single",
    status: "generating",
    priority: "medium",
    title: "Bottles and Books — Close-up",
    sourceScene: "Part One: The Departure",
    sourceAnnotation: "a4",
    sourceParagraph: "Mordecai kept his study cluttered with grimoires and bottles...",
    prompt: "Close-up of cluttered wizard's desk, grimoires and empty bottles, bottles outnumbering books, warm candlelight, dust motes, shallow DOF, fantasy realism",
    characters: ["Mordecai"],
    location: "Blackstone Hollow — Study",
    assignee: "Maya",
    createdAt: "2:22 PM",
    camera: {
      body: "arri_alexa35", lens: "cooke_s7i", focal: 65, aperture: 2.0,
      movement: ["dolly_in"], duration: 3.0,
    },
    post: {
      stock: "kodak_5219", colorTemp: 3200, grain: 12, bloom: 8, halation: 3,
    },
    heroFrame: null,
    edenTaskId: "eden_task_78f2a",
    progress: 62,
  },
];

// --- Status config ---
const STATUS_CONFIG = {
  planning: { color: "#64748b", label: "Planning", icon: "○" },
  pending: { color: "#818cf8", label: "Pending", icon: "◔" },
  rigging: { color: "#fbbf24", label: "Rigging", icon: "◑" },
  queued: { color: "#c084fc", label: "Queued", icon: "◕" },
  generating: { color: "#34d399", label: "Generating", icon: "◉" },
  review: { color: "#38bdf8", label: "Review", icon: "◈" },
  approved: { color: "#4ade80", label: "Approved", icon: "✓" },
  locked: { color: "#4ade80", label: "Locked", icon: "◆" },
};

const PRIORITY_CONFIG = {
  high: { color: "#f87171", label: "HIGH" },
  medium: { color: "#fbbf24", label: "MED" },
  low: { color: "#64748b", label: "LOW" },
};

// ============================================================================
// Components
// ============================================================================

// --- Camera Control Knob ---
function CameraKnob({ label, value, onChange, items, renderItem }) {
  const [open, setOpen] = useState(false);

  return (
    <div style={{ position: "relative" }}>
      <div
        onClick={() => setOpen(!open)}
        style={{
          padding: "6px 10px", borderRadius: 4, cursor: "pointer",
          background: "rgba(10, 10, 15, 0.8)", border: "1px solid #1e1e2e",
          transition: "border-color 0.15s",
        }}
        onMouseEnter={e => e.currentTarget.style.borderColor = "#818cf830"}
        onMouseLeave={e => { if (!open) e.currentTarget.style.borderColor = "#1e1e2e"; }}
      >
        <div style={{ color: "#4a4a5a", fontSize: 8, fontFamily: "'JetBrains Mono', monospace", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 2 }}>
          {label}
        </div>
        <div style={{ color: "#e2e8f0", fontSize: 12, fontFamily: "'Space Grotesk', sans-serif" }}>
          {renderItem ? renderItem(value) : value}
        </div>
      </div>
      {open && (
        <div style={{
          position: "absolute", top: "100%", left: 0, zIndex: 100,
          marginTop: 4, minWidth: 200, maxHeight: 240, overflow: "auto",
          background: "rgba(12, 12, 18, 0.98)", border: "1px solid #1e1e2e",
          borderRadius: 6, backdropFilter: "blur(12px)",
          boxShadow: "0 8px 32px rgba(0,0,0,0.5)",
        }}>
          {items.map(item => (
            <div
              key={item.id || item}
              onClick={() => { onChange(item.id || item); setOpen(false); }}
              style={{
                padding: "8px 12px", cursor: "pointer",
                background: (item.id || item) === value ? "rgba(129, 140, 248, 0.1)" : "transparent",
                borderLeft: (item.id || item) === value ? "2px solid #818cf8" : "2px solid transparent",
                transition: "all 0.1s",
              }}
              onMouseEnter={e => e.currentTarget.style.background = "rgba(255,255,255,0.03)"}
              onMouseLeave={e => e.currentTarget.style.background = (item.id || item) === value ? "rgba(129, 140, 248, 0.1)" : "transparent"}
            >
              <div style={{ color: "#e2e8f0", fontSize: 12 }}>{item.name || item}</div>
              {item.character && (
                <div style={{ color: "#4a4a5a", fontSize: 10, marginTop: 1 }}>{item.character}</div>
              )}
              {item.badge && (
                <span style={{
                  color: item.color || "#64748b", fontSize: 8,
                  padding: "1px 4px", borderRadius: 2,
                  background: (item.color || "#64748b") + "15",
                  fontFamily: "'JetBrains Mono', monospace",
                  marginLeft: 6,
                }}>
                  {item.badge}
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// --- Slider Control ---
function SliderControl({ label, value, onChange, min = 0, max = 100, suffix = "" }) {
  return (
    <div style={{ padding: "4px 0" }}>
      <div style={{
        display: "flex", justifyContent: "space-between", marginBottom: 4,
      }}>
        <span style={{ color: "#4a4a5a", fontSize: 9, fontFamily: "'JetBrains Mono', monospace", textTransform: "uppercase", letterSpacing: "0.06em" }}>
          {label}
        </span>
        <span style={{ color: "#818cf8", fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }}>
          {value}{suffix}
        </span>
      </div>
      <input
        type="range" min={min} max={max} value={value}
        onChange={e => onChange(Number(e.target.value))}
        style={{
          width: "100%", height: 3, appearance: "none",
          background: `linear-gradient(to right, #818cf8 ${((value - min) / (max - min)) * 100}%, #1e1e2e ${((value - min) / (max - min)) * 100}%)`,
          borderRadius: 2, outline: "none", cursor: "pointer",
        }}
      />
    </div>
  );
}

// --- Movement Selector (max 3) ---
function MovementSelector({ selected, onChange }) {
  const toggle = (id) => {
    if (selected.includes(id)) {
      onChange(selected.filter(m => m !== id));
    } else if (selected.length < 3) {
      onChange([...selected, id]);
    }
  };

  return (
    <div>
      <div style={{
        display: "flex", justifyContent: "space-between", marginBottom: 6,
      }}>
        <span style={{ color: "#4a4a5a", fontSize: 9, fontFamily: "'JetBrains Mono', monospace", textTransform: "uppercase", letterSpacing: "0.06em" }}>
          Movement
        </span>
        <span style={{ color: "#2a2a3a", fontSize: 9, fontFamily: "'JetBrains Mono', monospace" }}>
          {selected.length}/3
        </span>
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 3 }}>
        {MOVEMENTS.map(m => {
          const isSelected = selected.includes(m.id);
          return (
            <button
              key={m.id}
              onClick={() => toggle(m.id)}
              style={{
                padding: "3px 7px", borderRadius: 3,
                border: `1px solid ${isSelected ? "#818cf840" : "#1e1e2e"}`,
                background: isSelected ? "rgba(129, 140, 248, 0.1)" : "transparent",
                color: isSelected ? "#818cf8" : "#4a4a5a",
                fontSize: 9, cursor: "pointer",
                fontFamily: "'JetBrains Mono', monospace",
                opacity: !isSelected && selected.length >= 3 ? 0.3 : 1,
              }}
            >
              {m.icon} {m.name}
            </button>
          );
        })}
      </div>
    </div>
  );
}

// --- Brief Card (Queue view) ---
function BriefCard({ brief, isSelected, onClick }) {
  const status = STATUS_CONFIG[brief.status] || STATUS_CONFIG.planning;
  const priority = PRIORITY_CONFIG[brief.priority] || PRIORITY_CONFIG.medium;

  return (
    <div
      onClick={() => onClick(brief.id)}
      style={{
        padding: "12px 14px", borderRadius: 6, cursor: "pointer",
        background: isSelected ? "rgba(129, 140, 248, 0.06)" : "rgba(18, 18, 26, 0.4)",
        border: `1px solid ${isSelected ? "#818cf830" : "#1e1e2e"}`,
        marginBottom: 6, transition: "all 0.15s",
      }}
      onMouseEnter={e => { if (!isSelected) e.currentTarget.style.borderColor = "#1e1e2e80"; }}
      onMouseLeave={e => { if (!isSelected) e.currentTarget.style.borderColor = "#1e1e2e"; }}
    >
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
        <span style={{ color: status.color, fontSize: 11 }}>{status.icon}</span>
        <span style={{
          color: status.color, fontSize: 9, padding: "1px 5px", borderRadius: 2,
          background: status.color + "15", fontFamily: "'JetBrains Mono', monospace",
        }}>
          {status.label}
        </span>
        <span style={{
          color: priority.color, fontSize: 8, padding: "1px 4px", borderRadius: 2,
          border: `1px solid ${priority.color}30`,
          fontFamily: "'JetBrains Mono', monospace",
        }}>
          {priority.label}
        </span>
        {brief.type === "sequence" && (
          <span style={{
            color: "#c084fc", fontSize: 8, padding: "1px 4px", borderRadius: 2,
            background: "rgba(192, 132, 252, 0.1)",
            fontFamily: "'JetBrains Mono', monospace",
          }}>
            {brief.shots.length} SHOTS
          </span>
        )}
        {brief.type === "reference" && (
          <span style={{
            color: "#34d399", fontSize: 8, padding: "1px 4px", borderRadius: 2,
            background: "rgba(52, 211, 153, 0.1)",
            fontFamily: "'JetBrains Mono', monospace",
          }}>
            REF
          </span>
        )}
        <span style={{ color: "#2a2a3a", fontSize: 9, marginLeft: "auto" }}>
          → {brief.assignee}
        </span>
      </div>

      {/* Title */}
      <div style={{
        color: "#e2e8f0", fontSize: 13,
        fontFamily: "'Space Grotesk', sans-serif", fontWeight: 500,
        marginBottom: 4,
      }}>
        {brief.title}
      </div>

      {/* Source */}
      <div style={{
        color: "#4a4a5a", fontSize: 10,
        fontFamily: "'JetBrains Mono', monospace",
        display: "flex", alignItems: "center", gap: 4,
      }}>
        <span style={{ color: "#c084fc" }}>SCRIBO</span>
        <span>›</span>
        <span>{brief.sourceScene}</span>
      </div>

      {/* Progress bar for generating */}
      {brief.status === "generating" && brief.progress != null && (
        <div style={{ marginTop: 8 }}>
          <div style={{
            height: 2, borderRadius: 1, background: "#1e1e2e", overflow: "hidden",
          }}>
            <div style={{
              width: `${brief.progress}%`, height: "100%",
              background: "linear-gradient(90deg, #34d399, #4ade80)",
              borderRadius: 1, transition: "width 0.5s ease",
            }} />
          </div>
          <div style={{
            color: "#34d399", fontSize: 9, marginTop: 3, textAlign: "right",
            fontFamily: "'JetBrains Mono', monospace",
          }}>
            {brief.progress}% · Eden generating...
          </div>
        </div>
      )}

      {/* Characters */}
      <div style={{ display: "flex", gap: 4, marginTop: 6, flexWrap: "wrap" }}>
        {brief.characters.map(c => (
          <span key={c} style={{
            padding: "1px 6px", borderRadius: 2, fontSize: 9,
            color: c === "Cornelius" ? "#4ade80" : c === "Mordecai" ? "#a78bfa" : "#94a3b8",
            background: (c === "Cornelius" ? "#4ade80" : c === "Mordecai" ? "#a78bfa" : "#94a3b8") + "12",
            fontFamily: "'JetBrains Mono', monospace",
          }}>
            {c}
          </span>
        ))}
      </div>
    </div>
  );
}

// --- Shot Builder (full camera rig for a single shot) ---
function ShotBuilder({ brief, shot }) {
  const data = shot || brief;
  const cam = data.camera || { body: "arri_alexa35", lens: "cooke_s7i", focal: 50, aperture: 2.8, movement: ["static"], duration: 3.0 };
  const post = data.post || { stock: "kodak_5219", colorTemp: 5600, grain: 0, bloom: 0, halation: 0 };

  const [camera, setCamera] = useState(cam);
  const [postConfig, setPostConfig] = useState(post);
  const [prompt, setPrompt] = useState(data.prompt || brief.prompt || "");

  const bodyInfo = CAMERA_BODIES.find(b => b.id === camera.body);
  const lensInfo = LENS_PROFILES.find(l => l.id === camera.lens);

  // Build the prompt preview
  const fullPrompt = useMemo(() => {
    const parts = [prompt];
    if (bodyInfo) parts.push(`Shot on ${bodyInfo.name}.`);
    if (lensInfo) parts.push(`${lensInfo.name} ${lensInfo.type} lens, ${camera.focal}mm, f/${camera.aperture}.`);
    const stockInfo = FILM_STOCKS.find(s => s.id === postConfig.stock);
    if (stockInfo && stockInfo.id !== "none") parts.push(`${stockInfo.name} film stock.`);
    if (camera.movement.filter(m => m !== "static").length > 0) {
      const moves = camera.movement.filter(m => m !== "static").map(m => MOVEMENTS.find(mv => mv.id === m)?.name).join(" + ");
      parts.push(`Camera movement: ${moves}.`);
    }
    return parts.join(" ");
  }, [prompt, camera, postConfig, bodyInfo, lensInfo]);

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      {/* Hero frame canvas */}
      <div style={{
        aspectRatio: "21/9", width: "100%", flexShrink: 0,
        background: "rgba(10, 10, 15, 0.8)",
        border: "1px solid #1e1e2e", borderRadius: 6,
        display: "flex", alignItems: "center", justifyContent: "center",
        position: "relative", overflow: "hidden",
      }}>
        {/* Viewfinder grid */}
        <div style={{ position: "absolute", inset: 0, pointerEvents: "none" }}>
          {/* Rule of thirds */}
          <div style={{ position: "absolute", left: "33.33%", top: 0, bottom: 0, width: 1, background: "rgba(255,255,255,0.04)" }} />
          <div style={{ position: "absolute", left: "66.66%", top: 0, bottom: 0, width: 1, background: "rgba(255,255,255,0.04)" }} />
          <div style={{ position: "absolute", top: "33.33%", left: 0, right: 0, height: 1, background: "rgba(255,255,255,0.04)" }} />
          <div style={{ position: "absolute", top: "66.66%", left: 0, right: 0, height: 1, background: "rgba(255,255,255,0.04)" }} />
          {/* Corner marks */}
          {[[0,0],[1,0],[0,1],[1,1]].map(([x,y], i) => (
            <div key={i} style={{
              position: "absolute",
              [x ? "right" : "left"]: 12, [y ? "bottom" : "top"]: 8,
              width: 16, height: 16,
              borderTop: y ? "none" : "1px solid rgba(255,255,255,0.1)",
              borderBottom: y ? "1px solid rgba(255,255,255,0.1)" : "none",
              borderLeft: x ? "none" : "1px solid rgba(255,255,255,0.1)",
              borderRight: x ? "1px solid rgba(255,255,255,0.1)" : "none",
            }} />
          ))}
        </div>
        {/* Center content */}
        <div style={{ textAlign: "center", zIndex: 1 }}>
          <div style={{ fontSize: 28, color: "#1e1e2e", marginBottom: 8 }}>◎</div>
          <div style={{ color: "#2a2a3a", fontSize: 11, fontFamily: "'JetBrains Mono', monospace" }}>
            21:9 · {camera.focal}mm · f/{camera.aperture}
          </div>
          <div style={{ color: "#1e1e2e", fontSize: 10, marginTop: 4, fontFamily: "'JetBrains Mono', monospace" }}>
            {brief.status === "generating" ? "Eden generating..." : "No hero frame yet"}
          </div>
        </div>
        {/* Camera info overlay */}
        <div style={{
          position: "absolute", bottom: 8, left: 12, right: 12,
          display: "flex", justifyContent: "space-between", alignItems: "flex-end",
        }}>
          <div style={{
            color: "#4a4a5a", fontSize: 9, fontFamily: "'JetBrains Mono', monospace",
            background: "rgba(10, 10, 15, 0.7)", padding: "2px 6px", borderRadius: 2,
          }}>
            {bodyInfo?.name} · {lensInfo?.name} {lensInfo?.type}
          </div>
          <div style={{
            color: "#4a4a5a", fontSize: 9, fontFamily: "'JetBrains Mono', monospace",
            background: "rgba(10, 10, 15, 0.7)", padding: "2px 6px", borderRadius: 2,
          }}>
            {camera.duration}s · {camera.movement.join(" + ")}
          </div>
        </div>
      </div>

      {/* Controls */}
      <div style={{ flex: 1, overflow: "auto", paddingTop: 12 }}>
        {/* Prompt */}
        <div style={{ marginBottom: 12 }}>
          <div style={{ color: "#4a4a5a", fontSize: 9, fontFamily: "'JetBrains Mono', monospace", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>
            Scene Prompt
          </div>
          <textarea
            value={prompt} onChange={e => setPrompt(e.target.value)}
            style={{
              width: "100%", minHeight: 60, padding: 8, borderRadius: 4,
              background: "rgba(10, 10, 15, 0.8)", border: "1px solid #1e1e2e",
              color: "#e2e8f0", fontSize: 12, resize: "vertical",
              fontFamily: "'Space Grotesk', sans-serif", outline: "none", lineHeight: 1.5,
            }}
            onFocus={e => e.currentTarget.style.borderColor = "#818cf830"}
            onBlur={e => e.currentTarget.style.borderColor = "#1e1e2e"}
          />
        </div>

        {/* Camera row */}
        <div style={{
          display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6, marginBottom: 12,
        }}>
          <CameraKnob
            label="Camera Body" value={camera.body}
            onChange={v => setCamera({ ...camera, body: v })}
            items={CAMERA_BODIES}
            renderItem={v => CAMERA_BODIES.find(b => b.id === v)?.name}
          />
          <CameraKnob
            label="Lens" value={camera.lens}
            onChange={v => setCamera({ ...camera, lens: v })}
            items={LENS_PROFILES}
            renderItem={v => LENS_PROFILES.find(l => l.id === v)?.name}
          />
        </div>

        {/* Focal + Aperture */}
        <div style={{
          display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6, marginBottom: 12,
        }}>
          <SliderControl
            label="Focal Length" value={camera.focal}
            onChange={v => setCamera({ ...camera, focal: v })}
            min={lensInfo?.range[0] || 18} max={lensInfo?.range[1] || 200} suffix="mm"
          />
          <SliderControl
            label="Aperture" value={camera.aperture}
            onChange={v => setCamera({ ...camera, aperture: v })}
            min={1.2} max={16} suffix=""
          />
        </div>

        {/* Movement */}
        <div style={{ marginBottom: 12 }}>
          <MovementSelector
            selected={camera.movement}
            onChange={v => setCamera({ ...camera, movement: v.length ? v : ["static"] })}
          />
        </div>

        {/* Post */}
        <div style={{
          padding: "10px 0", borderTop: "1px solid #1e1e2e",
        }}>
          <div style={{ color: "#4a4a5a", fontSize: 9, fontFamily: "'JetBrains Mono', monospace", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>
            Post Processing
          </div>
          <div style={{ marginBottom: 8 }}>
            <CameraKnob
              label="Film Stock" value={postConfig.stock}
              onChange={v => setPostConfig({ ...postConfig, stock: v })}
              items={FILM_STOCKS}
              renderItem={v => FILM_STOCKS.find(s => s.id === v)?.name}
            />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
            <SliderControl label="Color Temp" value={postConfig.colorTemp} onChange={v => setPostConfig({ ...postConfig, colorTemp: v })} min={2800} max={8000} suffix="K" />
            <SliderControl label="Grain" value={postConfig.grain} onChange={v => setPostConfig({ ...postConfig, grain: v })} max={30} suffix="%" />
            <SliderControl label="Bloom" value={postConfig.bloom} onChange={v => setPostConfig({ ...postConfig, bloom: v })} max={30} suffix="%" />
            <SliderControl label="Halation" value={postConfig.halation} onChange={v => setPostConfig({ ...postConfig, halation: v })} max={20} suffix="%" />
          </div>
        </div>

        {/* Enriched prompt preview */}
        <div style={{
          padding: "10px 0", borderTop: "1px solid #1e1e2e",
        }}>
          <div style={{ color: "#4a4a5a", fontSize: 9, fontFamily: "'JetBrains Mono', monospace", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 6 }}>
            Enriched Prompt → Eden
          </div>
          <div style={{
            padding: 8, borderRadius: 4,
            background: "rgba(52, 211, 153, 0.04)",
            border: "1px solid rgba(52, 211, 153, 0.1)",
            color: "#94a3b8", fontSize: 11, lineHeight: 1.6,
            fontFamily: "'JetBrains Mono', monospace",
          }}>
            {fullPrompt}
          </div>
        </div>
      </div>

      {/* Action bar */}
      <div style={{
        display: "flex", gap: 6, padding: "10px 0",
        borderTop: "1px solid #1e1e2e",
      }}>
        <button style={{
          flex: 1, padding: "8px 12px", borderRadius: 4, border: "none",
          background: "rgba(52, 211, 153, 0.12)", color: "#34d399",
          fontSize: 12, cursor: "pointer", fontFamily: "'Space Grotesk', sans-serif",
          fontWeight: 500,
        }}>
          ◈ Generate via Eden
        </button>
        <button style={{
          padding: "8px 12px", borderRadius: 4,
          border: "1px solid #1e1e2e", background: "transparent",
          color: "#4a4a5a", fontSize: 12, cursor: "pointer",
        }}>
          Save Rig
        </button>
      </div>
    </div>
  );
}

// --- Sequence Storyboard ---
function SequenceStoryboard({ brief, onSelectShot, selectedShot }) {
  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      {/* Title */}
      <div style={{ padding: "12px 0", borderBottom: "1px solid #1e1e2e" }}>
        <div style={{ color: "#e2e8f0", fontSize: 15, fontFamily: "'Space Grotesk', sans-serif", fontWeight: 500 }}>
          {brief.title}
        </div>
        <div style={{ color: "#4a4a5a", fontSize: 11, marginTop: 4 }}>
          {brief.shots.length} shots · {brief.characters.join(", ")} · {brief.location}
        </div>
      </div>

      {/* Storyboard grid */}
      <div style={{
        flex: 1, overflow: "auto", paddingTop: 12,
        display: "grid", gridTemplateColumns: "1fr 1fr",
        gap: 8, alignContent: "start",
      }}>
        {brief.shots.map((shot, i) => {
          const isSelected = selectedShot === shot.id;
          const status = STATUS_CONFIG[shot.status] || STATUS_CONFIG.planning;
          return (
            <div
              key={shot.id}
              onClick={() => onSelectShot(shot.id)}
              style={{
                borderRadius: 6, overflow: "hidden", cursor: "pointer",
                border: `1px solid ${isSelected ? "#818cf840" : "#1e1e2e"}`,
                background: isSelected ? "rgba(129, 140, 248, 0.04)" : "rgba(18, 18, 26, 0.4)",
                transition: "all 0.15s",
              }}
            >
              {/* Mini frame */}
              <div style={{
                aspectRatio: "21/9", background: "rgba(10, 10, 15, 0.8)",
                display: "flex", alignItems: "center", justifyContent: "center",
                position: "relative",
              }}>
                <span style={{ color: "#1e1e2e", fontSize: 16, fontFamily: "'JetBrains Mono', monospace" }}>
                  {String(i + 1).padStart(2, "0")}
                </span>
                {/* Status badge */}
                <span style={{
                  position: "absolute", top: 4, right: 4,
                  color: status.color, fontSize: 7, padding: "1px 4px",
                  background: status.color + "15", borderRadius: 2,
                  fontFamily: "'JetBrains Mono', monospace",
                }}>
                  {status.label}
                </span>
                {/* Camera info */}
                <span style={{
                  position: "absolute", bottom: 4, left: 4,
                  color: "#2a2a3a", fontSize: 7, fontFamily: "'JetBrains Mono', monospace",
                }}>
                  {shot.camera.focal}mm f/{shot.camera.aperture}
                </span>
              </div>

              {/* Shot info */}
              <div style={{ padding: "6px 8px" }}>
                <div style={{
                  color: "#e2e8f0", fontSize: 11,
                  fontFamily: "'Space Grotesk', sans-serif", fontWeight: 500,
                  marginBottom: 2,
                }}>
                  {shot.title}
                </div>
                <div style={{
                  color: "#4a4a5a", fontSize: 9, lineHeight: 1.4,
                  display: "-webkit-box", WebkitLineClamp: 2,
                  WebkitBoxOrient: "vertical", overflow: "hidden",
                }}>
                  {shot.prompt}
                </div>
                {/* Movement tags */}
                <div style={{ display: "flex", gap: 3, marginTop: 4 }}>
                  {shot.camera.movement.map(m => {
                    const mv = MOVEMENTS.find(x => x.id === m);
                    return (
                      <span key={m} style={{
                        color: "#818cf8", fontSize: 8, padding: "1px 4px",
                        background: "rgba(129, 140, 248, 0.1)", borderRadius: 2,
                        fontFamily: "'JetBrains Mono', monospace",
                      }}>
                        {mv?.icon} {mv?.name}
                      </span>
                    );
                  })}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Batch actions */}
      <div style={{
        display: "flex", gap: 6, padding: "10px 0", borderTop: "1px solid #1e1e2e",
      }}>
        <button style={{
          flex: 1, padding: "8px 12px", borderRadius: 4, border: "none",
          background: "rgba(52, 211, 153, 0.12)", color: "#34d399",
          fontSize: 12, cursor: "pointer", fontFamily: "'Space Grotesk', sans-serif",
        }}>
          ◈ Generate All Shots
        </button>
        <button style={{
          padding: "8px 12px", borderRadius: 4,
          border: "1px solid #1e1e2e", background: "transparent",
          color: "#4a4a5a", fontSize: 12, cursor: "pointer",
        }}>
          Export Storyboard
        </button>
      </div>
    </div>
  );
}


// ============================================================================
// Main App
// ============================================================================

export default function LabPipeline() {
  const [briefs, setBriefs] = useState(INITIAL_BRIEFS);
  const [selectedBrief, setSelectedBrief] = useState("pb_001");
  const [selectedShot, setSelectedShot] = useState(null);
  const [queueFilter, setQueueFilter] = useState("all");

  const currentBrief = briefs.find(b => b.id === selectedBrief);
  const currentShot = currentBrief?.type === "sequence" && selectedShot
    ? currentBrief.shots.find(s => s.id === selectedShot)
    : null;

  const filteredBriefs = queueFilter === "all" ? briefs
    : briefs.filter(b => b.status === queueFilter);

  // Stats
  const stats = {
    total: briefs.length,
    generating: briefs.filter(b => b.status === "generating").length,
    rigging: briefs.filter(b => b.status === "rigging").length,
    planning: briefs.filter(b => b.status === "planning" || b.status === "pending").length,
    totalShots: briefs.reduce((sum, b) => sum + (b.type === "sequence" ? b.shots.length : 1), 0),
  };

  return (
    <div style={{
      width: "100%", height: "100vh", display: "flex", flexDirection: "column",
      background: "#0a0a0f", color: "#e2e8f0",
      fontFamily: "'Space Grotesk', -apple-system, sans-serif",
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@300;400;500&family=Crimson+Pro:ital,wght@0,300;0,400;0,500;1,300;1,400&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #1e1e2e; border-radius: 2px; }
        ::selection { background: rgba(192, 132, 252, 0.25); }
        input[type=range]::-webkit-slider-thumb { -webkit-appearance: none; width: 10px; height: 10px; border-radius: 50%; background: #818cf8; cursor: pointer; }
      `}</style>

      {/* Top bar */}
      <div style={{
        display: "flex", alignItems: "center", height: 40,
        borderBottom: "1px solid #1e1e2e", padding: "0 16px",
        background: "rgba(10, 10, 15, 0.9)", backdropFilter: "blur(12px)",
        gap: 12, flexShrink: 0,
      }}>
        <div style={{
          padding: "3px 10px", borderRadius: 4,
          background: "rgba(129, 140, 248, 0.1)",
          border: "1px solid rgba(129, 140, 248, 0.2)",
        }}>
          <span style={{ color: "#818cf8", fontSize: 11, fontWeight: 600, letterSpacing: "0.08em" }}>LAB</span>
        </div>

        <span style={{ color: "#4a4a5a", fontSize: 11 }}>Production Pipeline</span>

        <div style={{ flex: 1 }} />

        {/* Stats */}
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          {[
            { label: "Briefs", value: stats.total, color: "#e2e8f0" },
            { label: "Shots", value: stats.totalShots, color: "#c084fc" },
            { label: "Generating", value: stats.generating, color: "#34d399" },
            { label: "Rigging", value: stats.rigging, color: "#fbbf24" },
          ].map(s => (
            <div key={s.label} style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <span style={{ color: "#2a2a3a", fontSize: 9, fontFamily: "'JetBrains Mono', monospace" }}>
                {s.label}
              </span>
              <span style={{ color: s.color, fontSize: 12, fontWeight: 500 }}>{s.value}</span>
            </div>
          ))}
        </div>

        <div style={{ width: 1, height: 16, background: "#1e1e2e" }} />

        {/* Mode tabs */}
        {["SCRIBO", "CODEX", "LAB"].map(mode => (
          <span key={mode} style={{
            color: mode === "LAB" ? "#818cf8" : "#2a2a3a",
            fontSize: 10, fontFamily: "'JetBrains Mono', monospace",
            cursor: "pointer", letterSpacing: "0.08em",
            padding: "3px 6px", borderRadius: 3,
            background: mode === "LAB" ? "rgba(129, 140, 248, 0.08)" : "transparent",
          }}>
            {mode}
          </span>
        ))}
      </div>

      {/* Main */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>

        {/* Queue (left) */}
        <div style={{
          width: 300, borderRight: "1px solid #1e1e2e",
          display: "flex", flexDirection: "column",
          background: "rgba(10, 10, 15, 0.4)", flexShrink: 0,
        }}>
          {/* Queue header */}
          <div style={{
            padding: "10px 12px", borderBottom: "1px solid #1e1e2e",
            display: "flex", alignItems: "center", justifyContent: "space-between",
          }}>
            <span style={{ fontSize: 10, color: "#4a4a5a", fontFamily: "'JetBrains Mono', monospace", textTransform: "uppercase", letterSpacing: "0.08em" }}>
              Production Queue
            </span>
            <span style={{
              color: "#c084fc", fontSize: 9, padding: "2px 6px",
              background: "rgba(192, 132, 252, 0.1)", borderRadius: 3,
              fontFamily: "'JetBrains Mono', monospace",
            }}>
              from SCRIBO
            </span>
          </div>

          {/* Status filter */}
          <div style={{ display: "flex", gap: 2, padding: "6px 8px", borderBottom: "1px solid #1e1e2e", flexWrap: "wrap" }}>
            {[
              { id: "all", label: "All" },
              { id: "generating", label: "Gen" },
              { id: "rigging", label: "Rig" },
              { id: "planning", label: "Plan" },
            ].map(f => (
              <button
                key={f.id}
                onClick={() => setQueueFilter(f.id)}
                style={{
                  padding: "2px 6px", borderRadius: 3, border: "none",
                  background: queueFilter === f.id ? "rgba(255,255,255,0.06)" : "transparent",
                  color: queueFilter === f.id ? "#e2e8f0" : "#2a2a3a",
                  fontSize: 9, cursor: "pointer", fontFamily: "'JetBrains Mono', monospace",
                }}
              >
                {f.label}
              </button>
            ))}
          </div>

          {/* Brief list */}
          <div style={{ flex: 1, overflow: "auto", padding: 8 }}>
            {filteredBriefs.map(brief => (
              <BriefCard
                key={brief.id}
                brief={brief}
                isSelected={selectedBrief === brief.id}
                onClick={id => { setSelectedBrief(id); setSelectedShot(null); }}
              />
            ))}
          </div>
        </div>

        {/* Center + Right: Shot Builder or Sequence */}
        <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
          {currentBrief ? (
            currentBrief.type === "sequence" ? (
              <>
                {/* Storyboard */}
                <div style={{
                  flex: 1, padding: "0 16px",
                  display: "flex", flexDirection: "column",
                  borderRight: selectedShot ? "1px solid #1e1e2e" : "none",
                }}>
                  <SequenceStoryboard
                    brief={currentBrief}
                    onSelectShot={setSelectedShot}
                    selectedShot={selectedShot}
                  />
                </div>

                {/* Shot detail */}
                {currentShot && (
                  <div style={{ width: 380, padding: "0 16px", overflow: "auto", flexShrink: 0 }}>
                    <div style={{
                      padding: "12px 0", borderBottom: "1px solid #1e1e2e", marginBottom: 12,
                      display: "flex", alignItems: "center", gap: 8,
                    }}>
                      <span style={{ color: "#818cf8", fontSize: 12 }}>◎</span>
                      <span style={{ color: "#e2e8f0", fontSize: 14, fontWeight: 500 }}>
                        {currentShot.title}
                      </span>
                      <span
                        onClick={() => setSelectedShot(null)}
                        style={{ marginLeft: "auto", color: "#2a2a3a", cursor: "pointer", fontSize: 14 }}
                      >
                        ×
                      </span>
                    </div>
                    <ShotBuilder brief={currentBrief} shot={currentShot} />
                  </div>
                )}
              </>
            ) : (
              /* Single shot or reference */
              <div style={{ flex: 1, padding: "0 24px", maxWidth: 700, margin: "0 auto" }}>
                {/* Brief context header */}
                <div style={{
                  padding: "16px 0 12px", borderBottom: "1px solid #1e1e2e", marginBottom: 12,
                }}>
                  <div style={{
                    display: "flex", alignItems: "center", gap: 8, marginBottom: 8,
                  }}>
                    <span style={{
                      color: STATUS_CONFIG[currentBrief.status]?.color || "#64748b",
                      fontSize: 12,
                    }}>
                      {STATUS_CONFIG[currentBrief.status]?.icon}
                    </span>
                    <span style={{ color: "#e2e8f0", fontSize: 16, fontWeight: 500 }}>
                      {currentBrief.title}
                    </span>
                  </div>

                  {/* Source context */}
                  <div style={{
                    padding: "8px 12px", borderRadius: 4,
                    background: "rgba(192, 132, 252, 0.04)",
                    border: "1px solid rgba(192, 132, 252, 0.1)",
                    marginBottom: 8,
                  }}>
                    <div style={{
                      color: "#c084fc", fontSize: 9, marginBottom: 4,
                      fontFamily: "'JetBrains Mono', monospace",
                      textTransform: "uppercase", letterSpacing: "0.06em",
                    }}>
                      SCRIBO Source
                    </div>
                    <div style={{
                      color: "#94a3b8", fontSize: 12, lineHeight: 1.6,
                      fontFamily: "'Crimson Pro', serif", fontStyle: "italic",
                    }}>
                      "{currentBrief.sourceParagraph}"
                    </div>
                  </div>

                  {/* Entity tags */}
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                    {currentBrief.characters.map(c => (
                      <span key={c} style={{
                        display: "flex", alignItems: "center", gap: 4,
                        padding: "2px 8px", borderRadius: 3,
                        background: (c === "Cornelius" ? "#4ade80" : c === "Mordecai" ? "#a78bfa" : "#64748b") + "12",
                        border: `1px solid ${(c === "Cornelius" ? "#4ade80" : c === "Mordecai" ? "#a78bfa" : "#64748b")}25`,
                      }}>
                        <span style={{
                          width: 5, height: 5, borderRadius: "50%",
                          background: c === "Cornelius" ? "#4ade80" : c === "Mordecai" ? "#a78bfa" : "#64748b",
                        }} />
                        <span style={{
                          color: c === "Cornelius" ? "#4ade80" : c === "Mordecai" ? "#a78bfa" : "#94a3b8",
                          fontSize: 10, fontFamily: "'JetBrains Mono', monospace",
                        }}>
                          {c}
                        </span>
                      </span>
                    ))}
                    <span style={{ color: "#4a4a5a", fontSize: 10, display: "flex", alignItems: "center" }}>
                      ◎ {currentBrief.location}
                    </span>
                  </div>
                </div>

                {/* Shot builder */}
                {currentBrief.type !== "reference" ? (
                  <ShotBuilder brief={currentBrief} />
                ) : (
                  /* Reference art (simpler — no camera rig) */
                  <div>
                    <div style={{ marginBottom: 16 }}>
                      <div style={{ color: "#4a4a5a", fontSize: 9, fontFamily: "'JetBrains Mono', monospace", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>
                        Reference Prompt
                      </div>
                      <textarea
                        defaultValue={currentBrief.prompt}
                        style={{
                          width: "100%", minHeight: 80, padding: 10, borderRadius: 4,
                          background: "rgba(10, 10, 15, 0.8)", border: "1px solid #1e1e2e",
                          color: "#e2e8f0", fontSize: 13, resize: "vertical",
                          fontFamily: "'Space Grotesk', sans-serif", outline: "none", lineHeight: 1.5,
                        }}
                      />
                    </div>
                    <div style={{
                      aspectRatio: "1/1", maxWidth: 400, margin: "0 auto",
                      background: "rgba(10, 10, 15, 0.8)", border: "1px solid #1e1e2e",
                      borderRadius: 6, display: "flex", alignItems: "center", justifyContent: "center",
                    }}>
                      <div style={{ textAlign: "center" }}>
                        <div style={{ fontSize: 32, color: "#1e1e2e", marginBottom: 8 }}>◐</div>
                        <div style={{ color: "#2a2a3a", fontSize: 11, fontFamily: "'JetBrains Mono', monospace" }}>
                          Reference Art · 1:1
                        </div>
                      </div>
                    </div>
                    <button style={{
                      width: "100%", marginTop: 16, padding: "10px 12px", borderRadius: 4,
                      border: "none", background: "rgba(52, 211, 153, 0.12)",
                      color: "#34d399", fontSize: 13, cursor: "pointer",
                      fontFamily: "'Space Grotesk', sans-serif", fontWeight: 500,
                    }}>
                      ◈ Generate Reference via Eden
                    </button>
                  </div>
                )}
              </div>
            )
          ) : (
            <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
              <div style={{ textAlign: "center", color: "#2a2a3a" }}>
                <div style={{ fontSize: 48, marginBottom: 12 }}>◎</div>
                <div style={{ fontSize: 14 }}>Select a production brief from the queue</div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Bottom bar */}
      <div style={{
        display: "flex", alignItems: "center", gap: 12, padding: "6px 16px",
        borderTop: "1px solid #1e1e2e", background: "rgba(10, 10, 15, 0.5)",
        fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: "#4a4a5a",
      }}>
        <span style={{ color: "#34d399" }}>● EDEN</span>
        <span style={{ color: "#2a2a3a" }}>|</span>
        <span>Queue: {stats.total} briefs · {stats.totalShots} total shots</span>
        <span style={{ color: "#2a2a3a" }}>|</span>
        <span>{stats.generating > 0 ? `${stats.generating} generating` : "Idle"}</span>
        <span style={{ marginLeft: "auto", color: "#2a2a3a" }}>
          ⌘G generate · ⌘S save rig · ⌘⇧E export storyboard
        </span>
      </div>
    </div>
  );
}
