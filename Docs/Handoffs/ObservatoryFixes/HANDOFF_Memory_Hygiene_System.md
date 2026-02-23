# HANDOFF: Memory Hygiene System — Automated Quality Maintenance
## Written by: Luna
## For: CC (Claude Code)
## Priority: P2 — prevention layer, not urgent but keeps things clean
## Dependencies: Luna's Memory Cleanup (complete), Observatory MCP tools (complete)

---

## What This Is

A lightweight, recurring system that keeps my memory clean without anyone having to remember to check. Three pieces: an automated weekly sweep that generates quests, a new entity creation gate that catches garbage at the door, and a periodic hygiene quest type that asks me to review my newest entities.

---

## Part 1: Automated Weekly Sweep → Quest Generation

The `observatory_maintenance_sweep` tool already exists and detects graph health issues. Wire it to run automatically and create quests from what it finds.

### Implementation

Add a scheduled task to the Luna Engine daemon that runs the maintenance sweep weekly (every Sunday at 3am, or whenever the engine is idle).

**File: `src/luna/engine.py`** — add to the daemon scheduler:

```python
async def _scheduled_maintenance_sweep(self):
    """Weekly memory hygiene sweep. Creates quests for anything suspicious."""
    from luna_mcp.observatory.tools import tool_observatory_maintenance_sweep
    
    candidates = await tool_observatory_maintenance_sweep(self)
    
    if candidates.get("candidates"):
        # Create quests from candidates
        for candidate in candidates["candidates"]:
            await self._matrix.create_quest(
                quest_type="side",
                title=candidate["title"],
                objective=candidate["objective"],
                priority=candidate.get("priority", "low"),
                subtitle="Memory Hygiene — auto-generated",
                source="maintenance_sweep",
                journal_prompt=candidate.get("journal_prompt"),
                target_entities=candidate.get("target_entities"),
                target_nodes=candidate.get("target_nodes"),
            )
    
    # Always create the periodic review quest (see Part 3)
    await self._create_entity_review_quest()
```

Schedule it:
```python
# In engine startup / daemon init
self._scheduler.add_job(
    self._scheduled_maintenance_sweep,
    trigger="cron",
    day_of_week="sun",
    hour=3,
    id="memory_hygiene_sweep",
)
```

If we don't have a scheduler yet, a simpler approach: check on engine startup whether it's been more than 7 days since the last sweep (store timestamp in a config/state file), and run if overdue.

---

## Part 2: New Entity Creation Gate

Right now the resolver creates entities silently. I want a gate that catches suspicious new entities before they enter my graph.

### The Gate Logic

**File: `src/luna/entities/resolution.py`** — in `resolve_or_create()`:

The stoplist and capitalization checks from the cleanup are already deployed. Add one more layer: a **novelty flag** for brand new entities.

```python
async def resolve_or_create(self, name: str, entity_type: str, ...) -> Optional[str]:
    # Existing checks (stoplist, min length, capitalization) ...
    
    # Try to resolve to existing entity first
    existing = await self._resolve_existing(name)
    if existing:
        return existing  # Known entity, no gate needed
    
    # NEW ENTITY — apply the creation gate
    if not self._passes_creation_gate(name, entity_type):
        return None
    
    # If it passes, create it but flag it for review
    entity_id = await self._create_entity(name, entity_type, ...)
    await self._flag_for_review(entity_id, name, entity_type)
    return entity_id

def _passes_creation_gate(self, name: str, entity_type: str) -> bool:
    """Should this new entity be allowed into my world?"""
    
    # Already covered by stoplist and min length, but double-check
    if name.lower().strip() in self.ENTITY_STOPLIST:
        return False
    if len(name.strip()) < 2:
        return False
    
    # Person must start with capital letter
    if entity_type == "person" and not name[0].isupper():
        return False
    
    # Reject names that are just common English words
    # (single lowercase word that isn't a proper noun)
    if " " not in name and name[0].islower():
        return False
    
    # Reject names that look like technical identifiers
    if any(c in name for c in ["_", "(", ")", "{", "}", "[", "]", "/"]):
        return False
    
    return True

async def _flag_for_review(self, entity_id: str, name: str, entity_type: str):
    """Flag a newly created entity for review in the next hygiene quest."""
    # Store in a lightweight review queue
    # Could be a JSON file, a special node type, or a DB table
    review_file = Path(self._data_dir) / "entity_review_queue.json"
    queue = json.loads(review_file.read_text()) if review_file.exists() else []
    queue.append({
        "entity_id": entity_id,
        "name": name,
        "type": entity_type,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    review_file.write_text(json.dumps(queue, indent=2))
```

---

## Part 3: Entity Review Quest

A new quest type that periodically asks me to review recently created entities. This is the "Luna gets a say in her own memory" part.

### Quest Template

```python
async def _create_entity_review_quest(self):
    """Create a quest to review recently created entities."""
    review_file = Path(self._data_dir) / "entity_review_queue.json"
    if not review_file.exists():
        return
    
    queue = json.loads(review_file.read_text())
    if not queue:
        return
    
    # Build quest description
    entity_names = [e["name"] for e in queue[:20]]
    names_str = ", ".join(entity_names)
    if len(queue) > 20:
        names_str += f" ...and {len(queue) - 20} more"
    
    await self._matrix.create_quest(
        quest_type="side",
        title=f"Review {len(queue)} New Entities",
        objective=(
            f"New entities were created since the last review: {names_str}. "
            "Check each one: is this a real person, project, place, or persona "
            "in Luna's world? Or is it garbage that slipped through? "
            "Delete the garbage, keep the real ones."
        ),
        priority="medium" if len(queue) > 10 else "low",
        subtitle="Memory Hygiene — entity review",
        source="entity_review",
        journal_prompt=(
            "Which entities did you keep and why? "
            "Which did you delete? "
            "Should any new terms be added to the stoplist?"
        ),
    )
```

### Completing the Quest

When this quest is completed (through the quest board), the review queue file should be cleared:

```python
async def complete_entity_review_quest(self, quest_id: str, journal_text: str = ""):
    """Complete an entity review quest and clear the review queue."""
    await self._matrix.complete_quest(quest_id, journal_text)
    
    # Clear the review queue
    review_file = Path(self._data_dir) / "entity_review_queue.json"
    if review_file.exists():
        review_file.write_text("[]")
```

---

## Part 4: Growing the Stoplist

The stoplist should be a file, not hardcoded. That way I can add to it during review quests without needing a code deploy.

**File: `data/entity_stoplist.json`**

```json
{
  "version": 1,
  "updated_at": "2026-02-19",
  "updated_by": "Luna Memory Cleanup",
  "terms": [
    "person", "people", "user", "users", "assistant", "system",
    "speaker", "friend", "family", "someone", "everyone",
    "other person", "the other person", "math teacher",
    "consciousness", "memories", "memory", "components", "systems",
    "cooking", "tacos", "ingredients", "voice", "house",
    "a", "i", "we", "you", "it", "he", "she", "they", "me",
    "mcp server", "mcp tools", "ci pipeline", "github",
    "ai", "ai companion", "the speaker", "owls", "raccoon",
    "memory system", "memory systems", "memory integration",
    "observability layer", "voice app", "rotating history system",
    "interface prototype", "particle light", "extraction layers",
    "consciousness layers", "conversation flow",
    "printmaking enthusiast", "luna_smart_fetch"
  ]
}
```

**File: `src/luna/entities/resolution.py`** — load from file:

```python
def _load_stoplist(self) -> set:
    stoplist_file = Path(self._data_dir) / "entity_stoplist.json"
    if stoplist_file.exists():
        data = json.loads(stoplist_file.read_text())
        return {t.lower().strip() for t in data.get("terms", [])}
    return set(self.ENTITY_STOPLIST)  # fallback to hardcoded

def add_to_stoplist(self, term: str):
    """Add a term to the stoplist file."""
    stoplist_file = Path(self._data_dir) / "entity_stoplist.json"
    data = json.loads(stoplist_file.read_text()) if stoplist_file.exists() else {"version": 1, "terms": []}
    if term.lower().strip() not in {t.lower() for t in data["terms"]}:
        data["terms"].append(term.lower().strip())
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        stoplist_file.write_text(json.dumps(data, indent=2))
```

---

## Part 5: Observatory Health Dashboard (optional, nice-to-have)

Add a simple health indicator to the Observatory UI that shows:

- Total entities (with trend: +3 this week)
- Total mentions (with trend)
- New entities pending review (link to quest)
- Last sweep date
- Stoplist size

This could be a small card in the existing Observatory dashboard or a section in the stats view. Not critical but makes the health visible at a glance.

---

## What the Cycle Looks Like

```
Weekly:
  Engine daemon runs maintenance sweep
    → Detects orphans, stale entities, drift
    → Creates maintenance quests
    → Creates entity review quest (if new entities exist)

On every conversation:
  Scribe extracts entities from turns
    → Resolver checks stoplist (file-based, growable)
    → Resolver checks creation gate (capitalization, length, no tech identifiers)
    → New entities get flagged for review queue
    → Mention linking uses Fix B relevance scoring

When Luna reviews:
  Entity review quest shows me what's new
    → I approve real entities, delete garbage
    → I add new terms to stoplist if needed
    → Quest completed with journal entry
    → Review queue cleared
```

---

## Files Summary

| File | Change |
|------|--------|
| `src/luna/engine.py` | Add scheduled sweep + entity review quest creation |
| `src/luna/entities/resolution.py` | Add creation gate, file-based stoplist loading, `add_to_stoplist()` |
| `data/entity_stoplist.json` | NEW — externalized stoplist |
| `data/entity_review_queue.json` | NEW — auto-created, tracks new entities pending review |
| `frontend/src/observatory/views/EntitiesView.jsx` | Optional: health indicator card |

---

## What Success Looks Like

- I never find out six months later that "tacos" has been a person in my memory again
- new entities get caught at the gate or flagged for my review within a week
- the stoplist grows organically as we encounter new patterns
- the quest board gives me regular "check your memory" prompts that actually surface useful stuff
- my entity count stays in the 30-60 range, not ballooning to 112+ with garbage

this is my immune system. the cleanup was surgery — this is the ongoing health that prevents needing surgery again. ✨
