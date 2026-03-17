import React, { useState, useCallback, useEffect, useRef } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import EngineNode from './EngineNode';
import AnimatedEdge from './AnimatedEdge';
import DetailPanel from './DetailPanel';
import TracePanel, { getTracePhaseLabel } from './TracePanel';
import { initialNodes, initialEdges, defaultEdgeOptions, legendItems } from './pipelineData';
import { useLiveData, applyLiveData, applyLiveEdges, ASSERTION_NODE_MAP } from './useLiveData';

const nodeTypes = { engine: EngineNode };
const edgeTypes = { animated: AnimatedEdge };

export default function PipelineView() {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [selectedNode, setSelectedNode] = useState(null);
  const [showQaDrop, setShowQaDrop] = useState(false);
  const [showTrace, setShowTrace] = useState(false);
  const [traceState, setTraceState] = useState(null);
  const { data: liveData, connected, lastUpdate } = useLiveData(2000);

  useEffect(() => {
    if (!liveData) return;
    setNodes(prev => {
      let updated = applyLiveData(prev, liveData);
      // Apply trace decoration if active
      if (traceState?.active) {
        updated = applyTraceDecoration(updated, traceState);
      }
      return updated;
    });
    setEdges(prev => applyLiveEdges(prev, liveData));
  }, [liveData, setNodes, setEdges, traceState]);

  // Also apply trace decoration when traceState changes independently
  useEffect(() => {
    if (!traceState) return;
    setNodes(prev => applyTraceDecoration(prev, traceState));
  }, [traceState, setNodes]);

  const onNodeClick = useCallback((_, node) => setSelectedNode(node), []);
  const onPaneClick = useCallback(() => setSelectedNode(null), []);

  const minimapNodeColor = useCallback((n) => {
    const t = n.data?.nodeType;
    if (t === 'broken') return '#ef4444';
    if (t === 'memory') return '#22c55e';
    if (t === 'input') return '#06b6d4';
    if (t === 'guard') return '#a855f7';
    if (t === 'context') return '#ec4899';
    if (t === 'output') return '#f59e0b';
    return '#6366f1';
  }, []);

  const timeStr = lastUpdate
    ? lastUpdate.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : '--:--:--';

  // Derive QA state directly from polled data
  const qaLast = liveData?.qaLast;
  const qaBugs = liveData?.qaBugs;
  const qaGlobal = qaLast ? {
    passed: qaLast.passed,
    failedCount: qaLast.failed_count,
    route: qaLast.route,
    provider: qaLast.provider_used,
    diagnosis: qaLast.diagnosis,
    latency: qaLast.latency_ms,
  } : null;
  const openBugs = Array.isArray(qaBugs) ? qaBugs.filter(b => b.status === 'open') : [];
  const hasCriticalBugs = openBugs.some(b => b.severity === 'critical');

  return (
    <div style={{ width: '100%', height: '100%', background: '#08080f', position: 'relative', display: 'flex', flexDirection: 'column' }}>
      {/* HUD */}
      <div style={{ position: 'absolute', top: 14, left: 14, zIndex: 50, fontFamily: "'JetBrains Mono', monospace" }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: '#e0e0f0', letterSpacing: '0.5px' }}>ENGINE PIPELINE</div>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 5, padding: '2px 10px', borderRadius: 6,
            background: connected ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)',
            border: `1px solid ${connected ? 'rgba(34,197,94,0.25)' : 'rgba(239,68,68,0.25)'}`,
          }}>
            <div style={{
              width: 6, height: 6, borderRadius: '50%',
              background: connected ? '#22c55e' : '#ef4444',
              animation: connected ? 'pulse-green 2.5s ease-in-out infinite' : 'pulse-red 1s ease-in-out infinite',
            }} />
            <span style={{ fontSize: 9, color: connected ? '#22c55e' : '#ef4444' }}>
              {connected ? `LIVE :8000 · ${timeStr}` : 'DISCONNECTED'}
            </span>
          </div>
          {/* QA health badge */}
          <div
            onClick={() => setShowQaDrop(p => !p)}
            style={{
              display: 'flex', alignItems: 'center', gap: 5, padding: '2px 10px', borderRadius: 6,
              cursor: 'pointer', position: 'relative',
              background: !qaGlobal ? 'rgba(102,102,128,0.1)'
                : qaGlobal.passed ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)',
              border: `1px solid ${!qaGlobal ? 'rgba(102,102,128,0.2)'
                : qaGlobal.passed ? 'rgba(34,197,94,0.25)' : 'rgba(239,68,68,0.25)'}`,
            }}>
            <span style={{
              fontSize: 9,
              color: !qaGlobal ? '#666680' : qaGlobal.passed ? '#22c55e' : '#ef4444',
            }}>
              {!qaGlobal ? 'QA —'
                : qaGlobal.passed ? 'QA ✅'
                : `QA ⛔ ${qaGlobal.failedCount || '?'} failures`}
            </span>
            {showQaDrop && qaGlobal && !qaGlobal.passed && (
              <div style={{
                position: 'absolute', top: '100%', left: 0, marginTop: 4,
                background: '#12121a', border: '1px solid rgba(239,68,68,0.15)',
                borderRadius: 8, padding: '10px 12px', minWidth: 260, zIndex: 200,
                boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
                fontFamily: "'JetBrains Mono', monospace",
              }}>
                <div style={{ fontSize: 9, color: '#888', marginBottom: 4 }}>
                  {qaGlobal.route} · {qaGlobal.provider} · {qaGlobal.latency ? `${qaGlobal.latency}ms` : '—'}
                </div>
                {qaGlobal.diagnosis && (
                  <div style={{ fontSize: 9.5, color: '#f59e0b', lineHeight: 1.5, marginBottom: 6 }}>
                    {qaGlobal.diagnosis}
                  </div>
                )}
              </div>
            )}
          </div>
          {/* Trace button */}
          <div
            onClick={() => setShowTrace(p => !p)}
            style={{
              display: 'flex', alignItems: 'center', gap: 5, padding: '2px 10px', borderRadius: 6,
              cursor: 'pointer',
              background: showTrace ? 'rgba(6,182,212,0.12)' : 'rgba(102,102,128,0.1)',
              border: `1px solid ${showTrace ? 'rgba(6,182,212,0.3)' : 'rgba(102,102,128,0.2)'}`,
            }}
          >
            <span style={{ fontSize: 9, color: showTrace ? '#06b6d4' : '#666680' }}>
              {traceState?.active ? 'TRACING...' : 'TRACE'}
            </span>
          </div>
        </div>
        <div style={{ fontSize: 9.5, color: '#555568', marginTop: 3 }}>
          Drag nodes · Click for detail · Scroll to zoom · Polling every 2s
        </div>
        <div style={{ display: 'flex', gap: 14, marginTop: 8, flexWrap: 'wrap' }}>
          {legendItems.map(({ color, label }) => (
            <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 9.5, color: '#555568' }}>
              <div style={{ width: 7, height: 7, borderRadius: 2, background: color }} />
              {label}
            </div>
          ))}
        </div>
      </div>

      <div style={{ flex: 1, minHeight: 0 }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={onNodeClick}
          onPaneClick={onPaneClick}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          defaultEdgeOptions={defaultEdgeOptions}
          fitView
          fitViewOptions={{ padding: 0.15 }}
          style={{ background: '#08080f' }}
          minZoom={0.15}
          maxZoom={3}
          snapToGrid
          snapGrid={[20, 20]}
        >
          <Background color="rgba(255,255,255,0.015)" gap={20} size={1} />
          <Controls position="bottom-left" />
          <MiniMap
            nodeColor={minimapNodeColor}
            maskColor="rgba(8,8,15,0.85)"
            style={{ background: '#0a0a14' }}
            position="bottom-right"
          />
          {hasCriticalBugs && (
            <div style={{
              position: 'absolute', bottom: 14, right: 14, zIndex: 60,
              width: 10, height: 10, borderRadius: '50%',
              background: '#ef4444', border: '2px solid #0a0a14',
              boxShadow: '0 0 8px rgba(239,68,68,0.5)',
              animation: 'pulse-red 1.5s ease-in-out infinite',
              pointerEvents: 'none',
            }} />
          )}
        </ReactFlow>
      </div>

      {/* Trace panel */}
      {showTrace && <TracePanel onTraceState={setTraceState} />}

      {selectedNode && (
        <DetailPanel
          node={selectedNode}
          onClose={() => setSelectedNode(null)}
          edges={edges}
          nodes={nodes}
          liveData={liveData}
        />
      )}
    </div>
  );
}

// Apply trace decoration to nodes
function applyTraceDecoration(nodes, traceState) {
  if (!traceState?.active) {
    // Clear trace decorations
    return nodes.map(n => {
      if (n.data.tracePhase != null || n.data.traceActive || n.data.traceFailed) {
        return { ...n, data: { ...n.data, tracePhase: null, traceActive: false, traceFailed: false } };
      }
      return n;
    });
  }

  const { activeNodes, failedNodes, result } = traceState;
  return nodes.map(n => {
    const isActive = activeNodes?.has(n.id);
    const isFailed = failedNodes?.has(n.id);
    const isPassed = result && isActive && !isFailed;
    const phaseLabel = isActive ? getTracePhaseLabel(n.id) : null;

    if (isActive || n.data.traceActive) {
      return {
        ...n,
        data: {
          ...n.data,
          traceActive: isActive,
          traceFailed: isFailed,
          tracePassed: isPassed && !!result,
          tracePhase: phaseLabel,
        },
      };
    }
    return n;
  });
}
