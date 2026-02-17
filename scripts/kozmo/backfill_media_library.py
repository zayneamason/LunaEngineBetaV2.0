"""
Backfill media_library.yaml from existing briefs + assets on disk.

Scans lab/briefs/*.yaml for any brief with hero_frame set.
Cross-references with lab/assets/ for file existence.
Creates media_library.yaml entries for each.

Usage:
  python scripts/kozmo/backfill_media_library.py luna-manifesto
"""
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

from luna.services.kozmo.media_library import MediaLibraryService
from luna.services.kozmo.lab_pipeline import LabPipelineService


def backfill(project_slug: str):
    project_root = ROOT / "data" / "kozmo_projects" / project_slug
    if not project_root.exists():
        print(f"Project not found: {project_root}")
        sys.exit(1)

    lab = LabPipelineService(project_root)
    media = MediaLibraryService(project_root)

    briefs = lab.list_briefs()
    registered = 0

    for brief in briefs:
        if not brief.hero_frame:
            continue

        # Check file exists
        asset_path = project_root / brief.hero_frame
        if not asset_path.exists():
            print(f"  SKIP {brief.id} -- hero_frame points to missing file: {brief.hero_frame}")
            continue

        # Check not already registered
        existing = media.list_assets(brief_id=brief.id)
        if existing:
            print(f"  SKIP {brief.id} -- already in library")
            continue

        # Register
        filename = Path(brief.hero_frame).name
        asset = media.register_asset(
            filename=filename,
            path=brief.hero_frame,
            source="eden",
            brief_id=brief.id,
            scene_slug=getattr(brief, "source_scene", None),
            audio_track_id=getattr(brief, "audio_track_id", None),
            audio_start=getattr(brief, "audio_start", None),
            audio_end=getattr(brief, "audio_end", None),
            eden_task_id=getattr(brief, "eden_task_id", None),
            prompt=brief.prompt,
        )
        print(f"  + Registered {asset.id} <- {brief.id} ({filename})")
        registered += 1

    print(f"\nDone. Registered {registered} assets.")
    print(f"Library: {media.index_path}")


if __name__ == "__main__":
    slug = sys.argv[1] if len(sys.argv) > 1 else "luna-manifesto"
    backfill(slug)
