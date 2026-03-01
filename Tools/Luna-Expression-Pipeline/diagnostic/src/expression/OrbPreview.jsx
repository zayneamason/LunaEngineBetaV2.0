import React, { useRef, useEffect, useMemo } from 'react';

export default function OrbPreview({ dims, mode = 'SIM', rendererState, onModeChange, width = 260, height = 260 }) {
  const canvasRef = useRef(null);
  const animRef = useRef({ breatheT: 0, driftT: Math.random() * 1000 });

  // Map dimensions → ring rendering params
  const params = useMemo(() => {
    // In LIVE mode, use backend renderer state if available
    if (mode === 'LIVE' && rendererState) {
      return {
        hue: rendererState.hue || 260,
        sat: rendererState.sat || 65,
        light: rendererState.light || 47,
        breatheSpeed: rendererState.breatheSpeed || 0.015,
        breatheAmp: rendererState.breatheAmp || 2.5,
        driftSpeed: rendererState.driftSpeed || 0.0008,
        driftRx: rendererState.driftRx || 12,
        driftRy: rendererState.driftRy || 8,
        phaseOffset: rendererState.phaseOffset || 0.95,
        opacityMul: rendererState.opacityMul || 0.8,
        flicker: rendererState.flicker || false,
        glowAmbient: rendererState.glowAmbient || 0.08,
        glowCorona: rendererState.glowCorona || 0.12,
        coreBright: rendererState.coreBright || 0.65,
      };
    }

    // SIM mode: compute from dimension values
    const v = dims?.d_val ?? 0.6;
    const a = dims?.d_aro ?? 0.4;
    const c = dims?.d_cert ?? 0.7;
    const e = dims?.d_eng ?? 0.5;
    const w = dims?.d_warm ?? 0.7;

    const hue = 240 + ((v + 1) / 2) * 40 + w * 15;
    const sat = 50 + a * 30 + w * 12;
    const light = 38 + ((v + 1) / 2) * 18;
    const breatheSpeed = 0.008 + a * 0.027;
    const breatheAmp = 1.5 + a * 2.5;
    const driftSpeed = 0.0003 + a * 0.0012;
    const driftRx = 8 + (1 - e) * 10;
    const driftRy = 5 + (1 - e) * 7;
    const phaseOffset = 1.2 - c * 0.5;
    const opacityMul = 0.6 + c * 0.4;
    const flicker = c < 0.25;
    const glowAmbient = 0.04 + e * 0.11;
    const glowCorona = 0.06 + e * 0.16;
    const coreBright = 0.4 + ((v + 1) / 2) * 0.5;

    return { hue, sat, light, breatheSpeed, breatheAmp, driftSpeed, driftRx, driftRy,
             phaseOffset, opacityMul, flicker, glowAmbient, glowCorona, coreBright };
  }, [dims, mode, rendererState]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const dpr = 2;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = width + 'px';
    canvas.style.height = height + 'px';
    const anim = animRef.current;

    const BASE_R = 52;
    const RING_COUNT = 5;
    const spacing = BASE_R / (RING_COUNT + 0.5);
    const rings = [];
    for (let i = 0; i < RING_COUNT; i++) {
      const t = i / (RING_COUNT - 1);
      rings.push({
        baseRadius: BASE_R - i * spacing,
        baseOpacity: 0.08 + t * 0.35,
        hueOff: t * 8,
        satOff: t * 15,
        lightOff: t * 10,
        strokeWidth: 1.2 - t * 0.4,
        fill: i === RING_COUNT - 1,
      });
    }

    let animId;
    const render = () => {
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, width, height);

      const p = params;
      anim.breatheT += p.breatheSpeed;
      anim.driftT += p.driftSpeed;

      const cx = width / 2;
      const cy = height / 2;
      const dx = Math.sin(anim.driftT * 1.0) * p.driftRx + Math.sin(anim.driftT * 2.3) * 3;
      const dy = Math.cos(anim.driftT * 0.7) * p.driftRy + Math.cos(anim.driftT * 1.9) * 2;
      const bob = Math.sin(anim.driftT * 0.4) * 3;
      const x = cx + dx;
      const y = cy + dy + bob;

      const bt = anim.breatheT;

      // Glow layers
      const glowPulse = 0.7 + Math.sin(bt * 0.8) * 0.3;

      // Ambient halo
      const g1 = ctx.createRadialGradient(x, y, 0, x, y, BASE_R * 2.2);
      g1.addColorStop(0, `hsla(${p.hue}, ${p.sat}%, ${p.light + 20}%, ${p.glowAmbient * glowPulse})`);
      g1.addColorStop(0.4, `hsla(${p.hue}, ${p.sat}%, ${p.light + 20}%, ${p.glowAmbient * 0.4 * glowPulse})`);
      g1.addColorStop(1, `hsla(${p.hue}, ${p.sat}%, ${p.light + 20}%, 0)`);
      ctx.fillStyle = g1;
      ctx.beginPath(); ctx.arc(x, y, BASE_R * 2.2, 0, Math.PI * 2); ctx.fill();

      // Corona
      const g2 = ctx.createRadialGradient(x, y, 0, x, y, BASE_R * 1.4);
      g2.addColorStop(0, `hsla(${p.hue}, ${p.sat}%, ${p.light + 10}%, ${p.glowCorona * glowPulse})`);
      g2.addColorStop(0.5, `hsla(${p.hue}, ${p.sat - 10}%, ${p.light}%, ${p.glowCorona * 0.5 * glowPulse})`);
      g2.addColorStop(1, `hsla(${p.hue}, ${p.sat - 10}%, ${p.light}%, 0)`);
      ctx.fillStyle = g2;
      ctx.beginPath(); ctx.arc(x, y, BASE_R * 1.4, 0, Math.PI * 2); ctx.fill();

      // Rings
      rings.forEach((ring, i) => {
        const offset = i * p.phaseOffset;
        const wave = Math.sin(bt + offset);
        const wave2 = Math.sin(bt * 0.6 + offset * 1.3);
        const r = Math.max(2, ring.baseRadius + wave * p.breatheAmp + wave2 * 1.2);

        const opPulse = 0.5 + Math.sin(bt * 0.9 + offset) * 0.5;
        let alpha = ring.baseOpacity * (0.6 + opPulse * 0.5) * p.opacityMul;
        if (p.flicker) alpha *= (0.4 + Math.random() * 0.6);
        alpha = Math.max(0, Math.min(1, alpha));

        const rh = p.hue + ring.hueOff;
        const rs = p.sat + ring.satOff;
        const rl = p.light + ring.lightOff;

        ctx.beginPath();
        ctx.arc(x, y, r, 0, Math.PI * 2);
        ctx.strokeStyle = `hsla(${rh}, ${rs}%, ${rl}%, ${alpha})`;
        ctx.lineWidth = ring.strokeWidth;
        ctx.stroke();

        if (ring.fill) {
          const fg = ctx.createRadialGradient(x, y, 0, x, y, r);
          fg.addColorStop(0, `hsla(${rh}, ${rs + 10}%, ${rl + 15}%, ${alpha * 0.6})`);
          fg.addColorStop(0.6, `hsla(${rh}, ${rs}%, ${rl}%, ${alpha * 0.2})`);
          fg.addColorStop(1, `hsla(${rh}, ${rs}%, ${rl}%, 0)`);
          ctx.fillStyle = fg;
          ctx.fill();
        }
      });

      // Core
      const corePulse = 0.6 + Math.sin(bt * 1.2) * 0.4;
      const coreR = 3 + corePulse * 2;

      const cg = ctx.createRadialGradient(x, y, 0, x, y, coreR * 4);
      cg.addColorStop(0, `hsla(${p.hue}, ${p.sat + 10}%, ${p.light + 25}%, ${0.5 * corePulse * p.coreBright})`);
      cg.addColorStop(0.3, `hsla(${p.hue}, ${p.sat}%, ${p.light + 15}%, ${0.2 * corePulse * p.coreBright})`);
      cg.addColorStop(1, `hsla(${p.hue}, ${p.sat}%, ${p.light + 15}%, 0)`);
      ctx.fillStyle = cg;
      ctx.beginPath(); ctx.arc(x, y, coreR * 4, 0, Math.PI * 2); ctx.fill();

      ctx.beginPath();
      ctx.arc(x, y, coreR, 0, Math.PI * 2);
      ctx.fillStyle = `hsla(${p.hue}, ${p.sat - 10}%, ${p.light + 35}%, ${(0.6 + corePulse * 0.3) * p.coreBright})`;
      ctx.fill();

      // Anchor tether
      const dist = Math.sqrt((x - cx) ** 2 + (y - cy) ** 2);
      if (dist > 3) {
        ctx.beginPath();
        ctx.moveTo(cx, cy);
        ctx.lineTo(x, y);
        ctx.strokeStyle = `hsla(${p.hue}, ${p.sat}%, ${p.light + 15}%, ${Math.min(0.06, dist * 0.003)})`;
        ctx.lineWidth = 0.5;
        ctx.setLineDash([2, 4]);
        ctx.stroke();
        ctx.setLineDash([]);
      }

      animId = requestAnimationFrame(render);
    };

    render();
    return () => cancelAnimationFrame(animId);
  }, [params, width, height]);

  return (
    <div>
      <div style={{ display: 'flex', gap: 4, marginBottom: 6, justifyContent: 'center' }}>
        {['LIVE', 'SIM'].map(m => (
          <div key={m} onClick={() => onModeChange?.(m)} style={{
            fontSize: 8, padding: '2px 10px', borderRadius: 4, cursor: 'pointer',
            background: mode === m ? 'rgba(167,139,250,0.15)' : 'rgba(255,255,255,0.03)',
            color: mode === m ? '#a78bfa' : '#555',
            border: `1px solid ${mode === m ? 'rgba(167,139,250,0.3)' : 'rgba(255,255,255,0.06)'}`,
          }}>{m}</div>
        ))}
      </div>
      <div style={{ borderRadius: 10, overflow: 'hidden', background: '#06060c', border: '1px solid rgba(255,255,255,0.06)' }}>
        <canvas ref={canvasRef} style={{ display: 'block' }} />
      </div>
      <div style={{ fontSize: 7, color: '#333', marginTop: 3, textAlign: 'center' }}>
        {mode === 'SIM' ? 'drag dimension sliders to morph' : 'live engine data'}
      </div>
    </div>
  );
}
