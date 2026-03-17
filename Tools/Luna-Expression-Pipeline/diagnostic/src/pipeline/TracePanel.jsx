import React, { useState, useRef, useCallback } from 'react';
import { ASSERTION_NODE_MAP } from './useLiveData';

const API = '';
const MONO = "'JetBrains Mono', monospace";

// Trace phases: cosmetic timing for node animation
const TRACE_PHASES = [
  { delay: 0,    duration: 200,  color: '#06b6d4', nodes: ['buffer', 'dispatch'] },
  { delay: 200,  duration: 300,  color: '#4ade80', nodes: ['router', 'mem_ret', 'matrix_actor', 'matrix_db'] },
  { delay: 500,  duration: 500,  color: '#f472b6', nodes: ['hist_load', 'context', 'ring_inner', 'ring_mid', 'sysprompt'] },
  { delay: 1000, duration: 0,    color: '#f59e0b', nodes: ['director', 'scout'] },
];

// Node → phase index lookup (for numbered badges)
const NODE_PHASE = {};
TRACE_PHASES.forEach((phase, idx) => {
  phase.nodes.forEach(n => { NODE_PHASE[n] = idx; });
});

const PHASE_LABELS = ['①', '②', '③', '④'];

export function getTracePhase(nodeId) {
  return NODE_PHASE[nodeId] ?? null;
}

export function getTracePhaseLabel(nodeId) {
  const p = NODE_PHASE[nodeId];
  return p != null ? PHASE_LABELS[p] : null;
}

export default function TracePanel({ onTraceState }) {
  const [query, setQuery] = useState('');
  const [tracing, setTracing] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [expanded, setExpanded] = useState(false);
  const abortRef = useRef(null);

  const runTrace = useCallback(async () => {
    if (!query.trim() || tracing) return;

    setTracing(true);
    setResult(null);
    setError(null);
    setExpanded(false);

    // Notify parent: trace started, animate nodes in phases
    const activeNodes = new Set();
    const timers = [];

    TRACE_PHASES.forEach((phase, idx) => {
      const t = setTimeout(() => {
        phase.nodes.forEach(n => activeNodes.add(n));
        onTraceState?.({
          active: true,
          phase: idx,
          activeNodes: new Set(activeNodes),
          result: null,
        });
      }, phase.delay);
      timers.push(t);
    });

    try {
      abortRef.current = new AbortController();
      const res = await fetch(`${API}/qa/simulate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: query.trim() }),
        signal: abortRef.current.signal,
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      // Clear phase timers
      timers.forEach(clearTimeout);

      // Compute which nodes failed via assertion mapping
      const failedNodes = new Set();
      if (data.assertions) {
        for (const a of data.assertions) {
          if (!a.passed) {
            const mapped = ASSERTION_NODE_MAP[a.id] || [];
            mapped.forEach(n => failedNodes.add(n));
          }
        }
      }

      setResult(data);
      onTraceState?.({
        active: true,
        phase: 4,
        activeNodes: new Set([...activeNodes, 'textout']),
        result: data,
        failedNodes,
      });
    } catch (e) {
      if (e.name !== 'AbortError') {
        setError(e.message);
        timers.forEach(clearTimeout);
        onTraceState?.({ active: false, phase: -1, activeNodes: new Set(), result: null, failedNodes: new Set() });
      }
    } finally {
      setTracing(false);
    }
  }, [query, tracing, onTraceState]);

  const clearTrace = useCallback(() => {
    if (abortRef.current) abortRef.current.abort();
    setTracing(false);
    setResult(null);
    setError(null);
    setExpanded(false);
    onTraceState?.({ active: false, phase: -1, activeNodes: new Set(), result: null, failedNodes: new Set() });
  }, [onTraceState]);

  const failedAssertions = result?.assertions?.filter(a => !a.passed) || [];

  return (
    <div style={{
      borderTop: '1px solid rgba(255,255,255,0.06)',
      background: '#0a0a14',
      padding: '12px 16px',
      fontFamily: MONO,
      flexShrink: 0,
    }}>
      {/* Input bar */}
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: result || error ? 10 : 0 }}>
        <div style={{
          display: 'flex', gap: 6, alignItems: 'center', flex: 1,
          padding: '7px 12px', borderRadius: 6,
          background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)',
        }}>
          <span style={{ fontSize: 11, opacity: 0.3 }}>⟐</span>
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && runTrace()}
            placeholder="Type a message to trace through the pipeline..."
            disabled={tracing}
            style={{
              flex: 1, background: 'transparent', border: 'none', outline: 'none',
              color: '#e0e0f0', fontSize: 11, fontFamily: MONO,
            }}
          />
        </div>
        <button
          onClick={runTrace}
          disabled={tracing || !query.trim()}
          style={{
            padding: '7px 16px', borderRadius: 6, border: '1px solid rgba(6,182,212,0.3)',
            background: tracing ? 'rgba(6,182,212,0.08)' : 'rgba(6,182,212,0.12)',
            color: tracing ? '#555' : '#06b6d4',
            fontSize: 10, fontFamily: MONO, fontWeight: 600, letterSpacing: 0.5,
            cursor: tracing ? 'wait' : 'pointer',
          }}
        >
          {tracing ? 'TRACING...' : 'TRACE'}
        </button>
        {(result || error) && (
          <button
            onClick={clearTrace}
            style={{
              padding: '7px 10px', borderRadius: 6, border: '1px solid rgba(255,255,255,0.06)',
              background: 'transparent', color: '#555', fontSize: 10, fontFamily: MONO,
              cursor: 'pointer',
            }}
          >
            CLEAR
          </button>
        )}
      </div>

      {/* Error */}
      {error && (
        <div style={{ fontSize: 10, color: '#f87171', padding: '6px 0' }}>
          Trace failed: {error}
        </div>
      )}

      {/* Results */}
      {result && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {/* Summary row */}
          <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
            {/* Pass/fail badge */}
            <span style={{
              fontSize: 9, padding: '2px 8px', borderRadius: 4, fontWeight: 600,
              background: result.passed ? 'rgba(34,197,94,0.12)' : 'rgba(239,68,68,0.12)',
              color: result.passed ? '#22c55e' : '#ef4444',
              border: `1px solid ${result.passed ? 'rgba(34,197,94,0.25)' : 'rgba(239,68,68,0.25)'}`,
            }}>
              {result.passed ? 'QA PASSED' : `QA FAILED · ${result.failed_count} failures`}
            </span>

            {/* Route */}
            {(result.route || result.provider) && (
              <span style={{ fontSize: 9, color: '#818cf8' }}>
                {result.route || '—'} → {result.provider || '—'}
              </span>
            )}

            {/* Latency */}
            {result.latency_ms != null && (
              <span style={{ fontSize: 9, color: '#555' }}>
                {result.latency_ms < 1000
                  ? `${result.latency_ms.toFixed(0)}ms`
                  : `${(result.latency_ms / 1000).toFixed(1)}s`}
              </span>
            )}
          </div>

          {/* Response preview */}
          {result.final_response && (
            <div style={{
              padding: '8px 12px', borderRadius: 6,
              background: 'rgba(255,255,255,0.015)', border: '1px solid rgba(255,255,255,0.04)',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                <span style={{ fontSize: 8, color: '#555', letterSpacing: 1 }}>RESPONSE</span>
                <span
                  onClick={() => setExpanded(!expanded)}
                  style={{ fontSize: 8, color: '#818cf8', cursor: 'pointer' }}
                >
                  {expanded ? '▲ Collapse' : '▼ Expand'}
                </span>
              </div>
              <div style={{
                fontSize: 10, color: '#a0a0b0', lineHeight: 1.5,
                maxHeight: expanded ? 'none' : 48, overflow: 'hidden',
                whiteSpace: 'pre-wrap', wordBreak: 'break-word',
              }}>
                {result.final_response}
              </div>
            </div>
          )}

          {/* Failed assertions */}
          {failedAssertions.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {failedAssertions.map((a, i) => (
                <div key={i} style={{
                  display: 'flex', alignItems: 'center', gap: 8, fontSize: 9,
                  padding: '4px 8px', borderRadius: 4,
                  background: 'rgba(239,68,68,0.04)', border: '1px solid rgba(239,68,68,0.08)',
                }}>
                  <span style={{
                    padding: '1px 5px', borderRadius: 3, fontWeight: 600,
                    background: a.severity === 'high' ? 'rgba(239,68,68,0.15)' : 'rgba(245,158,11,0.15)',
                    color: a.severity === 'high' ? '#ef4444' : '#f59e0b',
                  }}>{a.id}</span>
                  <span style={{ color: '#888' }}>{a.name}</span>
                  {a.actual && (
                    <span style={{ color: '#f87171', marginLeft: 'auto' }}>
                      {typeof a.actual === 'string' ? a.actual.slice(0, 80) : String(a.actual)}
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Diagnosis */}
          {result.diagnosis && (
            <div style={{
              fontSize: 9.5, color: '#f59e0b', padding: '6px 8px',
              background: 'rgba(245,158,11,0.04)', borderRadius: 4, lineHeight: 1.5,
            }}>
              {result.diagnosis}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
