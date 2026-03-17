"""
Tests for the Luna Intent Layer — DirectiveEngine.

Tests cover:
- Seeding from YAML
- Loading armed directives
- Trigger evaluation (session_start, keyword, entity_mention, thread_resume)
- Cooldown enforcement
- Session fire limits
- Firing and recording
- Skill invocation
- Disable all emergency kill
- Re-arm fired directives
"""

import asyncio
import json
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio

# Ensure src is on path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from luna.agentic.directives import (
    DirectiveEngine,
    MAX_ARMED,
    MAX_FIRES_PER_SESSION,
    MIN_COOLDOWN_MINUTES,
)


@pytest.fixture
def db_path(tmp_path):
    """Create a temp DB with the quests table (intent layer schema)."""
    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.execute("""
        CREATE TABLE quests (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL CHECK(type IN (
                'main', 'side', 'contract', 'treasure_hunt', 'scavenger',
                'directive', 'skill'
            )),
            status TEXT NOT NULL DEFAULT 'available' CHECK(status IN (
                'available', 'active', 'complete', 'failed', 'expired',
                'armed', 'fired', 'disabled'
            )),
            priority TEXT DEFAULT 'medium',
            title TEXT NOT NULL,
            subtitle TEXT,
            objective TEXT NOT NULL,
            source TEXT,
            journal_prompt TEXT,
            target_lock_in REAL,
            reward_base REAL DEFAULT 0.15,
            investigation TEXT DEFAULT '{}',
            expires_at TEXT,
            completed_at TEXT,
            failed_at TEXT,
            fail_note TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            trigger_type TEXT,
            trigger_config TEXT,
            action TEXT,
            trust_tier TEXT DEFAULT 'confirm',
            authored_by TEXT DEFAULT 'system',
            approved_by TEXT,
            fire_count INTEGER DEFAULT 0,
            last_fired_at TEXT,
            cooldown_minutes INTEGER,
            steps TEXT,
            invocation_count INTEGER DEFAULT 0,
            last_invoked_at TEXT,
            tags_json TEXT DEFAULT '[]'
        )
    """)
    conn.commit()
    conn.close()
    return db


def _insert_directive(db_path, id, title, trigger_type, trigger_config=None,
                      action="surface_parked_threads", trust_tier="auto",
                      status="armed", cooldown_minutes=None):
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO quests (id, type, status, title, objective, trigger_type, "
        "trigger_config, action, trust_tier, authored_by, approved_by, "
        "cooldown_minutes, created_at, updated_at) "
        "VALUES (?, 'directive', ?, ?, ?, ?, ?, ?, ?, 'ahab', 'ahab', ?, "
        "datetime('now'), datetime('now'))",
        (id, status, title, title, trigger_type,
         json.dumps(trigger_config or {}), action, trust_tier, cooldown_minutes),
    )
    conn.commit()
    conn.close()


def _insert_skill(db_path, id, title, steps, tags=None):
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO quests (id, type, status, title, objective, steps, tags_json, "
        "authored_by, created_at, updated_at) "
        "VALUES (?, 'skill', 'available', ?, ?, ?, ?, 'ahab', "
        "datetime('now'), datetime('now'))",
        (id, title, title, json.dumps(steps), json.dumps(tags or [])),
    )
    conn.commit()
    conn.close()


# =============================================================================
# LOAD & EVALUATE
# =============================================================================


@pytest.mark.asyncio
async def test_load_armed(db_path):
    _insert_directive(db_path, "d1", "Test Dir", "session_start")
    _insert_directive(db_path, "d2", "Disabled", "session_start", status="disabled")

    de = DirectiveEngine(db_path)
    count = await de.load_armed()
    assert count == 1
    assert de._armed[0]["id"] == "d1"


@pytest.mark.asyncio
async def test_evaluate_session_start(db_path):
    _insert_directive(db_path, "d1", "Startup", "session_start")
    _insert_directive(db_path, "d2", "Keyword Only", "keyword",
                      trigger_config={"match": "test"})

    de = DirectiveEngine(db_path)
    await de.load_armed()
    matches = await de.evaluate_event("session_start", {})
    assert len(matches) == 1
    assert matches[0]["id"] == "d1"


@pytest.mark.asyncio
async def test_evaluate_keyword(db_path):
    _insert_directive(db_path, "d1", "Guardian Watch", "keyword",
                      trigger_config={"match": "guardian|rosa"})

    de = DirectiveEngine(db_path)
    await de.load_armed()

    matches = await de.evaluate_event("keyword", {"message": "tell me about guardian"})
    assert len(matches) == 1

    matches = await de.evaluate_event("keyword", {"message": "what is weather"})
    assert len(matches) == 0


@pytest.mark.asyncio
async def test_evaluate_keyword_case_insensitive(db_path):
    _insert_directive(db_path, "d1", "Test", "keyword",
                      trigger_config={"match": "GUARDIAN"})

    de = DirectiveEngine(db_path)
    await de.load_armed()
    matches = await de.evaluate_event("keyword", {"message": "guardian status"})
    assert len(matches) == 1


@pytest.mark.asyncio
async def test_evaluate_entity_mention(db_path):
    _insert_directive(db_path, "d1", "Entity Watch", "entity_mention",
                      trigger_config={"entities": ["Guardian", "ROSA"]})

    de = DirectiveEngine(db_path)
    await de.load_armed()

    matches = await de.evaluate_event("entity_mention", {"entities": ["guardian"]})
    assert len(matches) == 1

    matches = await de.evaluate_event("entity_mention", {"entities": ["Luna"]})
    assert len(matches) == 0


@pytest.mark.asyncio
async def test_evaluate_thread_resume(db_path):
    _insert_directive(db_path, "d1", "Thread Watch", "thread_resume",
                      trigger_config={"thread_topic_match": "guardian"})

    de = DirectiveEngine(db_path)
    await de.load_armed()

    matches = await de.evaluate_event("thread_resume",
                                       {"thread": {"topic": "Guardian Demo"}})
    assert len(matches) == 1

    matches = await de.evaluate_event("thread_resume",
                                       {"thread": {"topic": "Weather"}})
    assert len(matches) == 0


# =============================================================================
# COOLDOWN
# =============================================================================


@pytest.mark.asyncio
async def test_cooldown_blocks_repeat(db_path):
    _insert_directive(db_path, "d1", "Cooldown Test", "session_start",
                      cooldown_minutes=60)

    de = DirectiveEngine(db_path)
    await de.load_armed()

    # First should match
    matches = await de.evaluate_event("session_start", {})
    assert len(matches) == 1

    # Simulate fire (sets cooldown)
    de._cooldowns["d1"] = datetime.now()

    # Second should be blocked
    matches = await de.evaluate_event("session_start", {})
    assert len(matches) == 0


@pytest.mark.asyncio
async def test_cooldown_expires(db_path):
    _insert_directive(db_path, "d1", "Cooldown Test", "session_start",
                      cooldown_minutes=5)

    de = DirectiveEngine(db_path)
    await de.load_armed()

    # Set cooldown in the past
    de._cooldowns["d1"] = datetime.now() - timedelta(minutes=10)

    matches = await de.evaluate_event("session_start", {})
    assert len(matches) == 1


@pytest.mark.asyncio
async def test_min_cooldown_enforced(db_path):
    """Cooldown < MIN_COOLDOWN_MINUTES should be clamped."""
    _insert_directive(db_path, "d1", "Short Cooldown", "session_start",
                      cooldown_minutes=1)  # Less than MIN_COOLDOWN_MINUTES

    de = DirectiveEngine(db_path)
    await de.load_armed()

    # Set cooldown 2 minutes ago — below MIN_COOLDOWN_MINUTES
    de._cooldowns["d1"] = datetime.now() - timedelta(minutes=2)

    matches = await de.evaluate_event("session_start", {})
    assert len(matches) == 0  # Should be blocked by MIN_COOLDOWN_MINUTES


# =============================================================================
# SESSION FIRE LIMITS
# =============================================================================


@pytest.mark.asyncio
async def test_session_fire_limit(db_path):
    _insert_directive(db_path, "d1", "Fire Limit", "session_start")

    de = DirectiveEngine(db_path)
    await de.load_armed()

    # Simulate hitting the limit
    de._session_fire_counts["d1"] = MAX_FIRES_PER_SESSION

    matches = await de.evaluate_event("session_start", {})
    assert len(matches) == 0


# =============================================================================
# FIRING
# =============================================================================


@pytest.mark.asyncio
async def test_fire_records_to_db(db_path):
    _insert_directive(db_path, "d1", "Fire Test", "session_start")

    de = DirectiveEngine(db_path)
    await de.load_armed()

    result = await de.fire(de._armed[0], engine=None)
    assert result["directive_id"] == "d1"

    # Check DB
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM quests WHERE id = 'd1'").fetchone()
    assert row["status"] == "fired"
    assert row["fire_count"] == 1
    assert row["last_fired_at"] is not None
    conn.close()


@pytest.mark.asyncio
async def test_fire_updates_session_count(db_path):
    _insert_directive(db_path, "d1", "Count Test", "session_start")

    de = DirectiveEngine(db_path)
    await de.load_armed()
    await de.fire(de._armed[0], engine=None)

    assert de._session_fire_counts["d1"] == 1


# =============================================================================
# SKILLS
# =============================================================================


@pytest.mark.asyncio
async def test_get_skill(db_path):
    _insert_skill(db_path, "s1", "Guardian Demo Prep",
                  ["set_aperture:NARROW", "surface_parked_threads"])

    de = DirectiveEngine(db_path)
    skill = await de.get_skill("Guardian Demo")
    assert skill is not None
    assert skill["title"] == "Guardian Demo Prep"


@pytest.mark.asyncio
async def test_invoke_skill(db_path):
    _insert_skill(db_path, "s1", "My Skill",
                  ["surface_parked_threads", "surface_parked_threads"])

    de = DirectiveEngine(db_path)
    result = await de._invoke_skill("My Skill", engine=None)
    assert result["ok"] is True
    assert result["steps"] == 2

    # Check invocation recorded
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM quests WHERE id = 's1'").fetchone()
    assert row["invocation_count"] == 1
    conn.close()


@pytest.mark.asyncio
async def test_invoke_missing_skill(db_path):
    de = DirectiveEngine(db_path)
    result = await de._invoke_skill("nonexistent", engine=None)
    assert result["ok"] is False


# =============================================================================
# MANAGEMENT
# =============================================================================


@pytest.mark.asyncio
async def test_disable_all(db_path):
    _insert_directive(db_path, "d1", "A", "session_start")
    _insert_directive(db_path, "d2", "B", "keyword",
                      trigger_config={"match": "test"})

    de = DirectiveEngine(db_path)
    await de.load_armed()
    assert len(de._armed) == 2

    count = await de.disable_all()
    assert count == 2
    assert len(de._armed) == 0

    # Verify DB
    conn = sqlite3.connect(str(db_path))
    rows = conn.execute(
        "SELECT status FROM quests WHERE type = 'directive'"
    ).fetchall()
    assert all(r[0] == "disabled" for r in rows)
    conn.close()


@pytest.mark.asyncio
async def test_rearm_fired(db_path):
    _insert_directive(db_path, "d1", "Fired", "session_start", status="fired")

    de = DirectiveEngine(db_path)
    count = await de.rearm_fired()
    assert count == 1

    conn = sqlite3.connect(str(db_path))
    row = conn.execute("SELECT status FROM quests WHERE id = 'd1'").fetchone()
    assert row[0] == "armed"
    conn.close()


# =============================================================================
# SEEDING
# =============================================================================


@pytest.mark.asyncio
async def test_seed_from_yaml(db_path, tmp_path):
    yaml_content = """
schema_version: 1
seed_directives:
  - id: dir-test
    title: "Test Directive"
    objective: "Test"
    trigger_type: session_start
    trigger_config: {}
    action: "surface_parked_threads"
    trust_tier: auto
    authored_by: ahab
    approved_by: ahab
seed_skills:
  - id: skill-test
    title: "Test Skill"
    objective: "Test"
    steps:
      - "surface_parked_threads"
    tags: ["test"]
    authored_by: ahab
"""
    yaml_path = tmp_path / "seed.yaml"
    yaml_path.write_text(yaml_content)

    de = DirectiveEngine(db_path)
    result = await de.seed_from_yaml(yaml_path)
    assert result["directives"] == 1
    assert result["skills"] == 1
    assert result["skipped"] == 0

    # Re-seed should skip
    result2 = await de.seed_from_yaml(yaml_path)
    assert result2["skipped"] == 2

    # Force should replace
    result3 = await de.seed_from_yaml(yaml_path, force=True)
    assert result3["directives"] == 1
    assert result3["skills"] == 1


@pytest.mark.asyncio
async def test_seed_idempotent_count(db_path, tmp_path):
    """Seeding twice should not duplicate rows."""
    yaml_content = """
schema_version: 1
seed_directives:
  - id: dir-x
    title: "X"
    objective: "X"
    trigger_type: session_start
    action: "surface_parked_threads"
seed_skills: []
"""
    yaml_path = tmp_path / "seed.yaml"
    yaml_path.write_text(yaml_content)

    de = DirectiveEngine(db_path)
    await de.seed_from_yaml(yaml_path)
    await de.seed_from_yaml(yaml_path)

    conn = sqlite3.connect(str(db_path))
    count = conn.execute("SELECT COUNT(*) FROM quests").fetchone()[0]
    assert count == 1
    conn.close()
