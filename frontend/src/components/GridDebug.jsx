import React from 'react';
import { useGrid } from '../contexts/GridContext';

/**
 * GridDebug — Log overlay panel for the grid system.
 *
 * Shows recent grid events: point hovers, zone transitions,
 * subdivision changes, orb snap events. Only visible in debug mode.
 */
export default function GridDebug() {
  const gridCtx = useGrid();

  if (!gridCtx?.debugMode) return null;

  const { logs, level, grid, logVersion } = gridCtx;
  const { cols, rows, points } = grid;

  return (
    <div
      style={{
        position: 'absolute',
        bottom: 0,
        left: 0,
        width: 340,
        maxHeight: 240,
        background: 'rgba(255,255,255,0.96)',
        borderTop: '1px solid #e0dce8',
        borderRight: '1px solid #e0dce8',
        borderTopRightRadius: 4,
        fontFamily: '"JetBrains Mono", monospace',
        fontSize: 10,
        overflowY: 'auto',
        zIndex: 20,
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: '6px 10px',
          borderBottom: '1px solid #e0dce8',
          color: '#6d45c8',
          fontSize: 9,
          fontWeight: 500,
          letterSpacing: '0.1em',
          display: 'flex',
          justifyContent: 'space-between',
        }}
      >
        GRID LOG
        <span style={{ color: '#a098b8', fontWeight: 300 }}>
          L{level} {cols}×{rows} {points.length}pts
        </span>
      </div>

      {/* Log entries */}
      <div style={{ padding: '4px 0' }}>
        {logs.map((entry, i) => (
          <div
            key={`${logVersion}-${i}`}
            style={{
              padding: '2px 10px',
              lineHeight: 1.6,
              color: i === 0 ? '#4a2d8a' : '#7a7490',
              borderLeft: i === 0 ? '2px solid #6d45c8' : '2px solid transparent',
            }}
          >
            {entry}
          </div>
        ))}
      </div>
    </div>
  );
}
