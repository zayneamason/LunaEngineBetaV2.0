"""
Synthwave Theme - Neon Cyberpunk Aesthetic.

The default theme for Persona Forge, featuring:
- Cyan (#00FFFF) primary highlights
- Magenta (#FF00FF) accents
- Purple (#8B00FF) borders and tertiary elements
- Deep purple/black backgrounds
"""

from dataclasses import dataclass
from typing import Dict


@dataclass
class Theme:
    """
    A color theme for the TUI.

    Attributes:
        name: Theme identifier
        display_name: Human-readable name
        background: Primary background color
        background_dark: Darker background variant
        foreground: Primary text color
        accent_primary: Primary accent (highlights)
        accent_secondary: Secondary accent
        accent_tertiary: Tertiary accent
        success: Success/positive color
        warning: Warning color
        error: Error/negative color
        border: Border color
        muted: Muted/dim text color
    """
    name: str
    display_name: str
    background: str
    background_dark: str
    foreground: str
    accent_primary: str
    accent_secondary: str
    accent_tertiary: str
    success: str
    warning: str
    error: str
    border: str
    muted: str

    def to_css_vars(self) -> Dict[str, str]:
        """Convert to CSS variable dict."""
        return {
            "--background": self.background,
            "--background-dark": self.background_dark,
            "--foreground": self.foreground,
            "--accent-primary": self.accent_primary,
            "--accent-secondary": self.accent_secondary,
            "--accent-tertiary": self.accent_tertiary,
            "--success": self.success,
            "--warning": self.warning,
            "--error": self.error,
            "--border": self.border,
            "--muted": self.muted,
        }


SYNTHWAVE_THEME = Theme(
    name="synthwave",
    display_name="Synthwave",

    # Backgrounds - deep purple/violet
    background="#0D0221",        # Nearly black with purple tint
    background_dark="#080116",   # Even darker variant

    # Foreground - bright for contrast
    foreground="#E0E0FF",        # Soft white with blue tint

    # Accents - neon colors
    accent_primary="#00FFFF",    # Cyan - primary highlights
    accent_secondary="#FF00FF",  # Magenta - secondary accents
    accent_tertiary="#8B00FF",   # Electric purple - borders

    # Status colors
    success="#00FF00",           # Neon green
    warning="#FFFF00",           # Bright yellow
    error="#FF4444",             # Soft red

    # UI elements
    border="#8B00FF",            # Purple borders
    muted="#666699",             # Dimmed text
)


# Color palette reference for CSS
SYNTHWAVE_PALETTE = {
    # Primary neon colors
    "cyan": "#00FFFF",
    "magenta": "#FF00FF",
    "purple": "#8B00FF",
    "pink": "#FF69B4",

    # Background gradients
    "bg_darkest": "#080116",
    "bg_dark": "#0D0221",
    "bg_medium": "#1A0533",
    "bg_light": "#2D0844",
    "bg_highlight": "#3D0066",

    # Text colors
    "text_bright": "#FFFFFF",
    "text_normal": "#E0E0FF",
    "text_dim": "#9999CC",
    "text_muted": "#666699",

    # Status/semantic colors
    "success": "#00FF00",
    "warning": "#FFFF00",
    "error": "#FF4444",
    "info": "#00FFFF",

    # Special accents
    "gold": "#FFD700",
    "silver": "#C0C0C0",
    "bronze": "#CD7F32",

    # Gradient stops (for reference)
    "gradient_start": "#FF00FF",
    "gradient_mid": "#8B00FF",
    "gradient_end": "#00FFFF",
}


# ASCII art color mappings
SYNTHWAVE_ASCII_COLORS = {
    "stars": "yellow",
    "moon": "yellow",
    "border": "magenta",
    "text": "cyan",
    "shadow": "purple",
    "highlight": "white",
}


def get_synthwave_color(name: str) -> str:
    """
    Get a synthwave palette color by name.

    Args:
        name: Color name from palette

    Returns:
        Hex color string
    """
    return SYNTHWAVE_PALETTE.get(name, "#FFFFFF")


def create_gradient_text(text: str, start_color: str = "magenta", end_color: str = "cyan") -> str:
    """
    Create a simple gradient text effect for Rich.

    Note: This is a simplified version - Rich doesn't support true gradients.
    This alternates colors for a gradient-like effect.

    Args:
        text: Text to colorize
        start_color: Starting color name
        end_color: Ending color name

    Returns:
        Rich markup string
    """
    if len(text) <= 1:
        return f"[{start_color}]{text}[/]"

    mid = len(text) // 2
    return f"[{start_color}]{text[:mid]}[/][{end_color}]{text[mid:]}[/]"
