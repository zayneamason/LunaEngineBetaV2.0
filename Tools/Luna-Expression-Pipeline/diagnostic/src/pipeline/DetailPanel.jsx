import React, { useState, useEffect, useCallback } from 'react';
import { typeStyles, statusColors } from './pipelineData';
import { fetchLastInference, fetchPromptInfo } from './useLiveData';

const NODE_SOURCE_FILES = {
  director:     'src/luna/actors/director.py',
  scout:        'src/luna/actors/scout.py',
  reconcile:    'src/luna/actors/reconcile.py',
  scribe:       'src/luna/actors/scribe.py',
  cache:        'src/luna/cache/shared_turn.py',
  context:      'src/luna/context/assembler.py',
  sysprompt:    'src/luna/context/assembler.py',
  mem_ret:      'src/luna/substrate/memory.py',
  matrix_actor: 'src/luna/substrate/memory.py',
  router:       'src/luna/agentic/router.py',
  agent_loop:   'src/luna/agentic/loop.py',
  hist_mgr:     'src/luna/api/server.py',
  consciousness:'src/luna/services/orb_state.py',
};

// Nodes that have I/O diff support
const IO_NODES = new Set(['director', 'context', 'mem_ret', 'sysprompt', 'cache', 'router', 'scribe']);

const S = {
  section: {
    marginBottom: 14, padding: '10px 12px',
    background: 'rgba(255,255,255,0.02)', borderRadius: 8,
    border: '1px solid rgba(255,255,255,0.04)',
  },
  title: {
    fontSize: 9.5, fontWeight: 500, color: '#555568',
    textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 6,
  },
  metric: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    fontSize: 10, color: '#888', padding: '3px 0',
    borderBottom: '1px solid rgba(255,255,255,0.02)',
  },
  metricValue: {
    fontSize: 10, fontWeight: 600, fontFamily: "'JetBrains Mono', monospace",
  },
};

function MetricRow({ label, value, color }) {
  return (
    <div style={S.metric}>
      <span>{label}</span>
      <span style={{ ...S.metricValue, color: color || '#818cf8' }}>{value}</span>
    </div>
  );
}

function LiveBadge() {
  return (
    <span style={{
      fontSize: 8, padding: '1px 6px', borderRadius: 3,
      background: 'rgba(34,197,94,0.12)', color: '#22c55e',
      border: '1px solid rgba(34,197,94,0.25)',
      textTransform: 'uppercase', letterSpacing: '0.5px',
      animation: 'pulse-green 2.5s ease-in-out infinite',
    }}>LIVE</span>
  );
}

// Collapsible text section
function CollapsibleText({ label, text, maxPreview = 200 }) {
  const [open, setOpen] = useState(false);
  if (!text) return null;
  const preview = text.length > maxPreview ? text.slice(0, maxPreview) + '...' : text;

  return (
    <div style={{ marginTop: 4 }}>
      <div
        onClick={() => setOpen(!open)}
        style={{ fontSize: 8, color: '#818cf8', cursor: 'pointer', marginBottom: 2 }}
      >
        {open ? `▲ Hide ${label}` : `▼ Show ${label} (${text.length} chars)`}
      </div>
      {open && (
        <pre style={{
          fontSize: 9, color: '#999', lineHeight: 1.5, margin: 0,
          whiteSpace: 'pre-wrap', wordBreak: 'break-word',
          maxHeight: 300, overflow: 'auto',
          padding: '6px 8px', borderRadius: 4,
          background: 'rgba(0,0,0,0.2)', border: '1px solid rgba(255,255,255,0.03)',
        }}>{text}</pre>
      )}
      {!open && (
        <pre style={{
          fontSize: 9, color: '#666', lineHeight: 1.4, margin: 0,
          whiteSpace: 'pre-wrap', wordBreak: 'break-word',
          maxHeight: 36, overflow: 'hidden',
        }}>{preview}</pre>
      )}
    </div>
  );
}

// I/O Diff Section
function IODiffSection({ nodeId, liveData }) {
  const [lastInf, setLastInf] = useState(null);
  const [promptData, setPromptData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    Promise.all([fetchLastInference(), fetchPromptInfo()])
      .then(([inf, prompt]) => {
        if (mounted) {
          setLastInf(inf);
          setPromptData(prompt?.data || null);
          setLoading(false);
        }
      })
      .catch(() => mounted && setLoading(false));
    return () => { mounted = false; };
  }, [nodeId]);

  if (loading) {
    return (
      <div style={S.section}>
        <div style={{ ...S.title, color: '#06b6d4' }}>I/O Diff</div>
        <div style={{ fontSize: 9, color: '#555' }}>Loading...</div>
      </div>
    );
  }

  if (!lastInf && !promptData) return null;

  // Director node
  if (nodeId === 'director') {
    return (
      <div style={{ ...S.section, borderColor: 'rgba(6,182,212,0.15)' }}>
        <div style={{ ...S.title, color: '#06b6d4' }}>I/O Diff</div>
        <div style={{
          padding: '6px 8px', borderRadius: 4, marginBottom: 6,
          background: 'rgba(6,182,212,0.03)', border: '1px solid rgba(6,182,212,0.08)',
        }}>
          <div style={{ fontSize: 8, color: '#06b6d4', letterSpacing: 1, marginBottom: 4 }}>INPUT</div>
          <MetricRow label="System prompt" value={`${lastInf?.system_prompt_length || promptData?.length || 0} chars`} />
          <MetricRow label="Route" value={lastInf?.route || promptData?.route_decision || '—'} />
          <MetricRow label="Provider" value={lastInf?.provider || '—'} />
          <CollapsibleText label="full prompt" text={promptData?.full_prompt || lastInf?.system_prompt_preview} />
        </div>
        <div style={{
          padding: '6px 8px', borderRadius: 4,
          background: 'rgba(6,182,212,0.03)', border: '1px solid rgba(6,182,212,0.08)',
        }}>
          <div style={{ fontSize: 8, color: '#06b6d4', letterSpacing: 1, marginBottom: 4 }}>OUTPUT</div>
          <MetricRow label="Raw response" value={`${lastInf?.raw_response?.length || 0} chars`} />
          <MetricRow label="Narration" value={lastInf?.narration_applied ? 'APPLIED' : 'SKIPPED'} color={lastInf?.narration_applied ? '#22c55e' : '#f59e0b'} />
          <MetricRow label="Final response" value={`${lastInf?.final_response?.length || 0} chars`} />
          {lastInf?.latency_ms != null && <MetricRow label="Latency" value={`${lastInf.latency_ms.toFixed(0)}ms`} />}
          <CollapsibleText label="response" text={lastInf?.final_response} />
        </div>
      </div>
    );
  }

  // Context node
  if (nodeId === 'context') {
    const ctx = liveData?.context || {};
    const items = ctx.items || lastInf?.context_items || [];
    const statusCtx = liveData?.status?.context;
    const memItems = items.filter(i => i.source === 'MEMORY' || i.source === 2);
    return (
      <div style={{ ...S.section, borderColor: 'rgba(6,182,212,0.15)' }}>
        <div style={{ ...S.title, color: '#06b6d4' }}>I/O Diff</div>
        <div style={{
          padding: '6px 8px', borderRadius: 4, marginBottom: 6,
          background: 'rgba(6,182,212,0.03)', border: '1px solid rgba(6,182,212,0.08)',
        }}>
          <div style={{ fontSize: 8, color: '#06b6d4', letterSpacing: 1, marginBottom: 4 }}>INPUT</div>
          <MetricRow label="Budget" value={`${statusCtx?.token_budget || '8000'} tokens`} />
          <MetricRow label="Items" value={items.length} />
          {items.slice(0, 8).map((item, i) => (
            <div key={i} style={{ fontSize: 9, color: '#777', padding: '1px 0' }}>
              {item.ring || '?'}: {item.source || '?'} ({item.tokens || 0} tok)
            </div>
          ))}
          {items.length > 8 && <div style={{ fontSize: 8, color: '#555' }}>...{items.length - 8} more</div>}
        </div>
        <div style={{
          padding: '6px 8px', borderRadius: 4,
          background: 'rgba(6,182,212,0.03)', border: '1px solid rgba(6,182,212,0.08)',
        }}>
          <div style={{ fontSize: 8, color: '#06b6d4', letterSpacing: 1, marginBottom: 4 }}>OUTPUT</div>
          <MetricRow label="Total assembled" value={`${statusCtx?.total_tokens || items.reduce((s, i) => s + (i.tokens || 0), 0)} tokens`} />
          <MetricRow label="Budget used" value={`${statusCtx?.budget_used_pct?.toFixed(1) || '?'}%`} />
          <MetricRow label="Memory items" value={`${memItems.length}${memItems.length > 0 ? '' : ' ⚠️'}`} color={memItems.length > 0 ? '#22c55e' : '#f59e0b'} />
        </div>
      </div>
    );
  }

  // Memory retrieval node
  if (nodeId === 'mem_ret') {
    const ctx = liveData?.context || {};
    const items = ctx.items || lastInf?.context_items || [];
    const memItems = items.filter(i => i.source === 'MEMORY' || i.source === 2);
    return (
      <div style={{ ...S.section, borderColor: 'rgba(6,182,212,0.15)' }}>
        <div style={{ ...S.title, color: '#06b6d4' }}>I/O Diff</div>
        <div style={{
          padding: '6px 8px', borderRadius: 4, marginBottom: 6,
          background: 'rgba(6,182,212,0.03)', border: '1px solid rgba(6,182,212,0.08)',
        }}>
          <div style={{ fontSize: 8, color: '#06b6d4', letterSpacing: 1, marginBottom: 4 }}>INPUT</div>
          <MetricRow label="Query" value={lastInf?.query ? `"${lastInf.query.slice(0, 40)}"` : '—'} />
          <MetricRow label="Search type" value="hybrid (FTS5+vec)" />
        </div>
        <div style={{
          padding: '6px 8px', borderRadius: 4,
          background: 'rgba(6,182,212,0.03)', border: '1px solid rgba(6,182,212,0.08)',
        }}>
          <div style={{ fontSize: 8, color: '#06b6d4', letterSpacing: 1, marginBottom: 4 }}>OUTPUT</div>
          <MetricRow label="Results" value={`${memItems.length} items${memItems.length === 0 ? ' ⚠️' : ''}`} color={memItems.length > 0 ? '#22c55e' : '#f59e0b'} />
          {memItems.length === 0 && <div style={{ fontSize: 9, color: '#666' }}>(no memory retrieved)</div>}
        </div>
      </div>
    );
  }

  // System prompt node
  if (nodeId === 'sysprompt') {
    const assembler = lastInf?.assembler || promptData?.assembler;
    return (
      <div style={{ ...S.section, borderColor: 'rgba(6,182,212,0.15)' }}>
        <div style={{ ...S.title, color: '#06b6d4' }}>I/O Diff</div>
        <div style={{
          padding: '6px 8px', borderRadius: 4, marginBottom: 6,
          background: 'rgba(6,182,212,0.03)', border: '1px solid rgba(6,182,212,0.08)',
        }}>
          <div style={{ fontSize: 8, color: '#06b6d4', letterSpacing: 1, marginBottom: 4 }}>INPUT</div>
          <MetricRow label="Identity source" value={assembler?.identity_source || '—'} />
          <MetricRow label="Memory source" value={assembler?.memory_source || 'none'} />
          <MetricRow label="Gap category" value={assembler?.gap_category || '—'} />
          {assembler?.register_active && <MetricRow label="Register" value={assembler.register_active} />}
        </div>
        <div style={{
          padding: '6px 8px', borderRadius: 4,
          background: 'rgba(6,182,212,0.03)', border: '1px solid rgba(6,182,212,0.08)',
        }}>
          <div style={{ fontSize: 8, color: '#06b6d4', letterSpacing: 1, marginBottom: 4 }}>OUTPUT</div>
          <MetricRow label="Prompt length" value={`${lastInf?.system_prompt_length || promptData?.length || 0} chars`} />
          <MetricRow label="Tokens" value={`~${assembler?.prompt_tokens || '?'}`} />
          <CollapsibleText label="system prompt" text={promptData?.full_prompt || lastInf?.system_prompt_preview} />
        </div>
      </div>
    );
  }

  // Cache node
  if (nodeId === 'cache') {
    const cache = liveData?.cache;
    if (!cache) return null;
    return (
      <div style={{ ...S.section, borderColor: 'rgba(6,182,212,0.15)' }}>
        <div style={{ ...S.title, color: '#06b6d4' }}>I/O Diff</div>
        <div style={{
          padding: '6px 8px', borderRadius: 4, marginBottom: 6,
          background: 'rgba(6,182,212,0.03)', border: '1px solid rgba(6,182,212,0.08)',
        }}>
          <div style={{ fontSize: 8, color: '#06b6d4', letterSpacing: 1, marginBottom: 4 }}>INPUT</div>
          <MetricRow label="Last inference data" value="turn snapshot" />
        </div>
        <div style={{
          padding: '6px 8px', borderRadius: 4,
          background: 'rgba(6,182,212,0.03)', border: '1px solid rgba(6,182,212,0.08)',
        }}>
          <div style={{ fontSize: 8, color: '#06b6d4', letterSpacing: 1, marginBottom: 4 }}>OUTPUT</div>
          <MetricRow label="Tone" value={cache.expression?.emotional_tone || 'neutral'} />
          <MetricRow label="Expression hint" value={cache.expression?.expression_hint || 'idle_soft'} />
          <MetricRow label="Topic" value={cache.flow?.topic || '—'} />
          <MetricRow label="Mode" value={cache.flow?.mode || 'FLOW'} />
          <MetricRow label="Stale" value={cache.is_stale ? 'YES' : 'NO'} color={cache.is_stale ? '#f59e0b' : '#22c55e'} />
        </div>
      </div>
    );
  }

  // Router node
  if (nodeId === 'router') {
    const agentic = liveData?.status?.agentic;
    return (
      <div style={{ ...S.section, borderColor: 'rgba(6,182,212,0.15)' }}>
        <div style={{ ...S.title, color: '#06b6d4' }}>I/O Diff</div>
        <div style={{
          padding: '6px 8px', borderRadius: 4, marginBottom: 6,
          background: 'rgba(6,182,212,0.03)', border: '1px solid rgba(6,182,212,0.08)',
        }}>
          <div style={{ fontSize: 8, color: '#06b6d4', letterSpacing: 1, marginBottom: 4 }}>INPUT</div>
          <MetricRow label="Message complexity" value="evaluated" />
        </div>
        <div style={{
          padding: '6px 8px', borderRadius: 4,
          background: 'rgba(6,182,212,0.03)', border: '1px solid rgba(6,182,212,0.08)',
        }}>
          <div style={{ fontSize: 8, color: '#06b6d4', letterSpacing: 1, marginBottom: 4 }}>OUTPUT</div>
          <MetricRow label="Route" value={lastInf?.route || '—'} />
          <MetricRow label="Direct" value={agentic?.direct_responses || 0} />
          <MetricRow label="Planned" value={agentic?.planned_responses || 0} />
        </div>
      </div>
    );
  }

  // Scribe node
  if (nodeId === 'scribe') {
    const ex = liveData?.extraction?.scribe;
    return (
      <div style={{ ...S.section, borderColor: 'rgba(6,182,212,0.15)' }}>
        <div style={{ ...S.title, color: '#06b6d4' }}>I/O Diff</div>
        <div style={{
          padding: '6px 8px', borderRadius: 4, marginBottom: 6,
          background: 'rgba(6,182,212,0.03)', border: '1px solid rgba(6,182,212,0.08)',
        }}>
          <div style={{ fontSize: 8, color: '#06b6d4', letterSpacing: 1, marginBottom: 4 }}>INPUT</div>
          <MetricRow label="User turn text" value="last turn" />
        </div>
        <div style={{
          padding: '6px 8px', borderRadius: 4,
          background: 'rgba(6,182,212,0.03)', border: '1px solid rgba(6,182,212,0.08)',
        }}>
          <div style={{ fontSize: 8, color: '#06b6d4', letterSpacing: 1, marginBottom: 4 }}>OUTPUT</div>
          <MetricRow label="Extractions" value={ex?.extractions_count || 0} />
          <MetricRow label="Objects extracted" value={ex?.objects_extracted || 0} />
          <MetricRow label="Stack size" value={ex?.stack_size || 0} color={ex?.stack_size > 10 ? '#f59e0b' : '#22c55e'} />
        </div>
      </div>
    );
  }

  return null;
}

// Assertion Playground inline component
function AssertionPlayground({ assertion }) {
  const [text, setText] = useState('');
  const [result, setResult] = useState(null);
  const [checking, setChecking] = useState(false);

  const check = useCallback(async () => {
    if (!text.trim() || checking) return;
    setChecking(true);
    setResult(null);
    try {
      const res = await fetch('/qa/check-assertion', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ assertion_id: assertion.id, response_text: text }),
      });
      if (res.ok) setResult(await res.json());
      else setResult({ passed: false, actual: `HTTP ${res.status}` });
    } catch (e) {
      setResult({ passed: false, actual: e.message });
    } finally {
      setChecking(false);
    }
  }, [text, assertion.id, checking]);

  return (
    <div style={{
      marginTop: 6, padding: '6px 8px', borderRadius: 4,
      background: 'rgba(167,139,250,0.03)', border: '1px solid rgba(167,139,250,0.08)',
    }}>
      <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
        <input
          value={text}
          onChange={e => setText(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && check()}
          placeholder="Test a response..."
          style={{
            flex: 1, background: 'rgba(0,0,0,0.2)', border: '1px solid rgba(255,255,255,0.04)',
            borderRadius: 3, padding: '4px 6px', color: '#c0c0d0', fontSize: 9,
            fontFamily: "'JetBrains Mono', monospace", outline: 'none',
          }}
        />
        <button
          onClick={check}
          disabled={checking || !text.trim()}
          style={{
            padding: '4px 8px', borderRadius: 3, fontSize: 8, fontWeight: 600,
            border: '1px solid rgba(167,139,250,0.3)', background: 'rgba(167,139,250,0.08)',
            color: '#a78bfa', cursor: checking ? 'wait' : 'pointer',
            fontFamily: "'JetBrains Mono', monospace",
          }}
        >CHECK</button>
      </div>
      {result && (
        <div style={{
          marginTop: 4, fontSize: 9, display: 'flex', alignItems: 'center', gap: 6,
          color: result.passed ? '#22c55e' : '#f87171',
        }}>
          <span style={{
            padding: '1px 5px', borderRadius: 3, fontSize: 8, fontWeight: 600,
            background: result.passed ? 'rgba(34,197,94,0.12)' : 'rgba(239,68,68,0.12)',
            border: `1px solid ${result.passed ? 'rgba(34,197,94,0.25)' : 'rgba(239,68,68,0.25)'}`,
          }}>{result.passed ? 'PASS' : 'FAIL'}</span>
          <span style={{ color: '#888' }}>{result.actual || ''}</span>
        </div>
      )}
    </div>
  );
}

function LiveMetrics({ nodeId, liveData, memoryItemCount }) {
  if (!liveData) return null;
  const { status, memoryStats, consciousness, ring, extraction, voice } = liveData;

  if (nodeId === 'tick' && status) {
    return (
      <div style={S.section}>
        <div style={{ ...S.title, display: 'flex', alignItems: 'center', gap: 6 }}>Live Metrics <LiveBadge /></div>
        <MetricRow label="Uptime" value={`${(status.uptime_seconds / 60).toFixed(1)}m`} />
        <MetricRow label="Cognitive Ticks" value={status.cognitive_ticks?.toLocaleString()} />
        <MetricRow label="Events Processed" value={status.events_processed} />
        <MetricRow label="Messages Generated" value={status.messages_generated} />
        <MetricRow label="Buffer Size" value={status.buffer_size} />
        <MetricRow label="Current Turn" value={status.current_turn} />
      </div>
    );
  }

  if (nodeId === 'matrix_db' && memoryStats) {
    const m = memoryStats;
    return (
      <div style={S.section}>
        <div style={{ ...S.title, display: 'flex', alignItems: 'center', gap: 6 }}>Live Metrics <LiveBadge /></div>
        <MetricRow label="Total Nodes" value={m.total_nodes?.toLocaleString()} />
        <MetricRow label="Total Edges" value={m.total_edges?.toLocaleString()} />
        <MetricRow label="FACTs" value={m.nodes_by_type?.FACT?.toLocaleString()} />
        <MetricRow label="ENTITYs" value={m.nodes_by_type?.ENTITY} />
        <MetricRow label="Settled" value={m.nodes_by_lock_in?.settled} color="#22c55e" />
        <MetricRow label="Fluid" value={m.nodes_by_lock_in?.fluid?.toLocaleString()} color="#f59e0b" />
        <MetricRow label="Avg Lock-in" value={`${((m.avg_lock_in||0) * 100).toFixed(1)}%`} />
      </div>
    );
  }

  if ((nodeId === 'mem_ret' || nodeId === 'matrix_actor') && memoryStats) {
    return (
      <div style={S.section}>
        <div style={{ ...S.title, display: 'flex', alignItems: 'center', gap: 6 }}>Live Metrics <LiveBadge /></div>
        <MetricRow label="Memory Items in Context" value={memoryItemCount ?? '?'} color={memoryItemCount > 0 ? '#22c55e' : '#ef4444'} />
        <MetricRow label="Total Nodes in DB" value={memoryStats.total_nodes?.toLocaleString()} />
        <MetricRow label="Search Method" value="hybrid (FTS5+semantic)" color="#818cf8" />
      </div>
    );
  }

  if (nodeId === 'context' && status?.context) {
    const c = status.context;
    return (
      <div style={S.section}>
        <div style={{ ...S.title, display: 'flex', alignItems: 'center', gap: 6 }}>Live Metrics <LiveBadge /></div>
        <MetricRow label="Token Budget" value={`${c.total_tokens} / ${c.token_budget}`} />
        <MetricRow label="Budget Used" value={`${c.budget_used_pct?.toFixed(1)}%`} color={c.budget_used_pct < 50 ? '#f59e0b' : '#22c55e'} />
        <MetricRow label="Memory Items (all rings)" value={memoryItemCount ?? '?'} color={memoryItemCount > 0 ? '#22c55e' : '#ef4444'} />
      </div>
    );
  }

  if (nodeId === 'consciousness' && consciousness) {
    const c = consciousness;
    return (
      <div style={S.section}>
        <div style={{ ...S.title, display: 'flex', alignItems: 'center', gap: 6 }}>Live Metrics <LiveBadge /></div>
        <MetricRow label="Mood" value={c.mood} />
        <MetricRow label="Coherence" value={`${(c.coherence * 100).toFixed(0)}%`} />
        <MetricRow label="Tick Count" value={c.tick_count?.toLocaleString()} />
      </div>
    );
  }

  if ((nodeId === 'hist_mgr' || nodeId === 'hist_load') && ring) {
    return (
      <div style={S.section}>
        <div style={{ ...S.title, display: 'flex', alignItems: 'center', gap: 6 }}>Live Metrics <LiveBadge /></div>
        <MetricRow label="Turns" value={`${ring.current_turns} / ${ring.max_turns}`} />
        <MetricRow label="Topics" value={(ring.topics || []).slice(0, 5).join(', ')} />
      </div>
    );
  }

  if ((nodeId === 'voice' || nodeId === 'tts') && voice) {
    return (
      <div style={S.section}>
        <div style={{ ...S.title, display: 'flex', alignItems: 'center', gap: 6 }}>Live Metrics <LiveBadge /></div>
        <MetricRow label="Running" value={voice.running ? 'YES' : 'NO'} color={voice.running ? '#22c55e' : '#666'} />
        <MetricRow label="STT Provider" value={voice.stt_provider} />
        <MetricRow label="TTS Provider" value={voice.tts_provider} />
        <MetricRow label="Turn Count" value={voice.turn_count} />
      </div>
    );
  }

  if ((nodeId === 'router' || nodeId === 'agent_loop' || nodeId === 'director') && status?.agentic) {
    const a = status.agentic;
    return (
      <div style={S.section}>
        <div style={{ ...S.title, display: 'flex', alignItems: 'center', gap: 6 }}>Live Metrics <LiveBadge /></div>
        <MetricRow label="Processing" value={a.is_processing ? 'ACTIVE' : 'IDLE'} color={a.is_processing ? '#f59e0b' : '#22c55e'} />
        <MetricRow label="Tasks Started" value={a.tasks_started} />
        <MetricRow label="Tasks Completed" value={a.tasks_completed} />
        <MetricRow label="Direct Responses" value={a.direct_responses} />
      </div>
    );
  }

  return null;
}

export default function DetailPanel({ node, onClose, edges, nodes, liveData }) {
  if (!node) return null;
  const d = node.data;
  const t = typeStyles[d.nodeType] || typeStyles.process;
  const connected = edges.filter(e => e.source === node.id || e.target === node.id);
  const [playgroundOpen, setPlaygroundOpen] = useState(null);

  return (
    <div style={{
      position: 'fixed', right: 0, top: 0, width: 380, height: '100vh',
      background: '#0e0e18', borderLeft: '1px solid rgba(255,255,255,0.06)',
      zIndex: 100, overflowY: 'auto', padding: '20px 18px',
      fontFamily: "'JetBrains Mono', monospace",
      boxShadow: '-8px 0 30px rgba(0,0,0,0.5)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 18 }}>
        <span style={{ fontSize: 20 }}>{d.icon}</span>
        <span style={{ fontSize: 13, fontWeight: 600, color: t.accent, textTransform: 'uppercase', letterSpacing: '0.5px' }}>{d.label}</span>
        {d.live && <LiveBadge />}
        <span onClick={onClose} style={{ marginLeft: 'auto', cursor: 'pointer', color: '#555', fontSize: 16, padding: '2px 6px', borderRadius: 4 }}>✕</span>
      </div>

      <div style={S.section}>
        <div style={S.title}>Status</div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
          {(d.tags || [d.status]).map((tag, i) => {
            const c = tag.includes('live') ? '#22c55e' : tag.includes('broken') ? '#ef4444' : tag.includes('warn') ? '#f59e0b' : '#818cf8';
            return (
              <span key={i} style={{ fontSize: 9.5, padding: '2px 8px', borderRadius: 4, background: `${c}15`, color: c, border: `1px solid ${c}33` }}>{tag}</span>
            );
          })}
        </div>
      </div>

      <LiveMetrics nodeId={node.id} liveData={liveData} memoryItemCount={d.memoryItemCount} />

      {/* I/O Diff Section */}
      {IO_NODES.has(node.id) && <IODiffSection nodeId={node.id} liveData={liveData} />}

      <div style={S.section}>
        <div style={S.title}>Description</div>
        <pre style={{ fontSize: 10.5, color: '#aaa', lineHeight: 1.6, whiteSpace: 'pre-wrap', wordBreak: 'break-word', margin: 0 }}>{d.detail?.desc}</pre>
      </div>

      <div style={S.section}>
        <div style={S.title}>Source File</div>
        <pre style={{ fontSize: 10.5, color: '#818cf8', margin: 0 }}>{d.detail?.file}</pre>
      </div>

      {d.qaFailures && d.qaFailures.length > 0 && (
        <div style={{ ...S.section, borderColor: 'rgba(239,68,68,0.15)' }}>
          <div style={{ ...S.title, color: '#f87171', display: 'flex', alignItems: 'center', gap: 6 }}>
            QA Assertions
            <span style={{
              fontSize: 8, padding: '1px 6px', borderRadius: 3,
              background: 'rgba(239,68,68,0.12)', color: '#ef4444',
              border: '1px solid rgba(239,68,68,0.25)',
            }}>{d.qaFailures.filter(f => !f.passed).length} FAILING</span>
          </div>
          {d.qaDiagnosis && node.id === 'director' && (
            <>
              <MetricRow label="Route" value={liveData?.qaLast?.route || '—'} color="#818cf8" />
              <MetricRow label="Provider" value={liveData?.qaLast?.provider_used || '—'} color="#818cf8" />
              <MetricRow label="Latency" value={liveData?.qaLast?.latency_ms ? `${liveData.qaLast.latency_ms}ms` : '—'} color="#818cf8" />
              <div style={{ fontSize: 9.5, color: '#f59e0b', marginTop: 4, marginBottom: 8, padding: '4px 6px', background: 'rgba(245,158,11,0.06)', borderRadius: 4, lineHeight: 1.5 }}>
                {d.qaDiagnosis}
              </div>
            </>
          )}
          {d.qaFailures.map((f, i) => (
            <div key={i}>
              <div
                onClick={() => setPlaygroundOpen(playgroundOpen === f.id ? null : f.id)}
                style={{
                  marginBottom: playgroundOpen === f.id ? 0 : 8,
                  padding: '6px 8px', background: 'rgba(239,68,68,0.04)', borderRadius: 5,
                  border: '1px solid rgba(239,68,68,0.08)', cursor: 'pointer',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
                  <span style={{ fontSize: 10, fontWeight: 600, color: '#e0e0f0' }}>{f.id} — {f.name || 'Unnamed'}</span>
                  <span style={{
                    fontSize: 8, padding: '1px 5px', borderRadius: 3,
                    background: f.severity === 'high' ? 'rgba(239,68,68,0.15)' : 'rgba(245,158,11,0.15)',
                    color: f.severity === 'high' ? '#ef4444' : '#f59e0b',
                    border: `1px solid ${f.severity === 'high' ? 'rgba(239,68,68,0.3)' : 'rgba(245,158,11,0.3)'}`,
                  }}>{f.severity}</span>
                  <span style={{ fontSize: 8, color: '#555', marginLeft: 'auto' }}>
                    {playgroundOpen === f.id ? '▲ close' : '▼ test'}
                  </span>
                </div>
                {f.expected && <div style={{ fontSize: 9, color: '#666' }}>Expected: <span style={{ color: '#4ade80' }}>{f.expected}</span></div>}
                {f.actual && <div style={{ fontSize: 9, color: '#666' }}>Actual: <span style={{ color: '#f87171' }}>{typeof f.actual === 'string' ? f.actual.slice(0, 120) : String(f.actual)}</span></div>}
                {f.details && <div style={{ fontSize: 9, color: '#777', marginTop: 2 }}>{f.details}</div>}
              </div>
              {playgroundOpen === f.id && <AssertionPlayground assertion={f} />}
            </div>
          ))}
          {NODE_SOURCE_FILES[node.id] && (
            <div style={{ fontSize: 9.5, color: '#555568', marginTop: 4, fontFamily: "'JetBrains Mono', monospace" }}>
              📁 {NODE_SOURCE_FILES[node.id]}
            </div>
          )}
        </div>
      )}

      {connected.length > 0 && (
        <div style={S.section}>
          <div style={S.title}>Connections ({connected.length})</div>
          {connected.map((edge, i) => {
            const dir = edge.source === node.id ? '→' : '←';
            const otherId = edge.source === node.id ? edge.target : edge.source;
            const other = nodes.find(n => n.id === otherId);
            return (
              <div key={i} style={{ fontSize: 10, color: edge.data?.broken ? '#f87171' : '#777', marginBottom: 3, cursor: 'pointer' }}>
                {dir} {other?.data?.label || otherId}{edge.data?.label ? `: ${edge.data.label}` : ''}{edge.data?.broken ? ' ⚠️' : ''}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
