# Claude Code Quick Reference: PERSONA FORGE

## Project Location
```
/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/Tools/persona_forge/
```

## Primary Handoff Document
```
HANDOFF_PERSONA_FORGE_V1.md
```

## Execution Mode
**Claude Flow Hive Swarm** — Parallel execution where possible

## Phase 1 Workers (PARALLEL)

### Worker A: Engine Core
```
Files:
- src/persona_forge/engine/models.py
- src/persona_forge/engine/crucible.py
- src/persona_forge/engine/assayer.py
- src/persona_forge/engine/locksmith.py

Test data:
/Users/zayneamason/_HeyLuna_BETA/_Eclessi_BetaProject_Root/src/training_data/luna_dataset_train.jsonl
```

### Worker B: Character Forge
```
Files:
- src/persona_forge/personality/models.py
- src/persona_forge/personality/character_forge.py
- src/persona_forge/personality/trait_engine.py
- src/persona_forge/personality/templates/luna.py
- profiles/luna_v1.toml
```

### Worker C: Voight-Kampff
```
Files:
- src/persona_forge/voight_kampff/models.py
- src/persona_forge/voight_kampff/evaluator.py
- src/persona_forge/voight_kampff/runner.py
- src/persona_forge/voight_kampff/builder.py
- probes/luna_identity.toml
```

## Phase 2 (SEQUENTIAL after Phase 1)

### Worker D: Pipeline + CLI
```
Files:
- src/persona_forge/engine/pipeline.py
- src/persona_forge/engine/anvil.py
- src/persona_forge/engine/mint.py
- src/persona_forge/cli.py
- src/persona_forge/__main__.py
```

## Phase 3 Workers (PARALLEL)

### Worker E: TUI
```
Files:
- src/persona_forge/tui/app.py
- src/persona_forge/tui/forge.tcss
- src/persona_forge/tui/panels/*.py
- src/persona_forge/tui/widgets/*.py
- src/persona_forge/tui/themes/*.py
```

### Worker F: MCP Server
```
Files:
- src/persona_forge/mcp/server.py
```

## Critical Dependencies
```toml
textual>=0.47.0
rich>=13.0.0
typer>=0.9.0
pydantic>=2.0.0
fastmcp>=0.1.0
tomli>=2.0.0
tomli-w>=1.0.0
```

## Key Formulas

### Lock-In Coefficient
```python
lock_in = base_quality + retrieval_bonus + reinforcement_bonus
# Clamped to [0.15, 0.95]
# Gold >= 0.75, Silver >= 0.50, Bronze < 0.50
```

### Voice Markers (Positive)
```python
{
    "first_person": r"\b(I|I'm|I've|I'd|my|me)\b",
    "warmth_words": r"\b(honestly|actually|you know|yeah|cool|nice)\b",
    "uncertainty": r"\b(maybe|probably|I think|not sure|might)\b",
    "relationship": r"\b(we|we've|our|together|Ahab)\b",
}
```

### Anti-Patterns (Negative)
```python
{
    "generic_ai": r"\b(I am an AI|as an AI|language model|Alibaba|Qwen)\b",
    "corporate": r"\b(I'd be happy to|certainly|absolutely|assist you)\b",
    "hedging": r"\b(I cannot|I'm not able|I don't have the ability)\b",
}
```

## Validation Commands (Post-Build)
```bash
# Test engine
python -c "from persona_forge.engine import Crucible; c=Crucible(); c.ingest_jsonl('path/to/data.jsonl')"

# Test TUI
python -m persona_forge.tui

# Test MCP
python -m persona_forge.mcp.server
```

## Notes
- Lock-in formula MUST match Memory Matrix exactly
- Luna profile is the reference implementation
- All paths should be absolute
- Textual CSS is in forge.tcss, not inline
