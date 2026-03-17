"""Entry point for python -m lunar_forge.tui."""

from .app import LunarForgeApp

if __name__ == "__main__":
    app = LunarForgeApp()
    app.run()
