#!/bin/bash
# launch_luna.sh — One-command Luna + tunnel launcher
# Starts the Luna server, opens a cloudflared tunnel,
# and auto-updates the Apps Script sidebar URL.
#
# Usage:  ./scripts/launch_luna.sh
# Stop:   Ctrl+C (kills both server and tunnel)

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GOOGLE_DIR="$ROOT/scripts/google"
SIDEBAR_FILE="$GOOGLE_DIR/luna-side-bar.js"
PORT=8000

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

cleanup() {
  echo ""
  echo -e "${YELLOW}Shutting down...${NC}"
  [ -n "$TUNNEL_PID" ] && kill "$TUNNEL_PID" 2>/dev/null
  [ -n "$SERVER_PID" ] && kill "$SERVER_PID" 2>/dev/null
  # Restore the default URL so we don't leave a stale tunnel URL in the code
  if [ -f "$SIDEBAR_FILE" ]; then
    sed -i '' "s|url = '.*';  // AUTO-TUNNEL-URL|url = 'http://localhost:8000';  // AUTO-TUNNEL-URL|" "$SIDEBAR_FILE" 2>/dev/null
  fi
  echo -e "${GREEN}Done.${NC}"
  exit 0
}
trap cleanup EXIT INT TERM

# ── 1. Start Luna server if not running ──
if lsof -i :$PORT -t >/dev/null 2>&1; then
  echo -e "${GREEN}Luna server already running on :$PORT${NC}"
else
  echo -e "${CYAN}Starting Luna server...${NC}"
  cd "$ROOT"
  python scripts/run.py --server &
  SERVER_PID=$!
  echo -e "  PID: $SERVER_PID"

  # Wait for server to be ready
  for i in $(seq 1 30); do
    if curl -s http://localhost:$PORT/health >/dev/null 2>&1; then
      echo -e "${GREEN}  Server ready.${NC}"
      break
    fi
    sleep 1
  done
fi

# ── 2. Start cloudflared tunnel ──
echo -e "${CYAN}Starting cloudflared tunnel...${NC}"
TUNNEL_LOG=$(mktemp)
cloudflared tunnel --url http://localhost:$PORT 2>"$TUNNEL_LOG" &
TUNNEL_PID=$!

# Wait for the tunnel URL
TUNNEL_URL=""
for i in $(seq 1 15); do
  TUNNEL_URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$TUNNEL_LOG" 2>/dev/null | head -1)
  if [ -n "$TUNNEL_URL" ]; then
    break
  fi
  sleep 1
done

if [ -z "$TUNNEL_URL" ]; then
  echo "ERROR: Could not get tunnel URL. Check cloudflared output:"
  cat "$TUNNEL_LOG"
  exit 1
fi

echo -e "${GREEN}  Tunnel: $TUNNEL_URL${NC}"

# ── 3. Update Apps Script with new tunnel URL ──
echo -e "${CYAN}Updating Apps Script sidebar URL...${NC}"

# Patch the default URL in luna-side-bar.js
# We replace the getLunaApiUrl default so it always points to the current tunnel
if grep -q "AUTO-TUNNEL-URL" "$SIDEBAR_FILE"; then
  # Already has our marker — just update the URL
  sed -i '' "s|url = '.*';  // AUTO-TUNNEL-URL|url = '$TUNNEL_URL';  // AUTO-TUNNEL-URL|" "$SIDEBAR_FILE"
else
  # First time — add the marker to the default URL line
  sed -i '' "s|url = 'http://localhost:8000';|url = '$TUNNEL_URL';  // AUTO-TUNNEL-URL|" "$SIDEBAR_FILE"
fi

# Push to Apps Script
cd "$GOOGLE_DIR"
clasp push --force 2>&1 | sed 's/^/  /'
cd "$ROOT"

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Luna is live!${NC}"
echo -e "${GREEN}  Local:  http://localhost:$PORT${NC}"
echo -e "${GREEN}  Tunnel: $TUNNEL_URL${NC}"
echo -e "${GREEN}  Sidebar will auto-connect — just open it in Sheets.${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop.${NC}"

# Keep alive
wait $TUNNEL_PID
