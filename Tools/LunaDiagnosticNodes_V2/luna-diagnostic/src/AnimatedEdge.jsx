import React from 'react';
import { getBezierPath, BaseEdge } from '@xyflow/react';

export default function AnimatedEdge({
  id, sourceX, sourceY, targetX, targetY,
  sourcePosition, targetPosition, data, style,
}) {
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition,
  });
  const isBroken = data?.broken;

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        style={{
          ...style,
          stroke: isBroken ? 'rgba(239,68,68,0.5)' : (style?.stroke || 'rgba(129,140,248,0.18)'),
          strokeWidth: isBroken ? 2 : 1.2,
          strokeDasharray: isBroken ? '5 5' : (data?.animated ? '6 4' : undefined),
          animation: (isBroken || data?.animated) ? 'flow-dash 1s linear infinite' : undefined,
        }}
      />
      {/* Animated particle */}
      {(data?.animated || isBroken) && (
        <circle
          r={isBroken ? 3 : 2}
          fill={isBroken ? '#ef4444' : '#818cf8'}
          opacity={0.7}
        >
          <animateMotion
            dur={isBroken ? '1.5s' : '2.5s'}
            repeatCount="indefinite"
            path={edgePath}
          />
        </circle>
      )}
      {/* Edge label */}
      {data?.label && (
        <foreignObject
          x={labelX - 60}
          y={labelY - 10}
          width={120}
          height={20}
          style={{ overflow: 'visible' }}
        >
          <div style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 8.5,
            color: isBroken ? '#f87171' : '#555568',
            background: '#08080f',
            padding: '1px 6px',
            borderRadius: 3,
            whiteSpace: 'nowrap',
            textAlign: 'center',
            width: 'fit-content',
            margin: '0 auto',
            border: isBroken ? '1px solid rgba(239,68,68,0.15)' : 'none',
          }}>{data.label}</div>
        </foreignObject>
      )}
    </>
  );
}
