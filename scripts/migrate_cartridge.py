#!/usr/bin/env python3
"""
Migrate Priests and Programmers from research_library.db into its own cartridge.

Usage:
    python3 scripts/migrate_cartridge.py

Creates:
    collections/priests-and-programmers/priests_and_programmers.db

Does NOT delete from research_library.db — keep as backup until verified.
"""
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Source
SRC_DB = PROJECT_ROOT / "data" / "local" / "research_library.db"
# Target
TARGET_DIR = PROJECT_ROOT / "collections" / "priests-and-programmers"
TARGET_DB = TARGET_DIR / "priests_and_programmers.db"

# The document to extract (only doc in research_library)
DOC_ID = "607b5b69-cc69-4799-9f57-1cdc3c53d530"


def main():
    if not SRC_DB.exists():
        print(f"ERROR: Source DB not found: {SRC_DB}")
        sys.exit(1)

    if TARGET_DB.exists():
        print(f"Target DB already exists: {TARGET_DB}")
        resp = input("Overwrite? [y/N] ").strip().lower()
        if resp != "y":
            print("Aborted.")
            sys.exit(0)
        TARGET_DB.unlink()

    TARGET_DIR.mkdir(parents=True, exist_ok=True)

    # Import schemas
    sys.path.insert(0, str(PROJECT_ROOT / "src"))
    from luna.substrate.aibrarian_schema import (
        CARTRIDGE_SCHEMA,
        INVESTIGATION_SCHEMA,
        STANDARD_SCHEMA,
    )

    # Create target DB with full schema
    dst = sqlite3.connect(str(TARGET_DB))
    dst.executescript(STANDARD_SCHEMA)
    dst.executescript(INVESTIGATION_SCHEMA)
    dst.executescript(CARTRIDGE_SCHEMA)

    # Connect source
    src = sqlite3.connect(str(SRC_DB))

    # Copy documents
    rows = src.execute("SELECT * FROM documents WHERE id = ?", (DOC_ID,)).fetchall()
    if not rows:
        print(f"ERROR: Document {DOC_ID} not found in source DB")
        sys.exit(1)
    cols = [d[0] for d in src.execute("SELECT * FROM documents LIMIT 0").description]
    placeholders = ", ".join(["?"] * len(cols))
    col_names = ", ".join(cols)
    for row in rows:
        dst.execute(f"INSERT INTO documents ({col_names}) VALUES ({placeholders})", row)
    print(f"Documents: {len(rows)}")

    # Copy chunks
    rows = src.execute("SELECT * FROM chunks WHERE doc_id = ?", (DOC_ID,)).fetchall()
    cols = [d[0] for d in src.execute("SELECT * FROM chunks LIMIT 0").description]
    placeholders = ", ".join(["?"] * len(cols))
    col_names = ", ".join(cols)
    for row in rows:
        dst.execute(f"INSERT INTO chunks ({col_names}) VALUES ({placeholders})", row)
    print(f"Chunks: {len(rows)}")

    # Copy extractions
    rows = src.execute(
        "SELECT * FROM extractions WHERE doc_id = ?", (DOC_ID,)
    ).fetchall()
    cols = [d[0] for d in src.execute("SELECT * FROM extractions LIMIT 0").description]
    placeholders = ", ".join(["?"] * len(cols))
    col_names = ", ".join(cols)
    for row in rows:
        dst.execute(f"INSERT INTO extractions ({col_names}) VALUES ({placeholders})", row)
    print(f"Extractions: {len(rows)}")

    # Copy entities
    rows = src.execute("SELECT * FROM entities WHERE doc_id = ?", (DOC_ID,)).fetchall()
    cols = [d[0] for d in src.execute("SELECT * FROM entities LIMIT 0").description]
    placeholders = ", ".join(["?"] * len(cols))
    col_names = ", ".join(cols)
    for row in rows:
        dst.execute(f"INSERT INTO entities ({col_names}) VALUES ({placeholders})", row)
    print(f"Entities: {len(rows)}")

    # Copy investigation tables if they have data for this doc
    for table in ("connections", "gaps", "claims"):
        try:
            # Check if doc_id column or source_doc_id column exists
            col_info = src.execute(f"PRAGMA table_info({table})").fetchall()
            doc_col = None
            for c in col_info:
                if c[1] in ("source_doc_id", "doc_id"):
                    doc_col = c[1]
                    break
            if doc_col:
                rows = src.execute(
                    f"SELECT * FROM {table} WHERE {doc_col} = ?", (DOC_ID,)
                ).fetchall()
                if rows:
                    cols = [d[0] for d in src.execute(f"SELECT * FROM {table} LIMIT 0").description]
                    placeholders = ", ".join(["?"] * len(cols))
                    col_names = ", ".join(cols)
                    for row in rows:
                        dst.execute(
                            f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})",
                            row,
                        )
                    print(f"{table}: {len(rows)}")
        except sqlite3.OperationalError:
            pass  # Table doesn't exist in source

    # Populate cartridge_meta
    doc_row = src.execute(
        "SELECT title, word_count FROM documents WHERE id = ?", (DOC_ID,)
    ).fetchone()
    dst.execute(
        "INSERT INTO cartridge_meta (id, title, description, author, version, "
        "document_type, language, tags, word_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "manifest",
            doc_row[0] or "Priests and Programmers",
            "Water temples and the politics of irrigation in Bali",
            "J. Stephen Lansing",
            "1.0.0",
            "book",
            "en",
            '["research", "academic", "anthropology", "complex-systems", "bali"]',
            doc_row[1],
        ),
    )
    print("cartridge_meta: populated")

    dst.commit()

    # Verify counts
    print("\n--- Verification ---")
    for table in ("documents", "chunks", "extractions", "entities", "cartridge_meta"):
        count = dst.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {count}")

    src.close()
    dst.close()

    print(f"\nCartridge created: {TARGET_DB}")
    print("Source research_library.db left intact (backup).")


if __name__ == "__main__":
    main()
