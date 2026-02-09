"""
Memory Graph for Luna Engine
============================

NetworkX graph layer for Luna's Memory Matrix.

The graph maintains relationships between memory nodes:
- In-memory graph (NetworkX DiGraph) for fast traversal
- SQLite database for persistence
- Spreading activation for relevance calculation

Relationship types:
- DEPENDS_ON: Node A requires Node B
- RELATES_TO: General semantic relationship
- CAUSED_BY: Node A was caused by Node B
- FOLLOWED_BY: Temporal sequence
- CONTRADICTS: Node A contradicts Node B
- SUPPORTS: Node A provides evidence for Node B
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional, Protocol
import logging

import networkx as nx

if TYPE_CHECKING:
    from .database import MemoryDatabase

logger = logging.getLogger(__name__)


class RelationshipType(str, Enum):
    """Types of relationships between memory nodes."""
    DEPENDS_ON = "DEPENDS_ON"
    RELATES_TO = "RELATES_TO"
    CAUSED_BY = "CAUSED_BY"
    FOLLOWED_BY = "FOLLOWED_BY"
    CONTRADICTS = "CONTRADICTS"
    SUPPORTS = "SUPPORTS"


@dataclass
class Edge:
    """
    An edge in the memory graph.

    Represents a directed relationship between two memory nodes.
    """
    from_id: str
    to_id: str
    relationship: str
    strength: float = 1.0
    created_at: datetime = field(default_factory=datetime.now)

    def __repr__(self) -> str:
        return f"Edge({self.from_id} --{self.relationship}[{self.strength:.2f}]--> {self.to_id})"


class DatabaseProtocol(Protocol):
    """Protocol defining the interface MemoryDatabase must implement for graph operations."""

    async def execute(self, query: str, params: tuple = ()) -> None:
        """Execute a write query."""
        ...

    async def fetch_all(self, query: str, params: tuple = ()) -> list[dict]:
        """Fetch all rows from a query."""
        ...

    async def fetch_one(self, query: str, params: tuple = ()) -> Optional[dict]:
        """Fetch a single row from a query."""
        ...


class MemoryGraph:
    """
    In-memory graph backed by SQLite for persistence.

    Uses NetworkX DiGraph for fast traversal operations:
    - O(1) neighbor lookup
    - O(V+E) shortest path
    - Spreading activation for relevance

    All mutations update both the in-memory graph and the database.
    """

    def __init__(self, db: "MemoryDatabase"):
        """
        Initialize the memory graph.

        Args:
            db: MemoryDatabase instance for persistence
        """
        self.db = db
        self._graph: nx.DiGraph = nx.DiGraph()
        self._loaded = False

    @property
    def graph(self) -> nx.DiGraph:
        """Access the underlying NetworkX graph."""
        return self._graph

    # =========================================================================
    # Initialization
    # =========================================================================

    async def load_from_db(self) -> None:
        """
        Load all edges from database into the NetworkX graph.

        Should be called once at startup after database is initialized.
        """
        if self._loaded:
            logger.warning("Graph already loaded from database")
            return

        logger.info("Loading graph edges from database...")

        query = """
            SELECT from_id, to_id, relationship, strength, created_at
            FROM graph_edges
        """

        rows = await self.db.fetchall(query)

        for row in rows:
            # Row is a tuple: (from_id, to_id, relationship, strength, created_at)
            from_id, to_id, relationship, strength, created_at = row
            self._graph.add_edge(
                from_id,
                to_id,
                relationship=relationship,
                strength=strength,
                created_at=created_at,
            )

        self._loaded = True
        logger.info(f"Loaded {len(rows)} edges into memory graph")

    # =========================================================================
    # Edge Operations
    # =========================================================================

    async def add_edge(
        self,
        from_id: str,
        to_id: str,
        relationship: str,
        strength: float = 1.0,
    ) -> Edge:
        """
        Add an edge between two nodes.

        Updates both the in-memory graph and the database.
        If edge already exists, updates the strength.

        Args:
            from_id: Source node ID
            to_id: Target node ID
            relationship: Type of relationship (use RelationshipType)
            strength: Edge weight 0-1 (default 1.0)

        Returns:
            The created or updated Edge
        """
        # Clamp strength to valid range
        strength = max(0.0, min(1.0, strength))
        created_at = datetime.now()

        # Add to NetworkX graph
        self._graph.add_edge(
            from_id,
            to_id,
            relationship=relationship,
            strength=strength,
            created_at=created_at.isoformat(),
        )

        # Persist to database (upsert)
        query = """
            INSERT INTO graph_edges (from_id, to_id, relationship, strength, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(from_id, to_id, relationship)
            DO UPDATE SET strength = excluded.strength
        """
        await self.db.execute(query, (from_id, to_id, relationship, strength, created_at.isoformat()))

        logger.info(
            f"GRAPH_EDGE_ADDED: {from_id} --{relationship}[{strength:.2f}]--> {to_id} | "
            f"total_edges={self._graph.number_of_edges()}"
        )

        return Edge(
            from_id=from_id,
            to_id=to_id,
            relationship=relationship,
            strength=strength,
            created_at=created_at,
        )

    async def remove_edge(
        self,
        from_id: str,
        to_id: str,
        relationship: Optional[str] = None,
    ) -> bool:
        """
        Remove an edge between two nodes.

        Args:
            from_id: Source node ID
            to_id: Target node ID
            relationship: Optional - if provided, only remove edge with this relationship

        Returns:
            True if edge was removed, False if it didn't exist
        """
        # Check if edge exists
        if not self._graph.has_edge(from_id, to_id):
            return False

        if relationship:
            # Only remove if relationship matches
            edge_data = self._graph.get_edge_data(from_id, to_id)
            if edge_data and edge_data.get("relationship") != relationship:
                return False

            query = """
                DELETE FROM graph_edges
                WHERE from_id = ? AND to_id = ? AND relationship = ?
            """
            await self.db.execute(query, (from_id, to_id, relationship))
        else:
            query = """
                DELETE FROM graph_edges
                WHERE from_id = ? AND to_id = ?
            """
            await self.db.execute(query, (from_id, to_id))

        # Remove from NetworkX
        self._graph.remove_edge(from_id, to_id)

        logger.debug(f"Removed edge: {from_id} --> {to_id}")
        return True

    async def get_edges(self, node_id: str) -> list[Edge]:
        """
        Get all edges connected to a node (both incoming and outgoing).

        Args:
            node_id: The node to get edges for

        Returns:
            List of Edge objects
        """
        edges: list[Edge] = []

        # Outgoing edges
        for _, to_id, data in self._graph.out_edges(node_id, data=True):
            edges.append(Edge(
                from_id=node_id,
                to_id=to_id,
                relationship=data.get("relationship", "RELATES_TO"),
                strength=data.get("strength", 1.0),
                created_at=datetime.fromisoformat(data["created_at"]) if isinstance(data.get("created_at"), str) else data.get("created_at", datetime.now()),
            ))

        # Incoming edges
        for from_id, _, data in self._graph.in_edges(node_id, data=True):
            edges.append(Edge(
                from_id=from_id,
                to_id=node_id,
                relationship=data.get("relationship", "RELATES_TO"),
                strength=data.get("strength", 1.0),
                created_at=datetime.fromisoformat(data["created_at"]) if isinstance(data.get("created_at"), str) else data.get("created_at", datetime.now()),
            ))

        return edges

    # =========================================================================
    # Graph Traversal
    # =========================================================================

    async def get_neighbors(self, node_id: str, depth: int = 1) -> list[str]:
        """
        Get all nodes within N hops of a starting node.

        Uses BFS to find all reachable nodes up to the specified depth.

        Args:
            node_id: Starting node ID
            depth: Maximum number of hops (default 1)

        Returns:
            List of node IDs (excluding the starting node)
        """
        if node_id not in self._graph:
            return []

        if depth < 1:
            return []

        neighbors: set[str] = set()
        current_layer = {node_id}

        for _ in range(depth):
            next_layer: set[str] = set()
            for n in current_layer:
                # Both successors and predecessors (undirected traversal)
                next_layer.update(self._graph.successors(n))
                next_layer.update(self._graph.predecessors(n))

            # Remove already seen nodes
            next_layer -= neighbors
            next_layer.discard(node_id)  # Don't include start node

            neighbors.update(next_layer)
            current_layer = next_layer

            if not current_layer:
                break

        return list(neighbors)

    async def get_related_nodes(
        self,
        node_id: str,
        relationship: Optional[str] = None,
    ) -> list[str]:
        """
        Get nodes related to a node by a specific relationship.

        Args:
            node_id: Starting node ID
            relationship: Optional filter by relationship type

        Returns:
            List of related node IDs
        """
        if node_id not in self._graph:
            return []

        related: list[str] = []

        # Check outgoing edges
        for _, to_id, data in self._graph.out_edges(node_id, data=True):
            if relationship is None or data.get("relationship") == relationship:
                related.append(to_id)

        # Check incoming edges
        for from_id, _, data in self._graph.in_edges(node_id, data=True):
            if relationship is None or data.get("relationship") == relationship:
                if from_id not in related:  # Avoid duplicates
                    related.append(from_id)

        return related

    # =========================================================================
    # Spreading Activation
    # =========================================================================

    async def spreading_activation(
        self,
        start_nodes: list[str],
        decay: float = 0.5,
        max_depth: int = 3,
    ) -> dict[str, float]:
        """
        Calculate relevance scores using spreading activation.

        Starting from seed nodes with activation 1.0, spread activation
        through the graph with decay at each hop. Edge strength weights
        the activation transfer.

        This is how Luna expands context - start from current topics
        and find semantically related memories.

        Args:
            start_nodes: List of node IDs to start activation from
            decay: Decay factor per hop (0-1, default 0.5)
            max_depth: Maximum hops to propagate (default 3)

        Returns:
            Dict mapping node_id -> activation score (0-1)
        """
        # Initialize activations
        activations: dict[str, float] = {}

        # Start nodes get full activation
        for node_id in start_nodes:
            if node_id in self._graph:
                activations[node_id] = 1.0

        if not activations:
            return {}

        # Spread activation through graph
        current_layer = set(start_nodes)

        for depth in range(max_depth):
            next_layer: set[str] = set()
            current_decay = decay ** (depth + 1)

            for node_id in current_layer:
                if node_id not in self._graph:
                    continue

                node_activation = activations.get(node_id, 0)

                # Spread to successors
                for _, neighbor, data in self._graph.out_edges(node_id, data=True):
                    edge_strength = data.get("strength", 1.0)
                    spread = node_activation * current_decay * edge_strength

                    # Accumulate activation (nodes can receive from multiple sources)
                    current = activations.get(neighbor, 0)
                    activations[neighbor] = min(1.0, current + spread)
                    next_layer.add(neighbor)

                # Spread to predecessors (bidirectional activation)
                for neighbor, _, data in self._graph.in_edges(node_id, data=True):
                    edge_strength = data.get("strength", 1.0)
                    spread = node_activation * current_decay * edge_strength

                    current = activations.get(neighbor, 0)
                    activations[neighbor] = min(1.0, current + spread)
                    next_layer.add(neighbor)

            # Remove already visited from next layer
            next_layer -= current_layer
            current_layer = next_layer

            if not current_layer:
                break

        return activations

    # =========================================================================
    # Statistics
    # =========================================================================

    async def get_stats(self) -> dict:
        """
        Get statistics about the memory graph.

        Returns:
            Dict with node_count, edge_count, relationship breakdown, etc.
        """
        # Count relationships
        relationship_counts: dict[str, int] = {}
        for _, _, data in self._graph.edges(data=True):
            rel = data.get("relationship", "UNKNOWN")
            relationship_counts[rel] = relationship_counts.get(rel, 0) + 1

        # Calculate average degree
        degrees = [d for _, d in self._graph.degree()]
        avg_degree = sum(degrees) / len(degrees) if degrees else 0

        # Find most connected nodes
        sorted_by_degree = sorted(
            self._graph.degree(),
            key=lambda x: x[1],
            reverse=True
        )[:5]

        return {
            "node_count": self._graph.number_of_nodes(),
            "edge_count": self._graph.number_of_edges(),
            "relationship_counts": relationship_counts,
            "average_degree": round(avg_degree, 2),
            "most_connected": [
                {"node_id": node, "degree": degree}
                for node, degree in sorted_by_degree
            ],
            "is_connected": nx.is_weakly_connected(self._graph) if self._graph.number_of_nodes() > 0 else True,
            "loaded": self._loaded,
        }

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def has_node(self, node_id: str) -> bool:
        """Check if a node exists in the graph."""
        return node_id in self._graph

    def has_edge(self, from_id: str, to_id: str) -> bool:
        """Check if an edge exists between two nodes."""
        return self._graph.has_edge(from_id, to_id)

    async def clear(self) -> None:
        """
        Clear all edges from the graph.

        WARNING: This also clears the database table.
        """
        self._graph.clear()
        await self.db.execute("DELETE FROM graph_edges")
        logger.warning("Memory graph cleared")

    def __repr__(self) -> str:
        return f"MemoryGraph(nodes={self._graph.number_of_nodes()}, edges={self._graph.number_of_edges()})"
