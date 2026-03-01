import React, { useRef, useEffect } from 'react';
import { useGrid } from '../contexts/GridContext';
import { GRID_LAYER_CONFIG } from '../config/gridLayer';

const { debug: D } = GRID_LAYER_CONFIG;

/**
 * GridLayer — Canvas 2D grid visualization overlay.
 *
 * Renders the spatial index grid with anchor points, zone crosshairs,
 * and debug labels. Only draws when debug mode is active.
 */
export default function GridLayer() {
  const gridCtx = useGrid();
  const canvasRef = useRef(null);
  const stateRef = useRef({
    animId: null,
    mouseX: -1,
    mouseY: -1,
    nearest: null,
    lastId: null,
    lastZone: null,
  });

  // Render loop
  useEffect(() => {
    if (!gridCtx || !gridCtx.debugMode) return;

    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const s = stateRef.current;

    const render = () => {
      const parent = canvas.parentElement;
      if (!parent) return;

      const dpr = window.devicePixelRatio || 1;
      const w = parent.offsetWidth;
      const h = parent.offsetHeight;

      if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
        canvas.width = w * dpr;
        canvas.height = h * dpr;
        canvas.style.width = w + 'px';
        canvas.style.height = h + 'px';
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);

      const { points, cols, rows, cellW, cellH } = gridCtx.grid;
      if (!points.length) {
        s.animId = requestAnimationFrame(render);
        return;
      }

      // Draw grid lines
      ctx.strokeStyle = D.gridLineColor;
      ctx.lineWidth = D.gridLineWidth;
      for (let c = 0; c <= cols; c++) {
        ctx.beginPath();
        ctx.moveTo(c * cellW, 0);
        ctx.lineTo(c * cellW, h);
        ctx.stroke();
      }
      for (let r = 0; r <= rows; r++) {
        ctx.beginPath();
        ctx.moveTo(0, r * cellH);
        ctx.lineTo(w, r * cellH);
        ctx.stroke();
      }

      // Find nearest point to cursor
      let nearest = null;
      if (s.mouseX >= 0 && s.mouseY >= 0) {
        nearest = gridCtx.find(s.mouseX, s.mouseY);
        s.nearest = nearest;
      }

      // Draw points
      for (const p of points) {
        const isHit = nearest && nearest.id === p.id;
        const hasKids = p.children.length > 0;

        if (isHit) {
          // Crosshair
          ctx.strokeStyle = 'rgba(109,69,200,0.15)';
          ctx.lineWidth = 0.5;
          ctx.setLineDash(D.crosshairDash);
          ctx.beginPath(); ctx.moveTo(p.x, 0); ctx.lineTo(p.x, h); ctx.stroke();
          ctx.beginPath(); ctx.moveTo(0, p.y); ctx.lineTo(w, p.y); ctx.stroke();
          ctx.setLineDash([]);

          // Hit dot
          ctx.beginPath();
          ctx.arc(p.x, p.y, D.hitDotRadius, 0, Math.PI * 2);
          ctx.fillStyle = D.hitColor;
          ctx.fill();

          // Hit ring
          ctx.beginPath();
          ctx.arc(p.x, p.y, 9, 0, Math.PI * 2);
          ctx.strokeStyle = D.hitColor;
          ctx.lineWidth = 1;
          ctx.stroke();

          // Labels
          ctx.font = D.labelFont;
          ctx.textAlign = 'left';
          ctx.fillStyle = D.hitColor;
          ctx.fillText(p.id, p.x + 14, p.y - 6);
          ctx.fillStyle = D.zoneColor;
          ctx.fillText(p.zone, p.x + 14, p.y + 6);
          if (hasKids) {
            ctx.fillStyle = D.childColor;
            ctx.fillText(p.children.join(', '), p.x + 14, p.y + 17);
          }
        } else if (hasKids) {
          ctx.beginPath();
          ctx.arc(p.x, p.y, D.childDotRadius, 0, Math.PI * 2);
          ctx.fillStyle = D.childDotColor;
          ctx.fill();
        } else {
          ctx.beginPath();
          ctx.arc(p.x, p.y, D.dotRadius, 0, Math.PI * 2);
          ctx.fillStyle = D.dotColor;
          ctx.fill();
        }
      }

      // Log zone transitions
      if (nearest) {
        if (nearest.zone !== s.lastZone) {
          if (s.lastZone) gridCtx.addLog(`leave ${s.lastZone}`);
          gridCtx.addLog(`enter ${nearest.zone}`);
          s.lastZone = nearest.zone;
        }
        if (nearest.id !== s.lastId) {
          let msg = `${nearest.id} (${nearest.c},${nearest.r}) ${nearest.zone}`;
          if (nearest.children.length) msg += ` → ${nearest.children.join(', ')}`;
          gridCtx.addLog(msg);
          s.lastId = nearest.id;
        }
      }

      s.animId = requestAnimationFrame(render);
    };

    render();
    return () => {
      if (s.animId) cancelAnimationFrame(s.animId);
    };
  }, [gridCtx?.debugMode, gridCtx?.grid, gridCtx?.level]);

  // Mouse tracking
  useEffect(() => {
    if (!gridCtx?.debugMode) return;
    const canvas = canvasRef.current;
    if (!canvas) return;

    const s = stateRef.current;
    let throttle = 0;

    const onMove = (e) => {
      const now = Date.now();
      if (now - throttle < 40) return;
      throttle = now;
      const rect = canvas.getBoundingClientRect();
      s.mouseX = e.clientX - rect.left;
      s.mouseY = e.clientY - rect.top;
    };

    const onLeave = () => {
      s.mouseX = -1;
      s.mouseY = -1;
      s.nearest = null;
    };

    canvas.addEventListener('mousemove', onMove);
    canvas.addEventListener('mouseleave', onLeave);
    return () => {
      canvas.removeEventListener('mousemove', onMove);
      canvas.removeEventListener('mouseleave', onLeave);
    };
  }, [gridCtx?.debugMode]);

  if (!gridCtx?.debugMode) return null;

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'absolute',
        inset: 0,
        zIndex: 5,
        pointerEvents: 'auto',
        cursor: 'crosshair',
      }}
    />
  );
}
