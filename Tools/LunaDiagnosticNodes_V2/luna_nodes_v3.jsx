import { useState, useRef, useCallback } from "react";

const TC = {
  input:   { a: "#06b6d4", bg: "#0d1a24", b: "#164050" },
  process: { a: "#818cf8", bg: "#111024", b: "#2a2860" },
  memory:  { a: "#4ade80", bg: "#0d1f0d", b: "#1a4020" },
  broken:  { a: "#f87171", bg: "#1f0d0d", b: "#6b2020" },
  output:  { a: "#fbbf24", bg: "#1a160d", b: "#504020" },
  guard:   { a: "#c084fc", bg: "#160d24", b: "#3a2060" },
  context: { a: "#f472b6", bg: "#1f0d1a", b: "#502040" },
};
const SC = { live:"#22c55e", broken:"#ef4444", warn:"#f59e0b", idle:"#666" };

const N = (id,x,y,t,ic,l,body,s,desc,file) => ({id,x,y,t,ic,l,body,s,desc,file});

const INIT_NODES = [
  N("voice",20,20,"input","🎤","Voice STT","MLX Whisper","live","Speech-to-text via MLX Whisper.","src/voice/"),
  N("text",20,140,"input","⌨️","Text /message","REST → Buffer","live","REST endpoint wraps text in InputEvent.","src/luna/api/server.py"),
  N("stream",20,260,"input","🌊","/persona/stream","SSE bypass","warn","Bypasses InputBuffer → PersonaAdapter.","src/luna/api/server.py"),
  N("identity",20,380,"input","👤","Identity FaceID","Ahab → admin","live","FaceID. Currently sees Ahab.","src/luna/actors/identity.py"),
  N("buffer",250,80,"process","📥","Input Buffer","Priority queue","live","Events ordered by priority, polled 500ms.","src/luna/core/input_buffer.py"),
  N("tick",450,80,"process","💓","Cognitive Tick","500ms heartbeat","live","Poll → dispatch → state → rebalance.","src/luna/engine.py:643"),
  N("dispatch",450,220,"process","🔀","Event Dispatch","Route events","live","TEXT_INPUT → _handle_user_message.","src/luna/engine.py:688"),
  N("subtasks",250,360,"process","⚡","Subtask Runner","Qwen 3B local","live","Intent · Entity · Rewrite (parallel).","src/luna/inference/subtasks.py"),
  N("router",450,360,"process","🧭","Query Router","DIRECT vs PLANNED","live","Simple → Director. Complex → AgentLoop.","src/luna/agentic/router.py"),
  N("mem_ret",680,200,"broken","🧠","Memory Retrieval","RETURNS EMPTY ⚠️\n24,318 unreachable","broken","PRIMARY FAILURE. get_context() returns empty despite 24,318 nodes in DB.","src/luna/engine.py:825"),
  N("matrix_actor",900,280,"broken","🔮","Matrix Actor","get_context() → ???","broken","Wraps MemoryMatrix. Should search→activate→assemble. Returns empty.","src/luna/actors/matrix.py"),
  N("matrix_db",900,120,"memory","💾","Matrix DB","24,318 nodes ✅\n23,839 edges","live","Database healthy. Direct API works. Data is THERE.","data/memory_matrix.db"),
  N("dataroom",900,440,"memory","📁","Dataroom","SQL bypass ✅","live","Direct SQL works — bypasses get_context().","src/luna/engine.py"),
  N("hist_load",680,400,"process","📜","History Loader","Conv turns only","warn","Loads CONVERSATION not FACTs.","src/luna/engine.py"),
  N("hist_mgr",450,500,"process","🗂️","History Mgr","Tiered compress","live","Recent → Summary → Archive.","src/luna/actors/history_manager.py"),
  N("context",680,560,"context","🎯","Revolving Ctx","8000 tok budget\n26% used\nMID:0 OUT:0 ⚠️","warn","CORE:1 INNER:7 MIDDLE:0 OUTER:0. 74% unused.","src/luna/core/context.py"),
  N("ring_core",500,720,"context","◉","CORE","1·139tok","live","Identity. Permanent.","src/luna/core/context.py"),
  N("ring_inner",640,720,"context","◎","INNER","7·1948tok","live","Conversation only.","src/luna/core/context.py"),
  N("ring_mid",780,720,"broken","○","MIDDLE","0·0tok ⚠️","broken","EMPTY. Memory should go here.","src/luna/core/context.py"),
  N("ring_outer",920,720,"broken","◌","OUTER","0·0tok ⚠️","broken","EMPTY. Nothing to evict.","src/luna/core/context.py"),
  N("sysprompt",900,560,"process","📝","System Prompt","Memory: EMPTY ⚠️","warn","Assembles prompt. No memory section.","src/luna/engine.py"),
  N("director",1120,420,"process","🎬","Director","Claude Sonnet\nBlind ⚠️","live","Generates but has NO memory context.","src/luna/actors/director.py"),
  N("agent_loop",1120,280,"process","🔄","Agent Loop","Plan→Execute","live","Multi-step for PLANNED queries.","src/luna/agentic/loop.py"),
  N("scout",1320,280,"guard","🔭","Scout","Quality guard","live","Surrender·Shallow·Deflect detection.","src/luna/actors/scout.py"),
  N("overdrive",1320,420,"guard","⚡","Overdrive","Retry (futile ⚠️)","warn","Also uses broken get_context().","src/luna/actors/scout.py"),
  N("watchdog",1320,560,"guard","🐕","Watchdog","5s stuck detect","live","Auto-recovery if stuck >30s.","src/luna/actors/scout.py"),
  N("reconcile",1120,560,"guard","🔧","Reconcile","Not wired","idle","Needs confab + retrieval to work.","src/luna/actors/reconcile.py"),
  N("tts",1520,340,"output","🔊","TTS","Piper","live","Text-to-speech.","src/voice/tts/"),
  N("textout",1520,480,"output","💬","Text Out","REST + SSE","live","Response delivered.","src/luna/api/server.py"),
  N("scribe",250,640,"memory","✍️","Scribe","Extract FACT","live","Extracts from user turns.","src/luna/actors/scribe.py"),
  N("librarian",250,780,"memory","📚","Librarian","Dedup+file","live","Files into Matrix.","src/luna/actors/librarian.py"),
  N("consciousness",20,500,"process","🌀","Consciousness","Emotion·Energy","live","Internal state tracking.","src/luna/consciousness.py"),
  N("persona",250,220,"process","🎭","Persona Adapter","Separate path ⚠️","warn","Own retrieval pipeline.","src/voice/persona_adapter.py"),
];

const EDGES = [
  ["voice","buffer"],["text","buffer"],["stream","persona"],["persona","director"],
  ["buffer","tick"],["tick","dispatch"],["dispatch","subtasks"],["subtasks","router"],
  ["router","agent_loop"],["router","director"],["agent_loop","director"],
  ["dispatch","mem_ret"],["mem_ret","matrix_actor",1],["matrix_actor","matrix_db"],
  ["mem_ret","context",1],["dispatch","dataroom"],["dataroom","matrix_db"],
  ["dataroom","context"],["dispatch","hist_load"],["hist_load","matrix_db"],
  ["hist_load","context"],["hist_mgr","context"],["context","sysprompt"],
  ["sysprompt","director"],["context","ring_core"],["context","ring_inner"],
  ["context","ring_mid",1],["context","ring_outer",1],
  ["director","scout"],["scout","overdrive"],["overdrive","director"],
  ["scout","tts"],["scout","textout"],["scout","reconcile"],
  ["textout","scribe"],["scribe","librarian"],["librarian","matrix_db"],
  ["identity","sysprompt"],["consciousness","sysprompt"],
  ["tick","consciousness"],["tick","hist_mgr"],
];

const W = 160, H = 70;

function getH(n) { return H + (n.body.split("\n").length - 1) * 14; }
function cx(n) { return n.x + W/2; }
function cy(n) { return n.y + getH(n)/2; }

export default function App() {
  const [nodes, setNodes] = useState(INIT_NODES);
  const [sel, setSel] = useState(null);
  const [pan, setPan] = useState({x:0,y:0});
  const [zoom, setZoom] = useState(0.55);
  const dragRef = useRef(null);
  const panRef = useRef(null);
  const containerRef = useRef(null);

  const toWorld = useCallback((clientX, clientY) => {
    const r = containerRef.current?.getBoundingClientRect();
    if (!r) return {x:0,y:0};
    return {
      x: (clientX - r.left - pan.x) / zoom,
      y: (clientY - r.top - pan.y) / zoom,
    };
  }, [pan, zoom]);

  const onNodeDown = useCallback((e, id) => {
    e.stopPropagation();
    e.preventDefault();
    const w = toWorld(e.clientX, e.clientY);
    const n = nodes.find(n => n.id === id);
    dragRef.current = { id, ox: w.x - n.x, oy: w.y - n.y };
  }, [nodes, toWorld]);

  const onBgDown = useCallback((e) => {
    if (dragRef.current) return;
    panRef.current = { sx: e.clientX - pan.x, sy: e.clientY - pan.y };
  }, [pan]);

  const onMove = useCallback((e) => {
    if (dragRef.current) {
      const w = toWorld(e.clientX, e.clientY);
      const nx = Math.round((w.x - dragRef.current.ox)/10)*10;
      const ny = Math.round((w.y - dragRef.current.oy)/10)*10;
      setNodes(prev => prev.map(n => n.id === dragRef.current.id ? {...n, x:nx, y:ny} : n));
    } else if (panRef.current) {
      setPan({ x: e.clientX - panRef.current.sx, y: e.clientY - panRef.current.sy });
    }
  }, [toWorld]);

  const onUp = useCallback(() => {
    dragRef.current = null;
    panRef.current = null;
  }, []);

  const onWheel = useCallback((e) => {
    e.preventDefault();
    const d = e.deltaY > 0 ? 0.92 : 1.08;
    setZoom(z => Math.max(0.12, Math.min(3, z * d)));
  }, []);

  const edgePaths = EDGES.map(([fid,tid,brk],i) => {
    const f = nodes.find(n=>n.id===fid);
    const t = nodes.find(n=>n.id===tid);
    if(!f||!t) return null;
    const x1=cx(f), y1=cy(f), x2=cx(t), y2=cy(t);
    const dx=x2-x1;
    return { key:i, d:`M${x1},${y1} C${x1+dx*0.4},${y1} ${x2-dx*0.4},${y2} ${x2},${y2}`, brk:!!brk, x2, y2 };
  }).filter(Boolean);

  return (
    <div ref={containerRef}
      style={{ width:"100vw", height:"100vh", background:"#08080f", overflow:"hidden", position:"relative", touchAction:"none" }}
      onPointerMove={onMove} onPointerUp={onUp} onPointerLeave={onUp}>

      {/* HUD */}
      <div style={{ position:"absolute", top:10, left:10, zIndex:10, fontFamily:"monospace", pointerEvents:"none" }}>
        <div style={{fontSize:13,fontWeight:700,color:"#e0e0f0"}}>◈ LUNA ENGINE — PIPELINE DIAGNOSTIC</div>
        <div style={{fontSize:9,color:"#555",marginTop:2}}>Drag nodes · Scroll zoom · Pan background · Click for detail</div>
        <div style={{display:"flex",gap:10,marginTop:6}}>
          {Object.entries(TC).map(([k,v])=>(
            <span key={k} style={{display:"flex",alignItems:"center",gap:3,fontSize:8.5,color:"#555"}}>
              <span style={{width:6,height:6,borderRadius:2,background:v.a,display:"inline-block"}}/>{k}
            </span>
          ))}
        </div>
      </div>

      {/* SVG */}
      <svg width="100%" height="100%" style={{display:"block"}}
        onPointerDown={onBgDown} onWheel={onWheel}>
        <g transform={`translate(${pan.x},${pan.y}) scale(${zoom})`}>

          {/* Grid */}
          <defs>
            <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
              <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(255,255,255,0.02)" strokeWidth="0.5"/>
            </pattern>
          </defs>
          <rect x="-2000" y="-2000" width="6000" height="4000" fill="url(#grid)"/>

          {/* Edges */}
          {edgePaths.map(e=>(
            <g key={e.key}>
              <path d={e.d} fill="none" stroke={e.brk?"rgba(239,68,68,0.5)":"rgba(129,140,248,0.18)"} strokeWidth={e.brk?2:1}
                strokeDasharray={e.brk?"5,5":"none"}/>
              <circle r={e.brk?3:2} fill={e.brk?"#ef4444":"#818cf8"} opacity={0.6}>
                <animateMotion dur={e.brk?"1.5s":"3s"} repeatCount="indefinite" path={e.d}/>
              </circle>
            </g>
          ))}

          {/* Nodes */}
          {nodes.map(n => {
            const tc = TC[n.t]||TC.process;
            const h = getH(n);
            const isSel = sel?.id===n.id;
            const isBrk = n.s==="broken";
            return (
              <g key={n.id} onPointerDown={e=>onNodeDown(e,n.id)} onClick={e=>{e.stopPropagation();setSel(n);}} style={{cursor:"grab"}}>
                {isBrk && <rect x={n.x-3} y={n.y-3} width={W+6} height={h+6} rx={12} fill="none" stroke="rgba(239,68,68,0.2)" strokeWidth={2}>
                  <animate attributeName="stroke-opacity" values="0.1;0.4;0.1" dur="2s" repeatCount="indefinite"/>
                </rect>}
                {isSel && <rect x={n.x-2} y={n.y-2} width={W+4} height={h+4} rx={11} fill="none" stroke={tc.a} strokeWidth={1.5} opacity={0.5}/>}
                <rect x={n.x} y={n.y} width={W} height={h} rx={10} fill={tc.bg}
                  stroke={isBrk?"rgba(239,68,68,0.45)":isSel?tc.a:tc.b} strokeWidth={1}/>
                <circle cx={n.x+12} cy={n.y+15} r={3} fill={SC[n.s]||"#666"}>
                  {(n.s==="live"||n.s==="broken")&&<animate attributeName="opacity" values="1;0.3;1" dur={n.s==="broken"?"1s":"2.5s"} repeatCount="indefinite"/>}
                </circle>
                <text x={n.x+22} y={n.y+11} fontSize={13}>{n.ic}</text>
                <text x={n.x+38} y={n.y+18} fill={tc.a} fontSize={9.5} fontWeight={600} fontFamily="monospace">{n.l}</text>
                {n.body.split("\n").map((line,li)=>(
                  <text key={li} x={n.x+10} y={n.y+35+li*14} fill="#667" fontSize={9} fontFamily="monospace">{line}</text>
                ))}
                {/* Handles */}
                <circle cx={n.x} cy={n.y+h/2} r={3.5} fill={tc.bg} stroke={tc.a} strokeWidth={0.8} opacity={0.4}/>
                <circle cx={n.x+W} cy={n.y+h/2} r={3.5} fill={tc.bg} stroke={tc.a} strokeWidth={0.8} opacity={0.4}/>
              </g>
            );
          })}
        </g>
      </svg>

      {/* Detail Panel */}
      {sel && (
        <div style={{
          position:"absolute",right:0,top:0,width:340,height:"100vh",
          background:"#0c0c16",borderLeft:"1px solid rgba(255,255,255,0.06)",
          zIndex:20,overflowY:"auto",padding:"16px 14px",fontFamily:"monospace",
          boxShadow:"-6px 0 20px rgba(0,0,0,0.5)",
        }}>
          <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:14}}>
            <span style={{fontSize:18}}>{sel.ic}</span>
            <span style={{fontSize:11,fontWeight:600,color:TC[sel.t]?.a,textTransform:"uppercase"}}>{sel.l}</span>
            <span onClick={()=>setSel(null)} style={{marginLeft:"auto",cursor:"pointer",color:"#555",fontSize:15,padding:"0 4px"}}>✕</span>
          </div>
          <div style={ps}><div style={pt}>Status</div>
            <span style={{fontSize:9,padding:"2px 8px",borderRadius:4,background:`${SC[sel.s]}18`,color:SC[sel.s],border:`1px solid ${SC[sel.s]}33`}}>{sel.s}</span>
          </div>
          <div style={ps}><div style={pt}>Description</div>
            <pre style={{fontSize:10,color:"#999",lineHeight:1.6,whiteSpace:"pre-wrap",margin:0}}>{sel.desc}</pre>
          </div>
          <div style={ps}><div style={pt}>Source</div>
            <pre style={{fontSize:10,color:"#818cf8",margin:0}}>{sel.file}</pre>
          </div>
          <div style={ps}><div style={pt}>Connections</div>
            {EDGES.filter(e=>e[0]===sel.id||e[1]===sel.id).map((e,i)=>{
              const dir=e[0]===sel.id?"→":"←";
              const oid=e[0]===sel.id?e[1]:e[0];
              const o=INIT_NODES.find(n=>n.id===oid);
              return <div key={i} style={{fontSize:9.5,color:e[2]?"#f87171":"#666",marginBottom:2,cursor:"pointer"}}
                onClick={()=>{const found=nodes.find(n=>n.id===oid);if(found)setSel(found);}}>{dir} {o?.l||oid}{e[2]?" ⚠️":""}</div>;
            })}
          </div>
        </div>
      )}

      {/* Click background to deselect */}
      {sel && <div style={{position:"absolute",inset:0,zIndex:15,pointerEvents:"none"}}
        onClick={()=>setSel(null)}/>}
    </div>
  );
}

const ps = {marginBottom:10,padding:"8px 10px",background:"rgba(255,255,255,0.02)",borderRadius:7,border:"1px solid rgba(255,255,255,0.04)"};
const pt = {fontSize:8.5,fontWeight:500,color:"#555",textTransform:"uppercase",letterSpacing:0.4,marginBottom:4};
