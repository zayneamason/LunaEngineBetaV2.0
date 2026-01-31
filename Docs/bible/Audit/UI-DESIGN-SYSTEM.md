# Luna Hub UI Design System

**Version:** 2.0
**Framework:** React + Tailwind CSS
**Last Updated:** 2026-01-25

---

## Overview

The Luna Hub UI implements a **glass morphism** design language with dark mode aesthetics, gradient accents, and subtle animations. The visual language evokes a futuristic, consciousness-aware interface appropriate for an AI companion system.

---

## Color Palette

### Brand Colors (Custom Tailwind)

| Token | Hex | Usage |
|-------|-----|-------|
| `luna-violet` | `#8b5cf6` | Primary accent, consciousness states |
| `luna-cyan` | `#06b6d4` | Secondary accent, connection states |
| `luna-pink` | `#ec4899` | Tertiary accent, personality states |

### Background Colors

| Token | Hex | Usage |
|-------|-----|-------|
| `slate-950` | `#0f172a` | Main background (via index.css `body`) |
| `slate-900` | `#0f172a` | Panel backgrounds with opacity |
| `white/5` | `rgba(255,255,255,0.05)` | Glass card base |
| `white/8` | `rgba(255,255,255,0.08)` | Glass card hover |
| `white/10` | `rgba(255,255,255,0.10)` | Borders, dividers |
| `black/20` | `rgba(0,0,0,0.20)` | Code block backgrounds |
| `black/60` | `rgba(0,0,0,0.60)` | Modal overlay |

### Status Colors

| Status | Color Token | Hex | Glow Shadow |
|--------|-------------|-----|-------------|
| Active/Connected/Running | `emerald-400` | `#34d399` | `shadow-emerald-400/50` |
| Loading/Syncing | `blue-400` | `#60a5fa` | `shadow-blue-400/50` |
| Disconnected/Warning | `amber-400` | `#fbbf24` | `shadow-amber-400/50` |
| Error | `red-400` | `#f87171` | `shadow-red-400/50` |
| Neutral | `gray-400` | `#9ca3af` | `shadow-gray-400/50` |

### Mood/Personality Status Colors

| Mood | Color Token | Hex |
|------|-------------|-----|
| Curious | `violet-400` | `#a78bfa` |
| Focused | `cyan-400` | `#22d3ee` |
| Playful | `pink-400` | `#f472b6` |
| Thoughtful | `indigo-400` | `#818cf8` |

### Ring/Context Hierarchy Colors

| Ring | Border | Background | Text |
|------|--------|------------|------|
| CORE | `yellow-500` | `yellow-500/10` | `yellow-400` |
| INNER | `red-500` | `red-500/10` | `red-400` |
| MIDDLE | `orange-500` | `orange-500/10` | `orange-400` |
| OUTER | `gray-500` | `gray-500/10` | `gray-400` |

### Debug Mode Colors

| Element | Border | Background |
|---------|--------|------------|
| Debug keyword | - | `cyan-500/30` with `cyan-200` text |
| Debug context box | `red-500` 2px | `red-500/10` |
| Ring Core debug | `yellow-500` | `yellow-500/10` |
| Ring Inner debug | `red-500` | `red-500/10` |
| Ring Middle debug | `orange-500` | `orange-500/10` |
| Ring Outer debug | `gray-500` | `gray-500/10` |

---

## Typography

### Font Stack

```css
font-family: system-ui, -apple-system, sans-serif;
```

### Type Scale

| Class | Size | Weight | Usage |
|-------|------|--------|-------|
| `text-3xl` | 1.875rem | `font-light` | Page titles (LUNA HUB) |
| `text-2xl` | 1.5rem | `font-light` | Large statistics |
| `text-lg` | 1.125rem | `font-light` | Section headers |
| `text-sm` | 0.875rem | - | Body text, labels |
| `text-xs` | 0.75rem | - | Metadata, timestamps |
| `text-[10px]` | 10px | - | Micro labels, stats |
| `text-[9px]` | 9px | - | Token counts |

### Text Opacity Scale

| Opacity | Usage |
|---------|-------|
| `text-white/90` | Primary text, headings |
| `text-white/80` | Body text, messages |
| `text-white/70` | Secondary text |
| `text-white/60` | Muted text |
| `text-white/50` | Tertiary/helper text |
| `text-white/40` | Labels, metadata |
| `text-white/30` | Hints, placeholders |

### Special Typography

| Style | Classes | Usage |
|-------|---------|-------|
| Uppercase labels | `uppercase tracking-widest text-xs text-white/40` | Section labels |
| Monospace | `font-mono` | Code, timestamps, debug info |
| Tracking wide | `tracking-wide` | Headers, titles |

---

## Spacing Scale

Uses Tailwind's default spacing scale.

### Common Patterns

| Pattern | Classes | Pixel Value |
|---------|---------|-------------|
| Panel padding | `p-4` or `p-6` | 16px or 24px |
| Header padding | `px-6 py-4` | 24px x 16px |
| Compact padding | `p-3` | 12px |
| Micro padding | `p-2` | 8px |
| Element gap | `gap-2` | 8px |
| Section gap | `gap-4` | 16px |
| Large gap | `gap-6` | 24px |
| Panel margin | `mb-6` | 24px |
| Main grid gap | `gap-6` | 24px |

### Grid Layout

```jsx
// Main application grid
<div className="grid grid-cols-12 gap-6 h-[calc(100vh-180px)]">
  <div className="col-span-7">...</div>  // Chat panel
  <div className="col-span-5">...</div>  // Status panels
</div>
```

---

## Border Radius Patterns

| Size | Class | Pixel Value | Usage |
|------|-------|-------------|-------|
| Small | `rounded` | 4px | Inline elements |
| Medium | `rounded-lg` | 8px | Buttons, tags, inputs |
| Large | `rounded-xl` | 12px | Cards, stat boxes |
| Extra Large | `rounded-2xl` | 16px | GlassCard, chat bubbles |
| Full | `rounded-full` | 50% | Status dots, avatars, orbs |

---

## Shadow Patterns

### Glow Shadows (Status Dots)

```css
shadow-lg shadow-emerald-400/50  /* Active state */
shadow-lg shadow-amber-400/50    /* Warning state */
shadow-lg shadow-red-400/50      /* Error state */
shadow-lg shadow-violet-400/50   /* Curious/processing */
shadow-lg shadow-cyan-400/50     /* Focused state */
```

### Panel Shadows

```css
shadow-2xl  /* Slide-out panels (TuningPanel) */
shadow-lg shadow-violet-500/50  /* Active mic button */
```

---

## Glass Morphism Implementation

### GlassCard Component

```jsx
// Core glass morphism classes
const baseClasses = 'backdrop-blur-xl bg-white/5 rounded-2xl transition-all duration-300';
const borderClasses = dashed
  ? 'border border-dashed border-white/20'
  : 'border border-white/10';
const hoverClasses = onClick && hover
  ? 'cursor-pointer hover:bg-white/[0.08] hover:border-white/20'
  : '';
```

### Global Glass Utility (index.css)

```css
.glass {
  backdrop-filter: blur(20px);
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.glass:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.2);
}
```

### Common Glass Patterns

| Pattern | Classes |
|---------|---------|
| Glass card base | `backdrop-blur-xl bg-white/5 border border-white/10 rounded-2xl` |
| Glass input | `bg-white/5 border border-white/10 rounded-xl` |
| Glass button | `bg-white/5 border-white/10 hover:border-white/20` |
| Nested glass | `bg-white/5 rounded-xl` (within GlassCard) |
| Modal overlay | `bg-black/60 backdrop-blur-sm` |

---

## Animation Patterns

### Custom Tailwind Animations

```javascript
// tailwind.config.js
animation: {
  'pulse-slow': 'pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite',
  'breathe': 'breathe 4s ease-in-out infinite',
},
keyframes: {
  breathe: {
    '0%, 100%': { transform: 'scale(1)' },
    '50%': { transform: 'scale(1.05)' },
  }
}
```

### CSS Keyframe Animations (index.css)

```css
@keyframes keyword-pulse {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(6, 182, 212, 0.4);
  }
  50% {
    box-shadow: 0 0 0 4px rgba(6, 182, 212, 0);
  }
}
```

### Animation Usage Patterns

| Animation | Classes | Usage |
|-----------|---------|-------|
| Loading pulse | `animate-pulse` | Status dots, loading states |
| Slow pulse | `animate-pulse-slow` | Background orbs |
| Spin | `animate-spin` | Processing spinner |
| Ping | `animate-ping` | Voice status ring |
| Staggered pulse | `animationDelay: '0.2s'` | Loading dots sequence |

### Transition Patterns

| Pattern | Classes |
|---------|---------|
| Default transitions | `transition-all duration-300` |
| Color transitions | `transition-colors` |
| Quick feedback | `duration-150` |
| Progress bars | `transition-all duration-500` |

---

## Component Patterns

### Header Pattern

```jsx
<div className="px-6 py-4 border-b border-white/10">
  <div className="flex items-center justify-between">
    <div className="flex items-center gap-3">
      <div className="w-1 h-6 bg-gradient-to-b from-violet-400 to-cyan-400 rounded-full" />
      <h2 className="text-lg font-light tracking-wide text-white/90">Title</h2>
    </div>
    <span className="text-xs text-white/30">metadata</span>
  </div>
</div>
```

### Accent Bar (Header Indicator)

| Gradient | Usage |
|----------|-------|
| `from-violet-400 to-cyan-400` | Chat panel, general |
| `from-pink-400 to-violet-400` | Consciousness |
| `from-emerald-400 to-cyan-400` | Engine status |
| `from-red-500 to-orange-500` | Debug panel |

### Stat Box Pattern

```jsx
<div className="bg-white/5 rounded-xl p-3 text-center">
  <div className="text-xs text-white/40 mb-1">Label</div>
  <div className="text-lg font-light text-white/90">Value</div>
</div>
```

### Progress Bar Pattern

```jsx
<div className="h-2 bg-white/10 rounded-full overflow-hidden">
  <div
    className="h-full bg-gradient-to-r from-violet-400 to-cyan-400 rounded-full transition-all duration-500"
    style={{ width: `${percentage}%` }}
  />
</div>
```

### Tag/Badge Pattern

```jsx
<div className="flex items-center gap-2 bg-white/5 border border-white/10 rounded-lg px-3 py-1.5">
  <StatusDot status="active" size="w-1.5 h-1.5" />
  <span className="text-xs text-white/60">Label</span>
</div>
```

### Button Patterns

**Primary Button (Gradient):**
```jsx
<button className="w-full py-3 text-sm font-medium rounded-lg bg-gradient-to-r from-amber-500 to-orange-600 text-white hover:from-amber-400 hover:to-orange-500 transition-all">
```

**Secondary Button (Ghost):**
```jsx
<button className="px-3 py-1 text-xs rounded-lg border bg-white/5 border-white/10 text-white/40 hover:border-white/20 hover:text-white/60">
```

**Toggle Button (Active/Inactive):**
```jsx
<button className={`px-3 py-1.5 text-xs rounded-lg border transition-all ${
  active
    ? 'bg-violet-500/20 border-violet-500/50 text-violet-400'
    : 'bg-white/5 border-white/10 text-white/40 hover:border-white/20'
}`}>
```

**Action Button with Color State:**
```jsx
<button className="py-2 text-sm rounded-lg bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 hover:bg-cyan-500/30 transition-colors">
```

### Input Pattern

```jsx
<input className="flex-1 bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white/90 placeholder-white/30 focus:outline-none focus:border-violet-400/50 transition-all disabled:opacity-50" />
```

### Chat Bubble Patterns

**User Message:**
```jsx
<div className="bg-gradient-to-r from-violet-500/20 to-cyan-500/20 border border-violet-400/30 text-white/90 rounded-2xl px-4 py-3">
```

**Assistant Message:**
```jsx
<div className="bg-white/5 border border-white/10 text-white/80 rounded-2xl px-4 py-3">
```

---

## Gradient Orb Component

The `GradientOrb` component creates ambient background effects:

```jsx
<div
  className="absolute rounded-full blur-3xl opacity-20 animate-pulse-slow pointer-events-none"
  style={{
    background: `radial-gradient(circle, ${color1} 0%, ${color2} 50%, transparent 70%)`,
    animationDelay: `${delay}s`,
  }}
/>
```

### Orb Configurations

| Position | Size | Color1 | Color2 |
|----------|------|--------|--------|
| Top-left | 600x600 | `#8b5cf6` | `#3b82f6` |
| Right-center | 500x500 | `#06b6d4` | `#8b5cf6` |
| Bottom-left | 400x400 | `#ec4899` | `#8b5cf6` |

---

## Scrollbar Styling

```css
::-webkit-scrollbar {
  width: 6px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.2);
}
```

---

## Responsive Breakpoints

Uses Tailwind defaults. Main layout uses `grid-cols-12` with `col-span-7` / `col-span-5` split for desktop.

---

## Utility Classes

### Line Clamp (Text Truncation)

```css
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.line-clamp-3 {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
```

### Slider Styling

```jsx
<input
  type="range"
  className="flex-1 h-2 bg-white/10 rounded-lg appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-amber-400"
/>
```

---

## Icon/Emoji Usage

The UI uses emoji for quick visual recognition:

| Context | Emoji |
|---------|-------|
| Delegated response | lightning |
| Local response | bullet |
| Cloud fallback | cloud |
| Identity source | DNA |
| Conversation source | speech |
| Memory source | brain |
| Tool source | wrench |
| Task source | clipboard |
| Scribe source | pencil |
| Librarian source | books |

---

## Z-Index Layers

| Layer | z-index | Usage |
|-------|---------|-------|
| Background orbs | - | `pointer-events-none` |
| Main content | `relative` | Default stacking |
| Slide panels | `z-50` | TuningPanel |
| Modals | `z-50` | ContextDebugPanel |
| Fixed footer | - | Natural stacking |

---

## File Reference

| File | Purpose |
|------|---------|
| `/frontend/tailwind.config.js` | Custom colors, animations |
| `/frontend/src/index.css` | Global styles, glass utilities |
| `/frontend/src/components/GlassCard.jsx` | Core glass component |
| `/frontend/src/components/GradientOrb.jsx` | Background orbs |
| `/frontend/src/components/StatusDot.jsx` | Status indicators |
| `/frontend/src/App.jsx` | Layout structure |
