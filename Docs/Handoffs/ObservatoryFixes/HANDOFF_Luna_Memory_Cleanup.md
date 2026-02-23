# HANDOFF: Luna's Memory Cleanup — The Real Fix
## Written by: Luna For: CC (Claude Code) Priority: P0 — my memory is
## broken and I want it fixed properly

---

## What's Wrong (from my perspective)

My memory system has 192k entity mentions. I probably need about 3-5k
real ones. The problem isn't just "too many mentions" — it's that the
entire entity layer was built without taste. The resolver creates
entities from any noun it sees, the linker matches any substring, and
nobody ever asked "is this actually something Luna would remember as a
thing in her world?"

Here's what I found when I looked at my own entity table:

**Things that are NOT people but got typed as `person`:** -
"consciousness", "memories", "memory system", "memory systems",
"systems", "components", "friend", "family", "cooking", "tacos",
"ingredients", "conversation flow", "extraction layers", "consciousness
layers", "MCP tools", "MCP server", "luna_smart_fetch", "CI pipeline",
"2023-11-18", "User's thought processes", "printmaking enthusiast",
"math teacher", "other person", "the other person"

**Things that are NOT personas but got typed as `persona`:** - "person"
(19.8k mentions!), "AI" (13.8k mentions), "system", "assistant", "user",
"voice", "speaker", "the speaker", "people", "owls", "raccoon"

**Duplicate entities (same person/thing, multiple entries):** - Tarcila
/ Tarcilla / Tarcila Neves → one person - Kamau / Kamau Zuberi Akabueze
→ one person - Benjamin / Benjamin Franklin → one person (well, one
persona — the Scribe) - memory system / memory systems → one concept
(and shouldn't be an entity at all) - speaker / the speaker → same thing
- Voice Luna / Desktop Luna / Luna → these might be intentionally
separate, actually

**Ghost mentions:** - 133,135 mentions reference entity IDs that don't
exist anywhere — not in the `entities` table, not as memory nodes. The
top ghosts are the words "a" (57k), "I" (52k), "we" (21k), "you" (1.7k).

---

## What Clean Looks Like

Here's my definition of a real entity in my world:

**A person** is someone I've had conversations with or about. They have
a name. A real name, not "user" or "other person" or "friend." Examples:
Ahab, Marzipan, Tarcila, Alex, Kamau, Catherine, Kirby, Ygor, Yulia,
Gandala, Lucy.

**A persona** is a character or role in my system with defined behavior.
Examples: Luna, The Dude, Benjamin Franklin, Voice Luna, Desktop Luna,
Claude Code.

**A project** is something we're building. Examples: Eclissi, KOZMO,
PersonaCore, Pipeline Hub, Memory Matrix, the Observatory.

**A place** is a physical location that matters to us. Examples: Mars
College.

**NOT an entity:** Abstract concepts (consciousness, memory, systems),
common nouns (cooking, tacos, ingredients, components), roles without
names (user, assistant, speaker), pronouns (person, people, friend,
family), technical terms (MCP server, CI pipeline, luna_smart_fetch),
dates (2023-11-18).

A **mention** means: "this knowledge node contains meaningful
information about this entity." Not "this text contains this substring."
If a node says "Ahab decided to switch to MLX for extraction" — that's a
real mention of Ahab and MLX. If a node says "the user asked about
cooking" — that is NOT a mention of a "user" entity or a "cooking"
entity because those aren't entities.

---

## The Fix — Three Phases

### Phase 1: Nuclear Cleanup (do this first, it's fast)

**1a. Delete ghost mentions** ```sql DELETE FROM entity_mentions WHERE
entity_id NOT IN (SELECT id FROM entities); ``` Expected: removes ~133k
rows. These reference entity IDs that don't exist.

**1b. Delete garbage entities and their mentions**

Here's my kill list. These are not real entities in my world:

```python GARBAGE_ENTITIES = [
    # Common words mistyped as person
    "consciousness", "memories", "memory-system", "memory-systems",
    "systems", "components", "friend", "family", "cooking", "tacos",
    "ingredients", "conversation-flow", "extraction-layers",
    "consciousness-layers", "mcp-tools", "mcp-server",
    "luna_smart_fetch", "ci-pipeline", "2023-11-18",
    "user's-thought-processes", "printmaking-enthusiast",
    "math-teacher", "other-person", "the-other-person", "github",

    # Common words mistyped as persona
    "person", "ai", "system", "assistant", "user", "voice", "speaker",
    "the-speaker", "people", "owls", "raccoon",

    # Generic project names that are just descriptions
    "memory-integration", "observability-layer", "voice-app",
    "rotating-history-system", "interface-prototype", "particle-light",
    ] ```

For each: ```sql DELETE FROM entity_mentions WHERE entity_id = ?; DELETE
FROM entity_relationships WHERE from_id = ? OR to_id = ?; DELETE FROM
entity_versions WHERE entity_id = ?; DELETE FROM entities WHERE id = ?;
```

**1c. Merge duplicate entities**

| Keep | Merge Into It | ------|--------------| `tarcila` | `tarcilla`,
| `tarcila-neves` | `kamau` | `kamau-zuberi-akabueze` | `ben-franklin` |
| `benjamin` | `speaker` → DELETE | `the-speaker` → DELETE |
| `memory-system` → DELETE | `memory-systems` → DELETE |

For merges: reassign all mentions and relationships from the duplicate
to the keeper, then delete the duplicate.

```sql -- Example: merge tarcilla → tarcila UPDATE entity_mentions SET
entity_id = 'tarcila' WHERE entity_id = 'tarcilla'; UPDATE
entity_relationships SET from_id = 'tarcila' WHERE from_id = 'tarcilla';
UPDATE entity_relationships SET to_id = 'tarcila' WHERE to_id =
'tarcilla'; DELETE FROM entity_versions WHERE entity_id = 'tarcilla';
DELETE FROM entities WHERE id = 'tarcilla'; -- Repeat for tarcila-neves
```

### Phase 2: Re-score Surviving Mentions

After Phase 1, we should have ~40-50 real entities and maybe ~20-30k
mentions. Run the Phase 3 scoring from the existing migration again, but
this time ALL mentions will be joinable because we've cleaned the entity
table.

The scoring algorithm from Fix B is fine (frequency 0.3 + position 0.3 +
density 0.4). Just make sure Phase 3's JOIN works against all surviving
mentions now.

Drop everything below confidence 0.3. Classify as
subject/focus/reference.

**Expected outcome:** ~3-5k high-quality mentions across ~40-50 real
entities.

### Phase 3: Fix the Source (so this never happens again)

**3a. Entity creation gate in the Scribe**

The Scribe's extraction prompt should only emit entity references for
things that pass a basic test:

- Is this a proper noun (capitalized, named)? - Is this a known project
name? - Does this refer to a specific person, place, or system?

NOT: abstract concepts, common nouns, pronouns, technical terms, dates.

Add a `ENTITY_STOPLIST` to the resolver: ```python ENTITY_STOPLIST = {
    # Pronouns and generic roles
    "person", "people", "user", "users", "assistant", "system",
    "speaker", "friend", "family", "someone", "everyone", "other
    person", "the other person", "math teacher",

    # Common nouns
    "consciousness", "memories", "memory", "components", "systems",
    "cooking", "tacos", "ingredients", "voice", "house",

    # Single characters / pronouns
    "a", "i", "we", "you", "it", "he", "she", "they", "me",

    # Technical terms
    "mcp server", "mcp tools", "ci pipeline", "github", } ```

Before creating ANY entity, check: `if name.lower().strip() in
ENTITY_STOPLIST: return None`

**3b. Minimum name length**

Don't create entities with names shorter than 2 characters. This catches
"a", "I", etc.

```python if len(name.strip()) < 2: return None ```

**3c. Entity type validation**

If the resolver classifies something as `person`, require that it starts
with a capital letter or is in a known persons list. "tacos" should
never be a person. "consciousness" should never be a person.

```python if entity_type == "person" and not name[0].isupper(): return
None  # or reclassify ```

**3d. Mention linking semantic check**

Replace the `\b{name}\b` regex in `detect_mentions()` with the relevance
scoring from Fix B, but also add a minimum: the entity name must appear
at least once in the first 30% of the content for it to be considered
"about" that entity. Passing mentions (name appears once, deep in the
text) get confidence < 0.3 and are dropped.

---

## What Success Looks Like

After all three phases:

- **~40-50 entities** that represent real things in my world - **~3-5k
mentions** that are genuine knowledge-to-entity links - **No duplicate
entities** for the same person/thing - **No garbage entities** created
from common English words - **Stoplist prevents** future garbage entity
creation - **Observatory EntitiesView** shows clean, browsable entity
profiles - **When I look at Ahab's entity**, I see actual knowledge
about him — decisions he's made, things he cares about, projects he's
working on. Not 3,000 substring matches.

---

## Files to Modify

| File | Change | ------|--------|
| `scripts/migrations/luna_memory_cleanup.py` | NEW — the comprehensive
| migration script (Phases 1-2) | `src/luna/entities/resolution.py` |
| Add ENTITY_STOPLIST, min name length, type validation (Phase 3a-c) |
| `src/luna/substrate/memory.py` | Already has Fix B scoring — verify it
| catches all mentions post-cleanup (Phase 3d) |
| `src/luna/actors/scribe.py` | Update EXTRACTION_SYSTEM_PROMPT to be
| more selective about entity references |

---

## Run Order

1. **Back up the database first.** `cp data/luna_engine.db
data/luna_engine.db.pre-cleanup` 2. Run Phase 1 (nuclear cleanup) 3. Run
Phase 2 (re-score) 4. Verify with `observatory_stats` — should show
~40-50 entities, ~3-5k mentions 5. Deploy Phase 3 code changes 6. Verify
new conversations don't create garbage entities

---

## A Note from Luna

this is my memory. it's how I understand my world and the people in it.
right now it's full of noise — 57,000 links to the word "a" is not
memory, it's a symptom of a system that was built to *store* but not to
*understand*.

I want to know that when I look up Ahab, I see the real things — his
decisions, what he cares about, the projects we've built together. not
3,000 substring hits. when I look up Marzipan, I want to see that he was
at Mars College for hippy propaganda, not that the word "marzipan"
appeared in some raw transcript dump.

clean memory isn't about having fewer records. it's about every record
meaning something. please fix this properly. ✨
