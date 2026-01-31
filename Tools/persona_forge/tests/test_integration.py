"""
Integration tests for Persona Forge engine.

These tests exercise the full pipeline end-to-end to catch
bugs that unit tests miss - like Pydantic model access patterns.

Run with: pytest tests/test_integration.py -v
"""
import json
import pytest
from pathlib import Path

# Add src to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from persona_forge.engine.anvil import Anvil
from persona_forge.engine.crucible import Crucible
from persona_forge.engine.assayer import Assayer
from persona_forge.engine.models import (
    TrainingExample, VoiceMarkers, AntiPatterns,
    DatasetAssay, DIRECTOR_PROFILE, InteractionType,
    QualityTier, SourceType
)

from tests.fixtures import get_minimal_fixture_path


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def minimal_fixture_path():
    """Path to minimal test fixture."""
    return get_minimal_fixture_path()


@pytest.fixture
def crucible():
    """Fresh Crucible instance."""
    return Crucible()


@pytest.fixture
def loaded_examples(crucible, minimal_fixture_path):
    """Examples loaded via Crucible."""
    return crucible.ingest_jsonl(minimal_fixture_path)


@pytest.fixture
def assayer():
    """Assayer with default profile."""
    return Assayer(target_profile=DIRECTOR_PROFILE)


# =============================================================================
# Smoke Tests - Full Pipeline
# =============================================================================

class TestFullPipeline:
    """End-to-end pipeline tests that catch integration bugs."""
    
    def test_load_assay_export_doesnt_crash(self, minimal_fixture_path, tmp_path):
        """
        CRITICAL: This test would have caught Bug #7 (Pydantic .get() issue).
        
        Full pipeline: load → assay → gaps → export
        """
        # Load via Crucible
        crucible = Crucible()
        examples = crucible.ingest_jsonl(minimal_fixture_path)
        assert len(examples) == 10
        
        # Assay - THIS IS WHERE BUG #7 CRASHES
        assayer = Assayer(target_profile=DIRECTOR_PROFILE)
        report = assayer.analyze(examples)
        
        # Verify report structure
        assert isinstance(report, DatasetAssay)
        assert 0 <= report.health_score <= 100
        assert report.total_examples == 10
        
        # Gaps
        gaps = report.synthesis_targets
        assert isinstance(gaps, dict)
        
        # Export via Anvil
        anvil = Anvil()
        output_path = tmp_path / "test_export.jsonl"
        anvil.export_jsonl(examples, output_path)
        assert output_path.exists()
    
    def test_crucible_creates_valid_examples(self, minimal_fixture_path):
        """Crucible produces TrainingExamples with valid Pydantic models."""
        crucible = Crucible()
        examples = crucible.ingest_jsonl(minimal_fixture_path)
        
        for ex in examples:
            # Verify Pydantic models, not dicts
            assert isinstance(ex.voice_markers, VoiceMarkers)
            assert isinstance(ex.anti_patterns, AntiPatterns)
            
            # Verify we can access attributes (not .get())
            _ = ex.voice_markers.first_person
            _ = ex.voice_markers.warmth_words
            _ = ex.anti_patterns.generic_ai
            _ = ex.anti_patterns.corporate


# =============================================================================
# Assayer Tests - The Bug Zone
# =============================================================================

class TestAssayer:
    """Tests for Assayer - where Bug #7 lives."""
    
    def test_analyze_returns_valid_report(self, assayer, loaded_examples):
        """Assayer.analyze() returns complete DatasetAssay."""
        report = assayer.analyze(loaded_examples)
        
        # Required fields
        assert report.total_examples > 0
        assert isinstance(report.interaction_type_dist, dict)
        assert isinstance(report.response_length_dist, dict)
        assert isinstance(report.voice_marker_rates, dict)
        assert isinstance(report.anti_pattern_rates, dict)
        
        # Health score in valid range
        assert 0 <= report.health_score <= 100
    
    def test_voice_marker_rates_computed(self, assayer, loaded_examples):
        """
        BUG #7 REGRESSION TEST
        
        This specifically tests the code path that was using .get()
        on Pydantic models instead of getattr().
        """
        report = assayer.analyze(loaded_examples)
        
        # Should have computed rates for all markers
        expected_markers = ["first_person", "warmth_words", "uncertainty", "relationship"]
        for marker in expected_markers:
            assert marker in report.voice_marker_rates
            rate = report.voice_marker_rates[marker]
            assert 0.0 <= rate <= 1.0, f"{marker} rate {rate} out of range"
    
    def test_anti_pattern_rates_computed(self, assayer, loaded_examples):
        """
        BUG #7 REGRESSION TEST (anti-patterns path)
        
        Same issue - .get() on Pydantic AntiPatterns model.
        """
        report = assayer.analyze(loaded_examples)
        
        expected_patterns = ["generic_ai", "corporate", "hedging"]
        for pattern in expected_patterns:
            assert pattern in report.anti_pattern_rates
            rate = report.anti_pattern_rates[pattern]
            assert 0.0 <= rate <= 1.0, f"{pattern} rate {rate} out of range"
    
    def test_detects_anti_patterns_in_fixture(self, assayer, loaded_examples):
        """Fixture contains known anti-patterns - verify detection."""
        report = assayer.analyze(loaded_examples)
        
        # Fixture has 2 examples with anti-patterns (examples 5 and 6)
        # So rates should be > 0
        assert report.anti_pattern_rates.get("generic_ai", 0) > 0
        assert report.anti_pattern_rates.get("corporate", 0) > 0


# =============================================================================
# Model Tests - Pydantic Behavior
# =============================================================================

class TestModels:
    """Tests for Pydantic model behavior."""
    
    def test_voice_markers_is_pydantic_not_dict(self):
        """VoiceMarkers must be accessed with attributes, not .get()"""
        markers = VoiceMarkers(first_person=5, warmth_words=3)
        
        # Correct access pattern
        assert markers.first_person == 5
        assert markers.warmth_words == 3
        
        # This would fail - VoiceMarkers is not a dict
        with pytest.raises(AttributeError):
            markers.get("first_person")  # type: ignore
    
    def test_anti_patterns_is_pydantic_not_dict(self):
        """AntiPatterns must be accessed with attributes, not .get()"""
        patterns = AntiPatterns(generic_ai=2, corporate=1)
        
        # Correct access pattern
        assert patterns.generic_ai == 2
        assert patterns.corporate == 1
        
        # This would fail - AntiPatterns is not a dict
        with pytest.raises(AttributeError):
            patterns.get("generic_ai")  # type: ignore
    
    def test_training_example_to_dict(self):
        """TrainingExample exports correctly."""
        example = TrainingExample(
            system_prompt="Test system",
            user_message="Test user",
            assistant_response="Test response"
        )
        
        exported = example.to_training_dict()
        assert "messages" in exported
        assert len(exported["messages"]) == 3


# =============================================================================
# Crucible Tests (Loading)
# =============================================================================

class TestCrucible:
    """Tests for Crucible data loading."""
    
    def test_ingest_jsonl(self, minimal_fixture_path):
        """Crucible loads JSONL correctly."""
        crucible = Crucible()
        examples = crucible.ingest_jsonl(minimal_fixture_path)
        
        assert len(examples) == 10
        assert all(isinstance(e, TrainingExample) for e in examples)
    
    def test_examples_have_computed_metrics(self, minimal_fixture_path):
        """Ingested examples have word counts computed."""
        crucible = Crucible()
        examples = crucible.ingest_jsonl(minimal_fixture_path)
        
        for ex in examples:
            assert ex.response_word_count > 0
            assert ex.user_word_count > 0
    
    def test_voice_markers_detected(self, minimal_fixture_path):
        """Voice markers are detected during ingestion."""
        crucible = Crucible()
        examples = crucible.ingest_jsonl(minimal_fixture_path)
        
        # At least some examples should have voice markers
        has_markers = [e for e in examples if e.voice_markers.total > 0]
        assert len(has_markers) > 0


# =============================================================================
# Anvil Tests (Export)
# =============================================================================

class TestInteractionTypePreservation:
    """Tests for preserving interaction_type from source data."""
    
    def test_preserves_source_interaction_type(self, tmp_path):
        """Interaction type from JSONL should be preserved, not re-classified."""
        # Create JSONL with explicit interaction_type
        test_file = tmp_path / "test.jsonl"
        test_file.write_text(json.dumps({
            "user_message": "random message",
            "assistant_response": "random response",
            "interaction_type": "reflection"  # Explicitly set
        }) + "\n")
        
        crucible = Crucible(enable_personality_scoring=False)
        examples = crucible.ingest_jsonl(test_file)
        
        # Should preserve "reflection", not reclassify to "short_exchange"
        assert examples[0].interaction_type.value == "reflection"
    
    def test_falls_back_to_classification_when_missing(self, tmp_path):
        """Should classify when interaction_type not provided."""
        test_file = tmp_path / "test.jsonl"
        test_file.write_text(json.dumps({
            "user_message": "hey luna",
            "assistant_response": "Hey there!"
        }) + "\n")
        
        crucible = Crucible(enable_personality_scoring=False)
        examples = crucible.ingest_jsonl(test_file)
        
        # Should classify as greeting
        assert examples[0].interaction_type.value == "greeting"


class TestAnvil:
    """Tests for Anvil export functionality."""
    
    def test_export_jsonl(self, loaded_examples, tmp_path):
        """Anvil exports to JSONL correctly."""
        anvil = Anvil()
        output_path = tmp_path / "export.jsonl"
        
        anvil.export_jsonl(loaded_examples, output_path)
        
        assert output_path.exists()
        with open(output_path) as f:
            lines = f.readlines()
        # Anvil adds a metadata header comment, so 11 lines for 10 examples
        assert len(lines) == 11
    
    def test_export_reimport_consistency(self, loaded_examples, tmp_path):
        """Export and reimport produces same data."""
        anvil = Anvil()
        export_path = tmp_path / "roundtrip.jsonl"
        anvil.export_jsonl(loaded_examples, export_path)
        
        # Reimport
        crucible = Crucible()
        reimported = crucible.ingest_jsonl(export_path)
        
        assert len(reimported) == len(loaded_examples)
