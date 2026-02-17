"""Maintenance sweep — graph health analysis → quest generation."""

import uuid
from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .sandbox_matrix import SandboxMatrix


async def maintenance_sweep(matrix: "SandboxMatrix") -> list[dict]:
    """
    Scan for graph health issues. Returns quest candidates.

    Checks (in priority order):
    1. find_orphan_entities()    → entities with mentions but no relationships
    2. find_stale_entities()     → entities not updated in 30+ days with active mentions
    3. find_fragmented_entities()→ entities with high mention count but sparse profile
    4. find_contradictions()     → DECISION nodes with contradicting content in same cluster
    5. find_drifting_clusters()  → clusters with avg lock-in below 0.20
    6. find_unreflected_sessions()→ OUTCOME nodes with no linked INSIGHT/REFLECTION

    Each returns:
    {
        "quest_type": "scavenger" | "treasure_hunt" | "contract" | "side",
        "priority": "low" | "medium" | "high" | "urgent",
        "title": str,
        "subtitle": str,
        "objective": str,
        "source": str,  # which check generated this
        "target_entities": [entity_id, ...],
        "target_nodes": [node_id, ...],
        "target_clusters": [cluster_id, ...],
        "journal_prompt": str | None,
    }
    """
    candidates = []

    # 1. Orphan entities (mentions but no relationships)
    candidates.extend(await find_orphan_entities(matrix))

    # 2. Stale entities (not updated in 30+ days)
    candidates.extend(await find_stale_entities(matrix))

    # 3. Fragmented entities (high mentions, thin profile)
    candidates.extend(await find_fragmented_entities(matrix))

    # 4. Contradicting decisions in same cluster
    candidates.extend(await find_contradictions(matrix))

    # 5. Drifting clusters (avg lock-in < 0.20)
    candidates.extend(await find_drifting_clusters(matrix))

    # 6. Outcomes with no reflection
    candidates.extend(await find_unreflected_sessions(matrix))

    return candidates


async def find_orphan_entities(matrix: "SandboxMatrix") -> list[dict]:
    """Entities with mentions but no relationships → Scavenger quests."""
    quests = []

    # Get entities with mention_count > 0 but no relationships
    cursor = await matrix.execute("""
        SELECT e.* FROM entities e
        WHERE e.mention_count > 0
        AND NOT EXISTS (
            SELECT 1 FROM entity_relationships er
            WHERE er.from_id = e.id OR er.to_id = e.id
        )
    """)
    orphans = [dict(r) for r in await cursor.fetchall()]

    for entity in orphans:
        quests.append({
            "quest_type": "scavenger",
            "priority": "high" if entity["mention_count"] >= 5 else "medium",
            "title": f"Map {entity['name']}'s relationships",
            "subtitle": f"{entity['mention_count']} mentions, 0 connections",
            "objective": f"{entity['name']} appears {entity['mention_count']} times in your knowledge graph but has no mapped relationships. Who are they connected to? What roles do they play?",
            "source": "maintenance_sweep → orphan entity",
            "target_entities": [entity["id"]],
            "target_nodes": [],
            "target_clusters": [],
            "journal_prompt": None,
        })

    return quests


async def find_stale_entities(matrix: "SandboxMatrix") -> list[dict]:
    """Entities not updated in 30+ days with active mentions → Treasure Hunt quests."""
    quests = []
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=30)).isoformat()

    cursor = await matrix.execute("""
        SELECT e.* FROM entities e
        WHERE e.mention_count > 0
        AND e.updated_at < ?
        ORDER BY e.mention_count DESC
        LIMIT 5
    """, (cutoff,))
    stale = [dict(r) for r in await cursor.fetchall()]

    for entity in stale:
        updated_dt = datetime.fromisoformat(entity["updated_at"])
        days_old = (now - updated_dt).days

        quests.append({
            "quest_type": "treasure_hunt",
            "priority": "medium",
            "title": f"Refresh {entity['name']}'s profile",
            "subtitle": f"Last updated {days_old} days ago",
            "objective": f"{entity['name']} hasn't been updated in {days_old} days. Review recent mentions and update their profile with new information.",
            "source": "maintenance_sweep → stale entity",
            "target_entities": [entity["id"]],
            "target_nodes": [],
            "target_clusters": [],
            "journal_prompt": None,
        })

    return quests


async def find_fragmented_entities(matrix: "SandboxMatrix") -> list[dict]:
    """Entities with high mention count but sparse profile → Scavenger quests."""
    quests = []

    # Sparse = profile is NULL or core_facts is empty
    cursor = await matrix.execute("""
        SELECT e.* FROM entities e
        WHERE e.mention_count >= 5
        AND (e.profile IS NULL OR e.profile = '' OR e.core_facts = '{}')
        ORDER BY e.mention_count DESC
        LIMIT 5
    """)
    fragmented = [dict(r) for r in await cursor.fetchall()]

    for entity in fragmented:
        quests.append({
            "quest_type": "scavenger",
            "priority": "high",
            "title": f"Who is {entity['name']}?",
            "subtitle": f"{entity['mention_count']} mentions, sparse profile",
            "objective": f"{entity['name']} appears {entity['mention_count']} times but has an incomplete profile. What do you know about them? Fill in the gaps.",
            "source": "maintenance_sweep → fragmented entity",
            "target_entities": [entity["id"]],
            "target_nodes": [],
            "target_clusters": [],
            "journal_prompt": None,
        })

    return quests


async def find_contradictions(matrix: "SandboxMatrix") -> list[dict]:
    """DECISION nodes with contradicting keywords in same cluster → Contract quests."""
    quests = []

    # Simple heuristic: look for DECISION nodes in same cluster with opposite keywords
    contradiction_keywords = [
        ("use", "avoid"),
        ("implement", "skip"),
        ("adopt", "reject"),
        ("switch", "keep"),
        ("migrate", "stay"),
    ]

    clusters = await matrix.get_clusters()
    for cluster in clusters:
        members = await matrix.get_cluster_members(cluster["id"])
        decisions = [m for m in members if m["type"] == "DECISION"]

        if len(decisions) < 2:
            continue

        # Check for contradictions
        for word1, word2 in contradiction_keywords:
            nodes_with_1 = [d for d in decisions if word1.lower() in d["content"].lower()]
            nodes_with_2 = [d for d in decisions if word2.lower() in d["content"].lower()]

            if nodes_with_1 and nodes_with_2:
                quests.append({
                    "quest_type": "contract",
                    "priority": "urgent",
                    "title": f"Resolve {cluster['name']} crossroads",
                    "subtitle": f"Contradicting decisions: '{word1}' vs '{word2}'",
                    "objective": f"The {cluster['name']} cluster contains contradicting decisions. Review the context and resolve which path to take.",
                    "source": "maintenance_sweep → contradicting decisions",
                    "target_entities": [],
                    "target_nodes": [n["id"] for n in nodes_with_1 + nodes_with_2],
                    "target_clusters": [cluster["id"]],
                    "journal_prompt": None,
                })
                break  # One quest per cluster

    return quests


async def find_drifting_clusters(matrix: "SandboxMatrix") -> list[dict]:
    """Clusters with avg lock-in < 0.20 → Treasure Hunt quests."""
    quests = []

    cursor = await matrix.execute("""
        SELECT * FROM clusters
        WHERE lock_in < 0.20
        ORDER BY lock_in ASC
        LIMIT 5
    """)
    drifting = [dict(r) for r in await cursor.fetchall()]

    for cluster in drifting:
        members = await matrix.get_cluster_members(cluster["id"])

        quests.append({
            "quest_type": "treasure_hunt",
            "priority": "medium",
            "title": f"The {cluster['name']} cluster is fading",
            "subtitle": f"Lock-in: {cluster['lock_in']:.2f} — reinforce or let go",
            "objective": f"The {cluster['name']} cluster has {len(members)} nodes but low lock-in ({cluster['lock_in']:.2f}). Review its contents and decide: reinforce what matters or prune what doesn't.",
            "source": "maintenance_sweep → drifting cluster",
            "target_entities": [],
            "target_nodes": [m["id"] for m in members[:5]],  # Top 5 nodes
            "target_clusters": [cluster["id"]],
            "journal_prompt": None,
        })

    return quests


async def find_unreflected_sessions(matrix: "SandboxMatrix") -> list[dict]:
    """OUTCOME nodes with no linked INSIGHT/REFLECTION → Side quests."""
    quests = []

    # Get OUTCOME nodes
    cursor = await matrix.execute("""
        SELECT * FROM nodes
        WHERE type = 'OUTCOME'
        ORDER BY created_at DESC
        LIMIT 10
    """)
    outcomes = [dict(r) for r in await cursor.fetchall()]

    for outcome in outcomes:
        # Check if there's a linked INSIGHT/REFLECTION
        neighbors = await matrix.get_neighbors(outcome["id"], depth=1)
        has_reflection = any(
            n["type"] in ("INSIGHT", "OBSERVATION")
            and n["edge_relationship"] in ("reflects_on", "synthesizes")
            for n in neighbors
        )

        if not has_reflection:
            quests.append({
                "quest_type": "side",
                "priority": "low",
                "title": f"Journal about: {outcome['content'][:40]}...",
                "subtitle": "Unreflected outcome",
                "objective": f"You recorded an outcome but haven't reflected on it. What did you learn? What insights emerged?",
                "source": "maintenance_sweep → unreflected outcome",
                "target_entities": [],
                "target_nodes": [outcome["id"]],
                "target_clusters": [],
                "journal_prompt": f"Reflect on this outcome: {outcome['content']}\n\nWhat insights emerged? What would you do differently next time?",
            })

    return quests[:3]  # Limit to 3 side quests
