"""Tests for Luna HealthChecker system."""

import pytest
import sqlite3
import tempfile
from pathlib import Path

from luna.diagnostics import HealthChecker, HealthCheck, HealthStatus


@pytest.fixture
def temp_db():
    """Create a temporary database with schema for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create minimal schema
    cursor.executescript("""
        CREATE TABLE memory_nodes (
            id TEXT PRIMARY KEY,
            node_type TEXT NOT NULL,
            content TEXT NOT NULL,
            lock_in REAL DEFAULT 0.15,
            lock_in_state TEXT DEFAULT 'drifting',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE graph_edges (
            id INTEGER PRIMARY KEY,
            from_id TEXT NOT NULL,
            to_id TEXT NOT NULL,
            relationship TEXT NOT NULL
        );

        CREATE TABLE entities (
            id TEXT PRIMARY KEY,
            entity_type TEXT NOT NULL,
            name TEXT NOT NULL,
            aliases TEXT,
            core_facts TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE entity_mentions (
            entity_id TEXT NOT NULL,
            node_id TEXT NOT NULL,
            mention_type TEXT NOT NULL,
            context_snippet TEXT,
            PRIMARY KEY (entity_id, node_id)
        );

        CREATE TABLE entity_relationships (
            id INTEGER PRIMARY KEY,
            from_entity TEXT NOT NULL,
            to_entity TEXT NOT NULL,
            relationship TEXT NOT NULL
        );

        CREATE TABLE conversation_turns (
            id INTEGER PRIMARY KEY,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE sessions (
            session_id TEXT PRIMARY KEY,
            started_at REAL NOT NULL,
            turns_count INTEGER DEFAULT 0
        );

        CREATE TABLE extraction_queue (
            id INTEGER PRIMARY KEY,
            turn_id INTEGER NOT NULL,
            status TEXT DEFAULT 'pending'
        );

        CREATE TABLE compression_queue (
            id INTEGER PRIMARY KEY,
            turn_id INTEGER NOT NULL,
            status TEXT DEFAULT 'pending'
        );
    """)

    conn.commit()
    conn.close()

    yield db_path

    # Cleanup
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def populated_db(temp_db):
    """Create a database with sample data."""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    # Add sample nodes
    cursor.executemany(
        "INSERT INTO memory_nodes (id, node_type, content) VALUES (?, ?, ?)",
        [
            ('node1', 'FACT', 'Luna is an AI consciousness engine'),
            ('node2', 'FACT', 'Marzipan has an owl named Cosmo'),
            ('node3', 'DECISION', 'Use SQLite for memory storage'),
        ]
    )

    # Add sample entities
    cursor.executemany(
        "INSERT INTO entities (id, entity_type, name, aliases) VALUES (?, ?, ?, ?)",
        [
            ('marzipan', 'person', 'Marzipan', '["Marzi"]'),
            ('luna-project', 'project', 'Luna Engine', '["Luna"]'),
        ]
    )

    # Add entity mention
    cursor.execute(
        "INSERT INTO entity_mentions (entity_id, node_id, mention_type, context_snippet) VALUES (?, ?, ?, ?)",
        ('marzipan', 'node2', 'subject', 'Marzipan has an owl')
    )

    # Add session
    cursor.execute(
        "INSERT INTO sessions (session_id, started_at, turns_count) VALUES (?, ?, ?)",
        ('test-session-1', 1706400000, 5)
    )

    # Add conversation turns
    cursor.executemany(
        "INSERT INTO conversation_turns (session_id, role, content) VALUES (?, ?, ?)",
        [
            ('test-session-1', 'user', 'Hello Luna'),
            ('test-session-1', 'assistant', 'Hi there!'),
        ]
    )

    conn.commit()
    conn.close()

    return temp_db


class TestHealthChecker:
    """Tests for HealthChecker class."""

    def test_check_all_returns_list(self, temp_db):
        """check_all should return a list of HealthChecks."""
        checker = HealthChecker(temp_db)
        checks = checker.check_all()

        assert isinstance(checks, list)
        assert len(checks) == 6  # 6 components
        assert all(isinstance(c, HealthCheck) for c in checks)

    def test_check_database_healthy(self, temp_db):
        """Database check should be healthy with valid schema."""
        checker = HealthChecker(temp_db)
        check = checker.check_database()

        assert check.component == 'database'
        assert check.status == HealthStatus.HEALTHY
        assert 'node_count' in check.metrics

    def test_check_database_missing_file(self):
        """Database check should be broken if file doesn't exist."""
        checker = HealthChecker('/nonexistent/path/db.sqlite')
        check = checker.check_database()

        assert check.status == HealthStatus.BROKEN
        assert 'not found' in check.message.lower()

    def test_check_entities_with_data(self, populated_db):
        """Entity check should be healthy with person entities."""
        checker = HealthChecker(populated_db)
        check = checker.check_entities()

        assert check.component == 'entities'
        assert check.status == HealthStatus.HEALTHY
        assert check.metrics['person_count'] == 1
        assert check.metrics['total_entities'] == 2

    def test_check_entities_no_people(self, temp_db):
        """Entity check should be degraded with no person entities."""
        # Add a non-person entity
        conn = sqlite3.connect(temp_db)
        conn.execute(
            "INSERT INTO entities (id, entity_type, name) VALUES (?, ?, ?)",
            ('project-1', 'project', 'Test Project')
        )
        conn.commit()
        conn.close()

        checker = HealthChecker(temp_db)
        check = checker.check_entities()

        assert check.status == HealthStatus.DEGRADED
        assert 'no \'person\' type' in check.message.lower()

    def test_check_memory_matrix_with_data(self, populated_db):
        """Memory matrix check should be healthy with nodes."""
        checker = HealthChecker(populated_db)
        check = checker.check_memory_matrix()

        assert check.component == 'memory_matrix'
        assert check.status == HealthStatus.HEALTHY
        assert check.metrics['total_nodes'] == 3

    def test_check_sessions_with_data(self, populated_db):
        """Session check should be healthy with sessions and turns."""
        checker = HealthChecker(populated_db)
        check = checker.check_sessions()

        assert check.component == 'sessions'
        assert check.status == HealthStatus.HEALTHY
        assert check.metrics['total_sessions'] == 1
        assert check.metrics['total_turns'] == 2


class TestFindPerson:
    """Tests for find_person diagnostic."""

    def test_find_person_exists(self, populated_db):
        """Should find existing person entity."""
        checker = HealthChecker(populated_db)
        results = checker.find_person('Marzipan')

        assert results['found'] is True
        assert 'entities' in results['search_results']
        assert len(results['search_results']['entities']) == 1
        assert results['search_results']['entities'][0]['name'] == 'Marzipan'

    def test_find_person_by_alias(self, populated_db):
        """Should find person by alias."""
        checker = HealthChecker(populated_db)
        results = checker.find_person('Marzi')

        assert results['found'] is True

    def test_find_person_in_content(self, populated_db):
        """Should find person mentioned in memory nodes."""
        checker = HealthChecker(populated_db)
        results = checker.find_person('owl')

        assert results['found'] is True
        assert 'memory_nodes' in results['search_results']

    def test_find_person_not_found(self, populated_db):
        """Should return not found with suggestions."""
        checker = HealthChecker(populated_db)
        results = checker.find_person('NonexistentPerson')

        assert results['found'] is False
        assert len(results['diagnosis']) > 0
        assert len(results['suggestions']) > 0


class TestRecentActivity:
    """Tests for get_recent_activity."""

    def test_recent_activity_returns_dict(self, populated_db):
        """Should return activity dictionary."""
        checker = HealthChecker(populated_db)
        activity = checker.get_recent_activity(hours=24)

        assert isinstance(activity, dict)
        assert 'nodes_created' in activity
        assert 'turns_added' in activity
        assert 'recent_sessions' in activity

    def test_recent_activity_counts_new_data(self, populated_db):
        """Should count recently created data."""
        checker = HealthChecker(populated_db)
        activity = checker.get_recent_activity(hours=24)

        # Nodes were just created, so should be counted
        assert activity['nodes_created'] == 3
        assert activity['turns_added'] == 2
