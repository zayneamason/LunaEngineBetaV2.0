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

  const passRate = health?.pass_rate;
  const totalRuns = health?.total_runs || 0;
  const passed = lastReport?.passed;
  const failedCount = lastReport?.failed_count || 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Pass rate */}
      <div style={{ textAlign: 'center', padding: '12px 0' }}>
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
          PASS RATE ({totalRuns} runs)
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
          </div>
          {lastReport.query && (
            <div className="ec-font-body" style={{ fontSize: 11, color: 'var(--ec-text-soft)', lineHeight: 1.4 }}>
              "{lastReport.query.substring(0, 80)}{lastReport.query.length > 80 ? '...' : ''}"
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
              {lastReport.diagnosis.substring(0, 120)}{lastReport.diagnosis.length > 120 ? '...' : ''}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
