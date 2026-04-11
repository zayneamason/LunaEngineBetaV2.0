# HANDOFF READY: Hai Dai Ambassador Build V2

The handoff document is at: `Docs/HANDOFF_Hai_Dai_Ambassador_Build_V2.docx`

Download from Claude conversation or copy from outputs.

## Quick Summary
- **Part A** (7 tasks): Critical bugs from V1 build session — port binding, env isolation, registry fix, first-run logic, hardcoded dataroom, settings filtering, debug badges/dev UI removal
- **Part B** (7 tasks): Build config — identity bootstrap, profile YAML v0.3.0, nexus extraction from studio, observatory enabled, system knowledge variant, orphan cleanup, wizard verification  
- **Part C**: Voice plugin architecture (deferrable to v0.4.0)

## Key Changes from V1
- pymupdf excluded from build (was 90% of build time)
- Observatory now ON
- Debug badges, grounding stats, delegation indicators, COMPRESSION badge all hidden via debug_mode: false
- Expression, Engine Pipeline, QA sub-tabs hidden in non-dev builds
- Nexus extracted as standalone page (not sub-tab of Studio)
- Settings sections filtered (no LunaFM, Network, Memory, Skills for ambassador)
- Factory reset endpoint added
- Fixed port (8000) instead of random ephemeral
- Environment variable isolation in launcher script
