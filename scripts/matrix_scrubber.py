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
            return True, "assistant_pattern"

    # 3. User commands/queries (not facts)
    if "[user]" in text:
        for pattern in USER_COMMAND_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True, "user_command"

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
        row = cursor.fetchone()
        if row:
            content = row['content']
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
            WHERE from_id NOT IN (SELECT id FROM memory_nodes)
               OR to_id NOT IN (SELECT id FROM memory_nodes)
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
