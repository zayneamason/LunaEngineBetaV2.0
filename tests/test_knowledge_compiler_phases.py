"""
Tests for Knowledge Compiler Phases 1b, 1c, 2, 3.

Phase 1b: ConversationExtractor
Phase 1c: MarkdownExporter
Phase 2:  GroundingLink
Phase 3:  GroundingOverlay (frontend — not tested here)
"""

import asyncio
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from luna.compiler.conversation_extractor import ConversationExtractor, ExtractResult
from luna.compiler.markdown_export import MarkdownExporter, ExportResult
from luna.grounding.grounding_link import (
    GroundingLink,
    GroundingResult,
    GroundingSupport,
    GroundingSummary,
)


# ── Fixtures ────────────────────────────────────────────────────────


class FakeEntityIndex:
    """Minimal EntityIndex stub."""

    def __init__(self):
        self.entities = {}

    def resolve(self, name):
        mapping = {
            "amara": "amara_kabejja",
            "amara_kabejja": "amara_kabejja",
            "musoke": "elder_musoke",
        }
        return mapping.get(name.lower().strip(), None)

    def resolve_list(self, names):
        return [r for n in names if (r := self.resolve(n))]

    def load_entities(self, path):
        pass

    def get_profile(self, entity_id):
        return None


class FakeMatrix:
    """Minimal Matrix actor stub."""

    def __init__(self):
        self.stored = []
        self.is_ready = True
        self._counter = 0

    async def store_memory(self, content, node_type, tags, confidence, scope):
        self._counter += 1
        node_id = f"test-node-{self._counter}"
        self.stored.append({
            "id": node_id,
            "content": content,
            "node_type": node_type,
            "tags": tags,
            "confidence": confidence,
            "scope": scope,
        })
        return node_id


class FakeDB:
    """Minimal aiosqlite stub."""

    def __init__(self, rows=None):
        self._rows = rows or []

    async def execute_fetchall(self, query, params=None):
        return self._rows


class FakeMatrixWithDB:
    """Matrix stub with DB access for MarkdownExporter."""

    def __init__(self, rows):
        self._matrix = MagicMock()
        self._matrix.db = FakeDB(rows)
        self.is_ready = True


# ── Phase 2: GroundingLink tests ────────────────────────────────────


class TestGroundingLink:
    """Test the GroundingLink post-generation traceability system."""

    def test_empty_response(self):
        gl = GroundingLink()
        result = gl.ground("", [])
        assert isinstance(result, GroundingResult)
        assert result.supports == []
        assert result.summary.grounded == 0

    def test_empty_nodes(self):
        gl = GroundingLink()
        result = gl.ground("This is a test sentence.", [])
        assert result.supports == []

    def test_single_sentence_grounded(self):
        gl = GroundingLink()
        nodes = [
            {
                "id": "kn-fact-001",
                "content": "Amara GPS-surveyed three springs in November 2025 near Nakaseke.",
                "node_type": "FACT",
            }
        ]
        result = gl.ground(
            "Amara GPS-surveyed three springs in November 2025.",
            nodes,
        )
        assert len(result.supports) == 1
        s = result.supports[0]
        assert s.node_id == "kn-fact-001"
        assert s.node_type == "FACT"
        assert s.confidence > 0.3  # Should have significant overlap

    def test_multiple_sentences(self):
        gl = GroundingLink()
        nodes = [
            {"id": "fact-1", "content": "The spring has strong flow from a rock face.", "node_type": "FACT"},
            {"id": "fact-2", "content": "Water quality testing was conducted by NWSC.", "node_type": "FACT"},
        ]
        text = "The spring has strong flow from a rock face. Water quality testing was conducted by NWSC."
        result = gl.ground(text, nodes)
        assert len(result.supports) == 2
        assert result.summary.grounded + result.summary.inferred + result.summary.ungrounded == 2

    def test_classification_levels(self):
        assert GroundingLink._classify(0.8) == "GROUNDED"
        assert GroundingLink._classify(0.7) == "GROUNDED"
        assert GroundingLink._classify(0.5) == "INFERRED"
        assert GroundingLink._classify(0.4) == "INFERRED"
        assert GroundingLink._classify(0.3) == "UNGROUNDED"
        assert GroundingLink._classify(0.0) == "UNGROUNDED"

    def test_token_overlap_similarity(self):
        gl = GroundingLink()
        # Identical content should have high similarity
        score = gl._similarity_token_overlap(
            "Amara surveyed the springs near Nakaseke",
            "Amara surveyed the springs near Nakaseke",
        )
        assert score > 0.8

        # Completely different content should have low similarity
        score = gl._similarity_token_overlap(
            "The weather is sunny today",
            "Python programming language features",
        )
        assert score < 0.2

    def test_sentence_splitting(self):
        gl = GroundingLink()
        sentences = gl._split_sentences(
            "First sentence here. Second sentence here! Third one?"
        )
        assert len(sentences) == 3

    def test_short_fragments_filtered(self):
        gl = GroundingLink()
        sentences = gl._split_sentences("Hi. OK. This is a real sentence.")
        # "Hi" and "OK" should be filtered (< 10 chars)
        assert len(sentences) == 1

    def test_preview_truncation(self):
        short = "Short text"
        assert GroundingLink._preview(short) == short

        long = "A" * 200
        preview = GroundingLink._preview(long)
        assert len(preview) == 123  # 120 + "..."
        assert preview.endswith("...")

    def test_to_dict_format(self):
        gl = GroundingLink()
        nodes = [{"id": "n1", "content": "Amara surveyed springs in Nakaseke region.", "node_type": "FACT"}]
        result = gl.ground("Amara surveyed springs in Nakaseke region.", nodes)
        d = result.to_dict()
        assert "supports" in d
        assert "summary" in d
        assert isinstance(d["supports"], list)
        if d["supports"]:
            s = d["supports"][0]
            assert "sentence_index" in s
            assert "confidence" in s
            assert "level" in s

    def test_summarize(self):
        supports = [
            GroundingSupport(0, "s1", "n1", "FACT", None, 0.8, "GROUNDED"),
            GroundingSupport(1, "s2", "n2", "FACT", None, 0.5, "INFERRED"),
            GroundingSupport(2, "s3", None, None, None, 0.2, "UNGROUNDED"),
        ]
        summary = GroundingLink._summarize(supports)
        assert summary.grounded == 1
        assert summary.inferred == 1
        assert summary.ungrounded == 1
        assert abs(summary.avg_confidence - 0.5) < 0.01


# ── Phase 1b: ConversationExtractor tests ───────────────────────────


class TestConversationExtractor:
    """Test the ConversationExtractor for Phase 1b."""

    @pytest.fixture
    def extractor(self):
        return ConversationExtractor(FakeEntityIndex(), {})

    @pytest.fixture
    def matrix(self):
        return FakeMatrix()

    @pytest.fixture
    def thread_file(self, tmp_path):
        data = {
            "thread_id": "test_thread",
            "messages": [
                {
                    "id": "msg-001",
                    "role": "user",
                    "content": "Tell me about the spring survey.",
                    "timestamp": "2025-11-07T10:00:00Z",
                },
                {
                    "id": "msg-002",
                    "role": "assistant",
                    "content": (
                        "Amara GPS-surveyed three springs in November 2025. "
                        'The spring at 0.2788S was documented with strong flow. '
                        'Amara said "I found the spring hiding behind the banana plantation."'
                    ),
                    "timestamp": "2025-11-07T10:00:05Z",
                    "metadata": {
                        "entities": ["amara_kabejja"],
                        "topics": ["springs", "survey"],
                    },
                },
            ],
        }
        path = tmp_path / "test_thread.json"
        path.write_text(json.dumps(data))
        return tmp_path

    @pytest.mark.asyncio
    async def test_extract_thread(self, extractor, matrix, thread_file):
        result = await extractor.extract_all(thread_file, matrix)
        assert isinstance(result, ExtractResult)
        # Should extract at least some facts (GPS, date, action verbs)
        assert result.facts > 0 or result.quotes > 0

    @pytest.mark.asyncio
    async def test_extract_empty_dir(self, extractor, matrix, tmp_path):
        result = await extractor.extract_all(tmp_path, matrix)
        assert result.facts == 0
        assert result.quotes == 0

    @pytest.mark.asyncio
    async def test_extract_missing_dir(self, extractor, matrix):
        result = await extractor.extract_all(Path("/nonexistent"), matrix)
        assert len(result.errors) > 0

    def test_extract_result_to_dict(self):
        r = ExtractResult(facts=5, quotes=2, thread_arcs=1, corroborated=3)
        d = r.to_dict()
        assert d["facts"] == 5
        assert d["quotes"] == 2
        assert d["thread_arcs"] == 1
        assert d["corroborated"] == 3

    def test_hash_deterministic(self):
        ext = ConversationExtractor(FakeEntityIndex(), {})
        h1 = ext._hash("test content")
        h2 = ext._hash("test content")
        h3 = ext._hash("different content")
        assert h1 == h2
        assert h1 != h3


# ── Phase 1c: MarkdownExporter tests ───────────────────────────────


class TestMarkdownExporter:
    """Test the MarkdownExporter for Phase 1c."""

    @pytest.fixture
    def sample_rows(self):
        return [
            (
                "test-node-001",
                "Spring 3 (Nakayima) -- GPS Documented.\nGPS coordinates: 0.2788S, 31.7341E.",
                "FACT",
                '["guardian", "knowledge", "compiled", "fact", "amara_kabejja"]',
                80,
                "project:kinoni-ict-hub",
                "2025-11-07T10:00:00Z",
            ),
            (
                "test-briefing-001",
                "Amara Kabejja is the Youth Environmental Leader.\nKey accomplishments:\n- GPS-surveyed 3 springs",
                "PERSON_BRIEFING",
                '["briefing", "compiled", "constellation", "amara_kabejja"]',
                90,
                "project:kinoni-ict-hub",
                "2025-11-07T10:00:00Z",
            ),
        ]

    @pytest.mark.asyncio
    async def test_export_scope(self, sample_rows, tmp_path):
        matrix = FakeMatrixWithDB(sample_rows)
        exporter = MarkdownExporter(matrix)
        result = await exporter.export_scope("project:kinoni-ict-hub", tmp_path / "archive")
        assert result.files_written == 2
        assert result.bytes_written > 0

        # Check files exist
        files = list((tmp_path / "archive").glob("*.md"))
        assert len(files) == 2

    @pytest.mark.asyncio
    async def test_export_empty_scope(self, tmp_path):
        matrix = FakeMatrixWithDB([])
        exporter = MarkdownExporter(matrix)
        result = await exporter.export_scope("nonexistent", tmp_path / "empty")
        assert result.files_written == 0

    @pytest.mark.asyncio
    async def test_yaml_front_matter(self, sample_rows, tmp_path):
        matrix = FakeMatrixWithDB(sample_rows)
        exporter = MarkdownExporter(matrix)
        await exporter.export_scope("project:kinoni-ict-hub", tmp_path / "archive")

        files = list((tmp_path / "archive").glob("FACT_*.md"))
        assert len(files) >= 1
        content = files[0].read_text()
        assert content.startswith("---")
        assert "node_id:" in content
        assert "what: FACT" in content

    @pytest.mark.asyncio
    async def test_person_briefing_template(self, sample_rows, tmp_path):
        matrix = FakeMatrixWithDB(sample_rows)
        exporter = MarkdownExporter(matrix)
        await exporter.export_scope("project:kinoni-ict-hub", tmp_path / "archive")

        files = list((tmp_path / "archive").glob("PERSON_BRIEFING_*.md"))
        assert len(files) >= 1
        content = files[0].read_text()
        assert "PERSON_BRIEFING" in content
        assert "Amara" in content

    def test_export_result_to_dict(self):
        r = ExportResult(files_written=10, bytes_written=5000, skipped=2)
        d = r.to_dict()
        assert d["files_written"] == 10
        assert d["bytes_written"] == 5000
