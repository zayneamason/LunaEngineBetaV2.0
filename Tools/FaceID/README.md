# Luna FaceID Prototype

Local face recognition for Luna's identity-gated sovereignty system.
Runs entirely on-device. No cloud. No data leaves the machine.

## Stack

- **FaceNet** (facenet-pytorch) — face embeddings via InceptionResnetV1/VGGFace2
- **MTCNN** — face detection + alignment
- **OpenCV** — camera capture
- **SQLite** — embedding storage + access bridge

## Setup

```bash
cd Tools/FaceID
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

First run will download the FaceNet model (~100MB). This happens once.

## Usage

### Enroll yourself (admin)
```bash
python cli/enroll.py --name "Ahab" --luna-tier admin --dr-tier 1 --dr-categories 1,2,3,4,5,6,7,8,9
```

Camera opens. Look at it. Move your head slightly between captures.
It grabs 5 angles automatically. Press `q` to finish early.

### Enroll someone else
```bash
python cli/enroll.py --name "Tarcila" --luna-tier trusted --dr-tier 1 --dr-categories 1,2,3,4,5,6,7,8,9
python cli/enroll.py --name "Cliff" --luna-tier friend --dr-tier 2 --dr-categories 1,2,3,4,5,6,7,8,9
python cli/enroll.py --name "Calvin" --luna-tier trusted --dr-tier 3 --dr-categories 1,5,7
python cli/enroll.py --name "Hai Dai" --luna-tier friend --dr-tier 3 --dr-categories 8
```

### Live recognition
```bash
python cli/recognize.py
```

Opens camera, identifies faces in real time. Shows name, confidence, 
and both tier assignments. Color-coded by Luna tier. Press `q` to quit.

### Check status
```bash
python cli/status.py
```

Shows enrolled entities, embedding counts, and recent identity events.

## Architecture

```
MacBook Camera
    → MTCNN (face detection + alignment)
        → FaceNet InceptionResnetV1 (512-dim embedding)
            → Cosine similarity vs stored embeddings (SQLite)
                → IdentityResult (entity_id + both tiers)
```

## Files

```
Tools/FaceID/
├── README.md
├── requirements.txt
├── src/
│   ├── camera.py       — MacBook camera capture
│   ├── encoder.py      — FaceNet detection + embedding
│   ├── database.py     — SQLite storage + access bridge
│   └── matcher.py      — Cosine similarity matching
├── cli/
│   ├── enroll.py       — Capture + store faces
│   ├── recognize.py    — Live recognition
│   └── status.py       — Database inspector
└── data/
    └── faces.db        — Created on first enrollment
```

## Sovereignty

- All face embeddings stay in `data/faces.db`
- No network requests. No cloud. No telemetry.
- Copy the .db file → copy the identity knowledge
- Delete the .db file → all face data gone
- "Luna is a file" — face recognition included

## Integration Path

This prototype proves the pipeline. When ready to integrate into
the Luna Engine:

1. Move `src/` modules into `src/luna/identity/`
2. Swap SQLite to async (aiosqlite, matching engine's database.py)
3. Wire IdentityResult into Director.process()
4. Add RELATIONSHIP layer to PromptAssembler
5. Connect access_bridge to the data room document filter

See: `Docs/Handoffs/FacialRec/ARCHITECTURE_IDENTITY_GATED_SOVEREIGNTY.md`
See: `Dual_Tier_Bridge_Architecture.docx`

## Hardware Notes

- **M1 MacBook Air 8GB**: Works. FaceNet model is ~100MB in memory.
  Detection runs ~10-15 FPS with DETECT_EVERY=3 throttling.
- **Camera permissions**: macOS requires camera access grant.
  System Settings → Privacy & Security → Camera → Terminal (or your IDE)
