#!/bin/bash
# Persona Forge TUI Launcher
# Double-click this file to open TUI in a new terminal window

cd "$(dirname "$0")"
echo "🌙 Launching Persona Forge TUI..."
/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 -c "from persona_forge.tui import run_tui; run_tui()"
