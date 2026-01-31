#!/usr/bin/env python3
"""
Luna Engine State Inspector

Dumps current state of the Luna Engine for debugging.
Run with: python scripts/inspect_state.py
"""

import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime

# Add src to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))


async def inspect_database():
    """Inspect database state."""
    print("\n" + "=" * 60)
    print("📦 DATABASE STATE")
    print("=" * 60)
    
    db_path = Path.home() / ".luna" / "luna.db"
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return
    
    print(f"✅ Database: {db_path}")
    print(f"   Size: {db_path.stat().st_size / 1024:.1f} KB")
    
    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # List tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"\n   Tables: {[t[0] for t in tables]}")
        
        # Count rows in key tables
        for table in ['entities', 'memory_nodes', 'conversations', 'conversation_turns']:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"   {table}: {count} rows")
            except:
                pass
        
        # Check entities
        print("\n   📋 Entities:")
        cursor.execute("SELECT id, name, entity_type FROM entities LIMIT 10")
        for row in cursor.fetchall():
            print(f"      {row[0]}: {row[1]} ({row[2]})")
        
        # Check recent conversation turns
        print("\n   💬 Recent Conversation Turns:")
        try:
            cursor.execute("""
                SELECT id, role, content, created_at 
                FROM conversation_turns 
                ORDER BY created_at DESC 
                LIMIT 5
            """)
            for row in cursor.fetchall():
                content = row[2][:50] + "..." if len(row[2]) > 50 else row[2]
                print(f"      [{row[1]}] {content}")
        except Exception as e:
            print(f"      (error: {e})")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Database error: {e}")


async def inspect_config():
    """Inspect configuration."""
    print("\n" + "=" * 60)
    print("⚙️  CONFIGURATION")
    print("=" * 60)
    
    config_paths = [
        PROJECT_ROOT / "config.yaml",
        PROJECT_ROOT / "config.json",
        PROJECT_ROOT / ".env",
        Path.home() / ".luna" / "config.yaml",
    ]
    
    for path in config_paths:
        if path.exists():
            print(f"✅ Found: {path}")
        else:
            print(f"   Missing: {path}")


async def inspect_processes():
    """Inspect running processes."""
    print("\n" + "=" * 60)
    print("🔄 RUNNING PROCESSES")
    print("=" * 60)
    
    import subprocess
    
    result = subprocess.run(
        ["ps", "aux"],
        capture_output=True,
        text=True
    )
    
    luna_processes = [
        line for line in result.stdout.split("\n")
        if "luna" in line.lower() and "grep" not in line
    ]
    
    if luna_processes:
        for proc in luna_processes[:10]:
            parts = proc.split()
            if len(parts) >= 11:
                pid = parts[1]
                cpu = parts[2]
                mem = parts[3]
                cmd = " ".join(parts[10:])[:60]
                print(f"   PID {pid}: CPU={cpu}% MEM={mem}% {cmd}")
    else:
        print("   No Luna processes running")


async def inspect_logs():
    """Inspect recent logs."""
    print("\n" + "=" * 60)
    print("📜 RECENT LOGS")
    print("=" * 60)
    
    log_file = Path("/tmp/luna_backend.log")
    
    if not log_file.exists():
        print(f"   No log file: {log_file}")
        return
    
    print(f"   Log file: {log_file}")
    print(f"   Size: {log_file.stat().st_size / 1024:.1f} KB")
    
    # Get last 20 lines
    with open(log_file, 'r') as f:
        lines = f.readlines()
        last_lines = lines[-20:] if len(lines) >= 20 else lines
    
    print("\n   Last entries:")
    for line in last_lines:
        line = line.strip()
        if line:
            # Truncate long lines
            if len(line) > 100:
                line = line[:100] + "..."
            print(f"      {line}")
    
    # Count errors
    error_count = sum(1 for line in lines if "ERROR" in line or "Error" in line)
    warn_count = sum(1 for line in lines if "WARN" in line or "Warning" in line)
    print(f"\n   Errors: {error_count}, Warnings: {warn_count}")


async def inspect_code_structure():
    """Inspect code structure for key files."""
    print("\n" + "=" * 60)
    print("📁 CODE STRUCTURE")
    print("=" * 60)
    
    key_files = [
        "src/luna/engine.py",
        "src/luna/actors/director.py",
        "src/luna/entities/context.py",
        "src/luna/entities/resolution.py",
        "src/luna/voice/server.py",
        "src/luna/memory/ring.py",
        "src/luna/context/pipeline.py",
    ]
    
    for rel_path in key_files:
        path = PROJECT_ROOT / rel_path
        if path.exists():
            size = path.stat().st_size
            lines = len(path.read_text().split("\n"))
            print(f"   ✅ {rel_path}: {lines} lines, {size/1024:.1f} KB")
        else:
            print(f"   ❌ {rel_path}: NOT FOUND")


async def main():
    print("🌙 LUNA ENGINE STATE INSPECTOR")
    print(f"   Time: {datetime.now().isoformat()}")
    print(f"   Project: {PROJECT_ROOT}")
    
    await inspect_config()
    await inspect_database()
    await inspect_processes()
    await inspect_logs()
    await inspect_code_structure()
    
    print("\n" + "=" * 60)
    print("INSPECTION COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
