#!/usr/bin/env python3
"""
FaceID Reset CLI
================

PIN-gated reset: wipes face embeddings and re-enrolls via camera.
First run sets the PIN. Subsequent runs require it.

Usage:
    python reset.py --name "Ahab"
    python reset.py --name "Ahab" --set-pin       # Change PIN
    python reset.py --name "Ahab" --device 0       # Pick camera
"""

import sys
import os
import argparse
import getpass
import time
import cv2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.camera import Camera
from src.encoder import FaceEncoder
from src.database import FaceDatabase


def prompt_pin(label: str = "Enter 4-digit PIN") -> str:
    """Prompt for a 4-digit PIN with validation."""
    while True:
        pin = getpass.getpass(f"{label}: ")
        if len(pin) == 4 and pin.isdigit():
            return pin
        print("  PIN must be exactly 4 digits.")


def main():
    parser = argparse.ArgumentParser(description="PIN-gated FaceID reset & re-enrollment")
    parser.add_argument("--name", required=True, help="Entity name to reset")
    parser.add_argument("--set-pin", action="store_true", help="Set or change the admin PIN")
    parser.add_argument("--device", type=int, default=0, help="Camera device ID")
    parser.add_argument("--captures", type=int, default=10, help="Number of captures for re-enrollment")
    parser.add_argument("--db", default=None, help="Path to face database")
    args = parser.parse_args()

    with FaceDatabase(args.db) as db:
        # ── First-time setup: create PIN ──
        if not db.has_pin():
            print("\n  No admin PIN set. Let's create one now.")
            pin = prompt_pin("Create 4-digit PIN")
            confirm = prompt_pin("Confirm PIN")
            if pin != confirm:
                print("  PINs don't match. Aborting.")
                sys.exit(1)
            db.set_pin(pin)
            print("  PIN saved.\n")

        # ── Change PIN mode ──
        if args.set_pin:
            old = prompt_pin("Current PIN")
            if not db.verify_pin(old):
                print("  Incorrect PIN. Aborting.")
                sys.exit(1)
            new = prompt_pin("New 4-digit PIN")
            confirm = prompt_pin("Confirm new PIN")
            if new != confirm:
                print("  PINs don't match. Aborting.")
                sys.exit(1)
            db.set_pin(new)
            print("  PIN updated.\n")
            sys.exit(0)

        # ── Verify PIN ──
        pin = prompt_pin("Enter admin PIN to reset")
        if not db.verify_pin(pin):
            print("\n  Incorrect PIN. Reset denied.")
            db._log("reset_denied", details=f"Failed PIN attempt for {args.name}")
            sys.exit(1)

        # ── Find entity ──
        entities = db.list_entities()
        match = [e for e in entities if e["entity_name"].lower() == args.name.lower()]
        if not match:
            print(f"\n  No entity named '{args.name}' found in database.")
            print(f"  Known entities: {[e['entity_name'] for e in entities] or 'none'}")
            sys.exit(1)

        entity = match[0]
        entity_id = entity["entity_id"]

        print(f"\n{'='*50}")
        print(f"  FACEID RESET")
        print(f"{'='*50}")
        print(f"  Entity:    {entity['entity_name']}")
        print(f"  Entity ID: {entity_id}")
        print(f"  Current:   {entity['face_count']} embeddings")
        print(f"{'='*50}\n")

        # ── Wipe embeddings ──
        deleted = db.reset_entity(entity_id)
        print(f"  Deleted {deleted} embeddings.\n")

    # ── Re-enroll with camera ──
    print("[1/3] Loading FaceNet model...")
    encoder = FaceEncoder()

    print(f"[2/3] Opening camera (device {args.device})...")
    camera = Camera(device_id=args.device)
    if not camera.open():
        print("ERROR: Could not open camera.")
        sys.exit(1)

    print(f"[3/3] Capturing {args.captures} face samples...")
    print(f"       Look at the camera. Move slightly between captures.")
    print(f"       Press 'q' to finish early.\n")

    embeddings = []
    window_name = f"Re-enrolling: {args.name}"

    try:
        while len(embeddings) < args.captures:
            frame = camera.capture()
            if frame is None:
                continue

            detections = encoder.detect_faces(frame.image)
            display = frame.image.copy()

            # Draw bounding boxes for all detected faces
            for det in detections:
                x, y, w, h = det.bbox
                if w > 0 and h > 0:
                    color = (0, 255, 0) if det.confidence > 0.7 else (0, 255, 255)
                    cv2.rectangle(display, (x, y), (x + w, y + h), color, 2)
                    cv2.putText(display, f"{det.confidence:.2f}",
                                (x, y - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

            # Status overlay
            cv2.putText(display, f"Captured: {len(embeddings)}/{args.captures}",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

            if not detections:
                cv2.putText(display, "No face detected", (10, 60),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 1)

            cv2.imshow(window_name, display)
            key = cv2.waitKey(1) & 0xFF

            if key == ord('q'):
                print(f"\n  Finished early with {len(embeddings)} captures.")
                break

            # Auto-capture
            if detections and detections[0].confidence > 0.7:
                embeddings.append(detections[0])
                print(f"  Capture {len(embeddings)}: confidence={detections[0].confidence:.3f}")
                time.sleep(0.8)

    finally:
        camera.close()
        cv2.destroyAllWindows()

    if not embeddings:
        print("\nERROR: No faces captured. Embeddings wiped but not re-enrolled.")
        print("       Run enroll.py to re-enroll manually.")
        sys.exit(1)

    # ── Store new embeddings ──
    with FaceDatabase(args.db) as db:
        for det in embeddings:
            db.store_embedding(
                entity_id=entity_id,
                entity_name=args.name,
                embedding=det.embedding,
                model_name=encoder.model_name,
                quality=det.confidence,
                context="pin_reset",
            )
        total = db.count_embeddings(entity_id)
        print(f"\n  Stored {len(embeddings)} new embeddings ({total} total)")

    print(f"\n{'='*50}")
    print(f"  RESET COMPLETE")
    print(f"  {args.name}'s face has been re-enrolled.")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
