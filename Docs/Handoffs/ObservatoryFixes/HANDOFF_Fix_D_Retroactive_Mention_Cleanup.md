# HANDOFF: Fix D — Retroactive Mention Cleanup Migration
## Priority: P2 (Run after Fix A + Fix B are deployed)
## Estimated Effort: 30 minutes
## Owner: CC (Claude Code)
## Dependencies: Fix A and Fix B must be deployed first

---

## Problem

The database contains thousands of polluted entity mentions from before Fix A and Fix B:
- Raw conversation turns stored as `node_type="FACT"` with `[assistant]` and `[user]` prefixes
- All entity mentions have `confidence=1.0` and `mention_type="reference"` regardless of relevance
- ~110 of 123 Eclissi mentions are raw conversation dumps, not extracted knowledge

This migration cleans existing data to match the new standards.

## Migration Script

### Create: `scripts/migrations/fix_mention_pollution.py`

```python
#!/usr/bin/env python3
"""
Fix Mention Pollution Migration
================================

Three-phase cleanup:
1. Retype raw conversation FACT nodes to CONVERSATION_TURN
2. Delete entity_mentions linked to CONVERSATION_TURN nodes
3. Re-score remaining mentions using new relevance algorithm

Run AFTER Fix A (store_turn retype) and Fix B (relevance scoring) are deployed.

Usage:
    python scripts/migrations/fix_mention_pollution.py --dry-run
    python scripts/migrations/fix_mention_pollution.py
    python scripts/migrations/fix_mention_pollution.py --phase 1  # Only retype
    python scripts/migrations/fix_mention_pollution.py --phase 2  # Only delete mentions
    python scripts/migrations/fix_mention_pollution.py --phase 3  # Only re-score
"""

import asyncio
import aiosqlite
import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)
logger = logging.getLogger(__name__)

# Database path
DB_PATH = Path(__file__).parent.parent.parent / "data" / "luna_engine.db"


# ============================================================================
# PHASE 1: Retype raw conversation FACT nodes
# ============================================================================

async def phase_1_retype_conversation_facts(db: aiosqlite.Connection, dry_run: bool) -> dict:
    """
    Find FACT nodes that are actually raw conversation turns and retype them.
    
    Detection heuristics:
    - content starts with "[user]" or "[assistant]"
    - source = "conversation"
    - metadata contains "conversation" tag
    """
    stats = {"found": 0, "retyped": 0, "skipped": 0}
    
    # Find candidates: FACT nodes with conversation markers
    async with db.execute("""
        SELECT id, content, source, metadata
        FROM memory_nodes
        WHERE node_type = 'FACT'
        AND (
            content LIKE '[user]%'
            OR content LIKE '[assistant]%'
            OR content LIKE '[system]%'
            OR source = 'conversation'
        )
    """) as cursor:
        rows = await cursor.fetchall()
    
    stats["found"] = len(rows)
    logger.info(f"Phase 1: Found {len(rows)} candidate FACT nodes to retype")
    
    for row in rows:
        node_id, content, source, metadata = row
        
        # Verify this is a raw conversation turn, not extracted knowledge
        is_raw_turn = (
            content.startswith("[user]") or
            content.startswith("[assistant]") or
            content.startswith("[system]")
        )
        
        # Also check metadata for conversation tags
        if not is_raw_turn and metadata:
            try:
                meta = json.loads(metadata)
                tags = meta.get("tags", [])
                is_raw_turn = "conversation" in tags
            except (json.JSONDecodeError, TypeError):
                pass
        
        if not is_raw_turn:
            stats["skipped"] += 1
            continue
        
        if dry_run:
            logger.info(f"  [DRY RUN] Would retype {node_id}: {content[:60]}...")
            stats["retyped"] += 1
            continue
        
        await db.execute(
            "UPDATE memory_nodes SET node_type = 'CONVERSATION_TURN' WHERE id = ?",
            (node_id,)
        )
        stats["retyped"] += 1
    
    if not dry_run:
        await db.commit()
    
    logger.info(
        f"Phase 1 complete: {stats['retyped']} retyped, "
        f"{stats['skipped']} skipped (not raw turns)"
    )
    return stats


# ============================================================================
# PHASE 2: Delete mentions linked to CONVERSATION_TURN nodes
# ============================================================================

async def phase_2_delete_conversation_mentions(db: aiosqlite.Connection, dry_run: bool) -> dict:
    """Delete all entity_mentions linked to CONVERSATION_TURN nodes."""
    stats = {"found": 0, "deleted": 0}
    
    # Count first
    async with db.execute("""
        SELECT COUNT(*) FROM entity_mentions em
        JOIN memory_nodes mn ON em.node_id = mn.id
        WHERE mn.node_type = 'CONVERSATION_TURN'
    """) as cursor:
        row = await cursor.fetchone()
        stats["found"] = row[0] if row else 0
    
    logger.info(f"Phase 2: Found {stats['found']} mentions linked to CONVERSATION_TURN nodes")
    
    if stats["found"] == 0:
        return stats
    
    if dry_run:
        logger.info(f"  [DRY RUN] Would delete {stats['found']} mentions")
        stats["deleted"] = stats["found"]
        return stats
    
    await db.execute("""
        DELETE FROM entity_mentions
        WHERE node_id IN (
            SELECT id FROM memory_nodes
            WHERE node_type = 'CONVERSATION_TURN'
        )
    """)
    await db.commit()
    
    stats["deleted"] = stats["found"]
    logger.info(f"Phase 2 complete: {stats['deleted']} mentions deleted")
    return stats


# ============================================================================
# PHASE 3: Re-score remaining mentions
# ============================================================================

async def phase_3_rescore_mentions(db: aiosqlite.Connection, dry_run: bool) -> dict:
    """
    Re-score existing mentions using the new relevance algorithm.
    
    For each mention:
    1. Load the linked memory node content
    2. Calculate frequency, position, density scores
    3. Update mention_type and confidence
    4. Delete mentions below threshold (0.3)
    """
    stats = {"processed": 0, "updated": 0, "deleted": 0, "unchanged": 0}
    
    # Get all mentions with their node content
    async with db.execute("""
        SELECT em.entity_id, em.node_id, em.mention_type, em.confidence,
               mn.content, e.name
        FROM entity_mentions em
        JOIN memory_nodes mn ON em.node_id = mn.id
        JOIN entities e ON em.entity_id = e.id
        WHERE mn.node_type != 'CONVERSATION_TURN'
    """) as cursor:
        rows = await cursor.fetchall()
    
    stats["processed"] = len(rows)
    logger.info(f"Phase 3: Re-scoring {len(rows)} mentions")
    
    to_delete = []
    to_update = []
    
    for row in rows:
        entity_id, node_id, old_type, old_conf, content, entity_name = row
        
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
        
        # Changed? Update.
        if mention_type != old_type or abs(confidence - (old_conf or 1.0)) > 0.01:
            to_update.append((mention_type, round(confidence, 3), entity_id, node_id))
        else:
            stats["unchanged"] += 1
    
    logger.info(
        f"Phase 3 plan: {len(to_update)} updates, "
        f"{len(to_delete)} deletions, {stats['unchanged']} unchanged"
    )
    
    if dry_run:
        stats["updated"] = len(to_update)
        stats["deleted"] = len(to_delete)
        logger.info("  [DRY RUN] No changes written")
        return stats
    
    # Apply updates
    for mention_type, confidence, entity_id, node_id in to_update:
        await db.execute(
            """UPDATE entity_mentions 
               SET mention_type = ?, confidence = ?
               WHERE entity_id = ? AND node_id = ?""",
            (mention_type, confidence, entity_id, node_id)
        )
    stats["updated"] = len(to_update)
    
    # Apply deletions
    for entity_id, node_id in to_delete:
        await db.execute(
            "DELETE FROM entity_mentions WHERE entity_id = ? AND node_id = ?",
            (entity_id, node_id)
        )
    stats["deleted"] = len(to_delete)
    
    await db.commit()
    
    logger.info(
        f"Phase 3 complete: {stats['updated']} updated, "
        f"{stats['deleted']} deleted, {stats['unchanged']} unchanged"
    )
    return stats


# ============================================================================
# MAIN
# ============================================================================

async def main(dry_run: bool = True, phase: int = 0):
    """Run the migration."""
    if not DB_PATH.exists():
        logger.error(f"Database not found: {DB_PATH}")
        return 1
    
    logger.info("=" * 60)
    logger.info("Entity Mention Pollution Cleanup Migration")
    logger.info("=" * 60)
    if dry_run:
        logger.info("[DRY RUN MODE — no changes will be written]")
    logger.info(f"Database: {DB_PATH}")
    logger.info("")
    
    async with aiosqlite.connect(DB_PATH) as db:
        # Get baseline counts
        async with db.execute("SELECT COUNT(*) FROM entity_mentions") as c:
            total_mentions_before = (await c.fetchone())[0]
        async with db.execute(
            "SELECT COUNT(*) FROM memory_nodes WHERE node_type = 'FACT'"
        ) as c:
            total_facts_before = (await c.fetchone())[0]
        
        logger.info(f"Before: {total_mentions_before} mentions, {total_facts_before} FACT nodes")
        logger.info("")
        
        results = {}
        
        if phase == 0 or phase == 1:
            logger.info("--- Phase 1: Retype raw conversation FACT nodes ---")
            results["phase_1"] = await phase_1_retype_conversation_facts(db, dry_run)
            logger.info("")
        
        if phase == 0 or phase == 2:
            logger.info("--- Phase 2: Delete CONVERSATION_TURN mentions ---")
            results["phase_2"] = await phase_2_delete_conversation_mentions(db, dry_run)
            logger.info("")
        
        if phase == 0 or phase == 3:
            logger.info("--- Phase 3: Re-score remaining mentions ---")
            results["phase_3"] = await phase_3_rescore_mentions(db, dry_run)
            logger.info("")
        
        # Final counts
        if not dry_run:
            async with db.execute("SELECT COUNT(*) FROM entity_mentions") as c:
                total_mentions_after = (await c.fetchone())[0]
            async with db.execute(
                "SELECT COUNT(*) FROM memory_nodes WHERE node_type = 'FACT'"
            ) as c:
                total_facts_after = (await c.fetchone())[0]
            
            logger.info("=" * 60)
            logger.info("Summary")
            logger.info("=" * 60)
            logger.info(f"FACT nodes:      {total_facts_before} → {total_facts_after}")
            logger.info(f"Entity mentions: {total_mentions_before} → {total_mentions_after}")
            logger.info(f"Mentions removed: {total_mentions_before - total_mentions_after}")
        
        logger.info("")
        logger.info("Phase results:")
        for phase_name, stats in results.items():
            logger.info(f"  {phase_name}: {stats}")
    
    return 0


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Fix entity mention pollution")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--phase", type=int, default=0, help="Run specific phase (1/2/3, 0=all)")
    args = parser.parse_args()
    
    sys.exit(asyncio.run(main(dry_run=args.dry_run, phase=args.phase)))
```

## Usage

```bash
# Preview what will change (ALWAYS run first)
python scripts/migrations/fix_mention_pollution.py --dry-run

# Run all phases
python scripts/migrations/fix_mention_pollution.py

# Run phases individually (for debugging)
python scripts/migrations/fix_mention_pollution.py --phase 1  # Retype nodes
python scripts/migrations/fix_mention_pollution.py --phase 2  # Delete bad mentions  
python scripts/migrations/fix_mention_pollution.py --phase 3  # Re-score remaining
```

## Expected Results

Based on current data (~123 Eclissi mentions, ~90 AI companion mentions):
- Phase 1: ~60-80% of FACT nodes with `[user]`/`[assistant]` prefix get retyped
- Phase 2: Corresponding mentions deleted (bulk of the 123 Eclissi mentions)
- Phase 3: Remaining mentions re-scored; ~30-50% drop below 0.3 threshold

After migration, Eclissi should have ~10-15 high-quality mentions instead of 123.

## Safety

- **Backup first:** `cp data/luna_engine.db data/luna_engine.db.bak`
- **Dry run:** Always run with `--dry-run` first
- **Phased:** Can run each phase independently
- **No node deletion:** Phase 1 retypes, doesn't delete. Raw data preserved.
- **Mention deletion is safe:** Mentions are derived data, re-creatable from nodes

## Verification

After running:
```sql
-- Eclissi should have ~10-15 mentions, not 123
SELECT COUNT(*), mention_type, ROUND(AVG(confidence), 2) as avg_conf
FROM entity_mentions
WHERE entity_id = 'eclissi'
GROUP BY mention_type;

-- No mentions should link to CONVERSATION_TURN nodes
SELECT COUNT(*) FROM entity_mentions em
JOIN memory_nodes mn ON em.node_id = mn.id
WHERE mn.node_type = 'CONVERSATION_TURN';
-- Expected: 0

-- Confidence distribution should be spread, not all 1.0
SELECT 
  CASE 
    WHEN confidence >= 0.8 THEN 'high (0.8+)'
    WHEN confidence >= 0.5 THEN 'medium (0.5-0.8)'
    WHEN confidence >= 0.3 THEN 'low (0.3-0.5)'
    ELSE 'dropped (<0.3)'
  END as bucket,
  COUNT(*) as count
FROM entity_mentions
GROUP BY bucket;
```
