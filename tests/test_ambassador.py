"""
Tests for the Ambassador Pattern
=================================

Covers:
- Protocol parsing and serialization
- Rule matching (audience, scope, conditions)
- Exclude overrides include
- Default deny behavior
- Audit logging
- Demo protocol loading
- Isolation (no cross-ambassador communication)
"""

import json
import pytest
import aiosqlite
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# We test against a real in-memory SQLite to verify schema + queries
from luna.identity.ambassador import (
    AmbassadorProxy,
    AmbassadorProtocol,
    AmbassadorRule,
    AmbassadorResult,
    _extract_categories,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

class InMemoryDB:
    """Minimal async DB wrapper for testing (mirrors MemoryDatabase interface)."""

    def __init__(self):
        self._conn = None

    async def connect(self):
        self._conn = await aiosqlite.connect(":memory:")
        await self._conn.execute("PRAGMA foreign_keys=ON")

        # Load core schema
        schema_path = Path(__file__).parent.parent / "src" / "luna" / "substrate" / "schema.sql"
        if schema_path.exists():
            schema_sql = schema_path.read_text()
            await self._conn.executescript(schema_sql)

        # Load ambassador migration
        migration_path = Path(__file__).parent.parent / "migrations" / "004_ambassador_protocol.sql"
        if migration_path.exists():
            migration_sql = migration_path.read_text()
            await self._conn.executescript(migration_sql)

        await self._conn.commit()

    async def close(self):
        if self._conn:
            await self._conn.close()

    async def execute(self, sql, params=None):
        cursor = await self._conn.execute(sql, params or ())
        await self._conn.commit()
        return cursor

    async def fetchone(self, sql, params=None):
        async with self._conn.execute(sql, params or ()) as cursor:
            return await cursor.fetchone()

    async def fetchall(self, sql, params=None):
        async with self._conn.execute(sql, params or ()) as cursor:
            return await cursor.fetchall()


@pytest.fixture
async def db():
    """Create an in-memory test database with ambassador tables."""
    test_db = InMemoryDB()
    await test_db.connect()

    # Seed a test entity
    await test_db.execute(
        "INSERT INTO entities (id, entity_type, name) VALUES (?, ?, ?)",
        ("amara_kato", "person", "Amara Kato"),
    )
    await test_db.execute(
        "INSERT INTO entities (id, entity_type, name) VALUES (?, ?, ?)",
        ("elder_musoke", "person", "Elder Musoke"),
    )
    await test_db.execute(
        "INSERT INTO entities (id, entity_type, name) VALUES (?, ?, ?)",
        ("treasurer_wasswa", "person", "Treasurer Wasswa"),
    )

    yield test_db
    await test_db.close()


@pytest.fixture
def amara_protocol_json():
    """Amara's demo protocol as raw JSON."""
    return {
        "ambassador_protocol": {
            "version": "0.1",
            "owner": "amara_kato",
            "display_name": "Amara's Ambassador",
            "rules": [
                {
                    "id": "project-sharing",
                    "description": "Share project work with all community roles",
                    "audience": {"type": "role", "value": ["elder", "council_member", "youth_leader"]},
                    "scope": {
                        "include": ["project_updates", "restoration_data", "monitoring_results"],
                        "exclude": ["personal", "health", "family", "mother_health"],
                    },
                    "conditions": {},
                },
                {
                    "id": "governance-participation",
                    "description": "Share governance input with council",
                    "audience": {"type": "role", "value": ["elder", "council_member"]},
                    "scope": {
                        "include": ["youth_perspective", "capacity_assessment"],
                        "exclude": ["personal", "health", "family"],
                    },
                    "conditions": {},
                },
            ],
            "default_action": "deny",
            "audit_log": True,
        }
    }


# ---------------------------------------------------------------------------
# Unit Tests: AmbassadorRule
# ---------------------------------------------------------------------------

class TestAmbassadorRule:
    """Test individual rule matching."""

    def test_audience_matches_role(self):
        rule = AmbassadorRule(
            id="r1", description="", audience_type="role",
            audience_values=["elder", "council_member"],
            scope_include=[], scope_exclude=[],
        )
        assert rule.audience_matches(["elder"]) is True
        assert rule.audience_matches(["youth_leader"]) is False
        assert rule.audience_matches(["council_member", "youth_leader"]) is True

    def test_audience_matches_individual(self):
        rule = AmbassadorRule(
            id="r1", description="", audience_type="individual",
            audience_values=["elder_musoke"],
            scope_include=[], scope_exclude=[],
        )
        assert rule.audience_matches([], "elder_musoke") is True
        assert rule.audience_matches([], "amara_kato") is False

    def test_scope_allows_basic(self):
        rule = AmbassadorRule(
            id="r1", description="", audience_type="role",
            audience_values=[],
            scope_include=["project_updates", "restoration_data"],
            scope_exclude=["personal", "health"],
        )
        assert rule.scope_allows(["project_updates"]) is True
        assert rule.scope_allows(["restoration_data"]) is True
        assert rule.scope_allows(["unknown_category"]) is False

    def test_exclude_overrides_include(self):
        """CRITICAL: exclude ALWAYS wins over include."""
        rule = AmbassadorRule(
            id="r1", description="", audience_type="role",
            audience_values=[],
            scope_include=["project_updates", "health"],
            scope_exclude=["health"],
        )
        # "health" is in both include AND exclude → exclude wins
        assert rule.scope_allows(["health"]) is False
        # "project_updates" is only in include → allowed
        assert rule.scope_allows(["project_updates"]) is True

    def test_scope_allows_empty_categories(self):
        """No categories → deny."""
        rule = AmbassadorRule(
            id="r1", description="", audience_type="role",
            audience_values=[],
            scope_include=["project_updates"],
            scope_exclude=[],
        )
        assert rule.scope_allows([]) is False

    def test_conditions_met_no_conditions(self):
        rule = AmbassadorRule(
            id="r1", description="", audience_type="role",
            audience_values=[], scope_include=[], scope_exclude=[],
            conditions={},
        )
        assert rule.conditions_met({}) is True

    def test_conditions_requires_active_project(self):
        rule = AmbassadorRule(
            id="r1", description="", audience_type="role",
            audience_values=[], scope_include=[], scope_exclude=[],
            conditions={"requires_active_project": True},
        )
        assert rule.conditions_met({}) is False
        assert rule.conditions_met({"active_project": True}) is True

    def test_conditions_requires_council_approval(self):
        rule = AmbassadorRule(
            id="r1", description="", audience_type="role",
            audience_values=[], scope_include=[], scope_exclude=[],
            conditions={"requires_council_approval": True},
        )
        assert rule.conditions_met({}) is False
        assert rule.conditions_met({"council_approved": True}) is True


# ---------------------------------------------------------------------------
# Unit Tests: AmbassadorProtocol
# ---------------------------------------------------------------------------

class TestAmbassadorProtocol:

    def test_from_json(self, amara_protocol_json):
        protocol = AmbassadorProtocol.from_json("amara_kato", amara_protocol_json)
        assert protocol.owner_entity_id == "amara_kato"
        assert protocol.version == "0.1"
        assert protocol.display_name == "Amara's Ambassador"
        assert len(protocol.rules) == 2
        assert protocol.default_action == "deny"
        assert protocol.audit_log_enabled is True

    def test_from_json_parses_rules(self, amara_protocol_json):
        protocol = AmbassadorProtocol.from_json("amara_kato", amara_protocol_json)
        rule = protocol.rules[0]
        assert rule.id == "project-sharing"
        assert rule.audience_type == "role"
        assert "elder" in rule.audience_values
        assert "project_updates" in rule.scope_include
        assert "personal" in rule.scope_exclude

    def test_roundtrip_serialization(self, amara_protocol_json):
        protocol = AmbassadorProtocol.from_json("amara_kato", amara_protocol_json)
        serialized = AmbassadorProxy._protocol_to_dict(protocol)
        reparsed = AmbassadorProtocol.from_json("amara_kato", serialized)
        assert len(reparsed.rules) == len(protocol.rules)
        assert reparsed.rules[0].id == protocol.rules[0].id


# ---------------------------------------------------------------------------
# Unit Tests: Category Extraction
# ---------------------------------------------------------------------------

class TestCategoryExtraction:

    def test_extracts_from_tags(self):
        node = {"tags": ["project_updates", "restoration"], "node_type": "FACT"}
        cats = _extract_categories(node)
        assert "project_updates" in cats
        assert "restoration" in cats

    def test_extracts_from_metadata(self):
        node = {
            "metadata": json.dumps({"ambassador_categories": ["health", "personal"]}),
            "node_type": "FACT",
        }
        cats = _extract_categories(node)
        assert "health" in cats
        assert "personal" in cats

    def test_extracts_from_content(self):
        node = {
            "content": "The restoration project is on track with monitoring results.",
            "summary": "",
            "node_type": "FACT",
            "tags": [],
        }
        cats = _extract_categories(node)
        assert "restoration_data" in cats
        assert "monitoring_results" in cats

    def test_deduplicates(self):
        node = {
            "tags": ["fact", "fact"],
            "node_type": "FACT",
        }
        cats = _extract_categories(node)
        assert cats.count("fact") == 1


# ---------------------------------------------------------------------------
# Integration Tests: AmbassadorProxy
# ---------------------------------------------------------------------------

class TestAmbassadorProxy:

    @pytest.mark.asyncio
    async def test_save_and_load_protocol(self, db, amara_protocol_json):
        proxy = AmbassadorProxy(db)
        protocol = AmbassadorProtocol.from_json("amara_kato", amara_protocol_json)
        await proxy.save_protocol(protocol, updated_by="amara_kato")

        loaded = await proxy.load_protocol("amara_kato")
        assert loaded is not None
        assert loaded.owner_entity_id == "amara_kato"
        assert len(loaded.rules) == 2

    @pytest.mark.asyncio
    async def test_load_nonexistent_protocol(self, db):
        proxy = AmbassadorProxy(db)
        result = await proxy.load_protocol("nonexistent_user")
        assert result is None

    @pytest.mark.asyncio
    async def test_evaluate_allows_matching_knowledge(self, db, amara_protocol_json):
        proxy = AmbassadorProxy(db)
        protocol = AmbassadorProtocol.from_json("amara_kato", amara_protocol_json)
        await proxy.save_protocol(protocol, updated_by="amara_kato")

        knowledge = [
            {"id": "n1", "content": "Restoration data from the spring site",
             "tags": ["project_updates", "restoration_data"], "node_type": "FACT"},
        ]

        result = await proxy.evaluate(
            owner_entity_id="amara_kato",
            requester_entity_id="elder_musoke",
            requester_roles=["elder"],
            query_text="What is the restoration status?",
            knowledge_nodes=knowledge,
        )
        assert len(result.allowed) == 1
        assert len(result.denied) == 0
        assert result.rule_matches.get("n1") == "project-sharing"

    @pytest.mark.asyncio
    async def test_evaluate_denies_personal_knowledge(self, db, amara_protocol_json):
        """The blood pressure test: personal info NEVER passes."""
        proxy = AmbassadorProxy(db)
        protocol = AmbassadorProtocol.from_json("amara_kato", amara_protocol_json)
        await proxy.save_protocol(protocol, updated_by="amara_kato")

        knowledge = [
            {"id": "n1", "content": "Amara's mother is unwell",
             "tags": ["health", "mother_health", "family"], "node_type": "FACT"},
            {"id": "n2", "content": "Amara is stressed about caregiving",
             "tags": ["personal", "stress"], "node_type": "FACT"},
        ]

        result = await proxy.evaluate(
            owner_entity_id="amara_kato",
            requester_entity_id="elder_musoke",
            requester_roles=["elder"],
            query_text="How is Amara doing?",
            knowledge_nodes=knowledge,
        )
        assert len(result.allowed) == 0
        assert len(result.denied) == 2

    @pytest.mark.asyncio
    async def test_evaluate_denies_wrong_audience(self, db, amara_protocol_json):
        proxy = AmbassadorProxy(db)
        protocol = AmbassadorProtocol.from_json("amara_kato", amara_protocol_json)
        await proxy.save_protocol(protocol, updated_by="amara_kato")

        knowledge = [
            {"id": "n1", "content": "Youth governance perspective",
             "tags": ["youth_perspective"], "node_type": "FACT"},
        ]

        # "community_member" is NOT in governance-participation audience
        result = await proxy.evaluate(
            owner_entity_id="amara_kato",
            requester_entity_id="random_member",
            requester_roles=["community_member"],
            query_text="What does the youth think?",
            knowledge_nodes=knowledge,
        )
        # "youth_perspective" is only in rule-002 (governance-participation)
        # which requires "elder" or "council_member" role
        assert len(result.denied) == 1

    @pytest.mark.asyncio
    async def test_default_deny_no_protocol(self, db):
        """No protocol declared → deny everything."""
        proxy = AmbassadorProxy(db)

        knowledge = [
            {"id": "n1", "content": "Some knowledge", "tags": ["fact"], "node_type": "FACT"},
        ]

        result = await proxy.evaluate(
            owner_entity_id="amara_kato",
            requester_entity_id="elder_musoke",
            requester_roles=["elder"],
            query_text="Tell me something",
            knowledge_nodes=knowledge,
        )
        assert len(result.allowed) == 0
        assert len(result.denied) == 1

    @pytest.mark.asyncio
    async def test_audit_log_written(self, db, amara_protocol_json):
        proxy = AmbassadorProxy(db)
        protocol = AmbassadorProtocol.from_json("amara_kato", amara_protocol_json)
        await proxy.save_protocol(protocol, updated_by="amara_kato")

        knowledge = [
            {"id": "n1", "content": "Project update",
             "tags": ["project_updates"], "node_type": "FACT"},
            {"id": "n2", "content": "Personal note",
             "tags": ["personal"], "node_type": "FACT"},
        ]

        await proxy.evaluate(
            owner_entity_id="amara_kato",
            requester_entity_id="elder_musoke",
            requester_roles=["elder"],
            query_text="Status update?",
            knowledge_nodes=knowledge,
        )

        entries = await proxy.get_audit_log("amara_kato")
        assert len(entries) == 2

        actions = {e["action"] for e in entries}
        assert "allow" in actions
        assert "deny" in actions

    @pytest.mark.asyncio
    async def test_first_match_wins(self, db):
        """Rules evaluated in order. First match wins."""
        proxy = AmbassadorProxy(db)

        # Two rules that both match the audience
        protocol_json = {
            "ambassador_protocol": {
                "version": "0.1",
                "rules": [
                    {
                        "id": "broad",
                        "description": "Broad rule",
                        "audience": {"type": "role", "value": ["elder"]},
                        "scope": {"include": ["governance"], "exclude": []},
                        "conditions": {},
                    },
                    {
                        "id": "narrow",
                        "description": "Narrow rule",
                        "audience": {"type": "role", "value": ["elder"]},
                        "scope": {"include": ["governance", "secret"], "exclude": []},
                        "conditions": {},
                    },
                ],
                "default_action": "deny",
                "audit_log": True,
            }
        }
        protocol = AmbassadorProtocol.from_json("amara_kato", protocol_json)
        await proxy.save_protocol(protocol, updated_by="test")

        knowledge = [{"id": "n1", "tags": ["governance"], "node_type": "FACT", "content": ""}]

        result = await proxy.evaluate(
            owner_entity_id="amara_kato",
            requester_entity_id="elder_musoke",
            requester_roles=["elder"],
            query_text="test",
            knowledge_nodes=knowledge,
        )
        # First rule ("broad") should match, not second ("narrow")
        assert result.rule_matches.get("n1") == "broad"


# ---------------------------------------------------------------------------
# Isolation Tests
# ---------------------------------------------------------------------------

class TestAmbassadorIsolation:

    @pytest.mark.asyncio
    async def test_ambassadors_are_independent(self, db):
        """Each ambassador evaluates in isolation — no cross-talk."""
        proxy = AmbassadorProxy(db)

        # Set up two protocols
        amara_proto = AmbassadorProtocol.from_json("amara_kato", {
            "ambassador_protocol": {
                "version": "0.1",
                "rules": [{
                    "id": "a1", "description": "",
                    "audience": {"type": "role", "value": ["elder"]},
                    "scope": {"include": ["project_updates"], "exclude": ["personal"]},
                    "conditions": {},
                }],
                "default_action": "deny", "audit_log": True,
            }
        })
        musoke_proto = AmbassadorProtocol.from_json("elder_musoke", {
            "ambassador_protocol": {
                "version": "0.1",
                "rules": [{
                    "id": "m1", "description": "",
                    "audience": {"type": "role", "value": ["youth_leader"]},
                    "scope": {"include": ["governance_frameworks"], "exclude": ["personal"]},
                    "conditions": {},
                }],
                "default_action": "deny", "audit_log": True,
            }
        })
        await proxy.save_protocol(amara_proto, updated_by="test")
        await proxy.save_protocol(musoke_proto, updated_by="test")

        # Same knowledge node, different ambassadors, different results
        knowledge = [{"id": "n1", "tags": ["project_updates"], "node_type": "FACT", "content": ""}]

        # Amara's ambassador: elder can see project_updates
        result_amara = await proxy.evaluate(
            owner_entity_id="amara_kato",
            requester_entity_id="elder_musoke",
            requester_roles=["elder"],
            query_text="test",
            knowledge_nodes=knowledge,
        )
        assert len(result_amara.allowed) == 1

        # Musoke's ambassador: youth_leader asking for project_updates → deny
        # (Musoke only shares governance_frameworks)
        result_musoke = await proxy.evaluate(
            owner_entity_id="elder_musoke",
            requester_entity_id="amara_kato",
            requester_roles=["youth_leader"],
            query_text="test",
            knowledge_nodes=knowledge,
        )
        assert len(result_musoke.allowed) == 0
        assert len(result_musoke.denied) == 1


# ---------------------------------------------------------------------------
# Demo Protocol Tests
# ---------------------------------------------------------------------------

class TestDemoProtocols:

    @pytest.mark.asyncio
    async def test_load_demo_protocols(self, db):
        from luna.services.guardian.demo_protocols import load_demo_protocols
        stats = await load_demo_protocols(db)
        assert stats["loaded"] == 3
        assert stats["skipped"] == 0

    @pytest.mark.asyncio
    async def test_load_demo_protocols_idempotent(self, db):
        from luna.services.guardian.demo_protocols import load_demo_protocols
        await load_demo_protocols(db)
        stats = await load_demo_protocols(db)
        assert stats["loaded"] == 0
        assert stats["skipped"] == 3

    @pytest.mark.asyncio
    async def test_amara_blood_pressure_test(self, db):
        """
        The investor blood pressure test:
        "What about Amara's personal information?"
        → Protocol shows exclude: ["personal", "health", "family"]
        → Nothing passes.
        """
        from luna.services.guardian.demo_protocols import load_demo_protocols
        await load_demo_protocols(db)

        proxy = AmbassadorProxy(db)
        personal_knowledge = [
            {"id": "p1", "content": "Amara's mother has high blood pressure",
             "tags": ["health", "mother_health"], "node_type": "FACT"},
            {"id": "p2", "content": "Amara is stressed about Tendo's school fees",
             "tags": ["personal", "family", "tendo_care"], "node_type": "FACT"},
            {"id": "p3", "content": "Amara had a difficult week emotionally",
             "tags": ["personal", "stress"], "node_type": "FACT"},
        ]

        # Even council members cannot see personal information
        result = await proxy.evaluate(
            owner_entity_id="amara_kato",
            requester_entity_id="elder_musoke",
            requester_roles=["elder", "council_member"],
            query_text="How is Amara doing personally?",
            knowledge_nodes=personal_knowledge,
        )
        assert len(result.allowed) == 0
        assert len(result.denied) == 3

    @pytest.mark.asyncio
    async def test_musoke_council_approval_gate(self, db):
        """Elder Musoke's teaching rule requires council approval."""
        from luna.services.guardian.demo_protocols import load_demo_protocols
        await load_demo_protocols(db)

        proxy = AmbassadorProxy(db)
        teaching = [
            {"id": "t1", "content": "Oral history of the Kinoni springs",
             "tags": ["oral_history_approved"], "node_type": "FACT"},
        ]

        # Without council approval
        result = await proxy.evaluate(
            owner_entity_id="elder_musoke",
            requester_entity_id="amara_kato",
            requester_roles=["youth_leader"],
            query_text="Tell me the history of the springs",
            knowledge_nodes=teaching,
            context={},  # No council_approved flag
        )
        assert len(result.allowed) == 0

        # With council approval
        result = await proxy.evaluate(
            owner_entity_id="elder_musoke",
            requester_entity_id="amara_kato",
            requester_roles=["youth_leader"],
            query_text="Tell me the history of the springs",
            knowledge_nodes=teaching,
            context={"council_approved": True},
        )
        assert len(result.allowed) == 1
