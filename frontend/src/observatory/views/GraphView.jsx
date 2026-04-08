import React, { useRef, useCallback, useMemo, useEffect } from 'react'
import ForceGraph2D from 'react-force-graph-2d'
import { useObservatoryStore } from '../store'
import NodeCard from '../components/NodeCard'
import ObservatoryGlobe from './ObservatoryGlobe'
import GalaxyView from './GalaxyView'
import {
  forceCollide as d3ForceCollide,
  forceRadial as d3ForceRadial,
} from 'd3-force'

const TYPE_COLORS = {
  ENTITY: '#22d3ee',
  FACT: '#38bdf8',
  DECISION: '#a78bfa',
  INSIGHT: '#facc15',
  PROBLEM: '#f87171',
  ACTION: '#4ade80',
  OUTCOME: '#fb923c',
  OBSERVATION: '#94a3b8',
}

const DEFAULT_COLOR = '#555'
const MIN_HIT_RADIUS = 8

function getNodeColor(node) {
  return TYPE_COLORS[node.type || node.node_type] || DEFAULT_COLOR
}

// ── Shape drawing helpers (for ForceGraph2D solar system) ──

function drawDiamond(ctx, x, y, size) {
  ctx.moveTo(x, y - size)
  ctx.lineTo(x + size, y)
  ctx.lineTo(x, y + size)
  ctx.lineTo(x - size, y)
  ctx.closePath()
}

function drawSquare(ctx, x, y, size) {
  ctx.rect(x - size, y - size, size * 2, size * 2)
}

function drawHexagon(ctx, x, y, size) {
  for (let i = 0; i < 6; i++) {
    const angle = (Math.PI / 3) * i - Math.PI / 2
    const px = x + size * Math.cos(angle)
    const py = y + size * Math.sin(angle)
    if (i === 0) ctx.moveTo(px, py)
    else ctx.lineTo(px, py)
  }
  ctx.closePath()
}

function drawShape(ctx, shape, x, y, size) {
  ctx.beginPath()
  switch (shape) {
    case 'diamond': drawDiamond(ctx, x, y, size); break
    case 'square': drawSquare(ctx, x, y, size); break
    case 'hexagon': drawHexagon(ctx, x, y, size); break
    case 'ring':
    case 'circle':
    default:
      ctx.arc(x, y, size, 0, 2 * Math.PI)
      break
  }
}

// ── Solar System data builder ──────────────────────

function buildSolarSystemGraphData(solarSystemData) {
  if (!solarSystemData) return { nodes: [], links: [] }

  const focusNode = solarSystemData.focus_node
  const neighbors = solarSystemData.neighbors || []

  const nodes = [
    {
      id: focusNode.id,
      ...focusNode,
      fx: 0,
      fy: 0,
      _isFocus: true,
      _isCluster: false,
      _color: getNodeColor(focusNode),
    },
    ...neighbors.map(n => ({
      id: n.id,
      ...n,
      _isCluster: false,
      _isFocus: false,
      _color: getNodeColor(n),
    })),
  ]

  const nodeSet = new Set(nodes.map(n => n.id))
  const links = (solarSystemData.edges || [])
    .filter(e => nodeSet.has(e.from_id) && nodeSet.has(e.to_id))
    .map(e => ({
      source: e.from_id,
      target: e.to_id,
      relationship: e.relationship,
      strength: e.strength || 0.5,
    }))

  return { nodes, links }
}

// ── Main Component ─────────────────────────────────

export default function GraphView({ navigateTab }) {
  const graphRef = useRef()
  const globeRef = useRef()
  const galaxyRef = useRef()
  const hoveredNodeRef = useRef(null)
  const {
    nodes,
    zoomLevel, universeData, galaxyData, solarSystemData,
    focusClusterId, focusNodeId, isTransitioning,
    fetchUniverse, drillDown, drillUp,
    selectedNodeId, selectNode, activatedNodeIds,
    graphSettings,
  } = useObservatoryStore()

  // Load universe on first render if no data yet
  useEffect(() => {
    if (!universeData) fetchUniverse()
  }, [])

  // ── Solar system graph data ─────────────────────
  const solarGraphData = useMemo(() => {
    if (zoomLevel !== 'solarsystem') return { nodes: [], links: [] }
    return buildSolarSystemGraphData(solarSystemData)
  }, [zoomLevel, solarSystemData])

  // Selected node/cluster detail (for NodeCard at any zoom level)
  const selectedNode = useMemo(() => {
    if (!selectedNodeId) return null
    if (zoomLevel === 'solarsystem') {
      const inGraph = solarGraphData.nodes.find(n => n.id === selectedNodeId)
      if (inGraph) return inGraph
    }
    if (zoomLevel === 'galaxy' && galaxyData) {
      // Check flat nodes list
      const flat = (galaxyData.nodes || []).find(n => n.id === selectedNodeId)
      if (flat) return flat
      // Check inside sub_groups
      for (const sg of (galaxyData.sub_groups || [])) {
        const found = (sg.nodes || []).find(n => n.id === selectedNodeId)
        if (found) return found
      }
    }
    if (zoomLevel === 'universe' && universeData) {
      const cluster = (universeData.clusters || []).find(
        c => (c.id || c.cluster_id) === selectedNodeId
      )
      if (cluster) return {
        ...cluster,
        _isCluster: true,
        id: cluster.id || cluster.cluster_id,
        type: 'CLUSTER',
        content: cluster.summary || cluster.name || cluster.label || '',
        lock_in: cluster.lock_in || cluster.avg_node_lock_in || 0,
      }
    }
    return nodes.find(n => n.id === selectedNodeId) || null
  }, [solarGraphData.nodes, nodes, galaxyData, universeData, selectedNodeId, zoomLevel])

  // ── Force settings for solar system ──────────────
  useEffect(() => {
    const fg = graphRef.current
    if (!fg || zoomLevel !== 'solarsystem') return

    const charge = fg.d3Force('charge')
    if (charge) charge.strength(graphSettings.chargeStrength)

    const link = fg.d3Force('link')
    if (link) link.distance(graphSettings.linkDistance)

    const radialStr = graphSettings.radialStrength > 0
      ? graphSettings.radialStrength
      : 0.08
    const radialR = graphSettings.radialRadius || 220
    fg.d3Force('radial', d3ForceRadial(radialR).strength(radialStr))

    const collideR = graphSettings.collideRadius > 0
      ? graphSettings.collideRadius
      : 8
    fg.d3Force('collide', d3ForceCollide(collideR))

    fg.d3ReheatSimulation()
  }, [
    zoomLevel,
    graphSettings.chargeStrength,
    graphSettings.linkDistance,
    graphSettings.radialStrength,
    graphSettings.radialRadius,
    graphSettings.collideRadius,
    graphSettings._reheat,
  ])

  // Zoom to fit for solar system
  useEffect(() => {
    const fg = graphRef.current
    if (!fg || zoomLevel !== 'solarsystem' || solarGraphData.nodes.length === 0) return
    const timer = setTimeout(() => fg.zoomToFit(400, 60), 500)
    return () => clearTimeout(timer)
  }, [zoomLevel, solarGraphData.nodes.length])

  // ── Globe: cluster click → show card ───────────────
  const handleClusterClick = useCallback((clusterId) => {
    selectNode(clusterId) // null dismisses
  }, [selectNode])

  // ── Galaxy: node click → show card ────────────────
  const handleGalaxyNodeClick = useCallback((nodeId) => {
    selectNode(nodeId) // null dismisses
  }, [selectNode])

  // ── Solar system: node click ──────────────────────
  const handleSolarNodeClick = useCallback((node) => {
    selectNode(node.id)
    // Cross-tab navigation for entity/quest nodes
    if (navigateTab && node.entity_type && ['person', 'persona', 'place', 'project'].includes(node.entity_type)) {
      navigateTab('Entities', { entityId: node.id })
    } else if (navigateTab && node.node_type === 'THREAD') {
      navigateTab('Quests', { threadId: node.id })
    }
  }, [selectNode, navigateTab])

  const handleSolarNodeDblClick = useCallback((node) => {
    if (!node._isFocus) {
      drillDown('node', node.id)
    }
  }, [drillDown])

  // ── Solar system node renderer ────────────────────
  const renderNormalNode = useCallback((node, ctx, globalScale) => {
    const isSelected = node.id === selectedNodeId
    const isActivated = activatedNodeIds.has(node.id)
    const isFocus = node._isFocus
    const lockIn = node.lock_in || 0
    const baseSize = isFocus
      ? graphSettings.nodeBaseSize * 2 + lockIn * graphSettings.lockInScale
      : graphSettings.nodeBaseSize + lockIn * graphSettings.lockInScale
    const color = node._color
    const shape = graphSettings.nodeShape

    // Activation glow
    if (isActivated && graphSettings.showActivationGlow) {
      drawShape(ctx, shape, node.x, node.y, baseSize + 6)
      ctx.fillStyle = `${color}33`
      ctx.fill()
      ctx.strokeStyle = `${color}88`
      ctx.lineWidth = 1.5
      ctx.stroke()
    }

    // Focus node pulse ring
    if (isFocus) {
      ctx.beginPath()
      ctx.arc(node.x, node.y, baseSize + 8, 0, 2 * Math.PI)
      ctx.strokeStyle = `${color}44`
      ctx.lineWidth = 2
      ctx.stroke()
    }

    // Lock-in ring
    if (lockIn > 0.1 && graphSettings.showLockInRings) {
      ctx.beginPath()
      ctx.arc(node.x, node.y, baseSize + 3, -Math.PI / 2, -Math.PI / 2 + 2 * Math.PI * lockIn)
      ctx.strokeStyle = `${color}66`
      ctx.lineWidth = 1.5
      ctx.stroke()
    }

    // Main node
    drawShape(ctx, shape, node.x, node.y, baseSize)
    if (shape === 'ring') {
      ctx.fillStyle = 'transparent'
      ctx.fill()
      ctx.strokeStyle = isSelected ? '#fff' : color
      ctx.lineWidth = 2
      ctx.stroke()
    } else {
      ctx.fillStyle = isSelected ? '#fff' : color
      ctx.fill()
    }

    // Selection ring
    if (isSelected && shape !== 'ring') {
      ctx.strokeStyle = '#7dd3fc'
      ctx.lineWidth = 2
      ctx.stroke()
    }

    // Label — only on hover or selection
    const isHovered = hoveredNodeRef.current === node.id
    if (isHovered || isSelected || isFocus) {
      ctx.font = `${Math.max(9, 11 / globalScale)}px monospace`
      ctx.textAlign = 'center'
      ctx.textBaseline = 'top'
      ctx.fillStyle = isFocus ? '#ddd' : '#888'
      const label = node.content
        ? (node.content.length > 30 ? node.content.slice(0, 28) + '..' : node.content)
        : node.id
      ctx.fillText(label, node.x, node.y + baseSize + 4)

      if (isFocus) {
        ctx.font = `bold ${Math.max(10, 12 / globalScale)}px monospace`
        ctx.fillStyle = '#bbb'
        ctx.fillText(node.id, node.x, node.y + baseSize + 4)
      }
    }
  }, [selectedNodeId, activatedNodeIds, graphSettings.nodeShape, graphSettings.nodeBaseSize, graphSettings.lockInScale, graphSettings.showLockInRings, graphSettings.showActivationGlow])

  const handleNodeHover = useCallback((node) => {
    hoveredNodeRef.current = node ? node.id : null
  }, [])

  const nodePointerAreaPaint = useCallback((node, color, ctx) => {
    const r = Math.max(MIN_HIT_RADIUS, graphSettings.nodeBaseSize + (node.lock_in || 0) * graphSettings.lockInScale)
    ctx.beginPath()
    ctx.arc(node.x, node.y, r + 4, 0, 2 * Math.PI)
    ctx.fillStyle = color
    ctx.fill()
  }, [graphSettings.nodeBaseSize, graphSettings.lockInScale])

  const linkCanvasObject = useCallback((link, ctx) => {
    const start = link.source
    const end = link.target
    if (!start.x || !end.x) return

    const strength = link.strength || 0.5
    const opacity = (0.1 + strength * 0.3) * graphSettings.linkOpacity
    const width = (0.5 + strength * 1.5) * graphSettings.linkWidthScale

    ctx.beginPath()
    ctx.moveTo(start.x, start.y)
    ctx.lineTo(end.x, end.y)
    ctx.strokeStyle = `rgba(100, 100, 140, ${opacity})`
    ctx.lineWidth = width
    ctx.stroke()

    if (link.relationship) {
      const mx = (start.x + end.x) / 2
      const my = (start.y + end.y) / 2
      ctx.font = '8px monospace'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillStyle = '#555'
      ctx.fillText(link.relationship, mx, my)
    }
  }, [graphSettings.linkOpacity, graphSettings.linkWidthScale])

  // ── Breadcrumb ──────────────────────────────────
  const breadcrumb = useMemo(() => {
    const parts = [{ label: 'UNIVERSE', onClick: zoomLevel !== 'universe' ? () => drillUp() : null }]
    if (zoomLevel === 'galaxy' || zoomLevel === 'solarsystem') {
      const clusterLabel = galaxyData?.focus_cluster?.label || focusClusterId || '...'
      parts.push({
        label: clusterLabel,
        onClick: zoomLevel === 'solarsystem' ? () => drillUp() : null,
      })
    }
    if (zoomLevel === 'solarsystem') {
      const nodeLabel = solarSystemData?.focus_node?.id || focusNodeId || '...'
      parts.push({ label: nodeLabel, onClick: null })
    }
    return parts
  }, [zoomLevel, galaxyData, solarSystemData, focusClusterId, focusNodeId, drillUp])

  // ── Stats line ──────────────────────────────────
  const statsText = useMemo(() => {
    switch (zoomLevel) {
      case 'universe': {
        const count = universeData?.clusters?.length || 0
        const total = universeData?.total_nodes || 0
        const unclustered = universeData?.unclustered_count || 0
        return `${count} clusters / ${total} total nodes${unclustered ? ` / ${unclustered} unclustered` : ''}`
      }
      case 'galaxy': {
        const subGroups = galaxyData?.sub_groups?.length || 0
        const nodeCount = galaxyData?.nodes?.length || 0
        const neighbors = galaxyData?.neighbor_clusters?.length || 0
        return `${subGroups} sub-groups / ${nodeCount} nodes / ${neighbors} neighbors`
      }
      case 'solarsystem': {
        const neighborCount = solarSystemData?.neighbors?.length || 0
        const edgeCount = solarSystemData?.edges?.length || 0
        return `1 focus + ${neighborCount} neighbors / ${edgeCount} edges`
      }
      default:
        return ''
    }
  }, [zoomLevel, universeData, galaxyData, solarSystemData])

  const zoomLabels = { universe: 'UNIVERSE', galaxy: 'GALAXY', solarsystem: 'SOLAR SYSTEM' }

  // ── Render the appropriate view ──────────────────
  const renderView = () => {
    switch (zoomLevel) {
      case 'universe':
        return (
          <ObservatoryGlobe
            ref={globeRef}
            clusters={universeData?.clusters || []}
            phantomCount={graphSettings.phantomCount}
            globeStyle={graphSettings.globeStyle}
            autoRotate={graphSettings.autoRotate}
            showLockInRings={graphSettings.showLockInRings}
            showActivationGlow={graphSettings.showActivationGlow}
            onClusterClick={handleClusterClick}
            settings={graphSettings}
          />
        )

      case 'galaxy':
        return (
          <GalaxyView
            ref={galaxyRef}
            galaxyData={galaxyData}
            autoRotate={graphSettings.autoRotate}
            showLockInRings={graphSettings.showLockInRings}
            showActivationGlow={graphSettings.showActivationGlow}
            onNodeClick={handleGalaxyNodeClick}
            onBack={() => drillUp()}
            settings={graphSettings}
          />
        )

      case 'solarsystem':
        return (
          <ForceGraph2D
            ref={graphRef}
            graphData={solarGraphData}
            nodeCanvasObject={renderNormalNode}
            nodePointerAreaPaint={nodePointerAreaPaint}
            linkCanvasObject={linkCanvasObject}
            onNodeClick={handleSolarNodeClick}
            onNodeRightClick={handleSolarNodeDblClick}
            onNodeHover={handleNodeHover}
            onBackgroundClick={() => selectNode(null)}
            backgroundColor="#06060e"
            cooldownTicks={graphSettings.cooldownTicks}
            d3AlphaDecay={graphSettings.alphaDecay}
            d3VelocityDecay={graphSettings.velocityDecay}
            warmupTicks={50}
          />
        )

      default:
        return null
    }
  }

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', background: '#06060e' }}>
      {/* Main view renderer */}
      <div style={{ position: 'absolute', inset: 0, zIndex: 1 }}>
        {renderView()}
      </div>

      {/* Breadcrumb bar */}
      <div style={{
        position: 'absolute', top: 12, left: 16, zIndex: 2,
        display: 'flex', alignItems: 'center', gap: 4,
        fontSize: 11, pointerEvents: 'auto',
      }}>
        {breadcrumb.map((part, i) => (
          <React.Fragment key={i}>
            {i > 0 && <span style={{ color: '#333', margin: '0 2px' }}>/</span>}
            {part.onClick ? (
              <button
                onClick={part.onClick}
                style={{
                  background: 'none', border: 'none', cursor: 'pointer',
                  color: '#7dd3fc', fontFamily: 'inherit', fontSize: 11,
                  padding: '2px 4px', borderRadius: 2,
                  transition: 'background 0.15s',
                }}
                onMouseEnter={e => e.target.style.background = '#1a1a2e'}
                onMouseLeave={e => e.target.style.background = 'none'}
              >
                {part.label}
              </button>
            ) : (
              <span style={{ color: '#888', padding: '2px 4px' }}>{part.label}</span>
            )}
          </React.Fragment>
        ))}

        {/* Zoom level badge */}
        <span style={{
          marginLeft: 12,
          background: '#7dd3fc15',
          border: '1px solid #7dd3fc33',
          color: '#7dd3fc',
          padding: '1px 8px',
          borderRadius: 3,
          fontSize: 9,
          fontWeight: 700,
          letterSpacing: 1,
        }}>
          {zoomLabels[zoomLevel]}
        </span>
      </div>

      {/* Stats line */}
      <div style={{
        position: 'absolute', top: 34, left: 16, zIndex: 2,
        color: '#444', fontSize: 10, pointerEvents: 'none',
      }}>
        {statsText}
      </div>

      {/* Zoom out button */}
      {zoomLevel !== 'universe' && (
        <button
          onClick={() => drillUp()}
          style={{
            position: 'absolute', top: 12, right: selectedNode ? 340 : 16,
            background: '#1a1a2e',
            border: '1px solid #2a2a3e',
            color: '#7dd3fc',
            padding: '6px 14px',
            borderRadius: 4,
            cursor: 'pointer',
            fontSize: 11,
            fontFamily: 'inherit',
            fontWeight: 600,
            transition: 'all 0.15s',
            zIndex: 10,
          }}
          onMouseEnter={e => { e.target.style.borderColor = '#7dd3fc'; e.target.style.background = '#1a1a3e' }}
          onMouseLeave={e => { e.target.style.borderColor = '#2a2a3e'; e.target.style.background = '#1a1a2e' }}
        >
          ZOOM OUT
        </button>
      )}

      {/* Interaction hint */}
      <div style={{
        position: 'absolute', bottom: 60, left: 16, zIndex: 2,
        color: '#333', fontSize: 9, lineHeight: 1.5, pointerEvents: 'none',
      }}>
        {zoomLevel === 'universe' && 'CLICK cluster to inspect  ·  PINCH-IN to drill into galaxy  ·  SCROLL to zoom'}
        {zoomLevel === 'galaxy' && 'CLICK node to inspect  ·  PINCH-IN to drill into solar system  ·  PINCH-OUT to go back'}
        {zoomLevel === 'solarsystem' && 'CLICK node to inspect  ·  RIGHT-CLICK a neighbor to refocus'}
      </div>

      {/* Legend */}
      <div style={{
        position: 'absolute', bottom: 16, left: 16, zIndex: 2,
        background: '#0a0a14dd', border: '1px solid #1a1a2e',
        padding: '8px 12px', borderRadius: 4, fontSize: 11,
        pointerEvents: 'none',
      }}>
        <div style={{ color: '#555', marginBottom: 4 }}>
          {zoomLevel === 'universe' ? 'CLUSTER STATES' : 'NODE TYPES'}
        </div>
        {zoomLevel === 'universe' ? (
          <>
            {['fluid', 'crystallized', 'drifting'].map(state => (
              <div key={state} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
                <div style={{
                  width: 8, height: 8, borderRadius: '50%',
                  background: state === 'crystallized' ? '#4ade80' : state === 'fluid' ? '#22d3ee' : '#555',
                }} />
                <span style={{ color: '#888', textTransform: 'capitalize' }}>{state}</span>
              </div>
            ))}
          </>
        ) : (
          Object.entries(TYPE_COLORS).map(([type, color]) => (
            <div key={type} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: color }} />
              <span style={{ color: '#888' }}>{type}</span>
            </div>
          ))
        )}
      </div>

      {/* Loading overlay */}
      {isTransitioning && (
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: '#06060ecc', zIndex: 100,
        }}>
          <div style={{ color: '#7dd3fc', fontSize: 13, fontFamily: 'inherit' }}>
            Loading...
          </div>
        </div>
      )}

      {/* Node / cluster detail card (all zoom levels) */}
      {selectedNode && (
        <div style={{
          position: 'absolute', top: 12, right: 12, zIndex: 10,
          width: 320, maxHeight: 'calc(100% - 24px)', overflow: 'auto',
        }}>
          {selectedNode._isCluster ? (
            /* Cluster card for universe view */
            <div style={{
              background: '#0a0a14', border: '1px solid #1a1a2e',
              borderRadius: 6, padding: 16, boxShadow: '0 4px 24px rgba(0,0,0,0.5)',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
                <div>
                  <div style={{ color: '#22d3ee', fontSize: 10, letterSpacing: 1, marginBottom: 2 }}>CLUSTER</div>
                  <div style={{ color: '#ddd', fontSize: 14, fontWeight: 600 }}>
                    {selectedNode.name || selectedNode.label || selectedNode.id}
                  </div>
                </div>
                <button onClick={() => selectNode(null)} style={{
                  background: 'none', border: 'none', color: '#555', cursor: 'pointer',
                  fontSize: 16, padding: '0 4px',
                }}>x</button>
              </div>
              {selectedNode.summary && (
                <div style={{ color: '#999', fontSize: 12, lineHeight: 1.5, marginBottom: 12 }}>
                  {selectedNode.summary}
                </div>
              )}
              <div style={{
                display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6,
                fontSize: 11, color: '#666', marginBottom: 14,
              }}>
                <div>Nodes: <span style={{ color: '#888' }}>{selectedNode.member_count || selectedNode.node_count || 0}</span></div>
                <div>Lock-in: <span style={{ color: '#888' }}>{((selectedNode.lock_in || 0) * 100).toFixed(0)}%</span></div>
                <div>State: <span style={{ color: '#888' }}>{selectedNode.state || 'unknown'}</span></div>
                <div>Avg LI: <span style={{ color: '#888' }}>{((selectedNode.avg_node_lock_in || 0) * 100).toFixed(0)}%</span></div>
              </div>
              <button
                onClick={() => { selectNode(null); drillDown('cluster', selectedNodeId) }}
                style={{
                  width: '100%', padding: '8px 0', background: '#1a1a2e',
                  border: '1px solid #2a2a3e', borderRadius: 4, color: '#7dd3fc',
                  cursor: 'pointer', fontSize: 11, fontFamily: 'inherit', fontWeight: 600,
                }}
              >
                EXPLORE CLUSTER
              </button>
            </div>
          ) : (
            /* Node card for galaxy + solar system */
            <>
              <NodeCard node={selectedNode} onClose={() => selectNode(null)} />
              {zoomLevel === 'galaxy' && (
                <button
                  onClick={() => { selectNode(null); drillDown('node', selectedNodeId) }}
                  style={{
                    width: '100%', marginTop: 8, padding: '8px 0', background: '#1a1a2e',
                    border: '1px solid #2a2a3e', borderRadius: 4, color: '#7dd3fc',
                    cursor: 'pointer', fontSize: 11, fontFamily: 'inherit', fontWeight: 600,
                  }}
                >
                  VIEW CONNECTIONS
                </button>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}
