"""
Tests for KOZMO Timeline API Routes
====================================
Integration tests using FastAPI TestClient.
Covers: GET timeline, create, razor, split, merge, group, ungroup.
Full chain test mirrors the service-level chain.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import luna.services.kozmo.routes as routes_module
from luna.services.kozmo.routes import router


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def app(tmp_path):
    """Create test FastAPI app with KOZMO routes and temp project root."""
    routes_module.DEFAULT_PROJECTS_ROOT = tmp_path / "projects"
    routes_module.DEFAULT_PROJECTS_ROOT.mkdir()

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def project_slug(client):
    """Create a test project."""
    resp = client.post("/kozmo/projects", json={"name": "Timeline Test"})
    assert resp.status_code == 201
    return resp.json()["slug"]


@pytest.fixture
def project_with_timeline(client, project_slug):
    """
    Create a project and seed a timeline with V1, A1, A2 tracks
    by creating a container (which requires tracks to exist first).
    We'll seed tracks by saving a timeline directly.
    """
    from luna.services.kozmo.timeline_types import Timeline, Track, TrackType
    from luna.services.kozmo.timeline_store import save_timeline

    tl = Timeline(tracks=[
        Track(id="v1", label="V1", track_type=TrackType.VIDEO),
        Track(id="a1", label="A1", track_type=TrackType.AUDIO),
        Track(id="a2", label="A2", track_type=TrackType.AUDIO),
    ])

    project_root = routes_module.DEFAULT_PROJECTS_ROOT / project_slug
    save_timeline(project_root, tl)

    return project_slug


# ── GET Timeline ──────────────────────────────────────────────────────────────


class TestGetTimeline:
    def test_empty_timeline(self, client, project_slug):
        resp = client.get(f"/kozmo/projects/{project_slug}/timeline")
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == "2.0.0"
        assert data["containers"] == {}
        assert data["tracks"] == []

    def test_seeded_timeline(self, client, project_with_timeline):
        slug = project_with_timeline
        resp = client.get(f"/kozmo/projects/{slug}/timeline")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["tracks"]) == 3
        assert data["tracks"][0]["id"] == "v1"

    def test_404_on_missing_project(self, client):
        resp = client.get("/kozmo/projects/nonexistent/timeline")
        assert resp.status_code == 404


# ── Create Container ──────────────────────────────────────────────────────────


class TestCreateContainer:
    def test_create_basic(self, client, project_with_timeline):
        slug = project_with_timeline
        resp = client.post(f"/kozmo/projects/{slug}/timeline/containers", json={
            "asset_id": "asset001",
            "path": "assets/video/test.mp4",
            "duration": 10.0,
            "media_type": "video",
            "track_id": "v1",
            "position": 0.0,
            "label": "Wide Shot",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["ok"]
        assert len(data["container_ids"]) == 1

        # Verify it persisted
        tl = client.get(f"/kozmo/projects/{slug}/timeline").json()
        cid = data["container_ids"][0]
        assert cid in tl["containers"]
        assert tl["containers"][cid]["label"] == "Wide Shot"

    def test_create_overlap_rejected(self, client, project_with_timeline):
        slug = project_with_timeline
        body = {
            "asset_id": "a1", "path": "test.mp4", "duration": 10.0,
            "media_type": "video", "track_id": "v1", "position": 0.0,
        }
        r1 = client.post(f"/kozmo/projects/{slug}/timeline/containers", json=body)
        assert r1.status_code == 201

        body["position"] = 5.0  # overlaps [0, 10)
        r2 = client.post(f"/kozmo/projects/{slug}/timeline/containers", json=body)
        assert r2.status_code == 400
        assert "overlap" in r2.json()["detail"].lower()

    def test_create_on_missing_track(self, client, project_with_timeline):
        slug = project_with_timeline
        resp = client.post(f"/kozmo/projects/{slug}/timeline/containers", json={
            "asset_id": "a1", "path": "test.mp4", "duration": 5.0,
            "media_type": "video", "track_id": "nonexistent", "position": 0.0,
        })
        assert resp.status_code == 400


# ── Razor ─────────────────────────────────────────────────────────────────────


class TestRazor:
    def _create_container(self, client, slug, duration=10.0, position=0.0, track="v1"):
        resp = client.post(f"/kozmo/projects/{slug}/timeline/containers", json={
            "asset_id": "a1", "path": "test.mp4", "duration": duration,
            "media_type": "video", "track_id": track, "position": position,
        })
        assert resp.status_code == 201
        return resp.json()["container_ids"][0]

    def test_razor_basic(self, client, project_with_timeline):
        slug = project_with_timeline
        cid = self._create_container(client, slug)

        resp = client.post(f"/kozmo/projects/{slug}/timeline/razor", json={
            "container_id": cid,
            "cut_time": 4.0,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"]
        assert len(data["container_ids"]) == 2

        # Verify original gone, two halves present
        tl = client.get(f"/kozmo/projects/{slug}/timeline").json()
        assert cid not in tl["containers"]
        lid, rid = data["container_ids"]
        assert tl["containers"][lid]["duration"] == 4.0
        assert tl["containers"][rid]["duration"] == 6.0

    def test_razor_locked_rejected(self, client, project_with_timeline):
        slug = project_with_timeline
        cid = self._create_container(client, slug)

        # Lock the container directly via store
        from luna.services.kozmo.timeline_store import load_timeline, save_timeline
        project_root = routes_module.DEFAULT_PROJECTS_ROOT / slug
        tl = load_timeline(project_root)
        tl.containers[cid].locked = True
        save_timeline(project_root, tl)

        resp = client.post(f"/kozmo/projects/{slug}/timeline/razor", json={
            "container_id": cid,
            "cut_time": 5.0,
        })
        assert resp.status_code == 400
        assert "locked" in resp.json()["detail"].lower()

    def test_razor_out_of_bounds(self, client, project_with_timeline):
        slug = project_with_timeline
        cid = self._create_container(client, slug, duration=10.0)

        resp = client.post(f"/kozmo/projects/{slug}/timeline/razor", json={
            "container_id": cid, "cut_time": 15.0,
        })
        assert resp.status_code == 400


# ── Merge ─────────────────────────────────────────────────────────────────────


class TestMerge:
    def _create_two(self, client, slug):
        c1 = client.post(f"/kozmo/projects/{slug}/timeline/containers", json={
            "asset_id": "a1", "path": "a.mp4", "duration": 5.0,
            "media_type": "video", "track_id": "v1", "position": 0.0,
        }).json()["container_ids"][0]
        c2 = client.post(f"/kozmo/projects/{slug}/timeline/containers", json={
            "asset_id": "a2", "path": "b.mp4", "duration": 5.0,
            "media_type": "video", "track_id": "v1", "position": 10.0,
        }).json()["container_ids"][0]
        return c1, c2

    def test_merge_requires_confirmation(self, client, project_with_timeline):
        slug = project_with_timeline
        c1, c2 = self._create_two(client, slug)

        resp = client.post(f"/kozmo/projects/{slug}/timeline/merge", json={
            "target_id": c1, "source_id": c2, "confirmed": False,
        })
        assert resp.status_code == 400
        assert "confirmed" in resp.json()["detail"].lower()

    def test_merge_confirmed(self, client, project_with_timeline):
        slug = project_with_timeline
        c1, c2 = self._create_two(client, slug)

        resp = client.post(f"/kozmo/projects/{slug}/timeline/merge", json={
            "target_id": c1, "source_id": c2, "confirmed": True,
        })
        assert resp.status_code == 200
        assert resp.json()["ok"]

        tl = client.get(f"/kozmo/projects/{slug}/timeline").json()
        assert c1 in tl["containers"]
        assert c2 not in tl["containers"]


# ── Group / Ungroup ───────────────────────────────────────────────────────────


class TestGroupUngroup:
    def _create_two(self, client, slug):
        c1 = client.post(f"/kozmo/projects/{slug}/timeline/containers", json={
            "asset_id": "a1", "path": "a.mp4", "duration": 5.0,
            "media_type": "video", "track_id": "v1", "position": 0.0,
        }).json()["container_ids"][0]
        c2 = client.post(f"/kozmo/projects/{slug}/timeline/containers", json={
            "asset_id": "a2", "path": "b.wav", "duration": 5.0,
            "media_type": "audio", "track_id": "a1", "position": 0.0,
        }).json()["container_ids"][0]
        return c1, c2

    def test_group(self, client, project_with_timeline):
        slug = project_with_timeline
        c1, c2 = self._create_two(client, slug)

        resp = client.post(f"/kozmo/projects/{slug}/timeline/group", json={
            "container_ids": [c1, c2],
            "label": "Scene 1 Sync",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"]
        assert data["group_id"]

        tl = client.get(f"/kozmo/projects/{slug}/timeline").json()
        gid = data["group_id"]
        assert gid in tl["groups"]
        assert tl["containers"][c1]["group_id"] == gid

    def test_ungroup(self, client, project_with_timeline):
        slug = project_with_timeline
        c1, c2 = self._create_two(client, slug)

        group_resp = client.post(f"/kozmo/projects/{slug}/timeline/group", json={
            "container_ids": [c1, c2], "label": "Test",
        })
        gid = group_resp.json()["group_id"]

        resp = client.delete(f"/kozmo/projects/{slug}/timeline/group/{gid}")
        assert resp.status_code == 200
        assert resp.json()["ok"]

        tl = client.get(f"/kozmo/projects/{slug}/timeline").json()
        assert gid not in tl["groups"]
        assert tl["containers"][c1]["group_id"] is None

    def test_ungroup_nonexistent(self, client, project_with_timeline):
        slug = project_with_timeline
        resp = client.delete(f"/kozmo/projects/{slug}/timeline/group/fake")
        assert resp.status_code == 400

    def test_group_needs_two(self, client, project_with_timeline):
        slug = project_with_timeline
        c1 = client.post(f"/kozmo/projects/{slug}/timeline/containers", json={
            "asset_id": "a1", "path": "a.mp4", "duration": 5.0,
            "media_type": "video", "track_id": "v1", "position": 0.0,
        }).json()["container_ids"][0]

        resp = client.post(f"/kozmo/projects/{slug}/timeline/group", json={
            "container_ids": [c1],
        })
        assert resp.status_code == 400


# ── Full Chain (API level) ────────────────────────────────────────────────────


class TestFullChainAPI:
    def test_create_razor_group_ungroup_merge(self, client, project_with_timeline):
        slug = project_with_timeline

        # 1. Create video + audio containers
        r1 = client.post(f"/kozmo/projects/{slug}/timeline/containers", json={
            "asset_id": "v1", "path": "assets/video/shot.mp4", "duration": 10.0,
            "media_type": "video", "track_id": "v1", "position": 0.0, "label": "Wide",
        })
        r2 = client.post(f"/kozmo/projects/{slug}/timeline/containers", json={
            "asset_id": "a1", "path": "assets/audio/score.wav", "duration": 10.0,
            "media_type": "audio", "track_id": "a1", "position": 0.0, "label": "Score",
        })
        assert r1.status_code == 201 and r2.status_code == 201
        vid_id = r1.json()["container_ids"][0]
        aud_id = r2.json()["container_ids"][0]

        # 2. Razor video at 4s
        razor = client.post(f"/kozmo/projects/{slug}/timeline/razor", json={
            "container_id": vid_id, "cut_time": 4.0,
        })
        assert razor.status_code == 200
        lid, rid = razor.json()["container_ids"]

        # 3. Group right half with audio
        group = client.post(f"/kozmo/projects/{slug}/timeline/group", json={
            "container_ids": [rid, aud_id], "label": "Scene 1",
        })
        assert group.status_code == 200
        gid = group.json()["group_id"]

        # 4. Ungroup
        ungroup = client.delete(f"/kozmo/projects/{slug}/timeline/group/{gid}")
        assert ungroup.status_code == 200

        # 5. Merge left and right back
        merge = client.post(f"/kozmo/projects/{slug}/timeline/merge", json={
            "target_id": lid, "source_id": rid, "confirmed": True,
        })
        assert merge.status_code == 200

        # Final state: 2 containers (merged video + audio)
        tl = client.get(f"/kozmo/projects/{slug}/timeline").json()
        assert len(tl["containers"]) == 2


# ── WebSocket ─────────────────────────────────────────────────────────────────


class TestWebSocket:
    def test_ws_sends_initial_state(self, client, project_with_timeline):
        slug = project_with_timeline
        with client.websocket_connect(f"/kozmo/ws/kozmo/{slug}/timeline") as ws:
            data = ws.receive_json()
            assert data["type"] == "timeline.state"
            assert "timeline" in data
            assert len(data["timeline"]["tracks"]) == 3
