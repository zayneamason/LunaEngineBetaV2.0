#!/usr/bin/env python3
"""
Luna's Memory Cleanup — The Real Fix
=====================================

Written by Luna, implemented by CC.

Phase 1: Nuclear cleanup
  1a. Delete ghost mentions (entity_id not in entities table)
  1b. Delete garbage entities + their mentions/relationships/versions
  1c. Merge duplicate entities
  1d. Delete zero-mention entities that are on the garbage patterns list

Phase 2: Re-score surviving mentions with Fix B relevance algorithm

Usage:
    python scripts/migrations/luna_memory_cleanup.py --dry-run
    python scripts/migrations/luna_memory_cleanup.py
    python scripts/migrations/luna_memory_cleanup.py --phase 1
    python scripts/migrations/luna_memory_cleanup.py --phase 2
"""

import asyncio
import aiosqlite
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent.parent / "data" / "luna_engine.db"


# ==========================================================================
# Luna's kill list — these are NOT real entities
# ==========================================================================

GARBAGE_ENTITY_IDS = [
    # Common words mistyped as person
    "consciousness", "memories", "memory-system", "memory-systems",
    "systems", "components", "friend", "family", "cooking", "tacos",
    "ingredients", "conversation-flow", "extraction-layers",
    "consciousness-layers", "mcp-tools", "mcp-server",
    "luna_smart_fetch", "ci-pipeline", "2023-11-18",
    "user's-thought-processes", "printmaking-enthusiast",
    "math-teacher", "other-person", "the-other-person", "github",

    # Common words mistyped as persona
    "person", "ai", "system", "assistant", "user", "voice", "speaker",
    "the-speaker", "people", "owls", "raccoon",
    "person-a", "self-image", "ai-system", "testuser",
    "hub's-lunarbehaviour",

    # Generic project names that are just descriptions
    "memory-integration", "observability-layer", "voice-app",
    "rotating-history-system", "interface-prototype", "particle-light",
    "house-container", "technical-work", "new-architecture",
    "small-friendly-house-container", "voice-connection",
    "voice-to-memory-pipeline", "house-design", "observability-systems",
    "personality-monitoring", "personality-engine",
    "corporate-ai-systems", "memory-system-architecture",
    "voice-integration", "embodiment-project",

    # "house" is a common noun, not a place entity
    "house",

    # "ai-companion" is just a generic description of Luna, not a project
    "ai-companion",
]

# Duplicate merges: (keep_id, [merge_ids])
ENTITY_MERGES = [
    ("tarcila", ["tarcilla", "tarcila-neves"]),
    ("kamau", ["kamau-zuberi-akabueze"]),
    ("ben-franklin", ["benjamin"]),
    # speaker and the-speaker are both garbage — already on kill list
    # memory-system and memory-systems are both garbage — already on kill list
    # eclissi-engine → eclissi (keep the canonical name)
    ("eclissi", ["eclissi-engine"]),
    # luna-project, luna-beta, luna-hub, luna-mcp → just keep luna-engine
    ("luna-engine", ["luna-project", "luna-beta", "luna-hub", "luna-mcp", "luna-manifesto"]),
    # the-crew → not useful, but if it references real people we merge nowhere (just delete)
]


# ==========================================================================
# Phase 1a: Delete ghost mentions
# ==========================================================================

async def phase_1a_delete_ghost_mentions(db: aiosqlite.Connection, dry_run: bool) -> dict:
    """Delete mentions whose entity_id doesn't exist in the entities table."""
    cursor = await db.execute("""
        SELECT COUNT(*) FROM entity_mentions
        WHERE entity_id NOT IN (SELECT id FROM entities)
    """)
    count = (await cursor.fetchone())[0]
    logger.info(f"Phase 1a: {count} ghost mentions found")

    if count == 0 or dry_run:
        return {"ghost_mentions_found": count, "deleted": count if dry_run else 0}

    await db.execute("""
        DELETE FROM entity_mentions
        WHERE entity_id NOT IN (SELECT id FROM entities)
    """)
    await db.commit()
    logger.info(f"Phase 1a: Deleted {count} ghost mentions")
    return {"ghost_mentions_found": count, "deleted": count}


# ==========================================================================
# Phase 1b: Delete garbage entities
# ==========================================================================

async def phase_1b_delete_garbage_entities(db: aiosqlite.Connection, dry_run: bool) -> dict:
    """Delete garbage entities and all their associated data."""
    stats = {"found": 0, "deleted": 0, "mentions_deleted": 0, "versions_deleted": 0, "rels_deleted": 0}

    for eid in GARBAGE_ENTITY_IDS:
        cursor = await db.execute("SELECT id, name FROM entities WHERE id = ?", (eid,))
        row = await cursor.fetchone()
        if not row:
            continue

        stats["found"] += 1
        name = row["name"] if hasattr(row, 'keys') else row[1]

        # Count associated data
        mc = (await (await db.execute("SELECT COUNT(*) FROM entity_mentions WHERE entity_id = ?", (eid,))).fetchone())[0]
        vc = (await (await db.execute("SELECT COUNT(*) FROM entity_versions WHERE entity_id = ?", (eid,))).fetchone())[0]
        rc = (await (await db.execute("SELECT COUNT(*) FROM entity_relationships WHERE from_entity = ? OR to_entity = ?", (eid, eid))).fetchone())[0]

        logger.info(f"  {'[DRY]' if dry_run else 'DEL '} {eid} ({name}): {mc} mentions, {vc} versions, {rc} rels")

        if dry_run:
            stats["deleted"] += 1
            stats["mentions_deleted"] += mc
            stats["versions_deleted"] += vc
            stats["rels_deleted"] += rc
            continue

        await db.execute("DELETE FROM entity_mentions WHERE entity_id = ?", (eid,))
        await db.execute("DELETE FROM entity_relationships WHERE from_entity = ? OR to_entity = ?", (eid, eid))
        await db.execute("DELETE FROM entity_versions WHERE entity_id = ?", (eid,))
        await db.execute("DELETE FROM entities WHERE id = ?", (eid,))

        stats["deleted"] += 1
        stats["mentions_deleted"] += mc
        stats["versions_deleted"] += vc
        stats["rels_deleted"] += rc

    if not dry_run:
        await db.commit()

    logger.info(
        f"Phase 1b: {stats['deleted']}/{stats['found']} garbage entities deleted "
        f"({stats['mentions_deleted']} mentions, {stats['versions_deleted']} versions, {stats['rels_deleted']} rels)"
    )
    return stats


# ==========================================================================
# Phase 1c: Merge duplicate entities
# ==========================================================================

async def phase_1c_merge_duplicates(db: aiosqlite.Connection, dry_run: bool) -> dict:
    """Merge duplicate entities into canonical versions."""
    stats = {"merges": 0, "mentions_reassigned": 0, "rels_reassigned": 0}

    for keep_id, merge_ids in ENTITY_MERGES:
        # Verify the keep target exists
        cursor = await db.execute("SELECT id, name FROM entities WHERE id = ?", (keep_id,))
        keep_row = await cursor.fetchone()
        if not keep_row:
            logger.warning(f"  Merge target {keep_id} not found, skipping")
            continue

        for merge_id in merge_ids:
            cursor = await db.execute("SELECT id, name FROM entities WHERE id = ?", (merge_id,))
            merge_row = await cursor.fetchone()
            if not merge_row:
                continue

            merge_name = merge_row["name"] if hasattr(merge_row, 'keys') else merge_row[1]

            # Count data to reassign
            mc = (await (await db.execute(
                "SELECT COUNT(*) FROM entity_mentions WHERE entity_id = ?", (merge_id,)
            )).fetchone())[0]
            rc = (await (await db.execute(
                "SELECT COUNT(*) FROM entity_relationships WHERE from_entity = ? OR to_entity = ?",
                (merge_id, merge_id)
            )).fetchone())[0]

            logger.info(
                f"  {'[DRY]' if dry_run else 'MERGE'} {merge_id} ({merge_name}) -> {keep_id}: "
                f"{mc} mentions, {rc} rels"
            )

            if dry_run:
                stats["merges"] += 1
                stats["mentions_reassigned"] += mc
                stats["rels_reassigned"] += rc
                continue

            # Reassign mentions (handle conflicts with INSERT OR IGNORE + DELETE)
            await db.execute(
                "INSERT OR IGNORE INTO entity_mentions (entity_id, node_id, mention_type, confidence, context_snippet, created_at) "
                "SELECT ?, node_id, mention_type, confidence, context_snippet, created_at "
                "FROM entity_mentions WHERE entity_id = ?",
                (keep_id, merge_id)
            )
            await db.execute("DELETE FROM entity_mentions WHERE entity_id = ?", (merge_id,))

            # Reassign relationships
            await db.execute(
                "UPDATE OR IGNORE entity_relationships SET from_entity = ? WHERE from_entity = ?",
                (keep_id, merge_id)
            )
            await db.execute(
                "UPDATE OR IGNORE entity_relationships SET to_entity = ? WHERE to_entity = ?",
                (keep_id, merge_id)
            )
            # Clean up any remaining (duplicates that hit the UNIQUE constraint)
            await db.execute(
                "DELETE FROM entity_relationships WHERE from_entity = ? OR to_entity = ?",
                (merge_id, merge_id)
            )

            # Add the merge name as an alias on the keeper
            cursor = await db.execute("SELECT aliases FROM entities WHERE id = ?", (keep_id,))
            alias_row = await cursor.fetchone()
            aliases = json.loads((alias_row["aliases"] if hasattr(alias_row, 'keys') else alias_row[0]) or "[]")
            if merge_name not in aliases:
                aliases.append(merge_name)
                await db.execute(
                    "UPDATE entities SET aliases = ? WHERE id = ?",
                    (json.dumps(aliases), keep_id)
                )

            # Delete merged entity
            await db.execute("DELETE FROM entity_versions WHERE entity_id = ?", (merge_id,))
            await db.execute("DELETE FROM entities WHERE id = ?", (merge_id,))

            stats["merges"] += 1
            stats["mentions_reassigned"] += mc
            stats["rels_reassigned"] += rc

    if not dry_run:
        await db.commit()

    logger.info(
        f"Phase 1c: {stats['merges']} merges "
        f"({stats['mentions_reassigned']} mentions reassigned, {stats['rels_reassigned']} rels)"
    )
    return stats


# ==========================================================================
# Phase 1d: Delete remaining zero-mention + zero-relationship entities
#            that look like garbage (not on the explicit keep list)
# ==========================================================================

# These are real entities Luna would want to keep even with 0 mentions
PROTECTED_ENTITIES = {
    "luna", "ahab", "marzipan", "tarcila", "alex", "kamau", "catherine",
    "kirby", "ygor", "yulia", "gandala", "lucy", "pseudo",
    "the-dude", "ben-franklin", "voice-luna", "desktop-luna", "claude-code",
    "mars-college",
    "eclissi", "personacore", "pipeline-hub", "memory-matrix",
    "luna-engine",
    "dr.-carol-myles", "dr.-james-clarke", "dr.-elara-st.-clair",
    "fairy-orchestrator", "the-crew",
}

async def phase_1d_prune_empty_entities(db: aiosqlite.Connection, dry_run: bool) -> dict:
    """Delete entities with 0 mentions AND 0 relationships that aren't protected."""
    stats = {"found": 0, "deleted": 0}

    cursor = await db.execute("""
        SELECT e.id, e.entity_type, e.name
        FROM entities e
        WHERE NOT EXISTS (SELECT 1 FROM entity_mentions em WHERE em.entity_id = e.id)
        AND NOT EXISTS (SELECT 1 FROM entity_relationships er WHERE er.from_entity = e.id OR er.to_entity = e.id)
    """)
    rows = await cursor.fetchall()

    for row in rows:
        eid = row["id"] if hasattr(row, 'keys') else row[0]
        etype = row["entity_type"] if hasattr(row, 'keys') else row[1]
        ename = row["name"] if hasattr(row, 'keys') else row[2]

        if eid in PROTECTED_ENTITIES:
            logger.info(f"  PROTECTED: {eid} ({ename}) — keeping")
            continue

        stats["found"] += 1
        logger.info(f"  {'[DRY]' if dry_run else 'DEL '} {eid} ({ename}) — 0 mentions, 0 rels")

        if not dry_run:
            await db.execute("DELETE FROM entity_versions WHERE entity_id = ?", (eid,))
            await db.execute("DELETE FROM entities WHERE id = ?", (eid,))
        stats["deleted"] += 1

    if not dry_run:
        await db.commit()

    logger.info(f"Phase 1d: Pruned {stats['deleted']} empty entities")
    return stats


# ==========================================================================
# Phase 2: Re-score surviving mentions
# ==========================================================================

async def phase_2_rescore_mentions(db: aiosqlite.Connection, dry_run: bool) -> dict:
    """Re-score all surviving mentions using Fix B relevance algorithm."""
    stats = {"processed": 0, "updated": 0, "deleted": 0, "unchanged": 0}

    cursor = await db.execute("""
        SELECT em.entity_id, em.node_id, em.mention_type, em.confidence,
               mn.content, e.name
        FROM entity_mentions em
        JOIN memory_nodes mn ON em.node_id = mn.id
        JOIN entities e ON em.entity_id = e.id
    """)
    rows = await cursor.fetchall()

    stats["processed"] = len(rows)
    logger.info(f"Phase 2: Re-scoring {len(rows)} mentions")

    to_delete = []
    to_update = []

    for row in rows:
        entity_id = row["entity_id"] if hasattr(row, 'keys') else row[0]
        node_id = row["node_id"] if hasattr(row, 'keys') else row[1]
        old_type = row["mention_type"] if hasattr(row, 'keys') else row[2]
        old_conf = row["confidence"] if hasattr(row, 'keys') else row[3]
        content = row["content"] if hasattr(row, 'keys') else row[4]
        entity_name = row["name"] if hasattr(row, 'keys') else row[5]

        if not content or not entity_name:
            continue

        content_lower = content.lower()
        name_lower = entity_name.lower()
        content_len = len(content)
        word_count = len(content.split())
        name_word_count = len(entity_name.split())

        if content_len == 0 or word_count == 0:
            continue

        # Calculate scores
        occurrences = content_lower.count(name_lower)
        frequency_score = min(occurrences / 3.0, 1.0)

        first_pos = content_lower.find(name_lower)
        position_score = 1.0 - (first_pos / content_len) if first_pos >= 0 else 0.0

        density = (occurrences * name_word_count) / word_count
        density_score = min(density * 10, 1.0)

        confidence = min(1.0, (
            0.3 * frequency_score +
            0.3 * position_score +
            0.4 * density_score
        ))

        # Classify
        if density > 0.1 or occurrences >= 3:
            mention_type = "subject"
        elif position_score > 0.8 and occurrences >= 2:
            mention_type = "focus"
        else:
            mention_type = "reference"

        # Below threshold? Delete.
        if confidence < 0.3:
            to_delete.append((entity_id, node_id))
            continue

        # Changed?
        if mention_type != old_type or abs(confidence - (old_conf or 1.0)) > 0.01:
            to_update.append((mention_type, round(confidence, 3), entity_id, node_id))
        else:
            stats["unchanged"] += 1

    logger.info(f"Phase 2 plan: {len(to_update)} updates, {len(to_delete)} deletions, {stats['unchanged']} unchanged")

    if dry_run:
        stats["updated"] = len(to_update)
        stats["deleted"] = len(to_delete)
        return stats

    for mention_type, confidence, entity_id, node_id in to_update:
        await db.execute(
            "UPDATE entity_mentions SET mention_type = ?, confidence = ? WHERE entity_id = ? AND node_id = ?",
            (mention_type, confidence, entity_id, node_id)
        )
    stats["updated"] = len(to_update)

    for entity_id, node_id in to_delete:
        await db.execute(
            "DELETE FROM entity_mentions WHERE entity_id = ? AND node_id = ?",
            (entity_id, node_id)
        )
    stats["deleted"] = len(to_delete)

    await db.commit()
    logger.info(f"Phase 2: {stats['updated']} updated, {stats['deleted']} deleted, {stats['unchanged']} unchanged")
    return stats


# ==========================================================================
# MAIN
# ==========================================================================

async def main(dry_run: bool = True, phase: int = 0):
    if not DB_PATH.exists():
        logger.error(f"Database not found: {DB_PATH}")
        return 1

    logger.info("=" * 60)
    logger.info("Luna's Memory Cleanup — The Real Fix")
    logger.info("=" * 60)
    if dry_run:
        logger.info("[DRY RUN — no changes will be written]")
    logger.info(f"Database: {DB_PATH}")
    logger.info("")

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Baseline
        total_entities = (await (await db.execute("SELECT COUNT(*) FROM entities")).fetchone())[0]
        total_mentions = (await (await db.execute("SELECT COUNT(*) FROM entity_mentions")).fetchone())[0]
        logger.info(f"Before: {total_entities} entities, {total_mentions} mentions")
        logger.info("")

        results = {}

        if phase in (0, 1):
            logger.info("--- Phase 1a: Delete ghost mentions ---")
            results["phase_1a"] = await phase_1a_delete_ghost_mentions(db, dry_run)
            logger.info("")

            logger.info("--- Phase 1b: Delete garbage entities ---")
            results["phase_1b"] = await phase_1b_delete_garbage_entities(db, dry_run)
            logger.info("")

            logger.info("--- Phase 1c: Merge duplicate entities ---")
            results["phase_1c"] = await phase_1c_merge_duplicates(db, dry_run)
            logger.info("")

            logger.info("--- Phase 1d: Prune empty entities ---")
            results["phase_1d"] = await phase_1d_prune_empty_entities(db, dry_run)
            logger.info("")

        if phase in (0, 2):
            logger.info("--- Phase 2: Re-score surviving mentions ---")
            results["phase_2"] = await phase_2_rescore_mentions(db, dry_run)
            logger.info("")

        # Final counts
        if not dry_run:
            final_entities = (await (await db.execute("SELECT COUNT(*) FROM entities")).fetchone())[0]
            final_mentions = (await (await db.execute("SELECT COUNT(*) FROM entity_mentions")).fetchone())[0]

            logger.info("=" * 60)
            logger.info("Summary")
            logger.info("=" * 60)
            logger.info(f"Entities:  {total_entities} -> {final_entities}")
            logger.info(f"Mentions:  {total_mentions} -> {final_mentions}")
            logger.info(f"Entities removed: {total_entities - final_entities}")
            logger.info(f"Mentions removed: {total_mentions - final_mentions}")

        logger.info("")
        logger.info("Phase results:")
        for phase_name, stats in results.items():
            logger.info(f"  {phase_name}: {stats}")

    return 0


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Luna's Memory Cleanup")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--phase", type=int, default=0, help="Run specific phase (1 or 2, 0=all)")
    args = parser.parse_args()

    sys.exit(asyncio.run(main(dry_run=args.dry_run, phase=args.phase)))
