"""
Transcript Extractor - Phase 1: Extract Knowledge

Ben's 6-phase extraction framework applied to historical conversations:
1. NODES — Structured knowledge units (FACT, DECISION, PROBLEM, ACTION, OUTCOME, INSIGHT)
2. OBSERVATIONS — Emotional/philosophical weight (why it mattered)
3. ENTITIES — People, places, projects mentioned
4. EDGES — Relationships between nodes
5. KEY_DECISIONS — Architecture/life decisions
6. TEXTURE — Conversation mood

Era-aware extraction with chunking support for long conversations.
"""

import json
from typing import Dict, List, Optional
from datetime import datetime

from .prompts import (
    EXTRACTION_PROMPT,
    EXTRACTION_PROMPT_BRONZE,
)
from .validation import (
    validate_extraction_schema,
    safe_parse_json,
    ExtractionValidationError,
)


class TranscriptExtractor:
    """Extract structured knowledge from conversation transcripts."""

    # Era classification
    ERAS = {
        "PRE_LUNA": ("2023-01-01", "2024-06-01"),
        "PROTO_LUNA": ("2024-06-01", "2025-01-01"),
        "LUNA_DEV": ("2025-01-01", "2025-10-01"),
        "LUNA_LIVE": ("2025-10-01", "2030-01-01"),
    }

    # Node targets by tier
    NODE_TARGETS = {
        "GOLD": "8-12",
        "SILVER": "3-5",
        "BRONZE": "1-2",
    }

    DEFAULT_MODEL = "claude-sonnet-4-5-20250929"

    def __init__(self, llm_client=None, model: str = None):
        """
        Initialize extractor.

        Args:
            llm_client: LLM client for extraction (must have .create() method)
            model: Model name to pass to llm_client.create(). Defaults to Sonnet.
        """
        self.llm_client = llm_client
        self.model = model or self.DEFAULT_MODEL

    # ========================================================================
    # Era Classification
    # ========================================================================

    def classify_era(self, date_str: str) -> str:
        """
        Classify conversation era from date.

        Args:
            date_str: ISO date string (YYYY-MM-DD...)

        Returns:
            "PRE_LUNA" | "PROTO_LUNA" | "LUNA_DEV" | "LUNA_LIVE"
        """
        date = date_str[:10]  # YYYY-MM-DD

        for era, (start, end) in self.ERAS.items():
            if start <= date < end:
                return era

        return "LUNA_LIVE"  # Default to current era

    # ========================================================================
    # Conversation Formatting
    # ========================================================================

    def format_transcript(self, messages: List[Dict], max_length: int = 1000) -> str:
        """
        Format conversation messages for LLM consumption.

        Args:
            messages: List of message dicts
            max_length: Max chars per message (truncate longer)

        Returns:
            Formatted transcript string
        """
        lines = []
        for msg in messages:
            sender = "Ahab" if msg.get("sender") == "human" else "Claude"
            text = msg.get("text", "")[:max_length]

            # Include attachment info
            if msg.get("attachments"):
                att_names = [a.get("file_name", "file") for a in msg["attachments"]]
                text += f"\n  [Attachments: {', '.join(att_names)}]"

            lines.append(f"[{sender}] {text}")

        return "\n\n".join(lines)

    def chunk_messages(
        self,
        messages: List[Dict],
        chunk_size: int = 20,
        overlap: int = 2
    ) -> List[List[Dict]]:
        """
        Chunk long conversations with overlap.

        Args:
            messages: Full message list
            chunk_size: Messages per chunk
            overlap: Messages to overlap between chunks

        Returns:
            List of message chunks
        """
        if len(messages) <= chunk_size:
            return [messages]

        chunks = []
        start = 0

        while start < len(messages):
            end = min(start + chunk_size, len(messages))
            chunks.append(messages[start:end])

            # Move start forward, accounting for overlap
            start = end - overlap

            # Stop if we'd just repeat the last chunk
            if start >= len(messages) - overlap:
                break

        return chunks

    # ========================================================================
    # Extraction
    # ========================================================================

    async def extract_conversation(
        self,
        conversation: Dict,
        tier: str,
        scanner=None
    ) -> Dict:
        """
        Extract knowledge from a single conversation.

        Args:
            conversation: Full conversation dict (from scanner)
            tier: "GOLD" | "SILVER" | "BRONZE"
            scanner: TranscriptScanner instance (optional, for loading full data)

        Returns:
            {
                "nodes": [...],
                "observations": [...],
                "entities": [...],
                "edges": [...],
                "key_decisions": [...],
                "texture": [...],
                "extraction_status": "complete" | "partial" | "failed",
                "error_message": str (if failed),
            }
        """
        if not self.llm_client:
            raise ValueError("LLM client required for extraction")

        # Load full conversation if needed
        if scanner and "chat_messages" not in conversation:
            conversation = scanner.load_conversation(conversation["path"])

        messages = conversation.get("chat_messages", [])
        title = conversation.get("name", "Untitled")
        date = conversation.get("created_at", "")[:10]
        era = self.classify_era(date)
        node_target = self.NODE_TARGETS.get(tier, "3-5")

        # BRONZE tier: entity-only extraction
        if tier == "BRONZE":
            return await self._extract_entities_only(
                messages, title, date, era
            )

        # GOLD/SILVER: full extraction
        if len(messages) <= 25:
            # Single extraction
            transcript = self.format_transcript(messages)
            return await self._extract_with_retry(
                transcript=transcript,
                title=title,
                date=date,
                era=era,
                message_count=len(messages),
                node_target=node_target,
            )
        else:
            # Chunked extraction
            return await self._extract_chunked(
                messages=messages,
                title=title,
                date=date,
                era=era,
                node_target=node_target,
            )

    async def _extract_entities_only(
        self,
        messages: List[Dict],
        title: str,
        date: str,
        era: str
    ) -> Dict:
        """Extract entities only (BRONZE tier)."""
        # Only include human messages for BRONZE
        human_messages = [m for m in messages if m.get("sender") == "human"]
        transcript = self.format_transcript(human_messages, max_length=200)

        prompt = EXTRACTION_PROMPT_BRONZE.format(
            title=title,
            date=date,
            era=era,
            transcript_text=transcript,
        )

        try:
            response = await self.llm_client.create(
                model=self.model,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )

            result = safe_parse_json(response.content[0].text)
            if result is None:
                raise ExtractionValidationError("Failed to parse JSON")

            return {
                "nodes": [],
                "observations": [],
                "entities": result.get("entities", []),
                "edges": [],
                "key_decisions": [],
                "texture": [],
                "extraction_status": "complete",
            }

        except Exception as e:
            return {
                "nodes": [],
                "observations": [],
                "entities": [],
                "edges": [],
                "key_decisions": [],
                "texture": [],
                "extraction_status": "failed",
                "error_message": str(e),
            }

    async def _extract_with_retry(
        self,
        transcript: str,
        title: str,
        date: str,
        era: str,
        message_count: int,
        node_target: str,
        max_retries: int = 3
    ) -> Dict:
        """
        Extract with retry logic.

        Args:
            transcript: Formatted conversation text
            title: Conversation title
            date: Date (YYYY-MM-DD)
            era: Era classification
            message_count: Number of messages
            node_target: Target node count (e.g., "8-12")
            max_retries: Max retry attempts

        Returns:
            Extraction result dict
        """
        prompt = EXTRACTION_PROMPT.format(
            title=title,
            date=date,
            message_count=message_count,
            era=era,
            transcript_text=transcript,
            node_target=node_target,
        )

        for attempt in range(max_retries):
            try:
                response = await self.llm_client.create(
                    model=self.model,
                    max_tokens=8000,
                    messages=[{"role": "user", "content": prompt}]
                )

                # Parse and validate
                result = safe_parse_json(response.content[0].text)
                if result is None:
                    raise ExtractionValidationError("Failed to parse JSON from LLM response")

                validate_extraction_schema(result)

                # Add metadata
                result["extraction_status"] = "complete"
                return result

            except ExtractionValidationError as e:
                if attempt < max_retries - 1:
                    # Retry with simpler prompt
                    prompt = f"{prompt}\n\nIMPORTANT: Respond with ONLY valid JSON. No markdown, no explanation."
                    continue
                else:
                    return {
                        "nodes": [],
                        "observations": [],
                        "entities": [],
                        "edges": [],
                        "key_decisions": [],
                        "texture": [],
                        "extraction_status": "failed",
                        "error_message": f"Validation failed: {str(e)}",
                    }

            except Exception as e:
                if attempt < max_retries - 1:
                    continue
                else:
                    return {
                        "nodes": [],
                        "observations": [],
                        "entities": [],
                        "edges": [],
                        "key_decisions": [],
                        "texture": [],
                        "extraction_status": "failed",
                        "error_message": str(e),
                    }

    async def _extract_chunked(
        self,
        messages: List[Dict],
        title: str,
        date: str,
        era: str,
        node_target: str,
    ) -> Dict:
        """
        Extract from long conversation using chunks.

        Args:
            messages: Full message list
            title: Conversation title
            date: Date
            era: Era classification
            node_target: Node count target

        Returns:
            Merged extraction result
        """
        chunks = self.chunk_messages(messages, chunk_size=20, overlap=2)

        all_results = []
        for i, chunk in enumerate(chunks):
            transcript = self.format_transcript(chunk)

            result = await self._extract_with_retry(
                transcript=transcript,
                title=f"{title} (part {i+1}/{len(chunks)})",
                date=date,
                era=era,
                message_count=len(chunk),
                node_target=node_target,
            )

            all_results.append(result)

        # Merge chunks
        return self._merge_chunk_results(all_results)

    def _merge_chunk_results(self, results: List[Dict]) -> Dict:
        """
        Merge extraction results from multiple chunks.

        Args:
            results: List of extraction dicts

        Returns:
            Merged extraction dict
        """
        merged = {
            "nodes": [],
            "observations": [],
            "entities": [],
            "edges": [],
            "key_decisions": [],
            "texture": [],
            "extraction_status": "complete",
        }

        # Track entity names to deduplicate
        entity_names = set()

        for result in results:
            # Nodes: append all
            merged["nodes"].extend(result.get("nodes", []))

            # Observations: append all (will be re-indexed)
            merged["observations"].extend(result.get("observations", []))

            # Entities: deduplicate by name
            for entity in result.get("entities", []):
                name = entity.get("name", "")
                if name and name not in entity_names:
                    merged["entities"].append(entity)
                    entity_names.add(name)

            # Edges: skip for now (will be regenerated in resolver)
            # Cross-chunk edges are complex, so we only keep intra-chunk edges

            # Key decisions: append all
            merged["key_decisions"].extend(result.get("key_decisions", []))

            # Texture: merge and deduplicate
            for tag in result.get("texture", []):
                if tag not in merged["texture"]:
                    merged["texture"].append(tag)

            # If any chunk failed, mark as partial
            if result.get("extraction_status") == "failed":
                merged["extraction_status"] = "partial"

        # Re-index observations to match merged node list
        # (This is approximate — resolver will clean up)

        return merged
