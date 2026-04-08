# HANDOFF: Nexus Structural Extraction Pipeline

**Priority:** P1 — This is the "real fix" for document navigation  
**Status:** Ready for implementation  
**Target file:** `src/luna/substrate/aibrarian_engine.py`  
**Secondary:** `src/luna/substrate/aibrarian_schema.py`  
**Scope:** Ingestion pipeline only. No changes to recall, no changes to frontend.

---

## THE PROBLEM

When Luna ingests a document (e.g., an 80,000-word academic book), the pipeline:

1. Reads the file as flat text via `pdftotext` — all structure lost
2. Chunks by word count (500 words, 50 overlap) — no awareness of chapters
3. Sends batches of 5 chunks to Haiku — Haiku has no idea what chapter it's looking at
4. Stores extractions with `chunk_index` but zero structural metadata

Result: When a user asks "What is Chapter 2 about?", FTS5 searches for "chapter 2" across extractions and chunks. Since no extraction or chunk contains the literal text "Chapter 2" as a tagged label, it returns nothing. Luna correctly says "I don't have enough detail" — because the structure was thrown away at step 1.

## THE FIX — Three Changes

### Change 1: Structure Detection Function

Add a new function `detect_document_structure()` in `aibrarian_engine.py` (after `chunk_document()`, before `read_file_content()`).

This function takes the raw text from `read_file_content()` and returns a list of structural markers — chapter/section boundaries with their character offsets.

```python
@dataclass
class StructuralMarker:
    """A detected chapter or section boundary in a document."""
    heading: str          # "Chapter 2: The Powers of Water"
    level: int            # 1 = chapter, 2 = section, 3 = subsection
    start_char: int       # Character offset where this section begins
    end_char: int         # Character offset where next section begins (or end of doc)
    page_hint: str = ""   # Page number if detected (e.g., "37")


# Common heading patterns for structure detection
STRUCTURE_PATTERNS = [
    # "Chapter 1: Title" or "CHAPTER 1" or "Chapter One"
    re.compile(
        r"^(?:CHAPTER|Chapter)\s+(\d+|[A-Z][a-z]+)(?:\s*[:.]\s*(.+))?$",
        re.MULTILINE,
    ),
    # "1. Title" or "I. Title" (numbered sections at line start)
    re.compile(
        r"^(\d+|[IVXLC]+)\.\s+([A-Z][A-Za-z\s:]+)$",
        re.MULTILINE,
    ),
    # "Part I" / "Part 1"
    re.compile(
        r"^(?:PART|Part)\s+(\d+|[IVXLC]+)(?:\s*[:.]\s*(.+))?$",
        re.MULTILINE,
    ),
    # "Introduction" / "Conclusion" / "Preface" / "Epilogue" (standalone)
    re.compile(
        r"^(Introduction|Conclusion|Preface|Epilogue|Foreword|Afterword|Appendix(?:\s+[A-Z])?)(?:\s*[:.]\s*(.+))?$",
        re.MULTILINE,
    ),
    # ALL CAPS heading on its own line (≤ 60 chars, ≥ 3 words or known pattern)
    re.compile(
        r"^([A-Z][A-Z\s]{4,60})$",
        re.MULTILINE,
    ),
]

# Page number patterns (pdftotext often inserts these)
PAGE_NUMBER_PATTERN = re.compile(r"^\s*(\d{1,4})\s*$", re.MULTILINE)


def detect_document_structure(text: str) -> list[StructuralMarker]:
    """
    Detect chapter/section structure from document text.
    
    Scans for heading patterns and returns ordered list of
    structural markers with character offsets. Works best with
    text extracted via pdftotext which preserves line breaks.
    
    Returns empty list if no structure detected (short docs, etc.)
    """
    if len(text) < 5000:
        return []  # Too short to have meaningful structure
    
    markers: list[StructuralMarker] = []
    
    for pattern in STRUCTURE_PATTERNS:
        for match in pattern.finditer(text):
            heading = match.group(0).strip()
            start = match.start()
            
            # Determine level
            full = heading.lower()
            if full.startswith(("chapter", "part")):
                level = 1
            elif full.startswith(("introduction", "conclusion", "preface",
                                  "epilogue", "foreword", "afterword", "appendix")):
                level = 1
            elif heading.isupper():
                level = 2
            else:
                level = 2
            
            # Find nearest page number (look backward up to 200 chars)
            page_hint = ""
            lookback = text[max(0, start - 200):start]
            page_matches = list(PAGE_NUMBER_PATTERN.finditer(lookback))
            if page_matches:
                page_hint = page_matches[-1].group(1)
            
            markers.append(StructuralMarker(
                heading=heading,
                level=level,
                start_char=start,
                end_char=len(text),  # Will be corrected below
                page_hint=page_hint,
            ))
    
    if not markers:
        return []
    
    # Sort by position, deduplicate overlapping matches
    markers.sort(key=lambda m: m.start_char)
    
    # Remove duplicates (overlapping patterns matching same heading)
    deduped: list[StructuralMarker] = []
    for m in markers:
        if deduped and abs(m.start_char - deduped[-1].start_char) < 50:
            # Keep the one with more specific level
            if m.level < deduped[-1].level:
                deduped[-1] = m
            continue
        deduped.append(m)
    
    # Set end_char to next marker's start
    for i in range(len(deduped) - 1):
        deduped[i].end_char = deduped[i + 1].start_char
    # Last marker extends to end of document (already set)
    
    return deduped
```

### Change 2: Tag Chunks With Structure

Modify `chunk_document()` to accept an optional `structure` parameter and tag each chunk with its structural location.

**Schema change in `aibrarian_schema.py`:**

Add `section_label` and `section_level` columns to the `chunks` table:

```sql
-- In STANDARD_SCHEMA, modify chunks table:
CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,
    doc_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    word_count INTEGER,
    start_char INTEGER,
    end_char INTEGER,
    section_label TEXT,          -- NEW: "Chapter 2: The Powers of Water"
    section_level INTEGER,       -- NEW: 1=chapter, 2=section, 3=subsection
    FOREIGN KEY (doc_id) REFERENCES documents(id) ON DELETE CASCADE
);
```

Also add `section_label` to `chunks_fts`:

```sql
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    chunk_text,
    section_label,              -- NEW: searchable section label
    content='chunks',
    content_rowid='rowid'
);

-- Updated triggers must include section_label:
CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
    INSERT INTO chunks_fts(rowid, chunk_text, section_label)
    VALUES (new.rowid, new.chunk_text, COALESCE(new.section_label, ''));
END;
CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, chunk_text, section_label)
    VALUES ('delete', old.rowid, old.chunk_text, COALESCE(old.section_label, ''));
END;
CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, chunk_text, section_label)
    VALUES ('delete', old.rowid, old.chunk_text, COALESCE(old.section_label, ''));
    INSERT INTO chunks_fts(rowid, chunk_text, section_label)
    VALUES (new.rowid, new.chunk_text, COALESCE(new.section_label, ''));
END;
```

**Modify `DocumentChunk` dataclass:**

```python
@dataclass
class DocumentChunk:
    """A chunk of a document for indexing and embedding."""
    text: str
    index: int
    start_char: int
    end_char: int
    source_id: str = ""
    word_count: int = 0
    section_label: str = ""      # NEW
    section_level: int = 0       # NEW
```

**Modify `chunk_document()` signature:**

```python
def chunk_document(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50,
    source_id: str = "",
    preserve_sentences: bool = True,
    structure: list[StructuralMarker] | None = None,  # NEW
) -> list[DocumentChunk]:
```

**Inside the `while start_word < len(words):` loop**, after creating each `DocumentChunk`, add:

```python
        # Tag chunk with structural section
        if structure:
            for marker in reversed(structure):
                if chunk.start_char >= marker.start_char:
                    chunk.section_label = marker.heading
                    chunk.section_level = marker.level
                    break
```

**Update the INSERT in `ingest()`** to include new columns:

```python
        for chunk in chunks:
            chunk_id = f"{doc_id}:chunk:{chunk.index}"
            conn.conn.execute(
                """
                INSERT INTO chunks
                    (id, doc_id, chunk_index, chunk_text, word_count,
                     start_char, end_char, section_label, section_level)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk_id,
                    doc_id,
                    chunk.index,
                    chunk.text,
                    chunk.word_count,
                    chunk.start_char,
                    chunk.end_char,
                    chunk.section_label,
                    chunk.section_level,
                ),
            )
```

### Change 3: Structure-Aware Extraction Prompt

Modify the `extract()` method to pass structural context to Haiku.

In `extract()`, after fetching chunk rows but before building batches, add:

```python
        # Build section label lookup from chunks
        section_rows = conn.conn.execute(
            "SELECT chunk_index, section_label FROM chunks "
            "WHERE doc_id = ? AND section_label IS NOT NULL "
            "ORDER BY chunk_index",
            (doc_id,),
        ).fetchall()
        section_lookup = {r["chunk_index"]: r["section_label"] for r in section_rows}
```

Then modify the user message construction inside the batch loop:

```python
            # Determine section context for this batch
            batch_section = ""
            for ci in chunk_indices:
                if ci in section_lookup:
                    batch_section = section_lookup[ci]
                    break
            # If no direct match, find nearest preceding section
            if not batch_section and section_lookup:
                preceding = [
                    (idx, label) for idx, label in section_lookup.items()
                    if idx <= chunk_indices[0]
                ]
                if preceding:
                    batch_section = max(preceding, key=lambda x: x[0])[1]
            
            section_hint = (
                f"\n\nDOCUMENT LOCATION: This text is from \"{batch_section}\".\n"
                f"Include this section name in your summary.\n"
                if batch_section else ""
            )

            user_msg = (
                (
                    "This is the OPENING section of the document. "
                    "Provide a thorough summary of the document's subject, "
                    "scope, and main argument as best you can determine. "
                    "Also extract claims and entities.\n\n"
                )
                if is_first
                else f"Extract knowledge from this section of the document:{section_hint}\n\n"
            ) + batch_text
```

**Also store section_label on extractions via metadata field.** Change extraction INSERTs from:

```python
conn.conn.execute(
    "INSERT OR REPLACE INTO extractions "
    "(id, doc_id, chunk_index, node_type, content, confidence) "
    "VALUES (?, ?, ?, ?, ?, ?)",
    (ext_id, doc_id, chunk_ref, node_type, summary, 0.9),
)
```

To:

```python
ext_metadata = json.dumps({"section": batch_section}) if batch_section else None
conn.conn.execute(
    "INSERT OR REPLACE INTO extractions "
    "(id, doc_id, chunk_index, node_type, content, confidence, metadata) "
    "VALUES (?, ?, ?, ?, ?, ?, ?)",
    (ext_id, doc_id, chunk_ref, node_type, summary, 0.9, ext_metadata),
)
```

Do the same for CLAIM insertions.

### Change 4 (Bonus): TABLE_OF_CONTENTS Extraction

In `ingest()`, after structure detection and before calling `extract()`, generate a synthetic extraction:

```python
        # Generate TABLE_OF_CONTENTS extraction from structure
        if structure:
            toc_lines = []
            for marker in structure:
                indent = "  " * (marker.level - 1)
                page = f" (p. {marker.page_hint})" if marker.page_hint else ""
                toc_lines.append(f"{indent}{marker.heading}{page}")
            
            toc_content = "Document Structure:\n" + "\n".join(toc_lines)
            toc_id = f"{doc_id}:ext:toc:0"
            conn.conn.execute(
                "INSERT OR REPLACE INTO extractions "
                "(id, doc_id, chunk_index, node_type, content, confidence) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (toc_id, doc_id, 0, "TABLE_OF_CONTENTS", toc_content, 1.0),
            )
            conn.conn.commit()
```

---

## WIRE IT INTO `ingest()`

The modified `ingest()` flow becomes:

```python
    async def ingest(self, collection, file_path, metadata=None):
        # ... existing steps 1-2 (read file, create document record) ...
        
        # 2.5 NEW: Detect structure
        structure = detect_document_structure(content)
        if structure:
            logger.info(
                "Detected %d structural markers in %s",
                len(structure), file_path.name,
            )
        
        # ... existing step 3 (delete old chunks/extractions) ...
        
        # 4. Chunk — NOW with structure
        chunks = chunk_document(
            content,
            chunk_size=conn.config.chunk_size,
            overlap=conn.config.chunk_overlap,
            source_id=doc_id,
            structure=structure,  # NEW
        )
        
        # ... existing step 4 INSERT (updated to include section_label, section_level) ...
        
        # 4.5 NEW: Generate TOC extraction from structure
        # (see Change 4 above)
        
        # ... existing steps 5-6 (embed, extract) ...
```

---

## SCHEMA MIGRATION

Existing databases won't have `section_label` or `section_level` columns.

**Recommended:** Delete the DB and re-ingest. The `_create_database()` method uses the schema from `aibrarian_schema.py`, so new DBs get the columns automatically. This is what we've been doing for research_library.

---

## DO NOT

- Do NOT modify `_get_collection_context()` — the recall pipeline works fine; it just needs better data
- Do NOT modify the MCP tool definitions — they pass through to the engine
- Do NOT modify the extraction prompt JSON schema — Haiku's format works
- Do NOT add an LLM call for structure detection — regex is sufficient and free
- Do NOT try to detect structure from PDFs via page layout analysis — `pdftotext` line breaks are enough
- Do NOT add a separate "structural extraction" phase that runs independently — wire into existing `ingest()` flow

---

## VERIFICATION

After implementation, test with:

```bash
# 1. Delete old DB
rm data/local/research_library.db

# 2. Restart backend with venv
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
.venv/bin/python scripts/run.py --server --host 0.0.0.0 --port 8000

# 3. Re-ingest Priests & Programmers
curl -X POST http://localhost:8000/api/nexus/ingest \
  -H "Content-Type: application/json" \
  -d '{"collection": "research_library", "file_path": "/path/to/priests_and_programmers.pdf"}'

# 4. Verify structure detection
sqlite3 data/local/research_library.db "
  SELECT DISTINCT section_label FROM chunks
  WHERE section_label IS NOT NULL
  ORDER BY chunk_index;
"
# Expected: Chapter headings, Introduction, Conclusion, etc.

# 5. Verify TOC extraction
sqlite3 data/local/research_library.db "
  SELECT content FROM extractions
  WHERE node_type = 'TABLE_OF_CONTENTS';
"
# Expected: Structured list of chapters with page numbers

# 6. Verify FTS5 matches "chapter 2"
sqlite3 data/local/research_library.db "
  SELECT c.section_label, substr(c.chunk_text, 1, 80)
  FROM chunks_fts
  JOIN chunks c ON chunks_fts.rowid = c.rowid
  WHERE chunks_fts MATCH 'chapter 2'
  LIMIT 3;
"
# Expected: Chunks tagged with Chapter 2 heading

# 7. Ask Luna through UI: "What is Chapter 2 about?"
# Should now return a grounded answer about The Powers of Water
```

---

## ESTIMATED SCOPE

- ~150 lines new code (structure detection function + dataclass)
- ~30 lines schema changes (2 columns + FTS5 update)
- ~40 lines modifications to existing functions (ingest, chunk_document, extract)
- Zero new dependencies
- Zero API changes
- Zero frontend changes
