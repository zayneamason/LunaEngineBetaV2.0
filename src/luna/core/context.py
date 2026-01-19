"""
Revolving Context System for Luna Engine
=========================================

Manages Luna's working memory through a ring-based context system.
Items enter at outer rings and migrate inward based on relevance and access patterns.

Key insight: Context is not just what fits - it's what MATTERS right now.

The context window is assembled dynamically each tick, prioritizing:
1. CORE: Identity (never evicted)
2. INNER: Active conversation turns
3. MIDDLE: Recently accessed memories
4. OUTER: Background context (first to evict)
"""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import Any, Deque, Dict, List, Optional
import logging
import uuid

logger = logging.getLogger(__name__)


# Try to import tiktoken for accurate token counting
try:
    import tiktoken
    _ENCODER = tiktoken.get_encoding("cl100k_base")
    _HAS_TIKTOKEN = True
except ImportError:
    _ENCODER = None
    _HAS_TIKTOKEN = False
    logger.warning("tiktoken not available, using fallback token counting (len/4)")


def count_tokens(text: str) -> int:
    """
    Count tokens in text.

    Uses tiktoken if available, otherwise falls back to len/4 approximation.

    Args:
        text: The text to count tokens for.

    Returns:
        Estimated token count.
    """
    if _HAS_TIKTOKEN and _ENCODER is not None:
        return len(_ENCODER.encode(text))
    # Fallback: rough approximation (~4 chars per token for English)
    return max(1, len(text) // 4)


class ContextRing(IntEnum):
    """
    Concentric rings of context priority.

    Lower number = higher priority = closer to Luna's attention.
    Items migrate between rings based on relevance decay and access patterns.
    """
    CORE = 0    # Identity, personality - NEVER evicted
    INNER = 1   # Active conversation, current task
    MIDDLE = 2  # Recently accessed memories, relevant context
    OUTER = 3   # Background context, candidate for eviction


class ContextSource(IntEnum):
    """
    Sources that contribute context items.

    Each source has different priority weights for queue processing.
    """
    IDENTITY = 0      # Luna's core identity (highest priority)
    CONVERSATION = 1  # Current conversation turns
    MEMORY = 2        # Retrieved memories from substrate
    TOOL = 3          # Tool call results
    TASK = 4          # Current task context
    SCRIBE = 5        # Recent extraction results (Ben)
    LIBRARIAN = 6     # Retrieved knowledge (Dude)


# Default priority weights for queue processing
DEFAULT_SOURCE_WEIGHTS: Dict[ContextSource, float] = {
    ContextSource.IDENTITY: 1.0,
    ContextSource.CONVERSATION: 0.9,
    ContextSource.MEMORY: 0.7,
    ContextSource.TOOL: 0.8,
    ContextSource.TASK: 0.75,
    ContextSource.SCRIBE: 0.6,
    ContextSource.LIBRARIAN: 0.65,
}

# Default TTL (time-to-live) in seconds for each source
DEFAULT_SOURCE_TTL: Dict[ContextSource, float] = {
    ContextSource.IDENTITY: float('inf'),  # Never expires
    ContextSource.CONVERSATION: 300.0,     # 5 minutes
    ContextSource.MEMORY: 600.0,           # 10 minutes
    ContextSource.TOOL: 120.0,             # 2 minutes
    ContextSource.TASK: 900.0,             # 15 minutes
    ContextSource.SCRIBE: 180.0,           # 3 minutes
    ContextSource.LIBRARIAN: 600.0,        # 10 minutes
}


@dataclass
class ContextItem:
    """
    A single item in the context window.

    Items have:
    - Relevance score (0-1) that decays over time
    - Ring placement based on source and relevance
    - Token count for budget management
    - TTL for automatic expiration

    Attributes:
        id: Unique identifier for this item.
        content: The text content of this context item.
        source: Where this item came from (ContextSource enum).
        ring: Current ring placement (ContextRing enum).
        relevance: Relevance score from 0.0 to 1.0.
        created_at: When this item was created.
        last_accessed: When this item was last accessed.
        ttl_seconds: Time-to-live in seconds.
        tokens: Token count for this item's content.
        metadata: Additional metadata dictionary.
    """
    content: str
    source: ContextSource
    ring: ContextRing = ContextRing.MIDDLE
    relevance: float = 1.0  # 0.0 to 1.0
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    ttl_seconds: float = 600.0  # 10 minutes default
    tokens: int = field(init=False)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Calculate token count on creation and set TTL based on source."""
        self.tokens = count_tokens(self.content)
        # Set TTL based on source if still at default
        if self.ttl_seconds == 600.0 and self.source in DEFAULT_SOURCE_TTL:
            self.ttl_seconds = DEFAULT_SOURCE_TTL[self.source]

    def decay(self, factor: float = 0.95) -> None:
        """
        Apply relevance decay.

        Called periodically to reduce relevance of items not being accessed.
        Core items (ring 0) are immune to decay.

        Args:
            factor: Decay multiplier (0.95 = 5% decay per call).
        """
        if self.ring == ContextRing.CORE:
            return  # Core identity never decays
        self.relevance = max(0.0, self.relevance * factor)

    def access(self, relevance_boost: float = 0.1) -> None:
        """
        Mark item as accessed, boosting relevance.

        Called when item is used in context assembly or matched by query.

        Args:
            relevance_boost: Amount to increase relevance (capped at 1.0).
        """
        self.last_accessed = datetime.now()
        self.relevance = min(1.0, self.relevance + relevance_boost)

    @property
    def is_expired(self) -> bool:
        """Check if item has exceeded its TTL."""
        if self.ttl_seconds == float('inf'):
            return False
        age = (datetime.now() - self.created_at).total_seconds()
        return age > self.ttl_seconds

    @property
    def age_seconds(self) -> float:
        """Time since creation in seconds."""
        return (datetime.now() - self.created_at).total_seconds()

    @property
    def idle_seconds(self) -> float:
        """Time since last access in seconds."""
        return (datetime.now() - self.last_accessed).total_seconds()

    def __repr__(self) -> str:
        preview = self.content[:40].replace('\n', ' ')
        return (f"ContextItem(id={self.id}, ring={self.ring.name}, "
                f"rel={self.relevance:.2f}, tok={self.tokens}, '{preview}...')")


class QueueManager:
    """
    Manages multiple input queues for different context sources.

    Each source type has its own queue with configurable priority weights.
    The RevolvingContext pulls from these queues during context assembly.

    Key insight: Different sources have different urgency and importance.
    Conversation messages need immediate attention; memories can wait.

    Attributes:
        _max_size: Maximum items per queue.
        _weights: Priority weights for each source.
        _queues: Dictionary mapping sources to their deque queues.
    """

    def __init__(
        self,
        max_queue_size: int = 50,
        weights: Optional[Dict[ContextSource, float]] = None
    ):
        """
        Initialize queue manager.

        Args:
            max_queue_size: Maximum items per queue.
            weights: Priority weights for each source (higher = more priority).
        """
        self._max_size = max_queue_size
        self._weights = weights or DEFAULT_SOURCE_WEIGHTS.copy()

        # Create a deque for each source type
        self._queues: Dict[ContextSource, Deque[ContextItem]] = {
            source: deque(maxlen=max_queue_size)
            for source in ContextSource
        }

        # Statistics
        self._total_pushed = 0
        self._total_polled = 0

    def push(self, item: ContextItem) -> bool:
        """
        Push an item onto its source queue.

        Args:
            item: Context item to queue.

        Returns:
            True if added without eviction, False if queue was full (oldest was evicted).
        """
        queue = self._queues[item.source]
        was_full = len(queue) >= self._max_size
        queue.append(item)
        self._total_pushed += 1

        if was_full:
            logger.debug(f"Queue {item.source.name} full, oldest item evicted")

        return not was_full

    def poll_all(self) -> List[ContextItem]:
        """
        Poll all queues, returning items sorted by weighted priority.

        Items from higher-weight sources appear first.
        Within same weight, older items (FIFO) appear first.

        Returns:
            List of all queued items, sorted by priority.
        """
        items: List[tuple[float, datetime, ContextItem]] = []

        for source, queue in self._queues.items():
            weight = self._weights.get(source, 0.5)
            while queue:
                item = queue.popleft()
                items.append((weight, item.created_at, item))
                self._total_polled += 1

        # Sort by weight (descending), then timestamp (ascending for FIFO)
        items.sort(key=lambda x: (-x[0], x[1]))

        return [item for _, _, item in items]

    def poll_source(self, source: ContextSource, max_items: int = 10) -> List[ContextItem]:
        """
        Poll items from a specific source queue.

        Args:
            source: Source to poll from.
            max_items: Maximum items to return.

        Returns:
            List of items from the specified source.
        """
        items: List[ContextItem] = []
        queue = self._queues[source]

        while queue and len(items) < max_items:
            items.append(queue.popleft())
            self._total_polled += 1

        return items

    def peek_source(self, source: ContextSource) -> Optional[ContextItem]:
        """
        Peek at the next item in a source queue without removing it.

        Args:
            source: Source queue to peek at.

        Returns:
            The next item or None if queue is empty.
        """
        queue = self._queues[source]
        return queue[0] if queue else None

    def size(self, source: Optional[ContextSource] = None) -> int:
        """
        Get queue size for a source, or total across all sources.

        Args:
            source: Specific source to check, or None for total.

        Returns:
            Number of items in specified queue(s).
        """
        if source is not None:
            return len(self._queues[source])
        return sum(len(q) for q in self._queues.values())

    def clear(self, source: Optional[ContextSource] = None) -> int:
        """
        Clear one or all queues.

        Args:
            source: Specific source to clear, or None for all.

        Returns:
            Number of items cleared.
        """
        count = 0
        if source is not None:
            count = len(self._queues[source])
            self._queues[source].clear()
        else:
            for queue in self._queues.values():
                count += len(queue)
                queue.clear()
        return count

    def stats(self) -> Dict[str, Any]:
        """
        Get queue statistics.

        Returns:
            Dictionary containing queue stats.
        """
        return {
            "total_pushed": self._total_pushed,
            "total_polled": self._total_polled,
            "queue_sizes": {
                source.name: len(queue)
                for source, queue in self._queues.items()
            },
            "weights": {
                source.name: weight
                for source, weight in self._weights.items()
            },
        }

    def __repr__(self) -> str:
        total = self.size()
        return f"QueueManager(total_items={total}, queues={len(self._queues)})"


class RevolvingContext:
    """
    Luna's working memory - a revolving context window.

    Items are organized in concentric rings:
    - CORE: Identity (never evicted)
    - INNER: Active conversation
    - MIDDLE: Relevant memories
    - OUTER: Background context (evicted first)

    The context window is assembled dynamically each tick,
    respecting the token budget while prioritizing inner rings.

    Key insight: It's not about cramming more context in.
    It's about having the RIGHT context at the right moment.

    Attributes:
        token_budget: Maximum tokens allowed in assembled context.
        rings: Dictionary mapping ContextRing to list of items.
        queue_manager: QueueManager for incoming items.
    """

    def __init__(
        self,
        token_budget: int = 8000,
        decay_factor: float = 0.95,
        rebalance_threshold: float = 0.3
    ):
        """
        Initialize revolving context.

        Args:
            token_budget: Maximum tokens in assembled context window.
            decay_factor: Relevance decay multiplier per cycle.
            rebalance_threshold: Relevance threshold for ring demotion.
        """
        self.token_budget = token_budget
        self._decay_factor = decay_factor
        self._rebalance_threshold = rebalance_threshold

        # Ring storage
        self.rings: Dict[ContextRing, List[ContextItem]] = {
            ring: [] for ring in ContextRing
        }

        # Queue manager for incoming items
        self.queue_manager = QueueManager()

        # Core identity (special handling)
        self._core_identity: Optional[ContextItem] = None

        # Statistics
        self._total_added = 0
        self._total_evicted = 0
        self._assembly_count = 0

    def set_core_identity(
        self,
        identity_text: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ContextItem:
        """
        Set Luna's core identity. This is NEVER evicted.

        Args:
            identity_text: Luna's identity/personality description.
            metadata: Optional metadata for the identity item.

        Returns:
            The created ContextItem.
        """
        self._core_identity = ContextItem(
            content=identity_text,
            source=ContextSource.IDENTITY,
            ring=ContextRing.CORE,
            relevance=1.0,
            ttl_seconds=float('inf'),
            metadata=metadata or {},
        )

        # Clear and set in CORE ring
        self.rings[ContextRing.CORE] = [self._core_identity]
        logger.info(f"Core identity set ({self._core_identity.tokens} tokens)")

        return self._core_identity

    def add(
        self,
        content: str,
        source: ContextSource,
        ring: Optional[ContextRing] = None,
        relevance: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ContextItem:
        """
        Add an item to the context.

        Args:
            content: Text content.
            source: Source type.
            ring: Target ring (auto-assigned if None).
            relevance: Initial relevance score.
            metadata: Optional metadata.

        Returns:
            The created ContextItem.
        """
        # Auto-assign ring based on source if not specified
        if ring is None:
            ring = self._infer_ring(source)

        # Cannot add to CORE ring directly (use set_core_identity)
        if ring == ContextRing.CORE and source != ContextSource.IDENTITY:
            ring = ContextRing.INNER
            logger.warning("Cannot add non-identity item to CORE ring, placing in INNER")

        item = ContextItem(
            content=content,
            source=source,
            ring=ring,
            relevance=relevance,
            metadata=metadata or {},
        )

        self.rings[ring].append(item)
        self._total_added += 1

        # Enforce budget after adding
        self._enforce_budget()

        logger.debug(f"Added context item: {item}")
        return item

    def add_from_queues(self, max_items: int = 20) -> int:
        """
        Pull items from the queue manager and add to context.

        Args:
            max_items: Maximum items to pull.

        Returns:
            Number of items added.
        """
        items = self.queue_manager.poll_all()[:max_items]

        for item in items:
            # Items from queues go to their inferred ring
            target_ring = self._infer_ring(item.source)
            if target_ring != item.ring:
                item.ring = target_ring
            self.rings[item.ring].append(item)
            self._total_added += 1

        if items:
            self._enforce_budget()
            logger.debug(f"Added {len(items)} items from queues")

        return len(items)

    def _infer_ring(self, source: ContextSource) -> ContextRing:
        """
        Infer appropriate ring from source type.

        Args:
            source: The context source.

        Returns:
            The appropriate ContextRing for this source.
        """
        ring_mapping = {
            ContextSource.IDENTITY: ContextRing.CORE,
            ContextSource.CONVERSATION: ContextRing.INNER,
            ContextSource.TASK: ContextRing.INNER,
            ContextSource.TOOL: ContextRing.MIDDLE,
            ContextSource.MEMORY: ContextRing.MIDDLE,
            ContextSource.SCRIBE: ContextRing.OUTER,
            ContextSource.LIBRARIAN: ContextRing.MIDDLE,
        }
        return ring_mapping.get(source, ContextRing.OUTER)

    def _enforce_budget(self) -> int:
        """
        Ensure total tokens are within budget by evicting items.

        Returns:
            Number of items evicted.
        """
        evicted = 0

        while self._total_tokens() > self.token_budget:
            if not self._evict_one():
                logger.warning("Cannot evict any more items but still over budget")
                break
            evicted += 1

        if evicted:
            logger.debug(f"Evicted {evicted} items to enforce budget")

        return evicted

    def _evict_one(self) -> bool:
        """
        Evict a single item following priority order.

        Eviction order:
        1. Expired items (any ring except CORE)
        2. Outer ring, lowest relevance first
        3. Middle ring, lowest relevance first
        4. Inner ring, lowest relevance first
        5. CORE ring items are NEVER evicted

        Returns:
            True if an item was evicted, False if nothing to evict.
        """
        # First pass: find expired items
        for ring in [ContextRing.OUTER, ContextRing.MIDDLE, ContextRing.INNER]:
            items = self.rings[ring]
            for i, item in enumerate(items):
                if item.is_expired:
                    items.pop(i)
                    self._total_evicted += 1
                    logger.debug(f"Evicted expired item: {item}")
                    return True

        # Second pass: evict by ring priority and relevance
        for ring in [ContextRing.OUTER, ContextRing.MIDDLE, ContextRing.INNER]:
            items = self.rings[ring]
            if not items:
                continue

            # Find item with lowest relevance
            min_idx = min(range(len(items)), key=lambda i: items[i].relevance)
            evicted_item = items.pop(min_idx)
            self._total_evicted += 1
            logger.debug(f"Evicted item from {ring.name}: {evicted_item}")
            return True

        # Cannot evict CORE items
        return False

    def decay_all(self) -> None:
        """Apply relevance decay to all items (except CORE)."""
        for ring in [ContextRing.INNER, ContextRing.MIDDLE, ContextRing.OUTER]:
            for item in self.rings[ring]:
                item.decay(self._decay_factor)

    def _rebalance_rings(self) -> int:
        """
        Move items between rings based on relevance thresholds.

        Items with low relevance get demoted to outer rings.
        Items with high relevance can be promoted to inner rings.

        Returns:
            Number of items moved.
        """
        moved = 0

        # Demotion: INNER -> MIDDLE -> OUTER
        for src_ring, dst_ring in [(ContextRing.INNER, ContextRing.MIDDLE),
                                    (ContextRing.MIDDLE, ContextRing.OUTER)]:
            items = self.rings[src_ring]
            demote_indices: List[int] = []

            for i, item in enumerate(items):
                if item.relevance < self._rebalance_threshold:
                    demote_indices.append(i)

            # Remove in reverse order to preserve indices
            for i in reversed(demote_indices):
                item = items.pop(i)
                item.ring = dst_ring
                self.rings[dst_ring].append(item)
                moved += 1
                logger.debug(f"Demoted {item.id} from {src_ring.name} to {dst_ring.name}")

        # Promotion: OUTER -> MIDDLE -> INNER (for high relevance items)
        promotion_threshold = 0.8
        for src_ring, dst_ring in [(ContextRing.OUTER, ContextRing.MIDDLE),
                                    (ContextRing.MIDDLE, ContextRing.INNER)]:
            items = self.rings[src_ring]
            promote_indices: List[int] = []

            for i, item in enumerate(items):
                if item.relevance >= promotion_threshold:
                    promote_indices.append(i)

            for i in reversed(promote_indices):
                item = items.pop(i)
                item.ring = dst_ring
                self.rings[dst_ring].append(item)
                moved += 1
                logger.debug(f"Promoted {item.id} from {src_ring.name} to {dst_ring.name}")

        return moved

    def get_context_window(
        self,
        max_tokens: Optional[int] = None,
        include_metadata: bool = False
    ) -> str:
        """
        Assemble the context window for LLM consumption.

        Prioritizes inner rings, respecting token budget.

        Args:
            max_tokens: Override token budget (uses self.token_budget if None).
            include_metadata: Include source/ring info in output.

        Returns:
            Assembled context string.
        """
        budget = max_tokens or self.token_budget
        self._assembly_count += 1

        parts: List[str] = []
        used_tokens = 0

        # Process rings from innermost to outermost
        for ring in ContextRing:
            items = self.rings[ring]

            # Sort by relevance within ring (highest first)
            sorted_items = sorted(items, key=lambda x: x.relevance, reverse=True)

            for item in sorted_items:
                # Check if we have room
                if used_tokens + item.tokens > budget:
                    continue  # Skip but keep checking (smaller items might fit)

                # Mark as accessed
                item.access(relevance_boost=0.05)

                # Format content
                if include_metadata:
                    prefix = f"[{item.source.name}/{item.ring.name}] "
                    content = prefix + item.content
                else:
                    content = item.content

                parts.append(content)
                used_tokens += item.tokens

        logger.debug(f"Assembled context: {used_tokens}/{budget} tokens, {len(parts)} items")
        return "\n\n".join(parts)

    def query(self, keywords: str, max_results: int = 10) -> List[ContextItem]:
        """
        Simple keyword search across all context items.

        Args:
            keywords: Space-separated keywords to search for.
            max_results: Maximum results to return.

        Returns:
            Matching items sorted by relevance.
        """
        keywords_lower = keywords.lower().split()
        matches: List[tuple[float, ContextItem]] = []

        for ring in ContextRing:
            for item in self.rings[ring]:
                content_lower = item.content.lower()

                # Count keyword matches
                match_count = sum(1 for kw in keywords_lower if kw in content_lower)

                if match_count > 0:
                    # Score combines match count and relevance
                    score = (match_count / len(keywords_lower)) * item.relevance
                    matches.append((score, item))

        # Sort by score descending
        matches.sort(key=lambda x: x[0], reverse=True)

        # Mark accessed items
        results: List[ContextItem] = []
        for _, item in matches[:max_results]:
            item.access(relevance_boost=0.1)
            results.append(item)

        return results

    def _total_tokens(self) -> int:
        """
        Calculate total tokens across all rings.

        Returns:
            Total token count.
        """
        return sum(
            item.tokens
            for ring_items in self.rings.values()
            for item in ring_items
        )

    def _item_count(self) -> int:
        """
        Count total items across all rings.

        Returns:
            Total item count.
        """
        return sum(len(items) for items in self.rings.values())

    def stats(self) -> Dict[str, Any]:
        """
        Get context statistics.

        Returns:
            Dictionary containing context stats.
        """
        ring_stats: Dict[str, Dict[str, Any]] = {}
        for ring in ContextRing:
            items = self.rings[ring]
            ring_stats[ring.name] = {
                "count": len(items),
                "tokens": sum(item.tokens for item in items),
                "avg_relevance": (
                    sum(item.relevance for item in items) / len(items)
                    if items else 0.0
                ),
            }

        return {
            "total_items": self._item_count(),
            "total_tokens": self._total_tokens(),
            "token_budget": self.token_budget,
            "budget_used_pct": (
                self._total_tokens() / self.token_budget * 100
                if self.token_budget else 0
            ),
            "total_added": self._total_added,
            "total_evicted": self._total_evicted,
            "assembly_count": self._assembly_count,
            "has_core_identity": self._core_identity is not None,
            "rings": ring_stats,
            "queue_stats": self.queue_manager.stats(),
        }

    def clear(self, preserve_core: bool = True) -> int:
        """
        Clear all context items.

        Args:
            preserve_core: If True, keep core identity.

        Returns:
            Number of items cleared.
        """
        count = 0

        for ring in ContextRing:
            if ring == ContextRing.CORE and preserve_core:
                continue
            count += len(self.rings[ring])
            self.rings[ring] = []

        if not preserve_core:
            self._core_identity = None

        logger.info(f"Cleared {count} context items (preserve_core={preserve_core})")
        return count

    def __repr__(self) -> str:
        return (f"RevolvingContext(items={self._item_count()}, "
                f"tokens={self._total_tokens()}/{self.token_budget})")
