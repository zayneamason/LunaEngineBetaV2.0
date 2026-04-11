# HANDOFF — AiBrarian Vec Fallback Write Path

**Date:** 2026-04-11
**Priority:** High — blocks semantic search for cartridge collections in distribution builds (hai-dai ambassador build)
**Estimated effort:** 45–90 min for code changes + verification (excludes a full rebuild)
**File scope:** 2 files. ~50 lines of code change.

---

## TL;DR

`AiBrarianFallbackVec` (in [`src/luna/substrate/vec_fallback.py`](../src/luna/substrate/vec_fallback.py)) is a pure-Python embedding store that exists for cases where the `sqlite-vec` extension can't load (e.g. macOS system Python's `sqlite3` is built without `enable_load_extension`). Its **read side is fully wired** — `_vec_search()` at [`aibrarian_engine.py:1008-1052`](../src/luna/substrate/aibrarian_engine.py#L1008) correctly routes to `fallback.search()` when vec0 is unavailable.

But the **write side is missing entirely**. `AiBrarianFallbackVec` has no `store()` method, and the two write paths (`_embed_chunks` and `register_cartridge`) just `return` / skip silently when `_vec_loaded` is False. So `chunk_embeddings_fallback` is always empty, and the semantic search route at line 1019 finds nothing to return.

This handoff adds the missing write side. Three small changes in two files. Read side stays untouched.

---

## How we discovered this

While verifying that the `priests_and_programmers` cartridge actually ended up in the hai-dai ambassador build, I queried the bundled DB:

```
output/hai-dai-macos-arm64-0.3.0/data/system/aibrarian/priests_and_programmers.db
```

| Table | Rows | What this means |
|---|---:|---|
| `documents` | 1 | The .lun cartridge registered as a doc ✓ |
| `chunks` | 3,572 | Text chunks extracted ✓ |
| `chunks_fts` | 3,572 | FTS keyword index built ✓ |
| `chunk_embeddings_fallback` | **0** | **BUG — should be ~3,572** |
| `entities` | 0 | (separate issue, out of scope) |

So FTS keyword search works against the cartridge, but **semantic vector search returns nothing** because the fallback table is empty. For an ambassador build where indigenous leaders ask conversational questions, semantic search is the primary value-add — keyword search alone is a meaningful regression.

The build log also shows the upstream warning that triggers this:
```
sqlite-vec not available for priests_and_programmers:
'sqlite3.Connection' object has no attribute 'enable_load_extension'
```

That's macOS's bundled Python compiled without `--enable-loadable-sqlite-extensions`. The fallback class was added precisely for this scenario, but only the read half ever got wired up.

---

## Pre-flight: what's already correct (do NOT touch)

- **`AiBrarianFallbackVec.search()`** at [`vec_fallback.py:204-231`](../src/luna/substrate/vec_fallback.py#L204) — works correctly, queries `chunk_embeddings_fallback`, performs cosine similarity in numpy or pure Python. Already battle-tested by the existing `_vec_search` code path.
- **`AiBrarianFallbackVec._ensure_fallback_table()`** at [`vec_fallback.py:168`](../src/luna/substrate/vec_fallback.py#L168) — creates the `chunk_embeddings_fallback` table if it doesn't exist. Sets `self._migrated = True` when ready.
- **`_vec_search()`** at [`aibrarian_engine.py:1005-1052`](../src/luna/substrate/aibrarian_engine.py#L1005) — already routes to the fallback when `_vec_loaded` is False but `_fallback_vec` exists. No changes needed here. **This is the critical reason the fix is small.**
- **`AiBrarianConnection.initialize()`** at [`aibrarian_engine.py:493-518`](../src/luna/substrate/aibrarian_engine.py#L493) — already constructs `self._fallback_vec = AiBrarianFallbackVec(...)` in the `except` block when sqlite-vec fails to load. So `conn._fallback_vec` is reliably present whenever `conn._vec_loaded` is False.

In other words: the routing is already in place on read. We just need write-side parity.

## DO NOT

- Do NOT touch `_vec_search()` or `AiBrarianFallbackVec.search()` — they already work
- Do NOT change `AiBrarianConnection.initialize()` — fallback construction is already correct
- Do NOT switch to `apsw` or `pysqlite3-binary` — these would unblock native sqlite-vec but require a much larger refactor; out of scope for this handoff
- Do NOT touch any of the *other* `chunk_embeddings` query sites at [`aibrarian_engine.py:1149`](../src/luna/substrate/aibrarian_engine.py#L1149), [`:1156`](../src/luna/substrate/aibrarian_engine.py#L1156), [`:1175`](../src/luna/substrate/aibrarian_engine.py#L1175), [`:2014`](../src/luna/substrate/aibrarian_engine.py#L2014), [`:2025`](../src/luna/substrate/aibrarian_engine.py#L2025) — these are the doc-level embedding lookup helpers. They will need similar fallback wiring eventually, but cartridge semantic search via `_vec_search` does NOT depend on them. Leave them for a follow-up handoff so this fix stays small and verifiable.
- Do NOT try to fix the entity extraction gap (empty `entities` table). Different pipeline, separate issue.
- Do NOT modify the existing arm64 dist at `output/hai-dai-macos-arm64-0.3.0/` — leave the broken-state DB as a reference for comparison.

---

## The Fix — Three Changes

### Change 1 — Add `store()` to `AiBrarianFallbackVec`

**File:** [`src/luna/substrate/vec_fallback.py`](../src/luna/substrate/vec_fallback.py)

**Location:** Inside the `AiBrarianFallbackVec` class. Insert immediately AFTER the `_ensure_fallback_table` method (currently ending at line 202) and BEFORE the `search` method (currently starting at line 204).

**Add this method:**

```python
    def store(self, chunk_id: str, embedding) -> bool:
        """Store an embedding for a chunk_id in the fallback table.

        Accepts either a list[float] (will be serialized via _vec_to_blob)
        or a bytes blob already in the wire format. Cartridge ingestion
        passes raw blobs read from the .lun file's embeddings table; the
        runtime embedding pipeline passes list[float] from the generator.
        """
        if not self._migrated:
            return False
        if isinstance(embedding, (list, tuple)):
            blob = _vec_to_blob(list(embedding))
        elif isinstance(embedding, (bytes, bytearray, memoryview)):
            blob = bytes(embedding)
        else:
            logger.debug(
                "FallbackVec.store: unexpected embedding type %s for %s",
                type(embedding).__name__, chunk_id,
            )
            return False
        self.conn.execute(
            "INSERT OR REPLACE INTO chunk_embeddings_fallback "
            "(chunk_id, embedding) VALUES (?, ?)",
            (chunk_id, blob),
        )
        self.conn.commit()
        return True
```

**Why both signatures**: `_embed_chunks` generates embeddings as `list[float]` from the generator. `register_cartridge` reads pre-computed embeddings as `bytes` blobs from the .lun file. Both write paths need to call `store()`, so the method has to handle both shapes.

**Why `INSERT OR REPLACE`**: matches the existing `chunk_embeddings` write semantics elsewhere in the codebase — re-running ingestion should overwrite stale embeddings, not error or duplicate.

### Change 2 — Wire `_embed_chunks` to use the fallback when vec is unavailable

**File:** [`src/luna/substrate/aibrarian_engine.py`](../src/luna/substrate/aibrarian_engine.py)

**Location:** The `_embed_chunks` method, currently at [lines 2355-2390](../src/luna/substrate/aibrarian_engine.py#L2355).

**Current code (read first to confirm match):**

```python
    async def _embed_chunks(
        self,
        conn: AiBrarianConnection,
        doc_id: str,
        chunks: list[DocumentChunk],
    ) -> None:
        """Embed all chunks and store a document-level embedding (average)."""
        if not conn._vec_loaded:
            return

        gen = self._get_generator(conn.config)
        texts = [chunk.text for chunk in chunks]
        embeddings = await gen.generate_batch(texts)

        valid_embeddings = []
        for chunk, emb in zip(chunks, embeddings):
            if emb is None:
                continue
            chunk_id = f"{doc_id}:chunk:{chunk.index}"
            blob = _vector_to_blob(emb)
            conn.conn.execute(
                "INSERT OR REPLACE INTO chunk_embeddings (chunk_id, embedding) VALUES (?, ?)",
                (chunk_id, blob),
            )
            valid_embeddings.append(emb)

        # Document-level embedding = average of chunk embeddings
        if valid_embeddings:
            import numpy as np

            doc_vec = np.mean(valid_embeddings, axis=0).tolist()
            blob = _vector_to_blob(doc_vec)
            conn.conn.execute(
                "INSERT OR REPLACE INTO chunk_embeddings (chunk_id, embedding) VALUES (?, ?)",
                (doc_id, blob),
            )
```

**Replace with:**

```python
    async def _embed_chunks(
        self,
        conn: AiBrarianConnection,
        doc_id: str,
        chunks: list[DocumentChunk],
    ) -> None:
        """Embed all chunks and store a document-level embedding (average).

        When sqlite-vec is loaded, writes to the chunk_embeddings vec0 table.
        When vec is unavailable but the pure-Python fallback is initialized,
        writes to chunk_embeddings_fallback via conn._fallback_vec.store().
        Returns silently if neither path is available.
        """
        fallback = getattr(conn, "_fallback_vec", None)
        if not conn._vec_loaded and not fallback:
            return

        gen = self._get_generator(conn.config)
        texts = [chunk.text for chunk in chunks]
        embeddings = await gen.generate_batch(texts)

        valid_embeddings = []
        for chunk, emb in zip(chunks, embeddings):
            if emb is None:
                continue
            chunk_id = f"{doc_id}:chunk:{chunk.index}"
            if conn._vec_loaded:
                blob = _vector_to_blob(emb)
                conn.conn.execute(
                    "INSERT OR REPLACE INTO chunk_embeddings (chunk_id, embedding) VALUES (?, ?)",
                    (chunk_id, blob),
                )
            else:
                fallback.store(chunk_id, emb)
            valid_embeddings.append(emb)

        # Document-level embedding = average of chunk embeddings
        if valid_embeddings:
            import numpy as np

            doc_vec = np.mean(valid_embeddings, axis=0).tolist()
            if conn._vec_loaded:
                blob = _vector_to_blob(doc_vec)
                conn.conn.execute(
                    "INSERT OR REPLACE INTO chunk_embeddings (chunk_id, embedding) VALUES (?, ?)",
                    (doc_id, blob),
                )
            else:
                fallback.store(doc_id, doc_vec)
```

The shape of the change: instead of `if not conn._vec_loaded: return`, fall through with both paths. Each `INSERT INTO chunk_embeddings` call site gets an `if conn._vec_loaded:` / `else: fallback.store(...)` split.

### Change 3 — Wire `register_cartridge` to use the fallback when vec is unavailable

**File:** [`src/luna/substrate/aibrarian_engine.py`](../src/luna/substrate/aibrarian_engine.py)

**Location:** Inside the `register_cartridge` method, currently at [lines 2516-2544](../src/luna/substrate/aibrarian_engine.py#L2516).

**Current code (read first to confirm match):**

```python
            # Copy embeddings to collection's chunk_embeddings
            if conn._vec_loaded:
                embeddings = lun_conn.execute(
                    "SELECT node_id, level, vector FROM embeddings"
                ).fetchall()

                valid_embeddings = []
                for emb_row in embeddings:
                    node_id = emb_row["node_id"]
                    chunk_id = lun_node_to_chunk.get(node_id)
                    if not chunk_id:
                        # Section-level embedding — map to a synthetic chunk_id
                        chunk_id = f"{doc_id}:section:{node_id}"
                    blob = emb_row["vector"]
                    conn.conn.execute(
                        "INSERT OR REPLACE INTO chunk_embeddings (chunk_id, embedding) VALUES (?, ?)",
                        (chunk_id, blob),
                    )
                    valid_embeddings.append(blob)

                # Doc-level average embedding
                if valid_embeddings:
                    import numpy as np
                    vecs = [_blob_to_vector(b) for b in valid_embeddings]
                    doc_vec = np.mean(vecs, axis=0).tolist()
                    conn.conn.execute(
                        "INSERT OR REPLACE INTO chunk_embeddings (chunk_id, embedding) VALUES (?, ?)",
                        (doc_id, _vector_to_blob(doc_vec)),
                    )
```

**Replace with:**

```python
            # Copy embeddings to collection's chunk_embeddings (or fallback)
            fallback = getattr(conn, "_fallback_vec", None)
            if conn._vec_loaded or fallback:
                embeddings = lun_conn.execute(
                    "SELECT node_id, level, vector FROM embeddings"
                ).fetchall()

                valid_embeddings = []
                for emb_row in embeddings:
                    node_id = emb_row["node_id"]
                    chunk_id = lun_node_to_chunk.get(node_id)
                    if not chunk_id:
                        # Section-level embedding — map to a synthetic chunk_id
                        chunk_id = f"{doc_id}:section:{node_id}"
                    blob = emb_row["vector"]
                    if conn._vec_loaded:
                        conn.conn.execute(
                            "INSERT OR REPLACE INTO chunk_embeddings (chunk_id, embedding) VALUES (?, ?)",
                            (chunk_id, blob),
                        )
                    else:
                        fallback.store(chunk_id, blob)
                    valid_embeddings.append(blob)

                # Doc-level average embedding
                if valid_embeddings:
                    import numpy as np
                    vecs = [_blob_to_vector(b) for b in valid_embeddings]
                    doc_vec = np.mean(vecs, axis=0).tolist()
                    if conn._vec_loaded:
                        conn.conn.execute(
                            "INSERT OR REPLACE INTO chunk_embeddings (chunk_id, embedding) VALUES (?, ?)",
                            (doc_id, _vector_to_blob(doc_vec)),
                        )
                    else:
                        fallback.store(doc_id, _vector_to_blob(doc_vec))
```

Note: cartridge embeddings come in as raw `bytes` blobs (from the .lun file's `embeddings.vector` column), which is why `store()` accepts both `bytes` and `list[float]`. The doc-level average is computed from the unpacked vectors then re-blobbed via `_vector_to_blob` — this matches the original code's intent.

---

## Checkpoints

The user wants explicit recoverable savepoints. Make a git commit after each change so the work is rollback-safe. Use the user's normal commit style (the recent log uses `feat:` / `fix:` prefixes).

### Checkpoint A — after Change 1 (vec_fallback.py only)

**Verify before committing:**
```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
python3 -m py_compile src/luna/substrate/vec_fallback.py && echo "OK syntax"
python3 -c "
import sys; sys.path.insert(0, 'src')
from luna.substrate.vec_fallback import AiBrarianFallbackVec
import sqlite3
conn = sqlite3.connect(':memory:')
fb = AiBrarianFallbackVec(conn, dim=384)
ok = fb.store('test:chunk:0', [0.1] * 384)
print('store list[float]:', ok)
ok = fb.store('test:chunk:1', b'\\x00' * (384 * 4))
print('store bytes:', ok)
n = conn.execute('SELECT COUNT(*) FROM chunk_embeddings_fallback').fetchone()[0]
print(f'rows in fallback table: {n} (expected 2)')
"
```

Expected output:
```
OK syntax
store list[float]: True
store bytes: True
rows in fallback table: 2 (expected 2)
```

**Commit:**
```bash
git add src/luna/substrate/vec_fallback.py
git commit -m "feat(aibrarian): add store() to AiBrarianFallbackVec for write-side parity"
```

### Checkpoint B — after Change 2 (`_embed_chunks` wiring)

**Verify before committing:**
```bash
python3 -m py_compile src/luna/substrate/aibrarian_engine.py && echo "OK syntax"
```

Quick smoke test that the existing test suite (if any) for embedding paths still passes:
```bash
# If there's a relevant test:
python3 -m pytest tests/ -k "embed" -x --no-header 2>&1 | tail -20
```

(Skip if no relevant tests exist — this method is exercised mainly by integration tests via cartridge ingestion, which we'll run at Checkpoint D.)

**Commit:**
```bash
git add src/luna/substrate/aibrarian_engine.py
git commit -m "fix(aibrarian): _embed_chunks writes to fallback when sqlite-vec unavailable"
```

### Checkpoint C — after Change 3 (`register_cartridge` wiring)

**Verify before committing:**
```bash
python3 -m py_compile src/luna/substrate/aibrarian_engine.py && echo "OK syntax"
```

End-to-end smoke test that runs cartridge registration in isolation (without a full Forge build):

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
PYTHONPATH=src python3 <<'PY'
import asyncio, sqlite3, tempfile, yaml
from pathlib import Path
from luna.substrate.aibrarian_engine import AiBrarianEngine
from luna.substrate.aibrarian_schema import STANDARD_SCHEMA

LUN_PATH = Path("Docs/PRIESTS AND PROGRAMMERS_Lansing.lun")
assert LUN_PATH.exists(), f"missing test cartridge: {LUN_PATH}"

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    db_path = tmp / "test_pp.db"
    # Create empty collection DB with standard schema
    c = sqlite3.connect(str(db_path))
    c.executescript(STANDARD_SCHEMA)
    c.close()

    # Build a minimal registry pointing at the test DB
    registry = {
        "schema_version": 1,
        "collections": {
            "test_pp": {
                "enabled": True,
                "db_path": str(db_path),
                "schema_type": "standard",
                "read_only": False,
            }
        }
    }
    reg_path = tmp / "registry.yaml"
    reg_path.write_text(yaml.dump(registry))

    async def go():
        engine = AiBrarianEngine(reg_path)
        await engine.initialize()
        doc_id = await engine.register_cartridge("test_pp", LUN_PATH)
        await engine.shutdown()
        return doc_id

    doc_id = asyncio.run(go())
    print(f"registered doc_id: {doc_id}")

    # Verify what made it into the DB
    c = sqlite3.connect(str(db_path))
    for tbl in ("documents", "chunks", "chunks_fts", "chunk_embeddings_fallback"):
        try:
            n = c.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
            print(f"  {tbl:32s} {n}")
        except Exception as e:
            print(f"  {tbl:32s} ERR: {e}")
    c.close()
PY
```

Expected: `chunk_embeddings_fallback` shows a nonzero count (should be in the thousands — same order as `chunks`).

**Commit:**
```bash
git add src/luna/substrate/aibrarian_engine.py
git commit -m "fix(aibrarian): register_cartridge copies embeddings to fallback when vec unavailable"
```

### Checkpoint D — full build verification (optional but recommended)

This is a full rebuild to confirm the fix works end-to-end through Forge's pipeline. **Takes ~45–90 min.** If time is tight, the user (back in the original session) will do this themselves.

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/Builds
mkdir -p /tmp/luna-builds
nohup python3 -u -c "
import sys, importlib
sys.path.insert(0, '.')
sys.argv = ['build.py', '--profile', 'hai-dai']
m = importlib.import_module('Lunar-Forge.build')
m.main()
" > /tmp/luna-builds/hai-dai-vecfix.log 2>&1 &
echo "Build PID: $!"
```

Monitor with `tail -f /tmp/luna-builds/hai-dai-vecfix.log`. When complete, query the bundled DB:

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/Builds/Lunar-Forge/output/hai-dai-macos-arm64-0.3.0/data/system/aibrarian
python3 -c "
import sqlite3
c = sqlite3.connect('priests_and_programmers.db')
for tbl in ('chunks', 'chunks_fts', 'chunk_embeddings_fallback'):
    n = c.execute(f'SELECT COUNT(*) FROM {tbl}').fetchone()[0]
    print(f'{tbl:32s} {n}')
"
```

**Expected** (the key change vs the existing broken build):
- `chunks`: ~3,572
- `chunks_fts`: ~3,572
- `chunk_embeddings_fallback`: **nonzero, in the thousands** (was 0 before the fix)

A nonzero count here is **the canary** that proves the fix works through the full Forge pipeline.

---

## Verification (final)

After Checkpoint C (or D if you ran the full build), confirm the read side still works against the populated fallback table:

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
PYTHONPATH=src python3 <<'PY'
import asyncio, sqlite3, tempfile, yaml
from pathlib import Path
from luna.substrate.aibrarian_engine import AiBrarianEngine
from luna.substrate.aibrarian_schema import STANDARD_SCHEMA

LUN_PATH = Path("Docs/PRIESTS AND PROGRAMMERS_Lansing.lun")
with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    db_path = tmp / "test_pp.db"
    c = sqlite3.connect(str(db_path)); c.executescript(STANDARD_SCHEMA); c.close()
    reg = {"schema_version": 1, "collections": {"test_pp": {
        "enabled": True, "db_path": str(db_path),
        "schema_type": "standard", "read_only": False
    }}}
    reg_path = tmp / "registry.yaml"
    reg_path.write_text(yaml.dump(reg))

    async def go():
        engine = AiBrarianEngine(reg_path)
        await engine.initialize()
        await engine.register_cartridge("test_pp", LUN_PATH)
        # Now run a semantic search through the public API
        results = await engine.search("test_pp", "Balinese water temples", limit=5, mode="semantic")
        await engine.shutdown()
        return results

    results = asyncio.run(go())
    print(f"results: {len(results)}")
    for r in results[:3]:
        print(f"  score={r.get('score', '?'):.3f}  {r.get('snippet', '')[:80]}")
PY
```

**Expected:** `results: <nonzero>`, with snippets containing Balinese / Bali / water temple keywords. (If the cartridge contains material on Balinese subak systems, those are the highest-scoring chunks.)

If `results: 0`, something is still wrong — likely the embedding generator isn't actually producing vectors. Check `_EmbeddingGenerator._load_model()` in [`aibrarian_engine.py`](../src/luna/substrate/aibrarian_engine.py) and verify whatever `embedding_model` it's loading is actually installed and usable. (See [`HANDOFF_AIBRARIAN_EMBEDDING_PIPELINE.md`](HANDOFF_AIBRARIAN_EMBEDDING_PIPELINE.md) for the parallel issue with the generator returning None — that handoff covers a different layer of the same overall semantic-search problem.)

---

## What this fix does NOT do

Listed so the next session doesn't accidentally mission-creep:

- **Doesn't** wire fallback writes for the `_chunk_embeddings` query sites at lines 1149, 1156, 1175, 2014, 2025. Those are doc-level embedding helpers used by ranking and dedup. They will need similar treatment in a follow-up but cartridge semantic search via `_vec_search` does not depend on them.
- **Doesn't** populate the `entities` or `extractions` tables. Entity extraction is a separate pipeline (Scribe / Librarian actors per the engine spec). Out of scope.
- **Doesn't** populate `cartridge_meta`. That's metadata tracking for which cartridges are loaded into a collection — orthogonal to embedding storage. Out of scope.
- **Doesn't** make `sqlite-vec` itself work. The OS sqlite3 build can't load extensions, period; that's a Python-build-time decision. The fallback is the path forward unless/until Forge migrates to a Python with `--enable-loadable-sqlite-extensions` (homebrew Python likely qualifies — but switching the build host Python is a much bigger plumbing change and would also need every Luna dep installed there).
- **Doesn't** rebuild the hai-dai ambassador binary. Checkpoint D is optional; the user will likely run the full rebuild themselves once this fix lands.

---

## Files touched

| File | Change |
|---|---|
| [`src/luna/substrate/vec_fallback.py`](../src/luna/substrate/vec_fallback.py) | Add `store()` method to `AiBrarianFallbackVec` (~25 lines) |
| [`src/luna/substrate/aibrarian_engine.py`](../src/luna/substrate/aibrarian_engine.py) | Wire `_embed_chunks` (~15 line diff) and `register_cartridge` (~15 line diff) to use fallback when `_vec_loaded` is False |

No new files. No new dependencies. No profile changes. No Forge changes.

---

## Return to original session

Once Checkpoints A–C are committed (Checkpoint D optional), report back to the user with:

1. The three commit hashes
2. The Checkpoint C verification output (showing `chunk_embeddings_fallback > 0` in the test DB)
3. Whether you ran Checkpoint D (full build) or skipped it

The user will then continue in the original session: full hai-dai rebuild with both arch targets, verify the bundled DB, ship.
