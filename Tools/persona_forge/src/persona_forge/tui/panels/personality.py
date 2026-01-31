"""
Personality Panel - 8-Dimensional Personality Profile Display.

Shows personality scores with visual gauges and alignment status.
"""

from __future__ import annotations

from typing import Dict, Optional

from textual.app import ComposeResult
from textual.containers import Container, VerticalScroll
from textual.widgets import Static
from textual.reactive import reactive


# Dimension display configuration
DIMENSION_CONFIG = {
    "warmth": {"icon": "♥", "color": "#FF6B6B"},
    "technical": {"icon": "⚙", "color": "#4ECDC4"},
    "humor": {"icon": "☺", "color": "#FFE66D"},
    "directness": {"icon": "→", "color": "#95E1D3"},
    "creativity": {"icon": "✦", "color": "#DDA0DD"},
    "reflection": {"icon": "◐", "color": "#98D8C8"},
    "relationship": {"icon": "♦", "color": "#F7DC6F"},
    "assertiveness": {"icon": "▲", "color": "#BB8FCE"},
}

# Luna's target profile
TARGET_PROFILE = {
    "warmth": 0.85,
    "technical": 0.70,
    "humor": 0.65,
    "directness": 0.80,
    "creativity": 0.70,
    "reflection": 0.75,
    "relationship": 0.90,
    "assertiveness": 0.75,
}


class PersonalityGauge(Static):
    """A visual gauge for a single personality dimension."""

    value: reactive[float] = reactive(0.5)
    target: reactive[float] = reactive(0.7)

    def __init__(
        self,
        dimension: str,
        value: float = 0.5,
        target: float = 0.7,
        **kwargs
    ) -> None:
        super().__init__(**kwargs)
        self.dimension = dimension
        self.value = value
        self.target = target
        self.config = DIMENSION_CONFIG.get(dimension, {"icon": "●", "color": "white"})

    def render(self) -> str:
        icon = self.config["icon"]
        color = self.config["color"]

        # Calculate bar
        bar_width = 16
        filled = int(self.value * bar_width)
        empty = bar_width - filled

        # Status based on gap from target
        diff = self.value - self.target
        if abs(diff) < 0.05:
            status = "[green]✓✓[/]"
        elif abs(diff) < 0.10:
            status = "[yellow]✓ [/]"
        else:
            status = "[red]✗ [/]"

        # Diff indicator
        if diff > 0:
            diff_str = f"[green]↑+{diff:.2f}[/]"
        elif diff < 0:
            diff_str = f"[red]↓{diff:.2f}[/]"
        else:
            diff_str = "[dim]= 0.00[/]"

        bar = f"[{color}]{'█' * filled}[/][dim]{'░' * empty}[/]"

        return (
            f"{status} [{color}]{icon}[/] [bold]{self.dimension:12}[/] "
            f"{bar} [{color}]{self.value:.2f}[/] {diff_str}"
        )


class AlignmentGauge(Static):
    """Overall alignment gauge."""

    alignment: reactive[float] = reactive(0.0)

    def __init__(self, alignment: float = 0.0, **kwargs) -> None:
        super().__init__(**kwargs)
        self.alignment = alignment

    def render(self) -> str:
        pct = self.alignment * 100

        # Status emoji
        if pct >= 85:
            status = "🟢"
            color = "green"
        elif pct >= 70:
            status = "🟡"
            color = "yellow"
        else:
            status = "🔴"
            color = "red"

        # Bar
        bar_width = 20
        filled = int((pct / 100) * bar_width)
        empty = bar_width - filled
        bar = f"[{color}]{'█' * filled}[/][dim]{'░' * empty}[/]"

        return (
            f"[bold cyan]Personality Alignment[/]\n"
            f"{status} {bar} [{color}]{pct:.1f}%[/] [dim](target: ≥85%)[/]"
        )


class PersonalityPanel(Container):
    """
    Personality Profile Panel.

    Displays 8-dimensional personality scores with visual gauges
    and overall alignment status.
    """

    alignment: reactive[float] = reactive(0.0)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._scores: Dict[str, float] = {}
        self._variance: Dict[str, float] = {}
        self._target_llm: str = "qwen2.5-3b-instruct"
        self._init_default_data()

    def _init_default_data(self) -> None:
        """Initialize with default/demo data."""
        self._scores = {dim: 0.5 for dim in DIMENSION_CONFIG}
        self._variance = {dim: 0.0 for dim in DIMENSION_CONFIG}
        self.alignment = 0.0

    def compose(self) -> ComposeResult:
        yield Static("[ PERSONALITY ]", classes="panel-title")

        with VerticalScroll(classes="personality-container"):
            # Overall alignment
            yield AlignmentGauge(
                self.alignment,
                id="alignment-gauge",
                classes="alignment-gauge"
            )

            yield Static("", classes="spacer")
            yield Static("[cyan bold]Dimension Scores[/]", classes="section-header")

            # Individual dimension gauges
            for dim in DIMENSION_CONFIG:
                yield PersonalityGauge(
                    dimension=dim,
                    value=self._scores.get(dim, 0.5),
                    target=TARGET_PROFILE.get(dim, 0.7),
                    id=f"gauge-{dim}",
                    classes="personality-gauge"
                )

            yield Static("", classes="spacer")
            yield Static(
                f"[dim]Target LLM: {self._target_llm}[/]",
                id="target-llm-label",
                classes="target-label"
            )

    def update_scores(self, scores: Dict[str, float]) -> None:
        """Update personality scores."""
        self._scores = scores

        for dim, score in scores.items():
            try:
                gauge = self.query_one(f"#gauge-{dim}", PersonalityGauge)
                gauge.value = score
            except Exception:
                pass

    def update_variance(self, variance: Dict[str, float]) -> None:
        """Update variance values."""
        self._variance = variance

    def update_alignment(self, alignment: float) -> None:
        """Update overall alignment."""
        self.alignment = alignment

        try:
            gauge = self.query_one("#alignment-gauge", AlignmentGauge)
            gauge.alignment = alignment
        except Exception:
            pass

    def update_target_llm(self, llm_name: str) -> None:
        """Update target LLM label."""
        self._target_llm = llm_name

        try:
            label = self.query_one("#target-llm-label", Static)
            label.update(f"[dim]Target LLM: {llm_name}[/]")
        except Exception:
            pass

    def update_from_assay(self, assay) -> None:
        """
        Update panel from a DatasetAssay object.

        Args:
            assay: DatasetAssay with personality_profile, personality_variance,
                   and personality_alignment fields.
        """
        if assay.personality_profile:
            self.update_scores(assay.personality_profile)

        if assay.personality_variance:
            self.update_variance(assay.personality_variance)

        if assay.personality_alignment is not None:
            self.update_alignment(assay.personality_alignment)

    def refresh_data(self) -> None:
        """Refresh display."""
        for dim in DIMENSION_CONFIG:
            try:
                gauge = self.query_one(f"#gauge-{dim}", PersonalityGauge)
                gauge.value = self._scores.get(dim, 0.5)
                gauge.refresh()
            except Exception:
                pass

        try:
            alignment_gauge = self.query_one("#alignment-gauge", AlignmentGauge)
            alignment_gauge.alignment = self.alignment
            alignment_gauge.refresh()
        except Exception:
            pass

    def get_scores(self) -> Dict[str, float]:
        """Get current personality scores."""
        return self._scores.copy()

    def get_alignment(self) -> float:
        """Get current alignment score."""
        return self.alignment
