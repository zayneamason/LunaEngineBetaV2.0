# CC INSTRUCTIONS: Close 4 Remaining Gaps

**Context:** 90% of the reading system is implemented. The split budget, chunk search, reading prompt, Haiku backend, access log, and cartridge schema are all working. Four gaps remain.

**Do these in order. Each is small. Total: ~45 minutes.**

---

## Gap 1: Startup Script (5 min)

Create `scripts/start_engine.sh`:

```bash
#!/bin/bash
# Always use .venv Python, always clear bytecode cache
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
find src/ -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
find src/ -name "*.pyc" -delete 2>/dev/null
exec .venv/bin/python scripts/run.py --server --host 0.0.0.0 --port 8000
```

```bash
chmod +x scripts/start_engine.sh
```

**Why:** Stale `.pyc` files from system Python kept overriding source changes. This was the deployment blocker for the FTS5 fix.

---

## Gap 2: Document Reader Directive (2 min)

The `dir_document_reader` directive was never INSERTed into the quests table.

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
.venv/bin/python -c "
import sqlite3
conn = sqlite3.connect('data/user/luna_engine.db')
conn.execute('''INSERT OR REPLACE INTO quests (
    id, type, status, priority, title, objective,
    trigger_type, trigger_config, action,
    trust_tier, authored_by, cooldown_minutes,
    created_at, updated_at
) VALUES (
    'dir_document_reader', 'directive', 'armed', 'high',
    'Document Deep Reader',
    'Widen aperture when user asks for document depth',
    'keyword',
    '{\"match\": \"\\\\b(chapter|evidence|section|passage|quote|specific|detail|methodology|text say|cite|according to)\\\\b\"}',
    'set_aperture:WIDE',
    'system', 'system', 10,
    datetime('now'), datetime('now')
)''')
conn.commit()
print('Directive inserted')
conn.close()
"
```

**Verify:** `SELECT * FROM quests WHERE id='dir_document_reader';` should return 1 row.

---
## Gap 3: Reflection Write-Back (20 min)

**STATUS: NOT IMPLEMENTED.** The reflections table exists and has 0 rows. There is zero code anywhere in the codebase that writes to it. The `_write_reflection` method does not exist.

**File:** `src/luna/engine.py`

### 3A: Add the `_write_reflection` method to the LunaEngine class

Add this method somewhere in the class (after `_get_collection_context` is fine):

```python
    async def _write_reflection(self, query: str, response: str, nexus_nodes: list) -> None:
        """Background task: Luna reflects on what she just read and writes to cartridge."""
        try:
            source_texts = [n["content"][:300] for n in nexus_nodes if n.get("node_type") == "SOURCE_TEXT"]
            claims = [n["content"][:200] for n in nexus_nodes if n.get("node_type") in ("CLAIM", "SECTION_SUMMARY")]

            if not source_texts and not claims:
                return

            reflection_prompt = (
                "You just read source material and answered a question about it. "
                "Write a brief (2-3 sentence) first-person reflection on what you found interesting, "
                "surprising, or worth remembering. Write as yourself — this is your marginalia.\n\n"
                f"Question asked: {query[:200]}\n"
                f"Key claims found: {'; '.join(claims[:3])}\n"
                f"Source excerpt: {source_texts[0][:300] if source_texts else 'N/A'}\n"
                f"Your response summary: {response[:200]}\n\n"
                "Reflection (2-3 sentences, first person):"
            )

            # Use Haiku for the reflection — cheap, fast
            import anthropic
            client = anthropic.Anthropic()
            result = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=150,
                temperature=0.7,
                messages=[{"role": "user", "content": reflection_prompt}],
            )
            reflection_text = result.content[0].text.strip()

            if not reflection_text or len(reflection_text) < 20:
                return

            # Write to the FIRST collection that contributed SOURCE_TEXT nodes
            import uuid
            written = False
            for node in nexus_nodes:
                if written:
                    break
                source_key = node.get("source", "").replace("nexus/", "")
                if not source_key or not self.aibrarian:
                    continue
                conn = self.aibrarian.connections.get(source_key)
                if not conn:
                    continue
                try:
                    conn.conn.execute(
                        "INSERT INTO reflections "
                        "(id, extraction_id, reflection_type, content, luna_instance, created_at) "
                        "VALUES (?, ?, ?, ?, ?, datetime('now'))",
                        (
                            str(uuid.uuid4())[:8],
                            node.get("id", ""),
                            "connection",
                            reflection_text,
                            "luna-ahab",
                        ),
                    )
                    conn.conn.commit()
                    logger.info(f"[REFLECTION] Wrote to {source_key}: {reflection_text[:60]}...")
                    written = True
                except Exception as e:
                    logger.debug(f"[REFLECTION] Write failed for {source_key}: {e}")

        except Exception as e:
            logger.warning(f"[REFLECTION] Background reflection failed: {e}")
```

### 3B: Trigger reflection after deep reads

Find where the response is finalized after generation. Look for where `self._last_nexus_nodes` is populated and the response text is available. This is likely in `_process_direct()` or the generation callback.

Add this AFTER the response is generated, before it's returned:

```python
        # ── Write-back: Reflection on deep reads ──
        if (
            hasattr(self, '_last_nexus_nodes')
            and self._last_nexus_nodes
            and any(n.get("node_type") == "SOURCE_TEXT" for n in self._last_nexus_nodes)
            and len(response_text) > 200
        ):
            asyncio.create_task(self._write_reflection(
                query=user_message,
                response=response_text,
                nexus_nodes=list(self._last_nexus_nodes),
            ))
```

**Key:** Use `asyncio.create_task()` — this runs in the background. Luna's response is NOT delayed by the reflection write.

**Key:** Only fires when `SOURCE_TEXT` nodes are present (Tier 4 chunk search ran) AND the response is substantive (>200 chars). Simple overview questions don't trigger reflections.

### Verify:
1. Ask Luna a depth question: "What evidence does Lansing present about the simulation model?"
2. Wait 5 seconds for background reflection to complete
3. Check: `.venv/bin/python -c "import sqlite3; conn=sqlite3.connect('data/local/research_library.db'); print(conn.execute('SELECT * FROM reflections').fetchall())"`
4. Should have 1 row with Luna's reflection text

---
## Gap 4: Reflection Retrieval — Tier 5 (15 min)

**This is the compounding intelligence loop.** Without this, Luna writes reflections that nobody reads. The cartridge accumulates marginalia that never informs future responses.

**File:** `src/luna/engine.py` — inside `_get_collection_context()`, in the per-collection loop

### Insert Point

Right AFTER the Tier 4 chunk search block (after the `if chunk_rows:` log line and its except block), BEFORE the `# ── Write-back: Log access` section. The insertion goes inside the `for key in collections_to_search:` loop.

### Code to Add

```python
            # ── TIER 5: Luna's prior reflections on this material ────────
            try:
                refl_rows = conn.conn.execute(
                    "SELECT r.content, r.reflection_type, r.created_at "
                    "FROM reflections_fts "
                    "JOIN reflections r ON reflections_fts.rowid = r.rowid "
                    "WHERE reflections_fts MATCH ? "
                    "LIMIT 3",
                    (fts_query,),
                ).fetchall()
                for row in refl_rows:
                    text = row[0] if isinstance(row, tuple) else row["content"]
                    if text and text not in seen_content and content_budget > 0:
                        seen_content.add(text)
                        chunk = text[:content_budget]
                        parts.append(f"[Nexus/{key} LUNA_REFLECTION]\n{chunk}")
                        content_budget -= len(chunk)
                        nexus_nodes.append({
                            "id": f"nexus:{key}:reflection:{len(nexus_nodes)}",
                            "content": text,
                            "node_type": "LUNA_REFLECTION",
                            "source": f"nexus/{key}",
                            "confidence": 0.8,
                            "grounding_priority": priority,
                        })
                if refl_rows:
                    logger.info(f"[PHASE2] Tier 5: {len(refl_rows)} prior reflections for {key}")
            except Exception:
                pass  # reflections_fts may not exist in older collections
```

### How to verify the exact insertion point

```bash
grep -n "Write-back.*Log access\|TIER 4.*chunk\|chunk_rows.*raw passages" src/luna/engine.py | tail -5
```

The Tier 5 block goes BETWEEN the last line of Tier 4's except block and the `# ── Write-back: Log access` comment. It stays INSIDE the `for key in collections_to_search:` loop — same indentation level as Tier 4.

### Verify End-to-End

1. Ask Luna a depth question to trigger reflection write (Gap 3)
2. Wait 5 seconds
3. Ask the SAME topic again: "Tell me more about the simulation model"
4. Check engine logs for: `[PHASE2] Tier 5: 1 prior reflections for research_library`
5. Luna's response should incorporate her prior reflection naturally — building on what she thought last time instead of starting fresh

---

## Summary

| Gap | What | Time | Files |
|---|---|---|---|
| 1 | Startup script | 5 min | `scripts/start_engine.sh` (new) |
| 2 | Directive INSERT | 2 min | `data/user/luna_engine.db` (SQL) |
| 3 | Reflection write-back | 20 min | `src/luna/engine.py` (method + trigger) |
| 4 | Reflection retrieval | 15 min | `src/luna/engine.py` (Tier 5 in collection loop) |

**After all 4:** Luna reads → finds extractions + chunks → responds → reflects → writes reflection to cartridge → next time, finds her own prior reflection alongside the source material → builds on previous thinking.

The cartridge gets smarter. The loop closes.

## DO NOT

- Do NOT modify existing Tiers 1-4 — these are working
- Do NOT make reflection writes synchronous — always `asyncio.create_task()`
- Do NOT use Sonnet for reflections — Haiku at $0.003 per reflection is sufficient
- Do NOT skip the `SOURCE_TEXT` check on the write trigger — only deep reads should generate reflections
- Do NOT store reflections in the Memory Matrix — they belong IN the cartridge (the SQLite file)
