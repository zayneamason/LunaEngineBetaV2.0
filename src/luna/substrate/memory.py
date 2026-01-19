"""
Memory Matrix Operations Layer for Luna Engine
===============================================

High-level memory operations that wrap the database layer.
Provides CRUD for memory nodes, search, context retrieval,
and access tracking.

The Memory Matrix is Luna's soul - all knowledge lives here.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, Union
import json
import logging
import uuid

from .database import MemoryDatabase

logger = logging.getLogger(__name__)


# =============================================================================
# COLUMN MAPPINGS FOR ROW PARSING
# =============================================================================

# Column order for memory_nodes table (matches schema.sql)
MEMORY_NODE_COLUMNS = [
    "id", "node_type", "content", "summary", "source",
    "confidence", "importance", "access_count", "reinforcement_count",
    "lock_in", "lock_in_state", "last_accessed",
    "created_at", "updated_at", "metadata"
]

# Column order for conversation_turns table
TURN_COLUMNS = [
    "id", "session_id", "role", "content", "tokens", "created_at", "metadata"
]


def row_to_dict(row: tuple, columns: list[str]) -> dict:
    """Convert a database row tuple to a dictionary."""
    if row is None:
        return None
    return dict(zip(columns, row))


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class MemoryNode:
    """
    A node in the memory graph.

    Represents facts, decisions, problems, actions, and other typed knowledge.
    """
    id: str
    node_type: str  # FACT, DECISION, PROBLEM, ACTION, CONTEXT, etc.
    content: str
    summary: Optional[str] = None
    source: Optional[str] = None
    confidence: float = 1.0
    importance: float = 0.5
    access_count: int = 0
    reinforcement_count: int = 0
    lock_in: float = 0.15
    lock_in_state: str = "drifting"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()

    @classmethod
    def from_row(cls, row: Union[tuple, dict]) -> "MemoryNode":
        """Create MemoryNode from database row (tuple or dict)."""
        # Convert tuple to dict if needed
        if isinstance(row, tuple):
            row = row_to_dict(row, MEMORY_NODE_COLUMNS)

        if row is None:
            return None

        metadata = row.get("metadata")
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except (json.JSONDecodeError, TypeError):
                metadata = {}

        created_at = row.get("created_at")
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at)
            except ValueError:
                created_at = None

        updated_at = row.get("updated_at")
        if isinstance(updated_at, str):
            try:
                updated_at = datetime.fromisoformat(updated_at)
            except ValueError:
                updated_at = None

        return cls(
            id=row["id"],
            node_type=row["node_type"],
            content=row["content"],
            summary=row.get("summary"),
            source=row.get("source"),
            confidence=row.get("confidence") or 1.0,
            importance=row.get("importance") or 0.5,
            access_count=row.get("access_count") or 0,
            reinforcement_count=row.get("reinforcement_count") or 0,
            lock_in=row.get("lock_in") or 0.15,
            lock_in_state=row.get("lock_in_state") or "drifting",
            created_at=created_at,
            updated_at=updated_at,
            metadata=metadata or {},
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "node_type": self.node_type,
            "content": self.content,
            "summary": self.summary,
            "source": self.source,
            "confidence": self.confidence,
            "importance": self.importance,
            "access_count": self.access_count,
            "reinforcement_count": self.reinforcement_count,
            "lock_in": self.lock_in,
            "lock_in_state": self.lock_in_state,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "metadata": self.metadata,
        }


@dataclass
class Turn:
    """
    A single turn in a conversation.

    Represents one message exchange (user or assistant).
    """
    id: int
    session_id: str
    role: str  # user, assistant, system
    content: str
    tokens: Optional[int] = None
    created_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

    @classmethod
    def from_row(cls, row: Union[tuple, dict]) -> "Turn":
        """Create Turn from database row (tuple or dict)."""
        # Convert tuple to dict if needed
        if isinstance(row, tuple):
            row = row_to_dict(row, TURN_COLUMNS)

        if row is None:
            return None

        created_at = row.get("created_at")
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at)
            except ValueError:
                created_at = None

        return cls(
            id=row["id"],
            session_id=row["session_id"],
            role=row["role"],
            content=row["content"],
            tokens=row.get("tokens"),
            created_at=created_at,
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "role": self.role,
            "content": self.content,
            "tokens": self.tokens,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# =============================================================================
# MEMORY MATRIX
# =============================================================================

class MemoryMatrix:
    """
    High-level memory operations layer.

    Wraps the database with intuitive methods for:
    - Adding and retrieving memory nodes
    - Searching by text
    - Getting context for queries
    - Tracking access patterns
    - Managing conversation turns

    This is Luna's soul - all knowledge lives here.
    """

    def __init__(self, db: MemoryDatabase):
        """
        Initialize the Memory Matrix.

        Args:
            db: The underlying MemoryDatabase instance
        """
        self.db = db
        logger.info("MemoryMatrix initialized")

    # =========================================================================
    # NODE OPERATIONS
    # =========================================================================

    async def add_node(
        self,
        node_type: str,
        content: str,
        source: Optional[str] = None,
        metadata: Optional[dict] = None,
        summary: Optional[str] = None,
        confidence: float = 1.0,
        importance: float = 0.5,
    ) -> str:
        """
        Add a new memory node.

        Args:
            node_type: Type of node (FACT, DECISION, PROBLEM, ACTION, etc.)
            content: The actual content/information
            source: Where this came from (conversation, file, etc.)
            metadata: Optional extra data as dict
            summary: Optional short summary for display
            confidence: Confidence score 0-1 (default 1.0)
            importance: Importance score 0-1 (default 0.5)

        Returns:
            The ID of the created node
        """
        node_id = str(uuid.uuid4())[:12]
        now = datetime.now().isoformat()

        metadata_json = json.dumps(metadata) if metadata else None

        await self.db.execute(
            """
            INSERT INTO memory_nodes (
                id, node_type, content, summary, source,
                confidence, importance, access_count, reinforcement_count,
                lock_in, lock_in_state,
                created_at, updated_at, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 0.15, 'drifting', ?, ?, ?)
            """,
            [
                node_id, node_type, content, summary, source,
                confidence, importance, now, now, metadata_json
            ]
        )

        logger.debug(f"Added memory node: {node_id} ({node_type})")
        return node_id

    async def get_node(self, node_id: str) -> Optional[MemoryNode]:
        """
        Retrieve a memory node by ID.

        Args:
            node_id: The node's unique identifier

        Returns:
            MemoryNode if found, None otherwise
        """
        row = await self.db.fetchone(
            "SELECT * FROM memory_nodes WHERE id = ?",
            (node_id,)
        )

        if row is None:
            return None

        return MemoryNode.from_row(row)

    async def update_node(
        self,
        node_id: str,
        content: Optional[str] = None,
        summary: Optional[str] = None,
        confidence: Optional[float] = None,
        importance: Optional[float] = None,
        metadata: Optional[dict] = None,
    ) -> bool:
        """
        Update an existing memory node.

        Args:
            node_id: The node's unique identifier
            content: New content (if provided)
            summary: New summary (if provided)
            confidence: New confidence score (if provided)
            importance: New importance score (if provided)
            metadata: New metadata (if provided)

        Returns:
            True if node was updated, False if not found
        """
        updates = []
        params = []

        if content is not None:
            updates.append("content = ?")
            params.append(content)
        if summary is not None:
            updates.append("summary = ?")
            params.append(summary)
        if confidence is not None:
            updates.append("confidence = ?")
            params.append(confidence)
        if importance is not None:
            updates.append("importance = ?")
            params.append(importance)
        if metadata is not None:
            updates.append("metadata = ?")
            params.append(json.dumps(metadata))

        if not updates:
            return False

        updates.append("updated_at = ?")
        params.append(datetime.now().isoformat())
        params.append(node_id)

        result = await self.db.execute(
            f"UPDATE memory_nodes SET {', '.join(updates)} WHERE id = ?",
            params
        )

        return result.rowcount > 0

    async def delete_node(self, node_id: str) -> bool:
        """
        Delete a memory node.

        Args:
            node_id: The node's unique identifier

        Returns:
            True if node was deleted, False if not found
        """
        result = await self.db.execute(
            "DELETE FROM memory_nodes WHERE id = ?",
            (node_id,)
        )
        return result.rowcount > 0

    # =========================================================================
    # SEARCH OPERATIONS
    # =========================================================================

    async def search_nodes(
        self,
        query: str,
        node_type: Optional[str] = None,
        limit: int = 10,
    ) -> list[MemoryNode]:
        """
        Search memory nodes by text using LIKE query.

        Args:
            query: Search text (uses SQL LIKE with wildcards)
            node_type: Optional filter by node type
            limit: Maximum number of results (default 10)

        Returns:
            List of matching MemoryNodes, ordered by importance
        """
        search_pattern = f"%{query}%"

        if node_type:
            rows = await self.db.fetchall(
                """
                SELECT * FROM memory_nodes
                WHERE (content LIKE ? OR summary LIKE ?)
                  AND node_type = ?
                ORDER BY importance DESC, created_at DESC
                LIMIT ?
                """,
                (search_pattern, search_pattern, node_type, limit)
            )
        else:
            rows = await self.db.fetchall(
                """
                SELECT * FROM memory_nodes
                WHERE content LIKE ? OR summary LIKE ?
                ORDER BY importance DESC, created_at DESC
                LIMIT ?
                """,
                (search_pattern, search_pattern, limit)
            )

        return [MemoryNode.from_row(row) for row in rows]

    async def get_context(
        self,
        query: str,
        max_tokens: int = 2000,
        node_types: Optional[list[str]] = None,
    ) -> list[MemoryNode]:
        """
        Get relevant context for a query.

        Retrieves memories that might be relevant to the query,
        staying within the token budget. Uses simple text matching
        and importance weighting.

        Args:
            query: The query to find context for
            max_tokens: Maximum tokens worth of context (approximate)
            node_types: Optional list of node types to include

        Returns:
            List of relevant MemoryNodes within token budget
        """
        # Approximate tokens per character (rough estimate)
        chars_per_token = 4
        max_chars = max_tokens * chars_per_token

        search_pattern = f"%{query}%"

        # Build query based on filters
        if node_types:
            placeholders = ", ".join("?" * len(node_types))
            rows = await self.db.fetchall(
                f"""
                SELECT * FROM memory_nodes
                WHERE (content LIKE ? OR summary LIKE ?)
                  AND node_type IN ({placeholders})
                ORDER BY importance DESC, access_count DESC, created_at DESC
                LIMIT 50
                """,
                (search_pattern, search_pattern, *node_types)
            )
        else:
            rows = await self.db.fetchall(
                """
                SELECT * FROM memory_nodes
                WHERE content LIKE ? OR summary LIKE ?
                ORDER BY importance DESC, access_count DESC, created_at DESC
                LIMIT 50
                """,
                (search_pattern, search_pattern)
            )

        # Collect nodes within token budget
        results = []
        total_chars = 0

        for row in rows:
            node = MemoryNode.from_row(row)
            node_chars = len(node.content) + (len(node.summary) if node.summary else 0)

            if total_chars + node_chars > max_chars:
                break

            results.append(node)
            total_chars += node_chars

            # Record access
            await self.record_access(node.id)

        logger.debug(f"Retrieved {len(results)} nodes for context ({total_chars} chars)")
        return results

    async def get_nodes_by_type(
        self,
        node_type: str,
        limit: int = 100,
    ) -> list[MemoryNode]:
        """
        Get all nodes of a specific type.

        Args:
            node_type: The type to filter by
            limit: Maximum number of results

        Returns:
            List of MemoryNodes of the specified type
        """
        rows = await self.db.fetchall(
            """
            SELECT * FROM memory_nodes
            WHERE node_type = ?
            ORDER BY importance DESC, created_at DESC
            LIMIT ?
            """,
            (node_type, limit)
        )
        return [MemoryNode.from_row(row) for row in rows]

    async def get_recent_nodes(self, limit: int = 20) -> list[MemoryNode]:
        """
        Get the most recently created nodes.

        Args:
            limit: Maximum number of results

        Returns:
            List of recent MemoryNodes
        """
        rows = await self.db.fetchall(
            """
            SELECT * FROM memory_nodes
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,)
        )
        return [MemoryNode.from_row(row) for row in rows]

    # =========================================================================
    # CONVERSATION OPERATIONS
    # =========================================================================

    async def add_conversation_turn(
        self,
        session_id: str,
        role: str,
        content: str,
        tokens: Optional[int] = None,
    ) -> int:
        """
        Add a conversation turn to history.

        Args:
            session_id: The conversation session ID
            role: Who said this (user, assistant, system)
            content: The message content
            tokens: Optional token count

        Returns:
            The ID of the created turn
        """
        now = datetime.now().isoformat()

        result = await self.db.execute(
            """
            INSERT INTO conversation_turns (
                session_id, role, content, tokens, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, role, content, tokens, now)
        )

        turn_id = result.lastrowid
        logger.debug(f"Added conversation turn: {turn_id} ({role})")
        return turn_id

    async def get_recent_turns(
        self,
        session_id: str,
        limit: int = 10,
    ) -> list[Turn]:
        """
        Get recent conversation turns for a session.

        Args:
            session_id: The conversation session ID
            limit: Maximum number of turns (default 10)

        Returns:
            List of Turns in chronological order
        """
        rows = await self.db.fetchall(
            """
            SELECT * FROM conversation_turns
            WHERE session_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (session_id, limit)
        )

        # Reverse to get chronological order
        turns = [Turn.from_row(row) for row in rows]
        turns.reverse()
        return turns

    async def get_session_history(self, session_id: str) -> list[Turn]:
        """
        Get full conversation history for a session.

        Args:
            session_id: The conversation session ID

        Returns:
            List of all Turns in chronological order
        """
        rows = await self.db.fetchall(
            """
            SELECT * FROM conversation_turns
            WHERE session_id = ?
            ORDER BY created_at ASC
            """,
            (session_id,)
        )
        return [Turn.from_row(row) for row in rows]

    # =========================================================================
    # ACCESS TRACKING
    # =========================================================================

    async def record_access(self, node_id: str) -> None:
        """
        Record that a node was accessed.

        Increments access_count, updates last_accessed timestamp,
        and recalculates lock-in coefficient.

        Args:
            node_id: The node's unique identifier
        """
        from .lock_in import compute_lock_in, classify_state

        # First increment access count
        await self.db.execute(
            """
            UPDATE memory_nodes
            SET access_count = access_count + 1,
                last_accessed = datetime('now')
            WHERE id = ?
            """,
            (node_id,)
        )

        # Get updated counts for lock-in calculation
        row = await self.db.fetchone(
            "SELECT access_count, reinforcement_count FROM memory_nodes WHERE id = ?",
            (node_id,)
        )

        if row:
            access_count, reinforcement_count = row
            # TODO: Add network effects (locked neighbors) when graph is wired
            lock_in = compute_lock_in(
                retrieval_count=access_count,
                reinforcement_count=reinforcement_count,
                locked_neighbor_count=0,
                locked_tag_sibling_count=0,
            )
            state = classify_state(lock_in)

            await self.db.execute(
                "UPDATE memory_nodes SET lock_in = ?, lock_in_state = ? WHERE id = ?",
                (lock_in, state.value, node_id)
            )

    async def get_most_accessed(self, limit: int = 10) -> list[MemoryNode]:
        """
        Get the most frequently accessed nodes.

        Args:
            limit: Maximum number of results

        Returns:
            List of most accessed MemoryNodes
        """
        rows = await self.db.fetchall(
            """
            SELECT * FROM memory_nodes
            ORDER BY access_count DESC
            LIMIT ?
            """,
            (limit,)
        )
        return [MemoryNode.from_row(row) for row in rows]

    async def reinforce_node(self, node_id: str) -> bool:
        """
        Explicitly reinforce a memory node.

        This is for user-initiated reinforcement ("this is important").
        Increments reinforcement_count and recalculates lock-in.

        Args:
            node_id: The node's unique identifier

        Returns:
            True if node was reinforced, False if not found
        """
        from .lock_in import compute_lock_in, classify_state

        # Increment reinforcement count
        result = await self.db.execute(
            "UPDATE memory_nodes SET reinforcement_count = reinforcement_count + 1 WHERE id = ?",
            (node_id,)
        )

        if result.rowcount == 0:
            return False

        # Get updated counts for lock-in calculation
        row = await self.db.fetchone(
            "SELECT access_count, reinforcement_count FROM memory_nodes WHERE id = ?",
            (node_id,)
        )

        if row:
            access_count, reinforcement_count = row
            lock_in = compute_lock_in(
                retrieval_count=access_count,
                reinforcement_count=reinforcement_count,
                locked_neighbor_count=0,
                locked_tag_sibling_count=0,
            )
            state = classify_state(lock_in)

            await self.db.execute(
                "UPDATE memory_nodes SET lock_in = ?, lock_in_state = ? WHERE id = ?",
                (lock_in, state.value, node_id)
            )

        logger.debug(f"Reinforced memory node: {node_id}")
        return True

    async def get_nodes_by_lock_in_state(
        self,
        state: str,
        limit: int = 100,
    ) -> list[MemoryNode]:
        """
        Get nodes filtered by lock-in state.

        Args:
            state: 'drifting', 'fluid', or 'settled'
            limit: Maximum number of results

        Returns:
            List of MemoryNodes in that state
        """
        rows = await self.db.fetchall(
            """
            SELECT * FROM memory_nodes
            WHERE lock_in_state = ?
            ORDER BY lock_in DESC
            LIMIT ?
            """,
            (state, limit)
        )
        return [MemoryNode.from_row(row) for row in rows]

    async def get_drifting_nodes(self, limit: int = 100) -> list[MemoryNode]:
        """Get nodes that are drifting (candidates for pruning)."""
        return await self.get_nodes_by_lock_in_state("drifting", limit)

    async def get_settled_nodes(self, limit: int = 100) -> list[MemoryNode]:
        """Get nodes that are settled (core knowledge)."""
        return await self.get_nodes_by_lock_in_state("settled", limit)

    # =========================================================================
    # STATISTICS
    # =========================================================================

    async def get_stats(self) -> dict:
        """
        Get statistics about the memory matrix.

        Returns:
            Dictionary with stats including:
            - total_nodes: Total number of memory nodes
            - nodes_by_type: Count of nodes per type
            - total_turns: Total conversation turns
            - total_sessions: Unique session count
            - avg_confidence: Average confidence score
            - avg_importance: Average importance score
        """
        # Total nodes
        total_row = await self.db.fetchone(
            "SELECT COUNT(*) FROM memory_nodes"
        )
        total_nodes = total_row[0] if total_row else 0

        # Nodes by type
        type_rows = await self.db.fetchall(
            """
            SELECT node_type, COUNT(*)
            FROM memory_nodes
            GROUP BY node_type
            """
        )
        nodes_by_type = {row[0]: row[1] for row in type_rows}

        # Total turns
        turns_row = await self.db.fetchone(
            "SELECT COUNT(*) FROM conversation_turns"
        )
        total_turns = turns_row[0] if turns_row else 0

        # Unique sessions
        sessions_row = await self.db.fetchone(
            "SELECT COUNT(DISTINCT session_id) FROM conversation_turns"
        )
        total_sessions = sessions_row[0] if sessions_row else 0

        # Average scores
        averages_row = await self.db.fetchone(
            """
            SELECT
                AVG(confidence),
                AVG(importance),
                AVG(access_count)
            FROM memory_nodes
            """
        )

        avg_confidence = averages_row[0] if averages_row and averages_row[0] else 0.0
        avg_importance = averages_row[1] if averages_row and averages_row[1] else 0.0
        avg_access_count = averages_row[2] if averages_row and averages_row[2] else 0.0

        # Lock-in state distribution
        lock_in_rows = await self.db.fetchall(
            """
            SELECT lock_in_state, COUNT(*)
            FROM memory_nodes
            GROUP BY lock_in_state
            """
        )
        nodes_by_lock_in = {row[0]: row[1] for row in lock_in_rows}

        # Average lock-in
        avg_lock_in_row = await self.db.fetchone(
            "SELECT AVG(lock_in) FROM memory_nodes"
        )
        avg_lock_in = avg_lock_in_row[0] if avg_lock_in_row and avg_lock_in_row[0] else 0.15

        return {
            "total_nodes": total_nodes,
            "nodes_by_type": nodes_by_type,
            "nodes_by_lock_in": nodes_by_lock_in,
            "total_turns": total_turns,
            "total_sessions": total_sessions,
            "avg_confidence": avg_confidence,
            "avg_importance": avg_importance,
            "avg_access_count": avg_access_count,
            "avg_lock_in": avg_lock_in,
        }

    # =========================================================================
    # LIFECYCLE
    # =========================================================================

    async def close(self) -> None:
        """Close the underlying database connection."""
        await self.db.close()
        logger.info("MemoryMatrix closed")
