# HANDOFF: Nexus → Memory Matrix Bridge

**Priority:** P2 — Luna forgets document knowledge between sessions  
**Status:** Ready for implementation  
**Depends on:** Step 4 (Grounding Wiring) should land first — the bridge uses the same `_last_nexus_nodes`  
**Target files:**
- `src/luna/engine.py` (new bridge method, called post-generation)
- `src/luna/actors/librarian.py` (new message type for bridge nodes)
**Scope:** Post-generation memory storage only. No changes to retrieval, Scribe, or frontend.

---

## THE PROBLEM

Luna's knowledge lives in two completely separate stores:

- **Memory Matrix**: 25K+ conversation nodes. Persists across sessions. Searchable during every message.
- **Nexus**: Document collections with extractions. Searched via `_get_collection_context()` per-message, but never written to Memory Matrix.

When Luna gives a great answer about Priests & Programmers — "the subak system coordinates irrigation through ritual-based scheduling" — that knowledge exists in Nexus during this session. Next session, unless the same FTS5 search fires and hits the same extractions, Luna has no memory of ever discussing it. The knowledge doesn't cross-pollinate.

The Scribe can't fix this because it explicitly skips assistant responses: `"CRITICAL: Skip assistant responses entirely. Luna's own responses are NOT facts to be stored."` This is the correct behavior for conversation extraction — Luna shouldn't store her own words as facts. But document-sourced knowledge is different. It came from a vetted source, not from Luna's generation.

## THE PRINCIPLE

**Don't extract from Luna's responses. Bridge from Nexus extractions that were actually used.**

The distinction matters:
- Luna says "I think the subak system is interesting" → Scribe skips (opinion, not fact) ✅
- Nexus CLAIM extraction says "Water temples organize synchronized fallow periods" and Luna used it in her response → Bridge to Memory Matrix as a REFERENCE node with source attribution ✅

The bridge operates on the structured extraction objects, not on Luna's generated text.

## THE FIX

### Change 1: New `_bridge_nexus_to_matrix()` method in engine.py

Add this method to the engine class:

```python
    async def _bridge_nexus_to_matrix(self) -> None:
        """
        Post-generation: Bridge high-confidence Nexus extractions to Memory Matrix.
        
        Only bridges extractions that were actually retrieved and injected
        into the generation context. This ensures Luna "remembers" document
        facts across sessions without the Scribe having to extract from
        her own responses.
        
        Creates REFERENCE nodes in Memory Matrix with source attribution
        to the Nexus collection and extraction ID.
        """
        if not self._last_nexus_nodes:
            return
        
        matrix = self.get_actor("matrix")
        if not matrix or not matrix.is_ready:
            return
        
        librarian = self.get_actor("librarian")
        
        bridged = 0
        for node in self._last_nexus_nodes:
            content = node.get("content", "")
            node_type = node.get("node_type", "CLAIM")
            source = node.get("source", "nexus")
            node_id = node.get("id", "")
            confidence = node.get("confidence", 0.85)
            
            # Only bridge substantive extractions (skip CHUNK, TABLE_OF_CONTENTS)
            if node_type not in ("CLAIM", "SECTION_SUMMARY", "DOCUMENT_SUMMARY"):
                continue
            
            # Skip very short content
            if len(content) < 30:
                continue
            
            # Check if this content already exists in Matrix (dedup)
            # Use a quick keyword search to avoid duplicates
            try:
                existing = await matrix.search(
                    content[:60],  # First 60 chars as search key
                    limit=1,
                    scopes=None,
                )
                if existing:
                    # Check for near-duplicate (>80% word overlap)
                    existing_content = existing[0].get("content", "")
                    if _content_overlap(content, existing_content) > 0.8:
                        continue  # Already bridged
            except Exception:
                pass  # Search failed, bridge anyway
            
            # Create REFERENCE node in Memory Matrix
            try:
                if librarian:
                    await librarian.mailbox.put(Message(
                        type="store_reference",
                        payload={
                            "content": content,
                            "node_type": "REFERENCE",
                            "source_collection": source,
                            "source_extraction_id": node_id,
                            "original_node_type": node_type,
                            "confidence": confidence,
                            "tags": ["nexus-bridge", source.replace("/", "-")],
                        },
                    ))
                else:
                    # Direct matrix storage if no librarian
                    await matrix.store_memory(
                        content=content,
                        node_type="REFERENCE",
                        tags=["nexus-bridge", source.replace("/", "-")],
                        confidence=confidence,
                        metadata={
                            "source_collection": source,
                            "source_extraction_id": node_id,
                            "original_node_type": node_type,
                        },
                    )
                bridged += 1
            except Exception as e:
                logger.warning(f"[NEXUS-BRIDGE] Failed to bridge node: {e}")
        
        if bridged:
            logger.info(f"[NEXUS-BRIDGE] Bridged {bridged} extractions to Memory Matrix")
        
        # Clear after bridging (prevent re-bridging on next message)
        self._last_nexus_nodes = []
```

Add the overlap helper as a module-level function:

```python
def _content_overlap(a: str, b: str) -> float:
    """Quick word overlap ratio for dedup checking."""
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    return len(intersection) / min(len(words_a), len(words_b))
```

### Change 2: Call the bridge after generation completes

In `_process_message_agentic()`, after the generation phase (Phase 4) completes:

Currently the method ends after `_process_direct()` or `_process_with_agent_loop()`. Add the bridge call:

```python
            if routing.path == ExecutionPath.DIRECT:
                self.metrics.direct_responses += 1
                await self._process_direct(user_message, correlation_id, memory_context, history_context)
            else:
                self.metrics.planned_responses += 1
                await self._process_with_agent_loop(user_message, correlation_id, memory_context, history_context)

            # ══════════════════════════════════════════════════════════════
            # PHASE 5: Bridge Nexus knowledge to Memory Matrix (NEW)
            # ══════════════════════════════════════════════════════════════
            try:
                await self._bridge_nexus_to_matrix()
            except Exception as e:
                logger.warning(f"[NEXUS-BRIDGE] Non-fatal error: {e}")
```

### Change 3: Handle `store_reference` message in Librarian

The Librarian needs to accept a new message type. In `src/luna/actors/librarian.py`, add to the message handler:

```python
            case "store_reference":
                await self._handle_store_reference(msg)
```

And the handler:

```python
    async def _handle_store_reference(self, msg: Message) -> None:
        """
        Store a REFERENCE node bridged from Nexus.
        
        These are document-sourced facts that Luna used in a response.
        They get stored with source attribution so Luna can recall them
        in future sessions without re-searching Nexus.
        """
        payload = msg.payload or {}
        content = payload.get("content", "")
        node_type = payload.get("node_type", "REFERENCE")
        source_collection = payload.get("source_collection", "")
        source_extraction_id = payload.get("source_extraction_id", "")
        original_node_type = payload.get("original_node_type", "")
        confidence = payload.get("confidence", 0.85)
        tags = payload.get("tags", [])
        
        if not content:
            return
        
        matrix = self._get_matrix()
        if not matrix:
            return
        
        try:
            await matrix.store_memory(
                content=content,
                node_type=node_type,
                tags=tags,
                confidence=confidence,
                metadata={
                    "source": "nexus-bridge",
                    "source_collection": source_collection,
                    "source_extraction_id": source_extraction_id,
                    "original_node_type": original_node_type,
                    "bridged_at": datetime.now().isoformat(),
                },
            )
            logger.info(
                f"[LIBRARIAN] Stored REFERENCE from {source_collection}: "
                f"{content[:60]}..."
            )
        except Exception as e:
            logger.warning(f"[LIBRARIAN] Failed to store reference: {e}")
```

---

## HOW IT WORKS

```
Session 1:
  User: "What is Priests and Programmers about?"
    → Nexus search returns DOCUMENT_SUMMARY + 3 CLAIMs
    → Luna generates great answer
    → _bridge_nexus_to_matrix() fires:
      → DOCUMENT_SUMMARY → stored as REFERENCE node in Matrix
      → 3 CLAIMs → stored as REFERENCE nodes in Matrix
      → Each tagged with ["nexus-bridge", "nexus-research_library"]

Session 2 (next day):
  User: "Remember what we said about that Bali book?"
    → Memory Matrix search finds REFERENCE nodes from yesterday
    → Luna recalls: "Yes — Priests and Programmers, about the water temple system..."
    → No Nexus search even needed — the knowledge persisted
```

## SAFEGUARDS

1. **Dedup**: Before bridging, checks if content already exists in Matrix (80% word overlap). Prevents accumulation of duplicate REFERENCE nodes across repeated queries about the same topic.

2. **Selective**: Only bridges CLAIM, SECTION_SUMMARY, and DOCUMENT_SUMMARY. Raw chunks and TABLE_OF_CONTENTS are skipped — they're navigational, not factual.

3. **Source attribution**: Every REFERENCE node carries `source_collection`, `source_extraction_id`, and `original_node_type` in metadata. If something needs to be traced back to the document, the path is clear.

4. **Non-blocking**: Bridge runs post-generation. If it fails, the user sees no difference. Errors are logged but don't interrupt the response.

5. **One-shot**: `_last_nexus_nodes` is cleared after bridging. Same extractions won't be re-bridged on the next message.

6. **Lock-in calibration**: REFERENCE nodes start with the extraction's confidence (typically 0.85). Over time, Memory Matrix's lock-in system will reinforce frequently-accessed references and let rarely-used ones decay.

---

## DO NOT

- Do NOT modify the Scribe's "skip assistant turns" rule — that's correct for conversation extraction
- Do NOT bridge on every Nexus search hit — only bridge after generation completes (the extractions were actually used)
- Do NOT bridge raw chunks — only structured extractions (CLAIM, SECTION_SUMMARY, DOCUMENT_SUMMARY)
- Do NOT bridge TABLE_OF_CONTENTS — it's navigational metadata, not knowledge
- Do NOT remove the original Nexus extraction — the bridge creates a COPY in Matrix, the source stays in Nexus
- Do NOT make the bridge synchronous with generation — it runs after, fire-and-forget

---

## VERIFICATION

After implementation:

1. Ask Luna "What is Priests and Programmers about?" in the UI
2. Check backend logs for: `[NEXUS-BRIDGE] Bridged 4 extractions to Memory Matrix`
3. Verify REFERENCE nodes exist:
   ```bash
   sqlite3 data/memory_matrix.db "
     SELECT node_type, substr(content, 1, 80), tags
     FROM memory_nodes
     WHERE node_type = 'REFERENCE'
     ORDER BY created_at DESC
     LIMIT 5;
   "
   ```
4. Start a new session. Ask "What do you remember about the Bali book?"
   → Luna should recall from Matrix REFERENCE nodes WITHOUT Nexus search hitting

---

## ESTIMATED SCOPE

- ~60 lines new code in `engine.py` (`_bridge_nexus_to_matrix` + `_content_overlap`)
- ~5 lines in `engine.py` (Phase 5 call site)
- ~30 lines in `librarian.py` (new message handler)
- Zero new dependencies
- Zero schema changes
- Zero frontend changes
