#!/usr/bin/env python3
"""
Persona Forge Launcher

Usage:
    python launch.py          # Launch TUI (default)
    python launch.py tui      # Launch TUI
    python launch.py mcp      # Start MCP server
    python launch.py cli      # Show CLI help
"""

import sys


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "tui"

    if mode == "tui":
        from persona_forge.tui import run_tui
        run_tui()
    elif mode == "mcp":
        from persona_forge.mcp import main as run_mcp
        run_mcp()
    elif mode == "cli":
        from persona_forge.cli import app
        app()
    else:
        print(f"Unknown mode: {mode}")
        print("Available: tui, mcp, cli")
        sys.exit(1)


if __name__ == "__main__":
    main()
