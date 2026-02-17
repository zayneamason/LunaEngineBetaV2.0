# HANDOFF: KOZMO Platform — Build Guide

**Date:** 2026-02-11
**Scope:** KOZMO SCRIBO + CODEX + LAB — AI filmmaking platform inside Eclissi
**Status:** PHASE 1 BACKEND COMPLETE (179 tests), SCRIBO DESIGN COMPLETE — ready for Phase 6
**Architecture:** `Docs/ARCHITECTURE_KOZMO.md` (single source of truth)

---

## OVERVIEW

KOZMO is an AI filmmaking platform with three modes:
- **SCRIBO** — The writer's room. Hierarchical story navigation, mixed prose/Fountain editor, agent collaboration
- **CODEX** — World bible, entity management, relationship graphs, agent dispatch
- **LAB** — Production studio, shot creation, camera controls, hero frame generation

KOZMO runs inside Eclissi (Luna Engine's frontend). It's standalone-capable — no hard dependency on Eclissi internals. Luna Engine (FastAPI on :8000) is the backend. Eden.art (already integrated, Phases 1-4 complete) handles creative generation.

```
Eclissi (React :5173)  ──embeds──>  KOZMO (React, :5174 standalone)
                                         │
                                    HTTP/SSE
                                         │
                                    Luna Engine (FastAPI :8000)
                                         │
                                    ┌────┴────┐
                                  Eden API   Local MLX
```

---

## WHAT EXISTS (already built)

| What | Where | Status |
|------|-------|--------|
| Architecture doc | `Docs/ARCHITECTURE_KOZMO.md` | COMPLETE — 12 sections, all design decisions |
| Frontend scaffold | `Tools/KOZMO-Prototype-V1/` | COMPLETE — Vite + React + Tailwind, runnable |
| App root + mode switcher | `src/App.jsx` | COMPLETE — CODEX/LAB toggle |
| KozmoProvider (React context) | `src/KozmoProvider.jsx` | COMPLETE — project, agent, connection state |
| CODEX layout (3-panel) | `src/codex/KozmoCodex.jsx` | SCAFFOLD — layout + placeholders |
| LAB layout (3-panel + timeline) | `src/lab/KozmoLab.jsx` | SCAFFOLD — layout + placeholders |
| Camera config | `src/config/cameras.js` | COMPLETE — bodies, lenses, stocks, movements, prompt builder |
| API hooks | `src/hooks/` | SCAFFOLD — 4 hooks with fetch stubs |
| Eden adapter | `src/luna/services/eden/` | COMPLETE — 78 tests, 8 live validations |
| Eden MCP tools | `src/luna_mcp/tools/eden.py` | COMPLETE — 5 tools exposed |
| Eden policy/guardrails | `src/luna/services/eden/policy.py` | COMPLETE — kill switch, budget, audit |
| Prototype artifacts | Project files in Claude | COMPLETE — full CODEX + LAB React prototypes |

---

## WHAT NEEDS TO BE BUILT

### Phase 1: Backend — KOZMO Service Layer

**Goal:** Python service that reads/writes YAML project files, indexes them into a per-project graph DB, and exposes REST endpoints.

**New files to create:**

| File | Purpose |
|------|---------|
| `src/luna/services/kozmo/__init__.py` | Package exports |
| `src/luna/services/kozmo/types.py` | Pydantic models for projects, entities, shots, templates |
| `src/luna/services/kozmo/project.py` | Project CRUD — create, load, list, delete projects |
| `src/luna/services/kozmo/entity.py` | Entity CRUD — parse YAML, validate against templates |
| `src/luna/services/kozmo/graph.py` | Per-project graph DB (isolated from Memory Matrix) |
| `src/luna/services/kozmo/fountain.py` | Fountain screenplay parser |
| `src/luna/services/kozmo/prompt_builder.py` | Camera config → Eden prompt enrichment |
| `src/luna/api/kozmo_routes.py` | FastAPI router with all /kozmo/* endpoints |
| `config/kozmo_cameras.yaml` | Camera bodies, lenses, film stocks (backend copy) |
| `tests/test_kozmo_project.py` | Project CRUD tests |
| `tests/test_kozmo_entity.py` | Entity parsing, template validation tests |
| `tests/test_kozmo_graph.py` | Graph isolation, indexing, search tests |
| `tests/test_kozmo_fountain.py` | Fountain parsing tests |
| `tests/test_kozmo_routes.py` | API endpoint tests |

**Files to modify:**

| File | Change |
|------|--------|
| `src/luna/api/server.py` | Mount KOZMO router: `app.include_router(kozmo_router, prefix="/kozmo")` |
| `src/luna/engine.py` | Optional: `_init_kozmo()` during boot for project graph preloading |

---

### Phase 1 Detail: types.py

```python
# Pydantic models — match YAML structure exactly

class ProjectManifest(BaseModel):
    name: str
    slug: str
    version: int = 1
    created: datetime
    updated: datetime
    settings: ProjectSettings
    eden: Optional[EdenSettings] = None
    entity_types: list[str] = ["characters", "locations", "props", "lore", "factions"]

class ProjectSettings(BaseModel):
    default_camera: str = "arri_alexa35"
    default_lens: str = "cooke_s7i"
    default_film_stock: str = "kodak_5219"
    aspect_ratio: str = "21:9"

class Entity(BaseModel):
    type: str                    # character, location, prop, lore, faction
    name: str
    slug: str                    # filename stem (mordecai, crooked_nail)
    status: str = "active"       # active, deceased, unknown, draft
    data: dict                   # All YAML content beyond the core fields
    relationships: list[Relationship] = []
    references: EntityReferences = EntityReferences()
    scenes: list[str] = []
    tags: list[str] = []
    luna_notes: Optional[str] = None

class Relationship(BaseModel):
    entity: str                  # slug of related entity
    type: str                    # family, rival, catalyst, thematic_mirror, etc.
    detail: Optional[str] = None

class EntityReferences(BaseModel):
    images: list[str] = []       # relative paths to reference images
    lora: Optional[str] = None   # LoRA model ID or path

class ShotConfig(BaseModel):
    id: str                      # sh001, sh002
    scene: str                   # scene slug
    name: str
    status: str = "idea"         # idea | draft | rendering | hero_approved | approved | locked
    camera: CameraConfig
    post: PostConfig
    hero_frame: Optional[HeroFrame] = None
    prompt: str
    characters_present: list[str] = []
    location: Optional[str] = None
    continuity_notes: list[str] = []

class CameraConfig(BaseModel):
    body: str = "arri_alexa35"
    lens: str = "cooke_s7i"
    focal_mm: int = 50
    aperture: float = 2.8
    movement: list[str] = ["static"]   # max 3
    duration_sec: float = 3.0

class PostConfig(BaseModel):
    film_stock: str = "kodak_5219"
    color_temp_k: int = 5600
    grain_pct: int = 0
    bloom_pct: int = 0
    halation_pct: int = 0

class HeroFrame(BaseModel):
    path: Optional[str] = None
    eden_task_id: Optional[str] = None
    approved: bool = False
    approved_at: Optional[datetime] = None

class Template(BaseModel):
    type: str
    version: int = 1
    sections: list[TemplateSection]

class TemplateSection(BaseModel):
    name: str
    dynamic: bool = False
    fields: list[TemplateField] = []
    type: Optional[str] = None        # "list" for relationship-style sections
    item_fields: list[TemplateField] = []

class TemplateField(BaseModel):
    key: str
    type: str    # string, text, int, float, enum, ref, list, file_list
    required: bool = False
    ref_type: Optional[str] = None    # for ref fields: entity type or "any"
    options: list[str] = []           # for enum fields
    nullable: bool = False
```

---

### Phase 1 Detail: project.py

Core operations:

```python
class KozmoProjectService:
    """
    Manages KOZMO projects on disk.
    YAML files are the source of truth.
    Project graph DB is a derived index.
    """
    def __init__(self, projects_root: Path):
        self.root = projects_root  # default: data/projects/

    async def list_projects(self) -> list[ProjectManifest]:
        """Scan projects_root for project.yaml files."""

    async def create_project(self, name: str, slug: str) -> ProjectManifest:
        """
        Create directory structure + project.yaml + default templates.
        Creates: project_root/{characters,locations,props,lore,factions,
                               screenplay,shots,assets/reference,
                               assets/hero_frames,assets/loras}/
        Copies default _template.yaml into each entity type dir.
        """

    async def load_project(self, slug: str) -> ProjectManifest:
        """Read and parse project.yaml."""

    async def delete_project(self, slug: str) -> bool:
        """Remove project directory. Requires confirmation flag."""

    async def get_entities(self, slug: str, entity_type: str = None) -> list[Entity]:
        """
        Read YAML files from entity type directories.
        If entity_type specified, read only that dir.
        Otherwise read all entity types.
        Skip _template.yaml files.
        """

    async def get_entity(self, slug: str, entity_type: str, entity_id: str) -> Entity:
        """Read single entity YAML file."""

    async def save_entity(self, slug: str, entity: Entity) -> Entity:
        """Write entity back to YAML. Re-index in project graph."""

    async def create_entity(self, slug: str, entity_type: str, name: str) -> Entity:
        """
        Create entity from template.
        Read _template.yaml for the type.
        Generate slug from name.
        Write initial YAML with template-defined fields.
        """

    async def get_template(self, slug: str, entity_type: str) -> Template:
        """Read _template.yaml for entity type."""

    async def get_graph(self, slug: str) -> dict:
        """Read graph.yaml + inline relationships from all entities."""

    async def search(self, slug: str, query: str) -> list[Entity]:
        """Full-text search across project graph DB."""
```

**YAML parsing:** Use `PyYAML` (`yaml.safe_load` / `yaml.safe_dump`). Already available in Luna Engine deps. Preserve key order with `yaml.dump(default_flow_style=False, sort_keys=False)`.

**Slug generation:** `slugify(name)` → lowercase, replace spaces with `_`, strip non-alphanumeric. Example: `"Mordecai The Unwise"` → `"mordecai_the_unwise"`.

---

### Phase 1 Detail: graph.py

Per-project graph database. Uses the same Memory Matrix technology (SQLite + FTS5 + vectors) but a completely separate instance.

```python
class ProjectGraph:
    """
    Isolated graph DB for a single KOZMO project.
    Same tech as Memory Matrix. Different data. Never shared.

    CRITICAL: This is NOT Luna's personal memory.
    Luna reads from this. Luna never stores here.
    """
    def __init__(self, project_root: Path):
        self.db_path = project_root / "project_graph.db"

    async def initialize(self):
        """Create tables if not exist. Same schema as Memory Matrix nodes/edges."""

    async def index_entity(self, entity: Entity):
        """Upsert entity as node. Compute embedding. Index for FTS5."""

    async def index_relationships(self, entity: Entity, graph_yaml: dict):
        """Create edges from entity's inline relationships + graph.yaml."""

    async def reindex_all(self, project_root: Path):
        """Full reindex from YAML files. Used on project load or repair."""

    async def search(self, query: str, limit: int = 20) -> list[dict]:
        """Hybrid search (FTS5 + vector) across project entities."""

    async def get_neighbors(self, entity_slug: str, depth: int = 1) -> dict:
        """Graph traversal from seed entity."""

    async def get_inferred_edges(self, entity_slug: str) -> list[dict]:
        """V4 feature: compute semantic similarity to find un-declared relationships."""
```

**Embedding model:** Use whatever Memory Matrix currently uses. The project graph should call the same embedding function for consistency.

---

### Phase 1 Detail: fountain.py

Minimal Fountain parser for extracting metadata from screenplay files.

```python
class FountainParser:
    """
    Parse .fountain files to extract structural elements.
    Not a full Fountain renderer — just metadata extraction.

    Reference: https://fountain.io/syntax
    """

    def parse(self, text: str) -> FountainDocument:
        """Parse fountain text into structured document."""

    def extract_scene_headers(self, text: str) -> list[str]:
        """
        Scene headers start with INT., EXT., INT./EXT., or I/E.
        Returns list of scene header strings.
        """

    def extract_characters(self, text: str) -> list[str]:
        """
        Character names appear in ALL CAPS on their own line,
        optionally followed by (parenthetical).
        Returns deduplicated list of character names.
        """

    def extract_dialogue(self, text: str, character: str) -> list[str]:
        """Extract all dialogue lines for a specific character."""

class FountainDocument(BaseModel):
    scenes: list[FountainScene]
    characters: list[str]

class FountainScene(BaseModel):
    header: str
    characters_present: list[str]
    has_dialogue: dict[str, int]  # character -> line count
```

**Fountain syntax quick reference:**
- Scene headers: lines starting with `INT.`, `EXT.`, `INT./EXT.`, `I/E.`
- Character names: ALL CAPS line followed by dialogue
- Action: any line that isn't a scene header, character, or dialogue
- Transitions: lines ending with `TO:` (e.g., `> FADE TO:`)
- Notes: `[[this is a note]]`

---

### Phase 1 Detail: prompt_builder.py

Translates camera configuration into text that gets appended to Eden prompts.

```python
def build_camera_prompt(shot: ShotConfig) -> str:
    """
    Convert camera/lens/stock config into descriptive text.
    Appended to user's scene description when generating via Eden.

    Example output:
    "Shot on ARRI Alexa 35. Panavision C-Series anamorphic lens. 40mm. f/2.8.
     Kodak 5219 (500T) film stock. camera movement: Dolly In."
    """

def build_entity_context(entity: Entity) -> str:
    """
    Build context string from entity data for agent chat enrichment.
    Used when opening an Eden agent session scoped to an entity.

    Example output:
    "Character: Mordecai. The Wizard. Lean, angular, burn scars on palms.
     Threadbare traveling cloak. Brilliant, self-destructive, charming."
    """

def enrich_prompt(base_prompt: str, shot: ShotConfig, entities: list[Entity] = None) -> str:
    """
    Full prompt enrichment pipeline:
    1. Start with user's base prompt
    2. Append camera/lens/stock description
    3. Optionally append character/location context from entities
    """
```

**Note:** This is a text-based bridge. Eden doesn't have native camera controls. When/if Higgsfield opens an API, the `ShotConfig` maps directly to their native parameters instead of prompt text.

---

### Phase 1 Detail: kozmo_routes.py

FastAPI router. All endpoints under `/kozmo/` prefix.

```python
from fastapi import APIRouter, HTTPException
kozmo_router = APIRouter(tags=["kozmo"])

# --- Projects ---
@kozmo_router.get("/projects")
@kozmo_router.post("/projects")
@kozmo_router.get("/projects/{slug}")
@kozmo_router.delete("/projects/{slug}")

# --- Entities ---
@kozmo_router.get("/projects/{slug}/entities")
@kozmo_router.get("/projects/{slug}/entities/{entity_type}")
@kozmo_router.get("/projects/{slug}/entities/{entity_type}/{entity_id}")
@kozmo_router.post("/projects/{slug}/entities/{entity_type}")
@kozmo_router.put("/projects/{slug}/entities/{entity_type}/{entity_id}")
@kozmo_router.delete("/projects/{slug}/entities/{entity_type}/{entity_id}")

# --- Templates ---
@kozmo_router.get("/projects/{slug}/templates/{entity_type}")

# --- Graph ---
@kozmo_router.get("/projects/{slug}/graph")
@kozmo_router.get("/projects/{slug}/graph/{entity_id}")
@kozmo_router.post("/projects/{slug}/graph")

# --- Screenplay ---
@kozmo_router.get("/projects/{slug}/screenplay")
@kozmo_router.get("/projects/{slug}/screenplay/{scene_id}")

# --- Shots ---
@kozmo_router.get("/projects/{slug}/shots")
@kozmo_router.get("/projects/{slug}/shots/{scene_id}")
@kozmo_router.put("/projects/{slug}/shots/{shot_id}")

# --- Agent Dispatch ---
@kozmo_router.post("/dispatch")
@kozmo_router.get("/queue")
@kozmo_router.get("/queue/{task_id}")

# --- Eden Sessions ---
@kozmo_router.post("/session/create")
@kozmo_router.post("/session/{session_id}/message")
@kozmo_router.get("/session/{session_id}")

# --- Search ---
@kozmo_router.get("/projects/{slug}/search")

# --- Context ---
@kozmo_router.get("/projects/{slug}/context/{entity_id}")
@kozmo_router.get("/projects/{slug}/continuity")
```

**Mount in server.py:**
```python
from luna.api.kozmo_routes import kozmo_router
app.include_router(kozmo_router, prefix="/kozmo")
```

---

### Phase 2: Frontend — Wire CODEX + LAB to Backend

**Goal:** Replace placeholder components with real data from the KOZMO API.

| Task | File | What |
|------|------|------|
| Project loader | `KozmoProvider.jsx` | On mount, call `GET /kozmo/projects`, populate project list |
| Entity file tree | `codex/FileTree.jsx` | NEW — reads entity list, groups by type, renders tree |
| Entity card | `codex/EntityCard.jsx` | NEW — tabbed card (overview, details, scenes, refs) from entity data |
| Relationship badges | `codex/RelationshipBadge.jsx` | NEW — clickable badges that navigate to related entities |
| Shot card | `lab/ShotCard.jsx` | NEW — hero frame thumbnail + camera info strip |
| Camera controls | `lab/CameraControls.jsx` | NEW — dropdowns/knobs for camera body, lens, focal, aperture, movement |
| Post controls | `lab/PostControls.jsx` | NEW — film stock, color temp, grain, bloom, halation |
| Hero frame canvas | `lab/HeroFrameCanvas.jsx` | NEW — 21:9 frame with viewfinder overlay, rule of thirds |
| Timeline | `lab/Timeline.jsx` | NEW — proportional shot blocks with status colors |
| Agent panel | `shared/AgentPanel.jsx` | EXTRACT from CODEX inline `AgentRosterMini` |
| Agent chat | `shared/AgentChat.jsx` | NEW — Luna + Eden chat interface scoped to selected entity |
| Generation queue | `shared/GenerationQueue.jsx` | NEW — task list with polling status indicators |
| Wire hooks | `hooks/*.js` | Connect stubs to real `/kozmo/*` endpoints |

**Prototype artifacts to reference:** The Claude project files contain full React prototypes for both CODEX (`kozmo_codex.jsx`) and LAB (`kozmo_studio.jsx`). These are the design targets. Port the interaction patterns but use real API data instead of mock state.

---

### Phase 3: Agent Dispatch Pipeline

**Goal:** Wire Eden generation through KOZMO's dispatch system.

**Flow:**
```
User clicks "Generate Ref Art" for Mordecai
    │
    ▼
Frontend: POST /kozmo/dispatch
    { action: "generate_image", entity: "mordecai", project: "dwm" }
    │
    ▼
Backend (kozmo_routes.py):
    1. Read mordecai.yaml → build entity context
    2. Read shot config (if from LAB) → build camera prompt
    3. Call prompt_builder.enrich_prompt()
    4. Call eden_adapter.create_image(enriched_prompt)
    5. Return { task_id, status: "pending" }
    │
    ▼
Frontend: polls GET /kozmo/queue/{task_id} every 2s
    │
    ▼
Backend: polls eden_adapter.poll_task(task_id)
    When complete:
    1. Download result image URL
    2. Save to assets/reference/ or assets/hero_frames/
    3. Update entity YAML (add to references.images)
    4. Return { status: "completed", result_url, saved_path }
```

**Eden session bridge for entity chat:**
```
User clicks "Chat with Maya" for Mordecai
    │
    ▼
POST /kozmo/session/create
    { agent: "maya", entity: "mordecai", project: "dwm" }
    │
    ▼
Backend:
    1. Read mordecai.yaml → build_entity_context()
    2. eden_adapter.create_session(agent_ids=[maya], content=context)
    3. Return { session_id }
    │
    ▼
Frontend: opens chat panel
    User: "Make his staff gnarled and cracked with faint glow lines"
    │
    ▼
POST /kozmo/session/{session_id}/message
    { content: "Make his staff..." }
    │
    ▼
Backend:
    1. eden_adapter.send_message(session_id, content)
    2. Poll for agent response
    3. If response contains image → save to assets/reference/
    4. Return { response, attachments }
```

---

### Phase 4: Graph View (V2 → V4)

See `ARCHITECTURE_KOZMO.md` § 8 for the full roadmap. Implementation order:

**V2 — Force-directed graph:**
- Add `d3` and `d3-force` to `package.json`
- Create `codex/GraphView.jsx`
- Read graph data from `GET /kozmo/projects/{slug}/graph`
- D3 force simulation with entity nodes + relationship edges
- ~200-300 lines

**V3 — Interaction layer:**
- Zoom/pan (`d3-zoom`)
- Type clustering (grouped force parameters)
- Search highlighting
- Click-to-navigate (node click → `selectEntity()`)
- Edge labels on hover
- Minimap

**V4 — Intelligence layer:**
- `GET /kozmo/projects/{slug}/graph/{entity_id}` with `?inferred=true`
- Dotted lines for Luna-inferred edges
- Promote-to-explicit button (writes to `graph.yaml`)
- Semantic clustering (backend computes 2D projection from embeddings)
- Contextual subgraphs (depth slider, fade non-relevant nodes)
- Continuity overlay (red edges for detected breaks)

---

### Phase 5: Continuity Engine

**Goal:** Luna analyzes project data to surface inconsistencies.

- Parse Fountain screenplay → extract character appearances per scene
- Cross-reference with entity YAML (props, wardrobe by context)
- Flag: "Mordecai's staff appears in Scene 3 but first_appearance is Scene 5"
- Flag: "Constance is in scene_01 but not listed in cornelius.yaml relationships"
- Expose via `GET /kozmo/projects/{slug}/continuity`
- Display as warnings in CODEX entity cards and LAB shot cards

---

## FILE MAP (complete)

### Already Exists

| File | Phase | Purpose |
|------|-------|---------|
| `Tools/KOZMO-Prototype-V1/package.json` | — | Vite + React + Tailwind |
| `Tools/KOZMO-Prototype-V1/vite.config.js` | — | Dev server :5174, proxy to :8000 |
| `Tools/KOZMO-Prototype-V1/tailwind.config.js` | — | KOZMO color system |
| `Tools/KOZMO-Prototype-V1/index.html` | — | Entry HTML + Google Fonts |
| `Tools/KOZMO-Prototype-V1/src/main.jsx` | — | React entry point |
| `Tools/KOZMO-Prototype-V1/src/App.jsx` | — | Root — CODEX/LAB switcher |
| `Tools/KOZMO-Prototype-V1/src/KozmoProvider.jsx` | — | React context |
| `Tools/KOZMO-Prototype-V1/src/index.css` | — | Tailwind + glass-panel |
| `Tools/KOZMO-Prototype-V1/src/codex/KozmoCodex.jsx` | — | CODEX 3-panel layout |
| `Tools/KOZMO-Prototype-V1/src/lab/KozmoLab.jsx` | — | LAB 3-panel + timeline |
| `Tools/KOZMO-Prototype-V1/src/hooks/useKozmoProject.js` | — | Project API hook (stubs) |
| `Tools/KOZMO-Prototype-V1/src/hooks/useEdenAdapter.js` | — | Eden API hook (stubs) |
| `Tools/KOZMO-Prototype-V1/src/hooks/useAgentDispatch.js` | — | Queue lifecycle hook (stubs) |
| `Tools/KOZMO-Prototype-V1/src/hooks/useLunaAPI.js` | — | Luna health hook |
| `Tools/KOZMO-Prototype-V1/src/config/cameras.js` | — | Camera system + prompt builder |
| `Tools/KOZMO-Prototype-V1/src/shared/index.js` | — | Shared barrel (stubs) |
| `Tools/KOZMO-Prototype-V1/README.md` | — | Project docs |
| `Docs/ARCHITECTURE_KOZMO.md` | — | System architecture |
| `src/luna/services/eden/*` | Eden | Full Eden adapter (78 tests) |

### To Create — Phase 1 (Backend)

| File | Purpose |
|------|---------|
| `src/luna/services/kozmo/__init__.py` | Package exports |
| `src/luna/services/kozmo/types.py` | Pydantic models |
| `src/luna/services/kozmo/project.py` | Project CRUD, YAML parse |
| `src/luna/services/kozmo/entity.py` | Entity ops, template validation |
| `src/luna/services/kozmo/graph.py` | Per-project graph DB |
| `src/luna/services/kozmo/fountain.py` | Fountain parser |
| `src/luna/services/kozmo/prompt_builder.py` | Camera → prompt text |
| `src/luna/api/kozmo_routes.py` | FastAPI /kozmo/* endpoints |
| `config/kozmo_cameras.yaml` | Camera presets (backend) |
| `data/projects/.gitkeep` | Default projects directory |
| `tests/test_kozmo_project.py` | Project tests |
| `tests/test_kozmo_entity.py` | Entity tests |
| `tests/test_kozmo_graph.py` | Graph tests |
| `tests/test_kozmo_fountain.py` | Fountain parser tests |
| `tests/test_kozmo_routes.py` | API tests |

### To Create — Phase 2 (Frontend)

| File | Purpose |
|------|---------|
| `src/codex/FileTree.jsx` | Entity browser by type |
| `src/codex/EntityCard.jsx` | Tabbed entity viewer |
| `src/codex/RelationshipBadge.jsx` | Clickable relationship links |
| `src/codex/RelationshipMap.jsx` | Mini graph below entity card |
| `src/lab/ShotCard.jsx` | Shot preview + camera strip |
| `src/lab/HeroFrameCanvas.jsx` | 21:9 canvas + viewfinder |
| `src/lab/CameraControls.jsx` | Camera body/lens/focal/aperture |
| `src/lab/PostControls.jsx` | Film stock/grade/grain |
| `src/lab/Timeline.jsx` | Proportional shot blocks |
| `src/shared/AgentPanel.jsx` | Agent roster with status |
| `src/shared/AgentChat.jsx` | Entity-scoped chat |
| `src/shared/GenerationQueue.jsx` | Task queue display |
| `src/shared/ProjectHeader.jsx` | Project name + settings |
| `src/shared/EdenStatus.jsx` | Eden connection indicator |

### To Create — Phase 4 (Graph)

| File | Purpose |
|------|---------|
| `src/codex/GraphView.jsx` | D3 force-directed graph (V2-V4) |

### To Modify

| File | Change |
|------|--------|
| `src/luna/api/server.py` | Mount kozmo_router |
| `src/luna/engine.py` | Optional _init_kozmo() |
| `KozmoProvider.jsx` | Wire to real API data |
| `hooks/*.js` | Replace stubs with live fetches |

---

## DESIGN DECISIONS

| # | Decision | Chose | Over | Because |
|---|----------|-------|------|---------|
| 1 | YAML source of truth | YAML files on disk | SQLite-only | Git-trackable, human-editable, portable, writers actually open these |
| 2 | Project isolation | Separate DB per project | Shared Memory Matrix | Creative content ≠ Luna's personal memory. Must never cross-pollinate. |
| 3 | Per-project graph | Same tech as Memory Matrix | Different DB engine | Reuse embedding + search code. Just a different .db file. |
| 4 | Camera via prompt text | Descriptive text appended to prompts | Native camera API | Eden has no camera controls. Higgsfield API doesn't exist yet. Text is the bridge. |
| 5 | Fountain screenplay | .fountain files | Markdown | Industry standard, parseable, git-friendly, tools already exist |
| 6 | Templates as YAML | `_template.yaml` per type dir | Hardcoded schemas | User and Luna can customize per-project |
| 7 | Adapter over SDK (Eden) | Python httpx adapter | Eden JS SDK | SDK is JS-only, beta. httpx gives retry control + KOZMO extensions. Already built. |
| 8 | KOZMO standalone-capable | Own Vite app, embeddable | Tight Eclissi integration | Can extract without refactoring. KozmoProvider is the only coupling point. |
| 9 | Chat over forms (agents) | Natural language dispatch | Structured action buttons | More flexible, Luna interprets intent, all actions visible in chat trail |
| 10 | Graph DB rebuild from YAML | Derived index, rebuildable | DB as source | YAML is portable truth. DB is a cache. `reindex_all()` rebuilds from files. |

---

## DEPENDENCIES

**Backend (add to requirements):**
- `pyyaml` — YAML parsing (likely already present)
- No other new deps — uses existing httpx, pydantic, aiosqlite, FastAPI

**Frontend (add to package.json in Phase 4):**
- `d3` — force-directed graph
- `d3-force` — physics simulation
- `d3-zoom` — pan/zoom interactions

---

## RUNNING THE STACK

```bash
# Terminal 1: Luna Engine backend
cd _LunaEngine_BetaProject_V2.0_Root
python -m luna.api.server
# → http://localhost:8000

# Terminal 2: KOZMO frontend (standalone)
cd Tools/KOZMO-Prototype-V1
npm install
npm run dev
# → http://localhost:5174

# Terminal 3: Eclissi frontend (if embedding KOZMO)
cd frontend
npm run dev
# → http://localhost:5173
```

---

## TEST STRATEGY

Follow Eden pattern: mock HTTP in unit tests, live validation as a separate step.

**Phase 1 tests:**
- `test_kozmo_project.py` — create/list/load/delete projects, YAML round-trip
- `test_kozmo_entity.py` — parse entity YAML, validate against template, slug generation
- `test_kozmo_graph.py` — index entity, search, neighbor traversal, isolation (not in Memory Matrix)
- `test_kozmo_fountain.py` — extract scene headers, characters, dialogue from sample .fountain text
- `test_kozmo_routes.py` — FastAPI TestClient against all endpoints

**Sample test data:** Create a `tests/fixtures/sample_project/` with:
- `project.yaml`
- `characters/mordecai.yaml`, `characters/cornelius.yaml`
- `locations/crooked_nail.yaml`
- `props/mordecai_staff.yaml`
- `screenplay/act_1/scene_01_departure.fountain`
- `shots/scene_01/sh001_establishing.yaml`
- `graph.yaml`

---

## CRITICAL CONSTRAINTS

1. **Project data NEVER enters Luna's personal Memory Matrix.** Luna reads project files via the KOZMO service layer. She stores only high-level metadata about projects in her own memory ("Ahab has a project called DWM").

2. **YAML is source of truth.** The project graph DB is a derived index. It must be rebuildable from YAML files via `reindex_all()`. If they diverge, YAML wins.

3. **Camera config is text, not native.** Until a platform offers native camera controls via API, camera metadata is translated to descriptive prompt text. The `ShotConfig` → `CameraConfig` structure is designed so it can map to native controls later.

4. **Max 3 camera movements per shot.** Enforced in the `CameraConfig` model and the frontend UI.

5. **KOZMO is standalone-capable.** No imports from Eclissi's component tree. KozmoProvider is the only integration point.

---

## CLARIFICATIONS (Luna Review, 2026-02-11)

These came out of Luna's review of the handoff. Address before implementation starts.

### C1. entity.py vs project.py — ownership boundary

`project.py` lists entity CRUD methods (`get_entities`, `get_entity`, `save_entity`, `create_entity`). The file map also lists `entity.py` as "Entity CRUD — parse YAML, validate against templates." That's ambiguous — a builder won't know which file owns what.

**Resolution:** Split by concern, not by operation.

- **`project.py`** — project-level orchestration. Knows about the filesystem, project root, directory structure. Its entity methods are thin wrappers that delegate to `entity.py`:
  ```python
  async def get_entity(self, slug, entity_type, entity_id):
      path = self.root / slug / entity_type / f"{entity_id}.yaml"
      template = await self._load_template(slug, entity_type)
      return entity_service.parse_entity(path, template)
  ```

- **`entity.py`** — entity-level logic. Parsing YAML into `Entity` models, validating against `Template` schemas, slug generation, diffing for change detection:
  ```python
  def parse_entity(path: Path, template: Template = None) -> Entity:
      """Read YAML file → Entity model. Validate against template if provided."""

  def validate_entity(entity: Entity, template: Template) -> list[ValidationWarning]:
      """Check required fields, ref integrity, type constraints."""

  def slugify(name: str) -> str:
      """'Mordecai The Unwise' → 'mordecai_the_unwise'"""

  def entity_to_yaml(entity: Entity) -> str:
      """Entity model → YAML string. Preserves key order, handles luna_notes."""
  ```

`project.py` calls `entity.py`. `entity.py` doesn't know about projects or directories.

---

### C2. YAML sync — external edits and file watching

The whole point of YAML is that writers open and edit these files directly. But if someone edits `mordecai.yaml` in VS Code while KOZMO is running, the project graph DB doesn't know.

**Resolution:** Three strategies, implement in order:

1. **Re-index on project load (required, Phase 1).** Every time `load_project()` is called, run `reindex_all()`. This guarantees the graph matches the files at session start.

2. **Re-index on entity access (required, Phase 1).** When `get_entity()` reads a YAML file, compare its `mtime` against the indexed timestamp. If the file is newer, re-parse and re-index that single entity. Cheap check — one `os.stat()` call.

3. **File watcher for dev mode (optional, Phase 2+).** Use `watchfiles` (already async-compatible, lightweight) to monitor the project directory. On change, re-index the affected entity. This makes KOZMO reactive to external edits in real-time.

```python
# In project.py or graph.py
async def check_freshness(self, entity_type: str, entity_id: str) -> bool:
    """Compare file mtime against indexed timestamp. Re-index if stale."""
    path = self.root / entity_type / f"{entity_id}.yaml"
    file_mtime = path.stat().st_mtime
    indexed_at = await self.graph.get_indexed_timestamp(entity_id)
    if indexed_at is None or file_mtime > indexed_at:
        entity = entity_service.parse_entity(path)
        await self.graph.index_entity(entity)
        return True  # re-indexed
    return False  # still fresh
```

---

### C3. /kozmo/dispatch — split dispatch from result handling

The dispatch endpoint as described does too much: read entity, read shot, enrich prompt, call Eden, poll for completion, download result, save to disk, update YAML. That's a whole pipeline in one request.

**Resolution:** Split into dispatch (fast) and settlement (background).

**Dispatch (synchronous, fast):**
```python
@kozmo_router.post("/dispatch")
async def dispatch_task(request: DispatchRequest):
    """
    1. Read entity/shot context
    2. Build enriched prompt
    3. Call eden_adapter.create_image() with wait=False
    4. Add to in-memory generation queue
    5. Return { task_id, status: 'pending' } immediately
    """
```

**Settlement (background worker):**
```python
async def settle_task(task_id: str, project_slug: str, context: DispatchContext):
    """
    Runs as a background task (FastAPI BackgroundTasks or asyncio.create_task).
    1. Poll eden_adapter.poll_task(task_id) until terminal
    2. On success: download image, save to assets/, update entity YAML
    3. On failure: log error, update queue status
    4. Update in-memory queue entry with result
    """
```

**Queue state:**
```python
# In-memory queue (lives on KozmoProjectService or a dedicated QueueManager)
_generation_queue: dict[str, QueueEntry] = {}

class QueueEntry(BaseModel):
    task_id: str
    eden_task_id: str
    action: str              # generate_image, generate_video, etc.
    status: str              # pending, processing, completed, failed
    project_slug: str
    entity_slug: Optional[str]
    shot_id: Optional[str]
    result_url: Optional[str]
    saved_path: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]
```

The `/kozmo/queue/{task_id}` endpoint just reads from `_generation_queue`. No polling Eden on every frontend request — the background worker handles that.

---

### C4. Graph isolation — explicit negative test

The handoff mentions testing graph isolation but doesn't specify what that test looks like. This is the most important invariant in the system.

**Resolution:** Add this exact test to `test_kozmo_graph.py`:

```python
async def test_project_data_never_enters_personal_memory():
    """
    CRITICAL: Project entities must NEVER appear in Luna's personal
    Memory Matrix. This is the separation principle.
    """
    # 1. Create a project with a unique entity
    project = await service.create_project("Test Project", "test_isolation")
    entity = await service.create_entity("test_isolation", "characters", "Zxyqvort the Unique")

    # 2. Index it in the project graph
    project_graph = ProjectGraph(project_root)
    await project_graph.index_entity(entity)

    # 3. Search the project graph — SHOULD find it
    project_results = await project_graph.search("Zxyqvort")
    assert len(project_results) > 0, "Entity should exist in project graph"

    # 4. Search Luna's personal Memory Matrix — MUST NOT find it
    from luna.substrate.memory_matrix import MemoryMatrix
    personal_matrix = MemoryMatrix(personal_db_path)
    personal_results = await personal_matrix.search("Zxyqvort")
    assert len(personal_results) == 0, "Entity MUST NOT exist in personal memory"
```

Use a deliberately weird name (`Zxyqvort`) so there's zero chance of a false match. This test should run in every CI pass.

---

### C5. YAML error handling — graceful degradation

What happens when a YAML file is malformed, has missing required fields, or references a non-existent entity? The handoff doesn't specify.

**Resolution:** Load what you can, collect warnings, never crash the project.

```python
class EntityLoadResult(BaseModel):
    entity: Optional[Entity]       # None if completely unparseable
    warnings: list[str] = []       # Non-fatal issues
    error: Optional[str] = None    # Fatal parse failure

def parse_entity_safe(path: Path, template: Template = None) -> EntityLoadResult:
    """
    Graceful entity loading.

    Fatal (entity=None):
      - YAML syntax error (invalid YAML)
      - Missing 'name' field (can't identify the entity)

    Warning (entity loaded, warnings populated):
      - Missing optional fields defined in template
      - Relationship references non-existent entity slug
      - Unknown fields not in template (loaded into entity.data anyway)
      - Type mismatch (e.g. age is string instead of int)

    Never fatal:
      - Extra fields beyond template
      - Missing non-required fields
      - Empty sections
    """
```

**Frontend display:** Entities with warnings get a yellow indicator in the file tree. Clicking shows the warnings. Entities that failed to load get a red indicator with the error message.

**Project-level load:** `get_entities()` returns all successfully loaded entities plus a `warnings` summary. One bad YAML file doesn't block the rest of the project.

---

### C6. luna_notes — the write boundary

`luna_notes` is the one field where Luna writes to project data. This is close to the separation principle boundary and needs explicit rules.

**Resolution:** Luna writes `luna_notes` through a dedicated endpoint, not by directly editing YAML.

```python
@kozmo_router.put("/projects/{slug}/entities/{entity_type}/{entity_id}/notes")
async def update_luna_notes(slug: str, entity_type: str, entity_id: str, body: LunaNotesUpdate):
    """
    Append or replace Luna's contextual notes on an entity.
    This is the ONLY place Luna writes to project data.

    The notes are stored in the entity's YAML file under 'luna_notes:'.
    They are clearly separated from user-authored content.
    """
```

**Rules:**
1. Luna NEVER modifies user-authored fields (name, traits, relationships, wardrobe, etc.)
2. Luna ONLY writes to the `luna_notes` field
3. `luna_notes` is always at the bottom of the YAML file, visually separated
4. The user can edit or delete `luna_notes` — Luna's notes are suggestions, not canon
5. Luna's notes are NOT stored in her personal Memory Matrix — they live in the project YAML only

**What goes in luna_notes:**
- Continuity flags: "Staff appears in Scene 3 but isn't established until Scene 5"
- Production gaps: "Zero reference images. No LoRA. In 5 scenes. Priority."
- Context from conversations: "Ahab said addiction is to numbness, not magic itself"
- Relationship inferences: "Thematic mirror with Princess — both hiding"

**What does NOT go in luna_notes:**
- Full conversation transcripts
- Luna's personal feelings about the entity
- System/technical metadata

---

---

## PHASE 6: SCRIBO — The Writer's Room

**Added:** 2026-02-11 (post Phase 1 implementation)
**Status:** DESIGN COMPLETE, PROTOTYPE BUILT — ready for implementation
**Prototype:** Claude project files (`scribo.jsx` artifact)

### What SCRIBO Is

SCRIBO is KOZMO's third mode — the writing surface where stories are authored. CODEX is the reference library, LAB is the production floor, SCRIBO is the writer's room.

```
SCRIBO (write)  ←→  CODEX (know)  ←→  LAB (make)
   │                    │                  │
  story              world              shots
  scenes             entities           frames
  dialogue           relationships      camera
  structure          lore               generation
```

SCRIBO is the hub. You write a scene, Luna surfaces relevant character sheets from CODEX in the sidebar, you describe a shot and it routes to LAB for hero frame generation.

### The .scribo Document Format

Every SCRIBO document uses YAML frontmatter + flexible body. One format, one parser.

```yaml
---
type: scene                              # scene | chapter | act | note | outline
container: ch_01                         # parent container slug
characters_present: [mordecai, cornelius]
location: crooked_nail
time: evening
status: draft                            # idea | draft | revised | polished | locked
tags: [act_1, inciting_incident]
---

The tavern smelled of woodsmoke and regret. Mordecai pushed
through the door, staff clicking against the warped floorboards.

MORDECAI
(dropping into the opposite chair)
You look terrible.

CORNELIUS
(long pause)
Boy.
```

**Format rules:**
- YAML frontmatter is required (delimited by `---`)
- Body content is free-form: prose, Fountain dialogue, or mixed
- Fountain conventions work inline: ALL CAPS = character name, `(parenthetical)`, dialogue follows character
- Files stored as `.scribo` extension in the project's `story/` directory
- One file per scene. Container documents (chapters, acts) can also have body content (summaries, outlines)

### Story Hierarchy

User-defined, nestable containers. Labels are per-project.

```
Project
  └── Container (user-named: "Book", "Season", "Act", "Quest")
       └── Container (nestable: "Chapter", "Episode", "Part")
            └── Scene (the atomic writing unit)
                 └── Beat (optional sub-scene structure)
```

**On disk:**
```
data/kozmo_projects/{slug}/
  story/
    _structure.yaml          # Hierarchy definition + ordering
    act_1/
      _meta.yaml             # Act metadata (title, status, summary)
      ch_01/
        _meta.yaml           # Chapter metadata
        sc_01_crooked_nail.scribo
        sc_02_what_he_left.scribo
        sc_03_staff_remembers.scribo
      ch_02/
        _meta.yaml
        sc_04_first_fix.scribo
        sc_05_cornelius_follows.scribo
    act_2/
      ...
```

**`_structure.yaml`** defines the hierarchy shape and ordering:
```yaml
levels:
  - name: Act
    slug_prefix: act_
  - name: Chapter
    slug_prefix: ch_
  - name: Scene
    slug_prefix: sc_

order:
  - act_1:
    - ch_01: [sc_01, sc_02, sc_03]
    - ch_02: [sc_04, sc_05]
    - ch_03: [sc_06, sc_07]
  - act_2:
    - ch_04: [sc_08, sc_09]
    - ch_05: [sc_10]
  - act_3:
    - ch_06: [sc_11, sc_12]
```

### Pydantic Models (add to types.py)

```python
# =============================================================================
# SCRIBO Models
# =============================================================================


class StoryLevel(BaseModel):
    """Hierarchy level definition."""
    name: str               # "Act", "Chapter", "Scene", etc.
    slug_prefix: str        # "act_", "ch_", "sc_"


class StoryStructure(BaseModel):
    """Project story hierarchy and ordering."""
    levels: List[StoryLevel]
    order: Dict[str, Any]   # Nested dict of slug -> children


class ContainerMeta(BaseModel):
    """Metadata for a story container (act, chapter, etc.)."""
    title: str
    slug: str
    level: str              # Which StoryLevel this is
    status: str = "idea"    # idea | draft | revised | polished | locked
    summary: Optional[str] = None
    word_count: int = 0     # Computed from children
    notes: Optional[str] = None


class ScriboFrontmatter(BaseModel):
    """YAML frontmatter parsed from a .scribo file."""
    type: str = "scene"     # scene | chapter | act | note | outline
    container: Optional[str] = None  # Parent container slug
    characters_present: List[str] = Field(default_factory=list)
    location: Optional[str] = None
    time: Optional[str] = None
    status: str = "draft"
    tags: List[str] = Field(default_factory=list)


class ScriboDocument(BaseModel):
    """A complete SCRIBO document."""
    slug: str               # Filename stem
    path: str               # Relative path from project root
    frontmatter: ScriboFrontmatter
    body: str               # Raw body content (prose + Fountain mixed)
    word_count: int = 0
    luna_notes: List[LunaNote] = Field(default_factory=list)


class LunaNote(BaseModel):
    """Luna's inline annotation on a scene."""
    type: str               # continuity | tone | thematic | production | character
    text: str
    line_ref: Optional[int] = None  # Optional line number reference
    created: Optional[datetime] = None


class StoryTreeNode(BaseModel):
    """Recursive tree node for API responses."""
    id: str
    title: str
    type: str               # Level name or "scene"
    icon: Optional[str] = None
    status: str = "idea"
    word_count: int = 0
    children: List["StoryTreeNode"] = Field(default_factory=list)


StoryTreeNode.model_rebuild()  # Enable self-reference
```

### New Backend Files

| File | Purpose |
|------|---------|  
| `src/luna/services/kozmo/scribo.py` | SCRIBO service — parse/write .scribo files, build story tree, word counts |
| `src/luna/services/kozmo/scribo_parser.py` | .scribo format parser — split frontmatter/body, extract inline Fountain elements |
| `tests/test_kozmo_scribo.py` | SCRIBO tests — parse, write, tree building, word counts, frontmatter validation |

### scribo.py — Service Layer

```python
class ScriboService:
    """
    Manages SCRIBO documents within a KOZMO project.
    .scribo files are source of truth. Story tree is derived.
    """

    def __init__(self, project_root: Path):
        self.root = project_root
        self.story_dir = project_root / "story"

    def get_structure(self) -> StoryStructure:
        """Read _structure.yaml — hierarchy definition + ordering."""

    def save_structure(self, structure: StoryStructure) -> None:
        """Write _structure.yaml. Called when scenes are reordered."""

    def build_story_tree(self) -> StoryTreeNode:
        """
        Walk the story directory and build a recursive tree.
        Computes word counts at every level (sum of children).
        Returns the tree for the frontend story navigator.
        """

    def get_document(self, scene_slug: str) -> ScriboDocument:
        """Read and parse a .scribo file."""

    def save_document(self, doc: ScriboDocument) -> ScriboDocument:
        """
        Write .scribo file back to disk.
        Re-serialize frontmatter + body.
        Update word count.
        Re-index in project graph if characters_present or location changed.
        """

    def create_document(
        self, container_slug: str, title: str,
        doc_type: str = "scene"
    ) -> ScriboDocument:
        """
        Create a new .scribo file with default frontmatter.
        Generate slug from title.
        Add to _structure.yaml ordering.
        """

    def delete_document(self, scene_slug: str) -> bool:
        """Remove .scribo file and update _structure.yaml."""

    def move_document(
        self, scene_slug: str,
        new_container: str, position: int = -1
    ) -> None:
        """Move a scene to a different container. Update _structure.yaml."""

    def create_container(
        self, parent_slug: Optional[str], title: str, level: str
    ) -> ContainerMeta:
        """Create a new container directory with _meta.yaml."""

    def get_container(self, container_slug: str) -> ContainerMeta:
        """Read container _meta.yaml."""

    def list_documents(
        self, container_slug: Optional[str] = None
    ) -> List[ScriboDocument]:
        """List all .scribo documents, optionally filtered by container."""

    def search(self, query: str) -> List[ScriboDocument]:
        """Full-text search across all .scribo body content."""

    def get_word_counts(self) -> Dict[str, int]:
        """Word counts per container and total. Cached after first computation."""

    def extract_characters(self, doc: ScriboDocument) -> List[str]:
        """
        Parse body for Fountain-style character names (ALL CAPS lines).
        Cross-reference with CODEX entities.
        Auto-populate frontmatter.characters_present if empty.
        """

    def get_luna_notes(self, scene_slug: str) -> List[LunaNote]:
        """Read Luna's annotations for a scene."""

    def add_luna_note(
        self, scene_slug: str, note: LunaNote
    ) -> List[LunaNote]:
        """
        Append a Luna note to a scene.
        Same write boundary rules as entity luna_notes (see C6).
        """
```

### scribo_parser.py — Format Parser

```python
def parse_scribo(text: str) -> tuple[ScriboFrontmatter, str]:
    """
    Split a .scribo file into frontmatter + body.
    Frontmatter: YAML between --- delimiters.
    Body: everything after the second ---.
    """

def serialize_scribo(frontmatter: ScriboFrontmatter, body: str) -> str:
    """
    Combine frontmatter + body back into .scribo file format.
    """

def extract_fountain_elements(body: str) -> dict:
    """
    Extract Fountain elements from mixed prose/Fountain body.
    Returns:
      - characters: list of ALL CAPS character names found
      - dialogue_counts: dict of character -> line count
      - scene_headers: list (if INT./EXT. markers present)
      - parentheticals: list of (character, parenthetical) tuples
    """

def word_count(body: str) -> int:
    """
    Word count excluding frontmatter, Fountain character names,
    and parentheticals. Counts prose + dialogue.
    """
```

### New API Endpoints (add to routes.py)

```python
# --- Story Structure ---
@router.get("/projects/{slug}/story")
    # Returns StoryTreeNode (recursive tree)

@router.get("/projects/{slug}/story/structure")
    # Returns StoryStructure (hierarchy definition + ordering)

@router.put("/projects/{slug}/story/structure")
    # Update ordering (drag-and-drop reorder in UI)

# --- Containers ---
@router.post("/projects/{slug}/story/containers")
    # Create a new container (act, chapter, etc.)

@router.get("/projects/{slug}/story/containers/{container_slug}")
    # Get container metadata

@router.put("/projects/{slug}/story/containers/{container_slug}")
    # Update container metadata

# --- Documents ---
@router.get("/projects/{slug}/story/documents")
    # List all documents, optional ?container= filter

@router.get("/projects/{slug}/story/documents/{doc_slug}")
    # Get single document (frontmatter + body)

@router.post("/projects/{slug}/story/documents")
    # Create new document

@router.put("/projects/{slug}/story/documents/{doc_slug}")
    # Update document (frontmatter + body)

@router.delete("/projects/{slug}/story/documents/{doc_slug}")
    # Delete document

@router.post("/projects/{slug}/story/documents/{doc_slug}/move")
    # Move document to different container

# --- Luna Notes (SCRIBO-specific) ---
@router.get("/projects/{slug}/story/documents/{doc_slug}/notes")
    # Get Luna's notes for a scene

@router.post("/projects/{slug}/story/documents/{doc_slug}/notes")
    # Add Luna note (write boundary: only Luna writes here)

# --- Search ---
@router.get("/projects/{slug}/story/search")
    # Full-text search across all .scribo content

# --- Stats ---
@router.get("/projects/{slug}/story/stats")
    # Word counts per container, total, status breakdown
```

### Frontend Files (add to KOZMO-Prototype-V1)

| File | Purpose |
|------|---------|  
| `src/scribo/KozmoScribo.jsx` | SCRIBO main layout — 3-panel (story tree \| editor \| agents+codex) |
| `src/scribo/StoryTree.jsx` | Hierarchical story navigator with drill-in/out |
| `src/scribo/SceneEditor.jsx` | Mixed prose/Fountain writing surface with entity-colored character names |
| `src/scribo/Breadcrumb.jsx` | Position-in-hierarchy breadcrumb navigation |
| `src/scribo/LunaNotesPanel.jsx` | Typed Luna annotations below the writing surface |
| `src/scribo/WordCountBar.jsx` | Bottom bar with scene/project word counts + keyboard shortcuts |
| `src/hooks/useScribo.js` | API hook for story CRUD, tree loading, document operations |
| `src/shared/AgentChat.jsx` | Shared agent chat panel (already planned in Phase 2, SCRIBO uses it) |
| `src/shared/CodexSidebar.jsx` | Entity quick-reference panel filtered by scene context |

### How SCRIBO Connects to CODEX and LAB

**SCRIBO → CODEX:**
- Scene frontmatter `characters_present` links to CODEX entity slugs
- CODEX sidebar auto-filters to show entities in the current scene
- Character names in the editor are highlighted with their CODEX entity color
- Clicking a character name in the editor opens their CODEX card
- `extract_characters()` auto-detects Fountain character names and cross-references CODEX

**SCRIBO → LAB:**
- Scene description text can be sent to LAB as a shot prompt basis
- "Generate shot from this scene" action creates a ShotConfig with:
  - characters_present from frontmatter
  - location from frontmatter
  - prompt from selected prose text
  - camera defaults from project settings
- Luna notes of type `production` surface in LAB shot cards

**SCRIBO → Graph:**
- Scenes are indexed in the project graph as nodes
- Scene → Entity edges created from `characters_present`
- Scene → Location edges from `location` frontmatter
- Scene ordering captured for continuity analysis
- Enables: "Show me all scenes where Mordecai and The Princess interact"

### Agent Integration

**Inline (ambient):**
- Luna can append `luna_notes` to any scene (continuity, tone, thematic, production, character)
- Character name auto-detection: when you type ALL CAPS, SCRIBO checks CODEX and offers autocomplete
- Location auto-detection: if body mentions a known location, suggest adding to frontmatter

**Panel (orchestrated):**
- Agent chat panel (right sidebar, AGENTS tab)
- All agents available: Luna (context), Maya (visual), Chiba (orchestrator), Ben (scribe)
- Agent actions scoped to current scene context
- Team dispatch: "Maya, generate reference art for everyone in this scene" → dispatches to LAB
- Luna continuity check: "Luna, check this scene against the timeline" → flags issues as luna_notes

### Modify Existing Files

| File | Change |
|------|--------|
| `src/luna/services/kozmo/types.py` | Add SCRIBO models (StoryLevel, StoryStructure, ContainerMeta, ScriboFrontmatter, ScriboDocument, LunaNote, StoryTreeNode) |
| `src/luna/services/kozmo/routes.py` | Add ~14 SCRIBO endpoints under `/projects/{slug}/story/*` |
| `src/luna/services/kozmo/project.py` | Add `story/` to default directory creation in `create_project()` |
| `Tools/KOZMO-Prototype-V1/src/App.jsx` | Add SCRIBO mode to the mode switcher (SCRIBO / CODEX / LAB) |
| `Tools/KOZMO-Prototype-V1/src/KozmoProvider.jsx` | Add story tree state, current document state, SCRIBO API methods |

### Test Strategy

**`test_kozmo_scribo.py`:**
- Parse .scribo file → frontmatter + body
- Serialize frontmatter + body → .scribo file (round-trip)
- Malformed frontmatter → graceful error
- Missing frontmatter → default values
- Build story tree from directory structure
- Word count: prose only (exclude character names, parentheticals)
- Character extraction from Fountain dialogue
- Cross-reference extracted characters with CODEX entities
- Create/read/update/delete document
- Move document between containers → _structure.yaml updated
- Luna notes: add, read, delete
- Search across documents

**Sample test fixtures (add to `tests/fixtures/sample_project/story/`):**
- `_structure.yaml`
- `act_1/_meta.yaml`
- `act_1/ch_01/_meta.yaml`
- `act_1/ch_01/sc_01_crooked_nail.scribo`
- `act_1/ch_01/sc_02_what_he_left.scribo`

### Design Decisions

| # | Decision | Chose | Over | Because |
|---|----------|-------|------|---------|  
| 11 | Document format | YAML frontmatter + flexible body (.scribo) | Separate Fountain + Markdown files | Writers mix prose and dialogue. One format, one parser. YAML frontmatter matches KOZMO's lingua franca. |
| 12 | Hierarchy | User-defined nestable containers | Fixed Book→Chapter→Scene | Novelists, showrunners, and game writers all use different structures. Containers are generic and labelable. |
| 13 | Story ordering | `_structure.yaml` manifest | Filename sort order | Drag-and-drop reordering in the UI needs to persist. Filenames shouldn't encode position. |
| 14 | Character detection | Auto-extract from Fountain + cross-ref CODEX | Manual tagging only | Writers shouldn't have to manually tag who's in a scene when the dialogue already says. |
| 15 | Luna notes in .scribo | Stored in document, not separate file | Separate .notes file per scene | Notes travel with the document. One file = one unit. Same principle as entity luna_notes. |

---

---

## PHASE 7: SCRIBO Overlay — Annotation Layer

**Added:** 2026-02-13
**Status:** DESIGN COMPLETE, PROTOTYPE BUILT — ready for implementation
**Prototype:** Claude project files (`scribo_overlay.jsx`)
**Depends on:** Phase 6 (SCRIBO base)

### What the Overlay Is

A transparent annotation layer that floats on top of SCRIBO's writing surface. Has anchor points that pin to specific paragraphs. From those anchors, you can attach notes, comments, continuity flags, agent tasks, and LAB production actions. The overlay bridges SCRIBO → LAB by allowing production planning inline with the writing.

```
Writing Surface (text)
    │
    ├── Overlay Layer (toggle: OFF / PINS / FULL)
    │     ├── Anchor Point → paragraph p3
    │     │     ├── Luna note (continuity)
    │     │     └── LAB action (establishing shot)
    │     ├── Anchor Point → paragraph p5
    │     │     ├── User note (visual detail)
    │     │     └── Agent task (Maya: reference art)
    │     └── Anchor Point → paragraph p7
    │           └── LAB action (shot sequence, 4 shots)
    │
    └── Action Plan Sidebar (aggregated view)
```

### Overlay Visibility Modes

Three modes, toggled from the top bar:

| Mode | Behavior |
|------|----------|
| **OFF** | Clean writing surface. No overlay elements visible. |
| **PINS** | Small gutter markers show where annotations exist. Click to peek. |
| **FULL** | Click a pin and all annotations for that paragraph expand inline below the text. |

### Annotation Types

| Type | Icon | Color | Purpose |
|------|------|-------|---------|
| `note` | ✎ | `#fbbf24` (amber) | General writing notes |
| `comment` | 💬 | `#818cf8` (indigo) | Reactions, observations |
| `continuity` | ⚠ | `#f87171` (red) | Flags for inconsistencies |
| `agent` | ◈ | `#34d399` (emerald) | Task dispatch to Maya/Chiba/Ben |
| `action` | ▶ | `#c084fc` (violet) | LAB production actions (image, shot sequence) |
| `luna` | ☾ | `#c084fc` (violet) | Luna's insights and pattern tracking |

### Pydantic Models (add to types.py)

```python
# =============================================================================
# SCRIBO Overlay Models
# =============================================================================


class TextHighlight(BaseModel):
    """Optional text range within a paragraph."""
    start: int              # Character offset start
    end: int                # Character offset end


class LabAction(BaseModel):
    """Embedded LAB production action within an annotation."""
    type: str               # generate_image | shot_sequence | generate_video
    status: str             # planning | queued | generating | review | complete
    prompt: Optional[str] = None
    shots: Optional[List[str]] = None       # For shot_sequence type
    entity: Optional[str] = None            # CODEX entity slug
    assignee: Optional[str] = None          # Agent name


class AgentTask(BaseModel):
    """Embedded agent task within an annotation."""
    agent: str              # luna | maya | chiba | ben
    status: str             # pending | processing | complete
    action: str             # generate_reference | continuity_check | etc.
    entity: Optional[str] = None


class Annotation(BaseModel):
    """A single overlay annotation anchored to a paragraph."""
    id: str
    paragraph_id: str       # Anchored to this paragraph
    type: str               # note | comment | continuity | agent | action | luna
    author: str             # "Ahab", "Luna", etc.
    text: str               # Annotation content
    highlight: Optional[TextHighlight] = None  # Optional text range highlight
    resolved: bool = False
    lab_action: Optional[LabAction] = None
    agent_task: Optional[AgentTask] = None
    created_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None


class OverlayState(BaseModel):
    """Complete overlay state for a document."""
    document_slug: str
    annotations: List[Annotation] = Field(default_factory=list)
    mode: str = "pins"      # off | pins | full
    filter_type: str = "all" # all | note | comment | continuity | agent | action | luna
```

### Storage

Annotations are stored per-document as a sidecar file:

```
story/
  act_1/
    ch_01/
      sc_01_crooked_nail.scribo         # The document
      sc_01_crooked_nail.overlay.yaml   # Its annotations
```

**Why sidecar, not embedded in .scribo:**
- Keeps the writing file clean — writers can open .scribo files in any text editor
- Overlay data is structured (YAML list), not prose
- Annotations can be created/deleted without touching the document body
- The .scribo file stays version-control friendly

### New Backend: overlay.py

```python
class OverlayService:
    """Manages annotation overlays for SCRIBO documents."""

    def __init__(self, project_root: Path):
        self.root = project_root

    def get_overlay(self, doc_slug: str) -> OverlayState:
        """Read .overlay.yaml sidecar for a document."""

    def save_overlay(self, state: OverlayState) -> OverlayState:
        """Write .overlay.yaml sidecar."""

    def add_annotation(self, doc_slug: str, annotation: Annotation) -> Annotation:
        """Add annotation to overlay. Generates ID if not provided."""

    def update_annotation(self, doc_slug: str, annotation_id: str, updates: dict) -> Annotation:
        """Update annotation fields (text, status, resolved, etc.)."""

    def delete_annotation(self, doc_slug: str, annotation_id: str) -> bool:
        """Remove annotation from overlay."""

    def resolve_annotation(self, doc_slug: str, annotation_id: str) -> Annotation:
        """Toggle resolved status."""

    def get_annotations_by_type(self, doc_slug: str, ann_type: str) -> List[Annotation]:
        """Filter annotations by type."""

    def get_all_actions(self, project_slug: str) -> List[Annotation]:
        """
        Aggregate all LAB action annotations across all documents.
        Returns annotations with lab_action or agent_task set.
        Used by CODEX Production Board (Phase 9).
        """

    def push_to_lab(self, doc_slug: str, annotation_id: str) -> dict:
        """
        Convert an action annotation to a Production Brief.
        Carries: source text, entity context, prompt, assignee.
        Returns the created brief ID.
        """

    def push_all_actions(self, doc_slug: str) -> List[dict]:
        """Batch push all action annotations from a document to LAB."""
```

### New API Endpoints (add to routes.py)

```python
# --- Overlay ---
@router.get("/projects/{slug}/story/documents/{doc_slug}/overlay")
    # Get overlay state for a document

@router.post("/projects/{slug}/story/documents/{doc_slug}/overlay/annotations")
    # Add new annotation

@router.put("/projects/{slug}/story/documents/{doc_slug}/overlay/annotations/{ann_id}")
    # Update annotation

@router.delete("/projects/{slug}/story/documents/{doc_slug}/overlay/annotations/{ann_id}")
    # Delete annotation

@router.post("/projects/{slug}/story/documents/{doc_slug}/overlay/annotations/{ann_id}/resolve")
    # Toggle resolved

@router.post("/projects/{slug}/story/documents/{doc_slug}/overlay/annotations/{ann_id}/push-to-lab")
    # Convert annotation → Production Brief, push to LAB

@router.post("/projects/{slug}/story/documents/{doc_slug}/overlay/push-all")
    # Batch push all action annotations to LAB

@router.get("/projects/{slug}/overlay/actions")
    # Aggregate all action annotations across all documents (for CODEX board)
```

### Frontend Files

| File | Purpose |
|------|----------|
| `src/scribo/OverlayLayer.jsx` | Overlay container — modes, filter, gutter pins |
| `src/scribo/AnnotationCard.jsx` | Single annotation card with embedded LAB action / agent task |
| `src/scribo/AnnotationCreator.jsx` | New annotation form with type selector |
| `src/scribo/ActionPlanSidebar.jsx` | Aggregated view — tabs: Actions / Issues / Notes / Luna |
| `src/hooks/useOverlay.js` | Overlay state management, API calls |

### Test Strategy

- CRUD: create, read, update, delete annotation
- Overlay sidecar creation on first annotation
- Resolve/unresolve toggle
- Filter by type
- Aggregate actions across documents
- Push single annotation to LAB → creates Production Brief
- Batch push all actions
- Sidecar file not created if no annotations exist
- Malformed sidecar YAML → graceful degradation (empty overlay, not crash)

### Design Decisions

| # | Decision | Chose | Over | Because |
|---|----------|-------|------|---------|  
| 16 | Annotation storage | Sidecar .overlay.yaml file | Embedded in .scribo body | Keeps writing file clean, annotations are structured data not prose |
| 17 | Anchor granularity | Paragraph-level with optional text highlight | Character-level anchoring | Paragraph is stable across edits. Text highlights are optional refinement. |
| 18 | Overlay modes | Three modes (OFF/PINS/FULL) | Always visible or always hidden | Writers need clean mode, reviewers need full context, quick scan needs pins |

---

---

## PHASE 8: LAB Pipeline — Production Queue & Shot Builder

**Added:** 2026-02-13
**Status:** DESIGN COMPLETE, PROTOTYPE BUILT — ready for implementation
**Prototype:** Claude project files (`lab_pipeline.jsx`)
**Depends on:** Phase 7 (Overlay push-to-LAB), Phase 1 (Eden adapter)

### What the LAB Pipeline Is

The LAB receives Production Briefs from SCRIBO annotations (via the overlay) or from the CODEX Production Board. It's the workbench where briefs get rigged with camera settings and dispatched to Eden for generation.

```
SCRIBO annotation
    │  "→ send to LAB"
    ▼
Production Brief (carries source text, entities, location, prompt)
    │
    ▼
LAB Queue (landing zone)
    │
    ├── Single shot → Shot Builder (camera body, lens, focal, aperture, movement, post)
    │                    │
    │                    └── Enriched Prompt → Eden dispatch
    │
    ├── Shot sequence → Sequence Storyboard (grid of shot cards)
    │                    │
    │                    └── Each shot gets independent camera rig
    │
    └── Reference art → Prompt only, no camera rig needed → Eden dispatch
```

### Production Brief Model (add to types.py)

```python
# =============================================================================
# LAB Pipeline Models
# =============================================================================


class CameraRig(BaseModel):
    """Camera configuration for a shot."""
    body: str = "arri_alexa35"          # Camera body ID
    lens: str = "cooke_s7i"             # Lens profile ID
    focal: int = 50                      # Focal length mm
    aperture: float = 2.8                # f-stop
    movement: List[str] = Field(default_factory=lambda: ["static"])  # Max 3
    duration: float = 3.0                # Seconds


class PostConfig(BaseModel):
    """Post-processing configuration."""
    stock: str = "none"                  # Film stock ID
    color_temp: int = 5600               # Kelvin
    grain: int = 0                       # 0-30
    bloom: int = 0                       # 0-30
    halation: int = 0                    # 0-20


class SequenceShot(BaseModel):
    """Individual shot within a sequence brief."""
    id: str
    title: str
    prompt: str
    status: str = "planning"
    camera: CameraRig = Field(default_factory=CameraRig)
    post: PostConfig = Field(default_factory=PostConfig)
    hero_frame: Optional[str] = None     # Path to generated image
    eden_task_id: Optional[str] = None


class ProductionBrief(BaseModel):
    """A production unit in the LAB pipeline."""
    id: str
    type: str                            # single | sequence | reference
    status: str = "planning"             # planning | rigging | queued | generating | review | approved | locked
    priority: str = "medium"             # critical | high | medium | low
    title: str
    prompt: str

    # Source context (from SCRIBO)
    source_scene: Optional[str] = None
    source_annotation_id: Optional[str] = None
    source_paragraph: Optional[str] = None

    # Entity context
    characters: List[str] = Field(default_factory=list)  # CODEX entity slugs
    location: Optional[str] = None
    assignee: Optional[str] = None       # Agent: maya | chiba | luna | ben
    tags: List[str] = Field(default_factory=list)

    # Camera (for single shots)
    camera: Optional[CameraRig] = None
    post: Optional[PostConfig] = None

    # Sequence (for multi-shot briefs)
    shots: Optional[List[SequenceShot]] = None

    # Generation state
    hero_frame: Optional[str] = None
    eden_task_id: Optional[str] = None
    progress: Optional[int] = None       # 0-100 for generating status

    # Dependencies
    dependencies: List[str] = Field(default_factory=list)  # Other brief IDs

    # Discussion
    notes: str = ""
    ai_thread: List[dict] = Field(default_factory=list)  # Chat history

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
```

### Camera/Lens/Stock Registries

Static registries stored as Python dicts in a new file:

```python
# src/luna/services/kozmo/camera_registry.py

CAMERA_BODIES: dict[str, CameraBodyInfo]    # id → name, badge, sensor_size
LENS_PROFILES: dict[str, LensInfo]          # id → name, type, character, focal_range
FILM_STOCKS: dict[str, StockInfo]           # id → name, character, grain_profile
MOVEMENTS: dict[str, MovementInfo]          # id → name, icon, prompt_phrase
```

These are referenced by ID in CameraRig/PostConfig. The prompt builder uses them to enrich the Eden prompt:

```python
def build_enriched_prompt(brief: ProductionBrief) -> str:
    """
    Combine: base prompt + camera body + lens character
    + focal length + film stock + movement description.
    Returns the final prompt string sent to Eden.
    """
```

### Prompt Enrichment Flow

```
User prompt: "Stone cottage at Blackstone Hollow, morning mist, oversized doorframe"
    +
Camera:     "Shot on ARRI Alexa 35."
Lens:       "Cooke S7/i spherical lens, 24mm, f/5.6."
Stock:      "Kodak 5219 500T film stock."
Movement:   "Camera movement: static."
    =
Enriched:   "Stone cottage at Blackstone Hollow, morning mist, oversized doorframe.
             Shot on ARRI Alexa 35. Cooke S7/i spherical lens, 24mm, f/5.6.
             Kodak 5219 500T film stock. Camera movement: static."
```

### New Backend: lab_pipeline.py

```python
class LabPipelineService:
    """Manages the LAB production queue and dispatch."""

    def __init__(self, project_root: Path):
        self.root = project_root
        self.briefs_dir = project_root / "lab" / "briefs"

    # --- Queue Management ---
    def list_briefs(self, status: str = None, assignee: str = None) -> List[ProductionBrief]:
        """List briefs with optional filters."""

    def get_brief(self, brief_id: str) -> ProductionBrief:
        """Get single brief."""

    def create_brief(self, brief: ProductionBrief) -> ProductionBrief:
        """Create new brief. Called by overlay push-to-lab."""

    def update_brief(self, brief_id: str, updates: dict) -> ProductionBrief:
        """Update brief fields (prompt, status, priority, camera, post, etc.)."""

    def delete_brief(self, brief_id: str) -> bool:
        """Remove brief from queue."""

    # --- Camera Rigging ---
    def apply_camera_rig(self, brief_id: str, camera: CameraRig, post: PostConfig) -> ProductionBrief:
        """Apply camera + post settings to a brief or shot."""

    def apply_rig_to_shot(self, brief_id: str, shot_id: str, camera: CameraRig, post: PostConfig) -> SequenceShot:
        """Apply camera rig to individual shot in a sequence."""

    # --- Prompt Building ---
    def build_enriched_prompt(self, brief_id: str, shot_id: str = None) -> str:
        """Build enriched prompt combining base + camera + lens + stock + movement."""

    def preview_prompt(self, brief_id: str, shot_id: str = None) -> str:
        """Preview without dispatching. Returns the enriched prompt string."""

    # --- Eden Dispatch ---
    def dispatch_brief(self, brief_id: str) -> dict:
        """
        Dispatch single-shot brief to Eden.
        1. Build enriched prompt
        2. Call eden_adapter.create_image()
        3. Set status → generating, store eden_task_id
        4. Start background settlement worker
        Returns: { task_id, eden_task_id, status }
        """

    def dispatch_sequence(self, brief_id: str) -> List[dict]:
        """Dispatch all shots in a sequence. Returns task IDs per shot."""

    def dispatch_shot(self, brief_id: str, shot_id: str) -> dict:
        """Dispatch single shot from a sequence."""

    # --- Sequence Management ---
    def add_shot(self, brief_id: str, shot: SequenceShot) -> ProductionBrief:
        """Add shot to sequence."""

    def remove_shot(self, brief_id: str, shot_id: str) -> ProductionBrief:
        """Remove shot from sequence."""

    def reorder_shots(self, brief_id: str, shot_ids: List[str]) -> ProductionBrief:
        """Reorder shots in sequence."""
```

### Storage

Briefs stored as YAML files in the project:

```
data/kozmo_projects/{slug}/
  lab/
    briefs/
      pb_001_blackstone_hollow.yaml
      pb_002_road_north_montage.yaml
      pb_003_cornelius_garden_ref.yaml
    assets/                              # Generated images land here
      pb_001_hero.png
      pb_002_01_low_branch.png
      pb_002_02_narrow_bridge.png
```

### New API Endpoints (add to routes.py)

```python
# --- LAB Pipeline ---
@router.get("/projects/{slug}/lab/briefs")
    # List briefs, optional ?status=&assignee= filters

@router.get("/projects/{slug}/lab/briefs/{brief_id}")
    # Get single brief

@router.post("/projects/{slug}/lab/briefs")
    # Create brief

@router.put("/projects/{slug}/lab/briefs/{brief_id}")
    # Update brief

@router.delete("/projects/{slug}/lab/briefs/{brief_id}")
    # Delete brief

@router.put("/projects/{slug}/lab/briefs/{brief_id}/rig")
    # Apply camera rig + post to brief

@router.get("/projects/{slug}/lab/briefs/{brief_id}/prompt")
    # Preview enriched prompt

@router.post("/projects/{slug}/lab/briefs/{brief_id}/dispatch")
    # Dispatch to Eden

@router.post("/projects/{slug}/lab/briefs/{brief_id}/dispatch-all")
    # Dispatch all shots in sequence

@router.post("/projects/{slug}/lab/briefs/{brief_id}/shots/{shot_id}/dispatch")
    # Dispatch single shot from sequence

@router.put("/projects/{slug}/lab/briefs/{brief_id}/shots/{shot_id}/rig")
    # Apply rig to individual shot

@router.post("/projects/{slug}/lab/briefs/{brief_id}/shots")
    # Add shot to sequence

@router.delete("/projects/{slug}/lab/briefs/{brief_id}/shots/{shot_id}")
    # Remove shot from sequence

@router.put("/projects/{slug}/lab/briefs/{brief_id}/shots/reorder")
    # Reorder shots
```

### Frontend Files

| File | Purpose |
|------|----------|
| `src/lab/LabPipeline.jsx` | Main LAB layout — queue + builder/storyboard |
| `src/lab/ProductionQueue.jsx` | Left panel — brief cards, filters, status indicators |
| `src/lab/ShotBuilder.jsx` | Camera rig controls, viewfinder, enriched prompt preview |
| `src/lab/SequenceStoryboard.jsx` | Grid of shot cards for multi-shot briefs |
| `src/lab/CameraKnob.jsx` | Dropdown selector for camera/lens/stock |
| `src/lab/SliderControl.jsx` | Labeled slider with value display |
| `src/lab/MovementSelector.jsx` | Movement tag selector (max 3) |
| `src/lab/camera_data.js` | Static camera/lens/stock/movement registry |
| `src/hooks/useLabPipeline.js` | Pipeline state management, API calls |

### Test Strategy

- Brief CRUD
- Camera rig application → enriched prompt reflects camera settings
- Prompt enrichment: base + camera + lens + stock + movement assembled correctly
- Sequence: add/remove/reorder shots
- Dispatch: creates Eden task, updates status, stores task ID
- Settlement: background worker polls, downloads, saves to assets/
- Brief from overlay annotation carries source context (scene, paragraph, entities)
- Camera registry lookups (valid body/lens/stock IDs)
- Invalid rig values → validation error (focal length outside lens range, etc.)

### Design Decisions

| # | Decision | Chose | Over | Because |
|---|----------|-------|------|---------|  
| 19 | Brief storage | YAML files in lab/briefs/ | Database table | Consistent with KOZMO's file-first philosophy. Inspectable, versionable. |
| 20 | Prompt enrichment | Append camera metadata as natural language | Structured API params to Eden | Eden works with text prompts. Natural language gives it creative latitude. |
| 21 | Sequence dispatch | Individual shots dispatched independently | Single batched request | Eden processes one image at a time. Independent dispatch allows partial retries. |

---

---

## PHASE 9: CODEX Production Board — Master Planning View

**Added:** 2026-02-13
**Status:** DESIGN COMPLETE, PROTOTYPE BUILT — ready for implementation
**Prototype:** Claude project files (`codex_production_board.jsx`)
**Depends on:** Phase 8 (LAB Pipeline), Phase 7 (Overlay)

### What the Production Board Is

A planning view inside CODEX that aggregates all production briefs across all scenes. The producer's desk. You organize, discuss with AI, set dependencies, adjust priority, then push batches to LAB when ready.

```
SCRIBO (annotate)  →  CODEX Production Board (plan)  →  LAB (rig & generate)
  per-scene              all-scenes aggregated            per-brief execution
  inline notes           group / filter / deps            camera controls
  overlay anchors        AI chat per brief                Eden dispatch
```

**Key distinction from LAB queue:** CODEX is where you strategize and organize. LAB is where you execute. You might spend an hour in CODEX arranging the plan, then push the whole batch to LAB when it's ready.

### This uses existing models

The Production Board reads `ProductionBrief` objects (defined in Phase 8) and `Annotation` objects (defined in Phase 7). No new models needed — it's a view layer over existing data.

### New Features on Existing Models

The ProductionBrief model (Phase 8) already includes the fields the board needs:
- `dependencies: List[str]` — other brief IDs that must complete first
- `ai_thread: List[dict]` — per-brief AI conversation history
- `tags: List[str]` — for grouping/filtering
- `priority: str` — critical / high / medium / low
- `assignee: str` — agent assignment

### Grouping

The board supports grouping briefs by:

| Group By | Key | Color Source |
|----------|-----|-------|
| Act | `brief.act` field | Static palette |
| Status | `brief.status` | STATUS_CONFIG |
| Character | `brief.characters[]` | CODEX entity colors |
| Agent | `brief.assignee` | Agent config |
| Priority | `brief.priority` | PRIORITY_CONFIG |

### Dependency Graph

Briefs can declare dependencies on other briefs:

```python
ProductionBrief(
    id="pb_005",
    title="The Tower — First Reveal",
    dependencies=["pb_002"],  # Can't do tower reveal until road montage is done
)
```

The dependency tab shows:
- **Upstream:** what must complete before this brief can go to LAB
- **Downstream:** what's blocked by this brief
- Blocking warnings when a dependency is incomplete

### AI Chat Per Brief

Each brief has a conversation thread stored in `ai_thread`. Agents are contextual:

- **Luna** — continuity, pattern tracking, ECHO recognition
- **Maya** — visual design, reference art, composition
- **Chiba** — camera language, lens selection, shot planning
- **Ben** — narrative structure, pacing, story placement

The chat is stored on the brief YAML file (same `ai_thread` field). No separate storage needed.

### New Backend: production_board.py

```python
class ProductionBoardService:
    """Aggregation and planning layer over LAB briefs."""

    def __init__(self, project_root: Path, lab_service: LabPipelineService):
        self.lab = lab_service

    def get_board(self, group_by: str = "act", status: str = None) -> dict:
        """
        Get all briefs grouped by the specified field.
        Returns { groups: [{ key, color, briefs }], stats }
        """

    def get_stats(self) -> dict:
        """
        Aggregate stats: total briefs, total shots, by-status breakdown,
        blocking count, unresolved count.
        """

    def check_dependencies(self, brief_id: str) -> dict:
        """
        Check if all dependencies are met.
        Returns { can_proceed: bool, blocking: [...], blocked_by_this: [...] }
        """

    def push_ready_to_lab(self) -> List[str]:
        """
        Push all briefs with status=rigging and met dependencies to LAB.
        Returns list of pushed brief IDs.
        """

    def add_to_thread(self, brief_id: str, role: str, text: str) -> dict:
        """Add a message to a brief's AI thread."""

    def get_thread(self, brief_id: str) -> List[dict]:
        """Get the AI thread for a brief."""

    def bulk_update(self, brief_ids: List[str], updates: dict) -> List[ProductionBrief]:
        """
        Bulk update: set priority, assignee, or status on multiple briefs.
        Used for "select 6 shots, assign all to Chiba" operations.
        """
```

### New API Endpoints (add to routes.py)

```python
# --- Production Board ---
@router.get("/projects/{slug}/board")
    # Get full board state (grouped briefs + stats)
    # Query params: ?group_by=act&status=rigging

@router.get("/projects/{slug}/board/stats")
    # Aggregate statistics

@router.get("/projects/{slug}/board/briefs/{brief_id}/dependencies")
    # Check dependency state for a brief

@router.post("/projects/{slug}/board/push-ready")
    # Push all ready briefs to LAB

@router.post("/projects/{slug}/board/briefs/{brief_id}/thread")
    # Add message to brief's AI thread

@router.get("/projects/{slug}/board/briefs/{brief_id}/thread")
    # Get brief's AI thread

@router.post("/projects/{slug}/board/bulk-update")
    # Bulk update multiple briefs (priority, assignee, status)
```

### Frontend Files

| File | Purpose |
|------|----------|
| `src/codex/ProductionBoard.jsx` | Main board layout — grouped list + detail panel |
| `src/codex/BriefRow.jsx` | Compact brief row with status, priority, indicators |
| `src/codex/GroupHeader.jsx` | Collapsible group header |
| `src/codex/BriefDetail.jsx` | Right panel — details/AI chat/dependencies tabs |
| `src/codex/DependencyGraph.jsx` | Upstream/downstream dependency view |
| `src/codex/AgentChatPanel.jsx` | Per-brief AI conversation (uses shared AgentChat) |
| `src/hooks/useProductionBoard.js` | Board state, grouping, filtering, API calls |

### Test Strategy

- Board aggregation: all briefs from lab/briefs/ appear
- Grouping: by act, status, character, assignee, priority
- Filtering: by status
- Dependency check: upstream blocking detected, downstream listed
- Push-ready: only pushes briefs with met dependencies
- AI thread: add message, retrieve thread
- Bulk update: update N briefs at once
- Stats: correct totals, shot counts, status breakdown

### Design Decisions

| # | Decision | Chose | Over | Because |
|---|----------|-------|------|---------|  
| 22 | Board data source | Reads from LAB brief files, no separate storage | Duplicate database | Single source of truth. Board is a view, not a store. |
| 23 | AI thread storage | Stored on brief YAML (ai_thread field) | Separate conversation DB | Thread is brief-specific. One file = one unit. |
| 24 | Dependency model | Brief-to-brief ID references | Graph-based task DAG | Simple list of IDs covers 95% of cases. DAG is overkill for ~20-50 briefs per project. |

---

## UPDATED OVERVIEW

KOZMO is an AI filmmaking platform with three modes:
- **SCRIBO** — The writer's room: hierarchical story navigation, mixed prose/Fountain editor, annotation overlay, agent collaboration
- **CODEX** — World bible + Production Board: entity management, relationship graphs, master production planning
- **LAB** — Production studio: camera rigging, shot builder, sequence storyboard, Eden dispatch

### Full Data Flow

```
SCRIBO                         CODEX                          LAB
┌─────────────────┐     ┌──────────────────┐      ┌───────────────────┐
│ Write story     │     │ World Bible      │      │ Production Queue  │
│ .scribo files   │     │  entities, lore  │      │  brief cards      │
│                 │     │                  │      │  status filters   │
│ Overlay Layer   │     │ Production Board │      │                   │
│  annotations    │────>│  all briefs      │─────>│ Shot Builder      │
│  notes          │     │  group/filter    │      │  camera rig       │
│  LAB actions    │     │  AI chat/brief   │      │  lens/stock       │
│  agent tasks    │     │  dependencies    │      │  movement         │
│                 │     │  bulk ops        │      │  post processing  │
│ Action Plan     │     │                  │      │                   │
│  sidebar        │     │ Push Ready → LAB │      │ Sequence Board    │
│  batch push     │     │                  │      │  storyboard grid  │
└─────────────────┘     └──────────────────┘      │                   │
                                                  │ Enriched Prompt   │
                                                  │  → Eden dispatch  │
                                                  └───────────────────┘
```

### Phase Summary

| Phase | What | Status |
|-------|------|--------|
| 1 | Backend: types, project, entity, graph, fountain, prompt_builder, routes | ✅ COMPLETE (179 tests) |
| 2 | Frontend: React scaffold, component stubs | Scaffold built |
| 3 | Agent dispatch: Director routing, Eden integration | Eden adapter complete |
| 4 | Graph visualization: V1→V4 progression | Design complete |
| 5 | Continuity engine | Design complete |
| 6 | SCRIBO: writer's room, .scribo format, story tree | Design complete, prototype built |
| 7 | SCRIBO Overlay: annotation layer, anchor points, LAB actions | Design complete, prototype built |
| 8 | LAB Pipeline: production queue, shot builder, camera rig, Eden dispatch | Design complete, prototype built |
| 9 | CODEX Production Board: master planning, AI chat, dependencies | Design complete, prototype built |

### Recommended Build Order for Phases 6-9

1. **Phase 6** (SCRIBO base) — types, parser, service, routes, tests
2. **Phase 7** (Overlay) — overlay service, sidecar files, annotation CRUD
3. **Phase 8** (LAB Pipeline) — brief models, camera registry, prompt builder, queue service
4. **Phase 9** (CODEX Board) — aggregation layer, thin service over LAB briefs

Phases 7-9 can be built concurrently after Phase 6, but the data flows assume 7→8→9 order.

---

*This handoff follows the Eden integration handoff format. See `Docs/eden/HANDOFF_EDEN_INTEGRATION_COMPLETE.md` for the pattern.*
