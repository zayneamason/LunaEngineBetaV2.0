"""
FaceID Microservice — Lightweight HTTP server for face detection, recognition, and enrollment.

Runs in the FaceID venv (which has torch, facenet_pytorch, cv2).
The main Luna server proxies requests here.

Usage:
    cd Tools/FaceID
    source .venv/bin/activate
    python serve.py          # Runs on :8100
    python serve.py --port 8100
"""

import argparse
import base64
import io
import json
import logging
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from http.server import HTTPServer, BaseHTTPRequestHandler

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))
from src.encoder import FaceEncoder
from src.database import FaceDatabase
from src.matcher import IdentityMatcher

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("faceid-serve")

DB_PATH = Path(__file__).parent / "data" / "faces.db"

# Global singletons (initialized once)
encoder: FaceEncoder = None
db: FaceDatabase = None
matcher: IdentityMatcher = None

# Rate limiter for enrollment: max 5 per minute
import time as _time
_enroll_timestamps: list = []
ENROLL_RATE_LIMIT = 5
ENROLL_RATE_WINDOW = 60  # seconds


def init():
    global encoder, db, matcher
    encoder = FaceEncoder()
    db = FaceDatabase(DB_PATH)
    db.connect()
    matcher = IdentityMatcher(db)
    logger.info(f"FaceID ready: model={encoder.model_name}, entities={len(db.list_entities())}")


def decode_frame(b64: str) -> np.ndarray:
    """Decode base64 JPEG → BGR numpy array."""
    if "," in b64:
        b64 = b64.split(",", 1)[1]
    raw = base64.b64decode(b64)
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    rgb = np.array(img)
    return rgb[:, :, ::-1].copy()  # RGB → BGR


def build_bboxes(detections):
    bboxes = []
    for det in detections:
        x, y, w, h = det.bbox
        if w > 0 and h > 0:
            bboxes.append({"x": x, "y": y, "w": w, "h": h,
                           "confidence": round(det.confidence, 3)})
    return bboxes


class FaceIDHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_len = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(content_len)) if content_len else {}

        if self.path == "/recognize":
            self._handle_recognize(body)
        elif self.path == "/enroll":
            self._handle_enroll(body)
        elif self.path == "/reset":
            self._handle_reset(body)
        else:
            self._json(404, {"error": "Not found"})

    def do_GET(self):
        if self.path == "/status":
            self._handle_status()
        elif self.path == "/health":
            self._json(200, {"ok": True})
        else:
            self._json(404, {"error": "Not found"})

    def _handle_recognize(self, body):
        frame_b64 = body.get("frame", "")
        if not frame_b64:
            return self._json(200, {"is_present": False, "error": "No frame"})

        try:
            frame = decode_frame(frame_b64)
        except Exception as e:
            return self._json(200, {"is_present": False, "error": str(e)})

        detections = encoder.detect_faces(frame)
        bboxes = build_bboxes(detections)

        if not detections:
            return self._json(200, {"is_present": False, "bboxes": []})

        result = matcher.match_best_of_n(detections)

        if result.is_known:
            return self._json(200, {
                "is_present": True,
                "entity_id": result.entity_id,
                "entity_name": result.entity_name,
                "confidence": round(result.confidence, 3),
                "luna_tier": result.luna_tier,
                "dataroom_tier": result.dataroom_tier,
                "bboxes": bboxes,
            })

        return self._json(200, {"is_present": False, "bboxes": bboxes})

    def _handle_enroll(self, body):
        # Rate limit: max ENROLL_RATE_LIMIT enrollments per ENROLL_RATE_WINDOW
        now = _time.time()
        _enroll_timestamps[:] = [t for t in _enroll_timestamps if now - t < ENROLL_RATE_WINDOW]
        if len(_enroll_timestamps) >= ENROLL_RATE_LIMIT:
            return self._json(200, {"enrolled": False, "error": "Rate limit exceeded. Try again later."})
        _enroll_timestamps.append(now)

        frame_b64 = body.get("frame", "")
        entity_name = body.get("entity_name", "Unknown")
        entity_id = body.get("entity_id")

        if not frame_b64:
            return self._json(200, {"enrolled": False, "error": "No frame"})

        try:
            frame = decode_frame(frame_b64)
        except Exception as e:
            return self._json(200, {"enrolled": False, "error": str(e)})

        detections = encoder.detect_faces(frame)
        bboxes = build_bboxes(detections)

        if not detections:
            return self._json(200, {"enrolled": False, "error": "No face detected", "bboxes": []})

        best = max(detections, key=lambda d: d.confidence)
        if best.confidence < 0.5:
            return self._json(200, {"enrolled": False, "error": "Low confidence",
                                     "confidence": round(best.confidence, 3), "bboxes": bboxes})

        if not entity_id:
            import hashlib
            entity_id = f"entity_{hashlib.md5(entity_name.encode()).hexdigest()[:8]}"

        db.store_embedding(
            entity_id=entity_id,
            entity_name=entity_name,
            embedding=best.embedding,
            model_name=encoder.model_name,
            quality=best.confidence,
            context="browser_enrollment",
        )

        # Authorization check: if any admin exists, require authorized_by
        existing = db.list_entities()
        admins = [e for e in existing if e.get("luna_tier") == "admin"]
        if admins:
            authorized_by = body.get("authorized_by")
            if not authorized_by:
                return self._json(200, {"enrolled": False,
                    "error": "Enrollment requires admin authorization (authorized_by)"})
            auth_bridge = db.get_access(authorized_by)
            if not auth_bridge or auth_bridge.luna_tier != "admin":
                return self._json(200, {"enrolled": False,
                    "error": "Authorizer is not an admin"})

        db.set_access(
            entity_id=entity_id,
            entity_name=entity_name,
            luna_tier=body.get("luna_tier", "guest"),
            dataroom_tier=body.get("dataroom_tier", 5),
            dataroom_categories=body.get("dataroom_categories", []),
            set_by=body.get("authorized_by", "bootstrap"),
        )

        matcher.invalidate_cache()
        count = db.count_embeddings(entity_id)

        self._json(200, {
            "enrolled": True,
            "entity_id": entity_id,
            "entity_name": entity_name,
            "confidence": round(best.confidence, 3),
            "count": count,
            "bboxes": bboxes,
        })

    def _handle_reset(self, body):
        pin = body.get("pin", "")

        # PIN gate disabled — skip verification
        # To re-enable: uncomment the PIN checks below
        # if not db.has_pin():
        #     return self._json(200, {"reset": False, "error": "No admin PIN configured. Set one first."})
        # if not db.verify_pin(pin):
        #     return self._json(200, {"reset": False, "error": "Incorrect PIN"})

        entities = db.list_entities()
        total = 0
        for e in entities:
            total += db.reset_entity(e["entity_id"])

        matcher.invalidate_cache()
        self._json(200, {"reset": True, "deleted": total})

    def _handle_status(self):
        entity_count = len(db.list_entities())
        total = db.count_embeddings()
        self._json(200, {
            "entity_count": entity_count,
            "total_embeddings": total,
            "has_pin": db.has_pin(),
        })

    def _json(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "http://localhost:5173")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "http://localhost:5173")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        # Quieter logging
        pass


def main():
    parser = argparse.ArgumentParser(description="FaceID microservice")
    parser.add_argument("--port", type=int, default=8100)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    init()

    server = HTTPServer((args.host, args.port), FaceIDHandler)
    logger.info(f"FaceID microservice running on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down")
        server.shutdown()


if __name__ == "__main__":
    main()
