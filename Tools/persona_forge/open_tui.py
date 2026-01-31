#!/usr/bin/env python3
"""
Opens Persona Forge TUI in a new Terminal window.
Run this from anywhere - it will open Terminal.app with the TUI.
"""

import subprocess
import os

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON = "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"

# AppleScript to open Terminal and run the TUI
applescript = f'''
tell application "Terminal"
    activate
    do script "cd '{PROJECT_DIR}' && {PYTHON} -c \\"from persona_forge.tui import run_tui; run_tui()\\""
end tell
'''

subprocess.run(["osascript", "-e", applescript])
print("🌙 Opened Persona Forge TUI in Terminal")
