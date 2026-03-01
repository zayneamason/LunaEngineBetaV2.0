import { MarkerType } from '@xyflow/react';

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

const n = (id, x, y, nodeType, icon, label, body, status, desc, file, tags) => ({
  id,
  type: 'engine',
  position: { x, y },
  data: { icon, label, body, status, nodeType, tags: tags || [status], detail: { desc, file } },
});

export const initialNodes = [
  n('voice',    0,    0, 'input', '🎤', 'Voice STT',        'MLX Whisper\nTranscript → Engine',      'live',   'Speech-to-text via MLX Whisper.', 'src/voice/'),
  n('text',     0,  160, 'input', '⌨️', 'Text /message',    'REST POST\n→ InputBuffer',              'live',   'REST API endpoint.', 'src/luna/api/server.py'),
  n('stream',   0,  320, 'input', '🌊', '/persona/stream',  'SSE path\nBypasses buffer',             'warn',   'Streaming endpoint bypasses InputBuffer.', 'src/luna/api/server.py', ['warn:separate_path']),
  n('identity', 0,  480, 'input', '👤', 'Identity FaceID',  'Ahab → admin\nConfidence: 1.0',         'live',   'FaceID recognition via FaceNet.', 'src/luna/actors/identity.py'),

  n('buffer',    280,  80, 'process', '📥', 'Input Buffer',     'Priority queue\nPolled each tick',        'live',   'InputBuffer holds events ordered by priority.', 'src/luna/core/input_buffer.py'),
  n('tick',      520,  80, 'process', '💓', 'Cognitive Tick',   '500ms heartbeat\nPoll→Dispatch→State',    'live',   'Every 500ms: poll InputBuffer → dispatch events.', 'src/luna/engine.py:643'),
  n('dispatch',  520, 250, 'process', '🔀', 'Event Dispatch',   'Route by event type\n→ _handle_user_msg', 'live',   'Routes events by type.', 'src/luna/engine.py:688'),
  n('persona',   280, 260, 'process', '🎭', 'Persona Adapter',  '/persona/stream path\nSeparate retrieval', 'warn', 'Voice/streaming separate context building path.', 'src/voice/persona_adapter.py', ['warn:separate_pipeline']),

  n('subtasks',  280, 420, 'process', '⚡', 'Subtask Runner',   'Qwen 3B local\nIntent·Entity·Rewrite',   'live',   'Phase 1 of agentic pipeline.', 'src/luna/inference/subtasks.py'),
  n('router',    520, 420, 'process', '🧭', 'Query Router',     'DIRECT vs PLANNED\nComplexity score',     'live',   'Routes by complexity.', 'src/luna/agentic/router.py'),

  n('mem_ret',      780, 250, 'memory', '🧠', 'Memory Retrieval',  'hybrid_search()\nFTS5 + semantic (RRF)', 'live', 'Uses hybrid_search().', 'src/luna/engine.py:825', ['live']),
  n('matrix_actor', 1040, 320, 'memory', '🔮', 'Matrix Actor',     'get_context() → hybrid_search\nScope: global', 'live', 'Wraps MemoryMatrix.', 'src/luna/actors/matrix.py', ['live']),
  n('matrix_db',    1040, 140, 'memory', '💾', 'Memory Matrix DB', '24,318 nodes · 23,839 edges\nFTS5 + SQLite', 'live', 'Database is healthy.', 'data/memory_matrix.db'),

  n('dataroom',    1040, 500, 'memory', '📁', 'Dataroom Search',  'SQL: WHERE DOCUMENT\nKeyword match', 'live', 'WORKS via direct SQL.', 'src/luna/engine.py'),
  n('hist_load',   780, 470, 'process', '📜', 'History Loader',   'SQL: conversation turns\nLoads INNER ring only', 'warn', 'Loads CONVERSATION turns.', 'src/luna/engine.py', ['warn']),
  n('hist_mgr',    520, 600, 'process', '🗂️', 'History Manager',  'Tiered compression\nRecent→Summary→Archive', 'live', 'Manages conversation history.', 'src/luna/actors/history_manager.py'),

  n('context',     780, 640, 'context', '🎯', 'Revolving Context', 'Budget: 8000 tok\n4 concentric rings', 'warn', '4 concentric rings with 8000 token budget.', 'src/luna/core/context.py', ['broken:MIDDLE_empty', 'broken:OUTER_empty']),
  n('ring_core',   560, 800, 'context', '◉', 'CORE Ring',    '1 item · 139 tok\nIdentity prompt',     'live',   'Immutable identity prompt.', 'src/luna/core/context.py'),
  n('ring_inner',  720, 800, 'context', '◎', 'INNER Ring',   '7 items · 1948 tok\nConversation only',  'live',   'Conversation turns.', 'src/luna/core/context.py'),
  n('ring_mid',    880, 800, 'context',  '○', 'MIDDLE Ring',  '0 items (expected)\nPromoted to INNER',  'live',   'Memory items land here.', 'src/luna/core/context.py', ['live']),
  n('ring_outer', 1040, 800, 'context',  '◌', 'OUTER Ring',   '0 items · 0 tok\nOverflow buffer',      'live',   'Lower-relevance overflow.', 'src/luna/core/context.py', ['live']),

  n('sysprompt', 1040, 640, 'process', '📝', 'System Prompt',  '_build_system_prompt()\nIdentity+History', 'warn', 'Assembles the complete system prompt.', 'src/luna/engine.py', ['warn:no_memory_section']),
  n('director',  1300, 480, 'process', '🎬', 'Director',       'Claude Sonnet\nLLM generation', 'live', 'LLM inference via Claude Sonnet.', 'src/luna/actors/director.py', ['live', 'warn:blind']),
  n('agent_loop', 1300, 320, 'process', '🔄', 'Agent Loop',    'Multi-step planning\nMax 50 iterations', 'live', 'For PLANNED queries.', 'src/luna/agentic/loop.py'),

  n('scout',     1540, 320, 'guard', '🔭', 'Scout',      'Quality guard\nSurrender·Shallow·Deflect', 'live', 'Post-generation quality gate.', 'src/luna/actors/scout.py'),
  n('overdrive', 1540, 480, 'guard', '⚡', 'Overdrive',   'Retry enriched ctx', 'warn', 'Retry mechanism.', 'src/luna/actors/scout.py', ['live', 'warn:retries_futile']),
  n('watchdog',  1540, 640, 'guard', '🐕', 'Watchdog',    '5s interval\nStuck detection', 'live', 'Background monitoring loop.', 'src/luna/actors/scout.py'),
  n('reconcile', 1300, 640, 'guard', '🔧', 'Reconcile',   'Self-correction\nPending confab guard', 'idle', 'ReconcileManager.', 'src/luna/actors/reconcile.py', ['idle']),

  n('tts',     1740, 380, 'output', '🔊', 'TTS Output',     'Piper TTS\nText→Speech', 'live', 'Text-to-speech via Piper.', 'src/voice/tts/'),
  n('textout', 1740, 540, 'output', '💬', 'Text Response',   'REST + SSE\nContext updated', 'live', 'Response delivered via REST or SSE.', 'src/luna/api/server.py'),

  n('scribe',    280, 740, 'memory', '✍️', 'Scribe',     'Extract FACT/ENTITY\nUser turns only', 'live', 'Extracts knowledge from user turns.', 'src/luna/actors/scribe.py'),
  n('librarian',  280, 900, 'memory', '📚', 'Librarian',  'Dedup + file\nExtracted→Matrix', 'live', 'Files extracted objects into Memory Matrix.', 'src/luna/actors/librarian.py'),
  n('cache',      520, 820, 'process', '🧊', 'Cache Actor', 'Shared Turn Cache\nTone→Dimensional feed', 'live', 'Writes rotating YAML snapshot, derives emotional tone, feeds DimensionalEngine. Bridges MCP/voice/Eclissi into single-brain state.', 'src/luna/actors/cache.py'),

  n('consciousness', 0, 620, 'process', '🌀', 'Consciousness', 'Emotion · Attention\nEnergy state', 'live', 'Tracks internal emotional/cognitive state.', 'src/luna/consciousness.py'),
];

const e = (source, target, label, broken, animated = true) => ({
  id: `e-${source}-${target}`,
  source,
  target,
  type: 'animated',
  data: { label, broken: !!broken, animated },
});

export const initialEdges = [
  e('voice', 'buffer', 'TRANSCRIPT'),
  e('text', 'buffer', 'TEXT_INPUT'),
  e('stream', 'persona', 'SSE direct'),
  e('persona', 'director', 'generate'),
  e('buffer', 'tick', 'poll_all()'),
  e('tick', 'dispatch', 'events'),
  e('dispatch', 'subtasks', '_handle_msg'),
  e('subtasks', 'router', 'intent+entities'),
  e('router', 'agent_loop', 'PLANNED'),
  e('router', 'director', 'DIRECT'),
  e('agent_loop', 'director', 'generate'),
  e('dispatch', 'mem_ret', '_retrieve_ctx()'),
  e('mem_ret', 'matrix_actor', 'hybrid_search()'),
  e('matrix_actor', 'matrix_db', 'FTS5+vectors'),
  e('mem_ret', 'context', 'add(MEMORY)'),
  e('dispatch', 'dataroom', 'dataroom_ctx()'),
  e('dataroom', 'matrix_db', 'SQL direct'),
  e('dataroom', 'context', 'add(MEMORY)'),
  e('dispatch', 'hist_load', 'load_history()'),
  e('hist_load', 'matrix_db', 'SQL: conv turns'),
  e('hist_load', 'context', 'add(CONV)'),
  e('hist_mgr', 'context', 'history_ctx'),
  e('context', 'sysprompt', 'get_window()'),
  e('sysprompt', 'director', 'sys_prompt'),
  { id: 'e-ctx-core', source: 'context', target: 'ring_core', sourceHandle: 'bottom', targetHandle: 'top', type: 'animated', data: { animated: false } },
  { id: 'e-ctx-inner', source: 'context', target: 'ring_inner', sourceHandle: 'bottom', targetHandle: 'top', type: 'animated', data: { animated: false } },
  { id: 'e-ctx-mid', source: 'context', target: 'ring_mid', sourceHandle: 'bottom', targetHandle: 'top', type: 'animated', data: { animated: false } },
  { id: 'e-ctx-outer', source: 'context', target: 'ring_outer', sourceHandle: 'bottom', targetHandle: 'top', type: 'animated', data: { animated: false } },
  e('director', 'scout', 'draft'),
  e('scout', 'overdrive', 'flag→retry'),
  e('overdrive', 'director', 're-gen'),
  e('scout', 'tts', 'approved'),
  e('scout', 'textout', 'approved'),
  e('scout', 'reconcile', 'confab flag', false, false),
  e('textout', 'scribe', 'record turn'),
  e('scribe', 'librarian', 'extracted'),
  e('scribe', 'cache', 'cache_update'),
  e('cache', 'consciousness', 'dimensional feed'),
  e('librarian', 'matrix_db', 'file nodes'),
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
