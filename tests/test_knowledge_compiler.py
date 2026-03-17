"""
Tests for the Knowledge Compiler — Phase 1
===========================================

Tests entity resolution, knowledge compilation, constellation
generation, and edge creation.
"""

import json
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, MagicMock, PropertyMock

from luna.compiler.entity_index import EntityIndex, EntityProfile
from luna.compiler.constellation import (
    build_person_briefing,
    build_project_status,
    build_governance_record,
)
from luna.compiler.compiler import KnowledgeCompiler, CompileResult
from luna.compiler.constellation_prefetch import ConstellationPrefetch, PrefetchResult


# ── Fixtures ────────────────────────────────────────────────────


def _make_entities_json():
    """Minimal entities_updated.json fixture."""
    return {
        "entities": [
            {
                "id": "amara_kabejja",
                "name": "Amara Kabejja",
                "type": "person",
                "role": "Youth Environmental Leader",
                "profile": "Amara is a 22-year-old youth leader. She GPS-surveyed three springs.",
                "aliases": ["Amara", "Youth Leader"],
                "scope": "community",
                "clan": "Nkima",
                "mention_count_estimate": 50,
                "thread_presence": ["amara_thread"],
            },
            {
                "id": "elder_musoke",
                "name": "Elder Musoke",
                "type": "person",
                "role": "Council Elder",
                "profile": "Traditional knowledge holder of Olukomera.",
                "aliases": ["Musoke", "Jjajja Musoke"],
                "scope": "governance",
                "mention_count_estimate": 30,
                "thread_presence": ["musoke_thread"],
            },
            {
                "id": "wasswa",
                "name": "Wasswa Xyz",
                "type": "person",
                "role": "Treasurer",
                "profile": "Grant partner.",
                "aliases": ["wasswa_treasurer"],
                "scope": "community",
                "mention_count_estimate": 0,
            },
        ]
    }


def _make_facts_json():
    return {
        "nodes": [
            {
                "id": "kn-fact-001",
                "node_type": "FACT",
                "title": "Five historical springs identified by Musoke",
                "content": "Elder Musoke identified five springs from oral tradition.",
                "created_by": "elder_musoke",
                "created_date": "2025-10-08",
                "scope": "governance",
                "connections": ["kn-fact-006"],
                "lock_in": 0.6,
                "tags": ["springs", "oral-history"],
            },
            {
                "id": "kn-fact-006",
                "node_type": "FACT",
                "title": "Spring 1 GPS documented by Amara",
                "content": "Amara GPS-surveyed River Road SE spring. Active, steady flow.",
                "created_by": "amara_kabejja",
                "created_date": "2025-11-07",
                "scope": "community",
                "connections": ["kn-fact-001"],
                "lock_in": 0.8,
                "tags": ["springs", "gps", "survey"],
            },
        ]
    }


def _make_decisions_json():
    return {
        "nodes": [
            {
                "id": "kn-dec-001",
                "node_type": "DECISION",
                "title": "Integrate spring survey data into Rotary grant v3",
                "content": "The treasurer decided to include Amara's GPS data in grant.",
                "created_by": "wasswa",
                "created_date": "2025-11-22",
                "scope": "community",
                "connections": ["kn-fact-006"],
                "lock_in": 0.95,
                "tags": ["grant", "rotary"],
            },
        ]
    }


def _make_milestones_json():
    return {
        "nodes": [
            {
                "id": "kn-mil-001",
                "node_type": "MILESTONE",
                "title": "Council Decision #19 — Olukomera enters governance record",
                "content": "Olukomera formally recognized, passed 8-1.",
                "created_by": "elder_musoke",
                "created_date": "2026-01-15",
                "scope": "governance",
                "connections": [],
                "lock_in": 0.95,
                "tags": ["milestone", "governance"],
            },
        ]
    }


def _make_actions_json():
    return {
        "nodes": [
            {
                "id": "kn-act-001",
                "node_type": "ACTION",
                "title": "Field verification of remaining mapped springs",
                "content": "Pending field verification.",
                "created_by": "amara_kabejja",
                "created_date": "2025-11-10",
                "scope": "community",
                "connections": ["kn-fact-001"],
                "lock_in": 0.5,
                "tags": ["pending", "field-work"],
            },
        ]
    }


def _make_insights_json():
    return {
        "nodes": [
            {
                "id": "kn-ins-001",
                "node_type": "INSIGHT",
                "title": "Amara independently located springs Olukomera was designed to protect",
                "content": "GPS data converged with oral tradition at 2-meter precision.",
                "created_by": "amara_kabejja",
                "created_date": "2026-01-20",
                "scope": "governance",
                "connections": ["kn-fact-001", "kn-fact-006"],
                "lock_in": 0.6,
                "tags": ["convergence", "knowledge-systems"],
            },
        ]
    }


def _make_relationships_json():
    return {
        "relationships": [
            {
                "from": "elder_musoke",
                "to": "amara_kabejja",
                "type": "enables",
                "strength": 0.95,
                "description": "Musoke initiated Olukomera knowledge transfer",
            },
            {
                "from": "kn-fact-001",
                "to": "kn-fact-006",
                "type": "related_to",
                "strength": 0.8,
            },
        ]
    }


def _make_timeline_json():
    return {
        "events": [
            {
                "id": "org-evt-001",
                "timestamp": "2025-10-05T09:00:00+03:00",
                "title": "Amara Kabejja appointed youth leader",
                "description": "Amara was formally appointed as youth leader.",
                "knowledge_type": "MILESTONE",
                "actors": ["amara_kabejja"],
                "connections": {"enables": ["org-evt-002"]},
                "impact_score": 0.6,
                "tags": ["appointment"],
            },
            {
                "id": "org-evt-002",
                "timestamp": "2025-10-08T09:00:00+03:00",
                "title": "Elder Musoke meets Amara",
                "description": "Olukomera knowledge surfaced.",
                "knowledge_type": "MILESTONE",
                "actors": ["elder_musoke", "amara_kabejja"],
                "connections": {"depends_on": ["org-evt-001"]},
                "impact_score": 0.95,
                "tags": ["olukomera"],
            },
        ]
    }


def _make_scope_transitions_json():
    return {
        "transitions": [
            {
                "id": "st-001",
                "timestamp": "2026-02-10T12:32:00+03:00",
                "from_scope": "governance",
                "to_scope": "community",
                "content_description": "Olukomera governance framework for grant use",
                "approved_by": "continental_council",
            },
        ]
    }


@pytest.fixture
def guardian_data_dir():
    """Create a temporary Guardian data directory with fixture files."""
    with TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        # Create directory structure
        (root / "entities").mkdir()
        (root / "knowledge_nodes").mkdir()
        (root / "org_timeline").mkdir()
        (root / "membrane").mkdir()

        # Write fixture files
        with open(root / "entities" / "entities_updated.json", "w") as f:
            json.dump(_make_entities_json(), f)
        with open(root / "entities" / "relationships_updated.json", "w") as f:
            json.dump(_make_relationships_json(), f)
        with open(root / "knowledge_nodes" / "facts.json", "w") as f:
            json.dump(_make_facts_json(), f)
        with open(root / "knowledge_nodes" / "decisions.json", "w") as f:
            json.dump(_make_decisions_json(), f)
        with open(root / "knowledge_nodes" / "milestones.json", "w") as f:
            json.dump(_make_milestones_json(), f)
        with open(root / "knowledge_nodes" / "actions.json", "w") as f:
            json.dump(_make_actions_json(), f)
        with open(root / "knowledge_nodes" / "insights.json", "w") as f:
            json.dump(_make_insights_json(), f)
        with open(root / "org_timeline" / "timeline_events.json", "w") as f:
            json.dump(_make_timeline_json(), f)
        with open(root / "membrane" / "scope_transitions.json", "w") as f:
            json.dump(_make_scope_transitions_json(), f)

        yield root


@pytest.fixture
def mock_matrix():
    """Mock MatrixActor with store_memory and graph."""
    matrix = MagicMock()
    matrix.is_ready = True

    # store_memory returns incrementing node IDs
    call_count = {"n": 0}
    async def mock_store(content, node_type="FACT", tags=None,
                         confidence=100, session_id=None, scope="global"):
        call_count["n"] += 1
        return f"node_{call_count['n']:04d}"
    matrix.store_memory = mock_store

    # Graph mock
    graph = MagicMock()
    async def mock_add_edge(from_id, to_id, relationship, strength=1.0, scope="global"):
        pass
    graph.add_edge = mock_add_edge
    async def mock_load():
        pass
    graph.load_from_db = mock_load
    matrix._graph = graph

    # DB mock for clear
    db_mock = MagicMock()
    result_mock = MagicMock()
    result_mock.rowcount = 5
    async def mock_execute(sql, params=None):
        return result_mock
    db_mock.execute = mock_execute
    matrix_inner = MagicMock()
    matrix_inner.db = db_mock
    matrix._matrix = matrix_inner

    return matrix


@pytest.fixture
def mock_engine(mock_matrix):
    """Mock LunaEngine that returns the mock matrix."""
    engine = MagicMock()
    engine.get_actor.return_value = mock_matrix
    return engine


# ── Entity Index Tests ──────────────────────────────────────────


class TestEntityIndex:
    def test_load_entities(self, guardian_data_dir):
        idx = EntityIndex()
        idx.load_entities(guardian_data_dir / "entities" / "entities_updated.json")
        assert len(idx.entities) == 3
        assert "amara_kabejja" in idx.entities

    def test_resolve_canonical_id(self, guardian_data_dir):
        idx = EntityIndex()
        idx.load_entities(guardian_data_dir / "entities" / "entities_updated.json")
        assert idx.resolve("amara_kabejja") == "amara_kabejja"

    def test_resolve_alias(self, guardian_data_dir):
        idx = EntityIndex()
        idx.load_entities(guardian_data_dir / "entities" / "entities_updated.json")
        assert idx.resolve("Amara") == "amara_kabejja"
        assert idx.resolve("Youth Leader") == "amara_kabejja"

    def test_resolve_case_insensitive(self, guardian_data_dir):
        idx = EntityIndex()
        idx.load_entities(guardian_data_dir / "entities" / "entities_updated.json")
        assert idx.resolve("AMARA") == "amara_kabejja"
        assert idx.resolve("jjajja musoke") == "elder_musoke"

    def test_resolve_unknown(self, guardian_data_dir):
        idx = EntityIndex()
        idx.load_entities(guardian_data_dir / "entities" / "entities_updated.json")
        assert idx.resolve("Unknown Person") is None

    def test_resolve_list(self, guardian_data_dir):
        idx = EntityIndex()
        idx.load_entities(guardian_data_dir / "entities" / "entities_updated.json")
        result = idx.resolve_list(["Amara", "Musoke", "unknown", "Amara"])
        assert result == ["amara_kabejja", "elder_musoke"]

    def test_significant_entities(self, guardian_data_dir):
        idx = EntityIndex()
        idx.load_entities(guardian_data_dir / "entities" / "entities_updated.json")
        # Amara has 50, Musoke has 30, Wasswa has 1
        significant = idx.significant_entities(min_mentions=3)
        ids = [e.id for e in significant]
        assert "amara_kabejja" in ids
        assert "elder_musoke" in ids
        assert "wasswa" not in ids

    def test_record_mention(self, guardian_data_dir):
        idx = EntityIndex()
        idx.load_entities(guardian_data_dir / "entities" / "entities_updated.json")
        initial = idx.entities["amara_kabejja"].mention_count
        idx.record_mention("amara_kabejja", "kn-fact-006")
        assert idx.entities["amara_kabejja"].mention_count == initial + 1
        assert "kn-fact-006" in idx.entities["amara_kabejja"].mentioned_in

    def test_load_missing_file(self):
        idx = EntityIndex()
        idx.load_entities(Path("/nonexistent/file.json"))
        assert len(idx.entities) == 0

    def test_entity_profile_fields(self, guardian_data_dir):
        idx = EntityIndex()
        idx.load_entities(guardian_data_dir / "entities" / "entities_updated.json")
        amara = idx.get_profile("amara_kabejja")
        assert amara is not None
        assert amara.name == "Amara Kabejja"
        assert amara.entity_type == "person"
        assert amara.role == "Youth Environmental Leader"
        assert amara.clan == "Nkima"
        assert "Amara" in amara.aliases


# ── Constellation Tests ─────────────────────────────────────────


class TestConstellations:
    def test_person_briefing_content(self):
        profile = EntityProfile(
            id="amara_kabejja",
            name="Amara Kabejja",
            entity_type="person",
            role="Youth Environmental Leader",
            profile="Amara is a 22-year-old youth leader. She GPS-surveyed three springs.",
            clan="Nkima",
            scope="community",
        )
        related = [
            {"node_type": "FACT", "title": "Spring 1 GPS documented", "lock_in": 0.8},
            {"node_type": "MILESTONE", "title": "Council Decision #19", "created_date": "2026-01-15"},
            {"node_type": "ACTION", "title": "Field verification pending"},
        ]
        result = build_person_briefing(profile, related)
        assert result.node_type == "PERSON_BRIEFING"
        assert "Amara Kabejja" in result.content
        assert "Youth Environmental Leader" in result.content
        assert "Council Decision #19" in result.content
        assert result.confidence == 0.9
        assert "amara_kabejja" in result.entities

    def test_project_status(self):
        milestones = [
            {"node_type": "MILESTONE", "title": "Phase 1 complete", "created_date": "2026-01-15"},
        ]
        actions = [
            {"node_type": "ACTION", "title": "Spring verification", "tags": ["pending"]},
        ]
        decisions = [
            {"node_type": "DECISION", "title": "Grant approved"},
        ]
        result = build_project_status("Test Project", "test-proj", milestones, actions, decisions)
        assert result.node_type == "PROJECT_STATUS"
        assert "Test Project" in result.content
        assert "Phase 1 complete" in result.content

    def test_governance_record(self):
        decisions = [
            {"node_type": "DECISION", "title": "Council Decision #19", "scope": "governance", "created_date": "2026-01-15"},
        ]
        insights = [
            {"node_type": "INSIGHT", "title": "Knowledge gap identified", "scope": "governance"},
        ]
        transitions = [
            {"timestamp": "2026-02-10T12:00:00", "from_scope": "governance", "to_scope": "community", "content_description": "Olukomera for grant"},
        ]
        idx = EntityIndex()
        result = build_governance_record(decisions, insights, transitions, idx)
        assert result.node_type == "GOVERNANCE_RECORD"
        assert "Council Decision #19" in result.content
        assert "governance" in result.scope


# ── Compiler Integration Tests ──────────────────────────────────


class TestKnowledgeCompiler:
    @pytest.mark.asyncio
    async def test_compile_all(self, mock_engine, guardian_data_dir):
        compiler = KnowledgeCompiler(mock_engine, guardian_data_dir)
        result = await compiler.compile_all()

        assert isinstance(result, CompileResult)
        assert result.entities == 3  # 3 entities
        assert result.knowledge >= 5  # 5 knowledge nodes (facts + decisions + milestones + actions + insights)
        assert result.constellations >= 2  # At least person briefings + project status
        assert result.edges > 0
        assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_node_map_populated(self, mock_engine, guardian_data_dir):
        compiler = KnowledgeCompiler(mock_engine, guardian_data_dir)
        await compiler.compile_all()

        # Source IDs should be mapped to matrix node IDs
        assert "amara_kabejja" in compiler.node_map
        assert "elder_musoke" in compiler.node_map
        assert "kn-fact-001" in compiler.node_map
        assert "kn-fact-006" in compiler.node_map

    @pytest.mark.asyncio
    async def test_entity_index_built(self, mock_engine, guardian_data_dir):
        compiler = KnowledgeCompiler(mock_engine, guardian_data_dir)
        await compiler.compile_all()

        assert compiler.entity_index.resolve("Amara") == "amara_kabejja"
        assert compiler.entity_index.resolve("Musoke") == "elder_musoke"

    @pytest.mark.asyncio
    async def test_person_briefings_generated(self, mock_engine, guardian_data_dir):
        compiler = KnowledgeCompiler(mock_engine, guardian_data_dir)
        result = await compiler.compile_all()

        # Amara (50 mentions) and Musoke (30 mentions) should get briefings
        assert "briefing:amara_kabejja" in compiler.node_map
        assert "briefing:elder_musoke" in compiler.node_map
        # Wasswa only has 1 mention — no briefing
        assert "briefing:wasswa" not in compiler.node_map

    @pytest.mark.asyncio
    async def test_project_status_generated(self, mock_engine, guardian_data_dir):
        compiler = KnowledgeCompiler(mock_engine, guardian_data_dir)
        await compiler.compile_all()
        assert "project_status:kinoni-ict-hub" in compiler.node_map

    @pytest.mark.asyncio
    async def test_governance_record_generated(self, mock_engine, guardian_data_dir):
        compiler = KnowledgeCompiler(mock_engine, guardian_data_dir)
        await compiler.compile_all()
        assert "governance_record:nakaseke_rc" in compiler.node_map

    @pytest.mark.asyncio
    async def test_timeline_events_compiled(self, mock_engine, guardian_data_dir):
        compiler = KnowledgeCompiler(mock_engine, guardian_data_dir)
        result = await compiler.compile_all()

        # Both timeline events have impact >= 0.4
        assert "org-evt-001" in compiler.node_map
        assert "org-evt-002" in compiler.node_map

    @pytest.mark.asyncio
    async def test_clear(self, mock_engine, guardian_data_dir):
        compiler = KnowledgeCompiler(mock_engine, guardian_data_dir)
        await compiler.compile_all()

        removed = await compiler.clear()
        assert removed == 5  # Mock returns rowcount=5
        assert len(compiler.node_map) == 0

    @pytest.mark.asyncio
    async def test_matrix_not_ready(self, guardian_data_dir):
        engine = MagicMock()
        engine.get_actor.return_value = None
        compiler = KnowledgeCompiler(engine, guardian_data_dir)
        result = await compiler.compile_all()
        assert "Matrix actor not ready" in result.errors

    @pytest.mark.asyncio
    async def test_compile_result_to_dict(self):
        result = CompileResult(entities=3, knowledge=10, constellations=4, edges=20)
        d = result.to_dict()
        assert d["entities"] == 3
        assert d["knowledge"] == 10
        assert d["constellations"] == 4
        assert d["edges"] == 20

    @pytest.mark.asyncio
    async def test_empty_data_dir(self, mock_engine):
        with TemporaryDirectory() as tmpdir:
            compiler = KnowledgeCompiler(mock_engine, Path(tmpdir))
            result = await compiler.compile_all()
            assert result.entities == 0
            assert result.knowledge == 0


# -- EntityIndex.resolve_mentions tests -----------------------------------


class TestResolveMentions:
    def test_resolve_mentions_single(self, guardian_data_dir):
        idx = EntityIndex()
        idx.load_entities(guardian_data_dir / "entities" / "entities_updated.json")
        result = idx.resolve_mentions("Tell me about Amara")
        assert "amara_kabejja" in result

    def test_resolve_mentions_multiple(self, guardian_data_dir):
        idx = EntityIndex()
        idx.load_entities(guardian_data_dir / "entities" / "entities_updated.json")
        result = idx.resolve_mentions("What is the relationship between Amara and Musoke?")
        assert "amara_kabejja" in result
        assert "elder_musoke" in result

    def test_resolve_mentions_alias(self, guardian_data_dir):
        idx = EntityIndex()
        idx.load_entities(guardian_data_dir / "entities" / "entities_updated.json")
        result = idx.resolve_mentions("Jjajja Musoke shared knowledge")
        assert "elder_musoke" in result

    def test_resolve_mentions_no_match(self, guardian_data_dir):
        idx = EntityIndex()
        idx.load_entities(guardian_data_dir / "entities" / "entities_updated.json")
        result = idx.resolve_mentions("What is the weather like?")
        assert result == []

    def test_resolve_mentions_no_duplicates(self, guardian_data_dir):
        idx = EntityIndex()
        idx.load_entities(guardian_data_dir / "entities" / "entities_updated.json")
        # "Amara Kabejja" matches both "amara kabejja" and "amara" aliases
        result = idx.resolve_mentions("Amara Kabejja is the youth leader")
        assert result.count("amara_kabejja") == 1


# -- ConstellationPrefetch tests ------------------------------------------


class TestConstellationPrefetch:
    @pytest.fixture
    def prefetch_matrix(self):
        """Mock matrix with PERSON_BRIEFING nodes in DB."""
        matrix = MagicMock()
        matrix.is_ready = True

        # Simulate MemoryNode
        class FakeNode:
            def __init__(self, nid, node_type, content, lock_in=0.85):
                self.id = nid
                self.node_type = node_type
                self.content = content
                self.lock_in = lock_in

        amara_briefing = FakeNode(
            "node_0012", "PERSON_BRIEFING",
            "Amara Kabejja is the Youth Environmental Leader. "
            "She GPS-surveyed three springs in November 2025.",
        )
        project_status = FakeNode(
            "node_0020", "PROJECT_STATUS",
            "Project: Nakaseke Restoration Collective. Timeline: ...",
        )
        gov_record = FakeNode(
            "node_0021", "GOVERNANCE_RECORD",
            "Governance Record. Council decisions: ...",
        )

        # Mock DB fetchall + get_node
        db = MagicMock()
        memory = MagicMock()
        memory.db = db

        async def mock_fetchall(sql, params=None):
            if params and "PERSON_BRIEFING" in params:
                if params[-1] and "amara_kabejja" in params[-1]:
                    return [("node_0012",)]
                return []
            if params and "PROJECT_STATUS" in params:
                return [("node_0020",)]
            if params and "GOVERNANCE_RECORD" in params:
                return [("node_0021",)]
            return []
        db.fetchall = mock_fetchall

        node_map = {
            "node_0012": amara_briefing,
            "node_0020": project_status,
            "node_0021": gov_record,
        }
        async def mock_get_node(nid):
            return node_map.get(nid)
        memory.get_node = mock_get_node

        matrix._matrix = memory
        return matrix

    @pytest.fixture
    def prefetch_index(self, guardian_data_dir):
        idx = EntityIndex()
        idx.load_entities(guardian_data_dir / "entities" / "entities_updated.json")
        return idx

    @pytest.mark.asyncio
    async def test_prefetch_entity_match(self, prefetch_matrix, prefetch_index):
        pf = ConstellationPrefetch(prefetch_matrix, prefetch_index)
        result = await pf.prefetch("Tell me about Amara", scope="project:kinoni-ict-hub")
        assert len(result.nodes) == 1
        assert result.nodes[0].node_type == "PERSON_BRIEFING"
        assert "Amara Kabejja" in result.nodes[0].content
        assert result.tokens_used > 0

    @pytest.mark.asyncio
    async def test_prefetch_project_signal(self, prefetch_matrix, prefetch_index):
        pf = ConstellationPrefetch(prefetch_matrix, prefetch_index)
        result = await pf.prefetch("What is the project status?", scope="project:kinoni-ict-hub")
        assert any(n.node_type == "PROJECT_STATUS" for n in result.nodes)

    @pytest.mark.asyncio
    async def test_prefetch_governance_signal(self, prefetch_matrix, prefetch_index):
        pf = ConstellationPrefetch(prefetch_matrix, prefetch_index)
        result = await pf.prefetch("Tell me about governance decisions", scope="project:kinoni-ict-hub")
        assert any(n.node_type == "GOVERNANCE_RECORD" for n in result.nodes)

    @pytest.mark.asyncio
    async def test_prefetch_no_match(self, prefetch_matrix, prefetch_index):
        pf = ConstellationPrefetch(prefetch_matrix, prefetch_index)
        result = await pf.prefetch("What is the weather?", scope="project:kinoni-ict-hub")
        assert len(result.nodes) == 0
        assert result.tokens_used == 0

    @pytest.mark.asyncio
    async def test_prefetch_entity_plus_governance(self, prefetch_matrix, prefetch_index):
        pf = ConstellationPrefetch(prefetch_matrix, prefetch_index)
        result = await pf.prefetch(
            "What did Elder Musoke decide at the council?",
            scope="project:kinoni-ict-hub",
        )
        types = [n.node_type for n in result.nodes]
        # Should get governance record (council signal) — elder_musoke
        # may or may not get briefing depending on DB mock
        assert "GOVERNANCE_RECORD" in types
