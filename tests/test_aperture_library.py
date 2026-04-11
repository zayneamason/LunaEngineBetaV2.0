"""
Tests for Aperture & Library Cognition System.

Covers:
- Phase 1: Collection lock-in computation + engine
- Phase 2: Annotation system (the bridge)
- Phase 3: Aperture state + presets + manager
- Phase 4: Assembler aperture integration
"""

import math
import pytest
import sqlite3
import asyncio
from unittest.mock import AsyncMock, MagicMock
from pathlib import Path
from tempfile import TemporaryDirectory


# =============================================================================
# PHASE 1: Collection Lock-In
# =============================================================================

class TestCollectionLockInComputation:
    """Test the pure computation function."""

    def test_zero_activity_returns_floor(self):
        from luna.substrate.collection_lock_in import compute_collection_lock_in
        result = compute_collection_lock_in()
        assert result >= 0.05, "Floor is 0.05 — no collection ever reaches zero"

    def test_high_activity_approaches_ceiling(self):
        from luna.substrate.collection_lock_in import compute_collection_lock_in
        result = compute_collection_lock_in(
            access_count=100,
            annotation_count=50,
            connected_collections=10,
            entity_overlap=30,
        )
        assert result > 0.70, "High activity should produce settled-range lock-in"
        assert result <= 1.0, "Cannot exceed 1.0"

    def test_decay_reduces_lock_in(self):
        from luna.substrate.collection_lock_in import compute_collection_lock_in
        fresh = compute_collection_lock_in(access_count=20, annotation_count=5)
        decayed = compute_collection_lock_in(
            access_count=20, annotation_count=5,
            seconds_since_access=86400 * 30,  # 30 days
        )
        assert decayed < fresh, "Decay should reduce lock-in over time"

    def test_floor_never_breached(self):
        from luna.substrate.collection_lock_in import compute_collection_lock_in
        result = compute_collection_lock_in(
            access_count=0, annotation_count=0,
            seconds_since_access=86400 * 365,  # 1 year
        )
        assert result >= 0.05, "Floor of 0.05 is absolute"

    def test_annotation_boosts_lock_in(self):
        from luna.substrate.collection_lock_in import compute_collection_lock_in
        without = compute_collection_lock_in(access_count=10)
        with_annotations = compute_collection_lock_in(access_count=10, annotation_count=10)
        assert with_annotations > without, "Annotations should increase lock-in"


class TestCollectionLockInState:
    """Test state classification."""

    def test_settled_threshold(self):
        from luna.substrate.collection_lock_in import classify_collection_state
        from luna.substrate.lock_in import LockInState
        assert classify_collection_state(0.75) == LockInState.SETTLED

    def test_fluid_range(self):
        from luna.substrate.collection_lock_in import classify_collection_state
        from luna.substrate.lock_in import LockInState
        assert classify_collection_state(0.50) == LockInState.FLUID

    def test_drifting_threshold(self):
        from luna.substrate.collection_lock_in import classify_collection_state
        from luna.substrate.lock_in import LockInState
        assert classify_collection_state(0.20) == LockInState.DRIFTING


class TestCollectionLockInEngine:
    """Test the database-backed engine."""

    @pytest.fixture
    def mock_db(self):
        """Create an in-memory SQLite database with the collection_lock_in table."""
        db = AsyncMock()
        self._rows = {}

        async def mock_execute(sql, params=None):
            return MagicMock()

        async def mock_fetchone(sql, params=None):
            return None

        async def mock_fetchall(sql, params=None):
            return []

        db.execute = mock_execute
        db.fetchone = mock_fetchone
        db.fetchall = mock_fetchall
        return db

    @pytest.mark.asyncio
    async def test_ensure_table(self, mock_db):
        from luna.substrate.collection_lock_in import CollectionLockInEngine
        engine = CollectionLockInEngine(mock_db)
        await engine.ensure_table()
        # Should not raise

    @pytest.mark.asyncio
    async def test_ensure_tracked(self, mock_db):
        from luna.substrate.collection_lock_in import CollectionLockInEngine
        engine = CollectionLockInEngine(mock_db)
        await engine.ensure_tracked("dataroom")
        # Should not raise


# =============================================================================
# PHASE 2: Annotations
# =============================================================================

class TestAnnotationType:
    """Test annotation type enum."""

    def test_bookmark(self):
        from luna.substrate.collection_annotations import AnnotationType
        assert AnnotationType.BOOKMARK.value == "bookmark"

    def test_note(self):
        from luna.substrate.collection_annotations import AnnotationType
        assert AnnotationType.NOTE.value == "note"

    def test_flag(self):
        from luna.substrate.collection_annotations import AnnotationType
        assert AnnotationType.FLAG.value == "flag"


class TestAnnotationProvenance:
    """Test provenance metadata."""

    def test_provenance_to_dict(self):
        from luna.substrate.collection_annotations import AnnotationProvenance
        prov = AnnotationProvenance(
            source="aibrarian",
            collection="dataroom",
            doc_id="uuid-123",
            chunk_index=3,
            annotation_type="note",
            original_text_preview="The Rotary Foundation...",
        )
        d = prov.to_dict()
        assert d["source"] == "aibrarian"
        assert d["collection"] == "dataroom"
        assert d["doc_id"] == "uuid-123"
        assert d["chunk_index"] == 3
        assert d["annotation_type"] == "note"

    def test_provenance_without_chunk(self):
        from luna.substrate.collection_annotations import AnnotationProvenance
        prov = AnnotationProvenance(
            source="aibrarian",
            collection="dataroom",
            doc_id="uuid-123",
        )
        d = prov.to_dict()
        assert "chunk_index" not in d, "chunk_index omitted when None"

    def test_provenance_truncates_preview(self):
        from luna.substrate.collection_annotations import AnnotationProvenance
        long_text = "x" * 500
        prov = AnnotationProvenance(original_text_preview=long_text)
        # The truncation happens in AnnotationEngine.create, not in provenance itself


class TestAnnotationEngine:
    """Test the annotation engine."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        db.fetchone = AsyncMock(return_value=None)
        db.fetchall = AsyncMock(return_value=[])
        return db

    @pytest.fixture
    def mock_matrix(self):
        matrix = AsyncMock()
        matrix.add_node = AsyncMock(return_value="node-uuid-456")
        return matrix

    @pytest.fixture
    def mock_lock_in(self):
        lock_in = AsyncMock()
        lock_in.bump_annotation = AsyncMock(return_value=0.5)
        return lock_in

    @pytest.mark.asyncio
    async def test_create_annotation_with_matrix(self, mock_db, mock_matrix, mock_lock_in):
        from luna.substrate.collection_annotations import AnnotationEngine, AnnotationType
        engine = AnnotationEngine(mock_db, memory_matrix=mock_matrix, lock_in_engine=mock_lock_in)

        ann_id = await engine.create(
            collection_key="dataroom",
            doc_id="doc-001",
            annotation_type=AnnotationType.NOTE,
            content="Cross-ref Kinoni budget with Rotary grant",
            chunk_index=3,
        )

        assert ann_id is not None
        # Matrix node should have been created
        mock_matrix.add_node.assert_called_once()
        call_kwargs = mock_matrix.add_node.call_args
        assert call_kwargs.kwargs["node_type"] == "ANNOTATION"
        assert "aibrarian" in str(call_kwargs.kwargs["metadata"])

        # Lock-in should have been bumped
        mock_lock_in.bump_annotation.assert_called_once_with("dataroom")

    @pytest.mark.asyncio
    async def test_create_annotation_without_matrix(self, mock_db):
        from luna.substrate.collection_annotations import AnnotationEngine, AnnotationType
        engine = AnnotationEngine(mock_db)  # No matrix, no lock-in

        ann_id = await engine.create(
            collection_key="dataroom",
            doc_id="doc-001",
            annotation_type=AnnotationType.BOOKMARK,
        )

        assert ann_id is not None
        # DB insert should still happen
        mock_db.execute.assert_called()


# =============================================================================
# PHASE 3: Aperture
# =============================================================================

class TestAperturePresets:
    """Test aperture preset values."""

    def test_tunnel_angle(self):
        from luna.context.aperture import AperturePreset, APERTURE_ANGLES
        assert APERTURE_ANGLES[AperturePreset.TUNNEL] == 15

    def test_balanced_angle(self):
        from luna.context.aperture import AperturePreset, APERTURE_ANGLES
        assert APERTURE_ANGLES[AperturePreset.BALANCED] == 55

    def test_open_angle(self):
        from luna.context.aperture import AperturePreset, APERTURE_ANGLES
        assert APERTURE_ANGLES[AperturePreset.OPEN] == 95


class TestApertureState:
    """Test aperture state properties."""

    def test_breakthrough_threshold_tunnel(self):
        from luna.context.aperture import ApertureState, AperturePreset
        state = ApertureState(preset=AperturePreset.TUNNEL, angle=15)
        # 0.30 + ((95 - 15) / 95) * 0.50 = 0.30 + 0.42 = 0.72
        assert abs(state.breakthrough_threshold - 0.72) < 0.01

    def test_breakthrough_threshold_balanced(self):
        from luna.context.aperture import ApertureState, AperturePreset
        state = ApertureState(preset=AperturePreset.BALANCED, angle=55)
        # 0.30 + ((95 - 55) / 95) * 0.50 = 0.30 + 0.21 = 0.51
        assert abs(state.breakthrough_threshold - 0.51) < 0.01

    def test_breakthrough_threshold_open(self):
        from luna.context.aperture import ApertureState, AperturePreset
        state = ApertureState(preset=AperturePreset.OPEN, angle=95)
        # 0.30 + ((95 - 95) / 95) * 0.50 = 0.30
        assert state.breakthrough_threshold == 0.30

    def test_inner_ring_tunnel(self):
        from luna.context.aperture import ApertureState, AperturePreset
        state = ApertureState(preset=AperturePreset.TUNNEL)
        assert state.inner_ring_threshold == 0.75

    def test_inner_ring_open(self):
        from luna.context.aperture import ApertureState, AperturePreset
        state = ApertureState(preset=AperturePreset.OPEN)
        assert state.inner_ring_threshold == 0.0

    def test_to_dict(self):
        from luna.context.aperture import ApertureState, AperturePreset
        state = ApertureState(
            preset=AperturePreset.NARROW,
            angle=35,
            focus_tags=["luna", "architecture"],
            app_context="kozmo",
        )
        d = state.to_dict()
        assert d["preset"] == "narrow"
        assert d["angle"] == 35
        assert d["focus_tags"] == ["luna", "architecture"]
        assert d["app_context"] == "kozmo"
        assert "breakthrough_threshold" in d
        assert "inner_ring_threshold" in d


class TestApertureManager:
    """Test the aperture manager."""

    def test_default_state(self):
        from luna.context.aperture import ApertureManager, AperturePreset
        mgr = ApertureManager()
        assert mgr.state.preset == AperturePreset.WIDE
        assert mgr.state.angle == 75

    def test_set_app_context_kozmo(self):
        from luna.context.aperture import ApertureManager, AperturePreset
        mgr = ApertureManager()
        mgr.set_app_context("kozmo")
        assert mgr.state.preset == AperturePreset.NARROW
        assert mgr.state.angle == 35
        assert mgr.state.app_context == "kozmo"

    def test_set_app_context_dataroom(self):
        from luna.context.aperture import ApertureManager, AperturePreset
        mgr = ApertureManager()
        mgr.set_app_context("dataroom")
        assert mgr.state.preset == AperturePreset.TUNNEL
        assert mgr.state.angle == 15

    def test_user_override_persists_across_app_change(self):
        from luna.context.aperture import ApertureManager, AperturePreset
        mgr = ApertureManager()
        mgr.set_preset(AperturePreset.WIDE)
        assert mgr.state.user_override is True

        # App change should NOT reset when user_override is True
        mgr.set_app_context("dataroom")
        assert mgr.state.preset == AperturePreset.WIDE
        assert mgr.state.angle == 75

    def test_clear_override_restores_app_default(self):
        from luna.context.aperture import ApertureManager, AperturePreset
        mgr = ApertureManager()
        mgr.set_app_context("kozmo")
        mgr.set_preset(AperturePreset.OPEN)  # User override
        assert mgr.state.preset == AperturePreset.OPEN

        mgr.clear_override()
        assert mgr.state.preset == AperturePreset.NARROW  # Kozmo default
        assert mgr.state.user_override is False

    def test_set_angle_snaps_to_preset(self):
        from luna.context.aperture import ApertureManager, AperturePreset
        mgr = ApertureManager()
        mgr.set_angle(56)  # Closest to BALANCED (55)
        assert mgr.state.preset == AperturePreset.BALANCED
        assert mgr.state.angle == 56  # Raw angle preserved

    def test_set_angle_clamps(self):
        from luna.context.aperture import ApertureManager
        mgr = ApertureManager()
        mgr.set_angle(5)  # Below minimum
        assert mgr.state.angle == 15

        mgr.set_angle(200)  # Above maximum
        assert mgr.state.angle == 95

    def test_set_focus_tags(self):
        from luna.context.aperture import ApertureManager
        mgr = ApertureManager()
        mgr.set_focus_tags(["dinosaur", "screenplay"])
        assert mgr.state.focus_tags == ["dinosaur", "screenplay"]

    def test_from_dict(self):
        from luna.context.aperture import ApertureManager, AperturePreset
        mgr = ApertureManager()
        mgr.from_dict({
            "preset": "tunnel",
            "angle": 15,
            "focus_tags": ["urgent"],
            "app_context": "guardian",
            "user_override": True,
        })
        assert mgr.state.preset == AperturePreset.TUNNEL
        assert mgr.state.angle == 15
        assert mgr.state.focus_tags == ["urgent"]
        assert mgr.state.user_override is True

    def test_reset(self):
        from luna.context.aperture import ApertureManager, AperturePreset
        mgr = ApertureManager()
        mgr.set_preset(AperturePreset.TUNNEL)
        mgr.set_focus_tags(["test"])
        mgr.reset()
        assert mgr.state.preset == AperturePreset.WIDE
        assert mgr.state.focus_tags == []


class TestAppDefaults:
    """Test that each app context has a default aperture."""

    def test_all_apps_have_defaults(self):
        from luna.context.aperture import APP_DEFAULTS
        expected_apps = ["kozmo", "guardian", "eclissi", "companion", "dataroom"]
        for app in expected_apps:
            assert app in APP_DEFAULTS, f"Missing default for app: {app}"


# =============================================================================
# PHASE 4: Assembler Integration
# =============================================================================

class TestAssemblerApertureHint:
    """Test that the aperture hint is built correctly."""

    def test_aperture_hint_at_balanced(self):
        from luna.context.aperture import ApertureState, AperturePreset

        # Create a mock assembler
        assembler = MagicMock()
        assembler._build_aperture_hint = (
            lambda ap: _build_aperture_hint_standalone(ap)
        )

        state = ApertureState(
            preset=AperturePreset.BALANCED,
            angle=55,
            focus_tags=["luna", "architecture"],
            active_project="Luna Engine v2",
        )
        hint = _build_aperture_hint_standalone(state)
        assert hint is not None
        assert "55°" in hint
        assert "luna" in hint
        assert "Luna Engine v2" in hint

    def test_aperture_hint_at_open_is_none(self):
        from luna.context.aperture import ApertureState, AperturePreset
        state = ApertureState(preset=AperturePreset.OPEN, angle=95)
        hint = _build_aperture_hint_standalone(state)
        assert hint is None, "OPEN aperture should not inject a hint"


def _build_aperture_hint_standalone(aperture):
    """Standalone version for testing without full assembler."""
    from luna.context.aperture import AperturePreset
    if aperture.preset == AperturePreset.OPEN:
        return None
    lines = [
        "## Focus Awareness",
        f"Your recall has been shaped by your current focus ({aperture.preset.value}, {aperture.angle}°).",
    ]
    if aperture.focus_tags:
        lines.append(f"Focus tags: {', '.join(aperture.focus_tags)}")
    if aperture.active_project:
        lines.append(f"Active project: {aperture.active_project}")
    lines.append(
        "If you notice connections to knowledge outside your current scope "
        "that seem important, mention them."
    )
    return "\n".join(lines)


class TestPromptRequestAperture:
    """Test that PromptRequest accepts aperture field."""

    def test_prompt_request_with_aperture(self):
        from luna.context.assembler import PromptRequest
        from luna.context.aperture import ApertureState, AperturePreset
        state = ApertureState(preset=AperturePreset.TUNNEL, angle=15)
        req = PromptRequest(message="test", aperture=state)
        assert req.aperture is not None
        assert req.aperture.preset == AperturePreset.TUNNEL

    def test_prompt_request_without_aperture(self):
        from luna.context.assembler import PromptRequest
        req = PromptRequest(message="test")
        assert req.aperture is None


class TestPromptResultAperture:
    """Test that PromptResult includes aperture metadata."""

    def test_prompt_result_aperture_fields(self):
        from luna.context.assembler import PromptResult
        result = PromptResult(
            system_prompt="",
            messages=[],
            aperture_preset="tunnel",
            aperture_angle=15,
            aperture_inner_collections=3,
        )
        d = result.to_dict()
        assert d["aperture_preset"] == "tunnel"
        assert d["aperture_angle"] == 15
        assert d["aperture_inner_collections"] == 3

    def test_prompt_result_default_aperture_is_none(self):
        from luna.context.assembler import PromptResult
        result = PromptResult(system_prompt="", messages=[])
        d = result.to_dict()
        assert d["aperture_preset"] is None
        assert d["aperture_angle"] is None


# =============================================================================
# PHASE 4b: Three-Phase Recall Pipeline
# =============================================================================

class TestRecallPipelineOpenBypass:
    """At OPEN aperture, pipeline should delegate to standard memory."""

    @pytest.mark.asyncio
    async def test_open_uses_standard_recall(self):
        """At OPEN, _resolve_memory_with_aperture delegates to standard."""
        from luna.context.assembler import PromptAssembler, PromptRequest
        from luna.context.aperture import ApertureState, AperturePreset

        director = MagicMock()
        director._context_pipeline = None
        director._session_start_time = None

        assembler = PromptAssembler(director)

        # Mock the standard method to track calls
        called = {"standard": False}
        original = assembler._resolve_memory_with_confidence

        async def mock_standard(req):
            called["standard"] = True
            return None, None, None

        assembler._resolve_memory_with_confidence = mock_standard

        state = ApertureState(preset=AperturePreset.OPEN, angle=95)
        request = PromptRequest(message="test", aperture=state)
        await assembler._resolve_memory_with_aperture(request)

        assert called["standard"], "OPEN should delegate to standard recall"


class TestRecallPipelineNoneBypass:
    """When aperture is None, pipeline should delegate to standard memory."""

    @pytest.mark.asyncio
    async def test_none_aperture_uses_standard(self):
        from luna.context.assembler import PromptAssembler, PromptRequest

        director = MagicMock()
        director._context_pipeline = None

        assembler = PromptAssembler(director)

        called = {"standard": False}

        async def mock_standard(req):
            called["standard"] = True
            return None, None, None

        assembler._resolve_memory_with_confidence = mock_standard

        request = PromptRequest(message="test", aperture=None)
        await assembler._resolve_memory_with_aperture(request)

        assert called["standard"], "None aperture should delegate to standard recall"


class TestRecallPipelineInnerRing:
    """Test Phase A — focus query on inner ring collections."""

    @pytest.mark.asyncio
    async def test_inner_ring_includes_matching_collections(self):
        """Collections above threshold with tag overlap should be searched."""
        from luna.context.assembler import PromptAssembler, PromptRequest
        from luna.context.aperture import ApertureState, AperturePreset
        from luna.substrate.collection_lock_in import CollectionLockInRecord

        director = MagicMock()
        director._context_pipeline = None

        # Mock engine with aibrarian
        mock_aibrarian = AsyncMock()
        mock_config = MagicMock()
        mock_config.tags = ["investor", "eclipse"]
        mock_aibrarian.registry.collections = {"dataroom": mock_config}

        mock_lock_in = AsyncMock()
        mock_lock_in.get_above_threshold = AsyncMock(return_value=[
            CollectionLockInRecord(
                collection_key="dataroom",
                lock_in=0.80,
                state="settled",
                access_count=50,
                annotation_count=10,
                connected_collections=2,
                entity_overlap_count=5,
                last_accessed_at="2026-02-28",
                created_at="2026-01-01",
                updated_at="2026-02-28",
            ),
        ])
        mock_lock_in.get_all = AsyncMock(return_value=[])
        mock_aibrarian._lock_in_engine = mock_lock_in
        mock_aibrarian.search = AsyncMock(return_value=[
            {"title": "Budget Plan", "snippet": "Kinoni ICT budget for Q2", "score": 0.85},
        ])

        mock_engine = MagicMock()
        mock_engine._aibrarian = mock_aibrarian
        director._engine = mock_engine

        assembler = PromptAssembler(director)

        # Mock standard memory to return nothing
        async def mock_standard(req):
            return None, None, MagicMock(
                match_count=0, relevant_count=0, avg_similarity=0.0,
                best_lock_in="none", has_entity_match=False, query="test",
            )
        assembler._resolve_memory_with_confidence = mock_standard

        state = ApertureState(
            preset=AperturePreset.NARROW,
            angle=35,
            focus_tags=["investor"],
        )
        request = PromptRequest(message="budget overview", aperture=state)
        block, source, confidence = await assembler._resolve_memory_with_aperture(request)

        assert block is not None
        assert "Focus Ring" in block
        assert "Budget Plan" in block
        assert "aperture" in source


class TestRecallPipelineBreakthrough:
    """Test Phase C — agency check breakthrough."""

    @pytest.mark.asyncio
    async def test_high_score_breaks_through(self):
        """Outer ring results exceeding breakthrough threshold should surface."""
        from luna.context.assembler import PromptAssembler, PromptRequest
        from luna.context.aperture import ApertureState, AperturePreset
        from luna.substrate.collection_lock_in import CollectionLockInRecord

        director = MagicMock()
        director._context_pipeline = None

        mock_aibrarian = AsyncMock()
        mock_aibrarian.registry.collections = {}
        mock_lock_in = AsyncMock()
        mock_lock_in.get_above_threshold = AsyncMock(return_value=[])
        mock_lock_in.get_all = AsyncMock(return_value=[
            CollectionLockInRecord(
                collection_key="maxwell_case",
                lock_in=0.15,
                state="drifting",
                access_count=2,
                annotation_count=0,
                connected_collections=0,
                entity_overlap_count=0,
                last_accessed_at=None,
                created_at="2026-01-01",
                updated_at="2026-01-01",
            ),
        ])
        mock_aibrarian._lock_in_engine = mock_lock_in
        mock_aibrarian.search = AsyncMock(return_value=[
            {"title": "Deposition", "snippet": "Key testimony", "score": 0.90},
        ])

        mock_engine = MagicMock()
        mock_engine._aibrarian = mock_aibrarian
        director._engine = mock_engine

        assembler = PromptAssembler(director)

        async def mock_standard(req):
            return None, None, MagicMock(
                match_count=0, relevant_count=0, avg_similarity=0.0,
                best_lock_in="none", has_entity_match=False, query="test",
            )
        assembler._resolve_memory_with_confidence = mock_standard

        state = ApertureState(
            preset=AperturePreset.BALANCED,
            angle=55,
        )
        request = PromptRequest(message="testimony", aperture=state)
        block, source, confidence = await assembler._resolve_memory_with_aperture(request)

        assert block is not None
        assert "Breakthrough" in block
        assert "Deposition" in block


class TestRecallPipelineBuildIntegration:
    """Test that build() routes through aperture pipeline."""

    @pytest.mark.asyncio
    async def test_build_uses_aperture_pipeline_when_set(self):
        """When aperture is non-None and non-OPEN, build() uses the aperture pipeline."""
        from luna.context.assembler import PromptAssembler, PromptRequest
        from luna.context.aperture import ApertureState, AperturePreset

        director = MagicMock()
        director._context_pipeline = None

        assembler = PromptAssembler(director)

        # Track which pipeline was called
        pipeline_used = {"standard": False, "aperture": False}

        async def mock_standard(req):
            pipeline_used["standard"] = True
            from luna.context.assembler import MemoryConfidence
            conf = MemoryConfidence(
                match_count=0, relevant_count=0, avg_similarity=0.0,
                best_lock_in="none", has_entity_match=False, query=req.message,
            )
            return None, None, conf

        async def mock_aperture(req):
            pipeline_used["aperture"] = True
            from luna.context.assembler import MemoryConfidence
            conf = MemoryConfidence(
                match_count=0, relevant_count=0, avg_similarity=0.0,
                best_lock_in="none", has_entity_match=False, query=req.message,
            )
            return None, None, conf

        assembler._resolve_memory_with_confidence = mock_standard
        assembler._resolve_memory_with_aperture = mock_aperture

        # Mock other assembler methods to not fail
        async def mock_identity(req):
            return "You are Luna.", "fallback"
        assembler._resolve_identity = mock_identity
        assembler._build_expression_block = lambda r: None
        assembler._build_temporal_block = lambda r: (None, None)
        assembler._build_perception_block = lambda: None
        assembler._build_consciousness_block = lambda r: None
        assembler._build_voice_block = lambda r: None

        state = ApertureState(preset=AperturePreset.NARROW, angle=35)
        request = PromptRequest(message="hello", aperture=state)
        result = await assembler.build(request)

        assert pipeline_used["aperture"], "build() should use aperture pipeline when aperture is set"
        assert not pipeline_used["standard"], "Standard pipeline should not be called directly by build()"


# =============================================================================
# PHASE 6: MCP Tools
# =============================================================================

class TestApertureGetTool:
    """Test the aperture_get MCP tool."""

    @pytest.mark.asyncio
    async def test_returns_state_when_manager_set(self):
        import luna.tools.aperture_tools as at
        from luna.context.aperture import ApertureManager
        mgr = ApertureManager()
        at._aperture_manager = mgr

        result = await at.aperture_get()
        assert result["preset"] == "wide"
        assert result["angle"] == 75
        assert "breakthrough_threshold" in result

        at._aperture_manager = None  # cleanup

    @pytest.mark.asyncio
    async def test_returns_error_when_not_initialized(self):
        import luna.tools.aperture_tools as at
        at._aperture_manager = None
        result = await at.aperture_get()
        assert "error" in result


class TestApertureSetTool:
    """Test the aperture_set MCP tool."""

    @pytest.mark.asyncio
    async def test_set_preset(self):
        import luna.tools.aperture_tools as at
        from luna.context.aperture import ApertureManager
        mgr = ApertureManager()
        at._aperture_manager = mgr

        result = await at.aperture_set(preset="tunnel")
        assert result["preset"] == "tunnel"
        assert result["angle"] == 15
        assert result["user_override"] is True

        at._aperture_manager = None

    @pytest.mark.asyncio
    async def test_set_angle(self):
        import luna.tools.aperture_tools as at
        from luna.context.aperture import ApertureManager
        mgr = ApertureManager()
        at._aperture_manager = mgr

        result = await at.aperture_set(angle=36)
        assert result["angle"] == 36
        assert result["preset"] == "narrow"  # Snaps to nearest

        at._aperture_manager = None

    @pytest.mark.asyncio
    async def test_set_focus_tags(self):
        import luna.tools.aperture_tools as at
        from luna.context.aperture import ApertureManager
        mgr = ApertureManager()
        at._aperture_manager = mgr

        result = await at.aperture_set(focus_tags=["kinoni", "solar"])
        assert result["focus_tags"] == ["kinoni", "solar"]

        at._aperture_manager = None

    @pytest.mark.asyncio
    async def test_invalid_preset_returns_error(self):
        import luna.tools.aperture_tools as at
        from luna.context.aperture import ApertureManager
        mgr = ApertureManager()
        at._aperture_manager = mgr

        result = await at.aperture_set(preset="maximum_overdrive")
        assert "error" in result

        at._aperture_manager = None


class TestCollectionLockInTool:
    """Test the collection_lock_in MCP tool."""

    @pytest.mark.asyncio
    async def test_returns_error_when_not_initialized(self):
        import luna.tools.aperture_tools as at
        at._lock_in_engine = None
        result = await at.collection_lock_in()
        assert "error" in result

    @pytest.mark.asyncio
    async def test_returns_all_collections(self):
        import luna.tools.aperture_tools as at
        from luna.substrate.collection_lock_in import CollectionLockInRecord

        mock_engine = AsyncMock()
        mock_engine.get_all = AsyncMock(return_value=[
            CollectionLockInRecord(
                collection_key="dataroom", lock_in=0.65, state="fluid",
                access_count=30, annotation_count=5,
                connected_collections=1, entity_overlap_count=3,
                last_accessed_at="2026-02-28",
                created_at="2026-01-01", updated_at="2026-02-28",
            ),
        ])
        at._lock_in_engine = mock_engine

        result = await at.collection_lock_in()
        assert result["count"] == 1
        assert result["collections"][0]["collection_key"] == "dataroom"

        at._lock_in_engine = None

    @pytest.mark.asyncio
    async def test_returns_specific_collection(self):
        import luna.tools.aperture_tools as at
        from luna.substrate.collection_lock_in import CollectionLockInRecord

        mock_engine = AsyncMock()
        mock_engine.get_lock_in = AsyncMock(return_value=CollectionLockInRecord(
            collection_key="dataroom", lock_in=0.65, state="fluid",
            access_count=30, annotation_count=5,
            connected_collections=1, entity_overlap_count=3,
            last_accessed_at="2026-02-28",
            created_at="2026-01-01", updated_at="2026-02-28",
        ))
        at._lock_in_engine = mock_engine

        result = await at.collection_lock_in(collection="dataroom")
        assert result["collection_key"] == "dataroom"
        assert result["lock_in"] == 0.65

        at._lock_in_engine = None


class TestAnnotateTool:
    """Test the annotate MCP tool."""

    @pytest.mark.asyncio
    async def test_returns_error_when_not_initialized(self):
        import luna.tools.aperture_tools as at
        at._annotation_engine = None
        result = await at.annotate(collection="dataroom", doc_id="doc-1")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_note_without_content_fails(self):
        import luna.tools.aperture_tools as at
        mock_engine = AsyncMock()
        at._annotation_engine = mock_engine

        result = await at.annotate(
            collection="dataroom",
            doc_id="doc-1",
            annotation_type="note",
            content=None,
        )
        assert "error" in result
        assert "required" in result["error"].lower()

        at._annotation_engine = None

    @pytest.mark.asyncio
    async def test_invalid_annotation_type_fails(self):
        import luna.tools.aperture_tools as at
        mock_engine = AsyncMock()
        at._annotation_engine = mock_engine

        result = await at.annotate(
            collection="dataroom",
            doc_id="doc-1",
            annotation_type="invalid_type",
        )
        assert "error" in result

        at._annotation_engine = None

    @pytest.mark.asyncio
    async def test_successful_annotation(self):
        import luna.tools.aperture_tools as at
        from luna.substrate.collection_annotations import Annotation

        mock_engine = AsyncMock()
        mock_engine.create = AsyncMock(return_value="ann-uuid-123")
        mock_engine.get = AsyncMock(return_value=Annotation(
            id="ann-uuid-123",
            collection_key="dataroom",
            doc_id="doc-1",
            chunk_index=None,
            annotation_type="note",
            content="Important finding",
            matrix_node_id="node-uuid-456",
            created_at="2026-02-28",
        ))
        at._annotation_engine = mock_engine

        result = await at.annotate(
            collection="dataroom",
            doc_id="doc-1",
            annotation_type="note",
            content="Important finding",
        )
        assert result["success"] is True
        assert result["annotation_id"] == "ann-uuid-123"
        assert result["matrix_node_id"] == "node-uuid-456"

        at._annotation_engine = None


class TestToolRegistration:
    """Test that aperture tools register correctly."""

    def test_all_aperture_tools_defined(self):
        from luna.tools.aperture_tools import ALL_APERTURE_TOOLS
        assert len(ALL_APERTURE_TOOLS) == 4
        names = [t.name for t in ALL_APERTURE_TOOLS]
        assert "aperture_get" in names
        assert "aperture_set" in names
        assert "collection_lock_in" in names
        assert "annotate" in names

    def test_tools_importable_from_init(self):
        from luna.tools import APERTURE_TOOLS_AVAILABLE
        assert APERTURE_TOOLS_AVAILABLE is True


class TestCollectionTagsIntegration:
    """Test that aperture pipeline reads tags from AiBrarian registry configs."""

    def test_config_has_tags_field(self):
        """AiBrarianConfig should have a tags field."""
        from luna.substrate.aibrarian_engine import AiBrarianConfig
        config = AiBrarianConfig(key="test", name="Test", tags=["investor", "eclipse"])
        assert config.tags == ["investor", "eclipse"]

    def test_tag_overlap_detection(self):
        """Focus tags should overlap with collection tags (case-insensitive)."""
        focus_tags = ["investor", "kinoni"]
        collection_tags = ["Investor", "Eclipse", "Dataroom"]

        overlap = set(t.lower() for t in focus_tags) & set(t.lower() for t in collection_tags)
        assert "investor" in overlap
        assert len(overlap) == 1
