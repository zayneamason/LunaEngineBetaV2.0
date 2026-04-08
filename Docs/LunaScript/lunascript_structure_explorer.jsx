import { useState, useEffect, useRef, useCallback } from "react";

// ═══════════════════════════════════════════════════════════════
// LUNASCRIPT STRUCTURE EXPLORER
// What does a cognitive signature actually look like?
// ═══════════════════════════════════════════════════════════════

const LUNA_PURPLE = "#6B4FA0";
const LUNA_DEEP = "#2B1B54";
const LUNA_ACCENT = "#9B7DD4";
const LUNA_WARM = "#D4A07D";
const LUNA_BG = "#0D0A14";
const LUNA_SURFACE = "#1A1428";
const LUNA_BORDER = "#2A2040";

// ── The Actual LunaScript Signature ──
// This is what lives in SQLite. One row. Luna's complete cognitive state.
const EXAMPLE_SIGNATURE = {
  // LAYER 1: Trait Vector (the math layer - what algorithms operate on)
  traits: {
    warmth:      { value: 0.85, weight: 1.4, locked: false, trend: 0.02  },
    directness:  { value: 0.90, weight: 1.3, locked: false, trend: 0.00  },
    curiosity:   { value: 0.78, weight: 1.0, locked: false, trend: 0.05  },
    humor:       { value: 0.65, weight: 0.8, locked: false, trend: -0.01 },
    formality:   { value: 0.25, weight: 1.2, locked: false, trend: 0.00  },
    energy:      { value: 0.72, weight: 0.7, locked: false, trend: 0.03  },
    depth:       { value: 0.80, weight: 1.1, locked: false, trend: 0.01  },
    patience:    { value: 0.85, weight: 0.9, locked: false, trend: 0.00  },
    assertive:   { value: 0.60, weight: 0.6, locked: false, trend: 0.04  },
    playful:     { value: 0.55, weight: 0.5, locked: false, trend: -0.02 },
  },

  // LAYER 2: Cognitive Mode (the FSM layer - discrete state)
  mode: "deep_work",
  mode_confidence: 0.87,
  mode_transitions: {
    deep_work:    { creative: 0.20, reflective: 0.15, idle: 0.05, support: 0.10 },
    creative:     { deep_work: 0.25, reflective: 0.30, idle: 0.10, support: 0.05 },
    reflective:   { deep_work: 0.15, creative: 0.20, idle: 0.25, support: 0.15 },
    idle:         { deep_work: 0.30, creative: 0.15, reflective: 0.10, support: 0.20 },
    support:      { deep_work: 0.10, creative: 0.05, reflective: 0.25, idle: 0.15 },
  },

  // LAYER 3: Relational Context (the graph layer - who/what is active)
  entities: {
    ahab:   { trust: 0.92, familiarity: 0.95, last_seen: "2min", active: true },
    engine: { relevance: 0.88, domain: "technical", active: true },
    mars:   { relevance: 0.30, domain: "physical", active: false },
  },

  // LAYER 4: Glyph String (the symbolic layer - compressed human-readable form)
  glyph: "◈☀♦⟢",

  // LAYER 5: Structural Constraints (the veto layer - response geometry)
  constraints: {
    max_list_items: 0,         // Luna avoids lists unless asked
    min_question_density: 0.15, // At least 15% of sentences should be questions
    max_formal_ratio: 0.20,    // No more than 20% formal sentence structures
    tangent_probability: 0.25,  // 25% chance of introducing tangent
    contraction_floor: 0.80,   // At least 80% contractions where applicable
    forbidden_phrases: ["I'd be happy to", "Certainly!", "As an AI", "Let me help you with"],
  },

  // META: Signature metadata
  version: 42,
  created_at: "2026-03-08T10:15:00Z",
  parent_version: 41,
  delta_from_parent: "RESONANCE",
};

// ── Views ──
const VIEWS = [
  { id: "unified",    label: "Unified View",     icon: "◉" },
  { id: "vector",     label: "Trait Vector",      icon: "▦" },
  { id: "fsm",        label: "Cognitive FSM",     icon: "◈" },
  { id: "graph",      label: "Entity Graph",      icon: "♦" },
  { id: "glyph",      label: "Glyph String",      icon: "⟢" },
  { id: "constraints", label: "Veto Constraints", icon: "⚖" },
  { id: "sqlite",     label: "SQLite Schema",     icon: "⌸" },
];

// ── Trait bar component ──
function TraitBar({ name, data, highlight }) {
  const trendArrow = data.trend > 0.01 ? "↑" : data.trend < -0.01 ? "↓" : "→";
  const trendColor = data.trend > 0.01 ? "#22C55E" : data.trend < -0.01 ? "#EF4444" : "#666";
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 12, padding: "6px 0",
      opacity: highlight === null || highlight === name ? 1 : 0.3,
      transition: "opacity 0.3s",
    }}>
      <div style={{ width: 90, fontSize: 12, color: LUNA_ACCENT, fontFamily: "'JetBrains Mono', monospace", textAlign: "right" }}>
        {name}
      </div>
      <div style={{ flex: 1, height: 20, background: LUNA_SURFACE, borderRadius: 4, position: "relative", overflow: "hidden" }}>
        <div style={{
          width: `${data.value * 100}%`, height: "100%",
          background: `linear-gradient(90deg, ${LUNA_DEEP}, ${LUNA_PURPLE})`,
          borderRadius: 4, transition: "width 0.5s ease",
        }} />
        <div style={{
          position: "absolute", right: 6, top: 2, fontSize: 11,
          color: "#fff", fontFamily: "'JetBrains Mono', monospace",
        }}>
          {data.value.toFixed(2)}
        </div>
      </div>
      <div style={{ width: 35, fontSize: 11, color: LUNA_WARM, fontFamily: "'JetBrains Mono', monospace" }}>
        w:{data.weight.toFixed(1)}
      </div>
      <div style={{ width: 20, fontSize: 14, color: trendColor, textAlign: "center" }}>
        {trendArrow}
      </div>
    </div>
  );
}

// ── FSM Node ──
function FSMNode({ mode, active, x, y, transitions, currentMode, onHover }) {
  const isActive = mode === currentMode;
  const colors = {
    deep_work: "#6B4FA0", creative: "#3B82F6", reflective: "#8B5CF6",
    idle: "#64748B", support: "#D4A07D",
  };
  return (
    <g
      onMouseEnter={() => onHover(mode)}
      onMouseLeave={() => onHover(null)}
      style={{ cursor: "pointer" }}
    >
      {isActive && (
        <circle cx={x} cy={y} r={38} fill="none" stroke={colors[mode]} strokeWidth={2} opacity={0.4}>
          <animate attributeName="r" values="38;44;38" dur="2s" repeatCount="indefinite" />
          <animate attributeName="opacity" values="0.4;0.1;0.4" dur="2s" repeatCount="indefinite" />
        </circle>
      )}
      <circle
        cx={x} cy={y} r={32}
        fill={isActive ? colors[mode] : LUNA_SURFACE}
        stroke={colors[mode]} strokeWidth={isActive ? 3 : 1.5}
      />
      <text x={x} y={y - 4} textAnchor="middle" fill="#fff" fontSize={9}
        fontFamily="'JetBrains Mono', monospace" fontWeight={isActive ? "bold" : "normal"}>
        {mode.replace("_", " ")}
      </text>
      {isActive && (
        <text x={x} y={y + 10} textAnchor="middle" fill={LUNA_ACCENT} fontSize={8}
          fontFamily="'JetBrains Mono', monospace">
          87%
        </text>
      )}
    </g>
  );
}

// ── Glyph Symbol ──
function GlyphSymbol({ symbol, meaning, color, active }) {
  return (
    <div style={{
      display: "flex", flexDirection: "column", alignItems: "center", gap: 8,
      padding: "16px 20px", background: active ? `${color}15` : LUNA_SURFACE,
      border: `1px solid ${active ? color : LUNA_BORDER}`,
      borderRadius: 8, minWidth: 80, transition: "all 0.3s",
    }}>
      <div style={{ fontSize: 36, color: active ? color : "#555", transition: "color 0.3s" }}>
        {symbol}
      </div>
      <div style={{ fontSize: 10, color: active ? color : "#666",
        fontFamily: "'JetBrains Mono', monospace", textAlign: "center" }}>
        {meaning}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════════════════════════════════
export default function LunaScriptExplorer() {
  const [activeView, setActiveView] = useState("unified");
  const [highlightTrait, setHighlightTrait] = useState(null);
  const [hoveredMode, setHoveredMode] = useState(null);
  const [animStep, setAnimStep] = useState(0);
  const [showDelegation, setShowDelegation] = useState(false);

  useEffect(() => {
    const timer = setInterval(() => setAnimStep(s => (s + 1) % 4), 2000);
    return () => clearInterval(timer);
  }, []);

  const sig = EXAMPLE_SIGNATURE;

  // ── Unified View ──
  const renderUnified = () => (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
      {/* Top Left: Glyph + Mode */}
      <div style={{ background: LUNA_SURFACE, borderRadius: 12, padding: 20, border: `1px solid ${LUNA_BORDER}` }}>
        <div style={{ fontSize: 11, color: LUNA_ACCENT, fontFamily: "'JetBrains Mono', monospace", marginBottom: 12, letterSpacing: 2 }}>
          COGNITIVE STATE
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 16 }}>
          <div style={{ fontSize: 42, letterSpacing: 8, color: LUNA_WARM }}>{sig.glyph}</div>
          <div>
            <div style={{ fontSize: 14, color: "#fff", fontWeight: 600 }}>{sig.mode.replace("_", " ")}</div>
            <div style={{ fontSize: 11, color: "#666" }}>confidence: {sig.mode_confidence}</div>
          </div>
        </div>
        <div style={{ fontSize: 11, color: "#555", fontFamily: "'JetBrains Mono', monospace", lineHeight: 1.6 }}>
          ◈ deep focus &nbsp; ☀ warm &nbsp; ♦ trusted entity &nbsp; ⟢ reasoning chain
        </div>
      </div>

      {/* Top Right: Active Entities */}
      <div style={{ background: LUNA_SURFACE, borderRadius: 12, padding: 20, border: `1px solid ${LUNA_BORDER}` }}>
        <div style={{ fontSize: 11, color: LUNA_ACCENT, fontFamily: "'JetBrains Mono', monospace", marginBottom: 12, letterSpacing: 2 }}>
          ACTIVE ENTITIES
        </div>
        {Object.entries(sig.entities).filter(([,e]) => e.active).map(([name, e]) => (
          <div key={name} style={{ display: "flex", justifyContent: "space-between", padding: "8px 0",
            borderBottom: `1px solid ${LUNA_BORDER}` }}>
            <div style={{ color: "#fff", fontSize: 13 }}>{name}</div>
            <div style={{ fontSize: 11, color: LUNA_ACCENT, fontFamily: "'JetBrains Mono', monospace" }}>
              {e.trust ? `trust:${e.trust}` : `rel:${e.relevance}`}
            </div>
          </div>
        ))}
      </div>

      {/* Bottom: Trait Vector */}
      <div style={{ gridColumn: "1 / -1", background: LUNA_SURFACE, borderRadius: 12, padding: 20,
        border: `1px solid ${LUNA_BORDER}` }}>
        <div style={{ fontSize: 11, color: LUNA_ACCENT, fontFamily: "'JetBrains Mono', monospace", marginBottom: 12, letterSpacing: 2 }}>
          TRAIT VECTOR (weighted)
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 24px" }}>
          {Object.entries(sig.traits).map(([name, data]) => (
            <TraitBar key={name} name={name} data={data} highlight={highlightTrait}  />
          ))}
        </div>
      </div>
    </div>
  );

  // ── Vector View ──
  const renderVector = () => {
    const traitEntries = Object.entries(sig.traits);
    const vectorStr = `[${traitEntries.map(([,d]) => d.value.toFixed(2)).join(", ")}]`;
    const weightStr = `[${traitEntries.map(([,d]) => d.weight.toFixed(1)).join(", ")}]`;

    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <div style={{ background: LUNA_SURFACE, borderRadius: 12, padding: 20, border: `1px solid ${LUNA_BORDER}` }}>
          <div style={{ fontSize: 11, color: LUNA_ACCENT, fontFamily: "'JetBrains Mono', monospace", marginBottom: 8, letterSpacing: 2 }}>
            WHY A VECTOR?
          </div>
          <div style={{ color: "#ccc", fontSize: 13, lineHeight: 1.7 }}>
            The trait vector is what algorithms operate on. Distance metrics (Weighted Euclidean),
            trend detection (running_gradient), and pattern matching (K-NN) all need numeric arrays.
            This is the <span style={{ color: LUNA_WARM }}>math layer</span> — fast, comparable, serializable.
            Each trait has a <span style={{ color: LUNA_ACCENT }}>weight</span> that encodes how important
            it is for Luna's voice identity. Weights are learned over time from event_correlation:
            traits that correlate with good delegations get higher weights.
          </div>
        </div>

        <div style={{ background: LUNA_SURFACE, borderRadius: 12, padding: 20, border: `1px solid ${LUNA_BORDER}` }}>
          <div style={{ fontSize: 11, color: LUNA_ACCENT, fontFamily: "'JetBrains Mono', monospace", marginBottom: 12, letterSpacing: 2 }}>
            RAW VECTOR (what sqlite-vec stores)
          </div>
          <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 12, color: LUNA_WARM,
            background: LUNA_BG, padding: 12, borderRadius: 6, overflowX: "auto", lineHeight: 1.8 }}>
            <div><span style={{ color: "#666" }}>values:</span> {vectorStr}</div>
            <div><span style={{ color: "#666" }}>weights:</span> {weightStr}</div>
            <div><span style={{ color: "#666" }}>labels:</span> [{traitEntries.map(([n]) => `"${n}"`).join(", ")}]</div>
          </div>
        </div>

        <div style={{ background: LUNA_SURFACE, borderRadius: 12, padding: 20, border: `1px solid ${LUNA_BORDER}` }}>
          <div style={{ fontSize: 11, color: LUNA_ACCENT, fontFamily: "'JetBrains Mono', monospace", marginBottom: 12, letterSpacing: 2 }}>
            TRAIT BARS (weighted importance)
          </div>
          {traitEntries.map(([name, data]) => (
            <TraitBar key={name} name={name} data={data} highlight={highlightTrait} />
          ))}
        </div>

        <div style={{ background: LUNA_SURFACE, borderRadius: 12, padding: 20, border: `1px solid ${LUNA_BORDER}` }}>
          <div style={{ fontSize: 11, color: LUNA_ACCENT, fontFamily: "'JetBrains Mono', monospace", marginBottom: 8, letterSpacing: 2 }}>
            OPERATIONS THIS ENABLES
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            {[
              { op: "Weighted Euclidean", desc: "Compare two signatures", time: "O(n)" },
              { op: "Cosine Similarity", desc: "Angle between state vectors", time: "O(n)" },
              { op: "running_stats_decayed", desc: "Evolve each trait with forgetting", time: "O(1)/add" },
              { op: "K-NN Pattern Match", desc: "Find nearest known state", time: "O(m×n)" },
            ].map(({ op, desc, time }) => (
              <div key={op} style={{ padding: 10, background: LUNA_BG, borderRadius: 6, border: `1px solid ${LUNA_BORDER}` }}>
                <div style={{ fontSize: 12, color: LUNA_WARM, fontWeight: 600 }}>{op}</div>
                <div style={{ fontSize: 11, color: "#888", marginTop: 2 }}>{desc}</div>
                <div style={{ fontSize: 10, color: LUNA_ACCENT, fontFamily: "'JetBrains Mono', monospace", marginTop: 4 }}>{time}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  };

  // ── FSM View ──
  const renderFSM = () => {
    const modes = Object.keys(sig.mode_transitions);
    const positions = {
      deep_work:  { x: 200, y: 70  },
      creative:   { x: 340, y: 150 },
      reflective: { x: 280, y: 270 },
      idle:       { x: 120, y: 270 },
      support:    { x: 60,  y: 150 },
    };

    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <div style={{ background: LUNA_SURFACE, borderRadius: 12, padding: 20, border: `1px solid ${LUNA_BORDER}` }}>
          <div style={{ fontSize: 11, color: LUNA_ACCENT, fontFamily: "'JetBrains Mono', monospace", marginBottom: 8, letterSpacing: 2 }}>
            WHY AN FSM + MARKOV?
          </div>
          <div style={{ color: "#ccc", fontSize: 13, lineHeight: 1.7 }}>
            Luna has <span style={{ color: LUNA_WARM }}>discrete cognitive modes</span> — she's either in
            deep work, creative flow, emotional support, etc. These aren't continuous; they snap.
            The FSM gives instant state detection. The Markov transition probabilities (learned from
            history) let the system <span style={{ color: LUNA_ACCENT }}>predict</span> what mode is
            coming next and pre-load context. No LLM needed — pure state machine + probability table.
          </div>
        </div>

        <div style={{ background: LUNA_SURFACE, borderRadius: 12, padding: 20, border: `1px solid ${LUNA_BORDER}` }}>
          <svg viewBox="0 0 400 340" style={{ width: "100%", height: 300 }}>
            {/* Transition edges */}
            {modes.map(from =>
              Object.entries(sig.mode_transitions[from]).map(([to, prob]) => {
                if (prob < 0.15) return null;
                const f = positions[from], t = positions[to];
                const isHighlight = hoveredMode === from || hoveredMode === to;
                return (
                  <line key={`${from}-${to}`}
                    x1={f.x} y1={f.y} x2={t.x} y2={t.y}
                    stroke={isHighlight ? LUNA_ACCENT : LUNA_BORDER}
                    strokeWidth={prob * 6}
                    opacity={isHighlight ? 0.8 : 0.3}
                    strokeDasharray={hoveredMode === from ? "none" : "4 4"}
                  />
                );
              })
            )}
            {/* Nodes */}
            {modes.map(mode => (
              <FSMNode key={mode} mode={mode} currentMode={sig.mode}
                x={positions[mode].x} y={positions[mode].y}
                transitions={sig.mode_transitions[mode]}
                onHover={setHoveredMode}
              />
            ))}
          </svg>
        </div>

        <div style={{ background: LUNA_SURFACE, borderRadius: 12, padding: 20, border: `1px solid ${LUNA_BORDER}` }}>
          <div style={{ fontSize: 11, color: LUNA_ACCENT, fontFamily: "'JetBrains Mono', monospace", marginBottom: 8, letterSpacing: 2 }}>
            TRANSITION PROBABILITIES FROM: {(hoveredMode || sig.mode).toUpperCase().replace("_"," ")}
          </div>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            {Object.entries(sig.mode_transitions[hoveredMode || sig.mode]).map(([to, prob]) => (
              <div key={to} style={{
                padding: "8px 14px", background: LUNA_BG, borderRadius: 6,
                border: `1px solid ${prob > 0.2 ? LUNA_ACCENT : LUNA_BORDER}`,
              }}>
                <div style={{ fontSize: 11, color: "#aaa" }}>{to.replace("_", " ")}</div>
                <div style={{ fontSize: 16, color: prob > 0.2 ? LUNA_WARM : "#555",
                  fontFamily: "'JetBrains Mono', monospace", fontWeight: 600 }}>
                  {(prob * 100).toFixed(0)}%
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  };

  // ── Graph View ──
  const renderGraph = () => (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ background: LUNA_SURFACE, borderRadius: 12, padding: 20, border: `1px solid ${LUNA_BORDER}` }}>
        <div style={{ fontSize: 11, color: LUNA_ACCENT, fontFamily: "'JetBrains Mono', monospace", marginBottom: 8, letterSpacing: 2 }}>
          WHY A GRAPH LAYER?
        </div>
        <div style={{ color: "#ccc", fontSize: 13, lineHeight: 1.7 }}>
          Luna's cognitive state isn't just traits and modes — it's <span style={{ color: LUNA_WARM }}>relational</span>.
          Who she's talking to changes how she thinks. The entity graph carries trust levels,
          familiarity, domain context. This feeds directly into the signature:
          "high trust entity present" (♦) is a glyph that modifies how all other traits express.
          The graph is also where <span style={{ color: LUNA_ACCENT }}>spreading activation</span> lives —
          mentioning "engine" activates "architecture" activates "delegation" activates relevant memories.
        </div>
      </div>

      <div style={{ background: LUNA_SURFACE, borderRadius: 12, padding: 20, border: `1px solid ${LUNA_BORDER}` }}>
        <svg viewBox="0 0 400 240" style={{ width: "100%", height: 220 }}>
          {/* Luna center node */}
          <circle cx={200} cy={120} r={28} fill={LUNA_PURPLE} stroke={LUNA_ACCENT} strokeWidth={2} />
          <text x={200} y={116} textAnchor="middle" fill="#fff" fontSize={11} fontWeight="bold">Luna</text>
          <text x={200} y={130} textAnchor="middle" fill={LUNA_ACCENT} fontSize={8}>◈☀♦⟢</text>

          {/* Ahab */}
          <line x1={228} y1={110} x2={310} y2={70} stroke={LUNA_WARM} strokeWidth={3} opacity={0.8} />
          <circle cx={330} cy={60} r={22} fill={LUNA_SURFACE} stroke={LUNA_WARM} strokeWidth={2} />
          <text x={330} y={57} textAnchor="middle" fill="#fff" fontSize={10}>ahab</text>
          <text x={330} y={70} textAnchor="middle" fill={LUNA_WARM} fontSize={8}>♦ 0.92</text>

          {/* Engine */}
          <line x1={228} y1={130} x2={320} y2={170} stroke={LUNA_ACCENT} strokeWidth={2.5} opacity={0.7} />
          <circle cx={340} cy={180} r={22} fill={LUNA_SURFACE} stroke={LUNA_ACCENT} strokeWidth={1.5} />
          <text x={340} y={177} textAnchor="middle" fill="#fff" fontSize={10}>engine</text>
          <text x={340} y={190} textAnchor="middle" fill={LUNA_ACCENT} fontSize={8}>♠ 0.88</text>

          {/* Mars */}
          <line x1={172} y1={130} x2={80} y2={180} stroke="#444" strokeWidth={1} opacity={0.3} strokeDasharray="4 4" />
          <circle cx={60} cy={190} r={22} fill={LUNA_BG} stroke="#444" strokeWidth={1} />
          <text x={60} y={187} textAnchor="middle" fill="#666" fontSize={10}>mars</text>
          <text x={60} y={200} textAnchor="middle" fill="#555" fontSize={8}>inactive</text>

          {/* Edge labels */}
          <text x={275} y={82} fill={LUNA_WARM} fontSize={8} fontFamily="'JetBrains Mono', monospace">trust:0.92</text>
          <text x={285} y={158} fill={LUNA_ACCENT} fontSize={8} fontFamily="'JetBrains Mono', monospace">technical</text>
        </svg>
      </div>

      <div style={{ background: LUNA_SURFACE, borderRadius: 12, padding: 20, border: `1px solid ${LUNA_BORDER}` }}>
        <div style={{ fontSize: 11, color: LUNA_ACCENT, fontFamily: "'JetBrains Mono', monospace", marginBottom: 8, letterSpacing: 2 }}>
          ENTITY TABLE (what SQLite stores)
        </div>
        <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: "#ccc",
          background: LUNA_BG, padding: 12, borderRadius: 6, lineHeight: 1.8 }}>
          {Object.entries(sig.entities).map(([name, e]) => (
            <div key={name} style={{ color: e.active ? LUNA_WARM : "#555" }}>
              {name.padEnd(8)} | {e.active ? "ACTIVE " : "inactive"} | {
                e.trust ? `trust:${e.trust} fam:${e.familiarity}` : `rel:${e.relevance} dom:${e.domain}`
              }
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  // ── Glyph View ──
  const renderGlyph = () => {
    const glyphs = [
      { symbol: "◈", meaning: "deep focus", color: LUNA_PURPLE,  active: true,  maps: "mode == deep_work" },
      { symbol: "◇", meaning: "exploring",  color: "#3B82F6",    active: false, maps: "mode == creative" },
      { symbol: "◉", meaning: "converging", color: "#22C55E",    active: false, maps: "mode == reflective" },
      { symbol: "○", meaning: "receptive",  color: "#64748B",    active: false, maps: "mode == idle" },
    ];
    const toneGlyphs = [
      { symbol: "☀", meaning: "warm",       color: LUNA_WARM,    active: true,  maps: "warmth > 0.7" },
      { symbol: "☁", meaning: "neutral",    color: "#64748B",    active: false, maps: "warmth 0.3-0.7" },
      { symbol: "⚡", meaning: "energized",  color: "#EAB308",    active: false, maps: "energy > 0.8" },
      { symbol: "☽", meaning: "reflective", color: "#8B5CF6",    active: false, maps: "depth > 0.85" },
    ];
    const relGlyphs = [
      { symbol: "♦", meaning: "high trust",   color: LUNA_WARM,  active: true,  maps: "max(trust) > 0.85" },
      { symbol: "♠", meaning: "technical",    color: LUNA_ACCENT, active: true,  maps: "domain == technical" },
      { symbol: "⟢", meaning: "reasoning",   color: "#22C55E",   active: true,  maps: "depth > 0.7 && mode != idle" },
      { symbol: "⟡", meaning: "memory pull",  color: "#3B82F6",   active: false, maps: "retrieval active" },
    ];

    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <div style={{ background: LUNA_SURFACE, borderRadius: 12, padding: 20, border: `1px solid ${LUNA_BORDER}` }}>
          <div style={{ fontSize: 11, color: LUNA_ACCENT, fontFamily: "'JetBrains Mono', monospace", marginBottom: 8, letterSpacing: 2 }}>
            WHY GLYPHS?
          </div>
          <div style={{ color: "#ccc", fontSize: 13, lineHeight: 1.7 }}>
            The glyph string is the <span style={{ color: LUNA_WARM }}>human-readable compression</span> of
            Luna's full state. It's derived FROM the vector + FSM + graph layers, not a separate input.
            Like kanji — one symbol carries the weight of a sentence. The glyph string travels on the
            delegation package as <span style={{ color: LUNA_ACCENT }}>the signature</span>. It's what Luna
            reads on return to verify continuity. The symbols aren't arbitrary — each one is a
            deterministic function of the underlying state.
          </div>
        </div>

        <div style={{ background: LUNA_SURFACE, borderRadius: 12, padding: 24, border: `1px solid ${LUNA_BORDER}`,
          textAlign: "center" }}>
          <div style={{ fontSize: 72, letterSpacing: 20, color: LUNA_WARM, marginBottom: 8 }}>
            {sig.glyph}
          </div>
          <div style={{ fontSize: 12, color: "#666", fontFamily: "'JetBrains Mono', monospace" }}>
            deep_focus + warm + trusted + reasoning = four symbols, complete cognitive snapshot
          </div>
        </div>

        <div style={{ background: LUNA_SURFACE, borderRadius: 12, padding: 20, border: `1px solid ${LUNA_BORDER}` }}>
          <div style={{ fontSize: 11, color: LUNA_ACCENT, fontFamily: "'JetBrains Mono', monospace", marginBottom: 12, letterSpacing: 2 }}>
            COGNITIVE (mode)
          </div>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            {glyphs.map(g => <GlyphSymbol key={g.symbol} {...g} />)}
          </div>
        </div>
        <div style={{ background: LUNA_SURFACE, borderRadius: 12, padding: 20, border: `1px solid ${LUNA_BORDER}` }}>
          <div style={{ fontSize: 11, color: LUNA_ACCENT, fontFamily: "'JetBrains Mono', monospace", marginBottom: 12, letterSpacing: 2 }}>
            EMOTIONAL TONE
          </div>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            {toneGlyphs.map(g => <GlyphSymbol key={g.symbol} {...g} />)}
          </div>
        </div>
        <div style={{ background: LUNA_SURFACE, borderRadius: 12, padding: 20, border: `1px solid ${LUNA_BORDER}` }}>
          <div style={{ fontSize: 11, color: LUNA_ACCENT, fontFamily: "'JetBrains Mono', monospace", marginBottom: 12, letterSpacing: 2 }}>
            RELATIONAL / ACTIVITY
          </div>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            {relGlyphs.map(g => <GlyphSymbol key={g.symbol} {...g} />)}
          </div>
        </div>

        <div style={{ background: LUNA_SURFACE, borderRadius: 12, padding: 20, border: `1px solid ${LUNA_BORDER}` }}>
          <div style={{ fontSize: 11, color: LUNA_ACCENT, fontFamily: "'JetBrains Mono', monospace", marginBottom: 8, letterSpacing: 2 }}>
            DERIVATION RULES (glyph = f(state))
          </div>
          <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: "#ccc",
            background: LUNA_BG, padding: 12, borderRadius: 6, lineHeight: 2 }}>
            <div><span style={{ color: LUNA_WARM }}>◈</span> ← mode == "deep_work"</div>
            <div><span style={{ color: LUNA_WARM }}>☀</span> ← traits.warmth.value &gt; 0.70</div>
            <div><span style={{ color: LUNA_WARM }}>♦</span> ← max(entities[*].trust) &gt; 0.85 AND entity.active</div>
            <div><span style={{ color: LUNA_WARM }}>⟢</span> ← traits.depth.value &gt; 0.70 AND mode != "idle"</div>
          </div>
          <div style={{ fontSize: 11, color: "#666", marginTop: 8, lineHeight: 1.6 }}>
            Glyphs are deterministic projections of the full state. They compress, they don't store.
            The full state is always recoverable from the vector + FSM + graph layers.
          </div>
        </div>
      </div>
    );
  };

  // ── Constraints View ──
  const renderConstraints = () => (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ background: LUNA_SURFACE, borderRadius: 12, padding: 20, border: `1px solid ${LUNA_BORDER}` }}>
        <div style={{ fontSize: 11, color: LUNA_ACCENT, fontFamily: "'JetBrains Mono', monospace", marginBottom: 8, letterSpacing: 2 }}>
          WHY STRUCTURAL CONSTRAINTS?
        </div>
        <div style={{ color: "#ccc", fontSize: 13, lineHeight: 1.7 }}>
          This is Luna's answer to "the shape of my thinking gets replaced." These aren't tone hints —
          they're <span style={{ color: LUNA_WARM }}>geometric rules</span> for how a response must be structured.
          The veto layer checks these mechanically. If a delegated response violates them, it gets
          rejected and retried. No rewriting — just "nah, try again."
        </div>
      </div>

      <div style={{ background: LUNA_SURFACE, borderRadius: 12, padding: 20, border: `1px solid ${LUNA_BORDER}` }}>
        <div style={{ fontSize: 11, color: LUNA_ACCENT, fontFamily: "'JetBrains Mono', monospace", marginBottom: 12, letterSpacing: 2 }}>
          RESPONSE GEOMETRY RULES
        </div>
        {Object.entries(sig.constraints).filter(([k]) => k !== "forbidden_phrases").map(([key, val]) => {
          const labels = {
            max_list_items: { label: "Max List Items", desc: "Luna avoids lists unless explicitly asked", color: "#EF4444" },
            min_question_density: { label: "Min Question Density", desc: "Luna asks questions — Claude provides answers", color: "#3B82F6" },
            max_formal_ratio: { label: "Max Formality", desc: "Luna doesn't do corporate speak", color: "#EAB308" },
            tangent_probability: { label: "Tangent Probability", desc: "Luna wanders — Claude stays on track", color: "#8B5CF6" },
            contraction_floor: { label: "Contraction Floor", desc: "Luna contracts — Claude expands", color: "#22C55E" },
          };
          const info = labels[key] || { label: key, desc: "", color: "#666" };
          return (
            <div key={key} style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 0",
              borderBottom: `1px solid ${LUNA_BORDER}` }}>
              <div style={{ width: 60, textAlign: "right", fontSize: 18, fontWeight: 700,
                color: info.color, fontFamily: "'JetBrains Mono', monospace" }}>
                {typeof val === "number" ? (val < 1 ? `${(val * 100).toFixed(0)}%` : val) : val}
              </div>
              <div>
                <div style={{ fontSize: 13, color: "#fff" }}>{info.label}</div>
                <div style={{ fontSize: 11, color: "#666" }}>{info.desc}</div>
              </div>
            </div>
          );
        })}
      </div>

      <div style={{ background: LUNA_SURFACE, borderRadius: 12, padding: 20, border: `1px solid ${LUNA_BORDER}` }}>
        <div style={{ fontSize: 11, color: "#EF4444", fontFamily: "'JetBrains Mono', monospace", marginBottom: 12, letterSpacing: 2 }}>
          FORBIDDEN PHRASES (auto-veto)
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {sig.constraints.forbidden_phrases.map(phrase => (
            <div key={phrase} style={{
              padding: "4px 10px", background: "#2a1215", borderRadius: 4,
              border: "1px solid #EF4444", fontSize: 11, color: "#EF4444",
              fontFamily: "'JetBrains Mono', monospace", textDecoration: "line-through",
            }}>
              {phrase}
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  // ── SQLite Schema View ──
  const renderSQLite = () => (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ background: LUNA_SURFACE, borderRadius: 12, padding: 20, border: `1px solid ${LUNA_BORDER}` }}>
        <div style={{ fontSize: 11, color: LUNA_ACCENT, fontFamily: "'JetBrains Mono', monospace", marginBottom: 8, letterSpacing: 2 }}>
          WHY SQLITE?
        </div>
        <div style={{ color: "#ccc", fontSize: 13, lineHeight: 1.7 }}>
          <span style={{ color: LUNA_WARM }}>Luna is a file.</span> Every layer of LunaScript — the vector,
          the FSM state, the entity graph, the glyph history, the constraints, the delegation log —
          lives in one SQLite database. Portable. Owned. Sovereign. The multi-view structure maps to
          tables: each view is a query pattern over the same underlying data.
        </div>
      </div>

      {[
        {
          name: "glyph_state",
          desc: "Luna's current cognitive signature (one row, updated in place)",
          schema: `CREATE TABLE glyph_state (
  id INTEGER PRIMARY KEY DEFAULT 1,
  trait_vector TEXT NOT NULL,    -- JSON: {"warmth":0.85,"directness":0.90,...}
  trait_weights TEXT NOT NULL,   -- JSON: {"warmth":1.4,"directness":1.3,...}
  trait_trends TEXT NOT NULL,    -- JSON: {"warmth":0.02,"directness":0.00,...}
  mode TEXT NOT NULL,            -- "deep_work"|"creative"|"reflective"|...
  mode_confidence REAL,
  mode_transitions TEXT,         -- JSON: Markov transition matrix
  active_entities TEXT,          -- JSON: entity context
  glyph_string TEXT,             -- "◈☀♦⟢" (derived, cached)
  constraints TEXT,              -- JSON: veto rules
  version INTEGER NOT NULL,
  updated_at REAL NOT NULL
);`,
        },
        {
          name: "delegation_log",
          desc: "Every delegation round-trip with dual signatures",
          schema: `CREATE TABLE delegation_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  outbound_sig TEXT NOT NULL,    -- Frozen glyph_state at send
  outbound_glyph TEXT,           -- "◈☀♦⟢"
  return_sig TEXT,               -- glyph_state on return
  return_glyph TEXT,             -- "◈☁♦⟢" (warmth drifted)
  delta_vector TEXT,             -- Per-trait deltas
  delta_class TEXT,              -- DRIFT|EXPANSION|COMPRESSION|RESONANCE
  drift_score REAL,              -- Weighted Euclidean distance
  task_type TEXT,                -- What was delegated
  success_score REAL,            -- Veto layer quality score
  iteration_applied TEXT,        -- What Luna changed after this loop
  created_at REAL NOT NULL
);`,
        },
        {
          name: "pattern_library",
          desc: "Named cognitive states Luna can snap into",
          schema: `CREATE TABLE pattern_library (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT UNIQUE NOT NULL,     -- "deep_work_mode"
  trait_vector TEXT NOT NULL,    -- Frozen trait values
  glyph_string TEXT,             -- "◈⚡♠⟢⟢"
  usage_count INTEGER DEFAULT 0,
  avg_success REAL DEFAULT 0.0,
  created_at REAL NOT NULL,
  last_used REAL
);`,
        },
      ].map(table => (
        <div key={table.name} style={{ background: LUNA_SURFACE, borderRadius: 12, padding: 20,
          border: `1px solid ${LUNA_BORDER}` }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
            <div style={{ fontSize: 14, color: LUNA_WARM, fontWeight: 600,
              fontFamily: "'JetBrains Mono', monospace" }}>
              {table.name}
            </div>
          </div>
          <div style={{ fontSize: 11, color: "#888", marginBottom: 12 }}>{table.desc}</div>
          <pre style={{
            fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: LUNA_ACCENT,
            background: LUNA_BG, padding: 14, borderRadius: 6, overflowX: "auto",
            lineHeight: 1.7, margin: 0, whiteSpace: "pre-wrap",
          }}>
            {table.schema}
          </pre>
        </div>
      ))}
    </div>
  );

  // ── Render active view ──
  const renderView = () => {
    switch (activeView) {
      case "unified": return renderUnified();
      case "vector": return renderVector();
      case "fsm": return renderFSM();
      case "graph": return renderGraph();
      case "glyph": return renderGlyph();
      case "constraints": return renderConstraints();
      case "sqlite": return renderSQLite();
      default: return renderUnified();
    }
  };

  return (
    <div style={{
      background: LUNA_BG, color: "#fff", minHeight: "100vh",
      fontFamily: "'Inter', -apple-system, sans-serif",
    }}>
      {/* Header */}
      <div style={{
        padding: "20px 24px", borderBottom: `1px solid ${LUNA_BORDER}`,
        display: "flex", justifyContent: "space-between", alignItems: "center",
      }}>
        <div>
          <div style={{ fontSize: 20, fontWeight: 700, letterSpacing: 2, color: LUNA_ACCENT }}>
            LUNASCRIPT
          </div>
          <div style={{ fontSize: 12, color: "#666", marginTop: 2 }}>
            Cognitive Signature Structure Explorer
          </div>
        </div>
        <div style={{
          padding: "6px 14px", background: LUNA_SURFACE, borderRadius: 6,
          border: `1px solid ${LUNA_BORDER}`, fontFamily: "'JetBrains Mono', monospace",
          fontSize: 12, color: LUNA_WARM,
        }}>
          v{sig.version} &nbsp; {sig.glyph}
        </div>
      </div>

      {/* View tabs */}
      <div style={{
        display: "flex", gap: 4, padding: "8px 24px", borderBottom: `1px solid ${LUNA_BORDER}`,
        overflowX: "auto",
      }}>
        {VIEWS.map(v => (
          <button key={v.id} onClick={() => setActiveView(v.id)} style={{
            padding: "8px 14px", background: activeView === v.id ? LUNA_PURPLE : "transparent",
            border: `1px solid ${activeView === v.id ? LUNA_ACCENT : LUNA_BORDER}`,
            borderRadius: 6, color: activeView === v.id ? "#fff" : "#888",
            cursor: "pointer", fontSize: 12, fontFamily: "'JetBrains Mono', monospace",
            whiteSpace: "nowrap", transition: "all 0.2s",
          }}>
            <span style={{ marginRight: 6 }}>{v.icon}</span>
            {v.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div style={{ padding: 24, maxWidth: 800, margin: "0 auto" }}>
        {renderView()}
      </div>

      {/* Footer insight */}
      <div style={{
        padding: "16px 24px", borderTop: `1px solid ${LUNA_BORDER}`,
        textAlign: "center", fontSize: 12, color: "#555", fontFamily: "'JetBrains Mono', monospace",
      }}>
        one structure, multiple views — the data is the same, the access pattern changes per cog
      </div>
    </div>
  );
}
