"""
Matrix Actor - Memory Substrate Interface (Eclissi Integration)
================================================================

The Matrix is Luna's long-term memory - her soul lives here.

Now powered by Eclissi's advanced memory system:
- 53,438 memory nodes with typed relationships
- Hybrid search (FAISS + FTS5 + Graph)
- Lock-in coefficient for memory persistence
- NetworkX graph for relationship traversal
- smart_fetch() for budget-aware context retrieval

The engine queries the Matrix directly for context before generation.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional, List
import time

from luna.actors.base import Actor

# Eclissi's advanced memory matrix (linked from Eclissi project)
import sys
sys.path.insert(0, '/Users/zayneamason/_HeyLuna_BETA/_Eclessi_BetaProject_Root/src')

try:
    from memory_matrix import MemoryMatrix as EclissiMemoryMatrix
    from memory_matrix import MemoryNode, MemoryEdge, ContextPacket
    ECLISSI_AVAILABLE = True
except ImportError:
    ECLISSI_AVAILABLE = False

# Fallback to basic Luna substrate if Eclissi not available
from luna.substrate import MemoryDatabase, MemoryMatrix as BasicMemoryMatrix, MemoryGraph

logger = logging.getLogger(__name__)

# Default Eclissi database path (190MB with 53k nodes)
ECLISSI_DB_PATH = Path("/Users/zayneamason/_HeyLuna_BETA/_Eclessi_BetaProject_Root/data/memory/matrix/memory_matrix.db")


class MatrixActor(Actor):
    """
    Memory substrate actor - now powered by Eclissi.

    Manages Luna's long-term memory through:
    - Eclissi's advanced MemoryMatrix (53k nodes, hybrid search)
    - SQLite + NetworkX for graph operations
    - FAISS for semantic search
    - FTS5 for keyword matching
    - Lock-in coefficient for memory persistence
    """

    def __init__(self, db_path: Optional[Path] = None, use_eclissi: bool = True):
        """
        Initialize the Matrix actor.

        Args:
            db_path: Optional path to SQLite database.
                     Defaults to Eclissi's database if use_eclissi=True
            use_eclissi: If True, use Eclissi's advanced memory system
        """
        super().__init__(name="matrix")

        # Determine database path
        if db_path:
            self.db_path = db_path
        elif use_eclissi and ECLISSI_AVAILABLE and ECLISSI_DB_PATH.exists():
            self.db_path = ECLISSI_DB_PATH
        else:
            self.db_path = Path.home() / ".luna" / "luna.db"

        self._use_eclissi = use_eclissi and ECLISSI_AVAILABLE

        # Eclissi matrix (synchronous)
        self._eclissi_matrix: Optional[EclissiMemoryMatrix] = None

        # Basic Luna substrate (async fallback)
        self._db: Optional[MemoryDatabase] = None
        self._matrix: Optional[BasicMemoryMatrix] = None
        self._graph: Optional[MemoryGraph] = None

        self._initialized = False

    @property
    def matrix(self):
        """Access the memory matrix (Eclissi or basic)."""
        return self._eclissi_matrix or self._matrix

    @property
    def graph(self):
        """Access the NetworkX graph."""
        if self._eclissi_matrix:
            return self._eclissi_matrix.graph
        return self._graph

    @property
    def is_ready(self) -> bool:
        """Check if the matrix is initialized."""
        return self._initialized

    async def initialize(self) -> None:
        """Initialize database and load graph (without starting mailbox loop)."""
        if self._initialized:
            return

        logger.info(f"Matrix actor starting with db: {self.db_path}")

        if self._use_eclissi and ECLISSI_AVAILABLE:
            await self._init_eclissi()
        else:
            await self._init_basic()

        self._initialized = True
        logger.info(f"Matrix actor ready (Eclissi: {self._use_eclissi})")

    async def _init_eclissi(self) -> None:
        """Initialize Eclissi's advanced memory system."""
        loop = asyncio.get_event_loop()

        # Eclissi's MemoryMatrix is synchronous, run in executor
        # FAISS disabled - using FTS5 + Graph (sqlite-vec coming soon)
        # auto_init=False because the Eclissi DB already exists with valid schema
        self._eclissi_matrix = await loop.run_in_executor(
            None,
            lambda: EclissiMemoryMatrix(
                str(self.db_path),
                auto_init=False,  # DB already initialized with 53k+ nodes
                load_graph=True,
                enable_faiss=False  # Using FTS5 + Graph, not FAISS
            )
        )

        # Log stats
        if self._eclissi_matrix.graph:
            node_count = self._eclissi_matrix.graph.number_of_nodes()
            edge_count = self._eclissi_matrix.graph.number_of_edges()
            logger.info(f"Eclissi graph loaded: {node_count} nodes, {edge_count} edges")

        if self._eclissi_matrix._faiss_enabled:
            logger.info("FAISS hybrid search enabled")

    async def _init_basic(self) -> None:
        """Initialize basic Luna substrate (fallback)."""
        self._db = MemoryDatabase(self.db_path)
        await self._db.connect()
        self._matrix = BasicMemoryMatrix(self._db)
        self._graph = MemoryGraph(self._db)
        await self._graph.load_from_db()
        logger.info("Basic memory substrate initialized")

    async def start(self) -> None:
        """Start the actor's mailbox processing loop."""
        if not self._initialized:
            await self.initialize()
        await super().start()

    async def stop(self) -> None:
        """Close database connection."""
        await super().stop()

        if self._eclissi_matrix:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._eclissi_matrix.close)
            self._eclissi_matrix = None

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
        - smart_fetch: Use Eclissi's advanced retrieval
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

        elif msg.type == "retrieve" or msg.type == "smart_fetch":
            ctx = await self.get_context(
                query=payload.get("query", ""),
                budget_preset=payload.get("budget_preset", "balanced"),
            )
            logger.debug(f"Retrieved context: {len(ctx)} chars")

        elif msg.type == "search":
            results = await self.search(
                query=payload.get("query", ""),
                limit=payload.get("limit", 10),
            )
            logger.debug(f"Search found {len(results)} nodes")

    # =========================================================================
    # Core Memory Operations (Eclissi-powered)
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
            tags: Optional semantic tags
            confidence: Confidence level 0-100
            session_id: Optional session ID

        Returns:
            The node ID
        """
        if not self._initialized:
            raise RuntimeError("Matrix not initialized")

        if self._eclissi_matrix:
            loop = asyncio.get_event_loop()
            node = MemoryNode(
                type=node_type,
                content=content,
                timestamp=int(time.time()),
                tags=tags or [],
                confidence=confidence,
                session_id=session_id,
                status="ACTIVE",
            )
            return await loop.run_in_executor(
                None,
                self._eclissi_matrix.add_node,
                node
            )
        else:
            return await self._matrix.add_node(
                node_type=node_type,
                content=content,
                importance=confidence / 100.0,
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
        # Store conversation turns as FACT nodes in Eclissi
        return await self.store_memory(
            content=f"[{role}] {content}",
            node_type="FACT",
            tags=["conversation", role, session_id],
            confidence=100,
            session_id=session_id,
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
        budget_preset: str = "balanced",
        max_tokens: int = 3800,
    ) -> str:
        """
        Get relevant context for a query using Eclissi's smart_fetch.

        Budget presets:
        - "minimal": ~1800 tokens, depth 1, 3 results
        - "balanced": ~3800 tokens, depth 2, 5 results
        - "rich": ~7200 tokens, depth 3, 8 results

        Args:
            query: The query to find context for
            budget_preset: Token budget preset
            max_tokens: Fallback max tokens for basic mode

        Returns:
            Formatted context string
        """
        if not self._initialized:
            return ""

        if self._eclissi_matrix:
            loop = asyncio.get_event_loop()

            # Use Eclissi's smart_fetch with hybrid search
            context_packet: ContextPacket = await loop.run_in_executor(
                None,
                lambda: self._eclissi_matrix.smart_fetch(
                    query=query,
                    budget_preset=budget_preset,
                    show_hierarchy=True,
                    use_hybrid=True,
                )
            )

            if not context_packet.nodes:
                return ""

            # Format as markdown for Luna
            return self._format_context_packet(context_packet)
        else:
            # Fallback to basic search
            return await self._basic_get_context(query, max_tokens)

    def _format_context_packet(self, packet: ContextPacket) -> str:
        """Format Eclissi ContextPacket as markdown for Luna."""
        parts = []

        # Group nodes by type
        by_type = {}
        for node in packet.nodes:
            node_type = node.type
            if node_type not in by_type:
                by_type[node_type] = []
            by_type[node_type].append(node)

        # Format each type group
        type_order = ["FACT", "DECISION", "PROBLEM", "ACTION", "OUTCOME", "ASSUMPTION", "PARENT"]
        for node_type in type_order:
            if node_type in by_type:
                nodes = by_type[node_type]
                section = f"## {node_type}s\n"
                for node in nodes[:10]:  # Limit per type
                    # Show lock-in state if settled
                    lock_state = getattr(node, 'lock_in_state', 'fluid')
                    lock_indicator = " 🔒" if lock_state == "settled" else ""
                    section += f"- {node.content[:500]}{lock_indicator}\n"
                parts.append(section)

        # Add remaining types
        for node_type, nodes in by_type.items():
            if node_type not in type_order:
                section = f"## {node_type}s\n"
                for node in nodes[:5]:
                    section += f"- {node.content[:500]}\n"
                parts.append(section)

        result = "\n".join(parts)
        logger.debug(f"Context packet: {len(packet.nodes)} nodes, {packet.budget_used} tokens used")
        return result

    async def _basic_get_context(self, query: str, max_tokens: int) -> str:
        """Fallback context retrieval for basic mode."""
        parts = []
        chars_used = 0
        max_chars = max_tokens * 4

        # Get memory nodes
        nodes = await self._matrix.get_context(query, max_tokens=max_tokens)
        if nodes:
            node_parts = []
            for node in nodes:
                node_text = f"[{node.node_type}] {node.content}"
                if chars_used + len(node_text) > max_chars:
                    break
                node_parts.append(node_text)
                chars_used += len(node_text)
            if node_parts:
                parts.append("## Relevant Memories\n" + "\n\n".join(node_parts))

        return "\n\n".join(parts)

    async def search(
        self,
        query: str,
        limit: int = 10,
        use_hybrid: bool = True,
    ) -> list:
        """
        Search for memory nodes.

        Args:
            query: Search text
            limit: Max results
            use_hybrid: Use hybrid search if available

        Returns:
            List of matching nodes
        """
        if not self._initialized:
            return []

        if self._eclissi_matrix:
            loop = asyncio.get_event_loop()

            if use_hybrid and self._eclissi_matrix._faiss_enabled:
                # Hybrid search (FAISS + FTS5 + Graph)
                results = await loop.run_in_executor(
                    None,
                    lambda: self._eclissi_matrix.hybrid_search(query, k=limit)
                )
                # Get full node data
                nodes = []
                for node_id, score, sources in results:
                    node = await loop.run_in_executor(
                        None,
                        self._eclissi_matrix.get_node,
                        node_id
                    )
                    if node:
                        nodes.append(node)
                return nodes
            else:
                # FTS5 only
                results = await loop.run_in_executor(
                    None,
                    lambda: self._eclissi_matrix.semantic_search(query, limit=limit)
                )
                nodes = []
                for node_id, rank in results:
                    node = await loop.run_in_executor(
                        None,
                        self._eclissi_matrix.get_node,
                        node_id
                    )
                    if node:
                        nodes.append(node)
                return nodes
        else:
            return await self._matrix.search_nodes(query=query, limit=limit)

    async def get_stats(self) -> dict:
        """Get memory statistics."""
        if not self._initialized:
            return {"initialized": False}

        if self._eclissi_matrix:
            loop = asyncio.get_event_loop()

            # Count nodes by type
            cursor = self._eclissi_matrix.conn.execute("""
                SELECT type, COUNT(*) FROM memory_nodes
                WHERE status = 'ACTIVE'
                GROUP BY type
            """)
            nodes_by_type = {row[0]: row[1] for row in cursor.fetchall()}

            # Get graph stats
            graph_stats = {}
            if self._eclissi_matrix.graph:
                graph_stats = {
                    "nodes": self._eclissi_matrix.graph.number_of_nodes(),
                    "edges": self._eclissi_matrix.graph.number_of_edges(),
                }

            # Get lock-in stats
            lock_in_stats = await loop.run_in_executor(
                None,
                self._eclissi_matrix.get_lock_in_stats
            )

            # Get FAISS stats
            faiss_stats = self._eclissi_matrix.get_faiss_stats()

            return {
                "backend": "eclissi",
                "db_path": str(self.db_path),
                "nodes_by_type": nodes_by_type,
                "total_nodes": sum(nodes_by_type.values()),
                "graph": graph_stats,
                "lock_in": lock_in_stats,
                "faiss": faiss_stats,
            }
        else:
            matrix_stats = await self._matrix.get_stats()
            graph_stats = await self._graph.get_stats()
            return {
                "backend": "basic",
                **matrix_stats,
                "graph": graph_stats,
            }

    # =========================================================================
    # Advanced Eclissi Operations
    # =========================================================================

    async def reinforce_memory(self, node_id: str, amount: int = 1) -> None:
        """
        Reinforce a memory (increases lock-in coefficient).

        Args:
            node_id: Node to reinforce
            amount: Reinforcement amount
        """
        if not self._eclissi_matrix:
            return

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self._eclissi_matrix.on_reinforce(node_id, amount)
        )
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
        if not self._eclissi_matrix:
            return []

        loop = asyncio.get_event_loop()
        context_ids = await loop.run_in_executor(
            None,
            lambda: self._eclissi_matrix.get_context([node_id], depth=depth)
        )
        return list(context_ids)

    async def get_central_concepts(self, limit: int = 10) -> list:
        """
        Get most central/influential memory nodes (PageRank).

        Returns:
            List of (node_id, score) tuples
        """
        if not self._eclissi_matrix:
            return []

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self._eclissi_matrix.get_central_nodes(limit=limit)
        )
