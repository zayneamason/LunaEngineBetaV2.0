/**
 * ObservatoryGlobe — Pure Canvas 2D globe renderer for Universe zoom level.
 *
 * Renders clusters as positioned dots on a rotating 3D sphere with
 * phantom particles for depth. No Three.js, no WebGL — pure math.
 *
 * Props:
 *   clusters        — array of { id, label, node_count, avg_lock_in, lock_in, state, top_types }
 *   phantomCount    — number of background phantom particles (default 2000)
 *   globeStyle      — 'solid' | 'wireframe' | 'none'
 *   autoRotate      — boolean
 *   showLockInRings — boolean
 *   showActivationGlow — boolean
 *   onClusterClick  — (clusterId) => void
 *   onClusterHover  — (clusterId | null) => void
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

const CLUSTER_PALETTE = [
  '#22d3ee', '#a78bfa', '#facc15', '#4ade80', '#f87171',
  '#fb923c', '#38bdf8', '#e879f9', '#34d399', '#fbbf24',
]

const COLOR_VALUES = Object.values(TYPE_COLORS)

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
  // Y-axis rotation
  let x1 = px * Math.cos(rotY) + pz * Math.sin(rotY)
  let z1 = -px * Math.sin(rotY) + pz * Math.cos(rotY)
  let y1 = py
  // X-axis rotation
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

function getClusterColor(cluster, index) {
  // Use top_types to pick a weighted color, or fallback to palette
  if (cluster.top_types) {
    const entries = Object.entries(cluster.top_types)
    if (entries.length > 0) {
      entries.sort((a, b) => b[1] - a[1])
      const topType = entries[0][0]
      if (TYPE_COLORS[topType]) return TYPE_COLORS[topType]
    }
  }
  return CLUSTER_PALETTE[index % CLUSTER_PALETTE.length]
}

// ── Component ────────────────────────────────────────

const ObservatoryGlobe = forwardRef(function ObservatoryGlobe({
  clusters = [],
  phantomCount = 2000,
  globeStyle = 'solid',
  autoRotate = true,
  showLockInRings = true,
  showActivationGlow = true,
  onClusterClick,
  onClusterHover,
  influencers,
  settings = {},
}, ref) {
  // Physics tunables (from graphSettings, with defaults)
  const rotationSpeed = settings.rotationSpeed ?? 1
  const momentumDecay = settings.momentumDecay ?? 0.96
  const phantomDrift = settings.phantomDrift ?? 1
  const phantomAlpha = settings.phantomAlpha ?? 1
  const phantomSizeMul = settings.phantomSize ?? 1
  const twinkleSpeed = settings.twinkleSpeed ?? 1
  const clusterScale = settings.clusterScale ?? 1
  const globeRadiusScale = settings.globeRadiusScale ?? 1
  const depthFade = settings.depthFade ?? 1
  const canvasRef = useRef(null)
  const stateRef = useRef({
    rotX: 0.3,
    rotY: 0,
    dragRotX: 0,
    dragRotY: 0,
    momentumX: 0,
    momentumY: 0.002,
    isDragging: false,
    lastMouse: null,
    hoveredId: null,
    globeRadius: 200,
    zoom: 1,
    zoomTarget: 1,
    clusterNodes: [],
    phantoms: [],
    animId: null,
  })

  // Expose influencers ref for external objects
  const influencersRef = useRef([])
  useImperativeHandle(ref, () => ({
    get influencers() { return influencersRef.current },
    set influencers(val) { influencersRef.current = val },
    addInfluencer(inf) { influencersRef.current.push(inf) },
    removeInfluencer(id) {
      influencersRef.current = influencersRef.current.filter(i => i.id !== id)
    },
  }))

  // Sync external influencers prop
  useEffect(() => {
    if (influencers) influencersRef.current = influencers
  }, [influencers])

  // ── Generate cluster nodes from data ──
  useEffect(() => {
    const s = stateRef.current
    // Reset zoom when data changes (e.g. returning from galaxy)
    s.zoom = 1
    s.zoomTarget = 1
    if (!clusters || clusters.length === 0) {
      s.clusterNodes = []
      return
    }

    const positions = fibonacciSphere(clusters.length)
    s.clusterNodes = clusters.map((c, i) => {
      const pos = positions[i]
      const color = getClusterColor(c, i)
      const rgb = hexToRgb(color)
      const cid = c.id || c.cluster_id
      const nodeCount = c.member_count || c.node_count || 1
      const lockIn = c.lock_in || c.avg_lock_in || 0
      const size = Math.max(3, Math.sqrt(nodeCount) * 3)
      return {
        id: cid,
        label: c.label || c.name || cid,
        nodeCount,
        lockIn,
        state: c.state || 'drifting',
        baseX: pos.x,
        baseY: pos.y,
        baseZ: pos.z,
        size,
        color,
        rgb,
        alpha: 0.85 + lockIn * 0.15,
      }
    })
  }, [clusters])

  // ── Generate phantoms ──
  useEffect(() => {
    const s = stateRef.current
    const phantoms = []
    for (let i = 0; i < phantomCount; i++) {
      const p = randomSpherePoint()
      const colorIdx = Math.floor(Math.random() * COLOR_VALUES.length)
      const color = COLOR_VALUES[colorIdx]
      const rgb = hexToRgb(color)
      phantoms.push({
        baseX: p.x,
        baseY: p.y,
        baseZ: p.z,
        size: 0.5 + Math.random() * 1.2,
        rgb,
        alpha: 0.03 + Math.random() * 0.12,
        twinkleSpeed: Math.random() * 0.003 + 0.001,
        twinklePhase: Math.random() * Math.PI * 2,
        // Slight drift for organic feel
        driftX: (Math.random() - 0.5) * 0.0001,
        driftY: (Math.random() - 0.5) * 0.0001,
      })
    }
    s.phantoms = phantoms
  }, [phantomCount])

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
      // Only resize when dimensions change to avoid per-frame scale accumulation
      if (canvas.width !== dw * dpr || canvas.height !== dh * dpr) {
        canvas.width = dw * dpr
        canvas.height = dh * dpr
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      const cx = dw / 2
      const cy = dh / 2
      s.globeRadius = Math.min(dw, dh) * 0.38

      // Smooth zoom interpolation
      s.zoom += (s.zoomTarget - s.zoom) * 0.12
      const Z = s.zoom

      ctx.clearRect(0, 0, dw, dh)
      time++

      // Auto-rotate (scaled by rotationSpeed)
      const baseSpeed = 0.002 * rotationSpeed
      if (autoRotate && !s.isDragging) {
        s.rotY += s.momentumY
        s.rotX += s.momentumX
        // Decay momentum toward gentle auto-rotate
        s.momentumX *= momentumDecay
        s.momentumY = s.momentumY * momentumDecay + baseSpeed * (1 - momentumDecay)
      } else if (!s.isDragging) {
        // Momentum decay when not auto-rotating
        s.rotY += s.momentumY
        s.rotX += s.momentumX
        s.momentumX *= momentumDecay
        s.momentumY *= momentumDecay
      }

      const rotXVal = s.rotX + s.dragRotX
      const rotYVal = s.rotY + s.dragRotY
      const R = s.globeRadius * Z * globeRadiusScale

      // ── Draw globe shell ──
      if (globeStyle === 'solid') {
        const shellGrad = ctx.createRadialGradient(cx, cy, R * 0.85, cx, cy, R)
        shellGrad.addColorStop(0, 'rgba(20, 20, 40, 0)')
        shellGrad.addColorStop(0.7, 'rgba(30, 30, 60, 0.03)')
        shellGrad.addColorStop(1, 'rgba(60, 80, 120, 0.08)')
        ctx.beginPath()
        ctx.arc(cx, cy, R, 0, Math.PI * 2)
        ctx.fillStyle = shellGrad
        ctx.fill()

        // Subtle edge ring
        ctx.beginPath()
        ctx.arc(cx, cy, R, 0, Math.PI * 2)
        ctx.strokeStyle = 'rgba(100, 140, 200, 0.12)'
        ctx.lineWidth = 1
        ctx.stroke()
      } else if (globeStyle === 'wireframe') {
        // Latitude lines
        ctx.strokeStyle = 'rgba(100, 140, 200, 0.06)'
        ctx.lineWidth = 0.5
        for (let lat = -60; lat <= 60; lat += 30) {
          const latRad = (lat * Math.PI) / 180
          const r = R * Math.cos(latRad)
          const yOff = R * Math.sin(latRad)
          // Rotate the latitude circle
          const rotatedY = yOff * Math.cos(rotXVal)
          const scale = Math.max(0.1, 1 - Math.abs(Math.sin(rotXVal)) * Math.abs(Math.sin(latRad)))
          ctx.beginPath()
          ctx.ellipse(cx, cy + rotatedY, r * scale, r * 0.3, 0, 0, Math.PI * 2)
          ctx.stroke()
        }
        // Outer ring
        ctx.beginPath()
        ctx.arc(cx, cy, R, 0, Math.PI * 2)
        ctx.strokeStyle = 'rgba(100, 140, 200, 0.1)'
        ctx.lineWidth = 0.8
        ctx.stroke()
      }

      // ── Collect all renderable items ──
      const renderQueue = []

      // Phantoms
      for (const p of s.phantoms) {
        // Apply drift (scaled by phantomDrift)
        p.baseX += p.driftX * phantomDrift
        p.baseY += p.driftY * phantomDrift
        // Re-normalize to sphere surface
        const len = Math.sqrt(p.baseX * p.baseX + p.baseY * p.baseY + p.baseZ * p.baseZ)
        if (len > 0) {
          p.baseX /= len
          p.baseY /= len
          p.baseZ /= len
        }

        const rotated = rotatePoint(p, rotXVal, rotYVal)
        const twinkle = Math.sin(time * p.twinkleSpeed * twinkleSpeed + p.twinklePhase)
        const depthAlphaVal = (1 - depthFade * 0.35) + (rotated.z + 1) * 0.35 * depthFade
        const alpha = Math.max(0.01, p.alpha * phantomAlpha * depthAlphaVal + twinkle * 0.02)

        renderQueue.push({
          type: 'phantom',
          x: cx + rotated.x * R,
          y: cy + rotated.y * R,
          z: rotated.z,
          size: p.size * phantomSizeMul * (0.5 + (rotated.z + 1) * 0.25),
          rgb: p.rgb,
          alpha,
        })
      }

      // Cluster nodes
      for (const node of s.clusterNodes) {
        const rotated = rotatePoint(node, rotXVal, rotYVal)
        const depthFactor = (rotated.z + 1) / 2 // 0 = back, 1 = front
        const fadeRange = depthFade * 0.7
        const alpha = node.alpha * ((1 - fadeRange) + depthFactor * fadeRange)
        const renderSize = node.size * clusterScale * (0.6 + depthFactor * 0.4)

        renderQueue.push({
          type: 'cluster',
          id: node.id,
          label: node.label,
          nodeCount: node.nodeCount,
          lockIn: node.lockIn,
          state: node.state,
          x: cx + rotated.x * R,
          y: cy + rotated.y * R,
          z: rotated.z,
          size: renderSize,
          renderSize,
          color: node.color,
          rgb: node.rgb,
          alpha,
        })
      }

      // ── Apply influencer effects ──
      const infs = influencersRef.current
      if (infs && infs.length > 0) {
        for (const item of renderQueue) {
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

              if (inf.color) {
                item.tint = { color: inf.color, strength: effect * 0.3 }
              }
            }
          }
        }
      }

      // ── Depth sort (back to front) ──
      renderQueue.sort((a, b) => a.z - b.z)

      // ── Render ──
      let newHoveredId = null

      for (const item of renderQueue) {
        if (item.type === 'phantom') {
          ctx.beginPath()
          ctx.arc(item.x, item.y, item.size, 0, Math.PI * 2)
          ctx.fillStyle = `rgba(${item.rgb.r}, ${item.rgb.g}, ${item.rgb.b}, ${item.alpha})`
          ctx.fill()
        } else if (item.type === 'cluster') {
          const isFront = item.z > 0
          const isHovered = item.id === s.hoveredId

          // Glow for high lock-in or hovered
          if ((item.lockIn > 0.3 || isHovered) && isFront && showActivationGlow) {
            const glowR = item.size * 3
            const grad = ctx.createRadialGradient(item.x, item.y, item.size * 0.3, item.x, item.y, glowR)
            grad.addColorStop(0, `rgba(${item.rgb.r}, ${item.rgb.g}, ${item.rgb.b}, ${item.alpha * 0.25})`)
            grad.addColorStop(1, `rgba(${item.rgb.r}, ${item.rgb.g}, ${item.rgb.b}, 0)`)
            ctx.beginPath()
            ctx.arc(item.x, item.y, glowR, 0, Math.PI * 2)
            ctx.fillStyle = grad
            ctx.fill()
          }

          // Lock-in ring
          if (showLockInRings && item.lockIn > 0.1 && isFront) {
            ctx.beginPath()
            ctx.arc(item.x, item.y, item.size + 3, -Math.PI / 2, -Math.PI / 2 + 2 * Math.PI * item.lockIn)
            ctx.strokeStyle = `rgba(${item.rgb.r}, ${item.rgb.g}, ${item.rgb.b}, ${item.alpha * 0.6})`
            ctx.lineWidth = 1.5
            ctx.stroke()
          }

          // Main dot
          ctx.beginPath()
          ctx.arc(item.x, item.y, item.size, 0, Math.PI * 2)
          ctx.fillStyle = `rgba(${item.rgb.r}, ${item.rgb.g}, ${item.rgb.b}, ${item.alpha})`
          ctx.fill()

          // Bright center
          ctx.beginPath()
          ctx.arc(item.x, item.y, item.size * 0.35, 0, Math.PI * 2)
          ctx.fillStyle = `rgba(255, 255, 255, ${item.alpha * 0.6})`
          ctx.fill()

          // Hover ring
          if (isHovered && isFront) {
            ctx.beginPath()
            ctx.arc(item.x, item.y, item.size + 6, 0, Math.PI * 2)
            ctx.strokeStyle = `rgba(255, 255, 255, 0.6)`
            ctx.lineWidth = 1.5
            ctx.stroke()
          }

          // Label — only on hover
          if (isHovered && isFront && item.z > 0.3 && item.size > 4) {
            const fontSize = Math.max(8, Math.min(11, item.size * 0.8))
            ctx.font = `${fontSize}px monospace`
            ctx.textAlign = 'center'
            ctx.textBaseline = 'top'
            ctx.fillStyle = `rgba(200, 200, 220, ${item.alpha * 0.7})`
            const label = item.label.length > 22 ? item.label.slice(0, 20) + '..' : item.label
            ctx.fillText(label, item.x, item.y + item.size + 5)

            // Node count
            ctx.font = `${Math.max(7, fontSize - 2)}px monospace`
            ctx.fillStyle = `rgba(140, 140, 160, ${item.alpha * 0.5})`
            ctx.fillText(`${item.nodeCount}`, item.x, item.y + item.size + 5 + fontSize + 1)
          }

          // Hit test for hover
          if (isFront && s._mouseX !== undefined) {
            const dx = s._mouseX - item.x
            const dy = s._mouseY - item.y
            const hitR = Math.max(item.size + 4, 12)
            if (dx * dx + dy * dy < hitR * hitR) {
              newHoveredId = item.id
            }
          }
        }
      }

      // Update hover state
      if (newHoveredId !== s.hoveredId) {
        s.hoveredId = newHoveredId
        canvas.style.cursor = newHoveredId ? 'pointer' : 'grab'
        if (onClusterHover) onClusterHover(newHoveredId)
      }

      // ── Hover tooltip ──
      if (s.hoveredId && s._mouseX !== undefined) {
        const hovered = s.clusterNodes.find(n => n.id === s.hoveredId)
        if (hovered) {
          const rotated = rotatePoint(hovered, rotXVal, rotYVal)
          const tx = cx + rotated.x * R
          const ty = cy + rotated.y * R

          const tooltipW = 160
          const tooltipH = 52
          const tooltipX = tx + 15
          const tooltipY = ty - 10

          ctx.fillStyle = 'rgba(10, 10, 20, 0.9)'
          ctx.strokeStyle = 'rgba(100, 140, 200, 0.3)'
          ctx.lineWidth = 1
          ctx.beginPath()
          ctx.roundRect(tooltipX, tooltipY, tooltipW, tooltipH, 4)
          ctx.fill()
          ctx.stroke()

          ctx.font = '11px monospace'
          ctx.textAlign = 'left'
          ctx.textBaseline = 'top'
          ctx.fillStyle = hovered.color
          ctx.fillText(hovered.label.slice(0, 20), tooltipX + 8, tooltipY + 8)

          ctx.font = '9px monospace'
          ctx.fillStyle = '#888'
          ctx.fillText(`${hovered.nodeCount} nodes  |  lock-in: ${(hovered.lockIn * 100).toFixed(0)}%`, tooltipX + 8, tooltipY + 24)
          ctx.fillText(`state: ${hovered.state}`, tooltipX + 8, tooltipY + 36)
        }
      }

      s.animId = requestAnimationFrame(render)
    }

    render()
    return () => {
      if (s.animId) cancelAnimationFrame(s.animId)
    }
  }, [autoRotate, globeStyle, showLockInRings, showActivationGlow, onClusterHover])

  // ── Mouse interaction ──
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const s = stateRef.current

    const onMouseDown = (e) => {
      s.isDragging = true
      s.lastMouse = { x: e.clientX, y: e.clientY }
      s.dragRotX = 0
      s.dragRotY = 0
      canvas.style.cursor = 'grabbing'
    }

    const onMouseMove = (e) => {
      const rect = canvas.getBoundingClientRect()
      s._mouseX = e.clientX - rect.left
      s._mouseY = e.clientY - rect.top

      if (s.isDragging && s.lastMouse) {
        const dx = e.clientX - s.lastMouse.x
        const dy = e.clientY - s.lastMouse.y
        s.dragRotY = dx * 0.005
        s.dragRotX = dy * 0.005
        s.momentumY = dx * 0.003
        s.momentumX = dy * 0.003
        s.lastMouse = { x: e.clientX, y: e.clientY }
        // Apply drag rotation immediately
        s.rotY += s.dragRotY
        s.rotX += s.dragRotX
        s.dragRotY = 0
        s.dragRotX = 0
      }
    }

    const onMouseUp = () => {
      s.isDragging = false
      if (!s.hoveredId) {
        canvas.style.cursor = 'grab'
      }
    }

    const onClick = (e) => {
      if (onClusterClick) {
        onClusterClick(s.hoveredId || null)
      }
    }

    const onMouseLeave = () => {
      s.isDragging = false
      s._mouseX = undefined
      s._mouseY = undefined
      if (s.hoveredId) {
        s.hoveredId = null
        if (onClusterHover) onClusterHover(null)
      }
    }

    // Pinch / scroll zoom — trackpad two-finger gesture fires 'wheel'
    let drillCooldown = false
    const onWheel = (e) => {
      e.preventDefault()
      // ctrlKey is true for pinch gestures on trackpad
      const delta = e.ctrlKey ? -e.deltaY * 0.01 : -e.deltaY * 0.002
      s.zoomTarget = Math.max(0.3, Math.min(3.0, s.zoomTarget + delta))

      // Drill-in trigger: zoom past 2.2x while hovering a cluster
      if (s.zoomTarget > 2.2 && s.hoveredId && onClusterClick && !drillCooldown) {
        drillCooldown = true
        s.zoomTarget = 1
        s.zoom = 1
        onClusterClick(s.hoveredId)
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
  }, [onClusterClick, onClusterHover])

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

export default ObservatoryGlobe
