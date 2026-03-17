import React, { useState, useEffect, useCallback } from 'react';
import TabButton from './components/TabButton';
import PipelineOverlay from './components/PipelineOverlay';

const QA_ACCENT = 'var(--ec-accent-qa)';
const MONO = "'JetBrains Mono','SF Mono',monospace";
const LABEL = "'Bebas Neue',system-ui,sans-serif";
const BODY = "'DM Sans',system-ui,sans-serif";
const TABS = ['health', 'history', 'assertions', 'bugs', 'events'];

// ── Helpers ──────────────────────────────────────────────────

function Dot({ ok, size = 6 }) {
  return (
    <div style={{
      width: size, height: size, borderRadius: '50%', flexShrink: 0,
      background: ok ? '#22c55e' : '#f87171',
    }} />
  );
}

function Badge({ label, color }) {
  return (
    <span style={{
      fontSize: 8, fontWeight: 700, letterSpacing: 0.5, padding: '2px 6px', borderRadius: 3,
      color, background: `${color}15`,
    }}>
      {label}
    </span>
  );
}

function TimeAgo({ ts }) {
  if (!ts) return null;
  const d = new Date(ts);
  const now = new Date();
  const diffMs = now - d;
  const diffMin = Math.floor(diffMs / 60000);
  const diffHr = Math.floor(diffMin / 60);
  let text;
  if (diffMin < 1) text = 'just now';
  else if (diffMin < 60) text = `${diffMin}m ago`;
  else if (diffHr < 24) text = `${diffHr}h ago`;
  else text = d.toLocaleDateString();
  return (
    <span style={{ fontSize: 9, fontFamily: MONO, color: 'var(--ec-text-faint)' }} title={d.toLocaleString()}>
      {text}
    </span>
  );
}

// ── Panel A: Health Dashboard ────────────────────────────────

function HealthPanel({ health, lastReport }) {
  const passRate = health?.pass_rate != null ? health.pass_rate * 100 : null;
  const totalRuns = health?.total_24h || 0;
  const failedRuns = health?.failed_24h || 0;
  const failingBugs = health?.failing_bugs || 0;
  const topFailures = health?.top_failures || [];
  const systemEvents = health?.system_events_24h || 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Top metrics */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
        <div style={{ textAlign: 'center', padding: '16px 0' }}>
          <div style={{
            fontSize: 48, fontWeight: 300, fontFamily: LABEL,
            color: passRate == null ? 'var(--ec-text-faint)'
              : passRate >= 90 ? '#22c55e'
              : passRate >= 70 ? '#f59e0b'
              : '#ef4444',
          }}>
            {passRate != null ? `${passRate.toFixed(0)}%` : '\u2014'}
          </div>
          <div style={{ fontSize: 9, fontFamily: LABEL, letterSpacing: 1.5, color: 'var(--ec-text-faint)' }}>
            PASS RATE
          </div>
        </div>
        <div style={{ textAlign: 'center', padding: '16px 0' }}>
          <div style={{ fontSize: 48, fontWeight: 300, fontFamily: LABEL, color: 'var(--ec-text-soft)' }}>
            {totalRuns}
          </div>
          <div style={{ fontSize: 9, fontFamily: LABEL, letterSpacing: 1.5, color: 'var(--ec-text-faint)' }}>
            RUNS (24H)
          </div>
        </div>
        <div style={{ textAlign: 'center', padding: '16px 0' }}>
          <div style={{
            fontSize: 48, fontWeight: 300, fontFamily: LABEL,
            color: failedRuns > 0 ? '#ef4444' : '#22c55e',
          }}>
            {failedRuns}
          </div>
          <div style={{ fontSize: 9, fontFamily: LABEL, letterSpacing: 1.5, color: 'var(--ec-text-faint)' }}>
            FAILED (24H)
          </div>
        </div>
      </div>

      {/* Top failing assertions */}
      {topFailures.length > 0 && (
        <div>
          <div style={{ fontSize: 9, fontFamily: LABEL, letterSpacing: 1.5, color: 'var(--ec-text-faint)', marginBottom: 8 }}>
            TOP FAILURES (24H)
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {topFailures.map((f) => (
              <div key={f.id} style={{
                display: 'flex', alignItems: 'center', gap: 8, padding: '5px 8px', borderRadius: 4,
                background: 'rgba(239,68,68,0.04)', border: '1px solid rgba(239,68,68,0.08)',
              }}>
                <Badge label={f.id} color="#ef4444" />
                <span style={{ fontSize: 11, color: 'var(--ec-text-soft)', flex: 1, fontFamily: BODY }}>
                  {f.name}
                </span>
                <span style={{ fontSize: 11, fontFamily: MONO, color: '#ef4444', fontWeight: 600 }}>
                  {f.count}x
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Status row */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 6, padding: '4px 10px', borderRadius: 4,
          background: failingBugs > 0 ? 'rgba(239,68,68,0.06)' : 'rgba(34,197,94,0.06)',
          border: `1px solid ${failingBugs > 0 ? 'rgba(239,68,68,0.12)' : 'rgba(34,197,94,0.12)'}`,
        }}>
          <span style={{ fontSize: 9, fontFamily: LABEL, letterSpacing: 1, color: 'var(--ec-text-faint)' }}>BUGS</span>
          <span style={{ fontSize: 11, fontFamily: MONO, fontWeight: 600, color: failingBugs > 0 ? '#ef4444' : '#22c55e' }}>
            {failingBugs} open
          </span>
        </div>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 6, padding: '4px 10px', borderRadius: 4,
          background: systemEvents > 0 ? 'rgba(251,146,60,0.06)' : 'rgba(34,197,94,0.06)',
          border: `1px solid ${systemEvents > 0 ? 'rgba(251,146,60,0.12)' : 'rgba(34,197,94,0.12)'}`,
        }}>
          <span style={{ fontSize: 9, fontFamily: LABEL, letterSpacing: 1, color: 'var(--ec-text-faint)' }}>EVENTS</span>
          <span style={{ fontSize: 11, fontFamily: MONO, fontWeight: 600, color: systemEvents > 0 ? '#fb923c' : '#22c55e' }}>
            {systemEvents} (24h)
          </span>
        </div>
      </div>

      {/* Last report pipeline */}
      <PipelineOverlay report={lastReport} />
    </div>
  );
}

// ── Panel B: Report History ─────────────────────────────────

function HistoryPanel() {
  const [reports, setReports] = useState([]);
  const [expanded, setExpanded] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const res = await fetch('/qa/history?limit=25');
        if (res.ok && !cancelled) setReports(await res.json());
      } catch {}
      if (!cancelled) setLoading(false);
    };
    load();
    const id = setInterval(load, 10000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  if (loading) {
    return <div style={{ color: 'var(--ec-text-faint)', fontSize: 11, textAlign: 'center', padding: 24 }}>Loading history...</div>;
  }

  if (reports.length === 0) {
    return <div style={{ color: 'var(--ec-text-faint)', fontSize: 11, textAlign: 'center', padding: 24 }}>No QA reports yet. Send a message to Luna to generate one.</div>;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      {reports.map((r) => {
        const isExpanded = expanded === r.inference_id;
        const passed = r.passed;
        const failedAssertions = (r.assertions || []).filter(a => !a.passed);
        const passedAssertions = (r.assertions || []).filter(a => a.passed);
        const ctx = r.context || {};

        return (
          <div key={r.inference_id}>
            {/* Summary row */}
            <div
              onClick={() => setExpanded(isExpanded ? null : r.inference_id)}
              style={{
                display: 'flex', alignItems: 'center', gap: 8,
                padding: '8px 10px', borderRadius: 6, cursor: 'pointer',
                background: passed ? 'rgba(34,197,94,0.04)' : 'rgba(239,68,68,0.04)',
                border: `1px solid ${isExpanded
                  ? (passed ? 'rgba(34,197,94,0.25)' : 'rgba(239,68,68,0.25)')
                  : 'transparent'}`,
                transition: 'border-color 0.2s',
              }}
              onMouseEnter={e => { if (!isExpanded) e.currentTarget.style.borderColor = 'rgba(255,255,255,0.08)'; }}
              onMouseLeave={e => { if (!isExpanded) e.currentTarget.style.borderColor = 'transparent'; }}
            >
              <Dot ok={passed} size={8} />
              <span style={{ fontSize: 10, fontFamily: MONO, color: 'var(--ec-text-faint)', width: 60 }}>
                {r.inference_id}
              </span>
              <span style={{ fontSize: 11, color: 'var(--ec-text-soft)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontFamily: BODY }}>
                {r.query ? `"${r.query}"` : '—'}
              </span>
              {!passed && (
                <span style={{ fontSize: 9, fontFamily: MONO, color: '#ef4444', fontWeight: 600 }}>
                  {r.failed_count} fail
                </span>
              )}
              <Badge
                label={r.route || 'UNKNOWN'}
                color={r.route === 'DELEGATED' ? '#818cf8' : '#f59e0b'}
              />
              <TimeAgo ts={r.timestamp} />
              <span style={{ fontSize: 10, color: 'var(--ec-text-faint)' }}>{isExpanded ? '▲' : '▼'}</span>
            </div>

            {/* Expanded detail */}
            {isExpanded && (
              <div style={{
                padding: '12px 14px', marginTop: 2, marginBottom: 4, borderRadius: 6,
                background: 'rgba(255,255,255,0.02)', border: '1px solid var(--ec-border)',
              }}>
                {/* Forensic metadata */}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 12 }}>
                  <MetaChip label="Provider" value={r.provider_used || ctx.provider_used || '—'} />
                  <MetaChip label="Latency" value={r.latency_ms ? `${Math.round(r.latency_ms)}ms` : '—'} />
                  <MetaChip label="Tokens" value={ctx.output_tokens ? `${ctx.input_tokens || '?'}→${ctx.output_tokens}` : '—'} />
                  <MetaChip label="Route" value={r.route || '—'} />
                  <MetaChip label="Time" value={r.timestamp ? new Date(r.timestamp).toLocaleString() : '—'} />
                </div>

                {/* Request chain timeline */}
                {ctx.request_chain && ctx.request_chain.length > 0 && (
                  <div style={{ marginBottom: 12 }}>
                    <div style={{ fontSize: 9, fontFamily: LABEL, letterSpacing: 1.5, color: 'var(--ec-text-faint)', marginBottom: 6 }}>
                      REQUEST CHAIN
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                      {ctx.request_chain.map((step, i) => (
                        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '3px 8px', borderRadius: 4, background: 'rgba(255,255,255,0.02)' }}>
                          <span style={{ fontSize: 9, fontFamily: MONO, color: '#818cf8', width: 55, textAlign: 'right' }}>
                            {step.time_ms != null ? `${Math.round(step.time_ms)}ms` : ''}
                          </span>
                          <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#818cf8', flexShrink: 0 }} />
                          <span style={{ fontSize: 10, fontFamily: MONO, color: 'var(--ec-text-faint)', width: 60 }}>
                            {step.step}
                          </span>
                          <span style={{ fontSize: 10, color: 'var(--ec-text-soft)', fontFamily: BODY }}>
                            {step.detail}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Failed assertions with expected/actual */}
                {failedAssertions.length > 0 && (
                  <div style={{ marginBottom: 12 }}>
                    <div style={{ fontSize: 9, fontFamily: LABEL, letterSpacing: 1.5, color: '#ef4444', marginBottom: 6 }}>
                      FAILED ({failedAssertions.length})
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                      {failedAssertions.map(a => (
                        <div key={a.id} style={{
                          padding: '6px 10px', borderRadius: 6,
                          background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.12)',
                        }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                            <Badge label={a.id} color="#ef4444" />
                            <span style={{ fontSize: 11, color: '#e5e7eb', fontFamily: BODY }}>{a.name}</span>
                            <Badge label={a.severity} color={a.severity === 'critical' ? '#ef4444' : a.severity === 'high' ? '#f59e0b' : '#9ca3af'} />
                          </div>
                          <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '2px 8px', fontSize: 10, fontFamily: MONO }}>
                            <span style={{ color: 'var(--ec-text-faint)' }}>expected:</span>
                            <span style={{ color: '#22c55e' }}>{a.expected || '—'}</span>
                            <span style={{ color: 'var(--ec-text-faint)' }}>actual:</span>
                            <span style={{ color: '#ef4444' }}>{a.actual || '—'}</span>
                            {a.details && <>
                              <span style={{ color: 'var(--ec-text-faint)' }}>details:</span>
                              <span style={{ color: 'var(--ec-text-soft)' }}>{a.details}</span>
                            </>}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Passed assertions (collapsed) */}
                {passedAssertions.length > 0 && (
                  <div style={{ marginBottom: 8 }}>
                    <div style={{ fontSize: 9, fontFamily: LABEL, letterSpacing: 1.5, color: '#22c55e', marginBottom: 4 }}>
                      PASSED ({passedAssertions.length})
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                      {passedAssertions.map(a => (
                        <span key={a.id} style={{
                          fontSize: 9, fontFamily: MONO, padding: '2px 6px', borderRadius: 3,
                          background: 'rgba(34,197,94,0.08)', color: '#22c55e',
                        }}>
                          {a.id}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Diagnosis */}
                {r.diagnosis && (
                  <div style={{
                    fontSize: 10, color: QA_ACCENT, lineHeight: 1.5, fontFamily: BODY,
                    padding: '8px 10px', borderRadius: 6,
                    background: 'rgba(248,113,113,0.06)', border: '1px solid rgba(248,113,113,0.12)',
                  }}>
                    {r.diagnosis}
                  </div>
                )}

                {/* Response preview */}
                {ctx.final_response && (
                  <div style={{ marginTop: 8 }}>
                    <div style={{ fontSize: 9, fontFamily: LABEL, letterSpacing: 1.5, color: 'var(--ec-text-faint)', marginBottom: 4 }}>
                      RESPONSE
                    </div>
                    <div style={{
                      fontSize: 11, color: 'var(--ec-text-soft)', fontFamily: BODY, lineHeight: 1.5,
                      padding: '8px 10px', borderRadius: 6, background: 'rgba(255,255,255,0.02)',
                      maxHeight: 120, overflow: 'auto',
                    }}>
                      {ctx.final_response}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function MetaChip({ label, value }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 4, padding: '3px 8px', borderRadius: 4,
      background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)',
    }}>
      <span style={{ fontSize: 8, fontFamily: LABEL, letterSpacing: 1, color: 'var(--ec-text-faint)' }}>{label}</span>
      <span style={{ fontSize: 10, fontFamily: MONO, color: 'var(--ec-text-soft)' }}>{value}</span>
    </div>
  );
}

// ── Panel C: Assertion Manager ───────────────────────────────

function AssertionsPanel() {
  const [assertions, setAssertions] = useState([]);
  const [lastReport, setLastReport] = useState(null);
  const [expanded, setExpanded] = useState(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const [aRes, rRes] = await Promise.all([
          fetch('/qa/assertions'),
          fetch('/qa/last'),
        ]);
        if (aRes.ok && !cancelled) setAssertions(await aRes.json());
        if (rRes.ok && !cancelled) {
          const data = await rRes.json();
          if (!data.error) setLastReport(data);
        }
      } catch {}
    };
    load();
    const id = setInterval(load, 10000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  const toggle = useCallback(async (assertionId, enabled) => {
    try {
      await fetch(`/qa/assertions/${assertionId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled }),
      });
      setAssertions(prev => prev.map(a => a.id === assertionId ? { ...a, enabled } : a));
    } catch {}
  }, []);

  // Merge last report results into assertion list
  const reportMap = {};
  if (lastReport?.assertions) {
    for (const a of lastReport.assertions) reportMap[a.id] = a;
  }

  // Group by category
  const grouped = {};
  for (const a of assertions) {
    const cat = a.category || 'other';
    if (!grouped[cat]) grouped[cat] = [];
    grouped[cat].push(a);
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {lastReport && (
        <div style={{ fontSize: 9, fontFamily: BODY, color: 'var(--ec-text-faint)', padding: '4px 0' }}>
          Results from last inference ({lastReport.inference_id}) — <TimeAgo ts={lastReport.timestamp} />
        </div>
      )}
      {Object.entries(grouped).map(([cat, list]) => (
        <div key={cat}>
          <div style={{
            fontSize: 9, fontFamily: LABEL, letterSpacing: 1.5,
            color: 'var(--ec-text-faint)', marginBottom: 6, textTransform: 'uppercase',
          }}>
            {cat}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {list.map(a => {
              const result = reportMap[a.id];
              const isExpanded = expanded === a.id;
              return (
                <div key={a.id}>
                  <div
                    onClick={() => setExpanded(isExpanded ? null : a.id)}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 8,
                      padding: '6px 10px', borderRadius: 6, cursor: 'pointer',
                      background: a.enabled ? 'rgba(255,255,255,0.02)' : 'rgba(255,255,255,0.01)',
                      opacity: a.enabled ? 1 : 0.5,
                    }}
                  >
                    {/* Last result indicator */}
                    {result ? (
                      <Dot ok={result.passed} size={8} />
                    ) : (
                      <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'rgba(255,255,255,0.1)', flexShrink: 0 }} />
                    )}

                    {/* Toggle */}
                    <div
                      onClick={(e) => { e.stopPropagation(); toggle(a.id, !a.enabled); }}
                      style={{
                        width: 28, height: 16, borderRadius: 8, cursor: 'pointer',
                        background: a.enabled ? '#22c55e' : 'rgba(255,255,255,0.1)',
                        transition: 'background 0.2s ease', position: 'relative', flexShrink: 0,
                      }}
                    >
                      <div style={{
                        width: 12, height: 12, borderRadius: '50%', background: '#fff',
                        position: 'absolute', top: 2,
                        left: a.enabled ? 14 : 2, transition: 'left 0.2s ease',
                      }} />
                    </div>

                    <Badge label={a.id} color={a.severity === 'critical' ? '#ef4444' : a.severity === 'high' ? '#f59e0b' : '#9ca3af'} />
                    <span style={{ fontSize: 11, color: 'var(--ec-text-soft)', flex: 1, fontFamily: BODY }}>
                      {a.name}
                    </span>
                    <span style={{ fontSize: 9, color: 'var(--ec-text-faint)', fontFamily: MONO }}>
                      {a.check_type}
                    </span>
                    <span style={{ fontSize: 10, color: 'var(--ec-text-faint)' }}>{isExpanded ? '▲' : '▼'}</span>
                  </div>

                  {/* Expanded detail */}
                  {isExpanded && (
                    <div style={{
                      padding: '8px 12px', marginTop: 2, borderRadius: 4,
                      background: 'rgba(255,255,255,0.02)', border: '1px solid var(--ec-border)',
                    }}>
                      <div style={{ fontSize: 10, color: 'var(--ec-text-soft)', fontFamily: BODY, marginBottom: 6 }}>
                        {a.description}
                      </div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 4 }}>
                        <MetaChip label="Severity" value={a.severity} />
                        <MetaChip label="Category" value={a.category} />
                        <MetaChip label="Type" value={a.check_type} />
                      </div>
                      {result && (
                        <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '2px 8px', fontSize: 10, fontFamily: MONO, marginTop: 6 }}>
                          <span style={{ color: 'var(--ec-text-faint)' }}>status:</span>
                          <span style={{ color: result.passed ? '#22c55e' : '#ef4444', fontWeight: 600 }}>{result.passed ? 'PASS' : 'FAIL'}</span>
                          <span style={{ color: 'var(--ec-text-faint)' }}>expected:</span>
                          <span style={{ color: '#22c55e' }}>{result.expected || '—'}</span>
                          <span style={{ color: 'var(--ec-text-faint)' }}>actual:</span>
                          <span style={{ color: result.passed ? 'var(--ec-text-soft)' : '#ef4444' }}>{result.actual || '—'}</span>
                          {result.details && <>
                            <span style={{ color: 'var(--ec-text-faint)' }}>details:</span>
                            <span style={{ color: 'var(--ec-text-soft)' }}>{result.details}</span>
                          </>}
                        </div>
                      )}
                      {!result && (
                        <div style={{ fontSize: 10, color: 'var(--ec-text-faint)', fontStyle: 'italic' }}>
                          No result from last run
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      ))}
      {assertions.length === 0 && (
        <div style={{ color: 'var(--ec-text-faint)', fontSize: 11, textAlign: 'center', padding: 24 }}>
          Loading assertions...
        </div>
      )}
    </div>
  );
}

// ── Panel D: Bug Tracker ─────────────────────────────────────

const BUG_STATUS_COLOR = {
  open: '#f59e0b',
  failing: '#f87171',
  fixed: '#22c55e',
  wontfix: '#6b7280',
};

function BugsPanel() {
  const [bugs, setBugs] = useState(null);
  const [expanded, setExpanded] = useState(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const res = await fetch('/qa/bugs');
        if (res.ok && !cancelled) setBugs(await res.json());
      } catch {}
    };
    load();
    const id = setInterval(load, 10000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  if (bugs === null) {
    return <div style={{ color: 'var(--ec-text-faint)', fontSize: 11, textAlign: 'center', padding: 24 }}>Loading bugs...</div>;
  }

  if (bugs.length === 0) {
    return <div style={{ color: 'var(--ec-text-faint)', fontSize: 11, textAlign: 'center', padding: 24 }}>No tracked bugs</div>;
  }

  const openBugs = bugs.filter(b => b.status === 'open' || b.status === 'failing');
  const closedBugs = bugs.filter(b => b.status !== 'open' && b.status !== 'failing');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {/* Summary */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 4 }}>
        <MetaChip label="Open" value={`${openBugs.length}`} />
        <MetaChip label="Total" value={`${bugs.length}`} />
      </div>

      {bugs.map((bug) => {
        const isExpanded = expanded === bug.id;
        return (
          <div key={bug.id}>
            <div
              onClick={() => setExpanded(isExpanded ? null : bug.id)}
              style={{
                padding: '10px 12px', borderRadius: 6, cursor: 'pointer',
                background: 'rgba(255,255,255,0.02)', border: '1px solid var(--ec-border)',
                transition: 'border-color 0.2s',
              }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.12)'; }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--ec-border)'; }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <Badge
                  label={(bug.status || 'open').toUpperCase()}
                  color={BUG_STATUS_COLOR[bug.status] || '#9ca3af'}
                />
                <span style={{ fontSize: 11, fontWeight: 600, color: '#e5e7eb', fontFamily: MONO }}>{bug.id}</span>
                {bug.severity && (
                  <Badge label={bug.severity} color={bug.severity === 'critical' ? '#ef4444' : bug.severity === 'high' ? '#f59e0b' : '#9ca3af'} />
                )}
                <TimeAgo ts={bug.date_found} />
                <span style={{ fontSize: 10, color: 'var(--ec-text-faint)', marginLeft: 'auto' }}>{isExpanded ? '▲' : '▼'}</span>
              </div>
              <div style={{ fontSize: 12, color: 'var(--ec-text-soft)', fontFamily: BODY, lineHeight: 1.4 }}>
                {bug.name}
              </div>
            </div>

            {/* Expanded forensics */}
            {isExpanded && (
              <div style={{
                padding: '10px 14px', marginTop: 2, borderRadius: 6,
                background: 'rgba(255,255,255,0.02)', border: '1px solid var(--ec-border)',
              }}>
                {bug.query && (
                  <div style={{ marginBottom: 8 }}>
                    <div style={{ fontSize: 9, fontFamily: LABEL, letterSpacing: 1.5, color: 'var(--ec-text-faint)', marginBottom: 4 }}>TRIGGER QUERY</div>
                    <div style={{ fontSize: 11, color: 'var(--ec-text-soft)', fontFamily: BODY, padding: '6px 8px', borderRadius: 4, background: 'rgba(255,255,255,0.02)' }}>
                      "{bug.query}"
                    </div>
                  </div>
                )}
                {bug.expected_behavior && (
                  <div style={{ marginBottom: 8 }}>
                    <div style={{ fontSize: 9, fontFamily: LABEL, letterSpacing: 1.5, color: '#22c55e', marginBottom: 4 }}>EXPECTED</div>
                    <div style={{ fontSize: 11, color: 'var(--ec-text-soft)', fontFamily: BODY, lineHeight: 1.5 }}>
                      {bug.expected_behavior}
                    </div>
                  </div>
                )}
                {bug.actual_behavior && (
                  <div style={{ marginBottom: 8 }}>
                    <div style={{ fontSize: 9, fontFamily: LABEL, letterSpacing: 1.5, color: '#ef4444', marginBottom: 4 }}>ACTUAL</div>
                    <div style={{ fontSize: 11, color: 'var(--ec-text-soft)', fontFamily: BODY, lineHeight: 1.5 }}>
                      {bug.actual_behavior}
                    </div>
                  </div>
                )}
                {bug.root_cause && (
                  <div style={{ marginBottom: 8 }}>
                    <div style={{ fontSize: 9, fontFamily: LABEL, letterSpacing: 1.5, color: '#fb923c', marginBottom: 4 }}>ROOT CAUSE</div>
                    <div style={{ fontSize: 11, color: 'var(--ec-text-soft)', fontFamily: BODY, lineHeight: 1.5 }}>
                      {bug.root_cause}
                    </div>
                  </div>
                )}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  <MetaChip label="Found" value={bug.date_found ? new Date(bug.date_found).toLocaleDateString() : '—'} />
                  {bug.date_fixed && <MetaChip label="Fixed" value={new Date(bug.date_fixed).toLocaleDateString()} />}
                  {bug.fixed_by && <MetaChip label="Fixed by" value={bug.fixed_by} />}
                  {bug.last_test_passed != null && (
                    <MetaChip label="Last test" value={bug.last_test_passed ? 'PASS' : 'FAIL'} />
                  )}
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Panel E: System Events ───────────────────────────────────

const SEV_COLOR = { critical: '#ef4444', high: '#fb923c', medium: '#f59e0b', low: '#9ca3af' };
const SRC_COLOR = { watchdog: '#fb923c', health: '#38bdf8', api_error: '#ef4444' };

function EventsPanel() {
  const [events, setEvents] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const [eRes, sRes] = await Promise.all([
          fetch('/qa/events?limit=50'),
          fetch('/qa/events/summary'),
        ]);
        if (eRes.ok && !cancelled) setEvents(await eRes.json());
        if (sRes.ok && !cancelled) setSummary(await sRes.json());
      } catch {}
      if (!cancelled) setLoading(false);
    };
    load();
    const id = setInterval(load, 10000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  if (loading) {
    return <div style={{ color: 'var(--ec-text-faint)', fontSize: 11, textAlign: 'center', padding: 24 }}>Loading events...</div>;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Summary */}
      {summary && (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <MetaChip label="Total (24h)" value={`${summary.total}`} />
          {Object.entries(summary.by_source || {}).map(([src, count]) => (
            <MetaChip key={src} label={src} value={`${count}`} />
          ))}
          {Object.entries(summary.by_severity || {}).map(([sev, count]) => (
            <MetaChip key={sev} label={sev} value={`${count}`} />
          ))}
        </div>
      )}

      {/* Event list */}
      {events.length === 0 ? (
        <div style={{ color: 'var(--ec-text-faint)', fontSize: 11, textAlign: 'center', padding: 24 }}>
          No system events recorded. Watchdog, health checks, and API errors will appear here.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {events.map((ev, i) => (
            <div key={ev.id || i} style={{
              display: 'flex', alignItems: 'flex-start', gap: 8,
              padding: '8px 10px', borderRadius: 6,
              background: ev.severity === 'critical' ? 'rgba(239,68,68,0.04)' : 'rgba(255,255,255,0.02)',
              border: `1px solid ${ev.severity === 'critical' ? 'rgba(239,68,68,0.12)' : 'var(--ec-border)'}`,
            }}>
              <Badge label={ev.severity} color={SEV_COLOR[ev.severity] || '#9ca3af'} />
              <Badge label={ev.source} color={SRC_COLOR[ev.source] || '#818cf8'} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 11, color: 'var(--ec-text-soft)', fontFamily: BODY }}>
                  <span style={{ color: 'var(--ec-text-faint)', fontFamily: MONO, fontSize: 10 }}>{ev.component}</span>
                  {' — '}{ev.message}
                </div>
              </div>
              <TimeAgo ts={ev.timestamp} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── QAModuleView — Full QA diagnostic workspace ──────────────

export default function QAModuleView() {
  const [activeTab, setActiveTab] = useState('health');
  const [health, setHealth] = useState(null);
  const [lastReport, setLastReport] = useState(null);

  // Poll health + last report
  useEffect(() => {
    const poll = async () => {
      try {
        const [hRes, rRes] = await Promise.all([
          fetch('/qa/health'),
          fetch('/qa/last'),
        ]);
        if (hRes.ok) setHealth(await hRes.json());
        if (rRes.ok) {
          const data = await rRes.json();
          if (!data.error) setLastReport(data);
        }
      } catch {}
    };
    poll();
    const id = setInterval(poll, 5000);
    return () => clearInterval(id);
  }, []);

  const passRate = health?.pass_rate != null ? health.pass_rate * 100 : null;

  return (
    <div style={{
      height: '100%', display: 'flex', flexDirection: 'column',
      fontFamily: BODY, color: 'var(--ec-text)', background: 'var(--ec-bg)',
    }}>
      {/* Header */}
      <div style={{
        height: 44, background: 'var(--ec-bg-raised)', borderBottom: '1px solid var(--ec-border)',
        display: 'flex', alignItems: 'center', padding: '0 16px', gap: 10, flexShrink: 0,
      }}>
        <div style={{ width: 3, height: 20, borderRadius: 2, background: QA_ACCENT, boxShadow: '0 0 8px rgba(248,113,113,0.3)' }} />
        <span style={{ fontFamily: LABEL, fontSize: 11, letterSpacing: 2.5, color: QA_ACCENT }}>QA</span>
        <div style={{ width: 1, height: 14, background: 'var(--ec-border)' }} />
        <span style={{ fontFamily: LABEL, fontSize: 10, letterSpacing: 2, color: 'var(--ec-text-faint)' }}>DIAGNOSTICS</span>
        <div style={{ flex: 1 }} />

        {/* Pass rate badge */}
        {passRate != null && (
          <span style={{
            fontSize: 9, fontFamily: MONO, fontWeight: 600, padding: '2px 8px', borderRadius: 3,
            color: passRate >= 90 ? '#22c55e' : passRate >= 70 ? '#f59e0b' : '#ef4444',
            background: passRate >= 90 ? 'rgba(34,197,94,0.08)' : passRate >= 70 ? 'rgba(245,158,11,0.08)' : 'rgba(239,68,68,0.08)',
            border: `1px solid ${passRate >= 90 ? 'rgba(34,197,94,0.15)' : passRate >= 70 ? 'rgba(245,158,11,0.15)' : 'rgba(239,68,68,0.15)'}`,
          }}>
            {passRate.toFixed(0)}% PASS
          </span>
        )}

        {/* Runs count */}
        {health && (
          <span style={{ fontSize: 9, fontFamily: MONO, color: 'var(--ec-text-faint)' }}>
            {health.total_24h || 0} runs
          </span>
        )}
      </div>

      {/* Tab bar */}
      <div style={{
        display: 'flex', gap: 2, padding: '8px 16px',
        borderBottom: '1px solid var(--ec-border)', flexShrink: 0,
      }}>
        {TABS.map((tab) => (
          <TabButton
            key={tab}
            label={tab}
            accent={QA_ACCENT}
            isActive={activeTab === tab}
            onClick={() => setActiveTab(tab)}
          />
        ))}
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '12px 16px', minHeight: 0 }}>
        {activeTab === 'health' && <HealthPanel health={health} lastReport={lastReport} />}
        {activeTab === 'history' && <HistoryPanel />}
        {activeTab === 'assertions' && <AssertionsPanel />}
        {activeTab === 'bugs' && <BugsPanel />}
        {activeTab === 'events' && <EventsPanel />}
      </div>
    </div>
  );
}
