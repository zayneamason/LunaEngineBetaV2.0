# LunaScript — Cognitive Signature System

## Contents

| File | Purpose |
|------|---------|
| `HANDOFF_LUNASCRIPT_COGNITIVE_SIGNATURE.md` | Full implementation spec for Claude Code |
| `lunascript_measurement_REFERENCE.py` | Working measurement system (ran against real corpus) |
| `lunascript_calibration_results.txt` | Calibration output from 1268 Luna responses |
| `LunaScript_Algorithm_Research_Spec.docx` | Algorithm candidates with tradeoff analysis |

## Quick Start for Claude Code

1. Read the HANDOFF first — it has exact file paths, line-level integration points, and build phases
2. The measurement script is a working reference — port its functions into `src/luna/lunascript/features.py` and `measurement.py`
3. The calibration results show real numbers from Luna's corpus — use these as validation targets
4. Build in phase order: Phase 1 (Measure) → Phase 2 (Sign) → Phase 3 (Learn) → Phase 4 (Memory Integration)

## Architecture Principle

LunaScript is additive. It wraps the existing delegation call. If it breaks, Luna works exactly as before.
Zero LLM calls. All mechanical cogs.
