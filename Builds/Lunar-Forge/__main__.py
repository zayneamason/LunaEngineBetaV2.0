"""Entry point for python -m lunar_forge (runs TUI)."""

from .tui.app import LunarForgeApp

if __name__ == "__main__":
    app = LunarForgeApp()
    app.run()
