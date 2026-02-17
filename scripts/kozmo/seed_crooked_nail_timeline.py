"""
Seed Script: Crooked Nail Timeline
====================================

Creates a test timeline for the 'crooked_nail' project with:
  - 5 containers (3 video shots, 1 score bed, 1 tracking shot)
  - 3 tracks (V1 video, A1 dialogue/foley, A2 score)
  - 1 group (SC1 Sync: Cornelius CU + Mordecai OTS)

Usage:
    python scripts/kozmo/seed_crooked_nail_timeline.py [--project-root PATH]

If no --project-root, creates under data/kozmo_projects/crooked_nail/
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from luna.services.kozmo.timeline_types import (
    Timeline, Track, TrackType, Container, Clip, ContainerGroup,
    MediaAssetRef, MediaType, CameraMetadata,
)
from luna.services.kozmo.timeline_store import save_timeline
from luna.services.kozmo.project import create_project


def build_crooked_nail_timeline() -> Timeline:
    """Build the Crooked Nail test timeline from handoff spec."""

    # ── Helper to build Clips with MediaAssetRef ───────────────────────
    def _clip(cid, aid, mtype, dur, in_pt=0.0):
        return Clip(
            id=cid,
            asset_ref=MediaAssetRef(asset_id=aid, path=f"assets/{aid}", duration=dur, media_type=mtype),
            in_point=in_pt,
            out_point=dur,
        )

    # ── Containers ────────────────────────────────────────────────────────
    ct01 = Container(
        id="ct01",
        label="Crooked Nail — Wide",
        track_id="v1",
        position=0.0,
        duration=4.2,
        locked=False,
        clips=[
            _clip("cl01", "a01", MediaType.VIDEO, 4.2),
            _clip("cl02", "a02", MediaType.AUDIO, 4.2),
        ],
        camera=CameraMetadata(body="arri_alexa35", lens="panavision_c", focal_length=40, aperture=2.8, movement="dolly_in"),
    )

    ct02 = Container(
        id="ct02",
        label="Cornelius CU",
        track_id="v1",
        position=4.2,
        duration=2.8,
        locked=True,
        group_id="grp01",
        clips=[
            _clip("cl03", "a03", MediaType.VIDEO, 2.8),
            _clip("cl04", "a04", MediaType.AUDIO, 2.5),
        ],
        camera=CameraMetadata(body="arri_alexa35", lens="cooke_s7i", focal_length=85, aperture=1.4, movement="static"),
    )

    ct03 = Container(
        id="ct03",
        label="Mordecai OTS",
        track_id="v1",
        position=7.0,
        duration=3.8,
        locked=False,
        group_id="grp01",
        clips=[
            _clip("cl05", "a06", MediaType.VIDEO, 3.8),
            _clip("cl06", "a08", MediaType.AUDIO, 3.2),
        ],
        camera=CameraMetadata(body="arri_alexa35", lens="panavision_c", focal_length=50, aperture=2.0, movement="pan_right + dolly_in"),
    )

    ct04 = Container(
        id="ct04",
        label="Score — Tension",
        track_id="a2",
        position=0.0,
        duration=12.0,
        locked=False,
        clips=[
            _clip("cl07", "a07", MediaType.AUDIO, 12.0),
        ],
    )

    ct05 = Container(
        id="ct05",
        label="Road — Tracking",
        track_id="v1",
        position=10.8,
        duration=5.5,
        locked=False,
        clips=[
            _clip("cl08", "a09", MediaType.VIDEO, 5.5),
        ],
        camera=CameraMetadata(body="red_v_raptor", lens="zeiss_supreme", focal_length=24, aperture=5.6, movement="steadicam"),
    )

    # ── Tracks ────────────────────────────────────────────────────────────
    tracks = [
        Track(id="v1", label="V1", track_type=TrackType.VIDEO, container_ids=["ct01", "ct02", "ct03", "ct05"]),
        Track(id="a1", label="A1", track_type=TrackType.AUDIO, container_ids=["ct01", "ct02", "ct03"]),
        Track(id="a2", label="A2", track_type=TrackType.AUDIO, container_ids=["ct04"]),
    ]

    # ── Groups ────────────────────────────────────────────────────────────
    groups = {
        "grp01": ContainerGroup(id="grp01", label="SC1 Sync", container_ids=["ct02", "ct03"]),
    }

    # ── Timeline ──────────────────────────────────────────────────────────
    tl = Timeline(
        tracks=tracks,
        containers={
            "ct01": ct01, "ct02": ct02, "ct03": ct03, "ct04": ct04, "ct05": ct05,
        },
        groups=groups,
        total_duration=16.3,
    )

    return tl


def main():
    parser = argparse.ArgumentParser(description="Seed Crooked Nail timeline")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="Project root directory. Defaults to data/kozmo_projects/crooked_nail/",
    )
    args = parser.parse_args()

    if args.project_root:
        project_root = args.project_root
    else:
        projects_root = Path("data/kozmo_projects")
        project_root = projects_root / "crooked_nail"

        # Create project if it doesn't exist
        if not (project_root / "manifest.yaml").exists():
            print("Creating crooked_nail project...")
            create_project(projects_root, "Crooked Nail", slug="crooked_nail")

    print(f"Seeding timeline at: {project_root}")
    tl = build_crooked_nail_timeline()
    save_timeline(project_root, tl)

    print(f"  {len(tl.containers)} containers")
    print(f"  {len(tl.tracks)} tracks")
    print(f"  {len(tl.groups)} groups")
    print(f"  {tl.total_duration}s total duration")
    print("Done.")


if __name__ == "__main__":
    main()
