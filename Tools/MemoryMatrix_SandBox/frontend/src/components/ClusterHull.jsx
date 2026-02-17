import React from 'react'

/**
 * ClusterHull — renders a translucent circle around a cluster's centroid.
 * Used as an overlay on the graph canvas.
 * (For canvas-based rendering, this logic would go into the nodeCanvasObject callback.
 *  This component is provided for potential DOM-overlay usage.)
 */

const CLUSTER_COLORS = [
  '#22d3ee', '#a78bfa', '#f87171', '#4ade80', '#facc15',
  '#fb923c', '#38bdf8', '#94a3b8', '#c084fc', '#fbbf24',
]

export function getClusterColor(index) {
  return CLUSTER_COLORS[index % CLUSTER_COLORS.length]
}

export default function ClusterHull({ cluster, nodePositions, colorIndex = 0 }) {
  const memberIds = cluster.member_ids || []
  const positions = memberIds
    .map(id => nodePositions[id])
    .filter(Boolean)

  if (positions.length < 2) return null

  const cx = positions.reduce((s, p) => s + p.x, 0) / positions.length
  const cy = positions.reduce((s, p) => s + p.y, 0) / positions.length
  const maxDist = Math.max(
    ...positions.map(p => Math.sqrt((p.x - cx) ** 2 + (p.y - cy) ** 2))
  )
  const radius = maxDist + 20
  const color = getClusterColor(colorIndex)

  return (
    <circle
      cx={cx}
      cy={cy}
      r={radius}
      fill={`${color}0a`}
      stroke={`${color}33`}
      strokeWidth={1}
      strokeDasharray="4 4"
    />
  )
}
