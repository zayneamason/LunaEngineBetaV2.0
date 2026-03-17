"""Manifest Panel — Right panel showing resolved build configuration."""

from __future__ import annotations

from typing import Any

from textual.containers import Container, VerticalScroll
from textual.widgets import Static
from textual.app import ComposeResult


class ManifestPanel(Container):
    """Right panel — resolved build manifest."""

    DEFAULT_CSS = """
    ManifestPanel {
        height: 100%;
    }
    """

    def __init__(self, **kwargs):
        self._manifest: dict[str, Any] = {}
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        yield Static("[bold #8B00FF]MANIFEST[/]", classes="manifest-title")
        yield VerticalScroll(id="manifest-content")

    def on_mount(self) -> None:
        self._render_empty()

    def _render_empty(self) -> None:
        content = self.query_one("#manifest-content", VerticalScroll)
        content.remove_children()
        content.mount(Static("[#666699]Select a profile to view manifest[/]"))

    def update_manifest(self, manifest: dict[str, Any]) -> None:
        """Update the manifest display."""
        self._manifest = manifest
        content = self.query_one("#manifest-content", VerticalScroll)
        content.remove_children()

        # Profile header
        content.mount(Static(
            f"[bold cyan]PROFILE:[/] {manifest.get('profile', '?')}\n"
            f"[bold cyan]VERSION:[/] {manifest.get('version', '?')}\n"
            f"[bold cyan]PLATFORM:[/] {manifest.get('platform', '?')}"
        ))

        # Database
        db = manifest.get("database", {})
        db_text = f"[bold magenta]DATABASE[/]\n"
        db_text += f"  [#666699]Mode:[/] [cyan]{db.get('mode', 'seed')}[/]\n"
        if db.get("source"):
            db_text += f"  [#666699]Source:[/] [cyan]{db['source']}[/]"
        else:
            db_text += f"  [#666699]Source:[/] [cyan](blank schema)[/]"
        content.mount(Static(db_text, classes="manifest-section"))

        # Collections
        collections = manifest.get("collections", {})
        coll_text = f"[bold magenta]COLLECTIONS[/]\n"
        if collections:
            for name, info in collections.items():
                if info.get("enabled"):
                    size = info.get("size", 0)
                    size_str = f"{size/(1024*1024):.1f} MB" if info.get("exists") else "NOT FOUND"
                    coll_text += f"  [green]\u2713[/] {name}  [#666699]{size_str}[/]\n"
                else:
                    coll_text += f"  [red]\u2717[/] {name}\n"
        else:
            coll_text += "  [#666699](none)[/]"
        content.mount(Static(coll_text, classes="manifest-section"))

        # Config
        cfg = manifest.get("config", {})
        patches = cfg.get("personality_patches", [])
        cfg_text = f"[bold magenta]CONFIG[/]\n"
        cfg_text += f"  [#666699]Personality:[/] [cyan]clean[/]\n"
        cfg_text += f"  [#666699]Patches:[/] [cyan]{len(patches)}[/] ({', '.join(p.replace('bootstrap_', '').replace('_', ' ') for p in patches[:3])})\n"
        cfg_text += f"  [#666699]LLM:[/] [cyan]{cfg.get('llm_providers_mode', 'template')}[/]\n"
        cfg_text += f"  [#666699]Fallback:[/] [cyan]{' \u2192 '.join(cfg.get('fallback_chain', []))}[/]"
        content.mount(Static(cfg_text, classes="manifest-section"))

        # Secrets
        content.mount(Static(
            f"[bold magenta]SECRETS[/]\n"
            f"  [#666699]Mode:[/] [cyan]{manifest.get('secrets_mode', 'template')}[/]",
            classes="manifest-section",
        ))

        # Frontend
        fe = manifest.get("frontend", {})
        pages = fe.get("pages", {})
        widgets = fe.get("widgets", {})
        remap = fe.get("remap", {})

        fe_text = f"[bold magenta]FRONTEND[/]\n"
        fe_text += "  [#666699]Pages:[/]\n"
        for page, enabled in pages.items():
            icon = "[green]\u2713[/]" if enabled else "[red]\u2717[/]"
            fe_text += f"  {icon} {page}\n"

        if remap:
            fe_text += "\n  [#666699]Remap:[/]\n"
            for mod, cfg in remap.items():
                fe_text += f"  {mod} \u2192 {cfg.get('to', '?')}.{cfg.get('position', '?')}\n"

        enabled_widgets = sum(1 for v in widgets.values() if v)
        fe_text += f"\n  [#666699]Widgets:[/] [cyan]{enabled_widgets} / {len(widgets)}[/]\n"
        for w, enabled in widgets.items():
            if enabled:
                fe_text += f"  [green]\u2713[/] {w}\n"
        content.mount(Static(fe_text, classes="manifest-section"))

        # Nuitka
        nk = manifest.get("nuitka", {})
        nk_text = f"[bold magenta]NUITKA[/]\n"
        nk_text += f"  [#666699]Standalone:[/] [cyan]{nk.get('standalone', True)}[/]\n"
        nk_text += f"  [#666699]Excluded:[/] [cyan]{len(nk.get('excluded_packages', []))} packages[/]"
        content.mount(Static(nk_text, classes="manifest-section"))
