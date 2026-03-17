"""Luna Orb Widget — Animated ASCII art for the build system."""

from __future__ import annotations

import random

from textual.widgets import Static
from textual.timer import Timer


# Orb frames — minimal Luna orb animation
ORB_FRAMES_TWINKLE = [
    r"""
       .  *  .
    .    ___    .
   *   /   \   *
      | (o) |
   .   \___/   .
    *    |    *
       . * .
""",
    r"""
    *  .     .  *
       .___. *
   .  /     \  .
      | {o} |
   *  \_____/  *
    .    |    .
      *  .  *
""",
    r"""
   .  *    *  .
      .___.
   * /     \ *
     | [o] |
   . \_____/ .
     *  |  *
    .  * .  .
""",
]

ORB_FRAMES_PHASE = [
    r"""
       ___
      /   \
     | .   |
      \___/
""",
    r"""
       ___
      /  .\
     | ..  |
      \___/
""",
    r"""
       ___
      /...\
     |.....|
      \___/
""",
    r"""
       ___
      /.  \
     |  .. |
      \___/
""",
]

ORB_STATIC = r"""
       ___
      /   \
     | (o) |
      \___/
"""


class LunaOrbWidget(Static):
    """Animated Luna orb — adapted from MoonWidget."""

    DEFAULT_CSS = """
    LunaOrbWidget {
        height: auto;
        min-height: 8;
        text-align: center;
        color: #FFFF00;
    }
    """

    def __init__(self, mode: str = "twinkle", **kwargs):
        super().__init__(**kwargs)
        self._mode = mode
        self._frame_index = 0
        self._timer: Timer | None = None
        self._animating = True

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def animating(self) -> bool:
        return self._animating

    def on_mount(self) -> None:
        self._start_animation()
        self._render_frame()

    def set_mode(self, mode: str) -> None:
        """Switch animation mode."""
        self._mode = mode
        self._frame_index = 0
        if mode == "static":
            self._animating = False
            if self._timer:
                self._timer.stop()
            self.update(ORB_STATIC)
        else:
            self._animating = True
            self._start_animation()

    def _start_animation(self) -> None:
        if self._timer:
            self._timer.stop()

        interval = 0.4 if self._mode == "twinkle" else 2.0
        self._timer = self.set_interval(interval, self._advance_frame)

    def _advance_frame(self) -> None:
        if not self._animating:
            return
        frames = ORB_FRAMES_TWINKLE if self._mode == "twinkle" else ORB_FRAMES_PHASE
        self._frame_index = (self._frame_index + 1) % len(frames)
        self._render_frame()

    def _render_frame(self) -> None:
        if self._mode == "static":
            self.update(ORB_STATIC)
            return

        frames = ORB_FRAMES_TWINKLE if self._mode == "twinkle" else ORB_FRAMES_PHASE
        frame = frames[self._frame_index % len(frames)]
        self.update(frame)

    def pulse(self) -> None:
        """Quick visual pulse."""
        self.update("[bold yellow]*** PULSE ***[/]")
        self.set_timer(0.5, self._render_frame)

    def toggle_animation(self) -> None:
        self._animating = not self._animating
        if self._animating:
            self._start_animation()
        elif self._timer:
            self._timer.stop()
