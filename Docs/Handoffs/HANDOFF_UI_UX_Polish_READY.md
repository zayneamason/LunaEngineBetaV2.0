# HANDOFF: UI/UX Polish

Download the docx from Claude conversation.

## Tasks (in execution order)

1. **General layout audit** — flex: 1, overflow-y: auto, minHeight: 0 on all page containers
2. **Observatory layout** — specific fix for content cramming to top
3. **Markdown rendering** — react-markdown + remark-gfm + rehype-highlight in ChatPanel. Biggest visual impact.
4. **Nexus extraction** — move from Studio iframe to native Eclissi component. Copy nexus/ from Tools/Luna-Expression-Pipeline/diagnostic/src/nexus/ to frontend/src/nexus/. Gate dev elements behind debugMode.
5. **Chat accent element** — subtle dot + thin hairline border on assistant messages. Guardian-inspired. Color follows life_state.
6. **Debug toggle** — Settings > Display switch. Persists to frontend config. Controls badges, grounding stats, Nexus dev elements.
7. **Formatting presets** — Compact / Readable / Large in Display settings. Leverages existing --ec-font-scale CSS variable.

## Key Discovery
Studio (Expression, Engine Pipeline, Nexus, QA) is a **separate React app** at Tools/Luna-Expression-Pipeline/diagnostic/. Served via iframe at /studio. Nexus extraction means copying its nexus/ subdirectory into the main frontend and killing the iframe.

## Companion Handoffs
- V2: Build config, bootstrap identity, debug badges
- V3: Engine fixes, demo features (keys, preflight, jumpstart, reset)
- This: UI/UX polish
