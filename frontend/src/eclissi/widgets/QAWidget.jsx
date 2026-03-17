import React, { useState, useEffect } from 'react';

export default function QAWidget() {
  const [health, setHealth] = useState(null);
  const [lastReport, setLastReport] = useState(null);

  useEffect(() => {
    const poll = async () => {
      try {
        const [hRes, lRes] = await Promise.all([
          fetch('/qa/health'),
          fetch('/qa/last'),
        ]);
        if (hRes.ok) setHealth(await hRes.json());
        if (lRes.ok) {
          const data = await lRes.json();
          if (!data.error) setLastReport(data);
        }
      } catch {}
    };
    poll();
    const id = setInterval(poll, 5000);
    return () => clearInterval(id);
  }, []);

  const passRate = health?.pass_rate != null ? health.pass_rate * 100 : null;
  const totalRuns = health?.total_24h || 0;
  const failedRuns = health?.failed_24h || 0;
  const passed = lastReport?.passed;
  const failedCount = lastReport?.failed_count || 0;
  const topFailures = health?.top_failures || [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {/* Pass rate */}
      <div style={{ textAlign: 'center', padding: '8px 0' }}>
        <div
          className="ec-font-display"
          style={{
            fontSize: 42,
            fontWeight: 300,
            color: passRate == null
              ? 'var(--ec-text-faint)'
              : passRate >= 90
              ? '#22c55e'
              : passRate >= 70
              ? '#f59e0b'
              : 'var(--ec-accent-qa)',
          }}
        >
          {passRate != null ? `${passRate.toFixed(0)}%` : '—'}
        </div>
        <div className="ec-font-label" style={{ fontSize: 9, color: 'var(--ec-text-faint)' }}>
          PASS RATE · {totalRuns} runs · {failedRuns} failed
        </div>
      </div>

      {/* Last report */}
      {lastReport && (
        <div className="ec-glass-interactive" style={{ padding: '10px 12px', borderRadius: 6 }}>
          <div className="ec-font-label" style={{ fontSize: 9, color: 'var(--ec-text-faint)', marginBottom: 6 }}>
            LAST REPORT
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: 20,
                height: 20,
                borderRadius: 4,
                background: passed ? 'rgba(34,197,94,0.15)' : 'rgba(248,113,113,0.15)',
                fontSize: 11,
              }}
            >
              {passed ? '✓' : '✗'}
            </span>
            <span className="ec-font-body" style={{ fontSize: 11, color: passed ? '#22c55e' : 'var(--ec-accent-qa)' }}>
              {passed ? 'PASSED' : `${failedCount} FAILED`}
            </span>
            {lastReport.latency_ms && (
              <span style={{ fontSize: 9, color: 'var(--ec-text-faint)', marginLeft: 'auto', fontFamily: "'JetBrains Mono',monospace" }}>
                {Math.round(lastReport.latency_ms)}ms
              </span>
            )}
          </div>
          {lastReport.query && (
            <div className="ec-font-body" style={{ fontSize: 11, color: 'var(--ec-text-soft)', lineHeight: 1.4 }}>
              "{lastReport.query.substring(0, 80)}{lastReport.query.length > 80 ? '...' : ''}"
            </div>
          )}

          {/* Failed assertion IDs */}
          {!passed && lastReport.assertions && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 3, marginTop: 6 }}>
              {lastReport.assertions.filter(a => !a.passed).map(a => (
                <span key={a.id} style={{
                  fontSize: 8, fontWeight: 700, padding: '1px 5px', borderRadius: 3,
                  color: '#ef4444', background: 'rgba(239,68,68,0.1)',
                }}>
                  {a.id}
                </span>
              ))}
            </div>
          )}

          {!passed && lastReport.diagnosis && (
            <div
              className="ec-font-body"
              style={{
                fontSize: 10,
                color: 'var(--ec-accent-qa)',
                marginTop: 6,
                padding: '6px 8px',
                borderRadius: 4,
                background: 'rgba(248,113,113,0.08)',
                border: '1px solid rgba(248,113,113,0.15)',
                lineHeight: 1.4,
              }}
            >
              {lastReport.diagnosis.substring(0, 200)}{lastReport.diagnosis.length > 200 ? '...' : ''}
            </div>
          )}

          {lastReport.timestamp && (
            <div style={{ fontSize: 9, color: 'var(--ec-text-faint)', marginTop: 4 }}>
              {new Date(lastReport.timestamp).toLocaleString()}
            </div>
          )}
        </div>
      )}

      {/* Top failures */}
      {topFailures.length > 0 && (
        <div className="ec-glass-interactive" style={{ padding: '8px 12px', borderRadius: 6 }}>
          <div className="ec-font-label" style={{ fontSize: 9, color: 'var(--ec-text-faint)', marginBottom: 4 }}>
            TOP FAILURES (24H)
          </div>
          {topFailures.slice(0, 3).map(f => (
            <div key={f.id} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '2px 0' }}>
              <span style={{
                fontSize: 8, fontWeight: 700, padding: '1px 5px', borderRadius: 3,
                color: '#ef4444', background: 'rgba(239,68,68,0.1)', fontFamily: "'JetBrains Mono',monospace",
              }}>
                {f.id}
              </span>
              <span style={{ fontSize: 10, color: 'var(--ec-text-soft)', flex: 1 }}>{f.name}</span>
              <span style={{ fontSize: 10, color: '#ef4444', fontWeight: 600, fontFamily: "'JetBrains Mono',monospace" }}>{f.count}x</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
