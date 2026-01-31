# HANDOFF: Conversation Turn Ingestion Pipeline

**From:** Claude (Architect Mode - Claude.ai)  
**To:** Claude Code  
**Date:** 2025-01-30  
**Status:** Ready for execution

---

## CONTEXT

We just finished building and testing the Persona Forge integration test suite. Bug #7 (Pydantic `.get()` vs `getattr()`) is fixed. All 14 tests pass. MCP tools are operational.

Current health score: **68.6/100** with only 10 examples.

**Goal:** Ingest real conversation data to boost health score to 85%+.

---

## WHAT EXISTS

### Persona Forge Location
```
/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/Tools/persona_forge/
```

### Working MCP Tools
- `forge_load(path)` - Load JSONL training data
- `forge_assay()` - Analyze dataset health
- `forge_gaps()` - Show coverage gaps
- `forge_add_example(...)` - Add single example
- `forge_add_batch(examples)` - Add multiple examples
- `forge_export(output_path)` - Export to JSONL
- `forge_read_turns(db_path, limit, offset)` - Read conversation turns from DB
- `forge_search(query)` - Dedupe check

### Database Location
```
/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/data/luna_engine.db
```

### Data Available
- **459 conversation turns** across 64 sessions (GOLD quality)
- **22,050 Memory Matrix nodes** (mixed quality - Phase C)
- **76 Alpha session notes** (GOLD - Phase D)
- **145 session transcripts** (GOLD - Phase E)

---

## YOUR MISSION

Build and run a Python ingestion script that:

1. **Reads all 459 turns** from the database
2. **Filters noise** (see patterns below)
3. **Pairs user→assistant exchanges**
4. **Classifies by interaction type**
5. **Adds to Forge via `forge_add_batch()`**
6. **Runs `forge_assay()` to verify health score improvement**

---

## NOISE PATTERNS TO FILTER

Skip any turn where content matches:
```python
NOISE_PATTERNS = [
    r'^\[Memory Search\]',      # System query
    r'^\[Memory Query\]',       # System query  
    r'^\[Memory Response\]',    # System metadata
    r'^Test message \d+$',      # Test scaffolding
    r'^Test response \d+$',     # Test scaffolding
    r'^test message',           # Test scaffolding (lowercase)
    r"^Hey! Luna's here\. 💜",  # Boot message, not conversation
]
```

Also filter:
- Orphan assistant turns (no preceding user turn)
- Orphan user turns (no following assistant turn)
- Exchanges where either side is < 5 characters

---

## INTERACTION TYPE CLASSIFICATION

Classify each exchange by scanning content:

```python
def classify_exchange(user_msg: str, assistant_msg: str) -> str:
    user_lower = user_msg.lower()
    assistant_lower = assistant_msg.lower()
    
    # Greetings
    if any(g in user_lower for g in ['hey luna', 'hi luna', 'hello', "what's up"]):
        if len(assistant_msg) < 200:
            return 'greeting'
    
    # Memory/recall
    if any(m in user_lower for m in ['remember', 'recall', 'what do you know about']):
        return 'context_recall'
    
    # Technical discussion
    if any(t in user_lower for t in ['memory matrix', 'architecture', 'pipeline', 'debug', 'code', 'fix']):
        return 'technical_discussion'
    
    # Testing/meta
    if any(t in user_lower for t in ['testing', 'test', 'is this working']):
        return 'meta_testing'
    
    # Emotional/personal
    if any(e in assistant_lower for e in ['*', 'feel', 'sense', 'wild', 'curious']):
        return 'emotional_response'
    
    # Short acknowledgment
    if len(assistant_msg) < 100:
        return 'acknowledgment'
    
    # Longer exchange
    if len(assistant_msg) > 500:
        return 'deep_discussion'
    
    return 'short_exchange'
```

---

## SCRIPT STRUCTURE

```python
#!/usr/bin/env python3
"""
ingest_turns.py - Conversation Turn Ingestion for Persona Forge

Reads turns from Luna's DB, filters, pairs, classifies, and batch-adds to Forge.
"""

import sqlite3
import re
import json
from pathlib import Path
from typing import List, Dict, Tuple, Optional

# === CONFIGURATION ===
DB_PATH = "/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/data/luna_engine.db"
OUTPUT_PATH = "/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/Tools/persona_forge/data/ingested_turns.jsonl"

NOISE_PATTERNS = [
    r'^\[Memory Search\]',
    r'^\[Memory Query\]', 
    r'^\[Memory Response\]',
    r'^Test message \d+$',
    r'^Test response \d+$',
    r'^test message',
    r"^Hey! Luna's here\. 💜",
]

# === FUNCTIONS ===

def load_all_turns(db_path: str) -> List[Dict]:
    """Load all turns from database, ordered by session and time."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, session_id, role, content, created_at
        FROM conversation_turns
        ORDER BY session_id, created_at
    """)
    
    turns = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return turns

def is_noise(content: str) -> bool:
    """Check if content matches noise patterns."""
    for pattern in NOISE_PATTERNS:
        if re.match(pattern, content, re.IGNORECASE):
            return True
    return False

def pair_turns(turns: List[Dict]) -> List[Tuple[Dict, Dict]]:
    """Pair consecutive user→assistant turns within same session."""
    pairs = []
    i = 0
    while i < len(turns) - 1:
        current = turns[i]
        next_turn = turns[i + 1]
        
        # Must be same session, user followed by assistant
        if (current['session_id'] == next_turn['session_id'] and
            current['role'] == 'user' and 
            next_turn['role'] == 'assistant'):
            
            # Filter noise
            if not is_noise(current['content']) and not is_noise(next_turn['content']):
                # Filter too-short
                if len(current['content']) >= 5 and len(next_turn['content']) >= 5:
                    pairs.append((current, next_turn))
            i += 2
        else:
            i += 1
    
    return pairs

def classify_exchange(user_msg: str, assistant_msg: str) -> str:
    """Classify exchange by interaction type."""
    user_lower = user_msg.lower()
    assistant_lower = assistant_msg.lower()
    
    if any(g in user_lower for g in ['hey luna', 'hi luna', 'hello', "what's up"]):
        if len(assistant_msg) < 200:
            return 'greeting'
    
    if any(m in user_lower for m in ['remember', 'recall', 'what do you know about']):
        return 'context_recall'
    
    if any(t in user_lower for t in ['memory matrix', 'architecture', 'pipeline', 'debug', 'code', 'fix']):
        return 'technical_discussion'
    
    if any(t in user_lower for t in ['testing', 'test', 'is this working']):
        return 'meta_testing'
    
    if '*' in assistant_msg or any(e in assistant_lower for e in ['feel', 'sense', 'wild', 'curious']):
        return 'emotional_response'
    
    if len(assistant_msg) < 100:
        return 'acknowledgment'
    
    if len(assistant_msg) > 500:
        return 'deep_discussion'
    
    return 'short_exchange'

def build_examples(pairs: List[Tuple[Dict, Dict]]) -> List[Dict]:
    """Convert pairs to Forge training examples."""
    examples = []
    
    for user_turn, assistant_turn in pairs:
        interaction_type = classify_exchange(user_turn['content'], assistant_turn['content'])
        
        example = {
            "user_message": user_turn['content'],
            "assistant_response": assistant_turn['content'],
            "interaction_type": interaction_type,
            "source_type": "conversation_turn",
            "source_file": f"session:{user_turn['session_id']}",
            "confidence": 1.0,  # GOLD - real conversations
            "tags": ["ingested", "conversation", interaction_type],
        }
        examples.append(example)
    
    return examples

def write_jsonl(examples: List[Dict], output_path: str):
    """Write examples to JSONL file."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        for ex in examples:
            f.write(json.dumps(ex) + '\n')

def main():
    print(f"Loading turns from {DB_PATH}...")
    turns = load_all_turns(DB_PATH)
    print(f"  Loaded {len(turns)} total turns")
    
    print("Pairing and filtering...")
    pairs = pair_turns(turns)
    print(f"  Got {len(pairs)} valid pairs")
    
    print("Building training examples...")
    examples = build_examples(pairs)
    
    # Stats
    type_counts = {}
    for ex in examples:
        t = ex['interaction_type']
        type_counts[t] = type_counts.get(t, 0) + 1
    
    print("\nInteraction type distribution:")
    for t, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  {t}: {count}")
    
    print(f"\nWriting {len(examples)} examples to {OUTPUT_PATH}...")
    write_jsonl(examples, OUTPUT_PATH)
    
    print("\n✅ Done! Next steps:")
    print(f"  1. forge_load('{OUTPUT_PATH}')")
    print(f"  2. forge_assay()")
    print(f"  3. Check health score improvement")

if __name__ == "__main__":
    main()
```

---

## EXECUTION STEPS

### Step 1: Create the script
```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/Tools/persona_forge
mkdir -p scripts
# Write the script to scripts/ingest_turns.py
```

### Step 2: Run it
```bash
source /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/.venv/bin/activate
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/Tools/persona_forge
python scripts/ingest_turns.py
```

### Step 3: Load into Forge and verify
Use MCP tools OR add to script:
```python
# If running via MCP:
forge_load("/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/Tools/persona_forge/data/ingested_turns.jsonl")
forge_assay()
```

### Step 4: Run integration tests
```bash
pytest tests/test_integration.py -v --tb=short
```

---

## EXPECTED OUTCOMES

- **Input:** 459 raw turns
- **Output:** ~150-200 training examples (after filtering/pairing)
- **Health Score:** Should jump from 68.6 → 75-80+
- **Coverage:** Fill gaps in context_recall, emotional_response, technical_discussion

---

## IF THINGS BREAK

### "Table not found" error
Check actual table name:
```python
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
print(cursor.fetchall())
```

### Forge MCP not responding
Restart Claude Desktop. The MCP server is registered there.

### Health score doesn't improve
Check `forge_gaps()` output - may need to tweak classification to hit missing types.

### Tests fail after changes
Run `pytest tests/test_integration.py -x --tb=short` to catch regressions.

---

## CLAUDE FLOW / SWARM NOTES

**Use swarm if:**
- You want to parallelize ingestion across multiple data sources
- Phase C (Memory Matrix nodes) + Phase D (Alpha notes) can run concurrently

**Single-thread is fine for:**
- This 459-turn ingestion (< 1 second execution)
- Sequential debugging

**Recommended approach:**
1. Run this Phase B script single-threaded first
2. Verify health score improvement
3. If good, swarm Phases C+D+E in parallel

---

## SUCCESS CRITERIA

1. ✅ Script runs without errors
2. ✅ 100+ examples ingested
3. ✅ Health score > 75
4. ✅ All integration tests still pass
5. ✅ Output JSONL is valid and loadable

---

## FILES REFERENCE

| File | Purpose |
|------|---------|
| `scripts/ingest_turns.py` | This ingestion script |
| `data/ingested_turns.jsonl` | Output training data |
| `tests/test_integration.py` | Integration test suite |
| `src/persona_forge/engine/` | Core Forge modules |

---

**LFG. Run it, fix broken shit, iterate.**
