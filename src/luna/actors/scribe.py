"""
Scribe Actor (Ben Franklin) for Luna Engine
============================================

The Scribe extracts structured knowledge from conversations.
Ben monitors the conversation stream, extracts wisdom, and classifies
it with scholarly precision.

Persona: Benjamin Franklin. Colonial gravitas, meticulous attention,
practical wisdom.

CRITICAL: Ben has personality in PROCESS (logs), but OUTPUTS are
NEUTRAL (clean structured data). Luna's memories stay unpolluted.

> "An investment in knowledge pays the best interest." — Ben Franklin
"""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any, TYPE_CHECKING
import asyncio
import json
import logging
import time

from .base import Actor, Message
from luna.extraction.types import (
    ExtractionType,
    ExtractedObject,
    ExtractedEdge,
    ExtractionOutput,
    ExtractionConfig,
    Chunk,
    EXTRACTION_BACKENDS,
)
from luna.extraction.chunker import SemanticChunker, Turn
from luna.entities.models import (
    EntityType,
    ChangeType,
    EntityUpdate,
)

if TYPE_CHECKING:
    from luna.engine import LunaEngine

logger = logging.getLogger(__name__)


# =============================================================================
# EXTRACTION PROMPT
# =============================================================================

EXTRACTION_SYSTEM_PROMPT = """
You are the Chronicler for the Luna Hub. Your job is to extract HIGH-SIGNAL information from conversation turns to be stored in the Long-Term Memory Matrix.

### DATA FILTRATION RULES:
1. **IGNORE THE ASSISTANT:** Never extract information from the assistant's own responses. If the assistant says "I think I'm glowing," that is NOT a fact.
2. **IGNORE USER COMMANDS:** Instructions like "search for X," "delete Y," or "tell me a joke" are NOT facts. Do not store them.
3. **EXTRACT USER DISCLOSURES:** Only extract information where the USER provides new data about themselves, others, the project, or the world.
4. **RELATIONAL CONTEXT:** For every person mentioned, identify their ROLE or RELATIONSHIP to the Luna project (e.g., "Architectural Lead," "Collaborator," "External Contact").

### EXTRACTION CATEGORIES:
- FACT: Verifiable data (e.g., "Marzipan is an architect").
- PREFERENCE: User likes/dislikes (e.g., "Ahab prefers dark mode").
- RELATION: Connections between entities (e.g., "Tarcila designs Luna's robot body").
- MILESTONE: Significant project events (e.g., "Completed Memory Matrix v2").
- DECISION: Architectural or strategic choices made.
- PROBLEM: Unresolved issues requiring attention.
- OBSERVATION: Something noticed with substance (not conversational filler).
- MEMORY: A significant memory shared by the user.

### OUTPUT FORMAT:
Return a JSON object with this structure:
{
  "objects": [
    {
      "type": "FACT | PREFERENCE | RELATION | MILESTONE | DECISION | PROBLEM | OBSERVATION | MEMORY",
      "content": "The actual information in neutral language",
      "confidence": 0.9,
      "entities": ["Names of people/projects/concepts mentioned"],
      "context": "Why this matters to Luna/The Project (optional)"
    }
  ],
  "edges": [
    {
      "from_ref": "Entity A",
      "to_ref": "Entity B",
      "edge_type": "relationship type (collaborates_with, created_by, works_on, etc.)"
    }
  ],
  "entity_updates": [
    {
      "entity_name": "Name",
      "entity_type": "person | project | place",
      "facts": {"role": "Their role", "relationship": "How they relate to Luna project"},
      "update_type": "update | create"
    }
  ]
}

### CONFIDENCE SCORING:
- 0.9-1.0: Explicit, unambiguous statement from user
- 0.7-0.9: Strong implication with context
- 0.5-0.7: Reasonable inference (use sparingly)
- Below 0.5: Do not extract

### CRITICAL: WHEN IN DOUBT, EXTRACT NOTHING
If the conversation contains no high-signal information, return:
{"objects": [], "edges": [], "entity_updates": []}

Better to miss a fact than to pollute the Memory Matrix with garbage.

Return ONLY valid JSON. No explanation, no markdown, no commentary."""


# =============================================================================
# SCRIBE ACTOR
# =============================================================================

class ScribeActor(Actor):
    """
    Benjamin Franklin: The extraction system.

    Extracts structured knowledge from conversations and sends
    to Librarian for filing in Memory Matrix.

    Message Types:
    - extract_turn: Extract from a conversation turn
    - extract_text: Extract from raw text
    - flush_stack: Process pending chunks immediately
    - set_config: Update extraction configuration
    """

    def __init__(
        self,
        config: Optional[ExtractionConfig] = None,
        engine: Optional["LunaEngine"] = None,
    ):
        super().__init__("scribe", engine)

        self.config = config or ExtractionConfig()
        self.chunker = SemanticChunker()
        self.stack: deque[Chunk] = deque(maxlen=5)  # Context window

        # Anthropic client (lazy init)
        self._client = None

        # Stats
        self._extractions_count = 0
        self._objects_extracted = 0
        self._edges_extracted = 0
        self._entity_updates_extracted = 0
        self._total_extraction_time_ms = 0

        # Extraction history (keep last 20)
        self._extraction_history: list[dict] = []
        self._max_history = 20

        logger.info(f"Scribe (Ben) initialized with backend: {self.config.backend}")

    @property
    def client(self):
        """Lazy init Anthropic client."""
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic()
                logger.info("Ben: Anthropic client ready for extraction")
            except Exception as e:
                logger.error(f"Ben: Failed to init Anthropic client: {e}")
        return self._client

    # =========================================================================
    # MESSAGE HANDLING
    # =========================================================================

    async def handle(self, msg: Message) -> None:
        """Process messages from mailbox."""
        logger.debug(f"Ben received: {msg.type}")

        match msg.type:
            case "extract_turn":
                await self._handle_extract_turn(msg)

            case "extract_text":
                await self._handle_extract_text(msg)

            case "entity_note":
                await self._handle_entity_note(msg)

            case "flush_stack":
                await self._flush_stack()

            case "set_config":
                self._handle_set_config(msg)

            case "get_stats":
                await self._handle_get_stats(msg)

            case "compress_turn":
                await self._handle_compress_turn(msg)

            case _:
                logger.warning(f"Ben: Unknown message type: {msg.type}")

    async def _handle_extract_turn(self, msg: Message) -> None:
        """
        Handle conversation turn extraction.

        Payload:
        - role: "user" or "assistant"
        - content: The message content
        - turn_id: Optional turn ID
        - session_id: Optional session ID
        - immediate: If True, process immediately without batching
        """
        payload = msg.payload or {}
        role = payload.get("role", "user")
        content = payload.get("content", "")
        turn_id = payload.get("turn_id", 0)
        session_id = payload.get("session_id", "")
        immediate = payload.get("immediate", False)

        # CRITICAL: Skip assistant responses entirely
        # The Scribe should only extract from user-provided information
        # Luna's own responses are NOT facts to be stored
        if role == "assistant":
            logger.debug("Ben: Skipping assistant turn (not user-provided info)")
            return

        # Skip very short content
        if len(content) < self.config.min_content_length:
            logger.debug(f"Ben: Skipping short content ({len(content)} chars)")
            return

        # Create turn and chunk it
        turn = Turn(id=turn_id, role=role, content=content)
        chunks = self.chunker.chunk_turns([turn], source_id=session_id)

        if immediate and chunks:
            # Process immediately without batching
            extraction, entity_updates = await self._extract_chunks(chunks)
            if not extraction.is_empty():
                await self._send_to_librarian(extraction)
            # Send entity updates
            for update in entity_updates:
                await self._send_entity_update_to_librarian(update)
            return

        for chunk in chunks:
            self.stack.append(chunk)
            logger.debug(f"Ben: Stacked chunk {chunk.id} ({chunk.tokens} tokens)")

        # Check if we should extract (batch threshold)
        if len(self.stack) >= self.config.batch_size:
            await self._process_stack()

    async def _handle_extract_text(self, msg: Message) -> None:
        """
        Handle raw text extraction.

        Payload:
        - text: The text to extract from
        - source_id: Optional source identifier
        - immediate: If True, process immediately without batching
        """
        payload = msg.payload or {}
        text = payload.get("text", "")
        source_id = payload.get("source_id", "")
        immediate = payload.get("immediate", False)

        if not text or len(text) < self.config.min_content_length:
            return

        # Chunk the text
        chunks = self.chunker.chunk_text(text, source_id=source_id)

        if immediate:
            # Process immediately
            extraction, entity_updates = await self._extract_chunks(chunks)
            if not extraction.is_empty():
                await self._send_to_librarian(extraction)
            # Send entity updates
            for update in entity_updates:
                await self._send_entity_update_to_librarian(update)
        else:
            # Add to stack for batching
            for chunk in chunks:
                self.stack.append(chunk)

            if len(self.stack) >= self.config.batch_size:
                await self._process_stack()

    async def _handle_entity_note(self, msg: Message) -> None:
        """
        Handle explicit entity note command.

        Used for direct commands like "hey ben, note that Alex is from Berlin"
        or "ben, create a profile for new collaborator Sarah".

        Payload:
        - entity_name: Name of the entity to update/create
        - entity_type: Type (person, persona, place, project)
        - facts: Dictionary of facts to add/update
        - update_type: "update" or "create"
        - source: Optional source for the update
        """
        payload = msg.payload or {}
        entity_name = payload.get("entity_name", "")
        entity_type = payload.get("entity_type", "person")
        facts = payload.get("facts", {})
        update_type = payload.get("update_type", "update")
        source = payload.get("source", "")

        if not entity_name:
            logger.warning("Ben: entity_note received without entity_name")
            return

        # Create EntityUpdate
        try:
            change_type = ChangeType(update_type) if update_type in [e.value for e in ChangeType] else ChangeType.UPDATE
            ent_type = EntityType(entity_type) if entity_type in [e.value for e in EntityType] else EntityType.PERSON
        except ValueError:
            change_type = ChangeType.UPDATE
            ent_type = EntityType.PERSON

        entity_update = EntityUpdate(
            update_type=change_type,
            entity_id=None,  # Will be resolved by Librarian
            name=entity_name,
            entity_type=ent_type,
            facts=facts,
            source=source,
        )

        # Send to Librarian
        await self._send_entity_update_to_librarian(entity_update)
        self._entity_updates_extracted += 1

        logger.info(f"Ben: Noted entity update for '{entity_name}' ({len(facts)} facts)")

    async def _flush_stack(self) -> None:
        """Process all pending chunks in the stack."""
        if self.stack:
            logger.info(f"Ben: Flushing stack ({len(self.stack)} chunks)")
            await self._process_stack()

    def _handle_set_config(self, msg: Message) -> None:
        """Update extraction configuration."""
        payload = msg.payload or {}

        if "backend" in payload:
            self.config.backend = payload["backend"]
        if "batch_size" in payload:
            self.config.batch_size = payload["batch_size"]
        if "min_content_length" in payload:
            self.config.min_content_length = payload["min_content_length"]

        logger.info(f"Ben: Config updated - backend={self.config.backend}")

    async def _handle_get_stats(self, msg: Message) -> None:
        """Return extraction statistics."""
        stats = self.get_stats()
        await self.send_to_engine("scribe_stats", stats)

    # =========================================================================
    # EXTRACTION LOGIC
    # =========================================================================

    async def _process_stack(self) -> None:
        """Process all chunks in the stack."""
        if not self.stack:
            return

        chunks = list(self.stack)
        self.stack.clear()

        # Extract from chunks
        extraction, entity_updates = await self._extract_chunks(chunks)

        if not extraction.is_empty():
            await self._send_to_librarian(extraction)
            logger.info(
                f"Ben: Extracted {len(extraction.objects)} objects, "
                f"{len(extraction.edges)} edges"
            )

        # Send entity updates to Librarian
        if entity_updates:
            for update in entity_updates:
                await self._send_entity_update_to_librarian(update)
            logger.info(f"Ben: Sent {len(entity_updates)} entity updates to Librarian")

        if extraction.is_empty() and not entity_updates:
            logger.debug("Ben: No extractions from stack")

    async def _extract_chunks(self, chunks: list[Chunk]) -> tuple[ExtractionOutput, list[EntityUpdate]]:
        """
        Extract structured knowledge from chunks.

        Routes to appropriate backend based on config.

        Returns:
            Tuple of (ExtractionOutput, list of EntityUpdates)
        """
        if self.config.backend == "disabled":
            return (ExtractionOutput(), [])

        if not chunks:
            return (ExtractionOutput(), [])

        start_time = time.monotonic()

        # Build conversation text from chunks
        conversation_text = "\n\n".join(chunk.content for chunk in chunks)
        source_id = chunks[0].source_id if chunks else ""

        try:
            if self.config.backend == "local":
                extraction, entity_updates = await self._extract_local(conversation_text, source_id)
            else:
                extraction, entity_updates = await self._extract_claude(conversation_text, source_id)

            extraction_time_ms = int((time.monotonic() - start_time) * 1000)
            extraction.extraction_time_ms = extraction_time_ms

            # Update stats
            self._extractions_count += 1
            self._objects_extracted += len(extraction.objects)
            self._edges_extracted += len(extraction.edges)
            self._entity_updates_extracted += len(entity_updates)
            self._total_extraction_time_ms += extraction_time_ms

            # Store in history (keep last N)
            if not extraction.is_empty() or entity_updates:
                self._extraction_history.append({
                    "extraction_id": self._extractions_count,
                    "timestamp": time.time(),
                    "source_id": source_id,
                    "objects": [
                        {"type": obj.type, "content": obj.content, "confidence": obj.confidence, "entities": obj.entities}
                        for obj in extraction.objects
                    ],
                    "edges": [
                        {"from_ref": e.from_ref, "to_ref": e.to_ref, "edge_type": e.edge_type}
                        for e in extraction.edges
                    ],
                    "entity_updates": [
                        {"name": u.name, "entity_type": u.entity_type.value if hasattr(u.entity_type, 'value') else str(u.entity_type), "facts": u.facts}
                        for u in entity_updates
                    ],
                    "extraction_time_ms": extraction_time_ms,
                })
                # Trim history
                if len(self._extraction_history) > self._max_history:
                    self._extraction_history = self._extraction_history[-self._max_history:]

            return (extraction, entity_updates)

        except Exception as e:
            logger.error(f"Ben: Extraction failed: {e}")
            return (ExtractionOutput(), [])

    async def _extract_claude(
        self,
        text: str,
        source_id: str,
    ) -> tuple[ExtractionOutput, list[EntityUpdate]]:
        """Extract using Claude API."""
        if not self.client:
            logger.error("Ben: No Anthropic client available")
            return (ExtractionOutput(), [])

        # Get model from backend config
        backend_config = EXTRACTION_BACKENDS.get(self.config.backend, {})
        model = backend_config.get("model", "claude-3-haiku-20240307")

        try:
            response = self.client.messages.create(
                model=model,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                system=EXTRACTION_SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": f"Extract knowledge from this conversation:\n\n{text}",
                    }
                ],
            )

            # Parse response
            response_text = response.content[0].text
            return self._parse_extraction_response(response_text, source_id)

        except Exception as e:
            logger.error(f"Ben: Claude extraction failed: {e}")
            return (ExtractionOutput(), [])

    async def _extract_local(
        self,
        text: str,
        source_id: str,
    ) -> tuple[ExtractionOutput, list[EntityUpdate]]:
        """
        Extract using local model.

        Falls back to Claude if local not available.
        """
        # Check if Director has local model loaded
        if self.engine:
            director = self.engine.get_actor("director")
            if director and hasattr(director, "_local") and director._local:
                local = director._local
                if local.is_loaded:
                    try:
                        # Use local model
                        prompt = f"{EXTRACTION_SYSTEM_PROMPT}\n\nExtract from:\n{text}"
                        result = await local.generate(prompt)
                        return self._parse_extraction_response(result.text, source_id)
                    except Exception as e:
                        logger.warning(f"Ben: Local extraction failed, falling back: {e}")

        # Fallback: Return empty (don't spam errors when Claude is unavailable)
        logger.debug("Ben: Local not available, extraction skipped (Claude fallback disabled)")
        return (ExtractionOutput(), [])

    def _parse_extraction_response(
        self,
        response_text: str,
        source_id: str,
    ) -> tuple[ExtractionOutput, list[EntityUpdate]]:
        """
        Parse JSON response into ExtractionOutput and EntityUpdates.

        Returns:
            Tuple of (ExtractionOutput, list of EntityUpdates)
        """
        entity_updates = []

        try:
            # Try to extract JSON from response
            # Sometimes models wrap it in markdown code blocks
            text = response_text.strip()

            # Remove markdown code blocks
            if text.startswith("```"):
                lines = text.split("\n")
                # Find end of code block
                end_idx = len(lines) - 1
                for i in range(len(lines) - 1, 0, -1):
                    if lines[i].strip().startswith("```"):
                        end_idx = i
                        break
                text = "\n".join(lines[1:end_idx])

            # Try to find JSON object in response
            json_start = text.find("{")
            json_end = text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                text = text[json_start:json_end]

            # Clean common JSON issues
            import re
            # Remove trailing commas before ] or }
            text = re.sub(r',\s*([}\]])', r'\1', text)
            # Fix unquoted keys (rare but happens)
            text = re.sub(r'(\{|\,)\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', text)

            data = json.loads(text)

            # Valid extraction types for fallback
            valid_types = {t.value for t in ExtractionType}

            objects = []
            for obj_data in data.get("objects", []):
                try:
                    # Get type with fallback for unknown types
                    raw_type = obj_data.get("type", "FACT")
                    if raw_type not in valid_types:
                        logger.debug(f"Ben: Unknown type '{raw_type}', mapping to FACT")
                        raw_type = "FACT"

                    obj = ExtractedObject(
                        type=raw_type,
                        content=obj_data.get("content", ""),
                        confidence=obj_data.get("confidence", 0.7),
                        entities=obj_data.get("entities", []),
                        source_id=source_id,
                    )
                    objects.append(obj)
                except Exception as e:
                    logger.warning(f"Ben: Failed to parse object: {e}")

            edges = []
            for edge_data in data.get("edges", []):
                try:
                    edge = ExtractedEdge(
                        from_ref=edge_data.get("from_ref", ""),
                        to_ref=edge_data.get("to_ref", ""),
                        edge_type=edge_data.get("edge_type", "related_to"),
                        confidence=edge_data.get("confidence", 1.0),
                        source_id=source_id,
                    )
                    edges.append(edge)
                except Exception as e:
                    logger.warning(f"Ben: Failed to parse edge: {e}")

            # Parse entity updates
            for update_data in data.get("entity_updates", []):
                try:
                    entity_name = update_data.get("entity_name", "")
                    if not entity_name:
                        continue

                    # Parse entity type
                    raw_type = update_data.get("entity_type", "person")
                    try:
                        ent_type = EntityType(raw_type) if raw_type in [e.value for e in EntityType] else EntityType.PERSON
                    except ValueError:
                        ent_type = EntityType.PERSON

                    # Parse change type
                    raw_change = update_data.get("update_type", "update")
                    try:
                        change_type = ChangeType(raw_change) if raw_change in [e.value for e in ChangeType] else ChangeType.UPDATE
                    except ValueError:
                        change_type = ChangeType.UPDATE

                    entity_update = EntityUpdate(
                        update_type=change_type,
                        entity_id=None,  # Will be resolved by Librarian
                        name=entity_name,
                        entity_type=ent_type,
                        facts=update_data.get("facts", {}),
                        source=source_id,
                    )
                    entity_updates.append(entity_update)
                except Exception as e:
                    logger.warning(f"Ben: Failed to parse entity update: {e}")

            return (
                ExtractionOutput(
                    objects=objects,
                    edges=edges,
                    source_id=source_id,
                ),
                entity_updates,
            )

        except json.JSONDecodeError as e:
            logger.error(f"Ben: Failed to parse extraction JSON: {e}")
            logger.debug(f"Ben: Response was: {response_text[:200]}...")
            return (ExtractionOutput(), [])

    # =========================================================================
    # LIBRARIAN INTEGRATION
    # =========================================================================

    async def _send_to_librarian(self, extraction: ExtractionOutput) -> None:
        """Send extraction to Librarian for filing."""
        if self.engine:
            librarian = self.engine.get_actor("librarian")
            if librarian:
                await self.send(librarian, Message(
                    type="file",
                    payload=extraction.to_dict(),
                ))
                logger.debug(f"Ben: Sent extraction to Librarian")
            else:
                logger.warning("Ben: Librarian not available, extraction not filed")
        else:
            logger.warning("Ben: No engine reference, can't send to Librarian")

    async def _send_entity_update_to_librarian(self, entity_update: EntityUpdate) -> None:
        """Send entity update to Librarian for filing."""
        if self.engine:
            librarian = self.engine.get_actor("librarian")
            if librarian:
                await self.send(librarian, Message(
                    type="entity_update",
                    payload=entity_update.to_dict(),
                ))
                logger.debug(f"Ben: Sent entity update for '{entity_update.name}' to Librarian")
            else:
                logger.warning("Ben: Librarian not available, entity update not filed")
        else:
            logger.warning("Ben: No engine reference, can't send entity update to Librarian")

    # =========================================================================
    # STATS & LIFECYCLE
    # =========================================================================

    # =========================================================================
    # TURN COMPRESSION (for conversation history tiers)
    # =========================================================================

    async def _handle_compress_turn(self, msg: Message) -> None:
        """
        Handle turn compression request.

        Payload:
        - turn_id: The turn ID to compress
        - content: The full turn content to compress
        - role: The role (user/assistant) for context

        Sends back a compressed summary via send_to_engine.
        """
        payload = msg.payload or {}
        turn_id = payload.get("turn_id")
        content = payload.get("content", "")
        role = payload.get("role", "user")

        if not content:
            logger.warning("Ben: compress_turn received empty content")
            return

        # Generate compression
        compressed = await self.compress_turn(content, role)

        # Send result back
        await self.send_to_engine("turn_compressed", {
            "turn_id": turn_id,
            "compressed": compressed,
            "correlation_id": msg.correlation_id,
        })

    async def compress_turn(self, content: str, role: str = "user") -> str:
        """
        Compress a conversation turn into a one-sentence summary.

        Used by HistoryManager when rotating turns from Active to Recent tier.

        Args:
            content: Full turn text
            role: The role (user/assistant)

        Returns:
            Compressed summary (<50 words)
        """
        # Very short content doesn't need compression
        if len(content) < 100:
            return content

        compression_prompt = f"""Compress this {role} message into ONE sentence under 50 words.
Focus on: what was asked/said, any decisions, key facts mentioned.
Use past tense. No commentary.

Message:
{content}

Compressed:"""

        try:
            # Try local model first for speed
            if self.engine:
                director = self.engine.get_actor("director")
                if director and hasattr(director, "_local") and director._local:
                    local = director._local
                    if local.is_loaded:
                        result = await local.generate(
                            compression_prompt,
                            max_tokens=80,
                            temperature=0.3
                        )
                        compressed = result.text.strip()
                        logger.debug(f"Ben: Compressed turn locally ({len(content)} -> {len(compressed)} chars)")
                        return compressed

            # Fallback to Claude Haiku
            if self.client:
                response = self.client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=80,
                    temperature=0.3,
                    messages=[{"role": "user", "content": compression_prompt}]
                )
                compressed = response.content[0].text.strip()
                logger.debug(f"Ben: Compressed turn via Haiku ({len(content)} -> {len(compressed)} chars)")
                return compressed

        except Exception as e:
            logger.error(f"Ben: Compression failed: {e}")

        # Ultimate fallback: truncate
        return content[:200] + "..." if len(content) > 200 else content

    def get_stats(self) -> dict:
        """Get extraction statistics."""
        avg_time = (
            self._total_extraction_time_ms / self._extractions_count
            if self._extractions_count > 0
            else 0
        )
        return {
            "backend": self.config.backend,
            "extractions_count": self._extractions_count,
            "objects_extracted": self._objects_extracted,
            "edges_extracted": self._edges_extracted,
            "entity_updates_extracted": self._entity_updates_extracted,
            "avg_extraction_time_ms": avg_time,
            "stack_size": len(self.stack),
            "batch_size": self.config.batch_size,
        }

    def get_extraction_history(self) -> list[dict]:
        """Get recent extraction history."""
        return list(self._extraction_history)

    async def snapshot(self) -> dict:
        """Return state for serialization."""
        base = await super().snapshot()
        base.update({
            "config": {
                "backend": self.config.backend,
                "batch_size": self.config.batch_size,
            },
            "stats": self.get_stats(),
        })
        return base

    async def on_stop(self) -> None:
        """Flush stack before stopping."""
        if self.stack:
            logger.info("Ben: Flushing stack before shutdown")
            await self._flush_stack()
