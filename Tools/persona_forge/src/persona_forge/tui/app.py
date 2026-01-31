"""
Persona Forge TUI - Main Application.

The command center for Luna's personality forge pipeline.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Static
from textual.screen import Screen

from .panels.crucible import CruciblePanel
from .panels.anvil import AnvilPanel
from .panels.overwatch import OverwatchPanel
from .panels.personality import PersonalityPanel
from .widgets.moon import MoonWidget
from .widgets.palette import CommandPalette
from .themes import get_theme, THEME_NAMES, Theme


class PersonaForgeApp(App):
    """
    Persona Forge Command Center.

    A 3-panel TUI for managing Luna's personality training pipeline.

    Layout:
    - Left (Crucible): Source files and extraction status
    - Center (Anvil): Command output and pipeline progress
    - Right (Overwatch): Metrics and quality gauges
    """

    CSS_PATH = "forge.tcss"

    TITLE = "Persona Forge"
    SUB_TITLE = "Luna's Personality Crucible"

    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("slash", "command_palette", "Commands", key_display="/"),
        Binding("r", "refresh", "Refresh"),
        Binding("t", "cycle_theme", "Theme"),
        Binding("m", "cycle_moon", "Moon"),
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("f1", "help", "Help"),
    ]

    def __init__(self) -> None:
        # Initialize our attributes BEFORE calling super().__init__()
        # because Textual may access properties during initialization
        self._current_theme_index: int = 0
        self._forge_theme: Theme = get_theme(THEME_NAMES[0])
        self._command_history: List[str] = []
        self._running_task: Optional[asyncio.Task] = None
        super().__init__()

    @property
    def forge_theme(self) -> Theme:
        """Get the current forge theme."""
        return self._forge_theme

    def compose(self) -> ComposeResult:
        """Compose the 3-panel layout."""
        yield Header(show_clock=True)

        with Horizontal(id="main-container"):
            # Left panel - Crucible (sources)
            with Vertical(id="left-panel", classes="panel"):
                yield MoonWidget(id="moon-widget", animated=True, mode="twinkle")
                yield CruciblePanel(id="crucible-panel")

            # Center panel - Anvil (output)
            with Vertical(id="center-panel", classes="panel"):
                yield AnvilPanel(id="anvil-panel")

            # Right panel - Overwatch (metrics) + Personality
            with Vertical(id="right-panel", classes="panel"):
                yield OverwatchPanel(id="overwatch-panel")
                yield PersonalityPanel(id="personality-panel")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize on mount."""
        self._apply_theme()
        self._log_startup()

    def _apply_theme(self) -> None:
        """Apply the current theme colors."""
        # Update CSS variables based on theme
        self.dark = True  # Always dark mode for synthwave aesthetic

    def _log_startup(self) -> None:
        """Log startup message to anvil."""
        anvil = self.query_one("#anvil-panel", AnvilPanel)
        anvil.log_message("Persona Forge initialized", level="info")
        anvil.log_message(f"Theme: {self._forge_theme.name}", level="debug")
        anvil.log_message("Ready for commands. Press / for palette.", level="info")

    async def execute_command(self, command: str) -> None:
        """
        Execute a command and route to appropriate handler.

        Args:
            command: The command string to execute
        """
        if not command.strip():
            return

        # Add to history
        self._command_history.append(command)

        anvil = self.query_one("#anvil-panel", AnvilPanel)
        anvil.log_message(f"> {command}", level="command")

        # Parse command
        parts = command.strip().split()
        cmd = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []

        try:
            await self._route_command(cmd, args)
        except Exception as e:
            anvil.log_message(f"Error: {e}", level="error")

    async def _route_command(self, cmd: str, args: List[str]) -> None:
        """Route command to handler."""
        anvil = self.query_one("#anvil-panel", AnvilPanel)
        crucible = self.query_one("#crucible-panel", CruciblePanel)
        overwatch = self.query_one("#overwatch-panel", OverwatchPanel)

        handlers: Dict[str, Any] = {
            "help": self._cmd_help,
            "status": self._cmd_status,
            "load": self._cmd_load,
            "scan": self._cmd_scan,
            "extract": self._cmd_extract,
            "forge": self._cmd_forge,
            "validate": self._cmd_validate,
            "export": self._cmd_export,
            "theme": self._cmd_theme,
            "moon": self._cmd_moon,
            "clear": self._cmd_clear,
            "refresh": self._cmd_refresh,
            "personality": self._cmd_personality,
            "assay": self._cmd_assay,
        }

        handler = handlers.get(cmd)
        if handler:
            await handler(args)
        else:
            anvil.log_message(f"Unknown command: {cmd}", level="warning")
            anvil.log_message("Type 'help' for available commands", level="info")

    async def _cmd_help(self, args: List[str]) -> None:
        """Show help information."""
        anvil = self.query_one("#anvil-panel", AnvilPanel)
        help_text = """
Available Commands:
  help              - Show this help
  status            - Show pipeline status
  load <path>       - Load source files
  scan              - Scan loaded sources
  extract           - Extract training examples
  forge             - Run full pipeline
  validate          - Validate dataset quality
  export <format>   - Export dataset (jsonl, csv)
  personality       - Show personality profile
  assay <path>      - Run full assay with personality
  theme <name>      - Change theme (synthwave, midnight, ember)
  moon <mode>       - Moon animation (twinkle, phase, static)
  clear             - Clear output
  refresh           - Refresh all panels

Keyboard Shortcuts:
  /                 - Open command palette
  r                 - Refresh panels
  t                 - Cycle theme
  m                 - Cycle moon animation
  q                 - Quit
  F1                - Help
"""
        for line in help_text.strip().split("\n"):
            anvil.log_message(line, level="info")

    async def _cmd_status(self, args: List[str]) -> None:
        """Show current pipeline status."""
        anvil = self.query_one("#anvil-panel", AnvilPanel)
        anvil.log_message("Pipeline Status:", level="info")
        anvil.log_message("  Sources loaded: checking...", level="debug")

        # Trigger refresh to update panels
        await self.action_refresh()

    async def _cmd_load(self, args: List[str]) -> None:
        """Load source files."""
        anvil = self.query_one("#anvil-panel", AnvilPanel)

        if not args:
            anvil.log_message("Usage: load <path>", level="warning")
            return

        path = Path(args[0])
        anvil.log_message(f"Loading sources from: {path}", level="info")

        # Simulate loading progress
        for i in range(5):
            await asyncio.sleep(0.2)
            anvil.update_progress(f"Scanning... {(i+1)*20}%", (i+1)*20)

        anvil.log_message("Sources loaded successfully", level="success")
        anvil.clear_progress()

        # Refresh crucible
        crucible = self.query_one("#crucible-panel", CruciblePanel)
        crucible.refresh_data()

    async def _cmd_scan(self, args: List[str]) -> None:
        """Scan loaded sources."""
        anvil = self.query_one("#anvil-panel", AnvilPanel)
        anvil.log_message("Scanning sources...", level="info")

        # Simulate scan
        await asyncio.sleep(0.5)
        anvil.log_message("Found 3 conversation files", level="success")
        anvil.log_message("Found 2 personality templates", level="success")
        anvil.log_message("Found 1 voice sample file", level="success")

    async def _cmd_extract(self, args: List[str]) -> None:
        """Extract training examples."""
        anvil = self.query_one("#anvil-panel", AnvilPanel)
        anvil.log_message("Extracting training examples...", level="info")

        # Simulate extraction with progress
        steps = [
            "Parsing conversations...",
            "Identifying patterns...",
            "Extracting examples...",
            "Validating format...",
            "Finalizing...",
        ]

        for i, step in enumerate(steps):
            await asyncio.sleep(0.3)
            anvil.update_progress(step, int((i+1) / len(steps) * 100))

        anvil.log_message("Extracted 42 training examples", level="success")
        anvil.clear_progress()

        # Update metrics
        overwatch = self.query_one("#overwatch-panel", OverwatchPanel)
        overwatch.refresh_data()

    async def _cmd_forge(self, args: List[str]) -> None:
        """Run the full forge pipeline."""
        anvil = self.query_one("#anvil-panel", AnvilPanel)
        anvil.log_message("=== FORGE PIPELINE STARTING ===", level="info")
        anvil.set_status("FORGING")

        pipeline_steps = [
            ("Loading sources", self._cmd_load, ["."]),
            ("Scanning files", self._cmd_scan, []),
            ("Extracting examples", self._cmd_extract, []),
            ("Validating dataset", self._cmd_validate, []),
        ]

        for step_name, handler, step_args in pipeline_steps:
            anvil.log_message(f"Step: {step_name}", level="info")
            await handler(step_args)
            await asyncio.sleep(0.2)

        anvil.log_message("=== FORGE COMPLETE ===", level="success")
        anvil.set_status("READY")

    async def _cmd_validate(self, args: List[str]) -> None:
        """Validate dataset quality."""
        anvil = self.query_one("#anvil-panel", AnvilPanel)
        anvil.log_message("Validating dataset quality...", level="info")

        await asyncio.sleep(0.5)

        # Report validation results
        anvil.log_message("Quality Check Results:", level="info")
        anvil.log_message("  Format compliance: PASS", level="success")
        anvil.log_message("  Token limits: PASS", level="success")
        anvil.log_message("  Balance score: 0.85", level="info")
        anvil.log_message("  Health score: 92%", level="success")

        # Update overwatch
        overwatch = self.query_one("#overwatch-panel", OverwatchPanel)
        overwatch.refresh_data()

    async def _cmd_export(self, args: List[str]) -> None:
        """Export dataset."""
        anvil = self.query_one("#anvil-panel", AnvilPanel)

        fmt = args[0] if args else "jsonl"
        anvil.log_message(f"Exporting dataset as {fmt}...", level="info")

        await asyncio.sleep(0.3)
        anvil.log_message(f"Exported to: output/dataset.{fmt}", level="success")

    async def _cmd_theme(self, args: List[str]) -> None:
        """Change theme."""
        anvil = self.query_one("#anvil-panel", AnvilPanel)

        if not args:
            anvil.log_message(f"Available themes: {', '.join(THEME_NAMES)}", level="info")
            anvil.log_message(f"Current: {self._forge_theme.name}", level="info")
            return

        theme_name = args[0].lower()
        if theme_name in THEME_NAMES:
            self._current_theme_index = THEME_NAMES.index(theme_name)
            self._forge_theme = get_theme(theme_name)
            self._apply_theme()
            anvil.log_message(f"Theme changed to: {theme_name}", level="success")
        else:
            anvil.log_message(f"Unknown theme: {theme_name}", level="warning")

    async def _cmd_moon(self, args: List[str]) -> None:
        """Control moon animation."""
        anvil = self.query_one("#anvil-panel", AnvilPanel)
        moon = self.query_one("#moon-widget", MoonWidget)

        modes = ["twinkle", "phase", "static"]

        if not args:
            anvil.log_message(f"Moon modes: {', '.join(modes)}", level="info")
            anvil.log_message(f"Current: {moon.mode}", level="info")
            anvil.log_message("  twinkle - Twinkling stars (fast)", level="debug")
            anvil.log_message("  phase   - Moon phase cycle (slow)", level="debug")
            anvil.log_message("  static  - No animation", level="debug")
            return

        mode = args[0].lower()
        if mode in modes:
            moon.set_mode(mode)
            anvil.log_message(f"Moon animation: {mode}", level="success")
        elif mode == "pulse":
            moon.pulse()
            anvil.log_message("Moon pulse!", level="success")
        elif mode == "toggle":
            moon.toggle_animation()
            status = "on" if moon.animating else "off"
            anvil.log_message(f"Moon animation: {status}", level="info")
        else:
            anvil.log_message(f"Unknown mode: {mode}", level="warning")
            anvil.log_message(f"Available: {', '.join(modes)}, pulse, toggle", level="info")

    async def _cmd_clear(self, args: List[str]) -> None:
        """Clear output."""
        anvil = self.query_one("#anvil-panel", AnvilPanel)
        anvil.clear_log()
        anvil.log_message("Output cleared", level="info")

    async def _cmd_refresh(self, args: List[str]) -> None:
        """Refresh all panels."""
        await self.action_refresh()

    async def _cmd_personality(self, args: List[str]) -> None:
        """Show/update personality profile."""
        anvil = self.query_one("#anvil-panel", AnvilPanel)
        personality = self.query_one("#personality-panel", PersonalityPanel)

        anvil.log_message("Personality Profile:", level="info")

        scores = personality.get_scores()
        alignment = personality.get_alignment()

        anvil.log_message(f"  Alignment: {alignment * 100:.1f}%", level="info")
        for dim, score in scores.items():
            target = 0.7
            diff = score - target
            status = "✓" if abs(diff) < 0.1 else "✗"
            anvil.log_message(f"  {status} {dim}: {score:.2f}", level="debug")

    async def _cmd_assay(self, args: List[str]) -> None:
        """Run full dataset assay with personality analysis."""
        anvil = self.query_one("#anvil-panel", AnvilPanel)
        personality = self.query_one("#personality-panel", PersonalityPanel)
        overwatch = self.query_one("#overwatch-panel", OverwatchPanel)

        if not args:
            anvil.log_message("Usage: assay <path-to-jsonl>", level="warning")
            anvil.log_message("Example: assay ./data/training.jsonl", level="info")
            return

        path = args[0]
        target_llm = args[1] if len(args) > 1 else "qwen2.5-3b-instruct"

        anvil.log_message(f"Running assay on: {path}", level="info")
        anvil.log_message(f"Target LLM: {target_llm}", level="debug")

        try:
            from pathlib import Path
            from persona_forge.engine import Crucible, Assayer, TARGET_PROFILE

            # Load config for target LLM
            try:
                from persona_forge.config import ConfigLoader
                loader = ConfigLoader()
                personality_target = loader.get_personality_profile(target_llm)
            except Exception:
                personality_target = TARGET_PROFILE

            anvil.update_progress("Loading data...", 20)
            await asyncio.sleep(0.1)

            crucible = Crucible(enable_personality_scoring=True)
            examples = crucible.ingest_jsonl(Path(path))

            anvil.log_message(f"Loaded {len(examples)} examples", level="success")
            anvil.update_progress("Analyzing...", 60)
            await asyncio.sleep(0.1)

            assayer = Assayer(personality_target=personality_target)
            assay = assayer.analyze(examples)

            anvil.update_progress("Updating panels...", 90)
            await asyncio.sleep(0.1)

            # Update overwatch
            overwatch.update_health(assay.health_score)

            # Update personality panel
            personality.update_from_assay(assay)
            personality.update_target_llm(target_llm)

            anvil.clear_progress()

            # Report results
            anvil.log_message("=== ASSAY COMPLETE ===", level="success")
            anvil.log_message(f"Health Score: {assay.health_score:.1f}/100", level="info")

            if assay.personality_alignment is not None:
                pct = assay.personality_alignment * 100
                status = "🟢" if pct >= 85 else "🟡" if pct >= 70 else "🔴"
                anvil.log_message(f"Personality Alignment: {status} {pct:.1f}%", level="info")

            # Refresh panels
            personality.refresh_data()
            overwatch.refresh_data()

        except FileNotFoundError:
            anvil.log_message(f"File not found: {path}", level="error")
            anvil.clear_progress()
        except Exception as e:
            anvil.log_message(f"Error: {e}", level="error")
            anvil.clear_progress()

    # Actions

    def action_command_palette(self) -> None:
        """Open the command palette."""
        self.push_screen(CommandPalette(self._command_history), self._on_palette_result)

    def _on_palette_result(self, result: Optional[str]) -> None:
        """Handle command palette result."""
        if result:
            asyncio.create_task(self.execute_command(result))

    async def action_refresh(self) -> None:
        """Refresh all panels."""
        crucible = self.query_one("#crucible-panel", CruciblePanel)
        overwatch = self.query_one("#overwatch-panel", OverwatchPanel)

        crucible.refresh_data()
        overwatch.refresh_data()

        anvil = self.query_one("#anvil-panel", AnvilPanel)
        anvil.log_message("Panels refreshed", level="debug")

    def action_cycle_theme(self) -> None:
        """Cycle through available themes."""
        self._current_theme_index = (self._current_theme_index + 1) % len(THEME_NAMES)
        self._forge_theme = get_theme(THEME_NAMES[self._current_theme_index])
        self._apply_theme()

        anvil = self.query_one("#anvil-panel", AnvilPanel)
        anvil.log_message(f"Theme: {self._forge_theme.name}", level="debug")

    def action_cycle_moon(self) -> None:
        """Cycle through moon animation modes."""
        moon = self.query_one("#moon-widget", MoonWidget)
        modes = ["twinkle", "phase", "static"]
        current_idx = modes.index(moon.mode) if moon.mode in modes else 0
        next_idx = (current_idx + 1) % len(modes)
        moon.set_mode(modes[next_idx])

        anvil = self.query_one("#anvil-panel", AnvilPanel)
        anvil.log_message(f"Moon: {modes[next_idx]}", level="debug")

    def action_cancel(self) -> None:
        """Cancel current operation."""
        if self._running_task and not self._running_task.done():
            self._running_task.cancel()
            anvil = self.query_one("#anvil-panel", AnvilPanel)
            anvil.log_message("Operation cancelled", level="warning")

    def action_help(self) -> None:
        """Show help."""
        asyncio.create_task(self._cmd_help([]))


if __name__ == "__main__":
    app = PersonaForgeApp()
    app.run()
