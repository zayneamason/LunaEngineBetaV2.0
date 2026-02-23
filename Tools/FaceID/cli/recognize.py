#!/usr/bin/env python3
"""
FaceID Recognition CLI
======================

Opens the MacBook camera and performs live face recognition
against enrolled faces. Shows identity, confidence, and tier
in real time.

Usage:
    python recognize.py
    python recognize.py --threshold 0.6
    python recognize.py --db /path/to/faces.db

Press 'q' to quit.
"""

import sys
import os
import argparse
import cv2
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.camera import Camera
from src.encoder import FaceEncoder
from src.database import FaceDatabase
from src.matcher import IdentityMatcher


# Colors (BGR)
GREEN = (0, 255, 0)
YELLOW = (0, 255, 255)
RED = (0, 0, 255)
WHITE = (255, 255, 255)
GRAY = (150, 150, 150)


def tier_color(luna_tier: str) -> tuple:
    """Color-code by Luna tier."""
    return {
        "admin": (0, 255, 0),       # Green
        "trusted": (255, 200, 0),    # Cyan-ish
        "friend": (0, 200, 255),     # Orange-ish
        "guest": (200, 200, 200),    # Gray
        "unknown": (0, 0, 255),      # Red
    }.get(luna_tier, RED)


def main():
    parser = argparse.ArgumentParser(description="Live face recognition with Luna FaceID")
    parser.add_argument("--threshold", type=float, default=0.55,
                       help="Match confidence threshold (default: 0.55)")
    parser.add_argument("--db", default=None, help="Path to face database")
    args = parser.parse_args()
    
    print(f"\n{'='*50}")
    print(f"  LUNA FACEID — LIVE RECOGNITION")
    print(f"{'='*50}")
    
    # Initialize
    print("Loading FaceNet model...")
    encoder = FaceEncoder()
    
    db = FaceDatabase(args.db)
    db.connect()
    
    matcher = IdentityMatcher(db)
    matcher.MATCH_THRESHOLD = args.threshold
    
    # Show enrolled entities
    entities = db.list_entities()
    if not entities:
        print("\nWARNING: No faces enrolled. Run enroll.py first.")
        print("         Recognition will show all faces as 'unknown'.\n")
    else:
        print(f"\nEnrolled entities ({len(entities)}):")
        for e in entities:
            print(f"  • {e['entity_name']} — luna:{e['luna_tier']}, dr:{e['dataroom_tier']}, faces:{e['face_count']}")
    
    print(f"\nThreshold: {args.threshold}")
    print("Press 'q' to quit.\n")
    
    camera = Camera()
    if not camera.open():
        print("ERROR: Could not open camera.")
        db.close()
        sys.exit(1)
    
    window_name = "Luna FaceID — Live Recognition"
    fps_start = time.time()
    frame_count = 0
    fps = 0.0
    
    # Throttle detection to every N frames for performance
    DETECT_EVERY = 3
    last_results = []
    
    try:
        while True:
            frame = camera.capture()
            if frame is None:
                continue
            
            frame_count += 1
            display = frame.image.copy()
            
            # Run detection every N frames
            if frame_count % DETECT_EVERY == 0:
                detections = encoder.detect_faces(frame.image)
                last_results = []
                
                for det in detections:
                    result = matcher.match(det)
                    last_results.append((det, result))
            
            # Draw results
            for det, result in last_results:
                x, y, w, h = det.bbox
                color = tier_color(result.luna_tier)
                
                # Bounding box
                thickness = 2 if result.is_known else 1
                cv2.rectangle(display, (x, y), (x + w, y + h), color, thickness)
                
                # Identity label
                if result.is_known:
                    label = f"{result.entity_name} ({result.confidence:.2f})"
                    tier_label = f"luna:{result.luna_tier} | dr:{result.dataroom_tier}"
                else:
                    label = f"unknown ({result.confidence:.2f})"
                    tier_label = ""
                
                # Background rectangle for text
                (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
                cv2.rectangle(display, (x, y - th - 14), (x + tw + 4, y - 2), color, -1)
                cv2.putText(display, label, (x + 2, y - 6),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)
                
                if tier_label:
                    cv2.putText(display, tier_label, (x, y + h + 18),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)
            
            # FPS counter
            elapsed = time.time() - fps_start
            if elapsed > 1.0:
                fps = frame_count / elapsed
                frame_count = 0
                fps_start = time.time()
            
            cv2.putText(display, f"FPS: {fps:.1f}", (10, 25),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, GRAY, 1)
            
            if not entities:
                cv2.putText(display, "No faces enrolled — run enroll.py", 
                           (10, display.shape[0] - 15),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, RED, 1)
            
            cv2.imshow(window_name, display)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
    
    finally:
        camera.close()
        cv2.destroyAllWindows()
        db.close()
    
    print("\nRecognition stopped.")


if __name__ == "__main__":
    main()
