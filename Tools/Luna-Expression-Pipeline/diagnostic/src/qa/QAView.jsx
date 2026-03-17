import React, { useState, useEffect, useCallback, useRef } from 'react';

const API = '';

const STATUS_COLORS = { pass: '#34d399', warn: '#fbbf24', fail: '#f87171' };
const SEV_COLORS = {
  P1: '#f87171', P2: '#fb923c', P3: '#fbbf24',
  S1: '#7dd3fc', S2: '#818cf8', S3: '#93c5fd',
  V1: '#a78bfa', V2: '#c084fc',
  F1: '#34d399', R1: '#e09f3e',
  I1: '#60a5fa', I2: '#38bdf8',
  critical: '#f87171', high: '#fb923c', medium: '#fbbf24', low: '#94a3b8',
};
const BUG_STATUS_COLORS = { open: '#f87171', failing: '#fb923c', fixed: '#34d399', wontfix: '#666' };
const CATEGORY_COLORS = {
  personality: '#a78bfa', structural: '#60a5fa', voice: '#f472b6',
  flow: '#34d399', integration: '#fb923c',
};

function safeFetch(url) {
  return fetch(url).then(r => r.ok ? r.json() : null).catch(() => null);
}

function timeAgo(ts) {
  if (!ts) return '';
  const diff = Date.now() - new Date(ts).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function Badge({ color, children, onClick, style: extra }) {
  return (
    <span
      onClick={onClick}
      style={{
        fontSize: 9, padding: '2px 8px', borderRadius: 4,
        background: color + '18', color, border: `1px solid ${color}33`,
        fontWeight: 600, whiteSpace: 'nowrap', cursor: onClick ? 'pointer' : 'default',
        ...extra,
      }}
    >{children}</span>
  );
}

function Pill({ active, onClick, children }) {
  return (
    <button
      onClick={onClick}
      style={{
        fontSize: 9, padding: '3px 10px', borderRadius: 12, fontWeight: 600,
        border: `1px solid ${active ? '#a78bfa44' : 'rgba(255,255,255,0.08)'}`,
        background: active ? 'rgba(167,139,250,0.12)' : 'transparent',
        color: active ? '#a78bfa' : '#666', cursor: 'pointer',
        fontFamily: "'JetBrains Mono', monospace",
      }}
    >{children}</button>
  );
}

function ActionButton({ onClick, disabled, loading, children, primary, style: extra }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      style={{
        fontSize: 9, padding: '4px 12px', borderRadius: 4, fontWeight: 600,
        border: `1px solid ${primary ? '#a78bfa55' : 'rgba(255,255,255,0.1)'}`,
        background: primary ? 'rgba(167,139,250,0.15)' : 'rgba(255,255,255,0.03)',
        color: primary ? '#a78bfa' : '#94a3b8',
        cursor: disabled || loading ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.5 : 1,
        fontFamily: "'JetBrains Mono', monospace",
        display: 'inline-flex', alignItems: 'center', gap: 4,
        ...extra,
      }}
    >{loading ? '⟳' : ''}{children}</button>
  );
}

function Toast({ message, type }) {
  if (!message) return null;
  const c = type === 'error' ? '#f87171' : '#34d399';
  return (
    <div style={{
      position: 'fixed', bottom: 20, right: 20, zIndex: 9999,
      padding: '8px 16px', borderRadius: 6, fontSize: 11, fontWeight: 600,
      background: c + '18', color: c, border: `1px solid ${c}33`,
      fontFamily: "'JetBrains Mono', monospace",
      animation: 'fadeIn 0.2s ease',
    }}>{message}</div>
  );
}

function PassDot({ passed }) {
  return (
    <span style={{
      display: 'inline-block', width: 8, height: 8, borderRadius: '50%',
      background: passed ? '#34d399' : '#f87171', flexShrink: 0,
    }} />
  );
}

/* ─── Assertion Playground ─── */
function AssertionPlayground({ assertionId }) {
  const [text, setText] = useState('');
  const [result, setResult] = useState(null);
  const [checking, setChecking] = useState(false);

  const check = useCallback(async () => {
    if (!text.trim() || checking) return;
    setChecking(true);
    setResult(null);
    try {
      const res = await fetch(`${API}/qa/check-assertion`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ assertion_id: assertionId, response_text: text }),
      });
      if (res.ok) setResult(await res.json());
      else setResult({ passed: false, actual: `HTTP ${res.status}` });
    } catch (e) {
      setResult({ passed: false, actual: e.message });
    } finally {
      setChecking(false);
    }
  }, [text, assertionId, checking]);

  return (
    <div style={{
      padding: '8px 10px', marginTop: 4, borderRadius: 4,
      background: 'rgba(167,139,250,0.03)', border: '1px solid rgba(167,139,250,0.08)',
    }}>
      <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
        <input
          value={text}
          onChange={e => setText(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && check()}
          placeholder="Test a response against this assertion..."
          style={{
            flex: 1, background: 'rgba(0,0,0,0.2)', border: '1px solid rgba(255,255,255,0.04)',
            borderRadius: 3, padding: '4px 6px', color: '#c0c0d0', fontSize: 9,
            fontFamily: "'JetBrains Mono', monospace", outline: 'none',
          }}
        />
        <ActionButton onClick={check} disabled={!text.trim()} loading={checking} primary>
          CHECK
        </ActionButton>
      </div>
      {result && (
        <div style={{
          marginTop: 4, fontSize: 9, display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap',
          color: result.passed ? '#22c55e' : '#f87171',
        }}>
          <Badge color={result.passed ? '#22c55e' : '#ef4444'}>{result.passed ? 'PASS' : 'FAIL'}</Badge>
          {result.expected && <span style={{ color: '#666' }}>{result.expected}</span>}
          {result.actual && <span style={{ color: result.passed ? '#22c55e' : '#f87171' }}>{result.actual}</span>}
          {result.details && <span style={{ color: '#777' }}>{result.details}</span>}
        </div>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════
   MAIN QA VIEW
   ═══════════════════════════════════════════════ */
export default function QAView() {
  const [tab, setTab] = useState('dashboard');
  const [health, setHealth] = useState(null);
  const [lastReport, setLastReport] = useState(null);
  const [history, setHistory] = useState([]);
  const [assertions, setAssertions] = useState([]);
  const [bugs, setBugs] = useState([]);
  const [events, setEvents] = useState([]);
  const [eventsSummary, setEventsSummary] = useState(null);
  const [toast, setToast] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const toastTimer = useRef(null);

  const showToast = (message, type = 'success') => {
    setToast({ message, type });
    clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 3000);
  };

  const fetchAll = useCallback(async () => {
    const [h, last, hist, a, b, ev, evs] = await Promise.all([
      safeFetch(`${API}/qa/health`),
      safeFetch(`${API}/qa/last`),
      safeFetch(`${API}/qa/history?limit=25`),
      safeFetch(`${API}/qa/assertions`),
      safeFetch(`${API}/qa/bugs`),
      safeFetch(`${API}/qa/events?limit=50`),
      safeFetch(`${API}/qa/events/summary`),
    ]);
    setHealth(h);
    setLastReport(last);
    setHistory(Array.isArray(hist) ? hist : hist?.reports || []);
    setAssertions(Array.isArray(a) ? a : a?.assertions || []);
    setBugs(Array.isArray(b) ? b : b?.bugs || []);
    setEvents(Array.isArray(ev) ? ev : []);
    setEventsSummary(evs);
  }, []);

  useEffect(() => {
    fetchAll();
    const iv = setInterval(fetchAll, 10000);
    return () => clearInterval(iv);
  }, [fetchAll]);

  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchAll();
    setRefreshing(false);
    showToast('Refreshed');
  };

  const passRate = health?.pass_rate != null ? (health.pass_rate * 100).toFixed(1) : null;
  const status = health == null
    ? 'connecting'
    : health.pass_rate >= 0.9 ? 'pass' : health.pass_rate >= 0.7 ? 'warn' : 'fail';
  const statusColor = STATUS_COLORS[status] || '#666';

  const TABS = [
    { id: 'dashboard', label: 'Dashboard' },
    { id: 'history', label: 'History' },
    { id: 'assertions', label: 'Assertions' },
    { id: 'bugs', label: 'Bugs' },
    { id: 'events', label: 'Events' },
  ];

  const sty = {
    panel: {
      background: '#0c0c18', border: '1px solid rgba(255,255,255,0.06)',
      borderRadius: 8, padding: 14, marginBottom: 10,
    },
    label: {
      fontSize: 9, fontWeight: 600, letterSpacing: '0.5px', color: '#666',
      textTransform: 'uppercase', marginBottom: 6,
    },
    val: { fontSize: 20, fontWeight: 700, letterSpacing: '-0.5px' },
    row: { display: 'flex', gap: 10, marginBottom: 10 },
    clickRow: {
      display: 'flex', alignItems: 'center', gap: 8, padding: '6px 4px',
      borderBottom: '1px solid rgba(255,255,255,0.04)', fontSize: 11,
      cursor: 'pointer', transition: 'background 0.1s',
    },
  };

  return (
    <div style={{
      padding: 16, height: '100%', overflow: 'auto', color: '#e0e0f0',
      fontFamily: "'JetBrains Mono', monospace",
    }}>
      {/* Tab bar */}
      <div style={{
        display: 'flex', gap: 2, marginBottom: 14, borderBottom: '1px solid rgba(255,255,255,0.06)',
        paddingBottom: 8,
      }}>
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            style={{
              fontSize: 10, padding: '6px 14px', borderRadius: '6px 6px 0 0', fontWeight: 600,
              border: 'none', cursor: 'pointer',
              background: tab === t.id ? 'rgba(167,139,250,0.12)' : 'transparent',
              color: tab === t.id ? '#a78bfa' : '#555',
              borderBottom: tab === t.id ? '2px solid #a78bfa' : '2px solid transparent',
              fontFamily: "'JetBrains Mono', monospace",
            }}
          >{t.label}</button>
        ))}
      </div>

      {/* ═══ TAB 1: DASHBOARD ═══ */}
      {tab === 'dashboard' && <DashboardTab
        health={health} passRate={passRate} status={status} statusColor={statusColor}
        lastReport={lastReport} bugs={bugs} sty={sty}
        onRefresh={handleRefresh} refreshing={refreshing}
        showToast={showToast} setTab={setTab}
      />}

      {/* ═══ TAB 2: HISTORY ═══ */}
      {tab === 'history' && <HistoryTab
        history={history} sty={sty} showToast={showToast}
      />}

      {/* ═══ TAB 3: ASSERTIONS ═══ */}
      {tab === 'assertions' && <AssertionsTab
        assertions={assertions} lastReport={lastReport} sty={sty}
        showToast={showToast} onRefresh={fetchAll}
      />}

      {/* ═══ TAB 4: BUGS ═══ */}
      {tab === 'bugs' && <BugsTab
        bugs={bugs} sty={sty} showToast={showToast} onRefresh={fetchAll}
      />}

      {/* ═══ TAB 5: EVENTS ═══ */}
      {tab === 'events' && <EventsTab
        events={events} summary={eventsSummary} sty={sty}
      />}

      {toast && <Toast message={toast.message} type={toast.type} />}
    </div>
  );
}

/* ═══════════════════════════════════════════════
   TAB 1: DASHBOARD
   ═══════════════════════════════════════════════ */
function DashboardTab({ health, passRate, status, statusColor, lastReport, bugs, sty, onRefresh, refreshing, showToast, setTab }) {
  const [simulating, setSimulating] = useState(false);
  const [simResult, setSimResult] = useState(null);

  const runQACheck = async () => {
    setSimulating(true);
    setSimResult(null);
    try {
      const res = await fetch(`${API}/qa/simulate`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setSimResult(data);
        showToast('QA check complete');
      } else {
        showToast(`QA check failed: HTTP ${res.status}`, 'error');
      }
    } catch (e) {
      showToast(`QA check failed: ${e.message}`, 'error');
    } finally {
      setSimulating(false);
    }
  };

  const openBugCount = bugs.filter(b => b.status === 'open' || b.status === 'failing').length;

  return (
    <>
      {/* Action bar */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 12 }}>
        <ActionButton onClick={onRefresh} loading={refreshing} primary>Refresh</ActionButton>
        <ActionButton onClick={runQACheck} loading={simulating}>Run QA Check</ActionButton>
      </div>

      {/* Health cards */}
      <div style={sty.row}>
        <div style={{ ...sty.panel, flex: 1, marginBottom: 0 }}>
          <div style={sty.label}>Status</div>
          <div style={{ ...sty.val, color: statusColor }}>
            {status === 'connecting' ? 'CONNECTING...' : status.toUpperCase()}
          </div>
        </div>
        <div style={{ ...sty.panel, flex: 1, marginBottom: 0 }}>
          <div style={sty.label}>Pass Rate</div>
          <div style={{
            ...sty.val,
            color: passRate == null ? '#666' : parseFloat(passRate) >= 90 ? '#34d399' : parseFloat(passRate) >= 70 ? '#fbbf24' : '#f87171',
          }}>{passRate != null ? `${passRate}%` : '—'}</div>
        </div>
        <div style={{ ...sty.panel, flex: 1, marginBottom: 0 }}>
          <div style={sty.label}>Runs (24h)</div>
          <div style={sty.val}>{health?.total_24h ?? '—'}</div>
        </div>
        <div style={{ ...sty.panel, flex: 1, marginBottom: 0 }}>
          <div style={sty.label}>Failed (24h)</div>
          <div style={{ ...sty.val, color: (health?.failed_24h || 0) > 0 ? '#f87171' : '#34d399' }}>
            {health?.failed_24h ?? '—'}
          </div>
        </div>
        <div style={{ ...sty.panel, flex: 1, marginBottom: 0 }}>
          <div style={sty.label}>Open Bugs</div>
          <div style={{ ...sty.val, color: openBugCount > 0 ? '#f87171' : '#34d399' }}>{openBugCount}</div>
        </div>
        <div style={{ ...sty.panel, flex: 1, marginBottom: 0 }}>
          <div style={sty.label}>Events (24h)</div>
          <div style={{ ...sty.val, color: (health?.system_events_24h || 0) > 0 ? '#fb923c' : '#34d399' }}>
            {health?.system_events_24h ?? '—'}
          </div>
        </div>
      </div>

      {/* Top failures */}
      {health?.top_failures?.length > 0 && (
        <div style={sty.panel}>
          <div style={sty.label}>Top Failures</div>
          {health.top_failures.map((f, i) => (
            <div
              key={i}
              onClick={() => setTab('assertions')}
              style={{
                ...sty.clickRow,
                ':hover': { background: 'rgba(255,255,255,0.02)' },
              }}
              onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.02)'}
              onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
            >
              <Badge color={SEV_COLORS[f.id] || '#818cf8'}>{f.id}</Badge>
              <span style={{ flex: 1, color: '#94a3b8' }}>{f.name || f.id}</span>
              <span style={{ color: '#f87171', fontSize: 10, fontWeight: 600 }}>×{f.count}</span>
            </div>
          ))}
        </div>
      )}

      {/* Last report summary */}
      <div style={sty.panel}>
        <div style={sty.label}>Last Report</div>
        {lastReport ? (
          <div style={{ fontSize: 11 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
              <PassDot passed={lastReport.passed !== false && lastReport.failed_count === 0} />
              <span style={{ color: '#c0c0d0' }}>{lastReport.query || '—'}</span>
              {lastReport.route && <Badge color="#818cf8">{lastReport.route}</Badge>}
              <span style={{ color: '#555', fontSize: 9, marginLeft: 'auto' }}>{timeAgo(lastReport.timestamp)}</span>
            </div>
            {lastReport.assertions?.some(a => !a.passed) && (
              <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                {lastReport.assertions.filter(a => !a.passed).map((a, i) => (
                  <Badge key={i} color="#f87171">{a.id || a.name}</Badge>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div style={{ color: '#555', fontSize: 11 }}>No reports yet</div>
        )}
      </div>

      {/* Simulation result */}
      {simResult && (
        <div style={sty.panel}>
          <div style={sty.label}>QA Check Result</div>
          <div style={{ fontSize: 11 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <PassDot passed={simResult.passed !== false} />
              <span style={{ color: '#c0c0d0' }}>
                {simResult.passed !== false ? 'All assertions passed' : `${simResult.failed_count || 0} assertion(s) failed`}
              </span>
            </div>
            {simResult.diagnosis && (
              <div style={{ color: '#94a3b8', fontSize: 10, marginTop: 4 }}>{simResult.diagnosis}</div>
            )}
          </div>
        </div>
      )}
    </>
  );
}

/* ═══════════════════════════════════════════════
   TAB 2: HISTORY
   ═══════════════════════════════════════════════ */
function HistoryTab({ history, sty, showToast }) {
  const [filter, setFilter] = useState('all');
  const [expanded, setExpanded] = useState(null);

  const filtered = history.filter(r => {
    if (filter === 'failed') return r.failed_count > 0 || r.passed === false;
    if (filter === 'passed') return r.failed_count === 0 && r.passed !== false;
    return true;
  });

  const logAsBug = async (report) => {
    try {
      const res = await fetch(`${API}/qa/bugs/from-last`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ inference_id: report.inference_id }),
      });
      if (res.ok) showToast('Bug logged');
      else showToast(`Failed to log bug: HTTP ${res.status}`, 'error');
    } catch (e) {
      showToast(`Failed: ${e.message}`, 'error');
    }
  };

  const copyDiagnosis = (text) => {
    navigator.clipboard.writeText(text).then(() => showToast('Copied'));
  };

  return (
    <>
      <div style={{ display: 'flex', gap: 4, marginBottom: 10 }}>
        {['all', 'failed', 'passed'].map(f => (
          <Pill key={f} active={filter === f} onClick={() => setFilter(f)}>
            {f === 'all' ? 'All' : f === 'failed' ? 'Failed Only' : 'Passed Only'}
          </Pill>
        ))}
        <span style={{ marginLeft: 'auto', fontSize: 9, color: '#555' }}>{filtered.length} reports</span>
      </div>

      <div style={{ maxHeight: 'calc(100vh - 160px)', overflow: 'auto' }}>
        {filtered.length === 0 ? (
          <div style={{ ...sty.panel, color: '#555', fontSize: 11 }}>No reports match this filter.</div>
        ) : filtered.map((r, i) => {
          const isFail = r.failed_count > 0 || r.passed === false;
          const isOpen = expanded === i;
          return (
            <div key={r.inference_id || i} style={{ ...sty.panel, padding: 0, overflow: 'hidden' }}>
              <div
                onClick={() => setExpanded(isOpen ? null : i)}
                style={{
                  ...sty.clickRow, padding: '8px 12px', borderBottom: isOpen ? '1px solid rgba(255,255,255,0.04)' : 'none',
                }}
                onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.02)'}
                onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
              >
                <PassDot passed={!isFail} />
                <span style={{ color: '#555', fontSize: 9 }}>{r.inference_id?.slice(0, 8) || '—'}</span>
                <span style={{ flex: 1, color: '#c0c0d0', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 300 }}>
                  {r.query || '—'}
                </span>
                {r.route && <Badge color="#818cf8">{r.route}</Badge>}
                <span style={{ color: '#555', fontSize: 9 }}>{timeAgo(r.timestamp)}</span>
                <span style={{ color: '#555', fontSize: 8 }}>{isOpen ? '▲' : '▼'}</span>
              </div>

              {isOpen && (
                <div style={{ padding: '10px 12px', background: 'rgba(0,0,0,0.15)' }}>
                  {/* Metadata chips */}
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
                    {r.provider_used && <Badge color="#818cf8">{r.provider_used}</Badge>}
                    {r.latency_ms != null && <Badge color="#60a5fa">{r.latency_ms}ms</Badge>}
                    {r.context?.output_tokens != null && <Badge color="#94a3b8">{r.context.output_tokens} tokens</Badge>}
                    {r.route && <Badge color="#a78bfa">{r.route}</Badge>}
                    {r.timestamp && <Badge color="#555">{new Date(r.timestamp).toLocaleString()}</Badge>}
                  </div>

                  {/* Request chain timeline */}
                  {r.context?.request_chain?.length > 0 && (
                    <div style={{ marginBottom: 8 }}>
                      <div style={{ ...sty.label, marginBottom: 4 }}>Request Chain</div>
                      <div style={{ display: 'flex', gap: 0, flexWrap: 'wrap' }}>
                        {r.context.request_chain.map((step, si) => (
                          <div key={si} style={{ display: 'flex', alignItems: 'center' }}>
                            <div style={{
                              padding: '3px 8px', borderRadius: 3, fontSize: 9,
                              background: 'rgba(167,139,250,0.06)', border: '1px solid rgba(167,139,250,0.12)',
                              color: '#94a3b8',
                            }}>
                              <span style={{ color: '#a78bfa', fontWeight: 600 }}>{step.step}</span>
                              <span style={{ color: '#555', marginLeft: 4 }}>{step.time_ms}ms</span>
                              {step.detail && <span style={{ color: '#666', marginLeft: 4 }}>{step.detail}</span>}
                            </div>
                            {si < r.context.request_chain.length - 1 && (
                              <span style={{ color: '#333', margin: '0 2px' }}>→</span>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Failed assertions */}
                  {r.assertions?.filter(a => !a.passed).length > 0 && (
                    <div style={{ marginBottom: 8 }}>
                      <div style={{ ...sty.label, marginBottom: 4, color: '#f87171' }}>Failed Assertions</div>
                      {r.assertions.filter(a => !a.passed).map((a, ai) => (
                        <div key={ai} style={{
                          padding: '6px 8px', marginBottom: 4, borderRadius: 4,
                          background: 'rgba(248,113,113,0.04)', border: '1px solid rgba(248,113,113,0.1)',
                        }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
                            <Badge color={SEV_COLORS[a.id] || '#f87171'}>{a.id}</Badge>
                            <span style={{ color: '#c0c0d0', fontSize: 10 }}>{a.name}</span>
                            {a.severity && <Badge color={SEV_COLORS[a.severity] || '#fb923c'}>{a.severity}</Badge>}
                          </div>
                          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4, fontSize: 9 }}>
                            {a.expected && (
                              <div><span style={{ color: '#555' }}>Expected: </span><span style={{ color: '#94a3b8' }}>{a.expected}</span></div>
                            )}
                            {a.actual && (
                              <div><span style={{ color: '#555' }}>Actual: </span><span style={{ color: '#f87171' }}>{a.actual}</span></div>
                            )}
                          </div>
                          {a.details && <div style={{ fontSize: 9, color: '#777', marginTop: 2 }}>{a.details}</div>}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Passed assertions */}
                  {r.assertions?.filter(a => a.passed).length > 0 && (
                    <div style={{ marginBottom: 8 }}>
                      <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                        {r.assertions.filter(a => a.passed).map((a, ai) => (
                          <Badge key={ai} color="#34d399">{a.id || a.name}</Badge>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Diagnosis */}
                  {r.diagnosis && (
                    <div style={{ marginBottom: 8 }}>
                      <div style={{ ...sty.label, marginBottom: 2 }}>Diagnosis</div>
                      <div style={{ fontSize: 10, color: '#94a3b8', lineHeight: 1.4 }}>{r.diagnosis}</div>
                    </div>
                  )}

                  {/* Response preview */}
                  {r.context?.final_response && (
                    <div style={{ marginBottom: 8 }}>
                      <div style={{ ...sty.label, marginBottom: 2 }}>Response</div>
                      <div style={{
                        fontSize: 9, color: '#777', maxHeight: 120, overflow: 'auto',
                        background: 'rgba(0,0,0,0.2)', padding: '6px 8px', borderRadius: 3,
                        whiteSpace: 'pre-wrap', lineHeight: 1.4,
                      }}>{r.context.final_response}</div>
                    </div>
                  )}

                  {/* Action buttons */}
                  <div style={{ display: 'flex', gap: 6 }}>
                    {isFail && (
                      <ActionButton onClick={() => logAsBug(r)} primary>Log as Bug</ActionButton>
                    )}
                    {r.diagnosis && (
                      <ActionButton onClick={() => copyDiagnosis(r.diagnosis)}>Copy Diagnosis</ActionButton>
                    )}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </>
  );
}

/* ═══════════════════════════════════════════════
   TAB 3: ASSERTIONS
   ═══════════════════════════════════════════════ */
function AssertionsTab({ assertions, lastReport, sty, showToast, onRefresh }) {
  const [filter, setFilter] = useState('all');
  const [catFilter, setCatFilter] = useState('all');
  const [expanded, setExpanded] = useState(null);

  // Merge last report results with assertion configs
  const lastResults = {};
  (lastReport?.assertions || []).forEach(a => {
    lastResults[a.id || a.name] = a;
  });

  const categories = [...new Set(assertions.map(a => a.category).filter(Boolean))];

  const filtered = assertions.filter(a => {
    const result = lastResults[a.id || a.name];
    if (filter === 'failing' && result?.passed !== false) return false;
    if (filter === 'passing' && result?.passed === false) return false;
    if (filter === 'disabled' && a.enabled !== false) return false;
    if (catFilter !== 'all' && a.category !== catFilter) return false;
    return true;
  });

  const toggleAssertion = async (assertion) => {
    const newEnabled = assertion.enabled === false;
    try {
      const res = await fetch(`${API}/qa/assertions/${assertion.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: newEnabled }),
      });
      if (res.ok) {
        showToast(`${assertion.id} ${newEnabled ? 'enabled' : 'disabled'}`);
        onRefresh();
      } else {
        showToast(`Toggle failed: HTTP ${res.status}`, 'error');
      }
    } catch (e) {
      showToast(`Toggle failed: ${e.message}`, 'error');
    }
  };

  return (
    <>
      <div style={{ display: 'flex', gap: 4, marginBottom: 6, flexWrap: 'wrap' }}>
        {['all', 'failing', 'passing', 'disabled'].map(f => (
          <Pill key={f} active={filter === f} onClick={() => setFilter(f)}>
            {f.charAt(0).toUpperCase() + f.slice(1)}
          </Pill>
        ))}
      </div>
      {categories.length > 0 && (
        <div style={{ display: 'flex', gap: 4, marginBottom: 10, flexWrap: 'wrap' }}>
          <Pill active={catFilter === 'all'} onClick={() => setCatFilter('all')}>All Categories</Pill>
          {categories.map(c => (
            <Pill key={c} active={catFilter === c} onClick={() => setCatFilter(c)}>{c}</Pill>
          ))}
        </div>
      )}
      <span style={{ fontSize: 9, color: '#555', marginBottom: 8, display: 'block' }}>{filtered.length} assertions</span>

      <div style={{ maxHeight: 'calc(100vh - 200px)', overflow: 'auto' }}>
        {filtered.map((a, i) => {
          const result = lastResults[a.id || a.name];
          const isOpen = expanded === (a.id || a.name);
          return (
            <div key={a.id || i} style={{ ...sty.panel, padding: 0, overflow: 'hidden' }}>
              <div
                onClick={() => setExpanded(isOpen ? null : (a.id || a.name))}
                style={{ ...sty.clickRow, padding: '8px 12px' }}
                onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.02)'}
                onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
              >
                {result ? <PassDot passed={result.passed} /> : <span style={{ width: 8, height: 8, display: 'inline-block', borderRadius: '50%', background: '#333', flexShrink: 0 }} />}
                {/* Toggle switch */}
                <div
                  onClick={(e) => { e.stopPropagation(); toggleAssertion(a); }}
                  style={{
                    width: 28, height: 14, borderRadius: 7, cursor: 'pointer',
                    background: a.enabled !== false ? 'rgba(52,211,153,0.3)' : 'rgba(255,255,255,0.08)',
                    position: 'relative', transition: 'background 0.2s', flexShrink: 0,
                  }}
                >
                  <div style={{
                    width: 10, height: 10, borderRadius: '50%',
                    background: a.enabled !== false ? '#34d399' : '#555',
                    position: 'absolute', top: 2,
                    left: a.enabled !== false ? 16 : 2,
                    transition: 'left 0.2s',
                  }} />
                </div>
                <Badge color={SEV_COLORS[a.id] || '#818cf8'}>{a.id}</Badge>
                <span style={{ flex: 1, color: '#c0c0d0', fontSize: 10 }}>{a.name}</span>
                {a.check_type && <span style={{ color: '#555', fontSize: 8 }}>{a.check_type}</span>}
                <span style={{ color: '#555', fontSize: 8 }}>{isOpen ? '▲' : '▼'}</span>
              </div>

              {isOpen && (
                <div style={{ padding: '10px 12px', background: 'rgba(0,0,0,0.15)' }}>
                  {a.description && (
                    <div style={{ fontSize: 10, color: '#94a3b8', marginBottom: 6, lineHeight: 1.4 }}>{a.description}</div>
                  )}
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
                    {a.severity && <Badge color={SEV_COLORS[a.severity] || '#fb923c'}>{a.severity}</Badge>}
                    {a.category && <Badge color={CATEGORY_COLORS[a.category] || '#818cf8'}>{a.category}</Badge>}
                    {a.check_type && <Badge color="#555">{a.check_type}</Badge>}
                  </div>
                  {result && (
                    <div style={{
                      padding: '6px 8px', borderRadius: 4, marginBottom: 8,
                      background: result.passed ? 'rgba(52,211,153,0.04)' : 'rgba(248,113,113,0.04)',
                      border: `1px solid ${result.passed ? 'rgba(52,211,153,0.1)' : 'rgba(248,113,113,0.1)'}`,
                    }}>
                      <div style={{ fontSize: 9, color: '#555', marginBottom: 2 }}>Last Run Result</div>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4, fontSize: 9 }}>
                        {result.expected && <div><span style={{ color: '#555' }}>Expected: </span><span style={{ color: '#94a3b8' }}>{result.expected}</span></div>}
                        {result.actual && <div><span style={{ color: '#555' }}>Actual: </span><span style={{ color: result.passed ? '#34d399' : '#f87171' }}>{result.actual}</span></div>}
                      </div>
                      {result.details && <div style={{ fontSize: 9, color: '#777', marginTop: 2 }}>{result.details}</div>}
                    </div>
                  )}
                  <AssertionPlayground assertionId={a.id || a.name} />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </>
  );
}

/* ═══════════════════════════════════════════════
   TAB 4: BUGS
   ═══════════════════════════════════════════════ */
function BugsTab({ bugs, sty, showToast, onRefresh }) {
  const [filter, setFilter] = useState('open');
  const [expanded, setExpanded] = useState(null);
  const [adding, setAdding] = useState(false);
  const [newBug, setNewBug] = useState({ name: '', query: '', expected_behavior: '', actual_behavior: '', severity: 'medium' });
  const [submitting, setSubmitting] = useState(false);

  const openCount = bugs.filter(b => b.status === 'open' || b.status === 'failing').length;
  const filtered = bugs.filter(b => {
    if (filter === 'open') return b.status === 'open' || b.status === 'failing';
    if (filter === 'fixed') return b.status === 'fixed' || b.status === 'wontfix';
    return true;
  });

  const updateBugStatus = async (bugId, newStatus) => {
    try {
      const res = await fetch(`${API}/qa/bugs/${bugId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus }),
      });
      if (res.ok) {
        showToast(`Bug ${bugId} → ${newStatus}`);
        onRefresh();
      } else {
        showToast(`Status update failed: HTTP ${res.status}`, 'error');
      }
    } catch (e) {
      showToast(`Failed: ${e.message}`, 'error');
    }
  };

  const submitBug = async () => {
    if (!newBug.name.trim()) return;
    setSubmitting(true);
    try {
      const res = await fetch(`${API}/qa/bugs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newBug),
      });
      if (res.ok) {
        showToast('Bug added');
        setAdding(false);
        setNewBug({ name: '', query: '', expected_behavior: '', actual_behavior: '', severity: 'medium' });
        onRefresh();
      } else {
        showToast(`Failed: HTTP ${res.status}`, 'error');
      }
    } catch (e) {
      showToast(`Failed: ${e.message}`, 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const inputStyle = {
    width: '100%', background: 'rgba(0,0,0,0.2)', border: '1px solid rgba(255,255,255,0.06)',
    borderRadius: 3, padding: '4px 6px', color: '#c0c0d0', fontSize: 10,
    fontFamily: "'JetBrains Mono', monospace", outline: 'none', marginBottom: 4,
  };

  return (
    <>
      <div style={{ display: 'flex', gap: 4, marginBottom: 10, alignItems: 'center' }}>
        {['open', 'fixed', 'all'].map(f => (
          <Pill key={f} active={filter === f} onClick={() => setFilter(f)}>
            {f.charAt(0).toUpperCase() + f.slice(1)}
          </Pill>
        ))}
        <Badge color="#f87171" style={{ marginLeft: 8 }}>{openCount} open</Badge>
        <Badge color="#555">{bugs.length} total</Badge>
        <ActionButton onClick={() => setAdding(!adding)} primary style={{ marginLeft: 'auto' }}>
          {adding ? 'Cancel' : 'Add Bug'}
        </ActionButton>
      </div>

      {/* Add bug form */}
      {adding && (
        <div style={{ ...sty.panel, padding: 12 }}>
          <div style={sty.label}>New Bug Report</div>
          <input style={inputStyle} placeholder="Bug name" value={newBug.name} onChange={e => setNewBug({ ...newBug, name: e.target.value })} />
          <input style={inputStyle} placeholder="Trigger query" value={newBug.query} onChange={e => setNewBug({ ...newBug, query: e.target.value })} />
          <input style={inputStyle} placeholder="Expected behavior" value={newBug.expected_behavior} onChange={e => setNewBug({ ...newBug, expected_behavior: e.target.value })} />
          <input style={inputStyle} placeholder="Actual behavior" value={newBug.actual_behavior} onChange={e => setNewBug({ ...newBug, actual_behavior: e.target.value })} />
          <div style={{ display: 'flex', gap: 4, marginTop: 4, alignItems: 'center' }}>
            <span style={{ fontSize: 9, color: '#555' }}>Severity:</span>
            {['low', 'medium', 'high', 'critical'].map(s => (
              <Pill key={s} active={newBug.severity === s} onClick={() => setNewBug({ ...newBug, severity: s })}>{s}</Pill>
            ))}
            <ActionButton onClick={submitBug} loading={submitting} disabled={!newBug.name.trim()} primary style={{ marginLeft: 'auto' }}>
              Submit
            </ActionButton>
          </div>
        </div>
      )}

      <div style={{ maxHeight: 'calc(100vh - 200px)', overflow: 'auto' }}>
        {filtered.length === 0 ? (
          <div style={{ ...sty.panel, color: '#555', fontSize: 11 }}>No bugs match this filter.</div>
        ) : filtered.map((b, i) => {
          const isOpen = expanded === (b.id || i);
          return (
            <div key={b.id || i} style={{ ...sty.panel, padding: 0, overflow: 'hidden' }}>
              <div
                onClick={() => setExpanded(isOpen ? null : (b.id || i))}
                style={{ ...sty.clickRow, padding: '8px 12px' }}
                onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.02)'}
                onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
              >
                <Badge color={BUG_STATUS_COLORS[b.status] || '#666'}>{b.status}</Badge>
                <span style={{ color: '#555', fontSize: 9 }}>{b.id}</span>
                <span style={{ flex: 1, color: '#e0e0f0' }}>{b.name || b.title || b.description || `Bug #${b.id}`}</span>
                <Badge color={SEV_COLORS[b.severity] || '#fbbf24'}>{b.severity}</Badge>
                {b.date_found && <span style={{ color: '#555', fontSize: 9 }}>{timeAgo(b.date_found)}</span>}
                <span style={{ color: '#555', fontSize: 8 }}>{isOpen ? '▲' : '▼'}</span>
              </div>

              {isOpen && (
                <div style={{ padding: '10px 12px', background: 'rgba(0,0,0,0.15)' }}>
                  {b.query && (
                    <div style={{ marginBottom: 6 }}>
                      <div style={{ fontSize: 9, color: '#555' }}>Trigger Query</div>
                      <div style={{ fontSize: 10, color: '#94a3b8' }}>{b.query}</div>
                    </div>
                  )}
                  {b.expected_behavior && (
                    <div style={{ marginBottom: 6 }}>
                      <div style={{ fontSize: 9, color: '#555' }}>Expected</div>
                      <div style={{ fontSize: 10, color: '#34d399' }}>{b.expected_behavior}</div>
                    </div>
                  )}
                  {b.actual_behavior && (
                    <div style={{ marginBottom: 6 }}>
                      <div style={{ fontSize: 9, color: '#555' }}>Actual</div>
                      <div style={{ fontSize: 10, color: '#f87171' }}>{b.actual_behavior}</div>
                    </div>
                  )}
                  {b.root_cause && (
                    <div style={{ marginBottom: 6 }}>
                      <div style={{ fontSize: 9, color: '#555' }}>Root Cause</div>
                      <div style={{ fontSize: 10, color: '#94a3b8' }}>{b.root_cause}</div>
                    </div>
                  )}
                  <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 6, fontSize: 9 }}>
                    {b.date_found && <Badge color="#555">Found: {new Date(b.date_found).toLocaleDateString()}</Badge>}
                    {b.date_fixed && <Badge color="#34d399">Fixed: {new Date(b.date_fixed).toLocaleDateString()}</Badge>}
                  </div>
                  <div style={{ display: 'flex', gap: 4, marginTop: 6 }}>
                    {(b.status === 'open' || b.status === 'failing') && (
                      <>
                        <ActionButton onClick={() => updateBugStatus(b.id, 'fixed')} primary>Mark Fixed</ActionButton>
                        <ActionButton onClick={() => updateBugStatus(b.id, 'wontfix')}>Won't Fix</ActionButton>
                      </>
                    )}
                    {(b.status === 'fixed' || b.status === 'wontfix') && (
                      <ActionButton onClick={() => updateBugStatus(b.id, 'open')}>Reopen</ActionButton>
                    )}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </>
  );
}

/* ═══════════════════════════════════════════════
   TAB 5: EVENTS
   ═══════════════════════════════════════════════ */
function EventsTab({ events, summary, sty }) {
  const [sourceFilter, setSourceFilter] = useState('all');
  const [sevFilter, setSevFilter] = useState('all');

  const sources = [...new Set(events.map(e => e.source).filter(Boolean))];
  const severities = [...new Set(events.map(e => e.severity).filter(Boolean))];

  const filtered = events.filter(e => {
    if (sourceFilter !== 'all' && e.source !== sourceFilter) return false;
    if (sevFilter !== 'all' && e.severity !== sevFilter) return false;
    return true;
  });

  return (
    <>
      {/* Summary chips */}
      {summary && (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 10 }}>
          <Badge color="#60a5fa">{summary.total || 0} events ({summary.hours || 24}h)</Badge>
          {summary.by_source && Object.entries(summary.by_source).map(([k, v]) => (
            <Badge key={k} color="#818cf8">{k}: {v}</Badge>
          ))}
          {summary.by_severity && Object.entries(summary.by_severity).map(([k, v]) => (
            <Badge key={k} color={SEV_COLORS[k] || '#fbbf24'}>{k}: {v}</Badge>
          ))}
        </div>
      )}

      {/* Filters */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 6, flexWrap: 'wrap' }}>
        <Pill active={sourceFilter === 'all'} onClick={() => setSourceFilter('all')}>All Sources</Pill>
        {sources.map(s => (
          <Pill key={s} active={sourceFilter === s} onClick={() => setSourceFilter(s)}>{s}</Pill>
        ))}
      </div>
      <div style={{ display: 'flex', gap: 4, marginBottom: 10, flexWrap: 'wrap' }}>
        <Pill active={sevFilter === 'all'} onClick={() => setSevFilter('all')}>All Severity</Pill>
        {severities.map(s => (
          <Pill key={s} active={sevFilter === s} onClick={() => setSevFilter(s)}>{s}</Pill>
        ))}
      </div>

      <div style={{ maxHeight: 'calc(100vh - 220px)', overflow: 'auto' }}>
        {filtered.length === 0 ? (
          <div style={{ ...sty.panel, color: '#555', fontSize: 11 }}>
            No system events recorded. Watchdog alerts, health check failures, and API errors appear here.
          </div>
        ) : filtered.map((ev, i) => (
          <div key={ev.id || i} style={{
            ...sty.clickRow, cursor: 'default',
            padding: '6px 8px', borderBottom: '1px solid rgba(255,255,255,0.04)',
          }}>
            <Badge color={SEV_COLORS[ev.severity] || '#fbbf24'}>{ev.severity}</Badge>
            <Badge color={ev.source === 'api_error' ? '#f87171' : ev.source === 'watchdog' ? '#fb923c' : '#7dd3fc'}>{ev.source}</Badge>
            {ev.component && <span style={{ color: '#818cf8', fontSize: 9 }}>{ev.component}</span>}
            <span style={{ flex: 1, color: '#94a3b8', fontSize: 10 }}>{ev.message}</span>
            {ev.timestamp && <span style={{ color: '#555', fontSize: 9, whiteSpace: 'nowrap' }}>{timeAgo(ev.timestamp)}</span>}
          </div>
        ))}
      </div>
    </>
  );
}
