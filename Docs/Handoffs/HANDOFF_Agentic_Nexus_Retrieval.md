# HANDOFF: Agentic Nexus Retrieval

**Priority:** P3 — The full "thinking" upgrade. Luna requests more context mid-generation.  
**Status:** Ready for implementation  
**Depends on:** Steps 2-4 should land first. This builds on a working retrieval pipeline.  
**Target files:**
- `src/luna/agentic/loop.py` (register Nexus search tool)
- New file: `src/luna/tools/nexus_tools.py` (tool definitions)
- `src/luna/engine.py` (route complex Nexus queries through AgentLoop)
**Scope:** Agentic execution path only. Direct path unchanged.

---

## THE PROBLEM

Luna's current pipeline is:

```
search once → inject context → generate once → done
```

No iteration. No reflection. No "I found a summary but need the specific evidence." The LLM can't say "search again with different terms" because by the time it's generating, the search is over.

The AgentLoop exists. It has a tool registry. It implements observe → think → act → repeat. It's wired into `_process_with_agent_loop()` in the engine. But it has no Nexus tools registered. The only tools available are file_tools, memory_tools, and dataroom_tools.

## THE FIX

### Change 1: Create `nexus_tools.py`

New file: `src/luna/tools/nexus_tools.py`

```python
"""
Nexus Tools — Agentic document search for Luna's AgentLoop.

These tools let the LLM request additional Nexus searches during
the agentic execution loop. When Luna encounters a knowledge gap
mid-generation, she can search for more context.

Tools:
- nexus_search: Search extractions and chunks across collections
- nexus_lookup_section: Find content by chapter/section label
- nexus_get_summary: Get the document summary for a collection
"""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


async def nexus_search(
    query: str,
    collection: str = "",
    search_type: str = "hybrid",
    limit: int = 5,
    _engine: Any = None,
) -> dict:
    """
    Search Nexus collections for document knowledge.
    
    Use this when you need more information from ingested documents
    to answer a question. Searches both extractions (summaries, claims)
    and raw document chunks.
    
    Args:
        query: What to search for (e.g., "Green Revolution impact Bali")
        collection: Specific collection to search (optional — searches all if empty)
        search_type: "keyword", "semantic", or "hybrid" (default)
        limit: Max results to return
    
    Returns:
        Dict with results list, each containing content, node_type, and source.
    """
    if not _engine or not hasattr(_engine, 'aibrarian') or not _engine.aibrarian:
        return {"error": "Nexus not available", "results": []}
    
    results = []
    
    # Determine which collections to search
    if collection:
        collections = [collection]
    else:
        # Search all enabled collections with lock-in > 0
        collections = []
        for key, cfg in _engine.aibrarian.registry.collections.items():
            if cfg.enabled and key in _engine.aibrarian.connections:
                collections.append(key)
    
    for key in collections:
        conn = _engine.aibrarian.connections.get(key)
        if not conn:
            continue
        
        # Search extractions first
        try:
            from luna.substrate.aibrarian_engine import AiBrarianEngine
            fts_query = AiBrarianEngine._sanitize_fts_query(query)
            ext_rows = conn.conn.execute(
                "SELECT node_type, content, confidence, metadata "
                "FROM extractions_fts "
                "JOIN extractions e ON extractions_fts.rowid = e.rowid "
                "WHERE extractions_fts MATCH ? "
                "ORDER BY e.confidence DESC LIMIT ?",
                (fts_query, limit),
            ).fetchall()
            for row in ext_rows:
                results.append({
                    "content": row[1],
                    "node_type": row[0],
                    "confidence": row[2],
                    "source": f"nexus/{key}",
                    "metadata": row[3],
                })
        except Exception as e:
            logger.warning(f"[NEXUS-TOOL] Extraction search failed: {e}")
        
        # Also search chunks if extractions are sparse
        if len(results) < 2:
            try:
                chunk_results = await _engine.aibrarian.search(
                    key, query, search_type, limit=limit
                )
                for r in chunk_results:
                    content = r.get("snippet") or r.get("content", "")
                    if content:
                        results.append({
                            "content": content,
                            "node_type": "CHUNK",
                            "source": f"nexus/{key}",
                        })
            except Exception as e:
                logger.warning(f"[NEXUS-TOOL] Chunk search failed: {e}")
    
    return {
        "query": query,
        "result_count": len(results),
        "results": results[:limit],
    }


async def nexus_lookup_section(
    section_label: str,
    collection: str = "",
    _engine: Any = None,
) -> dict:
    """
    Find content by chapter or section label.
    
    Use this when you know which section of a document you need
    (e.g., "Chapter 2", "Introduction", "Conclusion").
    
    Args:
        section_label: The section to find (e.g., "CHAPTER TWO", "Introduction")
        collection: Specific collection (optional)
    
    Returns:
        Dict with section summaries and claims from that section.
    """
    if not _engine or not hasattr(_engine, 'aibrarian') or not _engine.aibrarian:
        return {"error": "Nexus not available", "results": []}
    
    results = []
    collections = [collection] if collection else list(_engine.aibrarian.connections.keys())
    
    for key in collections:
        conn = _engine.aibrarian.connections.get(key)
        if not conn:
            continue
        
        try:
            # Search extractions with section metadata
            rows = conn.conn.execute(
                "SELECT node_type, content, confidence, metadata "
                "FROM extractions "
                "WHERE metadata LIKE ? "
                "ORDER BY confidence DESC LIMIT 10",
                (f'%{section_label}%',),
            ).fetchall()
            for row in rows:
                results.append({
                    "content": row[1],
                    "node_type": row[0],
                    "confidence": row[2],
                    "source": f"nexus/{key}",
                    "section": section_label,
                })
        except Exception:
            pass
        
        # Also get chunks tagged with this section
        try:
            rows = conn.conn.execute(
                "SELECT chunk_text, section_label "
                "FROM chunks "
                "WHERE section_label LIKE ? "
                "ORDER BY chunk_index LIMIT 5",
                (f'%{section_label}%',),
            ).fetchall()
            for row in rows:
                results.append({
                    "content": row[0],
                    "node_type": "CHUNK",
                    "source": f"nexus/{key}",
                    "section": row[1],
                })
        except Exception:
            pass
    
    return {
        "section": section_label,
        "result_count": len(results),
        "results": results,
    }


async def nexus_get_summary(
    collection: str = "",
    _engine: Any = None,
) -> dict:
    """
    Get the document summary and table of contents for a collection.
    
    Use this when you need an overview of what a document covers
    before searching for specific details.
    
    Args:
        collection: Which collection (optional — returns all if empty)
    
    Returns:
        Dict with document summaries and TOC.
    """
    if not _engine or not hasattr(_engine, 'aibrarian') or not _engine.aibrarian:
        return {"error": "Nexus not available", "results": []}
    
    results = []
    collections = [collection] if collection else list(_engine.aibrarian.connections.keys())
    
    for key in collections:
        conn = _engine.aibrarian.connections.get(key)
        if not conn:
            continue
        
        try:
            rows = conn.conn.execute(
                "SELECT node_type, content FROM extractions "
                "WHERE node_type IN ('DOCUMENT_SUMMARY', 'TABLE_OF_CONTENTS') "
                "ORDER BY node_type"
            ).fetchall()
            for row in rows:
                results.append({
                    "content": row[1],
                    "node_type": row[0],
                    "source": f"nexus/{key}",
                })
        except Exception:
            pass
    
    return {
        "result_count": len(results),
        "results": results,
    }


def register_nexus_tools(registry, engine=None) -> None:
    """Register Nexus tools with the AgentLoop's tool registry."""
    
    async def _search(query: str, collection: str = "", **kwargs):
        return await nexus_search(query, collection, _engine=engine)
    
    async def _lookup(section_label: str, collection: str = "", **kwargs):
        return await nexus_lookup_section(section_label, collection, _engine=engine)
    
    async def _summary(collection: str = "", **kwargs):
        return await nexus_get_summary(collection, _engine=engine)
    
    registry.register(
        name="nexus_search",
        description="Search ingested documents for knowledge. Use when you need more information from books, reports, or other documents to answer a question.",
        handler=_search,
        parameters={
            "query": {"type": "string", "description": "What to search for", "required": True},
            "collection": {"type": "string", "description": "Specific collection to search (optional)"},
        },
    )
    
    registry.register(
        name="nexus_lookup_section",
        description="Find content by chapter or section label. Use when you know which part of a document you need.",
        handler=_lookup,
        parameters={
            "section_label": {"type": "string", "description": "Section to find (e.g., 'CHAPTER TWO', 'Introduction')", "required": True},
            "collection": {"type": "string", "description": "Specific collection (optional)"},
        },
    )
    
    registry.register(
        name="nexus_get_summary",
        description="Get document overview and table of contents. Use before detailed searches to understand document structure.",
        handler=_summary,
        parameters={
            "collection": {"type": "string", "description": "Which collection (optional)"},
        },
    )
    
    logger.info("[NEXUS-TOOLS] Registered 3 Nexus tools for agentic retrieval")
```

### Change 2: Register Nexus tools in AgentLoop

In `src/luna/agentic/loop.py`, in `_register_default_tools()`:

```python
    def _register_default_tools(self) -> None:
        """Register default tools available to the agent."""
        from luna.tools.file_tools import register_file_tools
        from luna.tools.memory_tools import register_memory_tools

        register_file_tools(self.tool_registry)
        register_memory_tools(self.tool_registry)

        # Nexus tools (document knowledge search)
        try:
            from luna.tools.nexus_tools import register_nexus_tools
            register_nexus_tools(self.tool_registry, engine=self.orchestrator)
        except ImportError:
            logger.debug("Nexus tools not available")

        # ... existing eden_tools, dataroom_tools ...
```

### Change 3: Route knowledge-heavy queries through AgentLoop

In `src/luna/engine.py`, the routing decision (Phase 2) currently routes based on complexity. Add a signal for knowledge-heavy queries:

In `_process_message_agentic()`, after routing is determined:

```python
            # Override: Route through AgentLoop if query is knowledge-heavy
            # and collection context is sparse (the LLM might need to search more)
            if (
                routing.path == ExecutionPath.DIRECT
                and self.agent_loop
                and len(self._last_nexus_nodes) < 2
                and subtask_phase
                and subtask_phase.intent
                and subtask_phase.intent.get("intent") in ("research", "memory_query")
            ):
                logger.info("[ROUTING] Upgrading to AgentLoop (knowledge-sparse research query)")
                routing = routing._replace(path=ExecutionPath.PLANNED)
```

This is a conservative upgrade: only routes through AgentLoop when:
- The initial Nexus search returned < 2 results (sparse context)
- The intent is classified as "research" or "memory_query" (not greeting, emotional, etc.)
- The AgentLoop is available

If any condition fails, it stays on the direct path. No degradation.

---

## HOW IT WORKS END-TO-END

### Before (current):
```
User: "What evidence does Lansing present for the water temple system being optimal?"
  → Single FTS5 search: "evidence Lansing present water temple system optimal"
  → Maybe 1 extraction hit (if lucky)
  → LLM generates with thin context
  → Hedges: "I have some information but not specific evidence..."
```

### After (with agentic retrieval):
```
User: "What evidence does Lansing present for the water temple system being optimal?"
  → Intent: research (complex)
  → Initial Nexus search: sparse (< 2 results)
  → Routed to AgentLoop
  
  AgentLoop Iteration 1:
    Think: "I need to understand the document structure first"
    Act: nexus_get_summary() → Gets DOCUMENT_SUMMARY + TABLE_OF_CONTENTS
    Observe: "Chapter 6 covers ecological modeling — that's likely where evidence is"
  
  AgentLoop Iteration 2:
    Think: "Let me search for the simulation evidence in Chapter 6"
    Act: nexus_search("computer simulation water temple optimal") → 3 CLAIMs
    Observe: "Found claims about simulation model proving temple system was optimal"
  
  AgentLoop Iteration 3:
    Think: "I also need the Chapter 3 ritual scheduling data"
    Act: nexus_lookup_section("CHAPTER THREE") → SECTION_SUMMARY + CLAIMs
    Observe: "Found claims about tika calendar and fallow synchronization"
  
  Complete: LLM now has document overview + specific simulation evidence + ritual scheduling data
  → Generates rich, multi-source answer with specific evidence
```

The key difference: the LLM DECIDES what to search for based on what it's already found. It can request the table of contents, then drill into specific sections, then search for specific terms. That's thinking.

---

## TOOL DESCRIPTIONS MATTER

The tool descriptions are what the LLM reads to decide which tool to use. They need to be:

- **Clear about when to use**: "Use when you need more information from books, reports, or other documents"
- **Distinct from each other**: nexus_search (keyword query) vs nexus_lookup_section (structural navigation) vs nexus_get_summary (overview)
- **Honest about scope**: These tools search INGESTED documents, not the internet or live data

The Planner in the AgentLoop generates a step-by-step plan that references these tools. If the descriptions are vague, the Planner picks the wrong tool.

---

## WHAT THIS CHANGES VS. DOESN'T CHANGE

| Path | Before | After |
|------|--------|-------|
| Direct (simple queries) | Single search → generate | **No change** |
| Direct (research, good initial results) | Single search → generate | **No change** (>= 2 Nexus results, stays direct) |
| AgentLoop (research, sparse results) | Search → thin context → hedge | Search → AgentLoop → multi-step retrieval → rich context → confident answer |

Most queries still take the direct path. The AgentLoop only fires for research-intent queries where the initial search came back sparse. This keeps latency low for simple interactions.

---

## LATENCY BUDGET

Each AgentLoop iteration adds:
- ~100ms for planning (Qwen local or skipped)
- ~50ms for tool execution (SQLite queries)
- The final generation is the same as direct path

Typical AgentLoop runs 2-3 iterations for knowledge queries. Total added latency: ~300-500ms. Acceptable for research-type questions where the alternative is a hedge.

---

## DO NOT

- Do NOT route ALL queries through AgentLoop — only knowledge-sparse research queries
- Do NOT let the AgentLoop iterate more than 5 times for Nexus tools — cap it
- Do NOT modify the direct path — it stays fast for simple queries
- Do NOT make Nexus tools synchronous — they return dicts, the AgentLoop handles async
- Do NOT give the tools write access to Nexus — these are READ-ONLY search tools
- Do NOT register these tools in the MCP server — they're internal to the AgentLoop only
- Do NOT remove the existing pre-generation search — the AgentLoop supplements it, doesn't replace it

---

## VERIFICATION

After implementation:

1. **Simple query (should NOT trigger AgentLoop):**
   - "What is Priests and Programmers about?"
   → Backend logs: `Routing (semantic): DIRECT` (no change)

2. **Research query with good initial results:**
   - "What happens during the Green Revolution in Bali?"
   → May stay DIRECT if initial search returns 2+ extractions

3. **Research query with sparse results (should trigger AgentLoop):**
   - "What specific evidence does Lansing present that the traditional system was mathematically optimal?"
   → Backend logs: `[ROUTING] Upgrading to AgentLoop (knowledge-sparse research query)`
   → Backend logs should show 2-3 tool calls: `nexus_get_summary`, `nexus_search`, `nexus_lookup_section`
   → Luna answers with specific simulation data and chapter references

4. Check tool registration:
   ```
   [NEXUS-TOOLS] Registered 3 Nexus tools for agentic retrieval
   ```

---

## ESTIMATED SCOPE

- ~200 lines new file (`nexus_tools.py` — three tools + registration function)
- ~5 lines in `loop.py` (register nexus tools)
- ~10 lines in `engine.py` (routing upgrade condition)
- Zero new dependencies
- Zero schema changes
- Zero frontend changes
