"""
Transcript Resolver - Phase 2: Merge, Dedup, Link

After extraction across all conversations:
1. Entity resolution - merge entities by canonical name, deduplicate
2. Node deduplication - cluster by embedding similarity (0.93 threshold), type+date aware
3. Cross-conversation edge discovery - embedding + type-pair heuristics
4. Edge disambiguation - LLM resolves DECISION↔DECISION ambiguity

Produces clean, deduplicated entity graph ready for commit.
"""

import asyncio
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
from datetime import datetime


class TranscriptResolver:
    """Resolve entities, deduplicate nodes, discover cross-conversation edges."""

    # Type-pair heuristics for edge classification
    TYPE_PAIR_HEURISTICS = {
        ("PROBLEM", "DECISION"): "clarifies",
        ("PROBLEM", "PROBLEM"): "related_to",
        ("DECISION", "ACTION"): "enables",
        ("DECISION", "DECISION"): "NEEDS_LLM",  # Ambiguous, requires LLM
        ("ACTION", "OUTCOME"): "depends_on",
        ("FACT", "FACT"): "related_to",
        ("INSIGHT", "DECISION"): "clarifies",
        ("INSIGHT", "INSIGHT"): "related_to",
        ("OBSERVATION", "FACT"): "clarifies",
        ("OBSERVATION", "DECISION"): "clarifies",
        ("FACT", "DECISION"): "enables",
        ("OUTCOME", "INSIGHT"): "derived_from",
        ("OUTCOME", "PROBLEM"): "enables",
    }

    def __init__(self, llm_client=None, embedding_fn=None):
        """
        Initialize resolver.

        Args:
            llm_client: LLM client for edge disambiguation (optional)
            embedding_fn: Function that takes text and returns embedding vector (optional)
        """
        self.llm_client = llm_client
        self.embedding_fn = embedding_fn

    # ========================================================================
    # Entity Resolution
    # ========================================================================

    def resolve_entities(self, all_extractions: List[Dict]) -> List[Dict]:
        """
        Merge entity mentions across all conversations.

        Args:
            all_extractions: List of extraction dicts from multiple conversations

        Returns:
            List of merged entity dicts with:
            - name: canonical name
            - type: entity type
            - aliases: set of all aliases
            - facts_timeline: chronological list of facts learned
            - conversations: list of conversation UUIDs
            - mention_count: total mentions across all conversations
            - type_conflicts: list of type mismatches (if any)
        """
        entity_map = {}  # canonical_name -> merged entity

        for extraction in all_extractions:
            convo_uuid = extraction.get("conversation_uuid", "unknown")
            convo_date = extraction.get("conversation_date", "")

            for entity in extraction.get("entities", []):
                # Canonicalize name (lowercase, strip spaces)
                key = self._canonicalize_name(entity.get("name", ""))
                if not key:
                    continue

                # Initialize if new
                if key not in entity_map:
                    entity_map[key] = {
                        "name": entity["name"],  # Keep original capitalization
                        "type": entity.get("type", "project"),
                        "aliases": set(),
                        "facts_timeline": [],
                        "conversations": [],
                        "mention_count": 0,
                    }

                merged = entity_map[key]

                # Merge aliases
                if entity.get("aliases"):
                    merged["aliases"].update(entity["aliases"])

                # Add to facts timeline
                facts = entity.get("facts_learned", [])
                if facts:
                    merged["facts_timeline"].append({
                        "date": convo_date,
                        "facts": facts if isinstance(facts, list) else [facts],
                        "source": convo_uuid,
                    })

                # Track conversations and mentions
                if convo_uuid not in merged["conversations"]:
                    merged["conversations"].append(convo_uuid)
                merged["mention_count"] += 1

                # Detect type conflicts
                if entity.get("type") and entity["type"] != merged["type"]:
                    if "type_conflicts" not in merged:
                        merged["type_conflicts"] = []
                    merged["type_conflicts"].append({
                        "claimed_type": entity["type"],
                        "source": convo_uuid,
                    })

        # Convert to list
        entities = []
        for canonical_name, entity in entity_map.items():
            entity["aliases"] = list(entity["aliases"])
            entity["canonical_name"] = canonical_name
            entities.append(entity)

        return entities

    def _canonicalize_name(self, name: str) -> str:
        """Canonicalize entity name for deduplication."""
        return name.lower().strip().replace("  ", " ")

    # ========================================================================
    # Node Deduplication
    # ========================================================================

    async def deduplicate_nodes(
        self,
        all_nodes: List[Dict],
        similarity_threshold: float = 0.93,
    ) -> List[Dict]:
        """
        Deduplicate nodes by embedding similarity with type+date awareness.

        Args:
            all_nodes: All nodes from all extractions
            similarity_threshold: Cosine similarity threshold (0.93 recommended)

        Returns:
            Deduplicated list of nodes with merged provenance
        """
        if not self.embedding_fn:
            # No embedding function, skip deduplication
            return all_nodes

        # Generate embeddings
        contents = [n.get("content", "") for n in all_nodes]
        embeddings = await self._embed_batch(contents)

        # Cluster by similarity
        clusters = self._cluster_by_similarity(
            embeddings,
            threshold=similarity_threshold
        )

        # Deduplicate within clusters (type+date aware)
        deduped = []
        for cluster_indices in clusters:
            if len(cluster_indices) == 1:
                # Single node, keep as-is
                deduped.append(all_nodes[cluster_indices[0]])
            else:
                # Multiple similar nodes - check type and date
                sub_clusters = self._split_by_type_and_date(
                    cluster_indices,
                    all_nodes
                )

                for sub_cluster in sub_clusters:
                    if len(sub_cluster) == 1:
                        deduped.append(all_nodes[sub_cluster[0]])
                    else:
                        # Merge nodes in sub-cluster
                        merged = self._merge_nodes(
                            [all_nodes[i] for i in sub_cluster]
                        )
                        deduped.append(merged)

        return deduped

    def _split_by_type_and_date(
        self,
        cluster_indices: List[int],
        all_nodes: List[Dict]
    ) -> List[List[int]]:
        """
        Within a similarity cluster, group by type + month.

        Only merge nodes of same type from same month.
        """
        groups = defaultdict(list)

        for idx in cluster_indices:
            node = all_nodes[idx]
            node_type = node.get("type", "FACT")
            node_date = node.get("source_date", "")[:7]  # YYYY-MM

            key = (node_type, node_date)
            groups[key].append(idx)

        return list(groups.values())

    def _merge_nodes(self, nodes: List[Dict]) -> Dict:
        """
        Merge multiple duplicate nodes into one.

        Strategy: Keep highest confidence, combine sources.
        """
        # Sort by confidence (highest first)
        sorted_nodes = sorted(
            nodes,
            key=lambda n: n.get("confidence", 0),
            reverse=True
        )

        # Start with highest confidence node
        merged = sorted_nodes[0].copy()

        # Combine provenance sources
        merged["provenance_sources"] = [
            {
                "conversation_uuid": n.get("source_conversation", ""),
                "confidence": n.get("confidence", 0),
            }
            for n in nodes
        ]

        # Mark as merged
        merged["merged_from_count"] = len(nodes)

        return merged

    async def _embed_batch(self, texts: List[str]) -> List:
        """Generate embeddings for a batch of texts."""
        if not self.embedding_fn:
            raise ValueError("No embedding function provided")

        # Call the embedding function
        result = self.embedding_fn(texts)

        # If result is a coroutine, await it
        if asyncio.iscoroutine(result):
            return await result
        else:
            return result

    def _cluster_by_similarity(
        self,
        embeddings: List,
        threshold: float
    ) -> List[List[int]]:
        """
        Cluster embeddings by cosine similarity.

        Returns: List of clusters (each cluster is list of indices)
        """
        n = len(embeddings)
        visited = [False] * n
        clusters = []

        for i in range(n):
            if visited[i]:
                continue

            # Start new cluster
            cluster = [i]
            visited[i] = True

            # Find all similar nodes
            for j in range(i + 1, n):
                if visited[j]:
                    continue

                sim = self._cosine_similarity(embeddings[i], embeddings[j])
                if sim >= threshold:
                    cluster.append(j)
                    visited[j] = True

            clusters.append(cluster)

        return clusters

    def _cosine_similarity(self, vec1, vec2) -> float:
        """Calculate cosine similarity between two vectors."""
        import math

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    # ========================================================================
    # Cross-Conversation Edge Discovery
    # ========================================================================

    async def discover_cross_edges(
        self,
        all_nodes: List[Dict],
        similarity_threshold: float = 0.76,
        max_edges_per_node: int = 5,
    ) -> List[Dict]:
        """
        Discover edges between nodes from different conversations.

        Args:
            all_nodes: All nodes (after deduplication)
            similarity_threshold: Minimum similarity to consider
            max_edges_per_node: Cap edges per node (prevent hubs)

        Returns:
            List of edge dicts
        """
        if not self.embedding_fn:
            return []

        # Generate embeddings
        contents = [n.get("content", "") for n in all_nodes]
        embeddings = await self._embed_batch(contents)

        edges = []
        edge_count = defaultdict(int)  # Track edges per node

        for i, node_a in enumerate(all_nodes):
            # Check if node already has too many edges
            max_for_this_node = self._max_edges_for_era(
                node_a.get("extraction_era", "PRE_LUNA")
            )

            if edge_count[i] >= max_for_this_node:
                continue

            # Find similar nodes from different conversations
            similarities = [
                (j, self._cosine_similarity(embeddings[i], embeddings[j]))
                for j in range(len(embeddings))
                if j != i
            ]

            # Filter by threshold and different conversation
            candidates = [
                (j, sim) for j, sim in similarities
                if sim >= similarity_threshold
                and all_nodes[j].get("source_conversation") != node_a.get("source_conversation")
                and edge_count[j] < max_edges_per_node
            ]

            # Sort by similarity, take top 3
            candidates.sort(key=lambda x: x[1], reverse=True)
            candidates = candidates[:3]

            for j, sim in candidates:
                node_b = all_nodes[j]

                # Classify edge type
                edge_type = self._classify_edge_type(node_a, node_b)

                edges.append({
                    "from_node_id": node_a.get("_id", i),
                    "to_node_id": node_b.get("_id", j),
                    "edge_type": edge_type,
                    "strength": sim * 0.6,  # Discount cross-conversation edges
                    "source": "cross_conversation_discovery",
                })

                edge_count[i] += 1
                edge_count[j] += 1

        return edges

    def _max_edges_for_era(self, era: str) -> int:
        """Era-tiered edge caps."""
        if era == "LUNA_LIVE":
            return 8
        elif era == "LUNA_DEV":
            return 6
        else:
            return 5

    def _classify_edge_type(self, node_a: Dict, node_b: Dict) -> str:
        """Classify edge type based on node types using heuristics."""
        type_a = node_a.get("type", "FACT")
        type_b = node_b.get("type", "FACT")

        pair = (type_a, type_b)
        reverse_pair = (type_b, type_a)

        if pair in self.TYPE_PAIR_HEURISTICS:
            result = self.TYPE_PAIR_HEURISTICS[pair]
        elif reverse_pair in self.TYPE_PAIR_HEURISTICS:
            result = self.TYPE_PAIR_HEURISTICS[reverse_pair]
        else:
            result = "related_to"

        if result == "NEEDS_LLM":
            # For now, default to related_to
            # TODO: Batch these for LLM disambiguation
            return "related_to"

        return result

    # ========================================================================
    # Validation
    # ========================================================================

    def validate_edge(self, edge: Dict, all_nodes: Dict) -> bool:
        """Validate edge quality."""
        # No self-loops
        if edge["from_node_id"] == edge["to_node_id"]:
            return False

        # Strength floor
        if edge.get("strength", 0) < 0.15:
            return False

        # Temporal sanity for "enables" edges
        if edge["edge_type"] == "enables":
            from_node = all_nodes.get(edge["from_node_id"])
            to_node = all_nodes.get(edge["to_node_id"])

            if from_node and to_node:
                from_date = from_node.get("source_date", "")
                to_date = to_node.get("source_date", "")

                # Can't enable something that happened before you
                if from_date > to_date:
                    return False

        return True
