"""
Cartridge Extractor
===================

LLM-based extraction pass for .lun cartridges.
Walks sections, sends text to Haiku, writes claims/entities/summaries
with source anchoring back to specific nodes.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from typing import Optional

logger = logging.getLogger(__name__)

CARTRIDGE_EXTRACTION_PROMPT = """\
You are extracting structured knowledge from a document section
for a long-term memory system.

Extract the following from the provided text:

1. SUMMARY: A 1-2 sentence summary of what this section covers.

2. CLAIMS: Key arguments, assertions, or findings.
   For each claim, include a short verbatim quote from the source
   that supports it. Include 3-10 claims per section.

3. ENTITIES: People, places, systems, organizations, and concepts
   mentioned. For each entity, note its type.

Return ONLY valid JSON:
{
  "summary": "Section summary...",
  "claims": [
    {"content": "The claim in your own words", "quote": "exact words from the source"}
  ],
  "entities": [
    {"name": "Entity Name", "type": "person|place|organization|concept|event"}
  ]
}

RULES:
- Be specific: include names, numbers, dates when present
- Claims must be attributable to the text
- Quotes must be verbatim substrings from the source text
- If the text is a title page, table of contents, or index,
  return {"summary": "", "claims": [], "entities": []}
- Return ONLY JSON. No markdown, no explanation.
"""


class CartridgeExtractor:
    """Extract claims, entities, and summaries from a .lun node tree."""

    def __init__(self):
        self._backend = None

    def _get_backend(self):
        if self._backend is None:
            from luna.inference.haiku_subtask_backend import HaikuSubtaskBackend
            self._backend = HaikuSubtaskBackend()
        return self._backend

    @property
    def is_available(self) -> bool:
        try:
            return self._get_backend().is_loaded
        except Exception:
            return False

    async def extract(self, conn: sqlite3.Connection) -> int:
        """Run extraction on all sections. Returns count of extractions created."""
        backend = self._get_backend()
        if not backend.is_loaded:
            logger.warning("[CARTRIDGE-EXTRACTOR] Haiku backend not available — skipping extraction")
            return 0

        # Gather sections with descendant text
        sections = conn.execute(
            "SELECT id, content FROM doc_nodes WHERE type = 'section'"
        ).fetchall()

        total_extractions = 0

        for section_id, section_heading in sections:
            # Get all sentence/paragraph content under this section
            descendants = conn.execute(
                """
                WITH RECURSIVE subtree AS (
                    SELECT id, content, type FROM doc_nodes WHERE id = ?
                    UNION ALL
                    SELECT d.id, d.content, d.type FROM doc_nodes d
                    JOIN subtree s ON d.parent_id = s.id
                )
                SELECT id, content, type FROM subtree
                WHERE type IN ('sentence', 'list_item', 'cell')
                AND content IS NOT NULL AND content != ''
                ORDER BY id
                """,
                (section_id,),
            ).fetchall()

            if not descendants:
                continue

            section_text = "\n".join(row[1] for row in descendants)
            if len(section_text.strip()) < 50:
                continue

            # Call Haiku
            try:
                user_msg = f"Section: {section_heading or 'Untitled'}\n\nTEXT:\n{section_text[:8000]}"
                result = await backend.generate(
                    user_message=user_msg,
                    system_prompt=CARTRIDGE_EXTRACTION_PROMPT,
                    max_tokens=4096,
                )

                # Parse JSON
                raw = result.text.strip()
                raw = re.sub(r"^```json\s*", "", raw)
                raw = re.sub(r"\s*```$", "", raw)
                data = json.loads(raw)

            except json.JSONDecodeError as e:
                logger.warning("[CARTRIDGE-EXTRACTOR] JSON parse failed for section '%s': %s", section_heading, e)
                continue
            except Exception as e:
                logger.warning("[CARTRIDGE-EXTRACTOR] Haiku call failed for section '%s': %s", section_heading, e)
                continue

            # Build sentence lookup for anchoring
            sentence_nodes = [(row[0], row[1]) for row in descendants if row[2] == "sentence"]

            # Write summary
            summary = data.get("summary", "")
            if summary:
                cursor = conn.execute(
                    "INSERT INTO extractions (type, content, confidence) VALUES (?, ?, ?)",
                    ("summary", summary, 0.9),
                )
                total_extractions += 1

            # Write claims with source anchoring
            for claim in data.get("claims", []):
                content = claim.get("content", "")
                quote = claim.get("quote", "")
                if not content:
                    continue

                cursor = conn.execute(
                    "INSERT INTO extractions (type, content, confidence) VALUES (?, ?, ?)",
                    ("claim", content, 0.85),
                )
                claim_id = cursor.lastrowid
                total_extractions += 1

                # Fuzzy-match quote to sentence nodes
                if quote:
                    self._anchor_claim(conn, claim_id, quote, sentence_nodes)

            # Write entities
            for entity in data.get("entities", []):
                name = entity.get("name", "")
                etype = entity.get("type", "concept")
                if not name:
                    continue

                conn.execute(
                    "INSERT INTO extractions (type, content, confidence) VALUES (?, ?, ?)",
                    ("entity", f"{name} [{etype}]", 0.85),
                )
                total_extractions += 1

        conn.commit()
        logger.info("[CARTRIDGE-EXTRACTOR] Created %d extractions across %d sections", total_extractions, len(sections))
        return total_extractions

    def _anchor_claim(
        self,
        conn: sqlite3.Connection,
        claim_id: int,
        quote: str,
        sentence_nodes: list[tuple[int, str]],
    ) -> None:
        """Fuzzy-match a quote to sentence nodes and write claim_sources."""
        quote_lower = quote.lower()

        for node_id, sentence_content in sentence_nodes:
            if not sentence_content:
                continue
            # Substring match
            if quote_lower in sentence_content.lower():
                conn.execute(
                    "INSERT OR IGNORE INTO claim_sources (claim_id, node_id) VALUES (?, ?)",
                    (claim_id, node_id),
                )
                return

        # Fallback: try first 40 chars as prefix
        prefix = quote_lower[:40]
        for node_id, sentence_content in sentence_nodes:
            if not sentence_content:
                continue
            if prefix in sentence_content.lower():
                conn.execute(
                    "INSERT OR IGNORE INTO claim_sources (claim_id, node_id) VALUES (?, ?)",
                    (claim_id, node_id),
                )
                return
