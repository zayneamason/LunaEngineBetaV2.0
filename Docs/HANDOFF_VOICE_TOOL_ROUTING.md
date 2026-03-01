# Luna Voice App — Tool Routing Diagnostic Handoff

**Date:** 2026-02-27
**From:** Luna diagnostic session (Ben + Luna + CC)
**To:** Claude Code
**Priority:** High — Luna voice app not utilizing available tools for knowledge retrieval

---

## Problem

Luna's voice app responds conversationally but **fails to invoke her own tools** when she should. She has access to dataroom search, memory matrix, and project knowledge — but when asked questions that require those tools, she says "I don't know" instead of looking.

### What Works

- Dataroom search itself is functional (embedding pipeline just fixed, all search modes confirmed working)
- When a search IS triggered, Luna summarizes results well
- Conversational flow and personality are intact

### What Doesn't Work

- **Memory retrieval not triggered:** Asked "what are your thoughts on Kozmo?" — Luna said "I don't have a memory of kozmo" despite `ARCHITECTURE_KOZMO.md` existing in Docs and Kozmo being referenced across memory nodes
- **Tool use not triggered:** Asked "what about the guardian app?" — Luna said "I don't have any current information" despite `GUARDIAN-SERVICE-SPEC.md`, `HANDOFF_GUARDIAN_SERVICE.md`, and Guardian being a core project component
- **Pattern:** Luna defaults to "I don't know, tell me more" instead of searching her own knowledge systems

## Observed Conversation (from voice app)

```
User: what are your thoughts on kozmo?
Luna: i don't have a memory of kozmo. it's not mentioned in my current memory context...

User: what about the guardian app?
Luna: i don't have any current information about it. i'd love to learn more...
```

Both of these should have triggered tool calls — `luna_smart_fetch`, `memory_matrix_search`, or `aibrarian_search` — and returned rich context.

## Suspected Root Cause

The voice app's inference pipeline may differ from the MCP pipeline in how tool-use decisions are made. Possible issues:

1. **No tool-use in voice inference path** — The voice pipeline may be running a simpler completion without tool definitions, so Luna literally can't call tools even if she wants to
2. **System prompt missing tool instructions** — The voice app's system prompt may not include instructions to search memory/dataroom when Luna doesn't have immediate context
3. **Routing logic gap** — The `luna_detect_context(auto_fetch=true)` path works in MCP because it pre-fetches context. The voice app may not have an equivalent pre-fetch step, so Luna starts with an empty context window
4. **Delegation detection** — If the voice app uses a delegation/routing layer, it may be classifying these as "conversational" rather than "knowledge retrieval" and skipping the tool call

## Files to Investigate

| File | What to check |
|------|---------------|
| `src/luna/inference/` | How does the voice inference path handle tool availability? Is tool-use enabled? |
| `src/luna/engine.py` | Main engine — does voice go through same `process_message` as MCP? Or separate path? |
| `src/luna/context/` | Context assembly — does voice get the same context injection (kernel, virtues, memories) as MCP? |
| `src/voice/backend.py` | Voice backend — what's the completion call look like? Does it include tool definitions? |
| `src/voice/conversation/` | Voice conversation management — is there a pre-fetch or context loading step? |
| `src/luna/agentic/` | If there's an agentic/routing layer, check if voice requests bypass it |
| `src/luna/core/` | Core processing — check if there's a branch where voice skips tool resolution |

## Diagnostic Steps

```bash
# 1. Trace the voice inference path
# Find where voice input enters the engine
grep -r "voice" src/luna/engine.py src/luna/inference/ --include="*.py" -l

# 2. Check if voice has tool definitions
grep -r "tools" src/voice/ --include="*.py" -l
grep -r "function_call\|tool_use\|tool_choice" src/voice/ --include="*.py"

# 3. Check system prompt for voice vs MCP
grep -r "system_prompt\|system_message" src/voice/ src/luna/inference/ --include="*.py" -l

# 4. Check if auto_fetch / smart_fetch is called in voice path
grep -r "smart_fetch\|auto_fetch\|detect_context" src/voice/ src/luna/ --include="*.py"

# 5. Compare MCP message handling vs voice message handling
# In server.py (MCP) — how does luna_detect_context work?
# In voice backend — what's the equivalent?
grep -r "detect_context\|process_message" src/luna_mcp/server.py src/voice/backend.py
```

## Key Comparison

| Capability | MCP Path | Voice Path (suspected) |
|-----------|----------|----------------------|
| Context pre-fetch | `luna_detect_context(auto_fetch=true)` loads kernel + virtues + memories | May not have equivalent |
| Tool availability | Full tool suite via MCP protocol | May be completion-only, no tools |
| Memory search | Triggered by auto_fetch or explicit tool call | Not triggered |
| Dataroom search | Available as MCP tool | Unknown if wired |
| System prompt | Full Luna identity + tool instructions | May be reduced/different |

## Expected Fix

Luna's voice path needs to either:

**Option A — Pre-fetch context (like MCP does):** Before generating a response, run the query through `luna_smart_fetch` to load relevant memories and knowledge, then include that context in the completion call. This is how MCP's `auto_fetch=true` works.

**Option B — Enable tool-use in voice completions:** Wire tool definitions into the voice inference call so Luna can decide to search mid-response. More complex but more flexible.

**Option C — Hybrid:** Pre-fetch broad context AND allow tool calls for specific lookups.

## Context

The AiBrarian dataroom was just fixed today (embedding pipeline was silently failing — see `HANDOFF_AIBRARIAN_EMBEDDING_PIPELINE.md`). All search modes now work. Memory Matrix has 24,000+ nodes. The tools exist and work — the voice app just isn't reaching for them.

## Expected Outcome

After fix:
- "What are your thoughts on Kozmo?" → Luna searches memory/docs, returns architecture context
- "What about the Guardian app?" → Luna searches memory/docs, returns Guardian service spec context
- Luna should never say "I don't know" about core project components without first checking her knowledge systems
