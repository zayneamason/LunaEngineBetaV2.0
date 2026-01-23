#!/bin/bash
# =============================================================================
# LUNA HUB APP LAUNCHER
# =============================================================================
# Double-click this to launch Luna Hub
# 
# To make this a proper macOS app:
# 1. Open Automator
# 2. Create new Application
# 3. Add "Run Shell Script" action
# 4. Paste: /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/scripts/launch_app.sh
# 5. Save as "Luna Hub.app" to Applications or Desktop
# =============================================================================

PROJECT_ROOT="/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root"

# Relaunch everything
"$PROJECT_ROOT/scripts/relaunch.sh"

# Wait for backend to be ready
echo "Waiting for backend..."
sleep 3

# Open the hub in browser (adjust URL as needed)
open "http://localhost:5173" 2>/dev/null || open "http://localhost:3000" 2>/dev/null || echo "Open your browser to the Luna Hub URL"

# Keep terminal open to show logs
echo ""
echo "Luna Hub is running. Press Ctrl+C to stop."
echo ""
tail -f /tmp/luna_backend.log
