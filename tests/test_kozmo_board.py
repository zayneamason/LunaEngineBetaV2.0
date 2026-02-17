"""
Tests for KOZMO Phase 9: Production Board Service

Tests aggregation, grouping, dependency checking, AI thread management,
bulk operations, and stats.
"""

import pytest
from pathlib import Path

from luna.services.kozmo.lab_pipeline import LabPipelineService
from luna.services.kozmo._quarantine.production_board import ProductionBoardService
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
    (tmp_path / "lab" / "briefs").mkdir(parents=True)
    (tmp_path / "lab" / "assets").mkdir(parents=True)
    return tmp_path


@pytest.fixture
def lab(project_dir):
    return LabPipelineService(project_dir)


@pytest.fixture
def board(lab):
    return ProductionBoardService(lab)


def _make_brief(**kwargs) -> ProductionBrief:
    defaults = {
        "id": "",
        "type": "single",
        "title": "Test Brief",
        "prompt": "A test scene",
    }
    defaults.update(kwargs)
    return ProductionBrief(**defaults)


def _seed_briefs(lab):
    """Create a realistic set of briefs for testing."""
    b1 = lab.create_brief(_make_brief(
        title="Blackstone Hollow Establishing",
        status="rigging", priority="high",
        characters=["cornelius", "mordecai"], assignee="maya",
    ))
    b2 = lab.create_brief(_make_brief(
        title="Road North Montage",
        type="sequence", status="planning", priority="high",
        characters=["cornelius"], assignee="chiba",
        shots=[
            SequenceShot(id="s01", title="Low Branch", prompt="A"),
            SequenceShot(id="s02", title="Narrow Bridge", prompt="B"),
        ],
    ))
    b3 = lab.create_brief(_make_brief(
        title="Cornelius Garden Reference",
        type="reference", status="planning", priority="medium",
        characters=["cornelius"], assignee="maya",
    ))
    b4 = lab.create_brief(_make_brief(
        title="Bottles and Books Close-up",
        status="generating", priority="medium",
        characters=["mordecai"], assignee="maya",
        progress=62,
    ))
    return b1, b2, b3, b4


# =============================================================================
# Stats
# =============================================================================


class TestStats:
    def test_stats_empty(self, board):
        stats = board.get_stats()
        assert stats["total_briefs"] == 0
        assert stats["total_shots"] == 0

    def test_stats_with_briefs(self, lab, board):
        _seed_briefs(lab)
        stats = board.get_stats()
        assert stats["total_briefs"] == 4
        # b1=1, b2=2 shots, b3=1, b4=1 = 5 total
        assert stats["total_shots"] == 5
        assert stats["by_status"]["rigging"] == 1
        assert stats["by_status"]["planning"] == 2
        assert stats["by_status"]["generating"] == 1


# =============================================================================
# Grouping
# =============================================================================


class TestGrouping:
    def test_group_by_status(self, lab, board):
        _seed_briefs(lab)
        result = board.get_board(group_by="status")
        groups = {g["key"]: g for g in result["groups"]}
        assert "rigging" in groups
        assert "planning" in groups
        assert "generating" in groups
        assert len(groups["planning"]["briefs"]) == 2

    def test_group_by_priority(self, lab, board):
        _seed_briefs(lab)
        result = board.get_board(group_by="priority")
        groups = {g["key"]: g for g in result["groups"]}
        assert "high" in groups
        assert "medium" in groups

    def test_group_by_assignee(self, lab, board):
        _seed_briefs(lab)
        result = board.get_board(group_by="assignee")
        groups = {g["key"]: g for g in result["groups"]}
        assert "maya" in groups
        assert "chiba" in groups
        assert len(groups["maya"]["briefs"]) == 3  # b1, b3, b4

    def test_group_by_character(self, lab, board):
        _seed_briefs(lab)
        result = board.get_board(group_by="character")
        groups = {g["key"]: g for g in result["groups"]}
        assert "cornelius" in groups
        assert "mordecai" in groups
        # cornelius appears in b1, b2, b3
        assert len(groups["cornelius"]["briefs"]) == 3

    def test_filter_by_status(self, lab, board):
        _seed_briefs(lab)
        result = board.get_board(status="planning")
        total_briefs = sum(len(g["briefs"]) for g in result["groups"])
        assert total_briefs == 2


# =============================================================================
# Dependencies
# =============================================================================


class TestDependencies:
    def test_no_dependencies(self, lab, board):
        b1 = lab.create_brief(_make_brief(title="No deps"))
        result = board.check_dependencies(b1.id)
        assert result["can_proceed"] is True
        assert result["blocking"] == []
        assert result["blocked_by_this"] == []

    def test_blocking_dependency(self, lab, board):
        b1 = lab.create_brief(_make_brief(title="Must finish first", status="planning"))
        b2 = lab.create_brief(_make_brief(title="Depends on first", dependencies=[b1.id]))

        result = board.check_dependencies(b2.id)
        assert result["can_proceed"] is False
        assert len(result["blocking"]) == 1
        assert result["blocking"][0]["id"] == b1.id

    def test_met_dependency(self, lab, board):
        b1 = lab.create_brief(_make_brief(title="Done", status="approved"))
        b2 = lab.create_brief(_make_brief(title="Depends on done", dependencies=[b1.id]))

        result = board.check_dependencies(b2.id)
        assert result["can_proceed"] is True
        assert result["blocking"] == []

    def test_blocked_by_this(self, lab, board):
        b1 = lab.create_brief(_make_brief(title="Blocker"))
        b2 = lab.create_brief(_make_brief(title="Waiting", dependencies=[b1.id]))
        b3 = lab.create_brief(_make_brief(title="Also waiting", dependencies=[b1.id]))

        result = board.check_dependencies(b1.id)
        assert len(result["blocked_by_this"]) == 2

    def test_not_found(self, board):
        result = board.check_dependencies("nonexistent")
        assert result["can_proceed"] is False


# =============================================================================
# Push Ready
# =============================================================================


class TestPushReady:
    def test_push_ready_briefs(self, lab, board):
        b1 = lab.create_brief(_make_brief(title="Ready", status="rigging"))
        b2 = lab.create_brief(_make_brief(title="Not ready", status="planning"))

        pushed = board.push_ready_to_lab()
        assert b1.id in pushed
        assert b2.id not in pushed

        # Verify status changed
        updated = lab.get_brief(b1.id)
        assert updated.status == "queued"

    def test_push_blocked_brief_not_pushed(self, lab, board):
        b1 = lab.create_brief(_make_brief(title="Dependency", status="planning"))
        b2 = lab.create_brief(_make_brief(
            title="Has dep", status="rigging", dependencies=[b1.id]
        ))

        pushed = board.push_ready_to_lab()
        assert b2.id not in pushed

    def test_push_empty(self, board):
        pushed = board.push_ready_to_lab()
        assert pushed == []


# =============================================================================
# AI Thread
# =============================================================================


class TestAIThread:
    def test_add_to_thread(self, lab, board):
        b = lab.create_brief(_make_brief())
        thread = board.add_to_thread(b.id, "user", "What about this shot?")
        assert len(thread) == 1
        assert thread[0]["role"] == "user"
        assert thread[0]["text"] == "What about this shot?"

    def test_add_multiple_messages(self, lab, board):
        b = lab.create_brief(_make_brief())
        board.add_to_thread(b.id, "user", "Question?")
        thread = board.add_to_thread(b.id, "luna", "Here's my analysis.")
        assert len(thread) == 2

    def test_get_thread(self, lab, board):
        b = lab.create_brief(_make_brief())
        board.add_to_thread(b.id, "user", "Hello")
        thread = board.get_thread(b.id)
        assert len(thread) == 1

    def test_thread_persists(self, lab, board):
        b = lab.create_brief(_make_brief())
        board.add_to_thread(b.id, "user", "Persist this")

        # Re-create service to test persistence
        lab2 = LabPipelineService(lab.root)
        board2 = ProductionBoardService(lab2)
        thread = board2.get_thread(b.id)
        assert len(thread) == 1
        assert thread[0]["text"] == "Persist this"

    def test_thread_not_found(self, board):
        assert board.get_thread("nonexistent") is None
        assert board.add_to_thread("nonexistent", "user", "x") is None


# =============================================================================
# Bulk Update
# =============================================================================


class TestBulkUpdate:
    def test_bulk_update_priority(self, lab, board):
        b1 = lab.create_brief(_make_brief(title="A"))
        b2 = lab.create_brief(_make_brief(title="B"))
        b3 = lab.create_brief(_make_brief(title="C"))

        updated = board.bulk_update([b1.id, b2.id], {"priority": "critical"})
        assert len(updated) == 2
        assert all(b.priority == "critical" for b in updated)

        # b3 unchanged
        assert lab.get_brief(b3.id).priority == "medium"

    def test_bulk_update_assignee(self, lab, board):
        b1 = lab.create_brief(_make_brief(title="A"))
        b2 = lab.create_brief(_make_brief(title="B"))

        updated = board.bulk_update([b1.id, b2.id], {"assignee": "chiba"})
        assert all(b.assignee == "chiba" for b in updated)

    def test_bulk_update_partial(self, lab, board):
        b1 = lab.create_brief(_make_brief(title="A"))
        updated = board.bulk_update([b1.id, "nonexistent"], {"status": "rigging"})
        assert len(updated) == 1
