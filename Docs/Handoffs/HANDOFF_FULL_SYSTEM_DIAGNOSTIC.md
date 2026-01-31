# HANDOFF: Full System Diagnostic Swarm

**Created:** 2025-01-28
**Priority:** 🚨 CRITICAL — Luna Hub broken, need complete visibility
**Status:** Ready for Claude Code + Claude Flow Swarm
**Location:** `/Docs/Handoffs/HANDOFF_FULL_SYSTEM_DIAGNOSTIC.md`

---

## SITUATION SUMMARY

Luna's been through emergency surgery today. Multiple fixes applied:
- ✅ MLX loading
- ✅ LoRA reconnected
- ✅ Scribe garbage fix
- ✅ WebSockets installed
- ✅ Gemini SDK installed
- ✅ Env vars export fix

**But Luna Hub is STILL broken.** WebSocket flapping:
```
[OrbState] Connected
[OrbState] Disconnected, reconnecting...
[OrbState] Error: Event
```

We need FULL VISIBILITY. Not patches. Understanding.

---

## CLAUDE FLOW SWARM SPECIFICATION

```yaml
# File: .swarm/full-system-diagnostic.yaml

name: full-system-diagnostic
description: |
  Comprehensive diagnostic swarm to identify all failure points in Luna Engine.
  Creates test scripts, runs diagnostics, captures results, and traces root causes.

coordinator:
  strategy: sequential-with-gates
  failure_mode: continue-and-report
  output_dir: Docs/Handoffs/DiagnosticResults
  
  gates:
    - name: scripts-created
      requires: [script-creator]
      condition: all-scripts-exist
      
    - name: diagnostics-run
      requires: [diagnostic-runner]
      condition: results-captured
      
    - name: analysis-complete
      requires: [failure-analyst]
      condition: root-causes-identified

agents:
  # ============================================
  # AGENT 1: Script Creator
  # ============================================
  - name: script-creator
    role: Create all diagnostic and test scripts
    
    tasks:
      - id: create-diagnostic-snapshot
        description: Create scripts/diagnostic_snapshot.py
        file: scripts/diagnostic_snapshot.py
        content: |
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
              tables = [("memory_nodes", 10000), ("graph_edges", 10000)]
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
                          print(f"  ✅ {name}: OK")
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
                              print(f"  ✅ WebSocket connected, received data")
                              return True
                      except Exception as e:
                          print(f"  ❌ WebSocket error: {e}")
                          return False
                  asyncio.run(test_ws())
              except ImportError:
                  print("  ❌ websockets module not installed")

          def main():
              print("\n" + "="*60)
              print("  LUNA SYSTEM DIAGNOSTIC SNAPSHOT")
              print(f"  {datetime.now().isoformat()}")
              print("="*60)
              check_env_vars()
              check_python_imports()
              check_files()
              check_database()
              check_server()
              check_websocket()
              section("DIAGNOSTIC COMPLETE")

          if __name__ == "__main__":
              os.chdir(PROJECT_ROOT)
              main()

      - id: create-websocket-test
        description: Create scripts/test_websocket.py
        file: scripts/test_websocket.py
        content: |
          #!/usr/bin/env python3
          """Stress test WebSocket connection."""
          import asyncio
          import json
          import time
          import websockets

          async def test_connection_stability():
              print("Testing WebSocket stability (10 seconds)...")
              uri = "ws://localhost:8000/ws/orb"
              try:
                  async with websockets.connect(uri) as ws:
                      print(f"✅ Connected")
                      messages = 0
                      start = time.time()
                      while time.time() - start < 10:
                          try:
                              msg = await asyncio.wait_for(ws.recv(), timeout=2)
                              messages += 1
                              if messages <= 3:
                                  print(f"  [{messages}] Received message")
                          except asyncio.TimeoutError:
                              print(f"  ⚠️ No message for 2s")
                          except websockets.exceptions.ConnectionClosed as e:
                              print(f"  ❌ Connection closed: {e}")
                              return False
                      print(f"✅ Stable: {messages} messages in 10s")
                      return True
              except Exception as e:
                  print(f"❌ Failed: {e}")
                  return False

          async def test_rapid_reconnect():
              print("\nTesting rapid reconnect (5 cycles)...")
              uri = "ws://localhost:8000/ws/orb"
              success = 0
              for i in range(5):
                  try:
                      async with websockets.connect(uri) as ws:
                          await asyncio.wait_for(ws.recv(), timeout=2)
                          success += 1
                  except Exception as e:
                      print(f"  [{i+1}] Failed: {e}")
                  await asyncio.sleep(0.3)
              print(f"{'✅' if success == 5 else '❌'} {success}/5 successful")

          async def main():
              print("="*50)
              print("  WEBSOCKET DIAGNOSTIC")
              print("="*50)
              await test_connection_stability()
              await test_rapid_reconnect()

          if __name__ == "__main__":
              asyncio.run(main())

      - id: create-llm-test
        description: Create scripts/test_llm_providers.py
        file: scripts/test_llm_providers.py
        content: |
          #!/usr/bin/env python3
          """Test each LLM provider end-to-end."""
          import asyncio
          import os
          import sys
          from pathlib import Path
          sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

          async def test_provider(name: str, provider_class):
              print(f"\n--- Testing {name} ---")
              try:
                  provider = provider_class()
                  print(f"  Available: {provider.is_available}")
                  if not provider.is_available:
                      return False
                  from luna.llm import Message
                  result = await provider.complete(
                      [Message("user", "Say 'hello' only.")],
                      max_tokens=10
                  )
                  print(f"  Response: {result.text[:50]}")
                  print(f"  ✅ {name} working")
                  return True
              except Exception as e:
                  print(f"  ❌ Error: {e}")
                  return False

          async def main():
              from dotenv import load_dotenv
              load_dotenv(Path(__file__).parent.parent / ".env")
              
              print("="*50)
              print("  LLM PROVIDER TESTS")
              print("="*50)
              
              from luna.llm.providers.gemini_provider import GeminiProvider
              from luna.llm.providers.groq_provider import GroqProvider
              from luna.llm.providers.claude_provider import ClaudeProvider
              
              results = {
                  "gemini": await test_provider("Gemini", GeminiProvider),
                  "groq": await test_provider("Groq", GroqProvider),
                  "claude": await test_provider("Claude", ClaudeProvider),
              }
              
              print("\n" + "="*50)
              for name, ok in results.items():
                  print(f"  {'✅' if ok else '❌'} {name}")

          if __name__ == "__main__":
              asyncio.run(main())

      - id: create-chat-flow-test
        description: Create scripts/test_chat_flow.py
        file: scripts/test_chat_flow.py
        content: |
          #!/usr/bin/env python3
          """Test complete chat flow."""
          import asyncio
          import json
          import time
          import httpx

          BASE = "http://localhost:8000"

          async def test_persona_stream():
              print("\n--- Testing /persona/stream ---")
              async with httpx.AsyncClient(timeout=30) as client:
                  try:
                      start = time.time()
                      resp = await client.post(
                          f"{BASE}/persona/stream",
                          json={"message": "hey luna test"},
                      )
                      elapsed = time.time() - start
                      print(f"  Status: {resp.status_code}")
                      print(f"  Time: {elapsed:.2f}s")
                      
                      events = []
                      for line in resp.text.split("\n"):
                          if line.startswith("data: "):
                              try:
                                  events.append(json.loads(line[6:]))
                              except:
                                  pass
                      
                      types = [e.get("type") for e in events]
                      print(f"  Events: {len(events)}")
                      print(f"  Types: {set(types)}")
                      
                      has_tokens = "token" in types
                      print(f"  {'✅' if has_tokens else '❌'} Has token events")
                      return has_tokens
                  except Exception as e:
                      print(f"  ❌ Error: {e}")
                      return False

          async def main():
              print("="*50)
              print("  CHAT FLOW TEST")
              print("="*50)
              await test_persona_stream()

          if __name__ == "__main__":
              asyncio.run(main())

      - id: create-unit-tests
        description: Create tests/test_critical_systems.py
        file: tests/test_critical_systems.py
        content: |
          """Critical systems unit tests."""
          import pytest
          import os
          from pathlib import Path
          from dotenv import load_dotenv
          load_dotenv(Path(__file__).parent.parent / ".env")

          class TestEnvironment:
              def test_anthropic_key(self):
                  assert os.environ.get("ANTHROPIC_API_KEY")
              def test_groq_key(self):
                  assert os.environ.get("GROQ_API_KEY")
              def test_google_key(self):
                  assert os.environ.get("GOOGLE_API_KEY")

          class TestImports:
              def test_mlx(self):
                  import mlx
                  import mlx_lm
              def test_gemini(self):
                  import google.generativeai
              def test_websockets(self):
                  import websockets

          class TestDatabase:
              def test_exists(self):
                  db = Path(__file__).parent.parent / "data" / "luna_engine.db"
                  assert db.exists()
              def test_nodes(self):
                  import sqlite3
                  db = Path(__file__).parent.parent / "data" / "luna_engine.db"
                  conn = sqlite3.connect(db)
                  count = conn.execute("SELECT COUNT(*) FROM memory_nodes").fetchone()[0]
                  conn.close()
                  assert count >= 10000

          class TestLLMProviders:
              def test_gemini(self):
                  from luna.llm.providers.gemini_provider import GeminiProvider
                  assert GeminiProvider().is_available
              def test_groq(self):
                  from luna.llm.providers.groq_provider import GroqProvider
                  assert GroqProvider().is_available

      - id: create-runner
        description: Create scripts/run_all_diagnostics.sh
        file: scripts/run_all_diagnostics.sh
        content: |
          #!/bin/bash
          set -e
          PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
          cd "$PROJECT_ROOT"
          
          echo "========================================"
          echo "  LUNA FULL SYSTEM DIAGNOSTIC"
          echo "  $(date)"
          echo "========================================"
          
          source .venv/bin/activate
          export $(grep -v '^#' .env | xargs)
          
          echo -e "\n>>> Phase 1: System Snapshot"
          python scripts/diagnostic_snapshot.py
          
          echo -e "\n>>> Phase 2: WebSocket Test"
          python scripts/test_websocket.py
          
          echo -e "\n>>> Phase 3: LLM Providers"
          python scripts/test_llm_providers.py
          
          echo -e "\n>>> Phase 4: Chat Flow"
          python scripts/test_chat_flow.py
          
          echo -e "\n>>> Phase 5: Unit Tests"
          pytest tests/test_critical_systems.py -v --tb=short || true
          
          echo -e "\n========================================"
          echo "  COMPLETE"
          echo "========================================"

    outputs:
      - scripts/diagnostic_snapshot.py
      - scripts/test_websocket.py
      - scripts/test_llm_providers.py
      - scripts/test_chat_flow.py
      - tests/test_critical_systems.py
      - scripts/run_all_diagnostics.sh

  # ============================================
  # AGENT 2: Diagnostic Runner
  # ============================================
  - name: diagnostic-runner
    role: Execute all diagnostic scripts and capture results
    depends_on: [script-creator]
    
    tasks:
      - id: make-executable
        command: |
          chmod +x scripts/run_all_diagnostics.sh
          chmod +x scripts/*.py
      
      - id: run-diagnostics
        command: |
          cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
          ./scripts/run_all_diagnostics.sh 2>&1 | tee Docs/Handoffs/DiagnosticResults/DIAGNOSTIC_OUTPUT.txt
      
      - id: capture-server-logs
        command: |
          tail -200 /tmp/luna_server.log > Docs/Handoffs/DiagnosticResults/SERVER_LOGS.txt 2>/dev/null || echo "No server log"
      
      - id: capture-frontend-state
        description: Document what useOrbState.js is doing
        file: Docs/Handoffs/DiagnosticResults/FRONTEND_AUDIT.md
        actions:
          - read: frontend/src/hooks/useOrbState.js
          - analyze: WebSocket connection logic
          - document: Any issues found

    outputs:
      - Docs/Handoffs/DiagnosticResults/DIAGNOSTIC_OUTPUT.txt
      - Docs/Handoffs/DiagnosticResults/SERVER_LOGS.txt
      - Docs/Handoffs/DiagnosticResults/FRONTEND_AUDIT.md

  # ============================================
  # AGENT 3: Failure Analyst
  # ============================================
  - name: failure-analyst
    role: Analyze diagnostic results and identify root causes
    depends_on: [diagnostic-runner]
    
    tasks:
      - id: analyze-failures
        description: Parse diagnostic output and categorize failures
        inputs:
          - Docs/Handoffs/DiagnosticResults/DIAGNOSTIC_OUTPUT.txt
          - Docs/Handoffs/DiagnosticResults/SERVER_LOGS.txt
        output: Docs/Handoffs/DiagnosticResults/FAILURE_ANALYSIS.md
        template: |
          # Failure Analysis Report
          
          ## Summary
          - Total tests run: {total}
          - Passed: {passed}
          - Failed: {failed}
          
          ## Failures
          
          {for each failure}
          ### {failure.name}
          - **Location:** {failure.file}:{failure.line}
          - **Error:** {failure.message}
          - **Root Cause:** {analysis}
          - **Fix:** {suggested_fix}
          {end for}
          
          ## Dependency Chain
          {trace which failures cause other failures}
          
          ## Priority Order
          1. {highest priority fix}
          2. ...
      
      - id: trace-websocket-issue
        description: Deep dive on WebSocket flapping
        inputs:
          - frontend/src/hooks/useOrbState.js
          - src/luna/api/server.py (ws/orb endpoint)
          - Docs/Handoffs/DiagnosticResults/SERVER_LOGS.txt
        output: Docs/Handoffs/DiagnosticResults/WEBSOCKET_TRACE.md
        
      - id: create-fix-plan
        description: Ordered list of fixes with dependencies
        output: Docs/Handoffs/DiagnosticResults/FIX_PLAN.md

    outputs:
      - Docs/Handoffs/DiagnosticResults/FAILURE_ANALYSIS.md
      - Docs/Handoffs/DiagnosticResults/WEBSOCKET_TRACE.md
      - Docs/Handoffs/DiagnosticResults/FIX_PLAN.md

  # ============================================
  # AGENT 4: Fix Implementer
  # ============================================
  - name: fix-implementer
    role: Apply fixes based on analysis
    depends_on: [failure-analyst]
    
    tasks:
      - id: read-fix-plan
        input: Docs/Handoffs/DiagnosticResults/FIX_PLAN.md
        
      - id: apply-fixes
        description: Apply each fix in priority order
        for_each: fix in FIX_PLAN
        actions:
          - apply: fix.changes
          - test: fix.verification
          - log: Docs/Handoffs/DiagnosticResults/FIX_LOG.md
      
      - id: restart-server
        command: |
          pkill -f "scripts/run.py" || true
          sleep 2
          cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
          export $(grep -v '^#' .env | xargs)
          .venv/bin/python scripts/run.py --server > /tmp/luna_server.log 2>&1 &
          sleep 8
          curl -s http://localhost:8000/health

    outputs:
      - Docs/Handoffs/DiagnosticResults/FIX_LOG.md

  # ============================================
  # AGENT 5: Verification Agent
  # ============================================
  - name: verifier
    role: Verify all fixes and confirm Luna is working
    depends_on: [fix-implementer]
    
    tasks:
      - id: rerun-diagnostics
        command: ./scripts/run_all_diagnostics.sh 2>&1 | tee Docs/Handoffs/DiagnosticResults/POST_FIX_DIAGNOSTIC.txt
      
      - id: test-luna-hub
        description: Manual verification checklist
        output: Docs/Handoffs/DiagnosticResults/VERIFICATION_CHECKLIST.md
        template: |
          # Verification Checklist
          
          ## Backend
          - [ ] Server starts without errors
          - [ ] /health returns healthy
          - [ ] /llm/providers shows all available
          - [ ] /persona/stream returns tokens
          
          ## WebSocket
          - [ ] /ws/orb accepts connections
          - [ ] Connection stays stable for 30+ seconds
          - [ ] Orb state broadcasts correctly
          
          ## Luna Hub UI
          - [ ] Page loads without console errors
          - [ ] Orb connects (green indicator)
          - [ ] Chat messages get responses
          - [ ] Responses stream token by token
          
          ## LLM Providers
          - [ ] Gemini responds
          - [ ] Groq responds
          - [ ] Claude responds
          - [ ] Provider switch works
      
      - id: create-final-report
        output: Docs/Handoffs/DiagnosticResults/FINAL_REPORT.md

    outputs:
      - Docs/Handoffs/DiagnosticResults/POST_FIX_DIAGNOSTIC.txt
      - Docs/Handoffs/DiagnosticResults/VERIFICATION_CHECKLIST.md
      - Docs/Handoffs/DiagnosticResults/FINAL_REPORT.md

# ============================================
# SUCCESS CRITERIA
# ============================================
success_criteria:
  required:
    - All diagnostic scripts created and executable
    - Diagnostic output captured
    - Failure analysis complete with root causes
    - Fix plan created with priorities
    - Fixes applied and logged
    - Post-fix diagnostics pass
    - Luna Hub functional
    
  verification:
    - WebSocket stable for 30 seconds
    - /persona/stream returns token events
    - All 3 LLM providers available
    - Unit tests pass
```

---

## QUICK START

```bash
# For Claude Code:
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root

# Run swarm
claude-flow run .swarm/full-system-diagnostic.yaml

# Or manually:
# 1. Create scripts (agent 1)
# 2. Run diagnostics (agent 2)
# 3. Analyze failures (agent 3)
# 4. Apply fixes (agent 4)
# 5. Verify (agent 5)
```

---

## OUTPUT STRUCTURE

```
Docs/Handoffs/DiagnosticResults/
├── DIAGNOSTIC_OUTPUT.txt      # Raw diagnostic output
├── SERVER_LOGS.txt            # Server log tail
├── FRONTEND_AUDIT.md          # useOrbState.js analysis
├── FAILURE_ANALYSIS.md        # Root cause analysis
├── WEBSOCKET_TRACE.md         # WebSocket deep dive
├── FIX_PLAN.md                # Ordered fix list
├── FIX_LOG.md                 # Applied fixes
├── POST_FIX_DIAGNOSTIC.txt    # Verification run
├── VERIFICATION_CHECKLIST.md  # Manual checks
└── FINAL_REPORT.md            # Summary
```

---

## THE GOAL

**Paint a complete picture of failure:**
1. What's broken
2. Why it's broken
3. What depends on what
4. Fix order
5. Verification that it's actually fixed

No more whack-a-mole. Systematic diagnosis. 🎯
