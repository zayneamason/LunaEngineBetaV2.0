#!/usr/bin/env python3
"""
Luna Engine Entity Seed Loader
==============================

Loads YAML seed files into the entity database with version tracking.

This script scans the entities/ directory for YAML files and:
1. Creates new entities if they don't exist
2. Updates existing entities if content has changed (detected via hash)
3. Creates version records for all changes
4. Reports a summary of actions taken

Usage:
    python scripts/load_entity_seeds.py
    python scripts/load_entity_seeds.py --entities-dir ./entities
    python scripts/load_entity_seeds.py --db-path ./test.db
    python scripts/load_entity_seeds.py --dry-run

Based on HANDOFF_ENTITY_SYSTEM.md specification.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import yaml

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from luna.substrate.database import MemoryDatabase

logger = logging.getLogger(__name__)


def hash_entity_data(data: dict[str, Any]) -> str:
    """
    Create a content hash of entity YAML data for change detection.

    Hashes the serialized JSON of relevant fields to detect content changes
    between the seed file and the database version.

    Args:
        data: Parsed YAML data from seed file

    Returns:
        SHA256 hash hex string
    """
    # Extract fields that matter for versioning
    hashable_content = {
        "core_facts": data.get("core_facts", {}),
        "full_profile": data.get("full_profile", ""),
        "voice_config": data.get("voice_config", {}),
        "aliases": data.get("aliases", []),
        "metadata": data.get("metadata", {}),
    }

    # Serialize to JSON with sorted keys for deterministic hashing
    content_str = json.dumps(hashable_content, sort_keys=True, ensure_ascii=False)

    return hashlib.sha256(content_str.encode("utf-8")).hexdigest()


def normalize_entity_id(name: str) -> str:
    """
    Normalize a name to a valid entity ID slug.

    Args:
        name: The entity name

    Returns:
        Lowercase slug with hyphens
    """
    return name.lower().replace(" ", "-").replace("_", "-")


class EntitySeedLoader:
    """
    Loads YAML seed files into the Luna Engine entity database.

    Handles:
    - Recursive scanning of entities directory
    - Change detection via content hashing
    - Creating/updating entities with version tracking
    - Dry run mode for previewing changes
    """

    def __init__(
        self,
        db: MemoryDatabase,
        entities_dir: Path,
        dry_run: bool = False
    ) -> None:
        """
        Initialize the seed loader.

        Args:
            db: Connected MemoryDatabase instance
            entities_dir: Path to entities/ directory with YAML files
            dry_run: If True, show what would be done without writing
        """
        self.db = db
        self.entities_dir = entities_dir
        self.dry_run = dry_run

        # Counters for summary
        self.loaded_count = 0
        self.updated_count = 0
        self.skipped_count = 0
        self.error_count = 0

    async def ensure_schema(self) -> None:
        """
        Ensure the entity tables exist.

        Creates the entities and entity_versions tables if they don't exist.
        This allows the script to work even if migrations haven't been run.
        """
        # Check if entities table exists
        result = await self.db.fetchone(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='entities'"
        )

        if result is None:
            logger.info("Creating entity tables...")

            # Read and execute migration
            migration_path = Path(__file__).parent.parent / "migrations" / "001_entity_system.sql"

            if migration_path.exists():
                migration_sql = migration_path.read_text()
                conn = self.db._ensure_connected()
                await conn.executescript(migration_sql)
                await conn.commit()
                logger.info("Entity tables created from migration")
            else:
                # Create minimal schema inline
                await self._create_minimal_schema()

    async def _create_minimal_schema(self) -> None:
        """Create minimal entity schema if migration file not available."""
        schema = """
        CREATE TABLE IF NOT EXISTS entities (
            id TEXT PRIMARY KEY,
            entity_type TEXT NOT NULL,
            name TEXT NOT NULL,
            aliases TEXT,
            core_facts TEXT,
            full_profile TEXT,
            voice_config TEXT,
            current_version INTEGER DEFAULT 1,
            metadata TEXT,
            content_hash TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS entity_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
            version INTEGER NOT NULL,
            core_facts TEXT,
            full_profile TEXT,
            voice_config TEXT,
            change_type TEXT NOT NULL,
            change_summary TEXT,
            changed_by TEXT NOT NULL,
            change_source TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            valid_from TEXT DEFAULT (datetime('now')),
            valid_until TEXT,
            UNIQUE(entity_id, version)
        );

        CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);
        CREATE INDEX IF NOT EXISTS idx_versions_current
        ON entity_versions(entity_id, valid_until) WHERE valid_until IS NULL;
        """

        conn = self.db._ensure_connected()
        await conn.executescript(schema)
        await conn.commit()
        logger.info("Created minimal entity schema")

    async def get_entity_by_id(self, entity_id: str) -> Optional[dict[str, Any]]:
        """
        Get an entity by ID.

        Args:
            entity_id: The entity's unique slug ID

        Returns:
            Entity row as dict, or None if not found
        """
        row = await self.db.fetchone(
            "SELECT * FROM entities WHERE id = ?",
            (entity_id,)
        )

        if row is None:
            return None

        # Convert sqlite row to dict
        columns = [
            "id", "entity_type", "name", "aliases", "core_facts",
            "full_profile", "voice_config", "current_version",
            "metadata", "created_at", "updated_at"
        ]

        # Handle potential content_hash column
        try:
            result = await self.db.fetchone(
                "SELECT content_hash FROM entities WHERE id = ?",
                (entity_id,)
            )
            if result is not None:
                columns.append("content_hash")
        except Exception:
            pass

        return dict(zip(columns, row))

    async def get_content_hash(self, entity_id: str) -> Optional[str]:
        """
        Get the stored content hash for an entity.

        Args:
            entity_id: The entity's unique slug ID

        Returns:
            Content hash string, or None if not stored
        """
        # First check if content_hash column exists
        try:
            row = await self.db.fetchone(
                "SELECT content_hash FROM entities WHERE id = ?",
                (entity_id,)
            )
            if row is not None:
                return row[0]
        except Exception:
            pass

        # Fallback: compute hash from stored data
        entity = await self.get_entity_by_id(entity_id)
        if entity is None:
            return None

        # Reconstruct data dict for hashing
        data = {
            "core_facts": json.loads(entity.get("core_facts") or "{}"),
            "full_profile": entity.get("full_profile") or "",
            "voice_config": json.loads(entity.get("voice_config") or "{}"),
            "aliases": json.loads(entity.get("aliases") or "[]"),
            "metadata": json.loads(entity.get("metadata") or "{}"),
        }

        return hash_entity_data(data)

    async def create_entity(self, data: dict[str, Any], source_file: str) -> None:
        """
        Create a new entity from seed data.

        Args:
            data: Parsed YAML data
            source_file: Source file name for tracking
        """
        entity_id = data.get("id") or normalize_entity_id(data["name"])
        content_hash = hash_entity_data(data)

        # Prepare JSON fields
        core_facts = json.dumps(data.get("core_facts", {}))
        aliases = json.dumps(data.get("aliases", []))
        voice_config = json.dumps(data.get("voice_config", {}))
        metadata = json.dumps(data.get("metadata", {}))
        full_profile = data.get("full_profile", "")

        logger.info(f"Creating entity: {entity_id} ({data.get('entity_type', 'unknown')})")

        if self.dry_run:
            print(f"  [DRY RUN] Would create entity: {entity_id}")
            self.loaded_count += 1
            return

        # Insert entity
        await self.db.execute(
            """
            INSERT INTO entities (
                id, entity_type, name, aliases, core_facts,
                full_profile, voice_config, current_version, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
            """,
            (
                entity_id,
                data.get("entity_type", "person"),
                data["name"],
                aliases,
                core_facts,
                full_profile,
                voice_config,
                metadata,
            )
        )

        # Create initial version record
        await self.db.execute(
            """
            INSERT INTO entity_versions (
                entity_id, version, core_facts, full_profile, voice_config,
                change_type, change_summary, changed_by, change_source
            ) VALUES (?, 1, ?, ?, ?, 'create', ?, 'seed_loader', ?)
            """,
            (
                entity_id,
                core_facts,
                full_profile,
                voice_config,
                f"Initial profile from seed file",
                f"seed:{source_file}",
            )
        )

        # Try to store content hash (column may not exist)
        try:
            await self.db.execute(
                "UPDATE entities SET content_hash = ? WHERE id = ?",
                (content_hash, entity_id)
            )
        except Exception:
            # content_hash column doesn't exist, that's okay
            pass

        self.loaded_count += 1
        print(f"  [CREATED] {entity_id}")

    async def update_entity(
        self,
        entity_id: str,
        data: dict[str, Any],
        current_version: int,
        source_file: str
    ) -> None:
        """
        Update an existing entity with new seed data.

        Args:
            entity_id: The entity's unique slug ID
            data: Parsed YAML data
            current_version: Current version number in database
            source_file: Source file name for tracking
        """
        content_hash = hash_entity_data(data)
        new_version = current_version + 1

        # Prepare JSON fields
        core_facts = json.dumps(data.get("core_facts", {}))
        aliases = json.dumps(data.get("aliases", []))
        voice_config = json.dumps(data.get("voice_config", {}))
        metadata = json.dumps(data.get("metadata", {}))
        full_profile = data.get("full_profile", "")

        logger.info(f"Updating entity: {entity_id} (v{current_version} -> v{new_version})")

        if self.dry_run:
            print(f"  [DRY RUN] Would update entity: {entity_id} to v{new_version}")
            self.updated_count += 1
            return

        # Close current version
        await self.db.execute(
            """
            UPDATE entity_versions
            SET valid_until = datetime('now')
            WHERE entity_id = ? AND valid_until IS NULL
            """,
            (entity_id,)
        )

        # Create new version record
        await self.db.execute(
            """
            INSERT INTO entity_versions (
                entity_id, version, core_facts, full_profile, voice_config,
                change_type, change_summary, changed_by, change_source
            ) VALUES (?, ?, ?, ?, ?, 'update', ?, 'seed_loader', ?)
            """,
            (
                entity_id,
                new_version,
                core_facts,
                full_profile,
                voice_config,
                f"Updated from seed file",
                f"seed:{source_file}",
            )
        )

        # Update entity record
        await self.db.execute(
            """
            UPDATE entities SET
                entity_type = ?,
                name = ?,
                aliases = ?,
                core_facts = ?,
                full_profile = ?,
                voice_config = ?,
                current_version = ?,
                metadata = ?,
                updated_at = datetime('now')
            WHERE id = ?
            """,
            (
                data.get("entity_type", "person"),
                data["name"],
                aliases,
                core_facts,
                full_profile,
                voice_config,
                new_version,
                metadata,
                entity_id,
            )
        )

        # Try to store content hash
        try:
            await self.db.execute(
                "UPDATE entities SET content_hash = ? WHERE id = ?",
                (content_hash, entity_id)
            )
        except Exception:
            pass

        self.updated_count += 1
        print(f"  [UPDATED] {entity_id} v{current_version} -> v{new_version}")

    async def process_seed_file(self, yaml_file: Path) -> None:
        """
        Process a single YAML seed file.

        Args:
            yaml_file: Path to the YAML file
        """
        relative_path = yaml_file.relative_to(self.entities_dir)
        logger.debug(f"Processing: {relative_path}")

        try:
            # Parse YAML
            with open(yaml_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if data is None:
                logger.warning(f"Empty YAML file: {yaml_file}")
                self.skipped_count += 1
                return

            # Validate required fields
            if "name" not in data:
                logger.error(f"Missing 'name' field in: {yaml_file}")
                self.error_count += 1
                return

            # Get or generate entity ID
            entity_id = data.get("id") or normalize_entity_id(data["name"])

            # Check if entity exists
            existing = await self.get_entity_by_id(entity_id)

            if existing is None:
                # New entity
                await self.create_entity(data, str(relative_path))
            else:
                # Check for changes
                current_hash = await self.get_content_hash(entity_id)
                new_hash = hash_entity_data(data)

                if current_hash != new_hash:
                    # Content changed - update
                    await self.update_entity(
                        entity_id,
                        data,
                        existing.get("current_version", 1),
                        str(relative_path)
                    )
                else:
                    # No changes
                    logger.debug(f"No changes for: {entity_id}")
                    self.skipped_count += 1
                    print(f"  [SKIPPED] {entity_id} (no changes)")

        except yaml.YAMLError as e:
            logger.error(f"YAML parse error in {yaml_file}: {e}")
            self.error_count += 1
            print(f"  [ERROR] {yaml_file}: YAML parse error")

        except Exception as e:
            logger.error(f"Error processing {yaml_file}: {e}")
            self.error_count += 1
            print(f"  [ERROR] {yaml_file}: {e}")

    async def load_all(self) -> dict[str, int]:
        """
        Load all seed files from the entities directory.

        Returns:
            Summary dict with counts: {loaded, updated, skipped, errors}
        """
        # Ensure schema exists
        await self.ensure_schema()

        # Find all YAML files
        yaml_files = list(self.entities_dir.rglob("*.yaml"))
        yaml_files.extend(self.entities_dir.rglob("*.yml"))

        if not yaml_files:
            logger.warning(f"No YAML files found in {self.entities_dir}")
            print(f"No YAML files found in {self.entities_dir}")
            return {
                "loaded": 0,
                "updated": 0,
                "skipped": 0,
                "errors": 0,
            }

        print(f"\nFound {len(yaml_files)} seed file(s) in {self.entities_dir}")
        if self.dry_run:
            print("[DRY RUN MODE - No changes will be written]\n")
        print()

        # Process each file
        for yaml_file in sorted(yaml_files):
            await self.process_seed_file(yaml_file)

        return {
            "loaded": self.loaded_count,
            "updated": self.updated_count,
            "skipped": self.skipped_count,
            "errors": self.error_count,
        }


async def main_async(args: argparse.Namespace) -> int:
    """
    Async main function.

    Args:
        args: Parsed command line arguments

    Returns:
        Exit code (0 for success, 1 for errors)
    """
    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Resolve paths
    entities_dir = Path(args.entities_dir).resolve()
    db_path = Path(args.db_path).expanduser().resolve()

    # Validate entities directory
    if not entities_dir.exists():
        print(f"[ERROR] Entities directory not found: {entities_dir}")
        print(f"\nCreate it with: mkdir -p {entities_dir}")
        return 1

    if not entities_dir.is_dir():
        print(f"[ERROR] Not a directory: {entities_dir}")
        return 1

    print("=" * 60)
    print("Luna Engine Entity Seed Loader")
    print("=" * 60)
    print(f"\nEntities directory: {entities_dir}")
    print(f"Database path: {db_path}")

    if args.dry_run:
        print("\n*** DRY RUN MODE - No changes will be written ***")

    # Connect to database and load seeds
    db = MemoryDatabase(db_path)

    try:
        await db.connect()

        loader = EntitySeedLoader(
            db=db,
            entities_dir=entities_dir,
            dry_run=args.dry_run
        )

        summary = await loader.load_all()

        # Print summary
        print("\n" + "=" * 60)
        print("Summary")
        print("=" * 60)
        print(f"  Created: {summary['loaded']}")
        print(f"  Updated: {summary['updated']}")
        print(f"  Skipped: {summary['skipped']} (no changes)")
        print(f"  Errors:  {summary['errors']}")

        total_processed = summary['loaded'] + summary['updated'] + summary['skipped']
        print(f"\n  Total processed: {total_processed}")

        if args.dry_run:
            print("\n[DRY RUN] No changes were made to the database.")

        return 0 if summary['errors'] == 0 else 1

    except Exception as e:
        logger.exception("Fatal error")
        print(f"\n[ERROR] {e}")
        return 1

    finally:
        await db.close()


def main() -> int:
    """
    Main entry point.

    Returns:
        Exit code
    """
    parser = argparse.ArgumentParser(
        description="Load YAML entity seed files into Luna Engine database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Load from default locations
    python scripts/load_entity_seeds.py

    # Custom entities directory
    python scripts/load_entity_seeds.py --entities-dir ./my_entities

    # Custom database path
    python scripts/load_entity_seeds.py --db-path ./test.db

    # Preview changes without writing
    python scripts/load_entity_seeds.py --dry-run

    # Verbose output for debugging
    python scripts/load_entity_seeds.py --verbose

Entity YAML Format:
    id: entity-slug           # Optional, generated from name
    entity_type: person       # person | persona | place | project
    name: "Entity Name"       # Required
    aliases:                  # Optional
      - "Alias 1"
      - "Alias 2"
    core_facts:               # Optional, structured profile
      key: value
    full_profile: |           # Optional, extended markdown
      Extended profile text...
    voice_config:             # Optional, for personas
      tone: "..."
      patterns: [...]
    metadata:                 # Optional, flexible
      key: value
"""
    )

    # Get project root for default paths
    project_root = Path(__file__).parent.parent
    default_entities_dir = project_root / "entities"
    default_db_path = Path.home() / ".luna" / "luna.db"

    parser.add_argument(
        "--entities-dir",
        type=str,
        default=str(default_entities_dir),
        help=f"Path to entities directory with YAML files (default: {default_entities_dir})"
    )

    parser.add_argument(
        "--db-path",
        type=str,
        default=str(default_db_path),
        help=f"Path to SQLite database file (default: {default_db_path})"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without writing to database"
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose debug logging"
    )

    args = parser.parse_args()

    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
