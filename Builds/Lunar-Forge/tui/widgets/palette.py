"""Action Menu — Replaces raw command palette with labeled, navigable actions."""

from __future__ import annotations

from typing import Optional, List, Tuple

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option


# (command_string, display_label, description)
ACTIONS: List[Tuple[str, str, str]] = [
    ("build",     "Build",           "Run full build for selected profile"),
    ("preview",   "Preview",         "Dry-run — show resolved config"),
    ("profiles",  "List Profiles",   "Show all available profiles"),
    ("new",       "New Profile",     "Create profile from template"),
    ("history",   "Build History",   "View past builds"),
    ("clean",     "Clean Staging",   "Remove staging directory"),
    ("open",      "Open Output",     "Open build folder in Finder"),
    ("refresh",   "Refresh",         "Reload profiles and manifest"),
    ("theme",     "Cycle Theme",     "Switch visual theme"),
    ("clear",     "Clear Log",       "Clear the build log"),
    ("help",      "Help",            "Show keyboard shortcuts"),
]


class ActionMenu(ModalScreen[Optional[str]]):
    """Action menu modal — pick from labeled commands."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="palette-container"):
            yield Static("[bold cyan]Actions[/]", id="palette-title")
            options = []
            for cmd, label, desc in ACTIONS:
                options.append(Option(f"[bold]{label}[/]  [dim]{desc}[/]", id=cmd))
            yield OptionList(*options, id="action-list")

    def on_mount(self) -> None:
        self.query_one("#action-list", OptionList).focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        cmd = event.option.id
        if cmd:
            self.dismiss(cmd)

    def action_cancel(self) -> None:
        self.dismiss(None)


class ConfirmDialog(ModalScreen[bool]):
    """Simple yes/no confirmation dialog."""

    BINDINGS = [
        Binding("y", "confirm", "Yes"),
        Binding("n", "cancel", "No"),
        Binding("enter", "confirm", "Confirm"),
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, title: str, message: str, **kwargs):
        super().__init__(**kwargs)
        self._title = title
        self._message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-container"):
            yield Static(f"[bold cyan]{self._title}[/]", id="confirm-title")
            yield Static(f"\n{self._message}\n", id="confirm-message")
            yield Static(
                "[bold green][ Y ] Yes[/]    [bold red][ N ] No[/]    [dim]Enter=Yes  Esc=No[/]",
                id="confirm-buttons",
            )

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)


class NewProfileDialog(ModalScreen[Optional[str]]):
    """Dialog to create a new profile — type a name."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, bases: List[str], **kwargs):
        super().__init__(**kwargs)
        self._bases = bases

    def compose(self) -> ComposeResult:
        from textual.widgets import Input

        with Vertical(id="new-profile-container"):
            yield Static("[bold cyan]New Profile[/]", id="new-profile-title")
            yield Static("[dim]Enter a name for the new profile:[/]")
            yield Input(placeholder="my-profile", id="new-profile-input")
            yield Static(f"\n[dim]Template: luna-only  |  Available: {', '.join(self._bases)}[/]")

    def on_mount(self) -> None:
        from textual.widgets import Input
        self.query_one("#new-profile-input", Input).focus()

    def on_input_submitted(self, event) -> None:
        value = event.value.strip()
        if value:
            self.dismiss(value)
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)
