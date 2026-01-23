"""
Unit tests for Luna Engine Tuning System.

Tests:
- ParamRegistry get/set/reset
- Evaluator test execution
- Session management and persistence
"""

import pytest
import asyncio
import tempfile
import os
from unittest.mock import AsyncMock, MagicMock, patch

from luna.tuning.params import ParamRegistry, TUNABLE_PARAMS, ParamSpec
from luna.tuning.evaluator import Evaluator, EvalResults, TestCase, TestResult
from luna.tuning.session import TuningSessionManager, TuningSession, TuningIteration


class TestParamRegistry:
    """Tests for ParamRegistry."""

    def test_list_params(self):
        """Test listing all parameters."""
        registry = ParamRegistry()
        params = registry.list_params()

        assert len(params) > 20  # Should have many params
        assert "inference.temperature" in params
        assert "memory.lock_in.access_weight" in params

    def test_list_categories(self):
        """Test listing categories."""
        registry = ParamRegistry()
        categories = registry.list_categories()

        assert "inference" in categories
        assert "memory" in categories
        assert "router" in categories
        assert "history" in categories

    def test_list_params_by_category(self):
        """Test filtering params by category."""
        registry = ParamRegistry()
        memory_params = registry.list_params(category="memory")

        assert all("memory" in p for p in memory_params)
        assert "memory.lock_in.access_weight" in memory_params

    def test_get_default(self):
        """Test getting default values."""
        registry = ParamRegistry()

        temp = registry.get("inference.temperature")
        assert temp == 0.7

        access_weight = registry.get("memory.lock_in.access_weight")
        assert access_weight == 0.3

    def test_get_unknown_param(self):
        """Test getting unknown parameter raises error."""
        registry = ParamRegistry()

        with pytest.raises(KeyError):
            registry.get("unknown.param")

    def test_set_param(self):
        """Test setting parameter value."""
        registry = ParamRegistry()

        prev = registry.set("inference.temperature", 0.9)
        assert prev == 0.7  # Previous value
        assert registry.get("inference.temperature") == 0.9

    def test_set_validates_bounds(self):
        """Test that set validates bounds."""
        registry = ParamRegistry()

        # Temperature bounds are (0.0, 2.0)
        with pytest.raises(ValueError):
            registry.set("inference.temperature", 3.0)

        with pytest.raises(ValueError):
            registry.set("inference.temperature", -1.0)

    def test_set_skip_validation(self):
        """Test bypassing validation."""
        registry = ParamRegistry()

        # Should not raise with validate=False
        registry.set("inference.temperature", 5.0, validate=False)
        assert registry.get("inference.temperature") == 5.0

    def test_reset_param(self):
        """Test resetting parameter to default."""
        registry = ParamRegistry()

        registry.set("inference.temperature", 0.9)
        assert registry.get("inference.temperature") == 0.9

        prev = registry.reset("inference.temperature")
        assert prev == 0.9
        assert registry.get("inference.temperature") == 0.7

    def test_reset_all(self):
        """Test resetting all parameters."""
        registry = ParamRegistry()

        registry.set("inference.temperature", 0.9)
        registry.set("inference.top_p", 0.5)

        count = registry.reset_all()
        assert count == 2

        assert registry.get("inference.temperature") == 0.7
        assert registry.get("inference.top_p") == 0.9

    def test_get_all(self):
        """Test getting all parameter values."""
        registry = ParamRegistry()
        all_params = registry.get_all()

        assert isinstance(all_params, dict)
        assert len(all_params) == len(TUNABLE_PARAMS)
        assert all_params["inference.temperature"] == 0.7

    def test_get_overrides(self):
        """Test getting only overridden parameters."""
        registry = ParamRegistry()

        assert registry.get_overrides() == {}

        registry.set("inference.temperature", 0.9)
        overrides = registry.get_overrides()

        assert len(overrides) == 1
        assert overrides["inference.temperature"] == 0.9

    def test_export(self):
        """Test exporting parameters with metadata."""
        registry = ParamRegistry()
        registry.set("inference.temperature", 0.9)

        export = registry.export()

        assert "inference.temperature" in export
        temp_export = export["inference.temperature"]
        assert temp_export["value"] == 0.9
        assert temp_export["default"] == 0.7
        assert temp_export["is_overridden"] is True

    def test_import_params(self):
        """Test importing parameters from dict."""
        registry = ParamRegistry()

        params = {
            "inference.temperature": 0.8,
            "inference.top_p": 0.85,
            "unknown.param": 123,  # Should be skipped
        }

        count = registry.import_params(params)
        assert count == 2

        assert registry.get("inference.temperature") == 0.8
        assert registry.get("inference.top_p") == 0.85

    def test_get_spec(self):
        """Test getting parameter specification."""
        registry = ParamRegistry()
        spec = registry.get_spec("inference.temperature")

        assert isinstance(spec, ParamSpec)
        assert spec.name == "inference.temperature"
        assert spec.default == 0.7
        assert spec.bounds == (0.0, 2.0)
        assert spec.category == "inference"


class TestEvaluator:
    """Tests for Evaluator."""

    def test_init_default_suite(self):
        """Test initializer with default test suite."""
        evaluator = Evaluator()

        assert len(evaluator._tests) > 0
        assert any(t.type == "memory_recall" for t in evaluator._tests)
        assert any(t.type == "routing" for t in evaluator._tests)

    def test_list_tests(self):
        """Test listing test names."""
        evaluator = Evaluator()
        tests = evaluator.list_tests()

        assert isinstance(tests, list)
        assert "recall_marzipan" in tests

    def test_add_test(self):
        """Test adding custom test."""
        evaluator = Evaluator()
        initial_count = len(evaluator._tests)

        evaluator.add_test({
            "type": "memory_recall",
            "name": "custom_test",
            "query": "Test query?",
            "expected": ["test"],
        })

        assert len(evaluator._tests) == initial_count + 1
        assert "custom_test" in evaluator.list_tests()

    def test_remove_test(self):
        """Test removing test."""
        evaluator = Evaluator()
        initial_count = len(evaluator._tests)

        result = evaluator.remove_test("recall_marzipan")
        assert result is True
        assert len(evaluator._tests) == initial_count - 1
        assert "recall_marzipan" not in evaluator.list_tests()

    @pytest.mark.asyncio
    async def test_run_all_mock(self):
        """Test running all tests with mock engine."""
        evaluator = Evaluator()  # No engine = mock mode
        results = await evaluator.run_all()

        assert isinstance(results, EvalResults)
        assert results.total_tests > 0
        assert 0 <= results.overall_score <= 1

    @pytest.mark.asyncio
    async def test_run_category(self):
        """Test running tests by category."""
        evaluator = Evaluator()
        results = await evaluator.run_category("routing")

        assert results.total_tests > 0
        # Only routing tests should be included
        assert all(r.test.type == "routing" for r in results.results)

    def test_eval_results_to_dict(self):
        """Test EvalResults serialization."""
        results = EvalResults(
            total_tests=10,
            passed_tests=8,
            memory_recall_score=0.75,
            overall_score=0.8,
        )

        d = results.to_dict()
        assert d["total_tests"] == 10
        assert d["passed_tests"] == 8
        assert d["overall_score"] == 0.8


class TestTuningSession:
    """Tests for TuningSession and TuningSessionManager."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        os.unlink(path)

    @pytest.mark.asyncio
    async def test_initialize(self, temp_db):
        """Test session manager initialization."""
        manager = TuningSessionManager(db_path=temp_db)
        await manager.initialize()

        assert manager._initialized is True

    @pytest.mark.asyncio
    async def test_new_session(self, temp_db):
        """Test creating new session."""
        manager = TuningSessionManager(db_path=temp_db)
        await manager.initialize()

        session = await manager.new_session(
            focus="memory",
            base_params={"test": 1},
            notes="Test session",
        )

        assert session.session_id is not None
        assert session.focus == "memory"
        assert session.base_params == {"test": 1}
        assert manager.current_session == session

    @pytest.mark.asyncio
    async def test_add_iteration(self, temp_db):
        """Test adding iteration to session."""
        manager = TuningSessionManager(db_path=temp_db)
        await manager.initialize()

        await manager.new_session(focus="memory")

        eval_results = EvalResults(
            total_tests=5,
            passed_tests=4,
            overall_score=0.8,
        )

        iteration = await manager.add_iteration(
            params_changed={"test": 2},
            param_snapshot={"test": 2},
            eval_results=eval_results,
            notes="Test iteration",
        )

        assert iteration.iteration_num == 1
        assert iteration.score == 0.8
        assert manager.current_session.best_iteration == 1
        assert manager.current_session.best_score == 0.8

    @pytest.mark.asyncio
    async def test_multiple_iterations_track_best(self, temp_db):
        """Test that multiple iterations track best score."""
        manager = TuningSessionManager(db_path=temp_db)
        await manager.initialize()

        await manager.new_session(focus="all")

        # First iteration: score 0.5
        await manager.add_iteration(
            params_changed={},
            param_snapshot={},
            eval_results=EvalResults(overall_score=0.5),
        )

        # Second iteration: score 0.8 (better)
        await manager.add_iteration(
            params_changed={"x": 1},
            param_snapshot={"x": 1},
            eval_results=EvalResults(overall_score=0.8),
        )

        # Third iteration: score 0.6 (worse)
        await manager.add_iteration(
            params_changed={"x": 2},
            param_snapshot={"x": 2},
            eval_results=EvalResults(overall_score=0.6),
        )

        assert manager.current_session.best_iteration == 2
        assert manager.current_session.best_score == 0.8

    @pytest.mark.asyncio
    async def test_end_session(self, temp_db):
        """Test ending session."""
        manager = TuningSessionManager(db_path=temp_db)
        await manager.initialize()

        await manager.new_session(focus="memory")
        session = await manager.end_session()

        assert session.ended_at is not None
        assert manager.current_session is None

    @pytest.mark.asyncio
    async def test_get_session(self, temp_db):
        """Test loading session by ID."""
        manager = TuningSessionManager(db_path=temp_db)
        await manager.initialize()

        session = await manager.new_session(focus="memory")
        session_id = session.session_id

        await manager.add_iteration(
            params_changed={},
            param_snapshot={"a": 1},
            eval_results=EvalResults(overall_score=0.75),
        )

        await manager.end_session()

        # Load it back
        loaded = await manager.get_session(session_id)

        assert loaded is not None
        assert loaded.session_id == session_id
        assert loaded.focus == "memory"
        assert len(loaded.iterations) == 1
        assert loaded.iterations[0].score == 0.75

    @pytest.mark.asyncio
    async def test_list_sessions(self, temp_db):
        """Test listing sessions."""
        manager = TuningSessionManager(db_path=temp_db)
        await manager.initialize()

        await manager.new_session(focus="memory")
        await manager.end_session()

        await manager.new_session(focus="routing")
        await manager.end_session()

        sessions = await manager.list_sessions()

        assert len(sessions) == 2
        # Most recent first
        assert sessions[0]["focus"] == "routing"

    @pytest.mark.asyncio
    async def test_compare_iterations(self, temp_db):
        """Test comparing iterations."""
        manager = TuningSessionManager(db_path=temp_db)
        await manager.initialize()

        await manager.new_session(focus="all")

        await manager.add_iteration(
            params_changed={},
            param_snapshot={"temp": 0.7},
            eval_results=EvalResults(
                overall_score=0.5,
                memory_recall_score=0.4,
            ),
        )

        await manager.add_iteration(
            params_changed={"temp": 0.9},
            param_snapshot={"temp": 0.9},
            eval_results=EvalResults(
                overall_score=0.7,
                memory_recall_score=0.6,
            ),
        )

        comparison = manager.compare_iterations(1, 2)

        assert comparison["score_diff"] == pytest.approx(0.2)
        assert comparison["param_diffs"]["temp"]["from"] == 0.7
        assert comparison["param_diffs"]["temp"]["to"] == 0.9

    @pytest.mark.asyncio
    async def test_get_best_params(self, temp_db):
        """Test getting best params."""
        manager = TuningSessionManager(db_path=temp_db)
        await manager.initialize()

        await manager.new_session(
            focus="all",
            base_params={"x": 1},
        )

        await manager.add_iteration(
            params_changed={},
            param_snapshot={"x": 1},
            eval_results=EvalResults(overall_score=0.5),
        )

        await manager.add_iteration(
            params_changed={"x": 2},
            param_snapshot={"x": 2},
            eval_results=EvalResults(overall_score=0.9),
        )

        best = manager.get_best_params()
        assert best == {"x": 2}


class TestTuningIteration:
    """Tests for TuningIteration dataclass."""

    def test_to_dict(self):
        """Test serialization."""
        iteration = TuningIteration(
            iteration_num=1,
            params_changed={"a": 1},
            param_snapshot={"a": 1, "b": 2},
            eval_results={"score": 0.8},
            score=0.8,
            notes="Test",
        )

        d = iteration.to_dict()
        assert d["iteration_num"] == 1
        assert d["params_changed"] == {"a": 1}
        assert d["score"] == 0.8

    def test_from_dict(self):
        """Test deserialization."""
        d = {
            "iteration_num": 1,
            "params_changed": {"a": 1},
            "param_snapshot": {"a": 1},
            "eval_results": {"score": 0.8},
            "score": 0.8,
            "notes": "",
            "created_at": "2026-01-20T00:00:00",
        }

        iteration = TuningIteration.from_dict(d)
        assert iteration.iteration_num == 1
        assert iteration.score == 0.8


class TestTuningSessionDataclass:
    """Tests for TuningSession dataclass."""

    def test_to_dict(self):
        """Test serialization."""
        session = TuningSession(
            session_id="test-123",
            focus="memory",
            started_at="2026-01-20T00:00:00",
            base_params={"x": 1},
        )

        d = session.to_dict()
        assert d["session_id"] == "test-123"
        assert d["focus"] == "memory"
        assert d["iterations"] == []

    def test_from_dict(self):
        """Test deserialization."""
        d = {
            "session_id": "test-123",
            "focus": "memory",
            "started_at": "2026-01-20T00:00:00",
            "ended_at": None,
            "notes": "",
            "iterations": [],
            "best_iteration": 0,
            "best_score": 0.0,
            "base_params": {},
        }

        session = TuningSession.from_dict(d)
        assert session.session_id == "test-123"
        assert session.focus == "memory"
