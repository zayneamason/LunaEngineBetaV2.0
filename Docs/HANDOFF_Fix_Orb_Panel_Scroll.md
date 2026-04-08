# HANDOFF: Fix Orb, Grid, and T-Panels Scrolling Away

## Problem

On the Eclissi home chat page, the Luna Orb, its 2D navigation grid (GridLayer/GridDebug), the ApertureDial, and the T-Shape Knowledge Panels (TPanels) all scroll up with the conversation messages and disappear off-screen. These elements should remain fixed/pinned in the visible viewport while only the messages scroll underneath.

## Root Cause

In `ChatPanel.jsx`, everything lives inside a single `<div>` that has `overflow-y-auto`. This div is the scroll container. The Orb, Grid, ApertureDial, and TPanels are all children of this scrolling div. Even though they use `position: absolute`, that resolves against the **scroll content** — so they move with the messages.

Additionally, `useOrbFollow.js` calculates the orb's Y target from `messagesEndRef.getBoundingClientRect()`, which changes as the user scrolls — making the orb actively chase the bottom of the message list rather than staying fixed in the viewport.

### Current Structure (Broken)

```
GlassCard (flex col, h-full)
├── Header (flex-shrink-0)
├── GridProvider containerRef={chatContainerRef}
│   └── ScrollDiv (ref=chatContainerRef, overflow-y-auto, position: relative) ← EVERYTHING IN HERE
│       ├── GridLayer (position: absolute, inset: 0)        ← scrolls away
│       ├── GridDebug                                        ← scrolls away
│       ├── OrbCanvas (position: absolute, z-index: 100)    ← scrolls away
│       ├── ApertureDial (position: fixed)                   ← OK (viewport-relative)
│       ├── Messages...                                      ← scrolls (correct)
│       ├── messagesEndRef                                   ← scrolls (correct)
│       └── TPanels (position: absolute)                     ← scrolls away
└── Input form (flex-shrink-0)
```

## Solution: Two-Layer Architecture

Split the single scroll div into a **fixed wrapper** and an **inner scroll div**. The wrapper holds all pinned elements. The scroll div only holds messages.

### Target Structure (Fixed)

```
GlassCard (flex col, h-full)
├── Header (flex-shrink-0)
├── GridProvider containerRef={gridContainerRef}
│   └── FixedWrapper (ref=gridContainerRef, position: relative, flex: 1, minHeight: 0)
│       ├── GridLayer (position: absolute, inset: 0)        ← pinned to wrapper
│       ├── GridDebug                                        ← pinned to wrapper
│       ├── ScrollDiv (ref=chatContainerRef, overflow-y-auto, height: 100%)
│       │   ├── Messages...                                  ← scrolls (correct)
│       │   └── messagesEndRef                               ← scrolls (correct)
│       ├── OrbCanvas (position: absolute, z-index: 100)    ← pinned to wrapper
│       ├── ApertureDial (position: fixed)                   ← unchanged (viewport)
│       └── TPanels (position: absolute)                     ← pinned to wrapper
└── Input form (flex-shrink-0)
```

## Files to Edit

### 1. `frontend/src/components/ChatPanel.jsx`

**A) Add `gridContainerRef`:**

```js
// FIND:
const chatContainerRef = useRef(null);
const messagesEndRef = useRef(null);

// REPLACE WITH:
const chatContainerRef = useRef(null);
const gridContainerRef = useRef(null);
const messagesEndRef = useRef(null);
```

**B) Restructure the layout — add wrapper div, separate scroll from overlays:**

Replace this block:

```jsx
{/* Messages container with floating orb + grid */}
<GridProvider containerRef={chatContainerRef}>
<div ref={mergeScrollRefs} onScroll={handleWindowScroll} className="flex-1 min-h-0 overflow-y-auto p-4 space-y-4 relative">
  {/* Grid debug overlay (toggle with backtick key) */}
  <GridLayer />
  <GridDebug />

  {/* Luna Orb — Canvas 2D ring renderer with spring physics */}
  <OrbCanvas
    ref={orbCanvasRef}
    state={animationOverride || (!isConnected ? 'disconnected' : (isLoading ? 'processing' : orbState.animation))}
    colorOverride={!isConnected ? null : orbState.color}
    brightness={!isConnected ? 0.7 : orbState.brightness}
    size={56}
    chatContainerRef={chatContainerRef}
    messagesEndRef={messagesEndRef}
    rendererState={orbState.renderer}
  />

  {/* Aperture dial — spawns from the floating orb position */}
  <ApertureDial
    angle={apertureAngle}
    onChange={handleApertureChange}
    visible={apertureVisible}
    orbCenter={orbCenter}
  />

  {messages.length === 0 ? (
```

With this:

```jsx
{/* Messages container with floating orb + grid */}
<GridProvider containerRef={gridContainerRef}>
<div ref={gridContainerRef} style={{ position: 'relative', flex: 1, minHeight: 0 }}>
  {/* Grid canvas — spatial index for orb navigation (fixed layer) */}
  <GridLayer />
  <GridDebug />

  {/* Scrollable message list */}
  <div ref={mergeScrollRefs} onScroll={handleWindowScroll} className="overflow-y-auto p-4 space-y-4" style={{ height: '100%' }}>

  {messages.length === 0 ? (
```

And replace the bottom section:

```jsx
    <div ref={messagesEndRef} />

    {/* T-Shape Knowledge Panels overlay */}
    {activeTPanel !== null && (
      <TPanels
        extractions={extractions}
        entities={extractionEntities}
        relationships={extractionRelationships}
        onClose={() => setActiveTPanel(null)}
      />
    )}
  </div>
  </GridProvider>
```

With this:

```jsx
    <div ref={messagesEndRef} />
  </div>
  {/* END scroll div */}

  {/* Fixed overlay layer — orb, aperture, and T-panels stay pinned to wrapper */}
  <OrbCanvas
    ref={orbCanvasRef}
    state={animationOverride || (!isConnected ? 'disconnected' : (isLoading ? 'processing' : orbState.animation))}
    colorOverride={!isConnected ? null : orbState.color}
    brightness={!isConnected ? 0.7 : orbState.brightness}
    size={56}
    chatContainerRef={gridContainerRef}
    messagesEndRef={messagesEndRef}
    rendererState={orbState.renderer}
  />

  <ApertureDial
    angle={apertureAngle}
    onChange={handleApertureChange}
    visible={apertureVisible}
    orbCenter={orbCenter}
  />

  {activeTPanel !== null && (
    <TPanels
      extractions={extractions}
      entities={extractionEntities}
      relationships={extractionRelationships}
      onClose={() => setActiveTPanel(null)}
    />
  )}
</div>
</GridProvider>
```

Key details:
- `GridProvider containerRef` → `gridContainerRef` (the fixed wrapper, not the scroll div)
- `OrbCanvas chatContainerRef` → `gridContainerRef` (orb navigates the fixed grid space)
- `chatContainerRef` stays on the scroll div via `mergeScrollRefs` (scroll events + windowed messages still work)
- **Do NOT set `overflow: hidden` on the wrapper div** — the orb's canvas extends beyond its position (negative margins for glow) and `overflow: hidden` clips it, creating an invisible cutoff line. The scroll div handles its own overflow.

### 2. `frontend/src/hooks/useOrbFollow.js`

The orb's Y-target currently chases `messagesEndRef`, which moves with scroll content. Change it to pin to the visible container bounds.

**Replace the `updateTarget` function:**

```js
// FIND:
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

// REPLACE WITH:
// Calculate target position — fixed within visible container bounds
const updateTarget = useCallback(() => {
  if (!chatContainerRef.current) return;

  const container = chatContainerRef.current;
  const containerRect = container.getBoundingClientRect();

  // X: Right side of container with margin
  const orbWidth = 56; // Match the size prop in ChatPanel
  const targetX = containerRect.width - marginFromEdge - orbWidth;

  // Y: Pin to bottom portion of visible container (not scroll content)
  // chatContainerRef now points to gridContainerRef (the fixed wrapper),
  // so containerRect.height is the viewport height, not scroll content height
  const targetY = containerRect.height - maxYFromBottom + verticalOffset;

  // Apply constraints
  const clampedY = Math.max(minY, Math.min(containerRect.height - maxYFromBottom, targetY));

  targetRef.current = { x: targetX, y: clampedY };
}, [chatContainerRef, marginFromEdge, verticalOffset, minY, maxYFromBottom]);
```

Note: `messagesEndRef` is removed from the dependency array since it's no longer used for targeting. The orb still receives it as a prop but ignores it for positioning. The fairy float (sine-wave drift) and spring physics continue to give the orb organic movement.

## Ref Routing Summary

| Ref | Points To | Used By |
|-----|-----------|---------|
| `gridContainerRef` | Fixed wrapper div | GridProvider, OrbCanvas.chatContainerRef, useOrbFollow target calculations |
| `chatContainerRef` | Inner scroll div (via mergeScrollRefs) | useWindowedMessages (scroll events), auto-scroll logic |
| `messagesEndRef` | Bottom of message list (inside scroll div) | Auto-scroll detection, passed to OrbCanvas but not used for positioning |

## Z-Index Stacking

| Layer | z-index | Position | Notes |
|-------|---------|----------|-------|
| GridLayer canvas | 5 | absolute, inset: 0 | Fills wrapper, under everything |
| TPanels backdrop | 10 | absolute | Click-to-dismiss |
| TPanels left/right | 11 | absolute | Knowledge panels |
| OrbCanvas | 100 | absolute | Topmost in chat area |
| ApertureDial | 100 | fixed | Viewport-level, unaffected by this change |

## Verification

After applying changes:
1. Hard reload (`Cmd+Shift+R`)
2. Send enough messages to trigger scrolling
3. Scroll up — orb should stay pinned near bottom-right, not follow messages
4. Toggle grid debug (backtick key) — grid should fill the visible area, not extend into scroll content
5. Trigger T-panels via KnowledgeBar — panels should overlay from edges, not scroll away
6. Mouse near orb — ApertureDial should still appear (already viewport-fixed, unaffected)
7. Check windowed message rendering still works (scroll up for older messages)

## Do NOT

- Set `overflow: hidden` on the wrapper div (clips the orb's glow canvas)
- Move `chatContainerRef` off the scroll div (breaks windowed message scroll events)
- Remove `messagesEndRef` from OrbCanvas props (may be used by other orb behaviors)
- Change the GridProvider/GridContext internals — only the `containerRef` routing changes
