# HANDOFF: Data Room Extraction Pipeline

**Date:** 2026-02-27
**Author:** Ahab (via Claude facilitator session)
**For:** Claude Code
**Priority:** HIGH — blocks data room completeness for ROSA demo

---

## EXECUTIVE SUMMARY

Wire `ingest_dataroom.py` to trigger the Scribe (Ben Franklin) extraction pipeline on document ingestion. Add document chunking, similarity search, and co-occurrence search to the Memory Matrix. All work stays within the existing sqlite-vec + FTS5 stack. No new dependencies.

**Reference implementation:** `/Volumes/ZDrive-1/DatabaseProject/` contains a fully working legal document search system with the same patterns. **DO NOT depend on ZDrive-1 at runtime** — it's an external drive that may be disconnected. Copy any needed reference code into the project. The ZDrive code uses FAISS; we use sqlite-vec. Same concepts, different backend.

---

## WHAT EXISTS TODAY

### Ingestion Pipeline (`scripts/ingest_dataroom.py`)
- Reads file index (Google Sheets or local FILE_MAP)
- Creates/updates DOCUMENT nodes in Memory Matrix
- Tracks `last_modified` timestamp to skip unchanged files
- Creates CATEGORY nodes, links DOCUMENT → CATEGORY via `BELONGS_TO` edges
- Has `--local` mode for local filesystem ingestion
- **Does NOT read file contents or trigger extraction**

### Scribe Actor (`src/luna/actors/scribe.py`)
- `extract_text` message type: accepts raw text + source_id, chunks it, extracts FACT/DECISION/PROBLEM/etc nodes
- `extract_turn` message type: same but for conversation turns
- Sends extractions to Librarian via `file` message
- Sends entity updates via `entity_update` message
- Has `SemanticChunker` for splitting text into chunks
- Uses Claude API (Haiku by default) for extraction
- **Already fully implemented and tested**

### Memory Matrix (`src/luna/substrate/memory.py`)
- CRUD for memory nodes (FACT, DECISION, DOCUMENT, etc.)
- FTS5 keyword search
- sqlite-vec for vector similarity search
- `EmbeddingStore` + `EmbeddingGenerator` (local MiniLM, 384 dims)
- Graph edges between nodes
- **Has vector search but no document-level similarity API**

### Data Room Folder Structure
- Root: `/Users/zayneamason/_HeyLuna_BETA/LUNA-DATAROOM/`
- 9 numbered folders (01_Company_Overview through 09_Financials)
- Each folder has INDEX.md with checklist of needed documents

---

## TASK 1: Wire Ingestion → Extraction

### What to Change

In `scripts/ingest_dataroom.py`, after a DOCUMENT node is created or updated, read the actual file content and send it to the Scribe for extraction.

### Implementation

Add a new function `extract_document_content()`:

```python
async def extract_document_content(
    matrix: MemoryMatrix,
    graph: MemoryGraph,
    node_id: str,
    file_path: Path,
    force: bool = False,
):
    """
    Read document content and trigger Scribe extraction.
    
    1. Read file content (supports .md, .txt, .pdf, .docx)
    2. Delete any existing extracted nodes linked to this DOCUMENT
    3. Chunk the content
    4. Extract FACT/INSIGHT/DECISION nodes via Scribe
    5. Link extracted nodes back to DOCUMENT via 'extracted_from' edge
    """
    # Step 1: Read content
    content = read_file_content(file_path)
    if not content or len(content.strip()) < 50:
        logger.info(f"Skipping extraction for {file_path.name} (too short)")
        return
    
    # Step 2: Delete old extractions (latest-wins versioning)
    old_nodes = await matrix.db.fetchall(
        "SELECT id FROM memory_nodes WHERE source = ?",
        (f"extracted_from:{node_id}",)
    )
    for row in old_nodes:
        await matrix.delete_node(row[0])
    if old_nodes:
        logger.info(f"Deleted {len(old_nodes)} stale extractions for {node_id}")
    
    # Step 3: Chunk the content
    chunks = chunk_document(content, chunk_size=500, overlap=50)
    
    # Step 4: Extract via Scribe
    # Option A: Direct Scribe call (if engine is running)
    # Option B: Inline extraction using same prompt (standalone script)
    for chunk in chunks:
        extraction = await extract_chunk(chunk, source_id=f"extracted_from:{node_id}")
        
        # Step 5: Store extracted nodes + link to DOCUMENT
        for obj in extraction.objects:
            fact_id = await matrix.add_node(
                node_type=obj.type,
                content=obj.content,
                source=f"extracted_from:{node_id}",
                confidence=obj.confidence,
                importance=0.7,
                metadata={"source_document": node_id, "chunk_index": chunk.index},
                scope="global",
            )
            # Edge: FACT --extracted_from--> DOCUMENT
            await graph.add_edge(
                from_id=fact_id,
                to_id=node_id,
                relationship="extracted_from",
                strength=1.0,
                scope="global",
            )
```

### File Reading Support

```python
def read_file_content(file_path: Path) -> str:
    """Read document content. Supports common formats."""
    suffix = file_path.suffix.lower()
    
    if suffix in ('.md', '.txt', '.csv'):
        return file_path.read_text(encoding='utf-8')
    
    elif suffix == '.pdf':
        # Use pdftotext (already available via homebrew)
        import subprocess
        result = subprocess.run(
            ['pdftotext', str(file_path), '-'],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            return result.stdout
        # OCR fallback
        return ocr_pdf(file_path)
    
    elif suffix == '.docx':
        # Use python-docx or pandoc
        import subprocess
        result = subprocess.run(
            ['pandoc', str(file_path), '-t', 'plain'],
            capture_output=True, text=True
        )
        return result.stdout if result.returncode == 0 else ""
    
    else:
        logger.warning(f"Unsupported file type: {suffix}")
        return ""
```

### Versioning Strategy: Latest-Wins

When a document's `last_modified` changes:
1. `ingest_dataroom.py` updates the DOCUMENT node (already works)
2. Delete all nodes where `source = "extracted_from:{doc_node_id}"`
3. Re-run extraction on the updated file content
4. Create fresh FACT/INSIGHT nodes linked to the DOCUMENT

This is clean-swap versioning. No history tracking needed for the data room use case — investors always see current state.

### Integration Point

In the existing `process_document()` function, add extraction trigger after create/update:

```python
# After line ~287 (node created) or ~264 (node updated):
if action in ("created", "updated") and not dry_run:
    # Resolve local file path from metadata
    local_path = resolve_local_path(row)
    if local_path and local_path.exists():
        await extract_document_content(matrix, graph, node_id, local_path, force)
```

### CLI Flag

Add `--no-extract` flag to skip extraction (useful for quick metadata-only syncs):

```python
parser.add_argument("--no-extract", action="store_true", help="Skip content extraction")
```

---

## TASK 2: Document Chunking for Memory Matrix

### What to Build

A standalone chunker module that works with Memory Matrix. Adapted from the proven pattern in `/Volumes/ZDrive-1/DatabaseProject/database/fts_index.py`.

### Location

`src/luna/substrate/chunker.py` (new file)

### Implementation

```python
"""
Document chunking for Memory Matrix.

Splits documents into overlapping chunks with sentence boundary preservation.
Used by ingestion pipeline and Scribe extraction.

Reference: /Volumes/ZDrive-1/DatabaseProject/database/fts_index.py
(adapted from FAISS pipeline to work with sqlite-vec)
"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class DocumentChunk:
    """A chunk of document text with position metadata."""
    text: str
    index: int
    start_char: int
    end_char: int
    source_id: str = ""
    word_count: int = 0


# Sentence boundary pattern
SENTENCE_BOUNDARY = re.compile(r'(?<=[.!?])\s+(?=[A-Z])')


def chunk_document(
    text: str,
    chunk_size: int = 500,       # words per chunk
    overlap: int = 50,            # word overlap between chunks
    source_id: str = "",
    preserve_sentences: bool = True,
) -> list[DocumentChunk]:
    """
    Split document text into overlapping chunks.
    
    Args:
        text: Full document text
        chunk_size: Target words per chunk
        overlap: Word overlap between consecutive chunks
        source_id: Source identifier for tracking
        preserve_sentences: If True, adjust chunk boundaries to
                          avoid splitting mid-sentence
    
    Returns:
        List of DocumentChunk objects
    """
    words = text.split()
    if not words:
        return []
    
    chunks = []
    start_word = 0
    chunk_index = 0
    
    while start_word < len(words):
        end_word = min(start_word + chunk_size, len(words))
        
        # Sentence boundary preservation
        if preserve_sentences and end_word < len(words):
            # Look backwards from end_word for a sentence boundary
            chunk_text = ' '.join(words[start_word:end_word])
            boundaries = list(SENTENCE_BOUNDARY.finditer(chunk_text))
            
            if boundaries:
                # Use the last sentence boundary within the chunk
                last_boundary = boundaries[-1]
                boundary_pos = last_boundary.start()
                # Count words up to that boundary
                words_to_boundary = len(chunk_text[:boundary_pos].split())
                if words_to_boundary > chunk_size * 0.6:  # Don't make chunks too small
                    end_word = start_word + words_to_boundary
        
        chunk_words = words[start_word:end_word]
        chunk_text = ' '.join(chunk_words)
        
        # Calculate character positions
        start_char = len(' '.join(words[:start_word])) + (1 if start_word > 0 else 0)
        end_char = start_char + len(chunk_text)
        
        chunks.append(DocumentChunk(
            text=chunk_text,
            index=chunk_index,
            start_char=start_char,
            end_char=end_char,
            source_id=source_id,
            word_count=len(chunk_words),
        ))
        
        chunk_index += 1
        
        if end_word >= len(words):
            break
        start_word = end_word - overlap
    
    # Edge case: text shorter than chunk_size
    if not chunks:
        chunks.append(DocumentChunk(
            text=text,
            index=0,
            start_char=0,
            end_char=len(text),
            source_id=source_id,
            word_count=len(words),
        ))
    
    return chunks
```

### Where It Gets Used

1. **Ingestion pipeline** — chunk documents before extraction
2. **Embedding generation** — embed chunks, not full documents
3. **FTS5 indexing** — chunks go into the FTS5 search index for better snippet generation

---

## TASK 3: Document Similarity Search

### What to Build

API endpoint + Memory Matrix method to find documents similar to a given document. Uses sqlite-vec embeddings that already exist.

### Reference

`/Volumes/ZDrive-1/DatabaseProject/api/routes/similarity.py` — same concept, adapted from FAISS to sqlite-vec.

### Location

Add to `src/luna/substrate/memory.py` (MemoryMatrix class):

```python
async def find_similar_documents(
    self,
    node_id: str,
    limit: int = 10,
    min_similarity: float = 0.3,
) -> list[dict]:
    """
    Find documents similar to the given node.
    
    Uses averaged chunk embeddings for document-level comparison.
    Works for any node type, but most useful for DOCUMENT nodes.
    
    Returns:
        List of {node_id, content, similarity, node_type} dicts
    """
    # Get embedding for the source node
    source_embedding = await self.embeddings.get_embedding(node_id)
    if source_embedding is None:
        return []
    
    # Search for similar embeddings
    results = await self.embeddings.search(
        source_embedding,
        limit=limit + 1,  # +1 to exclude self
        min_similarity=min_similarity,
    )
    
    # Filter out self and enrich with node data
    similar = []
    for result_node_id, similarity in results:
        if result_node_id == node_id:
            continue
        
        node = await self.get_node(result_node_id)
        if node:
            similar.append({
                "node_id": result_node_id,
                "content": node.content,
                "summary": node.summary,
                "node_type": node.node_type,
                "similarity": round(similarity, 4),
            })
        
        if len(similar) >= limit:
            break
    
    return similar
```

### Batch Similarity

For comparing document clusters (e.g., "how similar are all docs in 09_Financials?"):

```python
async def batch_similarity(
    self,
    node_ids: list[str],
) -> list[dict]:
    """
    Compute pairwise similarity between a set of nodes.
    
    Returns:
        List of {node_a, node_b, similarity} dicts, sorted by similarity desc
    """
    # Collect embeddings
    embeddings = {}
    for nid in node_ids:
        emb = await self.embeddings.get_embedding(nid)
        if emb is not None:
            embeddings[nid] = emb
    
    # Compute pairwise cosine similarity
    pairs = []
    ids = list(embeddings.keys())
    for i, id_a in enumerate(ids):
        for id_b in ids[i+1:]:
            # Dot product of normalized vectors = cosine similarity
            sim = sum(a * b for a, b in zip(embeddings[id_a], embeddings[id_b]))
            pairs.append({
                "node_a": id_a,
                "node_b": id_b,
                "similarity": round(sim, 4),
            })
    
    pairs.sort(key=lambda p: p["similarity"], reverse=True)
    return pairs
```

### API Endpoints

Add to `src/luna/api/server.py`:

```python
@app.get("/api/similar/{node_id}")
async def find_similar(node_id: str, limit: int = 10):
    """Find nodes similar to the given node."""
    results = await matrix.find_similar_documents(node_id, limit=limit)
    return {"source": node_id, "similar": results, "count": len(results)}

@app.post("/api/similarity/batch")
async def batch_sim(node_ids: list[str]):
    """Pairwise similarity between nodes."""
    pairs = await matrix.batch_similarity(node_ids)
    return {"documents": node_ids, "pairs": pairs, "count": len(pairs)}
```

### MCP Tool

Add to `src/luna_mcp/server.py` or `src/luna/tools/dataroom_tools.py`:

```python
@mcp_tool
async def dataroom_similar(node_id: str, limit: int = 5) -> str:
    """Find data room documents similar to a given document."""
    results = await matrix.find_similar_documents(node_id, limit=limit)
    # Format for Luna's response
    ...
```

---

## TASK 4: Co-occurrence Search

### What to Build

FTS5 query that finds documents containing ALL specified terms. Pure keyword search, no vectors needed.

### Reference

`/Volumes/ZDrive-1/DatabaseProject/search.py` — `co_occurrence()` function.

### Location

Add to `src/luna/substrate/memory.py` (MemoryMatrix class):

```python
async def co_occurrence_search(
    self,
    terms: list[str],
    node_type: str = None,
    limit: int = 20,
) -> list[dict]:
    """
    Find nodes containing ALL specified terms.
    
    Uses FTS5 boolean AND query. Useful for:
    - "Which docs mention both Kinoni AND budget?"
    - "Find nodes about Rotary AND grant"
    
    Args:
        terms: List of terms that must ALL appear
        node_type: Optional filter (e.g., "DOCUMENT", "FACT")
        limit: Max results
    
    Returns:
        List of matching nodes with snippets
    """
    if not terms:
        return []
    
    # Build FTS5 AND query
    fts_query = " AND ".join(f'"{t}"' for t in terms)
    
    type_filter = ""
    params = [fts_query, limit]
    if node_type:
        type_filter = "AND mn.node_type = ?"
        params = [fts_query, node_type, limit]
    
    rows = await self.db.fetchall(f"""
        SELECT
            mn.id,
            mn.node_type,
            mn.content,
            mn.summary,
            snippet(memory_fts, 0, '>>>', '<<<', '...', 32) as snippet,
            bm25(memory_fts) as score
        FROM memory_fts
        JOIN memory_nodes mn ON memory_fts.rowid = mn.rowid
        WHERE memory_fts MATCH ?
        {type_filter}
        ORDER BY score
        LIMIT ?
    """, tuple(params))
    
    return [
        {
            "node_id": row[0],
            "node_type": row[1],
            "content": row[2],
            "summary": row[3],
            "snippet": row[4],
            "score": -row[5],  # BM25 returns negative
        }
        for row in rows
    ]
```

### MCP Tool

```python
@mcp_tool
async def dataroom_co_occurrence(terms: str, node_type: str = None) -> str:
    """
    Find documents containing ALL specified terms.
    Terms should be comma-separated.
    Example: "Kinoni, budget, solar"
    """
    term_list = [t.strip() for t in terms.split(",")]
    results = await matrix.co_occurrence_search(term_list, node_type=node_type)
    # Format for Luna's response
    ...
```

---

## TASK 5: Embed Document Chunks at Ingestion

### What to Change

Currently, Memory Matrix embeds individual nodes by their `content` field. For DOCUMENT nodes, the content is just the filename + notes — not the actual document text. The extracted FACT nodes get their own embeddings, which is good, but we also want chunk-level embeddings for the document itself.

### Implementation

During ingestion, after chunking the document:

```python
async def embed_document_chunks(
    matrix: MemoryMatrix,
    node_id: str,
    chunks: list[DocumentChunk],
):
    """
    Generate and store embeddings for document chunks.
    
    Each chunk gets embedded independently. The document's 
    overall embedding is the average of its chunk embeddings.
    """
    generator = matrix.embedding_generator
    
    # Embed all chunks
    texts = [chunk.text for chunk in chunks]
    embeddings = await generator.generate_batch(texts)
    
    # Store chunk embeddings with composite IDs
    for chunk, embedding in zip(chunks, embeddings):
        chunk_id = f"{node_id}:chunk:{chunk.index}"
        await matrix.embeddings.store(chunk_id, embedding)
    
    # Store document-level embedding (average of chunks)
    import numpy as np
    doc_embedding = np.mean(embeddings, axis=0).tolist()
    await matrix.embeddings.store(node_id, doc_embedding)
```

### Where in the Pipeline

```
File detected (new/updated)
    → DOCUMENT node created/updated (existing)
    → File content read
    → Chunked (Task 2)
    → Chunks embedded (Task 5)
    → Chunks extracted via Scribe (Task 1)
    → FACT nodes created with edges to DOCUMENT
    → FACT nodes get their own embeddings (existing behavior)
```

---

## VERIFICATION

### Test Commands

```bash
# 1. Run ingestion with extraction
python scripts/ingest_dataroom.py --local --force

# 2. Check DOCUMENT nodes exist
# Via MCP: dataroom_status

# 3. Check FACT nodes were extracted
# Via MCP: memory_matrix_search(query="revenue projection")

# 4. Check edges exist
# Via MCP: memory_matrix_get_context(node_id="<document_node_id>")

# 5. Test similarity search
# Via MCP: dataroom_similar(node_id="<document_node_id>")

# 6. Test co-occurrence
# Via MCP: dataroom_co_occurrence(terms="Kinoni, solar, budget")

# 7. Test versioning — edit a file, re-run ingestion
# Old FACT nodes should be deleted, new ones created
```

### Success Criteria

1. `ingest_dataroom.py --local` creates DOCUMENT nodes AND extracted FACT nodes
2. FACT nodes link back to DOCUMENT via `extracted_from` edges
3. Re-running ingestion on modified files replaces old extractions (latest-wins)
4. `dataroom_similar` returns semantically related documents
5. `dataroom_co_occurrence` finds nodes with all specified terms
6. `luna_smart_fetch` returns extracted facts (not just document metadata)
7. **No dependency on `/Volumes/ZDrive-1/`** — all code is self-contained

---

## FILE MAP

| File | Action | Description |
|------|--------|-------------|
| `scripts/ingest_dataroom.py` | MODIFY | Add extraction trigger after create/update |
| `src/luna/substrate/chunker.py` | CREATE | Document chunking module |
| `src/luna/substrate/memory.py` | MODIFY | Add `find_similar_documents`, `batch_similarity`, `co_occurrence_search` |
| `src/luna/substrate/embeddings.py` | MODIFY | Add `get_embedding` if missing (needed for similarity) |
| `src/luna/api/server.py` | MODIFY | Add `/api/similar/`, `/api/similarity/batch` endpoints |
| `src/luna_mcp/server.py` | MODIFY | Add `dataroom_similar`, `dataroom_co_occurrence` MCP tools |
| `src/luna/tools/dataroom_tools.py` | MODIFY | Wire new tools to MCP |

## REFERENCE CODE (ZDrive-1)

These files contain proven patterns. **Copy logic, not code** — adapt to sqlite-vec:

| ZDrive File | What to Learn |
|-------------|---------------|
| `DatabaseProject/database/fts_index.py` | Chunking: `chunk_text()` function |
| `DatabaseProject/database/vector_store.py` | Embedding pipeline: batch encode → store → search |
| `DatabaseProject/api/routes/similarity.py` | Document similarity API: single + batch |
| `DatabaseProject/api/routes/search.py` | Hybrid search with RRF fusion |
| `DatabaseProject/api/routes/entities.py` | Entity extraction patterns (regex + known lists) |
| `DatabaseProject/search.py` | CLI: co-occurrence, interactive mode |
| `PT_DatabaseProject/schema.sql` | Graph schema: entities, connections, claims, gaps |
| `PT_DatabaseProject/search.py` | Network traversal, investigation gap tracking |

---

## NON-NEGOTIABLES

1. **Everything stays in one SQLite file** — sovereignty model. No FAISS, no external index files.
2. **sqlite-vec for vectors** — already integrated, already works.
3. **Offline-first** — extraction can use Claude API but must gracefully degrade if offline.
4. **No ZDrive dependency** — ZDrive-1 is reference only. All runtime code lives in the project.
5. **Latest-wins versioning** — re-extraction replaces old nodes. No history tracking needed.
6. **Scribe's extraction prompt stays unchanged** — don't modify `scribe.py`'s extraction logic, just call it.
