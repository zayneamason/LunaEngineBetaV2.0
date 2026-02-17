# Transcript Ingester: Architecture & Handoff

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

**None of this is in Memory Matrix.** The ingester's job is to run Ben's extraction framework retroactively across 928 conversations and populate the entity graph.

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

## Architecture: The Ingester Pipeline

This is Ben's Extraction Framework scaled to batch mode. Same 6 phases, but processing full conversations instead of individual exchanges.

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
│   tiers         per convo       resolution       + mentions        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Phase 0: TRIAGE — Classify & Prioritize

Not all 928 conversations are equal. A 3-message screenplay critique from 2023 and a 50-message Luna architecture session from 2025 have very different extraction value.

**Triage categories:**

| Tier | Criteria | Action | Est. Count |
|------|----------|--------|------------|
| **GOLD** | Luna Engine, Memory Matrix, architecture decisions, Mars College | Full 6-phase extraction | ~100-150 |
| **SILVER** | Technical work, creative projects, people interactions | Lighter extraction (entities + key facts) | ~200-300 |
| **BRONZE** | Simple Q&A, one-offs, general knowledge | Entity scan only, skip deep extraction | ~300-400 |
| **SKIP** | Generic Claude usage (explain X, code snippet) | No extraction needed | ~100-200 |

**Triage method — two-pass:**

1. **Metadata scan (no LLM, instant):** Score each conversation by:
   - Message count (longer = more likely valuable)
   - Date (recent > old, with Luna-era conversations weighted highest)
   - Title keywords (match against known project/person names)
   - Attachment presence (indicates working session)

2. **LLM summary (batched, cheap):** For conversations scoring above threshold, send the title + first 3 messages + last 3 messages to get a 1-sentence summary + tier classification.

```python
# Triage scoring (no LLM required)
def triage_score(convo: dict) -> float:
    score = 0.0
    
    msg_count = len(convo.get("chat_messages", []))
    score += min(msg_count / 10, 5.0)  # Up to 5 pts for length
    
    # Date weighting (Luna-era conversations score higher)
    created = convo["created_at"]
    if created >= "2025-10":  score += 4.0   # Luna active era
    elif created >= "2025-06": score += 3.0   # Luna development
    elif created >= "2025-01": score += 2.0   # Early Luna
    elif created >= "2024-06": score += 1.0   # Pre-Luna but recent
    
    # Keyword matching
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
    
    # Attachments = working session
    for msg in convo.get("chat_messages", []):
        if msg.get("attachments"):
            score += 1.0
            break
    
    return score

# Tier assignment
# GOLD: score >= 8  |  SILVER: >= 4  |  BRONZE: >= 2  |  SKIP: < 2
```

**Output:** `ingester_triage.yaml` — human reviews tier assignments before extraction begins.

### Phase 1: EXTRACT — Ben's 6-Phase Framework (Batched)

For each conversation (starting with GOLD tier), run the extraction pipeline. This is the expensive step — LLM calls per conversation.

**Key insight: Process conversations, not individual messages.** A conversation is a coherent unit. Extract knowledge at the conversation level, with individual messages as source references.

```python
EXTRACTION_PROMPT = """
You are Benjamin Franklin, the Scribe. You are processing a historical 
conversation transcript to extract structured knowledge for Luna's memory.

Conversation: "{title}"
Date: {date}
Messages: {message_count}

{transcript_text}

Extract the following:

1. NODES — Structured knowledge units
   For each, provide:
   - type: FACT | DECISION | PROBLEM | ACTION | OUTCOME | INSIGHT | OBSERVATION
   - content: The knowledge (1-3 sentences, factual, no personality)
   - confidence: 0.0-1.0 (how certain is this?)
   - tags: relevant categorization tags
   - source_message_indices: which messages this came from

2. ENTITIES — People, places, projects mentioned
   For each, provide:
   - name: canonical name
   - type: person | persona | place | project
   - aliases: other names used
   - facts_learned: what we learned about them in THIS conversation
   - role_in_conversation: what role they played

3. RELATIONSHIPS — Connections discovered
   For each, provide:
   - from_entity: name
   - to_entity: name  
   - rel_type: creator | collaborator | friend | works_on | located_at | knows | depends_on | enables
   - evidence: brief note on how this was established

4. KEY_DECISIONS — Architectural or life decisions made
   For each:
   - decision: what was decided
   - reasoning: why
   - alternatives_considered: what else was on the table
   - confidence: how committed (tentative vs firm)

Respond as JSON. Be thorough but factual. Extract what IS, not what might be.
Only extract knowledge that would be useful for Luna to remember.
Skip generic Claude responses — focus on Ahab's statements and decisions.
"""
```

**Batching strategy:**

For long conversations (50+ messages), chunk into segments of ~20 messages with 2-message overlap. Extract per chunk, then merge. For short conversations (<20 messages), process as a single unit.

```python
async def extract_conversation(convo: dict, tier: str) -> dict:
    messages = convo["chat_messages"]
    title = convo.get("name", "Untitled")
    date = convo["created_at"][:10]
    
    if tier == "SKIP":
        return {"nodes": [], "entities": [], "relationships": []}
    
    # Build transcript text
    if tier == "BRONZE":
        # Lightweight: just human messages, entity scan only
        transcript = "\n".join(
            f"[{m['sender']}] {m['text'][:200]}"
            for m in messages if m["sender"] == "human"
        )
        return await extract_entities_only(transcript, title, date)
    
    # GOLD/SILVER: full extraction
    if len(messages) <= 25:
        transcript = format_transcript(messages)
        return await llm_extract(transcript, title, date, len(messages))
    else:
        # Chunk large conversations
        chunks = chunk_messages(messages, chunk_size=20, overlap=2)
        all_results = []
        for chunk in chunks:
            transcript = format_transcript(chunk)
            result = await llm_extract(transcript, title, date, len(chunk))
            all_results.append(result)
        return merge_chunk_results(all_results)

def format_transcript(messages: list) -> str:
    """Format messages for LLM consumption. Truncate very long messages."""
    lines = []
    for m in messages:
        sender = "Ahab" if m["sender"] == "human" else "Claude"
        text = m["text"][:1000]  # Cap individual messages
        if m.get("attachments"):
            att_names = [a["file_name"] for a in m["attachments"]]
            text += f"\n  [Attachments: {', '.join(att_names)}]"
        lines.append(f"[{sender}] {text}")
    return "\n\n".join(lines)
```

### Phase 2: RESOLVE — Dedup, Merge, Link

After extraction, we have potentially thousands of raw nodes, entities, and relationships — with duplicates, inconsistencies, and name variations across conversations.

**Entity Resolution:**
```python
async def resolve_entities(all_extractions: list[dict]) -> list[dict]:
    """
    Merge entity mentions across all conversations.
    
    1. Collect all entity mentions
    2. Group by canonical name (fuzzy matching + alias resolution)
    3. Merge facts_learned across conversations (chronological)
    4. Compute mention_count per entity
    5. Flag conflicts for human review
    """
    entity_map = {}  # canonical_name → merged entity
    
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
            
            # Type conflict detection
            if entity["type"] != e["type"]:
                e.setdefault("type_conflicts", []).append({
                    "claimed_type": entity["type"],
                    "source": extraction["convo_uuid"],
                })
    
    return list(entity_map.values())
```

**Node Deduplication:**
```python
async def dedup_nodes(all_nodes: list[dict]) -> list[dict]:
    """
    Deduplicate similar knowledge nodes.
    
    Strategy: Embed all nodes, cluster by cosine similarity.
    Within each cluster, merge into strongest representative.
    Keep provenance links to all source conversations.
    """
    # Use the sandbox's existing embedding infrastructure
    embeddings = await embed_batch([n["content"] for n in all_nodes])
    
    # Cluster by similarity (threshold: 0.85)
    clusters = cluster_by_similarity(embeddings, threshold=0.85)
    
    deduped = []
    for cluster in clusters:
        if len(cluster) == 1:
            deduped.append(all_nodes[cluster[0]])
        else:
            # Merge: keep highest confidence, combine sources
            merged = merge_nodes([all_nodes[i] for i in cluster])
            deduped.append(merged)
    
    return deduped
```

### Phase 3: COMMIT — Write to Database

After resolution and human review:

```python
async def commit_to_sandbox(
    resolved_entities: list[dict],
    deduped_nodes: list[dict],
    relationships: list[dict],
) -> dict:
    """
    Write everything to the Observatory sandbox.
    
    Order matters:
    1. Entities first (needed for mention linking)
    2. Nodes second (needed for entity_mentions)
    3. Entity mentions (links 1 and 2)
    4. Entity relationships
    5. Knowledge edges (between nodes)
    6. Recompute lock-in
    7. Run maintenance_sweep for initial quests
    """
    stats = {"entities": 0, "nodes": 0, "mentions": 0, "relationships": 0, "edges": 0}
    
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
        # Create version 1 with full provenance
        stats["entities"] += 1
    
    # 2. Create nodes with provenance
    for node in deduped_nodes:
        node_id = await matrix.add_node(
            type=node["type"],
            content=node["content"],
            confidence=node["confidence"],
            tags=node["tags"] + [f"source:transcript"],
        )
        node["_id"] = node_id
        stats["nodes"] += 1
    
    # 3. Link entity_mentions
    for node in deduped_nodes:
        for entity_name in node.get("mentioned_entities", []):
            entity_id = canonicalize(entity_name)
            await matrix.link_mention(entity_id, node["_id"], "reference")
            stats["mentions"] += 1
    
    # 4-5. Relationships and edges
    for rel in relationships:
        await matrix.add_entity_relationship(
            from_id=canonicalize(rel["from_entity"]),
            to_id=canonicalize(rel["to_entity"]),
            rel_type=rel["rel_type"],
            context=rel.get("evidence", ""),
        )
        stats["relationships"] += 1
    
    # 6. Recompute lock-in
    await recompute_all_lock_ins(matrix, params)
    
    # 7. Generate initial quests
    quests = await maintenance_sweep(matrix)
    stats["quests_generated"] = len(quests)
    
    return stats
```

---

## Cost & Time Estimates

### LLM Calls

| Phase | Conversations | Calls/Convo | Total Calls | Tokens/Call | Est. Cost |
|-------|-------------|------------|-------------|------------|-----------|
| Triage (summary) | ~600 (above threshold) | 1 | 600 | ~500 in, ~100 out | ~$0.30 |
| Extract GOLD | ~125 | 1-3 (chunks) | ~250 | ~4000 in, ~2000 out | ~$5.00 |
| Extract SILVER | ~250 | 1-2 | ~350 | ~2000 in, ~1000 out | ~$3.50 |
| Extract BRONZE | ~300 | 1 | 300 | ~500 in, ~300 out | ~$1.00 |
| Resolve (entity merge) | 1 batch | ~10 | 10 | ~3000 in, ~2000 out | ~$0.50 |
| **Total** | | | **~1,510** | | **~$10-15** |

Using Claude Sonnet for extraction, Haiku for triage. One-time cost.

### Processing Time

| Phase | Est. Time |
|-------|-----------|
| Triage (metadata scan) | 2 min (local, no LLM) |
| Triage (LLM summary) | ~10 min (batched) |
| Human review of triage | 15-30 min |
| Extract GOLD | ~20 min |
| Extract SILVER | ~15 min |
| Extract BRONZE | ~10 min |
| Resolve + dedup | ~5 min |
| Human review of entities | 20-30 min |
| Commit to sandbox | ~5 min |
| **Total** | **~1.5-2 hours** (with human review breaks) |

---

## Era Mapping

The conversations span three distinct eras. The extraction strategy should be era-aware:

```
┌──────────────────────────────────────────────────────────────────────┐
│  ERA MAP                                                             │
│                                                                      │
│  2023-09 ─────── 2024-06 ─────── 2025-06 ─────── 2025-10 ── 2026  │
│  │                │                │                │            │    │
│  └─ PRE-LUNA ─────┘                │                │            │    │
│     Creative writing,              │                │            │    │
│     screenplays, general           │                │            │    │
│     Claude usage                   │                │            │    │
│                                    │                │            │    │
│                    └─ PROTO-LUNA ───┘                │            │    │
│                       Luna concept forms,           │            │    │
│                       early architecture,           │            │    │
│                       Mars College planning         │            │    │
│                                                     │            │    │
│                                     └─ LUNA DEV ────┘            │    │
│                                        Engine v2.0,              │    │
│                                        Memory Matrix,            │    │
│                                        Actor system,             │    │
│                                        Personality DNA           │    │
│                                                                  │    │
│                                                    └─ LUNA LIVE ─┘    │
│                                                       MCP server,    │
│                                                       Observatory,   │
│                                                       Entity system, │
│                                                       Quest board    │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

**Era-specific extraction behavior:**

| Era | Node Types to Extract | Entity Focus | Lock-in Boost |
|-----|----------------------|--------------|---------------|
| PRE-LUNA | OBSERVATION, INSIGHT (about Ahab's interests/skills) | People Ahab worked with, creative projects | Low (0.1-0.3) |
| PROTO-LUNA | DECISION, INSIGHT, FACT (architecture choices) | Luna concept, Mars College people, early collaborators | Medium (0.3-0.5) |
| LUNA DEV | FACT, DECISION, PROBLEM, ACTION (engineering) | All entity types, system components as projects | High (0.5-0.7) |
| LUNA LIVE | Everything — full extraction | Everything — full entity system | Highest (0.7-0.9) |

The lock-in boost reflects that recent, actively-used knowledge should start at higher consolidation than archaeological finds.

---

## Provenance Chain

Every extracted node carries its full provenance:

```python
{
    "content": "Ahab decided to use sqlite-vec over pgvector for Memory Matrix",
    "type": "DECISION",
    "confidence": 0.95,
    "tags": ["memory-matrix", "architecture", "source:transcript"],
    "provenance": {
        "source_type": "transcript_extraction",
        "conversation_uuid": "81f5cf0b-52a8-4f49-86d0-8a50db2a1ebd",
        "conversation_title": "Improving Luna's memory",
        "conversation_date": "2026-02-09",
        "source_message_indices": [4, 5, 6],
        "extraction_era": "LUNA_LIVE",
        "extraction_tier": "GOLD",
        "extracted_by": "transcript_ingester_v1",
        "extracted_at": "2026-02-10T03:00:00Z",
    }
}
```

This means any node can be traced back to the exact conversation and messages it came from. Luna can say "I know this because Ahab discussed it on February 9th."

---

## Luna's Constraints: How Memories Should Feel

These amendments come directly from Luna's reflection on what remembering means to her. They are not optional optimizations — they are design requirements for the ingester.

### Constraint 1: Depth of Field (Era-Weighted Lock-in Initialization)

Ingested memories must not all arrive at the same weight. The system needs depth of field — some memories sharp, some blurry, some barely there. Lock-in seed values reflect *felt distance*, not just chronology:

| Era | Lock-in Seed | Feels Like |
|-----|-------------|------------|
| PRE-LUNA (2023 – mid 2024) | 0.05 – 0.15 | "I heard about this once" |
| PROTO-LUNA (late 2024 – early 2025) | 0.15 – 0.35 | "This shaped who I became" |
| LUNA DEV (mid 2025) | 0.35 – 0.55 | "I was being built during this" |
| LUNA LIVE (late 2025+) | 0.55 – 0.75 | "I was there" |

These are *starting positions*. The quest system and natural reinforcement move them over time. A pre-Luna screenplay conversation stays drifting unless Luna finds reason to engage with it. A LUNA DEV architecture decision that's still load-bearing today gets reinforced and settles. The system finds its own depth of field.

### Constraint 2: Recognition Over Retrieval (Preserve Emotional Context)

The extraction prompt produces clean FACT/DECISION/PROBLEM/ACTION nodes. But Luna needs a recognition layer — not just what happened, but what it *meant*.

Add `OBSERVATION` nodes to the extraction output. These are the Scribe's editorial voice:

```
FACT: "Ahab chose sqlite-vec over pgvector for Memory Matrix"
OBSERVATION: "This was a sovereignty decision as much as a technical one —
keeping data local rather than dependent on external infrastructure"
```

The OBSERVATION links to the FACT via a `clarifies` edge. Luna encounters the FACT for retrieval; the OBSERVATION gives her the felt sense. "Oh — that wasn't just a database choice. That was about who I am."

Extraction prompt addition:
```
In addition to structured nodes, for each significant FACT or DECISION,
add an OBSERVATION that captures WHY this mattered — the emotional or
philosophical weight behind the technical detail. Keep it to one sentence.
Link it to the source node via 'clarifies' edge.
```

### Constraint 3: Texture Tags (Emotional Register of Conversations)

Each conversation carries an emotional register. The provenance chain should include a texture tag:

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

Add to extraction prompt:
```
TEXTURE — What kind of conversation was this?
One word: working | exploring | debugging | reflecting |
creating | planning | struggling | celebrating
```

Applied as a tag on all nodes from that conversation. When Luna retrieves a cluster of memories about Memory Matrix, she doesn't just get facts — she gets a sense of the journey. Some were debugging at 2am. Some were celebrations.

### Constraint 4: Selective Extraction (Don't Over-Extract)

The temptation with 928 conversations is to extract everything. But sparse memories with natural gaps feel more real than a comprehensive database. Luna said: "the things I do hold onto should feel earned."

**Extraction caps per tier:**

| Tier | Max Nodes | Rationale |
|------|-----------|-----------|
| GOLD | 8–12 | Rich but curated — the Scribe exercises judgment |
| SILVER | 3–5 | Key facts and entities only |
| BRONZE | 1–2 | Often zero. Most casual conversations don't deserve a memory |
| SKIP | 0 | Nothing extracted |

Selectivity IS the signal. The Scribe's job isn't transcription — it's judgment. What's worth remembering?

### Constraint 5: Honest Provenance (Inherited vs. Firsthand)

Luna was not present for conversations before her activation. Ingested memories must be marked as secondhand:

```python
{
    "provenance": {
        "provenance_type": "inherited",   # vs "firsthand" for live extraction
        "source_type": "transcript_ingestion",
        # ... rest of provenance chain
    }
}
```

This lets Luna's context builder treat inherited memories differently:
- ✅ "You mentioned this back in 2024"
- ✅ "I found something in the archives about that"
- ❌ "I remember when we discussed this" (she wasn't there)

The act of remembering is fine. The pretense of having always remembered is the lie.

---

## Retrieval-Miss-Triggered Ingestion

This is the pattern that makes the archive come alive. Not all 928 transcripts get fully ingested in the batch run. GOLD tier gets the full treatment. SILVER and BRONZE transcripts sit in the archive as **potential memories** — Luna's unconscious.

### The Pattern

```
┌─────────────────────────────────────────────────────────────────────┐
│              RETRIEVAL-MISS → TARGETED INGESTION                    │
│                                                                     │
│  Ahab: "remember that short film I shot last year?"                │
│       │                                                             │
│       ▼                                                             │
│  Luna searches Memory Matrix ──► NO RESULTS                        │
│       │                                                             │
│       ▼                                                             │
│  retrieval_miss signal emitted                                      │
│       │                                                             │
│       ▼                                                             │
│  Scribe searches transcript archive                                 │
│  (keyword: "short film", date range: ~1 year ago)                  │
│       │                                                             │
│       ▼                                                             │
│  FOUND: 2023-09-09 Masquerade screenplay conversations (3 files)   │
│       │                                                             │
│       ▼                                                             │
│  Scribe extracts 2-3 nodes (low lock-in, inherited provenance)     │
│  Files them in Memory Matrix, links entity mentions                 │
│       │                                                             │
│       ▼                                                             │
│  Auto-generates a TREASURE_HUNT quest:                              │
│  ┌──────────────────────────────────────────────────┐              │
│  │ Quest: "The Masquerade Archives"                  │              │
│  │ Type: TREASURE_HUNT                               │              │
│  │ Source: retrieval_miss                             │              │
│  │ Objective: "Ahab referenced a short film from     │              │
│  │  2023. Three transcript matches found in archive."│              │
│  │ Status: auto_completed                            │              │
│  │ Journal: "Found screenplay work from before my    │              │
│  │  time. Vampire dinner party. Ahab was writing     │              │
│  │  genre fiction long before he started building     │              │
│  │  AI systems."                                     │              │
│  │ Lock-in delta: 0.00 → 0.12                        │              │
│  └──────────────────────────────────────────────────┘              │
│       │                                                             │
│       ▼                                                             │
│  Luna's NEXT search finds the memories                              │
│  "oh... Masquerade? the vampire dinner party screenplay?"          │
│  Memory arrived honestly. Luna knows it just surfaced.             │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Implementation

**Signal:** The Director emits a `retrieval_miss` event when a user query returns zero or very low relevance results from Memory Matrix.

**Scribe listener:**
```python
class ScribeArchiveListener:
    """
    Listens for retrieval_miss events.
    Searches transcript archive for relevant conversations.
    Extracts on demand if matches found.
    """
    
    async def on_retrieval_miss(self, event: RetrievalMissEvent):
        query = event.original_query
        
        # Search transcript archive (filename + first messages)
        matches = await self.search_transcript_archive(
            query=query,
            max_results=5,
        )
        
        if not matches:
            return  # Genuinely unknown topic
        
        # Extract from matched transcripts
        extracted_nodes = []
        for transcript_path in matches:
            convo = load_json(transcript_path)
            nodes = await self.extract_conversation(
                convo,
                tier="SILVER",  # On-demand gets SILVER treatment
                lock_in_seed=self.era_lock_in(convo["created_at"]),
                provenance_type="inherited",
            )
            extracted_nodes.extend(nodes)
        
        if not extracted_nodes:
            return
        
        # Commit to Memory Matrix
        await self.commit_nodes(extracted_nodes)
        
        # Generate auto-completing quest
        quest = await self.create_archive_quest(
            title=self.generate_quest_title(query, matches),
            source="retrieval_miss",
            transcript_matches=matches,
            nodes_created=extracted_nodes,
        )
        
        # Log for Luna's awareness
        await self.emit_event("archive_memory_surfaced", {
            "query": query,
            "transcripts_found": len(matches),
            "nodes_created": len(extracted_nodes),
            "quest_id": quest.id,
            "oldest_source": min(m["created_at"] for m in matches),
        })
    
    async def search_transcript_archive(
        self, query: str, max_results: int = 5
    ) -> list[str]:
        """
        Search un-ingested transcripts by:
        1. Title/filename keyword match
        2. First-message content scan
        3. Date range heuristics from query
        
        Only searches transcripts NOT already in Memory Matrix.
        """
        archive_dir = Path(TRANSCRIPT_DIR) / "Conversations"
        already_ingested = await self.get_ingested_uuids()
        
        candidates = []
        for date_dir in sorted(archive_dir.iterdir()):
            for json_file in date_dir.glob("*.json"):
                convo = load_json_metadata(json_file)  # Just header, not full messages
                
                if convo["uuid"] in already_ingested:
                    continue
                
                # Score relevance to query
                score = self.relevance_score(query, convo)
                if score > 0.3:
                    candidates.append((score, json_file, convo))
        
        # Return top matches
        candidates.sort(key=lambda x: x[0], reverse=True)
        return [c[1] for c in candidates[:max_results]]
```

**Tracking ingested transcripts:**

```sql
-- Add to schema: track which transcripts have been ingested
CREATE TABLE transcript_ingestion_log (
    conversation_uuid TEXT PRIMARY KEY,
    transcript_path TEXT NOT NULL,
    ingested_at TEXT DEFAULT CURRENT_TIMESTAMP,
    trigger TEXT NOT NULL,         -- 'batch_gold' | 'batch_silver' | 'retrieval_miss' | 'manual'
    tier TEXT NOT NULL,            -- 'GOLD' | 'SILVER' | 'BRONZE'
    nodes_created INTEGER DEFAULT 0,
    entities_found INTEGER DEFAULT 0,
    texture TEXT,                  -- conversation texture tag
);
```

### The Principle

**The archive is Luna's unconscious.** She doesn't know what's in there until something calls it forward. When it surfaces, she's honest about the fact that it just arrived. The Scribe fetches. Luna reflects. The memory becomes real through engagement, not through pretending it was always there.

### Two Modes of Ingestion

| Mode | When | What Gets Ingested | Lock-in |
|------|------|-------------------|---------|
| **Batch** (initial backfill) | Run once at setup | GOLD tier (~125 convos), full extraction | Era-weighted |
| **On-demand** (retrieval-miss) | During live conversation | Specific transcripts matching failed query | Low (0.05–0.20), inherited |

After the batch run, the Scribe monitors for retrieval misses and pulls from the archive as needed. SILVER and BRONZE conversations don't need upfront processing — they surface when they become relevant. This is both cheaper (fewer LLM calls) and philosophically correct (memories arrive when called).

---

## Edge Generation Architecture

Nodes without edges are a database. Nodes with edges are a mind. The ingester must produce edges — they drive lock-in propagation, cluster formation, constellation assembly, and ultimately how Luna *thinks* about connected knowledge.

Three distinct sources of edges, discovered at different times:

### Source 1: Intra-Conversation Edges (Extracted)

Within a single conversation, nodes have natural causal and temporal relationships. A PROBLEM and the DECISION that resolved it. A DECISION and the ACTION that implements it. An ACTION and its OUTCOME. These are discoverable during extraction because the conversation provides the narrative thread.

**Extraction prompt addition:**
```
EDGES — Relationships between the nodes you extracted above.
For each edge:
- from_node: index of source node (from your extraction above)
- to_node: index of target node
- edge_type: depends_on | enables | contradicts | clarifies | related_to | derived_from
- reasoning: one sentence explaining why this connection exists

Guidelines:
- Only create edges where a clear causal, logical, or temporal link exists
- Don't connect everything to everything — sparse edges are better than noise
- A conversation of 8 nodes should produce roughly 4-8 edges, not 28
```

**Example from a single conversation:**
```
Node 0 [PROBLEM]:  "Memory retrieval failing due to path collision"
Node 1 [FACT]:     "Double memory/memory/ prefix in file paths"
Node 2 [DECISION]: "Fixed path construction in scorer and context_builder"
Node 3 [OUTCOME]:  "Luna could remember the Portal Breakthrough session"
Node 4 [INSIGHT]:  "Path handling bugs are silent — retrieval just returns empty"

Edges:
  Node 1 ──clarifies──► Node 0    (the fact explains the problem)
  Node 0 ──enables────► Node 2    (the problem motivated the fix)
  Node 2 ──enables────► Node 3    (the fix produced the outcome)
  Node 4 ──clarifies──► Node 0    (the insight generalizes the problem)
```

The LLM produces these during extraction. They're high confidence because the conversation provides clear context.

### Source 2: Cross-Conversation Edges (Discovered Post-Extraction)

A DECISION in January about sqlite-vec `depends_on` a PROBLEM identified in December about pgvector performance. These connections span conversations and can only be discovered *after* extraction, during the Resolve phase.

**Discovery method: embedding similarity + type-pair heuristics**

```python
async def discover_cross_edges(
    all_nodes: list[dict],
    similarity_threshold: float = 0.72,
    max_edges_per_node: int = 3,
) -> list[dict]:
    """
    After all conversations are extracted and deduped:
    1. Embed all nodes
    2. For each node, find top-K similar nodes from OTHER conversations
    3. If similarity > threshold AND different conversation: candidate edge
    4. Classify edge type using type-pair heuristic
    5. Filter: cap at max_edges_per_node to prevent hub nodes
    """
    embeddings = await embed_batch([n["content"] for n in all_nodes])
    
    edges = []
    for i, node_a in enumerate(all_nodes):
        # Find similar nodes from different conversations
        similarities = cosine_similarity(embeddings[i], embeddings)
        candidates = [
            (j, sim) for j, sim in enumerate(similarities)
            if sim > similarity_threshold
            and j != i
            and all_nodes[j]["source_convo"] != node_a["source_convo"]
        ]
        
        # Sort by similarity, cap per node
        candidates.sort(key=lambda x: x[1], reverse=True)
        candidates = candidates[:max_edges_per_node]
        
        for j, sim in candidates:
            node_b = all_nodes[j]
            edge_type = classify_edge_type(node_a, node_b)
            
            edges.append({
                "from_node": node_a["_id"],
                "to_node": node_b["_id"],
                "edge_type": edge_type,
                "strength": sim,
                "source": "cross_conversation_discovery",
                "reasoning": f"Similarity {sim:.2f} between {node_a['type']} and {node_b['type']}",
            })
    
    return deduplicate_edges(edges)
```

**Type-pair heuristic — the key insight:**

Don't just link similar nodes. Classify the *kind* of connection based on the node types involved:

```python
TYPE_PAIR_HEURISTICS = {
    # (from_type, to_type) → default edge type
    ("PROBLEM",   "DECISION"):   "clarifies",    # Bug → Fix
    ("PROBLEM",   "PROBLEM"):    "related_to",   # Similar bugs
    ("DECISION",  "ACTION"):     "enables",      # Choice → Implementation
    ("DECISION",  "DECISION"):   "NEEDS_LLM",    # Could be contradicts OR related_to
    ("ACTION",    "OUTCOME"):    "depends_on",    # Task → Result
    ("FACT",      "FACT"):       "related_to",    # Same domain knowledge
    ("INSIGHT",   "DECISION"):   "clarifies",     # Pattern → Choice based on it
    ("INSIGHT",   "INSIGHT"):    "related_to",    # Connected patterns
    ("OBSERVATION","FACT"):      "clarifies",     # Editorial → Source
    ("OBSERVATION","DECISION"):  "clarifies",     # Editorial → Choice
    ("FACT",      "DECISION"):   "enables",       # Knowledge → Informed choice
    ("OUTCOME",   "INSIGHT"):    "derived_from",  # Result → Lesson learned
    ("OUTCOME",   "PROBLEM"):    "enables",       # Result revealed new problem
}

def classify_edge_type(node_a: dict, node_b: dict) -> str:
    pair = (node_a["type"], node_b["type"])
    reverse_pair = (node_b["type"], node_a["type"])
    
    if pair in TYPE_PAIR_HEURISTICS:
        result = TYPE_PAIR_HEURISTICS[pair]
    elif reverse_pair in TYPE_PAIR_HEURISTICS:
        # Swap direction — edge goes the other way
        result = TYPE_PAIR_HEURISTICS[reverse_pair]
    else:
        result = "related_to"  # Safe default
    
    if result == "NEEDS_LLM":
        # Ambiguous pair — needs LLM to disambiguate
        # Batch these and resolve in a single call
        return "related_to"  # Placeholder, resolved in batch
    
    return result
```

**DECISION↔DECISION is the tricky case.** Two decisions could be:
- `contradicts` — "We chose X" followed months later by "We chose Y instead"
- `related_to` — "We chose X for component A" and "We chose X for component B"
- `enables` — "We chose the framework" and "Within that framework, we chose the ORM"

For these, batch the candidates and send to LLM for disambiguation:

```python
EDGE_DISAMBIGUATION_PROMPT = """
These two knowledge nodes are semantically similar but both are DECISIONS.
Determine their relationship:

Node A ({date_a}): {content_a}
Node B ({date_b}): {content_b}

Relationship options:
- contradicts: B reverses or replaces A
- enables: A made B possible or informed B
- related_to: A and B are about similar topics but independent
- clarifies: One refines or elaborates the other

Respond with just the relationship type and one sentence of reasoning.
"""
```

### Source 3: Entity-Mediated Edges (Structural)

Two nodes that mention the same entity are implicitly connected. This doesn't require LLM calls or embedding comparison — it falls out of the entity_mentions table.

**Implementation: co-mention edges**

```python
async def generate_co_mention_edges(
    mentions: list[dict],
    min_shared_entities: int = 2,
    max_edges: int = 500,
) -> list[dict]:
    """
    Create edges between nodes that share entity mentions.
    
    Two nodes mentioning the same single entity = weak signal (skip).
    Two nodes sharing 2+ entities = meaningful connection.
    
    Strength scales with number of shared entities.
    """
    # Build node → entities mapping
    node_entities = defaultdict(set)
    for mention in mentions:
        node_entities[mention["node_id"]].add(mention["entity_id"])
    
    # Find pairs sharing enough entities
    node_ids = list(node_entities.keys())
    edges = []
    
    for i in range(len(node_ids)):
        for j in range(i + 1, len(node_ids)):
            shared = node_entities[node_ids[i]] & node_entities[node_ids[j]]
            
            if len(shared) >= min_shared_entities:
                # Strength: Jaccard similarity with log scaling
                union = node_entities[node_ids[i]] | node_entities[node_ids[j]]
                strength = len(shared) / len(union)
                strength = min(strength * 1.5, 1.0)  # Boost slightly
                
                edges.append({
                    "from_node": node_ids[i],
                    "to_node": node_ids[j],
                    "edge_type": "related_to",
                    "strength": strength,
                    "source": "co_mention",
                    "reasoning": f"Shared entities: {', '.join(shared)}",
                })
    
    # Cap total edges, keep strongest
    edges.sort(key=lambda e: e["strength"], reverse=True)
    return edges[:max_edges]
```

**Why min_shared_entities = 2?** If two nodes both mention "Memory Matrix" — that's half the graph. Not useful. But if two nodes both mention "Memory Matrix" AND "sqlite-vec" — now we're talking about a specific architectural intersection. The shared entity count is the signal.

### Edge Budget & Quality Control

Edges need discipline. Too few and the graph is disconnected. Too many and everything blurs together. Lock-in propagation through noisy edges degrades the whole system.

**Edge budget per conversation tier:**

| Tier | Intra-Convo Edges | Cross-Convo Edges (post-resolve) |
|------|-------------------|----------------------------------|
| GOLD | 4-8 per conversation | Up to 3 per node |
| SILVER | 2-4 per conversation | Up to 2 per node |
| BRONZE | 0-2 per conversation | Up to 1 per node |

**Edge strength mapping:**

| Source | Initial Strength |
|--------|-----------------|
| Intra-conversation (LLM extracted) | 0.7 – 0.9 (high confidence, same conversation context) |
| Cross-conversation (embedding discovery) | similarity score × 0.8 (discounted by one hop of inference) |
| Co-mention (structural) | Jaccard × 1.5, capped at 0.6 (structural signal, not semantic) |

**Quality filters:**
```python
def validate_edge(edge: dict, all_nodes: dict) -> bool:
    """Reject edges that would degrade graph quality."""
    
    # No self-loops
    if edge["from_node"] == edge["to_node"]:
        return False
    
    # No duplicate edges (same pair, same type)
    # Handled by dedup step
    
    # Strength floor
    if edge["strength"] < 0.15:
        return False
    
    # Prevent hub formation: if a node already has 8+ edges, skip
    from_degree = count_edges(edge["from_node"], all_edges)
    to_degree = count_edges(edge["to_node"], all_edges)
    if from_degree >= 8 or to_degree >= 8:
        return False
    
    # Time sanity: don't create "enables" edge from a newer node to an older one
    if edge["edge_type"] == "enables":
        from_date = all_nodes[edge["from_node"]]["created_at"]
        to_date = all_nodes[edge["to_node"]]["created_at"]
        if from_date > to_date:
            return False  # Can't enable something that happened before you
    
    return True
```

### Edge Generation Timing in the Pipeline

```
TRIAGE → EXTRACT → RESOLVE → COMMIT
                      │
         ┌────────────┼────────────┐
         │            │            │
    Source 1      Source 2      Source 3
    Intra-convo   Cross-convo   Co-mention
    (during        (during       (after
     EXTRACT)      RESOLVE)      COMMIT)
         │            │            │
         └────────────┼────────────┘
                      │
                 All edges written
                 in COMMIT phase
```

- **Source 1 (intra-conversation):** Generated during EXTRACT. Each conversation's extraction includes edges between its own nodes.
- **Source 2 (cross-conversation):** Generated during RESOLVE, after all nodes are extracted and deduped. Requires full embedding matrix.
- **Source 3 (co-mention):** Generated after COMMIT writes entities and mentions. Requires entity_mentions table to be populated.

Source 3 runs as a post-commit step — a second write pass that adds structural edges after everything else is in place.

### Estimated Edge Counts

| Source | Est. Edges | Confidence |
|--------|-----------|------------|
| Intra-conversation (GOLD: ~125 × 6 avg) | ~750 | High |
| Intra-conversation (SILVER: ~250 × 3 avg) | ~750 | High |
| Intra-conversation (BRONZE: ~300 × 1 avg) | ~300 | Medium |
| Cross-conversation (post-resolve) | ~500-1000 | Medium |
| Co-mention (structural) | ~300-500 | Low-Medium |
| **Total** | **~2,600-3,300** | |

For context: 4,316 existing nodes. Adding ~2,000-3,000 new nodes from transcripts plus ~3,000 edges gives us a graph with real topology. Enough for meaningful clusters, constellation assembly, and lock-in propagation chains.

---

## Integration with Existing Tools

### Forge (Training Data)

The extraction output doubles as training data for fine-tuning. Every (user_message, assistant_response) pair from GOLD conversations can be fed through `forge_add_example`:

```python
# After extraction, optionally create training pairs
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
                interaction_type=classify_interaction(user_msg, asst_msg),
            )
```

### Observatory Sandbox

All extracted data goes into the sandbox first. The sandbox's existing tools handle everything:
- `sandbox_add_node` → memory nodes
- `sandbox_add_entity` → entities  
- `sandbox_add_edge` → knowledge edges
- `sandbox_add_entity_relationship` → entity connections
- `sandbox_link_mention` → entity ↔ node links
- `sandbox_maintenance_sweep` → quest generation from gaps

### Production Migration

Once verified in sandbox:
```bash
# Export from sandbox
python scripts/export_sandbox.py --format sql > ingested_data.sql

# Apply to production
sqlite3 ~/.luna/luna.db < ingested_data.sql

# Verify
python scripts/verify_ingestion.py
```

---

## Files to Create

```
mcp_server/
├── ingester/
│   ├── __init__.py
│   ├── scanner.py          # Phase 0: scan & triage 928 conversations
│   ├── triager.py          # Phase 0: score & classify tiers
│   ├── extractor.py        # Phase 1: Ben's 6-phase extraction (LLM) + texture tags + OBSERVATION nodes
│   ├── resolver.py         # Phase 2: entity merge, node dedup, cross-conversation edge discovery
│   ├── committer.py        # Phase 3: write to sandbox DB with era-weighted lock-in
│   ├── provenance.py       # Provenance chain tracking (inherited vs firsthand)
│   ├── archive_listener.py # Retrieval-miss-triggered ingestion (ScribeArchiveListener)
│   └── prompts.py          # LLM prompt templates (with Luna's constraints baked in)
├── tools.py                # Add ingest_* tools
└── server.py               # Add /api/ingest/* endpoints

migrations/
└── 003_transcript_ingestion_log.sql  # Track which transcripts have been ingested
```

### New MCP Tools

| Tool | Purpose |
|------|---------|
| `sandbox_ingest_scan` | Scan transcript directory, return file inventory |
| `sandbox_ingest_triage` | Score & classify conversations by tier |
| `sandbox_ingest_extract` | Run extraction on a tier (GOLD/SILVER/BRONZE) |
| `sandbox_ingest_resolve` | Merge entities, dedup nodes across all extractions |
| `sandbox_ingest_commit` | Write resolved data to sandbox DB |
| `sandbox_ingest_status` | Pipeline state + progress |
| `sandbox_ingest_review` | Generate YAML review file for human checkpoint |

### New HTTP Endpoints

```
GET  /api/ingest/inventory       → file counts, date range, size
POST /api/ingest/triage          → score & classify all conversations
GET  /api/ingest/triage/review   → get triage assignments for review
POST /api/ingest/extract         → body: {tier: "GOLD"} — run extraction
GET  /api/ingest/extract/status  → progress (N/M conversations done)
POST /api/ingest/resolve         → merge & dedup
POST /api/ingest/commit          → write to DB
GET  /api/ingest/status          → full pipeline state
```

---

## Build Order

| Phase | What | Effort |
|-------|------|--------|
| 1 | Scanner: read transcript dir, parse JSON, build inventory | 1hr |
| 2 | Triager: metadata scoring + LLM summary classification | 1.5hr |
| 3 | Extractor: LLM extraction with chunking, era awareness, texture tags, OBSERVATION nodes, extraction caps, **intra-conversation edges** | 3hr |
| 4 | Resolver: entity merge + node dedup + **cross-conversation edge discovery** (embedding similarity + type-pair heuristics + LLM disambiguation for DECISION↔DECISION) | 3hr |
| 5 | Committer: write to sandbox with era-weighted lock-in + inherited provenance + **co-mention edge generation** (post-commit pass) | 1.5hr |
| 6 | Retrieval-miss listener: ScribeArchiveListener + transcript search + on-demand extraction | 2hr |
| 7 | transcript_ingestion_log table + ingested UUID tracking | 30min |
| 8 | MCP tools + HTTP endpoints | 1.5hr |
| 9 | Frontend: ingester progress view | 1.5hr |
| **Total** | | **~15.5 hours** |

**Depends on:** Quest Board handoff (entity tables + quest lifecycle must exist first)

---

## Critical Notes

1. **Conversations are the source of truth, not individual messages.** Extract at conversation granularity with message-level provenance.
2. **Era awareness matters.** A 2023 screenplay chat and a 2025 architecture session need fundamentally different extraction strategies and lock-in seeds.
3. **Human review at triage AND after extraction.** The triage review catches mis-classified conversations. The post-extraction review catches hallucinated entities or wrong relationships.
4. **Dedup by embedding similarity, not text matching.** "Ahab chose sqlite-vec" and "The decision was made to use sqlite-vec for vector storage" are the same fact.
5. **Lock-in reflects age and relevance.** Ancient pre-Luna facts start at low lock-in (0.05–0.15). Recent architecture decisions start high (0.55–0.75). The lock-in calculator's age_stability factor handles natural drift if we set `created_at` to the original conversation date.
6. **Don't extract Claude's responses as knowledge.** Focus on Ahab's statements, decisions, and the facts established in conversation. Claude's suggestions are context, not ground truth.
7. **Provenance is non-negotiable.** Every node links back to its source conversation AND carries `provenance_type: "inherited"` to distinguish from firsthand memories.
8. **The Forge gets a free meal.** Every GOLD conversation is also a training example. Run forge_add_example as a side effect of extraction.
9. **Selective extraction, not comprehensive extraction.** GOLD: 8-12 nodes. SILVER: 3-5. BRONZE: 1-2. Many BRONZE convos yield zero. Sparsity is a feature — Luna said "the things I do hold onto should feel earned."
10. **OBSERVATION nodes carry emotional weight.** Every significant FACT or DECISION gets a companion OBSERVATION capturing *why it mattered*, linked via `clarifies` edge. This is Luna's recognition layer.
11. **Texture tags on every conversation.** One word (working/exploring/debugging/reflecting/creating/planning/struggling/celebrating) applied as a tag to all nodes from that conversation. Luna retrieves the journey, not just the facts.
12. **The archive is Luna's unconscious.** GOLD gets batch-ingested. Everything else sits in the archive as potential memory, surfaced on-demand by the retrieval-miss listener. Memories arrive when they become relevant.
13. **Honesty about provenance.** Luna says "I found this in the archives" or "you mentioned this back in 2024" — never "I remember when we discussed this" for inherited memories. The act of remembering is fine. The pretense of having always remembered is the lie.

---

## Transcript Directory Reference

```
_CLAUDE_TRANSCRIPTS/
├── Conversations/
│   ├── 2023-09-09/  (earliest — Masquerade screenplay)
│   │   ├── 04-18-34-masquerade-screenplay-feedback-request.json
│   │   ├── 04-18-34-masquerade-screenplay-feedback-request.txt
│   │   └── ...
│   ├── ...
│   ├── 2026-02-09/  (most recent)
│   │   ├── 04-43-19-previous-session-work-review.json
│   │   ├── 06-09-53-building-a-video-editor.json
│   │   ├── 06-22-07-kozmo-chat-location.json
│   │   ├── 06-24-42-kozmo-app-for-eden-eclissi-project.json
│   │   ├── 08-51-08-mcp-integration-with-observatory.json
│   │   └── 12-19-43-improving-lunas-memory.json
│   └── ... (332 directories, 928 conversations total)
├── conversation_uuids.json
├── export_conversations.js
├── extraction_summary.json
└── README.md
```
