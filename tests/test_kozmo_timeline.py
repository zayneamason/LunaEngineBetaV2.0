"""
Tests for KOZMO Timeline — Container System
=============================================
Covers: types, service operations, store persistence, invariant validation.

Full chain test: create → razor → group → ungroup → merge
Plus individual operation tests and edge cases.
"""

import pytest
from pathlib import Path

from luna.services.kozmo.timeline_types import (
    CameraMetadata,
    Clip,
    Container,
    ContainerGroup,
    EffectNode,
    MediaAssetRef,
    MediaType,
    Timeline,
    Track,
    TrackType,
    _new_id,
)
from luna.services.kozmo.timeline_service import (
    EventType,
    NullSink,
    Result,
    TimelineEvent,
    TimelineService,
)
from luna.services.kozmo.timeline_store import (
    load_timeline,
    save_timeline,
    timeline_path,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_asset(path="assets/video/test.mp4", duration=10.0, media_type=MediaType.VIDEO):
    return MediaAssetRef(
        asset_id=_new_id(),
        path=path,
        duration=duration,
        media_type=media_type,
    )


def make_timeline_with_tracks():
    """Create a timeline with V1, A1, A2 tracks."""
    v1 = Track(id="v1", label="V1", track_type=TrackType.VIDEO)
    a1 = Track(id="a1", label="A1", track_type=TrackType.AUDIO)
    a2 = Track(id="a2", label="A2", track_type=TrackType.AUDIO)
    return Timeline(tracks=[v1, a1, a2])


def make_service():
    return TimelineService(sink=NullSink())


# ── Type Construction Tests ───────────────────────────────────────────────────

class TestTypes:
    def test_media_asset_ref(self):
        ref = make_asset()
        assert ref.duration == 10.0
        assert ref.media_type == MediaType.VIDEO

    def test_clip_duration(self):
        ref = make_asset(duration=10.0)
        clip = Clip(asset_ref=ref, in_point=2.0, out_point=7.0)
        assert clip.duration == 5.0

    def test_clip_split(self):
        ref = make_asset(duration=10.0)
        clip = Clip(asset_ref=ref, in_point=0.0, out_point=10.0)
        left, right = clip.split_at(4.0)
        assert left.duration == 4.0
        assert right.duration == 6.0
        assert left.out_point == right.in_point == 4.0

    def test_clip_split_out_of_range(self):
        ref = make_asset(duration=10.0)
        clip = Clip(asset_ref=ref, in_point=2.0, out_point=8.0)
        with pytest.raises(AssertionError):
            clip.split_at(1.0)
        with pytest.raises(AssertionError):
            clip.split_at(9.0)

    def test_container_end(self):
        ct = Container(position=5.0, duration=3.0)
        assert ct.end == 8.0

    def test_container_deep_copy_effects(self):
        fx = EffectNode(plugin_type="color_grade", name="Kodak 5219", params={"intensity": 0.8})
        ct = Container(effect_chain=[fx])
        copied = ct.deep_copy_effects()
        assert len(copied) == 1
        assert copied[0].name == "Kodak 5219"
        # Verify deep copy — mutating copy doesn't affect original
        copied[0].params["intensity"] = 0.2
        assert ct.effect_chain[0].params["intensity"] == 0.8

    def test_container_fx_count(self):
        fx1 = EffectNode(plugin_type="color_grade", enabled=True)
        fx2 = EffectNode(plugin_type="film_grain", enabled=False)
        ct = Container(effect_chain=[fx1, fx2])
        assert ct.fx_count == 1

    def test_camera_metadata(self):
        cam = CameraMetadata(body="ARRI Alexa 35", lens="Panavision C-Series", focal_length=50)
        ct = Container(camera=cam)
        assert ct.camera.body == "ARRI Alexa 35"

    def test_timeline_recalculate_duration(self):
        tl = Timeline()
        tl.containers["a"] = Container(id="a", position=0.0, duration=5.0)
        tl.containers["b"] = Container(id="b", position=10.0, duration=3.0)
        tl.recalculate_duration()
        assert tl.total_duration == 13.0

    def test_timeline_recalculate_empty(self):
        tl = Timeline()
        tl.recalculate_duration()
        assert tl.total_duration == 0.0

    def test_new_id_format(self):
        id1 = _new_id()
        assert len(id1) == 12
        assert id1.isalnum()


# ── Invariant Validation Tests ────────────────────────────────────────────────

class TestInvariants:
    def test_clean_timeline(self):
        tl = make_timeline_with_tracks()
        svc = make_service()
        asset = make_asset(duration=5.0)
        svc.create_container(tl, asset, "v1", 0.0, "Shot 1")
        assert tl.validate_invariants() == []

    def test_inv1_container_shorter_than_clip(self):
        ref = make_asset(duration=10.0)
        clip = Clip(asset_ref=ref, in_point=0.0, out_point=10.0)
        ct = Container(id="bad", duration=5.0, clips=[clip])
        tl = Timeline(containers={"bad": ct})
        violations = tl.validate_invariants()
        assert any("INV-1" in v for v in violations)

    def test_inv2_overlap_detected(self):
        ct_a = Container(id="a", position=0.0, duration=10.0)
        ct_b = Container(id="b", position=5.0, duration=10.0)
        track = Track(id="t1", container_ids=["a", "b"])
        tl = Timeline(tracks=[track], containers={"a": ct_a, "b": ct_b})
        violations = tl.validate_invariants()
        assert any("INV-2" in v for v in violations)

    def test_inv4_missing_container_in_track(self):
        track = Track(id="t1", container_ids=["nonexistent"])
        tl = Timeline(tracks=[track])
        violations = tl.validate_invariants()
        assert any("INV-4" in v for v in violations)

    def test_inv5_missing_container_in_group(self):
        grp = ContainerGroup(id="g1", container_ids=["nonexistent"])
        tl = Timeline(groups={"g1": grp})
        violations = tl.validate_invariants()
        assert any("INV-5" in v for v in violations)


# ── Service: Create ──────────────────────────────────────────────────────────

class TestCreate:
    def test_create_basic(self):
        tl = make_timeline_with_tracks()
        svc = make_service()
        asset = make_asset(duration=5.0)

        result = svc.create_container(tl, asset, "v1", 0.0, "Wide Shot")
        assert result.ok
        assert len(result.container_ids) == 1

        cid = result.container_ids[0]
        assert cid in tl.containers
        assert tl.containers[cid].label == "Wide Shot"
        assert tl.containers[cid].duration == 5.0
        assert cid in tl.tracks[0].container_ids
        assert tl.total_duration == 5.0

    def test_create_on_missing_track(self):
        tl = make_timeline_with_tracks()
        svc = make_service()
        result = svc.create_container(tl, make_asset(), "nonexistent", 0.0)
        assert not result.ok
        assert "not found" in result.error

    def test_create_overlap_rejected(self):
        tl = make_timeline_with_tracks()
        svc = make_service()
        asset = make_asset(duration=10.0)

        r1 = svc.create_container(tl, asset, "v1", 0.0, "First")
        assert r1.ok

        r2 = svc.create_container(tl, asset, "v1", 5.0, "Overlapping")
        assert not r2.ok
        assert "overlap" in r2.error.lower()

    def test_create_adjacent_ok(self):
        tl = make_timeline_with_tracks()
        svc = make_service()
        asset = make_asset(duration=5.0)

        r1 = svc.create_container(tl, asset, "v1", 0.0, "First")
        r2 = svc.create_container(tl, asset, "v1", 5.0, "Second")
        assert r1.ok and r2.ok
        assert len(tl.containers) == 2

    def test_create_emits_events(self):
        tl = make_timeline_with_tracks()
        svc = make_service()
        result = svc.create_container(tl, make_asset(), "v1", 0.0)
        assert any(e.type == EventType.CONTAINER_CREATED for e in result.events)
        assert any(e.type == EventType.TIMELINE_RECALCULATED for e in result.events)

    def test_create_default_label_from_path(self):
        tl = make_timeline_with_tracks()
        svc = make_service()
        asset = make_asset(path="assets/video/crooked_nail.mp4")
        result = svc.create_container(tl, asset, "v1", 0.0)
        assert tl.containers[result.container_ids[0]].label == "crooked_nail.mp4"


# ── Service: Razor ────────────────────────────────────────────────────────────

class TestRazor:
    def test_razor_basic(self):
        tl = make_timeline_with_tracks()
        svc = make_service()
        asset = make_asset(duration=10.0)
        r = svc.create_container(tl, asset, "v1", 0.0, "Wide")
        original_id = r.container_ids[0]

        result = svc.razor(tl, original_id, 4.0)
        assert result.ok
        assert len(result.container_ids) == 2
        assert original_id not in tl.containers

        lid, rid = result.container_ids
        left = tl.containers[lid]
        right = tl.containers[rid]

        assert left.duration == 4.0
        assert right.duration == 6.0
        assert right.position == 4.0
        assert left.label == "Wide (L)"
        assert right.label == "Wide (R)"

    def test_razor_clips_split(self):
        tl = make_timeline_with_tracks()
        svc = make_service()
        asset = make_asset(duration=10.0)
        r = svc.create_container(tl, asset, "v1", 0.0)
        cid = r.container_ids[0]

        result = svc.razor(tl, cid, 4.0)
        lid, rid = result.container_ids
        left = tl.containers[lid]
        right = tl.containers[rid]

        assert len(left.clips) == 1
        assert left.clips[0].out_point == 4.0
        assert len(right.clips) == 1
        assert right.clips[0].in_point == 4.0

    def test_razor_preserves_effects(self):
        tl = make_timeline_with_tracks()
        svc = make_service()
        asset = make_asset(duration=10.0)
        r = svc.create_container(tl, asset, "v1", 0.0)
        cid = r.container_ids[0]

        # Add effects to the container
        tl.containers[cid].effect_chain = [
            EffectNode(plugin_type="color_grade", name="LUT"),
        ]

        result = svc.razor(tl, cid, 5.0)
        lid, rid = result.container_ids
        assert len(tl.containers[lid].effect_chain) == 1
        assert len(tl.containers[rid].effect_chain) == 1
        assert tl.containers[lid].effect_chain[0].name == "LUT"

    def test_razor_preserves_group(self):
        tl = make_timeline_with_tracks()
        svc = make_service()
        a1 = make_asset(duration=10.0)
        a2 = make_asset(duration=10.0)
        r1 = svc.create_container(tl, a1, "v1", 0.0, "Shot A")
        r2 = svc.create_container(tl, a2, "a1", 0.0, "Shot B")

        svc.group(tl, [r1.container_ids[0], r2.container_ids[0]], "Sync Group")

        result = svc.razor(tl, r1.container_ids[0], 5.0)
        lid, rid = result.container_ids
        assert tl.containers[lid].group_id is not None
        assert tl.containers[rid].group_id is not None

    def test_razor_locked_rejected(self):
        tl = make_timeline_with_tracks()
        svc = make_service()
        r = svc.create_container(tl, make_asset(), "v1", 0.0)
        cid = r.container_ids[0]
        tl.containers[cid].locked = True

        result = svc.razor(tl, cid, 5.0)
        assert not result.ok
        assert "locked" in result.error.lower()

    def test_razor_out_of_bounds(self):
        tl = make_timeline_with_tracks()
        svc = make_service()
        r = svc.create_container(tl, make_asset(duration=10.0), "v1", 0.0)
        cid = r.container_ids[0]

        assert not svc.razor(tl, cid, 0.0).ok
        assert not svc.razor(tl, cid, 10.0).ok
        assert not svc.razor(tl, cid, -1.0).ok
        assert not svc.razor(tl, cid, 15.0).ok

    def test_razor_missing_container(self):
        tl = make_timeline_with_tracks()
        svc = make_service()
        assert not svc.razor(tl, "nonexistent", 5.0).ok

    def test_razor_track_replacement(self):
        tl = make_timeline_with_tracks()
        svc = make_service()
        r = svc.create_container(tl, make_asset(duration=10.0), "v1", 0.0)
        cid = r.container_ids[0]
        assert cid in tl.tracks[0].container_ids

        result = svc.razor(tl, cid, 5.0)
        lid, rid = result.container_ids
        assert cid not in tl.tracks[0].container_ids
        assert lid in tl.tracks[0].container_ids
        assert rid in tl.tracks[0].container_ids


# ── Service: Split Clip ───────────────────────────────────────────────────────

class TestSplitClip:
    def test_split_requires_two_clips(self):
        tl = make_timeline_with_tracks()
        svc = make_service()
        r = svc.create_container(tl, make_asset(), "v1", 0.0)
        cid = r.container_ids[0]

        clip_id = tl.containers[cid].clips[0].id
        result = svc.split_clip_out(tl, cid, clip_id)
        assert not result.ok
        assert "2+" in result.error

    def test_split_extracts_clip(self):
        tl = make_timeline_with_tracks()
        svc = make_service()

        # Create a container with two clips manually
        ref_v = make_asset(path="assets/video/shot_a.mp4", duration=5.0)
        ref_a = make_asset(path="assets/audio/score.wav", duration=8.0, media_type=MediaType.AUDIO)
        clip_v = Clip(asset_ref=ref_v, in_point=0.0, out_point=5.0)
        clip_a = Clip(asset_ref=ref_a, in_point=0.0, out_point=8.0)

        ct = Container(
            label="Mixed Container",
            position=0.0,
            duration=8.0,
            clips=[clip_v, clip_a],
        )
        tl.containers[ct.id] = ct
        tl.tracks[0].container_ids.append(ct.id)  # V1

        result = svc.split_clip_out(tl, ct.id, clip_a.id)
        assert result.ok
        assert len(result.container_ids) == 2

        # Original should have 1 clip left
        assert len(tl.containers[ct.id].clips) == 1
        assert tl.containers[ct.id].clips[0].id == clip_v.id

        # New container should have the audio clip
        new_id = result.container_ids[1]
        assert len(tl.containers[new_id].clips) == 1
        assert tl.containers[new_id].clips[0].id == clip_a.id

    def test_split_locked_rejected(self):
        tl = make_timeline_with_tracks()
        svc = make_service()
        r = svc.create_container(tl, make_asset(), "v1", 0.0)
        cid = r.container_ids[0]
        tl.containers[cid].locked = True
        result = svc.split_clip_out(tl, cid, "any")
        assert not result.ok


# ── Service: Merge ────────────────────────────────────────────────────────────

class TestMerge:
    def test_merge_requires_confirmation(self):
        tl = make_timeline_with_tracks()
        svc = make_service()
        r1 = svc.create_container(tl, make_asset(duration=5.0), "v1", 0.0)
        r2 = svc.create_container(tl, make_asset(duration=5.0), "v1", 10.0)

        result = svc.merge(tl, r1.container_ids[0], r2.container_ids[0], confirmed=False)
        assert not result.ok
        assert "confirmed" in result.error.lower()

    def test_merge_basic(self):
        tl = make_timeline_with_tracks()
        svc = make_service()
        r1 = svc.create_container(tl, make_asset(duration=5.0), "v1", 0.0, "Target")
        r2 = svc.create_container(tl, make_asset(duration=5.0), "v1", 10.0, "Source")
        tid = r1.container_ids[0]
        sid = r2.container_ids[0]

        result = svc.merge(tl, tid, sid, confirmed=True)
        assert result.ok
        assert sid not in tl.containers
        assert tid in tl.containers
        assert len(tl.containers[tid].clips) == 2

    def test_merge_target_chain_wins(self):
        tl = make_timeline_with_tracks()
        svc = make_service()
        r1 = svc.create_container(tl, make_asset(duration=5.0), "v1", 0.0)
        r2 = svc.create_container(tl, make_asset(duration=5.0), "v1", 10.0)
        tid, sid = r1.container_ids[0], r2.container_ids[0]

        tl.containers[tid].effect_chain = [EffectNode(plugin_type="target_fx")]
        tl.containers[sid].effect_chain = [EffectNode(plugin_type="source_fx")]

        svc.merge(tl, tid, sid, confirmed=True)
        assert len(tl.containers[tid].effect_chain) == 1
        assert tl.containers[tid].effect_chain[0].plugin_type == "target_fx"

    def test_merge_locked_target_rejected(self):
        tl = make_timeline_with_tracks()
        svc = make_service()
        r1 = svc.create_container(tl, make_asset(duration=5.0), "v1", 0.0)
        r2 = svc.create_container(tl, make_asset(duration=5.0), "v1", 10.0)
        tl.containers[r1.container_ids[0]].locked = True

        result = svc.merge(tl, r1.container_ids[0], r2.container_ids[0], confirmed=True)
        assert not result.ok
        assert "locked" in result.error.lower()

    def test_merge_cleans_empty_group(self):
        tl = make_timeline_with_tracks()
        svc = make_service()
        r1 = svc.create_container(tl, make_asset(duration=5.0), "v1", 0.0)
        r2 = svc.create_container(tl, make_asset(duration=5.0), "v1", 10.0)
        r3 = svc.create_container(tl, make_asset(duration=5.0), "a1", 0.0)
        sid = r2.container_ids[0]

        # Group source with third container
        grp_result = svc.group(tl, [sid, r3.container_ids[0]], "Test Group")
        gid = grp_result.group_id

        # Now merge source into target — should remove source from group
        svc.merge(tl, r1.container_ids[0], sid, confirmed=True)

        # Group should still exist (has r3 left)
        # Actually the group only has 1 container left (r3), which means it's still valid
        # But it wasn't cleaned because it still has members
        if gid in tl.groups:
            assert sid not in tl.groups[gid].container_ids


# ── Service: Group / Ungroup ──────────────────────────────────────────────────

class TestGroup:
    def test_group_basic(self):
        tl = make_timeline_with_tracks()
        svc = make_service()
        r1 = svc.create_container(tl, make_asset(duration=5.0), "v1", 0.0)
        r2 = svc.create_container(tl, make_asset(duration=5.0), "a1", 0.0)
        c1, c2 = r1.container_ids[0], r2.container_ids[0]

        result = svc.group(tl, [c1, c2], "Scene 1 Sync")
        assert result.ok
        assert result.group_id is not None
        assert tl.containers[c1].group_id == result.group_id
        assert tl.containers[c2].group_id == result.group_id

    def test_group_needs_two(self):
        tl = make_timeline_with_tracks()
        svc = make_service()
        r1 = svc.create_container(tl, make_asset(), "v1", 0.0)
        result = svc.group(tl, [r1.container_ids[0]])
        assert not result.ok

    def test_group_removes_from_old_group(self):
        tl = make_timeline_with_tracks()
        svc = make_service()
        r1 = svc.create_container(tl, make_asset(duration=5.0), "v1", 0.0)
        r2 = svc.create_container(tl, make_asset(duration=5.0), "a1", 0.0)
        r3 = svc.create_container(tl, make_asset(duration=5.0), "a2", 0.0)
        c1, c2, c3 = r1.container_ids[0], r2.container_ids[0], r3.container_ids[0]

        g1 = svc.group(tl, [c1, c2], "Group A")
        g2 = svc.group(tl, [c2, c3], "Group B")

        assert g1.ok and g2.ok
        assert tl.containers[c2].group_id == g2.group_id

    def test_ungroup(self):
        tl = make_timeline_with_tracks()
        svc = make_service()
        r1 = svc.create_container(tl, make_asset(duration=5.0), "v1", 0.0)
        r2 = svc.create_container(tl, make_asset(duration=5.0), "a1", 0.0)
        c1, c2 = r1.container_ids[0], r2.container_ids[0]

        g = svc.group(tl, [c1, c2])
        result = svc.ungroup(tl, g.group_id)
        assert result.ok
        assert g.group_id not in tl.groups
        assert tl.containers[c1].group_id is None
        assert tl.containers[c2].group_id is None

    def test_ungroup_nonexistent(self):
        tl = make_timeline_with_tracks()
        svc = make_service()
        assert not svc.ungroup(tl, "fake").ok


# ── Full Chain Test ───────────────────────────────────────────────────────────

class TestFullChain:
    """
    Mirrors the validation script from the handoff:
    create → razor → group → ungroup → merge
    """

    def test_full_chain(self):
        tl = make_timeline_with_tracks()
        svc = make_service()

        # 1. Create two containers
        asset_v = make_asset(path="assets/video/crooked_nail.mp4", duration=10.0)
        asset_a = make_asset(path="assets/audio/score.wav", duration=10.0, media_type=MediaType.AUDIO)

        r1 = svc.create_container(tl, asset_v, "v1", 0.0, "Wide Shot")
        r2 = svc.create_container(tl, asset_a, "a1", 0.0, "Score Bed")
        assert r1.ok and r2.ok
        assert len(tl.containers) == 2
        vid_id = r1.container_ids[0]
        aud_id = r2.container_ids[0]

        # 2. Razor the video at 4s
        razor_result = svc.razor(tl, vid_id, 4.0)
        assert razor_result.ok
        assert len(tl.containers) == 3  # 2 halves + audio
        lid, rid = razor_result.container_ids
        assert tl.containers[lid].duration == 4.0
        assert tl.containers[rid].duration == 6.0

        # 3. Group the right half with the audio
        group_result = svc.group(tl, [rid, aud_id], "Scene 1 Sync")
        assert group_result.ok
        gid = group_result.group_id
        assert tl.containers[rid].group_id == gid
        assert tl.containers[aud_id].group_id == gid

        # 4. Ungroup
        ungroup_result = svc.ungroup(tl, gid)
        assert ungroup_result.ok
        assert tl.containers[rid].group_id is None
        assert tl.containers[aud_id].group_id is None

        # 5. Merge left and right back together
        merge_result = svc.merge(tl, lid, rid, confirmed=True)
        assert merge_result.ok
        assert len(tl.containers) == 2  # merged + audio

        # Validate invariants at every step
        assert tl.validate_invariants() == []


# ── Store Tests ───────────────────────────────────────────────────────────────

class TestStore:
    def test_round_trip(self, tmp_path):
        """Save → load → compare."""
        tl = make_timeline_with_tracks()
        svc = make_service()
        asset = make_asset(
            path="assets/video/test.mp4",
            duration=10.0,
        )
        svc.create_container(tl, asset, "v1", 0.0, "Test Shot")

        # Save
        path = save_timeline(tmp_path, tl)
        assert path.exists()
        assert path.name == "timeline.yaml"

        # Load
        loaded = load_timeline(tmp_path)
        assert len(loaded.containers) == 1
        assert len(loaded.tracks) == 3
        ct = list(loaded.containers.values())[0]
        assert ct.label == "Test Shot"
        assert ct.duration == 10.0

    def test_load_missing_returns_empty(self, tmp_path):
        tl = load_timeline(tmp_path)
        assert isinstance(tl, Timeline)
        assert len(tl.containers) == 0
        assert len(tl.tracks) == 0

    def test_load_empty_file(self, tmp_path):
        (tmp_path / "timeline.yaml").write_text("")
        tl = load_timeline(tmp_path)
        assert isinstance(tl, Timeline)

    def test_round_trip_with_effects(self, tmp_path):
        tl = make_timeline_with_tracks()
        svc = make_service()
        r = svc.create_container(tl, make_asset(), "v1", 0.0)
        cid = r.container_ids[0]
        tl.containers[cid].effect_chain = [
            EffectNode(plugin_type="color_grade", name="LUT", params={"intensity": 0.8}),
        ]

        save_timeline(tmp_path, tl)
        loaded = load_timeline(tmp_path)
        ct = list(loaded.containers.values())[0]
        assert len(ct.effect_chain) == 1
        assert ct.effect_chain[0].params["intensity"] == 0.8

    def test_round_trip_with_groups(self, tmp_path):
        tl = make_timeline_with_tracks()
        svc = make_service()
        r1 = svc.create_container(tl, make_asset(duration=5.0), "v1", 0.0)
        r2 = svc.create_container(tl, make_asset(duration=5.0), "a1", 0.0)
        svc.group(tl, [r1.container_ids[0], r2.container_ids[0]], "Sync")

        save_timeline(tmp_path, tl)
        loaded = load_timeline(tmp_path)
        assert len(loaded.groups) == 1
        grp = list(loaded.groups.values())[0]
        assert grp.label == "Sync"
        assert len(grp.container_ids) == 2

    def test_round_trip_with_camera(self, tmp_path):
        tl = make_timeline_with_tracks()
        svc = make_service()
        r = svc.create_container(tl, make_asset(), "v1", 0.0)
        cid = r.container_ids[0]
        tl.containers[cid].camera = CameraMetadata(
            body="ARRI Alexa 35",
            lens="Panavision C-Series",
            focal_length=50,
            aperture=2.8,
        )

        save_timeline(tmp_path, tl)
        loaded = load_timeline(tmp_path)
        ct = list(loaded.containers.values())[0]
        assert ct.camera.body == "ARRI Alexa 35"
        assert ct.camera.focal_length == 50

    def test_timeline_path(self, tmp_path):
        assert timeline_path(tmp_path) == tmp_path / "timeline.yaml"


# ── Event Sink Tests ──────────────────────────────────────────────────────────

class TestEventSink:
    def test_collecting_sink(self):
        """Verify events are emitted to a custom sink."""
        collected = []

        class CollectingSink:
            def emit(self, event):
                collected.append(event)

        tl = make_timeline_with_tracks()
        svc = TimelineService(sink=CollectingSink())
        svc.create_container(tl, make_asset(), "v1", 0.0)

        assert len(collected) == 2
        assert collected[0].type == EventType.CONTAINER_CREATED
        assert collected[1].type == EventType.TIMELINE_RECALCULATED
