"""
One-time migration: parse [[VISUAL]] from existing brief prompts.

Cleans up raw [[VISUAL timecode — prompt]] syntax in prompt/title fields,
extracts audio_start/audio_end timecodes, and links audio_track_id.

Usage:
    python scripts/migrate_briefs.py
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import yaml
from luna.services.kozmo.scribo_parser import extract_visual_annotations
from luna.services.kozmo.audio_timeline import AudioTimelineService

PROJECT_ROOT = Path(__file__).resolve().parent.parent / "data" / "kozmo_projects" / "luna-manifesto"
BRIEFS_DIR = PROJECT_ROOT / "lab" / "briefs"


def migrate():
    if not BRIEFS_DIR.exists():
        print(f"Briefs directory not found: {BRIEFS_DIR}")
        return

    audio_svc = AudioTimelineService(PROJECT_ROOT)
    migrated = 0

    for brief_file in sorted(BRIEFS_DIR.glob("*.yaml")):
        data = yaml.safe_load(brief_file.read_text(encoding="utf-8"))
        if not data:
            continue

        prompt = data.get("prompt", "")
        visuals = extract_visual_annotations(prompt)
        if not visuals:
            continue

        v = visuals[0]
        data["prompt"] = v["prompt"]
        data["title"] = v["prompt"][:80]
        data["audio_start"] = v["start_seconds"]
        data["audio_end"] = v["end_seconds"]

        track = audio_svc.get_track_at_time(v["start_seconds"])
        if track:
            data["audio_track_id"] = track.id

        brief_file.write_text(
            yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        migrated += 1
        print(f"  Migrated {brief_file.name}: {v['prompt'][:60]}...")

    print(f"\nDone. Migrated {migrated} briefs.")


if __name__ == "__main__":
    migrate()
