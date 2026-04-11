"""
Cartridge Builder
=================

Orchestrator: source file → .lun SQLite cartridge.

Usage:
    python -m luna.cartridge.builder input.md [output.lun]
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .schema import LUN_SCHEMA

logger = logging.getLogger(__name__)


class CartridgeBuilder:
    """Build .lun Knowledge Cartridges from source documents."""

    def __init__(
        self,
        output_dir: Path | str | None = None,
        extract: bool = True,
        embed: bool = True,
    ):
        self.output_dir = Path(output_dir) if output_dir else None
        self.do_extract = extract
        self.do_embed = embed

    async def build(self, source_path: Path | str, output_path: Path | str | None = None) -> Path:
        """Build a .lun cartridge from a source file.

        Args:
            source_path: Path to the source document (.md)
            output_path: Optional explicit output path. If None, derived from source.

        Returns:
            Path to the generated .lun file.
        """
        source_path = Path(source_path)

        if not source_path.exists():
            raise FileNotFoundError(f"Source file not found: {source_path}")

        ext = source_path.suffix.lower()
        if ext not in (".md", ".markdown", ".pdf"):
            raise ValueError(f"Unsupported format: {ext}. Supported: .md, .pdf")

        # Determine output path
        if output_path:
            lun_path = Path(output_path)
        elif self.output_dir:
            lun_path = self.output_dir / f"{source_path.stem}.lun"
        else:
            lun_path = source_path.with_suffix(".lun")

        lun_path.parent.mkdir(parents=True, exist_ok=True)

        # Remove existing cartridge (rebuild)
        if lun_path.exists():
            lun_path.unlink()

        logger.info("[CARTRIDGE] Building %s → %s", source_path.name, lun_path.name)

        # Parse
        if ext == ".pdf":
            from .parsers.pdf import PDFParser
            parser = PDFParser()
        else:
            from .parsers.markdown import MarkdownParser
            parser = MarkdownParser()
        nodes = parser.parse(source_path)
        logger.info("[CARTRIDGE] Parsed %d nodes from %s", len(nodes), source_path.name)

        # Create database
        conn = sqlite3.connect(str(lun_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=15000")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(LUN_SCHEMA)

        # Insert nodes — remap parent_idx to parent_id
        idx_to_db_id: dict[int, int] = {}

        for idx, node in enumerate(nodes):
            parent_idx = node.get("parent_idx")
            parent_id = idx_to_db_id.get(parent_idx) if parent_idx is not None else None
            meta_json = json.dumps(node.get("meta")) if node.get("meta") else None

            cursor = conn.execute(
                "INSERT INTO doc_nodes (parent_id, type, position, content, meta_json) "
                "VALUES (?, ?, ?, ?, ?)",
                (parent_id, node["type"], node["position"], node.get("content"), meta_json),
            )
            idx_to_db_id[idx] = cursor.lastrowid

        # Write meta
        source_bytes = source_path.read_bytes()
        source_hash = hashlib.sha256(source_bytes).hexdigest()

        # Extract title from first section or filename
        title = source_path.stem
        for node in nodes:
            if node["type"] == "section" and node.get("content"):
                title = node["content"]
                break

        word_count = sum(
            len(n.get("content", "").split())
            for n in nodes
            if n.get("content")
        )

        source_format = "pdf" if ext == ".pdf" else "markdown"

        meta_entries = {
            "title": title,
            "source_path": str(source_path.resolve()),
            "source_format": source_format,
            "source_hash": source_hash,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "schema_version": "1",
            "word_count": str(word_count),
            "node_count": str(len(nodes)),
            "embedding_model": "all-MiniLM-L6-v2",
            "embedding_dim": "384",
        }

        for key, value in meta_entries.items():
            conn.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
                (key, value),
            )

        conn.commit()

        # Extraction pass
        if self.do_extract:
            try:
                from .extractor import CartridgeExtractor
                extractor = CartridgeExtractor()
                if extractor.is_available:
                    count = await extractor.extract(conn)
                    logger.info("[CARTRIDGE] Extraction: %d artifacts", count)
                else:
                    logger.warning("[CARTRIDGE] Haiku not available — skipping extraction")
            except Exception as e:
                logger.warning("[CARTRIDGE] Extraction failed (non-fatal): %s", e)

        # Embedding pass
        if self.do_embed:
            try:
                from .embedder import CartridgeEmbedder
                embedder = CartridgeEmbedder()
                count = await embedder.embed(conn)
                logger.info("[CARTRIDGE] Embeddings: %d vectors", count)
            except Exception as e:
                logger.warning("[CARTRIDGE] Embedding failed (non-fatal): %s", e)

        conn.close()
        logger.info("[CARTRIDGE] Built %s (%d nodes, %d words)", lun_path.name, len(nodes), word_count)
        return lun_path


# ---------------------------------------------------------------------------
# CLI entry point: python -m luna.cartridge.builder input.md [output.lun]
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import asyncio
    import sys

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if len(sys.argv) < 2:
        print("Usage: python -m luna.cartridge.builder <input.md|input.pdf> [output.lun]")
        print("       python -m luna.cartridge.builder input.pdf --no-extract --no-embed")
        sys.exit(1)

    source = Path(sys.argv[1])
    output = None
    do_extract = True
    do_embed = True

    for arg in sys.argv[2:]:
        if arg == "--no-extract":
            do_extract = False
        elif arg == "--no-embed":
            do_embed = False
        elif not arg.startswith("--"):
            output = Path(arg)

    builder = CartridgeBuilder(extract=do_extract, embed=do_embed)
    result = asyncio.run(builder.build(source, output))
    print(f"Built: {result}")
