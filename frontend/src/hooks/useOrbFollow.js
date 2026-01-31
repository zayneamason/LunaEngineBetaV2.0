import { useRef, useEffect, useCallback } from 'react';
import { ORB_FOLLOW_CONFIG } from '../config/orbFollow';

/**
 * Hook for Luna Orb follow behavior with spring physics and fairy float
 *
 * @param {React.RefObject} chatContainerRef - Ref to the scrollable chat container
 * @param {React.RefObject} messagesEndRef - Ref to the end-of-messages marker
 * @param {React.RefObject} orbRef - Ref to the orb DOM element (for direct manipulation)
 * @returns {void} - Updates orb position via direct DOM manipulation
 */
export function useOrbFollow(chatContainerRef, messagesEndRef, orbRef) {
  const positionRef = useRef({ x: 0, y: 0 });
  const velocityRef = useRef({ x: 0, y: 0 });
  const targetRef = useRef({ x: 0, y: 0 });
  const animationFrameRef = useRef(null);
  const startTimeRef = useRef(Date.now());

  const {
    followSpeed,
    deceleration,
    floatAmplitudeX,
    floatAmplitudeY,
    floatSpeedX,
    floatSpeedY,
    marginFromEdge,
    verticalOffset,
    minY,
    maxYFromBottom,
  } = ORB_FOLLOW_CONFIG;

  // Calculate target position based on latest message
  const updateTarget = useCallback(() => {
    if (!chatContainerRef.current) return;

    const container = chatContainerRef.current;
    const containerRect = container.getBoundingClientRect();

    // X: Right side of container with margin
    const orbWidth = 56; // Match the size prop in ChatPanel
    const targetX = containerRect.width - marginFromEdge - orbWidth;

    // Y: Follow latest message or viewport center
    let targetY;

    if (messagesEndRef?.current) {
      // Anchor to latest message
      const messagesEnd = messagesEndRef.current;
      const endRect = messagesEnd.getBoundingClientRect();
      const containerTop = containerRect.top;
      targetY = endRect.top - containerTop - 100 + verticalOffset; // 100px above end marker
    } else {
      // Fallback: viewport center
      targetY = containerRect.height / 2 + verticalOffset;
    }

    // Apply constraints
    targetY = Math.max(minY, targetY);
    targetY = Math.min(containerRect.height - maxYFromBottom, targetY);

    targetRef.current = { x: targetX, y: targetY };
  }, [chatContainerRef, messagesEndRef, marginFromEdge, verticalOffset, minY, maxYFromBottom]);

  // Animation loop
  const animate = useCallback((timestamp) => {
    const elapsed = timestamp;

    // === Spring Physics ===
    const dx = targetRef.current.x - positionRef.current.x;
    const dy = targetRef.current.y - positionRef.current.y;

    // Apply spring force
    velocityRef.current.x += dx * followSpeed;
    velocityRef.current.y += dy * followSpeed;

    // Apply deceleration (friction)
    velocityRef.current.x *= deceleration;
    velocityRef.current.y *= deceleration;

    // Update position
    positionRef.current.x += velocityRef.current.x;
    positionRef.current.y += velocityRef.current.y;

    // === Fairy Float Overlay ===
    const floatX = Math.sin(elapsed * floatSpeedX) * floatAmplitudeX;
    const floatY = Math.sin(elapsed * floatSpeedY) * floatAmplitudeY;

    // === Final Position ===
    const finalX = positionRef.current.x + floatX;
    const finalY = positionRef.current.y + floatY;

    // Apply transform directly to DOM
    if (orbRef.current) {
      orbRef.current.style.transform = `translate(${finalX}px, ${finalY}px)`;
    }

    // Continue animation
    animationFrameRef.current = requestAnimationFrame(animate);
  }, [followSpeed, deceleration, floatAmplitudeX, floatAmplitudeY, floatSpeedX, floatSpeedY, orbRef]);

  // Start animation loop
  useEffect(() => {
    startTimeRef.current = performance.now();

    // Initialize position to a reasonable default
    if (chatContainerRef.current) {
      const containerRect = chatContainerRef.current.getBoundingClientRect();
      positionRef.current = {
        x: containerRect.width - marginFromEdge - 56,
        y: containerRect.height / 2
      };
      targetRef.current = { ...positionRef.current };
    }

    const runAnimation = (timestamp) => {
      updateTarget();
      animate(timestamp);
    };

    animationFrameRef.current = requestAnimationFrame(runAnimation);

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [animate, updateTarget, chatContainerRef, marginFromEdge]);

  // Listen for scroll events
  useEffect(() => {
    const container = chatContainerRef.current;
    if (!container) return;

    const handleScroll = () => {
      updateTarget(); // Target updates, spring physics handles smooth follow
    };

    container.addEventListener('scroll', handleScroll, { passive: true });
    return () => container.removeEventListener('scroll', handleScroll);
  }, [chatContainerRef, updateTarget]);

  // Listen for resize events
  useEffect(() => {
    const handleResize = () => {
      updateTarget();
    };

    window.addEventListener('resize', handleResize, { passive: true });
    return () => window.removeEventListener('resize', handleResize);
  }, [updateTarget]);
}
