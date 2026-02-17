# KOZMO Shot Persistence Design

**Date:** 2026-02-11
**Status:** Design Phase (Implementation in Phase 2)
**Purpose:** Define storage layer for LAB shot configurations

---

## Overview

Currently, LAB shots exist only in React `useState` — they vanish on page refresh. This design specifies how to persist shots to disk using YAML files and expose them via REST API.

**Key Constraint:** Shots are **scene-specific**. Each shot belongs to a scene and references its frontmatter (characters, location, time).

---

## File Structure

### Directory Layout

```
project_root/
├── story/
│   ├── acts/
│   ├── chapters/
│   └── scenes/
│       ├── scene_001_opening.scribo
│       └── scene_002_confrontation.scribo
└── shots/
    ├── scene_001_opening/
    │   ├── shot_0001.yaml
    │   ├── shot_0002.yaml
    │   └── shot_0003.yaml
    └── scene_002_confrontation/
        ├── shot_0001.yaml
        └── shot_0002.yaml
```

**Naming Convention:**
- Shot directory: `shots/{scene_slug}/`
- Shot file: `shot_{4-digit-counter}.yaml`
- Example: `shots/scene_001_opening/shot_0001.yaml`

---

## YAML Schema

### Shot Configuration File

```yaml
# shots/scene_001_opening/shot_0001.yaml

# Metadata
id: "shot_0001"
scene_slug: "scene_001_opening"
created_at: "2026-02-11T10:30:00Z"
updated_at: "2026-02-11T10:35:00Z"
status: "draft"  # draft | approved | generated | final

# Shot Configuration (maps to ShotConfig in types.py)
camera:
  angle: "eye_level"
  movement: "static"
  distance: "medium"
  lens: "50mm"
  fps: 24

lighting:
  setup: "natural"
  mood: "soft"
  time_of_day: "golden_hour"

style:
  look: "cinematic"
  color_grade: "warm"
  aspect_ratio: "2.39:1"

# Generated Assets (populated after Eden generation)
assets:
  hero_frame_url: null
  video_url: null
  prompt: null
  generation_id: null
  eden_task_id: null

# User Notes
notes: "Opening shot — establish location and mood"
tags: ["establishing", "wide"]
```

### Field Definitions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | ✓ | Unique shot ID (matches filename) |
| `scene_slug` | string | ✓ | Parent scene slug |
| `created_at` | ISO8601 | ✓ | Creation timestamp |
| `updated_at` | ISO8601 | ✓ | Last modification timestamp |
| `status` | enum | ✓ | `draft`, `approved`, `generated`, `final` |
| `camera` | object | ✓ | Camera settings (angle, movement, distance, lens, fps) |
| `lighting` | object | ✓ | Lighting setup (setup, mood, time_of_day) |
| `style` | object | ✓ | Visual style (look, color_grade, aspect_ratio) |
| `assets` | object | — | Generated assets (populated post-generation) |
| `notes` | string | — | User notes about the shot |
| `tags` | array | — | Categorization tags |

---

## API Routes

### Endpoints

All routes under `/api/kozmo/shots`:

| Method | Endpoint | Description | Status |
|--------|----------|-------------|--------|
| `POST` | `/shots` | Create new shot | 501 (Phase 2) |
| `GET` | `/shots/{scene_slug}` | List all shots for scene | 501 (Phase 2) |
| `GET` | `/shots/{scene_slug}/{shot_id}` | Get specific shot | 501 (Phase 2) |
| `PUT` | `/shots/{scene_slug}/{shot_id}` | Update shot configuration | 501 (Phase 2) |
| `DELETE` | `/shots/{scene_slug}/{shot_id}` | Delete shot | 501 (Phase 2) |
| `POST` | `/shots/{scene_slug}/{shot_id}/generate` | Trigger Eden generation | 501 (Phase 2) |

### Request/Response Examples

#### Create Shot
```http
POST /api/kozmo/shots
Content-Type: application/json

{
  "scene_slug": "scene_001_opening",
  "camera": {
    "angle": "eye_level",
    "movement": "static",
    "distance": "medium",
    "lens": "50mm",
    "fps": 24
  },
  "lighting": {
    "setup": "natural",
    "mood": "soft",
    "time_of_day": "golden_hour"
  },
  "style": {
    "look": "cinematic",
    "color_grade": "warm",
    "aspect_ratio": "2.39:1"
  },
  "notes": "Opening shot"
}
```

**Response:**
```json
{
  "shot_id": "shot_0001",
  "scene_slug": "scene_001_opening",
  "created_at": "2026-02-11T10:30:00Z",
  "status": "draft"
}
```

#### List Shots for Scene
```http
GET /api/kozmo/shots/scene_001_opening
```

**Response:**
```json
{
  "scene_slug": "scene_001_opening",
  "shots": [
    {
      "id": "shot_0001",
      "status": "draft",
      "camera": { "angle": "eye_level", "distance": "medium" },
      "created_at": "2026-02-11T10:30:00Z",
      "notes": "Opening shot"
    },
    {
      "id": "shot_0002",
      "status": "approved",
      "camera": { "angle": "low", "distance": "close_up" },
      "created_at": "2026-02-11T10:35:00Z",
      "notes": "Character reveal"
    }
  ]
}
```

#### Update Shot
```http
PUT /api/kozmo/shots/scene_001_opening/shot_0001
Content-Type: application/json

{
  "camera": {
    "angle": "high",
    "movement": "dolly_in",
    "distance": "wide"
  },
  "status": "approved",
  "notes": "Changed to high angle for dramatic effect"
}
```

#### Delete Shot
```http
DELETE /api/kozmo/shots/scene_001_opening/shot_0001
```

**Response:**
```json
{
  "success": true,
  "message": "Shot shot_0001 deleted"
}
```

---

## Service Layer

### New Module: `src/luna/services/kozmo/shot.py`

```python
"""
Shot persistence service for KOZMO LAB.

Handles CRUD operations for shot configuration YAML files.
"""
from pathlib import Path
from typing import List, Optional
from datetime import datetime
import yaml

from .types import ShotConfig
from .project import ProjectPaths


class ShotService:
    """Manages shot configuration persistence."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.shots_dir = project_root / "shots"
        self.shots_dir.mkdir(parents=True, exist_ok=True)

    def create_shot(self, scene_slug: str, shot_config: ShotConfig) -> dict:
        """
        Create new shot for scene.

        Generates shot ID, creates directory, saves YAML.
        Returns shot metadata.
        """
        # Create scene shots directory
        scene_shots_dir = self.shots_dir / scene_slug
        scene_shots_dir.mkdir(parents=True, exist_ok=True)

        # Generate shot ID (sequential counter)
        existing_shots = sorted(scene_shots_dir.glob("shot_*.yaml"))
        next_num = len(existing_shots) + 1
        shot_id = f"shot_{next_num:04d}"

        # Build shot data
        now = datetime.utcnow().isoformat() + "Z"
        shot_data = {
            "id": shot_id,
            "scene_slug": scene_slug,
            "created_at": now,
            "updated_at": now,
            "status": "draft",
            "camera": shot_config.camera.dict() if hasattr(shot_config.camera, 'dict') else shot_config.camera,
            "lighting": shot_config.lighting.dict() if hasattr(shot_config.lighting, 'dict') else shot_config.lighting,
            "style": shot_config.style.dict() if hasattr(shot_config.style, 'dict') else shot_config.style,
            "assets": {
                "hero_frame_url": None,
                "video_url": None,
                "prompt": None,
                "generation_id": None,
                "eden_task_id": None,
            },
            "notes": getattr(shot_config, 'notes', ''),
            "tags": getattr(shot_config, 'tags', []),
        }

        # Save YAML
        shot_file = scene_shots_dir / f"{shot_id}.yaml"
        with open(shot_file, 'w') as f:
            yaml.safe_dump(shot_data, f, default_flow_style=False, sort_keys=False)

        return {"shot_id": shot_id, "scene_slug": scene_slug, "created_at": now, "status": "draft"}

    def list_shots(self, scene_slug: str) -> List[dict]:
        """List all shots for a scene."""
        scene_shots_dir = self.shots_dir / scene_slug
        if not scene_shots_dir.exists():
            return []

        shots = []
        for shot_file in sorted(scene_shots_dir.glob("shot_*.yaml")):
            with open(shot_file) as f:
                shot_data = yaml.safe_load(f)
                shots.append(shot_data)

        return shots

    def get_shot(self, scene_slug: str, shot_id: str) -> Optional[dict]:
        """Get specific shot configuration."""
        shot_file = self.shots_dir / scene_slug / f"{shot_id}.yaml"
        if not shot_file.exists():
            return None

        with open(shot_file) as f:
            return yaml.safe_load(f)

    def update_shot(self, scene_slug: str, shot_id: str, updates: dict) -> bool:
        """Update shot configuration (partial update)."""
        shot_file = self.shots_dir / scene_slug / f"{shot_id}.yaml"
        if not shot_file.exists():
            return False

        # Load existing
        with open(shot_file) as f:
            shot_data = yaml.safe_load(f)

        # Merge updates
        shot_data.update(updates)
        shot_data["updated_at"] = datetime.utcnow().isoformat() + "Z"

        # Save
        with open(shot_file, 'w') as f:
            yaml.safe_dump(shot_data, f, default_flow_style=False, sort_keys=False)

        return True

    def delete_shot(self, scene_slug: str, shot_id: str) -> bool:
        """Delete shot file."""
        shot_file = self.shots_dir / scene_slug / f"{shot_id}.yaml"
        if not shot_file.exists():
            return False

        shot_file.unlink()

        # Remove empty directory
        scene_shots_dir = self.shots_dir / scene_slug
        if scene_shots_dir.exists() and not list(scene_shots_dir.iterdir()):
            scene_shots_dir.rmdir()

        return True
```

---

## Integration Points

### 1. Route Handlers (`routes.py`)

```python
from .shot import ShotService

@router.post("/shots", tags=["shots"])
async def create_shot(shot_data: dict):
    """Create new shot configuration."""
    service = ShotService(active_project_root)
    result = service.create_shot(shot_data["scene_slug"], shot_data)
    return result

@router.get("/shots/{scene_slug}", tags=["shots"])
async def list_shots(scene_slug: str):
    """List all shots for a scene."""
    service = ShotService(active_project_root)
    shots = service.list_shots(scene_slug)
    return {"scene_slug": scene_slug, "shots": shots}

# ... (get, update, delete endpoints)
```

### 2. Frontend State Migration (LAB)

**Before (ephemeral):**
```javascript
const [shots, setShots] = useState([]);
```

**After (persistent):**
```javascript
const { shots, createShot, updateShot, deleteShot } = useKozmo();

// shots comes from API: GET /shots/{scene_slug}
// createShot calls: POST /shots
// updateShot calls: PUT /shots/{scene_slug}/{shot_id}
// deleteShot calls: DELETE /shots/{scene_slug}/{shot_id}
```

### 3. Prompt Builder Integration

When generating Eden prompt:
```python
shot_data = shot_service.get_shot(scene_slug, shot_id)
scene_data = get_scene_frontmatter(scene_slug)

prompt = prompt_builder.build_shot_prompt(
    shot_config=shot_data,
    scene_frontmatter=scene_data["frontmatter"],
    entities=entities
)
```

---

## Migration Strategy

### Phase 2 Implementation Order

1. **Week 1: Backend**
   - Create `shot.py` service layer
   - Add routes to `routes.py`
   - Add `ShotConfig` type validation
   - Write tests (`test_kozmo_shot.py`)

2. **Week 2: Frontend**
   - Add shot CRUD methods to `KozmoProvider`
   - Update LAB to use persistent shots
   - Add shot list panel in SCRIBO (link to LAB)
   - Add "Generate" button per shot

3. **Week 3: Eden Integration**
   - Wire shot generation to Eden API
   - Store `eden_task_id` in shot YAML
   - Poll for generation completion
   - Update `assets` section with URLs

---

## Testing Checklist

- [ ] Create shot → YAML file appears in correct directory
- [ ] List shots → returns all shots for scene
- [ ] Get shot → returns full shot configuration
- [ ] Update shot → modifies existing YAML, updates timestamp
- [ ] Delete shot → removes YAML file, cleans empty directories
- [ ] Shot counter → sequential IDs (shot_0001, shot_0002, etc.)
- [ ] Invalid scene_slug → returns empty list or 404
- [ ] Concurrent creates → no ID collisions
- [ ] YAML round-trip → save → load → data preserved

---

## Future Enhancements (Phase 3+)

- **Shot Templates**: Preset camera/lighting combos ("Dramatic Close-Up", "Establishing Wide")
- **Shot Thumbnails**: Store preview images in `assets/`
- **Shot Ordering**: Drag-and-drop reorder (add `order` field)
- **Shot Duplication**: Clone existing shot with new ID
- **Shot Tags**: Filter shots by tags ("action", "dialogue", "transition")
- **Scene → LAB Link**: Button in SCRIBO to "Plan shots in LAB"
- **Bulk Operations**: "Generate all shots in scene"

---

## Summary

This design provides a **simple, file-based persistence layer** for LAB shots:

- ✅ YAML storage (human-readable, version-controllable)
- ✅ Scene-scoped organization (`shots/{scene_slug}/`)
- ✅ Sequential shot IDs (shot_0001, shot_0002, ...)
- ✅ Full CRUD API routes
- ✅ Clean service layer abstraction
- ✅ Ready for Eden integration (assets section)

**Next Steps:** Stub routes (Task 5.2) → Wire prompt builder (Task 5.3) → Implement in Phase 2
