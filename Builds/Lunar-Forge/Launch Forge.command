#!/bin/bash
# Lunar Forge Launcher — double-click to open
# Starts the backend (if not already running) and opens the browser.

cd "$(dirname "$0")"

PORT=8200

echo ""
echo "  ╔═══════════════════════════════╗"
echo "  ║       LUNAR FORGE v0.1        ║"
echo "  ╚═══════════════════════════════╝"
echo ""

# Use the same Python that has fastapi installed
PYTHON="${PYTHON:-python3}"

# Check if fastapi is available
if ! "$PYTHON" -c "import fastapi" 2>/dev/null; then
    echo "  ERROR: fastapi not installed."
    echo "  Run: pip install fastapi uvicorn"
    echo ""
    read -p "  Press Enter to close..."
    exit 1
fi

# serve.py handles singleton detection — if already running, it opens browser and exits
exec "$PYTHON" serve.py "$PORT"
