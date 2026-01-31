"""
Persona Forge TUI - Command Center Interface.

A Textual-based terminal user interface for the Persona Forge pipeline.

Panels:
- Crucible (left): Sources, loaded data
- Anvil (center): Commands, pipeline controls
- Overwatch (right): Metrics, charts

Features:
- Command palette (/)
- Theme switching (synthwave, midnight, ember)
- Luna moon ASCII art widget
- Live metrics display
"""

from .app import PersonaForgeApp


def run_tui() -> None:
    """Launch the Persona Forge TUI application."""
    app = PersonaForgeApp()
    app.run()


__all__ = ["PersonaForgeApp", "run_tui"]
