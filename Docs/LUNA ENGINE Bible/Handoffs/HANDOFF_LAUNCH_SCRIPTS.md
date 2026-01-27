# HANDOFF: Fix Luna Engine Launch Scripts

## Problem Statement

The launch scripts are broken and inconsistent:

1. `relaunch.sh` was trying to start `luna.voice.server` which doesn't exist
2. The actual server entry point is `scripts/run.py --server`
3. Frontend starts but backend fails silently
4. No health check to confirm backend is actually running
5. Voice server is a separate concern from the main API server

## Current State

### What Works
- `python scripts/run.py --server` — starts the API server correctly on port 8000
- Frontend (`npm run dev` in `/frontend`) — works fine on port 5173

### What's Broken
- `./scripts/relaunch.sh` — was calling non-existent `luna.voice.server`
- `./scripts/launch_app.sh` — calls relaunch.sh, inherits the problem
- No startup validation — scripts report success even when backend fails

## Files to Fix

| File | Issue |
|------|-------|
| `scripts/relaunch.sh` | Wrong backend start command (partially fixed) |
| `scripts/launch_app.sh` | Needs health check before declaring success |
| `scripts/stop.sh` | Review for consistency |

---

## Required Changes

### 1. Fix `scripts/relaunch.sh`

**Current (broken):**
```bash
# Start the voice server (or whatever the main backend is)
LOG_LEVEL=DEBUG python -m luna.voice.server > /tmp/luna_backend.log 2>&1 &
```

**Fixed:**
```bash
#!/bin/bash
# =============================================================================
# LUNA ENGINE RELAUNCH SCRIPT
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
NC='\033[0m'

# Kill existing processes
echo -e "${YELLOW}Stopping existing processes...${NC}"

# Kill backend
pkill -f "python.*run.py.*server" 2>/dev/null || true
pkill -f "uvicorn.*luna" 2>/dev/null || true
lsof -ti:8000 | xargs kill -9 2>/dev/null || true

# Kill frontend
pkill -f "vite" 2>/dev/null || true

sleep 2
echo -e "${GREEN}✓ Processes stopped${NC}"

# Activate virtual environment
cd "$PROJECT_ROOT"
if [ -d ".venv" ]; then
    source .venv/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
else
    echo -e "${RED}No virtual environment found!${NC}"
    exit 1
fi

# Start backend
echo -e "${YELLOW}Starting backend...${NC}"
LOG_LEVEL=INFO python scripts/run.py --server > /tmp/luna_backend.log 2>&1 &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

# Wait for backend to be healthy
echo -e "${YELLOW}Waiting for backend health check...${NC}"
MAX_RETRIES=30
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s http://localhost:8000/health | grep -q "healthy"; then
        echo -e "${GREEN}✓ Backend is healthy${NC}"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    sleep 1
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo -e "${RED}✗ Backend failed to start!${NC}"
    echo "Check logs: tail -f /tmp/luna_backend.log"
    cat /tmp/luna_backend.log
    exit 1
fi

# Start frontend (if exists)
if [ -d "$PROJECT_ROOT/frontend" ]; then
    echo -e "${YELLOW}Starting frontend...${NC}"
    cd "$PROJECT_ROOT/frontend"
    npm run dev > /tmp/luna_frontend.log 2>&1 &
    FRONTEND_PID=$!
    echo -e "${GREEN}✓ Frontend started (PID: $FRONTEND_PID)${NC}"
fi

echo ""
echo "======================="
echo -e "${GREEN}🚀 Luna Engine Running${NC}"
echo ""
echo "  API:      http://localhost:8000"
echo "  Frontend: http://localhost:5173"
echo ""
echo "  Backend log:  tail -f /tmp/luna_backend.log"
echo "  Frontend log: tail -f /tmp/luna_frontend.log"
echo ""
echo "  Stop: ./scripts/stop.sh"
```

### 2. Fix `scripts/stop.sh`

```bash
#!/bin/bash
# =============================================================================
# LUNA ENGINE STOP SCRIPT
# =============================================================================

echo "🛑 Stopping Luna Engine..."

# Kill by process pattern
pkill -f "python.*run.py.*server" 2>/dev/null || true
pkill -f "uvicorn.*luna" 2>/dev/null || true

# Kill by port (more reliable)
lsof -ti:8000 | xargs kill -9 2>/dev/null || true

# Kill frontend
pkill -f "vite" 2>/dev/null || true
lsof -ti:5173 | xargs kill -9 2>/dev/null || true

sleep 1

# Verify
if lsof -i:8000 > /dev/null 2>&1; then
    echo "⚠️  Port 8000 still in use"
else
    echo "✓ Backend stopped"
fi

if lsof -i:5173 > /dev/null 2>&1; then
    echo "⚠️  Port 5173 still in use"
else
    echo "✓ Frontend stopped"
fi

echo "🛑 Luna Engine stopped"
```

### 3. Update `scripts/launch_app.sh`

```bash
#!/bin/bash
# =============================================================================
# LUNA HUB APP LAUNCHER
# =============================================================================

PROJECT_ROOT="/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root"

# Relaunch everything (with health checks)
"$PROJECT_ROOT/scripts/relaunch.sh"

# Check if relaunch succeeded
if [ $? -ne 0 ]; then
    echo "Launch failed! Check logs."
    exit 1
fi

# Open browser
sleep 1
open "http://localhost:5173" 2>/dev/null || echo "Open http://localhost:5173 in your browser"

echo ""
echo "Luna Hub is running. Press Ctrl+C to stop."
echo ""

# Tail logs (user can Ctrl+C to exit)
tail -f /tmp/luna_backend.log
```

---

## Testing

After applying fixes:

```bash
# Full stop
./scripts/stop.sh

# Fresh start
./scripts/relaunch.sh

# Should see:
# ✓ Backend is healthy
# ✓ Frontend started

# Verify
curl http://localhost:8000/health
# {"status":"healthy","state":"RUNNING"}
```

---

## Root Cause

The `relaunch.sh` script had a stale reference to `luna.voice.server` which was either:
1. Moved to the Eclessi project
2. Never existed in this project
3. Left over from a refactor

The voice server is in `/Users/zayneamason/_HeyLuna_BETA/_Eclessi_BetaProject_Root/src/voice/` — it's a separate concern from the Luna Engine API server.

---

## Acceptance Criteria

- [ ] `./scripts/stop.sh` reliably kills all Luna processes
- [ ] `./scripts/relaunch.sh` starts backend with health check validation
- [ ] `./scripts/relaunch.sh` fails loudly if backend doesn't start
- [ ] `./scripts/launch_app.sh` works as one-click launcher
- [ ] Backend logs go to `/tmp/luna_backend.log`
- [ ] Frontend logs go to `/tmp/luna_frontend.log`

---

## Priority

**P0** — Can't develop or test anything if the server won't start reliably.
