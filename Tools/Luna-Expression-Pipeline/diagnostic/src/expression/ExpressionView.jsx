import React, { useState, useCallback, useEffect, useRef, useMemo } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  getBezierPath,
  BaseEdge,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import ExpressionNode from './ExpressionNode';
import OrbPreview from './OrbPreview';
import DimensionSliders from './DimensionSliders';
import TriagePanel from './TriagePanel';
import ScenarioRunner from './ScenarioRunner';
import { useOrbConnection } from './useOrbConnection';
import { initialNodes, initialEdges, EDGE_DEFS, SCENARIOS, TYPES } from './expressionData';

// Custom edge for expression pipeline
function ExpressionEdge({ id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, data, source }) {
  const [edgePath] = getBezierPath({ sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition });
  const hot = data?.lit;
  const srcNode = initialNodes.find(n => n.id === source);
  const accent = TYPES[srcNode?.data?.nodeType]?.accent || '#818cf8';

  return (
    <>
      <BaseEdge id={id} path={edgePath} style={{
        stroke: hot ? accent + '66' : accent + '16',
        strokeWidth: hot ? 2 : 1,
        strokeDasharray: hot ? undefined : '4 3',
        transition: 'stroke 0.4s, stroke-width 0.3s',
      }} />
      <circle r={hot ? 3 : 1.8} fill={accent} opacity={hot ? 0.8 : 0.3}>
        <animateMotion dur={hot ? '0.7s' : '2.5s'} repeatCount="indefinite" path={edgePath} />
      </circle>
      {hot && (
        <circle r={2} fill={accent} opacity={0.4}>
          <animateMotion dur="1.1s" repeatCount="indefinite" path={edgePath} begin="0.35s" />
        </circle>
      )}
    </>
  );
}

const nodeTypes = { expression: ExpressionNode };
const edgeTypes = { expression: ExpressionEdge };

export default function ExpressionView() {
  // Prepare nodes with onChange callback and nodeId in data
  const preparedNodes = useMemo(() => initialNodes.map(n => ({
    ...n,
    data: { ...n.data, nodeId: n.id },
  })), []);

  const [nodes, setNodes, onNodesChange] = useNodesState(preparedNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [showTriage, setShowTriage] = useState(false);
  const [simActive, setSimActive] = useState(false);
  const [simName, setSimName] = useState('');
  const [litNodes, setLitNodes] = useState(new Set());
  const [orbMode, setOrbMode] = useState('SIM');
  const [locked, setLocked] = useState({});
  const timers = useRef([]);

  const { isConnected, dimensions, rendererState } = useOrbConnection();

  // Extract current dimension values from nodes
  const dims = useMemo(() => {
    const d = {};
    nodes.forEach(n => {
      if (n.data?.nodeType === 'dimension') {
        const f = n.data.fields?.find(f => f.key === 'value');
        if (f) d[n.id] = f.value;
      }
    });
    return d;
  }, [nodes]);

  // Compute orb readout and push to map_render node
  const orbReadout = useMemo(() => {
    const v = dims.d_val ?? 0.6;
    const a = dims.d_aro ?? 0.4;
    const c = dims.d_cert ?? 0.7;
    const e = dims.d_eng ?? 0.5;
    const w = dims.d_warm ?? 0.7;
    return {
      breathe: (0.008 + a * 0.027).toFixed(4),
      glow: (0.04 + e * 0.11).toFixed(3),
      opacity: (0.6 + c * 0.4).toFixed(2),
    };
  }, [dims]);

  // Push readout to map_render node
  useEffect(() => {
    setNodes(prev => prev.map(n => {
      if (n.id === 'map_render') {
        return { ...n, data: { ...n.data, fields: n.data.fields.map(f => {
          if (f.key === 'breathe') return { ...f, value: orbReadout.breathe };
          if (f.key === 'glow') return { ...f, value: orbReadout.glow };
          if (f.key === 'opacity') return { ...f, value: orbReadout.opacity };
          return f;
        })}};
      }
      return n;
    }));
  }, [orbReadout, setNodes]);

  // Update live dimension values from WebSocket
  useEffect(() => {
    if (orbMode !== 'LIVE' || !dimensions) return;
    setNodes(prev => prev.map(n => {
      if (n.data?.nodeType === 'dimension' && !locked[n.id]) {
        const dimKey = { d_val: 'valence', d_aro: 'arousal', d_cert: 'certainty', d_eng: 'engagement', d_warm: 'warmth' }[n.id];
        const liveVal = dimensions[dimKey];
        if (liveVal !== undefined) {
          return { ...n, data: { ...n.data, fields: n.data.fields.map(f => f.key === 'value' ? { ...f, value: liveVal } : f) } };
        }
      }
      return n;
    }));
  }, [dimensions, orbMode, locked, setNodes]);

  // Node field change handler
  const onChange = useCallback((nodeId, fieldKey, value) => {
    setNodes(prev => prev.map(n =>
      n.id !== nodeId ? n : { ...n, data: { ...n.data, fields: n.data.fields.map(f => f.key === fieldKey ? { ...f, value } : f) } }
    ));
  }, [setNodes]);

  // Inject onChange into node data
  useEffect(() => {
    setNodes(prev => prev.map(n => ({
      ...n,
      data: { ...n.data, onChange },
    })));
  }, [onChange, setNodes]);

  // Update lit state on nodes and edges
  useEffect(() => {
    setNodes(prev => prev.map(n => ({
      ...n,
      data: { ...n.data, lit: litNodes.has(n.id) },
    })));
    setEdges(prev => prev.map(e => {
      const [src, tgt] = [e.source, e.target];
      const hot = litNodes.has(src) || litNodes.has(tgt);
      return { ...e, data: { ...e.data, lit: hot } };
    }));
  }, [litNodes, setNodes, setEdges]);

  // Scenario runner
  const runSim = useCallback((key) => {
    if (simActive) return;
    const sc = SCENARIOS[key];
    if (!sc) return;
    timers.current.forEach(clearTimeout);
    timers.current = [];
    setSimActive(true);
    setSimName(sc.label);

    sc.steps.forEach((step, si) => {
      const t = setTimeout(() => {
        setLitNodes(new Set(step.fire));

        if (step.sigs) {
          setNodes(prev => prev.map(n =>
            step.sigs[n.id] !== undefined
              ? { ...n, data: { ...n.data, fields: n.data.fields.map(f => f.key === 'sig' ? { ...f, value: step.sigs[n.id].toFixed(2) } : f) } }
              : n
          ));
        }
        if (step.dims) {
          setNodes(prev => prev.map(n =>
            step.dims[n.id] !== undefined
              ? { ...n, data: { ...n.data, fields: n.data.fields.map(f => f.key === 'value' ? { ...f, value: step.dims[n.id] } : f) } }
              : n
          ));
        }
        if (step.gest) {
          setNodes(prev => prev.map(n =>
            n.id === 'g_override' ? { ...n, data: { ...n.data, fields: n.data.fields.map(f => step.gest[f.key] ? { ...f, value: step.gest[f.key] } : f) } } : n
          ));
        }
        if (step.emoj) {
          setNodes(prev => prev.map(n =>
            n.id === 'g_emoji' ? { ...n, data: { ...n.data, fields: n.data.fields.map(f => step.emoj[f.key] ? { ...f, value: step.emoj[f.key] } : f) } } : n
          ));
        }
        if (step.pri) {
          setNodes(prev => prev.map(n =>
            n.id === 'priority' ? { ...n, data: { ...n.data, fields: n.data.fields.map(f => f.key === 'winner' ? { ...f, value: step.pri.winner } : f) } } : n
          ));
        }

        // Last step: clear after delay
        if (si === sc.steps.length - 1) {
          const end = setTimeout(() => {
            setLitNodes(new Set());
            setSimActive(false);
            setSimName('');
            setNodes(prev => prev.map(n => {
              if (n.id === 'g_override') return { ...n, data: { ...n.data, fields: n.data.fields.map(f => ['active', 'gesture'].includes(f.key) ? { ...f, value: '—' } : f) } };
              if (n.id === 'g_emoji') return { ...n, data: { ...n.data, fields: n.data.fields.map(f => ['active', 'emoji'].includes(f.key) ? { ...f, value: '—' } : f) } };
              if (n.id === 'priority') return { ...n, data: { ...n.data, fields: n.data.fields.map(f => f.key === 'winner' ? { ...f, value: 'P1 DIMENSION' } : f) } };
              return n;
            }));
          }, 2400);
          timers.current.push(end);
        }
      }, step.at);
      timers.current.push(t);
    });
  }, [simActive, setNodes]);

  // Cleanup timers
  useEffect(() => () => timers.current.forEach(clearTimeout), []);

  const onDimChange = useCallback((dimKey, value) => {
    setNodes(prev => prev.map(n =>
      n.id === dimKey ? { ...n, data: { ...n.data, fields: n.data.fields.map(f => f.key === 'value' ? { ...f, value } : f) } } : n
    ));
  }, [setNodes]);

  const onLockToggle = useCallback((dimKey) => {
    setLocked(prev => ({ ...prev, [dimKey]: !prev[dimKey] }));
  }, []);

  const minimapNodeColor = useCallback((n) => {
    const t = TYPES[n.data?.nodeType];
    return t?.accent || '#818cf8';
  }, []);

  // Live dimensions for slider display
  const liveDims = useMemo(() => {
    if (!dimensions) return undefined;
    return {
      d_val: dimensions.valence,
      d_aro: dimensions.arousal,
      d_cert: dimensions.certainty,
      d_eng: dimensions.engagement,
      d_warm: dimensions.warmth,
    };
  }, [dimensions]);

  return (
    <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', background: '#08080f' }}>
      {/* Main area: ReactFlow + Sidebar */}
      <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
        {/* ReactFlow Canvas */}
        <div style={{ flex: 1, position: 'relative' }}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            fitView
            fitViewOptions={{ padding: 0.15 }}
            style={{ background: '#08080f' }}
            minZoom={0.15}
            maxZoom={3}
            snapToGrid
            snapGrid={[10, 10]}
          >
            <Background color="rgba(255,255,255,0.015)" gap={20} size={1} />
            <Controls position="bottom-left" />
            <MiniMap
              nodeColor={minimapNodeColor}
              maskColor="rgba(8,8,15,0.85)"
              style={{ background: '#0a0a14' }}
              position="bottom-right"
            />
          </ReactFlow>
        </div>

        {/* Right Sidebar: Orb + Sliders */}
        <div style={{
          width: 300, flexShrink: 0, padding: '12px',
          borderLeft: '1px solid rgba(255,255,255,0.06)',
          overflowY: 'auto', background: '#0a0a14',
        }}>
          <OrbPreview
            dims={dims}
            mode={orbMode}
            rendererState={rendererState}
            onModeChange={setOrbMode}
          />
          <div style={{ marginTop: 16 }}>
            <DimensionSliders
              dims={dims}
              liveDims={liveDims}
              locked={locked}
              onDimChange={onDimChange}
              onLockToggle={onLockToggle}
            />
          </div>
        </div>
      </div>

      {/* Bottom Bar: Scenarios + Triage toggle */}
      <div style={{
        padding: '8px 12px',
        borderTop: '1px solid rgba(255,255,255,0.06)',
        background: '#0a0a14',
      }}>
        <ScenarioRunner
          simActive={simActive}
          simName={simName}
          onRunSim={runSim}
          onShowTriage={() => setShowTriage(!showTriage)}
          showTriage={showTriage}
        />
      </div>

      {/* Triage Panel Overlay */}
      {showTriage && <TriagePanel onClose={() => setShowTriage(false)} />}
    </div>
  );
}
