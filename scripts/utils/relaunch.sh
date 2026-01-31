#!/bin/bash
# =============================================================================
# LUNA ENGINE RELAUNCH SCRIPT
# =============================================================================
# One-click restart of backend + frontend
# Usage: ./scripts/relaunch.sh
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🔄 Luna Engine Relaunch"
echo "======================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Kill existing processes
echo -e "${YELLOW}Stopping existing processes...${NC}"

# Kill backend (voice server, hub, any python luna processes)
pkill -f "python.*luna" 2>/dev/null || true
pkill -f "uvicorn.*luna" 2>/dev/null || true

# Kill frontend (vite, node dev servers)
pkill -f "vite" 2>/dev/null || true
pkill -f "node.*luna" 2>/dev/null || true

# Wait for processes to die
sleep 2

echo -e "${GREEN}✓ Processes stopped${NC}"

# Start backend
echo -e "${YELLOW}Starting backend...${NC}"
cd "$PROJECT_ROOT"

# Check if virtual environment exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
fi

# Start the Luna Engine API server
LOG_LEVEL=DEBUG python scripts/run.py --server > /tmp/luna_backend.log 2>&1 &
BACKEND_PID=$!
echo -e "${GREEN}✓ Backend started (PID: $BACKEND_PID)${NC}"

# Start frontend (if exists)
if [ -d "$PROJECT_ROOT/frontend" ]; then
    echo -e "${YELLOW}Starting frontend...${NC}"
    cd "$PROJECT_ROOT/frontend"
    npm run dev > /tmp/luna_frontend.log 2>&1 &
    FRONTEND_PID=$!
    echo -e "${GREEN}✓ Frontend started (PID: $FRONTEND_PID)${NC}"
elif [ -d "$PROJECT_ROOT/hub" ]; then
    echo -e "${YELLOW}Starting hub...${NC}"
    cd "$PROJECT_ROOT/hub"
    npm run dev > /tmp/luna_frontend.log 2>&1 &
    FRONTEND_PID=$!
    echo -e "${GREEN}✓ Hub started (PID: $FRONTEND_PID)${NC}"
fi

echo ""
echo "======================="
echo -e "${GREEN}🚀 Luna Engine Relaunched${NC}"
echo ""
echo "Backend log:  tail -f /tmp/luna_backend.log"
echo "Frontend log: tail -f /tmp/luna_frontend.log"
echo ""
echo "To stop: ./scripts/stop.sh"
