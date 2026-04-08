"""
Luna Engine Memory Database

SQLite connection manager for Luna Engine's Memory Matrix.
Uses WAL mode for concurrent access and aiosqlite for async operations.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional, Sequence

import aiosqlite

from luna.core.paths import project_root, data_dir, user_dir

logger = logging.getLogger(__name__)


class MemoryDatabase:
    """
    Async SQLite database manager for Luna's memory substrate.

    Manages SQLite connection with WAL mode for concurrent read/write access.
    Automatically loads schema on first run and handles graceful shutdown
    with WAL checkpoint.

    Usage:
        async with MemoryDatabase() as db:
            await db.execute("INSERT INTO memory_nodes ...")
            row = await db.fetchone("SELECT * FROM memory_nodes WHERE id = ?", (id,))

    Or manually:
        db = MemoryDatabase()
        await db.connect()
        try:
            ...
        finally:
            await db.close()
    """

    # Use project's data directory, not ~/.luna (which caused memory wipe)
    # See: Docs/LUNA ENGINE Bible/Handoffs/HANDOFF-MEMORY-WIPE-INVESTIGATION.md
    DEFAULT_DB_DIR = user_dir()
    DEFAULT_DB_NAME = "luna_engine.db"

    def __init__(self, db_path: Optional[Path] = None) -> None:
        """
        Initialize the database manager.

        Args:
            db_path: Path to the SQLite database file.
                     Defaults to ~/.luna/luna.db
        """
        if db_path is None:
            db_path = self.DEFAULT_DB_DIR / self.DEFAULT_DB_NAME

        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None
        # Resolve schema.sql — check multiple locations for dev vs compiled mode.
        _candidates = [
            project_root() / "data" / "schema.sql",                        # compiled binary
            project_root() / "data" / "user" / "schema.sql",              # Forge build layout
            project_root() / "src" / "luna" / "substrate" / "schema.sql",  # dev mode
            Path(__file__).parent / "schema.sql",                          # fallback
        ]
        self._schema_path = next((c for c in _candidates if c.exists()), _candidates[-1])

    @property
    def is_connected(self) -> bool:
        """Check if database connection is active."""
        return self._connection is not None

    async def connect(self) -> None:
        """
        Open database connection and initialize schema.

        Creates the database directory if it doesn't exist.
        Enables WAL mode for better concurrent access.
        Loads schema from schema.sql on first run.
        """
        if self._connection is not None:
            logger.warning("Database already connected")
            return

        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Connecting to database: {self.db_path}")

        # Open connection
        self._connection = await aiosqlite.connect(self.db_path)

        # Enable WAL mode for concurrent access
        await self._connection.execute("PRAGMA journal_mode=WAL")

        # Set busy timeout (5 seconds) to handle concurrent writes
        await self._connection.execute("PRAGMA busy_timeout=15000")

        # Enable foreign keys
        await self._connection.execute("PRAGMA foreign_keys=ON")

        # Set reasonable cache size (negative = KB)
        await self._connection.execute("PRAGMA cache_size=-64000")  # 64MB

        # Load schema
        await self._load_schema()

        logger.info("Database connected and schema loaded")

    async def _load_schema(self) -> None:
        """Load and execute schema.sql to create tables."""
        if not self._schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {self._schema_path}")

        schema_sql = self._schema_path.read_text()

        # Execute schema (executescript equivalent for aiosqlite)
        await self._connection.executescript(schema_sql)
        await self._connection.commit()

        # Run migrations for existing databases
        await self._migrate_scope_columns()
        await self._migrate_origin_columns()
        await self._migrate_ambassador_tables()
        await self._migrate_aperture_tables()
        await self._migrate_lunascript_tables()

        logger.debug("Schema loaded successfully")

    async def _migrate_lunascript_tables(self) -> None:
        """Create LunaScript cognitive signature tables if missing (v2.4 migration)."""
        try:
            from luna.lunascript.schema import apply_lunascript_schema
            await apply_lunascript_schema(self)
            await self._connection.commit()
            logger.debug("LunaScript tables ready")
        except ImportError:
            logger.debug("LunaScript module not available, skipping migration")
        except Exception as e:
            logger.debug(f"LunaScript migration skip: {e}")

    async def _migrate_scope_columns(self) -> None:
        """Add scope columns to existing tables if missing (v2.1 migration)."""
        migrations = [
            ("memory_nodes", "scope", "ALTER TABLE memory_nodes ADD COLUMN scope TEXT NOT NULL DEFAULT 'global'"),
            ("graph_edges", "scope", "ALTER TABLE graph_edges ADD COLUMN scope TEXT NOT NULL DEFAULT 'global'"),
        ]

        for table, column, alter_sql in migrations:
            try:
                cursor = await self._connection.execute(f"PRAGMA table_info({table})")
                columns = await cursor.fetchall()
                col_names = [col[1] for col in columns]

                if column not in col_names:
                    await self._connection.execute(alter_sql)
                    logger.info(f"Migration: added '{column}' column to {table}")
            except Exception as e:
                # Column may already exist (race condition) — safe to ignore
                logger.debug(f"Migration skip for {table}.{column}: {e}")

        # Create scope indexes (must be after ALTER TABLE, not in schema.sql)
        scope_indexes = [
            "CREATE INDEX IF NOT EXISTS idx_nodes_scope ON memory_nodes(scope)",
            "CREATE INDEX IF NOT EXISTS idx_nodes_scope_type ON memory_nodes(scope, node_type)",
            "CREATE INDEX IF NOT EXISTS idx_edges_scope ON graph_edges(scope)",
        ]
        for idx_sql in scope_indexes:
            try:
                await self._connection.execute(idx_sql)
            except Exception as e:
                logger.debug(f"Scope index skip: {e}")

        await self._connection.commit()

    async def _migrate_origin_columns(self) -> None:
        """Add origin columns to entities and graph_edges if missing (v2.5 migration)."""
        migrations = [
            ("entities", "origin", "ALTER TABLE entities ADD COLUMN origin TEXT NOT NULL DEFAULT 'user'"),
            ("graph_edges", "origin", "ALTER TABLE graph_edges ADD COLUMN origin TEXT NOT NULL DEFAULT 'user'"),
        ]

        for table, column, alter_sql in migrations:
            try:
                cursor = await self._connection.execute(f"PRAGMA table_info({table})")
                columns = await cursor.fetchall()
                col_names = [col[1] for col in columns]

                if column not in col_names:
                    await self._connection.execute(alter_sql)
                    logger.info(f"Migration: added '{column}' column to {table}")
            except Exception as e:
                logger.debug(f"Migration skip for {table}.{column}: {e}")

        # Backfill entities: personas are system, seed_loader entries are seed
        try:
            await self._connection.execute(
                "UPDATE entities SET origin = 'system' WHERE entity_type = 'persona' AND origin = 'user'"
            )
            await self._connection.execute(
                "UPDATE entities SET origin = 'seed' "
                "WHERE id IN (SELECT DISTINCT entity_id FROM entity_versions WHERE changed_by = 'seed_loader') "
                "AND origin = 'user'"
            )
        except Exception as e:
            logger.debug(f"Origin backfill skip: {e}")

        # Create indexes
        for idx_sql in [
            "CREATE INDEX IF NOT EXISTS idx_entities_origin ON entities(origin)",
            "CREATE INDEX IF NOT EXISTS idx_edges_origin ON graph_edges(origin)",
        ]:
            try:
                await self._connection.execute(idx_sql)
            except Exception as e:
                logger.debug(f"Origin index skip: {e}")

        await self._connection.commit()

    async def _migrate_ambassador_tables(self) -> None:
        """Create ambassador protocol tables if missing (v2.2 migration)."""
        migration_path = project_root() / "migrations" / "004_ambassador_protocol.sql"
        if not migration_path.exists():
            logger.debug("Ambassador migration file not found, skipping")
            return

        try:
            # Check if table already exists
            cursor = await self._connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='ambassador_protocol'"
            )
            if await cursor.fetchone():
                logger.debug("Ambassador tables already exist, skipping migration")
                return

            migration_sql = migration_path.read_text()
            await self._connection.executescript(migration_sql)
            await self._connection.commit()
            logger.info("Migration: created ambassador_protocol and ambassador_audit_log tables")
        except Exception as e:
            logger.debug(f"Ambassador migration skip: {e}")

    async def _migrate_aperture_tables(self) -> None:
        """Create aperture & library cognition tables if missing (v2.3 migration)."""
        tables_to_check = [
            ("collection_lock_in", """
                CREATE TABLE IF NOT EXISTS collection_lock_in (
                    collection_key TEXT PRIMARY KEY,
                    lock_in REAL DEFAULT 0.15,
                    state TEXT DEFAULT 'drifting',
                    access_count INTEGER DEFAULT 0,
                    annotation_count INTEGER DEFAULT 0,
                    connected_collections INTEGER DEFAULT 0,
                    entity_overlap_count INTEGER DEFAULT 0,
                    last_accessed_at TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now'))
                )
            """),
            ("collection_annotations", """
                CREATE TABLE IF NOT EXISTS collection_annotations (
                    id TEXT PRIMARY KEY,
                    collection_key TEXT NOT NULL,
                    doc_id TEXT NOT NULL,
                    chunk_index INTEGER,
                    annotation_type TEXT NOT NULL,
                    content TEXT,
                    matrix_node_id TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                )
            """),
        ]

        for table_name, create_sql in tables_to_check:
            try:
                cursor = await self._connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table_name,),
                )
                if not await cursor.fetchone():
                    await self._connection.execute(create_sql)
                    logger.info(f"Migration: created {table_name} table")
            except Exception as e:
                logger.debug(f"Migration skip for {table_name}: {e}")

        # Create indexes
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_coll_lock_in_state ON collection_lock_in(state)",
            "CREATE INDEX IF NOT EXISTS idx_coll_lock_in_score ON collection_lock_in(lock_in DESC)",
            "CREATE INDEX IF NOT EXISTS idx_annotations_collection ON collection_annotations(collection_key)",
            "CREATE INDEX IF NOT EXISTS idx_annotations_type ON collection_annotations(annotation_type)",
            "CREATE INDEX IF NOT EXISTS idx_annotations_doc ON collection_annotations(collection_key, doc_id)",
        ]
        for idx_sql in indexes:
            try:
                await self._connection.execute(idx_sql)
            except Exception as e:
                logger.debug(f"Aperture index skip: {e}")

        await self._connection.commit()

    async def close(self) -> None:
        """
        Close database connection gracefully.

        Performs WAL checkpoint to merge WAL file back into main database,
        then closes the connection.
        """
        if self._connection is None:
            logger.warning("Database not connected")
            return

        logger.info("Closing database connection")

        try:
            # Checkpoint WAL to merge changes into main database
            await self._connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            await self._connection.commit()
            logger.debug("WAL checkpoint completed")
        except Exception as e:
            logger.warning(f"WAL checkpoint failed: {e}")

        await self._connection.close()
        self._connection = None

        logger.info("Database connection closed")

    def _ensure_connected(self) -> aiosqlite.Connection:
        """Ensure we have an active connection."""
        if self._connection is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._connection

    async def execute(
        self,
        sql: str,
        params: Optional[Sequence[Any]] = None
    ) -> aiosqlite.Cursor:
        """
        Execute a single SQL statement.

        Args:
            sql: SQL statement to execute
            params: Optional parameters for the statement

        Returns:
            The cursor from the execution
        """
        conn = self._ensure_connected()
        cursor = await conn.execute(sql, params or ())
        await conn.commit()
        return cursor

    async def executemany(
        self,
        sql: str,
        params_list: Sequence[Sequence[Any]]
    ) -> aiosqlite.Cursor:
        """
        Execute a SQL statement with multiple parameter sets.

        Useful for batch inserts.

        Args:
            sql: SQL statement to execute
            params_list: List of parameter tuples

        Returns:
            The cursor from the execution
        """
        conn = self._ensure_connected()
        cursor = await conn.executemany(sql, params_list)
        await conn.commit()
        return cursor

    async def fetchone(
        self,
        sql: str,
        params: Optional[Sequence[Any]] = None
    ) -> Optional[aiosqlite.Row]:
        """
        Execute query and fetch a single row.

        Args:
            sql: SQL query to execute
            params: Optional parameters for the query

        Returns:
            The first row of results, or None if no results
        """
        conn = self._ensure_connected()
        async with conn.execute(sql, params or ()) as cursor:
            return await cursor.fetchone()

    async def fetchall(
        self,
        sql: str,
        params: Optional[Sequence[Any]] = None
    ) -> list[aiosqlite.Row]:
        """
        Execute query and fetch all rows.

        Args:
            sql: SQL query to execute
            params: Optional parameters for the query

        Returns:
            List of all result rows
        """
        conn = self._ensure_connected()
        async with conn.execute(sql, params or ()) as cursor:
            return await cursor.fetchall()

    async def __aenter__(self) -> MemoryDatabase:
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()
