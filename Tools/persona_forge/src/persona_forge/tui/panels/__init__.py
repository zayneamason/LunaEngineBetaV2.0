"""
Persona Forge TUI Panels.

The four-panel layout:
- Crucible: Source file management (left)
- Anvil: Command output and logs (center)
- Overwatch: Metrics and quality gauges (right)
- Personality: 8-dimensional personality profile (right, below overwatch)
"""

from .crucible import CruciblePanel
from .anvil import AnvilPanel
from .overwatch import OverwatchPanel
from .personality import PersonalityPanel

__all__ = ["CruciblePanel", "AnvilPanel", "OverwatchPanel", "PersonalityPanel"]
