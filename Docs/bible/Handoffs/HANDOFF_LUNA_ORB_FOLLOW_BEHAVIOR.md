# HANDOFF: Luna Orb Follow Behavior with Fairy Movement

**Date:** 2025-01-27
**From:** Architecture Session (Claude.ai)
**To:** Claude Code
**Priority:** Medium - UX polish

---

## Problem Statement

Currently the Luna orb is anchored in a fixed position and stays static when the user scrolls through the conversation. This feels disconnected — Luna should travel alongside the chat content with smooth, organic "fairy-like" movement and graceful deceleration.

### Current Behavior
- Orb pinned to fixed viewport position
- No response to scroll
- Abrupt position changes (if any)

### Desired Behavior
- Orb follows the conversation flow
- Trails behind scroll with spring physics
- Settles with smooth deceleration
- Continuous subtle "fairy float" drift when idle
- Never teleports or jumps

---

## Animation Model: Spring-Follow with Drift

The orb uses two layered systems:

1. **Spring Physics** — Smooth pursuit of target position with velocity/deceleration
2. **Fairy Float** — Subtle sine-wave drift overlay for organic idle movement

```
Final Position = Spring Position + Fairy Float Offset
```

---

## Implementation Spec

### Configuration Constants

```javascript
// File: frontend/src/config/orbFollow.js

export const ORB_FOLLOW_CONFIG = {
  // === Spring Physics ===
  followSpeed: 0.08,        // How fast orb catches up (0.01-0.2, lower = more lag)
  deceleration: 0.92,       // Velocity decay per frame (0.85-0.98, higher = longer glide)
  velocityThreshold: 0.1,   // Stop calculating when velocity below this
  
  // === Fairy Float (idle drift) ===
  floatAmplitudeX: 8,       // Pixels of horizontal drift
  floatAmplitudeY: 12,      // Pixels of vertical drift
  floatSpeedX: 0.0015,      // Horizontal oscillation speed (radians per ms)
  floatSpeedY: 0.0023,      // Vertical (slightly different = organic feel)
  
  // === Positioning ===
  marginFromEdge: 40,       // Pixels from right edge of chat container
  verticalOffset: 0,        // Offset from anchor point (+ = down)
  anchorMode: 'latest',     // 'latest' | 'viewport' | 'scroll'
  
  // === Constraints ===
  minY: 100,                // Don't float above this (pixels from container top)
  maxYFromBottom: 150,      // Don't float below this (pixels from container bottom)
};
```

### Core Hook: `useOrbFollow.js`

```javascript
// File: frontend/src/hooks/useOrbFollow.js

import { useRef, useEffect, useCallback } from 'react';
import { ORB_FOLLOW_CONFIG } from '../config/orbFollow';

export function useOrbFollow(chatContainerRef, messagesEndRef) {
  const positionRef = useRef({ x: 0, y: 0 });
  const velocityRef = useRef({ x: 0, y: 0 });
  const targetRef = useRef({ x: 0, y: 0 });
  const animationFrameRef = useRef(null);
  const startTimeRef = useRef(Date.now());

  const {
    followSpeed,
    deceleration,
    velocityThreshold,
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
    const targetX = containerRect.width - marginFromEdge - 80; // 80 = orb width estimate
    
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
    const elapsed = timestamp - startTimeRef.current;
    
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
    
    // Continue animation
    animationFrameRef.current = requestAnimationFrame(animate);
    
    // Return position for rendering
    return { x: finalX, y: finalY };
  }, [followSpeed, deceleration, floatAmplitudeX, floatAmplitudeY, floatSpeedX, floatSpeedY]);

  // Start animation loop
  useEffect(() => {
    startTimeRef.current = Date.now();
    
    const runAnimation = (timestamp) => {
      updateTarget();
      animate(timestamp);
      animationFrameRef.current = requestAnimationFrame(runAnimation);
    };
    
    animationFrameRef.current = requestAnimationFrame(runAnimation);
    
    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [animate, updateTarget]);

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

  // Return current position for component to use
  return positionRef;
}
```

### Integration with LunaOrb Component

```javascript
// File: frontend/src/components/LunaOrb.jsx (modifications)

import { useOrbFollow } from '../hooks/useOrbFollow';

function LunaOrb({ chatContainerRef, messagesEndRef, ...props }) {
  const orbRef = useRef(null);
  const positionRef = useOrbFollow(chatContainerRef, messagesEndRef);
  
  // Use requestAnimationFrame for smooth rendering
  useEffect(() => {
    let frameId;
    
    const render = () => {
      if (orbRef.current && positionRef.current) {
        const { x, y } = positionRef.current;
        orbRef.current.style.transform = `translate(${x}px, ${y}px)`;
      }
      frameId = requestAnimationFrame(render);
    };
    
    frameId = requestAnimationFrame(render);
    return () => cancelAnimationFrame(frameId);
  }, [positionRef]);

  return (
    <div 
      ref={orbRef}
      className="luna-orb-container"
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        willChange: 'transform',  // GPU acceleration hint
        pointerEvents: 'none',    // Don't block chat interaction
      }}
    >
      {/* Existing orb content */}
    </div>
  );
}
```

### CSS Considerations

```css
/* Ensure smooth rendering */
.luna-orb-container {
  position: absolute;
  top: 0;
  left: 0;
  will-change: transform;
  pointer-events: none;
  z-index: 100;
  
  /* Prevent any CSS transitions interfering with JS animation */
  transition: none !important;
}

/* Chat container needs relative positioning */
.chat-container {
  position: relative;
  overflow-y: auto;
  overflow-x: hidden;
}
```

---

## Anchor Mode Options

The `anchorMode` config supports three strategies:

| Mode | Behavior | Best For |
|------|----------|----------|
| `'latest'` | Follows the most recent message | Default — Luna stays near the action |
| `'viewport'` | Centers in visible area | If user scrolls up to read history |
| `'scroll'` | Tracks scroll position directly | More literal "following" feel |

For v1, implement `'latest'` only. Others can be added later.

---

## Tuning Guide

| Want This | Adjust This |
|-----------|-------------|
| More lag behind scroll | Lower `followSpeed` (try 0.04) |
| Longer glide/coast | Higher `deceleration` (try 0.95) |
| Snappier response | Higher `followSpeed` (try 0.12) |
| More floaty idle | Higher `floatAmplitude` values |
| Slower fairy drift | Lower `floatSpeed` values |
| Less organic (more robotic) | Set both `floatSpeed` values equal |

---

## Edge Cases

| Scenario | Handling |
|----------|----------|
| Fast scroll | Orb trails behind gracefully, catches up with deceleration |
| Scroll to top | Target moves up, orb follows with same physics |
| New message arrives | Target shifts down, orb drifts to new position |
| Window resize | Recalculate X position, smooth transition |
| Container not mounted | Return early, no animation |
| Empty chat | Default to viewport center |

---

## Files to Modify

| File | Change |
|------|--------|
| `frontend/src/hooks/useOrbFollow.js` | **Create** — New hook for follow physics |
| `frontend/src/config/orbFollow.js` | **Create** — Configuration constants |
| `frontend/src/components/LunaOrb.jsx` | **Modify** — Integrate useOrbFollow |
| `frontend/src/components/ChatPanel.jsx` | **Modify** — Pass refs to LunaOrb |

---

## Testing Checklist

- [ ] Orb follows when scrolling down
- [ ] Orb follows when scrolling up
- [ ] Smooth deceleration when scroll stops
- [ ] Fairy float visible when idle
- [ ] No jank or stuttering
- [ ] Works with fast scroll
- [ ] Works with slow scroll
- [ ] New messages shift target correctly
- [ ] Orb doesn't escape container bounds
- [ ] Performance stays smooth (60fps)

---

## Performance Notes

- Use `requestAnimationFrame` for all position updates
- Use `transform` instead of `top/left` (GPU accelerated)
- Add `will-change: transform` CSS hint
- Use `passive: true` on scroll listener
- Avoid React state for position (causes re-renders) — use refs + direct DOM manipulation

---

## Success Criteria

- [ ] Orb travels with conversation, not pinned
- [ ] Movement feels organic, not mechanical
- [ ] Smooth deceleration when stopping
- [ ] Subtle fairy float when idle
- [ ] No performance degradation
- [ ] Respects container bounds

---

## Visual Reference

```
┌─────────────────────────────────────┐
│  User: Hello Luna                   │
│                                     │
│  Luna: Hi there! *waves*        🟣 ← Orb floats here
│                                 ↑    (near latest message)
│                            fairy drift
│  User: How are you?                 │
│                                     │
│  Luna: I'm doing great!         🟣 ← Orb follows down
│                                     │   (with spring physics)
└─────────────────────────────────────┘
         ↓ scroll down
┌─────────────────────────────────────┐
│  Luna: I'm doing great!             │
│                                     │
│  User: Tell me a joke               │
│                                     │
│  Luna: Why did the AI...        🟣 ← Orb settled here
│                                 ~~~   (fairy float continues)
└─────────────────────────────────────┘
```

---

## Notes

- The fairy float uses two sine waves at different frequencies — this creates organic, non-repetitive movement
- Spring physics prevents any jarring jumps — velocity builds gradually
- This pattern is common in game UI for "companion" elements
- Can later be extended to react to Luna's emotional state (faster float when excited, etc.)
