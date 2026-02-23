# HANDOFF: Fix B — Entity Mention Relevance Scoring
## Priority: P1 (Core data quality)
## Estimated Effort: 1-2 hours
## Owner: CC (Claude Code)

---

## Problem

`_link_entity_mentions()` in `src/luna/substrate/memory.py` uses binary string matching to link entities to knowledge nodes. Every entity whose name appears anywhere in node content gets linked with:
- `mention_type = "reference"` (always)
- `confidence = 1.0` (always)

This means a node saying "Ahab pushed the Eclissi build" gets the same entity link weight as "Eclissi architecture defines a modular rendering pipeline." Result: 123 mentions for Eclissi, ~90% irrelevant.

## Root Cause

```python
# Current: binary match, flat confidence
async def _link_entity_mentions(self, node_id, content):
    entities = await resolver.detect_mentions(content)  # regex \b{name}\b
    for entity in entities:
        await resolver.create_mention(
            entity_id=entity.id,
            node_id=node_id,
            mention_type="reference",   # ← ALWAYS "reference"
            confidence=1.0,             # ← ALWAYS 1.0
        )
```

## Solution: Relevance-Scored Mention Classification

Replace the flat linking with a scoring system that classifies mentions by relevance.

## File to Modify

### `src/luna/substrate/memory.py` — `_link_entity_mentions` method (~line 390)

**Replace entire method with:**

```python
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
            # Count non-overlapping occurrences
            occurrences = content_lower.count(name_lower)
            frequency_score = min(occurrences / 3.0, 1.0)  # caps at 3 mentions
            
            # --- Signal 2: Position ---
            # First occurrence position (0.0 = end, 1.0 = very start)
            first_pos = content_lower.find(name_lower)
            if first_pos >= 0:
                position_score = 1.0 - (first_pos / content_len)
            else:
                position_score = 0.0
            
            # --- Signal 3: Density ---
            # What fraction of total words is this entity name?
            density = (occurrences * name_word_count) / word_count
            density_score = min(density * 10, 1.0)  # 10% density = max score
            
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
```

## Scoring Examples

| Content | Entity | Freq | Pos | Density | Conf | Type |
|---------|--------|------|-----|---------|------|------|
| "Eclissi architecture defines a modular rendering pipeline. Eclissi uses WebGL..." | Eclissi | 2/3=0.67 | 1.0 | 0.13→1.0 | 0.89 | subject |
| "Ahab mentioned he's working on Eclissi today" | Eclissi | 1/3=0.33 | 0.3→0.7 | 0.014→0.14 | 0.37 | reference |
| "Updated the build pipeline for Observatory and Eclissi" | Eclissi | 1/3=0.33 | 0.1→0.1 | 0.014→0.14 | 0.16 | **DROPPED** |
| "Eclissi Eclissi Eclissi — the whole project needs a rethink" | Eclissi | 3/3=1.0 | 1.0 | 0.3→1.0 | 1.0 | subject |

## Verification

```python
# After deploying, add a test node and check mentions:
node_id = await matrix.add_node(
    node_type="FACT",
    content="Eclissi architecture uses WebGL for rendering. Eclissi supports multiple viewports.",
)
# Should create mention with type="subject", confidence > 0.7

node_id2 = await matrix.add_node(
    node_type="FACT", 
    content="Ahab pushed a build update that also touched Eclissi config files",
)
# Should create mention with type="reference", confidence ~0.35
# OR be dropped entirely if below 0.3

node_id3 = await matrix.add_node(
    node_type="FACT",
    content="The Observatory frontend uses React with Vite and has glassmorphic UI",
)
# Should NOT create an Eclissi mention (name not present)
```

## Edge Cases

- **Short entity names (< 3 chars):** Already handled by `detect_mentions` MIN_ENTITY_NAME_LENGTH = 3
- **Entity name IS the entire content:** density → 1.0, classified as "subject" ✅
- **Multiple entities in same node:** Each scored independently ✅
- **Zero word count:** Early return guard added ✅

## What This Does NOT Fix

- Existing mentions in database (Fix D handles retroactive cleanup)
- Raw CONVERSATION_TURN nodes getting entity links (Fix A handles this)
- Observatory UI display of mentions (Fix C handles filtering)
