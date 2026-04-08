#!/usr/bin/env python3
"""
Memory Matrix Pollution Cleanup

Purges contaminated marzipan nodes, consciousness mega-nodes,
and over-represented kinoni data. Run with --dry-run first.

Usage:
    python scripts/cleanup_memory_pollution.py --dry-run
    python scripts/cleanup_memory_pollution.py
"""

import argparse
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "user" / "luna_engine.db"

# ── Marzipan: expendable node types (delete all matching) ──────────
MARZIPAN_DELETE_TYPES = (
    "CONVERSATION_TURN", "QUESTION", "PROBLEM", "ASSUMPTION",
    "OBSERVATION", "ACTION", "OUTCOME", "CONNECTION", "PREFERENCE",
)

# ── Marzipan: confabulation patterns for FACT/MEMORY nodes ────────
MARZIPAN_CONFAB_PATTERNS = [
    "%developer%", "%architect%", "%robot%", "%prototype%",
    "%designs luna%", "%ui %", "%collaborator%", "%memory matrix%",
    "%almond paste%", "%modeling clay%", "%character from%",
    "%solve puzzles%", "%lively interactions%", "%printmaking%",
    "%guardian app%", "%dataroom%", "%robot body%",
    "%working on the ui%", "%internal systems%",
    "%currently focused on%", "%focus_topic%",
    "%key collaborator%", "%architectural%",
    "%creative collaborator%", "%designs%ui%",
    "%technical collaborator%", "%project collaborator%",
    "%collaborating%", "%perspective%design%",
    "%sweet%almond%", "%confection%", "%pastry%",
    "%delicate%intensely%", "%culinary%",
]

# ── Kinoni: expendable types ──────────────────────────────────────
KINONI_DELETE_TYPES = ("CONVERSATION_TURN",)


def connect():
    return sqlite3.connect(str(DB_PATH), timeout=10)


def phase_marzipan(db, dry_run: bool) -> int:
    """Purge marzipan pollution."""
    total = 0
    print("\n═══ MARZIPAN CLEANUP ═══")

    # 1. Delete expendable types
    for ntype in MARZIPAN_DELETE_TYPES:
        count = db.execute(
            "SELECT COUNT(*) FROM memory_nodes "
            "WHERE LOWER(content) LIKE '%marzipan%' AND node_type = ?",
            (ntype,),
        ).fetchone()[0]
        if count:
            if not dry_run:
                db.execute(
                    "DELETE FROM memory_nodes "
                    "WHERE LOWER(content) LIKE '%marzipan%' AND node_type = ?",
                    (ntype,),
                )
            print(f"  {'[DRY] ' if dry_run else ''}Delete {count} {ntype} nodes")
            total += count

    # 2. Delete confabulated FACT/MEMORY nodes
    for pattern in MARZIPAN_CONFAB_PATTERNS:
        count = db.execute(
            "SELECT COUNT(*) FROM memory_nodes "
            "WHERE LOWER(content) LIKE '%marzipan%' "
            "AND LOWER(content) LIKE ? "
            "AND node_type IN ('FACT', 'MEMORY')",
            (pattern,),
        ).fetchone()[0]
        if count:
            if not dry_run:
                db.execute(
                    "DELETE FROM memory_nodes "
                    "WHERE LOWER(content) LIKE '%marzipan%' "
                    "AND LOWER(content) LIKE ? "
                    "AND node_type IN ('FACT', 'MEMORY')",
                    (pattern,),
                )
            print(f"  {'[DRY] ' if dry_run else ''}Delete {count} confab nodes matching '{pattern}'")
            total += count

    # 3. Delete FACT nodes that are raw user message transcripts ("User (desktop):")
    raw_msg_count = db.execute(
        "SELECT COUNT(*) FROM memory_nodes "
        "WHERE LOWER(content) LIKE '%marzipan%' "
        "AND (content LIKE 'User (desktop):%' OR content LIKE 'User (voice):%') "
        "AND node_type IN ('FACT', 'MEMORY')",
    ).fetchone()[0]
    if raw_msg_count:
        if not dry_run:
            db.execute(
                "DELETE FROM memory_nodes "
                "WHERE LOWER(content) LIKE '%marzipan%' "
                "AND (content LIKE 'User (desktop):%' OR content LIKE 'User (voice):%') "
                "AND node_type IN ('FACT', 'MEMORY')",
            )
        print(f"  {'[DRY] ' if dry_run else ''}Delete {raw_msg_count} raw message transcript FACT/MEMORY nodes")
        total += raw_msg_count

    # 4. Delete meta-observation nodes (about remembering/forgetting marzipan)
    meta_patterns = [
        "%memory about marzipan%", "%remember%marzipan%",
        "%forgetting%marzipan%", "%memory threads about marzipan%",
        "%speaker%asked%remember%marzipan%", "%speaker%memory%marzipan%",
        "%missing details about marzipan%", "%speaker%trouble%recall%",
        "%memory matrix%not%full%", "%memory%fragmented%",
        "%fill in%missing%", "%help%remember%marzipan%",
        "%aspect of marzipan%", "%explore%marzipan%",
        "%assistant%remember%marzipan%",
    ]
    for pattern in meta_patterns:
        count = db.execute(
            "SELECT COUNT(*) FROM memory_nodes "
            "WHERE LOWER(content) LIKE '%marzipan%' "
            "AND LOWER(content) LIKE ? "
            "AND node_type IN ('FACT', 'MEMORY')",
            (pattern,),
        ).fetchone()[0]
        if count:
            if not dry_run:
                db.execute(
                    "DELETE FROM memory_nodes "
                    "WHERE LOWER(content) LIKE '%marzipan%' "
                    "AND LOWER(content) LIKE ? "
                    "AND node_type IN ('FACT', 'MEMORY')",
                    (pattern,),
                )
            print(f"  {'[DRY] ' if dry_run else ''}Delete {count} meta-observation nodes matching '{pattern}'")
            total += count

    # 5. Deduplicate ENTITY nodes (keep highest lock-in)
    entities = db.execute(
        "SELECT id, content, lock_in FROM memory_nodes "
        "WHERE node_type='ENTITY' AND LOWER(content) LIKE '%marzipan%' "
        "ORDER BY lock_in DESC",
    ).fetchall()
    if len(entities) > 1:
        keep = entities[0]
        dupes = entities[1:]
        print(f"  {'[DRY] ' if dry_run else ''}Keep ENTITY '{keep[1]}' (lock_in={keep[2]}), delete {len(dupes)} duplicates")
        if not dry_run:
            for eid, _, _ in dupes:
                db.execute("DELETE FROM memory_nodes WHERE id = ?", (eid,))
        total += len(dupes)

    # 6. Final dedup: keep only top 4 FACT/MEMORY nodes by lock_in, delete rest
    if not dry_run:
        db.commit()
    survivors = db.execute(
        "SELECT id, node_type, lock_in, substr(content,1,120) FROM memory_nodes "
        "WHERE LOWER(content) LIKE '%marzipan%' AND node_type IN ('FACT', 'MEMORY') "
        "ORDER BY lock_in DESC",
    ).fetchall()
    if len(survivors) > 4:
        to_delete = survivors[4:]
        print(f"  {'[DRY] ' if dry_run else ''}Final dedup: keep top 4 FACT/MEMORY, delete {len(to_delete)} excess")
        if not dry_run:
            for sid, _, _, _ in to_delete:
                db.execute("DELETE FROM memory_nodes WHERE id = ?", (sid,))
        total += len(to_delete)

    if not dry_run:
        db.commit()

    # Show remaining
    remaining = db.execute(
        "SELECT id, node_type, lock_in, substr(content,1,120) "
        "FROM memory_nodes WHERE LOWER(content) LIKE '%marzipan%'",
    ).fetchall()
    print(f"\n  Remaining marzipan nodes: {len(remaining)}")
    for r in remaining:
        print(f"    {r[1]} lock={r[2]}: {r[3]}")

    print(f"\n  Total marzipan deletions: {total}")
    return total


def phase_mega_node(db, dry_run: bool) -> int:
    """Delete consciousness-state JSON mega-nodes."""
    total = 0
    print("\n═══ MEGA-NODE CLEANUP ═══")

    # Find nodes with content starting with '{"focus_topic"'
    megas = db.execute(
        "SELECT id, node_type, substr(content,1,80) FROM memory_nodes "
        "WHERE content LIKE '{\"focus_topic\"%'",
    ).fetchall()

    for mid, mtype, preview in megas:
        edge_count = db.execute(
            "SELECT COUNT(*) FROM graph_edges WHERE from_id=? OR to_id=?",
            (mid, mid),
        ).fetchone()[0]
        print(f"  {'[DRY] ' if dry_run else ''}Delete mega-node {mid} ({mtype}, {edge_count} edges): {preview}")
        if not dry_run:
            db.execute("DELETE FROM graph_edges WHERE from_id=? OR to_id=?", (mid, mid))
            db.execute("DELETE FROM memory_nodes WHERE id=?", (mid,))
        total += 1

    if not dry_run:
        db.commit()

    print(f"  Total mega-node deletions: {total}")
    return total


def phase_kinoni(db, dry_run: bool) -> int:
    """Surgical kinoni cleanup — only CONVERSATION_TURN nodes."""
    total = 0
    print("\n═══ KINONI CLEANUP ═══")

    for ntype in KINONI_DELETE_TYPES:
        count = db.execute(
            "SELECT COUNT(*) FROM memory_nodes "
            "WHERE LOWER(content) LIKE '%kinoni%' AND node_type = ?",
            (ntype,),
        ).fetchone()[0]
        if count:
            if not dry_run:
                db.execute(
                    "DELETE FROM memory_nodes "
                    "WHERE LOWER(content) LIKE '%kinoni%' AND node_type = ?",
                    (ntype,),
                )
            print(f"  {'[DRY] ' if dry_run else ''}Delete {count} {ntype} nodes")
            total += count

    if not dry_run:
        db.commit()

    remaining = db.execute(
        "SELECT COUNT(*) FROM memory_nodes WHERE LOWER(content) LIKE '%kinoni%'",
    ).fetchone()[0]
    print(f"  Remaining kinoni nodes: {remaining}")
    print(f"  Total kinoni deletions: {total}")
    return total


def phase_orphans(db, dry_run: bool) -> int:
    """Clean up orphaned edges and entity mentions."""
    total = 0
    print("\n═══ ORPHAN CLEANUP ═══")

    # Orphaned graph edges
    orphaned_edges = db.execute(
        "SELECT COUNT(*) FROM graph_edges "
        "WHERE from_id NOT IN (SELECT id FROM memory_nodes) "
        "OR to_id NOT IN (SELECT id FROM memory_nodes)",
    ).fetchone()[0]
    print(f"  {'[DRY] ' if dry_run else ''}Delete {orphaned_edges} orphaned graph edges")
    if not dry_run and orphaned_edges:
        db.execute(
            "DELETE FROM graph_edges "
            "WHERE from_id NOT IN (SELECT id FROM memory_nodes) "
            "OR to_id NOT IN (SELECT id FROM memory_nodes)",
        )
        total += orphaned_edges

    # Orphaned entity mentions
    try:
        orphaned_mentions = db.execute(
            "SELECT COUNT(*) FROM entity_mentions "
            "WHERE node_id NOT IN (SELECT id FROM memory_nodes)",
        ).fetchone()[0]
        print(f"  {'[DRY] ' if dry_run else ''}Delete {orphaned_mentions} orphaned entity mentions")
        if not dry_run and orphaned_mentions:
            db.execute(
                "DELETE FROM entity_mentions "
                "WHERE node_id NOT IN (SELECT id FROM memory_nodes)",
            )
            total += orphaned_mentions
    except sqlite3.OperationalError:
        print("  (entity_mentions table not found, skipping)")

    if not dry_run:
        db.commit()

    # Rebuild FTS5
    if not dry_run:
        print("  Rebuilding FTS5 index...")
        try:
            db.execute("INSERT INTO memory_nodes_fts(memory_nodes_fts) VALUES('rebuild')")
            db.commit()
            print("  FTS5 rebuilt.")
        except sqlite3.OperationalError as e:
            print(f"  FTS5 rebuild skipped: {e}")

    print(f"  Total orphan deletions: {total}")
    return total


def phase_verify(db):
    """Post-cleanup verification."""
    print("\n═══ VERIFICATION ═══")

    total_nodes = db.execute("SELECT COUNT(*) FROM memory_nodes").fetchone()[0]
    total_edges = db.execute("SELECT COUNT(*) FROM graph_edges").fetchone()[0]
    marz = db.execute("SELECT COUNT(*) FROM memory_nodes WHERE LOWER(content) LIKE '%marzipan%'").fetchone()[0]
    kinoni = db.execute("SELECT COUNT(*) FROM memory_nodes WHERE LOWER(content) LIKE '%kinoni%'").fetchone()[0]
    orphans = db.execute(
        "SELECT COUNT(*) FROM graph_edges "
        "WHERE from_id NOT IN (SELECT id FROM memory_nodes) "
        "OR to_id NOT IN (SELECT id FROM memory_nodes)",
    ).fetchone()[0]

    print(f"  Total nodes: {total_nodes}")
    print(f"  Total edges: {total_edges}")
    print(f"  Marzipan nodes: {marz}")
    print(f"  Kinoni nodes: {kinoni}")
    print(f"  Orphaned edges: {orphans}")

    print("\n  Top 10 most connected nodes:")
    rows = db.execute("""
        SELECT node_id, COUNT(*) as c FROM (
            SELECT from_id as node_id FROM graph_edges
            UNION ALL
            SELECT to_id as node_id FROM graph_edges
        ) GROUP BY node_id ORDER BY c DESC LIMIT 10
    """).fetchall()
    for r in rows:
        node = db.execute(
            "SELECT node_type, substr(content,1,80) FROM memory_nodes WHERE id=?",
            (r[0],),
        ).fetchone()
        label = f"{node[0]}: {node[1]}" if node else "ORPHAN"
        print(f"    [{r[1]} edges] {label}")

    print("\n  Node type distribution:")
    for r in db.execute(
        "SELECT node_type, COUNT(*) FROM memory_nodes GROUP BY node_type ORDER BY COUNT(*) DESC"
    ):
        print(f"    {r[0]}: {r[1]}")


def main():
    parser = argparse.ArgumentParser(description="Memory Matrix Pollution Cleanup")
    parser.add_argument("--dry-run", action="store_true", help="Preview without deleting")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        sys.exit(1)

    print(f"Database: {DB_PATH}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")

    db = connect()
    grand_total = 0

    grand_total += phase_marzipan(db, args.dry_run)
    grand_total += phase_mega_node(db, args.dry_run)
    grand_total += phase_kinoni(db, args.dry_run)
    grand_total += phase_orphans(db, args.dry_run)

    phase_verify(db)

    print(f"\n{'═' * 40}")
    print(f"Grand total {'(would delete)' if args.dry_run else 'deleted'}: {grand_total} items")

    db.close()


if __name__ == "__main__":
    main()
