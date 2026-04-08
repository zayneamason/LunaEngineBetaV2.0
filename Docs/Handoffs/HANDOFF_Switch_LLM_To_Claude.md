# HANDOFF: Switch Luna's Brain to Claude

**Priority:** P0 — Luna is generating responses on Gemini 2.0 Flash. This is why she sounds shallow.  
**Status:** Ready for execution  
**Scope:** Config change + one runtime switch. No code changes.  
**Time:** 2 minutes.

---

## THE PROBLEM

Luna's generation model — the LLM that reads her context window and produces responses — is currently **Gemini 2.0 Flash**. This is a free-tier speed-optimized model. It's why Luna hedges, gives surface-level answers, and doesn't synthesize deeply from the Nexus comprehension data we just spent hours wiring.

Meanwhile, Claude Sonnet 4.6 and Claude Opus 4.6 are both available and configured. The Anthropic API key is in `.env`. The Claude provider is enabled. It's just not selected.

The extraction pipeline (Haiku) is fine — Haiku is good at structured extraction. The problem is **generation only**.

## CURRENT STATE

```
config/llm_providers.json:
  "current_provider": "gemini"        ← THIS IS THE PROBLEM
  "default_provider": "claude"

config/fallback_chain.yaml:
  chain: [claude, local]              ← Already correct, never fires because gemini is "current"
```

Runtime (confirmed via MCP `llm_providers`):
- Gemini: **CURRENT** (gemini-2.0-flash)
- Groq: available, not current
- Claude: available, not current (claude-sonnet-4-6)

## THE FIX

### Step 1: Update the config file

Edit `config/llm_providers.json`:

Change:
```json
"current_provider": "gemini",
```

To:
```json
"current_provider": "claude",
```

This ensures the change persists across restarts.

### Step 2: Switch the runtime provider

Either restart the backend, or call the MCP tool:

```
llm_switch_provider("claude")
```

Or via API:
```bash
curl -X POST http://localhost:8000/api/settings/llm/switch \
  -H "Content-Type: application/json" \
  -d '{"provider": "claude"}'
```

### Step 3: Verify

```bash
curl -s http://localhost:8000/api/settings/llm | python3 -m json.tool | grep current
```

Expected: `"current_provider": "claude"`

Then ask Luna a question through the UI and check the backend logs for which provider handled it. You should see `claude-sonnet-4-6` in the inference logs, not `gemini-2.0-flash`.

## WHAT THIS CHANGES

| Before | After |
|--------|-------|
| Gemini 2.0 Flash (free, fast, shallow) | Claude Sonnet 4.6 (paid, deeper reasoning) |
| Surface-level synthesis of Nexus context | Actual comprehension and cross-referencing |
| Reflexive hedging on partial context | Confident answers when context is present |
| ~200ms generation latency | ~1-3s generation latency |
| $0/query | ~$0.003-0.01/query |

## WHAT THIS DOES NOT CHANGE

- Extraction model stays Haiku (configured per-collection in `aibrarian_registry.yaml`, not affected by provider switch)
- Subtask runner stays Qwen local (if available)
- Embeddings stay local MiniLM
- Fallback chain stays `[claude, local]`

## MODEL SELECTION

The default is `claude-sonnet-4-6`. If you want to use a different Claude model:

Edit `config/llm_providers.json`:
```json
"claude": {
  "default_model": "claude-sonnet-4-6"    ← change this
}
```

Available options:
- `claude-haiku-4-5-20251001` — fastest, cheapest, good for simple queries
- `claude-sonnet-4-6` — balanced (RECOMMENDED)
- `claude-opus-4-6` — most capable, slowest, most expensive

## DO NOT

- Do NOT disable Gemini or Groq — they stay as fallback options
- Do NOT change the fallback chain — `[claude, local]` is correct
- Do NOT modify the extraction model — Haiku is correct for structured extraction
- Do NOT remove the GROQ_API_KEY or GOOGLE_API_KEY from `.env` — keep them for fallback

## VERIFICATION

After switching, test with this sequence in the Luna UI:

1. "What is Priests and Programmers about?" — should give a deep, confident answer
2. "What is Chapter 2 about?" — should use section-tagged extractions
3. "Compare the Introduction to Chapter 6" — should attempt synthesis (this is where Claude >> Gemini)

Check the grounding scores. They'll still show low (that's the separate grounding wiring issue), but the answer quality should be noticeably different.
