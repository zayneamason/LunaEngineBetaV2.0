#!/usr/bin/env python3
"""
FaceID Enrollment CLI
=====================

Captures face embeddings from the MacBook camera and stores them
in Luna's face database. Admin-only operation.

Usage:
    python enroll.py --name "Ahab"
    python enroll.py --name "Ahab" --entity-id "ahab-001"
    python enroll.py --name "Ahab" --luna-tier admin --dr-tier 1 --dr-categories 1,2,3,4,5,6,7,8,9
    python enroll.py --name "Tarcila" --luna-tier trusted --dr-tier 1 --dr-categories 1,2,3,4,5,6,7,8,9

The camera opens, captures multiple angles, stores embeddings,
and sets up the access bridge entry.
"""

import sys
import os
import argparse
import time
import uuid
import cv2

# Add parent to path so we can import src
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.camera import Camera
from src.encoder import FaceEncoder
from src.database import FaceDatabase


def main():
    parser = argparse.ArgumentParser(description="Enroll a face into Luna's identity system")
    parser.add_argument("--name", required="--list-cameras" not in sys.argv, help="Person's name")
    parser.add_argument("--entity-id", default=None, help="Entity ID (auto-generated if not provided)")
    parser.add_argument("--luna-tier", default="unknown", 
                       choices=["admin", "trusted", "friend", "guest", "unknown"],
                       help="Luna relationship tier")
    parser.add_argument("--dr-tier", type=int, default=5,
                       help="Data room tier (1=Sovereign, 2=Strategist, 3=Domain Lead, 4=Advisor, 5=External)")
    parser.add_argument("--dr-categories", default="",
                       help="Comma-separated data room category numbers (e.g., '1,5,7')")
    parser.add_argument("--captures", type=int, default=5,
                       help="Number of face captures to store (default: 5)")
    parser.add_argument("--device", type=int, default=0,
                       help="Camera device ID (0=built-in, 1=next, etc. Use --list-cameras to see available)")
    parser.add_argument("--list-cameras", action="store_true",
                       help="List available cameras and exit")
    parser.add_argument("--db", default=None, help="Path to face database")
    args = parser.parse_args()
    
    # List cameras mode
    if args.list_cameras:
        print("\nScanning camera devices...")
        for i in range(5):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                ret, frame = cap.read()
                status = "OK" if ret and frame is not None else "no frames"
                print(f"  Device {i}: {w}x{h} ({status})")
                cap.release()
            else:
                print(f"  Device {i}: not available")
        print("\nUse --device N to select a camera.\n")
        sys.exit(0)

    entity_id = args.entity_id or f"entity_{uuid.uuid4().hex[:8]}"
    dr_categories = [int(x.strip()) for x in args.dr_categories.split(",") if x.strip()]
    
    print(f"\n{'='*50}")
    print(f"  LUNA FACEID ENROLLMENT")
    print(f"{'='*50}")
    print(f"  Name:            {args.name}")
    print(f"  Entity ID:       {entity_id}")
    print(f"  Luna Tier:       {args.luna_tier}")
    print(f"  Data Room Tier:  {args.dr_tier}")
    print(f"  DR Categories:   {dr_categories or 'none'}")
    print(f"  Captures:        {args.captures}")
    print(f"{'='*50}\n")
    
    # Initialize
    print("[1/4] Loading FaceNet model...")
    encoder = FaceEncoder()
    print(f"       Model: {encoder.model_name} ({encoder.embedding_dim}-dim)")
    
    print(f"[2/4] Opening camera (device {args.device})...")
    camera = Camera(device_id=args.device)
    if not camera.open():
        print("ERROR: Could not open camera. Check permissions.")
        print("       macOS: System Settings → Privacy & Security → Camera")
        sys.exit(1)
    
    print(f"[3/4] Capturing {args.captures} face samples...")
    print(f"       Look at the camera. Move your head slightly between captures.")
    print(f"       Press 'q' to finish early. Press 's' to skip a bad frame.\n")
    
    embeddings = []
    window_name = f"Enrolling: {args.name}"
    preview_size = (320, 240)  # Compact preview window

    # Create a resizable window at a small size
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, preview_size[0], preview_size[1])

    try:
        while len(embeddings) < args.captures:
            frame = camera.capture()
            if frame is None:
                continue

            # Detect faces
            detections = encoder.detect_faces(frame.image)

            # Draw on frame
            display = frame.image.copy()

            # Draw bounding boxes for all detected faces
            for det in detections:
                x, y, w, h = det.bbox
                if w > 0 and h > 0:
                    color = (0, 255, 0) if det.confidence > 0.7 else (0, 255, 255)
                    cv2.rectangle(display, (x, y), (x + w, y + h), color, 2)
                    cv2.putText(display, f"{det.confidence:.2f}",
                               (x, y - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

            # Status text
            status = f"Captured: {len(embeddings)}/{args.captures}"
            cv2.putText(display, status, (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

            if not detections:
                cv2.putText(display, "No face detected", (10, 60),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 1)

            # Resize for compact preview
            display = cv2.resize(display, preview_size)
            cv2.imshow(window_name, display)
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('q'):
                print(f"\n       Finished early with {len(embeddings)} captures.")
                break
            elif key == ord('s'):
                print(f"       Skipped frame.")
                continue
            
            # Auto-capture when a good face is detected
            if detections and detections[0].confidence > 0.7:
                embeddings.append(detections[0])
                print(f"       ✓ Capture {len(embeddings)}: confidence={detections[0].confidence:.3f}")
                
                # Brief pause between captures for different angles
                time.sleep(0.8)
    
    finally:
        camera.close()
        cv2.destroyAllWindows()
    
    if not embeddings:
        print("\nERROR: No faces captured. Try again with better lighting.")
        sys.exit(1)
    
    # Store in database
    print(f"\n[4/4] Storing {len(embeddings)} embeddings...")
    
    db_path = args.db
    with FaceDatabase(db_path) as db:
        # Store each embedding
        for i, det in enumerate(embeddings):
            db.store_embedding(
                entity_id=entity_id,
                entity_name=args.name,
                embedding=det.embedding,
                model_name=encoder.model_name,
                quality=det.confidence,
                context="enrollment",
            )
        
        # Set up access bridge
        db.set_access(
            entity_id=entity_id,
            entity_name=args.name,
            luna_tier=args.luna_tier,
            dataroom_tier=args.dr_tier,
            dataroom_categories=dr_categories,
            set_by="admin",
        )
        
        total = db.count_embeddings(entity_id)
        print(f"       Stored {len(embeddings)} new embeddings ({total} total for {args.name})")
    
    print(f"\n{'='*50}")
    print(f"  ENROLLMENT COMPLETE")
    print(f"  {args.name} is now known to Luna.")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
