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

    DEFAULT_DB_DIR = Path.home() / ".luna"
    DEFAULT_DB_NAME = "luna.db"

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
        self._schema_path = Path(__file__).parent / "schema.sql"

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

        logger.debug("Schema loaded successfully")

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
