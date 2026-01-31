"""
Crucible Panel - Source File Management.

The left panel showing loaded sources, file types, and example counts.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from textual.app import ComposeResult
from textual.containers import Container, Vertical, VerticalScroll
from textual.widgets import Static, Label
from textual.reactive import reactive


@dataclass
class SourceFile:
    """A source file in the crucible."""
    name: str
    path: Path
    source_type: str
    example_count: int
    status: str = "loaded"  # loaded, processing, error


class SourceItem(Static):
    """A single source file item in the list."""

    def __init__(self, source: SourceFile, **kwargs) -> None:
        super().__init__(**kwargs)
        self.source = source

    def compose(self) -> ComposeResult:
        yield Static(self.source.name, classes="source-name")
        yield Static(f"[{self.source.source_type}]", classes="source-type")
        yield Static(f"{self.source.example_count} examples", classes="source-count")

    def render(self) -> str:
        status_icon = {
            "loaded": "[green]●[/]",
            "processing": "[yellow]◐[/]",
            "error": "[red]●[/]",
        }.get(self.source.status, "○")

        return (
            f"{status_icon} {self.source.name}\n"
            f"   [{self.source.source_type}] {self.source.example_count} examples"
        )


class CruciblePanel(Container):
    """
    The Crucible Panel - Source file management.

    Shows:
    - List of loaded source files
    - Source types (conversation, template, voice)
    - Example counts per source
    - Processing status
    """

    sources: reactive[List[SourceFile]] = reactive([])

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._sources: List[SourceFile] = []
        self._init_demo_sources()

    def _init_demo_sources(self) -> None:
        """Initialize with demo sources for display."""
        self._sources = [
            SourceFile(
                name="luna_conversations.json",
                path=Path("data/luna_conversations.json"),
                source_type="conversation",
                example_count=24,
                status="loaded"
            ),
            SourceFile(
                name="personality_core.yaml",
                path=Path("profiles/luna.yaml"),
                source_type="template",
                example_count=8,
                status="loaded"
            ),
            SourceFile(
                name="voice_samples.txt",
                path=Path("data/voice_samples.txt"),
                source_type="voice",
                example_count=12,
                status="loaded"
            ),
            SourceFile(
                name="edge_cases.json",
                path=Path("data/edge_cases.json"),
                source_type="edge_case",
                example_count=6,
                status="loaded"
            ),
        ]

    def compose(self) -> ComposeResult:
        yield Static("[ CRUCIBLE ]", classes="crucible-title")

        with VerticalScroll(classes="source-list"):
            for source in self._sources:
                yield SourceItem(source, classes="source-item")

        yield Static(self._get_summary(), id="crucible-summary")

    def _get_summary(self) -> str:
        """Get summary text."""
        total_files = len(self._sources)
        total_examples = sum(s.example_count for s in self._sources)
        return f"[cyan]{total_files} files[/] | [magenta]{total_examples} examples[/]"

    def refresh_data(self) -> None:
        """Refresh the source list data."""
        # In real implementation, this would scan actual files
        # For now, just trigger a re-render
        summary = self.query_one("#crucible-summary", Static)
        summary.update(self._get_summary())

    def add_source(self, source: SourceFile) -> None:
        """Add a source file to the crucible."""
        self._sources.append(source)
        self.refresh_data()

    def remove_source(self, name: str) -> bool:
        """Remove a source by name."""
        for i, source in enumerate(self._sources):
            if source.name == name:
                self._sources.pop(i)
                self.refresh_data()
                return True
        return False

    def get_total_examples(self) -> int:
        """Get total example count across all sources."""
        return sum(s.example_count for s in self._sources)

    def get_source_types(self) -> List[str]:
        """Get list of unique source types."""
        return list(set(s.source_type for s in self._sources))
