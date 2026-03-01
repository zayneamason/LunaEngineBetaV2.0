import { useState, useEffect, useRef, useCallback } from 'react';

const POLL_INTERVAL = 2000; // 2s default
const ENDPOINTS = {
  status:       '/api/status',
  health:       '/api/health',
  context:      '/api/debug/context',
  memoryStats:  '/api/memory/stats',
  voice:        '/api/voice/status',
  extraction:   '/api/extraction/stats',
  consciousness:'/api/consciousness',
  ring:         '/api/ring/status',
};

async function safeFetch(url) {
  try {
    const r = await fetch(url, { signal: AbortSignal.timeout(3000) });
    if (!r.ok) return null;
    return await r.json();
  } catch { return null; }
}

export function useLiveData(interval = POLL_INTERVAL) {
  const [data, setData] = useState(null);
  const [connected, setConnected] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(null);
  const mountedRef = useRef(true);

  const poll = useCallback(async () => {
    const results = await Promise.all(
      Object.entries(ENDPOINTS).map(async ([key, url]) => [key, await safeFetch(url)])
    );
    if (!mountedRef.current) return;
    const d = Object.fromEntries(results);
    const anyOk = Object.values(d).some(v => v !== null);
    setConnected(anyOk);
    if (anyOk) {
      setData(d);
      setLastUpdate(new Date());
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    poll();
    const id = setInterval(poll, interval);
    return () => { mountedRef.current = false; clearInterval(id); };
  }, [poll, interval]);

  return { data, connected, lastUpdate };
}

// ── Count MEMORY-sourced items across ALL rings ──
// Memory items enter MIDDLE then get promoted to INNER by rebalance_rings()
// (promotion threshold: relevance >= 0.8, memory enters at 1.0)
// So MIDDLE=0 is EXPECTED when retrieval is working — check all rings.
function countMemoryItems(liveData) {
  // Method 1: /debug/context returns items with source field
  const ctx = liveData?.context;
  if (ctx?.items && Array.isArray(ctx.items)) {
    return ctx.items.filter(item => item.source === 'MEMORY' || item.source === 2).length;
  }
  // Method 2: /debug/context returns rings with items arrays
  if (ctx?.rings) {
    let count = 0;
    for (const ring of Object.values(ctx.rings)) {
      if (Array.isArray(ring.items)) {
        count += ring.items.filter(item => item.source === 'MEMORY' || item.source === 2).length;
      } else if (Array.isArray(ring)) {
        count += ring.filter(item => item.source === 'MEMORY' || item.source === 2).length;
      }
    }
    return count;
  }
  // Method 3: Fall back to /status context — check if budget usage is high
  // (>60% means memory is being injected alongside conversation)
  const statusCtx = liveData?.status?.context;
  if (statusCtx) {
    const pct = statusCtx.budget_used_pct || 0;
    const innerCount = statusCtx.rings?.INNER?.count || 0;
    // If INNER has many items and budget is >60%, memory is likely promoted there
    if (pct > 60 && innerCount > 3) return innerCount - 3; // rough estimate
  }
  return 0;
}

// ── Map live data onto node statuses ──
export function applyLiveData(nodes, liveData) {
  if (!liveData) return nodes;
  const { status, health, context, memoryStats, voice, extraction, consciousness, ring } = liveData;

  const nodeMap = Object.fromEntries(nodes.map(n => [n.id, n]));
  const memoryItemCount = countMemoryItems(liveData);
  const memoryWorking = memoryItemCount > 0;

  function patch(id, updates) {
    if (!nodeMap[id]) return;
    nodeMap[id] = {
      ...nodeMap[id],
      data: { ...nodeMap[id].data, ...updates, live: true, memoryItemCount },
    };
  }

  // ── Engine state ──
  if (status) {
    const st = status;
    const engineRunning = st.state === 'RUNNING';

    // Tick
    patch('tick', {
      body: `${(st.uptime_seconds/60)|0}m uptime\n${st.cognitive_ticks.toLocaleString()} ticks\n${st.events_processed} events`,
      status: engineRunning ? 'live' : 'broken',
    });

    // Buffer
    patch('buffer', {
      body: `${st.buffer_size} queued\nTurn ${st.current_turn}`,
      status: st.buffer_size > 10 ? 'warn' : 'live',
    });

    // Dispatch
    patch('dispatch', {
      body: `${st.events_processed} processed\n${st.messages_generated} generated`,
      status: 'live',
    });

    // Agentic
    if (st.agentic) {
      const a = st.agentic;
      patch('router', {
        body: `${a.direct_responses} DIRECT\n${a.planned_responses || 0} PLANNED`,
        status: a.is_processing ? 'warn' : 'live',
      });
      patch('agent_loop', {
        body: `${a.tasks_completed}/${a.tasks_started} complete\n${a.tasks_aborted} aborted`,
        status: a.is_processing ? 'warn' : 'live',
      });
      patch('director', {
        body: `Claude Sonnet\n${a.tasks_completed} generations`,
        status: 'live',
        tags: memoryWorking ? ['live'] : ['live', 'warn:blind'],
      });
    }

    // Context rings from /status
    if (st.context) {
      const c = st.context;
      const pct = c.budget_used_pct?.toFixed(0) || '0';
      const midCount = c.rings?.MIDDLE?.count || 0;
      const outCount = c.rings?.OUTER?.count || 0;

      patch('context', {
        body: `Budget: ${c.token_budget} tok\nUsed: ${c.total_tokens} (${pct}%)\nCORE:${c.rings?.CORE?.count||0} INNER:${c.rings?.INNER?.count||0}\nMIDDLE:${midCount} OUTER:${outCount}\nMemory items: ${memoryItemCount}${memoryWorking?' ✅':' ⚠️'}`,
        status: memoryWorking ? 'live' : 'warn',
        tags: memoryWorking
          ? ['live', `live:${memoryItemCount}_memory_items`]
          : ['warn:no_memory_items'],
      });

      patch('ring_core', {
        body: `${c.rings?.CORE?.count||0} item · ${c.rings?.CORE?.tokens||0} tok\nIdentity prompt`,
        status: 'live',
      });
      patch('ring_inner', {
        body: `${c.rings?.INNER?.count||0} items · ${c.rings?.INNER?.tokens||0} tok\n${memoryWorking?'Conv + promoted memory':'Conversation only'}`,
        status: 'live',
      });
      patch('ring_mid', {
        body: `${midCount} items · ${c.rings?.MIDDLE?.tokens||0} tok\n${midCount===0?(memoryWorking?'Promoted to INNER ✅':'NO MEMORY ⚠️'):'Memory loaded'}`,
        status: midCount === 0 && !memoryWorking ? 'broken' : 'live',
        nodeType: midCount === 0 && !memoryWorking ? 'broken' : 'context',
      });
      patch('ring_outer', {
        body: `${outCount} items · ${c.rings?.OUTER?.tokens||0} tok\n${outCount===0?'Empty (normal)':'Overflow'}`,
        status: 'live',
        nodeType: 'context',
      });

      // System prompt
      patch('sysprompt', {
        body: `_build_system_prompt()\nIdentity+History\nMemory: ${memoryWorking?'✅':'EMPTY ⚠️'}`,
        status: memoryWorking ? 'live' : 'warn',
        tags: memoryWorking ? ['live'] : ['warn:no_memory_section'],
      });
    }

    // Actors list → identity
    if (st.actors?.includes('identity')) {
      patch('identity', { status: 'live' });
    }
    if (st.identity_state) {
      const id = st.identity_state;
      patch('identity', {
        body: `${id.entity_name || 'unknown'} → ${id.tier || '?'}\nConf: ${id.confidence?.toFixed(2) || '?'}`,
        status: 'live',
      });
    }
  }

  // ── Memory Stats ──
  if (memoryStats) {
    const m = memoryStats;
    const total = m.total_nodes || 0;
    const edges = m.total_edges || 0;
    const facts = m.nodes_by_type?.FACT || 0;
    const entities = m.nodes_by_type?.ENTITY || 0;

    patch('matrix_db', {
      body: `${total.toLocaleString()} nodes · ${edges.toLocaleString()} edges\n${facts.toLocaleString()} FACTs · ${entities} ENTITYs\nFTS5 + SQLite ✅`,
      status: 'live',
    });

    patch('mem_ret', {
      body: `hybrid_search()\n${memoryWorking ? `RETURNING DATA ✅ (${memoryItemCount} items)` : 'WAITING FOR QUERY'}\n${total.toLocaleString()} nodes available`,
      status: memoryWorking ? 'live' : 'idle',
      nodeType: memoryWorking ? 'memory' : 'process',
    });
    patch('matrix_actor', {
      body: `get_context() → ${memoryWorking ? '✅' : 'idle'}\nScope: global\nmax_tokens: 1500`,
      status: memoryWorking ? 'live' : 'idle',
      nodeType: memoryWorking ? 'memory' : 'process',
    });

    // Scribe + Librarian from memory distribution
    patch('librarian', {
      body: `Dedup + file\n${m.nodes_by_lock_in?.settled||0} settled\n${m.nodes_by_lock_in?.fluid||0} fluid`,
      status: 'live',
    });
  }

  // ── Extraction stats ──
  if (extraction) {
    const ex = extraction;
    if (ex.scribe) {
      patch('scribe', {
        body: `Extract FACT/ENTITY\n${ex.scribe.extractions_count} runs · ${ex.scribe.objects_extracted} objects\nStack: ${ex.scribe.stack_size}`,
        status: ex.scribe.stack_size > 10 ? 'warn' : 'live',
      });
    }
  }

  // ── Health ──
  if (health) {
    // Dataroom — always works via direct SQL
    patch('dataroom', {
      body: `SQL: WHERE DOCUMENT\nKeyword match ✅\nPipeline: ${health.pipeline?.connected ? 'connected' : 'disconnected'}`,
      status: 'live',
    });
  }

  // ── Voice ──
  if (voice) {
    patch('voice', {
      body: `${voice.stt_provider === 'none' ? 'STT: off' : voice.stt_provider}\n${voice.running ? 'Recording' : 'Idle'}`,
      status: voice.running ? 'live' : 'idle',
    });
    patch('tts', {
      body: `${voice.tts_provider === 'none' ? 'TTS: off' : voice.tts_provider}\n${voice.turn_count} turns`,
      status: voice.running ? 'live' : 'idle',
    });
  }

  // ── Consciousness ──
  if (consciousness) {
    const c = consciousness;
    const topTrait = c.top_traits?.[0]?.[0] || 'neutral';
    patch('consciousness', {
      body: `Mood: ${c.mood}\nCoherence: ${(c.coherence*100).toFixed(0)}%\n${topTrait} · ${c.tick_count?.toLocaleString()||0} ticks`,
      status: 'live',
    });
  }

  // ── Ring buffer ──
  if (ring) {
    patch('hist_mgr', {
      body: `${ring.current_turns}/${ring.max_turns} turns\nTopics: ${(ring.topics||[]).slice(0,3).join(', ')}`,
      status: 'live',
    });
    patch('hist_load', {
      body: `${ring.current_turns} conv turns\nINNER ring only`,
      status: 'warn',
    });
  }

  // ── Overdrive / Scout / Watchdog / Reconcile — derived from engine state ──
  if (status?.agentic) {
    const a = status.agentic;
    patch('scout', {
      body: `Quality guard\n${a.overdrive_triggers || 0} triggers\n${a.confab_flags || 0} confab flags`,
      status: 'live',
    });
    patch('overdrive', {
      body: `Retry enriched ctx\n${memoryWorking ? 'Retrieval working ✅' : 'Retrieval idle'}`,
      status: memoryWorking ? 'live' : 'warn',
      tags: memoryWorking ? ['live'] : ['warn:no_retrieval'],
    });
    patch('watchdog', {
      body: `5s interval\n${a.tasks_aborted} aborts`,
      status: 'live',
    });
    patch('reconcile', {
      body: `Self-correction\n${memoryWorking ? 'Ready' : 'Waiting for retrieval'}`,
      status: memoryWorking ? 'live' : 'idle',
    });
  }

  // ── Text/Persona paths stay status-quo unless data says otherwise ──
  patch('text', { status: 'live' });
  patch('stream', { status: 'warn' });
  patch('persona', { status: 'warn' });
  patch('textout', { status: 'live' });
  // Subtasks
  patch('subtasks', { status: 'live' });

  return Object.values(nodeMap);
}

// Map live data into edge patches based on memory retrieval status
export function applyLiveEdges(edges, liveData) {
  if (!liveData) return edges;
  const memoryItemCount = countMemoryItems(liveData);
  const memoryWorking = memoryItemCount > 0;

  return edges.map(e => {
    if (memoryWorking) {
      // Memory retrieval is working — un-break edges and update labels
      if (e.id === 'e-mem_ret-matrix_actor') {
        return { ...e, data: { ...e.data, broken: false, animated: true, label: 'hybrid_search() ✅' } };
      }
      if (e.id === 'e-mem_ret-context') {
        return { ...e, data: { ...e.data, broken: false, animated: true, label: 'add(MEMORY) ✅' } };
      }
      if (e.id === 'e-ctx-mid' || e.id === 'e-ctx-outer') {
        return { ...e, data: { ...e.data, broken: false } };
      }
    }
    return e;
  });
}
