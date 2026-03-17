#!/bin/bash
# launch_luna.sh — Luna Engine Launcher
# Reads config from config/luna.launch.json
# Accepts CLI overrides for one-off changes
# Launches all enabled services with health checks
#
# Usage:
#   ./scripts/launch_luna.sh                    # Default config
#   ./scripts/launch_luna.sh --profile full     # All services
#   ./scripts/launch_luna.sh --backend-port 9000
#   ./scripts/launch_luna.sh --no-frontend --tunnel
#   ./scripts/launch_luna.sh --status
#   ./scripts/launch_luna.sh --stop

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG_FILE="$ROOT/config/luna.launch.json"
PID_FILE="/tmp/luna_launcher.pids"
GOOGLE_DIR="$ROOT/scripts/google"
SIDEBAR_FILE="$GOOGLE_DIR/luna-side-bar.js"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

# ── Defaults ──
BACKEND_PORT=8000
BACKEND_ENABLED=true
BACKEND_HOST="0.0.0.0"
BACKEND_DEBUG=false
FRONTEND_PORT=5173
FRONTEND_ENABLED=true
OBSERVATORY_PORT=8100
OBSERVATORY_ENABLED=false
OBSERVATORY_START_PRODUCTION=false
TUNNEL_ENABLED=false
TUNNEL_PATCH_APPS_SCRIPT=true
PROFILE=""
DRY_RUN=false

# ── 1. Read config file ──
read_config() {
  if [ ! -f "$CONFIG_FILE" ]; then
    return  # Use defaults
  fi

  eval "$(CONFIG_FILE="$CONFIG_FILE" PROFILE="$PROFILE" python3 << 'PYEOF'
import json, sys, os

config_file = os.environ.get("CONFIG_FILE", "config/luna.launch.json")
profile_name = os.environ.get("PROFILE", "")

try:
    with open(config_file) as f:
        cfg = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    sys.exit(0)

services = dict(cfg.get("services", {}))

if profile_name and profile_name in cfg.get("profiles", {}):
    profile = cfg["profiles"][profile_name]
    for svc, overrides in profile.get("services", {}).items():
        if svc in services:
            services[svc] = {**services[svc], **overrides}

for svc, settings in services.items():
    prefix = svc.upper()
    for key, val in settings.items():
        varname = f"{prefix}_{key.upper()}"
        if isinstance(val, bool):
            val = "true" if val else "false"
        print(f'{varname}="{val}"')
PYEOF
  )"
}

# ── 2. Parse CLI flags (override config) ──
parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --backend-port)    BACKEND_PORT="$2"; shift 2 ;;
      --frontend-port)   FRONTEND_PORT="$2"; shift 2 ;;
      --observatory-port) OBSERVATORY_PORT="$2"; shift 2 ;;
      --profile)         PROFILE="$2"; shift 2 ;;
      --tunnel)          TUNNEL_ENABLED=true; shift ;;
      --no-tunnel)       TUNNEL_ENABLED=false; shift ;;
      --observatory)     OBSERVATORY_ENABLED=true; shift ;;
      --no-frontend)     FRONTEND_ENABLED=false; shift ;;
      --no-backend)      BACKEND_ENABLED=false; shift ;;
      --debug)           BACKEND_DEBUG=true; shift ;;
      --status)          show_status; exit 0 ;;
      --stop)            stop_all; exit 0 ;;
      --dry-run)         DRY_RUN=true; shift ;;
      -h|--help)         show_help; exit 0 ;;
      *)                 echo "Unknown flag: $1"; exit 1 ;;
    esac
  done
}

# ── 3. Env var overrides (between config and CLI) ──
apply_env_overrides() {
  if [ -n "$LUNA_BACKEND_PORT" ]; then BACKEND_PORT="$LUNA_BACKEND_PORT"; fi
  if [ -n "$LUNA_FRONTEND_PORT" ]; then FRONTEND_PORT="$LUNA_FRONTEND_PORT"; fi
  if [ -n "$LUNA_OBSERVATORY_PORT" ]; then OBSERVATORY_PORT="$LUNA_OBSERVATORY_PORT"; fi
}

# ── 4. Pre-flight checks ──
preflight() {
  echo ""
  echo -e "${CYAN}Luna Engine Launcher — Pre-flight Check${NC}"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

  if [ -f "$CONFIG_FILE" ]; then
    local profile_note=""
    [ -n "$PROFILE" ] && profile_note=" (profile: $PROFILE)"
    echo -e "  Config: ${GREEN}$CONFIG_FILE${NC}$profile_note"
  else
    echo -e "  Config: ${YELLOW}(none — using defaults)${NC}"
  fi
  echo ""

  LAUNCH_LIST=""
  SKIP_LIST=""

  check_service "Backend"     "$BACKEND_PORT"     "$BACKEND_ENABLED"
  check_service "Frontend"    "$FRONTEND_PORT"     "$FRONTEND_ENABLED"
  check_service "Observatory" "$OBSERVATORY_PORT"  "$OBSERVATORY_ENABLED"

  if [ "$TUNNEL_ENABLED" = true ]; then
    if command -v cloudflared &>/dev/null; then
      printf "  ${GREEN}✓${NC} %-13s cloudflared found\n" "Tunnel"
      LAUNCH_LIST="$LAUNCH_LIST tunnel"
    else
      printf "  ${RED}✗${NC} %-13s cloudflared not found (brew install cloudflared)\n" "Tunnel"
      SKIP_LIST="$SKIP_LIST tunnel(missing)"
    fi
  else
    printf "  ${YELLOW}–${NC} %-13s (disabled)\n" "Tunnel"
  fi

  echo ""
  echo "Dependencies:"
  for dep in python3 node; do
    if command -v "$dep" &>/dev/null; then
      ver=$("$dep" --version 2>&1 | head -1)
      printf "  ${GREEN}✓${NC} %-13s %s\n" "$dep" "$ver"
    else
      printf "  ${RED}✗${NC} %-13s NOT FOUND\n" "$dep"
    fi
  done

  echo ""

  if [ -n "$SKIP_LIST" ]; then
    echo -e "${YELLOW}Skipping:${NC}$SKIP_LIST"
    echo ""
  fi
}

check_service() {
  local name="$1" port="$2" enabled="$3"

  if [ "$enabled" != true ]; then
    printf "  ${YELLOW}–${NC} %-13s (disabled)\n" "$name"
    return
  fi

  local pid
  pid=$(lsof -t -i ":$port" 2>/dev/null | head -1 || true)

  if [ -n "$pid" ]; then
    local proc_name
    proc_name=$(ps -p "$pid" -o comm= 2>/dev/null || echo "unknown")
    printf "  ${RED}✗${NC} %-13s :%-5s (port in use — PID %s, %s)\n" "$name" "$port" "$pid" "$proc_name"
    SKIP_LIST="$SKIP_LIST $name:$port(conflict)"
  else
    printf "  ${GREEN}✓${NC} %-13s :%-5s (port available)\n" "$name" "$port"
    LAUNCH_LIST="$LAUNCH_LIST $name"
  fi
}

# ── 5. Launch services ──
launch_services() {
  local backend_pid="" frontend_pid="" observatory_pid="" tunnel_pid="" tunnel_url="" faceid_pid=""

  # FaceID (start before backend — backend proxy depends on it)
  local faceid_port=8101
  local existing_faceid
  existing_faceid=$(lsof -t -i ":$faceid_port" 2>/dev/null | head -1 || true)
  if [ -n "$existing_faceid" ]; then
    echo -e "  ${YELLOW}–${NC} FaceID already running on :$faceid_port (PID $existing_faceid)"
  else
    echo -e "${CYAN}Starting FaceID on :$faceid_port...${NC}"
    cd "$ROOT/Tools/FaceID"
    python3 serve.py --port "$faceid_port" &
    faceid_pid=$!
    sleep 2
    if curl -s "http://localhost:$faceid_port/health" >/dev/null 2>&1; then
      echo -e "  ${GREEN}●${NC} FaceID ready on :$faceid_port (PID $faceid_pid)"
    else
      echo -e "  ${YELLOW}!${NC} FaceID may still be starting (PID $faceid_pid)"
    fi
    cd "$ROOT"
  fi

  # Backend (must start first — frontend proxies to it)
  if [ "$BACKEND_ENABLED" = true ]; then
    echo -e "${CYAN}Starting backend on :$BACKEND_PORT...${NC}"
    cd "$ROOT"
    local debug_flag=""
    [ "$BACKEND_DEBUG" = true ] && debug_flag="--debug"
    PYTHONPATH=src python3 scripts/run.py --server --host "$BACKEND_HOST" --port "$BACKEND_PORT" $debug_flag &
    backend_pid=$!

    local ready=false
    for i in $(seq 1 30); do
      if curl -s "http://localhost:$BACKEND_PORT/health" >/dev/null 2>&1; then
        ready=true
        break
      fi
      sleep 1
    done

    if [ "$ready" = true ]; then
      echo -e "  ${GREEN}●${NC} Backend ready on :$BACKEND_PORT (PID $backend_pid)"
    else
      echo -e "  ${RED}✗${NC} Backend failed to start within 30s"
    fi
  fi

  # Frontend
  if [ "$FRONTEND_ENABLED" = true ]; then
    echo -e "${CYAN}Starting frontend on :$FRONTEND_PORT...${NC}"
    cd "$ROOT/frontend"
    LUNA_BACKEND_PORT=$BACKEND_PORT \
    LUNA_OBSERVATORY_PORT=$OBSERVATORY_PORT \
    LUNA_FRONTEND_PORT=$FRONTEND_PORT \
    npm run dev &
    frontend_pid=$!
    echo -e "  ${GREEN}●${NC} Frontend on :$FRONTEND_PORT (PID $frontend_pid)"
    cd "$ROOT"
  fi

  # Observatory
  if [ "$OBSERVATORY_ENABLED" = true ]; then
    echo -e "${CYAN}Starting observatory on :$OBSERVATORY_PORT...${NC}"
    cd "$ROOT/Tools/MemoryMatrix_SandBox"
    local prod_flag=""
    [ "$OBSERVATORY_START_PRODUCTION" = true ] && prod_flag="--production"
    python mcp_server/server.py --http-only --port "$OBSERVATORY_PORT" $prod_flag &
    observatory_pid=$!
    echo -e "  ${GREEN}●${NC} Observatory on :$OBSERVATORY_PORT (PID $observatory_pid)"
    cd "$ROOT"
  fi

  # Tunnel
  if [ "$TUNNEL_ENABLED" = true ]; then
    echo -e "${CYAN}Starting cloudflared tunnel...${NC}"
    local tunnel_log
    tunnel_log=$(mktemp)
    cloudflared tunnel --url "http://localhost:$BACKEND_PORT" 2>"$tunnel_log" &
    tunnel_pid=$!

    tunnel_url=""
    for i in $(seq 1 15); do
      tunnel_url=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$tunnel_log" 2>/dev/null | head -1)
      [ -n "$tunnel_url" ] && break
      sleep 1
    done

    if [ -n "$tunnel_url" ]; then
      echo -e "  ${GREEN}●${NC} Tunnel: $tunnel_url"

      if [ "$TUNNEL_PATCH_APPS_SCRIPT" = true ] && [ -f "$SIDEBAR_FILE" ]; then
        if grep -q "AUTO-TUNNEL-URL" "$SIDEBAR_FILE"; then
          sed -i '' "s|url = '.*';  // AUTO-TUNNEL-URL|url = '$tunnel_url';  // AUTO-TUNNEL-URL|" "$SIDEBAR_FILE"
        else
          sed -i '' "s|url = 'http://localhost:8000';|url = '$tunnel_url';  // AUTO-TUNNEL-URL|" "$SIDEBAR_FILE"
        fi
        cd "$GOOGLE_DIR" && clasp push --force 2>&1 | sed 's/^/  /' && cd "$ROOT"
        echo -e "  ${GREEN}●${NC} Apps Script sidebar updated"
      fi
    else
      echo -e "  ${RED}✗${NC} Could not get tunnel URL"
    fi
    rm -f "$tunnel_log"
  fi

  # Write PID file
  python3 -c "
import json
pids = {}
$([ -n "$faceid_pid" ] && echo "pids['faceid'] = {'pid': $faceid_pid, 'port': 8101}")
$([ -n "$backend_pid" ] && echo "pids['backend'] = {'pid': $backend_pid, 'port': $BACKEND_PORT}")
$([ -n "$frontend_pid" ] && echo "pids['frontend'] = {'pid': $frontend_pid, 'port': $FRONTEND_PORT}")
$([ -n "$observatory_pid" ] && echo "pids['observatory'] = {'pid': $observatory_pid, 'port': $OBSERVATORY_PORT}")
$([ -n "$tunnel_pid" ] && echo "pids['tunnel'] = {'pid': $tunnel_pid}")
$([ -n "$tunnel_url" ] && echo "pids.setdefault('tunnel', {})['url'] = '$tunnel_url'")
with open('$PID_FILE', 'w') as f:
    json.dump(pids, f, indent=2)
"
}

# ── 6. Status command ──
show_status() {
  if [ ! -f "$PID_FILE" ]; then
    echo "No Luna services tracked. Use ./scripts/launch_luna.sh to start."
    return
  fi

  echo ""
  echo -e "${CYAN}Luna Engine — Running Services${NC}"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""

  python3 -c "
import json, os
with open('$PID_FILE') as f:
    pids = json.load(f)

for svc, info in pids.items():
    pid = info.get('pid', 0)
    alive = False
    try:
        os.kill(pid, 0)
        alive = True
    except (OSError, TypeError):
        pass

    if alive:
        port = info.get('port', '')
        url = info.get('url', '')
        port_str = f':{port}' if port else ''
        extra = f'  {url}' if url else ''
        print(f'  \u25cf {svc:<13s} {port_str:<6s} PID {pid}{extra}')
    else:
        print(f'  \u25cb {svc:<13s} (not running)')
"
  echo ""
}

# ── 7. Stop command ──
stop_all() {
  if [ ! -f "$PID_FILE" ]; then
    echo "No Luna services tracked."
    return
  fi

  echo -e "${YELLOW}Stopping Luna services...${NC}"

  python3 -c "
import json, os, signal
with open('$PID_FILE') as f:
    pids = json.load(f)

for svc, info in pids.items():
    pid = info.get('pid', 0)
    try:
        os.kill(pid, signal.SIGTERM)
        print(f'  Killed {svc} (PID {pid})')
    except OSError:
        print(f'  {svc} already stopped')
"

  rm -f "$PID_FILE"

  # Restore Apps Script sidebar
  if [ -f "$SIDEBAR_FILE" ]; then
    sed -i '' "s|url = '.*';  // AUTO-TUNNEL-URL|url = 'http://localhost:8000';  // AUTO-TUNNEL-URL|" "$SIDEBAR_FILE" 2>/dev/null
    echo "  Restored Apps Script sidebar URL to localhost"
  fi

  echo -e "${GREEN}All services stopped.${NC}"
}

# ── Help ──
show_help() {
  cat << 'EOF'
Luna Engine Launcher

Usage: ./scripts/launch_luna.sh [OPTIONS]

Service ports:
  --backend-port PORT       Override backend port (default: 8000)
  --frontend-port PORT      Override frontend port (default: 5173)
  --observatory-port PORT   Override observatory port (default: 8100)

Service toggles:
  --tunnel                  Enable cloudflare tunnel
  --no-tunnel               Disable cloudflare tunnel
  --observatory             Enable observatory
  --no-frontend             Disable frontend
  --no-backend              Disable backend

Config:
  --profile NAME            Use a named profile (default, full, api-only)
  --debug                   Enable debug logging on backend

Commands:
  --status                  Show running services and exit
  --stop                    Kill all Luna processes and exit
  --dry-run                 Show what would launch without starting
  -h, --help                Show this help

Config file: config/luna.launch.json
EOF
}

# ── Cleanup trap (set after we know we're launching) ──
setup_cleanup_trap() {
  trap 'echo ""; stop_all' EXIT INT TERM
}

# ── Service watchdog ──
# Checks every 2s that FaceID, backend, and frontend are still up.
# Restarts any that have died, logging each event.
watchdog_loop() {
  local check_interval=2
  local restart_delay=1

  while true; do
    sleep "$check_interval"

    # FaceID
    if ! curl -s "http://localhost:8101/health" >/dev/null 2>&1; then
      echo -e "${YELLOW}[watchdog]${NC} FaceID down — restarting on :8101"
      cd "$ROOT/Tools/FaceID"
      python3 serve.py --port 8101 &
      cd "$ROOT"
      sleep "$restart_delay"
    fi

    # Backend
    if [ "$BACKEND_ENABLED" = true ] && ! curl -s "http://localhost:$BACKEND_PORT/health" >/dev/null 2>&1; then
      echo -e "${YELLOW}[watchdog]${NC} Backend down — restarting on :$BACKEND_PORT"
      cd "$ROOT"
      local debug_flag=""
      [ "$BACKEND_DEBUG" = true ] && debug_flag="--debug"
      PYTHONPATH=src python3 scripts/run.py --server --host "$BACKEND_HOST" --port "$BACKEND_PORT" $debug_flag &
      sleep "$restart_delay"
    fi

    # Frontend
    if [ "$FRONTEND_ENABLED" = true ] && ! curl -s "http://localhost:$FRONTEND_PORT" >/dev/null 2>&1; then
      echo -e "${YELLOW}[watchdog]${NC} Frontend down — restarting on :$FRONTEND_PORT"
      cd "$ROOT/frontend"
      LUNA_BACKEND_PORT=$BACKEND_PORT npm run dev &
      cd "$ROOT"
      sleep "$restart_delay"
    fi

  done
}

# ── Main ──
# First pass: grab --profile before reading config (it affects config parsing)
for arg in "$@"; do
  if [ "$prev" = "--profile" ]; then
    PROFILE="$arg"
    break
  fi
  prev="$arg"
done

export CONFIG_FILE PROFILE
read_config
parse_args "$@"
apply_env_overrides
preflight

if [ "$DRY_RUN" = true ]; then
  echo "[DRY RUN — no services started]"
  exit 0
fi

setup_cleanup_trap
launch_services

# Status banner
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Luna Engine is live!${NC}"
[ "$BACKEND_ENABLED" = true ]     && echo -e "${GREEN}  ● Backend:     http://localhost:$BACKEND_PORT${NC}"
[ "$FRONTEND_ENABLED" = true ]    && echo -e "${GREEN}  ● Frontend:    http://localhost:$FRONTEND_PORT${NC}"
[ "$OBSERVATORY_ENABLED" = true ] && echo -e "${GREEN}  ● Observatory: http://localhost:$OBSERVATORY_PORT${NC}"
[ -n "$tunnel_url" ]              && echo -e "${GREEN}  ● Tunnel:      $tunnel_url${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all services.${NC}"

# Keep alive — watchdog checks every 2s and restarts any dead service
watchdog_loop
