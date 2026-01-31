#!/bin/bash
# Persona Forge TUI Launcher
# Run this script to launch the TUI

cd "$(dirname "$0")"
/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 -c "from persona_forge.tui import run_tui; run_tui()"
