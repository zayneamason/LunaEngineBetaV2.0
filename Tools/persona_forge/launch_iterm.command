#!/bin/bash
# Persona Forge TUI Launcher - Forces iTerm2
# Double-click to launch TUI with inline graphics support

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Check if already in iTerm2
if [[ "$TERM_PROGRAM" == "iTerm.app" ]]; then
    cd "$SCRIPT_DIR"
    echo "🌙 Launching Persona Forge TUI..."
    PYTHONPATH="$SCRIPT_DIR/src" /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 -c "from persona_forge.tui import run_tui; run_tui()"
else
    # Open in iTerm2 using AppleScript
    osascript <<EOF
tell application "iTerm"
    activate
    create window with default profile
    tell current session of current window
        write text "cd '$SCRIPT_DIR' && PYTHONPATH=src /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 -c 'from persona_forge.tui import run_tui; run_tui()'"
    end tell
end tell
EOF
fi
