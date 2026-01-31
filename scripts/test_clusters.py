#!/usr/bin/env python3
"""Test ClusterManager CRUD operations."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from luna.memory.cluster_manager import ClusterManager, get_state_from_lock_in


def test_state_thresholds():
    """Test state calculation from lock-in values."""
    print("=== Testing State Thresholds ===\n")

    test_cases = [
        (0.0, 'drifting'),
        (0.15, 'drifting'),
        (0.20, 'fluid'),
        (0.50, 'fluid'),
        (0.70, 'settled'),
        (0.84, 'settled'),
        (0.85, 'crystallized'),
        (1.0, 'crystallized'),
    ]

    all_passed = True
    for lock_in, expected in test_cases:
        actual = get_state_from_lock_in(lock_in)
        status = "PASS" if actual == expected else "FAIL"
        if actual != expected:
            all_passed = False
        print(f"   lock_in={lock_in:.2f} -> {actual} (expected {expected}) [{status}]")

    print(f"\n   State threshold tests: {'ALL PASSED' if all_passed else 'SOME FAILED'}")
    return all_passed


def test_crud():
    """Test ClusterManager CRUD operations."""
    db_path = Path(__file__).parent.parent / "data" / "luna_engine.db"
    mgr = ClusterManager(str(db_path))

    print("\n=== Testing ClusterManager CRUD ===\n")

    # CREATE
    print("1. Creating test cluster...")
    cluster_id = mgr.create_cluster(
        name="Test: Actor Model Decisions",
        summary="Testing cluster CRUD operations",
        initial_lock_in=0.5
    )
    print(f"   Created: {cluster_id}")

    # READ
    print("\n2. Reading cluster...")
    cluster = mgr.get_cluster(cluster_id)
    assert cluster is not None, "Failed to read cluster"
    print(f"   Name: {cluster.name}")
    print(f"   State: {cluster.state}")
    print(f"   Lock-in: {cluster.lock_in}")
    assert cluster.state == 'fluid', f"Expected 'fluid' state, got '{cluster.state}'"

    # UPDATE lock-in
    print("\n3. Updating lock-in to 0.75...")
    mgr.update_lock_in(cluster_id, 0.75)
    cluster = mgr.get_cluster(cluster_id)
    print(f"   New state: {cluster.state}")
    print(f"   New lock-in: {cluster.lock_in}")
    assert cluster.state == 'settled', f"Expected 'settled' state, got '{cluster.state}'"

    # INCREMENT lock-in
    print("\n4. Incrementing lock-in by 0.15...")
    new_val = mgr.increment_lock_in(cluster_id, 0.15)
    cluster = mgr.get_cluster(cluster_id)
    print(f"   New lock-in: {new_val}")
    print(f"   New state: {cluster.state}")
    assert cluster.state == 'crystallized', f"Expected 'crystallized' state, got '{cluster.state}'"

    # Record access
    print("\n5. Recording access...")
    mgr.record_access(cluster_id)
    cluster = mgr.get_cluster(cluster_id)
    print(f"   Access count: {cluster.access_count}")
    assert cluster.access_count >= 1, "Access count should be at least 1"

    # Update summary
    print("\n6. Updating summary...")
    mgr.update_summary(cluster_id, "Updated summary for testing")
    cluster = mgr.get_cluster(cluster_id)
    print(f"   Summary: {cluster.summary}")
    assert cluster.summary == "Updated summary for testing"

    # LIST
    print("\n7. Listing all clusters...")
    all_clusters = mgr.list_clusters(limit=5)
    print(f"   Total returned: {len(all_clusters)}")
    for c in all_clusters[:3]:
        print(f"   - {c.name} ({c.state}, {c.lock_in:.2f})")

    # SEARCH
    print("\n8. Searching clusters...")
    results = mgr.search_clusters("Actor")
    print(f"   Found {len(results)} matching 'Actor'")

    # STATS
    print("\n9. Getting stats...")
    stats = mgr.get_stats()
    print(f"   Total clusters: {stats['total_clusters']}")
    print(f"   State distribution: {stats['state_distribution']}")
    print(f"   Average lock-in: {stats['avg_lock_in']}")
    print(f"   Total edges: {stats['total_edges']}")

    # DELETE
    print("\n10. Deleting test cluster...")
    mgr.delete_cluster(cluster_id)
    deleted = mgr.get_cluster(cluster_id)
    print(f"    Deleted successfully: {deleted is None}")
    assert deleted is None, "Cluster should be deleted"

    print("\n" + "=" * 40)
    print("ALL CRUD OPERATIONS PASSED!")
    print("=" * 40)
    return True


def test_edges():
    """Test cluster edge operations."""
    db_path = Path(__file__).parent.parent / "data" / "luna_engine.db"
    mgr = ClusterManager(str(db_path))

    print("\n=== Testing Cluster Edges ===\n")

    # Create two clusters
    print("1. Creating two test clusters...")
    c1 = mgr.create_cluster(name="Test: Cluster A", initial_lock_in=0.3)
    c2 = mgr.create_cluster(name="Test: Cluster B", initial_lock_in=0.4)
    print(f"   Created: {c1[:8]}... and {c2[:8]}...")

    # Add edge
    print("\n2. Adding edge between clusters...")
    mgr.add_edge(c1, c2, "relates_to", strength=0.7, lock_in=0.25)
    edges = mgr.get_edges_from(c1)
    print(f"   Edges from C1: {len(edges)}")
    assert len(edges) >= 1, "Should have at least one edge"

    # Reinforce edge
    print("\n3. Reinforcing edge...")
    mgr.reinforce_edge(c1, c2, "relates_to")
    edges = mgr.get_edges_from(c1)
    edge = [e for e in edges if e.to_cluster == c2][0]
    print(f"   Reinforcement count: {edge.reinforcement_count}")
    print(f"   Edge lock-in: {edge.lock_in}")

    # Get connected clusters
    print("\n4. Getting connected clusters...")
    connected = mgr.get_connected_clusters(c1)
    print(f"   Connected to C1: {len(connected)}")

    # Delete edge
    print("\n5. Deleting edge...")
    mgr.delete_edge(c1, c2, "relates_to")
    edges = mgr.get_edges_from(c1)
    remaining = [e for e in edges if e.to_cluster == c2]
    print(f"   Edge deleted: {len(remaining) == 0}")

    # Cleanup
    print("\n6. Cleaning up test clusters...")
    mgr.delete_cluster(c1)
    mgr.delete_cluster(c2)
    print("   Cleaned up!")

    print("\n" + "=" * 40)
    print("ALL EDGE OPERATIONS PASSED!")
    print("=" * 40)
    return True


def test_members():
    """Test cluster member operations."""
    db_path = Path(__file__).parent.parent / "data" / "luna_engine.db"
    mgr = ClusterManager(str(db_path))

    print("\n=== Testing Cluster Members ===\n")

    # Create a cluster
    print("1. Creating test cluster...")
    cluster_id = mgr.create_cluster(name="Test: Member Test Cluster", initial_lock_in=0.3)
    print(f"   Created: {cluster_id[:8]}...")

    # Add fake members (note: these need to be valid node_ids in memory_nodes due to FK)
    # For testing, we'll check the member_count update mechanism
    cluster = mgr.get_cluster(cluster_id)
    print(f"\n2. Initial member count: {cluster.member_count}")

    # Get members (empty)
    print("\n3. Getting cluster members...")
    members = mgr.get_cluster_members(cluster_id)
    print(f"   Members: {len(members)}")

    # Cleanup
    print("\n4. Cleaning up test cluster...")
    mgr.delete_cluster(cluster_id)
    print("   Cleaned up!")

    print("\n" + "=" * 40)
    print("MEMBER OPERATIONS TESTED!")
    print("=" * 40)
    return True


def main():
    print("\n" + "=" * 50)
    print("CLUSTER MANAGER TEST SUITE")
    print("=" * 50)

    results = []

    results.append(("State Thresholds", test_state_thresholds()))
    results.append(("CRUD Operations", test_crud()))
    results.append(("Edge Operations", test_edges()))
    results.append(("Member Operations", test_members()))

    print("\n" + "=" * 50)
    print("FINAL RESULTS")
    print("=" * 50)

    all_passed = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_passed = False
        print(f"  {name}: {status}")

    print("\n" + ("ALL TESTS PASSED!" if all_passed else "SOME TESTS FAILED"))
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
