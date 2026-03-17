import { useRef, useEffect } from 'react';
import { ORB_FOLLOW_CONFIG } from '../config/orbFollow';

/**
 * Hook for Luna Orb positioning.
 *
 * Places the orb at center of the container, then applies a gentle
 * sine-wave float controlled by ORB_FOLLOW_CONFIG (mutable via sliders).
 *
 * No spring physics, no waypoints, no timers — just a clean rAF loop.
 */
export function useOrbFollow(chatContainerRef, messagesEndRef, orbRef) {
  const animRef = useRef(null);

  useEffect(() => {
    const cfg = ORB_FOLLOW_CONFIG;

    // Compute center once (recalc on resize)
    let cx = 0;
    let cy = 0;

    const recalcCenter = () => {
      if (!chatContainerRef.current) return;
      const rect = chatContainerRef.current.getBoundingClientRect();
      const orbSize = 56;
      const canvasSize = orbSize * 4; // 224
      const centerOffset = canvasSize / 2 - orbSize / 2;
      cx = rect.width / 2 - orbSize / 2 - centerOffset;
      cy = rect.height / 2 - orbSize / 2 - centerOffset;
    };

    recalcCenter();

    const animate = (timestamp) => {
      const floatX = cfg.floatAmplitudeX > 0
        ? Math.sin(timestamp * cfg.floatSpeedX) * cfg.floatAmplitudeX
        : 0;
      const floatY = cfg.floatAmplitudeY > 0
        ? Math.sin(timestamp * cfg.floatSpeedY) * cfg.floatAmplitudeY
        : 0;

      if (orbRef.current) {
        orbRef.current.style.transform = `translate(${cx + floatX}px, ${cy + floatY}px)`;
      }

      animRef.current = requestAnimationFrame(animate);
    };

    animRef.current = requestAnimationFrame(animate);

    const onResize = () => recalcCenter();
    window.addEventListener('resize', onResize, { passive: true });

    return () => {
      if (animRef.current) cancelAnimationFrame(animRef.current);
      window.removeEventListener('resize', onResize);
    };
  }, [chatContainerRef, orbRef]);
}
