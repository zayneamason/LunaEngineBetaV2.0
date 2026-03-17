"""Build Log Panel — Center panel with log, pipeline tracker, and action bar."""

from __future__ import annotations

from datetime import datetime

from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Static, RichLog, ProgressBar, Button
from textual.app import ComposeResult
from textual.message import Message

from ..widgets.pipeline_tracker import PipelineTracker


LEVEL_STYLES = {
    "info": "cyan",
    "debug": "#666699",
    "warning": "yellow",
    "error": "bold red",
    "success": "green",
    "command": "bold magenta",
}


class ActionBarPressed(Message):
    """Posted when a toolbar button is pressed."""
    def __init__(self, action: str) -> None:
        self.action = action
        super().__init__()


class BuildLogPanel(Container):
    """Center panel — build output stream + pipeline tracker + action bar."""

    DEFAULT_CSS = """
    BuildLogPanel {
        height: 100%;
    }
    """

    def __init__(self, **kwargs):
        self._status = "READY"
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        # Action toolbar at the top
        with Horizontal(id="action-bar"):
            yield Button("\u25b6 Build", id="btn-build", variant="success")
            yield Button("\u25cb Preview", id="btn-preview", variant="primary")
            yield Button("+ New", id="btn-new", variant="default")
            yield Button("\u2716 Clean", id="btn-clean", variant="warning")
            yield Button("\u2261 More", id="btn-more", variant="default")

        yield Static("[bold magenta]BUILD LOG[/]", classes="build-log-title")

        # Pipeline tracker (hidden until build starts)
        yield PipelineTracker(id="pipeline-tracker")

        yield RichLog(id="log-output", highlight=True, markup=True, wrap=True, classes="build-log")
        yield ProgressBar(id="build-progress", total=100, show_eta=False, classes="progress-bar")

        with Vertical(classes="build-status"):
            yield Static("", id="status-display")

    def on_mount(self) -> None:
        progress = self.query_one("#build-progress", ProgressBar)
        progress.display = False
        self._update_status_display()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        action_map = {
            "btn-build": "build",
            "btn-preview": "preview",
            "btn-new": "new",
            "btn-clean": "clean",
            "btn-more": "more",
        }
        action = action_map.get(event.button.id, "")
        if action:
            self.post_message(ActionBarPressed(action))

    def log_message(self, message: str, level: str = "info") -> None:
        """Add a message to the log."""
        log = self.query_one("#log-output", RichLog)
        ts = datetime.now().strftime("%H:%M:%S")
        style = LEVEL_STYLES.get(level, "white")
        log.write(f"[dim]{ts}[/] [{style}]{message}[/]")

    def clear_log(self) -> None:
        """Clear the log output."""
        log = self.query_one("#log-output", RichLog)
        log.clear()

    def update_progress(self, message: str, pct: int) -> None:
        """Update progress bar."""
        progress = self.query_one("#build-progress", ProgressBar)
        progress.display = True
        progress.update(progress=pct)

        status = self.query_one("#status-display", Static)
        status.update(f"[cyan]{message}[/]  [magenta]{pct}%[/]")

    def clear_progress(self) -> None:
        """Hide progress bar."""
        progress = self.query_one("#build-progress", ProgressBar)
        progress.display = False
        self._update_status_display()

    def set_status(self, status: str) -> None:
        """Set build status (READY, FORGING, ERROR)."""
        self._status = status
        self._update_status_display()

    def get_pipeline_tracker(self) -> PipelineTracker:
        return self.query_one("#pipeline-tracker", PipelineTracker)

    def _update_status_display(self) -> None:
        colors = {
            "READY": "green",
            "FORGING": "magenta",
            "ERROR": "red",
            "LOADING": "cyan",
        }
        color = colors.get(self._status, "white")
        display = self.query_one("#status-display", Static)
        display.update(f"[bold cyan]Status:[/] [{color}]{self._status}[/]")
