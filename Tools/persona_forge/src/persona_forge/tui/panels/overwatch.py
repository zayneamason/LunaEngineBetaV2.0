"""
Overwatch Panel - Metrics and Quality Gauges.

The right panel showing dataset health, distribution charts, and quality tiers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from textual.app import ComposeResult
from textual.containers import Container, Vertical, VerticalScroll
from textual.widgets import Static, Sparkline
from textual.reactive import reactive


@dataclass
class MetricData:
    """A metric with label and value."""
    label: str
    value: float
    max_value: float = 100.0
    unit: str = ""

    @property
    def percentage(self) -> float:
        return (self.value / self.max_value) * 100 if self.max_value > 0 else 0

    @property
    def tier(self) -> str:
        """Get tier based on percentage."""
        if self.percentage >= 80:
            return "high"
        elif self.percentage >= 50:
            return "medium"
        return "low"


class HealthGauge(Static):
    """A visual gauge for health score."""

    value: reactive[float] = reactive(0.0)

    def __init__(self, label: str, value: float = 0.0, **kwargs) -> None:
        super().__init__(**kwargs)
        self.label = label
        self.value = value

    def render(self) -> str:
        # Create a visual bar gauge
        bar_width = 18
        filled = int((self.value / 100) * bar_width)
        empty = bar_width - filled

        # Color based on value
        if self.value >= 80:
            color = "green"
        elif self.value >= 50:
            color = "yellow"
        else:
            color = "red"

        bar = f"[{color}]{'█' * filled}[/][dim]{'░' * empty}[/]"

        return (
            f"[magenta bold]{self.label}[/]\n"
            f"{bar} [{color}]{self.value:.0f}%[/]"
        )


class DistributionChart(Static):
    """A simple bar chart for distributions."""

    def __init__(self, title: str, data: Dict[str, int], **kwargs) -> None:
        super().__init__(**kwargs)
        self.title = title
        self.data = data

    def render(self) -> str:
        lines = [f"[purple bold]{self.title}[/]"]

        if not self.data:
            lines.append("[dim]No data[/]")
            return "\n".join(lines)

        max_val = max(self.data.values()) if self.data else 1
        bar_width = 12

        for label, value in self.data.items():
            filled = int((value / max_val) * bar_width) if max_val > 0 else 0
            bar = "█" * filled + "░" * (bar_width - filled)
            lines.append(f"[dim]{label:8}[/] [cyan]{bar}[/] [magenta]{value:3}[/]")

        return "\n".join(lines)


class QualityTiers(Static):
    """Display quality tier breakdown."""

    def __init__(self, tiers: Dict[str, int], **kwargs) -> None:
        super().__init__(**kwargs)
        self.tiers = tiers

    def render(self) -> str:
        lines = ["[cyan bold]Quality Tiers[/]"]

        tier_colors = {
            "gold": "#FFD700",
            "silver": "#C0C0C0",
            "bronze": "#CD7F32",
        }

        total = sum(self.tiers.values())

        for tier, count in self.tiers.items():
            color = tier_colors.get(tier, "white")
            pct = (count / total * 100) if total > 0 else 0
            icon = {"gold": "★", "silver": "◆", "bronze": "●"}.get(tier, "○")
            lines.append(f"[{color}]{icon} {tier.capitalize():8}[/] {count:3} ({pct:.0f}%)")

        return "\n".join(lines)


class OverwatchPanel(Container):
    """
    The Overwatch Panel - Metrics and quality monitoring.

    Shows:
    - Dataset health score gauge
    - Distribution charts (by source type, tone, etc.)
    - Quality tier breakdown
    - Key metrics
    """

    health_score: reactive[float] = reactive(0.0)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._metrics: Dict[str, MetricData] = {}
        self._distributions: Dict[str, Dict[str, int]] = {}
        self._quality_tiers: Dict[str, int] = {}
        self._init_demo_data()

    def _init_demo_data(self) -> None:
        """Initialize with demo data for display."""
        self.health_score = 87.0

        self._metrics = {
            "examples": MetricData("Total Examples", 50, 100, ""),
            "balance": MetricData("Balance Score", 0.82, 1.0, ""),
            "coverage": MetricData("Trait Coverage", 94, 100, "%"),
            "diversity": MetricData("Vocabulary", 2847, 5000, "words"),
        }

        self._distributions = {
            "source_type": {
                "convo": 24,
                "template": 8,
                "voice": 12,
                "edge": 6,
            },
            "tone": {
                "warm": 18,
                "playful": 14,
                "wise": 10,
                "direct": 8,
            },
        }

        self._quality_tiers = {
            "gold": 22,
            "silver": 18,
            "bronze": 10,
        }

    def compose(self) -> ComposeResult:
        yield Static("[ OVERWATCH ]", classes="overwatch-title")

        with VerticalScroll(classes="metrics-container"):
            # Health gauge
            yield HealthGauge(
                "Dataset Health",
                self.health_score,
                id="health-gauge",
                classes="gauge-container"
            )

            # Key metrics
            yield Static(self._render_metrics(), id="key-metrics", classes="metric-card")

            # Distribution chart - source types
            yield DistributionChart(
                "By Source Type",
                self._distributions.get("source_type", {}),
                id="source-chart",
                classes="chart-container"
            )

            # Distribution chart - tones
            yield DistributionChart(
                "By Tone",
                self._distributions.get("tone", {}),
                id="tone-chart",
                classes="chart-container"
            )

            # Quality tiers
            yield QualityTiers(
                self._quality_tiers,
                id="quality-tiers",
                classes="tier-container"
            )

    def _render_metrics(self) -> str:
        """Render key metrics."""
        lines = ["[cyan bold]Key Metrics[/]"]

        for key, metric in self._metrics.items():
            color = {"high": "green", "medium": "yellow", "low": "red"}[metric.tier]
            if metric.max_value == 1.0:
                value_str = f"{metric.value:.2f}"
            else:
                value_str = f"{metric.value:.0f}"
            lines.append(f"[dim]{metric.label}:[/] [{color}]{value_str}{metric.unit}[/]")

        return "\n".join(lines)

    def refresh_data(self) -> None:
        """Refresh all metrics and charts."""
        # Update health gauge
        health_gauge = self.query_one("#health-gauge", HealthGauge)
        health_gauge.value = self.health_score

        # Update key metrics
        metrics_widget = self.query_one("#key-metrics", Static)
        metrics_widget.update(self._render_metrics())

    def update_health(self, score: float) -> None:
        """Update the health score."""
        self.health_score = min(100, max(0, score))
        self.refresh_data()

    def update_metric(self, key: str, value: float) -> None:
        """Update a specific metric."""
        if key in self._metrics:
            self._metrics[key].value = value
            self.refresh_data()

    def update_distribution(self, name: str, data: Dict[str, int]) -> None:
        """Update a distribution chart."""
        self._distributions[name] = data

        if name == "source_type":
            chart = self.query_one("#source-chart", DistributionChart)
            chart.data = data
            chart.refresh()
        elif name == "tone":
            chart = self.query_one("#tone-chart", DistributionChart)
            chart.data = data
            chart.refresh()

    def update_quality_tiers(self, tiers: Dict[str, int]) -> None:
        """Update quality tier breakdown."""
        self._quality_tiers = tiers
        tiers_widget = self.query_one("#quality-tiers", QualityTiers)
        tiers_widget.tiers = tiers
        tiers_widget.refresh()

    def get_health_score(self) -> float:
        """Get current health score."""
        return self.health_score

    def get_all_metrics(self) -> Dict[str, MetricData]:
        """Get all metrics."""
        return self._metrics.copy()
