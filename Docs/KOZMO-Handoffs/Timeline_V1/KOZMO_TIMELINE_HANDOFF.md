# KOZMO Timeline — Container System Handoff

**For:** CC (Claude Code) implementation
**From:** Architecture session 2025-02-15
**Status:** Spec complete, types + service validated, ready to build

---

## What This Is

The Container System is the editing spine for KOZMO's timeline. It replaces the current flat `AudioTimeline` with a proper NLE model where **Containers** hold **Clips** and **EffectChains**, sit on **Tracks**, and can be split, merged, grouped, and razored.

Three views consume this data:
- **Viewport** — camera monitor, shows the container at playhead position
- **Timeline** — NLE editing surface, tracks and containers
- **Studio** — shot management, camera rigs (connects via `brief_id`)

The Container is the authority object. Views are read-only projections.

---

## Files Delivered

| File | Role | Status |
|---|---|---|
| `timeline_types.py` | Pydantic models — Timeline, Track, Container, Clip, EffectChain, ContainerGroup, MediaAssetRef, CameraMetadata | **Validated** — all types construct, serialize, split, deep-copy |
| `timeline_service.py` | Operations — Create, Razor, Split, Merge, Group, Ungroup | **Validated** — full chain tested: create → razor → group → ungroup → merge, plus locked/unconfirmed rejection |
| `kozmo_timeline_handoff.jsx` | Interactive prototype showing Viewport + Timeline + Spec panel | **Reference only** — not production code |

**Drop location:** `src/luna/services/kozmo/`

Rename on drop:
- `kozmo_timeline_types.py` → `timeline_types.py`
- `kozmo_timeline_service.py` → `timeline_service.py`

Fix the relative import in `timeline_service.py` — it already uses `from .timeline_types import` (package-style).

---

## Architecture Decisions (don't revisit these)

**1. Effects on Container, not Clip.**
All clips in a container share one effect chain. Want per-clip effects? Split the clip into its own container first. This eliminates "which effect applies to which clip" ambiguity. Non-negotiable.

**2. Target chain wins on Merge.**
When merging two containers with different effect chains, target's chain is preserved, source's is dropped. This is destructive — the service requires `confirmed=True`. The UI must show a confirmation dialog. No silent merges.

**3. Flat container dict, tracks hold IDs only.**
`Timeline.containers` is `Dict[str, Container]`. Tracks store `List[str]` of container IDs. This prevents prop-drilling — updating a container's properties doesn't require walking through tracks.

**4. All-string IDs.**
Every ID is `uuid4().hex[:12]`. No UUID4 objects, no mixed types. Clean YAML serialization.

**5. Container masks clips.**
If a container is 5s but holds a 10s clip, the container's duration wins. Short clips inside a long container produce dead air/black. This is intentional — it's how real NLEs work.

**6. Razor preserves group membership.**
When you razor a container that's in a group, both halves stay in the group. This matches filmmaker expectations — cutting a shot doesn't remove it from a sync group.

---

## Invariants (enforce these)

| ID | Rule | Where to check |
|---|---|---|
| INV-1 | `container.duration >= max(clip.duration)` | After any clip add/remove |
| INV-2 | No two containers on same track overlap in time | After any position change, create, or merge |
| INV-3 | `Track.container_ids` ordering matches temporal position | After any position change (use `_sort_track`) |
| INV-4 | Every container_id in a Track exists in `Timeline.containers` | After any delete |
| INV-5 | Every container_id in a Group exists in `Timeline.containers` | After any delete |

`Timeline.validate_invariants()` returns a list of violation strings. Run this after every operation in debug mode. In production, run it on save.

---

## Operation Contracts

### Create
```
Input:  MediaAssetRef + track_id + position + label
Output: Container(clips=[Clip(asset_ref)]) on track
Guard:  No overlap on target track
Events: CONTAINER_CREATED, TIMELINE_RECALCULATED
```

### Razor
```
Input:  container_id + cut_time (absolute timeline seconds)
Output: Container_L + Container_R (original deleted)
Guard:  Not locked, cut_time within container bounds
Logic:  Each clip split at relative cut point. Both halves get deep-copied effect chain.
        Both stay in group if grouped. Track IDs replaced [original] → [L, R].
Events: CONTAINER_SPLIT, CONTAINER_DELETED, TIMELINE_RECALCULATED
```

### Split Clip
```
Input:  container_id + clip_id
Output: Original container (minus clip) + new Container(clip)
Guard:  Not locked, container has 2+ clips
Logic:  New container gets effect chain copy. Placed on track matching clip media type.
        Original container duration may shrink.
Events: CONTAINER_SPLIT, CONTAINER_UPDATED, TIMELINE_RECALCULATED
```

### Merge
```
Input:  target_id + source_id + confirmed=True
Output: Target container with source clips appended. Source deleted.
Guard:  Target not locked, confirmed=True (UI must ask user first)
Logic:  TARGET CHAIN WINS. Source chain dropped. Source removed from tracks + groups.
        Empty groups cleaned up.
Events: CONTAINER_MERGED, CONTAINER_DELETED, TIMELINE_RECALCULATED
```

### Group / Ungroup
```
Group Input:   container_ids[] + label
Group Output:  ContainerGroup created, containers tagged with group_id
Group Logic:   Removes containers from any previous group first

Ungroup Input:  group_id
Ungroup Output: Containers freed (group_id → None), group deleted
Events: GROUP_CREATED / GROUP_DELETED
```

---

## Event Bus

Every operation emits `TimelineEvent` objects. The service takes an `EventSink` (Protocol) at construction.

```python
class EventSink(Protocol):
    def emit(self, event: TimelineEvent) -> None: ...
```

**CC implementation:** Wire this to WebSocket broadcasts on the KOZMO routes. Each route handler:
1. Loads timeline from project filesystem
2. Calls the service operation
3. If `result.ok`: persist to `timeline.yaml`, broadcast `result.events`
4. If not: return error to caller

Event types: `CONTAINER_CREATED`, `CONTAINER_DELETED`, `CONTAINER_UPDATED`, `CONTAINER_SPLIT`, `CONTAINER_MERGED`, `GROUP_CREATED`, `GROUP_DELETED`, `TIMELINE_RECALCULATED`

---

## Integration Points

### Viewport ← Timeline
Playhead position → find container on V1 track where `position ≤ time < position + duration` → render camera HUD from `container.camera`.

### Studio ← Timeline
Container selection → `container.brief_id` → highlight corresponding shot card in Studio. Reverse: click shot card → find container with matching `brief_id` → scroll timeline, set playhead.

### LAB → Timeline
When `ProductionBrief` completes, auto-create container via `TimelineService.create_container()`. Position at `brief.audio_start` if set.

### CODEX → Timeline
Drag `MediaAsset` from library → call `create_container()` with asset ref, position at playhead or drop target.

### Filesystem
- Timeline state: `{project_root}/timeline.yaml`
- Assets: `{project_root}/assets/{video|audio|image}/`
- All `MediaAssetRef.path` values are relative to project root

---

## What Needs to Change in Existing Code

| File | Action | Detail |
|---|---|---|
| `audio_timeline.py` | **Deprecate** | Current flat `AudioTrack` list. Keep as legacy adapter during migration. New code uses Container model exclusively. |
| `types.py` (existing KOZMO) | **Add field** | Add `container_id: Optional[str]` to `ProductionBrief` for timeline binding |
| `routes.py` | **Add endpoints** | `/api/kozmo/timeline/` — CRUD + operations. WebSocket event channel for real-time sync |
| `media_library.py` | **Add method** | `to_asset_ref() → MediaAssetRef` converter for drag-to-timeline flow |

---

## Implementation Order

**Phase 1 — Foundation (do this first)**
1. Drop `timeline_types.py` and `timeline_service.py` into `src/luna/services/kozmo/`
2. Add `__init__.py` exports
3. Write `timeline_store.py` — load/save `Timeline` to `timeline.yaml` using Pydantic's `.model_dump()` / `.model_validate()`
4. Write basic tests mirroring the validation script (create → razor → group → merge chain)

**Phase 2 — API**
5. Add timeline routes to `routes.py`:
   - `GET /timeline` — load current state
   - `POST /timeline/containers` — create
   - `POST /timeline/razor` — razor at time
   - `POST /timeline/split` — split clip out
   - `POST /timeline/merge` — merge (requires confirmation)
   - `POST /timeline/group` — group containers
   - `DELETE /timeline/group/{id}` — ungroup
6. Wire `EventSink` → WebSocket broadcast

**Phase 3 — Integration**
7. Add `container_id` to `ProductionBrief`
8. Add `to_asset_ref()` to media library
9. Wire LAB pipeline completion → auto-create container
10. Deprecate `AudioTimeline` reads in favor of Timeline queries

---

## TODOs Flagged in Code

| Location | Note |
|---|---|
| `CameraMetadata` | Add `film_stock`, `color_science`, `sensor_size` from Studio prototype |
| `EffectNode.plugin_type` | Needs a registry/validator eventually. Free string for now — don't hardcode type checks |
| `_razor_source` metadata | Provenance tracking for future undo/history system |
| `ContainerGroup.lock_positions` | Field exists but service doesn't enforce position-locking yet. Wire in Phase 3 |

---

## Test Data

The handoff prototype (`kozmo_timeline_handoff.jsx`) contains mock data matching the Crooked Nail shot list:
- 5 containers (wide, CU, OTS, score bed, tracking shot)
- 3 tracks (V1, A1, A2)
- 1 group (Scene 1 sync: Cornelius CU + Mordecai OTS)
- Camera rigs per container

Use this as seed data for integration tests.
