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
import re as _re

from luna.extraction.types import (
    ExtractionType,
    ExtractedObject,
    ExtractedEdge,
    ExtractionOutput,
    ExtractionConfig,
    Chunk,
    EXTRACTION_BACKENDS,
    ConversationMode,
    FlowSignal,
    SourceProvenance,
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

### IMPORTANT — CONTENT vs ENTITIES:
- "content" is a SENTENCE describing the information
- "entities" is a LIST OF PROPER NOUNS only (names, places, projects)
- Never put a sentence in "entities"
- Never put a proper noun alone in "content" — always describe what about them

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

        # Flow tracking state (Layer 2)
        self._current_topic: str = ""
        self._current_entities: set[str] = set()
        self._recent_entities: deque[set[str]] = deque(maxlen=5)
        self._turn_count_in_flow: int = 0
        self._open_actions: list[dict] = []

        # Entity hints from LocalSubtaskRunner (gates expensive extraction)
        self._last_entity_hints: Optional[list] = None  # None = no hints received yet

        # Source tracking for cache actor
        self._current_source: str = "unknown"  # Set per-turn from message payload

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

            case "entity_hints":
                self._handle_entity_hints(msg)

            case "flush_stack":
                await self._flush_stack()

            case "set_config":
                self._handle_set_config(msg)

            case "get_stats":
                await self._handle_get_stats(msg)

            case "compress_turn":
                await self._handle_compress_turn(msg)

            case "extract_correction":
                await self._handle_extract_correction(msg)

            case _:
                logger.warning(f"Ben: Unknown message type: {msg.type}")

    def _handle_entity_hints(self, msg: Message) -> None:
        """
        Receive entity hints from LocalSubtaskRunner (Qwen 3B NER).

        These hints gate expensive Claude Haiku extraction:
        - If zero entities detected, skip deep extraction for this turn
        - If entities found, pass as hints to improve extraction accuracy
        """
        payload = msg.payload or {}
        entities = payload.get("entities", [])
        self._last_entity_hints = entities
        if entities:
            logger.info(f"Ben: Received {len(entities)} entity hints: {[e.get('name') for e in entities[:5]]}")
        else:
            logger.debug("Ben: Received empty entity hints (turn is pure chat)")

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
        source = payload.get("source", "unknown")
        self._current_source = source

        # CRITICAL: Skip assistant responses entirely
        # The Scribe should only extract from user-provided information
        # Luna's own responses are NOT facts to be stored
        if role == "assistant":
            logger.debug("Ben: Skipping assistant turn (not user-provided info)")
            return

        # GUARDIAN CONTEXT GUARD: Skip context-injected messages from Guardian frontend.
        # These contain panel metadata, control prefixes, and response format instructions
        # that should NOT be extracted as facts or stored in memory.
        _GUARDIAN_PREFIXES = ("[GUARDIAN CONTEXT", "[GUARDIAN CONTROL LAYER]", "[RESPONSE FORMAT]")
        if any(content.lstrip().startswith(pfx) for pfx in _GUARDIAN_PREFIXES):
            logger.info("Ben: Skipping Guardian context-injected message (not user knowledge)")
            return

        # Skip very short content
        if len(content) < self.config.min_content_length:
            logger.debug(f"Ben: Skipping short content ({len(content)} chars)")
            return

        # ENTITY HINT GATING: If Qwen NER found zero entities, skip expensive
        # Claude extraction for this turn. Pure chat ("lol", "ok", "thanks")
        # doesn't need deep extraction. Reset hints after consuming.
        if self._last_entity_hints is not None and len(self._last_entity_hints) == 0:
            logger.info("Ben: Skipping extraction (no entities detected by NER)")
            self._last_entity_hints = None  # Reset for next turn
            return
        # Consume and reset hints
        entity_hints = self._last_entity_hints
        self._last_entity_hints = None

        # Create turn and chunk it
        turn = Turn(id=turn_id, role=role, content=content)
        chunks = self.chunker.chunk_turns([turn], source_id=session_id)

        if immediate and chunks:
            # Process immediately without batching
            extraction, entity_updates = await self._extract_chunks(chunks)

            # Assess conversational flow (Layer 2) — MUST run on immediate
            # path too, otherwise FlowSignal never reaches Librarian and
            # THREAD nodes are never created.
            raw_text = "\n".join(chunk.content for chunk in chunks)
            flow_signal = self._assess_flow(extraction, raw_text)
            extraction.flow_signal = flow_signal

            logger.info(
                f"Ben: Flow={flow_signal.mode.value} "
                f"continuity={flow_signal.continuity_score:.2f} "
                f"topic='{flow_signal.current_topic[:30]}' "
                f"open_threads={len(flow_signal.open_threads)}"
            )

            # Send to CacheActor (writes YAML snapshot + feeds dimensional engine)
            await self._send_to_cache(
                extraction, flow_signal,
                source=source, session_id=session_id,
            )

            # Always send to Librarian when flow signal exists — even on
            # empty extractions — so thread management receives the signal.
            if not extraction.is_empty() or extraction.flow_signal is not None:
                await self._send_to_librarian(extraction)

            # Send entity updates
            for update in entity_updates:
                await self._send_entity_update_to_librarian(update)
            return

        for chunk in chunks:
            self.stack.append(chunk)
            logger.debug(f"Ben: Stacked chunk {chunk.id} ({chunk.tokens} tokens)")

        # ── INCREMENTAL EXTRACTION (every 3 turns) ──
        # Makes knowledge available mid-conversation instead of waiting for batch/session end
        self._turn_count_in_flow += 1
        if self._turn_count_in_flow % 3 == 0 and len(self.stack) >= 2:
            logger.info(f"Ben: Incremental extraction at turn {self._turn_count_in_flow}")
            await self._process_stack()
            return

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

        # Get raw text for flow assessment
        raw_text = "\n".join(chunk.content for chunk in chunks)

        # Extract from chunks
        extraction, entity_updates = await self._extract_chunks(chunks)

        # Assess conversational flow (Layer 2)
        flow_signal = self._assess_flow(extraction, raw_text)
        extraction.flow_signal = flow_signal

        logger.info(
            f"Ben: Flow={flow_signal.mode.value} "
            f"continuity={flow_signal.continuity_score:.2f} "
            f"topic='{flow_signal.current_topic[:30]}' "
            f"open_threads={len(flow_signal.open_threads)}"
        )

        # Send to CacheActor (batch path)
        session_id = chunks[0].source_id if chunks else ""
        await self._send_to_cache(
            extraction, flow_signal,
            source=self._current_source, session_id=session_id,
        )

        # Always send to Librarian when a flow signal exists — even on empty
        # extractions — so RECALIBRATION/AMEND signals reach thread management.
        if not extraction.is_empty() or extraction.flow_signal is not None:
            await self._send_to_librarian(extraction)
            if not extraction.is_empty():
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

    # =========================================================================
    # FLOW AWARENESS (Layer 2)
    # =========================================================================

    # Regex patterns for detecting conversational mode shifts
    _RECAL_PATTERNS = [
        _re.compile(r"(?i)^(anyway|so|moving on|switching|let'?s talk about)"),
        _re.compile(r"(?i)(different topic|change of subject|other thing)"),
        _re.compile(r"(?i)^(what about|how about|tell me about)\b(?!.*\b(this|that|it)\b)"),
    ]

    _AMEND_PATTERNS = [
        _re.compile(r"(?i)^(actually|wait|no|sorry|i mean)"),
        _re.compile(r"(?i)(go back|back to|not what i|that'?s wrong)"),
        _re.compile(r"(?i)(i meant|let me rephrase|correction)"),
    ]

    def _assess_flow(
        self,
        extraction: ExtractionOutput,
        raw_text: str,
    ) -> FlowSignal:
        """
        Assess conversational flow state from current extraction.

        Uses three signals:
        1. Entity overlap — are we talking about the same things?
        2. Explicit language — did the user signal a shift or correction?
        3. Extraction type distribution — ACTIONs without OUTCOMEs = open threads

        Pure Python, no cloud calls. < 2ms.
        """
        # 1. Gather current entities from extraction
        current_entities: set[str] = set()
        for obj in extraction.objects:
            current_entities.update(obj.entities)

        # 2. Calculate entity overlap with recent history
        if self._recent_entities:
            recent_union: set[str] = set()
            for entity_set in self._recent_entities:
                recent_union.update(entity_set)

            if current_entities or recent_union:
                intersection = current_entities & recent_union
                union = current_entities | recent_union
                entity_overlap = len(intersection) / len(union) if union else 0.0
            else:
                entity_overlap = 1.0  # No entities either way = neutral
        else:
            entity_overlap = 1.0  # First turn = flow by default

        # 3. Detect explicit signals in raw text
        signals: list[str] = []

        for pattern in self._RECAL_PATTERNS:
            if pattern.search(raw_text):
                signals.append(f"recal_language: {pattern.pattern}")

        for pattern in self._AMEND_PATTERNS:
            if pattern.search(raw_text):
                signals.append(f"amend_language: {pattern.pattern}")

        # 4. Determine mode
        has_recal_language = any("recal_language" in s for s in signals)
        has_amend_language = any("amend_language" in s for s in signals)

        if has_amend_language and entity_overlap > 0.3:
            mode = ConversationMode.AMEND
        elif has_recal_language or entity_overlap < 0.3:
            mode = ConversationMode.RECALIBRATION
        else:
            mode = ConversationMode.FLOW

        # 5. Track open threads (ACTIONs without OUTCOMEs)
        for obj in extraction.objects:
            if obj.type == ExtractionType.ACTION:
                self._open_actions.append({
                    "content": obj.content,
                    "entities": obj.entities,
                    "timestamp": time.time(),
                })
            elif obj.type == ExtractionType.OUTCOME:
                # Try to match and close an open action
                for i, action in enumerate(self._open_actions):
                    if set(action["entities"]) & set(obj.entities):
                        self._open_actions.pop(i)
                        break

        # Age out stale actions (> 24 hours)
        cutoff = time.time() - 86400
        self._open_actions = [a for a in self._open_actions if a["timestamp"] > cutoff]

        # 6. Generate topic label from highest-confidence extraction
        current_topic = self._current_topic
        if extraction.objects:
            best = max(extraction.objects, key=lambda o: o.confidence)
            if best.entities:
                current_topic = ", ".join(best.entities[:3])
            else:
                current_topic = best.content[:50]

        # 7. Update state
        if mode == ConversationMode.RECALIBRATION:
            self._turn_count_in_flow = 0
        else:
            self._turn_count_in_flow += 1

        self._recent_entities.append(current_entities)
        self._current_entities = current_entities
        self._current_topic = current_topic

        # 8. Build signal
        open_thread_descriptions = [a["content"][:80] for a in self._open_actions[-5:]]

        return FlowSignal(
            mode=mode,
            current_topic=current_topic,
            topic_entities=list(current_entities),
            continuity_score=entity_overlap,
            entity_overlap=entity_overlap,
            open_threads=open_thread_descriptions,
            correction_target=raw_text[:80] if mode == ConversationMode.AMEND else "",
            signals_detected=signals,
        )

    # =========================================================================
    # EXTRACTION
    # =========================================================================

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
                # Fallback: if local returned empty, try the Director's fallback chain
                if extraction.is_empty() and not entity_updates:
                    extraction, entity_updates = await self._extract_via_fallback(conversation_text, source_id)
            elif self.config.backend in ("haiku", "sonnet"):
                extraction, entity_updates = await self._extract_claude(conversation_text, source_id)
                # Fallback: if Claude credits exhausted, try the fallback chain
                if extraction.is_empty() and not entity_updates:
                    extraction, entity_updates = await self._extract_via_fallback(conversation_text, source_id)
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
        model = backend_config.get("model", "claude-haiku-4-5-20251001")

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

        Returns empty output if local model is unavailable.
        Does NOT fall back to Claude — sovereignty principle.
        Logs at WARNING so operators know extraction is being skipped.
        """
        if self.engine:
            director = self.engine.get_actor("director")
            if director and hasattr(director, "_local") and director._local:
                local = director._local
                if local.is_loaded:
                    try:
                        prompt = f"{EXTRACTION_SYSTEM_PROMPT}\n\nExtract from:\n{text}"
                        result = await local.generate(prompt)
                        return self._parse_extraction_response(result.text, source_id)
                    except Exception as e:
                        logger.warning(f"Ben: Local extraction failed: {e}")
                        return (ExtractionOutput(), [])
                else:
                    logger.warning(
                        "Ben: Local model not loaded — extraction skipped. "
                        "Load a model or switch backend to 'haiku'."
                    )
            else:
                logger.warning(
                    "Ben: Director has no local model configured — extraction skipped."
                )
        else:
            logger.warning("Ben: No engine reference — cannot access local model.")

        return (ExtractionOutput(), [])

    async def _extract_via_fallback(
        self,
        text: str,
        source_id: str,
    ) -> tuple[ExtractionOutput, list[EntityUpdate]]:
        """
        Extract using Director's fallback chain (Groq → Gemini → Claude).

        Called when primary backend (local or Claude) fails or returns empty.
        Uses the same fallback infrastructure as conversation generation.
        """
        if not self.engine:
            return (ExtractionOutput(), [])

        director = self.engine.get_actor("director")
        if not director or not hasattr(director, "_fallback_chain") or not director._fallback_chain:
            logger.debug("Ben: No fallback chain available for extraction")
            return (ExtractionOutput(), [])

        try:
            result = await director._fallback_chain.generate(
                messages=[
                    {
                        "role": "user",
                        "content": f"Extract knowledge from this conversation:\n\n{text}",
                    }
                ],
                system=EXTRACTION_SYSTEM_PROMPT,
                max_tokens=self.config.max_tokens,
            )

            logger.info(f"Ben: Fallback extraction via {result.provider_used}")
            return self._parse_extraction_response(result.content, source_id)

        except Exception as e:
            logger.warning(f"Ben: Fallback extraction failed: {e}")
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
    # CORRECTION EXTRACTION (Confabulation Guard integration)
    # =========================================================================

    # User correction detection patterns
    _USER_CORRECTION_PATTERNS = [
        _re.compile(r"(?i)^(no|nope|not quite|not exactly|close but)"),
        _re.compile(r"(?i)(it.s actually|it actually|the (real|correct|right) (answer|thing))"),
        _re.compile(r"(?i)(you.re (wrong|off|close|not quite)|that.s not (right|correct|it))"),
        _re.compile(r"(?i)(it puts you in|it.s called|the (name|term) is)"),
    ]

    async def _handle_extract_correction(self, msg: Message) -> None:
        """
        Handle correction event from Reconcile system.

        Creates a CORRECTION node with high confidence that supersedes
        the original confabulated claim.
        """
        payload = msg.payload or {}
        original_query = payload.get("original_query", "")
        flagged_claims = payload.get("flagged_claims", [])
        correction_response = payload.get("correction_response", "")
        session_id = payload.get("session_id", "")

        objects = []

        for claim_data in flagged_claims:
            claim = claim_data.get("claim", "")
            correction_obj = ExtractedObject(
                type=ExtractionType.CORRECTION,
                content=(
                    f"CORRECTED: Previously claimed '{claim[:100]}' but this was not "
                    f"supported by retrieved memory. Luna self-corrected. "
                    f"Original query: '{original_query}'"
                ),
                confidence=1.0,
                entities=self._extract_entity_names(claim),
                source_id=session_id,
                provenance=SourceProvenance.CORRECTED.value,
            )
            objects.append(correction_obj)

        if objects:
            extraction = ExtractionOutput(
                objects=objects,
                edges=[],
                source_id=session_id,
            )
            await self._send_to_librarian(extraction)
            logger.info(
                f"Ben: Filed {len(objects)} CORRECTION nodes — "
                f"Luna won't repeat these confabulations"
            )

    def _extract_entity_names(self, text: str) -> list:
        """Quick extraction of proper nouns from a claim."""
        words = text.split()
        entities = []
        for i, word in enumerate(words):
            cleaned = _re.sub(r'[^\w]', '', word)
            if cleaned and cleaned[0].isupper() and i > 0 and len(cleaned) > 2:
                entities.append(cleaned)
        return list(set(entities))

    def _detect_user_correction(self, user_turn: str) -> bool:
        """Detect when user is correcting something Luna said."""
        for pattern in self._USER_CORRECTION_PATTERNS:
            if pattern.search(user_turn):
                return True
        return False

    # =========================================================================
    # CACHE ACTOR INTEGRATION
    # =========================================================================

    async def _send_to_cache(
        self,
        extraction: ExtractionOutput,
        flow_signal: FlowSignal,
        source: str = "unknown",
        session_id: str = "",
    ) -> None:
        """Send extraction + flow data to CacheActor for cache write + dimensional feed."""
        if self.engine:
            cache_actor = self.engine.get_actor("cache")
            if cache_actor:
                await self.send(cache_actor, Message(
                    type="cache_update",
                    payload={
                        "extraction": extraction.to_dict(),
                        "flow_signal": flow_signal.to_dict(),
                        "source": source,
                        "session_id": session_id,
                    },
                ))
                logger.debug("Ben: Sent extraction to CacheActor")
            else:
                logger.warning("Ben: CacheActor not available, cache not updated")

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

            # Fallback to Claude — use configured backend model
            if self.config.backend != "disabled" and self.client:
                backend_config = EXTRACTION_BACKENDS.get(self.config.backend, {})
                model = backend_config.get("model", "claude-haiku-4-5-20251001")
                response = self.client.messages.create(
                    model=model,
                    max_tokens=80,
                    temperature=0.3,
                    messages=[{"role": "user", "content": compression_prompt}]
                )
                compressed = response.content[0].text.strip()
                logger.debug(f"Ben: Compressed turn via {model} ({len(content)} -> {len(compressed)} chars)")
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
