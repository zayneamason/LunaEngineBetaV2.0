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
from .embeddings import EmbeddingStore, EmbeddingGenerator

logger = logging.getLogger(__name__)

# Lazy-loaded entity resolver for mention detection
_entity_resolver = None


# =============================================================================
# COLUMN MAPPINGS FOR ROW PARSING
# =============================================================================

# Column order for memory_nodes table (matches schema.sql)
MEMORY_NODE_COLUMNS = [
    "id", "node_type", "content", "summary", "source",
    "confidence", "importance", "access_count", "reinforcement_count",
    "lock_in", "lock_in_state", "last_accessed",
    "created_at", "updated_at", "metadata", "scope"
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
    scope: str = "global"

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
            scope=row.get("scope") or "global",
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
            "scope": self.scope,
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

    def __init__(self, db: MemoryDatabase, enable_embeddings: bool = True):
        """
        Initialize the Memory Matrix.

        Args:
            db: The underlying MemoryDatabase instance
            enable_embeddings: Whether to auto-generate embeddings on add_node (default True)
        """
        self.db = db
        self.graph: Optional["MemoryGraph"] = None  # Set by MatrixActor after init
        self._enable_embeddings = enable_embeddings
        self._embedding_store: Optional[EmbeddingStore] = None
        self._embedding_generator: Optional[EmbeddingGenerator] = None
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
        link_entities: bool = True,
        scope: str = "global",
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
            link_entities: Whether to detect and link mentioned entities (default True)
            scope: Memory scope - 'global' or 'project:{slug}'

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
                created_at, updated_at, metadata, scope
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 0.15, 'drifting', ?, ?, ?, ?)
            """,
            [
                node_id, node_type, content, summary, source,
                confidence, importance, now, now, metadata_json, scope
            ]
        )

        logger.debug(f"Added memory node: {node_id} ({node_type})")

        # Detect and link entity mentions
        if link_entities:
            await self._link_entity_mentions(node_id, content)

        # Generate and store embedding
        if self._enable_embeddings:
            await self._store_embedding(node_id, content, summary)

        return node_id

    async def _ensure_embedding_components(self) -> bool:
        """
        Ensure embedding store and generator are initialized.

        Returns:
            True if embeddings are available, False otherwise
        """
        if self._embedding_store is None:
            from .local_embeddings import EMBEDDING_DIM
            self._embedding_store = EmbeddingStore(
                self.db,
                dim=EMBEDDING_DIM,
                table_name="memory_embeddings_local"
            )
            await self._embedding_store.initialize()

        if self._embedding_generator is None:
            self._embedding_generator = EmbeddingGenerator(model="local-minilm")

        return self._embedding_store.is_available

    async def _store_embedding(
        self,
        node_id: str,
        content: str,
        summary: Optional[str] = None,
    ) -> bool:
        """
        Generate and store embedding for a node.

        Args:
            node_id: The node ID
            content: The node content
            summary: Optional summary (prepended to content for embedding)

        Returns:
            True if embedding was stored, False otherwise
        """
        try:
            available = await self._ensure_embedding_components()
            if not available:
                return False

            # Combine summary and content for embedding
            text = content or ""
            if summary:
                text = f"{summary}\n{text}"

            if not text.strip():
                return False

            embedding = await self._embedding_generator.generate(text)
            await self._embedding_store.store(node_id, embedding)
            logger.debug(f"Stored embedding for node {node_id}")
            return True

        except Exception as e:
            logger.warning(f"Failed to store embedding for {node_id}: {e}")
            return False

    async def _get_entity_resolver(self):
        """Get or create the entity resolver instance."""
        global _entity_resolver
        if _entity_resolver is None:
            try:
                from ..entities.resolution import EntityResolver
                _entity_resolver = EntityResolver(self.db)
                logger.debug("EntityResolver initialized for mention detection")
            except ImportError as e:
                logger.warning(f"Could not import EntityResolver: {e}")
                return None
        return _entity_resolver

    async def _link_entity_mentions(self, node_id: str, content: str) -> int:
        """
        Detect entities in content and create relevance-scored mention links.

        Scoring based on:
        - Frequency: how many times the entity name appears
        - Position: early mentions suggest the node is ABOUT the entity
        - Density: what fraction of content is the entity name

        Classification:
        - "subject": node is primarily about this entity (high density/frequency)
        - "focus": entity is prominently featured (early + repeated)
        - "reference": passing mention (low relevance)

        Mentions below confidence 0.3 are dropped entirely.
        """
        resolver = await self._get_entity_resolver()
        if resolver is None:
            return 0

        try:
            entities = await resolver.detect_mentions(content)
            if not entities:
                return 0

            content_lower = content.lower()
            content_len = len(content)
            word_count = len(content.split())

            if content_len == 0 or word_count == 0:
                return 0

            mention_count = 0
            for entity in entities:
                name_lower = entity.name.lower()
                name_word_count = len(entity.name.split())

                # --- Signal 1: Frequency ---
                occurrences = content_lower.count(name_lower)
                frequency_score = min(occurrences / 3.0, 1.0)

                # --- Signal 2: Position ---
                first_pos = content_lower.find(name_lower)
                if first_pos >= 0:
                    position_score = 1.0 - (first_pos / content_len)
                else:
                    position_score = 0.0

                # --- Signal 3: Density ---
                density = (occurrences * name_word_count) / word_count
                density_score = min(density * 10, 1.0)

                # --- Composite Confidence ---
                confidence = min(1.0, (
                    0.3 * frequency_score +
                    0.3 * position_score +
                    0.4 * density_score
                ))

                # --- Drop low-relevance mentions ---
                if confidence < 0.3:
                    logger.debug(
                        f"Skipping low-relevance mention: '{entity.name}' "
                        f"in node {node_id} (conf={confidence:.2f})"
                    )
                    continue

                # --- Classify mention type ---
                if density > 0.1 or occurrences >= 3:
                    mention_type = "subject"
                elif position_score > 0.8 and occurrences >= 2:
                    mention_type = "focus"
                else:
                    mention_type = "reference"

                # --- Build context snippet ---
                pos = content_lower.find(name_lower)
                if pos >= 0:
                    start = max(0, pos - 30)
                    end = min(content_len, pos + len(entity.name) + 70)
                    snippet = content[start:end]
                    if start > 0:
                        snippet = "..." + snippet
                    if end < content_len:
                        snippet = snippet + "..."
                else:
                    snippet = content[:100] + "..." if content_len > 100 else content

                await resolver.create_mention(
                    entity_id=entity.id,
                    node_id=node_id,
                    mention_type=mention_type,
                    confidence=round(confidence, 3),
                    context_snippet=snippet,
                )
                mention_count += 1
                logger.debug(
                    f"Linked entity '{entity.name}' to node {node_id} "
                    f"(type={mention_type}, conf={confidence:.2f})"
                )

            if mention_count > 0:
                logger.info(f"Linked {mention_count} entities to node {node_id}")

            return mention_count

        except Exception as e:
            logger.warning(f"Failed to link entity mentions for node {node_id}: {e}")
            return 0

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
        scope: Optional[str] = None,
    ) -> list[MemoryNode]:
        """
        Search memory nodes by text using LIKE query.

        Args:
            query: Search text (uses SQL LIKE with wildcards)
            node_type: Optional filter by node type
            limit: Maximum number of results (default 10)
            scope: Optional scope filter ('global', 'project:slug'). None = all scopes.

        Returns:
            List of matching MemoryNodes, ordered by importance
        """
        search_pattern = f"%{query}%"
        conditions = ["(content LIKE ? OR summary LIKE ?)"]
        params: list = [search_pattern, search_pattern]

        if node_type:
            conditions.append("node_type = ?")
            params.append(node_type)

        if scope is not None:
            conditions.append("scope = ?")
            params.append(scope)

        where = " AND ".join(conditions)
        params.append(limit)

        rows = await self.db.fetchall(
            f"""
            SELECT * FROM memory_nodes
            WHERE {where}
            ORDER BY importance DESC, created_at DESC
            LIMIT ?
            """,
            tuple(params)
        )

        return [MemoryNode.from_row(row) for row in rows]

    # =========================================================================
    # FTS5 SEARCH (Full-Text Search with Stemming)
    # =========================================================================

    async def fts5_search(
        self,
        query: str,
        node_type: Optional[str] = None,
        limit: int = 10,
        scope: Optional[str] = None,
    ) -> list[tuple[MemoryNode, float]]:
        """
        Search memory nodes using FTS5 full-text search.

        Uses Porter stemmer: "collaborate" matches "collaborator", "collaboration".
        Supports phrase search, boolean operators, and prefix matching.

        Args:
            query: Search query (FTS5 syntax supported)
            node_type: Optional filter by node type
            limit: Maximum number of results (default 10)
            scope: Optional scope filter. None = all scopes.

        Returns:
            List of (MemoryNode, score) tuples, sorted by relevance
        """
        # Check if FTS5 table exists
        fts_exists = await self.db.fetchone("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='memory_nodes_fts'
        """)

        if not fts_exists:
            logger.warning("FTS5 table not found, falling back to LIKE search")
            nodes = await self.search_nodes(query, node_type, limit, scope=scope)
            return [(node, 1.0) for node in nodes]

        # Escape special FTS5 characters and prepare query
        safe_query = query.replace('"', '""')

        conditions = ["memory_nodes_fts MATCH ?"]
        params: list = [safe_query]

        if node_type:
            conditions.append("m.node_type = ?")
            params.append(node_type)

        if scope is not None:
            conditions.append("m.scope = ?")
            params.append(scope)

        where = " AND ".join(conditions)
        params.append(limit)

        rows = await self.db.fetchall(
            f"""
            SELECT m.*, bm25(memory_nodes_fts) as score
            FROM memory_nodes m
            JOIN memory_nodes_fts fts ON m.rowid = fts.rowid
            WHERE {where}
            ORDER BY bm25(memory_nodes_fts)
            LIMIT ?
            """,
            tuple(params)
        )

        results = []
        for row in rows:
            # Last column is the score, rest are node columns
            node_data = row[:-1]
            score = abs(row[-1])  # bm25 returns negative, lower is better
            node = MemoryNode.from_row(node_data)
            results.append((node, score))

        return results

    # =========================================================================
    # SEMANTIC SEARCH (Vector Similarity)
    # =========================================================================

    async def semantic_search(
        self,
        query: str,
        node_type: Optional[str] = None,
        limit: int = 10,
        min_similarity: float = 0.3,
        scope: Optional[str] = None,
    ) -> list[tuple[MemoryNode, float]]:
        """
        Search memory nodes using semantic similarity.

        Uses local MiniLM embeddings for vector search.
        Finds semantically similar content even without keyword matches.

        Args:
            query: Search query text
            node_type: Optional filter by node type
            limit: Maximum number of results (default 10)
            min_similarity: Minimum cosine similarity threshold (default 0.3)
            scope: Optional scope filter. None = all scopes.

        Returns:
            List of (MemoryNode, similarity) tuples, sorted by similarity
        """
        # Get or create embedding components
        if not hasattr(self, '_embedding_store') or self._embedding_store is None:
            from .local_embeddings import EMBEDDING_DIM
            self._embedding_store = EmbeddingStore(
                self.db,
                dim=EMBEDDING_DIM,
                table_name="memory_embeddings_local"
            )
            await self._embedding_store.initialize()

        if not hasattr(self, '_embedding_generator') or self._embedding_generator is None:
            self._embedding_generator = EmbeddingGenerator(model="local-minilm")

        if not self._embedding_store.is_available:
            logger.warning("sqlite-vec not available, falling back to LIKE search")
            nodes = await self.search_nodes(query, node_type, limit)
            return [(node, 1.0) for node in nodes]

        # Generate query embedding
        query_embedding = await self._embedding_generator.generate(query)

        # Search for similar embeddings
        similar = await self._embedding_store.search(
            query_embedding,
            limit=limit * 2,  # Get extra for filtering
            min_similarity=min_similarity,
        )

        if not similar:
            return []

        # Fetch full nodes and filter by type/scope
        results = []
        for node_id, similarity in similar:
            node = await self.get_node(node_id)
            if node is None:
                continue
            if node_type and node.node_type != node_type:
                continue
            if scope is not None and node.scope != scope:
                continue
            results.append((node, similarity))
            if len(results) >= limit:
                break

        return results

    # =========================================================================
    # HYBRID SEARCH (FTS5 + Semantic with RRF Fusion)
    # =========================================================================

    async def hybrid_search(
        self,
        query: str,
        node_type: Optional[str] = None,
        limit: int = 10,
        keyword_weight: float = 0.4,
        semantic_weight: float = 0.6,
        rrf_k: int = 60,
        scope: Optional[str] = None,
    ) -> list[tuple[MemoryNode, float]]:
        """
        Search using both FTS5 and semantic search with Reciprocal Rank Fusion.

        Combines keyword matching (exact terms, stemming) with semantic
        similarity (meaning-based) for best results.

        Args:
            query: Search query text
            node_type: Optional filter by node type
            limit: Maximum number of results (default 10)
            keyword_weight: Weight for FTS5 results (default 0.4)
            semantic_weight: Weight for semantic results (default 0.6)
            rrf_k: RRF constant (default 60, higher = more emphasis on top ranks)
            scope: Optional scope filter. None = all scopes.

        Returns:
            List of (MemoryNode, combined_score) tuples, sorted by score
        """
        # Run both searches in parallel conceptually (sequential here for SQLite)
        fts_results = await self.fts5_search(query, node_type, limit * 2, scope=scope)
        semantic_results = await self.semantic_search(query, node_type, limit * 2, scope=scope)

        # Build node lookup and rank maps
        nodes_by_id: dict[str, MemoryNode] = {}
        fts_ranks: dict[str, int] = {}
        semantic_ranks: dict[str, int] = {}

        for rank, (node, _score) in enumerate(fts_results, start=1):
            nodes_by_id[node.id] = node
            fts_ranks[node.id] = rank

        for rank, (node, _score) in enumerate(semantic_results, start=1):
            nodes_by_id[node.id] = node
            semantic_ranks[node.id] = rank

        # Calculate RRF scores
        # RRF(d) = Σ (weight / (k + rank(d)))
        rrf_scores: dict[str, float] = {}

        for node_id in nodes_by_id:
            score = 0.0

            if node_id in fts_ranks:
                score += keyword_weight / (rrf_k + fts_ranks[node_id])

            if node_id in semantic_ranks:
                score += semantic_weight / (rrf_k + semantic_ranks[node_id])

            rrf_scores[node_id] = score

        # Sort by RRF score (higher is better)
        sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)

        # Return top results
        results = [
            (nodes_by_id[node_id], rrf_scores[node_id])
            for node_id in sorted_ids[:limit]
        ]

        return results

    async def get_context(
        self,
        query: str,
        max_tokens: int = 2000,
        node_types: Optional[list[str]] = None,
        scope: Optional[str] = None,
        scopes: Optional[list[str]] = None,
    ) -> list[MemoryNode]:
        """
        Get relevant context for a query.

        Retrieves memories that might be relevant to the query,
        staying within the token budget. Uses tokenized text matching
        and importance weighting.

        Args:
            query: The query to find context for
            max_tokens: Maximum tokens worth of context (approximate)
            node_types: Optional list of node types to include
            scope: Single scope filter. None = all scopes.
            scopes: Multi-scope list (e.g. ["global", "project:crooked-nail"]).
                    When provided, queries each scope separately and merges results.
                    Overrides `scope` if both provided.

        Returns:
            List of relevant MemoryNodes within token budget
        """
        # Multi-scope: query each scope and merge with budget split
        if scopes and len(scopes) > 1:
            return await self._get_context_multi_scope(query, max_tokens, node_types, scopes)

        # Single scope (or all scopes if scope=None)
        effective_scope = scopes[0] if scopes else scope

        # Approximate tokens per character (rough estimate)
        chars_per_token = 4
        max_chars = max_tokens * chars_per_token

        # Tokenize query into meaningful words (skip common stopwords)
        stopwords = {
            "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did", "will", "would", "could",
            "should", "may", "might", "must", "can", "to", "of", "in", "for",
            "on", "with", "at", "by", "from", "as", "into", "through", "during",
            "before", "after", "above", "below", "between", "under", "again",
            "further", "then", "once", "here", "there", "when", "where", "why",
            "how", "all", "each", "few", "more", "most", "other", "some", "such",
            "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very",
            "just", "and", "but", "if", "or", "because", "until", "while", "about",
            "this", "that", "these", "those", "am", "it", "its", "my", "me", "you",
            "your", "he", "him", "his", "she", "her", "we", "us", "our", "they",
            "them", "their", "what", "which", "who", "whom", "i", "try", "remember",
            "now", "tell", "know", "think", "want", "need", "like", "please", "hi",
            "hello", "hey", "ok", "okay", "yes", "no", "luna",
        }

        # Extract meaningful words (3+ chars, not stopwords)
        words = [w.strip(".,!?;:'\"()[]{}") for w in query.lower().split()]
        keywords = [w for w in words if len(w) >= 3 and w not in stopwords]

        # Detect backward reference patterns (need recent conversation, not keyword search)
        backward_patterns = [
            "what were we", "what did we", "what was that",
            "earlier", "before", "last time", "just now",
            "you said", "you mentioned", "we discussed", "we talked",
            "remember when", "do you remember", "recall",
            "where were we", "continue", "going back"
        ]
        is_backward_ref = any(p in query.lower() for p in backward_patterns)

        # For backward references OR no keywords: fetch recent conversation directly
        if is_backward_ref or not keywords:
            logger.info(f"Context: backward_ref={is_backward_ref}, keywords={keywords or 'empty'} → fetching conversation")

            # Query conversation_turns table (NOT memory_nodes)
            conversation_rows = await self.db.fetchall("""
                SELECT id, session_id, role, content, tokens, created_at
                FROM conversation_turns
                ORDER BY created_at DESC
                LIMIT 15
            """)

            if conversation_rows:
                results = []
                total_chars = 0
                max_chars = max_tokens * 4  # ~4 chars per token

                for row in conversation_rows:
                    # Row is (id, session_id, role, content, tokens, created_at)
                    row_id, _, role, content, _, created_at = row[0], row[1], row[2], row[3], row[4], row[5]
                    content = content or ""
                    if total_chars + len(content) > max_chars:
                        break
                    # Create MemoryNode for compatibility with return type
                    node = MemoryNode(
                        id=str(row_id),
                        node_type="CONVERSATION",
                        content=f"[{role}]: {content}",
                        created_at=created_at,
                    )
                    results.append(node)
                    total_chars += len(content)

                logger.info(f"Context: returning {len(results)} conversation turns ({total_chars} chars)")
                return results

            # No conversation found - fall through to keyword search
            logger.debug("Context: no conversation found, falling back to keyword search")

        if not keywords:
            # Fall back to original behavior if no keywords found
            keywords = [query]

        logger.debug(f"Context search keywords: {keywords}")

        # Build search query with compound phrase boosting
        # Strategy:
        # 1. Try compound phrase first (e.g., "mars college" as one phrase)
        # 2. Fall back to individual keywords
        # 3. Prioritize smaller nodes (extracted facts) over huge conversation dumps
        # 4. Sort by lock_in for relevance

        # If we have 2+ keywords, also search for compound phrase
        compound_phrase = " ".join(keywords) if len(keywords) >= 2 else None

        # Build scope filter SQL fragment
        scope_clause = ""
        scope_params: list = []
        if effective_scope is not None:
            scope_clause = " AND scope = ?"
            scope_params = [effective_scope]

        if node_types:
            placeholders = ", ".join("?" * len(node_types))
            like_clauses = " OR ".join(
                ["(content LIKE ? OR summary LIKE ?)" for _ in keywords]
            )
            params = []
            for kw in keywords:
                params.extend([f"%{kw}%", f"%{kw}%"])
            params.extend(node_types)
            params.extend(scope_params)

            rows = await self.db.fetchall(
                f"""
                SELECT * FROM memory_nodes
                WHERE ({like_clauses})
                  AND node_type IN ({placeholders})
                  {scope_clause}
                ORDER BY lock_in DESC, length(content) ASC, created_at DESC
                LIMIT 50
                """,
                tuple(params)
            )
        else:
            like_clauses = " OR ".join(
                ["(content LIKE ? OR summary LIKE ?)" for _ in keywords]
            )
            params = []
            for kw in keywords:
                params.extend([f"%{kw}%", f"%{kw}%"])

            # First, try to find exact compound phrase matches (these are most relevant)
            if compound_phrase:
                compound_params = [f"%{compound_phrase}%", f"%{compound_phrase}%"] + scope_params
                compound_rows = await self.db.fetchall(
                    f"""
                    SELECT * FROM memory_nodes
                    WHERE (content LIKE ? OR summary LIKE ?)
                    {scope_clause}
                    ORDER BY lock_in DESC, length(content) ASC, created_at DESC
                    LIMIT 25
                    """,
                    tuple(compound_params)
                )
            else:
                compound_rows = []

            # Then get individual keyword matches
            keyword_params = params + scope_params
            keyword_rows = await self.db.fetchall(
                f"""
                SELECT * FROM memory_nodes
                WHERE {like_clauses}
                {scope_clause}
                ORDER BY lock_in DESC, length(content) ASC, created_at DESC
                LIMIT 50
                """,
                tuple(keyword_params)
            )

            # Combine: compound matches first (deduplicated), then keyword matches
            seen_ids = set()
            rows = []
            for row in compound_rows:
                if row[0] not in seen_ids:
                    seen_ids.add(row[0])
                    rows.append(row)
            for row in keyword_rows:
                if row[0] not in seen_ids:
                    seen_ids.add(row[0])
                    rows.append(row)
                if len(rows) >= 50:
                    break

        # =====================================================================
        # GRAPH EXPANSION: Use spreading activation to find connected nodes
        # =====================================================================
        # If we found keyword matches, expand through graph to find related nodes
        # that keyword search would miss (e.g., "Mars College" -> Robot Body -> Tarcila)
        if rows and self.graph:
            try:
                # Get IDs from keyword results as seed nodes
                seed_ids = [row[0] for row in rows[:10]]  # Top 10 keyword hits

                # Run spreading activation from seeds
                activations = await self.graph.spreading_activation(
                    start_nodes=seed_ids,
                    decay=0.5,
                    max_depth=2,
                    scope=effective_scope,
                )

                if activations:
                    # Get activated node IDs not already in results
                    existing_ids = {row[0] for row in rows}
                    graph_ids = [
                        (nid, score) for nid, score in activations.items()
                        if nid not in existing_ids and score >= 0.2
                    ]
                    # Sort by activation score
                    graph_ids.sort(key=lambda x: x[1], reverse=True)

                    # Fetch the top graph-discovered nodes (respecting scope)
                    if graph_ids:
                        graph_node_ids = [gid for gid, _ in graph_ids[:15]]
                        placeholders = ",".join("?" * len(graph_node_ids))
                        graph_query = f"""
                            SELECT * FROM memory_nodes
                            WHERE id IN ({placeholders})
                            {scope_clause}
                            ORDER BY lock_in DESC
                        """
                        graph_params = list(graph_node_ids) + scope_params
                        graph_rows = await self.db.fetchall(
                            graph_query, tuple(graph_params)
                        )
                        rows.extend(graph_rows)
                        logger.info(
                            f"GRAPH_EXPAND: Added {len(graph_rows)} nodes via "
                            f"spreading activation from {len(seed_ids)} seeds "
                            f"({len(activations)} total activated)"
                        )

            except Exception as e:
                # Graph expansion is supplementary - never block retrieval
                logger.warning(f"GRAPH_EXPAND_FAIL: {type(e).__name__}: {e}")

        # Collect nodes within token budget, filtering out confusing identity nodes
        results = []
        total_chars = 0

        for row in rows:
            node = MemoryNode.from_row(row)

            # Filter out potentially confusing identity nodes about other people
            # This prevents Luna from confusing the current user (Ahab/Zayne) with others
            content_lower = node.content.lower()
            if "my name is" in content_lower and "ahab" not in content_lower and "zayne" not in content_lower:
                logger.debug(f"Filtering out potentially confusing identity node: {node.id}")
                continue

            # Filter out raw conversation dumps (system prompts embedded in content)
            # These are not useful as memory context - they're just logs
            if "# luna's foundation" in content_lower or "# luna's core identity" in content_lower:
                logger.debug(f"Filtering out system prompt dump: {node.id}")
                continue

            # Filter out development notes (start with ### markdown headers)
            # These are technical specs, not Luna's actual knowledge
            if node.content.strip().startswith("###") or node.content.strip().startswith("## "):
                logger.debug(f"Filtering out dev note: {node.id}")
                continue

            # Filter out raw "User (desktop):" conversation logs
            # These contain system prompts and aren't useful knowledge
            if node.content.strip().startswith("User (desktop):") or node.content.strip().startswith("User (mobile):"):
                logger.debug(f"Filtering out raw conversation log: {node.id}")
                continue

            # Skip very long nodes (likely raw conversation dumps, not extracted facts)
            # Prefer concise, extracted knowledge over conversation transcripts
            if len(node.content) > 5000:
                logger.debug(f"Skipping oversized node ({len(node.content)} chars): {node.id}")
                continue

            node_chars = len(node.content) + (len(node.summary) if node.summary else 0)

            if total_chars + node_chars > max_chars:
                break

            results.append(node)
            total_chars += node_chars

            # Record access
            await self.record_access(node.id)

        logger.debug(f"Retrieved {len(results)} nodes for context ({total_chars} chars)")
        return results

    async def _get_context_multi_scope(
        self,
        query: str,
        max_tokens: int,
        node_types: Optional[list[str]],
        scopes: list[str],
    ) -> list[MemoryNode]:
        """
        Get context from multiple scopes with budget splitting.

        For project + global queries: 60% tokens to project scope, 40% to global.
        Deduplicates by node ID across scopes.
        """
        project_scopes = [s for s in scopes if s.startswith("project:")]
        global_scopes = [s for s in scopes if s == "global"]

        # Budget split: project gets priority
        if project_scopes and global_scopes:
            project_budget = int(max_tokens * 0.6)
            global_budget = max_tokens - project_budget
        else:
            # Only one type of scope
            project_budget = max_tokens
            global_budget = max_tokens

        all_results: list[MemoryNode] = []
        seen_ids: set[str] = set()

        # Query project scopes first (higher priority)
        for ps in project_scopes:
            nodes = await self.get_context(
                query, max_tokens=project_budget, node_types=node_types, scope=ps
            )
            for node in nodes:
                if node.id not in seen_ids:
                    seen_ids.add(node.id)
                    all_results.append(node)

        # Then global scope
        for gs in global_scopes:
            nodes = await self.get_context(
                query, max_tokens=global_budget, node_types=node_types, scope=gs
            )
            for node in nodes:
                if node.id not in seen_ids:
                    seen_ids.add(node.id)
                    all_results.append(node)

        return all_results

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

        # Total edges
        edges_row = await self.db.fetchone(
            "SELECT COUNT(*) FROM graph_edges"
        )
        total_edges = edges_row[0] if edges_row else 0

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
            "total_edges": total_edges,
        }

    # =========================================================================
    # LIFECYCLE
    # =========================================================================

    async def close(self) -> None:
        """Close the underlying database connection."""
        await self.db.close()
        logger.info("MemoryMatrix closed")
