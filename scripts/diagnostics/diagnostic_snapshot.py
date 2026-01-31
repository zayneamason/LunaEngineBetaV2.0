#!/usr/bin/env python3
"""Capture complete system state for debugging."""
import asyncio
import json
import os
import sys
import sqlite3
import subprocess
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent

def section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def check_env_vars():
    section("ENVIRONMENT VARIABLES")
    critical_vars = ["ANTHROPIC_API_KEY", "GROQ_API_KEY", "GOOGLE_API_KEY"]
    for var in critical_vars:
        val = os.environ.get(var)
        if val:
            print(f"  ✅ {var}: {val[:15]}...{val[-5:]}")
        else:
            print(f"  ❌ {var}: NOT SET")

def check_python_imports():
    section("PYTHON IMPORTS")
    modules = [
        ("mlx", "MLX base"),
        ("mlx_lm", "MLX Language Models"),
        ("google.generativeai", "Gemini SDK"),
        ("groq", "Groq SDK"),
        ("anthropic", "Anthropic SDK"),
        ("websockets", "WebSocket support"),
        ("aiosqlite", "Async SQLite"),
        ("fastapi", "FastAPI"),
        ("httpx", "HTTP client"),
        ("dotenv", "Dotenv"),
    ]
    for mod, desc in modules:
        try:
            __import__(mod)
            print(f"  ✅ {mod}: {desc}")
        except ImportError as e:
            print(f"  ❌ {mod}: {desc} - {e}")

def check_files():
    section("CRITICAL FILES")
    files = [
        ("data/luna_engine.db", "Memory database"),
        ("models/luna_lora_mlx/adapters.safetensors", "LoRA adapter"),
        ("config/llm_providers.json", "LLM provider config"),
        (".env", "Environment file"),
        ("src/luna/engine.py", "Main engine"),
        ("src/luna/api/server.py", "API server"),
        ("frontend/src/hooks/useOrbState.js", "Orb state hook"),
    ]
    for path, desc in files:
        full = PROJECT_ROOT / path
        if full.exists():
            size = full.stat().st_size
            print(f"  ✅ {path}: {desc} ({size:,} bytes)")
        else:
            print(f"  ❌ {path}: {desc} - MISSING")

def check_database():
    section("DATABASE INTEGRITY")
    db_path = PROJECT_ROOT / "data" / "luna_engine.db"
    if not db_path.exists():
        print("  ❌ Database not found")
        return
    conn = sqlite3.connect(db_path)
    tables = [("memory_nodes", 10000), ("graph_edges", 10000), ("clusters", 1)]
    for table, min_expected in tables:
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            status = "✅" if count >= min_expected else "⚠️"
            print(f"  {status} {table}: {count:,} rows (min: {min_expected})")
        except Exception as e:
            print(f"  ❌ {table}: Error - {e}")
    conn.close()

def check_server():
    section("SERVER STATUS")
    import urllib.request
    endpoints = [
        ("http://localhost:8000/health", "Health"),
        ("http://localhost:8000/llm/providers", "LLM Providers"),
    ]
    for url, name in endpoints:
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                data = json.loads(resp.read())
                print(f"  ✅ {name}: OK - {data}")
        except Exception as e:
            print(f"  ❌ {name}: {e}")

def check_websocket():
    section("WEBSOCKET TEST")
    try:
        import websockets
        async def test_ws():
            try:
                async with websockets.connect("ws://localhost:8000/ws/orb", close_timeout=2) as ws:
                    msg = await asyncio.wait_for(ws.recv(), timeout=3)
                    print(f"  ✅ WebSocket connected, received: {msg[:100] if len(msg) > 100 else msg}")
                    return True
            except Exception as e:
                print(f"  ❌ WebSocket error: {e}")
                return False
        asyncio.run(test_ws())
    except ImportError:
        print("  ❌ websockets module not installed")

def check_processes():
    section("RUNNING PROCESSES")
    try:
        result = subprocess.run(["pgrep", "-fl", "python.*luna"], capture_output=True, text=True)
        if result.stdout.strip():
            print(f"  Luna processes:\n{result.stdout}")
        else:
            print("  ⚠️ No Luna Python processes found")

        result = subprocess.run(["lsof", "-i", ":8000"], capture_output=True, text=True)
        if result.stdout.strip():
            lines = result.stdout.strip().split('\n')
            print(f"  Port 8000 listeners: {len(lines)-1 if len(lines) > 1 else 0}")
        else:
            print("  ⚠️ Nothing listening on port 8000")
    except Exception as e:
        print(f"  Error checking processes: {e}")

def main():
    print("\n" + "="*60)
    print("  LUNA SYSTEM DIAGNOSTIC SNAPSHOT")
    print(f"  {datetime.now().isoformat()}")
    print("="*60)
    check_env_vars()
    check_python_imports()
    check_files()
    check_database()
    check_processes()
    check_server()
    check_websocket()
    section("DIAGNOSTIC COMPLETE")

if __name__ == "__main__":
    os.chdir(PROJECT_ROOT)
    main()
