/**
 * GalaxyView — Multi-sphere Canvas 2D renderer for Galaxy zoom level.
 *
 * When drilling into a cluster, the galaxy becomes multiple sub-spheres:
 * - Projects (from entities) render as named spheres
 * - Natural communities render as unnamed groupings
 * Each sphere rotates on its own axis at a slightly different speed.
 *
 * Props:
 *   galaxyData      — full galaxy response from API (sub_groups, inter_group_edges, focus_cluster)
 *   autoRotate      — boolean
 *   showLockInRings — boolean
 *   showActivationGlow — boolean
 *   onNodeClick     — (nodeId) => void
 *   onNodeHover     — (nodeId | null) => void
 *   onBack          — () => void (drill up)
 *   influencers     — ref to array of external force objects
 */

import React, { useRef, useEffect, useCallback, useImperativeHandle, forwardRef } from 'react'

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

const COLOR_VALUES = Object.values(TYPE_COLORS)

const SUB_GROUP_COLORS = [
  '#22d3ee', '#a78bfa', '#facc15', '#4ade80', '#f87171',
  '#fb923c', '#38bdf8', '#e879f9', '#34d399', '#fbbf24',
]

// ── Math helpers ─────────────────────────────────────

function fibonacciSphere(count) {
  if (count <= 0) return []
  if (count === 1) return [{ x: 0, y: 0, z: 1 }]
  const points = []
  const goldenAngle = Math.PI * (3 - Math.sqrt(5))
  for (let i = 0; i < count; i++) {
    const y = 1 - (i / (count - 1)) * 2
    const radius = Math.sqrt(1 - y * y)
    const theta = goldenAngle * i
    points.push({
      x: Math.cos(theta) * radius,
      y: y,
      z: Math.sin(theta) * radius,
    })
  }
  return points
}

function randomSpherePoint() {
  const u = Math.random()
  const v = Math.random()
  const theta = 2 * Math.PI * u
  const phi = Math.acos(2 * v - 1)
  return {
    x: Math.sin(phi) * Math.cos(theta),
    y: Math.sin(phi) * Math.sin(theta),
    z: Math.cos(phi),
  }
}

function rotatePoint(p, rotX, rotY) {
  // Support both {x,y,z} and {baseX,baseY,baseZ} field names
  const px = p.baseX !== undefined ? p.baseX : p.x
  const py = p.baseY !== undefined ? p.baseY : p.y
  const pz = p.baseZ !== undefined ? p.baseZ : p.z
  let x1 = px * Math.cos(rotY) + pz * Math.sin(rotY)
  let z1 = -px * Math.sin(rotY) + pz * Math.cos(rotY)
  let y1 = py
  let y2 = y1 * Math.cos(rotX) - z1 * Math.sin(rotX)
  let z2 = y1 * Math.sin(rotX) + z1 * Math.cos(rotX)
  return { x: x1, y: y2, z: z2 }
}

function hexToRgb(hex) {
  const h = hex.replace('#', '')
  return {
    r: parseInt(h.substring(0, 2), 16),
    g: parseInt(h.substring(2, 4), 16),
    b: parseInt(h.substring(4, 6), 16),
  }
}

function getNodeColor(node) {
  return TYPE_COLORS[node.type || node.node_type] || '#555'
}

// ── Component ────────────────────────────────────────

const GalaxyView = forwardRef(function GalaxyView({
  galaxyData,
  autoRotate = true,
  showLockInRings = true,
  showActivationGlow = true,
  onNodeClick,
  onNodeHover,
  onBack,
  influencers,
  settings = {},
}, ref) {
  // Physics tunables
  const rotationSpeed = settings.rotationSpeed ?? 1
  const momentumDecay = settings.momentumDecay ?? 0.96
  const phantomDrift = settings.phantomDrift ?? 1
  const phantomAlpha = settings.phantomAlpha ?? 1
  const phantomSizeMul = settings.phantomSize ?? 1
  const twinkleSpeedMul = settings.twinkleSpeed ?? 1
  const clusterScale = settings.clusterScale ?? 1
  const globeRadiusScale = settings.globeRadiusScale ?? 1
  const depthFadeMul = settings.depthFade ?? 1
  const canvasRef = useRef(null)
  const stateRef = useRef({
    spheres: [],       // sub-group sphere objects
    phantoms: [],      // inter-sphere phantoms
    interEdges: [],    // edges between spheres
    hoveredNodeId: null,
    isDragging: false,
    lastMouse: null,
    // Galaxy-level rotation (overall arrangement)
    globalRotX: 0.15,
    globalRotY: 0,
    globalMomentumX: 0,
    globalMomentumY: 0.001,
    zoom: 1,
    zoomTarget: 1,
    _mouseX: undefined,
    _mouseY: undefined,
    animId: null,
  })

  // Expose influencers ref
  const influencersRef = useRef([])
  useImperativeHandle(ref, () => ({
    get influencers() { return influencersRef.current },
    set influencers(val) { influencersRef.current = val },
    addInfluencer(inf) { influencersRef.current.push(inf) },
    removeInfluencer(id) {
      influencersRef.current = influencersRef.current.filter(i => i.id !== id)
    },
  }))

  useEffect(() => {
    if (influencers) influencersRef.current = influencers
  }, [influencers])

  // ── Build sphere objects from galaxyData ──
  useEffect(() => {
    const s = stateRef.current
    // Reset zoom when data changes
    s.zoom = 1
    s.zoomTarget = 1
    if (!galaxyData) {
      s.spheres = []
      s.phantoms = []
      s.interEdges = []
      return
    }

    const subGroups = galaxyData.sub_groups || []

    // If no sub_groups, fall back to rendering all nodes as a single sphere
    const groups = subGroups.length > 0
      ? subGroups
      : [{
          id: 'all',
          label: galaxyData.focus_cluster?.label || 'Cluster',
          type: 'community',
          nodes: galaxyData.nodes || [],
          edges: galaxyData.edges || [],
          node_count: (galaxyData.nodes || []).length,
          avg_lock_in: 0,
        }]

    // Arrange spheres in a ring around center
    const sphereCount = groups.length
    const ringRadius = Math.max(100, sphereCount * 50)
    const spheres = groups.map((group, i) => {
      const angle = (2 * Math.PI * i) / sphereCount
      const nodeCount = group.node_count || (group.nodes || []).length
      const sphereRadius = Math.max(40, Math.sqrt(nodeCount) * 12)
      const centerX = Math.cos(angle) * ringRadius
      const centerY = Math.sin(angle) * ringRadius * 0.4 // flatten ellipse

      // Distribute nodes on this sphere's surface
      const nodes = (group.nodes || []).slice(0, 100) // max 100 per sphere
      const nodePositions = nodes.length > 0 ? fibonacciSphere(nodes.length) : []

      const color = SUB_GROUP_COLORS[i % SUB_GROUP_COLORS.length]
      const rgb = hexToRgb(color)

      return {
        id: group.id,
        label: group.label || `Group ${i}`,
        type: group.type || 'community',
        centerX,
        centerY,
        radius: sphereRadius,
        color,
        rgb,
        avgLockIn: group.avg_lock_in || 0,
        // Per-sphere rotation
        rotX: (Math.random() - 0.5) * 0.3, // slight tilt
        rotY: 0,
        rotSpeed: 0.001 + Math.random() * 0.002, // varied rotation speeds
        tiltX: (Math.random() - 0.5) * 0.4,
        // Nodes on this sphere
        nodes: nodes.map((n, j) => {
          const pos = nodePositions[j] || randomSpherePoint()
          const nodeColor = getNodeColor(n)
          const nodeRgb = hexToRgb(nodeColor)
          const lockIn = n.lock_in || 0
          const size = Math.max(2, 2 + lockIn * 5)
          return {
            id: n.id,
            content: n.content || n.id,
            type: n.type || n.node_type || 'OBSERVATION',
            lockIn,
            baseX: pos.x,
            baseY: pos.y,
            baseZ: pos.z,
            size,
            color: nodeColor,
            rgb: nodeRgb,
            alpha: 0.6 + lockIn * 0.4,
          }
        }),
      }
    })

    s.spheres = spheres

    // Inter-group edge references
    s.interEdges = (galaxyData.inter_group_edges || []).map(e => ({
      from: e.from_id,
      to: e.to_id,
      strength: e.strength || 0.3,
    }))

    // Generate inter-sphere phantoms (scattered between spheres)
    const phantoms = []
    for (let i = 0; i < 600; i++) {
      const colorIdx = Math.floor(Math.random() * COLOR_VALUES.length)
      const c = COLOR_VALUES[colorIdx]
      const rgb = hexToRgb(c)
      phantoms.push({
        x: (Math.random() - 0.5) * ringRadius * 3,
        y: (Math.random() - 0.5) * ringRadius * 2,
        size: 0.3 + Math.random() * 0.8,
        rgb,
        alpha: 0.02 + Math.random() * 0.06,
        driftX: (Math.random() - 0.5) * 0.05,
        driftY: (Math.random() - 0.5) * 0.03,
        twinkleSpeed: Math.random() * 0.003 + 0.001,
        twinklePhase: Math.random() * Math.PI * 2,
      })
    }
    s.phantoms = phantoms
  }, [galaxyData])

  // ── Animation loop ──
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    const s = stateRef.current
    let time = 0

    const dpr = window.devicePixelRatio || 1

    const render = () => {
      const dw = canvas.offsetWidth
      const dh = canvas.offsetHeight
      if (canvas.width !== dw * dpr || canvas.height !== dh * dpr) {
        canvas.width = dw * dpr
        canvas.height = dh * dpr
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      const cx = dw / 2
      const cy = dh / 2

      // Smooth zoom interpolation
      s.zoom += (s.zoomTarget - s.zoom) * 0.12
      const Z = s.zoom

      ctx.clearRect(0, 0, dw, dh)
      time++

      // Global rotation (scaled by rotationSpeed)
      const baseSpeed = 0.001 * rotationSpeed
      if (autoRotate && !s.isDragging) {
        s.globalRotY += s.globalMomentumY
        s.globalRotX += s.globalMomentumX
        s.globalMomentumX *= momentumDecay
        s.globalMomentumY = s.globalMomentumY * momentumDecay + baseSpeed * (1 - momentumDecay)
      } else if (!s.isDragging) {
        s.globalRotY += s.globalMomentumY
        s.globalRotX += s.globalMomentumX
        s.globalMomentumX *= momentumDecay
        s.globalMomentumY *= momentumDecay
      }

      // ── Draw phantoms ──
      for (const p of s.phantoms) {
        p.x += p.driftX * phantomDrift
        p.y += p.driftY * phantomDrift
        const twinkle = Math.sin(time * p.twinkleSpeed * twinkleSpeedMul + p.twinklePhase)
        const alpha = Math.max(0.01, p.alpha * phantomAlpha + twinkle * 0.015)
        ctx.beginPath()
        ctx.arc(cx + p.x * Z, cy + p.y * Z, p.size * Z * phantomSizeMul, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(${p.rgb.r}, ${p.rgb.g}, ${p.rgb.b}, ${alpha})`
        ctx.fill()
      }

      // Collect all renderable items across all spheres
      const allItems = []
      // Also build a lookup for node screen positions (for inter-group edges)
      const nodeScreenPos = {}

      let newHoveredId = null

      // ── Render each sub-sphere ──
      for (const sphere of s.spheres) {
        // Advance per-sphere rotation (scaled by rotationSpeed)
        sphere.rotY += sphere.rotSpeed * rotationSpeed

        // Sphere center position (with global rotation for depth), scaled by zoom
        const sphereCenterScreen = {
          x: cx + sphere.centerX * Math.cos(s.globalRotY) * 0.8 * Z,
          y: cy + sphere.centerY * Z,
        }

        const R = sphere.radius * Z * globeRadiusScale

        // ── Sphere shell ──
        ctx.beginPath()
        ctx.arc(sphereCenterScreen.x, sphereCenterScreen.y, R, 0, Math.PI * 2)
        const shellGrad = ctx.createRadialGradient(
          sphereCenterScreen.x, sphereCenterScreen.y, R * 0.7,
          sphereCenterScreen.x, sphereCenterScreen.y, R
        )
        shellGrad.addColorStop(0, `rgba(${sphere.rgb.r}, ${sphere.rgb.g}, ${sphere.rgb.b}, 0)`)
        shellGrad.addColorStop(1, `rgba(${sphere.rgb.r}, ${sphere.rgb.g}, ${sphere.rgb.b}, 0.04)`)
        ctx.fillStyle = shellGrad
        ctx.fill()

        // Shell ring
        ctx.beginPath()
        ctx.arc(sphereCenterScreen.x, sphereCenterScreen.y, R, 0, Math.PI * 2)
        ctx.strokeStyle = `rgba(${sphere.rgb.r}, ${sphere.rgb.g}, ${sphere.rgb.b}, 0.12)`
        ctx.lineWidth = 0.8
        ctx.stroke()

        // ── Nodes inside sphere ──
        const sphereRenderQueue = []

        for (const node of sphere.nodes) {
          const rotated = rotatePoint(node, sphere.tiltX + sphere.rotX, sphere.rotY)
          const depthFactor = (rotated.z + 1) / 2
          const fadeRange = depthFadeMul * 0.75
          const alpha = node.alpha * ((1 - fadeRange) + depthFactor * fadeRange)
          const renderSize = node.size * clusterScale * (0.5 + depthFactor * 0.5)

          const screenX = sphereCenterScreen.x + rotated.x * R
          const screenY = sphereCenterScreen.y + rotated.y * R

          nodeScreenPos[node.id] = { x: screenX, y: screenY }

          sphereRenderQueue.push({
            type: 'node',
            id: node.id,
            content: node.content,
            nodeType: node.type,
            lockIn: node.lockIn,
            x: screenX,
            y: screenY,
            z: rotated.z,
            size: renderSize,
            color: node.color,
            rgb: node.rgb,
            alpha,
            sphereId: sphere.id,
          })
        }

        // Apply influencer effects
        const infs = influencersRef.current
        if (infs && infs.length > 0) {
          for (const item of sphereRenderQueue) {
            for (const inf of infs) {
              const dx = item.x - inf.x
              const dy = item.y - inf.y
              const dist = Math.sqrt(dx * dx + dy * dy)
              if (dist < inf.radius && dist > 0) {
                const proximity = 1 - dist / inf.radius
                const effect = proximity * (inf.strength || 0.5)
                switch (inf.type) {
                  case 'attract':
                    item.x += (inf.x - item.x) * effect * 0.05
                    item.y += (inf.y - item.y) * effect * 0.05
                    break
                  case 'repel':
                    item.x -= (inf.x - item.x) * effect * 0.05
                    item.y -= (inf.y - item.y) * effect * 0.05
                    break
                  case 'excite':
                    item.alpha = Math.min(1, item.alpha + effect * 0.4)
                    item.size = item.size * (1 + effect * 0.5)
                    break
                  case 'calm':
                    item.alpha *= 1 - effect * 0.5
                    break
                }
              }
            }
          }
        }

        // Depth sort nodes within sphere
        sphereRenderQueue.sort((a, b) => a.z - b.z)

        // Render nodes
        for (const item of sphereRenderQueue) {
          const isFront = item.z > 0

          // Glow for high lock-in
          if (item.lockIn > 0.4 && isFront && showActivationGlow) {
            const glowR = item.size * 2.5
            const grad = ctx.createRadialGradient(item.x, item.y, item.size * 0.2, item.x, item.y, glowR)
            grad.addColorStop(0, `rgba(${item.rgb.r}, ${item.rgb.g}, ${item.rgb.b}, ${item.alpha * 0.2})`)
            grad.addColorStop(1, `rgba(${item.rgb.r}, ${item.rgb.g}, ${item.rgb.b}, 0)`)
            ctx.beginPath()
            ctx.arc(item.x, item.y, glowR, 0, Math.PI * 2)
            ctx.fillStyle = grad
            ctx.fill()
          }

          // Lock-in ring
          if (showLockInRings && item.lockIn > 0.15 && isFront) {
            ctx.beginPath()
            ctx.arc(item.x, item.y, item.size + 2, -Math.PI / 2, -Math.PI / 2 + 2 * Math.PI * item.lockIn)
            ctx.strokeStyle = `rgba(${item.rgb.r}, ${item.rgb.g}, ${item.rgb.b}, ${item.alpha * 0.5})`
            ctx.lineWidth = 1
            ctx.stroke()
          }

          // Main dot
          ctx.beginPath()
          ctx.arc(item.x, item.y, item.size, 0, Math.PI * 2)
          ctx.fillStyle = `rgba(${item.rgb.r}, ${item.rgb.g}, ${item.rgb.b}, ${item.alpha})`
          ctx.fill()

          // Bright center
          if (item.size > 2 && isFront) {
            ctx.beginPath()
            ctx.arc(item.x, item.y, item.size * 0.3, 0, Math.PI * 2)
            ctx.fillStyle = `rgba(255, 255, 255, ${item.alpha * 0.5})`
            ctx.fill()
          }

          // Hover highlight
          const isHovered = item.id === s.hoveredNodeId
          if (isHovered && isFront) {
            ctx.beginPath()
            ctx.arc(item.x, item.y, item.size + 5, 0, Math.PI * 2)
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.6)'
            ctx.lineWidth = 1.5
            ctx.stroke()
          }

          // Hit test
          if (isFront && s._mouseX !== undefined) {
            const dx = s._mouseX - item.x
            const dy = s._mouseY - item.y
            const hitR = Math.max(item.size + 3, 10)
            if (dx * dx + dy * dy < hitR * hitR) {
              newHoveredId = item.id
            }
          }
        }

        // ── Sphere label ──
        const labelY = sphereCenterScreen.y + R + 16
        ctx.font = 'bold 11px monospace'
        ctx.textAlign = 'center'
        ctx.textBaseline = 'top'
        ctx.fillStyle = sphere.type === 'project'
          ? `rgba(${sphere.rgb.r}, ${sphere.rgb.g}, ${sphere.rgb.b}, 0.9)`
          : `rgba(${sphere.rgb.r}, ${sphere.rgb.g}, ${sphere.rgb.b}, 0.5)`
        const label = sphere.label.length > 25 ? sphere.label.slice(0, 23) + '..' : sphere.label
        ctx.fillText(label, sphereCenterScreen.x, labelY)

        // Node count below label
        ctx.font = '9px monospace'
        ctx.fillStyle = 'rgba(140, 140, 160, 0.5)'
        ctx.fillText(`${sphere.nodes.length} nodes`, sphereCenterScreen.x, labelY + 14)

        // Type badge for projects
        if (sphere.type === 'project') {
          ctx.font = '8px monospace'
          ctx.fillStyle = 'rgba(250, 204, 21, 0.5)'
          ctx.fillText('PROJECT', sphereCenterScreen.x, labelY + 26)
        }
      }

      // ── Draw inter-group edges ──
      for (const edge of s.interEdges) {
        const fromPos = nodeScreenPos[edge.from]
        const toPos = nodeScreenPos[edge.to]
        if (fromPos && toPos) {
          ctx.beginPath()
          ctx.moveTo(fromPos.x, fromPos.y)
          ctx.lineTo(toPos.x, toPos.y)
          ctx.strokeStyle = `rgba(100, 100, 180, ${0.03 + edge.strength * 0.06})`
          ctx.lineWidth = 0.5
          ctx.setLineDash([3, 6])
          ctx.stroke()
          ctx.setLineDash([])
        }
      }

      // Update hover state
      if (newHoveredId !== s.hoveredNodeId) {
        s.hoveredNodeId = newHoveredId
        canvas.style.cursor = newHoveredId ? 'pointer' : 'grab'
        if (onNodeHover) onNodeHover(newHoveredId)
      }

      // ── Hover tooltip ──
      if (s.hoveredNodeId && s._mouseX !== undefined) {
        const pos = nodeScreenPos[s.hoveredNodeId]
        if (pos) {
          // Find the node data
          let hoveredNode = null
          for (const sphere of s.spheres) {
            hoveredNode = sphere.nodes.find(n => n.id === s.hoveredNodeId)
            if (hoveredNode) break
          }

          if (hoveredNode) {
            const tooltipW = 200
            const tooltipH = 52
            const tooltipX = Math.min(pos.x + 15, dw - tooltipW - 10)
            const tooltipY = pos.y - 10

            ctx.fillStyle = 'rgba(10, 10, 20, 0.92)'
            ctx.strokeStyle = 'rgba(100, 140, 200, 0.3)'
            ctx.lineWidth = 1
            ctx.beginPath()
            ctx.roundRect(tooltipX, tooltipY, tooltipW, tooltipH, 4)
            ctx.fill()
            ctx.stroke()

            ctx.font = '10px monospace'
            ctx.textAlign = 'left'
            ctx.textBaseline = 'top'
            ctx.fillStyle = hoveredNode.color
            const content = (hoveredNode.content || '').slice(0, 28)
            ctx.fillText(content || hoveredNode.id, tooltipX + 8, tooltipY + 8)

            ctx.font = '9px monospace'
            ctx.fillStyle = '#888'
            ctx.fillText(
              `${hoveredNode.type}  |  lock-in: ${(hoveredNode.lockIn * 100).toFixed(0)}%`,
              tooltipX + 8, tooltipY + 24
            )
            ctx.fillStyle = '#555'
            ctx.fillText(hoveredNode.id.slice(0, 30), tooltipX + 8, tooltipY + 36)
          }
        }
      }

      s.animId = requestAnimationFrame(render)
    }

    render()
    return () => {
      if (s.animId) cancelAnimationFrame(s.animId)
    }
  }, [autoRotate, showLockInRings, showActivationGlow, onNodeHover])

  // ── Mouse interaction ──
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const s = stateRef.current

    const onMouseDown = (e) => {
      s.isDragging = true
      s.lastMouse = { x: e.clientX, y: e.clientY }
      canvas.style.cursor = 'grabbing'
    }

    const onMouseMove = (e) => {
      const rect = canvas.getBoundingClientRect()
      s._mouseX = e.clientX - rect.left
      s._mouseY = e.clientY - rect.top

      if (s.isDragging && s.lastMouse) {
        const dx = e.clientX - s.lastMouse.x
        const dy = e.clientY - s.lastMouse.y
        s.globalRotY += dx * 0.003
        s.globalRotX += dy * 0.003
        s.globalMomentumY = dx * 0.002
        s.globalMomentumX = dy * 0.002
        s.lastMouse = { x: e.clientX, y: e.clientY }
      }
    }

    const onMouseUp = () => {
      s.isDragging = false
      if (!s.hoveredNodeId) canvas.style.cursor = 'grab'
    }

    const onClick = () => {
      if (s.hoveredNodeId && onNodeClick) {
        onNodeClick(s.hoveredNodeId)
      }
    }

    const onMouseLeave = () => {
      s.isDragging = false
      s._mouseX = undefined
      s._mouseY = undefined
      if (s.hoveredNodeId) {
        s.hoveredNodeId = null
        if (onNodeHover) onNodeHover(null)
      }
    }

    // Pinch / scroll zoom — trackpad two-finger gesture fires 'wheel'
    let drillCooldown = false
    const onWheel = (e) => {
      e.preventDefault()
      const delta = e.ctrlKey ? -e.deltaY * 0.01 : -e.deltaY * 0.002
      s.zoomTarget = Math.max(0.3, Math.min(3.0, s.zoomTarget + delta))

      // Drill-in: zoom past 2.2x while hovering a node
      if (s.zoomTarget > 2.2 && s.hoveredNodeId && onNodeClick && !drillCooldown) {
        drillCooldown = true
        s.zoomTarget = 1
        s.zoom = 1
        onNodeClick(s.hoveredNodeId)
        setTimeout(() => { drillCooldown = false }, 600)
      }

      // Drill-out: zoom below 0.4x → go back to universe
      if (s.zoomTarget < 0.4 && onBack && !drillCooldown) {
        drillCooldown = true
        s.zoomTarget = 1
        s.zoom = 1
        onBack()
        setTimeout(() => { drillCooldown = false }, 600)
      }
    }

    canvas.addEventListener('mousedown', onMouseDown)
    canvas.addEventListener('mousemove', onMouseMove)
    canvas.addEventListener('mouseup', onMouseUp)
    canvas.addEventListener('click', onClick)
    canvas.addEventListener('mouseleave', onMouseLeave)
    canvas.addEventListener('wheel', onWheel, { passive: false })

    return () => {
      canvas.removeEventListener('mousedown', onMouseDown)
      canvas.removeEventListener('mousemove', onMouseMove)
      canvas.removeEventListener('mouseup', onMouseUp)
      canvas.removeEventListener('click', onClick)
      canvas.removeEventListener('mouseleave', onMouseLeave)
      canvas.removeEventListener('wheel', onWheel)
    }
  }, [onNodeClick, onNodeHover, onBack])

  return (
    <canvas
      ref={canvasRef}
      style={{
        width: '100%',
        height: '100%',
        cursor: 'grab',
        display: 'block',
      }}
    />
  )
})

export default GalaxyView
