"""Profiles Panel — Left panel with clickable profile cards."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml

from textual.containers import Container, VerticalScroll
from textual.widgets import Static
from textual.app import ComposeResult
from textual.message import Message


class ProfileSelected(Message):
    """Posted when a profile is clicked."""
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__()


class ProfileBuildRequested(Message):
    """Posted when a profile is double-clicked or Enter is pressed."""
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__()


class ProfileItem(Static, can_focus=True):
    """A single clickable profile entry."""

    BINDINGS = [
        ("enter", "activate", "Build"),
    ]

    def __init__(self, name: str, description: str, db_mode: str, coll_count: int, **kwargs):
        self.profile_name = name
        self.profile_desc = description
        self.db_mode = db_mode
        self.coll_count = coll_count
        super().__init__(**kwargs)

    def render(self) -> str:
        return (
            f"[bold cyan]{self.profile_name}[/]\n"
            f"[italic #666699]{self.profile_desc}[/]\n"
            f"[#FF00FF]db: {self.db_mode} | coll: {self.coll_count}[/]"
        )

    def on_click(self) -> None:
        self.post_message(ProfileSelected(self.profile_name))

    def action_activate(self) -> None:
        self.post_message(ProfileBuildRequested(self.profile_name))


class ProfilesPanel(Container):
    """Left panel — clickable profile browser."""

    DEFAULT_CSS = """
    ProfilesPanel {
        height: 100%;
    }
    """

    def __init__(self, profiles_dir: Path, **kwargs):
        self._profiles_dir = profiles_dir
        self._selected: Optional[str] = None
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        yield Static("[bold cyan]PROFILES[/]\n[dim]Click to select \u2022 Enter to build[/]", classes="profiles-title")
        yield VerticalScroll(id="profile-list")
        yield Static("", id="platform-display", classes="platform-box")

    def on_mount(self) -> None:
        self.refresh_data()
        self._update_platform()

    def refresh_data(self) -> None:
        """Reload profiles from disk."""
        container = self.query_one("#profile-list", VerticalScroll)
        container.remove_children()

        if not self._profiles_dir.exists():
            container.mount(Static("[warning]No profiles directory[/]"))
            return

        for path in sorted(self._profiles_dir.glob("*.yaml")):
            try:
                with open(path) as f:
                    raw = yaml.safe_load(f) or {}
                name = path.stem
                desc = raw.get("description", "")
                db_mode = raw.get("database", {}).get("mode", "seed")
                coll_count = sum(
                    1 for c in raw.get("collections", {}).values()
                    if isinstance(c, dict) and c.get("enabled", False)
                )

                item = ProfileItem(
                    name=name,
                    description=desc,
                    db_mode=db_mode,
                    coll_count=coll_count,
                    classes="profile-item" + (" selected" if name == self._selected else ""),
                )
                container.mount(item)

            except Exception:
                container.mount(Static(f"[error]{path.name}: parse error[/]"))

    def select_profile(self, name: str) -> None:
        """Select a profile by name."""
        self._selected = name
        self.refresh_data()

    def get_profile_names(self) -> list[str]:
        """Return list of available profile names."""
        if not self._profiles_dir.exists():
            return []
        return [p.stem for p in sorted(self._profiles_dir.glob("*.yaml"))]

    def _update_platform(self) -> None:
        """Show detected platform."""
        try:
            from ...core import detect_platform
            plat = detect_platform()
        except Exception:
            import platform as _p
            plat = f"{_p.system()}-{_p.machine()}"

        display = self.query_one("#platform-display", Static)
        display.update(
            f"[bold #666699]PLATFORM[/]\n"
            f"[cyan]{plat}[/] [#666699](detected)[/]"
        )
