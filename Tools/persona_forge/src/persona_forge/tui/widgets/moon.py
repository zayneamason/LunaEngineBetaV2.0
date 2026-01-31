"""
Moon Widget - Luna's Animated Moon ASCII Art.

Displays Luna's moon with animated phase cycles and twinkling stars.
"""

from __future__ import annotations

from typing import List
import asyncio
import random

from textual.widgets import Static
from textual.reactive import reactive


# Animated moon frames with twinkling stars
MOON_FRAMES: List[str] = [
    # Frame 0: Stars bright, full glow
    """
      [bold yellow]★[/]    [bold cyan]✦[/]
        [yellow]🌙[/]
     .-'```'-.
    /  [magenta]◦[/]   [magenta]◦[/]  \\
   |    [dim]~~~[/]    |
   |  [bold magenta]LUNA[/]   |
    \\  [magenta]'...'[/]  /
     '-.___.-'
   [bold magenta]✧[/]   [bold cyan]✦[/]   [bold yellow]★[/]
""",
    # Frame 1: Stars dim, soft glow
    """
      [dim]★[/]    [cyan]✦[/]
        [yellow]🌙[/]
     .-'```'-.
    /  [dim]◦   ◦[/]  \\
   |    [dim]~~~[/]    |
   |  [magenta]LUNA[/]   |
    \\  [dim]'...'[/]  /
     '-.___.-'
   [magenta]✧[/]   [dim]✦[/]   [dim]★[/]
""",
    # Frame 2: Stars twinkle pattern A
    """
      [yellow]★[/]    [dim]✦[/]
        [yellow]🌙[/]
     .-'```'-.
    /  [magenta]◦[/]   [dim]◦[/]  \\
   |    [magenta]~~~[/]    |
   |  [bold magenta]LUNA[/]   |
    \\  [magenta]'...'[/]  /
     '-.___.-'
   [dim]✧[/]   [bold cyan]✦[/]   [yellow]★[/]
""",
    # Frame 3: Stars twinkle pattern B
    """
      [dim]★[/]    [bold cyan]✦[/]
        [yellow]🌙[/]
     .-'```'-.
    /  [dim]◦[/]   [magenta]◦[/]  \\
   |    [dim]~~~[/]    |
   |  [magenta]LUNA[/]   |
    \\  [dim]'...'[/]  /
     '-.___.-'
   [bold magenta]✧[/]   [dim]✦[/]   [dim]★[/]
""",
    # Frame 4: Pulse bright
    """
      [bold yellow]★[/]    [bold cyan]✦[/]
        [bold yellow]🌙[/]
     .-'```'-.
    /  [bold magenta]◦   ◦[/]  \\
   |    [bold magenta]~~~[/]    |
   |  [bold white]LUNA[/]   |
    \\  [bold magenta]'...'[/]  /
     '-.___.-'
   [bold magenta]✧[/]   [bold cyan]✦[/]   [bold yellow]★[/]
""",
    # Frame 5: Back to soft
    """
      [yellow]★[/]    [cyan]✦[/]
        [yellow]🌙[/]
     .-'```'-.
    /  [magenta]◦[/]   [magenta]◦[/]  \\
   |    [magenta]~~~[/]    |
   |  [magenta]LUNA[/]   |
    \\  [magenta]'...'[/]  /
     '-.___.-'
   [magenta]✧[/]   [cyan]✦[/]   [yellow]★[/]
""",
]

# Moon phase cycle (slower, for phase command)
MOON_PHASES: List[str] = [
    # New Moon
    """
      [dim].[/]    [dim].[/]
        [dim]🌑[/]
     .-'   '-.
    /         \\
   |           |
   |  [dim]LUNA[/]   |
    \\         /
     '-.___.-'
   [dim].[/]   [dim].[/]   [dim].[/]
""",
    # Waxing Crescent
    """
      [dim]★[/]    [dim]✦[/]
        [yellow]🌒[/]
     .-'   '-.
    /    [dim])[/]    \\
   |     [dim])[/]     |
   |  [magenta]LUNA[/]   |
    \\    [dim])[/]    /
     '-.___.-'
   [dim]✧[/]   [cyan]✦[/]   [dim]★[/]
""",
    # First Quarter
    """
      [yellow]★[/]    [cyan]✦[/]
        [yellow]🌓[/]
     .-'   '-.
    /   [white]▐[/]    \\
   |    [white]▐[/]     |
   |  [magenta]LUNA[/]   |
    \\   [white]▐[/]    /
     '-.___.-'
   [magenta]✧[/]   [cyan]✦[/]   [yellow]★[/]
""",
    # Waxing Gibbous
    """
      [bold yellow]★[/]    [bold cyan]✦[/]
        [yellow]🌔[/]
     .-'```'-.
    /  [white]▐██[/]   \\
   |   [white]▐██[/]    |
   |  [magenta]LUNA[/]   |
    \\  [white]▐██[/]   /
     '-.___.-'
   [bold magenta]✧[/]   [cyan]✦[/]   [bold yellow]★[/]
""",
    # Full Moon
    """
      [bold yellow]★[/]    [bold cyan]✦[/]
        [bold yellow]🌕[/]
     .-'```'-.
    / [white]██████[/] \\
   |  [white]██████[/]  |
   |  [bold white]LUNA[/]   |
    \\ [white]██████[/] /
     '-.___.-'
   [bold magenta]✧[/]   [bold cyan]✦[/]   [bold yellow]★[/]
""",
    # Waning Gibbous
    """
      [bold yellow]★[/]    [bold cyan]✦[/]
        [yellow]🌖[/]
     .-'```'-.
    /   [white]██▌[/]  \\
   |    [white]██▌[/]   |
   |  [magenta]LUNA[/]   |
    \\   [white]██▌[/]  /
     '-.___.-'
   [bold magenta]✧[/]   [cyan]✦[/]   [bold yellow]★[/]
""",
    # Last Quarter
    """
      [yellow]★[/]    [cyan]✦[/]
        [yellow]🌗[/]
     .-'   '-.
    /    [white]▌[/]   \\
   |     [white]▌[/]    |
   |  [magenta]LUNA[/]   |
    \\    [white]▌[/]   /
     '-.___.-'
   [magenta]✧[/]   [cyan]✦[/]   [yellow]★[/]
""",
    # Waning Crescent
    """
      [dim]★[/]    [dim]✦[/]
        [yellow]🌘[/]
     .-'   '-.
    /    [dim]([/]    \\
   |     [dim]([/]     |
   |  [dim magenta]LUNA[/]   |
    \\    [dim]([/]    /
     '-.___.-'
   [dim]✧[/]   [dim]✦[/]   [dim]★[/]
""",
]

# Simplified static moon for default display
LUNA_MOON = """
      [yellow]★[/]    [cyan]✦[/]
        [yellow]🌙[/]
     .-'```'-.
    /  [magenta]◦   ◦[/]  \\
   |    [magenta]~~~[/]    |
   |  [bold magenta]LUNA[/]   |
    \\  [magenta]'...'[/]  /
     '-.___.-'
   [magenta]✧[/]   [cyan]✦[/]   [yellow]★[/]
"""

# Alternative minimal ASCII (no emoji, for basic terminals)
LUNA_MOON_ASCII = """
       *  +
        ))
     .-'``'-.
    /  o   o  \\
   |    ~~~    |
   |   LUNA   |
    \\  '...'  /
     '-.___.-'
     *   +   *
"""


class MoonWidget(Static):
    """
    Luna's moon ASCII art widget with animations.

    Features:
    - Twinkling star animation (fast, default)
    - Moon phase cycle animation (slow)
    - Manual phase control
    - Synthwave color scheme
    """

    frame: reactive[int] = reactive(0)
    phase: reactive[int] = reactive(4)  # Start at full moon
    animating: reactive[bool] = reactive(False)
    mode: reactive[str] = reactive("twinkle")  # "twinkle", "phase", or "static"

    def __init__(self, animated: bool = True, mode: str = "twinkle", **kwargs) -> None:
        """
        Initialize the moon widget.

        Args:
            animated: Whether to animate (default True)
            mode: Animation mode - "twinkle" (fast stars), "phase" (moon cycle), "static"
        """
        super().__init__(**kwargs)
        self._animated = animated
        self.mode = mode
        self._animation_task = None

    def on_mount(self) -> None:
        """Start animation on mount."""
        if self._animated and self.mode != "static":
            self.start_animation()

    def render(self) -> str:
        """Render the current moon frame."""
        if self.mode == "twinkle" and self.animating:
            return MOON_FRAMES[self.frame % len(MOON_FRAMES)]
        elif self.mode == "phase":
            return MOON_PHASES[self.phase % len(MOON_PHASES)]
        return LUNA_MOON

    def start_animation(self) -> None:
        """Start the animation loop using Textual's timer."""
        if not self.animating:
            self.animating = True
            self._schedule_next_frame()

    def _schedule_next_frame(self) -> None:
        """Schedule the next animation frame."""
        if not self.animating:
            return

        if self.mode == "twinkle":
            # Fast twinkling stars (0.3-0.5s random interval)
            delay = 0.3 + random.random() * 0.2
            self.set_timer(delay, self._advance_frame)
        elif self.mode == "phase":
            # Slow moon phase cycle (5s per phase)
            self.set_timer(5.0, self._advance_frame)

    def _advance_frame(self) -> None:
        """Advance to next animation frame."""
        if not self.animating:
            return

        if self.mode == "twinkle":
            self.frame = (self.frame + 1) % len(MOON_FRAMES)
        elif self.mode == "phase":
            self.phase = (self.phase + 1) % len(MOON_PHASES)

        # Schedule next frame
        self._schedule_next_frame()

    def stop_animation(self) -> None:
        """Stop the animation."""
        self.animating = False

    def set_mode(self, mode: str) -> None:
        """
        Change animation mode.

        Args:
            mode: "twinkle", "phase", or "static"
        """
        was_animating = self.animating
        if was_animating:
            self.stop_animation()

        self.mode = mode

        if was_animating and mode != "static":
            self.start_animation()

        self.refresh()

    def set_phase(self, phase: int) -> None:
        """
        Set a specific moon phase (0-7).

        Args:
            phase: Phase index (0=new, 4=full, etc.)
        """
        self.phase = phase % len(MOON_PHASES)
        if self.mode == "phase":
            self.refresh()

    def toggle_animation(self) -> None:
        """Toggle animation on/off."""
        if self.animating:
            self.stop_animation()
        else:
            self.start_animation()

    def pulse(self) -> None:
        """Trigger a bright pulse effect."""
        # Jump to the bright frame
        self.frame = 4
        self.refresh()
