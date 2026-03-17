import React, { useRef, useEffect, useCallback, forwardRef } from 'react';
import { useOrbFollow } from '../hooks/useOrbFollow';
import { ORB_CANVAS_CONFIG as C } from '../config/orbCanvas';

/**
 * OrbCanvas — Canvas 2D ring-based orb renderer.
 *
 * Drop-in replacement for LunaOrb.jsx. Renders concentric breathing rings
 * with Lissajous fairy drift, layered glow, core dot, and anchor tether.
 *
 * Props match LunaOrb exactly (+ rendererState from WebSocket):
 *   state            — animation state string (idle, pulse, processing, etc.)
 *   size             — diameter in px (default 48)
 *   brightness       — multiplier 0-2 (default 1)
 *   colorOverride    — optional hex color
 *   showGlow         — show glow layers (default true)
 *   chatContainerRef — ref to chat container (enables follow behavior)
 *   messagesEndRef   — ref to messages end marker
 *   rendererState    — ring config from backend WebSocket (optional)
 */
export const OrbCanvas = forwardRef(function OrbCanvas({
  state = 'idle',
  size = 48,
  brightness = 1,
  colorOverride = null,
  showGlow = true,
  chatContainerRef = null,
  messagesEndRef = null,
  rendererState = null,
  onClick = null,
  onContextMenu = null,
}, externalRef) {
  const canvasRef = useRef(null);
  const containerRef = useRef(null);
  const internalOrbRef = useRef(null);
  const orbRef = externalRef || internalOrbRef;

  // Mutable animation state — never triggers re-renders
  const anim = useRef({
    breatheT: 0,
    driftT: Math.random() * 1000,
    orbX: 0,
    orbY: 0,
    homeX: 0,
    homeY: 0,
    dragging: false,
    animId: null,
    rings: null,        // ring config from backend or defaults
    params: null,       // animation params from backend or defaults
    lastState: null,    // track state changes
    initialized: false,
  });

  // Follow behavior (spring physics for scroll-tracking)
  const followEnabled = chatContainerRef !== null;
  useOrbFollow(
    followEnabled ? chatContainerRef : { current: null },
    followEnabled ? messagesEndRef : { current: null },
    followEnabled ? orbRef : { current: null },
  );

  // ── Build default rings (when backend doesn't provide them) ──
  const buildDefaultRings = useCallback(() => {
    const count = C.initialRingCount;
    const spacing = C.baseRadius / (count + 0.5);
    const rings = [];
    for (let i = 0; i < count; i++) {
      const t = count > 1 ? i / (count - 1) : 0;
      rings.push({
        baseRadius: C.baseRadius - i * spacing,
        baseOpacity: 0.08 + t * 0.35,
        hue: C.defaultHue,
        saturation: C.defaultSaturation + t * 15,
        lightness: C.defaultLightness + t * 10,
        strokeWidth: 1.2 - t * 0.4,
        hasFill: i === count - 1,
      });
    }
    return rings;
  }, []);

  // ── Default animation params ──
  const defaultParams = useCallback(() => ({
    breatheSpeed: C.breatheSpeed,
    breatheAmplitude: C.breatheAmplitude,
    driftRadiusX: C.driftRadiusX,
    driftRadiusY: C.driftRadiusY,
    driftSpeed: C.driftSpeed,
    ringPhaseOffset: C.ringPhaseOffset,
    syncBreathing: false,
    sequentialPulse: false,
    flicker: false,
    colorOverride: null,
    expandedDrift: false,
    contracted: false,
    speechRhythm: false,
    splitGroups: false,
    glowAmbientMax: C.glowAmbientMax,
    glowCoronaMax: C.glowCoronaMax,
  }), []);

  // ── Map state prop to local animation params (fallback when no backend) ──
  const paramsFromState = useCallback((st) => {
    const p = defaultParams();
    switch (st) {
      case 'pulse':
        p.syncBreathing = true;
        p.breatheAmplitude = C.breatheAmplitude * 1.5;
        p.breatheSpeed = 0.02;
        break;
      case 'pulse_fast':
        p.syncBreathing = true;
        p.breatheAmplitude = C.breatheAmplitude * 2;
        p.breatheSpeed = 0.04;
        break;
      case 'spin':
        p.ringPhaseOffset = 1.4;
        p.breatheSpeed = 0.02;
        break;
      case 'spin_fast':
        p.ringPhaseOffset = 2.0;
        p.breatheSpeed = 0.035;
        break;
      case 'flicker':
        p.flicker = true;
        break;
      case 'wobble':
        p.expandedDrift = true;
        p.driftRadiusX = 20;
        p.driftRadiusY = 16;
        p.driftSpeed = 0.0015;
        break;
      case 'drift':
        p.expandedDrift = true;
        p.driftRadiusX = 24;
        p.driftRadiusY = 16;
        p.driftSpeed = 0.001;
        break;
      case 'orbit':
        p.ringPhaseOffset = 1.2;
        p.breatheSpeed = 0.018;
        break;
      case 'glow':
        p.glowAmbientMax = 0.15;
        p.glowCoronaMax = 0.22;
        break;
      case 'split':
        p.splitGroups = true;
        break;
      case 'processing':
        p.sequentialPulse = true;
        p.breatheSpeed = 0.025;
        break;
      case 'listening':
        p.contracted = true;
        break;
      case 'speaking':
        p.speechRhythm = true;
        p.breatheSpeed = 0.03;
        break;
      case 'memory_search':
        p.colorOverride = '#06b6d4';
        p.ringPhaseOffset = 1.2;
        break;
      case 'error':
        p.colorOverride = '#ef4444';
        p.flicker = true;
        p.glowAmbientMax = 0.04;
        p.glowCoronaMax = 0.06;
        break;
      case 'disconnected':
        p.colorOverride = '#6b7280';
        p.breatheSpeed = 0.008;
        p.breatheAmplitude = 1.0;
        p.glowAmbientMax = 0.03;
        p.glowCoronaMax = 0.05;
        break;
      default:
        break;
    }
    return p;
  }, [defaultParams]);

  // ── Hex to HSLA helper ──
  const hexToHSL = useCallback((hex) => {
    const r = parseInt(hex.slice(1, 3), 16) / 255;
    const g = parseInt(hex.slice(3, 5), 16) / 255;
    const b = parseInt(hex.slice(5, 7), 16) / 255;
    const max = Math.max(r, g, b), min = Math.min(r, g, b);
    let h = 0, s = 0, l = (max + min) / 2;
    if (max !== min) {
      const d = max - min;
      s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
      if (max === r) h = ((g - b) / d + (g < b ? 6 : 0)) / 6;
      else if (max === g) h = ((b - r) / d + 2) / 6;
      else h = ((r - g) / d + 4) / 6;
    }
    return { h: h * 360, s: s * 100, l: l * 100 };
  }, []);

  // ── Canvas render loop ──
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const a = anim.current;

    // Initialize rings and params
    if (!a.initialized) {
      a.rings = buildDefaultRings();
      a.params = paramsFromState(state);
      a.initialized = true;
    }

    const render = () => {
      // ── Resolve ring config + params ──
      const rings = (rendererState?.rings) || a.rings || buildDefaultRings();
      const params = (rendererState?.animation) || a.params || defaultParams();
      const effectiveColor = colorOverride || params.colorOverride || null;
      const br = brightness;

      // ── Canvas sizing ──
      const parent = canvas.parentElement;
      if (!parent) { a.animId = requestAnimationFrame(render); return; }

      const dpr = window.devicePixelRatio || 1;
      // Canvas fills the orb container area
      const canvasSize = Math.max(size * 4, C.baseRadius * 5);
      const w = canvasSize;
      const h = canvasSize;

      if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
        canvas.width = w * dpr;
        canvas.height = h * dpr;
        canvas.style.width = w + 'px';
        canvas.style.height = h + 'px';
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);

      // ── Center position ──
      const cx = w / 2;
      const cy = h / 2;

      // ── Drift (fairy float) ──
      if (!a.dragging) {
        a.driftT += params.driftSpeed;
        const dx = Math.sin(a.driftT * 1.0) * params.driftRadiusX
                  + Math.sin(a.driftT * 2.3) * 4;
        const dy = Math.cos(a.driftT * 0.7) * params.driftRadiusY
                  + Math.cos(a.driftT * 1.9) * 3;
        const bob = Math.sin(a.driftT * 0.4) * 5;

        a.orbX += ((cx + dx) - a.orbX) * C.easeFactor;
        a.orbY += ((cy + dy + bob) - a.orbY) * C.easeFactor;
      }

      if (!a.orbX && !a.orbY) {
        a.orbX = cx;
        a.orbY = cy;
        a.homeX = cx;
        a.homeY = cy;
      }

      const x = a.orbX;
      const y = a.orbY;

      // ── Advance breathing ──
      a.breatheT += params.breatheSpeed;
      const breatheT = a.breatheT;

      // ── Determine base color ──
      let baseHue = C.defaultHue;
      let baseSat = C.defaultSaturation;
      let baseLight = C.defaultLightness;

      if (effectiveColor) {
        try {
          const hsl = hexToHSL(effectiveColor);
          baseHue = hsl.h;
          baseSat = hsl.s;
          baseLight = hsl.l;
        } catch (e) { /* use defaults */ }
      }

      // ── Glow layers ──
      if (showGlow) {
        const glowPulse = 0.7 + Math.sin(breatheT * C.glowPulseSpeed) * 0.3;

        // Ambient halo
        const g1 = ctx.createRadialGradient(x, y, 0, x, y, C.baseRadius * 2.2);
        g1.addColorStop(0, `hsla(${baseHue}, ${baseSat}%, ${baseLight + 20}%, ${params.glowAmbientMax * glowPulse * br})`);
        g1.addColorStop(0.4, `hsla(${baseHue}, ${baseSat}%, ${baseLight + 20}%, ${params.glowAmbientMax * 0.4 * glowPulse * br})`);
        g1.addColorStop(1, `hsla(${baseHue}, ${baseSat}%, ${baseLight + 20}%, 0)`);
        ctx.fillStyle = g1;
        ctx.beginPath(); ctx.arc(x, y, C.baseRadius * 2.2, 0, Math.PI * 2); ctx.fill();

        // Corona
        const g2 = ctx.createRadialGradient(x, y, 0, x, y, C.baseRadius * 1.4);
        g2.addColorStop(0, `hsla(${baseHue}, ${baseSat}%, ${baseLight + 10}%, ${params.glowCoronaMax * glowPulse * br})`);
        g2.addColorStop(0.5, `hsla(${baseHue}, ${baseSat - 10}%, ${baseLight}%, ${params.glowCoronaMax * 0.5 * glowPulse * br})`);
        g2.addColorStop(1, `hsla(${baseHue}, ${baseSat - 10}%, ${baseLight}%, 0)`);
        ctx.fillStyle = g2;
        ctx.beginPath(); ctx.arc(x, y, C.baseRadius * 1.4, 0, Math.PI * 2); ctx.fill();
      }

      // ── Rings ──
      rings.forEach((ring, i) => {
        const offset = params.syncBreathing ? 0 : i * params.ringPhaseOffset;
        const wave = Math.sin(breatheT + offset);
        const wave2 = Math.sin(breatheT * 0.6 + offset * 1.3);

        // Sequential pulse: each ring starts its pulse progressively later
        let seqMul = 1;
        if (params.sequentialPulse) {
          const seqPhase = (breatheT * 2 - i * 0.8) % (Math.PI * 2);
          seqMul = 0.5 + Math.sin(seqPhase) * 0.5;
        }

        // Flicker: random opacity jitter
        let flickerMul = 1;
        if (params.flicker) {
          flickerMul = 0.4 + Math.random() * 0.6;
        }

        // Speech rhythm: faster, irregular pulse
        let speechMul = 1;
        if (params.speechRhythm) {
          speechMul = 0.7 + Math.sin(breatheT * 3 + i * 0.5) * 0.3;
        }

        // Contracted: shrink radii
        const contractScale = params.contracted ? 0.7 : 1;

        // Animated radius
        let r = (ring.baseRadius * contractScale)
              + wave * params.breatheAmplitude * seqMul
              + wave2 * C.breatheSecondaryAmplitude;
        r = Math.max(2, r);

        // Animated opacity
        const opPulse = 0.5 + Math.sin(breatheT * 0.9 + offset) * 0.5;
        let alpha = ring.baseOpacity * (0.6 + opPulse * 0.5)
                   * flickerMul * speechMul * seqMul * br;
        if (params.contracted) alpha = Math.min(1, alpha * 1.5);
        alpha = Math.max(0, Math.min(1, alpha));

        // Ring color
        const rHue = effectiveColor ? baseHue : (ring.hue || baseHue);
        const rSat = effectiveColor ? baseSat : (ring.saturation || baseSat);
        const rLight = effectiveColor ? baseLight : (ring.lightness || baseLight);

        // Draw ring stroke
        ctx.beginPath();
        ctx.arc(x, y, r, 0, Math.PI * 2);
        ctx.strokeStyle = `hsla(${rHue}, ${rSat}%, ${rLight}%, ${alpha})`;
        ctx.lineWidth = ring.strokeWidth || 1;
        ctx.stroke();

        // Innermost ring fill
        if (ring.hasFill) {
          const fg = ctx.createRadialGradient(x, y, 0, x, y, r);
          fg.addColorStop(0, `hsla(${rHue}, ${rSat + 10}%, ${rLight + 15}%, ${alpha * 0.6})`);
          fg.addColorStop(0.6, `hsla(${rHue}, ${rSat}%, ${rLight}%, ${alpha * 0.2})`);
          fg.addColorStop(1, `hsla(${rHue}, ${rSat}%, ${rLight}%, 0)`);
          ctx.fillStyle = fg;
          ctx.fill();
        }
      });

      // ── Core dot ──
      const corePulse = 0.6 + Math.sin(breatheT * C.corePulseSpeed) * 0.4;
      const coreR = C.coreMinRadius + corePulse * (C.coreMaxRadius - C.coreMinRadius);

      // Core glow
      const cg = ctx.createRadialGradient(x, y, 0, x, y, coreR * 4);
      cg.addColorStop(0, `hsla(${baseHue}, ${baseSat + 10}%, ${baseLight + 25}%, ${0.5 * corePulse * br})`);
      cg.addColorStop(0.3, `hsla(${baseHue}, ${baseSat}%, ${baseLight + 15}%, ${0.2 * corePulse * br})`);
      cg.addColorStop(1, `hsla(${baseHue}, ${baseSat}%, ${baseLight + 15}%, 0)`);
      ctx.fillStyle = cg;
      ctx.beginPath(); ctx.arc(x, y, coreR * 4, 0, Math.PI * 2); ctx.fill();

      // Core solid
      ctx.beginPath();
      ctx.arc(x, y, coreR, 0, Math.PI * 2);
      ctx.fillStyle = `hsla(${baseHue}, ${baseSat - 10}%, ${baseLight + 35}%, ${(0.6 + corePulse * 0.3) * br})`;
      ctx.fill();

      // ── Anchor tether ──
      if (!a.dragging) {
        const dist = Math.sqrt((x - cx) ** 2 + (y - cy) ** 2);
        if (dist > 3) {
          ctx.beginPath();
          ctx.moveTo(cx, cy);
          ctx.lineTo(x, y);
          ctx.strokeStyle = `hsla(${baseHue}, ${baseSat}%, ${baseLight + 15}%, ${Math.min(C.anchorTetherMaxOpacity, dist * C.anchorTetherDistScale)})`;
          ctx.lineWidth = 0.5;
          ctx.setLineDash([2, 4]);
          ctx.stroke();
          ctx.setLineDash([]);
        }
      }

      a.animId = requestAnimationFrame(render);
    };

    render();
    return () => {
      if (a.animId) cancelAnimationFrame(a.animId);
    };
  }, [rendererState, buildDefaultRings, defaultParams, showGlow, hexToHSL]);

  // ── Update params when state prop changes ──
  useEffect(() => {
    const a2 = anim.current;
    if (a2.lastState !== state) {
      a2.lastState = state;
      if (!rendererState?.animation) {
        a2.params = paramsFromState(state);
      }
      if (!rendererState?.rings) {
        a2.rings = buildDefaultRings();
      }
    }
  }, [state, rendererState, paramsFromState, buildDefaultRings]);

  // ── Drag interaction ──
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const a3 = anim.current;

    const onDown = (e) => {
      const rect = canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;
      const dx = mx - a3.orbX;
      const dy = my - a3.orbY;
      if (Math.sqrt(dx * dx + dy * dy) < C.baseRadius + C.dragHitPadding) {
        a3.dragging = true;
        canvas.style.cursor = 'grabbing';
      }
    };

    const onMove = (e) => {
      if (!a3.dragging) return;
      const rect = canvas.getBoundingClientRect();
      a3.orbX = e.clientX - rect.left;
      a3.orbY = e.clientY - rect.top;
    };

    const onUp = () => {
      if (!a3.dragging) return;
      a3.dragging = false;
      canvas.style.cursor = '';
      // Home resets to current position (no grid snap without GridProvider)
      a3.homeX = a3.orbX;
      a3.homeY = a3.orbY;
    };

    canvas.addEventListener('mousedown', onDown);
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => {
      canvas.removeEventListener('mousedown', onDown);
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
  }, []);

  // ── Container style for follow behavior ──
  const canvasSize = Math.max(size * 4, C.baseRadius * 5);

  const containerStyle = followEnabled ? {
    position: 'absolute',
    top: 0,
    left: 0,
    width: canvasSize,
    height: canvasSize,
    willChange: 'transform',
    pointerEvents: 'none',
    zIndex: 100,
    transition: 'none',
  } : {};

  return (
    <div
      ref={orbRef}
      className="luna-orb-container"
      style={containerStyle}
    >
      <canvas
        ref={canvasRef}
        onClick={onClick}
        onContextMenu={onContextMenu}
        style={{
          width: canvasSize,
          height: canvasSize,
          pointerEvents: 'auto',
          cursor: onClick ? 'pointer' : 'default',
        }}
        role="img"
        aria-label={`Luna is ${state}`}
      />
    </div>
  );
});

export default OrbCanvas;
