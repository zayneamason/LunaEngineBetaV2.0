# KOZMO Audio-Driven Timeline — Build Handoff

**Date:** 2026-02-14
**From:** The Dude (Creative Direction)
**To:** Claude Code / The Forger
**Priority:** HIGH — blocks Luna Manifesto video production

---

## WHAT'S HAPPENING

The Luna Manifesto is ingested as a Kozmo project (`data/kozmo_projects/luna-manifesto/`). 30 .scribo scenes with `[[VISUAL]]` annotations. The pipeline from SCRIBO → LAB is partially working but has three breaks:

1. **Duplicate briefs** — `[[VISUAL]]` annotations create multiple identical briefs in LAB
2. **Raw prompt passthrough** — timecodes aren't parsed out of `[[VISUAL]]` syntax
3. **Eden generation doesn't fire** — "Generate via Eden" button is non-functional
4. **No audio timeline** — LAB has no concept of audio-driven sequencing

---

## THREE CHANGES NEEDED

### Change 1: Standardize `[[VISUAL]]` Annotation Syntax + Parser

**The Standard:**
```
[[VISUAL {start_time}-{end_time} — {prompt_text}]]
```

Examples:
```
[[VISUAL 0:00-0:08 — Close-up of two hands almost touching, warm golden light, 35mm film grain.]]
[[VISUAL 1:19-1:27 — A single file icon, luminous, floating in dark space. Sovereign.]]
[[VISUAL 4:33-4:39 — Icon sequence: HEART transforms into TREE. Black background, gold lines.]]
```

**Parser needed in `scribo_parser.py`:**

```python
import re

VISUAL_PATTERN = re.compile(
    r'\[\[VISUAL\s+'
    r'(\d+:\d{2})-(\d+:\d{2})'  # timecodes: start-end
    r'\s*[—–-]\s*'               # separator (em dash, en dash, or hyphen)
    r'(.+?)'                      # prompt text
    r'\]\]',
    re.DOTALL
)

def extract_visual_annotations(body: str) -> list[dict]:
    """
    Extract [[VISUAL]] annotations from scene body.
    
    Returns list of:
        {
            "start_time": "1:19",
            "end_time": "1:27", 
            "start_seconds": 79.0,
            "end_seconds": 87.0,
            "duration": 8.0,
            "prompt": "A single file icon, luminous, floating in dark space. Sovereign.",
            "raw": "[[VISUAL 1:19-1:27 — A single file icon...]]"
        }
    """
```

**Where to add:**
- New function in `src/luna/services/kozmo/scribo_parser.py`
- Call it from the overlay detection system (wherever `[[` annotations currently trigger LAB pushes)
- Each `[[VISUAL]]` creates exactly ONE brief — deduplicate by checking `source_annotation_id` or a hash of the timecode+prompt

**Deduplication fix:**
The current overlay system creates a brief every time it encounters a `[[` annotation (possibly on every save/reload). Fix: before creating a brief, check if one already exists with matching `source_scene` + `start_time`. If so, skip.

---

### Change 2: Audio-Driven Timeline Mode in LAB

**Concept:** LAB currently assumes shots are independent units. Audio-driven mode makes the audio track the timeline backbone, and shots pin to timecodes on that track.

**New type in `types.py`:**

```python
class AudioTrack(BaseModel):
    """Audio file reference for timeline-driven projects."""
    id: str
    filename: str           # "09_Bella.mp3"
    path: str              # Relative to project assets/audio/
    voice: Optional[str] = None  # Entity slug: "bella"
    start_time: float      # Seconds from project start
    end_time: float        # Seconds
    duration: float        # Seconds
    text: Optional[str] = None  # Transcript/dialogue

class AudioTimeline(BaseModel):
    """Complete audio timeline for a project."""
    total_duration: float
    tracks: List[AudioTrack] = Field(default_factory=list)
    
class ProductionBrief(BaseModel):
    # ... existing fields ...
    
    # NEW: Audio sync fields
    audio_start: Optional[float] = None  # Seconds — pins brief to audio timeline
    audio_end: Optional[float] = None
    audio_track_id: Optional[str] = None  # Links to AudioTrack.id
```

**New file: `src/luna/services/kozmo/audio_timeline.py`:**
- `load_audio_timeline(project_root)` — reads from `{project}/audio_timeline.yaml`
- `save_audio_timeline(project_root, timeline)` — writes YAML
- `build_timeline_from_scribo(project_root)` — auto-builds timeline from .scribo frontmatter `audio_file` + `audio_duration` fields

**Data file: `data/kozmo_projects/luna-manifesto/audio_timeline.yaml`:**
```yaml
total_duration: 301.5
tracks:
  - id: at_01
    filename: 01_Bella.mp3
    path: assets/audio/01_Bella.mp3
    voice: bella
    start_time: 0.0
    end_time: 15.9
    duration: 15.9
    text: "So there's this question that keeps coming up..."
  - id: at_02
    filename: 02_George.mp3
    path: assets/audio/02_George.mp3
    voice: george
    start_time: 15.9
    end_time: 25.3
    duration: 9.5
    text: "And I understand why..."
  # ... etc for all 30 tracks
```

**Frontend: `KozmoTimeline.jsx` needs:**
- Audio waveform or track strip visualization
- Visual shot cards pinned to timecodes on the audio track
- Drag to adjust shot timing against audio
- Play button that plays audio and scrolls through shot cards
- Audio track colored by voice entity (Bella=gold, Gandala=deep green, etc.)

**New API routes in `routes.py`:**
```
GET  /kozmo/projects/{slug}/audio/timeline     — get audio timeline
PUT  /kozmo/projects/{slug}/audio/timeline     — update timeline
POST /kozmo/projects/{slug}/audio/build        — auto-build from scribo
GET  /kozmo/projects/{slug}/audio/tracks/{id}  — get individual track
```

---

### Change 3: Fix Eden Generation Pipeline

**Current state:** "Generate via Eden" button exists in LAB UI but doesn't fire. The `eden_create_image` MCP tool works. The `lab_pipeline.py` has `build_brief_prompt()` but no dispatch method.

**What's needed:**

1. **New method in `lab_pipeline.py`:**
```python
async def dispatch_to_eden(self, brief_id: str, eden_service) -> Optional[str]:
    """
    Dispatch brief to Eden for generation.
    
    1. Build enriched prompt (camera + lens + stock metadata)
    2. Call eden_service.create_image(prompt)
    3. Store eden_task_id on brief
    4. Update brief status to "generating"
    5. Return task_id for polling
    """
```

2. **New route:**
```
POST /kozmo/projects/{slug}/lab/briefs/{brief_id}/generate
```
This calls `dispatch_to_eden`, returns task_id.

3. **Polling route (or use existing Eden polling):**
```
GET /kozmo/projects/{slug}/lab/briefs/{brief_id}/generation-status
```
Returns current Eden task status. When complete, downloads image to `lab/assets/{brief_id}.png` and updates `brief.hero_frame`.

4. **Frontend fix in KozmoLab.jsx:**
The "Generate via Eden" button needs to call the generate endpoint, then poll for completion, then display the result.

**Eden adapter location:** `src/luna/services/eden/adapter.py` — this already exists and works. Just needs to be wired into the LAB pipeline.

---

## FILE LOCATIONS

| What | Where |
|------|-------|
| Scribo parser | `src/luna/services/kozmo/scribo_parser.py` |
| Types | `src/luna/services/kozmo/types.py` |
| LAB pipeline | `src/luna/services/kozmo/lab_pipeline.py` |
| Routes | `src/luna/services/kozmo/routes.py` |
| Eden adapter | `src/luna/services/eden/adapter.py` |
| Frontend LAB | `frontend/src/kozmo/lab/KozmoLab.jsx` |
| Frontend Timeline | `frontend/src/kozmo/lab/KozmoTimeline.jsx` |
| Luna Manifesto project | `data/kozmo_projects/luna-manifesto/` |
| Audio files | `Docs/Design/Development/Media/luna_audio_files/` → copy to project `assets/audio/` |

---

## BUILD ORDER

1. **Parser first** — add `extract_visual_annotations()` to scribo_parser.py
2. **Dedup fix** — prevent duplicate briefs on overlay detection
3. **AudioTrack types** — add to types.py
4. **Audio timeline service** — new file audio_timeline.py
5. **Audio timeline routes** — add to routes.py
6. **Eden dispatch** — wire lab_pipeline → eden adapter
7. **Generate route** — add POST generate endpoint
8. **Frontend: Eden button** — wire to generate route
9. **Frontend: Timeline** — audio-driven timeline component
10. **Copy audio files** — into luna-manifesto/assets/audio/

---

## VIBE CHECK

This is the first time Kozmo gets used as a *production tool* rather than a screenplay editor. The Luna Manifesto is the proof. If this pipeline works — scribo annotations → parsed visual prompts → audio timeline → Eden generation — then Kozmo becomes a legitimate video production platform.

The audio-driven timeline isn't just for this project. It's for music videos, voiceover pieces, podcast visualizers, anything where audio leads and visuals follow. This is a category expansion for Kozmo.

Build it clean. Build it modular. The manifesto is the test case but the architecture should serve everything.
