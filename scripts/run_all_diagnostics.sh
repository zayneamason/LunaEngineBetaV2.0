#!/bin/bash
set -e
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "========================================"
echo "  LUNA FULL SYSTEM DIAGNOSTIC"
echo "  $(date)"
echo "========================================"

# Activate virtual environment
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
    echo "✅ Virtual environment activated"
else
    echo "⚠️ No .venv found, using system Python"
fi

# Export environment variables
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
    echo "✅ Environment variables loaded from .env"
else
    echo "⚠️ No .env file found"
fi

echo -e "\n>>> Phase 1: System Snapshot"
echo "-------------------------------------------"
python scripts/diagnostic_snapshot.py || echo "⚠️ Snapshot failed"

echo -e "\n>>> Phase 2: WebSocket Test"
echo "-------------------------------------------"
python scripts/test_websocket.py || echo "⚠️ WebSocket test failed"

echo -e "\n>>> Phase 3: LLM Providers"
echo "-------------------------------------------"
python scripts/test_llm_providers.py || echo "⚠️ LLM test failed"

echo -e "\n>>> Phase 4: Chat Flow"
echo "-------------------------------------------"
python scripts/test_chat_flow.py || echo "⚠️ Chat flow test failed"

echo -e "\n>>> Phase 5: Unit Tests"
echo "-------------------------------------------"
pytest tests/test_critical_systems.py -v --tb=short 2>&1 || echo "⚠️ Some tests failed"

echo -e "\n========================================"
echo "  DIAGNOSTIC COMPLETE"
echo "  $(date)"
echo "========================================"
