# Bite 8 — MCP Tools for Engine Control

Add MCP tools for backend capabilities that have API endpoints but NO MCP tool coverage. Each tool is a thin async wrapper that hits the existing API endpoint via `engine_client.py` pattern (HTTP call → format response → return string).

## Tools to add

### Aperture Control
- `aperture_get` → GET `/api/aperture` — returns current aperture state (mode, thresholds, active collections)
- `aperture_set(mode, **params)` → POST `/api/aperture` — set aperture mode and parameters
- `aperture_reset` → POST `/api/aperture/reset` — reset to defaults
- `aperture_lock_in_status` → GET `/api/collections/lock-in` — returns lock-in levels for all collections

### Voice Control
- `voice_start` → POST `/voice/start` — start voice session
- `voice_stop` → POST `/voice/stop` — stop voice session
- `voice_status` → GET `/voice/status` — current voice state
- `voice_speak(text)` → POST `/voice/speak` — TTS output

### LLM Provider
- `llm_providers` → GET `/llm/providers` — list available providers
- `llm_switch_provider(provider)` → POST `/llm/provider` — switch active provider
- `llm_fallback_chain` → GET `/llm/fallback-chain` — current fallback order

### Consciousness
- `consciousness_state` → GET `/consciousness` — Luna's current state model

### Extraction
- `extraction_trigger` → POST `/extraction/trigger` — trigger extraction on recent conversation
- `extraction_stats` → GET `/extraction/stats` — extraction pipeline stats

## Implementation pattern

Follow the exact pattern in `engine_client.py`:
```python
async def aperture_get(self) -> dict:
    result = await _http_get("/api/aperture")
    if result:
        result["source"] = "api"
        return result
    return {"error": "Engine offline", "source": "unavailable"}
```

Register all tools in `src/luna_mcp/server.py` as `@mcp.tool()` functions.

Do NOT create new API endpoints. They already exist. Just create the MCP tool wrappers.
