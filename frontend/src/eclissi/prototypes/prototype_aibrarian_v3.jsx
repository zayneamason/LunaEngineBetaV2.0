import { useState, useCallback, useMemo, useEffect } from "react";

// ─── TOKENS ───
const T = {
  bg: "#0a0a12", bgRaised: "#0e0e17", bgPanel: "#12121c", bgCard: "#171723",
  bgInput: "#0f0f19", border: "rgba(255,255,255,0.05)", borderHover: "rgba(255,255,255,0.1)",
  text: "#e8e8f0", textSoft: "#9a9ab0", textFaint: "#5a5a70", textMuted: "#3a3a50",
  luna: "#c084fc", memory: "#7dd3fc", voice: "#a78bfa", qa: "#f87171",
  debug: "#fbbf24", prompt: "#34d399", vk: "#fb923c", guardian: "#e09f3e",
  bookmark: "#f59e0b", note: "#a78bfa",
};
const F = "'DM Sans',system-ui,sans-serif";
const M = "'JetBrains Mono','SF Mono',monospace";
const L = "'Bebas Neue',system-ui,sans-serif";

// ─── LOCK-IN ENGINE (mirrors luna/substrate/lock_in.py) ───
const LOCK_IN_WEIGHTS = { retrieval: 0.4, reinforcement: 0.3, network: 0.2, tagSiblings: 0.1 };
const SIGMOID_K = 1.2;
const SIGMOID_X0 = 0.5;
const LOCK_IN_MIN = 0.15;
const LOCK_IN_MAX = 0.85;

function sigmoid(x, k = SIGMOID_K, x0 = SIGMOID_X0) {
  const z = -k * (x - x0);
  if (z > 700) return 0;
  if (z < -700) return 1;
  return 1 / (1 + Math.exp(z));
}

function computeCollectionLockIn({ accessCount = 0, annotationCount = 0, connectedCollections = 0, daysSinceAccess = 0, entityOverlap = 0 }) {
  // Adapted lock-in for collections:
  // retrieval → access count (searches, opens)
  // reinforcement → annotation count (Luna's engagement)
  // network → connected collections (cross-references)
  // tag_siblings → entity overlap with matrix
  const activity = (
    accessCount * LOCK_IN_WEIGHTS.retrieval +
    annotationCount * LOCK_IN_WEIGHTS.reinforcement +
    connectedCollections * LOCK_IN_WEIGHTS.network +
    entityOverlap * LOCK_IN_WEIGHTS.tagSiblings
  ) / 10.0;

  const raw = sigmoid(activity);
  let lockIn = LOCK_IN_MIN + (LOCK_IN_MAX - LOCK_IN_MIN) * raw;

  // Library-adjusted decay: much slower than memory nodes
  // Half-life ~7 days for drifting (vs 17 min for memory nodes)
  // Books get dusty, they don't vanish
  const LIBRARY_DECAY = {
    settled: 0.0000005,    // ~16 days half-life
    fluid: 0.000005,       // ~1.6 days half-life
    drifting: 0.00005,     // ~3.8 hours half-life
  };

  const state = lockIn >= 0.70 ? "settled" : lockIn >= 0.30 ? "fluid" : "drifting";
  const lambda = LIBRARY_DECAY[state] || 0.00005;
  const secondsSinceAccess = daysSinceAccess * 86400;
  lockIn *= Math.exp(-lambda * secondsSinceAccess);

  return Math.max(0.05, Math.min(1.0, lockIn));
}

function classifyState(lockIn) {
  if (lockIn >= 0.70) return "settled";
  if (lockIn >= 0.30) return "fluid";
  return "drifting";
}

const STATE_COLORS = { settled: T.prompt, fluid: T.memory, drifting: T.qa };
const STATE_ICONS = { settled: "◆", fluid: "◇", drifting: "○" };

// ─── MOCK DATA: 15 COLLECTIONS ───
const RAW_COLLECTIONS = [
  { id: "dataroom", label: "Project Eclipse Data Room", tags: ["investor","eclipse","dataroom"], color: T.prompt,
    stats: { documents: 18, chunks: 27, words: 8635, entities: 12 },
    access: { count: 47, annotations: 8, connections: 3, daysSince: 0.2, entityOverlap: 12 },
    docs: [
      { title: "LOI — Continental Council", type: "pdf" }, { title: "Financial Projections Y1", type: "xlsx" },
      { title: "Tapestry Strategic Plan", type: "pdf" }, { title: "Luna Proposal v3", type: "pdf" },
      { title: "Africa LOI", type: "pdf" }, { title: "Hai Dai LOI", type: "pdf" },
    ],
    annotations: [
      { type: "bookmark", text: "LOI signing timeline — critical for ROSA" },
      { type: "note", text: "Cross-ref Kinoni budget with Rotary grant" },
      { type: "bookmark", text: "Tarcila's grant narrative structure" },
    ],
  },
  { id: "luna_architecture", label: "Luna Engine Architecture Docs", tags: ["technical","luna","architecture"], color: T.luna,
    stats: { documents: 34, chunks: 156, words: 42000, entities: 28 },
    access: { count: 62, annotations: 12, connections: 4, daysSince: 0.1, entityOverlap: 28 },
    docs: [
      { title: "Memory Matrix Spec v4", type: "md" }, { title: "Expression Pipeline Design", type: "md" },
      { title: "Shared Turn Cache Handoff", type: "md" }, { title: "Scribe Actor Protocol", type: "py" },
    ],
    annotations: [
      { type: "note", text: "Lock-in formula needs library-adjusted decay" },
      { type: "bookmark", text: "ScribeActor write pattern — atomic YAML" },
      { type: "flag", text: "Expression pipeline integration pending" },
    ],
  },
  { id: "kinoni_deployment", label: "Kinoni ICT Hub Planning", tags: ["kinoni","uganda","deployment"], color: T.guardian,
    stats: { documents: 12, chunks: 48, words: 15200, entities: 18 },
    access: { count: 23, annotations: 5, connections: 2, daysSince: 1.5, entityOverlap: 8 },
    docs: [
      { title: "Rotary Grant Application", type: "pdf" }, { title: "Hub Infrastructure Plan", type: "pdf" },
      { title: "Community Needs Assessment", type: "pdf" },
    ],
    annotations: [
      { type: "bookmark", text: "Solar power requirements for offline operation" },
      { type: "note", text: "Luganda language model — check Crane AI Labs" },
    ],
  },
  { id: "maxwell_case", label: "Maxwell Case Documents", tags: ["legal","investigation","maxwell"], color: T.qa,
    stats: { documents: 900, chunks: 4200, words: 1200000, entities: 342 },
    access: { count: 15, annotations: 3, connections: 1, daysSince: 14, entityOverlap: 3 },
    docs: [
      { title: "Bates 001-100 (OCR)", type: "pdf" }, { title: "Deposition Transcripts", type: "pdf" },
    ],
    annotations: [
      { type: "flag", text: "3 entities overlap with Thiel collection" },
    ],
  },
  { id: "thiel_investigation", label: "Thiel Investigation", tags: ["investigation","thiel","palantir"], color: T.vk,
    stats: { documents: 47, chunks: 180, words: 52000, entities: 89 },
    access: { count: 8, annotations: 1, connections: 1, daysSince: 21, entityOverlap: 3 },
    docs: [
      { title: "Entity Network Map", type: "json" }, { title: "Palantir Connection Graph", type: "pdf" },
    ],
    annotations: [{ type: "note", text: "Cross-ref entity overlap with Maxwell" }],
  },
  { id: "rosa_conference", label: "ROSA Energy Conference Prep", tags: ["rosa","conference","demo"], color: "#e879f9",
    stats: { documents: 8, chunks: 32, words: 9800, entities: 6 },
    access: { count: 38, annotations: 6, connections: 3, daysSince: 0.5, entityOverlap: 6 },
    docs: [
      { title: "Virtual Track Agenda", type: "pdf" }, { title: "Guardian Demo Script", type: "md" },
      { title: "EarthScale Partnership Brief", type: "pdf" },
    ],
    annotations: [
      { type: "bookmark", text: "Demo sequence: identity → memory → sovereignty" },
      { type: "note", text: "Calvin reviewing investor pitch angle" },
    ],
  },
  { id: "guardian_specs", label: "Guardian Interface Specs", tags: ["guardian","ui","community"], color: T.guardian,
    stats: { documents: 15, chunks: 67, words: 19500, entities: 9 },
    access: { count: 29, annotations: 4, connections: 2, daysSince: 2, entityOverlap: 9 },
    docs: [
      { title: "Guardian Architecture Map", type: "html" }, { title: "Membrane Flow Design", type: "html" },
    ],
    annotations: [
      { type: "bookmark", text: "Consent framework — Baganda clan governance model" },
    ],
  },
  { id: "kozmo_creative", label: "Kozmo Creative Studio", tags: ["kozmo","creative","screenwriting"], color: "#38bdf8",
    stats: { documents: 22, chunks: 89, words: 31000, entities: 15 },
    access: { count: 18, annotations: 2, connections: 1, daysSince: 5, entityOverlap: 5 },
    docs: [
      { title: "KozmoScribo Editor Spec", type: "md" }, { title: "Entity Pipeline Design", type: "md" },
    ],
    annotations: [{ type: "note", text: "Bidirectional knowledge graph for screenplay entities" }],
  },
  { id: "sovereignty_research", label: "Sovereignty & Indigenous AI Research", tags: ["sovereignty","research","indigenous"], color: "#a3e635",
    stats: { documents: 41, chunks: 210, words: 78000, entities: 45 },
    access: { count: 12, annotations: 3, connections: 2, daysSince: 8, entityOverlap: 15 },
    docs: [
      { title: "Te Hiku Media — Papa Reo Analysis", type: "pdf" },
      { title: "NAGPRA Compliance Framework", type: "pdf" },
      { title: "Cross-Cultural Foundation Uganda", type: "pdf" },
    ],
    annotations: [
      { type: "bookmark", text: "Papa Reo governance model — Luna parallel" },
    ],
  },
  { id: "bombay_biennale", label: "Bombay Beach Biennale 2026", tags: ["art","installation","robot"], color: "#fb7185",
    stats: { documents: 6, chunks: 18, words: 5200, entities: 4 },
    access: { count: 7, annotations: 1, connections: 1, daysSince: 12, entityOverlap: 2 },
    docs: [
      { title: "Installation Concept — Sovereign Witness", type: "pdf" },
      { title: "Grant Proposal Draft", type: "docx" },
    ],
    annotations: [{ type: "note", text: "Raccoon on rocket platform — glowing" }],
  },
  { id: "funding_research", label: "Funding & Grant Research", tags: ["funding","grants","strategy"], color: T.debug,
    stats: { documents: 28, chunks: 112, words: 36000, entities: 22 },
    access: { count: 31, annotations: 7, connections: 3, daysSince: 1, entityOverlap: 10 },
    docs: [
      { title: "Rotary Foundation Global Grants", type: "pdf" },
      { title: "Aligned Funder Analysis", type: "xlsx" },
      { title: "Y1 Budget $70-125K Breakdown", type: "xlsx" },
    ],
    annotations: [
      { type: "bookmark", text: "$70-125K Year 1 target confirmed" },
      { type: "note", text: "EarthScale Ventures — platform + ROSA access" },
    ],
  },
  { id: "eden_integration", label: "Eden.art Integration", tags: ["eden","generative","api"], color: "#818cf8",
    stats: { documents: 5, chunks: 15, words: 4100, entities: 3 },
    access: { count: 9, annotations: 1, connections: 1, daysSince: 6, entityOverlap: 2 },
    docs: [
      { title: "Eden API Reference", type: "md" }, { title: "Agent Chat Protocol", type: "json" },
    ],
    annotations: [],
  },
  { id: "legal_incorporation", label: "Legal & Incorporation", tags: ["legal","business","incorporation"], color: "#94a3b8",
    stats: { documents: 9, chunks: 34, words: 11200, entities: 7 },
    access: { count: 6, annotations: 0, connections: 1, daysSince: 18, entityOverlap: 4 },
    docs: [
      { title: "Cliff Strategy Notes", type: "pdf" }, { title: "Entity Structure Options", type: "docx" },
    ],
    annotations: [],
  },
  { id: "voice_pipeline", label: "Voice & Expression Pipeline", tags: ["voice","stt","tts","expression"], color: T.voice,
    stats: { documents: 11, chunks: 45, words: 14800, entities: 5 },
    access: { count: 20, annotations: 3, connections: 2, daysSince: 3, entityOverlap: 5 },
    docs: [
      { title: "7-Layer Flow Awareness Spec", type: "md" },
      { title: "Emotional Tone Derivation", type: "py" },
    ],
    annotations: [{ type: "bookmark", text: "Voice blend → expression hint mapping" }],
  },
  { id: "continental_council", label: "Continental Council Archive", tags: ["council","indigenous","governance"], color: "#2dd4bf",
    stats: { documents: 16, chunks: 64, words: 21000, entities: 19 },
    access: { count: 14, annotations: 2, connections: 2, daysSince: 7, entityOverlap: 11 },
    docs: [
      { title: "Philosophical Governance Framework", type: "pdf" },
      { title: "Three-Continent Partnership Map", type: "pdf" },
    ],
    annotations: [{ type: "note", text: "Jero Wiku alignment compass — decision framework" }],
  },
];

const MATRIX_STATS = {
  nodes: 24478, edges: 23912, entities: 79, sizeMb: 124.2,
  lockIn: { drifting: 3204, fluid: 21074, settled: 200 },
};

// ─── SMALL COMPONENTS ───
function Pill({ label, value, color, small }) {
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 3,
      padding: small ? "1px 4px" : "2px 6px", borderRadius: 3,
      background: `${color || T.luna}08`, border: `1px solid ${color || T.luna}12`,
      fontSize: small ? 8 : 9, fontFamily: M, whiteSpace: "nowrap",
    }}>
      <span style={{ color: T.textFaint, fontSize: small ? 6 : 7 }}>{label}</span>
      <span style={{ color: color || T.text, fontWeight: 500 }}>
        {typeof value === "number" ? value.toLocaleString() : value}
      </span>
    </span>
  );
}

function LockInMeter({ value, width = 60, height = 4 }) {
  const state = classifyState(value);
  const color = STATE_COLORS[state];
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <div style={{ width, height, borderRadius: height / 2, background: `${T.textMuted}15`, overflow: "hidden" }}>
        <div style={{
          width: `${value * 100}%`, height: "100%", borderRadius: height / 2,
          background: color, opacity: 0.7, transition: "width 0.6s ease",
        }} />
      </div>
      <span style={{ fontSize: 8, fontFamily: M, color, minWidth: 28 }}>
        {(value * 100).toFixed(0)}%
      </span>
    </div>
  );
}

// ─── COLLECTION ROW (COMPACT) ───
function CompactRow({ col, lockIn, state, onExpand, onIngest, onToggle }) {
  const stateColor = STATE_COLORS[state];
  const opacity = state === "drifting" ? 0.45 : state === "fluid" ? 0.75 : 1;

  return (
    <div
      onClick={() => onExpand(col.id)}
      style={{
        display: "grid",
        gridTemplateColumns: "24px 1fr 200px 120px 80px 100px",
        alignItems: "center",
        padding: "8px 14px",
        background: T.bgPanel,
        borderRadius: 8,
        border: `1px solid ${T.border}`,
        cursor: "pointer",
        opacity,
        transition: "all 0.3s",
        gap: 8,
      }}
      onMouseOver={e => { e.currentTarget.style.borderColor = `${col.color}25`; e.currentTarget.style.opacity = Math.max(opacity, 0.8); }}
      onMouseOut={e => { e.currentTarget.style.borderColor = T.border; e.currentTarget.style.opacity = opacity; }}
    >
      {/* State indicator */}
      <div style={{ textAlign: "center" }}>
        <span style={{ color: stateColor, fontSize: 10 }}>{STATE_ICONS[state]}</span>
      </div>

      {/* Name + tags */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, overflow: "hidden" }}>
        <div style={{ width: 3, height: 12, borderRadius: 1, background: col.color, flexShrink: 0, opacity: state === "drifting" ? 0.3 : 0.8 }} />
        <span style={{ fontSize: 11, fontFamily: F, color: state === "drifting" ? T.textFaint : T.textSoft, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
          {col.label}
        </span>
        {col.annotations.length > 0 && (
          <span style={{ fontSize: 8, color: T.debug, flexShrink: 0 }}>📌{col.annotations.length}</span>
        )}
      </div>

      {/* Stats */}
      <div style={{ display: "flex", gap: 4 }}>
        <Pill label="D" value={col.stats.documents} color={col.color} small />
        <Pill label="E" value={col.stats.entities} color={T.memory} small />
        <Pill label="W" value={col.stats.words > 999 ? `${(col.stats.words / 1000).toFixed(0)}k` : col.stats.words} color={T.textFaint} small />
      </div>

      {/* Lock-in meter */}
      <LockInMeter value={lockIn} />

      {/* State label */}
      <div style={{
        fontSize: 7, fontFamily: L, letterSpacing: 1.5, color: stateColor,
        textAlign: "center",
      }}>
        {state.toUpperCase()}
      </div>

      {/* Actions */}
      <div style={{ display: "flex", gap: 4, justifyContent: "flex-end" }} onClick={e => e.stopPropagation()}>
        <div onClick={() => onIngest(col)} style={{
          padding: "2px 8px", borderRadius: 3, cursor: "pointer",
          border: `1px solid ${col.color}30`, background: `${col.color}08`,
          fontSize: 8, fontFamily: M, color: col.color,
        }}>+INGEST</div>
        <div onClick={() => onToggle(col.id)} style={{
          padding: "2px 6px", borderRadius: 3, cursor: "pointer",
          border: `1px solid ${T.border}`, fontSize: 8, fontFamily: M, color: T.textMuted,
        }}>{col._shelved ? "WAKE" : "SHELVE"}</div>
      </div>
    </div>
  );
}

// ─── COLLECTION ROW (EXPANDED) ───
function ExpandedRow({ col, lockIn, state, onCollapse, onIngest }) {
  const stateColor = STATE_COLORS[state];
  const iconMap = { bookmark: "🔖", note: "📝", flag: "🚩" };

  return (
    <div style={{
      background: T.bgPanel, borderRadius: 10, overflow: "hidden",
      border: `1px solid ${col.color}20`,
      boxShadow: `0 4px 20px ${col.color}06`,
    }}>
      {/* Header */}
      <div style={{
        display: "flex", alignItems: "center", padding: "10px 14px", gap: 10,
        borderBottom: `1px solid ${T.border}`, background: `${col.color}04`,
      }}>
        <span style={{ color: stateColor, fontSize: 11 }}>{STATE_ICONS[state]}</span>
        <div style={{ width: 3, height: 16, borderRadius: 2, background: col.color }} />
        <div style={{ flex: 1 }}>
          <div style={{ fontFamily: L, fontSize: 11, letterSpacing: 1.5, color: col.color }}>{col.id.toUpperCase().replace(/_/g, " ")}</div>
          <div style={{ fontSize: 9, color: T.textFaint, fontFamily: F }}>{col.label}</div>
        </div>
        <LockInMeter value={lockIn} width={80} />
        <span style={{ fontSize: 8, fontFamily: L, letterSpacing: 1.5, color: stateColor }}>{state.toUpperCase()}</span>
        <div onClick={() => onIngest(col)} style={{
          padding: "4px 10px", borderRadius: 4, cursor: "pointer",
          border: `1px solid ${col.color}40`, background: `${col.color}12`,
          fontSize: 9, fontFamily: M, color: col.color,
        }}>+ INGEST</div>
        <div onClick={() => onCollapse(col.id)} style={{
          padding: "4px 6px", borderRadius: 4, cursor: "pointer",
          border: `1px solid ${T.border}`, fontSize: 10, color: T.textFaint,
        }}>▾</div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 240px", borderTop: `1px solid ${T.border}` }}>
        {/* Stats + Tags */}
        <div style={{ padding: "10px 14px", borderRight: `1px solid ${T.border}` }}>
          <div style={{ fontSize: 7, fontFamily: L, letterSpacing: 1.5, color: T.textMuted, marginBottom: 8 }}>STATS & TAGS</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginBottom: 8 }}>
            <Pill label="DOCS" value={col.stats.documents} color={col.color} />
            <Pill label="CHUNKS" value={col.stats.chunks} color={T.textSoft} />
            <Pill label="WORDS" value={col.stats.words} color={T.textSoft} />
            <Pill label="ENTITIES" value={col.stats.entities} color={T.memory} />
          </div>
          <div style={{ display: "flex", gap: 3, flexWrap: "wrap" }}>
            {col.tags.map(t => (
              <span key={t} style={{
                padding: "1px 5px", borderRadius: 2, fontSize: 7, fontFamily: M,
                color: T.textMuted, background: `${T.textMuted}10`,
              }}>{t}</span>
            ))}
          </div>

          {/* Lock-in breakdown */}
          <div style={{ marginTop: 10 }}>
            <div style={{ fontSize: 7, fontFamily: L, letterSpacing: 1.5, color: T.textMuted, marginBottom: 4 }}>LOCK-IN FACTORS</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 3, fontSize: 8, fontFamily: M, color: T.textFaint }}>
              <span>Access: {col.access.count}</span>
              <span>Annotations: {col.access.annotations}</span>
              <span>Connections: {col.access.connections}</span>
              <span>Entity overlap: {col.access.entityOverlap}</span>
              <span>Days since: {col.access.daysSince}</span>
            </div>
          </div>
        </div>

        {/* Documents */}
        <div style={{ padding: "10px 14px", borderRight: `1px solid ${T.border}` }}>
          <div style={{ fontSize: 7, fontFamily: L, letterSpacing: 1.5, color: T.textMuted, marginBottom: 8 }}>DOCUMENTS</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
            {col.docs.map((doc, i) => (
              <div key={i} style={{
                padding: "5px 8px", borderRadius: 4, background: T.bgCard,
                border: `1px solid ${T.border}`, display: "flex", alignItems: "center", gap: 6,
                fontSize: 10, color: T.textSoft, fontFamily: F, cursor: "pointer",
              }}
                onMouseOver={e => e.currentTarget.style.borderColor = T.borderHover}
                onMouseOut={e => e.currentTarget.style.borderColor = T.border}
              >
                <span style={{ fontSize: 9 }}>
                  {doc.type === "pdf" ? "📄" : doc.type === "xlsx" ? "📊" : doc.type === "json" ? "🔗" : doc.type === "md" ? "📝" : doc.type === "py" ? "🐍" : "📁"}
                </span>
                <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{doc.title}</span>
                <div style={{ width: 4, height: 4, borderRadius: "50%", background: T.prompt }} />
              </div>
            ))}
          </div>
        </div>

        {/* Annotations */}
        <div style={{ padding: "10px 12px" }}>
          <div style={{ fontSize: 7, fontFamily: L, letterSpacing: 1.5, color: T.textMuted, marginBottom: 8 }}>LUNA'S ANNOTATIONS</div>
          {col.annotations.length === 0 ? (
            <div style={{ fontSize: 9, color: T.textMuted, fontFamily: F, fontStyle: "italic", padding: "8px 0" }}>
              No annotations yet — Luna hasn't marked anything here.
            </div>
          ) : (
            col.annotations.map((ann, i) => (
              <div key={i} style={{
                padding: "5px 8px", marginBottom: 3, borderRadius: 4,
                background: T.bgCard, borderLeft: `2px solid ${ann.type === "bookmark" ? T.bookmark : ann.type === "note" ? T.note : T.qa}`,
                fontSize: 9, color: T.textSoft, fontFamily: F,
              }}>
                {iconMap[ann.type] || "📌"} {ann.text}
              </div>
            ))
          )}
          <div style={{
            padding: "4px 8px", borderRadius: 4, border: `1px dashed ${T.textMuted}20`,
            textAlign: "center", fontSize: 8, color: T.textMuted, cursor: "pointer",
            fontFamily: F, marginTop: 4,
          }}
            onMouseOver={e => { e.currentTarget.style.borderColor = `${T.debug}40`; e.currentTarget.style.color = T.debug; }}
            onMouseOut={e => { e.currentTarget.style.borderColor = `${T.textMuted}20`; e.currentTarget.style.color = T.textMuted; }}
          >+ annotate</div>
        </div>
      </div>
    </div>
  );
}

// ─── INGEST MODAL ───
function IngestModal({ collection, onClose, onIngest }) {
  const [mode, setMode] = useState("directory");
  const [path, setPath] = useState("");
  const [recursive, setRecursive] = useState(true);

  return (
    <div style={{
      position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)", backdropFilter: "blur(4px)",
      display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000,
    }} onClick={onClose}>
      <div style={{
        width: 420, background: T.bgPanel, borderRadius: 14,
        border: `1px solid ${collection.color}30`, overflow: "hidden",
        boxShadow: `0 20px 60px rgba(0,0,0,0.6)`,
      }} onClick={e => e.stopPropagation()}>
        <div style={{
          padding: "14px 18px", borderBottom: `1px solid ${T.border}`,
          display: "flex", alignItems: "center", gap: 8,
        }}>
          <div style={{ width: 3, height: 16, borderRadius: 2, background: collection.color }} />
          <span style={{ fontFamily: L, fontSize: 11, letterSpacing: 2, color: collection.color }}>
            INGEST → {collection.id.toUpperCase()}
          </span>
          <div style={{ flex: 1 }} />
          <div onClick={onClose} style={{ cursor: "pointer", color: T.textFaint, fontSize: 13 }}>✕</div>
        </div>
        <div style={{ padding: 18, display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ display: "flex", gap: 4 }}>
            {["directory", "file", "url"].map(m => (
              <div key={m} onClick={() => setMode(m)} style={{
                padding: "4px 10px", borderRadius: 5, cursor: "pointer",
                background: mode === m ? `${collection.color}15` : "transparent",
                border: `1px solid ${mode === m ? `${collection.color}40` : T.border}`,
                fontSize: 9, fontFamily: M, color: mode === m ? collection.color : T.textFaint,
                textTransform: "uppercase",
              }}>{m}</div>
            ))}
          </div>
          <input value={path} onChange={e => setPath(e.target.value)}
            placeholder={mode === "directory" ? "/path/to/documents" : mode === "file" ? "/path/to/file.pdf" : "https://..."}
            style={{
              width: "100%", padding: "8px 12px", borderRadius: 6, boxSizing: "border-box",
              background: T.bgInput, border: `1px solid ${T.border}`,
              color: T.text, fontSize: 11, fontFamily: M, outline: "none",
            }}
          />
          {mode === "directory" && (
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <div onClick={() => setRecursive(!recursive)} style={{
                width: 28, height: 14, borderRadius: 7, cursor: "pointer",
                background: recursive ? `${T.prompt}40` : `${T.textMuted}30`,
                border: `1px solid ${recursive ? T.prompt : T.border}`,
                position: "relative",
              }}>
                <div style={{
                  width: 8, height: 8, borderRadius: "50%",
                  background: recursive ? T.prompt : T.textFaint,
                  position: "absolute", top: 2, left: recursive ? 16 : 2,
                  transition: "all 0.2s",
                }} />
              </div>
              <span style={{ fontSize: 9, color: T.textSoft }}>Recursive</span>
            </div>
          )}
          <div onClick={() => { onIngest(collection.id, mode, path); onClose(); }} style={{
            padding: "9px 0", borderRadius: 6, textAlign: "center", cursor: "pointer",
            background: `${collection.color}20`, border: `1px solid ${collection.color}40`,
            fontSize: 10, fontFamily: L, letterSpacing: 2, color: collection.color,
          }}>▶ BEGIN INGEST</div>
        </div>
      </div>
    </div>
  );
}

// ─── NEW COLLECTION MODAL ───
function NewCollectionModal({ onClose, onCreate }) {
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [tags, setTags] = useState("");
  return (
    <div style={{
      position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)", backdropFilter: "blur(4px)",
      display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000,
    }} onClick={onClose}>
      <div style={{
        width: 400, background: T.bgPanel, borderRadius: 14,
        border: `1px solid ${T.luna}30`, overflow: "hidden",
        boxShadow: `0 20px 60px rgba(0,0,0,0.6)`,
      }} onClick={e => e.stopPropagation()}>
        <div style={{
          padding: "14px 18px", borderBottom: `1px solid ${T.border}`,
          display: "flex", alignItems: "center", gap: 8,
        }}>
          <div style={{ width: 3, height: 16, borderRadius: 2, background: T.luna }} />
          <span style={{ fontFamily: L, fontSize: 11, letterSpacing: 2, color: T.luna }}>NEW COLLECTION</span>
          <div style={{ flex: 1 }} />
          <div onClick={onClose} style={{ cursor: "pointer", color: T.textFaint }}>✕</div>
        </div>
        <div style={{ padding: 18, display: "flex", flexDirection: "column", gap: 12 }}>
          {[
            { label: "ID", val: name, set: v => setName(v.toLowerCase().replace(/\s/g,"_")), ph: "collection_id", mono: true },
            { label: "DESCRIPTION", val: desc, set: setDesc, ph: "What is this collection for?", mono: false },
            { label: "TAGS", val: tags, set: setTags, ph: "tag1, tag2, tag3", mono: true },
          ].map(f => (
            <div key={f.label}>
              <div style={{ fontSize: 7, fontFamily: L, letterSpacing: 1.5, color: T.textMuted, marginBottom: 4 }}>{f.label}</div>
              <input value={f.val} onChange={e => f.set(e.target.value)} placeholder={f.ph} style={{
                width: "100%", padding: "7px 10px", borderRadius: 6, boxSizing: "border-box",
                background: T.bgInput, border: `1px solid ${T.border}`,
                color: T.text, fontSize: 11, fontFamily: f.mono ? M : F, outline: "none",
              }} />
            </div>
          ))}
          <div onClick={() => { if (name) { onCreate(name, desc, tags); onClose(); }}} style={{
            padding: "9px 0", borderRadius: 6, textAlign: "center", cursor: name ? "pointer" : "default",
            background: name ? `${T.luna}20` : `${T.textMuted}08`,
            border: `1px solid ${name ? `${T.luna}40` : T.border}`,
            fontSize: 10, fontFamily: L, letterSpacing: 2, color: name ? T.luna : T.textMuted,
          }}>CREATE</div>
        </div>
      </div>
    </div>
  );
}

// ─── MAIN ───
export default function AibrarianLibrary() {
  const [collections, setCollections] = useState(RAW_COLLECTIONS);
  const [expandedId, setExpandedId] = useState(null);
  const [ingestTarget, setIngestTarget] = useState(null);
  const [showNew, setShowNew] = useState(false);
  const [filter, setFilter] = useState("all"); // all, settled, fluid, drifting
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("lock_in"); // lock_in, name, docs, recent

  // Compute lock-in for each collection
  const enriched = useMemo(() => {
    return collections.map(col => {
      const lockIn = computeCollectionLockIn({
        accessCount: col.access.count,
        annotationCount: col.access.annotations,
        connectedCollections: col.access.connections,
        daysSinceAccess: col._shelved ? col.access.daysSince + 30 : col.access.daysSince,
        entityOverlap: col.access.entityOverlap,
      });
      const state = classifyState(lockIn);
      return { ...col, lockIn, state };
    });
  }, [collections]);

  // Filter + sort
  const displayed = useMemo(() => {
    let list = enriched;
    if (filter !== "all") list = list.filter(c => c.state === filter);
    if (search) list = list.filter(c =>
      c.label.toLowerCase().includes(search.toLowerCase()) ||
      c.id.toLowerCase().includes(search.toLowerCase()) ||
      c.tags.some(t => t.toLowerCase().includes(search.toLowerCase()))
    );
    list = [...list].sort((a, b) => {
      if (sortBy === "lock_in") return b.lockIn - a.lockIn;
      if (sortBy === "name") return a.label.localeCompare(b.label);
      if (sortBy === "docs") return b.stats.documents - a.stats.documents;
      if (sortBy === "recent") return a.access.daysSince - b.access.daysSince;
      return 0;
    });
    return list;
  }, [enriched, filter, search, sortBy]);

  const stateGroups = useMemo(() => ({
    settled: enriched.filter(c => c.state === "settled").length,
    fluid: enriched.filter(c => c.state === "fluid").length,
    drifting: enriched.filter(c => c.state === "drifting").length,
  }), [enriched]);

  const toggleShelve = useCallback((id) => {
    setCollections(prev => prev.map(c => c.id === id ? { ...c, _shelved: !c._shelved } : c));
  }, []);

  const handleNew = useCallback((name, desc, tags) => {
    const colors = [T.luna, T.memory, T.voice, T.prompt, T.vk, T.guardian, T.debug, "#e879f9", "#38bdf8"];
    setCollections(prev => [...prev, {
      id: name, label: desc || name, tags: tags ? tags.split(",").map(t => t.trim()).filter(Boolean) : [],
      color: colors[prev.length % colors.length],
      stats: { documents: 0, chunks: 0, words: 0, entities: 0 },
      access: { count: 0, annotations: 0, connections: 0, daysSince: 0, entityOverlap: 0 },
      docs: [], annotations: [],
    }]);
  }, []);

  const totalDocs = enriched.reduce((s, c) => s + c.stats.documents, 0);
  const totalAnnotations = enriched.reduce((s, c) => s + c.annotations.length, 0);
  const avgLockIn = enriched.length > 0 ? enriched.reduce((s, c) => s + c.lockIn, 0) / enriched.length : 0;

  return (
    <div style={{ width: "100%", height: "100vh", background: T.bg, fontFamily: F, color: T.text, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <style>{`
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
        ::-webkit-scrollbar{width:4px} ::-webkit-scrollbar-thumb{background:rgba(255,255,255,0.06);border-radius:2px} ::-webkit-scrollbar-track{background:transparent}
      `}</style>

      {/* ═══ HEADER ═══ */}
      <div style={{
        height: 44, background: T.bgRaised, borderBottom: `1px solid ${T.border}`,
        display: "flex", alignItems: "center", padding: "0 16px", gap: 10, flexShrink: 0,
      }}>
        <div style={{ width: 3, height: 20, borderRadius: 2, background: T.voice, boxShadow: `0 0 8px ${T.voice}50` }} />
        <span style={{ fontFamily: L, fontSize: 11, letterSpacing: 2.5, color: T.voice }}>LUNAR STUDIO</span>
        <div style={{ width: 1, height: 14, background: T.border }} />
        <span style={{ fontFamily: L, fontSize: 10, letterSpacing: 2, color: T.textFaint }}>AIBRARIAN</span>
        <div style={{ flex: 1 }} />
        <div onClick={() => setShowNew(true)} style={{
          padding: "4px 12px", borderRadius: 5, cursor: "pointer",
          border: `1px solid ${T.prompt}40`, background: `${T.prompt}10`,
          fontSize: 9, fontFamily: L, letterSpacing: 1.5, color: T.prompt,
        }}>+ NEW COLLECTION</div>
      </div>

      {/* ═══ QUERY LAYER (pinned) ═══ */}
      <div style={{ padding: "10px 16px", borderBottom: `1px solid ${T.border}`, background: `${T.luna}02`, flexShrink: 0 }}>
        <div style={{ display: "flex", gap: 6, alignItems: "center", padding: "7px 12px", background: T.bgPanel, borderRadius: 8, border: `1px solid ${T.border}` }}>
          <span style={{ fontSize: 12, opacity: 0.3 }}>⟐</span>
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search collections, tags, documents..."
            style={{ flex: 1, background: "transparent", border: "none", outline: "none", color: T.text, fontSize: 11, fontFamily: F }} />
          <div style={{ display: "flex", gap: 3 }}>
            {["all", "settled", "fluid", "drifting"].map(f => (
              <div key={f} onClick={() => setFilter(f)} style={{
                padding: "2px 8px", borderRadius: 3, cursor: "pointer",
                background: filter === f ? `${STATE_COLORS[f] || T.luna}15` : "transparent",
                border: `1px solid ${filter === f ? `${STATE_COLORS[f] || T.luna}30` : "transparent"}`,
                fontSize: 8, fontFamily: M, color: filter === f ? (STATE_COLORS[f] || T.luna) : T.textMuted,
                textTransform: "uppercase",
              }}>
                {f === "all" ? `ALL ${enriched.length}` : `${f} ${stateGroups[f]}`}
              </div>
            ))}
          </div>
          <div style={{ width: 1, height: 14, background: T.border }} />
          <select value={sortBy} onChange={e => setSortBy(e.target.value)} style={{
            background: T.bgCard, border: `1px solid ${T.border}`, borderRadius: 3,
            color: T.textSoft, fontSize: 8, fontFamily: M, padding: "2px 4px", outline: "none",
          }}>
            <option value="lock_in">SORT: LOCK-IN</option>
            <option value="recent">SORT: RECENT</option>
            <option value="docs">SORT: DOCS</option>
            <option value="name">SORT: NAME</option>
          </select>
        </div>
      </div>

      {/* ═══ COLLECTION LIST (scrollable) ═══ */}
      <div style={{ flex: 1, overflow: "auto" }}>
        {/* Column headers */}
        <div style={{
          display: "grid", gridTemplateColumns: "24px 1fr 200px 120px 80px 100px",
          padding: "6px 14px 4px 30px", gap: 8,
          fontSize: 7, fontFamily: L, letterSpacing: 1.5, color: T.textMuted,
          borderBottom: `1px solid ${T.border}`, background: T.bgRaised,
          position: "sticky", top: 0, zIndex: 2,
        }}>
          <span></span>
          <span>COLLECTION</span>
          <span>STATS</span>
          <span>LOCK-IN</span>
          <span style={{ textAlign: "center" }}>STATE</span>
          <span style={{ textAlign: "right" }}>ACTIONS</span>
        </div>

        <div style={{ padding: "8px 16px", display: "flex", flexDirection: "column", gap: 4 }}>
          {displayed.map(col => (
            expandedId === col.id ? (
              <ExpandedRow
                key={col.id} col={col} lockIn={col.lockIn} state={col.state}
                onCollapse={() => setExpandedId(null)} onIngest={setIngestTarget}
              />
            ) : (
              <CompactRow
                key={col.id} col={col} lockIn={col.lockIn} state={col.state}
                onExpand={setExpandedId} onIngest={setIngestTarget} onToggle={toggleShelve}
              />
            )
          ))}
        </div>

        {/* ═══ SECURITY LAYER ═══ */}
        <div style={{ padding: "12px 16px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
            <div style={{ fontSize: 7, fontFamily: L, letterSpacing: 2, color: T.guardian, opacity: 0.5 }}>ISOLATION LAYER</div>
            <div style={{ flex: 1, height: 1, background: `${T.guardian}10` }} />
          </div>
          <div style={{
            background: T.bgPanel, borderRadius: 8, border: `1px solid ${T.guardian}12`,
            padding: "8px 14px", display: "flex", gap: 12, alignItems: "center", fontSize: 9,
          }}>
            <span style={{ color: T.textFaint, fontFamily: F, flex: 1 }}>
              Collections are sandboxed. Luna reads but doesn't merge into Matrix unless she annotates. All provenance tracked.
            </span>
            {["READ-ONLY DEFAULT", "PROVENANCE TRACKED", "ANNOTATION = BRIDGE"].map(label => (
              <span key={label} style={{
                padding: "2px 8px", borderRadius: 3, fontSize: 7, fontFamily: M,
                background: `${T.guardian}08`, border: `1px solid ${T.guardian}15`, color: T.guardian,
              }}>{label}</span>
            ))}
          </div>
        </div>

        {/* ═══ MEMORY MATRIX FOUNDATION ═══ */}
        <div style={{ padding: "4px 16px 20px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
            <div style={{ fontSize: 7, fontFamily: L, letterSpacing: 2, color: T.luna, opacity: 0.5 }}>MEMORY MATRIX · FOUNDATION</div>
            <div style={{ flex: 1, height: 1, background: `${T.luna}10` }} />
          </div>
          <div style={{
            background: T.bgPanel, borderRadius: 10, border: `1px solid ${T.luna}15`,
            overflow: "hidden", boxShadow: `0 0 20px ${T.luna}04`,
          }}>
            <div style={{
              padding: "10px 14px", display: "flex", alignItems: "center", gap: 8,
              borderBottom: `1px solid ${T.border}`, background: `${T.luna}03`,
            }}>
              <div style={{ width: 3, height: 14, borderRadius: 2, background: T.luna, boxShadow: `0 0 6px ${T.luna}60` }} />
              <span style={{ fontFamily: L, fontSize: 10, letterSpacing: 2, color: T.luna }}>MEMORY MATRIX</span>
              <div style={{ flex: 1 }} />
              <div style={{ width: 5, height: 5, borderRadius: "50%", background: T.prompt, boxShadow: `0 0 4px ${T.prompt}80` }} />
              <span style={{ fontSize: 7, fontFamily: M, color: T.prompt }}>ACTIVE</span>
            </div>
            <div style={{ padding: "10px 14px", display: "grid", gridTemplateColumns: "auto 1fr 1fr", gap: 16, alignItems: "center" }}>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                <Pill label="NODES" value={MATRIX_STATS.nodes} color={T.luna} />
                <Pill label="EDGES" value={MATRIX_STATS.edges} color={T.voice} />
                <Pill label="ENTITIES" value={MATRIX_STATS.entities} color={T.memory} />
                <Pill label="SIZE" value={`${MATRIX_STATS.sizeMb}MB`} color={T.textSoft} />
              </div>

              {/* Lock-in distribution */}
              <div>
                <div style={{ display: "flex", height: 5, borderRadius: 3, overflow: "hidden", background: `${T.textMuted}12`, marginBottom: 4 }}>
                  <div style={{ width: `${(MATRIX_STATS.lockIn.drifting / MATRIX_STATS.nodes) * 100}%`, background: T.qa, opacity: 0.4 }} />
                  <div style={{ width: `${(MATRIX_STATS.lockIn.fluid / MATRIX_STATS.nodes) * 100}%`, background: T.memory, opacity: 0.35 }} />
                  <div style={{ width: `${(MATRIX_STATS.lockIn.settled / MATRIX_STATS.nodes) * 100}%`, background: T.prompt, opacity: 0.5 }} />
                </div>
                <div style={{ display: "flex", gap: 8, fontSize: 7, fontFamily: M, color: T.textFaint }}>
                  <span><span style={{ color: T.qa }}>●</span> {MATRIX_STATS.lockIn.drifting.toLocaleString()}</span>
                  <span><span style={{ color: T.memory }}>●</span> {MATRIX_STATS.lockIn.fluid.toLocaleString()}</span>
                  <span><span style={{ color: T.prompt }}>●</span> {MATRIX_STATS.lockIn.settled.toLocaleString()}</span>
                </div>
              </div>

              {/* Bridged */}
              <div>
                <div style={{ fontSize: 7, fontFamily: L, letterSpacing: 1, color: T.textMuted, marginBottom: 4 }}>BRIDGED COLLECTIONS</div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 3 }}>
                  {enriched.filter(c => c.annotations.length > 0).slice(0, 6).map(c => (
                    <span key={c.id} style={{
                      padding: "1px 5px", borderRadius: 2, fontSize: 7, fontFamily: M,
                      background: `${c.color}10`, border: `1px solid ${c.color}15`, color: c.color,
                    }}>{c.id} ·{c.annotations.length}</span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ═══ STATUS BAR ═══ */}
      <div style={{
        height: 26, background: T.bgRaised, borderTop: `1px solid ${T.border}`,
        display: "flex", alignItems: "center", padding: "0 16px", gap: 16,
        fontSize: 8, fontFamily: M, color: T.textFaint, flexShrink: 0,
      }}>
        <span><span style={{ color: T.prompt }}>◆</span> {stateGroups.settled} settled</span>
        <span><span style={{ color: T.memory }}>◇</span> {stateGroups.fluid} fluid</span>
        <span><span style={{ color: T.qa }}>○</span> {stateGroups.drifting} drifting</span>
        <span>·</span>
        <span>{totalDocs} docs</span>
        <span>📌 {totalAnnotations}</span>
        <span>avg lock-in: {(avgLockIn * 100).toFixed(0)}%</span>
        <div style={{ flex: 1 }} />
        <span style={{ color: T.voice }}>LUNAR STUDIO · AIBRARIAN</span>
      </div>

      {/* MODALS */}
      {ingestTarget && <IngestModal collection={ingestTarget} onClose={() => setIngestTarget(null)} onIngest={(id, m, p) => console.log("Ingest:", id, m, p)} />}
      {showNew && <NewCollectionModal onClose={() => setShowNew(false)} onCreate={handleNew} />}
    </div>
  );
}
