# BRONZE Extraction Handoff to Claude Code

**Status as of 2026-02-12 16:08 PST**

## Current State

**BRONZE batch extraction is RUNNING:**
- Process PID: 4718
- Started: 16:00:06
- Total conversations: 338
- Progress file: `bronze_extraction_progress.json` (saves every 10 conversations)
- Estimated completion: ~2-3 hours total
- Cost: $0 (local MLX + Qwen 3B)

**What's happening:**
```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/Tools/MemoryMatrix_SandBox
python3 run_bronze_batch.py
```

The script:
1. Loads BRONZE conversations from `ingester_triage_full.json`
2. Extracts entities using `LocalMLXClient` (your Qwen 3B via MLX)
3. Saves progress incrementally to `bronze_extraction_progress.json`
4. Resumable if interrupted (checks completed UUIDs)

## Monitor Progress

```bash
# Check how many completed
jq '.completed' bronze_extraction_progress.json

# See last processed conversation
jq '.results[-1].conversation.title' bronze_extraction_progress.json

# Count total entities extracted so far
jq '[.results[].extraction.entities[]] | length' bronze_extraction_progress.json
```

## When Complete

The script will output:
- Success/failure counts
- Total entities extracted
- Entity type distribution (person, project, place, persona)
- Time per conversation average

Output file: `bronze_extraction_progress.json`

## Next Steps After BRONZE

1. **SILVER tier (238 conversations)** - 3-5 nodes each
   - Test with local Qwen first: `python3 test_silver_extraction.py`
   - If Qwen struggles, fall back to Anthropic API
   
2. **GOLD tier (152 conversations)** - 8-12 nodes, full 6-phase
   - Requires either:
     - Anthropic credits (~$6-8 total)
     - OR larger local model (32B+)
   - Most valuable memories, worth getting right

3. **Resolver phase** - Deduplicate entities across conversations
   - File: `mcp_server/ingester/resolver.py`
   - Uses embeddings to merge duplicates (e.g., "Luna" and "Luna Engine")
   
4. **Committer phase** - Write to sandbox_matrix.db
   - File: `mcp_server/ingester/committer.py`
   - Creates nodes, edges, entities in Memory Matrix

## Files You'll Need

**Extraction pipeline:**
- `mcp_server/ingester/extractor.py` - Main extraction logic
- `mcp_server/ingester/llm_clients.py` - LLM adapters (Anthropic + LocalMLX)
- `mcp_server/ingester/prompts.py` - Extraction prompts
- `mcp_server/ingester/scanner.py` - Load conversations from disk
- `mcp_server/ingester/validation.py` - JSON validation

**Test scripts:**
- `run_bronze_batch.py` - Currently running
- `test_mlx_extraction.py` - Single conversation test
- `test_extraction_sample.py` - 10 GOLD sample (needs API key)

**Data files:**
- `ingester_triage_full.json` - 928 conversations classified
- `bronze_extraction_progress.json` - Current extraction results
- `_CLAUDE_TRANSCRIPTS/Conversations/` - Source conversations (928 files)

## Observatory

**Currently running:**
- Backend: http://localhost:8101 (PID 27781)
- Frontend: Visible in browser
- Database: `sandbox_matrix.db` (236 nodes currently - test data)

**To restart if needed:**
```bash
# Backend
python3 http_standalone.py

# Frontend (if not already running)
cd frontend && npm run dev
```

## Key Architectural Decisions

**Offline extraction working:**
- Built `LocalMLXClient` adapter in `llm_clients.py`
- Uses your Qwen 3B at `/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/src/luna/inference/local.py`
- Formats prompts via Qwen chat template
- Appends JSON-forcing suffix for structured output
- Low temperature (0.1) for deterministic extraction

**BRONZE tier limitations:**
- Entity extraction only (no nodes, edges, observations)
- Simple enough for 3B model to handle well
- Covers 338/928 conversations (36% of corpus)

**Why this approach:**
- BRONZE = free, offline, good entity coverage
- SILVER/GOLD = need bigger model or API credits for quality
- Extraction quality matters - this becomes Luna's foundational memory

## Problems Encountered & Solved

1. **Anthropic API credit balance too low** ✅
   - Solution: Built LocalMLXClient for offline extraction
   
2. **MLX not installed** ✅
   - Solution: `pip3 install mlx mlx-lm`
   
3. **Luna module import failing** ✅
   - Solution: Added `src/` to Python path in test scripts

4. **Buffered output in long-running process** ✅
   - Solution: Progress saves to JSON file every 10 conversations

## Questions for Claude Code

1. Should we test SILVER extraction with Qwen 3B, or wait for API credits?
2. Do you want to build the resolver/committer pipeline while BRONZE runs?
3. After BRONZE completes, commit to sandbox or wait for full extraction?

## Architecture Docs

See these for full pipeline details:
- `TRANSCRIPT-INGESTER-ARCHITECTURE-V2.md` - Complete ingestion spec
- `HANDOFF.md` - Original handoff to implementation team
- `/mnt/project/bens_extraction_framework.jsx` - Interactive framework demo

---

**Handoff from:** The Dude (Claude Desktop architect mode)
**To:** Claude Code (implementation mode)
**Date:** 2026-02-12 16:08 PST
**Context window remaining:** 49.2k tokens
