# HANDOFF: Luna Engine Launcher

**Created:** 2026-02-18
**Author:** The Dude (Architecture)
**For:** Claude Code Execution
**Complexity:** M (3-5 hours)
**Dependencies:** None — standalone improvement

---

## 1. THE PROBLEM

Launching Luna requires manually managing 4 services across scattered config:

| Service | Current Port | Where It's Hardcoded |
|---------|-------------|---------------------|
| Backend (uvicorn) | 8000 | `launch_luna.sh` line 10: `PORT=8000` |
| Frontend (Vite) | 5173 | `frontend/vite.config.js` line 7 |
| Observatory | 8100 | `frontend/vite.config.js` line 33 (proxy target) |
| Cloudflare Tunnel | — | `launch_luna.sh` (targets backend port) |

**Pain points:**
- Changing ports requires editing 3 files
- Vite proxy routes have 8 hardcoded `localhost:8000` references and 1 `localhost:8100`
- No way to toggle services on/off without editing shell script
- No pre-flight checks (port conflicts silently break things)
- No `--stop` or `--status` commands
- Observatory and tunnel aren't managed by the launcher at all

**What already works (don't break these):**
- `run.py` already has `--port` flag
- Frontend source uses relative URLs only (proxy handles routing)
- Observatory server accepts `--port`
- Cloudflared accepts `--url` argument

---

## 2. THE SOLUTION

Three deliverables:

1. **`config/luna.launch.json`** — Single source of truth for all ports and service toggles
2. **`scripts/launch_luna.sh`** — Rewritten launcher that reads config, accepts CLI overrides, manages all 4 services
3. **`scripts/luna_launcher.html`** — Standalone browser-based config UI that reads/writes the JSON

### Architecture

```
config/luna.launch.json  (source of truth)
        |                       |
   [CLI reads]            [HTML UI writes]
        |                       |
        v                       |
  launch_luna.sh  <-------------+
        |
   +---------+-----------+------------+
   |         |           |            |
   v         v           v            v
 Backend   Frontend   Observatory   Tunnel
 :8000     :5173      :8100         cloudflared
```

### Override Precedence (highest to lowest)

1. CLI flags: `--backend-port 9000`
2. Environment vars: `LUNA_BACKEND_PORT=9000`
3. Config file: `config/luna.launch.json`
4. Hardcoded defaults: `8000`

---

## 3. CONFIG FILE

### Create `config/luna.launch.json`

```json
{
  "services": {
    "backend": {
      "port": 8000,
      "enabled": true,
      "host": "0.0.0.0",
      "debug": false
    },
    "frontend": {
      "port": 5173,
      "enabled": true
    },
    "observatory": {
      "port": 8100,
      "enabled": false,
      "start_production": false
    },
    "tunnel": {
      "enabled": false,
      "patch_apps_script": true
    }
  },
  "profiles": {
    "default": {
      "services": {
        "backend": { "enabled": true },
        "frontend": { "enabled": true },
        "observatory": { "enabled": false },
        "tunnel": { "enabled": false }
      }
    },
    "full": {
      "services": {
        "backend": { "enabled": true },
        "frontend": { "enabled": true },
        "observatory": { "enabled": true },
        "tunnel": { "enabled": true }
      }
    },
    "api-only": {
      "services": {
        "backend": { "enabled": true },
        "frontend": { "enabled": false },
        "observatory": { "enabled": false },
        "tunnel": { "enabled": false }
      }
    }
  }
}
```

### Design decisions:

- **Profiles** for common setups so you don't toggle 4 switches every time
- **Flat JSON** — one level of service config, profiles just override top-level
- **Lives in `config/`** alongside `llm_providers.json`, `personality.json`, etc.
- **`debug` on backend only** — controls logging level
- **`observatory.start_production`** — starts sandbox pointed at prod Memory Matrix when true
- **If file doesn't exist**, launcher uses hardcoded defaults. First run works with no config.

---

## 4. CLI SPEC

### Rewrite `scripts/launch_luna.sh`

**Replace the current 110-line script entirely.** The new script (~250 lines) handles all 4 services.

#### Flags

```
./scripts/launch_luna.sh [OPTIONS]

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
```

#### Usage Examples

```bash
./scripts/launch_luna.sh                          # Uses config file defaults
./scripts/launch_luna.sh --profile full           # Everything on
./scripts/launch_luna.sh --backend-port 9000      # Custom backend port
./scripts/launch_luna.sh --no-frontend --tunnel   # Headless + tunnel
./scripts/launch_luna.sh --status                 # Check what's running
./scripts/launch_luna.sh --stop                   # Kill everything
```

#### Implementation Structure

```bash
#!/bin/bash
# launch_luna.sh — Luna Engine Launcher
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

# ── 1. Read config file ──
read_config() {
  if [ ! -f "$CONFIG_FILE" ]; then
    return  # Use defaults
  fi

  # Use Python to parse JSON into shell variables
  # Applies profile merging if PROFILE is set
  eval "$(python3 << 'PYEOF'
import json, sys, os

config_file = os.environ.get("CONFIG_FILE", "config/luna.launch.json")
profile_name = os.environ.get("PROFILE", "")

try:
    with open(config_file) as f:
        cfg = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    sys.exit(0)  # Silently use defaults

services = dict(cfg.get("services", {}))

# Apply profile overrides if specified
if profile_name and profile_name in cfg.get("profiles", {}):
    profile = cfg["profiles"][profile_name]
    for svc, overrides in profile.get("services", {}).items():
        if svc in services:
            services[svc] = {**services[svc], **overrides}

# Emit shell variables
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

# ── 3. Also check env var overrides ──
apply_env_overrides() {
  [ -n "$LUNA_BACKEND_PORT" ]     && BACKEND_PORT="$LUNA_BACKEND_PORT"
  [ -n "$LUNA_FRONTEND_PORT" ]    && FRONTEND_PORT="$LUNA_FRONTEND_PORT"
  [ -n "$LUNA_OBSERVATORY_PORT" ] && OBSERVATORY_PORT="$LUNA_OBSERVATORY_PORT"
}

# ── 4. Pre-flight checks ──
preflight() {
  echo ""
  echo -e "${CYAN}Luna Engine Launcher — Pre-flight Check${NC}"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""

  LAUNCH_LIST=""
  SKIP_LIST=""

  check_service "Backend"     "$BACKEND_PORT"     "$BACKEND_ENABLED"
  check_service "Frontend"    "$FRONTEND_PORT"     "$FRONTEND_ENABLED"
  check_service "Observatory" "$OBSERVATORY_PORT"  "$OBSERVATORY_ENABLED"

  # Tunnel doesn't need a port check, just check cloudflared exists
  if [ "$TUNNEL_ENABLED" = true ]; then
    if command -v cloudflared &>/dev/null; then
      echo -e "  ${GREEN}✓${NC} Tunnel       cloudflared found"
      LAUNCH_LIST="$LAUNCH_LIST tunnel"
    else
      echo -e "  ${RED}✗${NC} Tunnel       cloudflared not found (install: brew install cloudflared)"
      SKIP_LIST="$SKIP_LIST tunnel(missing)"
    fi
  else
    echo -e "  ${YELLOW}–${NC} Tunnel       (disabled)"
  fi

  echo ""

  # Dependency checks
  echo "Dependencies:"
  for dep in python3 node; do
    if command -v "$dep" &>/dev/null; then
      ver=$($dep --version 2>&1 | head -1)
      echo -e "  ${GREEN}✓${NC} $dep     $ver"
    else
      echo -e "  ${RED}✗${NC} $dep     NOT FOUND"
    fi
  done

  echo ""

  if [ -n "$SKIP_LIST" ]; then
    echo -e "${YELLOW}Skipping:${NC}$SKIP_LIST"
  fi
}

check_service() {
  local name="$1" port="$2" enabled="$3"

  if [ "$enabled" != true ]; then
    printf "  ${YELLOW}–${NC} %-13s (disabled)\n" "$name"
    return
  fi

  local pid
  pid=$(lsof -t -i ":$port" 2>/dev/null | head -1)

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
  PIDS="{}"

  # Backend (must start first — frontend proxies to it)
  if [ "$BACKEND_ENABLED" = true ]; then
    echo -e "${CYAN}Starting backend on :$BACKEND_PORT...${NC}"
    cd "$ROOT"
    local debug_flag=""
    [ "$BACKEND_DEBUG" = true ] && debug_flag="--debug"
    python scripts/run.py --server --host "$BACKEND_HOST" --port "$BACKEND_PORT" $debug_flag &
    local backend_pid=$!

    # Wait for health endpoint
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
    local frontend_pid=$!
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
    local observatory_pid=$!
    echo -e "  ${GREEN}●${NC} Observatory on :$OBSERVATORY_PORT (PID $observatory_pid)"
    cd "$ROOT"
  fi

  # Tunnel
  if [ "$TUNNEL_ENABLED" = true ]; then
    echo -e "${CYAN}Starting cloudflared tunnel...${NC}"
    local tunnel_log
    tunnel_log=$(mktemp)
    cloudflared tunnel --url "http://localhost:$BACKEND_PORT" 2>"$tunnel_log" &
    local tunnel_pid=$!

    # Wait for tunnel URL
    local tunnel_url=""
    for i in $(seq 1 15); do
      tunnel_url=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$tunnel_log" 2>/dev/null | head -1)
      [ -n "$tunnel_url" ] && break
      sleep 1
    done

    if [ -n "$tunnel_url" ]; then
      echo -e "  ${GREEN}●${NC} Tunnel: $tunnel_url"

      # Patch Apps Script sidebar
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
  write_pid_file
}

# ── 6. PID file management ──
write_pid_file() {
  python3 -c "
import json
pids = {}
$([ -n "$backend_pid" ] && echo "pids['backend'] = {'pid': $backend_pid, 'port': $BACKEND_PORT}")
$([ -n "$frontend_pid" ] && echo "pids['frontend'] = {'pid': $frontend_pid, 'port': $FRONTEND_PORT}")
$([ -n "$observatory_pid" ] && echo "pids['observatory'] = {'pid': $observatory_pid, 'port': $OBSERVATORY_PORT}")
$([ -n "$tunnel_pid" ] && echo "pids['tunnel'] = {'pid': $tunnel_pid}")
$([ -n "$tunnel_url" ] && echo "pids.get('tunnel', {})['url'] = '$tunnel_url'")
with open('$PID_FILE', 'w') as f:
    json.dump(pids, f, indent=2)
"
}

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
        print(f'  ● {svc:<13s} {port_str:<6s} PID {pid}{extra}')
    else:
        print(f'  ○ {svc:<13s} (not running)')
"
  echo ""
}

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

# ── Cleanup trap ──
cleanup() {
  echo ""
  stop_all
}
trap cleanup EXIT INT TERM

# ── Main ──
export CONFIG_FILE PROFILE  # For Python subprocess
read_config
parse_args "$@"
apply_env_overrides
preflight

if [ "$DRY_RUN" = true ]; then
  echo "[DRY RUN — no services started]"
  exit 0
fi

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

# Keep alive — wait for the first background process
wait
```

---

## 5. VITE CONFIG UPDATE

### Modify `frontend/vite.config.js`

Replace the current hardcoded config with env-var-backed version:

```javascript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Read from env vars (set by launcher) or fall back to defaults
const BACKEND_PORT = process.env.LUNA_BACKEND_PORT || 8000;
const OBS_PORT = process.env.LUNA_OBSERVATORY_PORT || 8100;

const backendTarget = 'http://localhost:' + BACKEND_PORT;
const obsTarget = 'http://localhost:' + OBS_PORT;

export default defineConfig({
  plugins: [react()],
  server: {
    port: parseInt(process.env.LUNA_FRONTEND_PORT || '5173'),
    proxy: {
      '/api': {
        target: backendTarget,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '')
      },
      '/kozmo': {
        target: backendTarget,
        changeOrigin: true,
        ws: true,
      },
      '/kozmo-assets': {
        target: backendTarget,
        changeOrigin: true,
      },
      '/project': {
        target: backendTarget,
        changeOrigin: true,
      },
      '/eden': {
        target: backendTarget,
        changeOrigin: true,
      },
      '/observatory': {
        target: obsTarget,
        changeOrigin: true,
        ws: true,
        rewrite: (path) => path.replace(/^\/observatory/, ''),
      },
      '/persona': {
        target: backendTarget,
        changeOrigin: true,
      },
      '/hub': {
        target: backendTarget,
        changeOrigin: true,
      },
      '/abort': {
        target: backendTarget,
        changeOrigin: true,
      },
    }
  }
})
```

**Critical:** This must remain backward-compatible. If env vars are NOT set (e.g., someone runs `npm run dev` directly), it falls back to `8000` / `8100` / `5173` — exactly the current behavior.

---

## 6. CONFIG UI

### Create `scripts/luna_launcher.html`

A standalone HTML file that opens in the browser (`open scripts/luna_launcher.html`).

**What it does:**
- Reads `config/luna.launch.json` via a file input (or starts with defaults if no file loaded)
- Shows service cards with port inputs and on/off toggles
- Shows profile selector (default, full, api-only)
- Generates and displays the equivalent CLI command
- Has a "Save Config" button that downloads the updated JSON
- Has a "Copy Command" button for the CLI

**What it does NOT do:**
- Does not start services (that's the CLI's job)
- Does not require a running server (it's a static HTML file)
- No dependencies — vanilla HTML/CSS/JS

**Implementation notes:**
- Since browsers can't write to the filesystem directly, "Save" downloads a file that the user places in `config/`
- Alternatively, we can include a tiny Python one-liner in the HTML page instructions: "After downloading, run: `mv ~/Downloads/luna.launch.json config/`"
- Keep it simple — this is a config editor, not a dashboard

---

## 7. FILES

| File | Action | Lines | Description |
|------|--------|-------|-------------|
| `config/luna.launch.json` | **NEW** | ~45 | Service ports, toggles, and profiles |
| `scripts/launch_luna.sh` | **REWRITE** | ~280 | Full launcher with config reader, pre-flight, PID tracking, --status/--stop |
| `scripts/luna_launcher.html` | **NEW** | ~250 | Standalone browser config UI |
| `frontend/vite.config.js` | **MODIFY** | ~10 changed | Read ports from env vars with fallback to defaults |

---

## 8. TESTING

### Test 1: Default launch (no config file)

```bash
# Remove config if it exists
mv config/luna.launch.json config/luna.launch.json.bak 2>/dev/null

# Should launch with defaults
./scripts/launch_luna.sh --dry-run

# Expected: Backend:8000, Frontend:5173, Observatory:disabled, Tunnel:disabled
```

### Test 2: Config file is read

```bash
# Restore config
mv config/luna.launch.json.bak config/luna.launch.json

# Set custom port in config
python3 -c "
import json
with open('config/luna.launch.json') as f:
    cfg = json.load(f)
cfg['services']['backend']['port'] = 9000
with open('config/luna.launch.json', 'w') as f:
    json.dump(cfg, f, indent=2)
"

./scripts/launch_luna.sh --dry-run
# Expected: Backend:9000
```

### Test 3: CLI overrides config

```bash
./scripts/launch_luna.sh --backend-port 7777 --dry-run
# Expected: Backend:7777 (regardless of config file value)
```

### Test 4: Profile loading

```bash
./scripts/launch_luna.sh --profile full --dry-run
# Expected: All 4 services enabled

./scripts/launch_luna.sh --profile api-only --dry-run
# Expected: Only backend enabled
```

### Test 5: Port conflict detection

```bash
# Start dummy server on 8000
python3 -m http.server 8000 &
DUMMY=$!

./scripts/launch_luna.sh --dry-run
# Expected: Backend shows "port in use — PID $DUMMY, python3"

kill $DUMMY
```

### Test 6: Status and stop

```bash
# Launch
./scripts/launch_luna.sh &
sleep 5

# Check status
./scripts/launch_luna.sh --status
# Expected: Shows running services with PIDs

# Stop
./scripts/launch_luna.sh --stop
# Expected: All killed, PID file cleaned
```

### Test 7: Vite env var passthrough

```bash
cd frontend

# Verify env vars are read
LUNA_BACKEND_PORT=9999 npx vite --config vite.config.js 2>&1 &
VITE_PID=$!
sleep 3

# Check that proxy target changed
curl -s http://localhost:5173/api/health 2>&1
# Should attempt to proxy to localhost:9999, not 8000

kill $VITE_PID
```

### Test 8: Backward compatibility

```bash
# Plain npm run dev (no env vars) should still work with default ports
cd frontend
npm run dev &
sleep 3
# Should proxy to localhost:8000 as before
kill %1
```

---

## 9. SUCCESS CRITERIA

1. `config/luna.launch.json` exists with default config + 3 profiles
2. `launch_luna.sh` reads config, accepts CLI overrides, launches services in dependency order
3. Pre-flight checks detect port conflicts and missing dependencies
4. `--status` shows running services with PIDs and ports
5. `--stop` kills all Luna services and cleans up
6. `--dry-run` shows what would launch without starting anything
7. PID tracking in `/tmp/luna_launcher.pids`
8. `vite.config.js` reads `LUNA_BACKEND_PORT`, `LUNA_OBSERVATORY_PORT`, `LUNA_FRONTEND_PORT` from env
9. Frontend still works with plain `npm run dev` (defaults apply, no env vars needed)
10. Tunnel captures URL and patches Apps Script sidebar
11. Ctrl+C cleanup kills all services and restores sidebar URL to localhost
12. `luna_launcher.html` opens in browser, shows config UI, generates CLI command, saves JSON

---

## 10. WHAT THIS DOES NOT DO

- **Does not change `run.py`** — it already has `--port`, launcher just passes the flag
- **Does not change `server.py`** — port comes from uvicorn, no changes needed
- **Does not change frontend source code** — already uses relative URLs
- **Does not add npm/Python dependencies** — pure bash + vanilla HTML
- **Does not auto-detect optimal ports** — user configures, launcher validates
- **Does not manage MCP server ports** — that's a separate concern

---

## 11. EXECUTION ORDER

1. Create `config/luna.launch.json` with default config
2. Modify `frontend/vite.config.js` — extract hardcoded ports to env vars
3. Test: `npm run dev` still works without env vars (backward compat)
4. Test: `LUNA_BACKEND_PORT=9999 npm run dev` reads the env var
5. Rewrite `scripts/launch_luna.sh` — start with the config reader and arg parser
6. Add pre-flight checks (port availability, dependency detection)
7. Add service launch logic (backend → frontend → observatory → tunnel)
8. Add PID file management, `--status`, `--stop`
9. Add cleanup trap
10. Test full launch cycle: start → status → stop
11. Test with `--profile full` and custom port overrides
12. Create `scripts/luna_launcher.html` — config editor UI
13. Test HTML UI: load defaults, change ports, save config, copy CLI command
14. Run all test scenarios from Section 8
