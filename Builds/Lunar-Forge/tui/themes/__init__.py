"""Theme system for Lunar Forge TUI."""

from dataclasses import dataclass


@dataclass
class Theme:
    name: str
    bg_deep: str
    bg_panel: str
    bg_highlight: str
    border: str
    primary: str
    secondary: str
    accent: str
    text: str
    text_muted: str
    success: str
    warning: str
    error: str


THEMES = {
    "synthwave": Theme(
        name="synthwave",
        bg_deep="#0D0221",
        bg_panel="#12032A",
        bg_highlight="#2D0844",
        border="#8B00FF",
        primary="#00FFFF",
        secondary="#FF00FF",
        accent="#8B00FF",
        text="#E0E0FF",
        text_muted="#666699",
        success="#00FF00",
        warning="#FFFF00",
        error="#FF4444",
    ),
    "midnight": Theme(
        name="midnight",
        bg_deep="#0a0a1a",
        bg_panel="#0f0f2a",
        bg_highlight="#1a1a4a",
        border="#3333ff",
        primary="#6666ff",
        secondary="#9999ff",
        accent="#3333ff",
        text="#ccccff",
        text_muted="#666688",
        success="#00cc66",
        warning="#ffcc00",
        error="#ff4444",
    ),
    "ember": Theme(
        name="ember",
        bg_deep="#1a0a0a",
        bg_panel="#2a0f0f",
        bg_highlight="#3a1a1a",
        border="#ff6633",
        primary="#ff9966",
        secondary="#ff6633",
        accent="#ff3300",
        text="#ffccaa",
        text_muted="#886644",
        success="#66cc33",
        warning="#ffaa00",
        error="#ff3333",
    ),
}

THEME_NAMES = list(THEMES.keys())


def get_theme(name: str) -> Theme:
    return THEMES.get(name, THEMES["synthwave"])


def list_themes() -> list[str]:
    return THEME_NAMES
