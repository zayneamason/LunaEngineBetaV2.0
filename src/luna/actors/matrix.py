"""
Matrix Actor - Memory Substrate Interface
==========================================

The Matrix is Luna's long-term memory - her soul lives here.

Powered by Luna Engine's native memory substrate:
- SQLite with WAL mode for concurrent access
- NetworkX graph for relationship traversal
- Lock-in coefficient for memory persistence
- Full-text search via LIKE queries

The engine queries the Matrix directly for context before generation.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional, List

from luna.actors.base import Actor
from luna.substrate import MemoryDatabase, MemoryMatrix, MemoryGraph

logger = logging.getLogger(__name__)


class MatrixActor(Actor):
    """
    Memory substrate actor.

    Manages Luna's long-term memory through:
    - SQLite database with WAL mode
    - MemoryMatrix for CRUD operations
    - MemoryGraph for relationship traversal
    - Lock-in coefficient for memory persistence
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize the Matrix actor.

        Args:
            db_path: Path to SQLite database.
                     Defaults to data/luna_engine.db
        """
        super().__init__(name="matrix")

        if db_path:
            self.db_path = db_path
        else:
            # Default: project data directory
            self.db_path = Path(__file__).parent.parent.parent.parent / "data" / "luna_engine.db"

        self._db: Optional[MemoryDatabase] = None
        self._matrix: Optional[MemoryMatrix] = None
        self._graph: Optional[MemoryGraph] = None
        self._initialized = False

    @property
    def matrix(self):
        """Access the memory matrix."""
        return self._matrix

    @property
    def graph(self):
        """Access the NetworkX graph."""
        if self._graph:
            return self._graph._graph
        return None

    @property
    def is_ready(self) -> bool:
        """Check if the matrix is initialized."""
        return self._initialized

    async def initialize(self) -> None:
        """Initialize database and load graph."""
        if self._initialized:
            return

        logger.info(f"Matrix actor starting with db: {self.db_path}")

        # Ensure data directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Connect to database
        self._db = MemoryDatabase(self.db_path)
        await self._db.connect()

        # Initialize memory matrix
        self._matrix = MemoryMatrix(self._db)

        # Initialize graph
        self._graph = MemoryGraph(self._db)
        await self._graph.load_from_db()

        # Wire graph into matrix for spreading activation in get_context()
        self._matrix.graph = self._graph

        self._initialized = True

        stats = await self._matrix.get_stats()
        graph_stats = await self._graph.get_stats()
        node_count = stats.get('total_nodes', 0)
        edge_count = graph_stats.get('edge_count', 0)
        logger.info(f"Matrix actor ready: {node_count} nodes, {edge_count} edges")

        # Warn if memory looks empty (likely pointing to wrong database)
        if node_count < 1000:
            logger.warning(
                f"⚠️  LOW MEMORY COUNT: Only {node_count} nodes found. "
                f"Luna's brain should have 50k+ nodes. "
                f"Check database path: {self.db_path}"
            )

    async def start(self) -> None:
        """Start the actor's mailbox processing loop."""
        if not self._initialized:
            await self.initialize()
        await super().start()

    async def stop(self) -> None:
        """Close database connection."""
        await super().stop()

        if self._db:
            await self._db.close()
            self._db = None
            self._matrix = None
            self._graph = None

        self._initialized = False
        logger.info("Matrix actor stopped")

    async def handle(self, msg) -> None:
        """
        Handle messages from mailbox.

        Message types:
        - store: Store a memory node
        - retrieve: Get context for query
        - search: Search memory nodes
        """
        from luna.actors.base import Message

        if not isinstance(msg, Message):
            return

        payload = msg.payload or {}

        if msg.type == "store":
            await self.store_memory(
                content=payload.get("content", ""),
                node_type=payload.get("node_type", "FACT"),
                tags=payload.get("tags", []),
                confidence=payload.get("confidence", 100),
            )

        elif msg.type == "retrieve":
            ctx = await self.get_context(
                query=payload.get("query", ""),
                max_tokens=payload.get("max_tokens", 3800),
            )
            logger.debug(f"Retrieved context: {len(ctx)} chars")

        elif msg.type == "search":
            results = await self.search(
                query=payload.get("query", ""),
                limit=payload.get("limit", 10),
            )
            logger.debug(f"Search found {len(results)} nodes")

    # =========================================================================
    # Core Memory Operations
    # =========================================================================

    async def store_memory(
        self,
        content: str,
        node_type: str = "FACT",
        tags: Optional[List[str]] = None,
        confidence: int = 100,
        session_id: Optional[str] = None,
    ) -> str:
        """
        Store a memory node.

        Args:
            content: The memory content
            node_type: Type (FACT, DECISION, PROBLEM, ASSUMPTION, ACTION, OUTCOME)
            tags: Optional semantic tags (stored in metadata)
            confidence: Confidence level 0-100
            session_id: Optional session ID (stored in metadata)

        Returns:
            The node ID
        """
        if not self._initialized:
            raise RuntimeError("Matrix not initialized")

        # Build metadata
        metadata = {}
        if tags:
            metadata["tags"] = tags
        if session_id:
            metadata["session_id"] = session_id

        return await self._matrix.add_node(
            node_type=node_type,
            content=content,
            confidence=confidence / 100.0,
            importance=0.5,
            metadata=metadata if metadata else None,
        )

    async def store_turn(
        self,
        session_id: str,
        role: str,
        content: str,
        tokens: Optional[int] = None,
    ) -> str:
        """
        Store a conversation turn as a FACT memory node.

        Args:
            session_id: Session identifier
            role: Who said this (user, assistant, system)
            content: Message content
            tokens: Optional token count (stored in metadata)

        Returns:
            The node ID
        """
        # Store conversation turns as FACT nodes
        metadata = {
            "tags": ["conversation", role, session_id],
            "session_id": session_id,
        }
        if tokens:
            metadata["tokens"] = tokens

        return await self._matrix.add_node(
            node_type="FACT",
            content=f"[{role}] {content}",
            source="conversation",
            metadata=metadata,
        )

    async def get_recent_turns(self, session_id: Optional[str] = None, limit: int = 10) -> list:
        """Get recent conversation turns (searches FACT nodes tagged as conversation)."""
        if not self._initialized:
            return []

        # Search for conversation-tagged nodes
        results = await self.search(f"conversation {session_id or ''}", limit=limit)
        return results

    async def get_context(
        self,
        query: str,
        max_tokens: int = 3800,
        budget_preset: str = "balanced",
    ) -> str:
        """
        Get relevant context for a query.

        Args:
            query: The query to find context for
            max_tokens: Maximum tokens of context to return
            budget_preset: Ignored (for API compatibility)

        Returns:
            Formatted context string
        """
        if not self._initialized:
            return ""

        # Get memory nodes
        nodes = await self._matrix.get_context(query, max_tokens=max_tokens)

        if not nodes:
            return ""

        # Format as markdown for Luna
        return self._format_context(nodes)

    def _format_context(self, nodes: list) -> str:
        """Format nodes as markdown for Luna."""
        parts = []

        # Group nodes by type
        by_type = {}
        for node in nodes:
            node_type = node.node_type
            if node_type not in by_type:
                by_type[node_type] = []
            by_type[node_type].append(node)

        # Format each type group
        type_order = ["FACT", "DECISION", "PROBLEM", "ACTION", "OUTCOME", "ASSUMPTION"]
        for node_type in type_order:
            if node_type in by_type:
                type_nodes = by_type[node_type]
                section = f"## {node_type}s\n"
                for node in type_nodes[:10]:  # Limit per type
                    # Show lock-in state if settled
                    lock_indicator = " 🔒" if node.lock_in_state == "settled" else ""
                    section += f"- {node.content[:500]}{lock_indicator}\n"
                parts.append(section)

        # Add remaining types
        for node_type, type_nodes in by_type.items():
            if node_type not in type_order:
                section = f"## {node_type}s\n"
                for node in type_nodes[:5]:
                    section += f"- {node.content[:500]}\n"
                parts.append(section)

        result = "\n".join(parts)
        logger.debug(f"Context: {len(nodes)} nodes")
        return result

    async def search(
        self,
        query: str,
        limit: int = 10,
        use_hybrid: bool = True,  # Ignored, for API compatibility
    ) -> list:
        """
        Search for memory nodes.

        Args:
            query: Search text
            limit: Max results
            use_hybrid: Ignored (for API compatibility)

        Returns:
            List of matching nodes
        """
        if not self._initialized:
            return []

        return await self._matrix.search_nodes(query=query, limit=limit)

    async def get_stats(self) -> dict:
        """Get memory statistics."""
        if not self._initialized:
            return {"initialized": False}

        matrix_stats = await self._matrix.get_stats()
        graph_stats = {"nodes": 0, "edges": 0}

        if self._graph:
            g_stats = await self._graph.get_stats()
            graph_stats = {
                "nodes": g_stats.get("node_count", 0),
                "edges": g_stats.get("edge_count", 0),
            }

        return {
            "backend": "luna_substrate",
            "db_path": str(self.db_path),
            **matrix_stats,
            "graph": graph_stats,
        }

    # =========================================================================
    # Advanced Operations
    # =========================================================================

    async def reinforce_memory(self, node_id: str, amount: int = 1) -> None:
        """
        Reinforce a memory (increases lock-in coefficient).

        Args:
            node_id: Node to reinforce
            amount: Reinforcement amount (each call = +1)
        """
        if not self._matrix:
            return

        for _ in range(amount):
            await self._matrix.reinforce_node(node_id)

        logger.debug(f"Reinforced memory {node_id} by {amount}")

    async def find_related(self, node_id: str, depth: int = 2) -> List[str]:
        """
        Find related nodes via graph traversal.

        Args:
            node_id: Starting node
            depth: How many hops to traverse

        Returns:
            List of related node IDs
        """
        if not self._graph:
            return []

        return self._graph.get_neighbors(node_id, depth=depth)

    async def get_central_concepts(self, limit: int = 10) -> list:
        """
        Get most central/influential memory nodes.

        Returns:
            List of (node_id, score) tuples
        """
        if not self._graph:
            return []

        return self._graph.get_central_nodes(limit=limit)

    # =========================================================================
    # Additional Methods for API Compatibility
    # =========================================================================

    async def add_node(
        self,
        node_type: str,
        content: str,
        source: Optional[str] = None,
        confidence: float = 1.0,
        importance: float = 0.5,
    ) -> str:
        """Add a memory node (direct passthrough to matrix)."""
        if not self._matrix:
            raise RuntimeError("Matrix not initialized")
        return await self._matrix.add_node(
            node_type=node_type,
            content=content,
            source=source,
            confidence=confidence,
            importance=importance,
        )

    async def get_node(self, node_id: str):
        """Get a node by ID (direct passthrough to matrix)."""
        if not self._matrix:
            return None
        return await self._matrix.get_node(node_id)
