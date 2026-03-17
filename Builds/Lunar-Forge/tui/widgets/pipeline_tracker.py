"""Pipeline Tracker — Visual step-by-step build progress display."""

from __future__ import annotations

from typing import Optional

from textual.widgets import Static


# Build pipeline stages (must match core.py step order)
PIPELINE_STAGES = [
    ("staging",        "Prepare Staging"),
    ("frontend",       "Copy Frontend"),
    ("config",         "Assemble Config"),
    ("data",           "Assemble Data"),
    ("secrets",        "Write Secrets"),
    ("frontend_cfg",   "Frontend Config"),
    ("nuitka",         "Nuitka Compile"),
    ("post_process",   "Post-Process"),
    ("output",         "Final Output"),
]

# Status icons
ICONS = {
    "pending":    "[dim]\u25cb[/]",       # empty circle
    "active":     "[bold cyan]\u25cf[/]",  # filled circle (cyan)
    "done":       "[bold green]\u2713[/]", # checkmark
    "error":      "[bold red]\u2717[/]",   # cross
    "skipped":    "[dim]\u2500[/]",        # dash
}


class PipelineTracker(Static):
    """Visual build pipeline — shows each stage with status icons.

    Starts hidden (display:none) until a build begins, then appears.
    """

    DEFAULT_CSS = """
    PipelineTracker {
        display: none;
        height: auto;
        max-height: 22;
        background: #0D0221;
        border: round #3D0066;
        margin-bottom: 1;
        padding: 1;
    }
    """

    def __init__(self, **kwargs):
        super().__init__("", **kwargs)
        self._stage_status: dict[str, str] = {
            key: "pending" for key, _ in PIPELINE_STAGES
        }
        self._current_stage: Optional[str] = None
        self._shown = False

    def render(self) -> str:
        """Always return a string to avoid NoneType crash."""
        if not self._shown:
            return ""
        return self._build_content()

    def show(self) -> None:
        """Show the pipeline tracker."""
        self._shown = True
        self.display = True
        self.refresh()

    def hide(self) -> None:
        """Hide the pipeline tracker."""
        self._shown = False
        self.display = False

    def reset(self) -> None:
        """Reset all stages to pending."""
        self._stage_status = {key: "pending" for key, _ in PIPELINE_STAGES}
        self._current_stage = None
        self.refresh()

    def set_stage(self, stage_key: str, status: str = "active") -> None:
        """Update a stage's status. Also marks previous active stage as done."""
        if stage_key not in self._stage_status:
            return

        # Auto-complete previous active stage
        if status == "active" and self._current_stage and self._current_stage != stage_key:
            self._stage_status[self._current_stage] = "done"

        self._stage_status[stage_key] = status
        if status == "active":
            self._current_stage = stage_key
        self.refresh()

    def complete_all(self) -> None:
        """Mark all stages as done."""
        for key, _ in PIPELINE_STAGES:
            self._stage_status[key] = "done"
        self._current_stage = None
        self.refresh()

    def fail_current(self) -> None:
        """Mark current stage as error."""
        if self._current_stage:
            self._stage_status[self._current_stage] = "error"
        self.refresh()

    def _build_content(self) -> str:
        lines = ["[bold magenta]PIPELINE[/]\n"]

        for i, (key, label) in enumerate(PIPELINE_STAGES):
            status = self._stage_status.get(key, "pending")
            icon = ICONS.get(status, ICONS["pending"])

            if status == "active":
                line = f"  {icon} [bold cyan]{label}[/] [magenta]\u25c0[/]"
            elif status == "done":
                line = f"  {icon} [green]{label}[/]"
            elif status == "error":
                line = f"  {icon} [bold red]{label}[/]"
            else:
                line = f"  {icon} [dim]{label}[/]"

            lines.append(line)

            # Connector line between stages
            if i < len(PIPELINE_STAGES) - 1:
                if status == "done":
                    lines.append("  [green]\u2502[/]")
                elif status == "active":
                    lines.append("  [cyan]\u2502[/]")
                else:
                    lines.append("  [dim]\u2502[/]")

        return "\n".join(lines)
