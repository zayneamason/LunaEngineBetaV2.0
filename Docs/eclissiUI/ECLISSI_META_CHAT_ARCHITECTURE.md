# Eclissi Meta Chat Architecture

> Option C + Guardian Luna — the enriched live chat with operational right panel.

---

## Screen layout

```
┌──────────────────────────────────────────────────────────────────┐
│                         EclissiShell                             │
├──────┬──────────────────────────────┬───────────────────────────-┤
│      │  Header                      │                            │
│      │  [orb] Chat  [Luna Engine]   │  Guardian Luna             │
│      │              ···── Mar 2026  │  [orb] Guardian Luna  OPS  │
│      ├──────────────────────────────┤                            │
│      │  Context strip               │  ┌────────────────────┐   │
│ Dock │  [project] │ Luna Engine │   │  │ Session summary    │   │
│      │  Observatory │ session 42m   │  │ 3 facts, 1 entity  │   │
│  E   ├──────────────────────────────┤  │ Scribe avg 0.89    │   │
│  M   │                              │  └────────────────────┘   │
│  V   │  Messages                    │  ┌────────────────────┐   │
│  Q   │                              │  │ ⚠ Recommendation   │   │
│  ─   │  [user bubble]               │  │ Prosody gap P0     │   │
│  P   │  [luna bubble + badges]      │  │ [Write handoff]    │   │
│  D   │  [activity card]             │  └────────────────────┘   │
│      │  [confirm card]              │  ┌────────────────────┐   │
│      │  [luna bubble + kbar]        │  │ Entity health      │   │
│      │  [attention prompt]          │  │ Corey: pending     │   │
│      │  [thread card]               │  │ Biennale: 0.71     │   │
│      │                              │  └────────────────────┘   │
│      ├──────────────────────────────┤                            │
│      │  T-bar ─── GUARDIAN LUNA ──  │  25K   115   26K   0.42   │
│      ├──────────────────────────────┤  nodes  ent  edges avg LI │
│      │  [input] [mic] [Send] [Cfg]  │  [Ask Guardian Luna...] ▶ │
└──────┴──────────────────────────────┴────────────────────────────┘
```

**Dock** — widget rail (52px). Existing: Engine, Memory, Voice, QA, Prompt, Debug.

**Chat column** — companion Luna. Always visible. Full width when Guardian panel is closed.

**Guardian Luna panel** — slides open from the right when T-bar is clicked. 380px wide. Independent scroll, input, and message history.

**T-bar** — thin gradient line anchored above the input bar. Shows "GUARDIAN LUNA" label + extraction count. Click toggles the right panel.

---

## Chat column components

### Header
- Orb (animated pulse, reflects connection state)
- "Chat" title
- Project tag (active project from ProjectStrip)
- Timeline scrubber: one segment per month, width proportional to conversation volume, color = dominant life state that month. Current month has outline. Click scrolls to that period.

### Context strip
Tags showing current conversation state:
- Life state tag: `personal` / `project` / `bridge` / `mixed` (color-coded)
- Active entity tags: clickable, navigate to Observatory > Entities
- Session duration
- Separator pipes between groups

### Messages
Standard chat bubbles with meta features layered on:

**User bubbles** — purple-tinted, right-aligned. Entity names highlighted as clickable blue links.

**Luna bubbles** — surface-colored, left-aligned. Features:
- **Life state border** — 2.5px left border colored by state (blue=personal, green=project, amber=bridge, purple=mixed)
- **Entity highlighting** — blue dotted-underline text, clickable → Observatory
- **Knowledge dot** — 5px amber circle when the message triggered Scribe extractions
- **Badge row** (configurable via Settings):
  - Route indicator: `⚡ delegated` / `● local` / `☁ cloud`
  - Model name (hidden by default)
  - Token count (hidden by default)
  - Latency in ms
  - Filtered count (FaceID access-denied nodes)
  - LunaScript classification: `RESONANCE` / `DRIFT` / `EXPANSION` / `COMPRESSION`
- **Knowledge bar** — thin colored line below the bubble showing extraction type (F=FACT, A=ACTION, P=PROBLEM). Hover shows content. Click navigates to Observatory.

**Between-message elements:**
- **Activity cards** — small muted cards showing real-time pipeline events: "Extracted: Observatory routes not merged (FACT · 0.92)", "Edge: Scribe → Entity Resolver (DEPENDS_ON)". Hover reveals "→ Observatory" navigation.
- **Confirmation cards** — prominent interactive cards: "Is **Corey Smith** a new person?" with Yes/No/Later buttons. Feeds back to entity resolver immediately.
- **Attention prompts** — "Fabrication mentioned 3 times this week. Track as a thread?" with Track button.
- **Thread cards** — "Fabrication pipeline: 3 mentions, 2 entities, 1 action" with status badge. Clickable → Observatory threads.
- **Quest cards** — "Review 3 new entities" with hover-reveal navigation.

### T-bar
- Gradient line: colors from extraction type distribution this session
- "GUARDIAN LUNA" label
- Extraction count badge
- Arrow indicator (rotates when panel is open)
- Click toggles Guardian Luna panel

### Input bar
- Text input with placeholder showing project context and identity
- Mic button (push-to-talk for voice mode)
- Send button
- Cfg button: opens badge visibility config dropdown

### Badge visibility config
Dropdown from Cfg button. Toggles for each badge type:
```yaml
chat_badges:
  show_route: true         # delegated/local/cloud
  show_model: false        # raw model name
  show_tokens: false       # token count
  show_latency: true       # inference time
  show_access_filter: true # FaceID filtered count
  show_lunascript: true    # RESONANCE/DRIFT/etc
  show_knowledge_events: true  # activity cards + kbars
```
Persisted in `/api/settings/chat-badges`. Pre-configurable per Forge build profile.

---

## Guardian Luna panel

### Identity
Guardian Luna is Luna but not the companion. She is operational, diagnostic, and eventually agentic. Think Claude Code, not friend. Same database, completely different persona.

**Voice:** Precise, terse, cited. Every claim tagged with source (Scribe stats, Memory Matrix, Entity resolver, Pipeline state).

**Function:** Monitors the extraction pipeline, reports session health, proposes actions, eventually writes code and triggers builds.

### Header
- Amber orb (Guardian color)
- "Guardian Luna" title
- Mode badge: `OPERATIONAL`
- Close button (×)

### Messages
Guardian Luna's messages include:

**Session summaries** — aggregate view of what happened this session:
- Extraction counts (facts, entities, edges, membrane events)
- Scribe performance (avg confidence, extraction rate)
- Pending confirmations

**Recommendations with action cards** — proactive suggestions:
- "The prosody gap was flagged as P0. I can write a handoff."
- Buttons: [Write handoff] [Dismiss]
- Code-aware: can reference specific files, functions, line numbers

**Entity health checks** — per-entity status:
- Lock-in score and state (drifting/fluid/settled)
- Pending confirmations
- Recent mention activity

**Source citations** — every Guardian message cites its data:
- `Memory Matrix` — data from luna_engine.db
- `Scribe stats` — extraction pipeline metrics
- `Entity resolver` — resolution and creation logs
- `Pipeline state` — inference chain health
- `Config` — settings and tuning parameters

### Stats footer
Four metric tiles: Nodes, Entities, Edges, Avg Lock-in. Read from `/observatory/api/stats`.

### Input bar
- "Ask Guardian Luna..." placeholder
- Send button (amber-themed)
- Separate from companion chat input — messages go to a different endpoint

---

## Data flow

### Event bus (backend)

New file: `src/luna/core/event_bus.py`

```
EventBus (knowledge_bus singleton)
  ├── subscribe(event_type, handler)
  ├── emit(event_type, data)  →  in-memory queue (500 max)
  └── broadcast to /ws/knowledge WebSocket
```

### Event types

| Event | Emitted by | Data |
|-------|-----------|------|
| `entity_created` | EntityResolver | entity_id, name, type, needs_confirmation |
| `entity_confirmed` | Confirm endpoint | entity_id, confirmed boolean |
| `fact_extracted` | Scribe | node_id, content, type, confidence, entities[] |
| `edge_created` | Librarian | from_id, to_id, relationship, strength |
| `thread_updated` | Matrix | thread_id, status, title |
| `quest_generated` | Maintenance sweep | quest_id, title, type |
| `extraction_batch` | Scribe | session_id, facts_count, edges_count, entities_count |

### Emit points (existing code instrumentation)

- `src/luna/entities/resolution.py` → `resolve_or_create()` after INSERT → `entity_created`
- `src/luna/actors/scribe.py` → after extraction completes → `extraction_batch` + `fact_extracted`
- `src/luna/actors/librarian.py` → after filing edges → `edge_created`
- `src/luna/actors/matrix.py` → after thread create/update → `thread_updated`

### WebSocket

New endpoint: `/ws/knowledge` in `server.py`

Follows exact same pattern as existing `/ws/orb`, `/ws/chat`, `/ws/identity`:
- Global set: `_knowledge_websockets`
- Broadcast function: `_broadcast_knowledge_event(event)`
- Wire at startup: `knowledge_bus.subscribe('*', _broadcast_knowledge_event)`

### Frontend consumers

**Both panels consume the same WebSocket, render differently:**

```
/ws/knowledge
  ├── useKnowledgeStream (companion chat)
  │   ├── Activity cards (real-time event display)
  │   ├── Confirmation cards (entity_created + needs_confirmation)
  │   ├── Knowledge bars (fact_extracted)
  │   └── Thread/quest cards (thread_updated, quest_generated)
  │
  └── useGuardianLuna (right panel)
      ├── Session summary (aggregated extraction_batch events)
      ├── Entity health (entity_created + DB queries)
      ├── Recommendations (pattern detection on event stream)
      └── Action cards (proposed fixes, handoff generation)
```

---

## Two Lunas: backend paths

| Aspect | Companion Luna | Guardian Luna |
|--------|---------------|---------------|
| **System prompt** | Director + personality kernel + virtues | Flat operational prompt, no personality |
| **LLM routing** | Full inference chain (Groq/Claude/Gemini fallback) | Direct LLM call, no personality wrapping |
| **Context** | Memory retrieval (FTS5 + vector + graph) | Pipeline stats + DB diagnostic queries |
| **History** | Conversation turns (user ↔ Luna) | Extraction audit trail + event log |
| **Voice** | Warm, curious, sovereign | Precise, terse, cited |
| **Responds to** | User messages about anything | System queries about Luna's internals |
| **Actions** | Answers, remembers, creates knowledge | Diagnoses, recommends, proposes code changes |
| **Database** | Same luna_engine.db | Same luna_engine.db, different queries |

### Guardian Luna endpoint (future)

```
POST /api/guardian-luna/message
Body: { "message": "why is extraction confidence low?", "session_context": {...} }
Response: { "response": "...", "sources": [...], "actions": [...] }
```

Guardian Luna's system prompt includes:
- Current session stats (from event bus aggregation)
- Recent extraction results
- Entity health snapshot
- Active threads and quests
- No personality kernel, no virtues, no prosody

---

## New files

### Backend
| File | Purpose |
|------|---------|
| `src/luna/core/event_bus.py` | EventBus class + knowledge_bus singleton |
| `src/luna/services/observatory/routes.py` | Observatory router (18 endpoints) |
| `src/luna/services/observatory/__init__.py` | Package init |

### Frontend
| File | Purpose |
|------|---------|
| `frontend/src/hooks/useKnowledgeStream.js` | WebSocket consumer for companion chat |
| `frontend/src/hooks/useGuardianLuna.js` | WebSocket consumer + LLM for Guardian panel |
| `frontend/src/hooks/useBadgeConfig.js` | Badge visibility settings |
| `frontend/src/components/ConfirmationCard.jsx` | Entity confirmation widget |
| `frontend/src/components/ActivityCard.jsx` | Pipeline event display |
| `frontend/src/components/AttentionPrompt.jsx` | Thread tracking prompt |
| `frontend/src/components/ThreadCard.jsx` | Active thread display |
| `frontend/src/components/QuestCard.jsx` | Quest notification |
| `frontend/src/components/GuardianLunaPanel.jsx` | Full right panel |
| `frontend/src/components/TBar.jsx` | Knowledge trigger bar |
| `frontend/src/components/ContextStrip.jsx` | Life state + entity tags |
| `frontend/src/components/TimelineScrubber.jsx` | Month navigation |
| `frontend/src/components/BadgeRow.jsx` | Configurable badge renderer |

### Modified files
| File | Changes |
|------|---------|
| `src/luna/api/server.py` | /ws/knowledge + /api/entities/confirm + /api/settings/chat-badges + /api/guardian-luna/message + event bus wiring |
| `src/luna/entities/resolution.py` | emit entity_created |
| `src/luna/actors/scribe.py` | emit extraction_batch + fact_extracted |
| `src/luna/actors/librarian.py` | emit edge_created |
| `src/luna/actors/matrix.py` | emit thread_updated |
| `frontend/vite.config.js` | /ws/knowledge proxy |
| `frontend/src/components/ChatPanel.jsx` | Integrate all new components, replace hardcoded badges with BadgeRow |
| `frontend/src/eclissi/EclissiHome.jsx` | Add ContextStrip, TimelineScrubber, TBar, GuardianLunaPanel |

---

## Click-through navigation

Every interactive element navigates somewhere:

| Element | Click target |
|---------|-------------|
| Entity name in bubble | Observatory > Entities > {entityId} |
| Entity tag in context strip | Observatory > Entities > {entityId} |
| Activity card | Observatory > relevant view |
| Knowledge bar | Observatory > Graph (centered on node) |
| Thread card | Observatory > Threads |
| Quest card | Observatory > Quests |
| Confirmation card entity name | Observatory > Entities > {entityId} |
| Guardian Luna source chip | Observatory > relevant data source |

All navigation uses existing `useNavigation` hook: `navigate({ to: 'observatory', tab: '...', entityId: '...' })`.

---

## Build configuration

Forge profiles control what's visible per build:

```yaml
# tarcila.yaml (end user)
settings:
  chat_badges:
    show_route: false
    show_model: false
    show_tokens: false
    show_latency: false
    show_access_filter: true
    show_lunascript: true
    show_knowledge_events: true
  guardian_luna:
    enabled: false  # hidden for end users initially

# dev.yaml (development)
settings:
  chat_badges:
    show_route: true
    show_model: true
    show_tokens: true
    show_latency: true
    show_access_filter: true
    show_lunascript: true
    show_knowledge_events: true
  guardian_luna:
    enabled: true
```

---

## Implementation order

1. EventBus + /ws/knowledge (backend infra)
2. One emit point (entity_created in resolution.py) — verify end-to-end
3. useKnowledgeStream hook — verify events in browser console
4. ConfirmationCard + /api/entities/confirm — test entity confirm/reject
5. ActivityCard component — render pipeline events inline
6. BadgeRow + useBadgeConfig + /api/settings/chat-badges — configurable badges
7. ContextStrip + TimelineScrubber — header enrichments
8. KnowledgeBar upgrade — wire to real-time events (replace polling)
9. TBar component — Guardian Luna trigger
10. GuardianLunaPanel + useGuardianLuna — right panel shell
11. Guardian Luna session summary (aggregate events)
12. Guardian Luna entity health (DB queries)
13. Guardian Luna action cards (recommendations)
14. Remaining emit points (scribe, librarian, matrix)
15. ThreadCard + QuestCard + AttentionPrompt
16. Click-through navigation wiring
17. Forge profile integration for badge/guardian config

---

## Prototypes

| File | Description |
|------|-------------|
| `eclissi_meta_chat_option_c.html` | Option C standalone — enriched live chat |
| `eclissi_option_c_guardian_luna.html` | Full layout — Option C + Guardian Luna panel |
| `eclissi_layout_map.html` | Component architecture diagram |
| `luna_knowledge_pipeline_map.html` | 5-tab knowledge pipeline reference |
