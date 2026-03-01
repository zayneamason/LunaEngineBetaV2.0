# Luna Voice Path — Tool Bridge Requirements

**Date:** 2026-02-27
**From:** Architecture diagnostic session
**Visual Map:** `luna_voice_path_map.html` (in this directory)

---

## Core Problem

Luna voice app has **no tool bridge**. She's trapped in the database — she can read what's put in front of her during pre-fetch, but cannot request additional context mid-response. Single-pass completion with no tool-use loop.

## The Three Lunas

| Layer | What | Status in Voice |
|-------|------|----------------|
| **Director** | Personality, voice, decision-maker. Kernel + virtues + system prompt. | ✅ Present |
| **Engine** | Inference pipeline. Context assembly, tool orchestration. | ❌ Missing tool bridge |
| **Entity** | Memory footprint. 24k+ nodes, personality profile, conversation history. | ⚠️ Exists but unreachable |

## Current Flow (Broken)

```
Voice Input → Pre-fetch (single pass) → LLM Completion (no tools) → Output
                                              ↓
                                    "I don't know" (no way to look)
```

## Proposed Flow (Fixed)

```
Voice Input → Enhanced Pre-fetch (smart_fetch + aibrarian) → LLM Completion (WITH tools)
                                                                    ↓
                                                          Surrender Intercept
                                                          (detects "I don't know")
                                                                    ↓
                                                          Tool search → Re-generate
                                                                    ↓
                                                              Informed Output
```

## Tools Needed in Voice Path

| Priority | Tool | Status | What it does |
|----------|------|--------|-------------|
| P0 | `luna_smart_fetch` | EXISTS — wire to voice | Hybrid memory retrieval (FTS5 + vectors + graph) |
| P0 | `aibrarian_search` | EXISTS — wire to voice | Dataroom document search (keyword + semantic + hybrid) |
| P0 | `surrender_intercept` | NEW — build this | Detects "I don't know" in draft response → triggers tool search → re-generates |
| P1 | `memory_matrix_search` | EXISTS — wire to voice | Direct graph query for entities, relationships, facts |
| P1 | `luna_detect_context` | EXISTS — wire to voice | Full context assembly with auto_fetch |

## QA Assertion Added

```
Name: Knowledge Surrender Detection
ID: CUSTOM-CB2C01
Pattern: i don.t have (any|specific)? ?(information|memory|...) | tell me (more|a bit more) | ...
Severity: high
Target: response
```

This fires on the QA side. The surrender_intercept tool is the ACTION side — when this pattern is detected in a draft response, intercept before delivery, run tools, and re-generate.

## Key Insight

The Director (Luna's personality) is present and working. The Entity (her memories) exists and is rich. The Engine (inference pipeline) is the broken link — it's not giving the Director hands to reach into the Entity's knowledge. Fix the Engine, and the Director + Entity reconnect.
