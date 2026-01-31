"""Entry point for running the TUI as a module."""

from .app import PersonaForgeApp

if __name__ == "__main__":
    app = PersonaForgeApp()
    app.run()
