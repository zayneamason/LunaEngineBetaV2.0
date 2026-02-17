import React, { useRef, useCallback, useMemo } from 'react'
import ForceGraph2D from 'react-force-graph-2d'
import { useStore } from '../store'
import NodeCard from '../components/NodeCard'

// Node type → color
const TYPE_COLORS = {
  ENTITY: '#22d3ee',    // cyan
  FACT: '#38bdf8',      // sky blue
  DECISION: '#a78bfa',  // purple
  INSIGHT: '#facc15',   // yellow
  PROBLEM: '#f87171',   // red
  ACTION: '#4ade80',    // green
  OUTCOME: '#fb923c',   // orange
  OBSERVATION: '#94a3b8', // slate
}

const DEFAULT_COLOR = '#555'

function getNodeColor(node) {
  return TYPE_COLORS[node.type] || DEFAULT_COLOR
}

export default function GraphView() {
  const graphRef = useRef()
  const { nodes, edges, clusters, selectedNodeId, selectNode, activatedNodeIds } = useStore()

  const graphData = useMemo(() => {
    const gNodes = nodes.map(n => ({
      id: n.id,
      ...n,
      _color: getNodeColor(n),
    }))

    const nodeSet = new Set(nodes.map(n => n.id))
    const gLinks = edges
      .filter(e => nodeSet.has(e.from_id) && nodeSet.has(e.to_id))
      .map(e => ({
        source: e.from_id,
        target: e.to_id,
        relationship: e.relationship,
        strength: e.strength,
      }))

    return { nodes: gNodes, links: gLinks }
  }, [nodes, edges])

  const selectedNode = useMemo(() => {
    if (!selectedNodeId) return null
    return nodes.find(n => n.id === selectedNodeId) || null
  }, [nodes, selectedNodeId])

  const nodeCanvasObject = useCallback((node, ctx, globalScale) => {
    const isSelected = node.id === selectedNodeId
    const isActivated = activatedNodeIds.has(node.id)
    const lockIn = node.lock_in || 0
    const baseSize = 4 + lockIn * 8
    const color = node._color

    // Activation glow
    if (isActivated) {
      ctx.beginPath()
      ctx.arc(node.x, node.y, baseSize + 6, 0, 2 * Math.PI)
      ctx.fillStyle = `${color}33`
      ctx.fill()
      ctx.strokeStyle = `${color}88`
      ctx.lineWidth = 1.5
      ctx.stroke()
    }

    // Lock-in ring
    if (lockIn > 0.1) {
      ctx.beginPath()
      ctx.arc(node.x, node.y, baseSize + 3, -Math.PI / 2, -Math.PI / 2 + (2 * Math.PI * lockIn))
      ctx.strokeStyle = `${color}66`
      ctx.lineWidth = 1.5
      ctx.stroke()
    }

    // Main node
    ctx.beginPath()
    ctx.arc(node.x, node.y, baseSize, 0, 2 * Math.PI)
    ctx.fillStyle = isSelected ? '#fff' : color
    ctx.fill()

    // Selection ring
    if (isSelected) {
      ctx.strokeStyle = '#7dd3fc'
      ctx.lineWidth = 2
      ctx.stroke()
    }

    // Label (only at sufficient zoom)
    if (globalScale > 1.5) {
      ctx.font = `${Math.max(9, 11 / globalScale)}px monospace`
      ctx.textAlign = 'center'
      ctx.fillStyle = '#888'
      ctx.fillText(node.id, node.x, node.y + baseSize + 10)
    }
  }, [selectedNodeId, activatedNodeIds])

  const linkCanvasObject = useCallback((link, ctx) => {
    const start = link.source
    const end = link.target
    if (!start.x || !end.x) return

    ctx.beginPath()
    ctx.moveTo(start.x, start.y)
    ctx.lineTo(end.x, end.y)
    ctx.strokeStyle = `rgba(100, 100, 140, ${0.1 + (link.strength || 0.5) * 0.3})`
    ctx.lineWidth = 0.5 + (link.strength || 0.5) * 1.5
    ctx.stroke()
  }, [])

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <ForceGraph2D
        ref={graphRef}
        graphData={graphData}
        nodeCanvasObject={nodeCanvasObject}
        linkCanvasObject={linkCanvasObject}
        onNodeClick={(node) => selectNode(node.id)}
        onBackgroundClick={() => selectNode(null)}
        backgroundColor="#06060e"
        linkDirectionalArrowLength={4}
        linkDirectionalArrowRelPos={0.8}
        cooldownTicks={100}
        d3AlphaDecay={0.02}
        d3VelocityDecay={0.3}
      />

      {/* Legend */}
      <div style={{
        position: 'absolute', bottom: 16, left: 16,
        background: '#0a0a14dd', border: '1px solid #1a1a2e',
        padding: '8px 12px', borderRadius: 4, fontSize: 11,
      }}>
        <div style={{ color: '#555', marginBottom: 4 }}>NODE TYPES</div>
        {Object.entries(TYPE_COLORS).map(([type, color]) => (
          <div key={type} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: color }} />
            <span style={{ color: '#888' }}>{type}</span>
          </div>
        ))}
      </div>

      {/* Stats overlay */}
      <div style={{
        position: 'absolute', top: 12, left: 16,
        color: '#555', fontSize: 11,
      }}>
        {nodes.length} nodes / {edges.length} edges / {clusters.length} clusters
      </div>

      {/* Node detail panel */}
      {selectedNode && (
        <div style={{
          position: 'absolute', top: 12, right: 12,
          width: 320, maxHeight: 'calc(100% - 24px)', overflow: 'auto',
        }}>
          <NodeCard node={selectedNode} onClose={() => selectNode(null)} />
        </div>
      )}
    </div>
  )
}
