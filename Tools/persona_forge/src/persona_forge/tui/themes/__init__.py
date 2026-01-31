"""
Persona Forge TUI Themes.

Theme registry for the command center.
Available themes: synthwave, midnight, ember
"""

from typing import Dict, List

from .synthwave import Theme, SYNTHWAVE_THEME


# Additional theme definitions

MIDNIGHT_THEME = Theme(
    name="midnight",
    display_name="Midnight Blue",
    background="#0a0a1a",
    background_dark="#050510",
    foreground="#e0e0ff",
    accent_primary="#6666ff",
    accent_secondary="#9999ff",
    accent_tertiary="#3333cc",
    success="#00ff88",
    warning="#ffcc00",
    error="#ff4466",
    border="#3333ff",
    muted="#666699",
)

EMBER_THEME = Theme(
    name="ember",
    display_name="Ember Glow",
    background="#1a0a0a",
    background_dark="#0a0505",
    foreground="#ffe0e0",
    accent_primary="#ff6633",
    accent_secondary="#ff9966",
    accent_tertiary="#cc3300",
    success="#88ff00",
    warning="#ffff00",
    error="#ff0000",
    border="#ff6633",
    muted="#996666",
)

# Theme registry
THEMES: Dict[str, Theme] = {
    "synthwave": SYNTHWAVE_THEME,
    "midnight": MIDNIGHT_THEME,
    "ember": EMBER_THEME,
}

THEME_NAMES: List[str] = ["synthwave", "midnight", "ember"]


def get_theme(name: str) -> Theme:
    """
    Get a theme by name.

    Args:
        name: Theme name (synthwave, midnight, ember)

    Returns:
        Theme object

    Raises:
        KeyError: If theme not found
    """
    if name not in THEMES:
        raise KeyError(f"Unknown theme: {name}. Available: {', '.join(THEME_NAMES)}")
    return THEMES[name]


def list_themes() -> List[str]:
    """Get list of available theme names."""
    return THEME_NAMES.copy()


__all__ = ["Theme", "get_theme", "list_themes", "THEME_NAMES", "THEMES"]
