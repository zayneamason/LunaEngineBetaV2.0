import { useState, useCallback, useRef, useEffect, useMemo } from "react";

// ─── TOKENS ───
const T = {
  bg: "#0a0a12", bgRaised: "#0e0e17", bgPanel: "#12121c",
  border: "rgba(255,255,255,0.06)", text: "#e8e8f0", textSoft: "#9a9ab0",
  textFaint: "#5a5a70", textMuted: "#3a3a50",
  luna: "#c084fc", memory: "#7dd3fc", voice: "#a78bfa",
  prompt: "#34d399", qa: "#f87171", debug: "#fbbf24",
  vk: "#fb923c", guardian: "#e09f3e",
};

const M = "'JetBrains Mono','SF Mono',monospace";
const F = "'DM Sans',system-ui,sans-serif";
const L = "'Bebas Neue',system-ui,sans-serif";

// ─── APERTURE PRESETS ───
const APERTURE_PRESETS = [
  { id: "tunnel", label: "TUNNEL", angle: 15, desc: "Project focus only", icon: "◉" },
  { id: "narrow", label: "NARROW", angle: 35, desc: "Project + related collections", icon: "◎" },
  { id: "balanced", label: "BALANCED", angle: 55, desc: "Focus with peripheral awareness", icon: "○" },
  { id: "wide", label: "WIDE", angle: 75, desc: "Broad recall, light filtering", icon: "◌" },
  { id: "open", label: "OPEN", angle: 95, desc: "Full memory access, no filtering", icon: "⊙" },
];

// ─── MOCK CONTEXT ───
const CURRENT_CONTEXT = {
  app: "Kozmo",
  project: "Dinosaur Screenplay",
  focusTags: ["dinosaur", "paleontology", "screenplay", "extinction"],
};

const VISIBLE_COLLECTIONS = [
  { id: "kozmo_creative", label: "Kozmo Creative", color: "#38bdf8", lockIn: 0.72, inAperture: true },
  { id: "luna_architecture", label: "Luna Architecture", color: T.luna, lockIn: 0.81, inAperture: true },
  { id: "sovereignty_research", label: "Sovereignty Research", color: "#a3e635", lockIn: 0.45, inAperture: false },
  { id: "dataroom", label: "Data Room", color: T.prompt, lockIn: 0.78, inAperture: false },
  { id: "rosa_conference", label: "ROSA Conference", color: "#e879f9", lockIn: 0.74, inAperture: false },
  { id: "funding_research", label: "Funding Research", color: T.debug, lockIn: 0.68, inAperture: false },
  { id: "guardian_specs", label: "Guardian Specs", color: T.guardian, lockIn: 0.55, inAperture: false },
  { id: "kinoni_deployment", label: "Kinoni Deployment", color: T.guardian, lockIn: 0.52, inAperture: false },
  { id: "voice_pipeline", label: "Voice Pipeline", color: T.voice, lockIn: 0.48, inAperture: false },
  { id: "maxwell_case", label: "Maxwell Case", color: T.qa, lockIn: 0.22, inAperture: false },
  { id: "thiel_investigation", label: "Thiel Investigation", color: T.vk, lockIn: 0.18, inAperture: false },
];

// ─── LUNA ORB ───
function LunaOrb({ size = 48, apertureAngle, isHovered, pulseColor }) {
  const normalizedAngle = apertureAngle / 95; // 0-1 range
  const glowSize = 8 + normalizedAngle * 20;
  const glowOpacity = 0.3 + normalizedAngle * 0.3;

  return (
    <div style={{ width: size, height: size, position: "relative" }}>
      {/* Outer glow */}
      <div style={{
        position: "absolute", inset: -glowSize, borderRadius: "50%",
        background: `radial-gradient(circle, ${pulseColor || T.luna}${Math.round(glowOpacity * 255).toString(16).padStart(2, '0')} 0%, transparent 70%)`,
        transition: "all 0.6s ease",
        animation: isHovered ? "orbPulse 2s ease-in-out infinite" : "none",
      }} />

      {/* Core orb */}
      <div style={{
        width: size, height: size, borderRadius: "50%", position: "relative",
        background: `radial-gradient(circle at 35% 35%, ${T.luna}40, ${T.voice}20, ${T.luna}10)`,
        border: `1.5px solid ${T.luna}40`,
        boxShadow: `0 0 ${glowSize}px ${T.luna}30, inset 0 0 12px ${T.luna}15`,
        transition: "all 0.4s ease",
        transform: isHovered ? "scale(1.08)" : "scale(1)",
      }}>
        {/* Inner highlight */}
        <div style={{
          position: "absolute", top: "15%", left: "20%", width: "30%", height: "25%",
          borderRadius: "50%", background: `radial-gradient(circle, rgba(255,255,255,0.15), transparent)`,
        }} />

        {/* Aperture indicator ring */}
        <svg style={{ position: "absolute", inset: -3, width: size + 6, height: size + 6 }} viewBox="0 0 54 54">
          <circle cx="27" cy="27" r="25" fill="none"
            stroke={T.luna} strokeWidth="1" strokeOpacity="0.15" />
          <circle cx="27" cy="27" r="25" fill="none"
            stroke={T.luna} strokeWidth="1.5" strokeOpacity="0.6"
            strokeDasharray={`${normalizedAngle * 157} 157`}
            strokeLinecap="round"
            transform="rotate(-90 27 27)"
            style={{ transition: "stroke-dasharray 0.4s ease" }}
          />
        </svg>
      </div>
    </div>
  );
}

// ─── APERTURE DIAL ───
function ApertureDial({ angle, onChange, visible, orbCenter }) {
  const dialRef = useRef(null);
  const [dragging, setDragging] = useState(false);
  const DIAL_RADIUS = 130;
  const KNOB_TRACK_RADIUS = 95;

  // Convert angle (15-95) to radians on the arc
  const angleToRad = (a) => ((a - 15) / 80) * Math.PI * 1.5 - Math.PI * 0.75;
  const radToAngle = (r) => ((r + Math.PI * 0.75) / (Math.PI * 1.5)) * 80 + 15;

  const knobRad = angleToRad(angle);
  const knobX = DIAL_RADIUS + Math.cos(knobRad) * KNOB_TRACK_RADIUS;
  const knobY = DIAL_RADIUS + Math.sin(knobRad) * KNOB_TRACK_RADIUS;

  const handleMouseDown = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragging(true);
  }, []);

  useEffect(() => {
    if (!dragging) return;
    const handleMove = (e) => {
      if (!dialRef.current) return;
      const rect = dialRef.current.getBoundingClientRect();
      const cx = rect.left + DIAL_RADIUS;
      const cy = rect.top + DIAL_RADIUS;
      const dx = e.clientX - cx;
      const dy = e.clientY - cy;
      let rad = Math.atan2(dy, dx);
      let newAngle = radToAngle(rad);
      newAngle = Math.max(15, Math.min(95, newAngle));
      onChange(Math.round(newAngle));
    };
    const handleUp = () => setDragging(false);
    window.addEventListener("mousemove", handleMove);
    window.addEventListener("mouseup", handleUp);
    return () => {
      window.removeEventListener("mousemove", handleMove);
      window.removeEventListener("mouseup", handleUp);
    };
  }, [dragging, onChange]);

  // Which preset is closest
  const activePreset = APERTURE_PRESETS.reduce((closest, p) =>
    Math.abs(p.angle - angle) < Math.abs(closest.angle - angle) ? p : closest
  );

  // Determine which collections are in aperture
  const threshold = 1 - (angle - 15) / 80; // higher angle = lower threshold
  const lockInThreshold = threshold * 0.8; // scale it

  // Compute aperture cone visualization
  const coneStartRad = -Math.PI / 2 - (angle * Math.PI / 180) / 2;
  const coneEndRad = -Math.PI / 2 + (angle * Math.PI / 180) / 2;
  const CONE_RADIUS = 70;

  return (
    <div
      ref={dialRef}
      style={{
        position: "absolute",
        width: DIAL_RADIUS * 2,
        height: DIAL_RADIUS * 2,
        left: orbCenter.x - DIAL_RADIUS,
        top: orbCenter.y - DIAL_RADIUS,
        opacity: visible ? 1 : 0,
        pointerEvents: visible ? "auto" : "none",
        transform: visible ? "scale(1)" : "scale(0.85)",
        transition: "opacity 0.25s ease, transform 0.25s ease",
        zIndex: 100,
      }}
    >
      <svg width={DIAL_RADIUS * 2} height={DIAL_RADIUS * 2} viewBox={`0 0 ${DIAL_RADIUS * 2} ${DIAL_RADIUS * 2}`}>
        {/* Background disc */}
        <circle cx={DIAL_RADIUS} cy={DIAL_RADIUS} r={DIAL_RADIUS - 2}
          fill={T.bg} fillOpacity="0.92" stroke={T.luna} strokeWidth="0.5" strokeOpacity="0.2" />

        {/* Aperture cone visualization */}
        <path
          d={`M${DIAL_RADIUS},${DIAL_RADIUS} L${DIAL_RADIUS + Math.cos(coneStartRad) * CONE_RADIUS},${DIAL_RADIUS + Math.sin(coneStartRad) * CONE_RADIUS} A${CONE_RADIUS},${CONE_RADIUS} 0 ${angle > 180 ? 1 : 0} 1 ${DIAL_RADIUS + Math.cos(coneEndRad) * CONE_RADIUS},${DIAL_RADIUS + Math.sin(coneEndRad) * CONE_RADIUS} Z`}
          fill={T.luna} fillOpacity="0.06"
          stroke={T.luna} strokeWidth="0.5" strokeOpacity="0.2"
        />

        {/* Collection dots arranged in rings */}
        {VISIBLE_COLLECTIONS.map((col, i) => {
          const colAngle = (i / VISIBLE_COLLECTIONS.length) * Math.PI * 2 - Math.PI / 2;
          const ringRadius = col.lockIn > lockInThreshold ? 40 + (1 - col.lockIn) * 40 : 85 + (1 - col.lockIn) * 30;
          const cx = DIAL_RADIUS + Math.cos(colAngle) * ringRadius;
          const cy = DIAL_RADIUS + Math.sin(colAngle) * ringRadius;
          const isVisible = col.lockIn > lockInThreshold || col.inAperture;
          const dotSize = isVisible ? 4 : 2.5;

          return (
            <g key={col.id}>
              {/* Connection line to center */}
              <line x1={DIAL_RADIUS} y1={DIAL_RADIUS} x2={cx} y2={cy}
                stroke={col.color} strokeWidth={isVisible ? 0.5 : 0.2}
                strokeOpacity={isVisible ? 0.3 : 0.08}
                strokeDasharray={isVisible ? "none" : "2 2"}
              />
              {/* Dot */}
              <circle cx={cx} cy={cy} r={dotSize}
                fill={isVisible ? col.color : T.textMuted}
                fillOpacity={isVisible ? 0.8 : 0.3}
                stroke={col.color} strokeWidth={isVisible ? 0.5 : 0}
                strokeOpacity={0.4}
              />
              {/* Label */}
              <text x={cx} y={cy + dotSize + 8}
                textAnchor="middle" fontSize="5.5" fontFamily={M}
                fill={isVisible ? col.color : T.textMuted}
                fillOpacity={isVisible ? 0.7 : 0.3}
              >
                {col.id.split("_")[0]}
              </text>
            </g>
          );
        })}

        {/* Track arc */}
        <circle cx={DIAL_RADIUS} cy={DIAL_RADIUS} r={KNOB_TRACK_RADIUS}
          fill="none" stroke={T.textMuted} strokeWidth="1" strokeOpacity="0.15"
          strokeDasharray="3 3"
        />

        {/* Filled arc showing current position */}
        <path
          d={(() => {
            const startRad = angleToRad(15);
            const endRad = angleToRad(angle);
            const sx = DIAL_RADIUS + Math.cos(startRad) * KNOB_TRACK_RADIUS;
            const sy = DIAL_RADIUS + Math.sin(startRad) * KNOB_TRACK_RADIUS;
            const ex = DIAL_RADIUS + Math.cos(endRad) * KNOB_TRACK_RADIUS;
            const ey = DIAL_RADIUS + Math.sin(endRad) * KNOB_TRACK_RADIUS;
            const largeArc = (angle - 15) > 53 ? 1 : 0;
            return `M${sx},${sy} A${KNOB_TRACK_RADIUS},${KNOB_TRACK_RADIUS} 0 ${largeArc} 1 ${ex},${ey}`;
          })()}
          fill="none" stroke={T.luna} strokeWidth="2" strokeOpacity="0.4" strokeLinecap="round"
        />

        {/* Preset tick marks */}
        {APERTURE_PRESETS.map(p => {
          const r = angleToRad(p.angle);
          const ix = DIAL_RADIUS + Math.cos(r) * (KNOB_TRACK_RADIUS - 8);
          const iy = DIAL_RADIUS + Math.sin(r) * (KNOB_TRACK_RADIUS - 8);
          const ox = DIAL_RADIUS + Math.cos(r) * (KNOB_TRACK_RADIUS + 8);
          const oy = DIAL_RADIUS + Math.sin(r) * (KNOB_TRACK_RADIUS + 8);
          const lx = DIAL_RADIUS + Math.cos(r) * (KNOB_TRACK_RADIUS + 20);
          const ly = DIAL_RADIUS + Math.sin(r) * (KNOB_TRACK_RADIUS + 20);
          const isActive = p.id === activePreset.id;
          return (
            <g key={p.id} onClick={() => onChange(p.angle)} style={{ cursor: "pointer" }}>
              <line x1={ix} y1={iy} x2={ox} y2={oy}
                stroke={isActive ? T.luna : T.textMuted} strokeWidth={isActive ? 1.5 : 0.5}
                strokeOpacity={isActive ? 0.8 : 0.3}
              />
              <text x={lx} y={ly} textAnchor="middle" dominantBaseline="middle"
                fontSize="6" fontFamily={L} letterSpacing="1"
                fill={isActive ? T.luna : T.textMuted} fillOpacity={isActive ? 0.9 : 0.4}
              >
                {p.label}
              </text>
            </g>
          );
        })}

        {/* Knob */}
        <g onMouseDown={handleMouseDown} style={{ cursor: "grab" }}>
          <circle cx={knobX} cy={knobY} r={12} fill="transparent" />
          <circle cx={knobX} cy={knobY} r={7}
            fill={T.bgRaised} stroke={T.luna} strokeWidth="1.5"
            style={{ filter: `drop-shadow(0 0 6px ${T.luna}60)` }}
          />
          <circle cx={knobX} cy={knobY} r={3}
            fill={T.luna} fillOpacity="0.6"
          />
        </g>

        {/* Center info */}
        <text x={DIAL_RADIUS} y={DIAL_RADIUS - 8} textAnchor="middle"
          fontSize="8" fontFamily={L} letterSpacing="1.5" fill={T.luna} fillOpacity="0.8"
        >
          {activePreset.icon}
        </text>
        <text x={DIAL_RADIUS} y={DIAL_RADIUS + 4} textAnchor="middle"
          fontSize="6.5" fontFamily={L} letterSpacing="1" fill={T.luna} fillOpacity="0.7"
        >
          {angle}°
        </text>
        <text x={DIAL_RADIUS} y={DIAL_RADIUS + 14} textAnchor="middle"
          fontSize="5" fontFamily={M} fill={T.textFaint} fillOpacity="0.6"
        >
          {activePreset.desc}
        </text>
      </svg>
    </div>
  );
}

// ─── CONTEXT DISPLAY ───
function ContextBar({ context, aperture, activePreset }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 12, padding: "8px 16px",
      background: T.bgPanel, borderRadius: 8, border: `1px solid ${T.border}`,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <div style={{ width: 3, height: 12, borderRadius: 2, background: "#38bdf8" }} />
        <span style={{ fontSize: 9, fontFamily: L, letterSpacing: 1.5, color: "#38bdf8" }}>{context.app.toUpperCase()}</span>
      </div>
      <div style={{ width: 1, height: 12, background: T.border }} />
      <span style={{ fontSize: 10, fontFamily: F, color: T.textSoft }}>{context.project}</span>
      <div style={{ display: "flex", gap: 3 }}>
        {context.focusTags.map(t => (
          <span key={t} style={{
            padding: "1px 5px", borderRadius: 2, fontSize: 7, fontFamily: M,
            background: `${T.luna}08`, border: `1px solid ${T.luna}12`, color: T.luna,
          }}>{t}</span>
        ))}
      </div>
      <div style={{ flex: 1 }} />
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <span style={{ fontSize: 8, fontFamily: M, color: T.textFaint }}>APERTURE</span>
        <span style={{ fontSize: 9, fontFamily: M, color: T.luna }}>{activePreset.label} {aperture}°</span>
      </div>
    </div>
  );
}

// ─── SCOPE VISUALIZATION ───
function ScopePreview({ aperture, collections }) {
  const threshold = 1 - (aperture - 15) / 80;
  const lockInThreshold = threshold * 0.8;

  const inner = collections.filter(c => c.lockIn > lockInThreshold || c.inAperture);
  const outer = collections.filter(c => c.lockIn <= lockInThreshold && !c.inAperture);

  return (
    <div style={{
      padding: "12px 16px", background: T.bgPanel, borderRadius: 8,
      border: `1px solid ${T.border}`,
    }}>
      <div style={{ fontSize: 7, fontFamily: L, letterSpacing: 1.5, color: T.textMuted, marginBottom: 8 }}>
        COGNITIVE SCOPE · WHAT LUNA SEES
      </div>

      <div style={{ display: "flex", gap: 16 }}>
        {/* Inner ring */}
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 7, fontFamily: L, letterSpacing: 1, color: T.prompt, marginBottom: 6 }}>
            ◉ INNER RING · AUTO-SEARCHED
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 3 }}>
            <div style={{
              padding: "3px 8px", borderRadius: 4, fontSize: 8, fontFamily: M,
              background: `${T.luna}12`, border: `1px solid ${T.luna}20`, color: T.luna,
            }}>MEMORY MATRIX</div>
            {inner.map(c => (
              <div key={c.id} style={{
                padding: "3px 8px", borderRadius: 4, fontSize: 8, fontFamily: M,
                background: `${c.color}10`, border: `1px solid ${c.color}20`, color: c.color,
                display: "flex", alignItems: "center", gap: 4,
              }}>
                <span>{c.id.split("_")[0]}</span>
                <span style={{ fontSize: 6, opacity: 0.5 }}>{(c.lockIn * 100).toFixed(0)}%</span>
              </div>
            ))}
          </div>
        </div>

        {/* Outer ring */}
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 7, fontFamily: L, letterSpacing: 1, color: T.textFaint, marginBottom: 6 }}>
            ○ OUTER RING · BREAKTHROUGH ONLY
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 3 }}>
            {outer.map(c => (
              <div key={c.id} style={{
                padding: "3px 8px", borderRadius: 4, fontSize: 8, fontFamily: M,
                background: `${T.textMuted}08`, border: `1px solid ${T.border}`, color: T.textMuted,
                display: "flex", alignItems: "center", gap: 4,
              }}>
                <span>{c.id.split("_")[0]}</span>
                <span style={{ fontSize: 6, opacity: 0.4 }}>{(c.lockIn * 100).toFixed(0)}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Agency note */}
      <div style={{
        marginTop: 10, padding: "6px 10px", borderRadius: 4,
        background: `${T.debug}06`, borderLeft: `2px solid ${T.debug}40`,
        fontSize: 9, fontFamily: F, color: T.textFaint,
      }}>
        <span style={{ color: T.debug, fontFamily: M, fontSize: 8 }}>⚡ AGENCY:</span>{" "}
        Luna can still surface outer ring results if relevance exceeds breakthrough threshold.
        Time-sensitive items (deadlines, urgent flags) bypass aperture.
      </div>
    </div>
  );
}

// ─── MAIN APP ───
export default function ApertureControl() {
  const [aperture, setAperture] = useState(55);
  const [hovered, setHovered] = useState(false);
  const [dialVisible, setDialVisible] = useState(false);
  const orbRef = useRef(null);
  const [orbCenter, setOrbCenter] = useState({ x: 0, y: 0 });
  const hideTimeout = useRef(null);

  const activePreset = APERTURE_PRESETS.reduce((closest, p) =>
    Math.abs(p.angle - aperture) < Math.abs(closest.angle - aperture) ? p : closest
  );

  // Update orb center position
  useEffect(() => {
    const update = () => {
      if (orbRef.current) {
        const rect = orbRef.current.getBoundingClientRect();
        setOrbCenter({ x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 });
      }
    };
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);

  const showDial = useCallback(() => {
    if (hideTimeout.current) clearTimeout(hideTimeout.current);
    setHovered(true);
    setDialVisible(true);
  }, []);

  const startHide = useCallback(() => {
    hideTimeout.current = setTimeout(() => {
      setHovered(false);
      setDialVisible(false);
    }, 400);
  }, []);

  const cancelHide = useCallback(() => {
    if (hideTimeout.current) clearTimeout(hideTimeout.current);
  }, []);

  return (
    <div style={{
      width: "100%", height: "100vh", background: T.bg, fontFamily: F,
      color: T.text, display: "flex", flexDirection: "column", overflow: "hidden",
    }}>
      <style>{`
        @keyframes orbPulse {
          0%, 100% { transform: scale(1); opacity: 0.6; }
          50% { transform: scale(1.15); opacity: 1; }
        }
      `}</style>

      {/* Header with orb */}
      <div style={{
        height: 56, background: T.bgRaised, borderBottom: `1px solid ${T.border}`,
        display: "flex", alignItems: "center", padding: "0 20px", gap: 14,
        flexShrink: 0, position: "relative",
      }}>
        {/* Orb */}
        <div
          ref={orbRef}
          onMouseEnter={showDial}
          onMouseLeave={startHide}
          style={{ cursor: "pointer", position: "relative", zIndex: 101 }}
        >
          <LunaOrb size={40} apertureAngle={aperture} isHovered={hovered} />
        </div>

        <div style={{ width: 1, height: 20, background: T.border }} />
        <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
          <span style={{ fontFamily: L, fontSize: 11, letterSpacing: 2.5, color: T.voice }}>LUNAR STUDIO</span>
          <span style={{ fontSize: 8, fontFamily: M, color: T.textFaint }}>
            {activePreset.icon} {activePreset.label} · {aperture}°
          </span>
        </div>

        <div style={{ flex: 1 }} />

        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div style={{
            padding: "4px 10px", borderRadius: 4,
            background: `${"#38bdf8"}10`, border: `1px solid ${"#38bdf8"}25`,
            fontSize: 8, fontFamily: M, color: "#38bdf8",
          }}>KOZMO · Dinosaur Screenplay</div>
        </div>
      </div>

      {/* Dial overlay */}
      <div
        onMouseEnter={cancelHide}
        onMouseLeave={startHide}
        style={{ position: "fixed", zIndex: 100, pointerEvents: dialVisible ? "auto" : "none" }}
      >
        <ApertureDial
          angle={aperture}
          onChange={setAperture}
          visible={dialVisible}
          orbCenter={orbCenter}
        />
      </div>

      {/* Main content area */}
      <div style={{ flex: 1, overflow: "auto", padding: "16px 20px", display: "flex", flexDirection: "column", gap: 12 }}>
        {/* Context bar */}
        <ContextBar context={CURRENT_CONTEXT} aperture={aperture} activePreset={activePreset} />

        {/* Scope preview */}
        <ScopePreview aperture={aperture} collections={VISIBLE_COLLECTIONS} />

        {/* Demo: show what changes */}
        <div style={{
          padding: "16px", background: T.bgPanel, borderRadius: 8,
          border: `1px solid ${T.border}`,
        }}>
          <div style={{ fontSize: 7, fontFamily: L, letterSpacing: 1.5, color: T.textMuted, marginBottom: 12 }}>
            RECALL PIPELINE PREVIEW
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
            {/* Step 1 */}
            <div style={{ padding: "10px", borderRadius: 6, background: T.bg, border: `1px solid ${T.luna}15` }}>
              <div style={{ fontSize: 8, fontFamily: L, letterSpacing: 1, color: T.luna, marginBottom: 6 }}>1 · FOCUS QUERY</div>
              <div style={{ fontSize: 9, fontFamily: F, color: T.textSoft, lineHeight: 1.5 }}>
                Search inner ring collections with full depth. Focus-weighted by project tags.
              </div>
              <div style={{ marginTop: 6, fontSize: 8, fontFamily: M, color: T.luna }}>
                depth: MAX · weight: 1.0
              </div>
            </div>

            {/* Step 2 */}
            <div style={{ padding: "10px", borderRadius: 6, background: T.bg, border: `1px solid ${T.memory}15` }}>
              <div style={{ fontSize: 8, fontFamily: L, letterSpacing: 1, color: T.memory, marginBottom: 6 }}>2 · MATRIX SWEEP</div>
              <div style={{ fontSize: 9, fontFamily: F, color: T.textSoft, lineHeight: 1.5 }}>
                Search Memory Matrix with focus tags. Core identity always included.
              </div>
              <div style={{ marginTop: 6, fontSize: 8, fontFamily: M, color: T.memory }}>
                depth: FOCUS · weight: 0.8
              </div>
            </div>

            {/* Step 3 */}
            <div style={{ padding: "10px", borderRadius: 6, background: T.bg, border: `1px solid ${T.debug}15` }}>
              <div style={{ fontSize: 8, fontFamily: L, letterSpacing: 1, color: T.debug, marginBottom: 6 }}>3 · AGENCY CHECK</div>
              <div style={{ fontSize: 9, fontFamily: F, color: T.textSoft, lineHeight: 1.5 }}>
                Lightweight sweep of outer ring for urgent/time-sensitive nodes. Breakthrough if relevance &gt; {(0.3 + (95 - aperture) / 95 * 0.5).toFixed(2)}.
              </div>
              <div style={{ marginTop: 6, fontSize: 8, fontFamily: M, color: T.debug }}>
                depth: SHALLOW · threshold: {(0.3 + (95 - aperture) / 95 * 0.5).toFixed(2)}
              </div>
            </div>
          </div>
        </div>

        {/* Aperture explanation */}
        <div style={{
          padding: "12px 16px", background: T.bgPanel, borderRadius: 8,
          border: `1px solid ${T.border}`,
        }}>
          <div style={{ fontSize: 7, fontFamily: L, letterSpacing: 1.5, color: T.textMuted, marginBottom: 8 }}>
            HOW THE APERTURE WORKS
          </div>
          <div style={{
            display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 6,
          }}>
            {APERTURE_PRESETS.map(p => {
              const isActive = p.id === activePreset.id;
              return (
                <div key={p.id} onClick={() => setAperture(p.angle)} style={{
                  padding: "8px", borderRadius: 6, cursor: "pointer",
                  background: isActive ? `${T.luna}10` : T.bg,
                  border: `1px solid ${isActive ? `${T.luna}30` : T.border}`,
                  textAlign: "center", transition: "all 0.2s",
                }}>
                  <div style={{ fontSize: 16, marginBottom: 4 }}>{p.icon}</div>
                  <div style={{ fontSize: 8, fontFamily: L, letterSpacing: 1, color: isActive ? T.luna : T.textFaint }}>
                    {p.label}
                  </div>
                  <div style={{ fontSize: 7, fontFamily: M, color: T.textMuted, marginTop: 2 }}>{p.angle}°</div>
                  <div style={{ fontSize: 7, fontFamily: F, color: T.textFaint, marginTop: 4, lineHeight: 1.3 }}>
                    {p.desc}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Status bar */}
      <div style={{
        height: 26, background: T.bgRaised, borderTop: `1px solid ${T.border}`,
        display: "flex", alignItems: "center", padding: "0 20px", gap: 16,
        fontSize: 8, fontFamily: M, color: T.textFaint, flexShrink: 0,
      }}>
        <span><span style={{ color: T.luna }}>◆</span> aperture: {aperture}° {activePreset.label}</span>
        <span>·</span>
        <span>inner: {VISIBLE_COLLECTIONS.filter(c => c.lockIn > (1 - (aperture - 15) / 80) * 0.8 || c.inAperture).length} collections</span>
        <span>outer: {VISIBLE_COLLECTIONS.filter(c => c.lockIn <= (1 - (aperture - 15) / 80) * 0.8 && !c.inAperture).length} collections</span>
        <span>breakthrough: {(0.3 + (95 - aperture) / 95 * 0.5).toFixed(2)}</span>
        <div style={{ flex: 1 }} />
        <span style={{ color: T.voice }}>LUNAR STUDIO · APERTURE CONTROL</span>
      </div>
    </div>
  );
}
