#!/bin/bash
# Luna Engine Startup Script
# ALWAYS use .venv Python. ALWAYS clear bytecode cache.
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root

# Kill any existing engine
lsof -i :8000 -t 2>/dev/null | xargs kill 2>/dev/null
sleep 2

# Clear stale bytecode — this was the deployment blocker for weeks
find src/ -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
find src/ -name "*.pyc" -delete 2>/dev/null

echo "[start_engine] Cache cleared, starting with .venv Python..."
exec .venv/bin/python scripts/run.py --server --host 0.0.0.0 --port 8000
