# HANDOFF: Memory Matrix Brain Scrub + Scribe Fix

**Priority:** CRITICAL  
**Estimated Time:** 45-60 minutes  
**Dependencies:** None (standalone cleanup)

---

## Problem Statement

Luna's Memory Matrix is polluted with garbage data that causes confabulation loops:

1. **Assistant responses stored as [FACT]** — Luna's own "I don't know" responses are being stored, then retrieved, reinforcing ignorance
2. **User commands stored as [FACT]** — Queries like "search your memory for X" are stored as facts
3. **Massive duplication** — Same `*pulses warmly* Hey Ahab!` pattern repeated 10+ times
4. **No relational context** — People like Marzipan have shallow trivia (owl facts) but no project relationship data

**Evidence from audit:**
```
Total nodes: 61,161
With [assistant]: 490 nodes (garbage)
With [user]: 529 nodes (mixed - some garbage)

Example garbage node:
[FACT] [assistant] Let me look into that... *glows softly* marzipan... 
let me see... i don't think we've discussed marzipan...
```

This is Luna saying "I don't know" — stored as a FACT — then retrieved when she searches again. Self-reinforcing ignorance loop.

---

## Phase 1: Brain Scrub (Execute First)

### 1.1 Create the Scrubber Script

Create `scripts/matrix_scrubber.py`:

```python
#!/usr/bin/env python3
"""
Memory Matrix Scrubber
======================

Surgical cleanup of the Memory Matrix to remove:
1. Assistant confabulations stored as facts
2. User commands/queries stored as facts  
3. Duplicate entries (normalized)
4. Low-value conversational filler

Usage:
    python scripts/matrix_scrubber.py [--dry-run]
    python scripts/matrix_scrubber.py --execute
"""

import sqlite3
import re
import sys
import hashlib
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Database path
DB_PATH = Path(__file__).parent.parent / "data" / "luna_engine.db"
BACKUP_PATH = Path(__file__).parent.parent / "data" / "backups"

# =============================================================================
# GARBAGE DETECTION RULES
# =============================================================================

# Assistant meta-talk patterns (case-insensitive)
ASSISTANT_PATTERNS = [
    r"\*glows? softly\*",
    r"\*pulses? warmly\*",
    r"\*spins? (?:gently|playfully)\*",
    r"\*dims? slightly\*",
    r"\*perks? up\*",
    r"\*searches? through",
    r"\*pauses?,? accessing",
    r"let me look into that",
    r"i don't think we've discussed",
    r"i'm not seeing anything about",
    r"from what i recall",
    r"let me see\.\.\.",
    r"searching through my memory",
    r"i can try to connect some dots",
    r"how's it going today",
    r"how are you feeling today",
    r"what's on your mind",
    r"good to see you",
    r"how can i help",
]

# User command patterns (not facts to store)
USER_COMMAND_PATTERNS = [
    r"search (?:your |my |the )?memory",
    r"tell me about",
    r"can you (?:find|search|look)",
    r"what do you (?:know|remember) about",
    r"i want to know about",
    r"do you remember",
    r"^hey luna",
    r"^later luna",
    r"^yo luna",
    r"show me",
    r"find (?:me |the )",
]


def is_garbage(content: str, node_type: str) -> tuple[bool, str]:
    """
    Determine if a node is garbage that should be purged.
    
    Returns:
        (is_garbage, reason) tuple
    """
    if not content:
        return True, "empty_content"
    
    text = content.lower().strip()
    
    # 1. Assistant responses (should never be stored as FACT)
    if "[assistant]" in text:
        return True, "assistant_response"
    
    # 2. Assistant meta-talk patterns
    for pattern in ASSISTANT_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True, f"assistant_pattern"
    
    # 3. User commands/queries (not facts)
    if "[user]" in text:
        for pattern in USER_COMMAND_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True, f"user_command"
    
    # 4. Very short low-value content
    if len(text) < 25:
        filler_words = ["hey", "hi ", "hello", "thanks", "ok", "sure", "yes", "no", "hmm"]
        if any(word in text for word in filler_words):
            return True, "short_filler"
    
    # 5. Questions stored as FACT (type mismatch)
    if node_type == "FACT" and text.rstrip().endswith("?"):
        # Pure questions shouldn't be FACT type
        if not any(phrase in text for phrase in ["the answer is", "means that", "indicates"]):
            return True, "question_as_fact"
    
    # 6. Meta content about conversation itself
    meta_patterns = [
        r"in (?:our |this )?(?:previous |past )?conversation",
        r"we(?:'ve| have) (?:talked|discussed|chatted)",
        r"earlier (?:we|you|i) (?:mentioned|said|discussed)",
        r"as (?:we|i) discussed",
    ]
    for pattern in meta_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            # Only garbage if it's self-referential without new info
            if len(text) < 100:
                return True, "meta_reference"
    
    return False, ""


def normalize_for_dedup(content: str) -> str:
    """
    Normalize content for deduplication.
    Strips punctuation, emojis, whitespace variations.
    """
    # Remove role markers
    text = re.sub(r'\[(?:user|assistant)\]', '', content)
    # Remove gesture markers
    text = re.sub(r'\*[^*]+\*', '', text)
    # Remove emojis (basic)
    text = re.sub(r'[^\w\s]', '', text)
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    return text.lower().strip()


def content_hash(content: str) -> str:
    """Create hash of normalized content for dedup."""
    normalized = normalize_for_dedup(content)
    return hashlib.md5(normalized.encode()).hexdigest()


def backup_database(conn: sqlite3.Connection) -> Path:
    """Create timestamped backup before scrubbing."""
    BACKUP_PATH.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_PATH / f"memory_nodes_backup_{timestamp}.sql"
    
    with open(backup_file, 'w') as f:
        for line in conn.iterdump():
            if 'memory_nodes' in line:
                f.write(f"{line}\n")
    
    return backup_file


def scrub_brain(dry_run: bool = True):
    """
    Main scrubbing function.
    
    Args:
        dry_run: If True, only report what would be deleted
    """
    if not DB_PATH.exists():
        print(f"❌ Database not found: {DB_PATH}")
        return
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get all nodes
    cursor.execute("""
        SELECT id, node_type, content, confidence, created_at 
        FROM memory_nodes
    """)
    all_nodes = cursor.fetchall()
    
    print(f"📊 Analyzing {len(all_nodes)} nodes...")
    
    # Categorize nodes
    garbage_nodes = []  # (id, reason)
    duplicate_nodes = []  # (id, original_id)
    clean_nodes = []
    
    seen_hashes = {}  # hash -> first node id
    reason_counts = defaultdict(int)
    
    for node in all_nodes:
        node_id = node['id']
        node_type = node['node_type']
        content = node['content'] or ""
        
        # Check if garbage
        is_trash, reason = is_garbage(content, node_type)
        if is_trash:
            garbage_nodes.append((node_id, reason))
            reason_counts[reason] += 1
            continue
        
        # Check for duplicates
        h = content_hash(content)
        if h in seen_hashes:
            duplicate_nodes.append((node_id, seen_hashes[h]))
            reason_counts['duplicate'] += 1
            continue
        
        seen_hashes[h] = node_id
        clean_nodes.append(node_id)
    
    # Report
    print("\n" + "="*60)
    print("📋 SCRUB ANALYSIS REPORT")
    print("="*60)
    print(f"\n🗃️  Total nodes: {len(all_nodes)}")
    print(f"🗑️  Garbage nodes: {len(garbage_nodes)}")
    print(f"📑 Duplicate nodes: {len(duplicate_nodes)}")
    print(f"✅ Clean nodes: {len(clean_nodes)}")
    
    print("\n📊 Garbage breakdown:")
    for reason, count in sorted(reason_counts.items(), key=lambda x: -x[1]):
        print(f"   {reason}: {count}")
    
    # Sample garbage
    print("\n🔍 Sample garbage nodes:")
    for node_id, reason in garbage_nodes[:5]:
        cursor.execute("SELECT content FROM memory_nodes WHERE id = ?", (node_id,))
        content = cursor.fetchone()['content']
        preview = (content[:80] + "...") if len(content) > 80 else content
        print(f"   [{reason}] {preview}")
    
    if dry_run:
        print("\n⚠️  DRY RUN - No changes made")
        print("   Run with --execute to apply changes")
    else:
        # Backup first
        print("\n💾 Creating backup...")
        backup_file = backup_database(conn)
        print(f"   Backup saved to: {backup_file}")
        
        # Delete garbage
        print("\n🗑️  Deleting garbage nodes...")
        garbage_ids = [n[0] for n in garbage_nodes]
        if garbage_ids:
            placeholders = ','.join('?' * len(garbage_ids))
            cursor.execute(f"DELETE FROM memory_nodes WHERE id IN ({placeholders})", garbage_ids)
        
        # Delete duplicates
        print("📑 Deleting duplicate nodes...")
        duplicate_ids = [n[0] for n in duplicate_nodes]
        if duplicate_ids:
            placeholders = ','.join('?' * len(duplicate_ids))
            cursor.execute(f"DELETE FROM memory_nodes WHERE id IN ({placeholders})", duplicate_ids)
        
        # Also clean up orphaned edges
        print("🔗 Cleaning orphaned edges...")
        cursor.execute("""
            DELETE FROM graph_edges 
            WHERE source_id NOT IN (SELECT id FROM memory_nodes)
               OR target_id NOT IN (SELECT id FROM memory_nodes)
        """)
        orphaned_edges = cursor.rowcount
        
        conn.commit()
        
        print("\n✅ SCRUB COMPLETE")
        print(f"   Deleted: {len(garbage_ids)} garbage + {len(duplicate_ids)} duplicates")
        print(f"   Orphaned edges cleaned: {orphaned_edges}")
        print(f"   Remaining nodes: {len(clean_nodes)}")
    
    conn.close()


def main():
    args = sys.argv[1:]
    
    if "--execute" in args:
        print("🧠 MEMORY MATRIX BRAIN SCRUB")
        print("   Mode: EXECUTE (changes will be applied)\n")
        confirm = input("⚠️  This will modify the database. Continue? [y/N]: ")
        if confirm.lower() == 'y':
            scrub_brain(dry_run=False)
        else:
            print("Aborted.")
    else:
        print("🧠 MEMORY MATRIX BRAIN SCRUB")
        print("   Mode: DRY RUN (no changes)\n")
        scrub_brain(dry_run=True)


if __name__ == "__main__":
    main()
```

### 1.2 Execute the Scrub

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root

# First, dry run to see what will be deleted
.venv/bin/python scripts/matrix_scrubber.py

# Review the output, then execute
.venv/bin/python scripts/matrix_scrubber.py --execute
```

### 1.3 Verify Results

After scrubbing, verify Marzipan search returns cleaner results:

```bash
# Test search
curl -s "http://localhost:8000/slash/search?q=marzipan" | python3 -m json.tool
```

Expected: Only "owl spirit animal" and "age 2 encounter" facts remain. No `[assistant]` confabulations.

---

## Phase 2: Fix the Scribe Extraction Prompt

### 2.1 The Problem with Current Prompt

Current `EXTRACTION_SYSTEM_PROMPT` in `scribe.py` says:
```
Extract ALL meaningful information as JSON.
```

This extracts:
- ✅ User facts (good)
- ❌ User commands (bad)
- ❌ Assistant responses (bad)
- ❌ Conversational filler (bad)

### 2.2 New Extraction Prompt (The Cynical Chronicler)

Replace `EXTRACTION_SYSTEM_PROMPT` in `src/luna/actors/scribe.py`:

```python
EXTRACTION_SYSTEM_PROMPT = """
You are the Chronicler for the Luna Hub. Your job is to extract HIGH-SIGNAL information from conversation turns to be stored in the Long-Term Memory Matrix.

### DATA FILTRATION RULES:
1. **IGNORE THE ASSISTANT:** Never extract information from the assistant's own responses. If the assistant says "I think I'm glowing," that is NOT a fact. 
2. **IGNORE USER COMMANDS:** Instructions like "search for X," "delete Y," or "tell me a joke" are NOT facts. Do not store them.
3. **EXTRACT USER DISCLOSURES:** Only extract information where the USER provides new data about themselves, others, the project, or the world.
4. **RELATIONAL CONTEXT:** For every person mentioned, identify their ROLE or RELATIONSHIP to the Luna project (e.g., "Architectural Lead," "Collaborator," "External Contact").

### EXTRACTION CATEGORIES:
- [FACT]: Verifiable data (e.g., "Marzipan is an architect").
- [PREFERENCE]: User likes/dislikes (e.g., "Ahab prefers dark mode").
- [RELATION]: Connections between entities (e.g., "Tarcila designs Luna's robot body").
- [MILESTONE]: Significant project events (e.g., "Completed Memory Matrix v2").
- [DECISION]: Architectural or strategic choices made.
- [PROBLEM]: Unresolved issues requiring attention.

### OUTPUT FORMAT:
Return a JSON object with this structure:
{
  "objects": [
    {
      "type": "FACT | PREFERENCE | RELATION | MILESTONE | DECISION | PROBLEM",
      "content": "The actual information in neutral language",
      "confidence": 0.9,
      "entities": ["Names of people/projects/concepts mentioned"],
      "context": "Why this matters to Luna/The Project (optional)"
    }
  ],
  "edges": [
    {
      "from_ref": "Entity A",
      "to_ref": "Entity B", 
      "edge_type": "relationship type (collaborates_with, created_by, works_on, etc.)"
    }
  ],
  "entity_updates": [
    {
      "entity_name": "Name",
      "entity_type": "person | project | place",
      "facts": {"role": "Their role", "relationship": "How they relate to Luna project"},
      "update_type": "update | create"
    }
  ]
}

### CONFIDENCE SCORING:
- 0.9-1.0: Explicit, unambiguous statement from user
- 0.7-0.9: Strong implication with context
- 0.5-0.7: Reasonable inference (use sparingly)
- Below 0.5: Do not extract

### CRITICAL: WHEN IN DOUBT, EXTRACT NOTHING
If the conversation contains no high-signal information, return:
{"objects": [], "edges": [], "entity_updates": []}

Better to miss a fact than to pollute the Memory Matrix with garbage.

Return ONLY valid JSON. No explanation, no markdown, no commentary.
"""
```

### 2.3 Add Role Filtering in Handler

Also modify `_handle_extract_turn` in `scribe.py` to skip assistant turns entirely:

```python
async def _handle_extract_turn(self, msg: Message) -> None:
    """Handle conversation turn extraction."""
    payload = msg.payload or {}
    role = payload.get("role", "user")
    content = payload.get("content", "")
    
    # CRITICAL: Skip assistant responses entirely
    # The Scribe should only extract from user-provided information
    if role == "assistant":
        logger.debug("Ben: Skipping assistant turn (not user-provided info)")
        return
    
    # Skip very short content
    if len(content) < self.config.min_content_length:
        logger.debug(f"Ben: Skipping short content ({len(content)} chars)")
        return
    
    # ... rest of method unchanged
```

### 2.4 Location of Changes

File: `src/luna/actors/scribe.py`

1. Replace `EXTRACTION_SYSTEM_PROMPT` (around line 45-100)
2. Add role check at start of `_handle_extract_turn` (around line 208)

---

## Phase 3: Verification

### 3.1 Test the Fixed Scribe

After changes, restart server and test:

```bash
# Restart
pkill -f "python.*run.py"
source .env && .venv/bin/python scripts/run.py --server &

# Send a test message that includes both user info and a query
curl -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d '{"message": "My friend Sarah is a data scientist at Google. Can you search your memory for information about her?"}'
```

Expected behavior:
- Scribe extracts: `[FACT] Sarah is a data scientist at Google` + entity update for Sarah
- Scribe does NOT extract: the "search your memory" command
- Scribe does NOT extract: Luna's response

### 3.2 Verify Memory Search

```bash
curl -s "http://localhost:8000/slash/search?q=Sarah" | python3 -m json.tool
```

Should show the Sarah fact, not any commands or Luna responses.

---

## Success Criteria

1. ✅ Scrubber removes 1000+ garbage nodes
2. ✅ No more `[assistant]` content in memory_nodes
3. ✅ No more user commands stored as facts
4. ✅ Marzipan search returns only clean facts (owl stuff)
5. ✅ New conversations don't pollute memory with garbage
6. ✅ Entity updates capture relational context

---

## Rollback Plan

If something goes wrong:

```bash
# Restore from backup
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root

# Find latest backup
ls -la data/backups/

# Restore (replace timestamp)
sqlite3 data/luna_engine.db < data/backups/memory_nodes_backup_YYYYMMDD_HHMMSS.sql
```

---

## Notes for Implementation

- The scrubber creates a backup before any destructive operations
- Dry run first to review what will be deleted
- The new Scribe prompt is aggressive about exclusion — better to miss some facts than pollute with garbage
- Entity updates are key for relational context — make sure they're being created for people mentioned
