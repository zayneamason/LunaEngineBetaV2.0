# HANDOFF: FaceID Frontend UX — Browser-Based Identity Recognition

**Date:** 2026-02-19
**Scope:** Frontend camera integration, identity UI, browser-based face recognition flow
**Status:** BACKEND COMPLETE — ready for frontend implementation
**Companion Docs:**
- `Docs/Handoffs/FacialRec/ARCHITECTURE_IDENTITY_GATED_SOVEREIGNTY.md` (full identity system design)
- `Dual_Tier_Bridge_Architecture.docx` (how identity connects to data room permissions)

---

## OVERVIEW

Luna's FaceID backend is fully wired. Camera → FaceNet → matcher → engine events → system prompt injection — the pipeline works. The missing piece is the **browser-side experience**: when someone opens Luna at `localhost:5173`, the frontend should use the browser's camera to identify them, push frames to the backend for recognition, and reflect identity state in the UI.

### What Exists (already built)

| What | Where | Status |
|------|-------|--------|
| FaceNet encoder + MTCNN detection | `Tools/FaceID/src/encoder.py` | COMPLETE — 512-dim embeddings |
| Face database + access bridge | `Tools/FaceID/src/database.py` | COMPLETE — SQLite, both tier systems |
| Cosine similarity matcher | `Tools/FaceID/src/matcher.py` | COMPLETE — returns IdentityResult |
| Camera capture (macOS native) | `Tools/FaceID/src/camera.py` | COMPLETE — OpenCV, works from Terminal |
| Enrollment CLI | `Tools/FaceID/cli/enroll.py` | COMPLETE — captures 5 angles, stores embeddings |
| Recognition CLI | `Tools/FaceID/cli/recognize.py` | COMPLETE — live feed with tier labels |
| IdentityActor (engine integration) | `src/luna/actors/identity.py` | COMPLETE — background loop, emits events |
| Engine event types | `src/luna/core/events.py` | COMPLETE — `IDENTITY_RECOGNIZED = 40`, `IDENTITY_LOST = 41` |
| Engine system prompt injection | `src/luna/engine.py` | COMPLETE — identity context injected into prompts |
| WebSocket endpoint | `src/luna/api/server.py` | COMPLETE — `/ws/identity` streams state changes |
| Identity status in /status API | `src/luna/api/server.py` | COMPLETE — `IdentityStatus` model in response |
| Frontend WebSocket hook | `frontend/src/hooks/useIdentity.js` | COMPLETE — connects to `/ws/identity`, parses events |
| IdentityBadge component | `frontend/src/components/IdentityBadge.jsx` | COMPLETE — compact badge with tier colors |
| Wired into App.jsx | `frontend/src/App.jsx` | COMPLETE — imports `useIdentity`, renders `IdentityBadge` |
| Ahab enrolled | `Tools/FaceID/data/faces.db` | COMPLETE — 10 embeddings, admin tier |

### What Needs To Be Built

| What | Where | Status |
|------|-------|--------|
| Browser camera capture component | `frontend/src/components/FaceIDCapture.jsx` | **NEW** |
| Frame-to-backend HTTP endpoint | `src/luna/api/server.py` | **NEW** — `POST /identity/recognize` |
| Session-start identity check flow | `frontend/src/hooks/useIdentity.js` | **MODIFY** |
| Identity-aware chat transitions | `frontend/src/App.jsx` | **MODIFY** |
| Enrollment flow (browser-based) | `frontend/src/components/FaceIDEnroll.jsx` | **NEW** (optional, Phase 2) |

---

## THE DESIGN DECISION

The current `IdentityActor` uses OpenCV to capture from the system camera. This works from Terminal.app but **not** from VS Code's terminal or browser contexts due to macOS TCC (Transparency, Consent, and Control) camera permissions. The browser has its own camera permission system via `getUserMedia`.

### Approach: Browser Camera → Backend Processing

The browser captures frames via WebRTC (`getUserMedia`), sends them as base64 JPEG to a new backend endpoint, and the backend runs FaceNet on them. This is the right approach because:

1. **Camera permissions are natural** — browser prompts for camera access, which users expect
2. **No system-level TCC headaches** — works regardless of which app launches the server
3. **FaceNet stays on the backend** — no torch.js in the browser, no 100MB model download to client
4. **Preserves sovereignty** — frames never leave localhost. Backend processes and discards them
5. **Works on any device** — if Luna runs on a Raspberry Pi in Kinoni, any browser on the same network can be the camera

---

## ARCHITECTURE

```
Browser (localhost:5173)                    Backend (localhost:8000)
┌─────────────────────────┐                ┌────────────────────────────┐
│                         │                │                            │
│  getUserMedia (camera)  │                │  POST /identity/recognize  │
│         │               │                │         │                  │
│  Canvas → JPEG (320px)  │── HTTP POST ──>│  Decode → FaceEncoder      │
│         │               │                │         │                  │
│  useIdentity hook       │<── JSON ───────│  IdentityMatcher           │
│         │               │                │         │                  │
│  IdentityBadge          │                │  Return IdentityResult     │
│  ChatPanel (tone shift) │                │  Emit engine events        │
│  FaceIDCapture (UI)     │                │  Update WebSocket clients  │
│                         │                │                            │
└─────────────────────────┘                └────────────────────────────┘
```

The existing WebSocket (`/ws/identity`) continues to push state changes. The new HTTP endpoint handles the actual frame-by-frame recognition. Both systems update the same `IdentityActor.current` state.

---

## PHASE 1: Backend — Frame Recognition Endpoint

### New Endpoint: `POST /identity/recognize`

Add to `src/luna/api/server.py`:

```python
from fastapi import UploadFile, File
import base64
import numpy as np
import cv2

@app.post("/identity/recognize")
async def recognize_frame(frame_data: dict):
    """
    Accept a base64 JPEG frame from the browser camera.
    Run face detection + matching. Return identity result.
    
    Request body:
    {
        "frame": "data:image/jpeg;base64,/9j/4AAQ...",
        "source": "browser"
    }
    
    Response:
    {
        "is_present": true,
        "entity_id": "entity_2ca6b7c7",
        "entity_name": "Ahab",
        "confidence": 0.987,
        "luna_tier": "admin",
        "dataroom_tier": 1
    }
    """
    identity_actor = _engine.get_actor("identity") if _engine else None
    if not identity_actor or not identity_actor._encoder:
        return {"is_present": False, "error": "FaceID not initialized"}
    
    # Decode base64 frame
    frame_b64 = frame_data.get("frame", "")
    if "," in frame_b64:
        frame_b64 = frame_b64.split(",")[1]  # Strip data:image/jpeg;base64, prefix
    
    frame_bytes = base64.b64decode(frame_b64)
    np_arr = np.frombuffer(frame_bytes, np.uint8)
    frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    
    if frame is None:
        return {"is_present": False, "error": "Invalid frame data"}
    
    # Run detection + matching (in executor to not block event loop)
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _recognize_frame, identity_actor, frame)
    
    return result


def _recognize_frame(identity_actor, frame):
    """Synchronous recognition on a decoded frame."""
    detections = identity_actor._encoder.detect_faces(frame)
    if not detections:
        return {"is_present": False}
    
    result = identity_actor._matcher.match_best_of_n(detections)
    
    if result.is_known:
        # Update the actor's current state (same as the camera loop would)
        import time
        identity_actor.current.entity_id = result.entity_id
        identity_actor.current.entity_name = result.entity_name
        identity_actor.current.confidence = result.confidence
        identity_actor.current.luna_tier = result.luna_tier
        identity_actor.current.dataroom_tier = result.dataroom_tier
        identity_actor.current.dataroom_categories = result.dataroom_categories
        identity_actor.current.last_seen = time.time()
        
        return {
            "is_present": True,
            "entity_id": result.entity_id,
            "entity_name": result.entity_name,
            "confidence": round(result.confidence, 3),
            "luna_tier": result.luna_tier,
            "dataroom_tier": result.dataroom_tier,
        }
    
    return {"is_present": False, "confidence": round(result.confidence, 3)}
```

### Modify IdentityActor for Dual-Source Recognition

The actor currently only recognizes via its own camera loop. It needs to also accept recognition results from the HTTP endpoint (browser camera). Two changes:

1. Make `_handle_recognition` callable from outside the actor's internal loop
2. When browser-sourced recognition happens, still emit engine events and notify WebSocket clients

In `src/luna/actors/identity.py`, add:

```python
async def recognize_from_frame(self, frame: np.ndarray) -> dict:
    """
    Run recognition on an externally-provided frame (e.g., from browser camera).
    Returns the same dict format as the internal _recognize_once.
    """
    if not self._encoder or not self._matcher:
        return None
    
    detections = self._encoder.detect_faces(frame)
    if not detections:
        return None
    
    result = self._matcher.match_best_of_n(detections)
    
    if result.is_known:
        match_data = {
            "entity_id": result.entity_id,
            "entity_name": result.entity_name,
            "confidence": result.confidence,
            "luna_tier": result.luna_tier,
            "dataroom_tier": result.dataroom_tier,
            "dataroom_categories": result.dataroom_categories,
        }
        await self._handle_recognition(match_data)
        return match_data
    
    return None
```

### CORS Note

The frontend runs on `:5173`, backend on `:8000`. The existing CORS middleware should already handle this. Verify that `POST /identity/recognize` works cross-origin. If not, ensure the middleware allows the `/identity/*` path.

---

## PHASE 2: Frontend — Browser Camera Component

### New Component: `FaceIDCapture.jsx`

```
frontend/src/components/FaceIDCapture.jsx
```

This component:
1. Requests browser camera permission via `getUserMedia`
2. Captures a frame every ~2 seconds (matching the actor's `RECOGNITION_INTERVAL`)
3. Sends the frame as base64 JPEG to `POST /identity/recognize`
4. Does NOT show a video feed (no creepy always-on camera view)
5. Shows a small camera icon/indicator while active
6. Auto-stops after successful recognition (session-based, not continuous)

**Behavior flow:**
```
Page load → show "Identify" button (camera icon)
   ↓
User clicks → browser camera permission prompt
   ↓
Permission granted → capture frames silently (no video preview)
   ↓
Frame sent to /identity/recognize every 2s
   ↓
Recognition successful → stop camera, show IdentityBadge
   ↓
Session continues without camera (identity held in state)
   ↓
IDENTITY_LOST event from WebSocket → optionally re-prompt
```

**Key implementation details:**

```jsx
// Capture at low resolution (320x240) — saves bandwidth, FaceNet doesn't need more
const constraints = {
  video: {
    width: { ideal: 320 },
    height: { ideal: 240 },
    facingMode: 'user',
  }
};

// Use a hidden <video> + <canvas> to grab frames
// Video element is not rendered in the DOM (or is visibility:hidden)
// Canvas is used to extract JPEG data

// Frame extraction:
const canvas = document.createElement('canvas');
canvas.width = 320;
canvas.height = 240;
const ctx = canvas.getContext('2d');
ctx.drawImage(videoElement, 0, 0, 320, 240);
const frameData = canvas.toDataURL('image/jpeg', 0.7); // 70% quality, ~15-30KB per frame

// Send to backend:
const response = await fetch('http://127.0.0.1:8000/identity/recognize', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ frame: frameData, source: 'browser' }),
});
```

**States the component should handle:**

| State | UI | Camera |
|-------|-----|--------|
| `idle` | Camera icon button, dimmed | Off |
| `requesting` | "Allow camera access" hint | Requesting permission |
| `denied` | "Camera access denied" message with settings link | Off |
| `scanning` | Subtle pulsing indicator (not a video feed) | On, capturing |
| `recognized` | Transitions to IdentityBadge | Off (camera released) |
| `failed` | "Couldn't recognize you" with retry button | Off |

### Style Notes

- No full video preview. Luna sees you; you don't see yourself through her eyes. This is a sovereignty choice — the camera is a perception tool, not a mirror.
- The scanning state should feel calm, not surveilling. A soft pulse or breathing animation on a small icon.
- Transition from scanning → recognized should feel like Luna "sees" you. A subtle warm shift. Maybe the orb changes color or brightens momentarily.
- The IdentityBadge (already built) takes over once recognition succeeds.

---

## PHASE 3: Modify useIdentity Hook

The existing `useIdentity.js` hook connects to `/ws/identity` and tracks state. It needs to also:

1. Expose a `startRecognition()` function that triggers the camera capture flow
2. Track the capture/recognition lifecycle state
3. Merge browser-initiated recognition with WebSocket-pushed state
4. Handle the case where backend camera (IdentityActor loop) and browser camera could both be active

```javascript
// Extended useIdentity API:
const {
  // Existing
  identity,
  isPresent,
  entityName,
  lunaTier,
  confidence,
  connected,
  
  // New
  captureState,        // 'idle' | 'requesting' | 'scanning' | 'recognized' | 'denied' | 'failed'
  startRecognition,    // () => void — trigger browser camera capture
  stopRecognition,     // () => void — stop camera, clean up
  cameraAvailable,     // boolean — is getUserMedia supported?
} = useIdentity();
```

---

## PHASE 4: Identity-Aware UI Transitions

Once identity is established, the UI should subtly shift:

### ChatPanel Adjustments

In `frontend/src/components/ChatPanel.jsx`:

- If `isPresent && entityName`, show a subtle greeting in the chat context (not a message, more like a status line: "Luna sees Ahab")
- The input placeholder could shift: "hey luna..." → "hey luna... (talking to Ahab)"
- This is light-touch. Don't make it feel like a login screen.

### Orb Response

If the orb (`LunaOrb.jsx` / `GradientOrb.jsx`) is rendered:

- On `IDENTITY_RECOGNIZED`: brief warm pulse (green for admin, blue for trusted, etc.)
- On `IDENTITY_LOST`: fade to neutral/dim state
- The orb already has expression states — this maps to the identity tier color scheme from `IdentityBadge.jsx`

### Engine Status

The `EngineStatus.jsx` component already reads `/status` which includes `identity` data. Verify it displays properly when FaceID is active.

---

## PHASE 5 (OPTIONAL): Browser-Based Enrollment

Currently enrollment happens via CLI (`python cli/enroll.py`). A browser-based enrollment flow would let new users register their face through the UI. This is a stretch goal but the architecture supports it:

### New Endpoint: `POST /identity/enroll`

```python
@app.post("/identity/enroll")
async def enroll_face(enrollment: dict):
    """
    Accept multiple base64 frames + entity metadata for enrollment.
    
    Request body:
    {
        "name": "Tarcila",
        "entity_id": "tarcila-001",  # optional, auto-generated if missing
        "luna_tier": "trusted",
        "dataroom_tier": 1,
        "dataroom_categories": [1,2,3,4,5,6,7,8,9],
        "frames": [
            "data:image/jpeg;base64,...",
            "data:image/jpeg;base64,...",
            ...
        ]
    }
    """
    # Admin-only: check current identity is admin tier
    # Process each frame through FaceEncoder
    # Store embeddings in FaceDatabase
    # Set up access_bridge entry
```

### New Component: `FaceIDEnroll.jsx`

- Admin-only (check `lunaTier === 'admin'` before showing)
- Step-by-step: name → camera → capture 5 angles → confirm → store
- Visual guide: "Look straight... now turn slightly left... now slightly right..."
- Shows captured face thumbnails for confirmation before storing

This is a Phase 2 feature. CLI enrollment works fine for now.

---

## KEY FILES TO TOUCH

### New Files

| File | Purpose |
|------|---------|
| `frontend/src/components/FaceIDCapture.jsx` | Browser camera capture + recognition trigger |
| `frontend/src/components/FaceIDEnroll.jsx` | Browser-based enrollment (Phase 2) |

### Modified Files

| File | Change |
|------|--------|
| `src/luna/api/server.py` | Add `POST /identity/recognize` endpoint, add `POST /identity/enroll` (Phase 2) |
| `src/luna/actors/identity.py` | Add `recognize_from_frame()` method for external frame input |
| `frontend/src/hooks/useIdentity.js` | Add `captureState`, `startRecognition()`, `stopRecognition()`, camera lifecycle |
| `frontend/src/App.jsx` | Wire `FaceIDCapture` into layout, pass identity state to ChatPanel and orb |
| `frontend/src/components/ChatPanel.jsx` | Light identity-aware hints (greeting line, input placeholder) |
| `frontend/src/components/IdentityBadge.jsx` | Already complete — verify it renders with live data |

### Files NOT To Touch

| File | Why |
|------|-----|
| `Tools/FaceID/src/*` | Prototype tools — already working, don't modify |
| `src/luna/core/events.py` | Event types already defined |
| `src/luna/engine.py` | Engine integration already complete |

---

## TESTING CHECKLIST

1. **Backend endpoint**: `curl -X POST http://127.0.0.1:8000/identity/recognize -H "Content-Type: application/json" -d '{"frame":"..."}'` — send a test base64 frame, verify response
2. **Browser camera**: Open `localhost:5173`, click identify, verify camera permission prompt appears
3. **Frame capture**: Verify frames are sent at ~2s intervals, responses come back quickly
4. **Recognition**: Enroll via CLI first (`python cli/enroll.py --name "Ahab" --luna-tier admin`), then verify browser recognizes you
5. **IdentityBadge**: Verify badge appears with correct name, tier, and color after recognition
6. **WebSocket**: Verify `/ws/identity` clients receive the update when browser-sourced recognition succeeds
7. **Camera cleanup**: Verify camera stops after successful recognition (check browser's camera indicator light)
8. **Denied permission**: Deny camera access, verify graceful fallback message
9. **No enrolled faces**: Clear the database, verify "couldn't recognize" state
10. **Engine prompt**: After browser recognition, send a chat message. Check that Luna's response reflects identity awareness (addresses user by name, appropriate tier behavior)

---

## NON-NEGOTIABLES

- **No video preview.** Luna sees you. You don't watch yourself through her eyes. The camera is a perception tool.
- **Frames stay on localhost.** Base64 JPEG travels from browser → backend on the same machine. Never to any external server.
- **Camera stops after recognition.** Session-based identity, not continuous surveillance.
- **Graceful degradation.** If camera is denied or FaceID fails, Luna still works — she just doesn't know who she's talking to.
- **Sovereignty preserved.** All face data in SQLite. All processing local. Move the file, move the identity knowledge.

---

## DEPENDENCIES

Backend (should already be installed if FaceID prototype works):
- `facenet-pytorch` — already in system Python 3.12
- `opencv-python-headless` — already installed (headless = no GUI needed for backend)
- `torch`, `torchvision`, `Pillow`, `numpy` — already installed

Frontend (no new dependencies):
- `getUserMedia` — native browser API
- `Canvas` — native browser API
- No new npm packages needed

---

## ORDER OF OPERATIONS

1. Add `POST /identity/recognize` to `server.py` — test with curl
2. Add `recognize_from_frame()` to `identity.py` — wire into endpoint
3. Build `FaceIDCapture.jsx` — get browser camera → backend → response working
4. Extend `useIdentity.js` — add capture lifecycle state
5. Wire into `App.jsx` — render FaceIDCapture, connect to identity state
6. Light-touch ChatPanel + orb updates
7. Test end-to-end: open browser → identify → chat with Luna as Ahab
