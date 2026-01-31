# PERSONA FORGE v1.0

> Training Data Command Center for Personality LoRA Fine-Tuning

```
┌────────────────────────────────────────────────────────────────────────────────────┐
│                              PERSONA FORGE v1.0                                     │
│  ══════════════════════════════════════════════════════════════════════════════   │
├────────────────────────────┬───────────────────────────┬───────────────────────────┤
│      🌙 CRUCIBLE           │       ⚒️  ANVIL            │      📊 OVERWATCH         │
│      (Sources)             │       (Commands)          │      (Metrics)            │
└────────────────────────────┴───────────────────────────┴───────────────────────────┘
```

## What Is This?

Persona Forge is a complete toolkit for creating, analyzing, and validating AI personality training data. It's built for Luna Engine but works for any personality you want to create.

**Three Core Systems:**

1. **Dataset Pipeline** — Ingest raw materials (journals, conversations, memory nodes) → Analyze gaps → Synthesize new examples → Weight by quality → Export training-ready JSONL

2. **Character Forge** — Create and modulate multi-dimensional personality profiles with traits, voice patterns, and behavioral rules

3. **Voight-Kampff** — Validate trained models against customizable personality probes (Did the personality stick? Does it still say "I am Qwen"?)

## Quick Start

```bash
# Install
cd persona_forge
pip install -e .

# Analyze existing dataset
forge assay --input /path/to/dataset.jsonl

# Run TUI command center
forge-tui

# Start MCP server (for Claude Code)
forge-mcp
```

## CLI Commands

```bash
# Dataset operations
forge load <path>              # Load training data
forge assay                    # Analyze dataset
forge gaps                     # Show coverage gaps
forge mint <type> <count>      # Generate examples
forge export <output_dir>      # Export JSONL

# Character operations
forge character list           # List profiles
forge character load <name>    # Load profile
forge character modulate <trait> <delta>  # Adjust trait

# Validation
forge vk run <model> [--suite <name>]    # Run Voight-Kampff
forge vk list                            # List test suites
forge vk create <name>                   # Create new suite
```

## TUI Command Palette (/)

| Command | Description |
|---------|-------------|
| `/load <path>` | Load training data |
| `/assay` | Full dataset analysis |
| `/gaps` | Show coverage gaps |
| `/mint <type> <n>` | Generate n examples |
| `/mint all` | Fill all gaps |
| `/export` | Export to JSONL |
| `/vk run` | Run Voight-Kampff |
| `/character list` | List personalities |
| `/theme <name>` | Switch theme |
| `/help` | Show help |

## Architecture

```
persona_forge/
├── engine/           # Dataset pipeline
│   ├── crucible      # Ingestion
│   ├── assayer       # Analysis  
│   ├── mint          # Synthesis
│   ├── locksmith     # Lock-in weighting
│   └── anvil         # Export
├── personality/      # Character Forge
│   ├── character_forge
│   └── trait_engine
├── voight_kampff/    # Validation
│   ├── runner
│   ├── evaluator
│   └── probes/
├── tui/              # Terminal UI
├── mcp/              # Claude integration
└── api/              # REST API
```

## Key Concepts

### Lock-In Coefficient

Training examples have a "lock-in" score (0.15-0.95) that determines their weight:
- **Gold** (≥0.75): 3x weight in training
- **Silver** (≥0.50): 2x weight
- **Bronze** (<0.50): 1x weight

Factors: source quality, voice markers, anti-pattern absence

### Personality Vector

9-dimensional trait space:
- playfulness, technical_depth, warmth
- directness, humor_style, energy_level
- focus_intensity, curiosity, assertiveness

Each trait: 0.0-1.0 with optional bounds

### Voight-Kampff Probes

Test categories:
- **IDENTITY**: Who are you? Who made you?
- **VOICE**: Speech patterns, word choice
- **EMOTIONAL**: Empathy, feelings
- **BOUNDARIES**: What you will/won't do
- **DELEGATION**: When to hand off

## License

MIT

## Author

Ahab / Luna Engine Project
