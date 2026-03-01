import React, { useState, useEffect } from 'react';

const PROBE_ICONS = {
  warmth: '🤗',
  memory_grounding: '🧠',
  boundary_holding: '🛡️',
  humor_timing: '😄',
  identity_stability: '🪞',
};

export default function VKWidget() {
  const [results, setResults] = useState(null);

  useEffect(() => {
    const poll = async () => {
      try {
        let res = await fetch('/vk/results/latest');
        if (res.ok) {
          const data = await res.json();
          if (!data.error) { setResults(data); return; }
        }
        res = await fetch('/vk/results/voice-memory');
        if (res.ok) {
          const data = await res.json();
          if (!data.error) setResults(data);
        }
      } catch {}
    };
    poll();
    const id = setInterval(poll, 30000);
    return () => clearInterval(id);
  }, []);

  if (!results) {
    return (
      <div style={{ color: 'var(--ec-text-faint)', fontSize: 12, textAlign: 'center', padding: 20 }}>
        No VK results yet
      </div>
    );
  }

  const passed = results.passed_count || 0;
  const failed = results.failed_count || 0;
  const total = passed + failed || 1;
  const passRate = ((passed / total) * 100).toFixed(0);
  const allPassed = failed === 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Status banner */}
      <div
        className="ec-glass-interactive"
        style={{
          padding: '12px',
          borderRadius: 8,
          textAlign: 'center',
          borderColor: allPassed ? 'rgba(34,197,94,0.2)' : 'rgba(248,113,113,0.2)',
        }}
      >
        <div style={{ fontSize: 24, marginBottom: 4 }}>{allPassed ? '✅' : '⚠️'}</div>
        <div className="ec-font-label" style={{ fontSize: 10, color: allPassed ? '#22c55e' : 'var(--ec-accent-vk)' }}>
          {allPassed ? 'ALL PROBES PASSED' : `${failed} PROBE(S) FAILED`}
        </div>
        <div className="ec-font-mono" style={{ fontSize: 11, color: 'var(--ec-text-faint)', marginTop: 2 }}>
          {passRate}% ({passed}/{total})
        </div>
      </div>

      {/* Probe results */}
      {results.probes && (
        <div>
          <div className="ec-font-label" style={{ fontSize: 9, color: 'var(--ec-text-faint)', marginBottom: 8 }}>
            PROBES
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {results.probes.map((probe, i) => {
              const icon = PROBE_ICONS[probe.name] || '🔬';
              return (
                <div
                  key={i}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '4px 8px',
                    borderRadius: 4,
                    background: 'rgba(255,255,255,0.02)',
                  }}
                >
                  <span style={{ fontSize: 11 }}>
                    {icon} <span className="ec-font-body" style={{ fontSize: 11, color: 'var(--ec-text-soft)', textTransform: 'capitalize' }}>
                      {(probe.name || '').replace(/_/g, ' ')}
                    </span>
                  </span>
                  <span style={{ fontSize: 11, color: probe.passed ? '#22c55e' : 'var(--ec-accent-qa)' }}>
                    {probe.passed ? '✓' : '✗'}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
