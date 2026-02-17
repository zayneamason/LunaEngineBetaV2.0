"""
Tests for KOZMO Phase 8: LAB Pipeline Service

Tests brief CRUD, camera rigging, prompt enrichment,
sequence management, and camera registry lookups.
"""

import pytest
import yaml
from pathlib import Path
from datetime import datetime

from luna.services.kozmo.lab_pipeline import LabPipelineService
from luna.services.kozmo.camera_registry import (
    CAMERA_BODIES,
    LENS_PROFILES,
    FILM_STOCKS,
    MOVEMENTS,
    build_enriched_prompt,
    get_camera_body,
    get_lens,
    get_stock,
    get_movement,
)
from luna.services.kozmo.types import (
    ProductionBrief,
    CameraRig,
    BriefPostConfig,
    SequenceShot,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def project_dir(tmp_path):
    """Create minimal project with lab directories."""
    (tmp_path / "lab" / "briefs").mkdir(parents=True)
    (tmp_path / "lab" / "assets").mkdir(parents=True)
    return tmp_path


@pytest.fixture
def lab(project_dir):
    return LabPipelineService(project_dir)


def _make_brief(**kwargs) -> ProductionBrief:
    defaults = {
        "id": "",
        "type": "single",
        "title": "Test Brief",
        "prompt": "A test scene with fantasy elements",
    }
    defaults.update(kwargs)
    return ProductionBrief(**defaults)


# =============================================================================
# Camera Registry
# =============================================================================


class TestCameraRegistry:
    def test_all_bodies_present(self):
        assert len(CAMERA_BODIES) == 6
        assert "arri_alexa35" in CAMERA_BODIES
        assert "vhs_camcorder" in CAMERA_BODIES

    def test_all_lenses_present(self):
        assert len(LENS_PROFILES) == 6
        assert "cooke_s7i" in LENS_PROFILES
        assert "helios_44" in LENS_PROFILES

    def test_all_stocks_present(self):
        assert len(FILM_STOCKS) == 6
        assert "none" in FILM_STOCKS
        assert "kodak_5219" in FILM_STOCKS

    def test_all_movements_present(self):
        assert len(MOVEMENTS) == 12
        assert "static" in MOVEMENTS
        assert "steadicam" in MOVEMENTS

    def test_lookup_helpers(self):
        assert get_camera_body("arri_alexa35") is not None
        assert get_camera_body("nonexistent") is None
        assert get_lens("cooke_s7i") is not None
        assert get_stock("kodak_5219") is not None
        assert get_movement("dolly_in") is not None

    def test_body_has_prompt_phrase(self):
        body = get_camera_body("arri_alexa35")
        assert "ARRI Alexa 35" in body.prompt_phrase

    def test_lens_has_focal_range(self):
        lens = get_lens("cooke_s7i")
        assert lens.focal_range == (18, 135)

    def test_lens_type(self):
        assert get_lens("panavision_c").type == "anamorphic"
        assert get_lens("cooke_s7i").type == "spherical"


# =============================================================================
# Prompt Enrichment
# =============================================================================


class TestPromptEnrichment:
    def test_basic_enrichment(self):
        result = build_enriched_prompt("A stone cottage in morning mist")
        assert "ARRI Alexa 35" in result
        assert "Cooke S7/i" in result
        assert "50mm" in result
        assert "f/2.8" in result

    def test_with_film_stock(self):
        result = build_enriched_prompt(
            "Test scene", stock_id="kodak_5219"
        )
        assert "Kodak 5219" in result

    def test_no_stock(self):
        result = build_enriched_prompt("Test scene", stock_id="none")
        assert "film stock" not in result

    def test_with_movement(self):
        result = build_enriched_prompt(
            "Test scene", movements=["dolly_in", "tilt_up"]
        )
        assert "Camera movement:" in result
        assert "Dolly In" in result
        assert "Tilt Up" in result

    def test_static_only_no_movement_line(self):
        result = build_enriched_prompt("Test scene", movements=["static"])
        assert "Camera movement:" not in result

    def test_custom_camera_lens(self):
        result = build_enriched_prompt(
            "Test scene",
            body_id="16mm_bolex",
            lens_id="helios_44",
            focal=58,
            aperture=2.0,
        )
        assert "16mm Bolex" in result
        assert "Helios 44-2" in result
        assert "58mm" in result


# =============================================================================
# Brief CRUD
# =============================================================================


class TestBriefCRUD:
    def test_create_brief(self, lab):
        brief = _make_brief()
        created = lab.create_brief(brief)
        assert created.id.startswith("pb_")
        assert created.created_at is not None
        assert created.updated_at is not None

    def test_create_brief_persists(self, lab):
        created = lab.create_brief(_make_brief())
        loaded = lab.get_brief(created.id)
        assert loaded is not None
        assert loaded.title == "Test Brief"

    def test_get_brief_not_found(self, lab):
        assert lab.get_brief("nonexistent") is None

    def test_list_briefs_empty(self, lab):
        assert lab.list_briefs() == []

    def test_list_briefs(self, lab):
        lab.create_brief(_make_brief(title="Brief 1"))
        lab.create_brief(_make_brief(title="Brief 2"))
        assert len(lab.list_briefs()) == 2

    def test_list_briefs_filter_status(self, lab):
        lab.create_brief(_make_brief(title="Planning", status="planning"))
        lab.create_brief(_make_brief(title="Rigging", status="rigging"))
        assert len(lab.list_briefs(status="planning")) == 1
        assert len(lab.list_briefs(status="rigging")) == 1

    def test_list_briefs_filter_assignee(self, lab):
        lab.create_brief(_make_brief(assignee="maya"))
        lab.create_brief(_make_brief(assignee="chiba"))
        assert len(lab.list_briefs(assignee="maya")) == 1

    def test_update_brief(self, lab):
        created = lab.create_brief(_make_brief())
        updated = lab.update_brief(created.id, {"title": "Updated Title", "priority": "high"})
        assert updated.title == "Updated Title"
        assert updated.priority == "high"

    def test_update_brief_not_found(self, lab):
        assert lab.update_brief("nonexistent", {"title": "x"}) is None

    def test_delete_brief(self, lab):
        created = lab.create_brief(_make_brief())
        assert lab.delete_brief(created.id) is True
        assert lab.get_brief(created.id) is None

    def test_delete_brief_not_found(self, lab):
        assert lab.delete_brief("nonexistent") is False


# =============================================================================
# Camera Rigging
# =============================================================================


class TestCameraRigging:
    def test_apply_camera_rig(self, lab):
        created = lab.create_brief(_make_brief())
        camera = CameraRig(body="red_v_raptor", lens="panavision_c", focal=40, aperture=2.8)
        post = BriefPostConfig(stock="kodak_5219", color_temp=5200, grain=10)
        updated = lab.apply_camera_rig(created.id, camera, post)
        assert updated.camera.body == "red_v_raptor"
        assert updated.post.stock == "kodak_5219"

    def test_apply_rig_to_shot(self, lab):
        shot = SequenceShot(id="s01", title="Shot 1", prompt="Test shot")
        brief = _make_brief(type="sequence", shots=[shot])
        created = lab.create_brief(brief)

        camera = CameraRig(body="sony_venice2", focal=85)
        post = BriefPostConfig(stock="fuji_eterna")
        result = lab.apply_rig_to_shot(created.id, "s01", camera, post)
        assert result is not None
        assert result.camera.body == "sony_venice2"

    def test_apply_rig_to_shot_not_found(self, lab):
        created = lab.create_brief(_make_brief(type="sequence", shots=[]))
        camera = CameraRig()
        post = BriefPostConfig()
        result = lab.apply_rig_to_shot(created.id, "nonexistent", camera, post)
        assert result is None


# =============================================================================
# Prompt Building
# =============================================================================


class TestPromptBuilding:
    def test_build_brief_prompt_with_rig(self, lab):
        brief = _make_brief()
        created = lab.create_brief(brief)
        camera = CameraRig(body="arri_alexa35", lens="cooke_s7i", focal=24, aperture=5.6)
        post = BriefPostConfig(stock="kodak_5219")
        lab.apply_camera_rig(created.id, camera, post)

        prompt = lab.build_brief_prompt(created.id)
        assert "ARRI Alexa 35" in prompt
        assert "24mm" in prompt
        assert "Kodak 5219" in prompt

    def test_build_brief_prompt_no_rig(self, lab):
        created = lab.create_brief(_make_brief(prompt="Base prompt only"))
        prompt = lab.build_brief_prompt(created.id)
        assert prompt == "Base prompt only"

    def test_build_shot_prompt(self, lab):
        shot = SequenceShot(
            id="s01", title="Shot 1", prompt="Close-up detail",
            camera=CameraRig(body="arri_alexa35", lens="cooke_s7i", focal=85, aperture=1.8),
            post=BriefPostConfig(stock="kodak_5219"),
        )
        brief = _make_brief(type="sequence", shots=[shot])
        created = lab.create_brief(brief)

        prompt = lab.build_brief_prompt(created.id, shot_id="s01")
        assert "85mm" in prompt
        assert "f/1.8" in prompt

    def test_build_prompt_not_found(self, lab):
        assert lab.build_brief_prompt("nonexistent") is None


# =============================================================================
# Sequence Management
# =============================================================================


class TestSequenceManagement:
    def test_add_shot(self, lab):
        created = lab.create_brief(_make_brief(type="sequence"))
        shot = SequenceShot(id="s01", title="New Shot", prompt="Test")
        updated = lab.add_shot(created.id, shot)
        assert updated is not None
        assert len(updated.shots) == 1

    def test_remove_shot(self, lab):
        shots = [
            SequenceShot(id="s01", title="Shot 1", prompt="A"),
            SequenceShot(id="s02", title="Shot 2", prompt="B"),
        ]
        created = lab.create_brief(_make_brief(type="sequence", shots=shots))
        updated = lab.remove_shot(created.id, "s01")
        assert len(updated.shots) == 1
        assert updated.shots[0].id == "s02"

    def test_reorder_shots(self, lab):
        shots = [
            SequenceShot(id="s01", title="Shot 1", prompt="A"),
            SequenceShot(id="s02", title="Shot 2", prompt="B"),
            SequenceShot(id="s03", title="Shot 3", prompt="C"),
        ]
        created = lab.create_brief(_make_brief(type="sequence", shots=shots))
        updated = lab.reorder_shots(created.id, ["s03", "s01", "s02"])
        assert [s.id for s in updated.shots] == ["s03", "s01", "s02"]


# =============================================================================
# YAML Persistence
# =============================================================================


class TestYAMLPersistence:
    def test_brief_round_trip(self, lab):
        brief = _make_brief(
            title="Round Trip Test",
            characters=["cornelius", "mordecai"],
            location="blackstone_hollow",
            tags=["establishing", "key_frame"],
            priority="high",
        )
        created = lab.create_brief(brief)

        # Verify YAML file exists
        path = lab._brief_path(created.id)
        assert path.exists()

        # Re-read
        loaded = lab.get_brief(created.id)
        assert loaded.title == "Round Trip Test"
        assert loaded.characters == ["cornelius", "mordecai"]
        assert loaded.priority == "high"

    def test_brief_with_camera_persists(self, lab):
        brief = _make_brief(
            camera=CameraRig(body="red_v_raptor", focal=40),
            post=BriefPostConfig(stock="cinestill_800", halation=15),
        )
        created = lab.create_brief(brief)
        loaded = lab.get_brief(created.id)
        assert loaded.camera.body == "red_v_raptor"
        assert loaded.post.halation == 15

    def test_malformed_yaml_returns_none(self, lab, project_dir):
        bad_path = project_dir / "lab" / "briefs" / "bad.yaml"
        bad_path.write_text("not: [valid: {{yaml")
        assert lab.get_brief("bad") is None
