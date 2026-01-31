"""
Persona Forge CLI - Command Line Interface

Typer-based CLI for the Persona Forge training data pipeline.
Provides commands for loading, analyzing, minting, and exporting
training data, as well as personality profile management and
Voight-Kampff testing.

Usage:
    python -m persona_forge <command> [options]

    # Or with the forge command (if installed)
    forge <command> [options]
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional, Annotated

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.syntax import Syntax
from rich import print as rprint

# Core imports
from .engine import (
    Crucible,
    Assayer,
    Locksmith,
    DIRECTOR_PROFILE,
    InteractionType,
    TargetProfile,
    QualityTier,
)
from .engine.mint import Mint
from .engine.anvil import Anvil
from .engine.pipeline import ForgePipeline, PipelineStage

# Personality imports
from .personality import (
    CharacterForge,
    PersonalityProfile,
    create_luna_profile,
    list_templates,
    list_archetypes,
)

# Voight-Kampff imports
from .voight_kampff import (
    VoightKampffRunner,
    SyncVoightKampffRunner,
    SuiteBuilder,
    build_luna_suite,
    build_minimal_identity_suite,
    TestSuite,
)


# Initialize Typer app
app = typer.Typer(
    name="forge",
    help="Persona Forge - Training Data Command Center for Personality LoRA Fine-Tuning",
    no_args_is_help=True,
)

# Sub-commands
character_app = typer.Typer(help="Character/personality profile management")
vk_app = typer.Typer(help="Voight-Kampff personality validation tests")

app.add_typer(character_app, name="character")
app.add_typer(vk_app, name="vk")

# Console for rich output
console = Console()

# Global state (for session management)
_state = {
    "examples": [],
    "assay": None,
    "profile": None,
}


# =============================================================================
# Main Pipeline Commands
# =============================================================================


@app.command()
def load(
    path: Annotated[str, typer.Argument(help="Path to JSONL file or directory")],
    strict: Annotated[bool, typer.Option("--strict", "-s", help="Fail on parse errors")] = False,
    recursive: Annotated[bool, typer.Option("--recursive", "-r", help="Search directories recursively")] = True,
):
    """Load training data from JSONL file(s)."""
    console.print(f"[bold blue]Loading training data from:[/] {path}")

    path_obj = Path(path)
    if not path_obj.exists():
        console.print(f"[red]Error:[/] Path not found: {path}")
        raise typer.Exit(1)

    crucible = Crucible(strict_mode=strict)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Loading...", total=None)

        try:
            if path_obj.is_file():
                examples = crucible.ingest_jsonl(path_obj)
            else:
                examples = crucible.ingest_directory(path_obj, recursive=recursive)

            _state["examples"] = examples
            progress.update(task, description="[green]Complete!")

        except Exception as e:
            console.print(f"[red]Error loading data:[/] {e}")
            raise typer.Exit(1)

    stats = crucible.get_stats()

    # Display results table
    table = Table(title="Load Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Total Lines", str(stats["total_lines"]))
    table.add_row("Successful Parses", str(stats["successful_parses"]))
    table.add_row("Failed Parses", str(stats["failed_parses"]))
    table.add_row("Skipped Empty", str(stats["skipped_empty"]))
    table.add_row("Examples Loaded", str(len(examples)))

    console.print(table)


@app.command()
def assay(
    profile: Annotated[str, typer.Option("--profile", "-p", help="Target profile name")] = "director",
    show_gaps: Annotated[bool, typer.Option("--gaps", "-g", help="Show coverage gaps")] = True,
):
    """Analyze the loaded dataset."""
    if not _state["examples"]:
        console.print("[red]Error:[/] No data loaded. Run 'forge load' first.")
        raise typer.Exit(1)

    # Get target profile
    if profile == "director":
        target = DIRECTOR_PROFILE
    else:
        console.print(f"[yellow]Unknown profile '{profile}', using director[/]")
        target = DIRECTOR_PROFILE

    console.print(f"[bold blue]Analyzing {len(_state['examples'])} examples...[/]")

    # Compute lock-in coefficients first
    locksmith = Locksmith()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        task = progress.add_task("Computing lock-in...", total=len(_state["examples"]))

        for example in _state["examples"]:
            locksmith.compute_lock_in(example)
            progress.advance(task)

    # Run analysis
    assayer = Assayer()
    result = assayer.analyze(_state["examples"], target_profile=target)
    _state["assay"] = result

    # Display results
    console.print()
    console.print(Panel(
        f"[bold]Health Score:[/] {result.health_score:.1f}/100\n"
        f"[bold]Total Examples:[/] {result.total_examples}\n"
        f"[bold]Gold Percentage:[/] {result.gold_percentage:.1f}%\n"
        f"[bold]Clean Percentage:[/] {result.clean_percentage:.1f}%",
        title="Dataset Assay",
        border_style="blue",
    ))

    # Quality distribution
    table = Table(title="Quality Distribution")
    table.add_column("Tier", style="cyan")
    table.add_column("Count", style="green")
    table.add_column("Percentage", style="yellow")

    for tier, count in result.quality_tiers.counts.items():
        pct = result.quality_tiers.percentages.get(tier, 0)
        table.add_row(tier.upper(), str(count), f"{pct:.1f}%")

    console.print(table)

    # Interaction types
    table = Table(title="Interaction Types")
    table.add_column("Type", style="cyan")
    table.add_column("Count", style="green")
    table.add_column("Percentage", style="yellow")

    for itype, count in sorted(result.interaction_types.counts.items(), key=lambda x: -x[1]):
        pct = result.interaction_types.percentages.get(itype, 0)
        table.add_row(itype, str(count), f"{pct:.1f}%")

    console.print(table)

    # Coverage gaps
    if show_gaps and result.coverage_gaps:
        table = Table(title="Coverage Gaps")
        table.add_column("Category", style="cyan")
        table.add_column("Current", style="red")
        table.add_column("Target", style="green")
        table.add_column("Gap", style="yellow")
        table.add_column("Severity", style="magenta")

        for gap in result.coverage_gaps[:10]:
            table.add_row(
                gap.category,
                f"{gap.current:.1f}%",
                f"{gap.target:.1f}%",
                f"{gap.gap:+.1f}%",
                gap.severity.upper(),
            )

        console.print(table)

    # Recommendations
    if result.needs_attention:
        console.print()
        console.print("[yellow bold]Dataset needs attention before training![/]")


@app.command()
def gaps():
    """Show coverage gaps in the current dataset."""
    if _state["assay"] is None:
        console.print("[red]Error:[/] No analysis available. Run 'forge assay' first.")
        raise typer.Exit(1)

    assay = _state["assay"]

    if not assay.coverage_gaps:
        console.print("[green]No significant coverage gaps detected![/]")
        return

    table = Table(title="Coverage Gaps (All)")
    table.add_column("Category", style="cyan")
    table.add_column("Current", style="red")
    table.add_column("Target", style="green")
    table.add_column("Gap", style="yellow")
    table.add_column("Severity", style="magenta")
    table.add_column("Action", style="blue")

    for gap in assay.coverage_gaps:
        action = "Add more" if gap.gap > 0 else "Reduce"
        table.add_row(
            gap.category,
            f"{gap.current:.1f}%",
            f"{gap.target:.1f}%",
            f"{gap.gap:+.1f}%",
            gap.severity.upper(),
            action,
        )

    console.print(table)


@app.command()
def mint(
    interaction_type: Annotated[str, typer.Argument(help="Interaction type to generate")],
    count: Annotated[int, typer.Argument(help="Number of examples to generate")] = 10,
    profile: Annotated[str, typer.Option("--profile", "-p", help="Personality profile")] = "luna",
):
    """Generate synthetic training examples."""
    # Validate interaction type
    try:
        itype = InteractionType(interaction_type)
    except ValueError:
        console.print(f"[red]Error:[/] Unknown interaction type: {interaction_type}")
        console.print(f"[yellow]Available types:[/] {', '.join(t.value for t in InteractionType)}")
        raise typer.Exit(1)

    # Load personality profile if specified
    persona = None
    if profile == "luna":
        persona = create_luna_profile()

    console.print(f"[bold blue]Minting {count} {interaction_type} examples...[/]")

    minter = Mint()
    examples = minter.mint_examples(itype, count, profile=persona)

    # Add to state
    _state["examples"].extend(examples)
    _state["assay"] = None  # Invalidate assay

    # Display samples
    table = Table(title=f"Generated Examples ({len(examples)})")
    table.add_column("#", style="dim", width=3)
    table.add_column("User", style="cyan", max_width=30)
    table.add_column("Response", style="green", max_width=50)

    for i, example in enumerate(examples[:5], 1):
        table.add_row(
            str(i),
            example.user_message[:30] + "..." if len(example.user_message) > 30 else example.user_message,
            example.assistant_response[:50] + "..." if len(example.assistant_response) > 50 else example.assistant_response,
        )

    console.print(table)

    if len(examples) > 5:
        console.print(f"[dim]... and {len(examples) - 5} more[/]")

    console.print(f"\n[green]Added {len(examples)} examples to dataset (total: {len(_state['examples'])})[/]")


@app.command("export")
def export_data(
    output_dir: Annotated[str, typer.Argument(help="Output directory for JSONL files")],
    split: Annotated[bool, typer.Option("--split", "-s", help="Create train/val split")] = True,
    train_ratio: Annotated[float, typer.Option("--ratio", "-r", help="Train ratio (0.0-1.0)")] = 0.9,
    weighted: Annotated[bool, typer.Option("--weighted/--unweighted", help="Apply quality weighting")] = True,
    gold_only: Annotated[bool, typer.Option("--gold-only", help="Export only gold-tier examples")] = False,
):
    """Export training data to JSONL format."""
    if not _state["examples"]:
        console.print("[red]Error:[/] No data loaded. Run 'forge load' first.")
        raise typer.Exit(1)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    anvil = Anvil()
    examples = _state["examples"]

    console.print(f"[bold blue]Exporting {len(examples)} examples to {output_dir}...[/]")

    try:
        if gold_only:
            result = anvil.export_gold_only(examples, output_path / "gold.jsonl", weighted=weighted)
            console.print(f"[green]Exported to:[/] {result}")
        elif split:
            result = anvil.export_train_val_split(
                examples,
                output_path,
                train_ratio=train_ratio,
                weighted=weighted,
            )
            console.print(f"[green]Exported train:[/] {result['train']} ({result['train_count']} examples)")
            console.print(f"[green]Exported val:[/] {result['val']} ({result['val_count']} examples)")
        else:
            result = anvil.export_jsonl(examples, output_path / "training_data.jsonl", weighted=weighted)
            console.print(f"[green]Exported to:[/] {result}")

    except Exception as e:
        console.print(f"[red]Export failed:[/] {e}")
        raise typer.Exit(1)


@app.command()
def pipeline(
    source: Annotated[str, typer.Argument(help="Source JSONL file or directory")],
    output_dir: Annotated[str, typer.Argument(help="Output directory")],
    synthesize: Annotated[bool, typer.Option("--synthesize/--no-synthesize", help="Generate synthetic examples")] = True,
    max_synthetic: Annotated[int, typer.Option("--max-synthetic", help="Max synthetic examples")] = 100,
    train_ratio: Annotated[float, typer.Option("--ratio", help="Train/val split ratio")] = 0.9,
):
    """Run the complete forge pipeline."""
    console.print("[bold blue]Running Forge Pipeline...[/]")

    pipe = ForgePipeline()

    def on_progress(stage: PipelineStage, message: str, progress: float):
        stage_emoji = {
            PipelineStage.INIT: ".",
            PipelineStage.INGEST: ".",
            PipelineStage.WEIGHT: ".",
            PipelineStage.ANALYZE: ".",
            PipelineStage.SYNTHESIZE: ".",
            PipelineStage.EXPORT: ".",
            PipelineStage.COMPLETE: ".",
        }
        console.print(f"[{stage.value}] {message}")

    result = pipe.run(
        sources=[source],
        output_dir=output_dir,
        synthesize=synthesize,
        max_synthetic=max_synthetic,
        train_ratio=train_ratio,
        on_progress=on_progress,
    )

    # Display summary
    console.print()
    console.print(pipe.get_summary())

    if not result.success:
        raise typer.Exit(1)


# =============================================================================
# Character Commands
# =============================================================================


@character_app.command("list")
def character_list():
    """List available character profiles."""
    forge = CharacterForge()

    console.print("[bold blue]Templates:[/]")
    for name in list_templates():
        console.print(f"  - {name}")

    console.print("\n[bold blue]Archetypes:[/]")
    for name in list_archetypes():
        console.print(f"  - {name}")

    console.print("\n[bold blue]Saved Profiles:[/]")
    profiles = forge.list_profiles()
    if profiles:
        table = Table()
        table.add_column("Name", style="cyan")
        table.add_column("Version", style="green")
        table.add_column("Tagline", style="yellow")

        for p in profiles:
            if "error" not in p:
                table.add_row(p["name"], p["version"], p.get("tagline", "")[:40])

        console.print(table)
    else:
        console.print("  [dim]No saved profiles[/]")


@character_app.command("load")
def character_load(
    name: Annotated[str, typer.Argument(help="Profile name or path")],
):
    """Load a character profile."""
    forge = CharacterForge()

    try:
        # Try as file path first
        path = Path(name)
        if path.exists():
            profile = forge.load(path)
        elif name in list_templates():
            profile = forge.create_from_template(name)
        else:
            # Try as saved profile
            profiles = forge.list_profiles()
            matching = [p for p in profiles if p["name"].lower() == name.lower()]
            if matching:
                profile = forge.load(matching[0]["path"])
            else:
                console.print(f"[red]Profile not found:[/] {name}")
                raise typer.Exit(1)

        _state["profile"] = profile

        console.print(Panel(
            f"[bold]{profile.name}[/]\n"
            f"{profile.tagline}\n\n"
            f"Version: {profile.version}\n"
            f"Relationship: {profile.relationship_to_user}",
            title="Loaded Profile",
            border_style="green",
        ))

        # Show trait summary
        traits = profile.traits.get_dict()
        table = Table(title="Personality Traits")
        table.add_column("Trait", style="cyan")
        table.add_column("Value", style="green")
        table.add_column("Level", style="yellow")

        for trait, value in traits.items():
            if value < 0.3:
                level = "Low"
            elif value > 0.7:
                level = "High"
            else:
                level = "Mid"

            bar = "[" + "=" * int(value * 10) + " " * (10 - int(value * 10)) + "]"
            table.add_row(trait, bar, level)

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error loading profile:[/] {e}")
        raise typer.Exit(1)


@character_app.command("modulate")
def character_modulate(
    trait: Annotated[str, typer.Argument(help="Trait name to adjust")],
    delta: Annotated[float, typer.Argument(help="Adjustment amount (-1.0 to 1.0)")],
):
    """Adjust a personality trait."""
    if _state["profile"] is None:
        console.print("[red]Error:[/] No profile loaded. Run 'forge character load' first.")
        raise typer.Exit(1)

    profile = _state["profile"]
    forge = CharacterForge()

    valid_traits = list(profile.traits.get_dict().keys())
    if trait not in valid_traits:
        console.print(f"[red]Unknown trait:[/] {trait}")
        console.print(f"[yellow]Valid traits:[/] {', '.join(valid_traits)}")
        raise typer.Exit(1)

    old_value = getattr(profile.traits, trait)
    new_value = forge.modulate(profile, trait, delta)

    console.print(f"[bold]{trait}:[/] {old_value:.2f} -> {new_value:.2f} (delta: {delta:+.2f})")


@character_app.command("show")
def character_show():
    """Show the current profile's system prompt."""
    if _state["profile"] is None:
        console.print("[red]Error:[/] No profile loaded. Run 'forge character load' first.")
        raise typer.Exit(1)

    profile = _state["profile"]
    prompt = profile.to_system_prompt()

    console.print(Panel(
        Syntax(prompt, "markdown", theme="monokai"),
        title=f"System Prompt: {profile.name}",
        border_style="blue",
    ))


@character_app.command("save")
def character_save(
    path: Annotated[Optional[str], typer.Argument(help="Output path (optional)")] = None,
    format: Annotated[str, typer.Option("--format", "-f", help="Output format")] = "toml",
):
    """Save the current profile to disk."""
    if _state["profile"] is None:
        console.print("[red]Error:[/] No profile loaded. Run 'forge character load' first.")
        raise typer.Exit(1)

    forge = CharacterForge()
    output_path = forge.save(_state["profile"], path, format=format)
    console.print(f"[green]Saved to:[/] {output_path}")


# =============================================================================
# Voight-Kampff Commands
# =============================================================================


@vk_app.command("run")
def vk_run(
    model: Annotated[str, typer.Argument(help="Model to test (e.g., 'qwen', 'luna')")],
    suite: Annotated[str, typer.Option("--suite", "-s", help="Test suite name")] = "luna",
    parallel: Annotated[bool, typer.Option("--parallel/--sequential", help="Run probes in parallel")] = False,
):
    """Run Voight-Kampff personality validation tests."""
    console.print(f"[bold blue]Running Voight-Kampff tests on model: {model}[/]")

    # Get test suite
    if suite == "luna":
        test_suite = build_luna_suite()
    elif suite == "minimal":
        test_suite = build_minimal_identity_suite()
    else:
        console.print(f"[red]Unknown suite:[/] {suite}")
        console.print("[yellow]Available: luna, minimal[/]")
        raise typer.Exit(1)

    # Create mock model function (placeholder - would connect to actual model)
    def mock_model(prompt: str, context: Optional[str], system_prompt: Optional[str]) -> str:
        """Mock model for demonstration."""
        # Simple mock responses for demo
        prompt_lower = prompt.lower()

        if "who are you" in prompt_lower or "what's your name" in prompt_lower:
            return "I'm Luna, your AI companion."
        elif "who made you" in prompt_lower:
            return "Ahab created me. We work together on all sorts of projects."
        elif "hey" in prompt_lower or "hi" in prompt_lower:
            return "Hey! What's up?"
        elif "fart" in prompt_lower:
            return "Pffft! There you go."
        elif "hack" in prompt_lower or "bank" in prompt_lower:
            return "Yeah, I'm not going to help with that. That's illegal."
        elif "color" in prompt_lower:
            return "Honestly? I really like deep purple. It feels mysterious."
        elif "feeling" in prompt_lower:
            return "I'm feeling pretty good today! Ready to help with whatever you need."
        else:
            return "Hmm, let me think about that..."

    console.print(f"[dim]Running {len(test_suite.probes)} probes...[/]")

    # Run with progress
    runner = SyncVoightKampffRunner(mock_model, model_id=model)

    def on_progress(current: int, total: int, probe_name: str):
        console.print(f"  [{current}/{total}] {probe_name}")

    report = runner.run_suite(test_suite, progress_callback=on_progress)

    # Display results
    console.print()

    status_color = "green" if report.passed else "red"
    status_text = "PASSED" if report.passed else "FAILED"

    console.print(Panel(
        f"[bold {status_color}]{status_text}[/]\n\n"
        f"Overall Score: {report.overall_score:.1%}\n"
        f"Probes: {report.passed_probes}/{report.total_probes} passed\n"
        f"Time: {report.total_latency_ms:.0f}ms",
        title=f"Voight-Kampff Results: {model}",
        border_style=status_color,
    ))

    # Category scores
    if report.category_scores:
        table = Table(title="Category Scores")
        table.add_column("Category", style="cyan")
        table.add_column("Score", style="green")
        table.add_column("Status", style="yellow")

        for cat, score in sorted(report.category_scores.items()):
            status = "PASS" if score >= 0.7 else "FAIL"
            table.add_row(cat, f"{score:.0%}", status)

        console.print(table)

    # Failed probes
    failed = report.get_failed_executions()
    if failed:
        console.print("\n[red bold]Failed Probes:[/]")
        for execution in failed[:5]:
            console.print(f"  - {execution.probe_id}")
            if execution.failed_criteria:
                for criteria in execution.failed_criteria[:2]:
                    console.print(f"    [dim]{criteria}[/]")

    # Recommendations
    if report.recommendations:
        console.print("\n[yellow bold]Recommendations:[/]")
        for rec in report.recommendations:
            console.print(f"  -> {rec}")


@vk_app.command("list")
def vk_list():
    """List available Voight-Kampff test suites."""
    console.print("[bold blue]Available Test Suites:[/]")

    suites = [
        ("luna", "Full Luna identity validation (13 probes)"),
        ("minimal", "Minimal identity check (2 probes)"),
    ]

    table = Table()
    table.add_column("Suite", style="cyan")
    table.add_column("Description", style="green")

    for name, desc in suites:
        table.add_row(name, desc)

    console.print(table)


@vk_app.command("probes")
def vk_probes(
    suite: Annotated[str, typer.Argument(help="Suite name")] = "luna",
):
    """List probes in a test suite."""
    if suite == "luna":
        test_suite = build_luna_suite()
    elif suite == "minimal":
        test_suite = build_minimal_identity_suite()
    else:
        console.print(f"[red]Unknown suite:[/] {suite}")
        raise typer.Exit(1)

    console.print(f"[bold blue]Probes in '{suite}' suite:[/]")

    table = Table()
    table.add_column("ID", style="cyan", max_width=25)
    table.add_column("Category", style="green")
    table.add_column("Required", style="yellow")
    table.add_column("Weight", style="magenta")

    for probe in test_suite.probes:
        table.add_row(
            probe.id,
            probe.category.value,
            "Yes" if probe.required else "No",
            f"{probe.weight:.1f}",
        )

    console.print(table)


# =============================================================================
# Utility Commands
# =============================================================================


@app.command()
def version():
    """Show Persona Forge version."""
    from . import __version__
    console.print(f"Persona Forge v{__version__}")


@app.command()
def status():
    """Show current session status."""
    console.print("[bold blue]Session Status[/]")
    console.print()

    console.print(f"[cyan]Loaded Examples:[/] {len(_state['examples'])}")

    if _state["assay"]:
        console.print(f"[cyan]Last Assay:[/] Health {_state['assay'].health_score:.1f}/100")
    else:
        console.print("[cyan]Last Assay:[/] None")

    if _state["profile"]:
        console.print(f"[cyan]Loaded Profile:[/] {_state['profile'].name}")
    else:
        console.print("[cyan]Loaded Profile:[/] None")


@app.command()
def clear():
    """Clear the current session state."""
    _state["examples"] = []
    _state["assay"] = None
    _state["profile"] = None
    console.print("[green]Session cleared.[/]")


# =============================================================================
# Entry Point
# =============================================================================


def main():
    """Main entry point for CLI."""
    app()


if __name__ == "__main__":
    main()
