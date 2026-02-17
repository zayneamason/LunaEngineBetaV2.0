"""
Tests for KOZMO Timeline Phase 3 — Integration
================================================
Covers:
- container_id on ProductionBrief
- MediaAsset.to_asset_ref() conversion
- LabPipelineService.auto_create_container()
- Full LAB → Timeline pipeline
"""

import pytest
from pathlib import Path

from luna.services.kozmo.types import ProductionBrief, MediaAsset
from luna.services.kozmo.lab_pipeline import LabPipelineService
from luna.services.kozmo.timeline_types import (
    Timeline, Track, TrackType, MediaType, MediaAssetRef,
)
from luna.services.kozmo.timeline_service import TimelineService
from luna.services.kozmo.timeline_store import load_timeline, save_timeline


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def project_root(tmp_path):
    """Create a minimal project structure."""
    (tmp_path / "manifest.yaml").write_text("name: test\nslug: test\n")
    (tmp_path / "lab" / "briefs").mkdir(parents=True)
    (tmp_path / "lab" / "assets").mkdir(parents=True)
    return tmp_path


@pytest.fixture
def project_with_timeline(project_root):
    """Project with timeline seeded with V1, A1 tracks."""
    tl = Timeline(tracks=[
        Track(id="v1", label="V1", track_type=TrackType.VIDEO),
        Track(id="a1", label="A1", track_type=TrackType.AUDIO),
    ])
    save_timeline(project_root, tl)
    return project_root


@pytest.fixture
def lab(project_root):
    return LabPipelineService(project_root)


# ── ProductionBrief.container_id ──────────────────────────────────────────────


class TestBriefContainerId:
    def test_container_id_default_none(self):
        brief = ProductionBrief(id="pb_001", type="single", title="Test", prompt="test")
        assert brief.container_id is None

    def test_container_id_set(self):
        brief = ProductionBrief(
            id="pb_001", type="single", title="Test", prompt="test",
            container_id="abc123def456",
        )
        assert brief.container_id == "abc123def456"

    def test_container_id_serializes(self):
        brief = ProductionBrief(
            id="pb_001", type="single", title="Test", prompt="test",
            container_id="abc123def456",
        )
        d = brief.model_dump()
        assert d["container_id"] == "abc123def456"

    def test_container_id_round_trip_yaml(self, project_root, lab):
        """container_id persists through YAML save/load cycle."""
        brief = ProductionBrief(
            id="pb_001", type="single", title="Test", prompt="test",
            container_id="abc123",
        )
        created = lab.create_brief(brief)
        loaded = lab.get_brief("pb_001")
        assert loaded.container_id == "abc123"


# ── MediaAsset.to_asset_ref() ────────────────────────────────────────────────


class TestToAssetRef:
    def test_video_asset(self):
        asset = MediaAsset(
            id="asset_001", type="video", filename="shot.mp4",
            path="lab/assets/shot.mp4", source="eden", duration=10.0,
        )
        ref = asset.to_asset_ref()
        assert isinstance(ref, MediaAssetRef)
        assert ref.asset_id == "asset_001"
        assert ref.path == "lab/assets/shot.mp4"
        assert ref.duration == 10.0
        assert ref.media_type == MediaType.VIDEO

    def test_image_asset(self):
        asset = MediaAsset(
            id="asset_002", type="image", filename="hero.png",
            path="lab/assets/hero.png", source="eden", duration=None,
        )
        ref = asset.to_asset_ref()
        assert ref.duration == 3.0  # Default for images
        assert ref.media_type == MediaType.IMAGE

    def test_audio_asset(self):
        asset = MediaAsset(
            id="asset_003", type="audio", filename="score.wav",
            path="assets/audio/score.wav", source="import", duration=120.0,
        )
        ref = asset.to_asset_ref()
        assert ref.duration == 120.0
        assert ref.media_type == MediaType.AUDIO

    def test_unknown_type_fallback(self):
        asset = MediaAsset(
            id="asset_004", type="unknown", filename="gen.ai",
            path="lab/gen.ai", source="eden",
        )
        ref = asset.to_asset_ref()
        assert ref.media_type == MediaType.GENERATIVE
        assert ref.duration == 3.0  # Default


# ── auto_create_container ─────────────────────────────────────────────────────


class TestAutoCreateContainer:
    def test_creates_container_on_timeline(self, project_with_timeline, lab):
        """auto_create_container places a container on the video track."""
        brief = ProductionBrief(
            id="pb_auto", type="single", title="Wide Shot", prompt="test",
        )
        lab.create_brief(brief)

        cid = lab.auto_create_container(
            "pb_auto", asset_path="lab/assets/pb_auto.png", duration=3.0,
        )
        assert cid is not None

        # Verify timeline has the container
        tl = load_timeline(project_with_timeline)
        assert cid in tl.containers
        ct = tl.containers[cid]
        assert ct.label == "Wide Shot"
        assert ct.brief_id == "pb_auto"
        assert ct.duration == 3.0

        # Verify brief was updated with container_id
        updated_brief = lab.get_brief("pb_auto")
        assert updated_brief.container_id == cid

    def test_positions_at_audio_start(self, project_with_timeline, lab):
        """If brief has audio_start, container is placed there."""
        brief = ProductionBrief(
            id="pb_pos", type="single", title="Timed Shot", prompt="test",
            audio_start=15.0,
        )
        lab.create_brief(brief)

        cid = lab.auto_create_container("pb_pos", "lab/assets/pb_pos.png", 3.0)
        tl = load_timeline(project_with_timeline)
        assert tl.containers[cid].position == 15.0

    def test_positions_at_end_when_no_audio_start(self, project_with_timeline, lab):
        """Without audio_start, container goes at end of timeline."""
        # First, put something on the timeline
        svc = TimelineService()
        tl = load_timeline(project_with_timeline)
        asset = MediaAssetRef(
            asset_id="existing", path="test.mp4", duration=10.0,
            media_type=MediaType.VIDEO,
        )
        svc.create_container(tl, asset, "v1", 0.0, "Existing")
        save_timeline(project_with_timeline, tl)

        brief = ProductionBrief(
            id="pb_end", type="single", title="Appended", prompt="test",
        )
        lab.create_brief(brief)

        cid = lab.auto_create_container("pb_end", "lab/assets/pb_end.png", 3.0)
        tl = load_timeline(project_with_timeline)
        assert tl.containers[cid].position == 10.0  # Right after existing

    def test_skips_if_already_bound(self, project_with_timeline, lab):
        """If brief already has a container_id, skip creation."""
        brief = ProductionBrief(
            id="pb_skip", type="single", title="Already Bound", prompt="test",
            container_id="existing_container",
        )
        lab.create_brief(brief)

        result = lab.auto_create_container("pb_skip", "lab/assets/skip.png", 3.0)
        assert result == "existing_container"

    def test_skips_if_no_tracks(self, project_root, lab):
        """Returns None if timeline has no tracks."""
        # Save empty timeline (no tracks)
        save_timeline(project_root, Timeline())

        brief = ProductionBrief(
            id="pb_notrack", type="single", title="No Tracks", prompt="test",
        )
        lab.create_brief(brief)

        result = lab.auto_create_container("pb_notrack", "lab/assets/notrack.png", 3.0)
        assert result is None

    def test_skips_if_brief_not_found(self, project_with_timeline, lab):
        result = lab.auto_create_container("nonexistent", "path.png", 3.0)
        assert result is None

    def test_overlap_returns_none(self, project_with_timeline, lab):
        """If position would overlap, auto_create returns None."""
        # Pre-fill position 0-10 on V1
        svc = TimelineService()
        tl = load_timeline(project_with_timeline)
        asset = MediaAssetRef(
            asset_id="blocker", path="blocker.mp4", duration=10.0,
            media_type=MediaType.VIDEO,
        )
        svc.create_container(tl, asset, "v1", 0.0, "Blocker")
        save_timeline(project_with_timeline, tl)

        brief = ProductionBrief(
            id="pb_overlap", type="single", title="Overlap", prompt="test",
            audio_start=5.0,  # Would land inside [0, 10)
        )
        lab.create_brief(brief)

        result = lab.auto_create_container("pb_overlap", "lab/assets/overlap.png", 3.0)
        assert result is None


# ── Full Pipeline Test ────────────────────────────────────────────────────────


class TestFullPipeline:
    def test_brief_to_container_to_timeline(self, project_with_timeline, lab):
        """
        Complete flow: create brief → auto-create container → verify timeline binding.
        """
        # 1. Create brief with audio sync
        brief = ProductionBrief(
            id="pb_full", type="single",
            title="Cornelius CU", prompt="close up of Cornelius at the bar",
            audio_start=22.5,
            characters=["cornelius"],
            location="crooked_nail",
        )
        lab.create_brief(brief)

        # 2. Auto-create container (simulating what poll_eden_status does)
        cid = lab.auto_create_container(
            "pb_full", asset_path="lab/assets/pb_full.png", duration=4.0,
        )
        assert cid is not None

        # 3. Verify timeline
        tl = load_timeline(project_with_timeline)
        ct = tl.containers[cid]
        assert ct.position == 22.5
        assert ct.duration == 4.0
        assert ct.brief_id == "pb_full"
        assert ct.label == "Cornelius CU"
        assert cid in tl.tracks[0].container_ids  # On V1

        # 4. Verify brief
        loaded = lab.get_brief("pb_full")
        assert loaded.container_id == cid

        # 5. Invariants clean
        assert tl.validate_invariants() == []

    def test_media_asset_to_timeline(self, project_with_timeline):
        """MediaAsset → to_asset_ref() → create_container on timeline."""
        asset = MediaAsset(
            id="asset_flow", type="image", filename="hero.png",
            path="lab/assets/hero.png", source="eden", duration=3.0,
        )
        ref = asset.to_asset_ref()

        tl = load_timeline(project_with_timeline)
        svc = TimelineService()
        result = svc.create_container(tl, ref, "v1", 0.0, "Hero Frame")
        assert result.ok

        ct = tl.containers[result.container_ids[0]]
        assert ct.clips[0].asset_ref.asset_id == "asset_flow"
        assert ct.clips[0].asset_ref.media_type == MediaType.IMAGE
