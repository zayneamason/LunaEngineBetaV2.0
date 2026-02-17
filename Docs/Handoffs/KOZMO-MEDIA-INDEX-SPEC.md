# KOZMO MEDIA INDEX SPECIFICATION
## The Single Source of Truth for Audio ↔ Scribo ↔ LAB Mapping

**Date:** 2026-02-15  
**Author:** Architecture review  
**Status:** IMPLEMENTATION SPEC — Claude Code follows this exactly  
**Project Root:** `/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root`

---

## THE PROBLEM

Three data layers exist that need bidirectional indexing:

```
.scribo scenes  ←→  audio tracks  ←→  production briefs (LAB)
```

Right now:
1. Audio files exist on disk but the `.scribo` ↔ audio link is **one-way** (frontmatter has `audio_file` but `serialize_scribo()` drops it on save)
2. `[[VISUAL]]` annotations in `.scribo` bodies get pushed to LAB as briefs, but the **raw syntax passes through unparsed** — the prompt field contains `[[VISUAL 1:19-1:27 — prompt text]]` instead of just the prompt text
3. Briefs have `source_scene` but `audio_start`/`audio_end`/`audio_track_id` are never populated
4. No route exists to query "give me everything linked to this scene" or "give me everything pinned to this timecode"
5. Generated video/image assets in LAB have no back-link to their audio track

---

## THE DATA MODEL (What Exists Today)

### Layer 1: .scribo Scene Files

**Location:** `data/kozmo_projects/{slug}/story/{container}/{scene}.scribo`

**Frontmatter** (`ScriboFrontmatter` in `types.py` line 280):
```yaml
type: scene
container: sec_1_the_wrong_question
characters_present: [bella]
time: "0:00 - 0:16"
status: final
tags: [opening]
audio_file: 01_Bella.mp3        # ← EXISTS but not serialized back on save
audio_duration: 15.9s            # ← EXISTS but not serialized back on save
```

**Body** contains inline `[[VISUAL]]` annotations:
```
[[VISUAL 0:00-0:08 — Close-up of two hands almost touching...]]
```

**BUG:** `serialize_scribo()` in `scribo_parser.py` (line 144) does NOT write `audio_file` or `audio_duration` back to YAML. It builds the dict manually and omits these fields. The fields exist on the Pydantic model and `parse_scribo()` reads them, but the serializer drops them.

### Layer 2: Audio Timeline

**Location:** `data/kozmo_projects/{slug}/audio_timeline.yaml`

```yaml
- id: at_01
  filename: 01_Bella.mp3
  path: assets/audio/01_Bella.mp3
  voice: bella
  start_time: 0.0
  end_time: 15.9
  duration: 15.9
  text: "So there's this question..."
  section: 1
  lines: 1-3
  document_slug: sc_01_bella_opening        # ← links to .scribo
  container_slug: sec_1_the_wrong_question   # ← links to container
  visual_prompt: "Close-up of two hands..."  # ← first visual from scene
```

**STATUS:** This file exists and is correct. But there is NO type model for it in `types.py`, NO service to load/query it, and NO routes to expose it.

### Layer 3: Production Briefs (LAB)

**Location:** `data/kozmo_projects/{slug}/lab/briefs/{brief_id}.yaml`

`ProductionBrief` in `types.py` (line 448):
```python
source_scene: Optional[str]           # ← populated ✓
source_annotation_id: Optional[str]   # ← populated ✓
audio_start: Optional[float]          # ← FIELD EXISTS, never populated
audio_end: Optional[float]            # ← FIELD EXISTS, never populated
audio_track_id: Optional[str]         # ← FIELD EXISTS, never populated
```

**BUG:** When `push_to_lab` creates a brief from a `[[VISUAL]]` annotation, it passes the RAW annotation text as the prompt.

Actual brief on disk (`pb_02f8b779.yaml`):
```yaml
title: '[[VISUAL 1:19-1:27 — A single file icon, luminous, floating in dark space. It pu'
prompt: '[[VISUAL 1:19-1:27 — A single file icon, luminous, floating in dark space.
  It pulses gently like a heartbeat...]]'
```

Should be:
```yaml
title: 'A single file icon, luminous, floating in dark space'
prompt: 'A single file icon, luminous, floating in dark space. It pulses gently...'
audio_start: 79.0
audio_end: 87.0
audio_track_id: at_09
```

---

## THE FIXES (Ordered by dependency)

### Fix 1: `serialize_scribo()` must round-trip audio fields

**File:** `src/luna/services/kozmo/scribo_parser.py`
**Function:** `serialize_scribo()` starting at line 144

The function manually builds a dict from frontmatter fields. It currently omits `audio_file` and `audio_duration`.

**Add after the `tags` block (around line 173):**
```python
if frontmatter.audio_file:
    data["audio_file"] = frontmatter.audio_file
if frontmatter.audio_duration:
    data["audio_duration"] = frontmatter.audio_duration
```

That's it. Two lines. The fields already exist on `ScriboFrontmatter` (line 290-291) and `parse_scribo()` already reads them (line 131-132). The serializer just drops them.

---

### Fix 2: Parse `[[VISUAL]]` before creating briefs

**File:** `src/luna/services/kozmo/overlay.py`
**Function:** `push_to_lab()` at line 193

When `ann.lab_action.prompt` contains a `[[VISUAL ...]]` string, it needs to be parsed before becoming a brief prompt.

**The parser already exists:** `extract_visual_annotations()` in `scribo_parser.py` (line 54).

**Change in `push_to_lab()`:** Before setting `brief_data["prompt"]`, check if the prompt contains `[[VISUAL`:

```python
from .scribo_parser import extract_visual_annotations

# In push_to_lab(), where prompt is set:
raw_prompt = ann.lab_action.prompt or ann.text

# Parse [[VISUAL]] if present
visuals = extract_visual_annotations(raw_prompt)
if visuals:
    v = visuals[0]
    brief_data["prompt"] = v["prompt"]
    brief_data["title"] = v["prompt"][:80]
    brief_data["audio_start"] = v["start_seconds"]
    brief_data["audio_end"] = v["end_seconds"]
else:
    brief_data["prompt"] = raw_prompt
    brief_data["title"] = raw_prompt[:80]
```

**Same fix needed in:** `push_all_actions()` in `overlay.py` if it exists, AND in `api_push_all_actions()` in `routes.py` (line 1589).

---

### Fix 3: Add AudioTrack / AudioTimeline types

**File:** `src/luna/services/kozmo/types.py`

Add after `ScriboFrontmatter` (around line 293):

```python
class AudioTrack(BaseModel):
    """A single audio clip in the timeline."""
    id: str                              # at_01, at_02, ...
    filename: str                        # 01_Bella.mp3
    path: str                            # assets/audio/01_Bella.mp3
    voice: Optional[str] = None          # entity slug: bella, george
    start_time: float                    # seconds from project start
    end_time: float
    duration: float
    text: Optional[str] = None           # transcript
    section: Optional[int] = None
    lines: Optional[str] = None          # "1-3"
    document_slug: Optional[str] = None  # sc_01_bella_opening
    container_slug: Optional[str] = None # sec_1_the_wrong_question
    visual_prompt: Optional[str] = None  # first visual from scene

class AudioTimeline(BaseModel):
    """Project-level audio timeline."""
    total_duration: float
    tracks: List[AudioTrack] = Field(default_factory=list)
```

---

### Fix 4: Audio Timeline service

**New file:** `src/luna/services/kozmo/audio_timeline.py`

```python
"""Audio Timeline Service — loads and queries audio_timeline.yaml"""

import yaml
from pathlib import Path
from typing import Optional, List
from .types import AudioTrack, AudioTimeline


class AudioTimelineService:
    def __init__(self, project_root: Path):
        self.root = project_root
        self.timeline_path = project_root / "audio_timeline.yaml"

    def load(self) -> Optional[AudioTimeline]:
        if not self.timeline_path.exists():
            return None
        data = yaml.safe_load(self.timeline_path.read_text(encoding="utf-8"))
        if not data:
            return None
        tracks = [AudioTrack(**t) for t in data.get("tracks", [])]
        return AudioTimeline(total_duration=data.get("total_duration", 0), tracks=tracks)

    def get_track_by_id(self, track_id: str) -> Optional[AudioTrack]:
        tl = self.load()
        if not tl: return None
        return next((t for t in tl.tracks if t.id == track_id), None)

    def get_tracks_for_scene(self, doc_slug: str) -> List[AudioTrack]:
        tl = self.load()
        if not tl: return []
        return [t for t in tl.tracks if t.document_slug == doc_slug]

    def get_track_at_time(self, seconds: float) -> Optional[AudioTrack]:
        tl = self.load()
        if not tl: return None
        return next((t for t in tl.tracks if t.start_time <= seconds < t.end_time), None)

    def get_track_for_visual(self, start_seconds: float) -> Optional[AudioTrack]:
        return self.get_track_at_time(start_seconds)
```

---

### Fix 5: Wire audio_track_id into brief creation

**File:** `src/luna/services/kozmo/routes.py`
**Functions:** `api_push_annotation_to_lab()` (line 1547) and `api_push_all_actions()` (line 1589)

After overlay returns `brief_data` and after `[[VISUAL]]` is parsed (Fix 2), look up the audio track:

```python
from .audio_timeline import AudioTimelineService

# After building brief_data, before creating PBModel:
audio_svc = AudioTimelineService(paths.root)
if brief_data.get("audio_start") is not None:
    track = audio_svc.get_track_for_visual(brief_data["audio_start"])
    if track:
        brief_data["audio_track_id"] = track.id
```

Then in the `PBModel(...)` constructor, add:
```python
audio_start=brief_data.get("audio_start"),       # ← ADD
audio_end=brief_data.get("audio_end"),             # ← ADD
audio_track_id=brief_data.get("audio_track_id"),   # ← ADD
```

---

### Fix 6: Audio timeline routes

**File:** `src/luna/services/kozmo/routes.py`

```python
@router.get("/projects/{project_slug}/audio/timeline", tags=["audio"])
async def api_get_audio_timeline(project_slug: str):
    paths = _get_project_paths(project_slug)
    svc = AudioTimelineService(paths.root)
    tl = svc.load()
    if not tl: return {"total_duration": 0, "tracks": []}
    return tl.model_dump()

@router.get("/projects/{project_slug}/audio/tracks/{track_id}", tags=["audio"])
async def api_get_audio_track(project_slug: str, track_id: str):
    paths = _get_project_paths(project_slug)
    svc = AudioTimelineService(paths.root)
    track = svc.get_track_by_id(track_id)
    if not track: raise HTTPException(status_code=404, detail=f"Track not found: {track_id}")
    return track.model_dump()

@router.get("/projects/{project_slug}/audio/scene/{doc_slug}", tags=["audio"])
async def api_get_audio_for_scene(project_slug: str, doc_slug: str):
    paths = _get_project_paths(project_slug)
    svc = AudioTimelineService(paths.root)
    return [t.model_dump() for t in svc.get_tracks_for_scene(doc_slug)]

@router.get("/projects/{project_slug}/audio/at/{seconds}", tags=["audio"])
async def api_get_audio_at_time(project_slug: str, seconds: float):
    paths = _get_project_paths(project_slug)
    svc = AudioTimelineService(paths.root)
    track = svc.get_track_at_time(seconds)
    if not track: return {"track": None, "seconds": seconds}
    return track.model_dump()
```

---

### Fix 7: Scene manifest endpoint (the full index query)

**New route:** `GET /kozmo/projects/{slug}/story/documents/{doc_slug}/manifest`

```python
@router.get("/projects/{project_slug}/story/documents/{doc_slug}/manifest", tags=["story", "manifest"])
async def api_get_scene_manifest(project_slug: str, doc_slug: str):
    paths = _get_project_paths(project_slug)

    # Scene
    scribo_svc = ScriboService(paths.root)
    doc = scribo_svc.get_document(doc_slug)
    if not doc: raise HTTPException(status_code=404, detail=f"Scene not found: {doc_slug}")

    # Audio
    audio_svc = AudioTimelineService(paths.root)
    audio_tracks = audio_svc.get_tracks_for_scene(doc_slug)

    # Visuals
    from .scribo_parser import extract_visual_annotations
    visuals = extract_visual_annotations(doc.body)

    # Briefs
    lab = LabPipelineService(paths.root)
    scene_briefs = [b for b in lab.list_briefs() if b.source_scene == doc_slug]

    return {
        "scene": {"slug": doc.slug, "path": doc.path, "frontmatter": doc.frontmatter.model_dump(), "word_count": doc.word_count},
        "audio": [t.model_dump() for t in audio_tracks],
        "visuals": visuals,
        "briefs": [b.model_dump() for b in scene_briefs],
        "entities": doc.frontmatter.characters_present,
        "container": doc.frontmatter.container,
    }
```

---

## EXISTING BRIEFS: MIGRATION

The 7 briefs on disk have raw `[[VISUAL]]` in prompts. One-time script:

**File:** `scripts/migrate_briefs.py`

```python
import yaml
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from luna.services.kozmo.scribo_parser import extract_visual_annotations
from luna.services.kozmo.audio_timeline import AudioTimelineService

project_root = Path("data/kozmo_projects/luna-manifesto")
briefs_dir = project_root / "lab" / "briefs"
audio_svc = AudioTimelineService(project_root)

for brief_file in briefs_dir.glob("*.yaml"):
    data = yaml.safe_load(brief_file.read_text())
    visuals = extract_visual_annotations(data.get("prompt", ""))
    if not visuals: continue
    v = visuals[0]
    data["prompt"] = v["prompt"]
    data["title"] = v["prompt"][:80]
    data["audio_start"] = v["start_seconds"]
    data["audio_end"] = v["end_seconds"]
    track = audio_svc.get_track_for_visual(v["start_seconds"])
    if track: data["audio_track_id"] = track.id
    brief_file.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True))
    print(f"Migrated {brief_file.name}: {v['prompt'][:60]}...")
```

---

## THE FULL INDEX MAP

```
.scribo file
  ├── frontmatter.audio_file ──────→ assets/audio/{filename}
  ├── frontmatter.audio_duration
  ├── frontmatter.characters_present ──→ entities/character/{slug}.yaml
  ├── frontmatter.container ───────→ story/{container}/_meta.yaml
  ├── body [[VISUAL]] annotations
  │     ├── .start_seconds ────────→ audio_timeline.yaml (track lookup)
  │     ├── .end_seconds
  │     └── .prompt ───────────────→ ProductionBrief.prompt (PARSED)
  └── body Fountain elements
        └── CHARACTER NAME ────────→ entities/character/{slug}.yaml

audio_timeline.yaml
  ├── track.document_slug ─────────→ .scribo scene slug
  ├── track.container_slug ────────→ story container slug
  ├── track.voice ─────────────────→ entities/character/{slug}.yaml
  └── track.id ────────────────────→ ProductionBrief.audio_track_id

ProductionBrief (lab/briefs/)
  ├── source_scene ────────────────→ .scribo scene slug
  ├── source_annotation_id ────────→ overlay annotation
  ├── audio_start / audio_end ─────→ timecode (seconds)
  ├── audio_track_id ──────────────→ AudioTrack.id
  ├── characters ──────────────────→ entities/character/{slug}.yaml
  └── hero_frame ──────────────────→ lab/assets/{brief_id}.png
```

---

## BUILD ORDER

| # | Fix | Lines | Files |
|---|-----|-------|-------|
| 1 | serialize_scribo round-trip audio | ~2 | scribo_parser.py |
| 2 | parse [[VISUAL]] in push_to_lab | ~10 | overlay.py |
| 3 | AudioTrack/AudioTimeline types | ~20 | types.py |
| 4 | AudioTimelineService | ~50 | audio_timeline.py (NEW) |
| 5 | Wire audio_track_id into briefs | ~5 | routes.py |
| 6 | Migrate existing briefs | script | scripts/migrate_briefs.py |
| 7 | Audio timeline routes | ~40 | routes.py |
| 8 | Scene manifest endpoint | ~30 | routes.py |

## FILES TO MODIFY

| File | What Changes |
|------|-------------|
| `src/luna/services/kozmo/scribo_parser.py` | Fix 1: 2 lines in serialize_scribo() |
| `src/luna/services/kozmo/overlay.py` | Fix 2: parse [[VISUAL]] in push_to_lab() |
| `src/luna/services/kozmo/types.py` | Fix 3: add AudioTrack, AudioTimeline models |
| `src/luna/services/kozmo/audio_timeline.py` | Fix 4: NEW FILE |
| `src/luna/services/kozmo/routes.py` | Fix 5, 7, 8: wire audio + new routes |

## FILES NOT TO MODIFY

| File | Why |
|------|-----|
| `scribo_parser.py` extract_visual_annotations() | Already correct |
| `lab_pipeline.py` | dispatch_to_eden() already works |
| `audio_timeline.yaml` | Already complete |
| `.scribo` scene files | Already have correct frontmatter |
| Entity YAML files | Already complete |

---

## VALIDATION CHECKLIST

- [ ] `GET /kozmo/projects/luna-manifesto/audio/timeline` → 30 tracks
- [ ] `GET /kozmo/projects/luna-manifesto/audio/scene/sc_01_bella_opening` → track at_01
- [ ] `GET /kozmo/projects/luna-manifesto/story/documents/sc_01_bella_opening/manifest` → scene + audio + visuals + briefs
- [ ] All 7 existing briefs have parsed prompts (no `[[VISUAL` in prompt field)
- [ ] New briefs via "Push to LAB" have parsed prompts + audio_start + audio_track_id
- [ ] Saving .scribo preserves audio_file and audio_duration in frontmatter
- [ ] `GET /kozmo/projects/luna-manifesto/audio/at/80.0` → returns track at_09


---

## ADDENDUM: THREE MORE ISSUES (2026-02-15 evening)

### Issue A: Generated Images Are Invisible (No Static File Serving)

**What happens:** Eden generates an image → `poll_eden_status()` downloads it to `lab/assets/pb_xxx.png` → brief gets `hero_frame: lab/assets/pb_02f8b779.png` → frontend does `<img src={brief.hero_frame}>` → **404 because no route serves project files.**

The Vite config has a `/kozmo-assets` proxy to `localhost:8000` but **there is no backend handler for it.** Zero file serving exists anywhere in the codebase.

**Fix:** Add an asset serving route to `routes.py`:

```python
from fastapi.responses import FileResponse

@router.get("/projects/{project_slug}/assets/{path:path}", tags=["assets"])
async def api_serve_project_asset(project_slug: str, path: str):
    """Serve static files from a project's directory."""
    paths = _get_project_paths(project_slug)
    file_path = paths.root / path
    
    # Security: ensure resolved path stays within project root
    resolved = file_path.resolve()
    if not str(resolved).startswith(str(paths.root.resolve())):
        raise HTTPException(status_code=403, detail="Access denied")
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Asset not found: {path}")
    
    return FileResponse(file_path)
```

**Then update `hero_frame` references to use the route:**

When `poll_eden_status` saves the file, the `hero_frame` value stored on the brief should be the API URL, not the filesystem path:

```python
# In lab_pipeline.py poll_eden_status():
# Instead of:
#   self.update_brief(brief_id, {"hero_frame": f"lab/assets/{filename}"})
# Use:
#   self.update_brief(brief_id, {"hero_frame": f"/kozmo/projects/{project_slug}/assets/lab/assets/{filename}"})
```

**OR** (simpler): Keep `hero_frame` as-is (relative path) and have the frontend prepend the asset route:

```jsx
// In LabPipeline.jsx and AudioTimeline.jsx:
// Instead of: <img src={brief.hero_frame} />
// Use: <img src={`/kozmo/projects/${projectSlug}/assets/${brief.hero_frame}`} />
```

**Recommendation:** Frontend prepend approach is cleaner — keeps stored data portable.

---

### Issue B: No Asset Archive / Library in Codex

Currently generated images live in `lab/assets/` as orphan files. There's no browsable library, no way to see all generated media, and no way to tag/organize them.

**What's needed:** An Asset Library panel, likely in the Codex or as a new top-level tab.

**Data model addition to `types.py`:**

```python
class MediaAsset(BaseModel):
    """A generated or imported media asset."""
    id: str                              # asset_xxx
    type: str                            # image | video | audio
    filename: str
    path: str                            # relative to project root
    source: str                          # eden | import | capture
    brief_id: Optional[str] = None       # links to ProductionBrief
    scene_slug: Optional[str] = None     # links to .scribo
    audio_track_id: Optional[str] = None # links to AudioTrack
    audio_start: Optional[float] = None  # timecode pin
    audio_end: Optional[float] = None
    eden_task_id: Optional[str] = None
    prompt: Optional[str] = None         # generation prompt
    tags: List[str] = Field(default_factory=list)
    status: str = "generated"            # generated | approved | rejected | archived
    created_at: Optional[datetime] = None
```

**New service:** `src/luna/services/kozmo/media_library.py`
- Maintains an index file: `{project}/media_library.yaml`
- `register_asset()` — called by `poll_eden_status()` when download completes
- `list_assets()` — filtered by type, scene, brief, tags, status
- `get_asset()` — by ID
- `tag_asset()` / `update_status()` — organize

**New routes:**
```
GET  /kozmo/projects/{slug}/media                    — list all assets
GET  /kozmo/projects/{slug}/media/{asset_id}         — single asset
GET  /kozmo/projects/{slug}/media/scene/{doc_slug}   — assets for scene
GET  /kozmo/projects/{slug}/media/brief/{brief_id}   — assets for brief
PUT  /kozmo/projects/{slug}/media/{asset_id}         — update tags/status
```

**Wire into `lab_pipeline.py`:** When `poll_eden_status()` downloads an image, also call `media_library.register_asset()` to index it.

**Frontend:** Add a tab to Codex (or a new panel) that shows a grid of all generated assets with filters by scene, brief, status, tags. Click an asset to see its brief, its scene, its audio track, its prompt.

---

### Issue C: Project Needs External Media Path + Settings Panel

The manifest currently has no way to configure external paths. You want:
- Generated assets to also sync to `/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/Docs/Design/Development/Media`
- A place in settings to configure this mapping

**Manifest addition:**

```yaml
# manifest.yaml
settings:
  default_camera: arri_alexa35
  default_lens: cooke_s7i
  default_film_stock: kodak_5219
  aspect_ratio: "21:9"
  media_sync_path: "/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/Docs/Design/Development/Media"
```

**Type model addition to `ProjectSettings` in `types.py`:**

```python
class ProjectSettings(BaseModel):
    default_camera: str = "arri_alexa35"
    default_lens: str = "cooke_s7i"
    default_film_stock: str = "kodak_5219"
    aspect_ratio: str = "21:9"
    media_sync_path: Optional[str] = None   # ← ADD: external dir for media sync
```

**Sync behavior in `lab_pipeline.py`:** When `poll_eden_status()` saves a file to `lab/assets/`, also copy it to `media_sync_path` if configured:

```python
# After saving to lab/assets/:
if media_sync_path:
    sync_dir = Path(media_sync_path)
    sync_dir.mkdir(parents=True, exist_ok=True)
    # Copy with meaningful name: {scene_slug}_{timecode}_{brief_id}.png
    import shutil
    scene_name = brief.source_scene or "unknown"
    sync_name = f"{scene_name}_{brief_id}.png"
    shutil.copy2(local_path, sync_dir / sync_name)
```

**Settings UI:** Add a project settings panel (likely accessible from the manifest/config area) that shows:
- Camera defaults
- Film stock
- Aspect ratio
- **Media sync directory** (file picker or text input)
- Eden budget

**Route for updating settings:**
```
PUT /kozmo/projects/{slug}/settings
Body: { "media_sync_path": "/path/to/media", ... }
```

---

## UPDATED BUILD ORDER (With Issues A-C)

| # | Fix | Priority | Files |
|---|-----|----------|-------|
| 1 | serialize_scribo round-trip audio | HIGH | scribo_parser.py |
| 2 | parse [[VISUAL]] in push_to_lab | HIGH | overlay.py |
| 3 | AudioTrack/AudioTimeline types | HIGH | types.py |
| 4 | AudioTimelineService | HIGH | audio_timeline.py (NEW) |
| 5 | Wire audio_track_id into briefs | HIGH | routes.py |
| 6 | Migrate existing briefs | HIGH | scripts/migrate_briefs.py |
| **A** | **Asset serving route** | **CRITICAL** | **routes.py + frontend** |
| 7 | Audio timeline routes | MEDIUM | routes.py |
| 8 | Scene manifest endpoint | MEDIUM | routes.py |
| **C** | **media_sync_path in settings** | MEDIUM | **types.py, manifest, lab_pipeline.py** |
| **B** | **Media library + Codex panel** | LOWER | **NEW: media_library.py, routes, frontend** |

Fix A is actually the most urgent — without it, generated images literally disappear from the UI even though they're saved to disk.

---

## UPDATED VALIDATION CHECKLIST

- [ ] Generated images visible in LAB pipeline (asset serving route works)
- [ ] `GET /kozmo/projects/luna-manifesto/assets/lab/assets/pb_02f8b779.png` → serves the image
- [ ] `GET /kozmo/projects/luna-manifesto/audio/timeline` → 30 tracks
- [ ] `GET /kozmo/projects/luna-manifesto/story/documents/sc_01_bella_opening/manifest` → scene + audio + visuals + briefs
- [ ] All 7 existing briefs have parsed prompts (no `[[VISUAL` in prompt)
- [ ] New briefs via "Push to LAB" have parsed prompts + audio_start + audio_track_id
- [ ] Saving .scribo preserves audio_file and audio_duration
- [ ] Setting media_sync_path in manifest copies generated assets to external dir
- [ ] Media library registers new assets when Eden generation completes
