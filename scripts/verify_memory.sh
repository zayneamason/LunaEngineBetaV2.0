#!/bin/bash
# =============================================================================
# LUNA MEMORY VERIFICATION SCRIPT
# =============================================================================
# Quick check that conversation history works across turns
# =============================================================================

set -e

PROJECT_ROOT="/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root"
cd "$PROJECT_ROOT"

echo "🧠 Luna Memory Verification"
echo "==========================="
echo ""

# Check if pytest is available
if ! command -v pytest &> /dev/null; then
    echo "❌ pytest not found. Install with: pip install pytest pytest-asyncio"
    exit 1
fi

# Run the conversation continuity tests
echo "Running multi-turn memory tests..."
echo ""

pytest tests/test_conversation_continuity.py -v --tb=short 2>&1 | tee /tmp/luna_memory_test.log

# Check result
if [ ${PIPESTATUS[0]} -eq 0 ]; then
    echo ""
    echo "✅ All memory tests passed!"
    echo ""
    echo "Next step: Manual verification"
    echo "1. Run: ./scripts/relaunch.sh"
    echo "2. Say: 'tell me about the owls'"
    echo "3. Say: 'what did you just tell me about owls?'"
    echo "4. Luna should reference her previous response"
else
    echo ""
    echo "❌ Memory tests FAILED"
    echo ""
    echo "Check /tmp/luna_memory_test.log for details"
    echo "DO NOT claim 'fixed' until these tests pass"
fi
