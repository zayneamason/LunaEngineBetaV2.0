"""
Luna Knowledge Cartridge (.lun)
===============================

A .lun file is a standalone SQLite database containing a document's
complete node tree, comprehension artifacts anchored to source nodes,
and embeddings for search.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Optional

from .builder import CartridgeBuilder
from .schema import LUN_SCHEMA

logger = logging.getLogger(__name__)

__all__ = ["CartridgeBuilder", "LUN_SCHEMA", "resolve_source_ref"]


def resolve_source_ref(lun_path: Path | str, node_id: int) -> Optional[dict]:
    """Walk the parent chain from a node_id to build a source reference.

    Returns:
        {
            "cartridge": "filename.lun",
            "node_id": int,
            "node_type": str,
            "content": str,
            "section": str (nearest section heading),
            "section_path": ["Document Title", "Chapter 1", "Section 1.2"],
            "position_in_parent": int,
            "claims": [{"id": int, "content": str, "confidence": float}],
        }
    """
    lun_path = Path(lun_path)
    if not lun_path.exists():
        return None

    conn = sqlite3.connect(f"file:{lun_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    try:
        # Read the node
        node = conn.execute(
            "SELECT id, parent_id, type, content, position FROM doc_nodes WHERE id = ?",
            (node_id,),
        ).fetchone()

        if not node:
            return None

        # Walk parent chain to build section_path
        section_path = []
        current_id = node["parent_id"]
        nearest_section = None

        while current_id is not None:
            parent = conn.execute(
                "SELECT id, parent_id, type, content, meta_json FROM doc_nodes WHERE id = ?",
                (current_id,),
            ).fetchone()

            if parent is None:
                break

            if parent["type"] == "section" and parent["content"]:
                section_path.append(parent["content"])
                if nearest_section is None:
                    nearest_section = parent["content"]
            elif parent["type"] == "document":
                meta = json.loads(parent["meta_json"]) if parent["meta_json"] else {}
                title = meta.get("title", "")
                if title:
                    section_path.append(title)

            current_id = parent["parent_id"]

        section_path.reverse()

        # Query claims anchored to this node
        claims = conn.execute(
            """
            SELECT e.id, e.content, e.confidence
            FROM extractions e
            JOIN claim_sources cs ON e.id = cs.claim_id
            WHERE cs.node_id = ?
            """,
            (node_id,),
        ).fetchall()

        return {
            "cartridge": lun_path.name,
            "node_id": node["id"],
            "node_type": node["type"],
            "content": node["content"] or "",
            "section": nearest_section or "",
            "section_path": section_path,
            "position_in_parent": node["position"],
            "claims": [
                {"id": c["id"], "content": c["content"], "confidence": c["confidence"]}
                for c in claims
            ],
        }

    finally:
        conn.close()
