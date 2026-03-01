import React from 'react';
import { typeStyles, statusColors } from './data';

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

function LiveMetrics({ nodeId, liveData, memoryItemCount }) {
  if (!liveData) return null;
  const { status, memoryStats, consciousness, ring, extraction, voice } = liveData;

  // Engine-wide metrics for tick node
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

  // Memory stats for matrix_db
  if (nodeId === 'matrix_db' && memoryStats) {
    const m = memoryStats;
    return (
      <div style={S.section}>
        <div style={{ ...S.title, display: 'flex', alignItems: 'center', gap: 6 }}>Live Metrics <LiveBadge /></div>
        <MetricRow label="Total Nodes" value={m.total_nodes?.toLocaleString()} />
        <MetricRow label="Total Edges" value={m.total_edges?.toLocaleString()} />
        <MetricRow label="FACTs" value={m.nodes_by_type?.FACT?.toLocaleString()} />
        <MetricRow label="ENTITYs" value={m.nodes_by_type?.ENTITY} />
        <MetricRow label="DOCUMENTs" value={m.nodes_by_type?.DOCUMENT} />
        <MetricRow label="CONVERSATIONs" value={m.nodes_by_type?.CONVERSATION_TURN?.toLocaleString()} />
        <MetricRow label="Settled" value={m.nodes_by_lock_in?.settled} color="#22c55e" />
        <MetricRow label="Fluid" value={m.nodes_by_lock_in?.fluid?.toLocaleString()} color="#f59e0b" />
        <MetricRow label="Drifting" value={m.nodes_by_lock_in?.drifting?.toLocaleString()} color="#ef4444" />
        <MetricRow label="Avg Lock-in" value={`${(m.avg_lock_in * 100).toFixed(1)}%`} />
      </div>
    );
  }

  // Memory retrieval nodes — show memory item count
  if ((nodeId === 'mem_ret' || nodeId === 'matrix_actor') && memoryStats) {
    const m = memoryStats;
    // memoryItemCount is injected by applyLiveData into node data
    return (
      <div style={S.section}>
        <div style={{ ...S.title, display: 'flex', alignItems: 'center', gap: 6 }}>Live Metrics <LiveBadge /></div>
        <MetricRow label="Memory Items in Context" value={memoryItemCount ?? '?'} color={memoryItemCount > 0 ? '#22c55e' : '#ef4444'} />
        <MetricRow label="Total Nodes in DB" value={m.total_nodes?.toLocaleString()} />
        <MetricRow label="Total Edges" value={m.total_edges?.toLocaleString()} />
        <MetricRow label="FACTs" value={m.nodes_by_type?.FACT?.toLocaleString()} />
        <MetricRow label="ENTITYs" value={m.nodes_by_type?.ENTITY} />
        <MetricRow label="Search Method" value="hybrid (FTS5+semantic)" color="#818cf8" />
      </div>
    );
  }

  // Context rings
  if (nodeId === 'context' && status?.context) {
    const c = status.context;
    return (
      <div style={S.section}>
        <div style={{ ...S.title, display: 'flex', alignItems: 'center', gap: 6 }}>Live Metrics <LiveBadge /></div>
        <MetricRow label="Token Budget" value={`${c.total_tokens} / ${c.token_budget}`} />
        <MetricRow label="Budget Used" value={`${c.budget_used_pct?.toFixed(1)}%`} color={c.budget_used_pct < 50 ? '#f59e0b' : '#22c55e'} />
        <MetricRow label="Memory Items (all rings)" value={memoryItemCount ?? '?'} color={memoryItemCount > 0 ? '#22c55e' : '#ef4444'} />
        <MetricRow label="CORE Items" value={c.rings?.CORE?.count} color="#22c55e" />
        <MetricRow label="INNER Items" value={c.rings?.INNER?.count} color="#22c55e" />
        <MetricRow label="MIDDLE Items" value={c.rings?.MIDDLE?.count} color="#22c55e" />
        <MetricRow label="OUTER Items" value={c.rings?.OUTER?.count} color="#22c55e" />
        <MetricRow label="Total Added" value={c.total_added} />
        <MetricRow label="Total Evicted" value={c.total_evicted} />
      </div>
    );
  }

  // Consciousness
  if (nodeId === 'consciousness' && consciousness) {
    const c = consciousness;
    return (
      <div style={S.section}>
        <div style={{ ...S.title, display: 'flex', alignItems: 'center', gap: 6 }}>Live Metrics <LiveBadge /></div>
        <MetricRow label="Mood" value={c.mood} />
        <MetricRow label="Coherence" value={`${(c.coherence * 100).toFixed(0)}%`} />
        <MetricRow label="Attention Topics" value={c.attention_topics} />
        {c.top_traits?.slice(0, 3).map(([trait, score], i) => (
          <MetricRow key={i} label={`Trait: ${trait}`} value={`${(score * 100).toFixed(0)}%`} />
        ))}
        <MetricRow label="Tick Count" value={c.tick_count?.toLocaleString()} />
      </div>
    );
  }

  // Ring buffer / history
  if ((nodeId === 'hist_mgr' || nodeId === 'hist_load') && ring) {
    return (
      <div style={S.section}>
        <div style={{ ...S.title, display: 'flex', alignItems: 'center', gap: 6 }}>Live Metrics <LiveBadge /></div>
        <MetricRow label="Turns" value={`${ring.current_turns} / ${ring.max_turns}`} />
        <MetricRow label="Topics" value={(ring.topics || []).slice(0, 5).join(', ')} />
      </div>
    );
  }

  // Extraction
  if ((nodeId === 'scribe' || nodeId === 'librarian') && extraction) {
    const section = nodeId === 'scribe' ? extraction.scribe : extraction.librarian;
    if (!section) return null;
    return (
      <div style={S.section}>
        <div style={{ ...S.title, display: 'flex', alignItems: 'center', gap: 6 }}>Live Metrics <LiveBadge /></div>
        {Object.entries(section).map(([k, v]) => (
          <MetricRow key={k} label={k.replace(/_/g, ' ')} value={typeof v === 'number' ? v.toLocaleString() : String(v)} />
        ))}
      </div>
    );
  }

  // Voice
  if ((nodeId === 'voice' || nodeId === 'tts') && voice) {
    return (
      <div style={S.section}>
        <div style={{ ...S.title, display: 'flex', alignItems: 'center', gap: 6 }}>Live Metrics <LiveBadge /></div>
        <MetricRow label="Running" value={voice.running ? 'YES' : 'NO'} color={voice.running ? '#22c55e' : '#666'} />
        <MetricRow label="Recording" value={voice.recording ? 'YES' : 'NO'} />
        <MetricRow label="Hands Free" value={voice.hands_free ? 'YES' : 'NO'} />
        <MetricRow label="STT Provider" value={voice.stt_provider} />
        <MetricRow label="TTS Provider" value={voice.tts_provider} />
        <MetricRow label="Persona Connected" value={voice.persona_connected ? 'YES' : 'NO'} />
        <MetricRow label="Turn Count" value={voice.turn_count} />
      </div>
    );
  }

  // Agentic stats
  if ((nodeId === 'router' || nodeId === 'agent_loop' || nodeId === 'director') && status?.agentic) {
    const a = status.agentic;
    return (
      <div style={S.section}>
        <div style={{ ...S.title, display: 'flex', alignItems: 'center', gap: 6 }}>Live Metrics <LiveBadge /></div>
        <MetricRow label="Processing" value={a.is_processing ? 'ACTIVE' : 'IDLE'} color={a.is_processing ? '#f59e0b' : '#22c55e'} />
        <MetricRow label="Tasks Started" value={a.tasks_started} />
        <MetricRow label="Tasks Completed" value={a.tasks_completed} />
        <MetricRow label="Tasks Aborted" value={a.tasks_aborted} />
        <MetricRow label="Direct Responses" value={a.direct_responses} />
        {a.current_goal && <MetricRow label="Current Goal" value={a.current_goal} />}
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

  return (
    <div style={{
      position: 'fixed', right: 0, top: 0, width: 380, height: '100vh',
      background: '#0e0e18', borderLeft: '1px solid rgba(255,255,255,0.06)',
      zIndex: 100, overflowY: 'auto', padding: '20px 18px',
      fontFamily: "'JetBrains Mono', monospace",
      boxShadow: '-8px 0 30px rgba(0,0,0,0.5)',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 18 }}>
        <span style={{ fontSize: 20 }}>{d.icon}</span>
        <span style={{
          fontSize: 13, fontWeight: 600, color: t.accent,
          textTransform: 'uppercase', letterSpacing: '0.5px',
        }}>{d.label}</span>
        {d.live && <LiveBadge />}
        <span onClick={onClose} style={{
          marginLeft: 'auto', cursor: 'pointer', color: '#555',
          fontSize: 16, padding: '2px 6px', borderRadius: 4,
        }}>✕</span>
      </div>

      {/* Status */}
      <div style={S.section}>
        <div style={S.title}>Status</div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
          {(d.tags || [d.status]).map((tag, i) => {
            const c = tag.includes('live') ? '#22c55e'
              : tag.includes('broken') ? '#ef4444'
              : tag.includes('warn') ? '#f59e0b' : '#818cf8';
            return (
              <span key={i} style={{
                fontSize: 9.5, padding: '2px 8px', borderRadius: 4,
                background: `${c}15`, color: c, border: `1px solid ${c}33`,
              }}>{tag}</span>
            );
          })}
        </div>
      </div>

      {/* Live Metrics */}
      <LiveMetrics nodeId={node.id} liveData={liveData} memoryItemCount={d.memoryItemCount} />

      {/* Description */}
      <div style={S.section}>
        <div style={S.title}>Description</div>
        <pre style={{
          fontSize: 10.5, color: '#aaa', lineHeight: 1.6,
          whiteSpace: 'pre-wrap', wordBreak: 'break-word', margin: 0,
        }}>{d.detail?.desc}</pre>
      </div>

      {/* Source */}
      <div style={S.section}>
        <div style={S.title}>Source File</div>
        <pre style={{ fontSize: 10.5, color: '#818cf8', margin: 0 }}>{d.detail?.file}</pre>
      </div>

      {/* Connections */}
      {connected.length > 0 && (
        <div style={S.section}>
          <div style={S.title}>Connections ({connected.length})</div>
          {connected.map((edge, i) => {
            const dir = edge.source === node.id ? '→' : '←';
            const otherId = edge.source === node.id ? edge.target : edge.source;
            const other = nodes.find(n => n.id === otherId);
            return (
              <div key={i} style={{
                fontSize: 10, color: edge.data?.broken ? '#f87171' : '#777',
                marginBottom: 3, cursor: 'pointer',
              }}>
                {dir} {other?.data?.label || otherId}
                {edge.data?.label ? `: ${edge.data.label}` : ''}
                {edge.data?.broken ? ' ⚠️' : ''}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
