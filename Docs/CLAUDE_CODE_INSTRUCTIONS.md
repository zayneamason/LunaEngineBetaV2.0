# Claude Code Build Instructions

## Two handoffs, one build sequence.

### Start here: Shared Turn Cache
**File:** `HANDOFF_SHARED_TURN_CACHE.md`

This goes first because everything else reads from it.

**Build order:**
1. **Phase 1** — Cache writer in `scribe.py`. This is the foundation. One YAML file, atomic writes, rotating snapshot (not a log).
2. **Phase 2** — Source tagging. Quick but critical — tag every inbound message with its origin surface (`eclissi`, `mcp`, `voice`, `guardian`). Phase 5 dedup won't work without this.
3. **Phase 3 + 4** — Can run in parallel once the cache is being written. Phase 3 wires expression pipeline to read the cache. Phase 4 enriches MCP context from it.
4. **Phase 5** — Broadcast deduplication. Suppresses shadow conversations from MCP calls while keeping the Scribe extraction path alive.

### Then: Eclissi Shell
**File:** `HANDOFF_ECLISSI_SHELL.md`

This is the frontend surface. Six phases building the unified desktop interface.

**Key dependency:** Phase 6 (wiring live data) reads from the Shared Turn Cache — so the cache handoff needs to land first.

**Build order:**
1. Shell chrome (header, 5-tab nav, grid layout)
2. Widget dock + right panel (9 diagnostic widgets)
3. Conversation spine (WebSocket chat)
4. T-shape knowledge panels (flanking exploration)
5. Voice mode (STT/TTS controls)
6. Wire live data feeds (depends on Shared Turn Cache being active)

### Reference prototype
The visual source of truth is `t_shape_eclissi_v3.html` — 615 lines of standalone HTML containing the complete design system, glass materials, all widget content, T-shape interactions, and voice mode. When in doubt about how something should look, open that file.

### Non-negotiables (both handoffs)
- **Sovereignty first** — offline-first, no cloud dependency
- **Inspectable** — YAML not JSON for cache, glass (transparent) design language for UI
- **Atomic** — temp file + rename for cache writes, never half-written
- **Source-tagged** — every message declares where it came from
- **Prototype is truth** — visual specs come from the HTML prototype, not guesswork
