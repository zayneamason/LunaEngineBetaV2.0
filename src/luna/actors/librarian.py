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
from luna.entities.models import (
    Entity,
    EntityType,
    ChangeType,
    EntityUpdate,
    EntityVersion,
)

if TYPE_CHECKING:
    from luna.engine import LunaEngine
    from luna.substrate.memory import MemoryMatrix, MemoryNode
    from luna.entities.resolution import EntityResolver

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

        # Entity resolver (lazy init)
        self._entity_resolver: Optional["EntityResolver"] = None

        # Inference queue for deferred processing
        self.inference_queue: list[str] = []
        self.batch_threshold = 10

        # Stats
        self._filings_count = 0
        self._nodes_created = 0
        self._nodes_merged = 0
        self._edges_created = 0
        self._edges_failed = 0
        self._edges_skipped_duplicate = 0
        self._entity_resolve_failures = 0
        self._context_retrievals = 0
        self._entity_updates_filed = 0
        self._entity_versions_created = 0
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

            case "entity_update":
                await self._handle_entity_update(msg)

            case "get_context":
                await self._handle_get_context(msg)

            case "resolve_entity":
                await self._handle_resolve_entity(msg)

            case "rollback_entity":
                await self._handle_rollback_entity(msg)

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

    async def _handle_entity_update(self, msg: Message) -> None:
        """
        Handle entity update from Scribe.

        Payload: EntityUpdate dict (from Scribe)
        - update_type: create, update, synthesize
        - entity_id: Optional entity ID (for updates to existing)
        - name: Entity name (required for create)
        - entity_type: person, persona, place, project
        - facts: Dictionary of facts to add/update
        - source: Source of the update
        """
        payload = msg.payload or {}

        # Parse the update type
        update_type_str = payload.get("update_type", "update")
        try:
            update_type = ChangeType(update_type_str) if update_type_str in [e.value for e in ChangeType] else ChangeType.UPDATE
        except ValueError:
            update_type = ChangeType.UPDATE

        # Parse entity type
        entity_type_str = payload.get("entity_type", "person")
        try:
            entity_type = EntityType(entity_type_str) if entity_type_str in [e.value for e in EntityType] else EntityType.PERSON
        except ValueError:
            entity_type = EntityType.PERSON

        entity_update = EntityUpdate(
            update_type=update_type,
            entity_id=payload.get("entity_id"),
            name=payload.get("name"),
            entity_type=entity_type,
            facts=payload.get("facts", {}),
            source=payload.get("source"),
        )

        # File the entity update
        result = await self._file_entity_update(entity_update)

        if result:
            logger.info(f"The Dude: Filed entity update for '{entity_update.name}'")
            self._entity_updates_filed += 1
        else:
            logger.warning(f"The Dude: Failed to file entity update for '{entity_update.name}'")

        # Send result if requested
        if msg.reply_to:
            await self.send_to_engine("entity_update_result", {
                "success": result is not None,
                "entity_id": result.id if result else None,
                "name": entity_update.name,
            })

    async def _handle_rollback_entity(self, msg: Message) -> None:
        """
        Handle entity rollback request.

        Payload:
        - entity_id: Entity ID to rollback
        - version: Target version number (optional, defaults to previous)
        - reason: Reason for rollback
        """
        payload = msg.payload or {}
        entity_id = payload.get("entity_id", "")
        target_version = payload.get("version")
        reason = payload.get("reason", "Rollback requested")

        if not entity_id:
            logger.warning("The Dude: Rollback requested without entity_id")
            return

        result = await self._rollback_entity(entity_id, target_version, reason)

        if result:
            logger.info(f"The Dude: Rolled back entity '{entity_id}' to version {target_version or 'previous'}")
        else:
            logger.warning(f"The Dude: Failed to rollback entity '{entity_id}'")

        # Send result
        await self.send_to_engine("rollback_result", {
            "success": result,
            "entity_id": entity_id,
            "reason": reason,
        })

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
        try:
            node_id = await self._create_node(name, entity_type, source_id)
            self.alias_cache[name_lower] = node_id
            self._nodes_created += 1
            logger.debug(f"ENTITY_NEW: '{name}' -> {node_id} (type={entity_type})")
            return node_id
        except Exception as e:
            logger.error(
                f"ENTITY_FAIL: Could not create node for '{name}' | "
                f"type={entity_type} source={source_id} | error={e}"
            )
            self._entity_resolve_failures += 1
            # Return a fallback ID so edge creation can still attempt
            import uuid
            fallback_id = f"unresolved_{uuid.uuid4().hex[:8]}"
            logger.warning(f"ENTITY_FALLBACK: Using {fallback_id} for '{name}'")
            return fallback_id

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
    # ENTITY FILING
    # =========================================================================

    async def _get_entity_resolver(self) -> Optional["EntityResolver"]:
        """Get or create EntityResolver instance."""
        if self._entity_resolver is not None:
            return self._entity_resolver

        # Try to get database from Matrix actor
        matrix = await self._get_matrix()
        if not matrix or not hasattr(matrix, 'db'):
            logger.warning("The Dude: Can't create EntityResolver, no database available")
            return None

        try:
            from luna.entities.resolution import EntityResolver
            self._entity_resolver = EntityResolver(matrix.db)
            logger.debug("The Dude: EntityResolver initialized")
            return self._entity_resolver
        except Exception as e:
            logger.error(f"The Dude: Failed to create EntityResolver: {e}")
            return None

    async def _file_entity_update(self, update: EntityUpdate) -> Optional[Entity]:
        """
        File an entity update to the database.

        Creates or updates an entity based on the update type.
        Always creates a new version record (append-only).

        Args:
            update: EntityUpdate from Scribe

        Returns:
            Updated Entity if successful, None otherwise
        """
        import json
        from datetime import datetime

        resolver = await self._get_entity_resolver()
        if not resolver:
            logger.error("The Dude: No EntityResolver available for filing")
            return None

        try:
            # Resolve or create the entity
            name = update.name or ""
            entity_type = update.entity_type.value if hasattr(update.entity_type, 'value') else str(update.entity_type)

            if update.update_type == ChangeType.CREATE or not update.entity_id:
                # Use resolve_or_create for new entities
                entity = await resolver.resolve_or_create(
                    name=name,
                    entity_type=entity_type,
                    source=update.source or "scribe",
                )
            else:
                # Get existing entity by ID
                entity = await resolver.get_entity(update.entity_id)
                if not entity:
                    # Try to resolve by name
                    entity = await resolver.resolve_entity(name)

                if not entity:
                    logger.warning(f"The Dude: Entity not found: {update.entity_id or name}")
                    return None

            # Merge new facts with existing
            merged_facts = dict(entity.core_facts)
            merged_facts.update(update.facts)

            # Update entity record
            now = datetime.now().isoformat()
            new_version = entity.current_version + 1

            await resolver.db.execute(
                """
                UPDATE entities
                SET core_facts = ?, current_version = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    json.dumps(merged_facts),
                    new_version,
                    now,
                    entity.id,
                )
            )

            # Create version record (append-only)
            change_type = update.update_type.value if hasattr(update.update_type, 'value') else str(update.update_type)
            change_summary = f"Added facts: {', '.join(update.facts.keys())}" if update.facts else "Update"

            await resolver.db.execute(
                """
                INSERT INTO entity_versions (
                    entity_id, version, core_facts, full_profile, voice_config,
                    change_type, change_summary, changed_by, change_source,
                    created_at, valid_from, valid_until
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entity.id,
                    new_version,
                    json.dumps(merged_facts),
                    entity.full_profile,
                    json.dumps(entity.voice_config) if entity.voice_config else None,
                    change_type,
                    change_summary,
                    "scribe",
                    update.source,
                    now,
                    now,
                    None,  # valid_until = NULL (current version)
                )
            )

            # Close out previous version
            await resolver.db.execute(
                """
                UPDATE entity_versions
                SET valid_until = ?
                WHERE entity_id = ? AND version = ?
                """,
                (now, entity.id, entity.current_version)
            )

            self._entity_versions_created += 1

            # Return updated entity
            entity.core_facts = merged_facts
            entity.current_version = new_version
            entity.updated_at = now

            logger.debug(f"The Dude: Filed entity update for '{entity.id}' v{new_version}")
            return entity

        except Exception as e:
            logger.error(f"The Dude: Failed to file entity update: {e}")
            return None

    async def _rollback_entity(
        self,
        entity_id: str,
        target_version: Optional[int] = None,
        reason: str = "Rollback requested",
    ) -> bool:
        """
        Rollback an entity to a previous version.

        Args:
            entity_id: Entity ID to rollback
            target_version: Target version (None = previous version)
            reason: Reason for rollback

        Returns:
            True if rollback successful
        """
        import json
        from datetime import datetime

        resolver = await self._get_entity_resolver()
        if not resolver:
            logger.error("The Dude: No EntityResolver available for rollback")
            return False

        try:
            # Get current entity
            entity = await resolver.get_entity(entity_id)
            if not entity:
                logger.warning(f"The Dude: Entity not found for rollback: {entity_id}")
                return False

            # Determine target version
            if target_version is None:
                target_version = entity.current_version - 1

            if target_version < 1:
                logger.warning(f"The Dude: Invalid target version {target_version}")
                return False

            # Get target version record
            row = await resolver.db.fetchone(
                """
                SELECT core_facts, full_profile, voice_config
                FROM entity_versions
                WHERE entity_id = ? AND version = ?
                """,
                (entity_id, target_version)
            )

            if not row:
                logger.warning(f"The Dude: Version {target_version} not found for {entity_id}")
                return False

            # Parse version data
            target_core_facts = json.loads(row[0]) if row[0] else {}
            target_full_profile = row[1]
            target_voice_config = json.loads(row[2]) if row[2] else {}

            # Create new version with rollback data
            now = datetime.now().isoformat()
            new_version = entity.current_version + 1

            # Update entity to rolled-back state
            await resolver.db.execute(
                """
                UPDATE entities
                SET core_facts = ?, full_profile = ?, voice_config = ?,
                    current_version = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    json.dumps(target_core_facts),
                    target_full_profile,
                    json.dumps(target_voice_config) if target_voice_config else None,
                    new_version,
                    now,
                    entity_id,
                )
            )

            # Create rollback version record
            await resolver.db.execute(
                """
                INSERT INTO entity_versions (
                    entity_id, version, core_facts, full_profile, voice_config,
                    change_type, change_summary, changed_by, change_source,
                    created_at, valid_from, valid_until
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entity_id,
                    new_version,
                    json.dumps(target_core_facts),
                    target_full_profile,
                    json.dumps(target_voice_config) if target_voice_config else None,
                    "rollback",
                    f"Rolled back to v{target_version}: {reason}",
                    "librarian",
                    None,
                    now,
                    now,
                    None,
                )
            )

            # Close out previous version
            await resolver.db.execute(
                """
                UPDATE entity_versions
                SET valid_until = ?
                WHERE entity_id = ? AND version = ?
                """,
                (now, entity_id, entity.current_version)
            )

            self._entity_versions_created += 1
            logger.info(f"The Dude: Rolled back '{entity_id}' to v{target_version}")
            return True

        except Exception as e:
            logger.error(f"The Dude: Failed to rollback entity: {e}")
            return False

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

        # 1. Process objects - store as memory nodes, resolve mentioned entities
        matrix = await self._get_matrix()

        for obj in extraction.objects:
            node_type = obj.type.value if hasattr(obj.type, 'value') else str(obj.type)

            # Store the extracted object as a memory node (not as an entity)
            if matrix:
                node_id = await matrix.add_node(
                    node_type=node_type,
                    content=obj.content,
                    source=extraction.source_id,
                    confidence=obj.confidence,
                    metadata=obj.metadata if hasattr(obj, 'metadata') else None,
                )
                result.nodes_created.append(node_id)
                self._nodes_created += 1
            else:
                import uuid
                node_id = str(uuid.uuid4())[:12]
                result.nodes_created.append(node_id)

            # Resolve mentioned entities (these ARE entity names)
            for entity_name in obj.entities:
                entity_id = await self._resolve_entity(
                    name=entity_name,
                    entity_type="ENTITY",
                    source_id=extraction.source_id,
                )
                # Create MENTIONS edge from the memory node to the entity
                await self._create_edge(
                    from_id=node_id,
                    to_id=entity_id,
                    edge_type="MENTIONS",
                    confidence=obj.confidence,
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
                logger.error(
                    f"EDGE_WIRE_FAIL: Exception in edge wiring | "
                    f"from_ref={edge.from_ref} to_ref={edge.to_ref} "
                    f"type={edge.edge_type} | error={type(e).__name__}: {e}"
                )
                self._edges_failed += 1
                result.edges_skipped.append(f"error: {type(e).__name__}: {e}")

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
        Logs all failures with full context for debugging.
        """
        # Get matrix actor to access graph
        if not self.engine:
            logger.error(
                "EDGE_FAIL: No engine reference | "
                f"from={from_id} to={to_id} type={edge_type}"
            )
            self._edges_failed += 1
            return False

        matrix_actor = self.engine.get_actor("matrix")
        if not matrix_actor:
            logger.error(
                "EDGE_FAIL: Matrix actor not found | "
                f"from={from_id} to={to_id} type={edge_type}"
            )
            self._edges_failed += 1
            return False

        # Use matrix actor's graph if available
        if not hasattr(matrix_actor, "_graph") or not matrix_actor._graph:
            logger.error(
                "EDGE_FAIL: Matrix actor has no graph | "
                f"from={from_id} to={to_id} type={edge_type} "
                f"has_attr={hasattr(matrix_actor, '_graph')} "
                f"graph_val={getattr(matrix_actor, '_graph', 'MISSING')}"
            )
            self._edges_failed += 1
            return False

        graph = matrix_actor._graph

        # Check if edge already exists
        if graph.has_edge(from_id, to_id):
            logger.debug(
                f"EDGE_SKIP: Duplicate | from={from_id} to={to_id} type={edge_type}"
            )
            self._edges_skipped_duplicate += 1
            return False

        # Create the edge
        try:
            await graph.add_edge(
                from_id=from_id,
                to_id=to_id,
                relationship=edge_type,
                strength=confidence,
            )
            logger.info(
                f"EDGE_OK: {from_id} --[{edge_type} @ {confidence:.2f}]--> {to_id}"
            )
            return True
        except TypeError as e:
            # This is the exact error class that killed edges before.
            logger.critical(
                f"EDGE_CRITICAL: TypeError in graph.add_edge — API CONTRACT VIOLATION | "
                f"from={from_id} to={to_id} type={edge_type} confidence={confidence} | "
                f"error={e}"
            )
            self._edges_failed += 1
            return False
        except Exception as e:
            logger.error(
                f"EDGE_FAIL: Unexpected error in graph.add_edge | "
                f"from={from_id} to={to_id} type={edge_type} | "
                f"error_type={type(e).__name__} error={e}"
            )
            self._edges_failed += 1
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

        # Iterate NetworkX edges via graph.graph property
        cutoff = datetime.now().timestamp() - (age_days * 24 * 3600)
        edges_to_prune = []

        for u, v, data in graph.graph.edges(data=True):
            strength = data.get("strength", 1.0)
            # created_at is stored as ISO string by add_edge, parse it
            created_raw = data.get("created_at")
            if isinstance(created_raw, str):
                try:
                    created = datetime.fromisoformat(created_raw).timestamp()
                except ValueError:
                    created = datetime.now().timestamp()
            elif isinstance(created_raw, (int, float)):
                created = float(created_raw)
            else:
                created = datetime.now().timestamp()

            if strength >= confidence_threshold:
                result["preserved"] += 1
                continue

            if created > cutoff:
                result["preserved"] += 1
                continue

            edges_to_prune.append((u, v, data.get("relationship")))

        for from_id, to_id, relationship in edges_to_prune:
            try:
                await graph.remove_edge(from_id, to_id, relationship)
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
            "edges_failed": self._edges_failed,
            "edges_skipped_duplicate": self._edges_skipped_duplicate,
            "entity_resolve_failures": self._entity_resolve_failures,
            "context_retrievals": self._context_retrievals,
            "entity_updates_filed": self._entity_updates_filed,
            "entity_versions_created": self._entity_versions_created,
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

    def _load_alias_cache(self) -> None:
        """Load alias cache from disk."""
        import json
        import os
        cache_path = os.path.join(
            os.environ.get("LUNA_BASE_PATH", ""),
            "data", "alias_cache.json"
        )
        try:
            if os.path.exists(cache_path):
                with open(cache_path, "r") as f:
                    self.alias_cache = json.load(f)
                logger.info(f"The Dude: Loaded {len(self.alias_cache)} alias cache entries")
        except Exception as e:
            logger.warning(f"The Dude: Failed to load alias cache: {e}")

    def _save_alias_cache(self) -> None:
        """Save alias cache to disk."""
        import json
        import os
        cache_path = os.path.join(
            os.environ.get("LUNA_BASE_PATH", ""),
            "data", "alias_cache.json"
        )
        try:
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            with open(cache_path, "w") as f:
                json.dump(self.alias_cache, f)
            logger.debug(f"The Dude: Saved {len(self.alias_cache)} alias cache entries")
        except Exception as e:
            logger.warning(f"The Dude: Failed to save alias cache: {e}")

    async def on_start(self) -> None:
        """Initialize on start."""
        self._load_alias_cache()
        logger.info("The Dude: Yeah, well, you know, that's just like, my opinion, man.")

    async def on_stop(self) -> None:
        """Cleanup on stop."""
        self._save_alias_cache()
        # Process any remaining inference queue
        if self.inference_queue:
            logger.info(f"The Dude: {len(self.inference_queue)} items in inference queue at shutdown")
