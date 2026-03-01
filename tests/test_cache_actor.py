"""
Tests for CacheActor
====================

Tests the shared turn cache actor: YAML write, emotional tone derivation,
dimensional engine feed, and message handling.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from pathlib import Path
from tempfile import TemporaryDirectory
import yaml

from luna.actors.base import Message
from luna.actors.cache import (
    CacheActor,
    TONE_MAP,
    TYPE_TO_CATEGORY,
    TONE_TO_SENTIMENT,
)
from luna.extraction.types import (
    ExtractionOutput,
    ExtractedObject,
    ExtractionType,
    FlowSignal,
    ConversationMode,
)


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_cache_dir():
    with TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def cache_actor(tmp_cache_dir):
    actor = CacheActor()
    actor._cache_path = tmp_cache_dir / "shared_turn.yaml"
    return actor


@pytest.fixture
def sample_extraction():
    return ExtractionOutput(
        objects=[
            ExtractedObject(
                type=ExtractionType.FACT,
                content="Berlin is the capital of Germany",
                confidence=0.9,
                entities=["Berlin", "Germany"],
            ),
            ExtractedObject(
                type=ExtractionType.DECISION,
                content="Use SQLite for the prototype",
                confidence=0.85,
                entities=["SQLite"],
            ),
        ],
        edges=[],
    )


@pytest.fixture
def sample_flow_signal():
    return FlowSignal(
        mode=ConversationMode.FLOW,
        current_topic="databases",
        continuity_score=0.8,
        open_threads=["SQLite migration"],
    )


# ── Tone derivation tests ──────────────────────────────────────────────────

class TestDeriveEmotionalTone:
    def test_amend_mode_returns_correcting(self, cache_actor, sample_extraction):
        fs = FlowSignal(mode=ConversationMode.AMEND, current_topic="fix")
        assert cache_actor._derive_emotional_tone(sample_extraction, fs) == "correcting"

    def test_recalibration_returns_shifting(self, cache_actor, sample_extraction):
        fs = FlowSignal(mode=ConversationMode.RECALIBRATION, current_topic="new topic")
        assert cache_actor._derive_emotional_tone(sample_extraction, fs) == "shifting"

    def test_problem_returns_concerned(self, cache_actor):
        ext = ExtractionOutput(objects=[
            ExtractedObject(type=ExtractionType.PROBLEM, content="Bug found", confidence=0.9),
        ])
        fs = FlowSignal(mode=ConversationMode.FLOW, current_topic="bugs")
        assert cache_actor._derive_emotional_tone(ext, fs) == "concerned"

    def test_decision_returns_resolute(self, cache_actor):
        ext = ExtractionOutput(objects=[
            ExtractedObject(type=ExtractionType.DECISION, content="Go with Postgres", confidence=0.9),
        ])
        fs = FlowSignal(mode=ConversationMode.FLOW, current_topic="db")
        assert cache_actor._derive_emotional_tone(ext, fs) == "resolute"

    def test_action_returns_focused(self, cache_actor):
        ext = ExtractionOutput(objects=[
            ExtractedObject(type=ExtractionType.ACTION, content="Deploy to prod", confidence=0.9),
        ])
        fs = FlowSignal(mode=ConversationMode.FLOW, current_topic="deploy")
        assert cache_actor._derive_emotional_tone(ext, fs) == "focused"

    def test_high_continuity_returns_engaged(self, cache_actor):
        ext = ExtractionOutput(objects=[])
        fs = FlowSignal(mode=ConversationMode.FLOW, current_topic="chat", continuity_score=0.9)
        assert cache_actor._derive_emotional_tone(ext, fs) == "engaged"

    def test_default_returns_neutral(self, cache_actor):
        ext = ExtractionOutput(objects=[])
        fs = FlowSignal(mode=ConversationMode.FLOW, current_topic="chat", continuity_score=0.3)
        assert cache_actor._derive_emotional_tone(ext, fs) == "neutral"


# ── Cache file write tests ──────────────────────────────────────────────────

class TestCacheFileWrite:
    def test_write_creates_yaml_file(self, cache_actor, sample_extraction, sample_flow_signal):
        cache_data = cache_actor._build_cache_data(
            sample_extraction, sample_flow_signal, "resolute", "test", "session1",
        )
        cache_actor._write_cache_file(cache_data)
        assert cache_actor._cache_path.exists()
        assert cache_actor._writes_count == 1

    def test_written_yaml_is_parseable(self, cache_actor, sample_extraction, sample_flow_signal):
        cache_data = cache_actor._build_cache_data(
            sample_extraction, sample_flow_signal, "resolute", "test", "session1",
        )
        cache_actor._write_cache_file(cache_data)
        with open(cache_actor._cache_path) as f:
            loaded = yaml.safe_load(f)
        assert loaded["schema_version"] == 1
        assert loaded["source"] == "test"
        assert loaded["session_id"] == "session1"

    def test_cache_data_has_correct_structure(self, cache_actor, sample_extraction, sample_flow_signal):
        cache_data = cache_actor._build_cache_data(
            sample_extraction, sample_flow_signal, "resolute", "test", "s1",
        )
        assert "scribed" in cache_data
        assert "flow" in cache_data
        assert "expression" in cache_data
        assert cache_data["expression"]["emotional_tone"] == "resolute"
        assert cache_data["expression"]["expression_hint"] == "confident_warm"

    def test_categorization_maps_types(self, cache_actor, sample_extraction, sample_flow_signal):
        cache_data = cache_actor._build_cache_data(
            sample_extraction, sample_flow_signal, "resolute", "test", "s1",
        )
        assert len(cache_data["scribed"]["facts"]) == 1
        assert len(cache_data["scribed"]["decisions"]) == 1

    def test_raw_summary_uses_best_extraction(self, cache_actor, sample_extraction, sample_flow_signal):
        cache_data = cache_actor._build_cache_data(
            sample_extraction, sample_flow_signal, "resolute", "test", "s1",
        )
        # Best confidence is Berlin fact at 0.9
        assert "Berlin" in cache_data["raw_summary"]

    def test_empty_extraction_uses_topic(self, cache_actor, sample_flow_signal):
        ext = ExtractionOutput(objects=[])
        cache_data = cache_actor._build_cache_data(ext, sample_flow_signal, "neutral", "test", "s1")
        assert "databases" in cache_data["raw_summary"]

    def test_stores_last_cache_data(self, cache_actor, sample_extraction, sample_flow_signal):
        cache_data = cache_actor._build_cache_data(
            sample_extraction, sample_flow_signal, "engaged", "test", "s1",
        )
        cache_actor._write_cache_file(cache_data)
        assert cache_actor._last_cache_data is not None
        assert cache_actor._last_cache_data["source"] == "test"


# ── Dimensional feed tests ──────────────────────────────────────────────────

class TestDimensionalFeed:
    def test_feed_calls_update_dimensions(self, cache_actor, sample_extraction, sample_flow_signal):
        mock_osm = MagicMock()
        cache_actor._orb_state_manager = mock_osm
        cache_actor._feed_dimensional_engine("engaged", sample_flow_signal, sample_extraction)
        mock_osm.update_dimensions.assert_called_once()
        assert cache_actor._dimensional_feeds == 1

    def test_feed_skips_without_osm(self, cache_actor, sample_extraction, sample_flow_signal):
        cache_actor._feed_dimensional_engine("neutral", sample_flow_signal, sample_extraction)
        assert cache_actor._dimensional_feeds == 0

    def test_sentiment_mapping_engaged(self, cache_actor, sample_extraction, sample_flow_signal):
        mock_osm = MagicMock()
        cache_actor._orb_state_manager = mock_osm
        cache_actor._feed_dimensional_engine("engaged", sample_flow_signal, sample_extraction)
        call_args = mock_osm.update_dimensions.call_args[0][0]
        assert call_args["sentiment"] == 0.6

    def test_sentiment_mapping_excited(self, cache_actor, sample_extraction, sample_flow_signal):
        mock_osm = MagicMock()
        cache_actor._orb_state_manager = mock_osm
        cache_actor._feed_dimensional_engine("excited", sample_flow_signal, sample_extraction)
        call_args = mock_osm.update_dimensions.call_args[0][0]
        assert call_args["sentiment"] == 0.85

    def test_sentiment_mapping_concerned(self, cache_actor, sample_extraction, sample_flow_signal):
        mock_osm = MagicMock()
        cache_actor._orb_state_manager = mock_osm
        cache_actor._feed_dimensional_engine("concerned", sample_flow_signal, sample_extraction)
        call_args = mock_osm.update_dimensions.call_args[0][0]
        assert call_args["sentiment"] == -0.3

    def test_topic_personal_high_extractions(self, cache_actor, sample_flow_signal):
        ext = ExtractionOutput(objects=[
            ExtractedObject(type=ExtractionType.FACT, content=f"fact {i}", confidence=0.9)
            for i in range(5)
        ])
        mock_osm = MagicMock()
        cache_actor._orb_state_manager = mock_osm
        cache_actor._feed_dimensional_engine("focused", sample_flow_signal, ext)
        call_args = mock_osm.update_dimensions.call_args[0][0]
        assert call_args["topic_personal"] == 0.7

    def test_topic_personal_low_extractions(self, cache_actor, sample_flow_signal):
        ext = ExtractionOutput(objects=[
            ExtractedObject(type=ExtractionType.FACT, content="single fact", confidence=0.9),
        ])
        mock_osm = MagicMock()
        cache_actor._orb_state_manager = mock_osm
        cache_actor._feed_dimensional_engine("neutral", sample_flow_signal, ext)
        call_args = mock_osm.update_dimensions.call_args[0][0]
        assert call_args["topic_personal"] == 0.55

    def test_flow_includes_continuity_boost(self, cache_actor, sample_extraction, sample_flow_signal):
        mock_osm = MagicMock()
        cache_actor._orb_state_manager = mock_osm
        cache_actor._feed_dimensional_engine("engaged", sample_flow_signal, sample_extraction)
        call_args = mock_osm.update_dimensions.call_args[0][0]
        # flow = min(1.0, turn * 0.15 + continuity * 0.3)
        # turn = 0 (no engine), continuity = 0.8 → flow = 0.24
        assert call_args["flow"] == pytest.approx(0.24, abs=0.01)

    def test_triggers_dict_has_all_keys(self, cache_actor, sample_extraction, sample_flow_signal):
        mock_osm = MagicMock()
        cache_actor._orb_state_manager = mock_osm
        cache_actor._feed_dimensional_engine("neutral", sample_flow_signal, sample_extraction)
        call_args = mock_osm.update_dimensions.call_args[0][0]
        expected_keys = {"sentiment", "memory_hit", "identity", "topic_personal", "flow", "time_mod"}
        assert set(call_args.keys()) == expected_keys


# ── Message handling tests ──────────────────────────────────────────────────

class TestCacheActorMessages:
    @pytest.mark.asyncio
    async def test_handle_cache_update(self, cache_actor, sample_extraction, sample_flow_signal):
        cache_actor.engine = MagicMock()
        cache_actor.engine.input_buffer = MagicMock()
        cache_actor.engine.input_buffer.put = AsyncMock()
        cache_actor.engine.get_actor = MagicMock(return_value=None)
        cache_actor.engine.context = MagicMock(current_turn=5)

        msg = Message(
            type="cache_update",
            payload={
                "extraction": sample_extraction.to_dict(),
                "flow_signal": sample_flow_signal.to_dict(),
                "source": "test",
                "session_id": "s1",
            },
        )
        await cache_actor.handle(msg)
        assert cache_actor._writes_count == 1
        assert cache_actor._cache_path.exists()

    @pytest.mark.asyncio
    async def test_handle_read_cache(self, cache_actor):
        cache_actor._last_cache_data = {"schema_version": 1}
        cache_actor.engine = MagicMock()
        cache_actor.engine.input_buffer = MagicMock()
        cache_actor.engine.input_buffer.put = AsyncMock()

        msg = Message(type="read_cache")
        await cache_actor.handle(msg)
        cache_actor.engine.input_buffer.put.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_get_stats(self, cache_actor):
        cache_actor._writes_count = 10
        cache_actor._dimensional_feeds = 8
        cache_actor._errors = 1
        cache_actor.engine = MagicMock()
        cache_actor.engine.input_buffer = MagicMock()
        cache_actor.engine.input_buffer.put = AsyncMock()

        msg = Message(type="get_stats")
        await cache_actor.handle(msg)
        cache_actor.engine.input_buffer.put.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_update_without_flow_signal_skips(self, cache_actor):
        msg = Message(type="cache_update", payload={"extraction": {}})
        await cache_actor.handle(msg)
        assert cache_actor._writes_count == 0

    @pytest.mark.asyncio
    async def test_unknown_message_type_doesnt_crash(self, cache_actor):
        msg = Message(type="unknown_type")
        await cache_actor.handle(msg)  # Should not raise


# ── Snapshot tests ──────────────────────────────────────────────────────────

class TestCacheActorSnapshot:
    @pytest.mark.asyncio
    async def test_snapshot_includes_stats(self, cache_actor):
        cache_actor._writes_count = 5
        cache_actor._dimensional_feeds = 3
        cache_actor._errors = 1
        snap = await cache_actor.snapshot()
        assert snap["writes"] == 5
        assert snap["dimensional_feeds"] == 3
        assert snap["errors"] == 1
        assert snap["name"] == "cache"


# ── Compatibility with read_shared_turn ─────────────────────────────────────

class TestReadSharedTurnCompatibility:
    def test_written_cache_readable_by_reader(self, cache_actor, sample_extraction, sample_flow_signal):
        from luna.cache.shared_turn import read_shared_turn

        cache_data = cache_actor._build_cache_data(
            sample_extraction, sample_flow_signal, "engaged", "test", "s1",
        )
        cache_actor._write_cache_file(cache_data)

        snapshot = read_shared_turn(path=cache_actor._cache_path)
        assert snapshot is not None
        assert snapshot.emotional_tone == "engaged"
        assert snapshot.expression_hint == "curious_warm"
        assert snapshot.topic == "databases"
        assert len(snapshot.facts) == 1
        assert len(snapshot.decisions) == 1
        assert snapshot.source == "test"


# ── Mapping completeness tests ──────────────────────────────────────────────

class TestMappings:
    def test_tone_map_covers_all_tones(self):
        """Every tone in TONE_TO_SENTIMENT should have an expression hint."""
        for tone in TONE_TO_SENTIMENT:
            assert tone in TONE_MAP, f"Missing TONE_MAP entry for: {tone}"

    def test_type_to_category_covers_extraction_types(self):
        """Every ExtractionType should map to a category."""
        for ext_type in ExtractionType:
            assert ext_type.value in TYPE_TO_CATEGORY, \
                f"Missing TYPE_TO_CATEGORY entry for: {ext_type.value}"
