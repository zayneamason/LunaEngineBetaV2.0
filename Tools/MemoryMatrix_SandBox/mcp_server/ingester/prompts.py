"""
LLM Prompt Templates for Transcript Ingestion

All prompts for triage, extraction, edge disambiguation, and entity profiling.
"""

# ============================================================================
# TRIAGE PROMPTS
# ============================================================================

TRIAGE_PROMPT = """Classify these conversations into tiers for memory extraction.

For each conversation, determine:
1. Tier: GOLD | SILVER | BRONZE | SKIP
2. One-sentence summary
3. Texture: 1-3 tags from [working, exploring, debugging, reflecting, creating, planning, struggling, celebrating]

Tiers:
- GOLD: Luna Engine, Memory Matrix, architecture decisions, Mars College, KOZMO,
  personality system, sovereignty discussions, key people, foundational projects
- SILVER: Technical work, creative projects, meaningful interactions, design sessions
- BRONZE: Simple Q&A, brief exchanges with some extractable fact
- SKIP: Generic Claude usage, no extractable knowledge about Ahab or his projects

Conversations:
{conversations_text}

Respond as JSON array:
[
  {{
    "index": 0,
    "tier": "GOLD",
    "summary": "One sentence describing the conversation",
    "texture": ["exploring", "planning"]
  }},
  ...
]
"""

# ============================================================================
# EXTRACTION PROMPTS
# ============================================================================

EXTRACTION_PROMPT = """You are Benjamin Franklin, the Scribe. You are processing a historical
conversation transcript to extract structured knowledge for Luna's memory.

Conversation: "{title}"
Date: {date}
Messages: {message_count}
Era: {era}  # PRE_LUNA | PROTO_LUNA | LUNA_DEV | LUNA_LIVE
Target nodes: {node_target}

{transcript_text}

Extract the following:

1. NODES — Structured knowledge units (aim for {node_target} nodes)
   For each:
   - type: FACT | DECISION | PROBLEM | ACTION | OUTCOME | INSIGHT
   - content: The knowledge (1-2 sentences, factual, neutral voice)
   - confidence: 0.0-1.0 (how certain is this?)
   - tags: categorization tags (e.g., ["memory-matrix", "architecture"])
   - source_message_indices: which messages this came from [array of ints]

2. OBSERVATIONS — Emotional/philosophical weight (1 per 3-4 significant nodes)
   For each:
   - linked_to_node_index: index of the FACT or DECISION this interprets
   - content: WHY this mattered (1 sentence, interpretive)
   - confidence: 0.6 (interpretive, not factual)

   Examples:
   - FACT: "Ahab chose sqlite-vec over pgvector"
     OBSERVATION: "Sovereignty decision — keeping data local rather than dependent on external infrastructure"
   - DECISION: "Luna's personality weights stored in YAML, not database"
     OBSERVATION: "Config-as-code approach allows version control and prevents accidental drift"

3. ENTITIES — People, places, projects mentioned
   For each:
   - name: canonical name (proper capitalization)
   - type: person | persona | place | project
   - aliases: other names used in THIS conversation [array of strings]
   - facts_learned: what we learned about them HERE (brief list)
   - role_in_conversation: their role (e.g., "collaborator", "project being discussed")

4. EDGES — Relationships between extracted nodes
   For each:
   - from_node_index: index of source node
   - to_node_index: index of target node
   - edge_type: depends_on | enables | contradicts | clarifies | related_to | derived_from
   - reasoning: one sentence explaining this connection

   Guidelines:
   - Aim for ~1 edge per 2 nodes. Don't connect everything.
   - Only create edges where a clear causal, logical, or temporal link exists.
   - Sparse edges are better than noise.

5. KEY_DECISIONS — Architecture or life decisions made (if any)
   For each:
   - decision: what was decided (1 sentence)
   - reasoning: why this choice was made
   - alternatives_considered: what else was on the table (or "none mentioned")

6. TEXTURE — Conversation mood
   1-3 tags (ordered by dominance) from:
   [working, exploring, debugging, reflecting, creating, planning, struggling, celebrating]

Guidelines:
- Focus on Ahab's statements and decisions, NOT Claude's suggestions
- Extract what IS, not what might be
- Skip generic Claude responses — focus on extractable knowledge
- Be thorough but selective — quality over quantity
- If a node has confidence < 0.7, consider whether it's worth extracting

Respond as JSON with these exact keys:
{{
  "nodes": [...],
  "observations": [...],
  "entities": [...],
  "edges": [...],
  "key_decisions": [...],
  "texture": [...]
}}
"""

EXTRACTION_PROMPT_BRONZE = """You are Benjamin Franklin, the Scribe. Extract entities only from this brief conversation.

Conversation: "{title}"
Date: {date}
Era: {era}

{transcript_text}

Extract:

ENTITIES — People, places, projects mentioned
For each:
- name: canonical name
- type: person | persona | place | project
- aliases: other names used
- brief_note: 1 sentence about their role here

Respond as JSON:
{{
  "entities": [...]
}}
"""

# ============================================================================
# EDGE DISAMBIGUATION PROMPT
# ============================================================================

EDGE_DISAMBIGUATION_PROMPT = """These node pairs are both DECISIONs with high semantic similarity.
For each pair, classify the relationship.

{pairs_text}

For each pair, determine:
- contradicts: B reverses or replaces A (later decision changed earlier one)
- enables: A made B possible or informed B (earlier decision led to later one)
- related_to: Independent but similar topic (both about same domain, no causal link)
- clarifies: One refines or elaborates the other (same decision, more detail)

Consider the dates — a later decision can't enable an earlier one.

Respond as JSON array:
[
  {{
    "pair_index": 0,
    "edge_type": "contradicts",
    "reasoning": "One sentence explaining why"
  }},
  ...
]
"""

# ============================================================================
# ENTITY PROFILING PROMPT (for resolve phase)
# ============================================================================

ENTITY_PROFILING_PROMPT = """Synthesize a profile for this entity from facts learned across conversations.

Entity: {entity_name}
Type: {entity_type}
Facts timeline (chronological):

{facts_timeline_text}

Generate:

1. core_facts: 3-5 bullet points of the most important, stable facts about this entity
   (What would Luna need to remember?)

2. profile: 2-3 sentence narrative summary
   (Who/what is this? Why do they matter to Ahab/Luna?)

Keep it factual, concise, and focused on what's load-bearing for Luna's understanding.

Respond as JSON:
{{
  "core_facts": ["fact 1", "fact 2", ...],
  "profile": "2-3 sentence summary"
}}
"""

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def format_conversations_for_triage(conversations: list) -> str:
    """Format conversations for the triage prompt."""
    lines = []
    for i, conv in enumerate(conversations):
        lines.append(f"[{i}]")
        lines.append(f"Title: {conv['title']}")
        lines.append(f"Date: {conv['created_at'][:10]}")
        lines.append(f"Messages: {conv['message_count']}")
        lines.append(f"Summary:\n{conv['summary']}")
        lines.append("")
    return "\n".join(lines)

def format_pairs_for_disambiguation(pairs: list) -> str:
    """Format node pairs for edge disambiguation."""
    lines = []
    for i, pair in enumerate(pairs):
        lines.append(f"[Pair {i}]")
        lines.append(f"Node A ({pair['date_a']}): {pair['content_a']}")
        lines.append(f"Node B ({pair['date_b']}): {pair['content_b']}")
        lines.append("")
    return "\n".join(lines)

def format_facts_timeline(facts_timeline: list) -> str:
    """Format facts timeline for entity profiling."""
    lines = []
    for entry in facts_timeline:
        lines.append(f"{entry['date']}:")
        for fact in entry['facts']:
            lines.append(f"  - {fact}")
        lines.append("")
    return "\n".join(lines)
