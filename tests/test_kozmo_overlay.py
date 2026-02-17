"""
Tests for KOZMO Phase 7: Overlay Service

Tests annotation CRUD, sidecar file management, resolve/unresolve,
type filtering, push-to-lab, and graceful degradation.
"""

import pytest
import yaml
from pathlib import Path
from datetime import datetime

from luna.services.kozmo._quarantine.overlay import OverlayService
from luna.services.kozmo.types import (
    Annotation,
    OverlayState,
    LabAction,
    AgentTask,
    TextHighlight,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def project_dir(tmp_path):
    """Create a minimal project structure with a .scribo file."""
    story = tmp_path / "story" / "act_1" / "ch_01"
    story.mkdir(parents=True)

    # Create a .scribo file
    scribo_content = (
        "---\ntype: scene\ncharacters_present: [mordecai, cornelius]\n"
        "location: crooked_nail\nstatus: draft\n---\n"
        "The tavern smelled of woodsmoke and regret."
    )
    (story / "sc_01_departure.scribo").write_text(scribo_content)
    (story / "sc_02_road_north.scribo").write_text(
        "---\ntype: scene\nstatus: draft\n---\nThe road north was not kind."
    )
    return tmp_path


@pytest.fixture
def svc(project_dir):
    return OverlayService(project_dir)


def _make_annotation(
    ann_type="note", paragraph_id="p3", text="Test note", **kwargs
) -> Annotation:
    return Annotation(
        id="",
        paragraph_id=paragraph_id,
        type=ann_type,
        author="Ahab",
        text=text,
        **kwargs,
    )


# =============================================================================
# Basic CRUD
# =============================================================================


class TestAnnotationCRUD:
    def test_get_overlay_empty(self, svc):
        state = svc.get_overlay("sc_01_departure")
        assert state.document_slug == "sc_01_departure"
        assert state.annotations == []

    def test_add_annotation(self, svc):
        ann = _make_annotation()
        created = svc.add_annotation("sc_01_departure", ann)
        assert created.id != ""
        assert created.text == "Test note"
        assert created.created_at is not None

    def test_add_annotation_persists(self, svc):
        ann = _make_annotation()
        svc.add_annotation("sc_01_departure", ann)
        state = svc.get_overlay("sc_01_departure")
        assert len(state.annotations) == 1
        assert state.annotations[0].text == "Test note"

    def test_add_multiple_annotations(self, svc):
        svc.add_annotation("sc_01_departure", _make_annotation(text="First"))
        svc.add_annotation("sc_01_departure", _make_annotation(text="Second"))
        state = svc.get_overlay("sc_01_departure")
        assert len(state.annotations) == 2

    def test_update_annotation(self, svc):
        created = svc.add_annotation("sc_01_departure", _make_annotation())
        updated = svc.update_annotation(
            "sc_01_departure", created.id, {"text": "Updated text"}
        )
        assert updated is not None
        assert updated.text == "Updated text"

    def test_update_annotation_not_found(self, svc):
        result = svc.update_annotation("sc_01_departure", "nonexistent", {"text": "x"})
        assert result is None

    def test_delete_annotation(self, svc):
        created = svc.add_annotation("sc_01_departure", _make_annotation())
        deleted = svc.delete_annotation("sc_01_departure", created.id)
        assert deleted is True
        state = svc.get_overlay("sc_01_departure")
        assert len(state.annotations) == 0

    def test_delete_annotation_not_found(self, svc):
        deleted = svc.delete_annotation("sc_01_departure", "nonexistent")
        assert deleted is False


# =============================================================================
# Resolve
# =============================================================================


class TestResolve:
    def test_resolve_annotation(self, svc):
        created = svc.add_annotation("sc_01_departure", _make_annotation())
        assert created.resolved is False

        resolved = svc.resolve_annotation("sc_01_departure", created.id)
        assert resolved.resolved is True
        assert resolved.resolved_at is not None

    def test_unresolve_annotation(self, svc):
        created = svc.add_annotation("sc_01_departure", _make_annotation())
        svc.resolve_annotation("sc_01_departure", created.id)
        unresolved = svc.resolve_annotation("sc_01_departure", created.id)
        assert unresolved.resolved is False
        assert unresolved.resolved_at is None

    def test_resolve_not_found(self, svc):
        result = svc.resolve_annotation("sc_01_departure", "nonexistent")
        assert result is None


# =============================================================================
# Filtering
# =============================================================================


class TestFiltering:
    def test_get_annotations_by_type(self, svc):
        svc.add_annotation("sc_01_departure", _make_annotation(ann_type="note"))
        svc.add_annotation("sc_01_departure", _make_annotation(ann_type="continuity"))
        svc.add_annotation("sc_01_departure", _make_annotation(ann_type="note"))

        notes = svc.get_annotations_by_type("sc_01_departure", "note")
        assert len(notes) == 2
        continuity = svc.get_annotations_by_type("sc_01_departure", "continuity")
        assert len(continuity) == 1

    def test_get_annotations_by_type_empty(self, svc):
        result = svc.get_annotations_by_type("sc_01_departure", "action")
        assert result == []


# =============================================================================
# Action Aggregation
# =============================================================================


class TestActionAggregation:
    def test_get_all_actions(self, svc):
        svc.add_annotation(
            "sc_01_departure",
            _make_annotation(
                ann_type="action",
                lab_action=LabAction(type="generate_image", status="planning"),
            ),
        )
        svc.add_annotation(
            "sc_01_departure",
            _make_annotation(ann_type="note"),  # Not an action
        )
        svc.add_annotation(
            "sc_02_road_north",
            _make_annotation(
                ann_type="agent",
                agent_task=AgentTask(agent="maya", status="pending", action="generate_reference"),
            ),
        )

        actions = svc.get_all_actions()
        assert len(actions) == 2

    def test_get_all_actions_empty(self, svc):
        actions = svc.get_all_actions()
        assert actions == []


# =============================================================================
# Push to LAB
# =============================================================================


class TestPushToLab:
    def test_push_action_annotation(self, svc):
        created = svc.add_annotation(
            "sc_01_departure",
            _make_annotation(
                ann_type="action",
                text="Need establishing shot of Blackstone Hollow",
                lab_action=LabAction(
                    type="generate_image",
                    status="planning",
                    prompt="Wide shot, stone cottage, morning mist",
                    assignee="Maya",
                ),
            ),
        )
        result = svc.push_to_lab("sc_01_departure", created.id)
        assert result is not None
        assert result["type"] == "single"
        assert result["prompt"] == "Wide shot, stone cottage, morning mist"
        assert result["assignee"] == "Maya"
        assert result["source_scene"] == "sc_01_departure"

    def test_push_agent_task_annotation(self, svc):
        created = svc.add_annotation(
            "sc_01_departure",
            _make_annotation(
                ann_type="agent",
                text="Maya: reference art for Cornelius",
                agent_task=AgentTask(
                    agent="maya", status="pending",
                    action="generate_reference", entity="cornelius",
                ),
            ),
        )
        result = svc.push_to_lab("sc_01_departure", created.id)
        assert result is not None
        assert result["type"] == "reference"
        assert result["assignee"] == "maya"
        assert "cornelius" in result["characters"]

    def test_push_shot_sequence(self, svc):
        created = svc.add_annotation(
            "sc_01_departure",
            _make_annotation(
                ann_type="action",
                text="Road montage",
                lab_action=LabAction(
                    type="shot_sequence",
                    status="planning",
                    shots=["Low branch", "Narrow bridge", "Wide landscape"],
                ),
            ),
        )
        result = svc.push_to_lab("sc_01_departure", created.id)
        assert result["type"] == "sequence"

    def test_push_not_found(self, svc):
        result = svc.push_to_lab("sc_01_departure", "nonexistent")
        assert result is None

    def test_push_all_actions(self, svc):
        svc.add_annotation(
            "sc_01_departure",
            _make_annotation(
                ann_type="action",
                lab_action=LabAction(type="generate_image", status="planning", prompt="Shot 1"),
            ),
        )
        svc.add_annotation(
            "sc_01_departure",
            _make_annotation(ann_type="note", text="Just a note"),
        )
        svc.add_annotation(
            "sc_01_departure",
            _make_annotation(
                ann_type="agent",
                agent_task=AgentTask(agent="maya", status="pending", action="ref"),
            ),
        )

        results = svc.push_all_actions("sc_01_departure")
        assert len(results) == 2  # action + agent, not the note


# =============================================================================
# Sidecar File Handling
# =============================================================================


class TestSidecarFiles:
    def test_sidecar_created_on_first_annotation(self, svc, project_dir):
        svc.add_annotation("sc_01_departure", _make_annotation())
        sidecar = project_dir / "story" / "act_1" / "ch_01" / "sc_01_departure.overlay.yaml"
        assert sidecar.exists()

    def test_sidecar_not_created_without_annotations(self, svc, project_dir):
        svc.get_overlay("sc_01_departure")  # Just reading
        sidecar = project_dir / "story" / "act_1" / "ch_01" / "sc_01_departure.overlay.yaml"
        assert not sidecar.exists()

    def test_malformed_sidecar_returns_empty(self, svc, project_dir):
        sidecar = project_dir / "story" / "act_1" / "ch_01" / "sc_01_departure.overlay.yaml"
        sidecar.write_text("this is not valid: [yaml: {{broken")
        state = svc.get_overlay("sc_01_departure")
        assert state.annotations == []

    def test_sidecar_round_trip(self, svc):
        ann = _make_annotation(
            ann_type="action",
            text="Test action",
            lab_action=LabAction(type="generate_image", status="queued", prompt="Test"),
            highlight=TextHighlight(start=10, end=25),
        )
        created = svc.add_annotation("sc_01_departure", ann)

        # Re-read from disk
        state = svc.get_overlay("sc_01_departure")
        assert len(state.annotations) == 1
        loaded = state.annotations[0]
        assert loaded.id == created.id
        assert loaded.type == "action"
        assert loaded.lab_action.type == "generate_image"
        assert loaded.highlight.start == 10
        assert loaded.highlight.end == 25


# =============================================================================
# Annotation Types
# =============================================================================


class TestAnnotationTypes:
    @pytest.mark.parametrize("ann_type", ["note", "comment", "continuity", "agent", "action", "luna"])
    def test_all_types_supported(self, svc, ann_type):
        created = svc.add_annotation(
            "sc_01_departure",
            _make_annotation(ann_type=ann_type),
        )
        assert created.type == ann_type

    def test_annotation_with_highlight(self, svc):
        ann = _make_annotation(highlight=TextHighlight(start=38, end=56))
        created = svc.add_annotation("sc_01_departure", ann)
        assert created.highlight is not None
        assert created.highlight.start == 38
