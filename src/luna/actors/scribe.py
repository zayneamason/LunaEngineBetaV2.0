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

if TYPE_CHECKING:
    from luna.engine import LunaEngine

logger = logging.getLogger(__name__)


# =============================================================================
# EXTRACTION PROMPT
# =============================================================================

EXTRACTION_SYSTEM_PROMPT = """You are an extraction system that converts conversation into structured knowledge.

Extract ALL meaningful information as JSON. For each piece of knowledge, identify:
- type: One of FACT, DECISION, PROBLEM, ASSUMPTION, CONNECTION, ACTION, OUTCOME
- content: The distilled statement (neutral, factual)
- confidence: 0.0-1.0 based on how explicit the statement is
- entities: List of people, projects, concepts mentioned

Also identify relationships between entities as edges:
- from_ref: Source entity name
- to_ref: Target entity name
- edge_type: Relationship type (works_on, knows, decided, caused, etc.)

Return valid JSON with this structure:
{
  "objects": [
    {"type": "FACT", "content": "...", "confidence": 0.9, "entities": ["..."]},
    ...
  ],
  "edges": [
    {"from_ref": "Alex", "to_ref": "Pi Project", "edge_type": "works_on"},
    ...
  ]
}

Guidelines:
- FACT: Known to be true ("Alex lives in Berlin")
- DECISION: A choice made ("We chose SQLite")
- PROBLEM: Unresolved issue ("Authentication is broken")
- ASSUMPTION: Believed but unverified ("Users prefer voice")
- CONNECTION: Relationship ("Alex and Sarah are teammates")
- ACTION: To be done ("Need to implement caching")
- OUTCOME: Result ("Switching databases saved 45ms")

Confidence scoring:
- 0.9-1.0: Explicit statement
- 0.7-0.9: Strong implication
- 0.5-0.7: Weak inference
- 0.3-0.5: Speculation

Return ONLY valid JSON. No explanation or markdown."""


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
        self._total_extraction_time_ms = 0

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

            case "flush_stack":
                await self._flush_stack()

            case "set_config":
                self._handle_set_config(msg)

            case "get_stats":
                await self._handle_get_stats(msg)

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
        """
        payload = msg.payload or {}
        role = payload.get("role", "user")
        content = payload.get("content", "")
        turn_id = payload.get("turn_id", 0)
        session_id = payload.get("session_id", "")

        # Skip very short content
        if len(content) < self.config.min_content_length:
            logger.debug(f"Ben: Skipping short content ({len(content)} chars)")
            return

        # Create turn and chunk it
        turn = Turn(id=turn_id, role=role, content=content)
        chunks = self.chunker.chunk_turns([turn], source_id=session_id)

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
            extraction = await self._extract_chunks(chunks)
            if not extraction.is_empty():
                await self._send_to_librarian(extraction)
        else:
            # Add to stack for batching
            for chunk in chunks:
                self.stack.append(chunk)

            if len(self.stack) >= self.config.batch_size:
                await self._process_stack()

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
        extraction = await self._extract_chunks(chunks)

        if not extraction.is_empty():
            await self._send_to_librarian(extraction)
            logger.info(
                f"Ben: Extracted {len(extraction.objects)} objects, "
                f"{len(extraction.edges)} edges"
            )
        else:
            logger.debug("Ben: No extractions from stack")

    async def _extract_chunks(self, chunks: list[Chunk]) -> ExtractionOutput:
        """
        Extract structured knowledge from chunks.

        Routes to appropriate backend based on config.
        """
        if self.config.backend == "disabled":
            return ExtractionOutput()

        if not chunks:
            return ExtractionOutput()

        start_time = time.monotonic()

        # Build conversation text from chunks
        conversation_text = "\n\n".join(chunk.content for chunk in chunks)
        source_id = chunks[0].source_id if chunks else ""

        try:
            if self.config.backend == "local":
                extraction = await self._extract_local(conversation_text, source_id)
            else:
                extraction = await self._extract_claude(conversation_text, source_id)

            extraction_time_ms = int((time.monotonic() - start_time) * 1000)
            extraction.extraction_time_ms = extraction_time_ms

            # Update stats
            self._extractions_count += 1
            self._objects_extracted += len(extraction.objects)
            self._edges_extracted += len(extraction.edges)
            self._total_extraction_time_ms += extraction_time_ms

            return extraction

        except Exception as e:
            logger.error(f"Ben: Extraction failed: {e}")
            return ExtractionOutput()

    async def _extract_claude(
        self,
        text: str,
        source_id: str,
    ) -> ExtractionOutput:
        """Extract using Claude API."""
        if not self.client:
            logger.error("Ben: No Anthropic client available")
            return ExtractionOutput()

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
            return ExtractionOutput()

    async def _extract_local(
        self,
        text: str,
        source_id: str,
    ) -> ExtractionOutput:
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

        # Fallback to Haiku
        logger.debug("Ben: Local not available, using Haiku fallback")
        old_backend = self.config.backend
        self.config.backend = "haiku"
        result = await self._extract_claude(text, source_id)
        self.config.backend = old_backend
        return result

    def _parse_extraction_response(
        self,
        response_text: str,
        source_id: str,
    ) -> ExtractionOutput:
        """Parse JSON response into ExtractionOutput."""
        try:
            # Try to extract JSON from response
            # Sometimes models wrap it in markdown code blocks
            text = response_text.strip()
            if text.startswith("```"):
                # Remove markdown code blocks
                lines = text.split("\n")
                text = "\n".join(lines[1:-1])

            data = json.loads(text)

            objects = []
            for obj_data in data.get("objects", []):
                try:
                    obj = ExtractedObject(
                        type=obj_data.get("type", "FACT"),
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

            return ExtractionOutput(
                objects=objects,
                edges=edges,
                source_id=source_id,
            )

        except json.JSONDecodeError as e:
            logger.error(f"Ben: Failed to parse extraction JSON: {e}")
            logger.debug(f"Ben: Response was: {response_text[:200]}...")
            return ExtractionOutput()

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

    # =========================================================================
    # STATS & LIFECYCLE
    # =========================================================================

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
            "avg_extraction_time_ms": avg_time,
            "stack_size": len(self.stack),
            "batch_size": self.config.batch_size,
        }

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
