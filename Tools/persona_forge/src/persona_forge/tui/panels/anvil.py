"""
Anvil Panel - Command Output and Pipeline Progress.

The center panel showing command output, logs, and operation status.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import Static, ProgressBar, RichLog
from textual.reactive import reactive


@dataclass
class LogEntry:
    """A log message entry."""
    timestamp: datetime
    message: str
    level: str  # info, debug, warning, error, success, command


class AnvilPanel(Container):
    """
    The Anvil Panel - Command output and progress.

    Shows:
    - Command execution log
    - Pipeline progress bar
    - Current operation status
    """

    status: reactive[str] = reactive("READY")
    progress_text: reactive[str] = reactive("")
    progress_value: reactive[float] = reactive(0.0)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._log_entries: List[LogEntry] = []

    def compose(self) -> ComposeResult:
        yield Static("[ ANVIL ]", classes="anvil-title")

        yield RichLog(
            highlight=True,
            markup=True,
            wrap=True,
            id="anvil-log",
            classes="anvil-log"
        )

        with Container(classes="anvil-status"):
            yield Static("", id="progress-text")
            yield ProgressBar(id="progress-bar", show_eta=False, show_percentage=True)
            yield Static("", id="status-display")

    def on_mount(self) -> None:
        """Initialize on mount."""
        self._update_status_display()
        progress_bar = self.query_one("#progress-bar", ProgressBar)
        progress_bar.display = False

    def watch_status(self, status: str) -> None:
        """React to status changes."""
        self._update_status_display()

    def _update_status_display(self) -> None:
        """Update the status display."""
        status_display = self.query_one("#status-display", Static)

        color_map = {
            "READY": "green",
            "FORGING": "magenta",
            "LOADING": "cyan",
            "ERROR": "red",
            "PAUSED": "yellow",
        }
        color = color_map.get(self.status, "white")
        status_display.update(f"Status: [{color}]{self.status}[/]")

    def log_message(self, message: str, level: str = "info") -> None:
        """
        Add a message to the log.

        Args:
            message: The message text
            level: Message level (info, debug, warning, error, success, command)
        """
        entry = LogEntry(
            timestamp=datetime.now(),
            message=message,
            level=level
        )
        self._log_entries.append(entry)

        log = self.query_one("#anvil-log", RichLog)

        # Color coding by level
        color_map = {
            "info": "cyan",
            "debug": "dim",
            "warning": "yellow",
            "error": "red bold",
            "success": "green",
            "command": "magenta bold",
        }
        color = color_map.get(level, "white")

        timestamp = entry.timestamp.strftime("%H:%M:%S")
        log.write(f"[dim]{timestamp}[/] [{color}]{message}[/]")

    def clear_log(self) -> None:
        """Clear the log output."""
        log = self.query_one("#anvil-log", RichLog)
        log.clear()
        self._log_entries.clear()

    def update_progress(self, text: str, value: int) -> None:
        """
        Update the progress bar.

        Args:
            text: Progress description text
            value: Progress percentage (0-100)
        """
        progress_text = self.query_one("#progress-text", Static)
        progress_bar = self.query_one("#progress-bar", ProgressBar)

        progress_text.update(f"[cyan]{text}[/]")
        progress_bar.display = True
        progress_bar.update(total=100, progress=value)

    def clear_progress(self) -> None:
        """Hide the progress bar."""
        progress_text = self.query_one("#progress-text", Static)
        progress_bar = self.query_one("#progress-bar", ProgressBar)

        progress_text.update("")
        progress_bar.display = False

    def set_status(self, status: str) -> None:
        """
        Set the current operation status.

        Args:
            status: Status string (READY, FORGING, LOADING, ERROR, PAUSED)
        """
        self.status = status

    def get_log_entries(self) -> List[LogEntry]:
        """Get all log entries."""
        return self._log_entries.copy()

    def get_entries_by_level(self, level: str) -> List[LogEntry]:
        """Get log entries filtered by level."""
        return [e for e in self._log_entries if e.level == level]
