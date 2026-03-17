import React, { useState, useCallback, useRef, useEffect, useMemo } from 'react';

const MONO = "'JetBrains Mono','SF Mono',monospace";
const LABEL = "'Bebas Neue',system-ui,sans-serif";

export const APERTURE_PRESETS = [
  { id: 'tunnel',   label: 'TUNNEL',   angle: 15, desc: 'Project focus only',                 icon: '\u25C9' },
  { id: 'narrow',   label: 'NARROW',   angle: 35, desc: 'Project + related collections',      icon: '\u25CE' },
  { id: 'balanced', label: 'BALANCED', angle: 55, desc: 'Focus with peripheral awareness',   icon: '\u25CB' },
  { id: 'wide',     label: 'WIDE',     angle: 75, desc: 'Broad recall, light filtering',      icon: '\u25CC' },
  { id: 'open',     label: 'OPEN',     angle: 95, desc: 'Full memory access, no filtering',   icon: '\u2299' },
];

// --- ApertureDial ---
export default function ApertureDial({ angle, onChange, visible, orbCenter, collections = [] }) {
  const dialRef = useRef(null);
  const [dragging, setDragging] = useState(false);
  const DIAL_RADIUS = 130;
  const KNOB_TRACK_RADIUS = 95;

  const angleToRad = (a) => ((a - 15) / 80) * Math.PI * 1.5 - Math.PI * 0.75;
  const radToAngle = (r) => ((r + Math.PI * 0.75) / (Math.PI * 1.5)) * 80 + 15;

  const knobRad = angleToRad(angle);
  const knobX = DIAL_RADIUS + Math.cos(knobRad) * KNOB_TRACK_RADIUS;
  const knobY = DIAL_RADIUS + Math.sin(knobRad) * KNOB_TRACK_RADIUS;

  const handleMouseDown = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragging(true);
  }, []);

  useEffect(() => {
    if (!dragging) return;
    const handleMove = (e) => {
      if (!dialRef.current) return;
      const rect = dialRef.current.getBoundingClientRect();
      const cx = rect.left + DIAL_RADIUS;
      const cy = rect.top + DIAL_RADIUS;
      const dx = e.clientX - cx;
      const dy = e.clientY - cy;
      const rad = Math.atan2(dy, dx);
      let newAngle = radToAngle(rad);
      newAngle = Math.max(15, Math.min(95, newAngle));
      onChange(Math.round(newAngle));
    };
    const handleUp = () => setDragging(false);
    window.addEventListener('mousemove', handleMove);
    window.addEventListener('mouseup', handleUp);
    return () => {
      window.removeEventListener('mousemove', handleMove);
      window.removeEventListener('mouseup', handleUp);
    };
  }, [dragging, onChange]);

  const activePreset = APERTURE_PRESETS.reduce((closest, p) =>
    Math.abs(p.angle - angle) < Math.abs(closest.angle - angle) ? p : closest
  );

  const threshold = 1 - (angle - 15) / 80;
  const lockInThreshold = threshold * 0.8;

  // Aperture cone
  const coneStartRad = -Math.PI / 2 - (angle * Math.PI / 180) / 2;
  const coneEndRad = -Math.PI / 2 + (angle * Math.PI / 180) / 2;
  const CONE_RADIUS = 70;

  const hasCenter = orbCenter && (orbCenter.x || orbCenter.y);
  const posStyle = hasCenter
    ? { position: 'fixed', left: orbCenter.x - DIAL_RADIUS, top: orbCenter.y - DIAL_RADIUS }
    : { position: 'fixed', top: '50%', left: '50%', transform: `translate(-50%, -50%) scale(${visible ? 1 : 0.85})` };

  return (
    <div
      ref={dialRef}
      style={{
        width: DIAL_RADIUS * 2,
        height: DIAL_RADIUS * 2,
        ...posStyle,
        opacity: visible ? 1 : 0,
        pointerEvents: visible ? 'auto' : 'none',
        ...(hasCenter ? { transform: visible ? 'scale(1)' : 'scale(0.85)' } : {}),
        transition: 'opacity 0.25s ease, transform 0.25s ease',
        zIndex: 100,
      }}
    >
      <svg width={DIAL_RADIUS * 2} height={DIAL_RADIUS * 2} viewBox={`0 0 ${DIAL_RADIUS * 2} ${DIAL_RADIUS * 2}`}>
        {/* Background disc */}
        <circle cx={DIAL_RADIUS} cy={DIAL_RADIUS} r={DIAL_RADIUS - 2}
          fill="var(--ec-bg, #0c0c14)" fillOpacity="0.92"
          stroke="#c084fc" strokeWidth="0.5" strokeOpacity="0.2" />

        {/* Aperture cone */}
        <path
          d={`M${DIAL_RADIUS},${DIAL_RADIUS} L${DIAL_RADIUS + Math.cos(coneStartRad) * CONE_RADIUS},${DIAL_RADIUS + Math.sin(coneStartRad) * CONE_RADIUS} A${CONE_RADIUS},${CONE_RADIUS} 0 ${angle > 180 ? 1 : 0} 1 ${DIAL_RADIUS + Math.cos(coneEndRad) * CONE_RADIUS},${DIAL_RADIUS + Math.sin(coneEndRad) * CONE_RADIUS} Z`}
          fill="#c084fc" fillOpacity="0.06"
          stroke="#c084fc" strokeWidth="0.5" strokeOpacity="0.2"
        />

        {/* Collection dots */}
        {collections.map((col, i) => {
          const colAngle = (i / Math.max(collections.length, 1)) * Math.PI * 2 - Math.PI / 2;
          const isVisible = (col.lockIn || 0) > lockInThreshold;
          const ringRadius = isVisible ? 40 + (1 - (col.lockIn || 0)) * 40 : 85 + (1 - (col.lockIn || 0)) * 30;
          const cx = DIAL_RADIUS + Math.cos(colAngle) * ringRadius;
          const cy = DIAL_RADIUS + Math.sin(colAngle) * ringRadius;
          const dotSize = isVisible ? 4 : 2.5;

          return (
            <g key={col.key}>
              <line x1={DIAL_RADIUS} y1={DIAL_RADIUS} x2={cx} y2={cy}
                stroke={col.color} strokeWidth={isVisible ? 0.5 : 0.2}
                strokeOpacity={isVisible ? 0.3 : 0.08}
                strokeDasharray={isVisible ? 'none' : '2 2'}
              />
              <circle cx={cx} cy={cy} r={dotSize}
                fill={isVisible ? col.color : 'var(--ec-text-muted, #3a3a50)'}
                fillOpacity={isVisible ? 0.8 : 0.3}
                stroke={col.color} strokeWidth={isVisible ? 0.5 : 0}
                strokeOpacity={0.4}
              />
              <text x={cx} y={cy + dotSize + 8}
                textAnchor="middle" fontSize="5.5" fontFamily={MONO}
                fill={isVisible ? col.color : 'var(--ec-text-muted, #3a3a50)'}
                fillOpacity={isVisible ? 0.7 : 0.3}
              >
                {col.key.split('_')[0]}
              </text>
            </g>
          );
        })}

        {/* Track arc */}
        <circle cx={DIAL_RADIUS} cy={DIAL_RADIUS} r={KNOB_TRACK_RADIUS}
          fill="none" stroke="var(--ec-text-muted, #3a3a50)" strokeWidth="1" strokeOpacity="0.15"
          strokeDasharray="3 3"
        />

        {/* Filled arc */}
        <path
          d={(() => {
            const startRad = angleToRad(15);
            const endRad = angleToRad(angle);
            const sx = DIAL_RADIUS + Math.cos(startRad) * KNOB_TRACK_RADIUS;
            const sy = DIAL_RADIUS + Math.sin(startRad) * KNOB_TRACK_RADIUS;
            const ex = DIAL_RADIUS + Math.cos(endRad) * KNOB_TRACK_RADIUS;
            const ey = DIAL_RADIUS + Math.sin(endRad) * KNOB_TRACK_RADIUS;
            const largeArc = (angle - 15) > 53 ? 1 : 0;
            return `M${sx},${sy} A${KNOB_TRACK_RADIUS},${KNOB_TRACK_RADIUS} 0 ${largeArc} 1 ${ex},${ey}`;
          })()}
          fill="none" stroke="#c084fc" strokeWidth="2" strokeOpacity="0.4" strokeLinecap="round"
        />

        {/* Preset tick marks */}
        {APERTURE_PRESETS.map(p => {
          const r = angleToRad(p.angle);
          const ix = DIAL_RADIUS + Math.cos(r) * (KNOB_TRACK_RADIUS - 8);
          const iy = DIAL_RADIUS + Math.sin(r) * (KNOB_TRACK_RADIUS - 8);
          const ox = DIAL_RADIUS + Math.cos(r) * (KNOB_TRACK_RADIUS + 8);
          const oy = DIAL_RADIUS + Math.sin(r) * (KNOB_TRACK_RADIUS + 8);
          const lx = DIAL_RADIUS + Math.cos(r) * (KNOB_TRACK_RADIUS + 20);
          const ly = DIAL_RADIUS + Math.sin(r) * (KNOB_TRACK_RADIUS + 20);
          const isActive = p.id === activePreset.id;
          return (
            <g key={p.id} onClick={() => onChange(p.angle)} style={{ cursor: 'pointer' }}>
              <line x1={ix} y1={iy} x2={ox} y2={oy}
                stroke={isActive ? '#c084fc' : 'var(--ec-text-muted, #3a3a50)'}
                strokeWidth={isActive ? 1.5 : 0.5}
                strokeOpacity={isActive ? 0.8 : 0.3}
              />
              <text x={lx} y={ly} textAnchor="middle" dominantBaseline="middle"
                fontSize="6" fontFamily={LABEL} letterSpacing="1"
                fill={isActive ? '#c084fc' : 'var(--ec-text-muted, #3a3a50)'}
                fillOpacity={isActive ? 0.9 : 0.4}
              >
                {p.label}
              </text>
            </g>
          );
        })}

        {/* Knob */}
        <g onMouseDown={handleMouseDown} style={{ cursor: 'grab' }}>
          <circle cx={knobX} cy={knobY} r={12} fill="transparent" />
          <circle cx={knobX} cy={knobY} r={7}
            fill="var(--ec-bg-raised, #111119)" stroke="#c084fc" strokeWidth="1.5"
            style={{ filter: 'drop-shadow(0 0 6px rgba(192,132,252,0.38))' }}
          />
          <circle cx={knobX} cy={knobY} r={3}
            fill="#c084fc" fillOpacity="0.6"
          />
        </g>

        {/* Center info */}
        <text x={DIAL_RADIUS} y={DIAL_RADIUS - 8} textAnchor="middle"
          fontSize="8" fontFamily={LABEL} letterSpacing="1.5" fill="#c084fc" fillOpacity="0.8"
        >
          {activePreset.icon}
        </text>
        <text x={DIAL_RADIUS} y={DIAL_RADIUS + 4} textAnchor="middle"
          fontSize="6.5" fontFamily={LABEL} letterSpacing="1" fill="#c084fc" fillOpacity="0.7"
        >
          {angle}{'\u00B0'}
        </text>
        <text x={DIAL_RADIUS} y={DIAL_RADIUS + 14} textAnchor="middle"
          fontSize="5" fontFamily={MONO} fill="var(--ec-text-faint, #5a5a70)" fillOpacity="0.6"
        >
          {activePreset.desc}
        </text>
      </svg>
    </div>
  );
}
