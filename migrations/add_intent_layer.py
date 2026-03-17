#!/usr/bin/env python3
"""
Intent Layer Migration — Expand quest table for directives and skills.

Rebuilds the quests table to add:
- New types: 'directive', 'skill'
- New statuses: 'armed', 'fired', 'disabled'
- Directive columns: trigger_type, trigger_config, action, trust_tier, etc.
- Skill columns: steps, invocation_count, last_invoked_at, tags_json

Run:
    python migrations/add_intent_layer.py [--db PATH] [--force]
"""

import sqlite3
import shutil
import sys
from datetime import datetime
from pathlib import Path


DEFAULT_DB = Path(__file__).parent.parent / "data" / "luna_engine.db"


def migrate(db_path: Path, force: bool = False) -> bool:
    """Rebuild quests table with expanded constraints and new columns."""

    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return False

    # 0. Backup
    backup_dir = db_path.parent / "backups"
    backup_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"luna_engine.db.pre-intent-layer-{stamp}"
    shutil.copy2(db_path, backup_path)
    print(f"Backup: {backup_path}")

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = OFF")
    cursor = conn.cursor()

    # Check if migration already applied (look for trigger_type column)
    cursor.execute("PRAGMA table_info(quests)")
    columns = [row[1] for row in cursor.fetchall()]
    if "trigger_type" in columns:
        if not force:
            print("Migration already applied (trigger_type column exists). Use --force to re-run.")
            conn.close()
            return True
        print("Force mode: re-running migration.")

    # Count before
    cursor.execute("SELECT COUNT(*) FROM quests")
    count_before = cursor.fetchone()[0]
    print(f"Quests before: {count_before}")

    # 1. Create new table with expanded constraints + new columns
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quests_new (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL CHECK(type IN (
                'main', 'side', 'contract', 'treasure_hunt', 'scavenger',
                'directive', 'skill'
            )),
            status TEXT NOT NULL DEFAULT 'available' CHECK(status IN (
                'available', 'active', 'complete', 'failed', 'expired',
                'armed', 'fired', 'disabled'
            )),
            priority TEXT DEFAULT 'medium' CHECK(priority IN ('low', 'medium', 'high', 'urgent')),
            title TEXT NOT NULL,
            subtitle TEXT,
            objective TEXT NOT NULL,
            source TEXT,
            journal_prompt TEXT,
            target_lock_in REAL,
            reward_base REAL DEFAULT 0.15,
            investigation TEXT DEFAULT '{}',
            expires_at TEXT,
            completed_at TEXT,
            failed_at TEXT,
            fail_note TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            -- Intent layer: directive columns
            trigger_type TEXT,
            trigger_config TEXT,
            action TEXT,
            trust_tier TEXT DEFAULT 'confirm',
            authored_by TEXT DEFAULT 'system',
            approved_by TEXT,
            fire_count INTEGER DEFAULT 0,
            last_fired_at TEXT,
            cooldown_minutes INTEGER,
            -- Intent layer: skill columns
            steps TEXT,
            invocation_count INTEGER DEFAULT 0,
            last_invoked_at TEXT,
            tags_json TEXT DEFAULT '[]'
        )
    """)

    # 2. Copy existing data (new columns get defaults)
    cursor.execute("""
        INSERT OR IGNORE INTO quests_new (
            id, type, status, priority, title, subtitle, objective,
            source, journal_prompt, target_lock_in, reward_base,
            investigation, expires_at, completed_at, failed_at,
            fail_note, created_at, updated_at
        )
        SELECT
            id, type, status, priority, title, subtitle, objective,
            source, journal_prompt, target_lock_in, reward_base,
            investigation, expires_at, completed_at, failed_at,
            fail_note, created_at, updated_at
        FROM quests
    """)

    # 3. Swap tables
    cursor.execute("DROP TABLE quests")
    cursor.execute("ALTER TABLE quests_new RENAME TO quests")

    # 4. Recreate indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_quests_status ON quests(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_quests_type ON quests(type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_quests_type_status ON quests(type, status)")

    conn.commit()

    # 5. Verify
    cursor.execute("SELECT COUNT(*) FROM quests")
    count_after = cursor.fetchone()[0]
    print(f"Quests after:  {count_after}")

    if count_before != count_after:
        print(f"ROW COUNT MISMATCH: {count_before} -> {count_after}")
        conn.close()
        return False

    # Verify new types work
    cursor.execute("""
        INSERT INTO quests (id, type, status, title, objective, created_at, updated_at)
        VALUES ('_test_directive', 'directive', 'armed', 'test', 'test', datetime('now'), datetime('now'))
    """)
    cursor.execute("DELETE FROM quests WHERE id = '_test_directive'")
    conn.commit()
    print("Directive INSERT: OK")

    cursor.execute("""
        INSERT INTO quests (id, type, status, title, objective, created_at, updated_at)
        VALUES ('_test_skill', 'skill', 'available', 'test', 'test', datetime('now'), datetime('now'))
    """)
    cursor.execute("DELETE FROM quests WHERE id = '_test_skill'")
    conn.commit()
    print("Skill INSERT: OK")

    # Verify quest_targets still reference correctly
    cursor.execute("SELECT COUNT(*) FROM quest_targets")
    targets = cursor.fetchone()[0]
    print(f"Quest targets intact: {targets}")

    cursor.execute("SELECT COUNT(*) FROM quest_journal")
    journals = cursor.fetchone()[0]
    print(f"Quest journal intact: {journals}")

    conn.close()
    print("Migration complete.")
    return True


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Intent Layer migration")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="Database path")
    parser.add_argument("--force", action="store_true", help="Re-run even if already applied")
    args = parser.parse_args()
    success = migrate(args.db, force=args.force)
    sys.exit(0 if success else 1)
