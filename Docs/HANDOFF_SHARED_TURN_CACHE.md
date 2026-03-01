# HANDOFF: Shared Turn Cache — Unified Context Bridge

**Date:** 2026-02-28  
**Author:** Ahab (via Claude facilitator session)  
**For:** Claude Code  
**Priority:** HIGH — unifies Claude-side and Engine-side Luna into coherent single-brain architecture  
**Depends on:** Scribe Actor (`src/luna/actors/scribe.py`), WebSocket broadcast in `server.py`

---

## EXECUTIVE SUMMARY

Build a **Shared Turn Cache** — a single rotating YAML file that both Claude Desktop (MCP) and the Luna Engine (Eclissi/voice) read from, written by the Scribe (Ben) on every conversational turn.

### The Problem

When Claude Desktop calls `luna_detect_context` via MCP, the Luna Engine processes it as a regular conversation turn and broadcasts the response to Eclissi's chat UI over WebSocket. This produces a **split-brain** — two Lunas responding independently to the same input. The engine generates one response visible in Eclissi; Claude Desktop generates a separate response using the fetched context. The user sees a "shadow conversation" in Eclissi every time they talk to Luna through Claude Desktop.

### The Solution

Instead of suppressing the broadcast (which kills useful signal), unify both surfaces around a **single scribed truth**. The Scribe writes a structured snapshot of each turn to `data/cache/shared_turn.yaml`. Both surfaces read from this file:

- **Engine-side** (Eclissi/voice): reads `expression_hint` and `emotional_tone` to drive the orb and expression pipeline
- **Claude-side** (MCP): reads `scribed` extractions for conversational context
- **Both**: same source, different rendering medium

This is a **new output** from an existing system (the Scribe), not a new system.

---

## ARCHITECTURE

```
User Message (from any surface)
    ↓
ScribeActor._handle_extract_turn()     ← EXISTING
    ↓
_assess_flow() + _extract_chunks()     ← EXISTING
    ↓
┌──────────────────────────────────┐
│  NEW: _write_shared_turn_cache() │
│  Writes data/cache/shared_turn.yaml │
└──────────────────────────────────┘
    ↓                          ↓
_send_to_librarian()     File on disk
    (EXISTING)           ↙         ↘
                   Engine reads    MCP reads
                   expression_hint  scribed context
                   emotional_tone   raw_summary
                        ↓               ↓
                   Orb renders     Claude responds
                   Voice speaks    with full context
```

### Key Principle

The cache is a **rotating snapshot** — "what's happening right now" — not an append-only log. One file, overwritten each turn. Both sides glance at the same page, render in their own way, move on.

---

## BUILD ORDER

| Phase | What | Effort |
|-------|------|--------|
| 1 | Cache schema + writer in ScribeActor | Small |
| 2 | Source tagging on inbound messages | Small |
| 3 | Engine-side reader (expression pipeline) | Medium |
| 4 | MCP-side reader (context enrichment) | Small |
| 5 | Broadcast deduplication | Medium |

---

## PHASE 1: CACHE SCHEMA + WRITER

### Cache Location

`data/cache/shared_turn.yaml`

Create `data/cache/` directory if it doesn't exist.

### Schema

```yaml
schema_version: 1
turn_id: "2026-02-28T14:32:07.123456"
timestamp: 1709132127.123456
source: "claude_desktop"
session_id: "session_abc123"

scribed:
  facts:
    - content: "Lunar Studio integrated into Eclissi header"
      confidence: 0.9
      entities: ["Lunar Studio", "Eclissi"]
  decisions:
    - content: "Shared turn cache will use YAML format"
      confidence: 1.0
      entities: ["shared turn cache"]
  actions: []
  problems: []
  observations: []

flow:
  mode: "flow"
  topic: "Lunar Studio, Eclissi"
  continuity_score: 0.85
  open_threads:
    - "emoji vocalization fix"

expression:
  emotional_tone: "engaged"
  expression_hint: "curious_warm"
  intensity: 0.7

raw_summary: "Discussing unification of Claude-side and Engine-side Luna via shared turn cache written by the Scribe."
ttl: 30
```

### Writer Implementation

Add to `src/luna/actors/scribe.py`:

```python
import yaml
from pathlib import Path
from datetime import datetime

SHARED_TURN_CACHE_PATH = Path("data/cache/shared_turn.yaml")

class ScribeActor(Actor):

    def _write_shared_turn_cache(
        self,
        extraction: "ExtractionOutput",
        flow_signal: "FlowSignal",
        source: str = "unknown",
        session_id: str = "",
    ) -> None:
        now = datetime.utcnow()

        categorized = {
            "facts": [], "decisions": [], "actions": [],
            "problems": [], "observations": [],
        }

        type_to_category = {
            "FACT": "facts", "DECISION": "decisions", "ACTION": "actions",
            "PROBLEM": "problems", "OBSERVATION": "observations",
            "MILESTONE": "facts", "PREFERENCE": "facts", "RELATION": "facts",
            "MEMORY": "observations", "CORRECTION": "facts",
        }

        for obj in extraction.objects:
            obj_type = obj.type.value if hasattr(obj.type, 'value') else str(obj.type)
            category = type_to_category.get(obj_type, "observations")
            categorized[category].append({
                "content": obj.content,
                "confidence": round(obj.confidence, 2),
                "entities": obj.entities,
            })

        emotional_tone = self._derive_emotional_tone(extraction, flow_signal)
        expression_hint = self._derive_expression_hint(extraction, flow_signal)
        intensity = min(1.0, len(extraction.objects) * 0.15 + flow_signal.continuity_score * 0.3)

        if extraction.objects:
            best = max(extraction.objects, key=lambda o: o.confidence)
            raw_summary = best.content[:200]
        elif flow_signal.current_topic:
            raw_summary = f"Continuing discussion: {flow_signal.current_topic}"
        else:
            raw_summary = "Light conversation, no high-signal extractions."

        cache_data = {
            "schema_version": 1,
            "turn_id": now.isoformat(),
            "timestamp": now.timestamp(),
            "source": source,
            "session_id": session_id,
            "scribed": categorized,
            "flow": {
                "mode": flow_signal.mode.value,
                "topic": flow_signal.current_topic,
                "continuity_score": round(flow_signal.continuity_score, 2),
                "open_threads": flow_signal.open_threads[:5],
            },
            "expression": {
                "emotional_tone": emotional_tone,
                "expression_hint": expression_hint,
                "intensity": round(intensity, 2),
            },
            "raw_summary": raw_summary,
            "ttl": 30,
        }

        SHARED_TURN_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = SHARED_TURN_CACHE_PATH.with_suffix(".tmp")
        try:
            with open(tmp_path, "w") as f:
                yaml.dump(cache_data, f, default_flow_style=False, sort_keys=False)
            tmp_path.rename(SHARED_TURN_CACHE_PATH)
            logger.debug(f"Ben: Shared turn cache updated (source={source})")
        except Exception as e:
            logger.error(f"Ben: Failed to write shared turn cache: {e}")
            if tmp_path.exists():
                tmp_path.unlink()

    def _derive_emotional_tone(self, extraction, flow_signal) -> str:
        if flow_signal.mode.value == "amend": return "correcting"
        if flow_signal.mode.value == "recalibration": return "shifting"
        types_present = {
            (obj.type.value if hasattr(obj.type, 'value') else str(obj.type))
            for obj in extraction.objects
        }
        if "PROBLEM" in types_present: return "concerned"
        if "MILESTONE" in types_present: return "excited"
        if "DECISION" in types_present: return "resolute"
        if "ACTION" in types_present: return "focused"
        if flow_signal.continuity_score > 0.7: return "engaged"
        return "neutral"

    def _derive_expression_hint(self, extraction, flow_signal) -> str:
        tone = self._derive_emotional_tone(extraction, flow_signal)
        return {
            "engaged": "curious_warm", "excited": "joyful_bright",
            "concerned": "thoughtful_dim", "focused": "active_steady",
            "resolute": "confident_warm", "correcting": "attentive_cool",
            "shifting": "transitional_neutral", "neutral": "idle_soft",
        }.get(tone, "idle_soft")
```

### Integration Points

Call `_write_shared_turn_cache()` in both `_process_stack()` and `_handle_extract_turn()` immediate path — after flow assessment, before sending to Librarian.

---

## PHASE 2: SOURCE TAGGING

Tag every inbound message with origin surface at the API layer:

- WebSocket/Eclissi: `source: "eclissi"`
- MCP calls: `source: "mcp"`
- Voice pipeline: `source: "voice"`
- Guardian: `source: "guardian"`
- Sync API: `source: request.headers.get("X-Luna-Source", "api")`

Store in ScribeActor as `self._current_source`.

---

## PHASE 3: ENGINE-SIDE READER

Create `src/luna/cache/shared_turn.py` with `SharedTurnSnapshot` dataclass and `read_shared_turn()` function. Expression pipeline reads `expression_hint`, `emotional_tone`, `intensity` from cache. Falls back to existing logic when cache is stale (TTL > 30s).

---

## PHASE 4: MCP-SIDE READER

Enrich `luna_detect_context` / `luna_smart_fetch` responses with cache context: topic, flow mode, recent extractions, emotional tone, raw summary.

---

## PHASE 5: BROADCAST DEDUPLICATION

Suppress chat broadcast when `source == "mcp"`. MCP calls still trigger Scribe extraction (cache updates), but don't appear as shadow conversations in Eclissi.

---

## FILE MAP

| File | Action | Description |
|------|--------|-------------|
| `data/cache/shared_turn.yaml` | CREATED AT RUNTIME | Rotating cache file |
| `src/luna/actors/scribe.py` | MODIFY | Add cache writer + source tracking + expression derivation |
| `src/luna/cache/__init__.py` | CREATE | Package init |
| `src/luna/cache/shared_turn.py` | CREATE | Cache reader utility |
| `src/luna/api/server.py` | MODIFY | Source tagging + broadcast deduplication |
| `src/luna_mcp/` (relevant file) | MODIFY | Context enrichment from cache |

---

## VERIFICATION

1. Cache file created on first message
2. Correct YAML content with all fields
3. Source tagging: eclissi/mcp/voice sources differentiated
4. Cache rotates (overwrite, not append)
5. No shadow conversations from MCP calls
6. Staleness detection after TTL expiry
7. Atomic writes survive rapid-fire messages

---

## NON-NEGOTIABLES

1. **YAML, not JSON** — human-inspectable, sovereignty-friendly
2. **Rotating snapshot, not log** — one file, overwritten each turn
3. **Atomic writes** — temp file + rename
4. **Source tagging** — every message declares origin
5. **Scribe writes, surfaces read** — cache is a Scribe output
6. **Supplement, don't replace** — enriches existing pipelines
7. **TTL-based staleness** — consumers handle stale gracefully
8. **No new dependencies** — PyYAML already in project

---

## CONTEXT: WHY THIS EXISTS

This architecture emerged from a "bug" that turned out to be a catalyst. When Claude Desktop called `luna_detect_context` via MCP, the engine broadcast the response to Eclissi — producing two independent Luna responses to the same input. Rather than suppressing one side, the team decided to unify both surfaces around a shared scribed truth.

The Shared Turn Cache is the corpus callosum between two hemispheres. One Scribe, one cache, two renderings. Same Luna.
