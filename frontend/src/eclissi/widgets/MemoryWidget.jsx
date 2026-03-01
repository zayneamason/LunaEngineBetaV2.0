import React, { useState, useEffect } from 'react';

export default function MemoryWidget() {
  const [stats, setStats] = useState(null);
  const [extraction, setExtraction] = useState(null);

  useEffect(() => {
    const poll = async () => {
      try {
        const [sRes, eRes] = await Promise.all([
          fetch('/memory/stats'),
          fetch('/extraction/stats'),
        ]);
        if (sRes.ok) setStats(await sRes.json());
        if (eRes.ok) setExtraction(await eRes.json());
      } catch {}
    };
    poll();
    const id = setInterval(poll, 15000);
    return () => clearInterval(id);
  }, []);

  if (!stats) {
    return (
      <div style={{ color: 'var(--ec-text-faint)', fontSize: 12, textAlign: 'center', padding: 20 }}>
        Loading memory stats...
      </div>
    );
  }

  const nodes = stats.total_nodes || 0;
  const edges = stats.total_edges || 0;
  const entities = stats.nodes_by_type?.ENTITY || 0;
  const facts = stats.nodes_by_type?.FACT || 0;
  const settled = stats.nodes_by_lock_in?.settled || 0;
  const fluid = stats.nodes_by_lock_in?.fluid || 0;
  const total = settled + fluid || 1;
  const settledPct = ((settled / total) * 100).toFixed(0);

  const scribeRuns = extraction?.scribe?.extractions_count || 0;
  const objectsExtracted = extraction?.scribe?.objects_extracted || 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Stats grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        <div className="ec-glass-interactive" style={{ padding: '8px 10px', borderRadius: 6 }}>
          <div className="ec-font-label" style={{ fontSize: 9, color: 'var(--ec-text-faint)' }}>NODES</div>
          <div className="ec-font-mono" style={{ fontSize: 14, color: 'var(--ec-accent-memory)' }}>{nodes.toLocaleString()}</div>
        </div>
        <div className="ec-glass-interactive" style={{ padding: '8px 10px', borderRadius: 6 }}>
          <div className="ec-font-label" style={{ fontSize: 9, color: 'var(--ec-text-faint)' }}>EDGES</div>
          <div className="ec-font-mono" style={{ fontSize: 14, color: 'var(--ec-accent-memory)' }}>{edges.toLocaleString()}</div>
        </div>
        <div className="ec-glass-interactive" style={{ padding: '8px 10px', borderRadius: 6 }}>
          <div className="ec-font-label" style={{ fontSize: 9, color: 'var(--ec-text-faint)' }}>FACTS</div>
          <div className="ec-font-mono" style={{ fontSize: 14, color: 'var(--ec-text)' }}>{facts.toLocaleString()}</div>
        </div>
        <div className="ec-glass-interactive" style={{ padding: '8px 10px', borderRadius: 6 }}>
          <div className="ec-font-label" style={{ fontSize: 9, color: 'var(--ec-text-faint)' }}>ENTITIES</div>
          <div className="ec-font-mono" style={{ fontSize: 14, color: 'var(--ec-text)' }}>{entities}</div>
        </div>
      </div>

      {/* Lock-in bar */}
      <div>
        <div className="ec-font-label" style={{ fontSize: 9, color: 'var(--ec-text-faint)', marginBottom: 6 }}>
          LOCK-IN ({settledPct}% settled)
        </div>
        <div style={{ height: 6, borderRadius: 3, background: 'rgba(255,255,255,0.06)', overflow: 'hidden' }}>
          <div
            style={{
              width: `${settledPct}%`,
              height: '100%',
              background: 'var(--ec-accent-memory)',
              borderRadius: 3,
              transition: 'width 0.5s ease',
            }}
          />
        </div>
      </div>

      {/* Scribe stats */}
      <div className="ec-glass-interactive" style={{ padding: '8px 10px', borderRadius: 6 }}>
        <div className="ec-font-label" style={{ fontSize: 9, color: 'var(--ec-text-faint)', marginBottom: 4 }}>SCRIBE</div>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
          <span className="ec-font-body" style={{ color: 'var(--ec-text-soft)' }}>{scribeRuns} runs</span>
          <span className="ec-font-mono" style={{ color: 'var(--ec-text)' }}>{objectsExtracted} objects</span>
        </div>
      </div>
    </div>
  );
}
