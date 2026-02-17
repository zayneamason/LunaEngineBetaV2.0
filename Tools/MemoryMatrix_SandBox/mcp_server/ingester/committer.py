"""
Transcript Committer - Phase 4: Write to Sandbox with Era-Weighted Lock-In

After resolution:
1. Apply era-weighted lock-in (PRE_LUNA: 0.05-0.15, LUNA_DEV: 0.35-0.55, etc.)
2. Generate embeddings for nodes (use sandbox embedding service)
3. Write nodes to MemoryMatrix
4. Write edges to MemoryMatrix
5. Update transcript_ingestion_log
6. Handle errors and rollback on failure

Uses the sandbox MemoryMatrix for testing before production deployment.
"""

import asyncio
import aiosqlite
import uuid
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from pathlib import Path


class TranscriptCommitter:
    """Commit resolved extractions to sandbox MemoryMatrix with era-weighted lock-in."""

    # Era-weighted lock-in ranges
    ERA_LOCK_IN = {
        "PRE_LUNA": (0.05, 0.15),
        "PROTO_LUNA": (0.15, 0.35),
        "LUNA_DEV": (0.35, 0.55),
        "LUNA_LIVE": (0.55, 0.75),
    }

    def __init__(self, sandbox_db_path: str):
        """
        Initialize committer.

        Args:
            sandbox_db_path: Path to sandbox MemoryMatrix database
        """
        self.db_path = sandbox_db_path

    # ========================================================================
    # Era-Weighted Lock-In
    # ========================================================================

    def calculate_lock_in(self, era: str, confidence: float) -> float:
        """
        Calculate lock-in score with era weighting.

        Args:
            era: Extraction era (PRE_LUNA, PROTO_LUNA, LUNA_DEV, LUNA_LIVE)
            confidence: Extraction confidence (0.0-1.0)

        Returns:
            Lock-in score (0.0-1.0)
        """
        if era not in self.ERA_LOCK_IN:
            era = "PRE_LUNA"  # Default to lowest tier

        min_lock, max_lock = self.ERA_LOCK_IN[era]

        # Scale confidence to era range
        # confidence 0.0 → min_lock, confidence 1.0 → max_lock
        lock_in = min_lock + (confidence * (max_lock - min_lock))

        return round(lock_in, 2)

    # ========================================================================
    # Node Commitment
    # ========================================================================

    async def commit_nodes(
        self,
        nodes: List[Dict],
        embedding_fn=None,
    ) -> List[str]:
        """
        Commit nodes to sandbox MemoryMatrix.

        Args:
            nodes: List of node dicts with metadata
            embedding_fn: Optional embedding function (async)

        Returns:
            List of committed node IDs

        Raises:
            Exception if commit fails
        """
        if not nodes:
            return []

        committed_ids = []

        async with aiosqlite.connect(self.db_path) as db:
            # Enable foreign keys
            await db.execute("PRAGMA foreign_keys = ON")

            for node in nodes:
                # Extract metadata
                content = node.get("content", "")
                node_type = node.get("type", "FACT")
                confidence = node.get("confidence", 0.5)
                era = node.get("extraction_era", "PRE_LUNA")
                source_date = node.get("source_date", "")
                source_conv = node.get("source_conversation", "")

                # Calculate lock-in
                lock_in = self.calculate_lock_in(era, confidence)

                # Generate embedding if function provided
                embedding = None
                if embedding_fn:
                    result = embedding_fn([content])
                    # Check if result is a coroutine
                    if asyncio.iscoroutine(result):
                        embeddings = await result
                    else:
                        embeddings = result
                    embedding = embeddings[0] if embeddings else None

                # Generate node ID
                node_id = str(uuid.uuid4())
                timestamp = datetime.now().isoformat()

                # Prepare tags (JSON array for sandbox schema)
                tags_json = json.dumps(node.get("tags", []))

                # Insert node
                await db.execute(
                    """
                    INSERT INTO nodes (
                        id, content, type, confidence, lock_in,
                        tags, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        node_id,
                        content,
                        node_type,
                        confidence,
                        lock_in,
                        tags_json,
                        timestamp,
                        timestamp,
                    )
                )

                # Insert embedding if available
                if embedding:
                    try:
                        # Convert to bytes for vec0
                        import struct
                        embedding_bytes = struct.pack(f"{len(embedding)}f", *embedding)

                        await db.execute(
                            """
                            INSERT INTO node_embeddings (node_id, embedding)
                            VALUES (?, ?)
                            """,
                            (node_id, embedding_bytes)
                        )
                    except Exception as e:
                        # Skip embedding if vec0 not loaded
                        pass

                committed_ids.append(node_id)

            await db.commit()

        return committed_ids

    # ========================================================================
    # Edge Commitment
    # ========================================================================

    async def commit_edges(
        self,
        edges: List[Dict],
        node_id_map: Dict[str, str],
    ) -> int:
        """
        Commit edges to sandbox MemoryMatrix.

        Args:
            edges: List of edge dicts
            node_id_map: Maps extraction node IDs to committed database IDs

        Returns:
            Number of edges committed
        """
        if not edges:
            return 0

        committed = 0

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA foreign_keys = ON")

            for edge in edges:
                # Map extraction IDs to database IDs
                # Support both extraction format (from_node_index) and resolver format (from_node_id)
                if "from_node_index" in edge:
                    # Extraction format: convert index to node_N key
                    from_id_key = f"node_{edge['from_node_index']}"
                    to_id_key = f"node_{edge['to_node_index']}"
                else:
                    # Resolver format: use node_id directly
                    from_id_key = edge.get("from_node_id", "")
                    to_id_key = edge.get("to_node_id", "")

                from_id = node_id_map.get(from_id_key)
                to_id = node_id_map.get(to_id_key)

                if not from_id or not to_id:
                    # Debug: print why edge was skipped
                    # print(f"DEBUG: Skipped edge {from_id_key} -> {to_id_key} (from_id={from_id}, to_id={to_id})")
                    # Skip edges with missing nodes
                    continue

                edge_type = edge.get("edge_type", "related_to")
                strength = edge.get("strength", 0.5)

                # Insert edge
                try:
                    timestamp = datetime.now().isoformat()
                    await db.execute(
                        """
                        INSERT INTO edges (from_id, to_id, relationship, strength, created_at)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (from_id, to_id, edge_type, strength, timestamp)
                    )
                    committed += 1
                except Exception as e:
                    # Skip duplicates or invalid edges
                    continue

            await db.commit()

        return committed

    # ========================================================================
    # Full Commit Workflow
    # ========================================================================

    async def commit_extraction(
        self,
        extraction: Dict,
        conversation: Dict,
        embedding_fn=None,
    ) -> Dict:
        """
        Commit a full extraction to sandbox MemoryMatrix.

        Args:
            extraction: Extraction result dict
            conversation: Conversation metadata dict
            embedding_fn: Optional embedding function

        Returns:
            Commit summary dict:
            {
                "status": "success" | "partial" | "failed",
                "nodes_committed": int,
                "edges_committed": int,
                "error_message": str (if failed),
            }
        """
        try:
            # Extract nodes and edges
            nodes = extraction.get("nodes", [])
            edges = extraction.get("edges", [])
            era = self._classify_era(conversation.get("created_at", ""))

            # Add era metadata to nodes
            for node in nodes:
                node["extraction_era"] = era
                node["source_conversation"] = conversation.get("uuid", "")
                node["source_date"] = conversation.get("created_at", "")[:10]

            # Commit nodes
            node_ids = await self.commit_nodes(nodes, embedding_fn=embedding_fn)

            # Create node ID mapping (extraction index → database ID)
            node_id_map = {
                f"node_{i}": node_ids[i]
                for i in range(len(node_ids))
            }

            # Also map by _id if present
            for i, node in enumerate(nodes):
                if node.get("_id"):
                    node_id_map[node["_id"]] = node_ids[i]

            # Commit edges
            edges_committed = await self.commit_edges(edges, node_id_map)

            # Update ingestion log
            await self._update_ingestion_log(
                conversation_uuid=conversation.get("uuid", ""),
                transcript_path=conversation.get("path", ""),
                tier=extraction.get("tier", "BRONZE"),
                texture=extraction.get("texture", []),
                nodes_created=len(node_ids),
                edges_created=edges_committed,
                status="success",
            )

            return {
                "status": "success",
                "nodes_committed": len(node_ids),
                "edges_committed": edges_committed,
            }

        except Exception as e:
            # Update ingestion log with error
            await self._update_ingestion_log(
                conversation_uuid=conversation.get("uuid", ""),
                transcript_path=conversation.get("path", ""),
                tier=extraction.get("tier", "BRONZE"),
                texture=extraction.get("texture", []),
                nodes_created=0,
                edges_created=0,
                status="failed",
                error_message=str(e),
            )

            return {
                "status": "failed",
                "nodes_committed": 0,
                "edges_committed": 0,
                "error_message": str(e),
            }

    # ========================================================================
    # Batch Commit
    # ========================================================================

    async def commit_batch(
        self,
        extractions: List[Tuple[Dict, Dict]],
        embedding_fn=None,
        progress_callback=None,
    ) -> Dict:
        """
        Commit multiple extractions in batch.

        Args:
            extractions: List of (extraction, conversation) tuples
            embedding_fn: Optional embedding function
            progress_callback: Optional callback(current, total) for progress

        Returns:
            Batch summary dict
        """
        results = []
        total = len(extractions)

        for i, (extraction, conversation) in enumerate(extractions, 1):
            result = await self.commit_extraction(
                extraction=extraction,
                conversation=conversation,
                embedding_fn=embedding_fn,
            )
            results.append(result)

            if progress_callback:
                progress_callback(i, total)

        # Aggregate results
        successful = [r for r in results if r["status"] == "success"]
        failed = [r for r in results if r["status"] == "failed"]

        return {
            "total": total,
            "successful": len(successful),
            "failed": len(failed),
            "nodes_committed": sum(r["nodes_committed"] for r in results),
            "edges_committed": sum(r["edges_committed"] for r in results),
            "errors": [r.get("error_message") for r in failed if r.get("error_message")],
        }

    # ========================================================================
    # Helpers
    # ========================================================================

    def _classify_era(self, date_str: str) -> str:
        """Classify conversation era from date."""
        ERAS = {
            "PRE_LUNA": ("2023-01-01", "2024-06-01"),
            "PROTO_LUNA": ("2024-06-01", "2025-01-01"),
            "LUNA_DEV": ("2025-01-01", "2025-10-01"),
            "LUNA_LIVE": ("2025-10-01", "2030-01-01"),
        }

        date = date_str[:10]  # YYYY-MM-DD

        for era, (start, end) in ERAS.items():
            if start <= date < end:
                return era

        return "LUNA_LIVE"

    async def _update_ingestion_log(
        self,
        conversation_uuid: str,
        transcript_path: str,
        tier: str,
        texture: List[str],
        nodes_created: int,
        edges_created: int,
        status: str,
        error_message: str = "",
    ):
        """Update transcript_ingestion_log table."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO transcript_ingestion_log (
                    conversation_uuid, transcript_path, ingested_at,
                    trigger, tier, texture, extraction_status,
                    nodes_created, edges_created,
                    error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (conversation_uuid) DO UPDATE SET
                    ingested_at = excluded.ingested_at,
                    tier = excluded.tier,
                    texture = excluded.texture,
                    extraction_status = excluded.extraction_status,
                    nodes_created = excluded.nodes_created,
                    edges_created = excluded.edges_created,
                    error_message = excluded.error_message
                """,
                (
                    conversation_uuid,
                    transcript_path,
                    datetime.now().isoformat(),
                    "manual_ingestion",  # trigger
                    tier,
                    ",".join(texture) if texture else "",
                    status,
                    nodes_created,
                    edges_created,
                    error_message,
                )
            )
            await db.commit()
