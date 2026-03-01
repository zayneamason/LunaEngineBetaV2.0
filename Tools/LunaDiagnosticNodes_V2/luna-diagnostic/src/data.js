import { MarkerType } from '@xyflow/react';

// ═══════════════════════════════════════════════════════
// TYPE STYLES
// ═══════════════════════════════════════════════════════
export const typeStyles = {
  input:   { bg: 'linear-gradient(135deg, #0f1729, #111d35)', accent: '#06b6d4', iconBg: 'rgba(6,182,212,0.12)' },
  process: { bg: 'linear-gradient(135deg, #110f29, #161135)', accent: '#818cf8', iconBg: 'rgba(129,140,248,0.12)' },
  memory:  { bg: 'linear-gradient(135deg, #0f1f0f, #112211)', accent: '#4ade80', iconBg: 'rgba(74,222,128,0.12)' },
  broken:  { bg: 'linear-gradient(135deg, #1f0f0f, #271111)', accent: '#f87171', iconBg: 'rgba(248,113,113,0.15)' },
  output:  { bg: 'linear-gradient(135deg, #1f1a0f, #271f11)', accent: '#fbbf24', iconBg: 'rgba(251,191,36,0.12)' },
  guard:   { bg: 'linear-gradient(135deg, #1a0f27, #1f1135)', accent: '#c084fc', iconBg: 'rgba(192,132,252,0.12)' },
  context: { bg: 'linear-gradient(135deg, #1f0f1a, #271127)', accent: '#f472b6', iconBg: 'rgba(244,114,182,0.12)' },
};

export const statusColors = {
  live:   { dot: '#22c55e', glow: 'rgba(34,197,94,0.4)' },
  broken: { dot: '#ef4444', glow: 'rgba(239,68,68,0.5)' },
  warn:   { dot: '#f59e0b', glow: 'rgba(245,158,11,0.4)' },
  idle:   { dot: '#666680', glow: 'transparent' },
};

export const legendItems = [
  { color: '#06b6d4', label: 'Input' },
  { color: '#818cf8', label: 'Process' },
  { color: '#4ade80', label: 'Memory' },
  { color: '#c084fc', label: 'Guard' },
  { color: '#f472b6', label: 'Context' },
  { color: '#fbbf24', label: 'Output' },
  { color: '#f87171', label: 'BROKEN' },
];

// ═══════════════════════════════════════════════════════
// NODE FACTORY
// ═══════════════════════════════════════════════════════
const n = (id, x, y, nodeType, icon, label, body, status, desc, file, tags) => ({
  id,
  type: 'engine',
  position: { x, y },
  data: { icon, label, body, status, nodeType, tags: tags || [status], detail: { desc, file } },
});

export const initialNodes = [
  // ── INPUT ──
  n('voice',    0,    0, 'input', '🎤', 'Voice STT',        'MLX Whisper\nTranscript → Engine',      'live',   'Speech-to-text via MLX Whisper. Produces TRANSCRIPT_FINAL events that enter InputBuffer.', 'src/voice/'),
  n('text',     0,  160, 'input', '⌨️', 'Text /message',    'REST POST\n→ InputBuffer',              'live',   'REST API endpoint. Wraps text in InputEvent(TEXT_INPUT) and pushes to InputBuffer.', 'src/luna/api/server.py'),
  n('stream',   0,  320, 'input', '🌊', '/persona/stream',  'SSE path\nBypasses buffer',             'warn',   'Streaming endpoint bypasses InputBuffer — calls PersonaAdapter directly → Director. Separate retrieval pipeline.', 'src/luna/api/server.py', ['warn:separate_path']),
  n('identity', 0,  480, 'input', '👤', 'Identity FaceID',  'Ahab → admin\nConfidence: 1.0',         'live',   'FaceID recognition via FaceNet. Currently sees Ahab with admin tier at full confidence.', 'src/luna/actors/identity.py'),

  // ── CORE PROCESSING ──
  n('buffer',    280,  80, 'process', '📥', 'Input Buffer',     'Priority queue\nPolled each tick',        'live',   'InputBuffer holds events ordered by priority. Cognitive loop polls every 500ms.', 'src/luna/core/input_buffer.py'),
  n('tick',      520,  80, 'process', '💓', 'Cognitive Tick',   '500ms heartbeat\nPoll→Dispatch→State',    'live',   'Every 500ms: poll InputBuffer → dispatch events → consciousness tick → history tick → rebalance context rings.', 'src/luna/engine.py:643'),
  n('dispatch',  520, 250, 'process', '🔀', 'Event Dispatch',   'Route by event type\n→ _handle_user_msg', 'live',   'Routes events by type. TEXT_INPUT → _handle_user_message(). Spawns async task for agentic pipeline.', 'src/luna/engine.py:688'),
  n('persona',   280, 260, 'process', '🎭', 'Persona Adapter',  '/persona/stream path\nSeparate retrieval ⚠️', 'warn', 'Voice/streaming has its OWN context building path. Second potential failure point if it has a different retrieval chain.', 'src/voice/persona_adapter.py', ['warn:separate_pipeline']),

  // ── AGENTIC PIPELINE ──
  n('subtasks',  280, 420, 'process', '⚡', 'Subtask Runner',   'Qwen 3B local\nIntent·Entity·Rewrite',   'live',   'Phase 1 of agentic pipeline: 3 lightweight local inference tasks run in parallel.\n\n• Intent classification\n• Entity extraction\n• Query rewriting', 'src/luna/inference/subtasks.py'),
  n('router',    520, 420, 'process', '🧭', 'Query Router',     'DIRECT vs PLANNED\nComplexity score',     'live',   'Routes by complexity.\n\nSimple → DIRECT (skip planning, go straight to Director)\nComplex → PLANNED (AgentLoop with multi-step planning)\n\nUses subtask intent or regex fallback.', 'src/luna/agentic/router.py'),

  // ── MEMORY RETRIEVAL ──
  n('mem_ret',      780, 250, 'memory', '🧠', 'Memory Retrieval',  'hybrid_search()\nFTS5 + semantic (RRF)\nStatus from live data', 'live',
    'Uses hybrid_search() — FTS5 (BM25) + semantic search with Reciprocal Rank Fusion ranking.\n\nAt engine.py:825, the engine calls:\n  matrix.get_context(query, max_tokens=1500, scopes=active_scopes)\n\nFix applied: replaced broken LIKE-with-stopwords search with hybrid_search() (same path as working /memory/search API).\n\nMemory items enter MIDDLE ring then get promoted to INNER by rebalance_rings() (threshold: relevance >= 0.8, memory enters at 1.0).\n\nStatus determined live from /debug/context — counts MEMORY-sourced items across all rings.',
    'src/luna/engine.py:825', ['live']),

  n('matrix_actor', 1040, 320, 'memory', '🔮', 'Matrix Actor',     'get_context() → hybrid_search\nScope: global\nmax_tokens: 1500', 'live',
    'Wraps MemoryMatrix. get_context() delegates to hybrid_search() (RRF-ranked).\n\n1. hybrid_search() — FTS5 (BM25) + semantic search\n2. Spreading activation (graph traversal)\n3. Constellation assembly (scored results)\n4. Format as text string\n\nFix applied: was broken (LIKE + stopwords stripped queries to nothing). Now uses the same hybrid_search path as /memory/search API.',
    'src/luna/actors/matrix.py', ['live']),

  n('matrix_db',    1040, 140, 'memory', '💾', 'Memory Matrix DB', '24,318 nodes · 23,839 edges\n20,256 FACTs · 700 ENTITYs\nFTS5 + SQLite ✅', 'live',
    'Database is healthy and queryable.\n\nDirect API calls to /memory/search return correct results. The data is THERE.\n\nNode type breakdown:\n• 20,256 FACT nodes\n• 700 ENTITY nodes\n• Various DECISION, PROBLEM, ACTION, INSIGHT nodes\n\n23,839 edges connecting the graph.',
    'data/memory_matrix.db'),

  // ── WORKING MEMORY PATHS ──
  n('dataroom',    1040, 500, 'memory', '📁', 'Dataroom Search',  'SQL: WHERE DOCUMENT\nKeyword match ✅\nBypasses get_context()', 'live',
    'WORKS because it uses direct SQL — not get_context().\n\nCode path:\n  rows = await memory.db.fetchall(\n    "SELECT ... FROM memory_nodes WHERE node_type = \'DOCUMENT\'...")\n\nThis proves the database is accessible and queryable during message processing. The break is specifically in get_context().', 'src/luna/engine.py'),

  n('hist_load',   780, 470, 'process', '📜', 'History Loader',   'SQL: conversation turns\nLoads INNER ring only', 'warn',
    'Loads CONVERSATION turns (not FACTs or ENTITYs) into the INNER context ring.\n\nLuna sees her own previous responses but NOT the knowledge graph. She has short-term memory but no long-term recall.', 'src/luna/engine.py', ['warn']),

  n('hist_mgr',    520, 600, 'process', '🗂️', 'History Manager',  'Tiered compression\nRecent→Summary→Archive', 'live',
    'Manages conversation history across three compression tiers.\n\nRecent: full text\nSummary: compressed\nArchive: minimal\n\nTicked every cognitive cycle.', 'src/luna/actors/history_manager.py'),

  // ── REVOLVING CONTEXT ──
  n('context',     780, 640, 'context', '🎯', 'Revolving Context', 'Budget: 8000 tok\nUsed: 2087 (26%)\nCORE:1 INNER:7\nMIDDLE:0 ⚠️ OUTER:0 ⚠️', 'warn',
    '4 concentric rings with 8000 token budget:\n\nCORE (1 item, 139 tok): Identity prompt — never evicted\nINNER (7 items, 1948 tok): Conversation turns — recent history\nMIDDLE (0 items, 0 tok): ← SHOULD HAVE MEMORY SEARCH RESULTS\nOUTER (0 items, 0 tok): ← SHOULD HAVE LOWER-RELEVANCE OVERFLOW\n\n74% of token budget UNUSED because no memory is injected. context.add(content, source=MEMORY) never fires.',
    'src/luna/core/context.py', ['broken:MIDDLE_empty', 'broken:OUTER_empty']),

  n('ring_core',   560, 800, 'context', '◉', 'CORE Ring',    '1 item · 139 tok\nIdentity prompt',     'live',   'Immutable identity prompt. TTL=-1 (permanent). Never evicted.', 'src/luna/core/context.py'),
  n('ring_inner',  720, 800, 'context', '◎', 'INNER Ring',   '7 items · 1948 tok\nConversation only',  'live',   'All 7 items are Luna\'s previous conversation turns. No knowledge graph content whatsoever.', 'src/luna/core/context.py'),
  n('ring_mid',    880, 800, 'context',  '○', 'MIDDLE Ring',  '0 items (expected)\nPromoted to INNER',       'live', 'Memory items land here via context.add(source=MEMORY), then get promoted to INNER ring by rebalance_rings().\n\nPromotion threshold: relevance >= 0.8. Memory enters at relevance 1.0 → immediate promotion.\n\nMIDDLE=0 is EXPECTED when retrieval is working correctly.', 'src/luna/core/context.py', ['live']),
  n('ring_outer', 1040, 800, 'context',  '◌', 'OUTER Ring',   '0 items · 0 tok\nOverflow buffer',  'live', 'Lower-relevance items that overflow from MIDDLE. First ring to be evicted when budget is tight. May be empty when budget is sufficient.', 'src/luna/core/context.py', ['live']),

  // ── SYSTEM PROMPT + DIRECTOR ──
  n('sysprompt', 1040, 640, 'process', '📝', 'System Prompt',  '_build_system_prompt()\nIdentity+History\nMemory: EMPTY ⚠️', 'warn',
    'Assembles the complete system prompt from components:\n\n1. Identity context (from FaceID)\n2. Expression directive\n3. Consciousness hints\n4. Thread context\n5. History context (conversation turns)\n6. Memory context ← EMPTY\n\nSince memory_context is empty string, the "Relevant Memory Context" section never appears in the prompt.',
    'src/luna/engine.py', ['warn:no_memory_section']),

  n('director',  1300, 480, 'process', '🎬', 'Director',       'Claude Sonnet\nLLM generation\nNo memory in prompt ⚠️', 'live',
    'LLM inference via Claude Sonnet. Generates correctly — the model works fine.\n\nBut it has NO MEMORY in its system prompt. Only sees identity + conversation history.\n\nResult: confabulates answers (invents facts) or surrenders ("I don\'t have enough context").', 'src/luna/actors/director.py', ['live', 'warn:blind']),

  n('agent_loop', 1300, 320, 'process', '🔄', 'Agent Loop',    'Multi-step planning\nMax 50 iterations', 'live',
    'For PLANNED queries. Multi-step loop:\n\n1. Plan: break into subtasks\n2. Execute: run each step\n3. Review: assess results\n\nMax 50 iterations. Routes to Director for generation.', 'src/luna/agentic/loop.py'),

  // ── QUALITY GUARDS ──
  n('scout',     1540, 320, 'guard', '🔭', 'Scout',      'Quality guard\nSurrender·Shallow·Deflect\nConfab: planned', 'live',
    'Post-generation quality gate.\n\nCurrently detects:\n• Surrender patterns ("I don\'t have enough context")\n• Shallow recall (generic responses)\n• Deflection (topic avoidance)\n\nTriggers Overdrive retry on failure.\n\nPlanned: Confabulation detection (Level 1-3). Blocked by broken retrieval — can\'t distinguish real confab from system failure when context is always empty.',
    'src/luna/actors/scout.py'),

  n('overdrive', 1540, 480, 'guard', '⚡', 'Overdrive',   'Retry enriched ctx\nAlso hits broken retrieval\nRetries futile ⚠️', 'warn',
    'Retry mechanism — re-runs generation with enriched context.\n\nPROBLEM: Overdrive ALSO calls matrix.get_context() for enrichment, which ALSO returns empty. Retries are futile until upstream retrieval is fixed.',
    'src/luna/actors/scout.py', ['live', 'warn:retries_futile']),

  n('watchdog',  1540, 640, 'guard', '🐕', 'Watchdog',    '5s interval\nStuck detection\nAuto-recovery', 'live',
    'Background monitoring loop. Every 5 seconds checks for stuck states.\n\nIf processing stuck >30 seconds, forces reset. Prevents infinite loops in the agentic pipeline.',
    'src/luna/actors/scout.py'),

  n('reconcile', 1300, 640, 'guard', '🔧', 'Reconcile',   'Self-correction\nInitialized, not wired\nPending confab guard', 'idle',
    'ReconcileManager — initialized but not yet functional.\n\nRequires:\n1. Confabulation detection (from Scout)\n2. Working memory retrieval (to cross-reference claims)\n\nBoth prerequisites are currently blocked.', 'src/luna/actors/reconcile.py', ['idle']),

  // ── OUTPUT ──
  n('tts',     1740, 380, 'output', '🔊', 'TTS Output',     'Piper TTS\nText→Speech', 'live', 'Text-to-speech via Piper. Converts Director output to audio.', 'src/voice/tts/'),
  n('textout', 1740, 540, 'output', '💬', 'Text Response',   'REST + SSE\nContext updated', 'live', 'Response delivered via REST or SSE stream. After delivery: context updated, turn recorded to Scribe.', 'src/luna/api/server.py'),

  // ── EXTRACTION LOOP ──
  n('scribe',    280, 740, 'memory', '✍️', 'Scribe',     'Extract FACT/ENTITY\nUser turns only\nV2: + corrections', 'live',
    'Extracts knowledge from user turns:\n\n• FACT nodes (declarative knowledge)\n• ENTITY nodes (people, places, things)\n\nScribe V2 (designed, not implemented):\n• CORRECTION type for confabulation fixes\n• Process assistant turns too\n• Closed-loop integrity', 'src/luna/actors/scribe.py'),

  n('librarian',  280, 900, 'memory', '📚', 'Librarian',  'Dedup + file\nExtracted→Matrix', 'live',
    'Files extracted objects into Memory Matrix.\n\n• Deduplication check\n• Entity resolution\n• Edge creation (relationships)\n• Tag assignment', 'src/luna/actors/librarian.py'),

  // ── CONSCIOUSNESS ──
  n('consciousness', 0, 620, 'process', '🌀', 'Consciousness', 'Emotion · Attention\nEnergy state', 'live',
    'Tracks internal emotional/cognitive state.\n\nDimensions: emotional valence, attention focus, energy level.\n\nTicked every cognitive cycle. Provides hints to system prompt for contextual responses.', 'src/luna/consciousness.py'),
];

// ═══════════════════════════════════════════════════════
// EDGES
// ═══════════════════════════════════════════════════════
const e = (source, target, label, broken, animated = true) => ({
  id: `e-${source}-${target}`,
  source,
  target,
  type: 'animated',
  data: { label, broken: !!broken, animated },
});

export const initialEdges = [
  // Input → Buffer
  e('voice', 'buffer', 'TRANSCRIPT'),
  e('text', 'buffer', 'TEXT_INPUT'),
  e('stream', 'persona', 'SSE direct'),
  e('persona', 'director', 'generate'),

  // Buffer → Tick → Dispatch
  e('buffer', 'tick', 'poll_all()'),
  e('tick', 'dispatch', 'events'),

  // Dispatch → Pipeline
  e('dispatch', 'subtasks', '_handle_msg'),
  e('subtasks', 'router', 'intent+entities'),
  e('router', 'agent_loop', 'PLANNED'),
  e('router', 'director', 'DIRECT'),
  e('agent_loop', 'director', 'generate'),

  // Memory retrieval
  e('dispatch', 'mem_ret', '_retrieve_ctx()'),
  e('mem_ret', 'matrix_actor', 'hybrid_search()'),
  e('matrix_actor', 'matrix_db', 'FTS5+vectors'),
  e('mem_ret', 'context', 'add(MEMORY)'),

  // Dataroom — WORKS
  e('dispatch', 'dataroom', 'dataroom_ctx()'),
  e('dataroom', 'matrix_db', 'SQL direct ✅'),
  e('dataroom', 'context', 'add(MEMORY) ✅'),

  // History
  e('dispatch', 'hist_load', 'load_history()'),
  e('hist_load', 'matrix_db', 'SQL: conv turns'),
  e('hist_load', 'context', 'add(CONV)'),
  e('hist_mgr', 'context', 'history_ctx'),

  // Context → Prompt → Director
  e('context', 'sysprompt', 'get_window()'),
  e('sysprompt', 'director', 'sys_prompt'),

  // Context → Rings
  { id: 'e-ctx-core', source: 'context', target: 'ring_core', sourceHandle: 'bottom', targetHandle: 'top', type: 'animated', data: { animated: false } },
  { id: 'e-ctx-inner', source: 'context', target: 'ring_inner', sourceHandle: 'bottom', targetHandle: 'top', type: 'animated', data: { animated: false } },
  { id: 'e-ctx-mid', source: 'context', target: 'ring_mid', sourceHandle: 'bottom', targetHandle: 'top', type: 'animated', data: { animated: false } },
  { id: 'e-ctx-outer', source: 'context', target: 'ring_outer', sourceHandle: 'bottom', targetHandle: 'top', type: 'animated', data: { animated: false } },

  // Director → Guards → Output
  e('director', 'scout', 'draft'),
  e('scout', 'overdrive', 'flag→retry'),
  e('overdrive', 'director', 're-gen'),
  e('scout', 'tts', 'approved'),
  e('scout', 'textout', 'approved'),
  e('scout', 'reconcile', 'confab flag', false, false),

  // Output → Extraction
  e('textout', 'scribe', 'record turn'),
  e('scribe', 'librarian', 'extracted'),
  e('librarian', 'matrix_db', 'file nodes'),

  // Identity + Consciousness
  e('identity', 'sysprompt', 'identity ctx'),
  e('consciousness', 'sysprompt', 'state hints'),
  e('tick', 'consciousness', 'tick()'),
  e('tick', 'hist_mgr', 'tick()'),
];

export const defaultEdgeOptions = {
  type: 'animated',
  style: { stroke: 'rgba(129,140,248,0.18)', strokeWidth: 1.2 },
  markerEnd: { type: MarkerType.ArrowClosed, width: 12, height: 12, color: 'rgba(129,140,248,0.3)' },
};
