# HANDOFF: Eclissi Shell — Unified Surface Architecture

**Date:** 2026-03-01  
**Author:** Ahab (via Claude facilitator session)  
**For:** Claude Code  
**Priority:** HIGH — defines the primary user-facing surface for Luna Engine  
**Depends on:** Luna Engine API (`src/luna/api/server.py`), WebSocket broadcast, Shared Turn Cache, Guardian service, Kozmo service, Observatory MCP tools

---

## EXECUTIVE SUMMARY

Build the **Eclissi Shell** — a single-page web application that serves as Luna's primary desktop interface. Five tabbed views (Eclissi, Studio, Kozmo, Guardian, Observatory) share a common header, widget dock, and glass panel design language. The conversation spine uses a "T-shape" pattern where knowledge bars extend horizontally from messages, opening flanking panels that show what Luna learned and who/what it connects to.

**Reference prototype:** `t_shape_eclissi_v3.html` (615 lines, standalone HTML) — contains the full design system, all 9 diagnostic widgets, T-shape interaction patterns, voice mode controls, and glass material treatment. This is the source of truth for visual specifications.

**This is a frontend build.** The backend endpoints already exist or are covered by other handoffs. This handoff covers the Eclissi tab implementation only — other tabs (Studio, Kozmo, Guardian, Observatory) are separate views that share the shell chrome.

---

## ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────────┐
│  HEADER   [ ✦ ECLISSI ]  [ STUDIO  KOZMO  GUARDIAN  OBSERVATORY ] │
├──────┬──────────────────────────────────────────┬───────────────┤
│      │                                          │               │
│  W   │   CONVERSATION SPINE                     │  RIGHT PANEL  │
│  I   │   ┌─────────────────────┐                │  (widget      │
│  D   │   │ user message        │                │   content)    │
│  G   │   └─────────────────────┘                │               │
│  E   │   ┌─────────────────────┐                │  Engine Status│
│  T   │   │ luna response       │                │  Voice Blend  │
│      │   │ ══════ KNOWLEDGE BAR ════════        │  Memory Mon.  │
│  D   │   └─────────────────────┘                │  QA Assert.   │
│  O   │                                          │  Prompt Insp. │
│  C   │   T-PANELS (slide from spine edges):     │  Context Dbg  │
│  K   │   ┌──────┐         ┌──────┐              │  Voight-Kampff│
│      │   │LEFT  │         │RIGHT │              │  Turn Cache   │
│  9   │   │Knowl.│  spine  │Entity│              │  Thought Strm │
│  i   │   │cards │         │cards │              │               │
│  c   │   └──────┘         └──────┘              │               │
│  o   │                                          │               │
│  n   │   ┌──────────────────────────┐           │               │
│  s   │   │ 🎤  [talk to luna...]  → │           │               │
│      │   └──────────────────────────┘           │               │
└──────┴──────────────────────────────────────────┴───────────────┘
```

### Three Independent Systems

1. **Widget Dock** (left rail) → controls right panel content
2. **T-Shape Navigator** (center spine) → knowledge exploration from conversation
3. **Chat Input** (bottom anchored) → text + voice input

These operate independently. Grid layout keeps widget panel separate from T-shape panels. Input bar is fixed outside scroll area.

---

## BUILD ORDER

| Phase | What | Effort |
|-------|------|--------|
| 1 | Shell chrome: header, nav tabs, routing skeleton | Small |
| 2 | Widget dock + right panel (9 widgets) | Medium |
| 3 | Conversation spine with WebSocket connection | Medium |
| 4 | T-shape knowledge panels | Medium |
| 5 | Voice mode (STT/TTS controls) | Small |
| 6 | Wire widget data feeds to live endpoints | Medium |

---

## PHASE 1: SHELL CHROME

### Tech Stack

**Tauri + React (existing Eclissi app structure)**  
If building inside the existing `eclissi/` Tauri project, use React components. If building as a standalone web app served by the Luna Engine FastAPI, use vanilla HTML/JS or lightweight framework — match whatever the Guardian surface uses.

The prototype is vanilla HTML/CSS/JS. Adapt to whatever framework Eclissi already uses.

### Header

Fixed top bar, full width. Contains:

- **Brand:** `✦ ECLISSI` with accent bar (3px × 24px, `#c084fc`, glowing shadow)
- **Nav tabs:** `ECLISSI · STUDIO · KOZMO · GUARDIAN · OBSERVATORY`
  - Active tab: `background: rgba(192,132,252,0.08)`, border: `rgba(192,132,252,0.3)`, text: `#c084fc`
  - STUDIO tab gets `color: #a78bfa` (voice accent)
  - GUARDIAN tab gets `color: #e09f3e` (guardian accent)
  - Other tabs: standard faint text
- **Right side:** Identity badge (FaceID status dot + name), connection indicator

### Grid Layout

```css
.app {
  display: grid;
  grid-template-columns: 52px 1fr 320px;
  grid-template-rows: 48px 1fr;
  height: 100vh;
}
.app.right-collapsed {
  grid-template-columns: 52px 1fr 0px;
}
```

Header spans full width (`grid-column: 1 / -1`). Widget bar is column 1, spine is column 2, right panel is column 3.

### Routing

Tab clicks swap the center content area. For now, only Eclissi is implemented — other tabs show placeholder views. Guardian and Observatory already have their own prototype HTML that can be embedded later.

---

## PHASE 2: WIDGET DOCK + RIGHT PANEL

### Widget Bar (Left Rail, 52px wide)

9 clickable icons in a vertical column. Each icon is 36px × 36px with `border-radius: 6px`. Click toggles the right panel with that widget's content.

#### Icons and Accent Colors

| # | Icon | Widget | Accent |
|---|------|--------|--------|
| 1 | ⚡ | Engine Status | `#c084fc` (luna) |
| 2 | 🔊 | Voice Blend | `#a78bfa` (voice) |
| 3 | 🧠 | Memory Monitor | `#7dd3fc` (memory) |
| 4 | ✓ | QA Assertions | `#f87171` (qa) — has alert badge |
| 5 | — | *(divider)* | |
| 6 | 📜 | Prompt Inspector | `#34d399` (prompt) |
| 7 | 🔍 | Context Debug | `#fbbf24` (debug) |
| 8 | 🎭 | Voight-Kampff | `#fb923c` (vk) |
| 9 | — | *(divider)* | |
| 10 | 💾 | Shared Turn Cache | `#c084fc` (luna) |
| 11 | 💭 | Thought Stream | `#a78bfa` (voice) |

Section labels between groups: "DIAGNOSTICS", "INTERNALS" — `font-family: Bebas Neue, 7px, letter-spacing: 1.5px`.

### Right Panel (320px, collapsible)

Transparent glass panel with `backdrop-filter: blur(20px) saturate(1.4) brightness(1.05)`. Border-left shadow: `-4px 0 30px rgba(0,0,0,0.3)`.

Each widget has:
- **Header:** accent bar (3px × 14px) + title (Bebas Neue, 11px, 1.5px spacing) + close button
- **Body:** scrollable area with glass cards

### Widget Content Specs

All widget cards use this glass treatment:
```css
.w-card {
  background: transparent;
  backdrop-filter: blur(12px) saturate(1.2);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 10px;
  padding: 12px 14px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.3), 0 1px 3px rgba(0,0,0,0.2);
}
.w-card:hover {
  border-color: rgba(255,255,255,0.1);
  transform: translateY(-1px);
  box-shadow: 0 6px 18px rgba(0,0,0,0.4);
}
```

**1. Engine Status** — Actor roster with status dots, model info, consciousness metrics
**2. Voice Blend** — TTS/STT state, blend params, last utterance
**3. Memory Monitor** — Recent extractions, graph health, lock-in distribution
**4. QA Assertions** — Latest inference checks, failure diagnosis
**5. Prompt Inspector** — Token composition breakdown
**6. Context Debug** — Retrieval query details, method, latency
**7. Voight-Kampff** — Last run stats, probe results
**8. Shared Turn Cache** — Current YAML snapshot rendered
**9. Thought Stream** — Active reasoning/retrieval/planning nodes

### Interaction Pattern

- Click dock icon → right panel slides in (0.4s cubic-bezier), icon gets active state
- Click same icon again or close button → panel collapses
- Only one widget visible at a time

---

## PHASE 3: CONVERSATION SPINE

### Layout

Center column is a flex column:
- **Scrollable conversation area** (`flex: 1; overflow-y: auto`)
- **Fixed input bar** (`flex-shrink: 0`) — always anchored at bottom

### WebSocket Connection

Connect to Luna Engine's existing WebSocket at `ws://localhost:8000/ws`. All messages sent include `source: "eclissi"`.

### Chat Input Bar

Fixed at bottom of spine. Three elements:
1. **Mic button** (🎤) — toggles voice mode
2. **Text input** — placeholder "talk to luna..."
3. **Send button** (→) — purple accent with glow

---

## PHASE 4: T-SHAPE KNOWLEDGE PANELS

Knowledge bars extend horizontally from messages where Scribe extracted knowledge. Click opens flanking panels:

- **Left Panel (300px):** Knowledge cards — FACT (cyan), DECISION (purple), INSIGHT (amber), ACTION (emerald), MILESTONE (orange)
- **Right Panel (300px):** Connected entities and graph neighbors

T-panels and widget right panel are independent systems.

Data sources: Shared Turn Cache, Memory Matrix via `luna_smart_fetch()`, WebSocket extraction events.

---

## PHASE 5: VOICE MODE

- **STT:** Browser Web Speech API (zero infrastructure)
- **TTS:** Server-side Piper via `POST /api/tts`
- Voice mode bar with animated waveform, "LISTENING" label, mic pulse animation
- Reference: Guardian HANDOFF-05 voice integration spec

---

## PHASE 6: WIRE LIVE DATA

| Widget | Endpoint / Source | Refresh |
|--------|-------------------|---------|
| Engine Status | `GET /api/status` | 5s poll |
| Voice Blend | Voice pipeline state via WS | Real-time |
| Memory Monitor | `observatory_stats()` | 10s poll |
| QA Assertions | `qa_get_last_report()` | On inference |
| Prompt Inspector | `GET /api/prompt/composition` | On message |
| Context Debug | `observatory_replay(query)` | On message |
| Voight-Kampff | `vk_run()` results cache | Manual |
| Shared Turn Cache | `data/cache/shared_turn.yaml` | On update |
| Thought Stream | WebSocket thought channel | Real-time |

Add thin FastAPI routes at `src/luna/api/routes/diagnostics.py` wrapping existing MCP functions.

---

## DESIGN SYSTEM

### Palette
```
Backgrounds: #0c0c14, #111119, #15151f, #1a1a26
Accents: Luna #c084fc, Memory #7dd3fc, Voice #a78bfa, QA #f87171, Debug #fbbf24, Prompt #34d399, VK #fb923c, Guardian #e09f3e
Knowledge types: Fact #7dd3fc, Decision #c084fc, Insight #fbbf24, Action #34d399, Milestone #f59e0b
```

### Typography
Display: Fraunces (serif) | Body: DM Sans | Labels: Bebas Neue | Mono: JetBrains Mono

### Glass Material
Parent panels: `blur(20px) saturate(1.4) brightness(1.05)`
Child cards: `blur(12px) saturate(1.2)` + depth shadows
Interactive: `blur(8px)` + subtle shadows

---

## FILE MAP

| File | Action | Description |
|------|--------|-------------|
| Shell component | CREATE | Header, grid, nav routing |
| Widget dock component | CREATE | Left rail, 9 icons |
| Right panel component | CREATE | Collapsible widget content |
| 9 widget components | CREATE | Individual widget views |
| Conversation spine | CREATE | Chat UI + WebSocket |
| T-shape panels | CREATE | Knowledge flanking panels |
| Chat input | CREATE | Input bar + mic + send |
| Voice mode | CREATE | Voice bar + waveform |
| Design system CSS | CREATE | Variables, glass, animations |
| `src/luna/api/routes/diagnostics.py` | CREATE | HTTP wrappers for widget data |
| `t_shape_eclissi_v3.html` | REFERENCE | Visual source of truth |

---

## VERIFICATION

1. Shell loads with 5 nav tabs
2. Widget dock opens/closes right panel
3. Chat works via WebSocket with source="eclissi"
4. T-shape panels open on knowledge bar click
5. Voice mode: mic → listen → transcribe → send → TTS response
6. Widgets show live data from API endpoints
7. Glass treatment renders (blur/saturation on all panels)
8. Input bar stays fixed during scroll

---

## NON-NEGOTIABLES

1. **Glass, not opaque** — every panel uses `backdrop-filter`
2. **Fixed input bar** — never scrolls away
3. **Independent systems** — widget dock, T-shape, chat input don't interfere
4. **Source tagging** — all messages include `source: "eclissi"`
5. **Offline-first** — graceful WebSocket disconnect handling
6. **Existing endpoints** — thin HTTP wrappers, don't duplicate backend logic
7. **Design system enforced** — CSS variables, specified fonts
8. **Prototype is truth** — `t_shape_eclissi_v3.html` is the visual reference
