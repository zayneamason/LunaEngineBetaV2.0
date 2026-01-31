"""
Command Palette - Command Input with History.

A modal screen for entering commands with history support.
"""

from __future__ import annotations

from typing import List, Optional

from textual import on
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.containers import Container, Vertical, VerticalScroll
from textual.widgets import Static, Input, Label
from textual.binding import Binding


class HistoryItem(Static):
    """A clickable history item."""

    def __init__(self, command: str, index: int, **kwargs) -> None:
        super().__init__(**kwargs)
        self.command = command
        self.index = index

    def render(self) -> str:
        return f"[dim]{self.index}.[/] {self.command}"

    def on_click(self) -> None:
        """Handle click to select this command."""
        self.screen.select_history(self.command)


class CommandPalette(ModalScreen[Optional[str]]):
    """
    Command palette modal screen.

    Features:
    - Text input for commands
    - Command history list
    - Keyboard navigation
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "submit", "Execute", show=False),
        Binding("up", "history_up", "Previous", show=False),
        Binding("down", "history_down", "Next", show=False),
    ]

    def __init__(self, history: Optional[List[str]] = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._history = list(reversed(history or []))[:10]  # Keep last 10, newest first
        self._history_index = -1

    def compose(self) -> ComposeResult:
        with Container(id="palette-container"):
            yield Static("[ COMMAND PALETTE ]", id="palette-title")
            yield Input(
                placeholder="Enter command...",
                id="palette-input"
            )

            if self._history:
                yield Static("[dim]Recent commands:[/]", id="history-label")
                with VerticalScroll(id="palette-history"):
                    for i, cmd in enumerate(self._history):
                        yield HistoryItem(cmd, i + 1, classes="history-item")
            else:
                yield Static("[dim]No command history[/]", id="history-empty")

    def on_mount(self) -> None:
        """Focus the input on mount."""
        self.query_one("#palette-input", Input).focus()

    @on(Input.Submitted, "#palette-input")
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        command = event.value.strip()
        if command:
            self.dismiss(command)
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        """Cancel and close."""
        self.dismiss(None)

    def action_submit(self) -> None:
        """Submit the current input."""
        input_widget = self.query_one("#palette-input", Input)
        command = input_widget.value.strip()
        if command:
            self.dismiss(command)

    def action_history_up(self) -> None:
        """Navigate up in history."""
        if not self._history:
            return

        self._history_index = min(self._history_index + 1, len(self._history) - 1)
        self._set_input_from_history()

    def action_history_down(self) -> None:
        """Navigate down in history."""
        if not self._history:
            return

        self._history_index = max(self._history_index - 1, -1)
        self._set_input_from_history()

    def _set_input_from_history(self) -> None:
        """Set input value from history."""
        input_widget = self.query_one("#palette-input", Input)

        if self._history_index >= 0 and self._history_index < len(self._history):
            input_widget.value = self._history[self._history_index]
            input_widget.cursor_position = len(input_widget.value)
        else:
            input_widget.value = ""

    def select_history(self, command: str) -> None:
        """Select a command from history."""
        self.dismiss(command)
