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

**1. Engine Status**
- Actor roster: Director, Scribe (Ben), Librarian (Dude), Scout, Identity — each with status dot (green/amber/red)
- Model info: name, temperature, max tokens
- Consciousness metrics: lock-in score, total nodes, total entities
- **Data source:** `GET /api/status` or new `/api/engine/status`

**2. Voice Blend**
- TTS state: Piper (Amy voice), status
- STT state: Whisper or Web Speech API, status
- Blend params: warmth (0-1), pace (multiplier), breath (0-1)
- Last utterance preview with latency
- **Data source:** voice pipeline state

**3. Memory Monitor**
- Recent extractions: last 5 scribed items with type badges (DECISION, FACT, ACTION, PROBLEM)
- Graph health: total nodes, edges, entities
- Lock-in distribution bar (quintile breakdown)
- **Data source:** `observatory_stats()` MCP tool, Shared Turn Cache

**4. QA Assertions**
- Latest inference results: N assertions, pass/fail counts
- Failure detail cards with diagnosis
- Alert badge on widget icon when failures exist
- **Data source:** `qa_get_last_report()` MCP tool

**5. Prompt Inspector**
- Token composition breakdown: system prompt, memory context, conversation history, user message
- Total tokens, percentage bars
- **Data source:** new endpoint or prompt assembler diagnostic

**6. Context Debug**
- Last retrieval query details: search method (hybrid/FTS5/vector), nodes retrieved, latency
- Keyword tags from query
- **Data source:** `observatory_replay()` MCP tool

**7. Voight-Kampff**
- Last run summary: pass/fail count, suite name
- Probe results: warmth, memory grounding, boundary holding, humor timing, identity stability — each with pass/fail indicator
- **Data source:** `vk_run()` results

**8. Shared Turn Cache**
- Current YAML snapshot rendered: turn_id, source, session_id, flow state, expression hints, scribed counts
- TTL countdown / staleness indicator
- **Data source:** `data/cache/shared_turn.yaml` (read directly or via API)

**9. Thought Stream**
- Active reasoning/retrieval/planning nodes
- Real-time feed of Luna's internal process
- **Data source:** WebSocket stream or new thought broadcast channel

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

This prevents the input bar from scrolling away.

### WebSocket Connection

Connect to Luna Engine's existing WebSocket at `ws://localhost:8000/ws`:

```javascript
const ws = new WebSocket('ws://localhost:8000/ws');
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'chat_response') appendMessage('assistant', data.content);
  if (data.type === 'expression_update') updateOrb(data);
  // ... other message types
};
```

### Message Rendering

Each message block:
- **User messages:** right-aligned, subtle background
- **Luna messages:** left-aligned, glass card treatment
- **Knowledge bars:** horizontal line cutting across the message, styled with gradient. Only appears on messages where Scribe extracted something.

### Chat Input Bar

Fixed at bottom of spine. Three elements:

1. **Mic button** (🎤) — toggles voice mode (see Phase 5)
2. **Text input** — placeholder "talk to luna...", glass background
3. **Send button** (→) — purple accent with glow on hover

```javascript
async function sendMessage(text) {
  appendMessage('user', text);
  ws.send(JSON.stringify({ type: 'chat', content: text, source: 'eclissi' }));
}
```

---

## PHASE 4: T-SHAPE KNOWLEDGE PANELS

### Knowledge Bars

Horizontal lines that extend from conversation messages where the Scribe extracted knowledge. Visual treatment:
- Subtle gradient line with accent glow
- Appears between the message content and the next message
- Hover: lines extend slightly with increased opacity
- Click: opens flanking T-panels

### T-Panels

Two panels that slide in from the edges of the spine:

**Left Panel (300px) — Knowledge Created:**
- Cards for each extraction: FACT, DECISION, INSIGHT, ACTION, MILESTONE
- Each card has: 3px left accent border (type-colored), content text, confidence score, lock-in score
- Glass card treatment matching widget cards

**Right Panel (300px) — Connected Context:**
- Entity cards: avatar placeholder + name + role/type
- Graph neighbors: related nodes with relationship labels
- "Depends on", "Enables", "Corroborates" relationship types

### Accent Colors by Type

```
FACT:      #7dd3fc (cyan)
DECISION:  #c084fc (purple)
INSIGHT:   #fbbf24 (amber)
ACTION:    #34d399 (emerald)
MILESTONE: #f59e0b (orange)
```

### Interaction

- Click knowledge bar → both panels slide in (0.5s cubic-bezier(0.16,1,0.3,1))
- Click again or back button → panels slide out
- T-panels and widget right panel are independent — T-panels overlay the spine area, widget panel is a separate grid column

### Data Source

Knowledge bar data comes from:
1. **Shared Turn Cache** — most recent turn's extractions
2. **Memory Matrix** — historical extractions linked to conversation turns via `luna_smart_fetch()` or `memory_matrix_search()`
3. **WebSocket events** — real-time extraction notifications from Scribe

---

## PHASE 5: VOICE MODE

### Mic Button Toggle

Click mic → voice mode bar appears above input. Contains:
- Animated waveform (5 rings pulsing at different heights/delays)
- "LISTENING" label
- Piper TTS status indicator
- Close button

```css
@keyframes waveform { 0%,100% { height: 6px } 50% { height: var(--h) } }
/* 5 rings with staggered delays: 0s, 0.15s, 0.3s, 0.1s, 0.25s */
```

Mic button gets purple background + pulse animation when active:
```css
@keyframes micPulse {
  0%,100% { box-shadow: 0 0 0 0 rgba(192,132,252,0.4) }
  50% { box-shadow: 0 0 0 8px rgba(192,132,252,0) }
}
```

### STT Implementation

Use browser Web Speech API (zero infrastructure):
```javascript
const recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
recognition.continuous = true;
recognition.interimResults = true;
recognition.onresult = (event) => {
  const transcript = event.results[event.results.length - 1][0].transcript;
  if (event.results[event.results.length - 1].isFinal) {
    sendMessage(transcript);
  }
};
```

### TTS Implementation

Server-side Piper TTS via Luna Engine:
```javascript
async function speakResponse(text) {
  const response = await fetch('/api/tts', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, voice: 'amy' })
  });
  const audio = new Audio(URL.createObjectURL(await response.blob()));
  audio.play();
}
```

**Reference:** Guardian HANDOFF-05 voice integration spec.

---

## PHASE 6: WIRE LIVE DATA

Replace the static content in widgets with live API calls:

| Widget | Endpoint / Source | Refresh |
|--------|-------------------|---------|
| Engine Status | `GET /api/status` | 5s poll |
| Voice Blend | Voice pipeline state via WS | Real-time |
| Memory Monitor | `observatory_stats()` | 10s poll |
| QA Assertions | `qa_get_last_report()` | On inference |
| Prompt Inspector | New: `GET /api/prompt/composition` | On message |
| Context Debug | `observatory_replay(query)` | On message |
| Voight-Kampff | `vk_run()` results cache | Manual trigger |
| Shared Turn Cache | Read `data/cache/shared_turn.yaml` | On update |
| Thought Stream | WebSocket thought channel | Real-time |

For MCP tools that don't have HTTP equivalents, add thin FastAPI routes that call the same underlying functions:

```python
# src/luna/api/routes/diagnostics.py
@router.get("/api/diagnostics/memory")
async def memory_stats():
    return await observatory_stats()

@router.get("/api/diagnostics/qa")
async def qa_report():
    return await qa_get_last_report()
```

---

## DESIGN SYSTEM

### Palette

```css
:root {
  /* Backgrounds */
  --bg: #0c0c14;
  --bg-raised: #111119;
  --bg-panel: #15151f;
  --bg-widget: #1a1a26;

  /* Borders */
  --border: rgba(255,255,255,0.06);
  --border-active: rgba(192,132,252,0.3);
  --border-hover: rgba(255,255,255,0.1);

  /* Text */
  --text: #e8e8f0;
  --text-soft: #9a9ab0;
  --text-faint: #5a5a70;
  --text-muted: #3a3a50;

  /* Accents */
  --accent-luna: #c084fc;
  --accent-memory: #7dd3fc;
  --accent-voice: #a78bfa;
  --accent-qa: #f87171;
  --accent-debug: #fbbf24;
  --accent-prompt: #34d399;
  --accent-vk: #fb923c;
  --accent-guardian: #e09f3e;
}
```

### Typography

| Role | Font | Weight | Use |
|------|------|--------|-----|
| Display | Fraunces (serif) | 300-600 | Titles, brand |
| Body | DM Sans (sans-serif) | 300-500 | Content, messages |
| Labels | Bebas Neue (sans-serif) | 400 | Nav, section headers, uppercase labels |
| Mono | JetBrains Mono | 300-500 | Code, metrics, IDs |

### Glass Material Recipe

**Parent panels** (right panel, T-panels):
```css
backdrop-filter: blur(20px) saturate(1.4) brightness(1.05);
border: 1px solid rgba(255,255,255,0.06);
box-shadow: -4px 0 30px rgba(0,0,0,0.3);
```

**Child cards** (widget cards, knowledge cards):
```css
backdrop-filter: blur(12px) saturate(1.2);
border: 1px solid rgba(255,255,255,0.06);
box-shadow: 0 4px 12px rgba(0,0,0,0.3), 0 1px 3px rgba(0,0,0,0.2);
/* Hover: translateY(-1px) + deeper shadow */
```

**Interactive elements** (stat boxes, buttons):
```css
backdrop-filter: blur(8px);
border: 1px solid var(--border);
box-shadow: 0 2px 8px rgba(0,0,0,0.25);
```

### Animations

| Element | Duration | Easing |
|---------|----------|--------|
| Panel slides | 0.5s | `cubic-bezier(0.16, 1, 0.3, 1)` |
| Grid column change | 0.4s | same |
| Fade-ups | 0.35s | `ease` |
| Mic pulse | 1.5s infinite | ease-in-out |
| Waveform rings | 1.2s staggered | ease-in-out |
| Card hover lift | 0.3s | ease |

---

## FILE MAP

| File | Action | Description |
|------|--------|-------------|
| `src/eclissi/shell.html` (or React equivalent) | CREATE | Main shell: header, grid, nav routing |
| `src/eclissi/components/widget-dock.{js,jsx}` | CREATE | Left rail with 9 icons |
| `src/eclissi/components/right-panel.{js,jsx}` | CREATE | Collapsible widget content panel |
| `src/eclissi/components/widgets/*.{js,jsx}` | CREATE | 9 widget content components |
| `src/eclissi/components/conversation-spine.{js,jsx}` | CREATE | Chat UI with WebSocket |
| `src/eclissi/components/t-shape-panels.{js,jsx}` | CREATE | Knowledge flanking panels |
| `src/eclissi/components/chat-input.{js,jsx}` | CREATE | Input bar with mic + send |
| `src/eclissi/components/voice-mode.{js,jsx}` | CREATE | Voice bar with waveform |
| `src/eclissi/styles/design-system.css` | CREATE | CSS variables, glass mixins, animations |
| `src/luna/api/routes/diagnostics.py` | CREATE | Thin HTTP wrappers for widget data |
| `t_shape_eclissi_v3.html` | REFERENCE | Full prototype — source of truth for visual specs |

---

## VERIFICATION

```bash
# 1. Shell loads with all 5 nav tabs
# Navigate to http://localhost:8000/eclissi → see header with tabs

# 2. Widget dock opens/closes right panel
# Click any widget icon → right panel slides in with that widget's content
# Click again → collapses

# 3. Chat works
# Type message → appears in spine → Luna responds via WebSocket
# Source field = "eclissi" in Shared Turn Cache

# 4. T-shape panels work
# Messages with knowledge bars → click bar → flanking panels open
# Knowledge cards show correct type colors and content

# 5. Voice mode works
# Click mic → "LISTENING" bar appears with waveform
# Speak → transcript sent as message
# Luna response → TTS audio plays

# 6. Widgets show live data
# Engine Status → matches /api/status
# Memory Monitor → matches observatory_stats()
# QA → shows real assertion results

# 7. Glass treatment renders correctly
# All panels and cards have blur/saturation
# Hover states lift cards with deeper shadow
# No opaque backgrounds — everything is transparent glass

# 8. Input bar stays fixed
# Scroll long conversation → input bar stays at bottom
# Voice bar and studio drawer stack upward from fixed position
```

---

## NON-NEGOTIABLES

1. **Glass, not opaque** — every panel and card uses `backdrop-filter`. No solid backgrounds on floating elements.
2. **Fixed input bar** — never scrolls away. Flex column with scrollable inner wrapper.
3. **Independent systems** — widget dock, T-shape, and chat input operate without interfering.
4. **Source tagging** — all messages sent from Eclissi include `source: "eclissi"`.
5. **Offline-first** — UI degrades gracefully if WebSocket disconnects. Show connection status.
6. **Existing endpoints** — don't duplicate backend logic. Use existing MCP tool functions via thin HTTP wrappers.
7. **Design system enforced** — use CSS variables, not hardcoded colors. All fonts from the specified families.
8. **Prototype is truth** — when in doubt about visual treatment, refer to `t_shape_eclissi_v3.html`.

---

## CONTEXT: WHY THIS ARCHITECTURE

The Eclissi Shell emerged from iterating on the fundamental question: how do you show what an AI *knows* alongside what it *says*? The T-shape pattern is the answer — conversation flows vertically (what Luna says), knowledge extends horizontally (what Luna learned). The widget dock provides engineering-level diagnostics without cluttering the conversation.

The five-tab nav (Eclissi, Studio, Kozmo, Guardian, Observatory) represents Luna's five faces: companion (Eclissi), creator (Studio/Kozmo), steward (Guardian), and inspector (Observatory). Same engine, different lenses.

The glass design language is intentional — transparency as a visual metaphor for inspectability. You can see through everything. No black boxes. Sovereignty means you can look under the hood.
