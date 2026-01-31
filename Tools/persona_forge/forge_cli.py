#!/usr/bin/env python3
"""
Persona Forge CLI

Command-line interface for the Persona Forge training data pipeline.
Enhanced with personality monitoring capabilities.
"""

import sys
from pathlib import Path

# Add src to path for development
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from persona_forge.engine import Crucible, Assayer, DIRECTOR_PROFILE
from persona_forge.engine.personality_scorer import TARGET_PROFILE


def main():
    """Main CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Persona Forge - Training Data Command Center",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic assay
  python forge_cli.py assay /path/to/dataset.jsonl

  # Assay with personality analysis
  python forge_cli.py assay /path/to/dataset.jsonl --with-personality

  # Assay with personality visualizations
  python forge_cli.py assay /path/to/dataset.jsonl --with-personality --personality-viz

  # Target specific LLM
  python forge_cli.py assay /path/to/dataset.jsonl --with-personality --target-llm llama-3-8b-instruct

  # JSON output
  python forge_cli.py assay /path/to/dataset.jsonl --format json

  # List available LLM targets
  python forge_cli.py targets
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Assay command
    assay_parser = subparsers.add_parser("assay", help="Analyze a dataset")
    assay_parser.add_argument("path", type=str, help="Path to JSONL dataset")
    assay_parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format"
    )
    assay_parser.add_argument(
        "--with-personality",
        action="store_true",
        help="Include personality analysis (scores all examples)"
    )
    assay_parser.add_argument(
        "--personality-viz",
        action="store_true",
        help="Generate personality visualizations (requires --with-personality)"
    )
    assay_parser.add_argument(
        "--target-llm",
        type=str,
        default="qwen2.5-7b-instruct",
        help="Target LLM for personality baseline (default: qwen2.5-7b-instruct)"
    )
    assay_parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output directory for visualizations (default: current directory)"
    )

    # Load command (just load and show stats)
    load_parser = subparsers.add_parser("load", help="Load and show basic stats")
    load_parser.add_argument("path", type=str, help="Path to JSONL dataset")
    load_parser.add_argument(
        "--with-personality",
        action="store_true",
        help="Enable personality scoring during load"
    )

    # Targets command (list available LLM configurations)
    targets_parser = subparsers.add_parser(
        "targets",
        help="List available LLM target configurations"
    )

    # Viz command (iTerm2 inline graphics)
    viz_parser = subparsers.add_parser(
        "viz",
        help="Display personality visualization inline (iTerm2 only)"
    )
    viz_parser.add_argument("path", type=str, help="Path to JSONL dataset")
    viz_parser.add_argument(
        "--target-llm",
        type=str,
        default="qwen2.5-3b-instruct",
        help="Target LLM for comparison"
    )
    viz_parser.add_argument(
        "--chart",
        choices=["spider", "gauge", "bars", "all"],
        default="spider",
        help="Chart type (default: spider)"
    )

    args = parser.parse_args()

    if args.command == "assay":
        run_assay(args)
    elif args.command == "load":
        run_load(args)
    elif args.command == "targets":
        run_targets()
    elif args.command == "viz":
        run_viz(args)
    else:
        parser.print_help()


def run_load(args):
    """Load dataset and show basic stats."""
    enable_personality = getattr(args, 'with_personality', False)
    crucible = Crucible(enable_personality_scoring=enable_personality)

    print(f"Loading: {args.path}")
    if enable_personality:
        print("(personality scoring enabled)")

    examples = crucible.ingest_jsonl(Path(args.path))

    print(f"\n✓ Loaded {len(examples)} examples")

    # Quick stats
    stats = crucible.get_stats()
    print(f"\nLoad history:")
    for entry in stats["load_history"]:
        print(f"  - {entry['source']}: {entry['count']} examples")

    # Show personality scoring status
    if enable_personality:
        scored = sum(1 for e in examples if e.personality_scores)
        print(f"\nPersonality scored: {scored}/{len(examples)} examples")


def run_assay(args):
    """Run full dataset assay with optional personality analysis."""
    enable_personality = getattr(args, 'with_personality', False)
    generate_viz = getattr(args, 'personality_viz', False)
    target_llm = getattr(args, 'target_llm', 'qwen2.5-7b-instruct')
    output_dir = getattr(args, 'output_dir', None)
    output_format = args.format

    # Load target profile if specified
    personality_target = None
    if enable_personality and target_llm:
        try:
            from persona_forge.config.config_loader import ConfigLoader
            loader = ConfigLoader()
            personality_target = loader.get_personality_profile(target_llm)
            print(f"Target LLM: {target_llm}")
        except Exception as e:
            print(f"Warning: Could not load config for {target_llm}: {e}")
            print("Using default target profile")
            personality_target = TARGET_PROFILE

    # Create components
    crucible = Crucible(enable_personality_scoring=enable_personality)
    assayer = Assayer(
        target_profile=DIRECTOR_PROFILE,
        personality_target=personality_target,
    )

    print(f"Loading: {args.path}")
    if enable_personality:
        print("(personality scoring enabled)")

    examples = crucible.ingest_jsonl(Path(args.path))
    print(f"✓ Loaded {len(examples)} examples")

    print("\nAnalyzing...")
    assay = assayer.analyze(examples)

    if output_format == "json":
        import json
        print(json.dumps(assay.model_dump(), indent=2, default=str))
    else:
        print("\n" + assayer.format_report(assay))

    # Generate visualizations if requested
    if enable_personality and generate_viz:
        print("\nGenerating personality visualizations...")
        try:
            from persona_forge.visualization import generate_personality_visualizations
            output_path = Path(output_dir) if output_dir else Path.cwd()
            outputs = generate_personality_visualizations(
                examples,
                assay,
                target_llm,
                output_path
            )
            if outputs:
                print(f"\n✓ Visualizations saved to {output_path}")
                for name, path in outputs.items():
                    print(f"  - {name}: {path.name}")
            else:
                print("No visualizations generated (plotly may not be installed)")
        except ImportError as e:
            print(f"Warning: Could not generate visualizations: {e}")
            print("Install plotly with: pip install plotly")


def run_targets():
    """List available LLM target configurations."""
    try:
        from persona_forge.config.config_loader import ConfigLoader
        loader = ConfigLoader()
        llms = loader.list_llms()

        print("Available LLM Target Configurations:")
        print("=" * 60)

        for llm_name in llms:
            config = loader.get_config(llm_name)
            desc = config.get("description", "No description")
            base = config.get("base_personality", {})
            note = base.get("note", "")

            print(f"\n{llm_name}")
            print(f"  Model: {config['model_path']}")
            print(f"  Description: {desc}")
            if note:
                print(f"  Characteristics: {note}")

            # Show training focus
            focus = loader.compute_training_focus(llm_name)
            top_focus = sorted(focus.items(), key=lambda x: -x[1])[:3]
            if top_focus and top_focus[0][1] > 0:
                focus_str = ", ".join(f"{d} (+{g:.2f})" for d, g in top_focus if g > 0)
                print(f"  Training Focus: {focus_str}")

        print("\n" + "=" * 60)
        print(f"Use --target-llm <name> to select a configuration")

    except Exception as e:
        print(f"Error loading configurations: {e}")
        print("\nDefault targets available:")
        print("  - qwen2.5-7b-instruct (default)")
        print("  - qwen2.5-3b-instruct")
        print("  - llama-3-8b-instruct")
        print("  - mistral-7b-instruct")
        print("  - phi-3-mini-instruct")


def run_viz(args):
    """Display personality visualization inline in iTerm2."""
    from persona_forge.visualization.iterm_display import (
        is_iterm2,
        display_spider_chart,
        display_alignment_gauge,
        display_dimension_bars,
    )

    if not is_iterm2():
        print("This command requires iTerm2 for inline graphics.")
        print("Use --personality-viz with 'assay' command for HTML output instead:")
        print(f"  python forge_cli.py assay {args.path} --with-personality --personality-viz")
        return

    target_llm = getattr(args, 'target_llm', 'qwen2.5-3b-instruct')
    chart_type = getattr(args, 'chart', 'spider')

    # Load target profile
    try:
        from persona_forge.config.config_loader import ConfigLoader
        loader = ConfigLoader()
        target_profile = loader.get_personality_profile(target_llm)
    except Exception:
        target_profile = TARGET_PROFILE

    # Load and analyze dataset
    print(f"Loading: {args.path}")
    crucible = Crucible(enable_personality_scoring=True)
    examples = crucible.ingest_jsonl(Path(args.path))
    print(f"✓ Loaded {len(examples)} examples")

    print("Analyzing...")
    assayer = Assayer(personality_target=target_profile)
    assay = assayer.analyze(examples)

    profile = assay.personality_profile or {}
    alignment = assay.personality_alignment or 0.0

    print(f"\nPersonality Profile (vs {target_llm}):")
    print(f"Alignment: {alignment * 100:.1f}%\n")

    if chart_type in ("spider", "all"):
        display_spider_chart(
            profile,
            target_profile,
            title=f"Luna vs {target_llm}"
        )

    if chart_type in ("gauge", "all"):
        display_alignment_gauge(alignment, target_llm)

    if chart_type in ("bars", "all"):
        display_dimension_bars(profile, target_profile)


if __name__ == "__main__":
    main()
