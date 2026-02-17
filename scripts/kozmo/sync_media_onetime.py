"""
One-time sync of existing assets to external media directory.

Copies generated PNGs with meaningful scene-based filenames.
Run after backfill_media_library.py has seeded the index.

Usage:
  python scripts/kozmo/sync_media_onetime.py [target_dir]
"""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
PROJECT = ROOT / "data" / "kozmo_projects" / "luna-manifesto"
DEFAULT_TARGET = ROOT / "Docs" / "Design" / "Development" / "Media"

# Map of brief_id -> (scene_slug, asset_filename)
ASSETS = {
    "pb_02f8b779": ("sc_09_bella_im_a_file", "pb_02f8b779.png"),
    "pb_18baca3e": ("sc_18_maria_clara_soil", "pb_18baca3e.png"),
    "pb_5cc0efb8": ("sc_01_bella_opening", "pb_5cc0efb8.png"),
}


def sync(target_dir: Path):
    target_dir.mkdir(parents=True, exist_ok=True)
    synced = 0

    for brief_id, (scene, filename) in ASSETS.items():
        src = PROJECT / "lab" / "assets" / filename
        dst = target_dir / f"{scene}_{brief_id}.png"
        if src.exists():
            shutil.copy2(src, dst)
            print(f"  + {dst.name}")
            synced += 1
        else:
            print(f"  x Missing: {src}")

    print(f"\nDone. Synced {synced}/{len(ASSETS)} assets to {target_dir}")


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_TARGET
    sync(target)
