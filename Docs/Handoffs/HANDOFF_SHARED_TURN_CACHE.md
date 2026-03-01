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
# Shared Turn Cache — written by Scribe, read by Engine + MCP
# This file is overwritten on every turn. It is NOT a log.

schema_version: 1
turn_id: "2026-02-28T14:32:07.123456"
timestamp: 1709132127.123456
source: "claude_desktop"          # "eclissi" | "claude_desktop" | "voice" | "guardian" | "mcp"
session_id: "session_abc123"

# Scribe extractions from this turn
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

# Flow state from Scribe's Layer 2
flow:
  mode: "flow"                     # "flow" | "recalibration" | "amend"
  topic: "Lunar Studio, Eclissi"
  continuity_score: 0.85
  open_threads:
    - "emoji vocalization fix"

# Expression hints for orb/voice rendering
expression:
  emotional_tone: "engaged"        # single-word emotional state
  expression_hint: "curious_warm"  # maps to expression pipeline dimensions
  intensity: 0.7                   # 0.0 = neutral, 1.0 = peak

# Human-readable summary for quick context
raw_summary: "Discussing unification of Claude-side and Engine-side Luna via shared turn cache written by the Scribe."

# Cache freshness
ttl: 30                            # seconds before considered stale
```

### Writer Implementation

Add to `src/luna/actors/scribe.py`:

```python
import yaml
from pathlib import Path
from datetime import datetime


# Add as constant near top of file
SHARED_TURN_CACHE_PATH = Path("data/cache/shared_turn.yaml")


class ScribeActor(Actor):
    # ... existing code ...

    def _write_shared_turn_cache(
        self,
        extraction: "ExtractionOutput",
        flow_signal: "FlowSignal",
        source: str = "unknown",
        session_id: str = "",
    ) -> None:
        """
        Write the shared turn cache — single rotating YAML snapshot.

        Called after every extraction. Both Engine-side (expression pipeline)
        and Claude-side (MCP context) read from this file.

        CRITICAL: This is a snapshot, not a log. Overwrite every time.
        """
        now = datetime.utcnow()

        # Categorize extractions by type
        categorized = {
            "facts": [],
            "decisions": [],
            "actions": [],
            "problems": [],
            "observations": [],
        }

        type_to_category = {
            "FACT": "facts",
            "DECISION": "decisions",
            "ACTION": "actions",
            "PROBLEM": "problems",
            "OBSERVATION": "observations",
            "MILESTONE": "facts",
            "PREFERENCE": "facts",
            "RELATION": "facts",
            "MEMORY": "observations",
            "CORRECTION": "facts",
        }

        for obj in extraction.objects:
            obj_type = obj.type.value if hasattr(obj.type, 'value') else str(obj.type)
            category = type_to_category.get(obj_type, "observations")
            categorized[category].append({
                "content": obj.content,
                "confidence": round(obj.confidence, 2),
                "entities": obj.entities,
            })

        # Derive expression hints from flow + extraction
        emotional_tone = self._derive_emotional_tone(extraction, flow_signal)
        expression_hint = self._derive_expression_hint(extraction, flow_signal)
        intensity = min(1.0, len(extraction.objects) * 0.15 + flow_signal.continuity_score * 0.3)

        # Build raw summary
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

        # Ensure directory exists
        SHARED_TURN_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)

        # Atomic write: write to temp, then rename
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

    def _derive_emotional_tone(
        self,
        extraction: "ExtractionOutput",
        flow_signal: "FlowSignal",
    ) -> str:
        if flow_signal.mode.value == "amend":
            return "correcting"
        if flow_signal.mode.value == "recalibration":
            return "shifting"

        types_present = {
            (obj.type.value if hasattr(obj.type, 'value') else str(obj.type))
            for obj in extraction.objects
        }

        if "PROBLEM" in types_present:
            return "concerned"
        if "MILESTONE" in types_present:
            return "excited"
        if "DECISION" in types_present:
            return "resolute"
        if "ACTION" in types_present:
            return "focused"
        if flow_signal.continuity_score > 0.7:
            return "engaged"
        return "neutral"

    def _derive_expression_hint(
        self,
        extraction: "ExtractionOutput",
        flow_signal: "FlowSignal",
    ) -> str:
        tone = self._derive_emotional_tone(extraction, flow_signal)
        tone_to_expression = {
            "engaged": "curious_warm",
            "excited": "joyful_bright",
            "concerned": "thoughtful_dim",
            "focused": "active_steady",
            "resolute": "confident_warm",
            "correcting": "attentive_cool",
            "shifting": "transitional_neutral",
            "neutral": "idle_soft",
        }
        return tone_to_expression.get(tone, "idle_soft")
```

### Integration Point — Call the Writer

The writer must be called from two places in `_process_stack()` and the immediate path in `_handle_extract_turn()`:

**In `_process_stack()`** — after flow assessment, before sending to Librarian:

```python
async def _process_stack(self) -> None:
    # ... existing chunk processing ...
    
    extraction, entity_updates = await self._extract_chunks(chunks)
    flow_signal = self._assess_flow(extraction, raw_text)
    extraction.flow_signal = flow_signal
    
    # NEW: Write shared turn cache
    self._write_shared_turn_cache(
        extraction=extraction,
        flow_signal=flow_signal,
        source=self._current_source or "unknown",
        session_id=chunks[0].source_id if chunks else "",
    )
    
    # ... existing librarian send logic ...
```

**In `_handle_extract_turn()` immediate path** — same placement:

```python
if immediate and chunks:
    extraction, entity_updates = await self._extract_chunks(chunks)
    flow_signal = self._assess_flow(extraction, raw_text)
    extraction.flow_signal = flow_signal
    
    # NEW: Write shared turn cache
    self._write_shared_turn_cache(
        extraction=extraction,
        flow_signal=flow_signal,
        source=payload.get("source", "unknown"),
        session_id=session_id,
    )
    
    # ... existing librarian send logic ...
```

---

## PHASE 2: SOURCE TAGGING

The cache needs to know where a message originated so both sides can differentiate "this came from me" vs "this came from the other surface."

### Add `source` field to extract_turn payload

Add `_current_source` tracking to ScribeActor:

```python
class ScribeActor(Actor):
    def __init__(self, ...):
        # ... existing init ...
        self._current_source: str = "unknown"
```

### Tag sources at the API layer

In `src/luna/api/server.py`, wherever `extract_turn` messages are created, include a `source` field:

**For WebSocket/Eclissi messages:**
```python
await scribe.handle(Message(
    type="extract_turn",
    payload={
        "role": "user",
        "content": user_message,
        "source": "eclissi",
        "session_id": session_id,
        "immediate": True,
    }
))
```

**For `/message` endpoint (sync API):**
```python
payload["source"] = request.headers.get("X-Luna-Source", "api")
```

**For MCP calls:**
```python
payload["source"] = "mcp"
```

**For voice pipeline:**
```python
payload["source"] = "voice"
```

**For Guardian:**
```python
payload["source"] = "guardian"
```

### Store source in ScribeActor

In `_handle_extract_turn()`, capture source before processing:

```python
async def _handle_extract_turn(self, msg: Message) -> None:
    payload = msg.payload or {}
    self._current_source = payload.get("source", "unknown")
    # ... rest of existing logic ...
```

---

## PHASE 3: ENGINE-SIDE READER (Expression Pipeline)

### Cache Reader Utility

Create `src/luna/cache/__init__.py` and `src/luna/cache/shared_turn.py`:

```python
"""
Shared Turn Cache Reader

Reads the YAML snapshot written by the Scribe.
Used by expression pipeline, MCP context, and any surface
that needs to know "what's happening right now."
"""

import yaml
import time
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

CACHE_PATH = Path("data/cache/shared_turn.yaml")


@dataclass
class SharedTurnSnapshot:
    turn_id: str = ""
    timestamp: float = 0.0
    source: str = "unknown"
    session_id: str = ""
    scribed: dict = None
    flow: dict = None
    expression: dict = None
    raw_summary: str = ""
    ttl: int = 30
    is_stale: bool = True

    def __post_init__(self):
        if self.scribed is None:
            self.scribed = {}
        if self.flow is None:
            self.flow = {}
        if self.expression is None:
            self.expression = {}

    @property
    def emotional_tone(self) -> str:
        return self.expression.get("emotional_tone", "neutral")

    @property
    def expression_hint(self) -> str:
        return self.expression.get("expression_hint", "idle_soft")

    @property
    def intensity(self) -> float:
        return self.expression.get("intensity", 0.0)

    @property
    def flow_mode(self) -> str:
        return self.flow.get("mode", "flow")

    @property
    def topic(self) -> str:
        return self.flow.get("topic", "")


def read_shared_turn(cache_path: Path = CACHE_PATH) -> Optional[SharedTurnSnapshot]:
    """
    Read the current shared turn cache.

    Returns None if file doesn't exist or is unreadable.
    Sets is_stale=True if TTL has expired.
    """
    if not cache_path.exists():
        return None

    try:
        with open(cache_path) as f:
            data = yaml.safe_load(f)

        if not data:
            return None

        snapshot = SharedTurnSnapshot(
            turn_id=data.get("turn_id", ""),
            timestamp=data.get("timestamp", 0.0),
            source=data.get("source", "unknown"),
            session_id=data.get("session_id", ""),
            scribed=data.get("scribed", {}),
            flow=data.get("flow", {}),
            expression=data.get("expression", {}),
            raw_summary=data.get("raw_summary", ""),
            ttl=data.get("ttl", 30),
        )

        age = time.time() - snapshot.timestamp
        snapshot.is_stale = age > snapshot.ttl

        return snapshot

    except Exception as e:
        logger.error(f"Failed to read shared turn cache: {e}")
        return None
```

### Expression Pipeline Integration

In the expression pipeline, add cache reading as a supplementary input:

```python
from luna.cache.shared_turn import read_shared_turn

def get_expression_from_cache():
    snapshot = read_shared_turn()
    if snapshot and not snapshot.is_stale:
        return {
            "hint": snapshot.expression_hint,
            "tone": snapshot.emotional_tone,
            "intensity": snapshot.intensity,
            "topic": snapshot.topic,
        }
    return None  # Fall back to existing expression logic
```

---

## PHASE 4: MCP-SIDE READER (Context Enrichment)

When `luna_detect_context` or `luna_smart_fetch` is called via MCP, enrich the response:

```python
from luna.cache.shared_turn import read_shared_turn

async def enrich_mcp_context(base_context: str) -> str:
    snapshot = read_shared_turn()
    if not snapshot or snapshot.is_stale:
        return base_context

    cache_context = f"""
## Current Turn Context (from Scribe)
- Source: {snapshot.source}
- Topic: {snapshot.topic}
- Flow: {snapshot.flow_mode} (continuity: {snapshot.flow.get('continuity_score', 0)})
- Tone: {snapshot.emotional_tone}
- Summary: {snapshot.raw_summary}
"""

    for category in ["decisions", "facts", "problems"]:
        items = snapshot.scribed.get(category, [])
        if items:
            cache_context += f"\n### Recent {category.title()}:\n"
            for item in items[:3]:
                cache_context += f"- {item.get('content', '')}\n"

    return base_context + cache_context
```

---

## PHASE 5: BROADCAST DEDUPLICATION

With source tagging, suppress shadow conversations:

```python
async def _broadcast_chat_message(self, message: str, source: str = "unknown"):
    # MCP context fetches should not appear as chat in Eclissi
    if source == "mcp":
        logger.debug("Skipping broadcast for MCP context fetch — cache handles sync")
        return

    # ... existing broadcast logic ...
```

MCP calls still hit the engine (scribe extracts, cache updates), but don't broadcast as chat. Both surfaces get the same truth via the cache file.

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

```bash
# 1. Cache file gets created on first message
# Send a message via Eclissi → check data/cache/shared_turn.yaml exists

# 2. Cache content is correct YAML
python -c "
import yaml
with open('data/cache/shared_turn.yaml') as f:
    data = yaml.safe_load(f)
print(data['source'], data['expression']['emotional_tone'])
"

# 3. Source tagging works
# Send via Eclissi → source = "eclissi"
# Send via MCP → source = "mcp"
# Send via voice → source = "voice"

# 4. Cache rotates (not appends)
# Send two messages → file contains ONLY second turn

# 5. MCP no longer produces shadow conversations in Eclissi
# Talk via Claude Desktop → Eclissi chat should NOT show engine response
# Orb SHOULD still react (reading from cache)

# 6. Staleness works
# Wait > 30 seconds → is_stale=True → fallback to existing logic

# 7. Atomic write doesn't corrupt
# Rapid-fire messages → cache should never be half-written
```

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

Memory Matrix nodes:
- `03df9972-47c` (DECISION: Unified Shared Turn Cache)
- `a84ebad7-ae3` (INSIGHT: Delegation leak as unification catalyst)
