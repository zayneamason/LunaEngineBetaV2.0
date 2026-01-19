"""
Librarian Actor (The Dude) for Luna Engine
==========================================

The Librarian files extractions into the Memory Matrix and wires
knowledge together. He doesn't just store; he connects.

Persona: The Dude from The Big Lebowski. Chill, competent, cuts
through bullshit. The Dude abides... and files things where they belong.

CRITICAL: The Dude has personality in PROCESS (logs), but OUTPUTS
are NEUTRAL (clean context packets, properly filed nodes).

> "The Dude abides." — The Dude
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any, TYPE_CHECKING
import asyncio
import logging
import time

from .base import Actor, Message
from luna.extraction.types import (
    ExtractionOutput,
    ExtractedObject,
    ExtractedEdge,
    FilingResult,
)

if TYPE_CHECKING:
    from luna.engine import LunaEngine
    from luna.substrate.memory import MemoryMatrix, MemoryNode

logger = logging.getLogger(__name__)


# =============================================================================
# CONTEXT BUDGET PRESETS
# =============================================================================

BUDGET_PRESETS = {
    "minimal": 1800,   # Voice mode, fast response needed
    "balanced": 3800,  # Normal conversation
    "rich": 7200,      # Deep research, complex query
}


# =============================================================================
# LIBRARIAN ACTOR
# =============================================================================

class LibrarianActor(Actor):
    """
    The Dude: Files extractions into Memory Matrix.

    Core functions:
    - Entity Resolution: Deduplicate ("Mark" = "Zuck" = "The Landlord")
    - Knowledge Wiring: Create explicit edges from extractions
    - Context Retrieval: Get relevant context for queries
    - Synaptic Pruning: Clean low-value edges (periodic)

    Message Types:
    - file: File an extraction into Memory Matrix
    - get_context: Retrieve context for a query
    - resolve_entity: Resolve entity to existing node or create new
    - prune: Run synaptic pruning
    - get_stats: Get filing statistics
    """

    def __init__(self, engine: Optional["LunaEngine"] = None):
        super().__init__("librarian", engine)

        # Entity resolution cache: name_lower -> node_id
        self.alias_cache: dict[str, str] = {}

        # Inference queue for deferred processing
        self.inference_queue: list[str] = []
        self.batch_threshold = 10

        # Stats
        self._filings_count = 0
        self._nodes_created = 0
        self._nodes_merged = 0
        self._edges_created = 0
        self._context_retrievals = 0
        self._total_filing_time_ms = 0

        logger.info("Librarian (The Dude) initialized")

    # =========================================================================
    # MESSAGE HANDLING
    # =========================================================================

    async def handle(self, msg: Message) -> None:
        """Process messages from mailbox."""
        logger.debug(f"The Dude received: {msg.type}")

        match msg.type:
            case "file":
                await self._handle_file(msg)

            case "get_context":
                await self._handle_get_context(msg)

            case "resolve_entity":
                await self._handle_resolve_entity(msg)

            case "prune":
                await self._handle_prune(msg)

            case "get_stats":
                await self._handle_get_stats(msg)

            case _:
                logger.warning(f"The Dude: Unknown message type: {msg.type}")

    async def _handle_file(self, msg: Message) -> None:
        """
        File an extraction into Memory Matrix.

        Payload: ExtractionOutput dict (from Scribe)
        """
        payload = msg.payload or {}

        # Parse extraction from dict
        extraction = ExtractionOutput.from_dict(payload)

        if extraction.is_empty():
            logger.debug("The Dude: Empty extraction, nothing to file")
            return

        # File it
        result = await self._wire_extraction(extraction)

        logger.info(
            f"The Dude: Filed {len(result.nodes_created)} new nodes, "
            f"merged {len(result.nodes_merged)}, "
            f"created {len(result.edges_created)} edges"
        )

        # Send result back if requested
        if msg.reply_to:
            await self.send_to_engine("filing_result", result.to_dict())

    async def _handle_get_context(self, msg: Message) -> None:
        """
        Retrieve context for a query.

        Payload:
        - query: The query string
        - budget: Token budget preset ("minimal", "balanced", "rich") or int
        - node_types: Optional list of node types to include
        """
        payload = msg.payload or {}
        query = payload.get("query", "")
        budget = payload.get("budget", "balanced")
        node_types = payload.get("node_types")

        if not query:
            return

        # Convert budget preset to tokens
        if isinstance(budget, str):
            max_tokens = BUDGET_PRESETS.get(budget, 3800)
        else:
            max_tokens = int(budget)

        # Get context
        context = await self._get_context(query, max_tokens, node_types)

        self._context_retrievals += 1

        # Send result
        await self.send_to_engine("context_result", {
            "query": query,
            "nodes": [n.to_dict() for n in context],
            "count": len(context),
        })

    async def _handle_resolve_entity(self, msg: Message) -> None:
        """
        Resolve entity to existing node or create new.

        Payload:
        - name: Entity name
        - entity_type: Type (PERSON, PROJECT, CONCEPT, etc.)
        """
        payload = msg.payload or {}
        name = payload.get("name", "")
        entity_type = payload.get("entity_type", "ENTITY")

        if not name:
            return

        node_id = await self._resolve_entity(name, entity_type)

        await self.send_to_engine("entity_resolved", {
            "name": name,
            "node_id": node_id,
        })

    async def _handle_prune(self, msg: Message) -> None:
        """Run synaptic pruning on low-value connections and drifting nodes."""
        payload = msg.payload or {}
        confidence_threshold = payload.get("confidence_threshold", 0.3)
        age_days = payload.get("age_days", 30)
        prune_nodes = payload.get("prune_nodes", True)
        max_prune_nodes = payload.get("max_prune_nodes", 100)

        # Prune edges
        edge_result = await self._prune_edges(confidence_threshold, age_days)
        logger.info(f"The Dude: Pruned {edge_result['pruned']} edges")

        # Prune drifting nodes if requested
        node_result = {"pruned": 0, "preserved": 0, "candidates": 0}
        if prune_nodes:
            node_result = await self._prune_drifting_nodes(age_days, max_prune_nodes)

        combined_result = {
            "edges_pruned": edge_result["pruned"],
            "edges_preserved": edge_result["preserved"],
            "nodes_pruned": node_result["pruned"],
            "nodes_preserved": node_result["preserved"],
            "drifting_candidates": node_result["candidates"],
        }

        await self.send_to_engine("prune_result", combined_result)

    async def _handle_get_stats(self, msg: Message) -> None:
        """Return filing statistics."""
        stats = self.get_stats()
        await self.send_to_engine("librarian_stats", stats)

    # =========================================================================
    # ENTITY RESOLUTION
    # =========================================================================

    async def _resolve_entity(
        self,
        name: str,
        entity_type: str,
        source_id: str = "",
    ) -> str:
        """
        Resolve entity to existing node or create new.

        Resolution order:
        1. Alias cache (O(1))
        2. Exact DB match
        3. Create new if not found
        """
        name_lower = name.lower().strip()

        # 1. Check alias cache
        if name_lower in self.alias_cache:
            logger.debug(f"The Dude: Cache hit for '{name}'")
            return self.alias_cache[name_lower]

        # 2. Check exact DB match via Matrix actor
        matrix = await self._get_matrix()
        if matrix:
            existing = await self._find_existing_node(matrix, name, entity_type)
            if existing:
                self.alias_cache[name_lower] = existing
                self._nodes_merged += 1
                logger.debug(f"The Dude: Found existing node for '{name}'")
                return existing

        # 3. Create new node
        node_id = await self._create_node(name, entity_type, source_id)
        self.alias_cache[name_lower] = node_id
        self._nodes_created += 1

        logger.debug(f"The Dude: Created new node for '{name}' -> {node_id}")
        return node_id

    async def _find_existing_node(
        self,
        matrix: "MemoryMatrix",
        name: str,
        entity_type: str,
    ) -> Optional[str]:
        """Find existing node by name and type."""
        # Search for exact match
        nodes = await matrix.search_nodes(name, node_type=entity_type, limit=1)

        for node in nodes:
            # Check for exact content match
            if node.content.lower() == name.lower():
                return node.id

        return None

    async def _create_node(
        self,
        content: str,
        node_type: str,
        source_id: str = "",
    ) -> str:
        """Create a new memory node."""
        matrix = await self._get_matrix()
        if not matrix:
            # Fallback: generate ID but can't persist
            import uuid
            return str(uuid.uuid4())[:12]

        node_id = await matrix.add_node(
            node_type=node_type,
            content=content,
            source=source_id,
            confidence=1.0,
            importance=0.5,
        )

        return node_id

    # =========================================================================
    # KNOWLEDGE WIRING
    # =========================================================================

    async def _wire_extraction(
        self,
        extraction: ExtractionOutput,
    ) -> FilingResult:
        """
        Wire extraction into Memory Matrix.

        1. Resolve/create nodes for each extracted object
        2. Create edges between entities
        """
        start_time = time.monotonic()

        result = FilingResult()

        # 1. Process objects - create/resolve nodes
        for obj in extraction.objects:
            node_id = await self._resolve_entity(
                name=obj.content,
                entity_type=obj.type.value if hasattr(obj.type, 'value') else str(obj.type),
                source_id=extraction.source_id,
            )

            # Track if created or merged
            if self._nodes_created > len(result.nodes_created) + len(result.nodes_merged):
                result.nodes_created.append(node_id)
            else:
                result.nodes_merged.append((obj.content, node_id))

            # Also resolve any mentioned entities
            for entity in obj.entities:
                await self._resolve_entity(
                    name=entity,
                    entity_type="ENTITY",
                    source_id=extraction.source_id,
                )

        # 2. Create edges
        for edge in extraction.edges:
            try:
                from_id = await self._resolve_entity(
                    edge.from_ref,
                    "ENTITY",
                    extraction.source_id,
                )
                to_id = await self._resolve_entity(
                    edge.to_ref,
                    "ENTITY",
                    extraction.source_id,
                )

                # Create edge in graph
                edge_created = await self._create_edge(
                    from_id=from_id,
                    to_id=to_id,
                    edge_type=edge.edge_type,
                    confidence=edge.confidence,
                )

                if edge_created:
                    result.edges_created.append(f"{from_id}->{to_id}")
                    self._edges_created += 1
                else:
                    result.edges_skipped.append(
                        f"duplicate: {edge.from_ref}->{edge.to_ref}"
                    )

            except Exception as e:
                logger.warning(f"The Dude: Failed to create edge: {e}")
                result.edges_skipped.append(f"error: {e}")

        # Update stats
        filing_time_ms = int((time.monotonic() - start_time) * 1000)
        result.filing_time_ms = filing_time_ms
        self._filings_count += 1
        self._total_filing_time_ms += filing_time_ms

        return result

    async def _create_edge(
        self,
        from_id: str,
        to_id: str,
        edge_type: str,
        confidence: float = 1.0,
    ) -> bool:
        """
        Create edge between nodes.

        Returns True if created, False if duplicate.
        """
        # Get matrix actor to access graph
        if not self.engine:
            return False

        matrix_actor = self.engine.get_actor("matrix")
        if not matrix_actor:
            return False

        # Use matrix actor's graph if available
        if hasattr(matrix_actor, "_graph") and matrix_actor._graph:
            graph = matrix_actor._graph

            # Check if edge already exists
            if graph.has_edge(from_id, to_id, edge_type):
                return False

            # Create edge
            graph.add_edge(
                from_id=from_id,
                to_id=to_id,
                edge_type=edge_type,
                weight=confidence,
            )
            return True

        return False

    # =========================================================================
    # CONTEXT RETRIEVAL
    # =========================================================================

    async def _get_context(
        self,
        query: str,
        max_tokens: int,
        node_types: Optional[list[str]] = None,
    ) -> list["MemoryNode"]:
        """
        Get relevant context for a query within token budget.

        Uses MatrixActor for retrieval.
        """
        matrix = await self._get_matrix()
        if not matrix:
            return []

        # Use matrix's get_context method
        nodes = await matrix.get_context(
            query=query,
            max_tokens=max_tokens,
            node_types=node_types,
        )

        return nodes

    # =========================================================================
    # SYNAPTIC PRUNING
    # =========================================================================

    async def _prune_edges(
        self,
        confidence_threshold: float = 0.3,
        age_days: int = 30,
    ) -> dict:
        """
        Remove stale, low-confidence edges.

        Prunes edges that:
        - Have confidence below threshold
        - Are older than age_days
        - Connect to drifting nodes
        """
        result = {"pruned": 0, "preserved": 0}

        # Get matrix actor's graph
        if not self.engine:
            return result

        matrix_actor = self.engine.get_actor("matrix")
        if not matrix_actor or not hasattr(matrix_actor, "_graph"):
            return result

        graph = matrix_actor._graph
        if not graph:
            return result

        # Get all edges and filter
        all_edges = graph.get_all_edges()
        cutoff = datetime.now().timestamp() - (age_days * 24 * 3600)

        for edge in all_edges:
            # Skip high-confidence edges
            if edge.get("weight", 1.0) >= confidence_threshold:
                result["preserved"] += 1
                continue

            # Skip recent edges
            created = edge.get("created_at", datetime.now().timestamp())
            if created > cutoff:
                result["preserved"] += 1
                continue

            # Prune this edge
            try:
                graph.remove_edge(
                    edge["from_id"],
                    edge["to_id"],
                    edge.get("edge_type"),
                )
                result["pruned"] += 1
            except Exception:
                result["preserved"] += 1

        return result

    async def _prune_drifting_nodes(
        self,
        age_days: int = 30,
        max_prune: int = 100,
    ) -> dict:
        """
        Remove nodes that are drifting and old.

        Only prunes nodes that:
        - Have lock_in_state = 'drifting'
        - Are older than age_days
        - Have zero reinforcement_count (never explicitly marked important)

        Args:
            age_days: Minimum age for pruning
            max_prune: Maximum nodes to prune in one pass

        Returns:
            Dict with 'pruned' and 'preserved' counts
        """
        result = {"pruned": 0, "preserved": 0, "candidates": 0}

        matrix = await self._get_matrix()
        if not matrix:
            return result

        # Get drifting nodes
        drifting = await matrix.get_drifting_nodes(limit=max_prune * 2)
        result["candidates"] = len(drifting)

        cutoff = datetime.now().timestamp() - (age_days * 24 * 3600)

        for node in drifting:
            # Never prune reinforced nodes
            if node.reinforcement_count > 0:
                result["preserved"] += 1
                continue

            # Skip recent nodes
            if node.created_at:
                node_ts = node.created_at.timestamp()
                if node_ts > cutoff:
                    result["preserved"] += 1
                    continue

            # Prune this node
            try:
                deleted = await matrix.delete_node(node.id)
                if deleted:
                    result["pruned"] += 1
                    logger.debug(f"The Dude: Pruned drifting node {node.id}")
                else:
                    result["preserved"] += 1
            except Exception as e:
                logger.warning(f"The Dude: Failed to prune {node.id}: {e}")
                result["preserved"] += 1

            # Respect max_prune limit
            if result["pruned"] >= max_prune:
                break

        logger.info(
            f"The Dude: Pruning complete - {result['pruned']} pruned, "
            f"{result['preserved']} preserved out of {result['candidates']} drifting"
        )
        return result

    # =========================================================================
    # HELPERS
    # =========================================================================

    async def _get_matrix(self) -> Optional["MemoryMatrix"]:
        """Get MemoryMatrix from MatrixActor."""
        if not self.engine:
            return None

        matrix_actor = self.engine.get_actor("matrix")
        if not matrix_actor:
            return None

        # MatrixActor stores MemoryMatrix in _matrix (or _memory for backwards compat)
        if hasattr(matrix_actor, "_matrix") and matrix_actor._matrix:
            return matrix_actor._matrix
        if hasattr(matrix_actor, "_memory"):
            return matrix_actor._memory

        return None

    # =========================================================================
    # STATS & LIFECYCLE
    # =========================================================================

    def get_stats(self) -> dict:
        """Get filing statistics."""
        avg_time = (
            self._total_filing_time_ms / self._filings_count
            if self._filings_count > 0
            else 0
        )
        return {
            "filings_count": self._filings_count,
            "nodes_created": self._nodes_created,
            "nodes_merged": self._nodes_merged,
            "edges_created": self._edges_created,
            "context_retrievals": self._context_retrievals,
            "avg_filing_time_ms": avg_time,
            "cache_size": len(self.alias_cache),
            "inference_queue_size": len(self.inference_queue),
        }

    async def snapshot(self) -> dict:
        """Return state for serialization."""
        base = await super().snapshot()
        base.update({
            "stats": self.get_stats(),
            "cache_size": len(self.alias_cache),
        })
        return base

    async def on_start(self) -> None:
        """Initialize on start."""
        logger.info("The Dude: Yeah, well, you know, that's just like, my opinion, man.")

    async def on_stop(self) -> None:
        """Cleanup on stop."""
        # Process any remaining inference queue
        if self.inference_queue:
            logger.info(f"The Dude: {len(self.inference_queue)} items in inference queue at shutdown")
