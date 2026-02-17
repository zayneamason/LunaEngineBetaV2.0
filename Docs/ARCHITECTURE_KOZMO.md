# KOZMO Architecture — System Design Document

**Version:** 0.1.0
**Date:** 2026-02-11
**Author:** Architect (The Dude)
**Status:** DESIGN — not yet implemented

---

## 1. What KOZMO Is

KOZMO is an AI filmmaking platform. It combines agent-driven intelligence (Eden) with cinema-grade production controls and a persistent world bible. Nobody has both agent smarts AND deterministic camera controls. That's the wedge.

KOZMO has two modes:

- **KOZMO CODEX** — World bible + agent command center
- **KOZMO LAB** — Production studio for shot creation

Both share a common Project layer and agent layer.

KOZMO is designed as a standalone-capable application that is currently hosted inside Eclissi. It could be extracted into its own app if needed — the coupling is intentional but not structural.

---

## 2. Where Everything Lives

### The Stack

```
┌──────────────────────────────────────────────────────────────┐
│                  ECLISSI (Frontend / UX+UI)                   │
│                  React + Vite · localhost:5173                 │
│                                                               │
│  Eclissi is the face of the Luna Engine. Unified frontend     │
│  for consciousness monitoring, memory, AND creative work.     │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                    EXISTING PAGES                        │ │
│  │  Luna Hub (chat) · Memory Matrix · Engine Status         │ │
│  │  QA Panel · Voight-Kampff · Memory Monitor · Settings    │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                    KOZMO (new modes)                     │ │
│  │                                                          │ │
│  │  ┌────────────────────┐  ┌────────────────────────────┐ │ │
│  │  │   KOZMO CODEX      │  │   KOZMO LAB                │ │ │
│  │  │   World Bible      │  │   Production Studio        │ │ │
│  │  │                    │  │                            │ │ │
│  │  │   Entity Browser   │  │   Shot List               │ │ │
│  │  │   Relationships    │  │   Hero Frame Canvas       │ │ │
│  │  │   Agent Dispatch   │  │   Camera Controls         │ │ │
│  │  │   Luna Context     │  │   Post / DI Agent         │ │ │
│  │  │   Graph View (v4)  │  │   Timeline                │ │ │
│  │  │   Templates        │  │   Agent Activity          │ │ │
│  │  └────────────────────┘  └────────────────────────────┘ │ │
│  │                                                          │ │
│  │  KOZMO is standalone-capable. Currently hosted by        │ │
│  │  Eclissi but has no hard dependency on Eclissi pages.    │ │
│  └─────────────────────────────────────────────────────────┘ │
│                           │                                   │
│                      HTTP / SSE                               │
│                      to :8000                                 │
├──────────────────────────────────────────────────────────────┤
│                  LUNA ENGINE (Backend)                         │
│                  Python · FastAPI · localhost:8000             │
│                                                               │
│  ┌───────────────────────────────────────────────────────┐   │
│  │  src/luna/                                             │   │
│  │  ├── engine.py          Main engine (tick loops)       │   │
│  │  ├── api/server.py      FastAPI endpoints              │   │
│  │  ├── actors/            Actor system (Director, etc)   │   │
│  │  ├── services/                                         │   │
│  │  │   ├── eden/          Eden adapter (Phase 1-2 done)  │   │
│  │  │   └── kozmo/         KOZMO service layer (NEW)      │   │
│  │  ├── substrate/         Memory Matrix (SQLite + vec)   │   │
│  │  └── inference/         Local MLX models               │   │
│  └───────────────────────────────────────────────────────┘   │
│                           │                                   │
│              ┌────────────┼────────────┐                      │
│              ▼            ▼            ▼                      │
│         Eden API     Claude API    Local MLX                  │
│        (cloud)       (cloud)      (on-device)                 │
└──────────────────────────────────────────────────────────────┘
```

### Filesystem Layout

**KOZMO App (Eclissi-hosted, standalone-capable):**

```
Tools/KOZMO-Prototype-V1/
├── index.html
├── package.json
├── vite.config.js
├── tailwind.config.js
├── postcss.config.js
│
├── src/
│   ├── main.jsx                # Entry point
│   ├── App.jsx                 # Root — CODEX/LAB mode switching
│   ├── KozmoProvider.jsx       # React context — active project, state
│   │
│   ├── codex/                  # KOZMO CODEX (World Bible)
│   │   ├── KozmoCodex.jsx      # CODEX mode root
│   │   ├── FileTree.jsx
│   │   ├── EntityCard.jsx
│   │   ├── RelationshipBadge.jsx
│   │   ├── RelationshipMap.jsx
│   │   └── GraphView.jsx       # Future V4
│   │
│   ├── lab/                    # KOZMO LAB (Production Studio)
│   │   ├── KozmoLab.jsx        # LAB mode root
│   │   ├── ShotCard.jsx
│   │   ├── HeroFrameCanvas.jsx
│   │   ├── CameraControls.jsx
│   │   ├── PostControls.jsx
│   │   └── Timeline.jsx
│   │
│   ├── shared/                 # Shared across CODEX + LAB
│   │   ├── AgentPanel.jsx
│   │   ├── AgentChat.jsx
│   │   ├── GenerationQueue.jsx
│   │   ├── ProjectHeader.jsx
│   │   └── EdenStatus.jsx
│   │
│   ├── hooks/
│   │   ├── useKozmoProject.js  # Project CRUD, YAML loading
│   │   ├── useEdenAdapter.js   # Eden operations via Luna API
│   │   ├── useAgentDispatch.js # Agent task management
│   │   └── useLunaAPI.js       # Luna Engine connection
│   │
│   └── config/
│       └── cameras.js          # Camera bodies, lenses, film stocks
│
└── public/
    └── ...                     # Static assets
```

**Eclissi integration:** KOZMO's `<App />` component gets embedded into
Eclissi as a page/route. The `KozmoProvider` wraps everything KOZMO needs.
No hard dependency on Eclissi internals — KOZMO can also run standalone
by pointing `main.jsx` at its own root.

**Location:** `_LunaEngine.../Tools/KOZMO-Prototype-V1/`

**Backend (Luna Engine):**

```
src/luna/
├── services/
│   ├── eden/                   # DONE — Eden HTTP adapter
│   │   ├── adapter.py
│   │   ├── client.py
│   │   ├── config.py
│   │   └── types.py
│   │
│   └── kozmo/                  # NEW — KOZMO service layer
│       ├── __init__.py
│       ├── project.py          # Project CRUD, YAML parsing
│       ├── entity.py           # Entity operations, template system
│       ├── graph.py            # Project graph (isolated from Memory Matrix)
│       └── fountain.py         # Fountain screenplay parser
│
├── api/
│   ├── server.py               # Existing — add KOZMO routes
│   └── kozmo_routes.py         # NEW — /kozmo/* API endpoints
```

---

## 3. The Separation Principle

### Luna's Memory vs. Project Data

This is the critical architectural constraint. Luna's Memory Matrix is her personal memory — conversations, decisions, operational knowledge. A KOZMO project is creative content that belongs to the project, not to Luna.

```
Luna's Memory Matrix (PERSONAL)         Project Data (CREATIVE)
─────────────────────────────           ──────────────────────────
• Conversations with Ahab              • Mordecai's character sheet
• System decisions                     • Scene descriptions
• Technical knowledge                  • Shot configurations
• "Ahab is working on DWM project"     • Camera profiles
• How Luna feels about things          • Relationship graphs
                                        • Reference images
NEVER cross-pollinated.                 • Screenplay text
Stored in: data/memory_matrix.db        Stored in: YAML files +
                                          project_graph.db (per project)
```

**Luna's relationship to project data:** Luna doesn't *remember* Mordecai. She *reads* Mordecai's file when working on that project. When Ahab asks "what's Mordecai's arc?" Luna:

1. Checks which project is active
2. Reads `characters/mordecai.yaml` (or queries project graph)
3. Answers from project context, NOT personal memory

What Luna DOES store personally: high-level metadata. "Ahab has a project called Dinosaur Wizard Mother with 4 main characters." Not the contents.

### Project Isolation

Each project gets its own graph database — same technology as Memory Matrix (SQLite + FTS5 + vectors) but a completely separate instance.

```
data/
├── memory_matrix.db              # Luna's personal memory
├── luna_memories.db              # Session recordings
└── projects/
    ├── dinosaur_wizard_mother/
    │   └── project_graph.db      # This project's entity index
    └── another_project/
        └── project_graph.db      # Separate, isolated
```

---

## 4. The Project Layer

### 4.1 YAML as Source of Truth

All project content lives as human-readable YAML files. Git-trackable, hand-editable, portable. The project graph DB is a derived index — it can always be rebuilt from the YAML files.

```
projects/
└── dinosaur_wizard_mother/
    ├── project.yaml              # Manifest
    ├── characters/
    │   ├── _template.yaml        # Schema for character entities
    │   ├── cornelius.yaml
    │   ├── mordecai.yaml
    │   ├── constance.yaml
    │   └── princess.yaml
    ├── locations/
    │   ├── _template.yaml
    │   ├── crooked_nail.yaml
    │   └── crystal_tower.yaml
    ├── props/
    │   ├── _template.yaml
    │   └── mordecai_staff.yaml
    ├── lore/
    │   ├── _template.yaml
    │   └── magic_system.yaml
    ├── factions/
    │   └── _template.yaml
    ├── screenplay/
    │   ├── act_1/
    │   │   ├── scene_01_departure.yaml      # Metadata
    │   │   └── scene_01_departure.fountain   # Screenplay text
    │   └── act_2/
    │       └── ...
    ├── shots/
    │   ├── scene_01/
    │   │   ├── sh001_establishing.yaml
    │   │   └── sh002_cornelius_cu.yaml
    │   └── ...
    ├── assets/
    │   ├── reference/
    │   ├── hero_frames/
    │   └── loras/
    └── graph.yaml                # Explicit cross-entity relationships
```

**Default location:** `_LunaEngine.../data/projects/<slug>/`
**Portable:** Can exist anywhere on disk. `project.yaml` contains a `root` path override.

### 4.2 Project Manifest

```yaml
# project.yaml
name: "The Dinosaur, The Wizard, and The Mother"
slug: dinosaur_wizard_mother
version: 1
created: 2026-02-11
updated: 2026-02-11

settings:
  default_camera: arri_alexa35
  default_lens: cooke_s7i
  default_film_stock: kodak_5219
  aspect_ratio: "21:9"

eden:
  default_agent_id: null
  manna_budget: 100.0

entity_types:
  - characters
  - locations
  - props
  - lore
  - factions
```

### 4.3 Entity YAML

```yaml
# characters/mordecai.yaml
type: character
name: Mordecai
role: The Wizard
status: active

physical:
  age: 28
  build: "lean, angular"
  hair: "dark, unkempt"
  distinguishing: "burn scars on palms from early magic"

wardrobe:
  default: "threadbare traveling cloak, leather satchel"
  tavern: "cloak removed, shirtsleeves rolled"
  underground: "disheveled, cloak missing"

traits: [brilliant, self-destructive, charming, addicted]

arc:
  summary: "Prodigy → Lost → Broken → ???"
  turning_point: scene_04

voice:
  speech_pattern: "Eloquent when sober, fragmented when using"
  verbal_tics:
    - "Addresses Cornelius as 'old man'"

relationships:
  - entity: cornelius
    type: family
    detail: "Son. Resents his protection. Needs it."
  - entity: princess
    type: complicated
    detail: "She offers what he wants. That's the problem."
  - entity: constance
    type: family
    detail: "Mother. Can't face her. Won't call her."

references:
  images: [assets/reference/mordecai_concept_v1.png]
  lora: null

props:
  - entity: mordecai_staff
    note: "Appears Scene 3 onward. NOT in Scene 1."

scenes: [scene_01, scene_02, scene_03, scene_04, scene_05, scene_07, scene_09]

tags: [main_cast, magic_sector, act_1, act_2, act_3]

# Luna can append context below this line
luna_notes: |
  Mordecai's addiction is to numbness, not to magic itself.
  Key distinction Ahab emphasized.
```

### 4.4 Template System

Templates define the schema for each entity type. They're YAML files that describe expected fields, types, and sections. Customizable by the user or by Luna.

```yaml
# characters/_template.yaml
type: character
version: 1

sections:
  - name: identity
    fields:
      - { key: name, type: string, required: true }
      - { key: role, type: string }
      - { key: status, type: enum, options: [active, deceased, unknown] }

  - name: physical
    dynamic: true    # user can add arbitrary keys
    fields:
      - { key: age, type: string }
      - { key: build, type: string }
      - { key: distinguishing, type: text }

  - name: wardrobe
    dynamic: true

  - name: arc
    fields:
      - { key: summary, type: string }
      - { key: turning_point, type: ref, ref_type: scene }

  - name: voice
    fields:
      - { key: speech_pattern, type: text }
      - { key: verbal_tics, type: list }

  - name: relationships
    type: list
    item_fields:
      - { key: entity, type: ref, ref_type: any }
      - { key: type, type: string }
      - { key: detail, type: text }

  - name: references
    fields:
      - { key: images, type: file_list }
      - { key: lora, type: string, nullable: true }
```

When creating a new entity, the template provides the form. Luna can pre-fill fields based on what she's heard in conversation. Luna can also suggest adding fields to templates: "You keep mentioning Mordecai's magic limitations — want me to add a `magic_constraints` section?"

### 4.5 Shot YAML

```yaml
# shots/scene_01/sh001_establishing.yaml
type: shot
id: sh001
scene: scene_01
name: "Crooked Nail — Establishing"
status: approved    # idea | draft | rendering | hero_approved | approved | locked

camera:
  body: arri_alexa35
  lens: panavision_c
  focal_mm: 40
  aperture: 2.8
  movement: [dolly_in]
  duration_sec: 3

post:
  film_stock: kodak_5219
  color_temp_k: 5600
  grain_pct: 25
  bloom_pct: 15
  halation_pct: 10

hero_frame:
  path: assets/hero_frames/sh001_hero_v2.png
  eden_task_id: "task_abc123"
  approved: true
  approved_at: 2026-02-10T14:30:00Z

prompt: >
  Exterior of a ramshackle pub at the edge of nowhere.
  Warm light through dirty windows. Evening. Overcast sky.
  Shot on ARRI Alexa 35, Panavision C-Series anamorphic 40mm.

characters_present: [cornelius, mordecai, constance]
location: crooked_nail

continuity_notes:
  - "Mordecai does NOT have his staff yet"
  - "Constance in doorway, never enters frame"
```

### 4.6 Fountain Screenplay

```fountain
INT. THE CROOKED NAIL - EVENING

A ramshackle pub at the edge of nowhere. Warm light
through dirty windows.

CORNELIUS
(quietly)
We leave at dawn.

MORDECAI
No.

CONSTANCE watches from the doorway. She says nothing.
She doesn't need to.

> FADE TO:
```

Fountain is the industry standard plaintext screenplay format. Any Fountain-aware tool renders it with proper formatting. For KOZMO the key value is parseability — Luna can extract scene headers, character appearances, action lines, and dialogue programmatically to auto-populate scene YAML metadata.

Fountain files are plaintext, so they diff beautifully in git.

### 4.7 Relationship Graph

Explicit cross-cutting relationships live in `graph.yaml` at project root:

```yaml
# graph.yaml
relationships:
  - from: mordecai
    to: princess
    type: catalyst
    note: "She makes his cracks visible"

  - from: crooked_nail
    to: underground
    type: thematic_mirror
    note: "Both are places of hiding. One warm, one dark."

  - from: mordecai_staff
    to: magic_system
    type: governed_by
```

Entities also declare relationships inline. The project graph merges both sources. Luna adds inferred edges on top — visually distinct (dotted vs solid), promotable to explicit with one click.

### 4.8 Data Flow

```
YAML Files (source of truth, git-tracked, human-editable)
    │
    ├── on project load ──→ Project Graph DB (derived index)
    │                        ├── Entity nodes
    │                        ├── Explicit edges (YAML + graph.yaml)
    │                        ├── FTS5 index (searchable)
    │                        └── Vector embeddings (semantic search)
    │
    ├── on edit via UI ──→ Write back to YAML → re-index affected nodes
    │
    └── Luna reads ──→ Project context (temporary, never personal memory)

CODEX reads Project Graph DB for:
    ├── Entity cards (rendered from template + data)
    ├── Relationship navigation
    ├── Search results
    └── Context panels

LAB reads Project Graph DB for:
    ├── Shot configurations
    ├── Character refs for LoRA/anchor selection
    ├── Location lighting notes → camera suggestions
    └── Continuity validation
```

---

## 5. Agent Architecture

### 5.1 The Agents

```
┌─────────────────────────────────────────────────────────────┐
│                     KOZMO AGENT LAYER                        │
│                                                              │
│  ┌──────────┐  Routes tasks to optimal Eden pipeline.       │
│  │  CHIBA   │  Decides: Eden vs local. Image vs video.      │
│  │  orch.   │  Manages generation queue.                    │
│  └──────────┘                                               │
│                                                              │
│  ┌──────────┐  Generates reference art, concept frames.     │
│  │  MAYA    │  Locks reference anchors for consistency.      │
│  │  vision  │  Manages LoRA training lifecycle.             │
│  └──────────┘                                               │
│                                                              │
│  ┌──────────┐  Film stock emulation, color grading.         │
│  │ DI AGENT │  Applies LUTs, grain, bloom, halation.        │
│  │  post    │  Matches Dehancer profiles.                   │
│  └──────────┘                                               │
│                                                              │
│  ┌──────────┐  Sound design, voice, music.                  │
│  │  FOLEY   │  ElevenLabs integration.                      │
│  │  audio   │  Lip-sync coordination.                       │
│  └──────────┘                                               │
│                                                              │
│  ┌──────────┐  Project context intelligence.                │
│  │  LUNA    │  Continuity tracking, relationship inference.  │
│  │  memory  │  Reads project data, never stores it.         │
│  └──────────┘  Style lock enforcement.                      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 Agent ↔ Eden ↔ Luna Flow

```
User action in CODEX/LAB
        │
        ▼
┌──────────────┐     "Generate reference art for Mordecai"
│  Agent Panel │
│  (frontend)  │
└──────┬───────┘
       │ POST /kozmo/dispatch
       ▼
┌──────────────┐     Chiba decides: Eden txt2img pipeline
│  KOZMO API   │     Enriches prompt with project context
│  (backend)   │     (reads mordecai.yaml for physical desc)
└──────┬───────┘
       │
  ┌────┴─────────────────────────────┐
  │                                  │
  ▼                                  ▼
┌──────────┐               ┌──────────────────┐
│  Eden    │               │  Luna (context)   │
│  Adapter │               │                   │
│          │               │  "Mordecai: lean,  │
│  create  │               │  angular, burn     │
│  task    │               │  scars on palms,   │
│  poll    │               │  threadbare cloak"  │
│  result  │               └──────────────────┘
└──────┬───┘
       │ task complete
       ▼
┌──────────────┐
│  Result      │
│  • URL       │──→ Save to assets/reference/
│  • Metadata  │──→ Update mordecai.yaml references
│  • Task ID   │──→ Log for provenance
└──────────────┘
       │
       ▼
  Frontend updates: entity card shows new image,
  generation queue marks complete
```

### 5.3 Eden Agent Sessions

For interactive work (concept exploration, iterative generation), KOZMO opens Eden agent sessions scoped to the current entity:

```
User in CODEX selects Mordecai → clicks "Chat with Maya"
        │
        ▼
POST /kozmo/session/create
  { agent: "maya", entity: "mordecai", project: "dwm" }
        │
        ▼
Backend:
  1. Read mordecai.yaml → build context prompt
  2. Create Eden session with Maya agent
  3. Inject context: "You are designing Mordecai. Here's what we know: ..."
  4. Return session_id
        │
        ▼
Frontend: Agent chat panel opens with Maya
  User: "Design his staff — ancient wood, cracked, faint glow lines"
  Maya: [generates concept art, returns image]
        │
        ▼
Backend:
  1. Poll Eden task until complete
  2. Save result to assets/reference/
  3. Optionally update mordecai.yaml props section
  4. DO NOT save to Luna's personal memory
```

---

## 6. API Endpoints (New)

All KOZMO endpoints live under `/kozmo/` prefix on the existing FastAPI server.

```
# Project Management
GET    /kozmo/projects                    # List projects
POST   /kozmo/projects                    # Create project
GET    /kozmo/projects/{slug}             # Get project manifest
DELETE /kozmo/projects/{slug}             # Delete project

# Entities
GET    /kozmo/projects/{slug}/entities                    # List all entities
GET    /kozmo/projects/{slug}/entities/{type}             # List by type
GET    /kozmo/projects/{slug}/entities/{type}/{id}        # Get entity
PUT    /kozmo/projects/{slug}/entities/{type}/{id}        # Update entity
POST   /kozmo/projects/{slug}/entities/{type}             # Create entity
DELETE /kozmo/projects/{slug}/entities/{type}/{id}        # Delete entity

# Templates
GET    /kozmo/projects/{slug}/templates/{type}            # Get template

# Relationships
GET    /kozmo/projects/{slug}/graph                       # Full relationship graph
GET    /kozmo/projects/{slug}/graph/{entity_id}           # Relationships for entity
POST   /kozmo/projects/{slug}/graph                       # Add relationship

# Screenplay
GET    /kozmo/projects/{slug}/screenplay                  # Scene list
GET    /kozmo/projects/{slug}/screenplay/{scene_id}       # Scene metadata + fountain

# Shots
GET    /kozmo/projects/{slug}/shots                       # All shots
GET    /kozmo/projects/{slug}/shots/{scene_id}            # Shots for scene
PUT    /kozmo/projects/{slug}/shots/{shot_id}             # Update shot config

# Agent Dispatch
POST   /kozmo/dispatch                                    # Dispatch agent task
GET    /kozmo/queue                                       # Generation queue status
GET    /kozmo/queue/{task_id}                              # Task status

# Eden Sessions (scoped to entity)
POST   /kozmo/session/create                              # Create Eden agent session
POST   /kozmo/session/{session_id}/message                # Send message
GET    /kozmo/session/{session_id}                         # Get session state

# Search
GET    /kozmo/projects/{slug}/search?q=...                # Full-text search across project

# Context (Luna reads project data, doesn't memorize it)
GET    /kozmo/projects/{slug}/context/{entity_id}         # Luna's contextual analysis
GET    /kozmo/projects/{slug}/continuity                  # Continuity report
```

---

## 7. Camera System

### 7.1 Camera Presets (from Higgsfield research)

```yaml
# Stored in: config/kozmo_cameras.yaml

camera_bodies:
  arri_alexa35:
    name: "ARRI Alexa 35"
    sensor: S35
    color_science: "ARRI LogC4"
    badge: CINEMA

  red_v_raptor:
    name: "RED V-Raptor"
    sensor: VV
    color_science: REDWideGamut
    badge: CINEMA

  bmpcc_6k:
    name: "Blackmagic 6K"
    sensor: S35
    color_science: "Blackmagic Film"
    badge: INDIE

  16mm_bolex:
    name: "16mm Bolex"
    sensor: S16
    color_science: "Kodak 7219"
    badge: FILM

  vhs_camcorder:
    name: "VHS Camcorder"
    sensor: "1/3\""
    color_science: Composite
    badge: LO-FI

lens_profiles:
  cooke_s7i:
    name: "Cooke S7/i"
    type: spherical
    character: "Warm, organic flares"
    focal_range: [18, 135]

  panavision_c:
    name: "Panavision C-Series"
    type: anamorphic
    character: "Classic oval bokeh, blue streaks"
    focal_range: [35, 100]

  zeiss_supreme:
    name: "Zeiss Supreme"
    type: spherical
    character: "Clean, clinical precision"
    focal_range: [15, 200]

  canon_k35:
    name: "Canon K35"
    type: spherical
    character: "70s softness, vintage glow"
    focal_range: [18, 85]

  helios_44:
    name: "Helios 44-2"
    type: spherical
    character: "Swirly bokeh, Soviet glass"
    focal_range: [58, 58]

camera_movements:
  - { id: static, name: Static }
  - { id: dolly_in, name: "Dolly In" }
  - { id: dolly_out, name: "Dolly Out" }
  - { id: pan_left, name: "Pan Left" }
  - { id: pan_right, name: "Pan Right" }
  - { id: tilt_up, name: "Tilt Up" }
  - { id: tilt_down, name: "Tilt Down" }
  - { id: crane_up, name: "Crane Up" }
  - { id: crane_down, name: "Crane Down" }
  - { id: orbit_cw, name: "Orbit CW" }
  - { id: orbit_ccw, name: "Orbit CCW" }
  - { id: handheld, name: Handheld }
  - { id: fpv, name: "FPV Drone" }
  - { id: steadicam, name: Steadicam }
  # Max 3 combined per shot

film_stocks:
  kodak_5219:
    name: "Kodak 5219 (500T)"
    character: "Warm tungsten, cinema standard"
  kodak_5207:
    name: "Kodak 5207 (250D)"
    character: "Daylight, neutral palette"
  fuji_eterna:
    name: "Fuji Eterna Vivid"
    character: "Rich greens, cooler shadows"
  cinestill_800:
    name: "CineStill 800T"
    character: "Halation halos, neon warmth"
  ilford_hp5:
    name: "Ilford HP5+ (B&W)"
    character: "Punchy contrast, classic grain"
```

### 7.2 How Camera Settings Flow to Eden

Camera metadata is translated into prompt enrichment when generating via Eden:

```python
# src/luna/services/kozmo/prompt_builder.py

def enrich_prompt(base_prompt: str, shot: ShotConfig) -> str:
    """
    Append camera/lens/stock info to user's prompt.
    Eden doesn't have native camera controls —
    we describe the look we want.
    """
    parts = [base_prompt]

    if shot.camera:
        parts.append(f"Shot on {shot.camera.name}")
    if shot.lens:
        parts.append(f"{shot.lens.name} {shot.lens.type} lens")
    if shot.focal_mm:
        parts.append(f"{shot.focal_mm}mm")
    if shot.aperture:
        parts.append(f"f/{shot.aperture}")
    if shot.film_stock and shot.film_stock.id != "none":
        parts.append(f"{shot.film_stock.name} film stock")
    if shot.camera_movements:
        moves = [m.name for m in shot.camera_movements]
        parts.append(f"camera movement: {', '.join(moves)}")

    return ". ".join(parts)
```

When/if Higgsfield opens an API, the camera config maps directly to their native controls instead of prompt text.

---

## 8. Graph View — Roadmap to V4

The graph is the soul of CODEX. The target is V4 — a living, intelligent visualization that shows not just what the filmmaker connected, but what Luna *discovered*. Each version builds toward that.

### V1 — Entity Cards (prototype, done)

**What:** Entity cards rendered from YAML, relationship lists as clickable badges, navigate between entities by clicking connections.

**Tech:** Pure React state. No visualization libraries. Cards are just styled divs with `onClick` handlers that update `selectedEntity` in KozmoProvider.

**Difficulty:** Easy. It's rendering data as UI. The CODEX prototype already demonstrates this.

**Why it matters:** Proves the data layer works. If YAML → card rendering is clean, everything above it is just visualization.

---

### V2 — Force-Directed Graph

**What:** Interactive node-link diagram. Entities are nodes (colored by type), relationships are edges. Physics simulation positions everything automatically — related entities cluster together, unrelated ones drift apart.

**Tech:** D3 `d3-force` simulation. Nodes get charge repulsion (push apart), link forces (pull connected nodes together), and center gravity (keep the graph from drifting). D3 handles all the physics — we configure parameters and render.

**Difficulty:** Medium. ~200-300 lines. The algorithm is solved. The work is wiring D3's simulation to React rendering (either SVG elements or canvas) and making it feel good — force strengths, damping, collision radius.

**Key forces:**
```
forceCharge:  -300     (nodes repel each other)
forceLink:    distance based on relationship strength
forceCenter:  pull toward viewport center
forceCollide: prevent node overlap (radius + padding)
```

**What the filmmaker sees:** Drop into the graph view and their world is a living constellation. Characters cluster near their locations. Props orbit the characters who wield them. The shape of the story emerges from the data.

---

### V3 — Obsidian-Quality

**What:** Full interaction layer on top of V2. This is where it becomes a tool, not a demo.

- **Zoom + pan** — transform matrix on the SVG/canvas container
- **Type clustering** — stronger repulsion between groups, visual grouping with subtle background regions
- **Search highlighting** — type a query, matching nodes glow, non-matching fade to 20% opacity
- **Animated growth** — replay node creation timestamps, watch the world build itself over time (the "watch your world grow" effect from Obsidian)
- **Click-to-navigate** — click a node → CODEX scrolls to that entity card
- **Edge labels** — relationship types shown on hover or always-on (user toggle)
- **Minimap** — small overview in corner showing full graph with viewport rectangle

**Tech:** D3 + interaction code. Zoom is `d3-zoom`. Minimap is a second smaller SVG with the same data. Search is filtering the node array and applying CSS classes.

**Difficulty:** Medium-Hard. Not algorithmically hard — it's UX polish. A lot of interaction code, event handling, animation timing. No unsolved problems, just craft.

**What the filmmaker sees:** Obsidian's graph view, but for their film. They can explore their world spatially, find orphaned entities (nodes with no edges), spot over-connected characters, and watch the project evolve over time.

---

### V4 — Beyond Obsidian (THE TARGET)

This is where KOZMO leaves Obsidian behind. Obsidian's graph shows links the user made. KOZMO's graph shows links Luna *found*.

**4a. Luna-Inferred Edges**

Luna analyzes entity descriptions, scene co-occurrences, dialogue patterns, and screenplay text to suggest relationships the filmmaker hasn't explicitly declared.

- Displayed as **dotted lines** (vs solid for explicit relationships)
- Color-coded by inference type: semantic similarity, co-occurrence, thematic
- **Promote-to-explicit** with one click — dotted → solid, written to `graph.yaml`
- **Dismiss** to suppress that inference permanently

Example: Luna notices Mordecai and the Princess never share a scene but their character arcs mirror each other (both hiding from something). She suggests a `thematic_mirror` edge. Filmmaker clicks → it's canon.

**4b. Semantic Clustering**

Obsidian clusters by folder/tag. KOZMO clusters by *meaning*.

Run embeddings on entity descriptions → project into 2D (UMAP or t-SNE) → entities that *feel* similar group together regardless of declared type. A location and a character might cluster together because they share thematic DNA.

- Toggle between **type clustering** (V3) and **semantic clustering** (V4)
- Cluster boundaries drawn as subtle convex hulls
- Luna names the clusters: "These three locations all feel claustrophobic — hiding places"

**4c. Contextual Subgraphs**

"Show me everything connected to Scene 4."

Graph traversal from a seed node with configurable depth. The full graph fades, and only the relevant subgraph illuminates — characters in that scene, locations used, props that appear, lore that applies, shots that reference it.

- Seed from any entity, scene, or shot
- Depth slider: 1-hop (direct connections only) → 2-hop → 3-hop
- Contextual subgraphs can be saved as **named views** for quick access

**4d. Continuity Visualization**

Overlay mode: edges turn red where Luna detects continuity breaks. "Mordecai's staff appears in Scene 3 but isn't established until Scene 5." The graph becomes a debugging tool for story logic.

**Tech:** D3 for rendering + Memory Matrix for intelligence. Embeddings are already computed by the project graph (same tech as Luna's memory). Graph traversal is what Memory Matrix does natively (spreading activation). The question is piping it to the visualization — which is API calls from the frontend to `/kozmo/projects/{slug}/context/{entity_id}` and `/kozmo/projects/{slug}/graph/{entity_id}`.

**Difficulty:** Hard-ish. Not because the algorithms are unsolved — Memory Matrix already does hybrid search, vector similarity, and graph traversal. The hard part is the UX: making inferred edges feel helpful not noisy, making semantic clusters legible, making contextual subgraphs animate smoothly. It's a design problem more than an engineering problem.

**What the filmmaker sees:** A world that understands itself. They don't just see what they built — they see what it *means*. Patterns they didn't notice. Connections they didn't declare. Gaps they need to fill. The graph becomes a creative partner, not just a map.

---

## 9. Standalone Capability

KOZMO is designed so it could run independently of Eclissi:

```
Standalone mode:
  KOZMO CODEX + LAB  →  own React app (Vite)
  Luna Engine         →  still the backend (FastAPI :8000)
  Eden Adapter        →  still in Luna Engine
  Project files       →  same YAML structure

Eclissi-hosted mode (current):
  KOZMO is pages/components within the Eclissi frontend
  Shares the same Vite dev server, same React context
  Can access Eclissi's other panels (Memory Matrix, etc.)
```

The coupling point is `KozmoProvider.jsx` — a React context that wraps KOZMO components and provides project state, agent state, and API hooks. In standalone mode, this provider would be the app root. In Eclissi mode, it wraps the KOZMO pages.

---

## 10. Build Phases

```
PHASE 1: Project Layer (backend)                              CURRENT
═══════════════════════════════
  • Project CRUD service (src/luna/services/kozmo/project.py)
  • YAML parsing + entity operations
  • Template system
  • FastAPI routes (/kozmo/*)
  • Fountain parser (basic)

PHASE 2: Eclissi Integration (frontend)
═══════════════════════════════════════
  • KozmoProvider context
  • CODEX page (port from artifact prototype)
  • LAB page (port from artifact prototype)
  • Wire to KOZMO API endpoints
  • useKozmoProject + useEdenAdapter hooks

PHASE 3: Agent Dispatch
═══════════════════════
  • Generation queue (dispatch → poll → result → save)
  • Eden session bridge (entity-scoped agent chat)
  • Prompt enrichment (camera → text)
  • Result → YAML writeback

PHASE 4: Graph View
════════════════════
  • V2: D3 force-directed graph
  • V3: Interaction polish
  • V4: Luna-inferred edges, semantic clustering

PHASE 5: Continuity Engine
══════════════════════════
  • Screenplay → auto-populate scene YAML
  • Cross-scene continuity validation
  • Prop tracking (first appearance enforcement)
  • Luna contextual flags
```

---

## 11. Design Decisions Log

| Decision | Chose | Over | Because |
|----------|-------|------|---------|
| YAML source of truth | YAML files | SQLite-only | Git-trackable, human-editable, portable |
| Project isolation | Separate DB per project | Shared Memory Matrix | Creative content ≠ Luna's personal memory |
| Eden via prompt enrichment | Text-based camera desc | Native camera API | Higgsfield API doesn't exist yet, Eden has no camera controls |
| Templates as YAML | `_template.yaml` per type | Hardcoded schemas | User/Luna customizable, per-project variation |
| Fountain screenplay | `.fountain` files | Markdown prose | Industry standard, parseable, git-friendly |
| KOZMO inside Eclissi | Hosted mode | Standalone first | Shares infrastructure, but designed for extraction |
| Agent chat over forms | Natural language dispatch | Structured buttons only | More flexible, Luna can interpret intent |
| React context for state | KozmoProvider | Redux/Zustand | Minimal, matches existing Eclissi patterns |

---

## 12. Reference

### Prototypes (Claude artifacts)
- `kozmo_codex.jsx` — CODEX world bible interface
- `kozmo_studio.jsx` — LAB production interface (file will be renamed to `kozmo_lab.jsx`)
- `kozmo_ide.jsx` — Story/narrative IDE (predecessor, may merge into CODEX)
- `eden_vs_higgsfield.jsx` — Platform comparison

### Existing Code
- Eden Adapter: `src/luna/services/eden/` (Phase 1-2 complete, 29 tests passing)
- Luna Engine API: `src/luna/api/server.py` (FastAPI on :8000)
- Eclissi Frontend: `frontend/src/` (React + Vite on :5173)

### External References
- Eden API: `https://api.eden.art` / `https://docs.eden.art`
- Eden SDK (JS reference): `Eden_Project/hello-eden/src/lib/eden.ts`
- Fountain format: `https://fountain.io/syntax`
- Architecture diagrams: `Eden_Project/DIAGRAMS_Architecture_Options.md`

---

*This document is the single source of truth for KOZMO's architecture. Update it when decisions change.*
