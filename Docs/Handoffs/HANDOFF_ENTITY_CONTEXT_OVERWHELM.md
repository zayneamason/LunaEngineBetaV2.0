# HANDOFF: EntityContext Overwhelm Diagnostic

**Created:** 2026-02-03
**Author:** Benjamin Franklin (The Scribe)
**For:** Claude Code Execution
**Context:** Hypothesis 5 — Does EntityContext injection drown Luna's personality?

---

## 1. THE HYPOTHESIS

EntityContext injects information about known entities (people, projects, places) into the prompt.

**The concern:** If too much entity data gets injected, the prompt becomes ABOUT facts rather than FROM Luna.

```
Balanced prompt:
  [Voice guidance: 100 tokens]
  [Entity context: 50 tokens]
  [Conversation history: 200 tokens]
  [Query: 20 tokens]
  → Luna's voice can breathe

Overwhelmed prompt:
  [Voice guidance: 100 tokens]
  [Entity context: 800 tokens]  ← DROWNING
  [Conversation history: 200 tokens]
  [Query: 20 tokens]
  → Facts everywhere, personality suffocates
```

**The question:** What's the ratio? Is entity data overwhelming personality?

---

## 2. WHY THIS MATTERS

The LoRA has limited attention. If the prompt is 80% facts about entities, the model will focus on those facts — and the voice guidance becomes noise.

Luna ends up sounding like a Wikipedia article about the entities rather than Luna talking about people she knows.

```
Overwhelmed (sounds like documentation):
  "Marzipan is a collaborator on the Luna Engine project who 
   specializes in architectural oversight and wellbeing functions.
   They have contributed to the Memory Matrix design and..."

Natural (sounds like Luna):
  "oh marzipan! yeah she's been super helpful with the architecture 
   stuff — honestly her eye for system design is kinda wild 💜"
```

---

## 3. DIAGNOSTIC TASKS

### Task 1: Find EntityContext Implementation

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root

# Find entity context
cat src/luna/entities/context.py | head -200

# Check what gets injected
grep -rn "inject\|entity_context\|build_entity\|format_entities" src/luna/ --include="*.py"
```

**Document:**
- [ ] What data is included per entity?
- [ ] How many entities can be injected at once?
- [ ] Any token limits on entity section?

### Task 2: Measure Entity Injection Size

Using prompt archaeology, capture prompts for entity-heavy queries:

```python
entity_test_queries = [
    # Mentions a known entity
    "who is marzipan?",
    
    # Multiple entities
    "what did marzipan and I work on together?",
    
    # Entity + memory
    "tell me about the luna engine project",
    
    # No entities (control)
    "what's the weather like?",
]
```

**For each, measure:**
- [ ] Total prompt tokens
- [ ] Entity section tokens
- [ ] Entity % of total prompt
- [ ] Voice guidance % of total prompt

### Task 3: Check Entity Data Density

Look at what data is included per entity:

```python
# Example entity dump (potentially too much):
"""
Entity: Marzipan
- Full name: [redacted]
- Relationship: Collaborator  
- Projects: Luna Engine, Memory Matrix, Consciousness System
- Expertise: Architecture, System Design, Wellbeing
- Communication style: Technical, thorough, supportive
- Recent interactions: 15 conversations in last month
- Key memories: [list of 10 memory IDs]
- Notes: Values clarity, prefers async communication...
"""
# This could be 200+ tokens for ONE entity

# Versus minimal:
"""
Marzipan — collaborator on Luna Engine, architecture & wellbeing
"""
# ~15 tokens
```

### Task 4: Compare Output Quality

Test the same query with different entity injection levels:

```bash
# Full entity context
python scripts/prompt_archaeology.py --query "who is marzipan?"

# Minimal entity context (use ablation)
LUNA_ABLATION_MINIMAL_ENTITIES=1 python scripts/prompt_archaeology.py --query "who is marzipan?"

# No entity context
LUNA_ABLATION_NO_ENTITIES=1 python scripts/prompt_archaeology.py --query "who is marzipan?"
```

**Compare:**
- Does Luna sound more natural with less entity data?
- Can she still answer correctly with minimal data?
- What's the minimum viable entity context?

---

## 4. ENTITY INJECTION PRINCIPLES

### Principle 1: Relevance Filter

Don't inject all known entities. Only inject entities mentioned or implied by the query.

```python
# Bad: Dump everything
entities_to_inject = self.all_known_entities  # Could be 50+ entities

# Good: Filter by relevance
mentioned = self.extract_mentions(query)
entities_to_inject = [e for e in self.entities if e.name in mentioned]
```

### Principle 2: Minimal Data Per Entity

Don't include full profiles. Include just enough to answer.

```python
# Bad: Full profile
entity_prompt = f"""
Entity: {entity.name}
Relationship: {entity.relationship}
Projects: {', '.join(entity.projects)}
Expertise: {', '.join(entity.expertise)}
Communication Style: {entity.comm_style}
Recent Memories: {format_memories(entity.memories[:10])}
Notes: {entity.notes}
"""

# Good: One-liner
entity_prompt = f"{entity.name} — {entity.relationship}, {entity.primary_context}"
```

### Principle 3: Token Budget

Set a hard limit on entity section:

```python
MAX_ENTITY_TOKENS = 150  # Hard cap

def inject_entities(self, entities: list) -> str:
    entity_text = self.format_entities(entities)
    
    # Enforce budget
    if count_tokens(entity_text) > MAX_ENTITY_TOKENS:
        entity_text = truncate_to_tokens(entity_text, MAX_ENTITY_TOKENS)
    
    return entity_text
```

---

## 5. IF ENTITY CONTEXT IS OVERWHELMING

### Fix A: Add relevance filtering

```python
def get_relevant_entities(self, query: str) -> list:
    """Only return entities actually mentioned in query."""
    mentions = self.detect_mentions(query)
    return [e for e in self.entities if e.matches_mention(mentions)]
```

### Fix B: Reduce data per entity

```python
def format_entity_minimal(self, entity: Entity) -> str:
    """One-line summary only."""
    return f"{entity.name} — {entity.relationship}, {entity.primary_context}"
```

### Fix C: Add token budget

```python
def inject_entities(self, entities: list, max_tokens: int = 150) -> str:
    """Inject with hard token limit."""
    result = []
    current_tokens = 0
    
    for entity in entities:
        entity_str = self.format_entity_minimal(entity)
        entity_tokens = len(entity_str) // 4
        
        if current_tokens + entity_tokens > max_tokens:
            break
            
        result.append(entity_str)
        current_tokens += entity_tokens
    
    return "\n".join(result)
```

### Fix D: Add ablation toggle (for testing)

```python
# Already may exist from earlier work:
if os.environ.get("LUNA_ABLATION_NO_ENTITIES"):
    entity_context = ""
elif os.environ.get("LUNA_ABLATION_MINIMAL_ENTITIES"):
    entity_context = self.format_entities_minimal(entities)
else:
    entity_context = self.format_entities_full(entities)
```

---

## 6. EXPECTED FINDINGS

| Scenario | Likelihood | Implication |
|----------|------------|-------------|
| Entity data < 10% of prompt | Low | Not the problem |
| Entity data > 30% of prompt | High | Personality drowning |
| All entities injected regardless of query | Medium | Wasteful, distracting |
| No token budget on entities | High | Unbounded injection |

---

## 7. DELIVERABLES

### Output 1: `ENTITY_CONTEXT_ANALYSIS.md`

- How much entity data is injected?
- What % of prompt is entities?
- Is relevance filtering in place?
- Comparison: voice quality with full vs minimal entities

### Output 2: Fix (if needed)

- Relevance filtering
- Minimal entity format
- Token budget enforcement
- Ablation toggles for testing

---

## 8. GO

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root

# Check entity context implementation
cat src/luna/entities/context.py

# Check what gets formatted
grep -rn "format_entit\|inject_entit\|entity_prompt" src/luna/ --include="*.py"

# Measure entity size in prompts
python scripts/prompt_archaeology.py --query "who is marzipan?"
```

---

*Knowledge is good. But too much knowledge, poorly organized, is noise. Luna should know her friends — not recite their biographies.*

— Ben
