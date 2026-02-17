# HANDOFF: Media Pipeline Backfill & Asset Library

**Date:** 2026-02-15
**Priority:** HIGH — current pipeline is broken for existing assets
**Depends on:** Previous KOZMO-MEDIA-INDEX-SPEC.md implementation (partially complete)

---

## SITUATION

The media pipeline implementation from KOZMO-MEDIA-INDEX-SPEC.md was partially completed.
The *forward* path works — new Eden generations will save, register, and sync. But:

1. **3 existing generated images are invisible** — registered nowhere
2. **5 of 7 briefs have data quality issues** — missing fields, duplicates, unparsed prompts
3. **media_library.yaml doesn't exist** — service was built but never seeded
4. **No frontend for asset library or settings** — API routes exist, no UI

The forward pipeline is correct. This handoff is about **backfilling the past and building the UI**.

---

## TASK 1: Brief Cleanup (Data Migration)

### Current Brief Inventory

| ID | Status | Problem |
|----|--------|---------|
| `pb_02f8b779` | review ✓ | **GOOD** — fully migrated, has image, all fields populated |
| `pb_18baca3e` | review | **BAD** — prompt still contains `NOTE: VISUAL 2:45-2:53 —` prefix, missing `source_scene`, `audio_start/end/track_id` |
| `pb_5cc0efb8` | review | **BAD** — same unparsed prompt issue, missing all audio linkage |
| `pb_2a91bfff` | planning | **DUPLICATE** — identical to pb_02f8b779 but no image, no eden_task_id |
| `pb_8c3ae285` | planning | **DUPLICATE** — identical to pb_02f8b779 but no image, no eden_task_id |
| `pb_d234ef3c` | planning | **DUPLICATE** — identical to pb_02f8b779 but no image, no eden_task_id |
| `pb_3acfdce0` | generating | **TEST** — prompt is literally "test prompt", stuck in generating |

### Actions Required

**Step 1: Delete duplicates and test brief**

Delete these 4 YAML files from `data/kozmo_projects/luna-manifesto/lab/briefs/`:
- `pb_2a91bfff.yaml`
- `pb_8c3ae285.yaml`
- `pb_d234ef3c.yaml`
- `pb_3acfdce0.yaml`

**Step 2: Fix pb_18baca3e**

File: `data/kozmo_projects/luna-manifesto/lab/briefs/pb_18baca3e.yaml`

Current prompt:
```
prompt: 'NOTE: VISUAL 2:45-2:53 — Aerial view of terraced farmland — ancient agricultural
  engineering. The soil is rich and dark. Hands planting seeds. Latin American highlands.
  The earth belongs to whoever tends it.'
```

Fix to:
```yaml
prompt: 'Aerial view of terraced farmland — ancient agricultural engineering. The soil is rich and dark. Hands planting seeds. Latin American highlands. The earth belongs to whoever tends it.'
source_scene: sc_18_maria_clara_soil
source_annotation_id: null
audio_start: 165.3
audio_end: 180.7
audio_track_id: at_18
```

The timecode mapping: `2:45 = 165s`, cross-reference with `audio_timeline.yaml` track `at_18` which runs `165.3 → 180.7`.

**Step 3: Fix pb_5cc0efb8**

File: `data/kozmo_projects/luna-manifesto/lab/briefs/pb_5cc0efb8.yaml`

Current prompt:
```
prompt: ' NOTE: VISUAL 0:08-0:16 — A glowing phone screen in darkness showing a chat
  interface. The screen reflects on a face we barely see. Warm blue light. The question
  hangs: what is this?'
```

Fix to:
```yaml
prompt: 'A glowing phone screen in darkness showing a chat interface. The screen reflects on a face we barely see. Warm blue light. The question hangs: what is this?'
source_scene: sc_01_bella_opening
source_annotation_id: null
audio_start: 8.0
audio_end: 16.0
audio_track_id: at_01
```

The timecode mapping: `0:08 = 8s`, falls within `at_01` which runs `0.0 → 15.9`. Using `at_01` since the visual annotation starts at 8s within that track.

---

## TASK 2: Seed media_library.yaml

### What Exists

The `MediaLibraryService` at `src/luna/services/kozmo/media_library.py` is fully implemented.
It reads/writes `{project_root}/media_library.yaml`.
The file **does not exist yet**.

3 images exist on disk:
```
lab/assets/pb_02f8b779.png  (sovereign file icon — 530KB)
lab/assets/pb_18baca3e.png  (terraced farmland)
lab/assets/pb_5cc0efb8.png  (glowing phone screen)
```

### Create Backfill Script

Write a Python script: `scripts/kozmo/backfill_media_library.py`

```python
"""
Backfill media_library.yaml from existing briefs + assets on disk.

Scans lab/briefs/*.yaml for any brief with hero_frame set.
Cross-references with lab/assets/ for file existence.
Creates media_library.yaml entries for each.

Usage:
  python scripts/kozmo/backfill_media_library.py luna-manifesto
"""
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

from luna.services.kozmo.media_library import MediaLibraryService
from luna.services.kozmo.lab_pipeline import LabPipelineService

def backfill(project_slug: str):
    project_root = ROOT / "data" / "kozmo_projects" / project_slug
    lab = LabPipelineService(project_root)
    media = MediaLibraryService(project_root)
    
    briefs = lab.list_briefs()
    registered = 0
    
    for brief in briefs:
        if not brief.hero_frame:
            continue
        
        # Check file exists
        asset_path = project_root / brief.hero_frame
        if not asset_path.exists():
            print(f"  SKIP {brief.id} — hero_frame points to missing file: {brief.hero_frame}")
            continue
        
        # Check not already registered
        existing = media.list_assets(brief_id=brief.id)
        if existing:
            print(f"  SKIP {brief.id} — already in library")
            continue
        
        # Register
        filename = Path(brief.hero_frame).name
        asset = media.register_asset(
            filename=filename,
            path=brief.hero_frame,
            source="eden",
            brief_id=brief.id,
            scene_slug=brief.source_scene,
            audio_track_id=brief.audio_track_id,
            audio_start=brief.audio_start,
            audio_end=brief.audio_end,
            eden_task_id=brief.eden_task_id,
            prompt=brief.prompt,
        )
        print(f"  ✓ Registered {asset.id} ← {brief.id} ({filename})")
        registered += 1
    
    print(f"\nDone. Registered {registered} assets.")
    print(f"Library: {media.index_path}")

if __name__ == "__main__":
    slug = sys.argv[1] if len(sys.argv) > 1 else "luna-manifesto"
    backfill(slug)
```

### Expected Output

After running (post brief-cleanup), `media_library.yaml` should contain 3 entries:

```yaml
- id: asset_XXXXXXXX
  type: image
  filename: pb_02f8b779.png
  path: lab/assets/pb_02f8b779.png
  source: eden
  brief_id: pb_02f8b779
  scene_slug: sc_09_bella_im_a_file
  audio_track_id: at_09
  audio_start: 79.0
  audio_end: 87.0
  eden_task_id: 6992069aed7cf40bea54928f
  prompt: "A single file icon, luminous, floating in dark space..."
  status: generated
  tags: []
  created_at: "2026-02-15T..."

- id: asset_YYYYYYYY
  type: image
  filename: pb_18baca3e.png
  path: lab/assets/pb_18baca3e.png
  source: eden
  brief_id: pb_18baca3e
  scene_slug: sc_18_maria_clara_soil
  audio_track_id: at_18
  audio_start: 165.3
  audio_end: 180.7
  eden_task_id: 699132a6ed7cf40bea548ab6
  prompt: "Aerial view of terraced farmland..."
  status: generated
  tags: []

- id: asset_ZZZZZZZZ
  type: image
  filename: pb_5cc0efb8.png
  path: lab/assets/pb_5cc0efb8.png
  source: eden
  brief_id: pb_5cc0efb8
  scene_slug: sc_01_bella_opening
  audio_track_id: at_01
  audio_start: 8.0
  audio_end: 16.0
  eden_task_id: 699132f5ed7cf40bea548ab8
  prompt: "A glowing phone screen in darkness..."
  status: generated
  tags: []
```

---

## TASK 3: media_sync_path in Settings

### What Exists (Backend)

- `ProjectSettings` in `types.py:29` has `media_sync_path: Optional[str] = None`
- `PUT /projects/{slug}/settings` route at `routes.py:283` — **verify this exists and works**
- `_sync_to_media_dir()` in `lab_pipeline.py:78-94` — reads from manifest settings, copies files

### What's Missing (Frontend)

The manifest currently has no `media_sync_path`:

```yaml
# data/kozmo_projects/luna-manifesto/manifest.yaml
settings:
  default_camera: arri_alexa35
  default_lens: cooke_s7i
  default_film_stock: kodak_5219
  aspect_ratio: '21:9'
  # media_sync_path is ABSENT
```

### Required: Settings Panel in Frontend

Add a `ProjectSettings` component accessible from the Kozmo layout. Minimal implementation:

**Location:** `frontend/src/kozmo/settings/ProjectSettings.jsx`

**Fields:**
- `media_sync_path` — text input with file path
- `default_camera` — dropdown (existing camera bodies)
- `default_lens` — dropdown (existing lens profiles)
- `default_film_stock` — dropdown (existing stocks)
- `aspect_ratio` — dropdown (16:9, 21:9, 2.39:1, 4:3)

**API call:** `PUT /kozmo/projects/${slug}/settings` with body `{ media_sync_path: "..." }`

**Target sync path for Luna Manifesto:**
```
/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/Docs/Design/Development/Media
```

**Integration:** Add a "Settings" tab or gear icon to the Kozmo top nav alongside SCRIBO, CODEX, LAB, TIMELINE.

---

## TASK 4: Asset Library in Codex

### What Exists (Backend)

Routes already implemented in `routes.py:2215-2290`:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/projects/{slug}/media` | GET | List all assets (filter by type, scene, brief, status, tag) |
| `/projects/{slug}/media/{id}` | GET | Get single asset |
| `/projects/{slug}/media/scene/{doc_slug}` | GET | Assets by scene |
| `/projects/{slug}/media/brief/{brief_id}` | GET | Assets by brief |
| `/projects/{slug}/media/{id}` | PUT | Update status/tags |

### What's Missing (Frontend)

No component exists. The Codex (`KozmoCodex.jsx`) currently has: FileTree, EntityCard, Agent Center, Relationship Map.

### Required: MediaLibrary Panel

**Location:** `frontend/src/kozmo/codex/MediaLibrary.jsx`

**Design:** Grid of asset cards with:
- Thumbnail (served via `/kozmo/projects/${slug}/assets/${path}`)
- Brief ID, scene, voice, timecode
- Status badge (generated → approved → synced → archived)
- Status change buttons (Approve / Sync / Archive)
- Tag editor
- Filter bar (by status, by scene, by voice)

**Integration options (pick one):**
1. New tab in Codex alongside entity browser
2. Panel in LAB alongside the brief queue
3. Standalone panel accessible from Kozmo nav

Recommendation: **Tab in Codex** — entities and assets are both world-state. The Codex is the world bible. Assets belong there.

### heroUrl Helper

The helper already exists in `LabPipeline.jsx:17-20`:
```javascript
const heroUrl = (heroFrame, slug) => {
  if (!heroFrame) return heroFrame;
  if (heroFrame.startsWith('http')) return heroFrame;
  return slug ? `/kozmo/projects/${slug}/assets/${heroFrame}` : heroFrame;
};
```

Extract this to a shared utility: `frontend/src/kozmo/utils/heroUrl.js`

Use it in both LabPipeline and the new MediaLibrary component.

---

## TASK 5: Backfill Sync to External Media Dir

After Tasks 1-3 are complete, run a one-time sync of existing assets:

```python
"""One-time sync of existing assets to external media dir."""
import shutil
from pathlib import Path

PROJECT = Path("data/kozmo_projects/luna-manifesto")
SYNC_DIR = Path("/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/Docs/Design/Development/Media")

SYNC_DIR.mkdir(parents=True, exist_ok=True)

# Map of brief_id → (scene_slug, asset_filename)
ASSETS = {
    "pb_02f8b779": ("sc_09_bella_im_a_file", "pb_02f8b779.png"),
    "pb_18baca3e": ("sc_18_maria_clara_soil", "pb_18baca3e.png"),
    "pb_5cc0efb8": ("sc_01_bella_opening", "pb_5cc0efb8.png"),
}

for brief_id, (scene, filename) in ASSETS.items():
    src = PROJECT / "lab" / "assets" / filename
    dst = SYNC_DIR / f"{scene}_{brief_id}.png"
    if src.exists():
        shutil.copy2(src, dst)
        print(f"  ✓ {dst.name}")
    else:
        print(f"  ✗ Missing: {src}")
```

---

## EXECUTION ORDER

```
1. Delete 4 bad briefs (pb_2a91bfff, pb_8c3ae285, pb_d234ef3c, pb_3acfdce0)
2. Fix pb_18baca3e YAML (parse prompt, add audio fields)
3. Fix pb_5cc0efb8 YAML (parse prompt, add audio fields)
4. Set media_sync_path in manifest.yaml
5. Run backfill_media_library.py → creates media_library.yaml
6. Run sync script → copies 3 images to external Media dir
7. Build ProjectSettings.jsx → wire to PUT /settings
8. Build MediaLibrary.jsx → wire to GET/PUT /media endpoints
9. Extract heroUrl to shared utility
```

Steps 1-6 are data fixes (~15 min).
Steps 7-9 are frontend work (~2-3 hours).

---

## VERIFICATION

After all tasks:

- [ ] `ls data/kozmo_projects/luna-manifesto/lab/briefs/` → exactly 3 files (pb_02f8b779, pb_18baca3e, pb_5cc0efb8)
- [ ] All 3 briefs have `source_scene`, `audio_start`, `audio_end`, `audio_track_id` populated
- [ ] No brief prompts contain `NOTE: VISUAL` or `[[VISUAL` prefix text
- [ ] `media_library.yaml` exists with 3 entries
- [ ] Each media entry has `brief_id`, `scene_slug`, `audio_track_id`, `prompt` populated
- [ ] `manifest.yaml` has `media_sync_path` under settings
- [ ] External Media dir contains 3 PNG files with `{scene}_{brief_id}.png` naming
- [ ] `GET /kozmo/projects/luna-manifesto/media` returns 3 assets
- [ ] `GET /kozmo/projects/luna-manifesto/assets/lab/assets/pb_02f8b779.png` serves the image
- [ ] Frontend Settings panel can read/write media_sync_path
- [ ] Frontend MediaLibrary shows all 3 assets with thumbnails
- [ ] Future Eden generations auto-register + auto-sync (forward pipeline already works)

---

## FILE REFERENCE

| File | Purpose |
|------|---------|
| `data/kozmo_projects/luna-manifesto/lab/briefs/*.yaml` | Production briefs (fix these) |
| `data/kozmo_projects/luna-manifesto/lab/assets/*.png` | Generated images (3 on disk) |
| `data/kozmo_projects/luna-manifesto/audio_timeline.yaml` | 30 audio tracks with timecodes |
| `data/kozmo_projects/luna-manifesto/manifest.yaml` | Project settings (add media_sync_path) |
| `data/kozmo_projects/luna-manifesto/media_library.yaml` | Asset index (CREATE) |
| `src/luna/services/kozmo/media_library.py` | MediaLibraryService (done) |
| `src/luna/services/kozmo/lab_pipeline.py` | Forward pipeline integration (done) |
| `src/luna/services/kozmo/routes.py:2196-2290` | Asset + media routes (done) |
| `src/luna/services/kozmo/types.py:29` | ProjectSettings.media_sync_path (done) |
| `frontend/src/kozmo/lab/LabPipeline.jsx` | heroUrl helper to extract (done) |
| `frontend/src/kozmo/codex/KozmoCodex.jsx` | Add MediaLibrary tab (TODO) |
| `frontend/src/kozmo/settings/ProjectSettings.jsx` | Settings panel (CREATE) |
| `frontend/src/kozmo/codex/MediaLibrary.jsx` | Asset browser (CREATE) |
