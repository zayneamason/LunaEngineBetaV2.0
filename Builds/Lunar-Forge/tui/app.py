"""
Lunar Forge TUI — Main Application.

3-panel build command center with clickable UI, pipeline tracker,
action bar, and confirmation dialogs.
"""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import Optional, List

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer

from .panels.profiles import ProfilesPanel, ProfileSelected, ProfileBuildRequested
from .panels.build_log import BuildLogPanel, ActionBarPressed
from .panels.manifest import ManifestPanel
from .widgets.luna_orb import LunaOrbWidget
from .widgets.palette import ActionMenu, ConfirmDialog, NewProfileDialog
from .widgets.pipeline_tracker import PIPELINE_STAGES
from .themes import get_theme, THEME_NAMES, Theme
from ..core import BuildPipeline, detect_platform, list_profiles, load_profile


# Map core.py progress messages to pipeline stage keys
STAGE_KEYWORDS = {
    "staging": "staging",
    "frontend assets": "frontend",
    "config": "config",
    "data": "data",
    "secrets": "secrets",
    "frontend_config": "frontend_cfg",
    "nuitka": "nuitka",
    "post-process": "post_process",
    "output": "output",
    "moving": "output",
}


def _match_stage(message: str) -> Optional[str]:
    """Match a progress message to a pipeline stage key."""
    lower = message.lower()
    for keyword, stage in STAGE_KEYWORDS.items():
        if keyword in lower:
            return stage
    return None


class LunarForgeApp(App):
    """
    Lunar Forge Build System — Command Center.

    Layout:
    - Left: Profiles browser + Luna orb
    - Center: Action bar + Pipeline tracker + Build log
    - Right: Resolved manifest
    """

    CSS_PATH = "build.tcss"

    TITLE = "Lunar Forge"
    SUB_TITLE = "Luna Build System"

    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("slash", "open_menu", "Menu", key_display="/"),
        Binding("b", "build", "Build"),
        Binding("p", "preview", "Preview"),
        Binding("t", "cycle_theme", "Theme"),
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("f1", "help", "Help"),
    ]

    def __init__(self) -> None:
        self._current_theme_index: int = 0
        self._forge_theme: Theme = get_theme(THEME_NAMES[0])
        self._running_task: Optional[asyncio.Task] = None
        self._selected_profile: Optional[str] = None

        # Resolve forge root
        self._forge_root = Path(__file__).parent.parent
        self._profiles_dir = self._forge_root / "profiles"

        super().__init__()

    @property
    def forge_theme(self) -> Theme:
        return self._forge_theme

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Horizontal(id="main-container"):
            # Left panel — profiles + orb
            with Vertical(id="left-panel", classes="panel"):
                yield LunaOrbWidget(id="orb-widget")
                yield ProfilesPanel(
                    id="profiles-panel",
                    profiles_dir=self._profiles_dir,
                )

            # Center panel — action bar + build log
            with Vertical(id="center-panel", classes="panel"):
                yield BuildLogPanel(id="build-log-panel")

            # Right panel — manifest
            with Vertical(id="right-panel", classes="panel"):
                yield ManifestPanel(id="manifest-panel")

        yield Footer()

    def on_mount(self) -> None:
        self.dark = True
        self._log_startup()

    def _log_startup(self) -> None:
        log = self.query_one("#build-log-panel", BuildLogPanel)
        log.log_message("Lunar Forge initialized", level="info")
        log.log_message(f"Theme: {self._forge_theme.name}", level="debug")
        log.log_message(f"Profiles: {self._profiles_dir}", level="debug")
        log.log_message("Click a profile to select it, then hit Build.", level="info")

    # ------------------------------------------------------------------
    # Message handlers — clickable profiles
    # ------------------------------------------------------------------

    def on_profile_selected(self, event: ProfileSelected) -> None:
        """Handle profile click — select it."""
        self._selected_profile = event.name
        log = self.query_one("#build-log-panel", BuildLogPanel)
        log.log_message(f"Selected: [bold]{event.name}[/]", level="success")

        profiles_panel = self.query_one("#profiles-panel", ProfilesPanel)
        profiles_panel.select_profile(event.name)

        asyncio.create_task(self._refresh_manifest())

    def on_profile_build_requested(self, event: ProfileBuildRequested) -> None:
        """Handle profile Enter key — trigger build with confirmation."""
        self._selected_profile = event.name
        profiles_panel = self.query_one("#profiles-panel", ProfilesPanel)
        profiles_panel.select_profile(event.name)
        asyncio.create_task(self._refresh_manifest())
        self._confirm_and_build(event.name)

    # ------------------------------------------------------------------
    # Message handlers — action bar buttons
    # ------------------------------------------------------------------

    def on_action_bar_pressed(self, event: ActionBarPressed) -> None:
        action = event.action
        if action == "build":
            self.action_build()
        elif action == "preview":
            self.action_preview()
        elif action == "new":
            self._action_new_profile()
        elif action == "clean":
            self._action_clean()
        elif action == "more":
            self.action_open_menu()

    # ------------------------------------------------------------------
    # Build with confirmation + pipeline tracking
    # ------------------------------------------------------------------

    def _confirm_and_build(self, profile_name: str) -> None:
        """Show confirmation dialog then build."""
        self.push_screen(
            ConfirmDialog(
                title="Start Build",
                message=f"Build profile [bold cyan]{profile_name}[/] ?\n"
                        f"Platform: {detect_platform()}",
            ),
            lambda confirmed: (
                asyncio.create_task(self._run_build(profile_name))
                if confirmed else None
            ),
        )

    async def _run_build(self, profile_name: str) -> None:
        log = self.query_one("#build-log-panel", BuildLogPanel)
        orb = self.query_one("#orb-widget", LunaOrbWidget)
        tracker = log.get_pipeline_tracker()

        profile_path = self._profiles_dir / f"{profile_name}.yaml"
        if not profile_path.exists():
            log.log_message(f"Profile not found: {profile_name}", level="error")
            return

        # Show pipeline
        tracker.reset()
        tracker.show()

        log.log_message(f"=== BUILDING: {profile_name} ===", level="info")
        log.set_status("FORGING")
        orb.set_mode("phase")

        try:
            def on_progress(message: str, pct: int) -> None:
                # Update pipeline tracker based on message content
                stage = _match_stage(message)
                if stage:
                    tracker.set_stage(stage, "active")

                if pct >= 0:
                    log.update_progress(message, pct)
                else:
                    log.log_message(message, level="debug")

            pipeline = BuildPipeline(
                profile_path,
                forge_root=self._forge_root,
            )

            # Run build in thread to keep TUI responsive
            report = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: pipeline.build(on_progress=on_progress),
            )

            log.clear_progress()

            if report.status == "SUCCESS":
                tracker.complete_all()
                log.log_message("=== BUILD COMPLETE ===", level="success")
                log.log_message(
                    f"Output: {report.binary_path.parent if report.binary_path else 'N/A'}",
                    level="success",
                )
                log.log_message(
                    f"Binary: {report.binary_size/(1024*1024):.0f} MB | "
                    f"Total: {report.total_size/(1024*1024):.0f} MB | "
                    f"Files: {report.file_count}",
                    level="info",
                )
                log.set_status("READY")
                orb.set_mode("twinkle")
            else:
                tracker.fail_current()
                log.log_message("=== BUILD FAILED ===", level="error")
                for err in report.errors:
                    log.log_message(f"  {err}", level="error")
                log.set_status("ERROR")
                orb.set_mode("static")

        except Exception as e:
            tracker.fail_current()
            log.log_message(f"Build error: {e}", level="error")
            log.set_status("ERROR")
            orb.set_mode("static")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_open_menu(self) -> None:
        """Open the action menu (replaces old command palette)."""
        self.push_screen(ActionMenu(), self._on_menu_result)

    def _on_menu_result(self, result: Optional[str]) -> None:
        if not result:
            return

        handlers = {
            "build": self.action_build,
            "preview": self.action_preview,
            "profiles": self._action_list_profiles,
            "new": self._action_new_profile,
            "history": self._action_history,
            "clean": self._action_clean,
            "open": self._action_open,
            "refresh": lambda: asyncio.create_task(self._action_refresh()),
            "theme": self.action_cycle_theme,
            "clear": self._action_clear,
            "help": self.action_help,
        }

        handler = handlers.get(result)
        if handler:
            handler()

    def action_build(self) -> None:
        if not self._selected_profile:
            log = self.query_one("#build-log-panel", BuildLogPanel)
            log.log_message("No profile selected. Click one on the left.", level="warning")
            return
        self._confirm_and_build(self._selected_profile)

    def action_preview(self) -> None:
        log = self.query_one("#build-log-panel", BuildLogPanel)
        if not self._selected_profile:
            log.log_message("No profile selected.", level="warning")
            return

        profile_path = self._profiles_dir / f"{self._selected_profile}.yaml"
        if not profile_path.exists():
            log.log_message(f"Profile not found: {self._selected_profile}", level="error")
            return

        pipeline = BuildPipeline(profile_path, forge_root=self._forge_root)
        manifest = pipeline.preview()

        log.log_message(f"=== Preview: {manifest['profile']} ===", level="info")
        log.log_message(f"  Platform:  {manifest['platform']}", level="info")

        db = manifest["database"]
        log.log_message(f"  Database:  {db.get('mode', 'seed')}", level="info")

        for name, info in manifest.get("collections", {}).items():
            status = "\u2713" if info["enabled"] else "\u2717"
            size = f"{info['size']/(1024*1024):.1f} MB" if info["exists"] else "NOT FOUND"
            log.log_message(f"  {status} {name}: {size}", level="info")

        cfg = manifest["config"]
        log.log_message(f"  Patches:   {', '.join(cfg.get('personality_patches', []))}", level="debug")
        log.log_message(f"  Secrets:   {manifest.get('secrets_mode', 'template')}", level="debug")

    def _action_list_profiles(self) -> None:
        log = self.query_one("#build-log-panel", BuildLogPanel)
        profiles = list_profiles(self._profiles_dir)
        if not profiles:
            log.log_message("No profiles found.", level="warning")
            return
        for p in profiles:
            selected = " \u25b8" if p["file"].replace(".yaml", "") == self._selected_profile else "  "
            log.log_message(
                f"{selected} {p['name']:20s}  db:{p['database_mode']:5s}  "
                f"coll:{p['collections_count']}",
                level="info",
            )

    def _action_new_profile(self) -> None:
        profiles_panel = self.query_one("#profiles-panel", ProfilesPanel)
        bases = profiles_panel.get_profile_names()
        self.push_screen(
            NewProfileDialog(bases=bases),
            self._on_new_profile_result,
        )

    def _on_new_profile_result(self, name: Optional[str]) -> None:
        if not name:
            return

        log = self.query_one("#build-log-panel", BuildLogPanel)
        base = "luna-only"
        src = self._profiles_dir / f"{base}.yaml"
        dst = self._profiles_dir / f"{name}.yaml"

        if dst.exists():
            log.log_message(f"Profile already exists: {name}", level="error")
            return
        if not src.exists():
            log.log_message(f"Base profile not found: {base}", level="error")
            return

        shutil.copy2(str(src), str(dst))
        log.log_message(f"Created: {name}.yaml (from {base})", level="success")

        profiles_panel = self.query_one("#profiles-panel", ProfilesPanel)
        profiles_panel.refresh_data()

    def _action_history(self) -> None:
        log = self.query_one("#build-log-panel", BuildLogPanel)
        output_dir = self._forge_root / "output"
        if not output_dir.exists() or not list(output_dir.iterdir()):
            log.log_message("No builds found.", level="info")
            return

        for d in sorted(output_dir.iterdir()):
            if d.is_dir():
                report = d / "BUILD_REPORT.md"
                status = "\u2713" if report.exists() else "?"
                size_mb = sum(f.stat().st_size for f in d.rglob("*") if f.is_file()) / (1024 * 1024)
                log.log_message(f"  {status} {d.name}  ({size_mb:.0f} MB)", level="info")

    def _action_clean(self) -> None:
        log = self.query_one("#build-log-panel", BuildLogPanel)
        staging = self._forge_root / "staging"
        if staging.exists():
            shutil.rmtree(staging)
            log.log_message("Staging directory cleaned", level="success")
        else:
            log.log_message("Nothing to clean", level="info")

    def _action_open(self) -> None:
        log = self.query_one("#build-log-panel", BuildLogPanel)
        import subprocess
        output_dir = self._forge_root / "output"
        if output_dir.exists():
            subprocess.Popen(["open", str(output_dir)])
            log.log_message(f"Opened: {output_dir}", level="success")
        else:
            log.log_message("No output directory found", level="warning")

    async def _action_refresh(self) -> None:
        profiles_panel = self.query_one("#profiles-panel", ProfilesPanel)
        profiles_panel.refresh_data()
        await self._refresh_manifest()
        log = self.query_one("#build-log-panel", BuildLogPanel)
        log.log_message("Refreshed", level="debug")

    def _action_clear(self) -> None:
        log = self.query_one("#build-log-panel", BuildLogPanel)
        log.clear_log()
        log.log_message("Cleared", level="info")

    def action_cycle_theme(self) -> None:
        self._current_theme_index = (self._current_theme_index + 1) % len(THEME_NAMES)
        self._forge_theme = get_theme(THEME_NAMES[self._current_theme_index])
        log = self.query_one("#build-log-panel", BuildLogPanel)
        log.log_message(f"Theme: {self._forge_theme.name}", level="debug")

    def action_cancel(self) -> None:
        if self._running_task and not self._running_task.done():
            self._running_task.cancel()
            log = self.query_one("#build-log-panel", BuildLogPanel)
            log.log_message("Cancelled", level="warning")

    def action_help(self) -> None:
        log = self.query_one("#build-log-panel", BuildLogPanel)
        help_lines = [
            "",
            "[bold cyan]Keyboard Shortcuts[/]",
            "  [magenta]/[/]     Open action menu",
            "  [magenta]b[/]     Build selected profile",
            "  [magenta]p[/]     Preview config",
            "  [magenta]t[/]     Cycle theme",
            "  [magenta]q[/]     Quit",
            "  [magenta]F1[/]    This help",
            "",
            "[bold cyan]Mouse[/]",
            "  Click a profile to select it",
            "  Press Enter on a profile to build",
            "  Use the toolbar buttons at the top",
            "",
        ]
        for line in help_lines:
            log.log_message(line, level="info")

    # ------------------------------------------------------------------
    # Manifest refresh
    # ------------------------------------------------------------------

    async def _refresh_manifest(self) -> None:
        if not self._selected_profile:
            return
        manifest_panel = self.query_one("#manifest-panel", ManifestPanel)
        profile_path = self._profiles_dir / f"{self._selected_profile}.yaml"
        if profile_path.exists():
            pipeline = BuildPipeline(profile_path, forge_root=self._forge_root)
            manifest = pipeline.preview()
            manifest_panel.update_manifest(manifest)


if __name__ == "__main__":
    app = LunarForgeApp()
    app.run()
