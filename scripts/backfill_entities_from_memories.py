#!/usr/bin/env python3
"""
Backfill Entity Profiles from Memory Matrix

Scans existing memories for mentioned people and creates entity profiles.
Run once to bootstrap, then Scribe handles ongoing creation.

Usage:
    python scripts/backfill_entities_from_memories.py
    python scripts/backfill_entities_from_memories.py --dry-run
"""

import asyncio
import aiosqlite
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# ============================================================================
# KNOWN PEOPLE TO BACKFILL
# Add anyone Luna should know about here
# ============================================================================

KNOWN_PEOPLE = [
    {
        "name": "Marzipan",
        "aliases": ["Marzi"],
        "context": "Friend from Mars College, interested in AI consciousness",
        "relationship_to_ahab": "friend, collaborator",
        "location": "Mars College",
    },
    {
        "name": "Yulia",
        "aliases": [],
        "context": "Met during voice conversation testing",
        "relationship_to_ahab": "acquaintance",
        "notes": "Loves chocolate, asked about Bombay Beach weather",
    },
    {
        "name": "Tarsila",
        "aliases": ["Tarcila", "Tarsila Neves"],
        "context": "Artist designing Luna's physical robot body",
        "relationship_to_ahab": "collaborator",
        "project": "Luna robot embodiment with raccoon aesthetics",
    },
    {
        "name": "Kamau",
        "aliases": [],
        "context": "Friend from Mars College, runs Akashic Creativity workshop",
        "relationship_to_ahab": "friend",
        "location": "Mars College",
    },
]


async def get_mentions_from_memory(db: aiosqlite.Connection, name: str) -> List[Dict]:
    """Search Memory Matrix for mentions of a person."""
    try:
        async with db.execute("""
            SELECT id, content, node_type, created_at
            FROM memory_nodes
            WHERE content LIKE ?
            ORDER BY created_at DESC
            LIMIT 20
        """, (f"%{name}%",)) as cursor:
            rows = await cursor.fetchall()

        return [
            {
                "id": row[0],
                "content": row[1],
                "node_type": row[2],
                "created_at": row[3],
            }
            for row in rows
        ] if rows else []
    except Exception as e:
        logger.warning(f"Could not search memories for {name}: {e}")
        return []


def extract_facts_from_mentions(person: Dict, mentions: List[Dict]) -> Dict:
    """
    Extract structured facts from memory mentions.

    In production, this could use an LLM to synthesize.
    For now, we use the bootstrap data + mention count.
    """
    facts = {
        "relationship": person.get("relationship_to_ahab", "known person"),
        "context": person.get("context", ""),
        "mention_count": len(mentions),
        "first_seen": mentions[-1]["created_at"] if mentions else datetime.now().isoformat(),
        "last_seen": mentions[0]["created_at"] if mentions else datetime.now().isoformat(),
    }

    # Add optional fields if present
    if person.get("location"):
        facts["location"] = person["location"]
    if person.get("project"):
        facts["project"] = person["project"]
    if person.get("notes"):
        facts["notes"] = person["notes"]

    return facts


def generate_profile(person: Dict, mentions: List[Dict]) -> str:
    """Generate a full profile from bootstrap data and mentions."""
    lines = [
        f"{person['name']} is someone Luna knows through {person.get('context', 'previous conversations')}.",
        "",
    ]

    if person.get("relationship_to_ahab"):
        lines.append(f"Relationship to Ahab: {person['relationship_to_ahab']}")

    if person.get("location"):
        lines.append(f"Location: {person['location']}")

    if person.get("project"):
        lines.append(f"Project: {person['project']}")

    if person.get("notes"):
        lines.append(f"Notes: {person['notes']}")

    if mentions:
        lines.append("")
        lines.append(f"Mentioned in {len(mentions)} memory nodes.")

    return "\n".join(lines)


async def create_entity(
    db: aiosqlite.Connection,
    person: Dict,
    facts: Dict,
    profile: str,
    dry_run: bool = False
) -> bool:
    """Create an entity in the database."""
    entity_id = person["name"].lower().replace(" ", "-")
    aliases = json.dumps(person.get("aliases", []))
    core_facts = json.dumps(facts)

    if dry_run:
        logger.info(f"  [DRY RUN] Would create entity: {entity_id}")
        logger.info(f"    Facts: {facts}")
        return True

    try:
        # Insert entity
        await db.execute("""
            INSERT INTO entities (
                id, entity_type, name, aliases, core_facts, full_profile, current_version
            ) VALUES (?, 'person', ?, ?, ?, ?, 1)
        """, (entity_id, person["name"], aliases, core_facts, profile))

        # Create version record
        await db.execute("""
            INSERT INTO entity_versions (
                entity_id, version, core_facts, full_profile,
                change_type, change_summary, changed_by, change_source
            ) VALUES (?, 1, ?, ?, 'create', ?, 'backfill_script', 'memory_scan')
        """, (entity_id, core_facts, profile, f"Backfilled from {facts['mention_count']} memory mentions"))

        await db.commit()
        return True

    except Exception as e:
        logger.error(f"  [ERROR] Failed to create {entity_id}: {e}")
        return False


async def entity_exists(db: aiosqlite.Connection, name: str) -> bool:
    """Check if an entity already exists."""
    entity_id = name.lower().replace(" ", "-")

    # Check by ID
    async with db.execute("SELECT id FROM entities WHERE id = ?", (entity_id,)) as cursor:
        row = await cursor.fetchone()
    if row:
        return True

    # Check by name
    async with db.execute("SELECT id FROM entities WHERE LOWER(name) = LOWER(?)", (name,)) as cursor:
        row = await cursor.fetchone()
    if row:
        return True

    return False


async def main(dry_run: bool = False):
    """Main backfill routine."""
    db_path = Path.home() / ".luna" / "luna.db"

    if not db_path.exists():
        logger.error(f"Database not found: {db_path}")
        logger.error("Run the migration first: sqlite3 ~/.luna/luna.db < migrations/001_entity_system.sql")
        return 1

    logger.info("=" * 60)
    logger.info("Entity Backfill from Memory Matrix")
    logger.info("=" * 60)

    if dry_run:
        logger.info("[DRY RUN MODE - No changes will be written]")

    logger.info(f"\nDatabase: {db_path}")
    logger.info(f"People to process: {len(KNOWN_PEOPLE)}\n")

    created = 0
    skipped = 0
    errors = 0

    async with aiosqlite.connect(db_path) as db:
        for person in KNOWN_PEOPLE:
            name = person["name"]
            logger.info(f"Processing: {name}")

            # Check if exists
            if await entity_exists(db, name):
                logger.info(f"  [SKIP] Already exists")
                skipped += 1
                continue

            # Get mentions from Memory Matrix
            mentions = await get_mentions_from_memory(db, name)
            logger.info(f"  Found {len(mentions)} memory mentions")

            # Extract facts
            facts = extract_facts_from_mentions(person, mentions)

            # Generate profile
            profile = generate_profile(person, mentions)

            # Create entity
            if await create_entity(db, person, facts, profile, dry_run):
                logger.info(f"  [CREATED] {name}")
                created += 1
            else:
                errors += 1

    logger.info("\n" + "=" * 60)
    logger.info("Summary")
    logger.info("=" * 60)
    logger.info(f"  Created: {created}")
    logger.info(f"  Skipped: {skipped} (already exist)")
    logger.info(f"  Errors:  {errors}")

    if dry_run:
        logger.info("\n[DRY RUN] No changes were made.")

    return 0 if errors == 0 else 1


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Backfill entity profiles from Memory Matrix")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()

    sys.exit(asyncio.run(main(dry_run=args.dry_run)))
