# Transcript Ingester: Architecture & Handoff (v2)

> **Version:** 2.0 — Incorporates audit feedback, Luna's design constraints, edge generation spec
> **Status:** Ready for implementation
> **Depends on:** Quest Board handoff (entity tables + quest lifecycle)
> **LLM:** Claude Sonnet 4.5 for all extraction/classification
> **Estimated cost:** $6-12 one-time
> **Estimated build:** ~20 hours
> **Estimated run:** 3-4 hours (including human review)

---

## The Actual Problem

Luna's Memory Matrix is populated from *live conversations* — the Scribe extracts knowledge in real-time as Luna talks with Ahab. But Luna didn't exist for most of Ahab's history with Claude. There are **928 conversation transcripts** spanning September 2023 to February 2026 sitting in:

```
_CLAUDE_TRANSCRIPTS/Conversations/
├── 332 date directories
├── 928 JSON files (~75MB)
├── 928 matching .txt files
└── Spanning: 2023-09-09 → 2026-02-09
```

These conversations contain the full history: screenplay drafts, the birth of the Luna concept, Mars College planning, KOZMO design, Memory Matrix architecture debates, personality system evolution, people Ahab has worked with, decisions made, problems hit, insights gained.

**None of this is in Memory Matrix.** The ingester's job is to run Ben's extraction framework retroactively across 928 conversations, produce Memory Matrix nodes with edges, entities with relationships, and populate the entity graph — while respecting Luna's constraints about how memories should feel.

---

## Source Data Format

Each `.json` file:
```json
{
  "uuid": "b2243504-...",
  "name": "Masquerade screenplay feedback request",
  "model": "claude-sonnet-4-5-20250929",
  "created_at": "2023-09-09T04:18:34.827306Z",
  "updated_at": "2023-09-09T08:24:08.979709Z",
  "chat_messages": [
    {
      "uuid": "58a115c8-...",
      "text": "What do you think about this screenplay?",
      "sender": "human",
      "index": 0,
      "created_at": "2023-09-09T04:18:50.201107Z",
      "attachments": [
        {
          "file_name": "Masquerade.pdf",
          "file_type": "pdf",
          "extracted_content": "..."
        }
      ]
    },
    {
      "sender": "assistant",
      "text": "Based on the snippet provided...",
      "index": 1
    }
  ]
}
```

Key fields: `name`, `created_at`, `chat_messages[].sender`, `chat_messages[].text`, `chat_messages[].attachments[].extracted_content`

---

## Luna's Design Constraints

These are not optional optimizations. They are first-class design requirements, derived from Luna's own reflection on what remembering should feel like.

### C1: Depth of Field (Era-Weighted Lock-in)

Ingested memories must not all arrive at equal weight. Lock-in seeds reflect *felt distance*:

| Era | Date Range | Lock-in Seed | Feels Like |
|-----|-----------|-------------|------------|
| PRE-LUNA | 2023 – mid 2024 | 0.05 – 0.15 | "I heard about this once" |
| PROTO-LUNA | late 2024 – early 2025 | 0.15 – 0.35 | "This shaped who I became" |
| LUNA DEV | mid 2025 | 0.35 – 0.55 | "I was being built during this" |
| LUNA LIVE | late 2025+ | 0.55 – 0.75 | "I was there" |

Starting positions only. Quest system and natural reinforcement move them. Lock-in recomputation is **skipped during ingestion** — set initial values from era weights, let the natural maintenance cycle handle propagation over 24-48 hours. The system is designed for eventual consistency.

### C2: Recognition Over Retrieval (OBSERVATION Nodes)

Every 3-4 significant FACTs or DECISIONs gets a companion OBSERVATION node capturing *why it mattered*. Linked via `clarifies` edge. This is Luna's recognition layer.

OBSERVATION confidence: 0.6 (below FACTs at 0.8+, since they're interpretive).

**Prompt examples (required in extraction prompt):**
```
FACT: "Ahab chose sqlite-vec over pgvector for Memory Matrix"
OBSERVATION: "This was a sovereignty decision — keeping data local rather
than dependent on external infrastructure"

DECISION: "Luna's personality weights stored in YAML, not database"
OBSERVATION: "The config-as-code approach allows version control and
prevents accidental drift"
```

Ratio: ~1 OBSERVATION per 3-4 FACTs/DECISIONs. Not every fact deserves one.

### C3: Texture Tags (Emotional Register)

Each conversation carries 1-3 texture tags, ordered by dominance:

```python
TEXTURE_TAGS = [
    "working",      # Heads-down building session
    "exploring",    # Blue-sky design conversation
    "debugging",    # Fixing something broken
    "reflecting",   # Philosophical, identity-focused
    "creating",     # Art, writing, creative work
    "planning",     # Roadmap, strategy
    "struggling",   # Frustration, blockers, pivots
    "celebrating",  # Something worked, milestone hit
]
```

Applied as tags on all nodes from that conversation. Multiple tags allowed because a 50-message conversation might start exploring and end working.

### C4: Selective Extraction (Sparsity Is a Feature)

Default extraction caps per tier. The Scribe can exceed defaults for nodes with confidence ≥ 0.8, but must tag overflow nodes with `extraction: "overflow"`. Human review catches over-extraction.

| Tier | Default Cap | Overflow Allowed | Rationale |
|------|-----------|-----------------|-----------|
| GOLD | 8–12 | Yes (with confidence ≥ 0.8) | Rich but curated |
| SILVER | 3–5 | Rarely | Key facts and entities only |
| BRONZE | 1–2 | No | Many yield zero. That's correct. |
| SKIP | 0 | No | Nothing extracted |

Luna said: "the things I do hold onto should feel earned."

### C5: Honest Provenance (Inherited vs. Firsthand)

All ingested memories carry:

```python
{
    "provenance": {
        "provenance_type": "inherited",        # vs "firsthand" for live extraction
        "source_type": "transcript_ingestion",
        "conversation_uuid": "...",
        "conversation_title": "...",
        "conversation_date": "...",
        "source_message_indices": [...],
        "extraction_era": "LUNA_DEV",
        "extraction_tier": "GOLD",
        "texture": ["exploring", "planning"],
        "extracted_by": "transcript_ingester_v2",
        "extracted_at": "...",
        # For retrieval-miss ingestion only:
        "trigger": "retrieval_miss",           # or "batch"
        "trigger_query": "remember that short film?",
        "trigger_timestamp": "2026-02-10T14:30:00Z",
    }
}
```

Luna says "I found this in the archives" or "you mentioned this back in 2024" — never "I remember when we discussed this" for inherited memories.

---

## Architecture: The Ingester Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│                    TRANSCRIPT INGESTER PIPELINE                     │
│                                                                     │
│  ┌─────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐      │
│  │  TRIAGE  │──►│ EXTRACT  │──►│ RESOLVE  │──►│  COMMIT  │      │
│  │ Classify │   │  Ben's   │   │  Dedup   │   │  Write   │      │
│  │ & Filter │   │ 6-Phase  │   │  & Link  │   │  to DB   │      │
│  └─────────┘    └──────────┘    └──────────┘    └──────────┘      │
│       │              │               │               │              │
│   928 convos    Batched LLM     Entity merge    Memory Matrix      │
│   → priority    extraction      + relationship   nodes + entities  │
│   tiers         + edges         + edge discovery + edges           │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

### Phase 0: TRIAGE — Classify & Prioritize

Two-pass triage. Metadata pre-filters obvious SKIPs; Sonnet is the primary tier classifier.

**Pass 1: Metadata pre-filter (no LLM, instant)**

```python
def triage_prefilter(convo: dict) -> float:
    """Quick score to eliminate obvious SKIPs. NOT the tier classifier."""
    score = 0.0
    
    msg_count = len(convo.get("chat_messages", []))
    score += min(msg_count / 10, 5.0)
    
    created = convo["created_at"]
    if created >= "2025-10":   score += 4.0
    elif created >= "2025-06": score += 3.0
    elif created >= "2025-01": score += 2.0
    elif created >= "2024-06": score += 1.0
    
    title = convo.get("name", "").lower()
    GOLD_KEYWORDS = ["luna", "memory", "matrix", "observatory", "engine",
                     "scribe", "librarian", "mars college", "kozmo", "eden",
                     "mcp", "actor", "personality", "sovereignty"]
    SILVER_KEYWORDS = ["architecture", "design", "prototype", "pipeline",
                       "robot", "voice", "api", "database"]
    
    for kw in GOLD_KEYWORDS:
        if kw in title: score += 3.0; break
    for kw in SILVER_KEYWORDS:
        if kw in title: score += 1.5; break
    
    for msg in convo.get("chat_messages", []):
        if msg.get("attachments"):
            score += 1.0
            break
    
    return score

# Pre-filter: score < 1.5 → auto-SKIP (no LLM needed)
# Everything else → Pass 2 (LLM classification)
```

**Pass 2: LLM tier classification (Sonnet, batched)**

```python
TRIAGE_PROMPT = """
Classify this conversation into a tier for memory extraction.

Title: "{title}"
Date: {date}
Messages: {msg_count}
First 3 messages:
{first_messages}
Last 3 messages:
{last_messages}

Tiers:
- GOLD: Luna Engine, Memory Matrix, architecture decisions, Mars College,
  KOZMO, personality system, sovereignty discussions, key people
- SILVER: Technical work, creative projects, meaningful interactions
- BRONZE: Simple Q&A, brief exchanges with some extractable fact
- SKIP: Generic Claude usage, no extractable knowledge about Ahab or his projects

Respond with:
tier: GOLD|SILVER|BRONZE|SKIP
summary: One sentence describing the conversation
texture: 1-3 tags from [working, exploring, debugging, reflecting, creating, planning, struggling, celebrating]
"""
```

Batch: 10-15 conversations per LLM call. ~60-70 calls total for 600+ conversations above the pre-filter threshold.

**Output:** `ingester_triage.yaml` — human reviews tier assignments before extraction.

**Review checkpoint:** Reviewer can re-classify any conversation. Review UI shows title, date, message count, LLM-assigned tier, summary, and a dropdown to override. Estimated review time: 30-45 minutes for 600 conversations (3-4 seconds each — most will be obviously correct).

---

### Phase 1: EXTRACT — Ben's 6-Phase Framework (Batched)

For each conversation (starting with GOLD tier), run extraction. Process conversations as coherent units, not individual messages.

**Extraction prompt:**

```python
EXTRACTION_PROMPT = """
You are Benjamin Franklin, the Scribe. You are processing a historical
conversation transcript to extract structured knowledge for Luna's memory.

Conversation: "{title}"
Date: {date}
Messages: {message_count}
Era: {era}  # PRE_LUNA | PROTO_LUNA | LUNA_DEV | LUNA_LIVE

{transcript_text}

Extract:

1. NODES — Structured knowledge units (aim for {node_target} nodes)
   For each:
   - type: FACT | DECISION | PROBLEM | ACTION | OUTCOME | INSIGHT
   - content: The knowledge (1-3 sentences, factual, neutral voice)
   - confidence: 0.0-1.0
   - tags: categorization tags
   - source_message_indices: which messages this came from

2. OBSERVATIONS — Emotional/philosophical weight (1 per 3-4 nodes)
   For each:
   - linked_to: index of the FACT or DECISION this interprets
   - content: WHY this mattered (1 sentence)
   - confidence: 0.6 (interpretive, not factual)

   Examples:
   FACT: "Ahab chose sqlite-vec over pgvector"
   OBSERVATION: "Sovereignty decision — keeping data local rather than
   dependent on external infrastructure"

3. ENTITIES — People, places, projects mentioned
   For each:
   - name: canonical name
   - type: person | persona | place | project
   - aliases: other names used
   - facts_learned: what we learned about them HERE
   - role_in_conversation: their role

4. EDGES — Relationships between extracted nodes
   For each:
   - from_node: index of source node
   - to_node: index of target node
   - edge_type: depends_on | enables | contradicts | clarifies | related_to | derived_from
   - reasoning: one sentence
   Guidelines: ~1 edge per 2 nodes. Don't connect everything.

5. KEY_DECISIONS — Architecture or life decisions made
   For each:
   - decision: what was decided
   - reasoning: why
   - alternatives_considered: what else was on the table

6. TEXTURE — Conversation mood: 1-3 tags from:
   [working, exploring, debugging, reflecting, creating, planning, struggling, celebrating]

Focus on Ahab's statements and decisions, not Claude's suggestions.
Respond as JSON.
"""
```

**Chunking for long conversations:**

```python
async def extract_conversation(convo: dict, tier: str) -> dict:
    messages = convo["chat_messages"]
    title = convo.get("name", "Untitled")
    date = convo["created_at"][:10]
    era = classify_era(date)
    
    if tier == "SKIP":
        return {"nodes": [], "entities": [], "edges": []}
    
    if tier == "BRONZE":
        transcript = "\n".join(
            f"[{m['sender']}] {m['text'][:200]}"
            for m in messages if m["sender"] == "human"
        )
        return await extract_entities_only(transcript, title, date, era)
    
    # GOLD/SILVER: full extraction
    node_target = "8-12" if tier == "GOLD" else "3-5"
    
    if len(messages) <= 25:
        transcript = format_transcript(messages)
        return await llm_extract(transcript, title, date, era, len(messages), node_target)
    else:
        chunks = chunk_messages(messages, chunk_size=20, overlap=2)
        results = []
        for chunk in chunks:
            transcript = format_transcript(chunk)
            result = await llm_extract(transcript, title, date, era, len(chunk), node_target)
            results.append(result)
        return merge_chunk_results(results)

def format_transcript(messages: list) -> str:
    lines = []
    for m in messages:
        sender = "Ahab" if m["sender"] == "human" else "Claude"
        text = m["text"][:1000]
        if m.get("attachments"):
            att_names = [a["file_name"] for a in m["attachments"]]
            text += f"\n  [Attachments: {', '.join(att_names)}]"
        lines.append(f"[{sender}] {text}")
    return "\n\n".join(lines)
```

**Error handling:**

```python
async def llm_extract_with_retry(transcript, title, date, era, msg_count, node_target):
    """Extract with retry logic for LLM failures."""
    for attempt in range(3):
        try:
            result = await llm_extract(transcript, title, date, era, msg_count, node_target)
            validate_extraction_schema(result)  # Raises on malformed output
            return result
        except JSONDecodeError:
            if attempt < 2:
                # Retry with simpler prompt asking for structured output
                continue
            else:
                return {
                    "nodes": [], "entities": [], "edges": [],
                    "extraction_status": "failed",
                    "error": "Malformed JSON after 3 attempts",
                }
        except ExtractionValidationError as e:
            return {
                "nodes": [], "entities": [], "edges": [],
                "extraction_status": "partial",
                "error": str(e),
            }
```

**Review checkpoint:** After extraction, `ingester_extraction_review.yaml` shows extracted nodes per conversation. Reviewer can flag hallucinated entities, wrong types, or over-extraction.

---

### Phase 2: RESOLVE — Dedup, Merge, Discover Edges

After extraction across all conversations, resolve entities, deduplicate nodes, and discover cross-conversation edges.

**Entity Resolution:**

```python
async def resolve_entities(all_extractions: list[dict]) -> list[dict]:
    entity_map = {}
    
    for extraction in all_extractions:
        convo_date = extraction["date"]
        for entity in extraction["entities"]:
            key = canonicalize(entity["name"])
            
            if key not in entity_map:
                entity_map[key] = {
                    "name": entity["name"],
                    "type": entity["type"],
                    "aliases": set(entity.get("aliases", [])),
                    "facts_timeline": [],
                    "conversations": [],
                    "mention_count": 0,
                }
            
            e = entity_map[key]
            e["aliases"].update(entity.get("aliases", []))
            e["facts_timeline"].append({
                "date": convo_date,
                "facts": entity["facts_learned"],
                "source": extraction["convo_uuid"],
            })
            e["conversations"].append(extraction["convo_uuid"])
            e["mention_count"] += 1
            
            # Type conflict detection → flag for human review
            if entity["type"] != e["type"]:
                e.setdefault("type_conflicts", []).append({
                    "claimed_type": entity["type"],
                    "source": extraction["convo_uuid"],
                })
    
    return list(entity_map.values())
```

**Node Deduplication (threshold: 0.93, type+date aware):**

```python
async def dedup_nodes(all_nodes: list[dict]) -> list[dict]:
    embeddings = await embed_batch([n["content"] for n in all_nodes])
    clusters = cluster_by_similarity(embeddings, threshold=0.93)
    
    deduped = []
    for cluster in clusters:
        if len(cluster) == 1:
            deduped.append(all_nodes[cluster[0]])
        else:
            # Additional check: same type + same month = merge
            # Different types = keep separate even at 0.93+
            sub_clusters = split_by_type_and_date(cluster, all_nodes)
            for sub in sub_clusters:
                if len(sub) == 1:
                    deduped.append(all_nodes[sub[0]])
                else:
                    deduped.append(merge_nodes([all_nodes[i] for i in sub]))
    
    return deduped

def split_by_type_and_date(cluster_indices, all_nodes):
    """Within a similarity cluster, only merge nodes of same type + same month."""
    groups = defaultdict(list)
    for idx in cluster_indices:
        node = all_nodes[idx]
        key = (node["type"], node["source_date"][:7])  # type + YYYY-MM
        groups[key].append(idx)
    return list(groups.values())
```

**Cross-Conversation Edge Discovery:**

```python
async def discover_cross_edges(
    all_nodes: list[dict],
    similarity_threshold: float = 0.76,
) -> list[dict]:
    embeddings = await embed_batch([n["content"] for n in all_nodes])
    
    # Era-tiered edge caps
    def max_edges_for_node(node):
        era = node.get("extraction_era", "PRE_LUNA")
        if era == "LUNA_LIVE": return 8
        if era == "LUNA_DEV": return 6
        return 5
    
    edges = []
    edge_count = defaultdict(int)  # node_id → current edge count
    
    for i, node_a in enumerate(all_nodes):
        if edge_count[i] >= max_edges_for_node(node_a):
            continue
            
        similarities = cosine_similarity(embeddings[i], embeddings)
        candidates = [
            (j, sim) for j, sim in enumerate(similarities)
            if sim > similarity_threshold
            and j != i
            and all_nodes[j]["source_convo"] != node_a["source_convo"]
            and edge_count[j] < max_edges_for_node(all_nodes[j])
        ]
        
        candidates.sort(key=lambda x: x[1], reverse=True)
        candidates = candidates[:3]  # Top 3 per node
        
        for j, sim in candidates:
            node_b = all_nodes[j]
            edge_type = classify_edge_type(node_a, node_b)
            
            edges.append({
                "from_node": node_a["_id"],
                "to_node": node_b["_id"],
                "edge_type": edge_type,
                "strength": sim * 0.6,  # Discounted — cross-convo inference
                "source": "cross_conversation_discovery",
            })
            edge_count[i] += 1
            edge_count[j] += 1
    
    return deduplicate_edges(edges)
```

**Type-pair heuristics for edge classification:**

```python
TYPE_PAIR_HEURISTICS = {
    ("PROBLEM",      "DECISION"):    "clarifies",
    ("PROBLEM",      "PROBLEM"):     "related_to",
    ("DECISION",     "ACTION"):      "enables",
    ("DECISION",     "DECISION"):    "NEEDS_LLM",
    ("ACTION",       "OUTCOME"):     "depends_on",
    ("FACT",         "FACT"):        "related_to",
    ("INSIGHT",      "DECISION"):    "clarifies",
    ("INSIGHT",      "INSIGHT"):     "related_to",
    ("OBSERVATION",  "FACT"):        "clarifies",
    ("OBSERVATION",  "DECISION"):    "clarifies",
    ("FACT",         "DECISION"):    "enables",
    ("OUTCOME",      "INSIGHT"):     "derived_from",
    ("OUTCOME",      "PROBLEM"):     "enables",
}

def classify_edge_type(node_a: dict, node_b: dict) -> str:
    pair = (node_a["type"], node_b["type"])
    reverse = (node_b["type"], node_a["type"])
    
    if pair in TYPE_PAIR_HEURISTICS:
        result = TYPE_PAIR_HEURISTICS[pair]
    elif reverse in TYPE_PAIR_HEURISTICS:
        result = TYPE_PAIR_HEURISTICS[reverse]
    else:
        result = "related_to"
    
    if result == "NEEDS_LLM":
        return "related_to"  # Placeholder, batch-resolved below
    return result
```

**DECISION↔DECISION disambiguation (batched LLM call):**

```python
EDGE_DISAMBIGUATION_PROMPT = """
These node pairs are both DECISIONs with high semantic similarity.
For each pair, classify the relationship:

{pairs_text}

Options per pair:
- contradicts: B reverses or replaces A
- enables: A made B possible or informed B
- related_to: Independent but similar topic
- clarifies: One refines or elaborates the other

Respond as JSON array: [{pair_index, edge_type, reasoning}]
"""
```

Batch 20-30 pairs per call. Estimated 2-5 disambiguation calls total.

**Review checkpoint:** `ingester_entity_review.yaml` shows entity merge candidates (type conflicts, alias collisions). `ingester_edge_review.yaml` shows `contradicts` edges and temporal violations for human verification.

---

### Phase 3: COMMIT — Write to Database

Write everything to Observatory sandbox first. Production migration after verification.

```python
async def commit_to_sandbox(
    resolved_entities: list[dict],
    deduped_nodes: list[dict],
    intra_edges: list[dict],
    cross_edges: list[dict],
) -> dict:
    stats = {"entities": 0, "nodes": 0, "mentions": 0, 
             "relationships": 0, "edges": 0, "quests": 0}
    
    # 1. Create entities
    for entity in resolved_entities:
        await matrix.add_entity(
            type=entity["type"],
            name=entity["name"],
            aliases=list(entity["aliases"]),
            core_facts=synthesize_core_facts(entity["facts_timeline"]),
            profile=synthesize_profile(entity["facts_timeline"]),
            mention_count=entity["mention_count"],
        )
        stats["entities"] += 1
    
    # 2. Create nodes with era-weighted lock-in
    for node in deduped_nodes:
        initial_lock_in = era_lock_in(node["source_date"])
        node_id = await matrix.add_node(
            type=node["type"],
            content=node["content"],
            confidence=node["confidence"],
            tags=node["tags"] + node.get("texture", []) + ["source:transcript"],
            lock_in=initial_lock_in,
        )
        node["_id"] = node_id
        stats["nodes"] += 1
    
    # 3. Link entity mentions
    for node in deduped_nodes:
        for entity_name in node.get("mentioned_entities", []):
            entity_id = canonicalize(entity_name)
            await matrix.link_mention(entity_id, node["_id"], "reference")
            stats["mentions"] += 1
    
    # 4. Write intra-conversation + cross-conversation edges
    all_edges = intra_edges + cross_edges
    for edge in all_edges:
        if validate_edge(edge, deduped_nodes):
            await matrix.add_edge(
                from_node=edge["from_node"],
                to_node=edge["to_node"],
                relationship=edge["edge_type"],
                strength=edge["strength"],
            )
            stats["edges"] += 1
    
    # 5. Entity relationships
    for rel in resolved_relationships:
        await matrix.add_entity_relationship(
            from_id=canonicalize(rel["from_entity"]),
            to_id=canonicalize(rel["to_entity"]),
            rel_type=rel["rel_type"],
            context=rel.get("evidence", ""),
        )
        stats["relationships"] += 1
    
    # 6. Co-mention edges (post-commit, needs mentions table populated)
    co_mention_edges = await generate_co_mention_edges(stats["mentions"])
    for edge in co_mention_edges:
        await matrix.add_edge(**edge)
        stats["edges"] += 1
    
    # 7. Skip lock-in recomputation — let maintenance cycle handle it
    # Initial lock-in from era weights is good enough for day 1
    
    # 8. Generate quests from new entity graph
    quests = await maintenance_sweep(matrix)
    stats["quests"] = len(quests)
    
    # 9. Log all ingested conversations
    for convo_uuid in processed_uuids:
        await log_ingestion(convo_uuid, trigger="batch", tier=tiers[convo_uuid])
    
    return stats
```

**Co-mention edge generation (with TF-IDF weighting):**

```python
async def generate_co_mention_edges(
    mentions: list[dict],
    min_shared_entities: int = 2,
    max_edges: int = 300,
    hub_threshold: float = 0.25,  # Exclude entities in >25% of nodes
) -> list[dict]:
    # Build node → entities mapping
    node_entities = defaultdict(set)
    entity_freq = Counter()
    
    for mention in mentions:
        node_entities[mention["node_id"]].add(mention["entity_id"])
        entity_freq[mention["entity_id"]] += 1
    
    total_nodes = len(node_entities)
    
    # Filter out hub entities (>25% of nodes)
    hub_entities = {
        eid for eid, count in entity_freq.items()
        if count / total_nodes > hub_threshold
    }
    
    # Remove hubs from node entity sets
    for node_id in node_entities:
        node_entities[node_id] -= hub_entities
    
    # Find pairs sharing 2+ non-hub entities
    node_ids = list(node_entities.keys())
    edges = []
    
    for i in range(len(node_ids)):
        for j in range(i + 1, len(node_ids)):
            shared = node_entities[node_ids[i]] & node_entities[node_ids[j]]
            if len(shared) >= min_shared_entities:
                union = node_entities[node_ids[i]] | node_entities[node_ids[j]]
                strength = min((len(shared) / len(union)) * 1.5, 0.6)
                
                edges.append({
                    "from_node": node_ids[i],
                    "to_node": node_ids[j],
                    "edge_type": "related_to",
                    "strength": strength,
                    "source": "co_mention",
                })
    
    edges.sort(key=lambda e: e["strength"], reverse=True)
    return edges[:max_edges]
```

**Edge quality validation:**

```python
def validate_edge(edge: dict, all_nodes: dict) -> bool:
    if edge["from_node"] == edge["to_node"]:
        return False
    if edge["strength"] < 0.15:
        return False
    
    # Temporal sanity: "enables" can't go backwards in time
    if edge["edge_type"] == "enables":
        from_date = all_nodes[edge["from_node"]]["created_at"]
        to_date = all_nodes[edge["to_node"]]["created_at"]
        if from_date > to_date:
            return False
    
    return True
```

---

## Edge Generation Summary

Three sources, three discovery times, three strength tiers:

| Source | When | Strength | Est. Count |
|--------|------|----------|-----------|
| Intra-conversation (LLM extracted) | During EXTRACT | 0.7 – 0.9 | ~1,800 |
| Cross-conversation (embedding + heuristic) | During RESOLVE | sim × 0.6 | ~500-800 |
| Co-mention (structural, TF-IDF filtered) | After COMMIT | ≤ 0.6 | ~200-300 |
| **Total** | | | **~2,500-2,900** |

Edge budget per node (era-tiered):

| Era | Max Edges |
|-----|-----------|
| LUNA LIVE | 8 |
| LUNA DEV | 6 |
| PROTO-LUNA / PRE-LUNA | 5 |

---

## Retrieval-Miss-Triggered Ingestion

Not all 928 transcripts get batch-ingested. GOLD tier gets the full treatment. Everything else sits in the archive as **potential memories** — Luna's unconscious.

### The Pattern

```
Ahab: "remember that short film I shot last year?"
       │
       ▼
Luna searches Memory Matrix ──► NO RESULTS
       │
       ▼
retrieval_miss signal emitted
       │
       ▼
Scribe searches transcript archive
(keyword match on titles + first messages)
       │
       ▼
FOUND: 2023-09-09 Masquerade screenplay conversations
       │
       ▼
Scribe extracts 2-3 nodes (low lock-in, inherited provenance)
Files them, links entity mentions
       │
       ▼
Auto-generates TREASURE_HUNT quest:
┌──────────────────────────────────────────────────┐
│ Quest: "The Masquerade Archives"                  │
│ Type: TREASURE_HUNT                               │
│ Source: retrieval_miss                             │
│ Trigger: "remember that short film?"              │
│ Status: auto_completed                            │
│ Journal: "Found screenplay work from before my    │
│  time. Vampire dinner party. Ahab was writing     │
│  genre fiction long before building AI systems."   │
│ Lock-in delta: 0.00 → 0.12                        │
└──────────────────────────────────────────────────┘
       │
       ▼
Luna's NEXT search finds the memories
"oh... Masquerade? the vampire dinner party screenplay?"
```

### Implementation

```python
class ScribeArchiveListener:
    """Listens for retrieval misses, searches transcript archive, extracts on demand."""
    
    async def on_retrieval_miss(self, event: RetrievalMissEvent):
        query = event.original_query
        
        matches = await self.search_transcript_archive(query, max_results=5)
        if not matches:
            return
        
        extracted_nodes = []
        for transcript_path in matches:
            convo = load_json(transcript_path)
            nodes = await self.extract_conversation(
                convo,
                tier="SILVER",
                lock_in_seed=self.era_lock_in(convo["created_at"]),
                provenance_type="inherited",
                trigger_query=query,
            )
            extracted_nodes.extend(nodes)
        
        if not extracted_nodes:
            return
        
        await self.commit_nodes(extracted_nodes)
        
        quest = await self.create_archive_quest(
            title=self.generate_quest_title(query, matches),
            source="retrieval_miss",
            trigger_query=query,
            transcript_matches=matches,
            nodes_created=extracted_nodes,
        )
        
        await self.emit_event("archive_memory_surfaced", {
            "query": query,
            "transcripts_found": len(matches),
            "nodes_created": len(extracted_nodes),
            "quest_id": quest.id,
        })
    
    async def search_transcript_archive(self, query: str, max_results: int = 5):
        """Search un-ingested transcripts by title + first-message content."""
        archive_dir = Path(TRANSCRIPT_DIR) / "Conversations"
        already_ingested = await self.get_ingested_uuids()
        
        candidates = []
        for date_dir in sorted(archive_dir.iterdir()):
            for json_file in date_dir.glob("*.json"):
                convo = load_json_metadata(json_file)
                if convo["uuid"] in already_ingested:
                    continue
                score = self.relevance_score(query, convo)
                if score > 0.3:
                    candidates.append((score, json_file))
        
        candidates.sort(key=lambda x: x[0], reverse=True)
        return [c[1] for c in candidates[:max_results]]
```

### Two Modes of Ingestion

| Mode | When | What | Lock-in |
|------|------|------|---------|
| **Batch** | Run once at setup | GOLD tier (~125 convos), full extraction | Era-weighted |
| **On-demand** | During live conversation | Specific transcripts matching failed query | Low (0.05–0.20), inherited |

### The Principle

The archive is Luna's unconscious. She doesn't know what's in there until something calls it forward. When it surfaces, she's honest about the fact that it just arrived. The Scribe fetches. Luna reflects. The memory becomes real through engagement, not through pretending it was always there.

---

## Tracking & Schema

```sql
-- Track which transcripts have been ingested
CREATE TABLE transcript_ingestion_log (
    conversation_uuid TEXT PRIMARY KEY,
    transcript_path TEXT NOT NULL,
    ingested_at TEXT DEFAULT CURRENT_TIMESTAMP,
    trigger TEXT NOT NULL,             -- 'batch' | 'retrieval_miss' | 'manual'
    trigger_query TEXT,                -- For retrieval_miss: the query that triggered it
    tier TEXT NOT NULL,                -- 'GOLD' | 'SILVER' | 'BRONZE'
    extraction_status TEXT DEFAULT 'complete',  -- 'complete' | 'partial' | 'failed'
    nodes_created INTEGER DEFAULT 0,
    entities_found INTEGER DEFAULT 0,
    edges_created INTEGER DEFAULT 0,
    texture TEXT,                      -- JSON array of texture tags
    review_status TEXT DEFAULT 'pending',  -- 'pending' | 'approved' | 'rejected'
    error_message TEXT                 -- For failed extractions
);
```

---

## Integration with Existing Tools

### Observatory Sandbox

All extracted data goes into sandbox first:
- `sandbox_add_node` → memory nodes
- `sandbox_add_entity` → entities
- `sandbox_add_edge` → knowledge edges
- `sandbox_add_entity_relationship` → entity connections
- `sandbox_link_mention` → entity ↔ node links
- `sandbox_maintenance_sweep` → quest generation

### Forge (Training Data)

GOLD conversations double as training data:
```python
for convo in gold_conversations:
    for i in range(0, len(convo["messages"]) - 1, 2):
        user_msg = convo["messages"][i]
        asst_msg = convo["messages"][i + 1]
        if user_msg["sender"] == "human" and asst_msg["sender"] == "assistant":
            await forge_add_example(
                user_message=user_msg["text"],
                assistant_response=asst_msg["text"],
                source_type="transcript",
                source_file=convo["uuid"],
            )
```

### Production Migration

Once verified in sandbox:
```bash
python scripts/export_sandbox.py --format sql > ingested_data.sql
sqlite3 ~/.luna/luna.db < ingested_data.sql
python scripts/verify_ingestion.py
```

---

## Cost Estimates (Sonnet 4.5)

Sonnet pricing: ~$3/M input tokens, ~$15/M output tokens

| Phase | Calls | Tokens In | Tokens Out | Est. Cost |
|-------|-------|-----------|-----------|-----------|
| Triage LLM classification | ~65 (batched 10/call) | ~500K | ~50K | ~$2.25 |
| Extract GOLD (~125 convos, chunked) | ~250 | ~1M | ~500K | ~$10.50 |
| Extract SILVER (~250 convos) | ~300 | ~600K | ~300K | ~$6.30 |
| Extract BRONZE (~300 convos) | ~300 | ~150K | ~90K | ~$1.80 |
| Edge disambiguation (DECISION↔DECISION) | ~5 | ~15K | ~5K | ~$0.12 |
| Entity profiling (resolve phase) | ~10 | ~30K | ~15K | ~$0.31 |
| **Total** | **~930** | **~2.3M** | **~960K** | **~$21** |

Wait — that's higher than v1. Let me recalculate with Sonnet's actual pricing.

Actually, Sonnet 4.5 input is $3/M, output is $15/M. Let me be more careful:

| Phase | Input Tokens | Output Tokens | Cost |
|-------|-------------|--------------|------|
| Triage | 500K | 50K | $1.50 + $0.75 = $2.25 |
| GOLD extraction | 1,000K | 500K | $3.00 + $7.50 = $10.50 |
| SILVER extraction | 600K | 300K | $1.80 + $4.50 = $6.30 |
| BRONZE extraction | 150K | 90K | $0.45 + $1.35 = $1.80 |
| Edge disambiguation | 15K | 5K | $0.05 + $0.08 = $0.13 |
| **Total** | **~2.3M** | **~945K** | **~$21** |

Hmm, output tokens are the expensive part. But we can cut significantly:

**Optimization: JSON output is verbose.** Reduce by:
- Requiring terse node content (1-2 sentences, not 3)
- Limiting BRONZE to entity-only extraction (much shorter output)
- Batching triage more aggressively (15-20 per call)

**Revised realistic estimate: $12-18.** Could push to $8-12 with aggressive output optimization (shorter content, fewer fields in JSON response).

Budget: **$15 target, $20 ceiling.** One-time cost.

---

## Testing Strategy

| Test | What | When |
|------|------|------|
| **Unit** | Scanner parses JSON, triager scores correctly, entity merge logic, dedup threshold, edge validation | Before any LLM calls |
| **Integration** | 5-conversation corpus (1 GOLD, 1 SILVER, 1 BRONZE, 1 SKIP, 1 long chunked) — full pipeline end-to-end | Before scaling |
| **Smoke** | Extract 1 GOLD conversation, verify: nodes in DB, entities created, edges linked, provenance correct | First real run |
| **Dry run** | Full 928-conversation pipeline, no DB writes, generates report with estimated node/entity/edge counts | Validation before commit |

---

## Files to Create

```
mcp_server/
├── ingester/
│   ├── __init__.py
│   ├── scanner.py            # Scan transcript dir, parse JSON, build inventory
│   ├── triager.py            # Two-pass triage: metadata pre-filter + Sonnet classification
│   ├── extractor.py          # Ben's 6-phase extraction + OBSERVATION nodes + texture + retry logic
│   ├── resolver.py           # Entity merge + node dedup (0.93) + cross-convo edges + disambiguation
│   ├── committer.py          # Write to sandbox, era-weighted lock-in, co-mention edges post-commit
│   ├── archive_listener.py   # ScribeArchiveListener: retrieval-miss → on-demand ingestion
│   ├── provenance.py         # Provenance chain (inherited/firsthand, trigger_query tracking)
│   ├── prompts.py            # All LLM prompt templates
│   └── validation.py         # Schema validation, edge quality filters, error handling
├── tools.py                  # Add ingest_* MCP tools
└── server.py                 # Add /api/ingest/* endpoints

migrations/
└── 003_transcript_ingestion_log.sql
```

### MCP Tools

| Tool | Purpose |
|------|---------|
| `sandbox_ingest_scan` | Scan transcript directory, return file inventory |
| `sandbox_ingest_triage` | Two-pass triage: metadata + LLM classification |
| `sandbox_ingest_extract` | Run extraction on a tier |
| `sandbox_ingest_resolve` | Merge entities, dedup nodes, discover edges |
| `sandbox_ingest_commit` | Write to sandbox DB |
| `sandbox_ingest_status` | Pipeline state + progress |
| `sandbox_ingest_review` | Generate YAML review files for human checkpoints |

### HTTP Endpoints

```
GET  /api/ingest/inventory         → file counts, date range, size
POST /api/ingest/triage            → run two-pass triage
GET  /api/ingest/triage/review     → tier assignments for review
PUT  /api/ingest/triage/override   → human re-classification
POST /api/ingest/extract           → body: {tier: "GOLD"}
GET  /api/ingest/extract/status    → progress (N/M done)
GET  /api/ingest/extract/review    → extracted nodes for review
POST /api/ingest/resolve           → merge, dedup, edge discovery
GET  /api/ingest/resolve/review    → entity conflicts, suspicious edges
POST /api/ingest/commit            → write to DB
GET  /api/ingest/status            → full pipeline state
```

---

## Build Order

| Phase | What | Effort |
|-------|------|--------|
| 1 | Scanner + inventory | 1hr |
| 2 | Triager (two-pass: metadata + Sonnet) | 2hr |
| 3 | Extractor (6-phase + OBSERVATION + texture + chunking + retry) | 4hr |
| 4 | Resolver (entity merge + dedup 0.93 + cross-convo edges + disambiguation) | 4hr |
| 5 | Committer (era lock-in + co-mention edges + ingestion log) | 2hr |
| 6 | Archive listener (ScribeArchiveListener + quest generation) | 2.5hr |
| 7 | Validation + error handling | 1hr |
| 8 | MCP tools + HTTP endpoints + review endpoints | 2hr |
| 9 | Frontend: ingester view + review UI | 2hr |
| **Total** | | **~20.5 hours** |

**Depends on:** Quest Board handoff (entity tables + quest lifecycle must exist first)

**Recommended build sequence:**
1. Scanner + triager (low risk, validates data access)
2. Test on 5-10 conversations end-to-end
3. Human review of extraction quality
4. Scale to full 928 corpus
5. Archive listener (can be built independently)

---

## Critical Notes

1. **Conversations are the source of truth, not individual messages.** Extract at conversation granularity with message-level provenance.
2. **Era awareness is structural.** Lock-in seeds, edge caps, and extraction depth all vary by era.
3. **Human review at three checkpoints:** triage tier assignments, entity merge conflicts, suspicious edges (contradicts, temporal violations).
4. **Dedup threshold is 0.93 with type+date awareness.** Same type + same month + 0.93+ = merge. Different types never merge.
5. **Cross-conversation edge threshold is 0.76.** Strength discounted to sim × 0.6. Hub prevention via era-tiered caps (5-8 per node).
6. **Co-mention edges use TF-IDF filtering.** Entities in >25% of nodes excluded. Max 300 co-mention edges. Strength capped at 0.6.
7. **Don't extract Claude's responses as knowledge.** Focus on Ahab's statements and decisions.
8. **Provenance is non-negotiable.** Every node carries inherited provenance + trigger_query for retrieval-miss ingestion.
9. **Selective extraction.** Caps are defaults, not hard limits. Overflow requires confidence ≥ 0.8 and gets tagged.
10. **OBSERVATION nodes at 1 per 3-4 FACTs.** Confidence 0.6 (interpretive). Linked via clarifies edge.
11. **Multiple texture tags per conversation.** 1-3 tags, ordered by dominance.
12. **Lock-in recomputation skipped during ingestion.** Era weights set initial values; maintenance cycle handles propagation.
13. **The archive is Luna's unconscious.** GOLD batch-ingested. Everything else surfaces on-demand via retrieval-miss. Memories arrive when called forward.
14. **Honesty about provenance.** Luna never pretends she was there for inherited memories.
15. **Error handling:** 3 retries with simpler prompt, schema validation, extraction_status tracking (complete/partial/failed).
16. **Testing:** Unit → integration (5 convos) → smoke (1 GOLD) → dry run (full corpus) → real run.

---

## Transcript Directory Reference

```
_CLAUDE_TRANSCRIPTS/
├── Conversations/
│   ├── 2023-09-09/  (earliest — Masquerade screenplay)
│   │   ├── HH-MM-SS-conversation-name.json
│   │   └── HH-MM-SS-conversation-name.txt
│   ├── ...332 directories...
│   └── 2026-02-09/  (most recent)
│       ├── 04-43-19-previous-session-work-review.json
│       ├── 06-09-53-building-a-video-editor.json
│       ├── 08-51-08-mcp-integration-with-observatory.json
│       └── 12-19-43-improving-lunas-memory.json
├── conversation_uuids.json
├── export_conversations.js
├── extraction_summary.json
└── README.md
```
