import { useState, useRef, useEffect, useCallback } from "react";

// ═══════════════════════════════════════════════════════════════
// LUNASCRIPT PROTOTYPE — The Cog Machine Running Live
// ═══════════════════════════════════════════════════════════════

const C = {
  bg: "#0B0811", surface: "#151020", surface2: "#1C1530",
  border: "#2A2040", borderActive: "#6B4FA0",
  purple: "#6B4FA0", purpleLight: "#9B7DD4", purpleDim: "#3D2D6B",
  warm: "#D4A07D", warmDim: "#8B6B52",
  green: "#22C55E", greenDim: "#0F2418",
  red: "#EF4444", redDim: "#2A1215",
  yellow: "#EAB308", yellowDim: "#2A2008",
  blue: "#3B82F6", blueDim: "#0E2040",
  text: "#E8E4F0", textDim: "#666680", textMuted: "#444455",
};

const mono = "'JetBrains Mono', 'Fira Code', 'Consolas', monospace";
const sans = "'Inter', -apple-system, sans-serif";

// ── Initial Engine State ──
const INITIAL_STATE = {
  traits: {
    warmth: { value: 0.80, weight: 1.4, trend: 0.0 },
    directness: { value: 0.85, weight: 1.3, trend: 0.0 },
    curiosity: { value: 0.75, weight: 1.0, trend: 0.0 },
    humor: { value: 0.60, weight: 0.8, trend: 0.0 },
    formality: { value: 0.25, weight: 1.2, trend: 0.0 },
    energy: { value: 0.70, weight: 0.7, trend: 0.0 },
    depth: { value: 0.70, weight: 1.1, trend: 0.0 },
    patience: { value: 0.85, weight: 0.9, trend: 0.0 },
  },
  mode: "idle",
  modeConfidence: 0.5,
  position: "OPENING",
  entities: {},
  glyph: "○",
  version: 1,
  epsilon: 0.15,
  driftHistory: [],
  delegationCount: 0,
  turnCount: 0,
};

// ── Geometry Templates ──
const GEOMETRY = {
  OPENING: { maxSent: 3, questionReq: true, assertRatio: 0.2, tangent: false, pattern: "acknowledge → question", color: C.blue },
  EXPLORING: { maxSent: 8, questionReq: true, assertRatio: 0.4, tangent: true, pattern: "react → think_aloud → tangent? → question", color: C.purpleLight },
  BUILDING: { maxSent: 15, questionReq: false, assertRatio: 0.7, tangent: false, pattern: "build_on → add_layer → validate?", color: C.green },
  DEEPENING: { maxSent: 20, questionReq: false, assertRatio: 0.8, tangent: true, pattern: "connect → go_deeper → surface_insight", color: C.warm },
  PIVOTING: { maxSent: 8, questionReq: true, assertRatio: 0.3, tangent: false, pattern: "acknowledge_shift → bridge → new_question", color: C.yellow },
  CLOSING: { maxSent: 4, questionReq: false, assertRatio: 0.5, tangent: false, pattern: "summarize → next_step? → warm_close", color: C.textDim },
};

// ── Known Entities ──
const KNOWN_ENTITIES = {
  ahab: { type: "person", trust: 0.92, familiarity: 0.95 },
  luna: { type: "self", trust: 1.0, familiarity: 1.0 },
  engine: { type: "project", relevance: 0.88, domain: "technical" },
  "memory matrix": { type: "system", relevance: 0.85, domain: "technical" },
  "mars college": { type: "place", relevance: 0.50, domain: "physical" },
  tarcila: { type: "person", trust: 0.70, familiarity: 0.60 },
  marzipan: { type: "person", trust: 0.65, familiarity: 0.55 },
  ben: { type: "persona", relevance: 0.75, domain: "extraction" },
  dude: { type: "persona", relevance: 0.80, domain: "architecture" },
  lora: { type: "system", relevance: 0.70, domain: "training" },
  sqlite: { type: "technology", relevance: 0.82, domain: "technical" },
  claude: { type: "system", relevance: 0.78, domain: "delegation" },
  lunascript: { type: "project", relevance: 0.90, domain: "technical" },
};

// ── Detection Functions (THE COGS) ──

function detectEntities(message) {
  const lower = message.toLowerCase();
  const found = {};
  for (const [name, data] of Object.entries(KNOWN_ENTITIES)) {
    if (lower.includes(name)) {
      found[name] = { ...data, active: true, lastSeen: 0 };
    }
  }
  return found;
}

function detectFormality(message) {
  const formal = /\b(therefore|furthermore|however|consequently|regarding|pursuant|shall|whereas)\b/gi;
  const casual = /\b(yo|yeah|cool|lol|haha|nah|kinda|gonna|wanna|dude|hey|ok|btw)\b/gi;
  const formalCount = (message.match(formal) || []).length;
  const casualCount = (message.match(casual) || []).length;
  const total = formalCount + casualCount || 1;
  return formalCount / total;
}

function detectQuestionDensity(message) {
  const sentences = message.split(/[.!?]+/).filter(s => s.trim());
  const questions = message.split("?").length - 1;
  return sentences.length > 0 ? questions / sentences.length : 0;
}

function detectTechnicalDensity(message) {
  const tech = /\b(algorithm|architecture|schema|vector|sqlite|api|function|cog|pipeline|prototype|binary|matrix|database|embed|inference|lora|model|deploy|runtime|latency|throughput|async|sync|token|parameter)\b/gi;
  const words = message.split(/\s+/).length || 1;
  return Math.min((message.match(tech) || []).length / words * 3, 1.0);
}

function detectEmotionalWeight(message) {
  const emotional = /\b(feel|feeling|felt|love|hate|scared|worried|excited|happy|sad|frustrated|anxious|afraid|hope|miss|hurt|angry|grateful|proud|lonely|overwhelmed)\b/gi;
  const words = message.split(/\s+/).length || 1;
  return Math.min((message.match(emotional) || []).length / words * 5, 1.0);
}

function detectNovelty(message, history) {
  if (history.length === 0) return 0.5;
  const prevWords = new Set(history.slice(-3).join(" ").toLowerCase().split(/\s+/));
  const newWords = message.toLowerCase().split(/\s+/).filter(w => !prevWords.has(w) && w.length > 3);
  return Math.min(newWords.length / (message.split(/\s+/).length || 1) * 2, 1.0);
}

function detectSentiment(message) {
  const pos = /\b(great|awesome|perfect|love|yes|yeah|nice|good|excellent|amazing|cool|sweet|brilliant|exactly|hell yeah)\b/gi;
  const neg = /\b(no|wrong|bad|hate|broken|fail|ugly|terrible|issue|problem|bug|stuck|confused|frustrated)\b/gi;
  const p = (message.match(pos) || []).length;
  const n = (message.match(neg) || []).length;
  return (p - n) / Math.max(p + n, 1);
}

function detectPosition(message, history, prevPosition) {
  const turnCount = history.length;
  const lower = message.toLowerCase().trim();
  const msgLen = message.length;
  const questionDensity = detectQuestionDensity(message);
  const hasDecisionLang = /\b(let's|going with|decided|choose|go ahead|do it|ship it|build|make|create)\b/i.test(message);
  const hasClosingLang = /\b(thanks|ok cool|got it|later|wrap|bye|see you|that's all|perfect)\b/i.test(message);
  const hasPivotLang = /\b(what about|actually|wait|hold on|different|change|switch|other|instead|btw|also)\b/i.test(message);
  const hasDeepLang = /\b(how does|why does|explain|what if|deeper|more about|specifically|exactly|detail)\b/i.test(message);

  if (turnCount <= 1) return { position: "OPENING", confidence: 0.9 };
  if (hasClosingLang && msgLen < 80) return { position: "CLOSING", confidence: 0.8 };
  if (hasPivotLang && prevPosition !== "OPENING") return { position: "PIVOTING", confidence: 0.7 };
  if (hasDecisionLang) return { position: "BUILDING", confidence: 0.75 };
  if (hasDeepLang || (msgLen > 200 && questionDensity < 0.3)) return { position: "DEEPENING", confidence: 0.7 };
  if (questionDensity > 0.3) return { position: "EXPLORING", confidence: 0.75 };
  if (prevPosition === "BUILDING" && !hasPivotLang) return { position: "BUILDING", confidence: 0.6 };
  return { position: "EXPLORING", confidence: 0.5 };
}

function detectMode(message, currentMode, history) {
  const tech = detectTechnicalDensity(message);
  const emo = detectEmotionalWeight(message);
  const novelty = detectNovelty(message, history);
  const msgLen = message.length;

  const scores = {
    deep_work: tech * 0.6 + (msgLen > 100 ? 0.3 : 0) + (detectQuestionDensity(message) < 0.3 ? 0.1 : 0),
    creative: novelty * 0.5 + (tech < 0.3 ? 0.2 : 0) + (msgLen > 50 ? 0.1 : 0),
    support: emo * 0.7 + (tech < 0.2 ? 0.2 : 0),
    reflective: (message.match(/\b(thinking|wonder|realize|maybe|hmm|interesting)\b/gi) || []).length * 0.25,
    idle: msgLen < 30 && detectQuestionDensity(message) < 0.2 ? 0.5 : 0,
  };

  // Inertia: current mode gets a bonus
  scores[currentMode] = (scores[currentMode] || 0) + 0.15;

  let best = currentMode, bestScore = scores[currentMode] || 0;
  for (const [mode, score] of Object.entries(scores)) {
    if (score > bestScore) { best = mode; bestScore = score; }
  }
  return { mode: best, confidence: Math.min(bestScore, 0.99) };
}

function deriveGlyph(state) {
  let g = [];
  const modeMap = { deep_work: "◈", creative: "◇", reflective: "◉", idle: "○", support: "◎" };
  g.push(modeMap[state.mode] || "○");
  if (state.traits.warmth.value > 0.70) g.push("☀");
  else if (state.traits.warmth.value < 0.35) g.push("☁");
  if (state.traits.energy.value > 0.80) g.push("⚡");
  const hasHighTrust = Object.values(state.entities).some(e => e.trust > 0.85 && e.active);
  if (hasHighTrust) g.push("♦");
  const hasTech = Object.values(state.entities).some(e => e.domain === "technical" && e.active);
  if (hasTech) g.push("♠");
  if (state.traits.depth.value > 0.70 && state.mode !== "idle") g.push("⟢");
  if (state.traits.curiosity.value > 0.80) g.push("⟡");
  return g.join("");
}

function simulateDelegation(state, message) {
  // Simulate what Claude might do to Luna's signature
  const noise = () => (Math.random() - 0.5) * 0.15;
  const returnTraits = {};
  let driftDetails = [];

  for (const [name, t] of Object.entries(state.traits)) {
    let drift = noise();
    // Claude tends to: reduce warmth, increase formality, reduce humor, flatten curiosity
    if (name === "warmth") drift -= 0.08;
    if (name === "formality") drift += 0.10;
    if (name === "humor") drift -= 0.06;
    if (name === "curiosity") drift -= 0.04;
    if (name === "directness") drift -= 0.03;

    const newVal = Math.max(0, Math.min(1, t.value + drift));
    returnTraits[name] = { ...t, value: newVal };

    if (Math.abs(drift) > 0.05) {
      driftDetails.push({ trait: name, sent: t.value, returned: newVal, delta: drift });
    }
  }

  return { returnTraits, driftDetails };
}

function vetoCheck(delegation, geometry) {
  const violations = [];
  // Simulate checking structural constraints
  if (delegation.returnTraits.formality.value > 0.50) violations.push("formality_too_high");
  if (delegation.returnTraits.warmth.value < 0.50) violations.push("warmth_lost");
  if (delegation.returnTraits.humor.value < 0.30) violations.push("humor_flattened");
  if (!geometry.tangent && Math.random() > 0.7) violations.push("unwanted_tangent");
  if (geometry.questionReq && Math.random() > 0.6) violations.push("no_question_found");
  return { passed: violations.length === 0, violations, score: Math.max(0, 1 - violations.length * 0.2) };
}

function classifyDelta(driftScore) {
  if (driftScore < 0.08) return { cls: "RESONANCE", color: C.green, icon: "✓" };
  if (driftScore < 0.20) return { cls: "DRIFT", color: C.yellow, icon: "~" };
  if (driftScore < 0.35) return { cls: "COMPRESSION", color: C.red, icon: "↓" };
  return { cls: "COMPRESSION", color: C.red, icon: "!!" };
}

// ── UI Components ──

function CogStatus({ label, value, color, detail, firing }) {
  return (
    <div style={{
      padding: "8px 12px", background: firing ? `${color}15` : C.surface,
      border: `1px solid ${firing ? color : C.border}`,
      borderRadius: 6, transition: "all 0.3s",
      borderLeft: `3px solid ${firing ? color : C.border}`,
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontSize: 11, fontFamily: mono, color: firing ? color : C.textDim, letterSpacing: 1 }}>
          {label}
        </span>
        <span style={{ fontSize: 12, fontFamily: mono, color: firing ? C.text : C.textDim, fontWeight: 600 }}>
          {value}
        </span>
      </div>
      {detail && firing && (
        <div style={{ fontSize: 10, color: C.textDim, marginTop: 4, fontFamily: mono }}>
          {detail}
        </div>
      )}
    </div>
  );
}

function TraitMini({ name, data, prevValue }) {
  const changed = prevValue !== undefined && Math.abs(data.value - prevValue) > 0.01;
  const dir = prevValue !== undefined ? (data.value > prevValue ? "↑" : data.value < prevValue ? "↓" : "") : "";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, padding: "3px 0" }}>
      <span style={{ width: 70, fontSize: 10, fontFamily: mono, color: C.purpleLight, textAlign: "right" }}>{name}</span>
      <div style={{ flex: 1, height: 8, background: C.surface2, borderRadius: 4, overflow: "hidden" }}>
        <div style={{
          width: `${data.value * 100}%`, height: "100%",
          background: changed ? (dir === "↑" ? C.green : C.red) : C.purpleDim,
          borderRadius: 4, transition: "all 0.5s",
        }} />
      </div>
      <span style={{ width: 32, fontSize: 10, fontFamily: mono, color: changed ? (dir === "↑" ? C.green : C.red) : C.textDim }}>
        {data.value.toFixed(2)}
      </span>
      {changed && <span style={{ fontSize: 10, color: dir === "↑" ? C.green : C.red }}>{dir}</span>}
    </div>
  );
}

function LogEntry({ entry }) {
  const colors = { info: C.purpleLight, cog: C.warm, delegation: C.blue, veto: C.yellow, learn: C.green, error: C.red };
  return (
    <div style={{
      display: "flex", gap: 8, padding: "4px 0",
      borderBottom: `1px solid ${C.border}08`,
      fontSize: 11, fontFamily: mono, lineHeight: 1.5,
    }}>
      <span style={{ color: C.textMuted, minWidth: 30 }}>{entry.turn}</span>
      <span style={{ color: colors[entry.type] || C.textDim, minWidth: 12 }}>{entry.icon || "·"}</span>
      <span style={{ color: C.textDim }}>{entry.text}</span>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// MAIN
// ═══════════════════════════════════════════════════════════════

export default function LunaScriptPrototype() {
  const [state, setState] = useState(INITIAL_STATE);
  const [prevTraits, setPrevTraits] = useState({});
  const [history, setHistory] = useState([]);
  const [logs, setLogs] = useState([{ turn: 0, type: "info", icon: "◉", text: "LunaScript engine initialized. glyph_state loaded from SQLite." }]);
  const [input, setInput] = useState("");
  const [cogsFiring, setCogsFiring] = useState({});
  const [delegationResult, setDelegationResult] = useState(null);
  const [lastMessage, setLastMessage] = useState("");
  const logRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [logs]);

  const addLog = useCallback((turn, type, icon, text) => {
    setLogs(prev => [...prev, { turn, type, icon, text }]);
  }, []);

  const fireCog = useCallback((name, duration = 600) => {
    setCogsFiring(prev => ({ ...prev, [name]: true }));
    setTimeout(() => setCogsFiring(prev => ({ ...prev, [name]: false })), duration);
  }, []);

  const processMessage = (msg) => {
    if (!msg.trim()) return;
    const turn = state.turnCount + 1;
    const newHistory = [...history, msg];
    setLastMessage(msg);

    setPrevTraits(Object.fromEntries(
      Object.entries(state.traits).map(([k, v]) => [k, v.value])
    ));

    addLog(turn, "info", "▸", `USER: "${msg.length > 60 ? msg.slice(0, 60) + "..." : msg}"`);

    // Build new state as mutable copy
    const newTraits = {};
    for (const [k, v] of Object.entries(state.traits)) {
      newTraits[k] = { ...v };
    }
    const ns = {
      traits: newTraits,
      mode: state.mode,
      modeConfidence: state.modeConfidence,
      position: state.position,
      entities: { ...state.entities },
      glyph: state.glyph,
      version: state.version,
      epsilon: state.epsilon,
      driftHistory: [...state.driftHistory],
      delegationCount: state.delegationCount,
      turnCount: turn,
    };

    // ── COG 1: Position Detection (ALWAYS) ──
    setTimeout(() => {
      fireCog("position", 800);
      const { position, confidence } = detectPosition(msg, newHistory, state.position);
      const posChanged = position !== state.position;
      ns.position = position;
      addLog(turn, "cog", "⚙", `POSITION: ${position} (${(confidence * 100).toFixed(0)}%)${posChanged ? ` ← was ${state.position}` : ""}`);
    }, 100);

    // ── COG 2: Entity Activation (ALWAYS) ──
    setTimeout(() => {
      fireCog("entities", 700);
      const found = detectEntities(msg);
      // Merge with existing, decay old
      const merged = { ...state.entities };
      for (const [name, e] of Object.entries(merged)) {
        if (!found[name]) {
          e.lastSeen = (e.lastSeen || 0) + 1;
          if (e.lastSeen > 5) e.active = false;
        }
      }
      for (const [name, e] of Object.entries(found)) {
        merged[name] = e;
      }
      ns.entities = merged;
      const activeNames = Object.entries(merged).filter(([, e]) => e.active).map(([n]) => n);
      if (activeNames.length > 0) {
        addLog(turn, "cog", "⚙", `ENTITIES: [${activeNames.join(", ")}] active`);
      }
    }, 300);

    // ── COG 3: Mode Detection (CONDITIONAL) ──
    setTimeout(() => {
      const { mode, confidence } = detectMode(msg, state.mode, history);
      const modeChanged = mode !== state.mode;
      if (modeChanged || confidence > 0.6) {
        fireCog("mode", 800);
        ns.mode = mode;
        ns.modeConfidence = confidence;
        addLog(turn, "cog", modeChanged ? "⚡" : "⚙",
          `MODE: ${mode} (${(confidence * 100).toFixed(0)}%)${modeChanged ? ` ← TRANSITION from ${state.mode}` : ""}`);
      }
    }, 500);

    // ── COG 4: Trait Adjustment (CONDITIONAL) ──
    setTimeout(() => {
      const formality = detectFormality(msg);
      const sentiment = detectSentiment(msg);
      const techDensity = detectTechnicalDensity(msg);
      const emotionalWeight = detectEmotionalWeight(msg);
      let traitShifts = [];

      const traits = { ...ns.traits };
      const lerp = (curr, target, alpha) => curr + (target - curr) * alpha;

      // Formality adapts to user
      const newFormality = lerp(traits.formality.value, formality, 0.3);
      if (Math.abs(newFormality - traits.formality.value) > 0.02) {
        traitShifts.push(`formality ${traits.formality.value.toFixed(2)}→${newFormality.toFixed(2)}`);
        traits.formality = { ...traits.formality, value: newFormality };
      }

      // Warmth responds to sentiment
      if (sentiment !== 0) {
        const warmShift = sentiment * 0.08;
        const newWarmth = Math.max(0.3, Math.min(1, traits.warmth.value + warmShift));
        if (Math.abs(warmShift) > 0.02) {
          traitShifts.push(`warmth ${traits.warmth.value.toFixed(2)}→${newWarmth.toFixed(2)}`);
          traits.warmth = { ...traits.warmth, value: newWarmth };
        }
      }

      // Depth responds to technical density
      if (techDensity > 0.3) {
        const newDepth = lerp(traits.depth.value, Math.min(0.95, traits.depth.value + 0.1), 0.4);
        traitShifts.push(`depth ${traits.depth.value.toFixed(2)}→${newDepth.toFixed(2)}`);
        traits.depth = { ...traits.depth, value: newDepth };
      }

      // Energy responds to message intensity
      const intensity = msg.length > 150 ? 0.8 : msg.length > 80 ? 0.6 : 0.4;
      const newEnergy = lerp(traits.energy.value, intensity, 0.2);
      if (Math.abs(newEnergy - traits.energy.value) > 0.03) {
        traitShifts.push(`energy ${traits.energy.value.toFixed(2)}→${newEnergy.toFixed(2)}`);
        traits.energy = { ...traits.energy, value: newEnergy };
      }

      // Curiosity increases when user asks questions
      if (detectQuestionDensity(msg) > 0.3) {
        const newCuriosity = Math.min(0.95, traits.curiosity.value + 0.05);
        traitShifts.push(`curiosity ${traits.curiosity.value.toFixed(2)}→${newCuriosity.toFixed(2)}`);
        traits.curiosity = { ...traits.curiosity, value: newCuriosity };
      }

      ns.traits = traits;
      if (traitShifts.length > 0) {
        fireCog("traits", 900);
        addLog(turn, "cog", "⚙", `TRAITS: ${traitShifts.join(", ")}`);
      }
    }, 700);

    // ── COG 5: Glyph Derivation (ALWAYS, after other cogs) ──
    setTimeout(() => {
      fireCog("glyph", 500);
      const newGlyph = deriveGlyph(ns);
      const glyphChanged = newGlyph !== state.glyph;
      ns.glyph = newGlyph;
      ns.version = state.version + 1;
      addLog(turn, "cog", glyphChanged ? "✦" : "⚙",
        `GLYPH: ${newGlyph} v${ns.version}${glyphChanged ? ` ← was ${state.glyph}` : " (unchanged)"}`);
    }, 1000);

    // ── DELEGATION SIMULATION (every 3rd turn or if complex) ──
    const shouldDelegate = turn % 3 === 0 || msg.length > 150 || detectTechnicalDensity(msg) > 0.4;
    if (shouldDelegate) {
      setTimeout(() => {
        fireCog("sign", 500);
        addLog(turn, "delegation", "✒", `SIGN OUTBOUND: ${ns.glyph} v${ns.version}`);
      }, 1200);

      setTimeout(() => {
        fireCog("delegate", 1000);
        addLog(turn, "delegation", "→", "DELEGATING to Claude API...");
      }, 1500);

      setTimeout(() => {
        const delegation = simulateDelegation(ns, msg);
        const driftScore = Math.sqrt(
          delegation.driftDetails.reduce((sum, d) =>
            sum + (ns.traits[d.trait]?.weight || 1) * d.delta * d.delta, 0)
        );
        const classification = classifyDelta(driftScore);

        // Veto check
        fireCog("veto", 800);
        const geo = GEOMETRY[ns.position] || GEOMETRY.EXPLORING;
        const veto = vetoCheck(delegation, geo);

        if (!veto.passed) {
          addLog(turn, "veto", "✗", `VETO FAILED: [${veto.violations.join(", ")}] — retrying with tighter constraints`);
          fireCog("veto", 400);
        }

        addLog(turn, "delegation", "←", `RETURNED: drift=${driftScore.toFixed(3)} → ${classification.cls}`);
        if (delegation.driftDetails.length > 0) {
          const drifted = delegation.driftDetails.map(d =>
            `${d.trait}: ${d.sent.toFixed(2)}→${d.returned.toFixed(2)} (${d.delta > 0 ? "+" : ""}${d.delta.toFixed(3)})`
          ).join(", ");
          addLog(turn, "delegation", "Δ", `DELTA: ${drifted}`);
        }

        // Learn
        setTimeout(() => {
          fireCog("learn", 800);
          ns.driftHistory = [...state.driftHistory, driftScore].slice(-50);
          ns.delegationCount = state.delegationCount + 1;

          // Weight adjustment
          const adjustments = [];
          for (const d of delegation.driftDetails) {
            if (Math.abs(d.delta) > 0.05) {
              const trait = ns.traits[d.trait];
              if (trait) {
                const oldWeight = trait.weight;
                trait.weight = Math.min(2.0, trait.weight * 1.08);
                adjustments.push(`${d.trait} weight ${oldWeight.toFixed(2)}→${trait.weight.toFixed(2)}`);
              }
            }
          }

          // Epsilon decay
          ns.epsilon = Math.max(0.02, state.epsilon * 0.995);

          addLog(turn, "learn", "◈", `LEARN: drift baseline updated (n=${ns.driftHistory.length}), ε=${ns.epsilon.toFixed(3)}`);
          if (adjustments.length > 0) {
            addLog(turn, "learn", "⚖", `WEIGHTS: ${adjustments.join(", ")}`);
          }

          setDelegationResult({ driftScore, classification, veto, delegation });
        }, 2800);

      }, 2200);
    }

    // ── Finalize state ──
    setTimeout(() => {
      setState({...ns});
      addLog(turn, "info", "·", `── turn ${turn} complete ──`);
    }, shouldDelegate ? 3400 : 1200);

    setHistory(newHistory);
    setInput("");
  };

  const handleSend = () => {
    if (input.trim()) processMessage(input);
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const geo = GEOMETRY[state.position] || GEOMETRY.EXPLORING;
  const activeEntities = Object.entries(state.entities).filter(([, e]) => e.active);
  const avgDrift = state.driftHistory.length > 0
    ? state.driftHistory.reduce((a, b) => a + b, 0) / state.driftHistory.length : 0;

  return (
    <div style={{ background: C.bg, color: C.text, minHeight: "100vh", fontFamily: sans }}>
      {/* Header */}
      <div style={{
        padding: "12px 20px", borderBottom: `1px solid ${C.border}`,
        display: "flex", justifyContent: "space-between", alignItems: "center",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ fontSize: 18, fontWeight: 700, letterSpacing: 2, color: C.purpleLight, fontFamily: mono }}>
            LUNASCRIPT
          </span>
          <span style={{ fontSize: 11, color: C.textDim }}>prototype — cog machine</span>
        </div>
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <span style={{ fontSize: 28, color: C.warm, letterSpacing: 6 }}>{state.glyph}</span>
          <span style={{ fontSize: 11, fontFamily: mono, color: C.textDim }}>v{state.version}</span>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "280px 1fr 260px", height: "calc(100vh - 50px)" }}>
        {/* LEFT PANEL: State */}
        <div style={{ borderRight: `1px solid ${C.border}`, padding: 12, overflowY: "auto", display: "flex", flexDirection: "column", gap: 8 }}>
          <div style={{ fontSize: 10, fontFamily: mono, color: C.textMuted, letterSpacing: 2, paddingBottom: 4 }}>COGNITIVE STATE</div>

          <CogStatus label="MODE" value={state.mode.replace("_", " ")} color={C.purple}
            detail={`confidence: ${(state.modeConfidence * 100).toFixed(0)}%`}
            firing={cogsFiring.mode} />

          <CogStatus label="POSITION" value={state.position} color={geo.color}
            detail={geo.pattern}
            firing={cogsFiring.position} />

          <CogStatus label="GLYPH" value={state.glyph} color={C.warm}
            detail={`v${state.version}`}
            firing={cogsFiring.glyph} />

          <div style={{ fontSize: 10, fontFamily: mono, color: C.textMuted, letterSpacing: 2, paddingTop: 8, paddingBottom: 4 }}>
            TRAIT VECTOR
          </div>
          <div style={{
            background: C.surface, borderRadius: 6, padding: 8,
            border: `1px solid ${cogsFiring.traits ? C.warm : C.border}`,
            transition: "border-color 0.3s",
          }}>
            {Object.entries(state.traits).map(([name, data]) => (
              <TraitMini key={name} name={name} data={data} prevValue={prevTraits[name]} />
            ))}
          </div>

          <div style={{ fontSize: 10, fontFamily: mono, color: C.textMuted, letterSpacing: 2, paddingTop: 8, paddingBottom: 4 }}>
            ACTIVE ENTITIES
          </div>
          <div style={{
            background: C.surface, borderRadius: 6, padding: 8,
            border: `1px solid ${cogsFiring.entities ? C.blue : C.border}`,
            transition: "border-color 0.3s", minHeight: 30,
          }}>
            {activeEntities.length === 0 ? (
              <span style={{ fontSize: 10, color: C.textMuted, fontFamily: mono }}>none detected</span>
            ) : activeEntities.map(([name, e]) => (
              <div key={name} style={{ display: "flex", justifyContent: "space-between", padding: "2px 0" }}>
                <span style={{ fontSize: 11, color: C.text }}>{name}</span>
                <span style={{ fontSize: 10, fontFamily: mono, color: C.purpleLight }}>
                  {e.trust ? `♦${e.trust}` : e.relevance ? `${e.relevance}` : ""}
                </span>
              </div>
            ))}
          </div>

          <div style={{ fontSize: 10, fontFamily: mono, color: C.textMuted, letterSpacing: 2, paddingTop: 8, paddingBottom: 4 }}>
            RESPONSE GEOMETRY
          </div>
          <div style={{ background: C.surface, borderRadius: 6, padding: 8, border: `1px solid ${C.border}`, fontSize: 10, fontFamily: mono }}>
            <div style={{ color: C.textDim }}>max: <span style={{ color: C.text }}>{geo.maxSent} sentences</span></div>
            <div style={{ color: C.textDim }}>questions: <span style={{ color: geo.questionReq ? C.green : C.textMuted }}>{geo.questionReq ? "required" : "optional"}</span></div>
            <div style={{ color: C.textDim }}>tangents: <span style={{ color: geo.tangent ? C.green : C.textMuted }}>{geo.tangent ? "allowed" : "blocked"}</span></div>
            <div style={{ color: C.textDim }}>assert ratio: <span style={{ color: C.text }}>{(geo.assertRatio * 100).toFixed(0)}%</span></div>
            <div style={{ color: C.purpleLight, marginTop: 4, lineHeight: 1.4 }}>{geo.pattern}</div>
          </div>

          <div style={{ fontSize: 10, fontFamily: mono, color: C.textMuted, letterSpacing: 2, paddingTop: 8, paddingBottom: 4 }}>
            DELEGATION STATS
          </div>
          <div style={{ background: C.surface, borderRadius: 6, padding: 8, border: `1px solid ${C.border}`, fontSize: 10, fontFamily: mono }}>
            <div style={{ color: C.textDim }}>delegations: <span style={{ color: C.text }}>{state.delegationCount}</span></div>
            <div style={{ color: C.textDim }}>avg drift: <span style={{ color: avgDrift > 0.15 ? C.red : avgDrift > 0.08 ? C.yellow : C.green }}>{avgDrift.toFixed(3)}</span></div>
            <div style={{ color: C.textDim }}>epsilon: <span style={{ color: C.text }}>{state.epsilon.toFixed(3)}</span></div>
            <div style={{ color: C.textDim }}>turns: <span style={{ color: C.text }}>{state.turnCount}</span></div>
          </div>
        </div>

        {/* CENTER: Log + Input */}
        <div style={{ display: "flex", flexDirection: "column" }}>
          <div ref={logRef} style={{
            flex: 1, overflowY: "auto", padding: "12px 16px",
            background: `${C.bg}`,
          }}>
            {logs.map((log, i) => <LogEntry key={i} entry={log} />)}
          </div>

          <div style={{
            padding: 12, borderTop: `1px solid ${C.border}`,
            display: "flex", gap: 8,
          }}>
            <input
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type a message to Luna and watch the cogs turn..."
              style={{
                flex: 1, padding: "10px 14px", background: C.surface,
                border: `1px solid ${C.border}`, borderRadius: 6,
                color: C.text, fontFamily: sans, fontSize: 13,
                outline: "none",
              }}
              onFocus={e => e.target.style.borderColor = C.purpleLight}
              onBlur={e => e.target.style.borderColor = C.border}
              autoFocus
            />
            <button onClick={handleSend} style={{
              padding: "10px 20px", background: C.purple, border: "none",
              borderRadius: 6, color: "#fff", fontFamily: mono, fontSize: 12,
              cursor: "pointer", letterSpacing: 1,
            }}>
              SEND
            </button>
          </div>
        </div>

        {/* RIGHT PANEL: Delegation detail */}
        <div style={{ borderLeft: `1px solid ${C.border}`, padding: 12, overflowY: "auto" }}>
          <div style={{ fontSize: 10, fontFamily: mono, color: C.textMuted, letterSpacing: 2, paddingBottom: 8 }}>
            LAST DELEGATION
          </div>

          {delegationResult ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <div style={{
                textAlign: "center", padding: 16, background: C.surface, borderRadius: 8,
                border: `1px solid ${delegationResult.classification.color}40`,
              }}>
                <div style={{ fontSize: 28, color: delegationResult.classification.color }}>
                  {delegationResult.classification.icon}
                </div>
                <div style={{ fontSize: 14, fontWeight: 700, color: delegationResult.classification.color, fontFamily: mono }}>
                  {delegationResult.classification.cls}
                </div>
                <div style={{ fontSize: 11, color: C.textDim, marginTop: 4 }}>
                  drift: {delegationResult.driftScore.toFixed(3)}
                </div>
              </div>

              <div style={{ fontSize: 10, fontFamily: mono, color: C.textMuted, letterSpacing: 2, paddingTop: 4 }}>
                VETO RESULT
              </div>
              <div style={{
                padding: 10, background: C.surface, borderRadius: 6,
                border: `1px solid ${delegationResult.veto.passed ? C.green : C.red}40`,
              }}>
                <div style={{
                  fontSize: 12, fontWeight: 600, fontFamily: mono,
                  color: delegationResult.veto.passed ? C.green : C.red,
                }}>
                  {delegationResult.veto.passed ? "PASSED" : "REJECTED"}
                </div>
                {delegationResult.veto.violations.length > 0 && (
                  <div style={{ marginTop: 6 }}>
                    {delegationResult.veto.violations.map(v => (
                      <div key={v} style={{ fontSize: 10, color: C.red, fontFamily: mono, padding: "1px 0" }}>
                        ✗ {v}
                      </div>
                    ))}
                  </div>
                )}
                <div style={{ fontSize: 10, color: C.textDim, marginTop: 4 }}>
                  quality: {(delegationResult.veto.score * 100).toFixed(0)}%
                </div>
              </div>

              <div style={{ fontSize: 10, fontFamily: mono, color: C.textMuted, letterSpacing: 2, paddingTop: 4 }}>
                TRAIT DELTAS
              </div>
              {delegationResult.delegation.driftDetails.map(d => (
                <div key={d.trait} style={{
                  display: "flex", justifyContent: "space-between", padding: "4px 8px",
                  background: C.surface, borderRadius: 4, fontSize: 10, fontFamily: mono,
                  border: `1px solid ${Math.abs(d.delta) > 0.08 ? C.red : C.border}30`,
                }}>
                  <span style={{ color: C.purpleLight }}>{d.trait}</span>
                  <span style={{ color: d.delta > 0 ? C.green : C.red }}>
                    {d.delta > 0 ? "+" : ""}{d.delta.toFixed(3)}
                  </span>
                </div>
              ))}

              <div style={{ fontSize: 10, fontFamily: mono, color: C.textMuted, letterSpacing: 2, paddingTop: 8 }}>
                DRIFT HISTORY
              </div>
              <div style={{ background: C.surface, borderRadius: 6, padding: 8, height: 60, position: "relative", overflow: "hidden" }}>
                <svg viewBox={`0 0 ${Math.max(state.driftHistory.length, 10)} 1`} preserveAspectRatio="none"
                  style={{ width: "100%", height: "100%" }}>
                  {/* Threshold lines */}
                  <line x1="0" y1="0.92" x2={state.driftHistory.length} y2="0.92" stroke={C.green} strokeWidth="0.01" opacity="0.3" />
                  <line x1="0" y1="0.80" x2={state.driftHistory.length} y2="0.80" stroke={C.yellow} strokeWidth="0.01" opacity="0.3" />
                  {/* Drift line */}
                  {state.driftHistory.length > 1 && (
                    <polyline
                      fill="none" stroke={C.warm} strokeWidth="0.02"
                      points={state.driftHistory.map((d, i) => `${i},${1 - d}`).join(" ")}
                    />
                  )}
                  {state.driftHistory.map((d, i) => (
                    <circle key={i} cx={i} cy={1 - d} r="0.03"
                      fill={d > 0.20 ? C.red : d > 0.08 ? C.yellow : C.green} />
                  ))}
                </svg>
              </div>
            </div>
          ) : (
            <div style={{
              textAlign: "center", padding: 20, color: C.textMuted, fontSize: 11, fontFamily: mono,
            }}>
              No delegations yet. Send a few messages — delegation triggers every 3rd turn or on complex messages.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
