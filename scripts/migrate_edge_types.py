#!/usr/bin/env python3
"""
One-time migration: normalize all graph_edges relationship types to 8 canonical values.

Handoff #48 — Edge Type Cleanup (L2 prerequisite).

Run once:
    .venv/bin/python3 scripts/migrate_edge_types.py

What it does:
    1. Shows before-distribution
    2. For each non-canonical type, computes canonical mapping
    3. Handles UNIQUE(from_id, to_id, relationship) collisions:
       keeps edge with higher strength, deletes the other
    4. Runs UPDATE statements
    5. Shows after-distribution and verifies exactly 8 types remain
"""

import sqlite3
import sys
from pathlib import Path

# Add project root to path so we can import normalize_edge_type
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from luna.substrate.graph import normalize_edge_type, CANONICAL_EDGE_TYPES

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "user" / "luna_engine.db"


def show_distribution(conn: sqlite3.Connection, label: str) -> dict[str, int]:
    """Print edge type distribution and return it."""
    cur = conn.execute(
        "SELECT relationship, COUNT(*) as cnt FROM graph_edges "
        "GROUP BY relationship ORDER BY cnt DESC"
    )
    rows = cur.fetchall()
    total = sum(r[1] for r in rows)
    print(f"\n{'=' * 60}")
    print(f"  {label}  ({total} total edges, {len(rows)} distinct types)")
    print(f"{'=' * 60}")
    for rel, cnt in rows:
        pct = (cnt / total) * 100 if total else 0
        marker = "" if rel in CANONICAL_EDGE_TYPES else " ← NON-CANONICAL"
        print(f"  {rel:30s} {cnt:>6d}  ({pct:5.1f}%){marker}")
    return dict(rows)


def migrate(conn: sqlite3.Connection) -> None:
    """Run the full migration."""
    # Step 1: Get all non-canonical types
    cur = conn.execute("SELECT DISTINCT relationship FROM graph_edges")
    all_types = [r[0] for r in cur.fetchall()]
    non_canonical = [t for t in all_types if t not in CANONICAL_EDGE_TYPES]

    if not non_canonical:
        print("\nAll edges already canonical. Nothing to do.")
        return

    print(f"\nFound {len(non_canonical)} non-canonical types to normalize.")

    # Step 2: Group by target canonical type
    migrations: dict[str, list[str]] = {}  # canonical → [freeform types]
    for raw in non_canonical:
        target = normalize_edge_type(raw)
        migrations.setdefault(target, []).append(raw)

    for target, sources in sorted(migrations.items()):
        print(f"\n  → {target}:")
        for s in sources[:10]:
            print(f"      {s}")
        if len(sources) > 10:
            print(f"      ... and {len(sources) - 10} more")

    # Step 3: Handle UNIQUE collisions before UPDATE
    # The unique constraint is (from_id, to_id, relationship).
    # If node A→B has both 'works_on' and 'INVOLVES', and both map to
    # RELATES_TO, the UPDATE would violate the constraint. We need to
    # delete the weaker duplicate first.
    print("\n--- Checking for UNIQUE collisions ---")
    collision_deletes = 0

    for target, sources in migrations.items():
        if len(sources) < 2:
            # Also check collision with existing canonical edges
            pass

        # Find all edges that would collide after normalization
        # (same from_id, to_id, but different relationship → same target)
        all_source_types = sources.copy()
        # Also include the target itself (existing canonical edges)
        all_source_types.append(target)

        if len(all_source_types) < 2:
            continue

        placeholders = ",".join("?" * len(all_source_types))
        collision_query = f"""
            SELECT from_id, to_id, relationship, strength, rowid
            FROM graph_edges
            WHERE relationship IN ({placeholders})
            GROUP BY from_id, to_id
            HAVING COUNT(*) > 1
        """
        # Actually need a different approach — find duplicate (from_id, to_id) pairs
        dup_query = f"""
            SELECT from_id, to_id
            FROM graph_edges
            WHERE relationship IN ({placeholders})
            GROUP BY from_id, to_id
            HAVING COUNT(*) > 1
        """
        dups = conn.execute(dup_query, all_source_types).fetchall()

        for from_id, to_id in dups:
            # Get all edges for this pair that map to the same target
            edges = conn.execute(
                f"SELECT rowid, relationship, strength FROM graph_edges "
                f"WHERE from_id = ? AND to_id = ? AND relationship IN ({placeholders})",
                [from_id, to_id] + all_source_types,
            ).fetchall()

            if len(edges) <= 1:
                continue

            # Keep the one with highest strength, delete the rest
            edges_sorted = sorted(edges, key=lambda e: e[2], reverse=True)
            keep = edges_sorted[0]
            for discard in edges_sorted[1:]:
                conn.execute("DELETE FROM graph_edges WHERE rowid = ?", (discard[0],))
                collision_deletes += 1

    if collision_deletes:
        print(f"  Deleted {collision_deletes} weaker duplicate edges to avoid constraint violations.")
    else:
        print("  No collisions found.")

    # Step 4: Run UPDATE statements
    print("\n--- Running UPDATE statements ---")
    total_updated = 0

    for target, sources in migrations.items():
        for source in sources:
            cur = conn.execute(
                "UPDATE graph_edges SET relationship = ? WHERE relationship = ?",
                (target, source),
            )
            if cur.rowcount > 0:
                print(f"  {source:40s} → {target:15s} ({cur.rowcount} edges)")
                total_updated += cur.rowcount

    conn.commit()
    print(f"\nTotal edges updated: {total_updated}")
    print(f"Total duplicate edges removed: {collision_deletes}")


def verify(conn: sqlite3.Connection) -> bool:
    """Verify exactly 8 canonical types remain."""
    cur = conn.execute("SELECT DISTINCT relationship FROM graph_edges")
    remaining = sorted(r[0] for r in cur.fetchall())
    canonical_sorted = sorted(CANONICAL_EDGE_TYPES)

    if remaining == canonical_sorted:
        print(f"\n✓ VERIFIED: Exactly {len(remaining)} canonical types remain.")
        return True
    else:
        extra = set(remaining) - CANONICAL_EDGE_TYPES
        missing = CANONICAL_EDGE_TYPES - set(remaining)
        if extra:
            print(f"\n✗ FAILED: {len(extra)} non-canonical types remain: {extra}")
        if missing:
            print(f"  (Canonical types with 0 edges: {missing})")
        return False


def main():
    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        sys.exit(1)

    print(f"Database: {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH))

    # Before
    show_distribution(conn, "BEFORE MIGRATION")

    # Migrate
    migrate(conn)

    # After
    show_distribution(conn, "AFTER MIGRATION")

    # Verify
    ok = verify(conn)

    conn.close()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
