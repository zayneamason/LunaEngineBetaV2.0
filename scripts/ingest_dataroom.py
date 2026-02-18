#!/usr/bin/env python3
"""
Data Room Ingestion Pipeline
=============================

Reads the Master Index Sheet from Google Drive and creates/updates
DOCUMENT nodes in Luna's Memory Matrix.

Usage:
    python scripts/ingest_dataroom.py              # Normal sync
    python scripts/ingest_dataroom.py --dry-run    # Preview only
    python scripts/ingest_dataroom.py --force      # Re-sync all

Setup:
    1. Download OAuth credentials from Google Cloud Console
    2. Save as config/google_credentials.json
    3. Set sheet_id in config/dataroom.json
    4. Run — first run opens browser for consent
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from luna.substrate.database import MemoryDatabase
from luna.substrate.memory import MemoryMatrix
from luna.substrate.graph import MemoryGraph

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Local FILE_MAP (mirrors populate_dataroom.py)
# ---------------------------------------------------------------------------

from populate_dataroom import FILE_MAP

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CONFIG_PATH = PROJECT_ROOT / "config" / "dataroom.json"

IMPORTANCE_MAP = {
    "Final": 0.8,
    "Draft": 0.5,
    "Needs Review": 0.3,
}


def load_config() -> dict:
    """Load dataroom config from config/dataroom.json."""
    if not CONFIG_PATH.exists():
        print(f"ERROR: Config not found at {CONFIG_PATH}")
        print("Copy config/dataroom.json and fill in your sheet_id.")
        sys.exit(1)

    with open(CONFIG_PATH) as f:
        config = json.load(f)

    if config.get("sheet_id") == "YOUR_GOOGLE_SHEET_ID_HERE":
        print("ERROR: Update sheet_id in config/dataroom.json with your Master Index Sheet ID.")
        print("Find it in the sheet URL: docs.google.com/spreadsheets/d/{SHEET_ID}/edit")
        sys.exit(1)

    return config


# ---------------------------------------------------------------------------
# Google Sheets API
# ---------------------------------------------------------------------------

def authenticate_google_sheets(config: dict):
    """
    Authenticate with Google Sheets API via OAuth2.

    First run opens a browser for consent. Subsequent runs use cached token
    with auto-refresh.
    """
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

    creds_path = PROJECT_ROOT / config.get("credentials_path", "config/google_credentials.json")
    token_path = PROJECT_ROOT / config.get("token_path", "config/google_token.json")

    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not creds_path.exists():
                print(f"ERROR: Google OAuth credentials not found at {creds_path}")
                print("Download from Google Cloud Console → APIs & Services → Credentials")
                print("Create an OAuth 2.0 Client ID (Desktop app), download the JSON.")
                sys.exit(1)

            flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
            creds = flow.run_local_server(port=0)

        token_path.write_text(creds.to_json())
        print(f"Token saved to {token_path}")

    return build("sheets", "v4", credentials=creds)


def read_index_sheet(service, sheet_id: str, sheet_range: str) -> list[dict]:
    """Read the Master Index Sheet and return rows as dicts."""
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=sheet_id, range=sheet_range)
        .execute()
    )

    rows = result.get("values", [])
    if not rows:
        print("No data found in Master Index Sheet.")
        return []

    # Column order matches indexGenerator.gs output:
    # A: File ID, B: File Name, C: Category, D: Subfolder, E: File Type,
    # F: File Size, G: Created Date, H: Last Modified, I: Direct Link,
    # J: Tags, K: Status, L: Notes
    COLUMNS = [
        "file_id", "file_name", "category", "subfolder", "file_type",
        "file_size", "created_date", "last_modified", "direct_link",
        "tags", "status", "notes",
    ]

    parsed = []
    for row in rows:
        # Pad row to expected length
        padded = row + [""] * (len(COLUMNS) - len(row))
        entry = dict(zip(COLUMNS, padded))

        # Skip rows without a file ID
        if not entry["file_id"]:
            continue

        parsed.append(entry)

    return parsed


# ---------------------------------------------------------------------------
# Luna Memory Operations
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    """Convert category name to a slug for source IDs."""
    return text.lower().strip().replace(" ", "-").replace("&", "and").replace(".", "")


async def get_or_create_category(
    matrix: MemoryMatrix, graph: MemoryGraph, category_name: str, dry_run: bool = False
) -> str:
    """Get or create a CATEGORY node. Idempotent."""
    source = f"dataroom:category:{slugify(category_name)}"

    # Direct DB lookup by source
    existing = await matrix.db.fetchone(
        "SELECT id FROM memory_nodes WHERE source = ? AND node_type = 'CATEGORY'",
        (source,),
    )

    if existing:
        return existing[0]

    if dry_run:
        return f"[dry-run:category:{slugify(category_name)}]"

    node_id = await matrix.add_node(
        node_type="CATEGORY",
        content=f"Data Room Category: {category_name}",
        source=source,
        summary=category_name,
        confidence=1.0,
        importance=0.7,
        metadata={"category_type": "dataroom"},
        link_entities=False,
        scope="global",
    )

    logger.info(f"Created CATEGORY node: {category_name} ({node_id})")
    return node_id


async def process_document(
    matrix: MemoryMatrix,
    graph: MemoryGraph,
    row: dict,
    force: bool = False,
    dry_run: bool = False,
) -> tuple[str, str]:
    """
    Process a single document row from the index sheet.

    Returns:
        (node_id, action) where action is 'created', 'updated', or 'skipped'
    """
    file_id = row["file_id"]
    source = f"gdrive:{file_id}"

    # Build metadata
    metadata = {
        "gdrive_file_id": file_id,
        "gdrive_url": row["direct_link"],
        "category": row["category"],
        "subfolder": row["subfolder"],
        "file_type": row["file_type"],
        "file_size": row["file_size"],
        "last_synced": datetime.now().isoformat(),
        "status": row["status"] or "Draft",
        "tags": [t.strip() for t in row["tags"].split(",") if t.strip()],
    }

    # Generate summary
    summary = f"{row['file_name']} — {row['category']}"
    if row["status"]:
        summary += f" ({row['status']})"

    importance = IMPORTANCE_MAP.get(row["status"], 0.5)
    content = row["file_name"]
    if row["notes"]:
        content += f"\n{row['notes']}"

    # Check if node exists
    existing = await matrix.db.fetchone(
        "SELECT id, metadata FROM memory_nodes WHERE source = ?",
        (source,),
    )

    if existing:
        node_id = existing[0]
        existing_meta = json.loads(existing[1]) if existing[1] else {}

        # Skip if not forced and file hasn't been modified
        if not force and row["last_modified"] == existing_meta.get("last_modified_drive"):
            return node_id, "skipped"

        if dry_run:
            print(f"  [dry-run] Would UPDATE: {row['file_name']}")
            return node_id, "updated"

        metadata["last_modified_drive"] = row["last_modified"]
        await matrix.update_node(
            node_id,
            content=content,
            summary=summary,
            importance=importance,
            metadata=metadata,
        )
        return node_id, "updated"

    else:
        if dry_run:
            print(f"  [dry-run] Would CREATE: {row['file_name']}")
            return "[dry-run]", "created"

        metadata["last_modified_drive"] = row["last_modified"]
        node_id = await matrix.add_node(
            node_type="DOCUMENT",
            content=content,
            source=source,
            summary=summary,
            confidence=1.0,
            importance=importance,
            metadata=metadata,
            link_entities=True,
            scope="global",
        )

        # Create category node + BELONGS_TO edge
        category_id = await get_or_create_category(matrix, graph, row["category"], dry_run)
        if not graph.has_edge(node_id, category_id):
            await graph.add_edge(
                from_id=node_id,
                to_id=category_id,
                relationship="BELONGS_TO",
                strength=1.0,
                scope="global",
            )

        return node_id, "created"


async def cleanup_orphans(
    matrix: MemoryMatrix,
    current_file_ids: set[str],
    dry_run: bool = False,
) -> int:
    """Delete DOCUMENT nodes for files no longer in the index."""
    rows = await matrix.db.fetchall(
        "SELECT id, source FROM memory_nodes WHERE node_type = 'DOCUMENT' AND source LIKE 'gdrive:%'"
    )

    deleted = 0
    for row in rows:
        node_id = row[0]
        file_id = row[1].replace("gdrive:", "")

        if file_id not in current_file_ids:
            if dry_run:
                print(f"  [dry-run] Would DELETE orphan: {node_id} (file {file_id})")
            else:
                await matrix.delete_node(node_id)
                logger.info(f"Deleted orphan DOCUMENT node: {node_id}")
            deleted += 1

    return deleted


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build_local_index() -> list[dict]:
    """Build index data from local FILE_MAP instead of Google Sheets."""
    import mimetypes
    import os

    entries = []
    for rel_path, category in FILE_MAP:
        full_path = PROJECT_ROOT / rel_path
        if not full_path.exists():
            print(f"  MISSING: {rel_path}")
            continue

        stat = full_path.stat()
        ext = full_path.suffix.lower()
        mime = mimetypes.guess_type(str(full_path))[0] or "application/octet-stream"

        # Use relative path as a stable file_id (no Google Drive ID needed)
        stable_id = rel_path.replace("/", "__").replace(" ", "_")

        size_kb = stat.st_size / 1024
        if size_kb > 1024:
            size_str = f"{size_kb / 1024:.1f} MB"
        else:
            size_str = f"{size_kb:.0f} KB"

        entries.append({
            "file_id": stable_id,
            "file_name": full_path.name,
            "category": category,
            "subfolder": "",
            "file_type": ext.lstrip(".").upper() or mime,
            "file_size": size_str,
            "created_date": datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d"),
            "last_modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "direct_link": f"file://{full_path}",
            "tags": "",
            "status": "Draft",
            "notes": f"Local file: {rel_path}",
        })

    return entries


async def run(args):
    config = load_config()

    if args.local:
        print("Building index from local FILE_MAP...")
        index_data = build_local_index()
        print(f"Found {len(index_data)} local documents.")
    else:
        print("Authenticating with Google Sheets API...")
        service = authenticate_google_sheets(config)

        print(f"Reading Master Index Sheet ({config['sheet_id'][:20]}...)...")
        index_data = read_index_sheet(service, config["sheet_id"], config["sheet_range"])
        print(f"Found {len(index_data)} documents in index.")

    if not index_data:
        return

    # Connect to Luna's memory
    print("Connecting to Luna Memory Matrix...")
    db = MemoryDatabase()
    await db.connect()
    matrix = MemoryMatrix(db)
    graph = MemoryGraph(db)
    await graph.load_from_db()

    # Process documents
    created = 0
    updated = 0
    skipped = 0

    for row in index_data:
        node_id, action = await process_document(
            matrix, graph, row,
            force=args.force,
            dry_run=args.dry_run,
        )
        if action == "created":
            created += 1
        elif action == "updated":
            updated += 1
        else:
            skipped += 1

    # Cleanup orphans (only for sheet-based sync, not local)
    deleted = 0
    if not args.local:
        current_ids = {row["file_id"] for row in index_data}
        deleted = await cleanup_orphans(matrix, current_ids, dry_run=args.dry_run)

    # Summary
    prefix = "[DRY RUN] " if args.dry_run else ""
    source = "local FILE_MAP" if args.local else "index"
    print(f"\n{prefix}Sync complete:")
    print(f"  Documents: {len(index_data)} in {source}")
    print(f"  Created:   {created}")
    print(f"  Updated:   {updated}")
    print(f"  Skipped:   {skipped}")
    if not args.local:
        print(f"  Orphans:   {deleted} deleted")

    await db.close()


def main():
    parser = argparse.ArgumentParser(description="Ingest Google Drive Data Room into Luna Memory")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing to database")
    parser.add_argument("--force", action="store_true", help="Re-sync all documents regardless of modification date")
    parser.add_argument("--local", action="store_true", help="Ingest from local FILE_MAP instead of Google Sheets")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")

    asyncio.run(run(args))


if __name__ == "__main__":
    main()
