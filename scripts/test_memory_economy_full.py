#!/usr/bin/env python3
"""
Full Memory Economy pipeline test.
Run AFTER all agents have completed their work.

Tests the complete Memory Economy integration:
1. Schema verification
2. ClusterManager CRUD
3. ClusteringEngine keyword extraction
4. LockInCalculator formula
5. ConstellationAssembler assembly
6. ClusterRetrieval integration
7. Overall statistics

Usage:
    PYTHONPATH=src python scripts/test_memory_economy_full.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_schema(db_path: str) -> bool:
    """Test 1: Verify cluster tables exist."""
    print("\n1. Testing schema...")
    import sqlite3

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name IN ('clusters', 'cluster_members', 'cluster_edges')
        ORDER BY name
    """)
    tables = [r[0] for r in cursor.fetchall()]
    conn.close()

    expected = ['cluster_edges', 'cluster_members', 'clusters']
    if tables == expected:
        print(f"   PASS: Tables exist: {tables}")
        return True
    else:
        print(f"   FAIL: Expected {expected}, found {tables}")
        return False


def test_cluster_manager(db_path: str) -> bool:
    """Test 2: ClusterManager CRUD operations."""
    print("\n2. Testing ClusterManager...")
    from luna.memory.cluster_manager import ClusterManager

    mgr = ClusterManager(db_path)

    # Create
    test_id = mgr.create_cluster(
        name="Pipeline Test Cluster",
        summary="Testing full Memory Economy pipeline",
        initial_lock_in=0.5
    )
    print(f"   Created cluster: {test_id[:8]}...")

    # Read
    cluster = mgr.get_cluster(test_id)
    if cluster is None:
        print("   FAIL: Could not read created cluster")
        return False

    if cluster.state != 'fluid':
        print(f"   FAIL: Expected 'fluid' state for lock_in=0.5, got '{cluster.state}'")
        mgr.delete_cluster(test_id)
        return False

    # Update
    mgr.update_lock_in(test_id, 0.9)
    cluster = mgr.get_cluster(test_id)
    if cluster.state != 'crystallized':
        print(f"   FAIL: Expected 'crystallized' state for lock_in=0.9, got '{cluster.state}'")
        mgr.delete_cluster(test_id)
        return False

    # Delete
    mgr.delete_cluster(test_id)
    if mgr.get_cluster(test_id) is not None:
        print("   FAIL: Cluster still exists after delete")
        return False

    print("   PASS: CRUD operations working")
    return True


def test_clustering_engine(db_path: str) -> bool:
    """Test 3: ClusteringEngine keyword extraction."""
    print("\n3. Testing ClusteringEngine...")
    from luna.memory.clustering_engine import ClusteringEngine

    engine = ClusteringEngine(db_path)

    # Test keyword extraction
    test_text = "Luna memory matrix architecture uses semantic clustering for knowledge organization"
    keywords = engine._extract_keywords(test_text)

    if len(keywords) == 0:
        print("   FAIL: No keywords extracted")
        return False

    # Check that stopwords are filtered
    stopwords_found = [kw for kw in keywords if kw in engine.stopwords]
    if stopwords_found:
        print(f"   FAIL: Stopwords in keywords: {stopwords_found}")
        return False

    print(f"   PASS: Keyword extraction working - {keywords[:5]}")
    return True


def test_lock_in_calculator(db_path: str) -> bool:
    """Test 4: LockInCalculator formula."""
    print("\n4. Testing LockInCalculator...")
    from luna.memory.lock_in import LockInCalculator
    from luna.memory.cluster_manager import ClusterManager

    mgr = ClusterManager(db_path)
    calc = LockInCalculator(db_path)

    # Create test cluster
    test_id = mgr.create_cluster(
        name="LockIn Test Cluster",
        summary="Testing lock-in calculation",
        initial_lock_in=0.3
    )

    # Calculate lock-in (should work even with no members)
    lock_in = calc.calculate_cluster_lock_in(test_id)

    # Should return a reasonable default for empty cluster
    if not (0.0 <= lock_in <= 1.0):
        print(f"   FAIL: Lock-in out of range: {lock_in}")
        mgr.delete_cluster(test_id)
        return False

    # Test update
    result = calc.update_cluster(test_id)
    if 'error' in result:
        print(f"   FAIL: Update failed: {result['error']}")
        mgr.delete_cluster(test_id)
        return False

    # Cleanup
    mgr.delete_cluster(test_id)

    print(f"   PASS: Lock-in calculation working - {lock_in:.3f}")
    return True


def test_constellation_assembler() -> bool:
    """Test 5: ConstellationAssembler assembly."""
    print("\n5. Testing ConstellationAssembler...")
    from luna.memory.constellation import ConstellationAssembler, Constellation
    from luna.memory.cluster_manager import Cluster

    assembler = ConstellationAssembler(max_tokens=3000)

    # Test with empty inputs
    constellation = assembler.assemble(clusters=[], nodes=[])
    if constellation.total_tokens != 0:
        print(f"   FAIL: Empty assembly should have 0 tokens, got {constellation.total_tokens}")
        return False

    # Test with mock data
    mock_cluster = Cluster(
        cluster_id="test-123",
        name="Test Cluster",
        summary="A test cluster for validation",
        lock_in=0.8,
        state="settled",
        created_at="2024-01-01",
        updated_at="2024-01-01",
        last_accessed_at=None,
        access_count=5,
        member_count=10,
        avg_node_lock_in=0.6,
        centroid_embedding=None
    )

    mock_clusters = [{'cluster': mock_cluster, 'relevance_score': 0.9}]
    mock_nodes = [
        {'node_type': 'FACT', 'content': 'Test content here', 'lock_in': 0.5},
        {'node_type': 'MEMORY', 'content': 'Another test memory', 'lock_in': 0.3},
    ]

    constellation = assembler.assemble(clusters=mock_clusters, nodes=mock_nodes)

    if constellation.assembly_stats['clusters_selected'] != 1:
        print(f"   FAIL: Expected 1 cluster selected, got {constellation.assembly_stats['clusters_selected']}")
        return False

    if constellation.assembly_stats['nodes_selected'] != 2:
        print(f"   FAIL: Expected 2 nodes selected, got {constellation.assembly_stats['nodes_selected']}")
        return False

    # Test formatting
    formatted = assembler.format_for_director(constellation)
    if "ACTIVE MEMORY CLUSTERS" not in formatted:
        print("   FAIL: Missing cluster section in formatted output")
        return False

    if "RELEVANT MEMORIES" not in formatted:
        print("   FAIL: Missing memories section in formatted output")
        return False

    print(f"   PASS: Assembly working - {constellation.assembly_stats}")
    return True


def test_cluster_retrieval(db_path: str) -> bool:
    """Test 6: ClusterRetrieval integration."""
    print("\n6. Testing ClusterRetrieval...")
    from luna.librarian.cluster_retrieval import ClusterRetrieval

    retrieval = ClusterRetrieval(db_path)

    # Test auto-activated clusters (high lock-in)
    auto = retrieval.get_auto_activated_clusters()
    print(f"   Auto-activated clusters (lock_in >= 0.8): {len(auto)}")

    # Test find relevant clusters with empty input
    relevant = retrieval.find_relevant_clusters(node_ids=[], top_k=5)
    if relevant:
        print(f"   FAIL: Should return empty for empty node_ids")
        return False

    print(f"   PASS: ClusterRetrieval working")
    return True


def test_stats(db_path: str) -> dict:
    """Test 7: Get Memory Economy statistics."""
    print("\n7. Memory Economy Stats...")
    from luna.memory.cluster_manager import ClusterManager

    mgr = ClusterManager(db_path)
    stats = mgr.get_stats()

    print(f"   Total clusters: {stats['total_clusters']}")
    print(f"   State distribution: {stats['state_distribution']}")
    print(f"   Average lock-in: {stats['avg_lock_in']:.3f}")
    print(f"   Total edges: {stats['total_edges']}")
    print(f"   Total memberships: {stats['total_memberships']}")

    return stats


def test_full_pipeline():
    """Run complete Memory Economy validation."""
    print("=" * 60)
    print("MEMORY ECONOMY - FULL PIPELINE TEST")
    print("=" * 60)

    db_path = str(Path(__file__).parent.parent / "data" / "luna_engine.db")

    if not Path(db_path).exists():
        print(f"\nERROR: Database not found at {db_path}")
        print("Run migration first: python scripts/migration_001_memory_economy.py")
        sys.exit(1)

    results = []

    # Run all tests
    results.append(("Schema", test_schema(db_path)))
    results.append(("ClusterManager", test_cluster_manager(db_path)))
    results.append(("ClusteringEngine", test_clustering_engine(db_path)))
    results.append(("LockInCalculator", test_lock_in_calculator(db_path)))
    results.append(("ConstellationAssembler", test_constellation_assembler()))
    results.append(("ClusterRetrieval", test_cluster_retrieval(db_path)))

    # Get stats (not a pass/fail test)
    stats = test_stats(db_path)

    # Summary
    print("\n" + "=" * 60)
    print("TEST RESULTS")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_passed = False
        print(f"  {name}: {status}")

    print("\n" + "=" * 60)
    if all_passed:
        print("ALL TESTS PASSED - Memory Economy is operational!")
    else:
        print("SOME TESTS FAILED - Check output above for details")
    print("=" * 60)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(test_full_pipeline())
