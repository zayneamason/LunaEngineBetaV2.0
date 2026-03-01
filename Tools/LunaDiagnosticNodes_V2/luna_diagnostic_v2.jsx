import { useState, useRef, useEffect, useCallback } from "react";
import * as d3 from "d3";

// ═══════════════════════════════════════════════════════
// NODE DATA
// ═══════════════════════════════════════════════════════
const typeColors = {
  input:   { accent: "#06b6d4", bg: "#0d1a24", border: "#164050" },
  process: { accent: "#818cf8", bg: "#111024", border: "#2a2860" },
  memory:  { accent: "#4ade80", bg: "#0d1f0d", border: "#1a4020" },
  broken:  { accent: "#f87171", bg: "#1f0d0d", border: "#6b2020" },
  output:  { accent: "#fbbf24", bg: "#1a160d", border: "#504020" },
  guard:   { accent: "#c084fc", bg: "#160d24", border: "#3a2060" },
  context: { accent: "#f472b6", bg: "#1f0d1a", border: "#502040" },
};

const statusMeta = {
  live:   { color: "#22c55e", label: "LIVE" },
  broken: { color: "#ef4444", label: "BROKEN" },
  warn:   { color: "#f59e0b", label: "WARN" },
  idle:   { color: "#666680", label: "IDLE" },
};

const mkNode = (id, x, y, type, icon, label, body, status, desc, file, tags) => ({
  id, x, y, type, icon, label, body, status, desc, file, tags: tags || [status],
});

const initNodes = [
  mkNode("voice",0,0,"input","🎤","Voice STT","MLX Whisper\nTranscript → Engine","live","Speech-to-text via MLX Whisper. Produces TRANSCRIPT_FINAL events that enter InputBuffer.","src/voice/"),
  mkNode("text",0,150,"input","⌨️","Text /message","REST POST\n→ InputBuffer","live","REST API endpoint. Wraps text in InputEvent(TEXT_INPUT) and pushes to InputBuffer.","src/luna/api/server.py"),
  mkNode("stream",0,300,"input","🌊","/persona/stream","SSE path\nBypasses buffer","warn","Streaming endpoint bypasses InputBuffer — calls PersonaAdapter directly → Director. Separate retrieval pipeline.","src/luna/api/server.py",["warn:separate_path"]),
  mkNode("identity",0,450,"input","👤","Identity FaceID","Ahab → admin\nConfidence: 1.0","live","FaceID recognition. Currently sees Ahab with admin tier at full confidence.","src/luna/actors/identity.py"),
  mkNode("buffer",270,75,"process","📥","Input Buffer","Priority queue\nPolled each tick","live","InputBuffer holds events ordered by priority. Cognitive loop polls every 500ms.","src/luna/core/input_buffer.py"),
  mkNode("tick",500,75,"process","💓","Cognitive Tick","500ms heartbeat\nPoll→Dispatch→State","live","Every 500ms: poll InputBuffer → dispatch events → consciousness tick → history tick → rebalance rings.","src/luna/engine.py:643"),
  mkNode("dispatch",500,240,"process","🔀","Event Dispatch","Route by event type\n→ _handle_user_msg","live","Routes events by type. TEXT_INPUT → _handle_user_message(). Spawns async task.","src/luna/engine.py:688"),
  mkNode("subtasks",270,400,"process","⚡","Subtask Runner","Qwen 3B local\nIntent·Entity·Rewrite","live","Phase 1: 3 lightweight local inference tasks in parallel. Intent classification, entity extraction, query rewriting.","src/luna/inference/subtasks.py"),
  mkNode("router",500,400,"process","🧭","Query Router","DIRECT vs PLANNED\nComplexity score","live","Simple → DIRECT (skip planning). Complex → PLANNED (AgentLoop). Uses subtask intent or regex fallback.","src/luna/agentic/router.py"),
  mkNode("mem_ret",760,230,"broken","🧠","Memory Retrieval","matrix.get_context()\nRETURNS EMPTY ⚠️\n24,318 nodes unreachable","broken","PRIMARY FAILURE.\n\nengine.py:825 → matrix.get_context(query, max_tokens=1500, scopes=active_scopes)\n\nMatrix has 24,318 nodes. Direct API queries work. But get_context() returns empty.\n\nif memory_context: at line 828 → False → nothing added to MEMORY ring.\n\nEvidence: /debug/context shows 0 items in MIDDLE and OUTER rings.","src/luna/engine.py:825",["broken"]),
  mkNode("matrix_actor",1010,300,"broken","🔮","Matrix Actor","get_context() → ???\nScope: global\nmax_tokens: 1500","broken","Wraps MemoryMatrix. get_context() should: search → activate → assemble → format.\n\nReturns empty. Possible causes:\n• Scope filtering too aggressive\n• get_context() ≠ search() method\n• Vector embeddings missing\n• FTS5 parse failure for short queries","src/luna/actors/matrix.py",["broken"]),
  mkNode("matrix_db",1010,120,"memory","💾","Memory Matrix DB","24,318 nodes · 23,839 edges\n20,256 FACTs · 700 ENTITYs\nFTS5 + SQLite ✅","live","Database is healthy. Direct API queries return correct results for Ahab, Kozmo, Marzipan, etc. Data is THERE.","data/memory_matrix.db"),
  mkNode("dataroom",1010,480,"memory","📁","Dataroom Search","SQL: WHERE DOCUMENT\nKeyword match ✅\nBypasses get_context()","live","WORKS because it uses direct SQL (WHERE node_type=DOCUMENT) — not get_context(). Luna correctly retrieved docs.","src/luna/engine.py"),
  mkNode("hist_load",760,450,"process","📜","History Loader","SQL: conversation turns\nLoads INNER ring only","warn","Loads CONVERSATION turns (not FACTs/ENTITYs). Luna sees her own responses but NOT the knowledge graph.","src/luna/engine.py",["warn"]),
  mkNode("hist_mgr",500,570,"process","🗂️","History Manager","Tiered compression\nRecent→Summary→Archive","live","Manages conversation history across three tiers. Ticked every cognitive cycle.","src/luna/actors/history_manager.py"),
  mkNode("context",760,620,"context","🎯","Revolving Context","Budget: 8000 tok\nUsed: 2087 (26%)\nCORE:1 INNER:7\nMIDDLE:0 ⚠️ OUTER:0 ⚠️","warn","4 concentric rings:\n\nCORE (1 item, 139 tok): Identity — never evicted\nINNER (7, 1948 tok): Conversation turns\nMIDDLE (0, 0 tok): ← SHOULD HAVE MEMORY\nOUTER (0, 0 tok): ← SHOULD HAVE OVERFLOW\n\n74% budget UNUSED.","src/luna/core/context.py",["broken:MIDDLE_empty","broken:OUTER_empty"]),
  mkNode("ring_core",540,780,"context","◉","CORE Ring","1 item · 139 tok\nIdentity prompt","live","Immutable identity. TTL=-1 permanent.","src/luna/core/context.py"),
  mkNode("ring_inner",700,780,"context","◎","INNER Ring","7 items · 1948 tok\nConversation only","live","All 7 items are Luna's previous responses. No knowledge graph content.","src/luna/core/context.py"),
  mkNode("ring_mid",860,780,"broken","○","MIDDLE Ring","0 items · 0 tok\nMEMORY HERE ⚠️","broken","EMPTY. Should contain memory search results. Nothing enters upstream.","src/luna/core/context.py",["broken"]),
  mkNode("ring_outer",1020,780,"broken","◌","OUTER Ring","0 items · 0 tok\nDecayed overflow ⚠️","broken","EMPTY. Nothing to decay or evict.","src/luna/core/context.py",["broken"]),
  mkNode("sysprompt",1010,620,"process","📝","System Prompt","_build_system_prompt()\nIdentity+History\nMemory: EMPTY ⚠️","warn","Assembles prompt from components. Since memory_context is empty, the 'Relevant Memory Context' section never appears in the prompt.","src/luna/engine.py",["warn:no_memory"]),
  mkNode("director",1260,460,"process","🎬","Director","Claude Sonnet\nLLM generation\nNo memory in prompt ⚠️","live","Generates correctly but has NO MEMORY in its prompt. Only sees conversation + identity. Confabulates or surrenders.","src/luna/actors/director.py",["live","warn:blind"]),
  mkNode("agent_loop",1260,300,"process","🔄","Agent Loop","Multi-step planning\nMax 50 iterations","live","For PLANNED queries. Plan → Execute → Review. Routes to Director.","src/luna/agentic/loop.py"),
  mkNode("scout",1490,300,"guard","🔭","Scout","Quality guard\nSurrender·Shallow·Deflect\nConfab: planned","live","Post-generation quality gate. Detects surrender, shallow recall, deflection. Triggers Overdrive retry.","src/luna/actors/scout.py"),
  mkNode("overdrive",1490,460,"guard","⚡","Overdrive","Retry enriched ctx\nAlso hits broken retrieval\nRetries futile ⚠️","warn","Retries use get_context() too — also returns empty. Futile until upstream fixed.","src/luna/actors/scout.py",["warn:futile"]),
  mkNode("watchdog",1490,620,"guard","🐕","Watchdog","5s interval\nStuck detection","live","Background loop. If stuck >30s, forces reset.","src/luna/actors/scout.py"),
  mkNode("reconcile",1260,620,"guard","🔧","Reconcile","Self-correction\nNot yet wired","idle","ReconcileManager initialized but not functional. Needs confab detection + working retrieval.","src/luna/actors/reconcile.py",["idle"]),
  mkNode("tts",1700,360,"output","🔊","TTS Output","Piper TTS\nText→Speech","live","Text-to-speech via Piper.","src/voice/tts/"),
  mkNode("textout",1700,520,"output","💬","Text Response","REST + SSE\nContext updated","live","Response via REST or SSE. Context updated, turn recorded.","src/luna/api/server.py"),
  mkNode("scribe",270,720,"memory","✍️","Scribe","Extract FACT/ENTITY\nUser turns only","live","Extracts knowledge from user turns. V2 will add CORRECTION type.","src/luna/actors/scribe.py"),
  mkNode("librarian",270,870,"memory","📚","Librarian","Dedup + file\nExtracted→Matrix","live","Files extracted objects into Matrix. Dedup, entity resolution, edges.","src/luna/actors/librarian.py"),
  mkNode("consciousness",0,580,"process","🌀","Consciousness","Emotion · Attention\nEnergy state","live","Tracks internal state. Ticked every cognitive cycle.","src/luna/consciousness.py"),
  mkNode("persona",270,240,"process","🎭","Persona Adapter","/persona/stream path\nSeparate retrieval ⚠️","warn","Voice/streaming has its OWN context building. Second potential failure point.","src/voice/persona_adapter.py",["warn:separate_pipeline"]),
];

const mkEdge = (from, to, label, broken) => ({ from, to, label: label || "", broken: !!broken });

const initEdges = [
  mkEdge("voice","buffer","TRANSCRIPT"),
  mkEdge("text","buffer","TEXT_INPUT"),
  mkEdge("stream","persona","SSE direct"),
  mkEdge("persona","director","generate"),
  mkEdge("buffer","tick","poll_all()"),
  mkEdge("tick","dispatch","events"),
  mkEdge("dispatch","subtasks","_handle_msg"),
  mkEdge("subtasks","router","intent+ents"),
  mkEdge("router","agent_loop","PLANNED"),
  mkEdge("router","director","DIRECT"),
  mkEdge("agent_loop","director","generate"),
  mkEdge("dispatch","mem_ret","_retrieve_ctx()"),
  mkEdge("mem_ret","matrix_actor","get_context()",true),
  mkEdge("matrix_actor","matrix_db","FTS5+vectors"),
  mkEdge("mem_ret","context","EMPTY→no add()",true),
  mkEdge("dispatch","dataroom","dataroom_ctx()"),
  mkEdge("dataroom","matrix_db","SQL direct ✅"),
  mkEdge("dataroom","context","add(MEM) ✅"),
  mkEdge("dispatch","hist_load","load_history()"),
  mkEdge("hist_load","matrix_db","SQL: conv turns"),
  mkEdge("hist_load","context","add(CONV)"),
  mkEdge("hist_mgr","context","history_ctx"),
  mkEdge("context","sysprompt","get_window()"),
  mkEdge("sysprompt","director","sys_prompt"),
  mkEdge("context","ring_core",""),
  mkEdge("context","ring_inner",""),
  mkEdge("context","ring_mid","",true),
  mkEdge("context","ring_outer","",true),
  mkEdge("director","scout","draft"),
  mkEdge("scout","overdrive","flag→retry"),
  mkEdge("overdrive","director","re-gen"),
  mkEdge("scout","tts","approved"),
  mkEdge("scout","textout","approved"),
  mkEdge("scout","reconcile","confab flag"),
  mkEdge("textout","scribe","record turn"),
  mkEdge("scribe","librarian","extracted"),
  mkEdge("librarian","matrix_db","file nodes"),
  mkEdge("identity","sysprompt","identity ctx"),
  mkEdge("consciousness","sysprompt","state hints"),
  mkEdge("tick","consciousness","tick()"),
  mkEdge("tick","hist_mgr","tick()"),
];

// ═══════════════════════════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════════════════════════
export default function App() {
  const svgRef = useRef(null);
  const gRef = useRef(null);
  const [nodes, setNodes] = useState(initNodes);
  const [selected, setSelected] = useState(null);
  const [transform, setTransform] = useState({ x: 30, y: 20, k: 0.52 });
  const dragState = useRef({ active: false, nodeId: null, offsetX: 0, offsetY: 0 });
  const W = 190, H_BASE = 70;

  const getNodeHeight = (n) => {
    const lines = n.body.split("\n").length;
    return H_BASE + lines * 14;
  };

  const getCenter = useCallback((n) => {
    return { x: n.x + W / 2, y: n.y + getNodeHeight(n) / 2 };
  }, []);

  // Zoom
  useEffect(() => {
    if (!svgRef.current) return;
    const svg = d3.select(svgRef.current);
    const zoom = d3.zoom()
      .scaleExtent([0.15, 3])
      .on("zoom", (e) => {
        setTransform({ x: e.transform.x, y: e.transform.y, k: e.transform.k });
      });
    svg.call(zoom);
    svg.call(zoom.transform, d3.zoomIdentity.translate(30, 20).scale(0.52));
    return () => svg.on(".zoom", null);
  }, []);

  // Node drag
  const onPointerDown = useCallback((e, nodeId) => {
    e.stopPropagation();
    const node = nodes.find(n => n.id === nodeId);
    if (!node) return;
    const svgPt = svgRef.current.getBoundingClientRect();
    const mx = (e.clientX - svgPt.left - transform.x) / transform.k;
    const my = (e.clientY - svgPt.top - transform.y) / transform.k;
    dragState.current = { active: true, nodeId, offsetX: mx - node.x, offsetY: my - node.y };
    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
  }, [nodes, transform]);

  const onPointerMove = useCallback((e) => {
    if (!dragState.current.active) return;
    const svgPt = svgRef.current.getBoundingClientRect();
    const mx = (e.clientX - svgPt.left - transform.x) / transform.k;
    const my = (e.clientY - svgPt.top - transform.y) / transform.k;
    const nx = Math.round((mx - dragState.current.offsetX) / 10) * 10;
    const ny = Math.round((my - dragState.current.offsetY) / 10) * 10;
    setNodes(prev => prev.map(n => n.id === dragState.current.nodeId ? { ...n, x: nx, y: ny } : n));
  }, [transform]);

  const onPointerUp = useCallback(() => {
    dragState.current.active = false;
    window.removeEventListener("pointermove", onPointerMove);
    window.removeEventListener("pointerup", onPointerUp);
  }, [onPointerMove]);

  // Render edges as curved paths
  const renderEdges = () => {
    return initEdges.map((e, i) => {
      const fromN = nodes.find(n => n.id === e.from);
      const toN = nodes.find(n => n.id === e.to);
      if (!fromN || !toN) return null;
      const f = getCenter(fromN);
      const t = getCenter(toN);
      const dx = t.x - f.x;
      const dy = t.y - f.y;
      const cx1 = f.x + dx * 0.4;
      const cy1 = f.y;
      const cx2 = t.x - dx * 0.4;
      const cy2 = t.y;
      const path = `M${f.x},${f.y} C${cx1},${cy1} ${cx2},${cy2} ${t.x},${t.y}`;
      const color = e.broken ? "rgba(239,68,68,0.55)" : "rgba(129,140,248,0.2)";
      const lx = (f.x + t.x) / 2;
      const ly = (f.y + t.y) / 2;
      return (
        <g key={`edge-${i}`}>
          <path d={path} fill="none" stroke={color} strokeWidth={e.broken ? 2 : 1.2}
            strokeDasharray={e.broken ? "5 5" : "none"} />
          {/* Animated dot */}
          <circle r={e.broken ? 3 : 2} fill={e.broken ? "#ef4444" : "#818cf8"} opacity={0.7}>
            <animateMotion dur={e.broken ? "1.5s" : "2.5s"} repeatCount="indefinite" path={path} />
          </circle>
          {/* Arrow */}
          <circle cx={t.x} cy={t.y} r={3} fill={e.broken ? "#ef4444" : "rgba(129,140,248,0.4)"} />
          {/* Label */}
          {e.label && (
            <g transform={`translate(${lx},${ly})`}>
              <rect x={-e.label.length * 3.2 - 4} y={-8} width={e.label.length * 6.4 + 8} height={14}
                rx={3} fill="#0a0a12" opacity={0.9} />
              <text textAnchor="middle" dy={3} fill={e.broken ? "#f87171" : "#555568"}
                fontSize={9} fontFamily="'JetBrains Mono',monospace">{e.label}</text>
            </g>
          )}
        </g>
      );
    });
  };

  // Render nodes
  const renderNodes = () => {
    return nodes.map(n => {
      const tc = typeColors[n.type] || typeColors.process;
      const sc = statusMeta[n.status] || statusMeta.idle;
      const nh = getNodeHeight(n);
      const isSel = selected?.id === n.id;
      const isBroken = n.status === "broken";
      return (
        <g key={n.id} transform={`translate(${n.x},${n.y})`}
          onPointerDown={(e) => onPointerDown(e, n.id)}
          onClick={(e) => { e.stopPropagation(); setSelected(n); }}
          style={{ cursor: "grab" }}>
          {/* Glow for broken */}
          {isBroken && <rect x={-4} y={-4} width={W + 8} height={nh + 8} rx={14}
            fill="none" stroke="rgba(239,68,68,0.2)" strokeWidth={2}>
            <animate attributeName="stroke-opacity" values="0.15;0.4;0.15" dur="2s" repeatCount="indefinite" />
          </rect>}
          {/* Selection ring */}
          {isSel && <rect x={-3} y={-3} width={W + 6} height={nh + 6} rx={13}
            fill="none" stroke={tc.accent} strokeWidth={1.5} opacity={0.6} />}
          {/* Body */}
          <rect width={W} height={nh} rx={10} fill={tc.bg}
            stroke={isBroken ? "rgba(239,68,68,0.5)" : isSel ? tc.accent : tc.border}
            strokeWidth={isBroken ? 1.5 : 1} />
          {/* Header row */}
          <circle cx={14} cy={16} r={3.5} fill={sc.color}>
            {n.status === "live" && <animate attributeName="opacity" values="1;0.4;1" dur="2.5s" repeatCount="indefinite" />}
            {n.status === "broken" && <animate attributeName="opacity" values="1;0.3;1" dur="1s" repeatCount="indefinite" />}
          </circle>
          <text x={24} y={12} fontSize={14}>{n.icon}</text>
          <text x={42} y={19} fill={tc.accent} fontSize={10} fontWeight={600}
            fontFamily="'JetBrains Mono',monospace" letterSpacing={0.3}>{n.label}</text>
          {/* Body text */}
          {n.body.split("\n").map((line, li) => (
            <text key={li} x={12} y={38 + li * 14} fill="#667" fontSize={9.5}
              fontFamily="'JetBrains Mono',monospace">{line}</text>
          ))}
          {/* Connection handles */}
          <circle cx={0} cy={nh / 2} r={4} fill={tc.bg} stroke={tc.accent} strokeWidth={1} opacity={0.5} />
          <circle cx={W} cy={nh / 2} r={4} fill={tc.bg} stroke={tc.accent} strokeWidth={1} opacity={0.5} />
        </g>
      );
    });
  };

  return (
    <div style={{ width: "100vw", height: "100vh", background: "#08080f", fontFamily: "'JetBrains Mono',monospace", overflow: "hidden", position: "relative" }}>
      <style>{`@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700&display=swap');`}</style>

      {/* HUD */}
      <div style={{ position: "absolute", top: 12, left: 12, zIndex: 10, pointerEvents: "none" }}>
        <div style={{ fontSize: 14, fontWeight: 700, color: "#e0e0f0", letterSpacing: 0.5 }}>◈ LUNA ENGINE — PIPELINE DIAGNOSTIC</div>
        <div style={{ fontSize: 9, color: "#555568", marginTop: 3 }}>Drag nodes · Click for detail · Scroll to zoom · Pan background</div>
        <div style={{ display: "flex", gap: 12, marginTop: 8, flexWrap: "wrap" }}>
          {Object.entries(typeColors).map(([k, v]) => (
            <div key={k} style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 9, color: "#555568" }}>
              <div style={{ width: 7, height: 7, borderRadius: 2, background: v.accent }} />
              {k.toUpperCase()}
            </div>
          ))}
        </div>
      </div>

      {/* SVG Canvas */}
      <svg ref={svgRef} width="100%" height="100%" style={{ display: "block" }}
        onClick={() => setSelected(null)}>
        <g ref={gRef} transform={`translate(${transform.x},${transform.y}) scale(${transform.k})`}>
          {renderEdges()}
          {renderNodes()}
        </g>
      </svg>

      {/* Detail Panel */}
      {selected && (
        <div style={{
          position: "absolute", right: 0, top: 0, width: 360, height: "100vh",
          background: "#0c0c16", borderLeft: "1px solid rgba(255,255,255,0.06)",
          zIndex: 20, overflowY: "auto", padding: "18px 16px",
          boxShadow: "-6px 0 24px rgba(0,0,0,0.5)",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
            <span style={{ fontSize: 20 }}>{selected.icon}</span>
            <span style={{ fontSize: 12, fontWeight: 600, color: typeColors[selected.type]?.accent, textTransform: "uppercase" }}>{selected.label}</span>
            <span onClick={() => setSelected(null)} style={{ marginLeft: "auto", cursor: "pointer", color: "#555", fontSize: 16 }}>✕</span>
          </div>

          {/* Status tags */}
          <div style={panelSection}>
            <div style={panelTitle}>Status</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
              {selected.tags.map((t, i) => {
                const c = t.includes("live") ? "#22c55e" : t.includes("broken") ? "#ef4444" : t.includes("warn") ? "#f59e0b" : "#818cf8";
                return <span key={i} style={{ fontSize: 9, padding: "2px 8px", borderRadius: 4, background: `${c}18`, color: c, border: `1px solid ${c}33` }}>{t}</span>;
              })}
            </div>
          </div>

          {/* Description */}
          <div style={panelSection}>
            <div style={panelTitle}>Description</div>
            <pre style={{ fontSize: 10, color: "#999", lineHeight: 1.6, whiteSpace: "pre-wrap", wordBreak: "break-word", margin: 0 }}>{selected.desc}</pre>
          </div>

          {/* Source */}
          <div style={panelSection}>
            <div style={panelTitle}>Source File</div>
            <pre style={{ fontSize: 10, color: "#818cf8", margin: 0 }}>{selected.file}</pre>
          </div>

          {/* Connections */}
          <div style={panelSection}>
            <div style={panelTitle}>Connections</div>
            {initEdges.filter(e => e.from === selected.id || e.to === selected.id).map((e, i) => {
              const dir = e.from === selected.id ? "→" : "←";
              const otherId = e.from === selected.id ? e.to : e.from;
              const other = nodes.find(n => n.id === otherId);
              return (
                <div key={i} style={{ fontSize: 10, color: e.broken ? "#f87171" : "#666", marginBottom: 3, cursor: "pointer" }}
                  onClick={() => { const o = nodes.find(n => n.id === otherId); if (o) setSelected(o); }}>
                  {dir} {other?.label || otherId}{e.label ? `: ${e.label}` : ""}{e.broken ? " ⚠️" : ""}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

const panelSection = { marginBottom: 12, padding: "10px 12px", background: "rgba(255,255,255,0.02)", borderRadius: 8, border: "1px solid rgba(255,255,255,0.04)" };
const panelTitle = { fontSize: 9, fontWeight: 500, color: "#555568", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 6 };
