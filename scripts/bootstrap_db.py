#!/usr/bin/env python3
"""
Luna Engine Database Bootstrap Script

Creates and initializes the Luna Engine SQLite database with:
- All tables from schema.sql
- sqlite-vec extension for embeddings
- memory_embeddings virtual table
- Verification of all required components

Usage:
    python scripts/bootstrap_db.py                    # Default: data/luna_engine.db
    python scripts/bootstrap_db.py --path /path/to.db # Custom path
    python scripts/bootstrap_db.py --path :memory:    # In-memory for testing

Exit codes:
    0 - Success
    1 - Failure
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

# Default embedding dimension (matches OpenAI text-embedding-3-small)
DEFAULT_EMBEDDING_DIM = 1536

# Required tables
REQUIRED_TABLES = [
    "memory_nodes",
    "conversation_turns",
    "graph_edges",
    "sessions",
    "consciousness_snapshots",
]

# Required columns on memory_nodes
REQUIRED_MEMORY_NODES_COLUMNS = [
    "reinforcement_count",
    "lock_in",
    "lock_in_state",
]

# Required indexes
REQUIRED_INDEXES = [
    "idx_nodes_lock_in",
    "idx_nodes_lock_in_state",
]


def get_schema_path() -> Path:
    """Get the path to schema.sql relative to this script."""
    script_dir = Path(__file__).parent.resolve()
    project_root = script_dir.parent
    return project_root / "src" / "luna" / "substrate" / "schema.sql"


def load_sqlite_vec(conn: sqlite3.Connection) -> bool:
    """
    Load the sqlite-vec extension.

    Returns True if loaded successfully, False otherwise.
    """
    try:
        import sqlite_vec

        conn.enable_load_extension(True)
        ext_path = sqlite_vec.loadable_path()
        conn.execute("SELECT load_extension(?)", (ext_path,))
        conn.enable_load_extension(False)

        print("[OK] sqlite-vec extension loaded")
        return True

    except ImportError:
        print("[WARN] sqlite-vec package not installed (pip install sqlite-vec)")
        print("[WARN] memory_embeddings table will not be created")
        return False
    except Exception as e:
        print(f"[WARN] Failed to load sqlite-vec extension: {e}")
        print("[WARN] memory_embeddings table will not be created")
        return False


def create_embeddings_table(conn: sqlite3.Connection, dim: int = DEFAULT_EMBEDDING_DIM) -> bool:
    """
    Create the memory_embeddings virtual table using sqlite-vec.

    Returns True if created successfully.
    """
    try:
        conn.execute(f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS memory_embeddings USING vec0(
                node_id TEXT PRIMARY KEY,
                embedding FLOAT[{dim}]
            )
        """)
        conn.commit()
        print(f"[OK] memory_embeddings virtual table created ({dim}-dim vectors)")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to create memory_embeddings table: {e}")
        return False


def verify_tables(conn: sqlite3.Connection) -> bool:
    """Verify all required tables exist."""
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )
    existing_tables = {row[0] for row in cursor.fetchall()}

    all_ok = True
    for table in REQUIRED_TABLES:
        if table in existing_tables:
            print(f"[OK] Table exists: {table}")
        else:
            print(f"[ERROR] Table missing: {table}")
            all_ok = False

    return all_ok


def verify_memory_nodes_columns(conn: sqlite3.Connection) -> bool:
    """Verify required columns exist on memory_nodes table."""
    cursor = conn.execute("PRAGMA table_info(memory_nodes)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    all_ok = True
    for col in REQUIRED_MEMORY_NODES_COLUMNS:
        if col in existing_columns:
            print(f"[OK] Column exists on memory_nodes: {col}")
        else:
            print(f"[ERROR] Column missing on memory_nodes: {col}")
            all_ok = False

    return all_ok


def verify_indexes(conn: sqlite3.Connection) -> bool:
    """Verify required indexes exist."""
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index'"
    )
    existing_indexes = {row[0] for row in cursor.fetchall()}

    all_ok = True
    for idx in REQUIRED_INDEXES:
        if idx in existing_indexes:
            print(f"[OK] Index exists: {idx}")
        else:
            print(f"[ERROR] Index missing: {idx}")
            all_ok = False

    return all_ok


def verify_embeddings_table(conn: sqlite3.Connection) -> bool:
    """Verify memory_embeddings virtual table exists."""
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='memory_embeddings'"
    )
    exists = cursor.fetchone() is not None

    if exists:
        print("[OK] Virtual table exists: memory_embeddings")
    else:
        print("[WARN] Virtual table missing: memory_embeddings (sqlite-vec not available)")

    return exists


def bootstrap_database(db_path: str, embedding_dim: int = DEFAULT_EMBEDDING_DIM) -> bool:
    """
    Bootstrap the Luna Engine database.

    Args:
        db_path: Path to database file, or ":memory:" for in-memory
        embedding_dim: Dimension for embedding vectors

    Returns:
        True if successful, False otherwise
    """
    schema_path = get_schema_path()

    # Validate schema exists
    if not schema_path.exists():
        print(f"[ERROR] Schema file not found: {schema_path}")
        return False

    print(f"Schema file: {schema_path}")

    # Handle file path (create parent dirs if needed)
    if db_path != ":memory:":
        db_path_obj = Path(db_path)
        db_path_obj.parent.mkdir(parents=True, exist_ok=True)
        print(f"Database path: {db_path_obj.resolve()}")
    else:
        print("Database path: :memory: (in-memory)")

    # Connect to database
    try:
        conn = sqlite3.connect(db_path)
        print("[OK] Database connection established")
    except Exception as e:
        print(f"[ERROR] Failed to connect to database: {e}")
        return False

    try:
        # Enable WAL mode for file-based databases
        if db_path != ":memory:":
            conn.execute("PRAGMA journal_mode=WAL")
            print("[OK] WAL mode enabled")

        # Enable foreign keys
        conn.execute("PRAGMA foreign_keys=ON")
        print("[OK] Foreign keys enabled")

        # Load and execute schema
        print("\n--- Loading Schema ---")
        schema_sql = schema_path.read_text()
        conn.executescript(schema_sql)
        conn.commit()
        print("[OK] Schema loaded successfully")

        # Load sqlite-vec and create embeddings table
        print("\n--- Setting Up Embeddings ---")
        vec_loaded = load_sqlite_vec(conn)
        embeddings_created = False
        if vec_loaded:
            embeddings_created = create_embeddings_table(conn, embedding_dim)

        # Verification
        print("\n--- Verification ---")
        tables_ok = verify_tables(conn)
        columns_ok = verify_memory_nodes_columns(conn)
        indexes_ok = verify_indexes(conn)
        embeddings_ok = verify_embeddings_table(conn)

        # Final checkpoint for WAL
        if db_path != ":memory:":
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.commit()

        conn.close()

        # Summary
        print("\n--- Summary ---")
        core_ok = tables_ok and columns_ok and indexes_ok

        if core_ok:
            print("[SUCCESS] Core database setup complete")
            if embeddings_ok:
                print("[SUCCESS] Embeddings table ready")
            else:
                print("[INFO] Embeddings table not available (semantic search disabled)")
            return True
        else:
            print("[FAILURE] Database setup incomplete - see errors above")
            return False

    except Exception as e:
        print(f"[ERROR] Database bootstrap failed: {e}")
        conn.close()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Bootstrap Luna Engine database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/bootstrap_db.py                        # Default path
    python scripts/bootstrap_db.py --path ./test.db       # Custom path
    python scripts/bootstrap_db.py --path :memory:        # In-memory testing
    python scripts/bootstrap_db.py --dim 384              # Custom embedding dim
        """
    )

    parser.add_argument(
        "--path",
        type=str,
        default="data/luna_engine.db",
        help="Path to database file (default: data/luna_engine.db). Use :memory: for testing."
    )

    parser.add_argument(
        "--dim",
        type=int,
        default=DEFAULT_EMBEDDING_DIM,
        help=f"Embedding dimension (default: {DEFAULT_EMBEDDING_DIM})"
    )

    args = parser.parse_args()

    print("=" * 50)
    print("Luna Engine Database Bootstrap")
    print("=" * 50)
    print()

    success = bootstrap_database(args.path, args.dim)

    print()
    print("=" * 50)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
