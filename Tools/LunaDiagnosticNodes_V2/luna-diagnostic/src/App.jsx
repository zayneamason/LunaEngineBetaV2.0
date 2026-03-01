import React, { useState, useCallback, useEffect } from 'react';
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
import { initialNodes, initialEdges, defaultEdgeOptions, legendItems } from './data';
import { useLiveData, applyLiveData, applyLiveEdges } from './useLiveData';

const nodeTypes = { engine: EngineNode };
const edgeTypes = { animated: AnimatedEdge };

export default function App() {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [selectedNode, setSelectedNode] = useState(null);
  const { data: liveData, connected, lastUpdate } = useLiveData(2000);

  // Apply live data to nodes/edges when it arrives
  useEffect(() => {
    if (!liveData) return;
    setNodes(prev => applyLiveData(prev, liveData));
    setEdges(prev => applyLiveEdges(prev, liveData));
  }, [liveData, setNodes, setEdges]);

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

  return (
    <div style={{ width: '100vw', height: '100vh', background: '#08080f' }}>
      {/* HUD */}
      <div style={{
        position: 'fixed', top: 14, left: 14, zIndex: 50,
        fontFamily: "'JetBrains Mono', monospace",
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            fontSize: 14, fontWeight: 700, color: '#e0e0f0', letterSpacing: '0.5px',
          }}>◈ LUNA ENGINE — PIPELINE DIAGNOSTIC</div>
          {/* Connection indicator */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 5,
            padding: '2px 10px', borderRadius: 6,
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
        </div>
        <div style={{ fontSize: 9.5, color: '#555568', marginTop: 3 }}>
          Drag nodes · Click for detail · Scroll to zoom · Animated edges = data flow · Red = broken · Polling every 2s
        </div>
        <div style={{ display: 'flex', gap: 14, marginTop: 8, flexWrap: 'wrap' }}>
          {legendItems.map(({ color, label }) => (
            <div key={label} style={{
              display: 'flex', alignItems: 'center', gap: 4,
              fontSize: 9.5, color: '#555568',
            }}>
              <div style={{ width: 7, height: 7, borderRadius: 2, background: color }} />
              {label}
            </div>
          ))}
        </div>
      </div>

      {/* React Flow Canvas */}
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
      </ReactFlow>

      {/* Detail Panel */}
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
