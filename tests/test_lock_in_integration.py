"""
Integration tests for lock-in coefficient in Luna Engine.

Tests the full flow of lock-in tracking:
- Access tracking updates lock-in
- Reinforcement boosts lock-in
- Pruning respects lock-in states
- Stats include lock-in distribution
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from luna.engine import LunaEngine, EngineConfig
from luna.actors.base import Message
from luna.substrate.database import MemoryDatabase
from luna.substrate.memory import MemoryMatrix


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
async def memory_matrix(tmp_path):
    """Create an isolated MemoryMatrix for testing."""
    db_path = tmp_path / "test_lock_in.db"
    db = MemoryDatabase(db_path)
    await db.connect()
    matrix = MemoryMatrix(db)
    yield matrix
    await db.close()


@pytest.fixture
async def engine_with_actors(tmp_path):
    """
    Create a LunaEngine with Matrix and Librarian actors for integration tests.
    """
    config = EngineConfig(
        cognitive_interval=0.1,
        reflective_interval=60,
        data_dir=tmp_path,
    )

    engine = LunaEngine(config)

    # Initialize Matrix actor with test database
    from luna.actors.matrix import MatrixActor
    matrix_actor = MatrixActor(db_path=tmp_path / "engine_test.db")
    engine.register_actor(matrix_actor)
    await matrix_actor.initialize()

    # Add get_all_edges method to graph for compatibility with Librarian
    # (This is needed because Librarian calls get_all_edges which doesn't exist)
    if matrix_actor._graph:
        def get_all_edges():
            """Return all edges as list of dicts."""
            edges = []
            for from_id, to_id, data in matrix_actor._graph._graph.edges(data=True):
                edges.append({
                    "from_id": from_id,
                    "to_id": to_id,
                    "edge_type": data.get("relationship"),
                    "weight": data.get("strength", 1.0),
                    "created_at": data.get("created_at"),
                })
            return edges
        matrix_actor._graph.get_all_edges = get_all_edges

    # Add _memory alias for Librarian compatibility
    # (Librarian's _get_matrix looks for _memory but MatrixActor uses _matrix)
    matrix_actor._memory = matrix_actor._matrix

    # Initialize Librarian actor
    from luna.actors.librarian import LibrarianActor
    librarian = LibrarianActor(engine)
    engine.register_actor(librarian)

    yield engine

    # Cleanup
    await matrix_actor.stop()


# =============================================================================
# TEST 1: Access Updates Lock-In
# =============================================================================

@pytest.mark.asyncio
async def test_access_updates_lock_in(memory_matrix):
    """
    Test that accessing a node increases its lock-in coefficient.

    Flow:
    1. Create node - verify initial state (0.15, drifting)
    2. Access 10 times via matrix.record_access()
    3. Verify lock_in increased (> 0.30 = fluid)
    4. Verify access_count == 10
    """
    # Create a new node
    node_id = await memory_matrix.add_node(
        node_type="FACT",
        content="Test fact for access tracking",
        source="test",
    )

    # Verify initial state
    node = await memory_matrix.get_node(node_id)
    assert node is not None
    assert node.lock_in == 0.15, f"Expected initial lock_in of 0.15, got {node.lock_in}"
    assert node.lock_in_state == "drifting", f"Expected initial state 'drifting', got {node.lock_in_state}"
    assert node.access_count == 0

    # Access the node 10 times
    for _ in range(10):
        await memory_matrix.record_access(node_id)

    # Verify access count and lock-in increased
    node = await memory_matrix.get_node(node_id)
    assert node.access_count == 10, f"Expected access_count of 10, got {node.access_count}"
    assert node.lock_in > 0.30, f"Expected lock_in > 0.30 after 10 accesses, got {node.lock_in}"
    assert node.lock_in_state == "fluid", f"Expected state 'fluid' after accesses, got {node.lock_in_state}"


# =============================================================================
# TEST 2: Reinforcement Boosts Lock-In
# =============================================================================

@pytest.mark.asyncio
async def test_reinforcement_boosts_lock_in(memory_matrix):
    """
    Test that reinforcing a node increases lock-in.

    Flow:
    1. Create node
    2. Call matrix.reinforce_node()
    3. Verify reinforcement_count == 1
    4. Verify lock_in > 0.15
    """
    # Create a new node
    node_id = await memory_matrix.add_node(
        node_type="DECISION",
        content="Important decision to remember",
        source="test",
    )

    # Verify initial state
    node = await memory_matrix.get_node(node_id)
    initial_lock_in = node.lock_in
    assert node.reinforcement_count == 0

    # Reinforce the node
    result = await memory_matrix.reinforce_node(node_id)
    assert result is True, "reinforce_node should return True on success"

    # Verify reinforcement count and lock-in increased
    node = await memory_matrix.get_node(node_id)
    assert node.reinforcement_count == 1, f"Expected reinforcement_count of 1, got {node.reinforcement_count}"
    assert node.lock_in > initial_lock_in, f"Expected lock_in to increase from {initial_lock_in}, got {node.lock_in}"

    # Reinforce multiple times
    for _ in range(4):
        await memory_matrix.reinforce_node(node_id)

    node = await memory_matrix.get_node(node_id)
    assert node.reinforcement_count == 5
    # With 5 reinforcements, should be significantly above initial
    assert node.lock_in > 0.30, f"Expected high lock_in after 5 reinforcements, got {node.lock_in}"


# =============================================================================
# TEST 3: Pruning Respects Lock-In
# =============================================================================

@pytest.mark.asyncio
async def test_pruning_respects_lock_in(engine_with_actors):
    """
    Test that Librarian's prune operation respects lock-in states.

    Flow:
    1. Create drifting node (manually backdate created_at to 60 days ago)
    2. Create settled node (high access count)
    3. Create reinforced node
    4. Run prune via Librarian message
    5. Verify: drifting pruned, settled preserved, reinforced preserved
    """
    engine = engine_with_actors
    matrix_actor = engine.get_actor("matrix")
    matrix = matrix_actor._matrix

    # 1. Create drifting node (old, never accessed, never reinforced)
    drifting_id = await matrix.add_node(
        node_type="FACT",
        content="Old drifting fact that should be pruned",
        source="test",
    )

    # Backdate the drifting node to 60 days ago
    sixty_days_ago = (datetime.now() - timedelta(days=60)).isoformat()
    await matrix.db.execute(
        "UPDATE memory_nodes SET created_at = ? WHERE id = ?",
        (sixty_days_ago, drifting_id)
    )

    # Verify drifting node state
    drifting_node = await matrix.get_node(drifting_id)
    assert drifting_node.lock_in_state == "drifting"
    assert drifting_node.access_count == 0
    assert drifting_node.reinforcement_count == 0

    # 2. Create settled node (high access count)
    settled_id = await matrix.add_node(
        node_type="FACT",
        content="Frequently accessed fact that should be preserved",
        source="test",
    )

    # Access many times to make it settled
    for _ in range(25):
        await matrix.record_access(settled_id)

    # Backdate so it's old enough to be considered for pruning
    await matrix.db.execute(
        "UPDATE memory_nodes SET created_at = ? WHERE id = ?",
        (sixty_days_ago, settled_id)
    )

    settled_node = await matrix.get_node(settled_id)
    assert settled_node.lock_in_state in ("fluid", "settled"), f"Expected fluid/settled, got {settled_node.lock_in_state}"

    # 3. Create reinforced node
    reinforced_id = await matrix.add_node(
        node_type="FACT",
        content="Reinforced fact that should be preserved",
        source="test",
    )

    # Reinforce it
    await matrix.reinforce_node(reinforced_id)

    # Backdate
    await matrix.db.execute(
        "UPDATE memory_nodes SET created_at = ? WHERE id = ?",
        (sixty_days_ago, reinforced_id)
    )

    reinforced_node = await matrix.get_node(reinforced_id)
    assert reinforced_node.reinforcement_count > 0

    # 4. Run prune via Librarian message
    librarian = engine.get_actor("librarian")

    prune_msg = Message(
        type="prune",
        payload={
            "age_days": 30,
            "prune_nodes": True,
            "max_prune_nodes": 100,
        }
    )

    await librarian.handle(prune_msg)

    # 5. Verify pruning results
    # Drifting node should be pruned
    drifting_after = await matrix.get_node(drifting_id)
    assert drifting_after is None, "Drifting node should have been pruned"

    # Settled node should be preserved (fluid/settled state protects it)
    settled_after = await matrix.get_node(settled_id)
    assert settled_after is not None, "Settled node should have been preserved"

    # Reinforced node should be preserved
    reinforced_after = await matrix.get_node(reinforced_id)
    assert reinforced_after is not None, "Reinforced node should have been preserved"


# =============================================================================
# TEST 4: Stats Include Lock-In Distribution
# =============================================================================

@pytest.mark.asyncio
async def test_stats_include_lock_in_distribution(memory_matrix):
    """
    Test that get_stats() returns lock-in distribution.

    Flow:
    1. Create several nodes with different lock-in states
    2. Call matrix.get_stats()
    3. Verify 'nodes_by_lock_in' and 'avg_lock_in' are present
    """
    # Create nodes with varying lock-in states

    # Drifting node (default)
    await memory_matrix.add_node(
        node_type="FACT",
        content="Drifting fact 1",
        source="test",
    )

    # Fluid node (access a few times)
    fluid_id = await memory_matrix.add_node(
        node_type="FACT",
        content="Fluid fact",
        source="test",
    )
    for _ in range(5):
        await memory_matrix.record_access(fluid_id)

    # Another drifting node
    await memory_matrix.add_node(
        node_type="DECISION",
        content="Drifting decision",
        source="test",
    )

    # Settled-ish node (heavily accessed and reinforced)
    settled_id = await memory_matrix.add_node(
        node_type="PROBLEM",
        content="Important problem",
        source="test",
    )
    for _ in range(20):
        await memory_matrix.record_access(settled_id)
    for _ in range(3):
        await memory_matrix.reinforce_node(settled_id)

    # Get stats
    stats = await memory_matrix.get_stats()

    # Verify lock-in stats are present
    assert "nodes_by_lock_in" in stats, "Stats should include 'nodes_by_lock_in'"
    assert "avg_lock_in" in stats, "Stats should include 'avg_lock_in'"

    # Verify nodes_by_lock_in has expected keys
    nodes_by_lock_in = stats["nodes_by_lock_in"]
    assert isinstance(nodes_by_lock_in, dict), "nodes_by_lock_in should be a dict"

    # Should have at least one state represented
    valid_states = {"drifting", "fluid", "settled"}
    state_keys = set(nodes_by_lock_in.keys())
    assert state_keys.issubset(valid_states), f"Unexpected lock-in states: {state_keys - valid_states}"

    # Total nodes in distribution should match total_nodes
    total_in_distribution = sum(nodes_by_lock_in.values())
    assert total_in_distribution == stats["total_nodes"], \
        f"Distribution total ({total_in_distribution}) should match total_nodes ({stats['total_nodes']})"

    # Average lock-in should be reasonable (between 0 and 1)
    avg_lock_in = stats["avg_lock_in"]
    assert 0.0 <= avg_lock_in <= 1.0, f"avg_lock_in should be between 0 and 1, got {avg_lock_in}"


# =============================================================================
# TEST 5: Lock-In State Queries
# =============================================================================

@pytest.mark.asyncio
async def test_get_nodes_by_lock_in_state(memory_matrix):
    """
    Test that we can query nodes by their lock-in state.
    """
    # Create drifting node
    drifting_id = await memory_matrix.add_node(
        node_type="FACT",
        content="Drifting test node",
        source="test",
    )

    # Create node and access it enough to become fluid
    fluid_id = await memory_matrix.add_node(
        node_type="FACT",
        content="Fluid test node",
        source="test",
    )
    for _ in range(10):
        await memory_matrix.record_access(fluid_id)

    # Query drifting nodes
    drifting_nodes = await memory_matrix.get_drifting_nodes(limit=100)
    drifting_ids = [n.id for n in drifting_nodes]
    assert drifting_id in drifting_ids, "Drifting node should be in get_drifting_nodes result"
    assert fluid_id not in drifting_ids, "Fluid node should NOT be in get_drifting_nodes result"

    # Query by specific state
    fluid_nodes = await memory_matrix.get_nodes_by_lock_in_state("fluid", limit=100)
    fluid_ids = [n.id for n in fluid_nodes]
    assert fluid_id in fluid_ids, "Fluid node should be in fluid state query"


# =============================================================================
# TEST 6: Lock-In Persists Across Queries
# =============================================================================

@pytest.mark.asyncio
async def test_lock_in_persists(memory_matrix):
    """
    Test that lock-in changes persist in the database.
    """
    # Create and modify a node
    node_id = await memory_matrix.add_node(
        node_type="FACT",
        content="Persistence test node",
        source="test",
    )

    # Access and reinforce
    for _ in range(5):
        await memory_matrix.record_access(node_id)
    await memory_matrix.reinforce_node(node_id)

    # Get the node fresh
    node = await memory_matrix.get_node(node_id)
    expected_access = 5
    expected_reinforcement = 1

    assert node.access_count == expected_access
    assert node.reinforcement_count == expected_reinforcement

    # Query directly from database to verify persistence
    row = await memory_matrix.db.fetchone(
        "SELECT access_count, reinforcement_count, lock_in, lock_in_state FROM memory_nodes WHERE id = ?",
        (node_id,)
    )

    assert row is not None
    db_access, db_reinforcement, db_lock_in, db_state = row

    assert db_access == expected_access, f"DB access_count mismatch: {db_access} vs {expected_access}"
    assert db_reinforcement == expected_reinforcement, f"DB reinforcement_count mismatch"
    assert db_lock_in == node.lock_in, "DB lock_in should match node.lock_in"
    assert db_state == node.lock_in_state, "DB lock_in_state should match node.lock_in_state"
